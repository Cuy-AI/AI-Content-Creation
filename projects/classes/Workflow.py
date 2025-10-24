import os
import json
from pathlib import Path
from functools import wraps
from typing import Callable, Union, Dict, Any
from prefect import get_run_logger


# TEMPLATES / CLASSES ==============================================================================

PathLikeTemplate = Union[str, Callable[..., str]]
LoaderTemplate = Callable[[Path], Any]
SaverTemplate = Callable[[Any, Path], None]


# WORKFLOW CLASS ===================================================================================

class Workflow:

    # INITIALIZER ==================================================================================

    def __init__(self, base_path: str|Path = ".", execution_id:int|str = None, id_path_digits: int = 4):
        
        # Mandatory number of digits of the id (4 digits -> "0000")
        self.id_path_digits = id_path_digits

        # Convert str to path
        base_path = Path(base_path)

        # Resolve Execution ID
        if execution_id is None: execution_id = self.generate_exe_id(base_path)

        # Set up environment
        self.execution_id = self.int2id(execution_id)
        self.workflow_path = base_path / self.execution_id
        self.workflow_path.mkdir(parents=True, exist_ok=True)

        # Create a converter
        self.converter = Converter()


    # MANAGE EXECUTION ID ==========================================================================

    def int2id(self, id: int|str) -> str:
        if isinstance(id, str): return id
        id_str = str(id)
        if len(id_str) > self.id_path_digits: return id_str
        return id_str.zfill(self.id_path_digits)
    

    def generate_exe_id(self, base_path: str|Path = ""):

        # Create base path if not exists
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)

        # Check for all existing folders (ids) inside basepath 
        folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]

        # If not folders, use id = 0
        if not folders: return 0
        
        # Find the highest existing id and increment
        return max([int(f) for f in folders if f.isdigit()], default=-1) + 1


    # CACHE DECORATOR ==============================================================================

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

            # Provide a fallback for `func_name` if user wants it
            mapping.setdefault("func", func_name)

            # Try formatting; raise helpful error if keys missing
            try:
                path_str = path_template.format_map(mapping)
            except KeyError as e:
                missing = e.args[0] if e.args else "unknown"
                raise KeyError(f"path template is missing key: {missing}. "
                               f"Available keys: positional indices '0','1',... aliases 'arg0','arg1', and kwargs keys.") from e

        return Path(path_str)


    def generate_save_path(self, relative_path: Path) -> Path:
        """Return the actual path inside workflow_path/execution_id/relative_path."""
        return self.workflow_path / relative_path
    
    def add_loader(self, ext: str, func: LoaderTemplate):
        self.converter.add_loader(ext, func)

    def add_saver(self, ext: str, func: SaverTemplate):
        self.converter.add_saver(ext, func)


    def stored_result(
        self,
        path: PathLikeTemplate,
        loader: LoaderTemplate = None,
        saver: SaverTemplate = None,
    ):
        """
        Decorator factory that caches task results using configurable path and loaders/savers functions..
        
        Args:
            path: either a template string (supports {id}, {0}, etc.) or a callable `(*args, **kwargs) -> str`.
            
        Usage:
            @w.stored_result("fetch-{id}/out.json")
            def func(...)

            or

            @w.stored_result(lambda *a, **kw: f"fetch-{kw['id']}/out.json")


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
               @w.stored_result("data/fetch-{id}/out.json")
               def fetch_data(id: str, ...) -> dict:
                   # ... implementation ...
            
            2. Using a lambda/callable for dynamic path generation:
               @w.stored_result(lambda *a, **kw: f"results/{kw['date']}/output.pkl", 
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
                func_name = func.__name__

                # Resolve template/callable into a Path relative to execution-specific folder
                file_path = self._resolve_path(path, args, kwargs, func_name)

                # If resolved path looks like a directory (no suffix)
                if file_path.suffix == "":
                    raise ValueError(f"Cannot load/save output with a folder path {file_path}")

                # Convert to final absolute path under workflow/execution id
                final_path = self.generate_save_path(file_path)

                # Make sure parent exists
                final_path.parent.mkdir(parents=True, exist_ok=True)

                # Load from stored file if exists
                if final_path.exists():
                    use_loader = loader or self.converter.load
                    return use_loader(final_path)

                # Not cached => call function and persist result as JSON (assume dict)
                result = func(*args, **kwargs)

                use_saver = saver or self.converter.save
                use_saver(result, final_path)
                return result

            return wrapper

        return decorator



# CONVERTER CLASS ===================================================================================

class Converter:
    """Handles loading and saving based on file extension."""
    def __init__(self):
        self._loaders: Dict[str, LoaderTemplate] = {}
        self._savers: Dict[str, SaverTemplate] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default converters for common types."""
        self.add_loader(".json", lambda p: json.loads(p.read_text()))
        self.add_saver(".json", lambda d, p: p.write_text(json.dumps(d, indent=2)))

        self.add_loader(".txt", lambda p: p.read_text())
        self.add_saver(".txt", lambda s, p: p.write_text(str(s)))

        # For binary formats (images, audio, etc.)
        for ext in (".wav", ".mp3", ".mp4", ".bin"):
            self.add_loader(ext, lambda p: p.read_bytes())
            self.add_saver(ext, lambda b, p: p.write_bytes(b))

    def add_loader(self, ext: str, func: LoaderTemplate):
        """Register a custom loader for a file extension."""
        self._loaders[ext.lower()] = func

    def add_saver(self, ext: str, func: SaverTemplate):
        """Register a custom saver for a file extension."""
        self._savers[ext.lower()] = func

    def load(self, path: Path) -> Any:
        ext = path.suffix.lower()
        if ext not in self._loaders:
            raise ValueError(f"No loader registered for extension: {ext}")
        return self._loaders[ext](path)

    def save(self, value: Any, path: Path):
        ext = path.suffix.lower()
        if ext not in self._savers:
            raise ValueError(f"No saver registered for extension: {ext}")
        self._savers[ext](value, path)