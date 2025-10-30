import os
import json
import asyncio
from pathlib import Path
from functools import wraps
from typing import Callable, Union, List, Dict, Any

from prefect.serializers import Serializer
from prefect.filesystems import LocalFileSystem


# UTILS ============================================================================================

def _validate_path(path: str, throw_err:bool = True) -> bool:
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




# CUSTOM CACHE STORAGE DECORATOR ===================================================================

class PersistentResult:
    """
    A utility class that provides a decorator for **persistent result caching**.

    This class allows you to transparently cache and retrieve the output of functions
    to/from disk (or other persistent storage). It supports flexible cache key
    generation (via strings, paths, or callables), customizable verification logic,
    and configurable serialization through *converter* classes.

    With this mechanism you can decide:
    - How interprete and generate cache keys
    - How cache existence is cheked
    - How to save or load a result

    Usage example:
        @PersistentResult.stored_result("cache-{0}.json", converter=PersistentResult.DictionaryConverter)
        def expensive_computation(x):
            return {"result": x**2}

    Key features:
      - Resolve dynamic file paths for cache storage.
      - Verify and load cached results before recomputation.
      - Customize how results are saved/loaded via converters.
    """

    # TEMPLATES / CLASSES ==========================================================================
    PathTemplate = Union[str, Path, Callable[..., str]] # Can be a str, Path obj or a function
    SolverFunction = Callable[[Any, tuple, dict], tuple[bool, Any]] # Must be a function with 3 params and return bool, any

    # METHODS FOR PERSIST STORAGE ==================================================================
    @staticmethod
    def resolve_path(path_template: PathTemplate, args: tuple, kwargs: dict) -> Path:
        """
        Resolves a dynamic cache file path from a template, callable, or static path.

        Parameters:
            path_template (str | Path | Callable):
                - If a `Path`, it is returned as-is.
                - If a `Callable`, it is called with `(*args, **kwargs)` and must return a string path.
                - If a `str`, it can include Python-style placeholders for both args and kwargs.
                  Supported placeholders:
                    • Named placeholders: {id}, {user}, etc.
                    • Positional indices: {0}, {1}, ...
                    • Positional aliases: {arg0}, {arg1}, ...

            args (tuple):
                The positional arguments passed to the wrapped function.

            kwargs (dict):
                The keyword arguments passed to the wrapped function.

        Returns:
            Path:
                The fully resolved file system path where the result should be stored.

        Raises:
            KeyError:
                If a required placeholder key is missing from args/kwargs.
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
    def _defaultSolver(cache_key: PathTemplate, args: tuple, kwargs: dict) -> tuple[bool, Path]:
        """
        Default solver used by `stored_result` to determine both:
        1. Whether a cached result already exists (cache hit).
        2. The *resolved identifier* (a fixed cache key) that should be used to
            either load or save the function result.

        Parameters:
            cache_key (PathTemplate):
                A key template defining how to locate or identify a cached result.
                It can be:
                - A static path (`Path` or string)
                - A callable that returns a path-like string based on `args`/`kwargs`
                - A format string with placeholders (e.g. `"cache-{user}-{0}.json"`)
                - ANYTHING

            args (tuple):
                Positional arguments passed to the wrapped function. Used to resolve
                dynamic placeholders or callables in the key template.

            kwargs (dict):
                Keyword arguments passed to the wrapped function. Used for resolving
                dynamic placeholders or callables in the key template.

        Returns:
            tuple[bool, Any]:
                A tuple with two elements:
                - `bool`: Indicates whether a stored result already exists (True = cache hit).
                - `Any`: A *fixed cache key* derived from the original `cache_key`.
                            This key is used consistently for both loading and saving the result.

        Notes:
            • The *fixed cache key* does not need to be a filesystem path — it can represent
            any unique identifier (e.g., a database key, URL, or hash string).
            However, the default implementation assumes file-based caching.

            • When this method returns `(True, key)`, the `key` is passed to the converter’s
            `load()` method to retrieve the stored result.

            • When it returns `(False, key)`, the `key` is passed to the converter’s
            `save(result, key)` method after the function executes, allowing the new
            result to be persisted using the same identifier.

            • Custom solvers can redefine how cache existence is checked and how keys
            are generated.
        """
        # Resolve template/callable into a Path relative to execution-specific folder
        file_path = PersistentResult.resolve_path(cache_key, args, kwargs)

        # Check if the path is valid, throw error if not
        _validate_path(str(file_path))

        # Return if path exist
        return file_path.exists(), file_path


    @staticmethod
    def stored_result(cache_key: Any, converter: Any = None, solver: SolverFunction = None) -> Callable:
        """
        Decorator that caches the result of a function call to persistent storage.

        Parameters:
            cache_key (Any):
                Template or callable that determines where the cached result will be stored.

            converter (object, optional):
                A converter class defining how results should be saved and loaded.
                It must implement:
                    - `save(result, path)`
                    - `load(path)`
                See `DictionaryConverter` or `TextConverter` for examples.

            solver (Callable, optional):
                Custom function used to verify if the cached result exists.
                Must return a tuple `(cache_hit: bool, resolved_key: Any)`.

        Returns:
            Callable:
                The decorated function that automatically loads cached results
                when available and saves new results when computed.

        Workflow:
            1. Use `solver` (default: `_defaultSolver`) to check if the result is cached.
            2. If cached → load and return the stored value (via `converter.load()`).
            3. If not cached → execute the original function, save its output (via `converter.save()`), and return it.
        """

        def decorator(func):

            @wraps(func)
            def wrapper(*args, **kwargs):
                
                # Choose which verifier use
                verifier_function = PersistentResult._defaultSolver if solver is None else solver

                # Use verifier to decide if is possible to load a result instead of calculating it
                cache_hit, fixed_cache_key = verifier_function(cache_key, args, kwargs)

                # Load the result. If not loader, return the cache_key
                if cache_hit: return str(fixed_cache_key) if converter is None else converter.load(fixed_cache_key)

                # Not cached => call function to generate a result
                result = func(*args, **kwargs)

                # Save result
                if converter is not None: 
                    converter.save(result, fixed_cache_key) # Store value using cache key

                return result

            return wrapper

        return decorator


    # CONVERTER CLASSES ===================================================================================
    """
    These classes are mean to be used as params of the stored_result method.
    These classes were build to work with _defaultSolver 
    These classes allow you to specify the following:
      - Save: Given a result of any type: How should we save it?
      - Load: Given some stored data: How should we load it?
    
    You can create you own converter using this classes as examples.
    Hint 1: 
        You can receive any type as value and any type as path (identifier).
        Your logic will decide how to handle this value-identifer.
    """
    class DictionaryConverter:

        @staticmethod
        def save(result:dict, cache_key: str|Path):
            path = _convert_to_path(cache_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2))

        @staticmethod
        def load(cache_key: str|Path) -> dict:
            path = _convert_to_path(cache_key)
            return json.loads(path.read_text())
        

    class TextConverter:

        @staticmethod
        def save(result:str, cache_key: str|Path):
            path = _convert_to_path(cache_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result)

        @staticmethod
        def load(cache_key: str|Path) -> str:
            path = _convert_to_path(cache_key)
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
