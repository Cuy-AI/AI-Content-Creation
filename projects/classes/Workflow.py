import os
import json
import asyncio
from pathlib import Path
from functools import wraps
from typing import Callable, Union, List, Dict, Any

from prefect import get_run_logger
from prefect.serializers import Serializer
from prefect.filesystems import LocalFileSystem


# TEMPLATES / CLASSES ==============================================================================

PathLikeTemplate = Union[str, Callable[..., str]]


# UTILS ============================================================================================

def _validate_path(path: str) -> bool:
    # Ensure the resolved path string does not contain any forbidden characters.
    INVALID_CHARS = ('<', '>', ':', '"', '|', '?', '*')
    for char in path:
        if char in INVALID_CHARS: # Raise a ValueError, specifying the forbidden character found
            raise ValueError(
                f"Resolved path name contains invalid character: '{char}'. "
                f"Forbidden characters are: {', '.join(f"'{c}'" for c in INVALID_CHARS)}"
            )
    return True

def _convert_to_path(path:str|Path) -> Path:
    return Path(path) if isinstance(path, str) else path


# WORKFLOW CLASS ===================================================================================

class Workflow:

    # INITIALIZER ==================================================================================

    def __init__(
        self, 
        base_path: str|Path = ".", 
        execution_id:int|str = None, 
        storage_block_name: str = None,
        id_path_digits: int = 4
    ):
        
        # Mandatory number of digits of the id (4 digits -> "0000")
        self.id_path_digits = id_path_digits

        # Resolve Workflow path
        self.set_workflow_path(base_path, execution_id, storage_block_name)

 

    # MANAGE EXECUTION ID & ENVIRONMENT ============================================================

    def _int2id(self, id: int|str) -> str:

        # Return if already a string
        if isinstance(id, str): return id

        # Convert to string
        id_str = str(id)

        # Check if padding with zeros is necessary
        if len(id_str) > self.id_path_digits: return id_str
        return id_str.zfill(self.id_path_digits)
    

    def create_execution_id(self) -> int:

        # Check for all existing folders (ids) inside basepath 
        folders = [f for f in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, f))]

        # If not folders, use id = 0
        if not folders: return 0
        
        # Find the highest existing id and increment
        return max([int(f) for f in folders if f.isdigit()], default=-1) + 1


    def set_workflow_path(
        self, 
        base_path: str|Path = ".", 
        execution_id:int|str = None, 
        storage_block_name:str = None
    ) -> str:
        '''
        Workflow path is built as: base_path/execution_id
        This method must be called whenever we want to set a new workflow path.
        '''

        # Resolve execution id
        if execution_id is None: execution_id = getattr(self, 'execution_id', None)
        if execution_id is None: execution_id = self.create_execution_id()
        self.execution_id = self._int2id(execution_id)

        # Resolve base path
        base_path = _convert_to_path(base_path)

        # Resolve storage_block_name
        if storage_block_name is None: self.storage_block_name = getattr(self, 'storage_block_name', 'my-custom-local-storage')
        else: self.storage_block_name = storage_block_name + '-' + self.execution_id

        # Create new workflow folder
        self.workflow_path = base_path / self.execution_id
        _validate_path(str(self.workflow_path))
        self.workflow_path.mkdir(parents=True, exist_ok=True)

        # Set up block storage
        self._setup_storage_block()

        return self.workflow_path


    # MANAGE PREFECT STORAGE =======================================================================

    def _setup_storage_block(self):
        asyncio.run(self._setup_local_storage_block())
        self.result_storage = f"local-file-system/{self.storage_block_name}"

    async def _setup_local_storage_block(self):
        """Defines and persists the LocalFileSystem block."""

        # Create LocalFileSystem block
        custom_storage = LocalFileSystem(
            basepath=os.path.join(os.getcwd(), str(self.workflow_path))
        )

        # Save the block instance. This satisfies the TypeError requirement.
        await custom_storage.save(name=self.storage_block_name, overwrite=True)


    # SETUP LOGGER =================================================================================

    def set_logger(self, loggerObj = None):
        '''
        Setup prefect logger for the workflow or use a custom one.
        NOTE: Prefect's get_run_logger() only works within a Prefect flow/task context.
        '''
        self.logger = get_run_logger() if loggerObj is None else loggerObj


    # CUSTOM CACHE STORAGE DECORATOR ===============================================================

    def _resolve_path(self, path_template: PathLikeTemplate, args: tuple, kwargs: dict, func_name: str) -> Path:
        """
        Resolve the final file path using either:
          - a callable: path_template(*args, **kwargs) -> str
          - a template string: "folder-{id}/out-{0}.json" -> will substitute kwargs and positional indices
        Supported placeholders:
          - named: {id}, {user}
          - numeric: {0}, {1} for positional args
          - argN alias: {arg0}, {arg1}
        """
        if callable(path_template):
            path_str = path_template(*args, **kwargs)
        else:
            # Build mapping: '0', '1', ... for positional indices and 'arg0', 'arg1' aliases
            mapping = {str(i): v for i, v in enumerate(args)}
            mapping.update({f"arg{i}": v for i, v in enumerate(args)})
            mapping.update(kwargs)

            # Provide a fallbacks
            mapping.setdefault("func", func_name)
            mapping.setdefault("id", self.execution_id)

            # Try formatting; raise helpful error if keys missing
            try:
                path_str = path_template.format_map(mapping)
            except KeyError as e:
                missing = e.args[0] if e.args else "unknown"
                raise KeyError(f"path template is missing key: {missing}. "
                               f"Available keys: positional indices '0','1',... aliases 'arg0','arg1', and kwargs keys.") from e
            
        _validate_path(path_str)
        return self.workflow_path / Path(path_str)


    def stored_result(self, path: PathLikeTemplate, converter: Any = None) -> Callable:
        """
        Decorator factory that caches task results using configurable path and loaders/savers functions..
        
        Args:
            path: either a template string (supports {id}, {0}, etc.) or a callable `(*args, **kwargs) -> str`.
            
        Usage:
            @MyWorkflow.stored_result("fetch-{id}/out.json")
            def func(...)

            or

            @MyWorkflow.stored_result(lambda *a, **kw: f"fetch-{kw['id']}/out.json")


        Decorator factory that caches a task's result to a file path, loading from 
        cache if the file exists or saving the result if the function is executed.
        
        Args:
            path: Either a template string (supports {id}, {0}, etc., for positional/keyword 
                  arguments) or a callable `(*args, **kwargs) -> str` that resolves to the 
                  cache file path (relative to the execution folder). Must resolve to a file 
                  path, not a directory.
            loader: An optional callable `(path: Path) -> Any` used to load the cached result 
                    from the file path. If None, the workflow's default converter loader 
                    (e.g., for JSON) is used.
            saver: An optional callable `(result: Any, path: Path) -> None` used to save the 
                   result to the file path. If None, the workflow's default converter saver 
                   is used.
            
        Usage:
            1. Using a template string:
               @MyWorkflow.stored_result("data/fetch-{id}/out.json")
               def fetch_data(id: str, ...) -> dict:
                   # ... implementation ...
            
            2. Using a lambda/callable for dynamic path generation:
               @MyWorkflow.stored_result(lambda *a, **kw: f"results/{kw['date']}/output.pkl", 
                                loader=load_pickle, saver=save_pickle)
               def process_data(date: str, ...) -> Any:
                   # ... implementation ...

        Notes:
            - The `path` is resolved based on the decorated function's arguments.
            - If the file at the resolved path exists, it's loaded and returned immediately.
            - If it doesn't exist, the decorated function is executed, and its result is 
              saved to the file before being returned.
        """
        def decorator(func):

            @wraps(func)
            def wrapper(*args, **kwargs):

                # Resolve template/callable into a Path relative to execution-specific folder
                file_path = self._resolve_path(path, args, kwargs, func.__name__)

                # Make sure parent exists
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Load from stored file if exists
                if file_path.exists():
                    return str(file_path) if converter is None else converter.load(file_path)

                # Not cached => call function and persist result
                result = func(*args, **kwargs)

                # Save and return result
                if converter is not None: converter.save(result, file_path)
                return result

            return wrapper

        return decorator



# SERIALIZER CLASSES ===================================================================================

class Serializers:

    class NumberSerializer(Serializer):
        """A serializer that stores a single number (int or float) as plain text."""
        type: str = "number-custom"

        def dumps(self, obj: Union[int, float]) -> bytes:
            """Converts a number to its string representation, then to bytes."""
            if not isinstance(obj, (int, float)): raise TypeError(f"NumberSerializer expects an int or float, got {type(obj)}")
            return str(obj).encode("utf-8")

        def loads(self, blob: bytes) -> Union[int, float]:
            """Converts bytes back into a number (int or float)."""
            text = blob.decode("utf-8").strip()
            try:
                value = float(text)
                if value == int(value): return int(value)
                return value
            except ValueError:
                raise ValueError(f"Could not convert stored text '{text}' to a number.")


    class TextSerializer(Serializer):
        """A serializer that stores a single string object as plain text."""
        type: str = "text-custom"

        def dumps(self, obj: str) -> bytes:
            """Converts a string object to bytes."""
            if not isinstance(obj, str): raise TypeError(f"TextSerializer expects a string, got {type(obj)}")
            return obj.encode("utf-8")

        def loads(self, blob: bytes) -> str:
            """Converts bytes back into a string object."""
            return blob.decode("utf-8")
        

    class DictionarySerializer(Serializer):
        """A custom serializer that stores and loads data as simple JSON."""
        type: str = "json-custom"

        def dumps(self, obj: dict) -> bytes:
            """Converts the object to JSON string, then to bytes."""
            if not isinstance(obj, dict): raise TypeError(f"DictionarySerializer expects a dict, got {type(obj)}")
            return json.dumps(obj, indent=2).encode("utf-8")

        def loads(self, blob: bytes):
            """Converts bytes back into a JSON object."""
            return json.loads(blob.decode("utf-8"))
        
    

# CONVERTER CLASSES ===================================================================================

class Converters:
    """Handles loading and saving based on file extension."""

    class DictionaryConverter:
        
        def save(dictionary:dict, path: str|Path):
            path = _convert_to_path(path)
            path.write_text(json.dumps(dictionary, indent=2))

        def load(path: str|Path) -> dict:
            return json.loads(path.read_text())
        

    class TextConverter:
        
        def save(text:str, path: str|Path):
            path = _convert_to_path(path)
            path.write_text(text)

        def load(path: str|Path) -> str:
            return path.read_text()

