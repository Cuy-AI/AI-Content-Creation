import os
import json
import asyncio
from pathlib import Path
from functools import wraps
from typing import Callable, Union, List, Dict, Any

from prefect.serializers import Serializer
from prefect.filesystems import LocalFileSystem


# UTILS ============================================================================================

class Utils:

    @staticmethod
    def validate_path(path: Path|str, throw_err:bool = True) -> bool:

        # Convert to string
        if isinstance(path, Path): path = str(path)

        # Ensure the resolved path string does not contain any forbidden characters.
        INVALID_CHARS = ('<', '>', ':', '"', '|', '?', '*')
        for char in path:
            if char in INVALID_CHARS: # Raise a ValueError, specifying the forbidden character found
                if throw_err:
                    raise ValueError(
                        f"Resolved path name contains invalid character: '{char}'. "
                        f"Forbidden characters are: {', '.join(f"'{c}'" for c in INVALID_CHARS)}"
                    )
                else: return False
        return True

    @staticmethod
    def convert_to_path(path:str|Path) -> Path:
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
    

    def next_execution_id(self, base_path: str|Path = None) -> int:

        if base_path is None: base_path = Utils.convert_to_path(self.base_path)
        else: base_path = Utils.convert_to_path(base_path)

        # If directory doesn't exist yet, start at 0
        if not base_path.exists(): return 0

        # Collect names of subdirectories (use Path API)
        folders = [p.name for p in base_path.iterdir() if p.is_dir()]

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

        # Resolve base path
        self.base_path = Utils.convert_to_path(base_path)

        # Resolve execution id
        if execution_id is None: execution_id = getattr(self, 'execution_id', None)
        if execution_id is None: execution_id = self.next_execution_id()
        self.execution_id = self._int2id(execution_id)


        # Resolve storage_block_name
        if storage_block_name is None: self.storage_block_name = getattr(self, 'storage_block_name', 'my-custom-local-storage')
        else: self.storage_block_name = storage_block_name + '-' + self.execution_id

        # Create new workflow folder
        self.workflow_path = self.base_path / self.execution_id
        Utils.validate_path(str(self.workflow_path))
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




# CUSTOM CACHE STORAGE DECORATOR ===================================================================

class PersistentResult:
    """
    A helper class to persist and retrieve function results based on a given cache key.

    This class provides a flexible mechanism for storing results of function calls
    to avoid recomputation. It supports customizable logic for:
      - Generating cache keys (`SolverFunction`)
      - Verifying cache existence (`VerifierFunction`)
      - Saving results (`SaverFunction`)
      - Loading cached results (`LoaderFunction`)

    The typical use case is wrapping expensive or deterministic functions so that
    their results are stored on disk or another persistent medium and reused when possible.
    """

    # TEMPLATES / CLASSES ==========================================================================

    # A str, Path obj or a function
    PathTemplate = Union[str, Path, Callable[..., str]] 

    # Receives the cache key and funciton params. Return the fixed cache key
    SolverFunction = Callable[[Any, tuple, dict], Any] 

    # Receives the fixed cache key. Returns True if result can be loaded
    VerifierFunction = Callable[[Any], bool]

    # Receives the cache key and the function result. Stores the result
    SaverFunction = Callable[[Any, Any], None] 

    # Receives the cache key. Loads an stored result
    LoaderFunction = Callable[[Any], Any]


    # METHODS FOR PERSIST STORAGE ==================================================================
    @staticmethod
    def DefaultSolver(path_template: PathTemplate, args: tuple, kwargs: dict) -> Path:
        """
        Default function for resolving a cache path from a template and function arguments.

        This method interprets `path_template` in the following ways:
          - If it's a `Path` object, it returns it directly.
          - If it's a callable, it invokes it with `*args` and `**kwargs` to produce the path.
          - If it's a string, it formats it using both positional (`0`, `1`, ...) 
            and alias (`arg0`, `arg1`, ...) placeholders, as well as keyword arguments.

        Raises:
            KeyError: If the provided template references a key not present in the arguments.

        Example:
            path_template = "results/{0}_{param}.json"
            args = ("data",)
            kwargs = {"param": "v1"}
            → returns Path("results/data_v1.json")
        """

        if isinstance(path_template, Path): 
            return path_template
        elif callable(path_template):
            path_str = path_template(*args, **kwargs)
        else:
            # Build mapping: '0', '1', ... for positional indices and 'arg0', 'arg1' aliases
            mapping = {str(i): v for i, v in enumerate(args)}
            mapping.update({f"arg{i}": v for i, v in enumerate(args)})
            mapping.update(kwargs)

            # Try formatting; raise helpful error if keys missing
            try:
                path_str = path_template.format_map(mapping)
            except KeyError as e:
                missing = e.args[0] if e.args else "unknown"
                raise KeyError(f"path template is missing key: {missing}. "
                               f"Available keys: positional indices '0','1',... aliases 'arg0','arg1', and kwargs keys.") from e
            
        return Path(path_str)
    

    @staticmethod
    def DefaultVerifier(cache_key: Path|str) -> bool:
        """
        Default verification method that checks if a cached result exists at the given path.

        It converts string paths into `Path` objects, validates the path format using
        `Utils.validate_path`, and returns `True` if the file exists.

        Args:
            cache_key (Path | str): The resolved cache key, usually a file path.

        Returns:
            bool: True if the cache file exists, False otherwise.

        Raises:
            ValueError: If the provided path is invalid.
        """
        # Convert strings to Path objects
        if isinstance(cache_key, str): cache_key = Path(cache_key)

        # Check if the path is valid, throw error if not
        Utils.validate_path(cache_key)

        # Return True if path exist
        return cache_key.exists()


    @staticmethod
    def stored_result(
        cache_key: Any, 
        solver: SolverFunction = None, 
        verifier: VerifierFunction = None, 
        saver: SaverFunction = None,
        loader: LoaderFunction = None, 
    ) -> Callable:
        """
        Decorator for automatically caching function results using a persistent storage mechanism.

        When a decorated function is called:
          1. The cache key is resolved via `solver` (or the default one if not provided).
          2. The verifier checks whether a cached result already exists.
          3. If cached, the result is loaded via `loader` (if provided) and returned.
          4. Otherwise, the function executes normally, its result is saved via `saver` 
             (if provided), and the result is returned.

        Args:
            cache_key (Any): The initial cache key, or a template used by the solver.
            solver (SolverFunction, optional): Custom function to resolve the cache key.
            verifier (VerifierFunction, optional): Function to check if a cache exists.
            saver (SaverFunction, optional): Function to store results persistently.
            loader (LoaderFunction, optional): Function to load results from cache.

        Returns:
            Callable: The decorated function with persistent caching behavior.

        Example:
            @PersistentResult.stored_result("cache/{0}.json")
            def heavy_computation(param):
                ...
        """

        def decorator(func):

            @wraps(func)
            def wrapper(*args, **kwargs):
                
                # Choose which verifier and solver to use
                solver_function: PersistentResult.SolverFunction = solver or PersistentResult.DefaultSolver
                verifier_function: PersistentResult.VerifierFunction = verifier or PersistentResult.DefaultVerifier

                # Solve cache key
                solved_cache_key: Any = solver_function(cache_key, args, kwargs)

                # Use verifier to decide if is possible to load a result instead of calculating it
                if verifier_function(solved_cache_key): 
                    return solved_cache_key if loader is None else loader(solved_cache_key)

                # Not cached => call function to generate a result
                result: Any = func(*args, **kwargs)

                # Store value using cache key
                if saver is not None: saver(result, solved_cache_key) 

                return result

            return wrapper

        return decorator


    # CONVERTER CLASSES ===================================================================================
    """
    These functions are mean to be used as params of the stored_result method.
    You can create you own converters using this functions as examples.
    They allow you to specify the following:
      - Save: Given a result of any type: How should we save it?
      - Load: Given some stored data: How should we load it?
    
    Hint: 
        You can receive any type as value and any type as cache_key.
    """
    class Converters:

        @staticmethod
        def DictionarySaver(result:dict, cache_key: str|Path):
            path = Utils.convert_to_path(cache_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2))

        @staticmethod
        def DictionaryLoader(cache_key: str|Path) -> dict:
            path = Utils.convert_to_path(cache_key)
            return json.loads(path.read_text())
        

        @staticmethod
        def TextSaver(result:str, cache_key: str|Path):
            path = Utils.convert_to_path(cache_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result)

        @staticmethod
        def TextLoader(cache_key: str|Path) -> str:
            path = Utils.convert_to_path(cache_key)
            return path.read_text()




# SERIALIZER CLASSES ===================================================================================

class Serializers:
    """
    Collection of **custom Prefect serializer classes** for fine-grained control over
    how Prefect stores and reconstructs task results.

    Prefect, by default, serializes objects as bytes. These custom serializers define
    explicit encoding and decoding logic for specific data types such as numbers,
    strings, and dictionaries.

    You can register these serializers with Prefect to improve readability or
    efficiency of stored results, or to handle unsupported types.

    Each serializer implements:
      - `dumps(obj) -> bytes`: Converts the Python object into bytes.
      - `loads(blob) -> Any`: Converts bytes back into the original object.
    """

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
