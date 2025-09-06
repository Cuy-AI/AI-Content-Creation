import os
import json
import time
import subprocess
import requests
import lmstudio as lms
from jsonschema import Draft7Validator
from classes.BaseAI import BaseAI

class LMStudio(BaseAI):
    """
    Full-control helper for LM Studio local server and models.

    Key features:
    - Start/stop server via `lms server start|stop` with health checks.
    - Query available models via GET /v1/models (OpenAI-compatible).
    - Load models with LM Studio Python SDK: client.llm.load_new_instance(model_key, config=...).
    - Generate text with structured JSON output using response_format + json_schema.

    Requirements:
        - LM Studio installed and its CLI `lms` available in PATH.

    Docs:
        CLI start/stop: https://lmstudio.ai/docs/cli
        Python load_new_instance: https://lmstudio.ai/docs/python/manage-models/loading
    """

    def __init__(self, model_id: str|None = None, auto_start: bool = True) -> None:
        super().__init__()

        self.base_url = "http://127.0.0.1:1234"
        self.client = lms.get_default_client()
        self.request_timeout = 45
        self.generation_timeout = 120

        # Load params (BaseAI)
        # self.params_path = "params.json"
        self.params_path = "components/LM/LMStudio/params.json"
        self.set_default_params()

        # Default JSON Schema for structured outputs (user can replace via set_schema)
        self.schema = {
            "name": "standard_response",
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                },
                "required": ["answer"],
            }
        }

        # Ensure server is running if requested
        if auto_start: self.start_server()

        # Populate model info
        self.lm_models = {}
        self.refresh_models()

        # Check model_id and load the model
        if model_id: self.load_model(model_id)
        else: self.model = model_id
        

    # -----------------------
    # Server lifecycle
    # -----------------------
    def start_server(self) -> None:
        """
        Start LM Studio server via CLI and wait until healthy.
        Raises RuntimeError if the server doesn't become healthy in time.
        """
        try:
            # Attempt quick probe first
            if self._is_server_up():
                print("Server is already up")
                return "Server is already up"

            proc = subprocess.run(
                ["lms", "server", "start"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
            )

            # Don't rely only on exit code—poll health
            start_timeout = 60
            deadline = time.time() + start_timeout
            while time.time() < deadline:
                if self._is_server_up(): 
                    print("Server started successfully")
                    return "Server started successfully"
                time.sleep(0.5)

            # If we got here, it didn't become healthy
            err_msg = (
                "Failed to start LM Studio server: not healthy after "
                f"{start_timeout}s.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )

            raise RuntimeError(err_msg)
        
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Could not execute 'lms'. Ensure LM Studio CLI is installed and in PATH."
            ) from e

    def stop_server(self) -> None:
        """
        Stop LM Studio server via CLI and wait until it is no longer reachable.
        Raises RuntimeError on failure.
        """
        try:
            proc = subprocess.run(
                ["lms", "server", "stop"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
            )
            # Poll until the API stops responding
            stop_timeout = 45
            deadline = time.time() + stop_timeout
            while time.time() < deadline:
                if not self._is_server_up(): 
                    print("Server stopped successfully")
                    return "Server stopped successfully"
                time.sleep(0.5)
            raise RuntimeError(
                "Failed to stop LM Studio server cleanly within "
                f"{stop_timeout}s.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Could not execute '{"lms"}'. Ensure LM Studio CLI is installed and in PATH."
            ) from e

    def _is_server_up(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/v0/models", timeout=self.request_timeout)
            return r.ok
        except Exception:
            return False

    # -----------------------
    # Model discovery
    # -----------------------
    def refresh_models(self) -> None:
        """
        Refresh models data with endpoint: /api/v0/models
        """
        # GET /api/v0/models
        r = requests.get(f"{self.base_url}/api/v0/models", timeout=self.request_timeout)
        r.raise_for_status()
        models_raw = r.json()

        # Get model names only of llm's (not embeddings)
        self.lm_models = {}

        for model in models_raw.get("data", []):
            if model.get("type", None) == "llm":
                model_id = model.get("id", None)
                if model_id is not None:
                    fixed_dic = model.copy()
                    del fixed_dic['id']
                    self.lm_models[model_id] = fixed_dic.copy()

        return "Models were refreshed successfully "
    
    def _check_model_id(self, model_id):
        return model_id in self.lm_models.keys()

    # -----------------------
    # Model loading
    # -----------------------

    def get_model(self) -> str:
        return self.model
    
    def set_model(self, model_id:str):
        if not self._check_model_id(model_id):
            raise ValueError("The model id is not listed on downloaded models")
        
        if model_id not in self.list_loaded_models():
            raise ValueError("The model is not listed on loaded models")
        
        self.model_id = model_id
        return "LM model was set successfully"

    def load_model(self, model_id: str, config: dict = {}) -> None:
        """
        Load a model using the LM Studio Python SDK, then refresh state.
        """

        if not self._check_model_id(model_id):
            raise ValueError("The model id is not listed on downloaded models")
        
        self.model = model_id

        # Check if model is already loaded
        self.refresh_models()
        
        if self.model in self.list_loaded_models():
            return f"Model {self.model} was already loaded"
        
        # Load model
        self.client.llm.load_new_instance(self.model, config=config)

        # After loading, refresh our local snapshot
        self.refresh_models()

        # Check if refresh models reflects the changes
        load_timeout = 90
        deadline = time.time() + load_timeout
        while time.time() < deadline:
            self.refresh_models()
            if self.lm_models[self.model].get("state", None) == "loaded":
                return f"Model {self.model} was loaded successfully"
            time.sleep(0.5)
            
        raise RuntimeError(f"Failed to load {self.model} model")

    def eject_model(self, model_id: str) -> None:

        if model_id not in self.list_available_models():
            raise ValueError("The model id is not listed on downloaded models")

        if model_id not in self.list_loaded_models():
            raise ValueError("The model is not listed on loaded models")
        
        # Unload model
        self.client.llm.unload(self.model)

        # After unloading, refresh our local snapshot
        self.model_id = None
        self.refresh_models()

        # Check if refresh models reflects the changes
        load_timeout = 60
        deadline = time.time() + load_timeout
        while time.time() < deadline:
            self.refresh_models()
            if self.lm_models[self.model].get("state", None) == "not-loaded":
                return f"Model {self.model} was unloaded successfully"
            time.sleep(0.5)

        raise RuntimeError(f"Failed to unload {self.model} model")
        
        
    # -----------------------
    # Structured generation
    # -----------------------
    def set_schema(self, schema: dict) -> None:
        """Replace the JSON Schema used for structured outputs."""
        try:
            Draft7Validator.check_schema(schema.copy())
            self.schema = {
                "name": "qa_schema",
                "schema": schema.copy(),
                "strict": False
            }
            return "Json schema was set successfully"
        except Exception as e:
             raise ValueError(f"The json schema is not valid: {e}")

    def get_schema(self) -> dict:
        return self.schema.copy()


    # -----------------------
    # Generation
    # -----------------------
    def _validate_messages(self, messages: dict) -> bool:
        for msg in messages:
            if "role" not in msg.keys() or "content" not in msg.keys() or len(msg.keys()) > 2:
                return False, "Messages param was not structured correctly with 'role' and 'content'"
            role = msg.get("role")
            if role not in ("system", "user", "assistant", "tool", "function"):
                return False, f"Role: {role} not valid"
        return True, ""

    def generate(self, prompt: str|None = None, messages: list|None = None, save_path: str|None = None) -> dict:
        """
        Generate a completion with structured JSON output.
        - By default uses chat completions if `messages` provided; otherwise uses text completions with `prompt`.
        - Always sends `response_format` with a JSON Schema (self.schema).
        - You can override/extend params via `params`.

        Returns: parsed JSON response from LM Studio server.
        """

        # Route choice
        if messages is not None:
            use_chat = True 
            validation, msg = self._validate_messages(messages)
            if not validation: raise ValueError(msg)
        elif prompt is not None:
            use_chat = False
        else:
            raise ValueError("Provide 'messages' (or a 'prompt')")

        # Base payload
        params = self.params.copy()
        params["seed"] = self._generate_random()

        # Build request
        if use_chat:
            url = f"{self.base_url}/v1/chat/completions"
            body = {
                "model": self.model,
                "messages": messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": self.schema
                },
                **{k: v for k, v in params.items() if v is not None},
            }
        else:
            url = f"{self.base_url}/v1/completions"
            body = {
                "model": self.model,
                "prompt": prompt,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": self.schema
                },
                **{k: v for k, v in params.items() if v is not None},
            }

        r = requests.post(url, json=body, timeout=self.generation_timeout)
        r.raise_for_status()
        if use_chat:
            text_answ = r.json()["choices"][0]["message"]["content"]
        else:
            text_answ = r.json()["choices"][0]["text"]

        try:
            structured_answer = json.loads(text_answ)
        except json.JSONDecodeError:
            structured_answer = text_answ

        final_output = {
            "model": self.model,
            "input": prompt,
            "schema": self.schema,
            "parameters": self.params,
            "output": structured_answer,
        }

        if save_path:
            # If save_path looks like a file (has an extension), handle as file
            if os.path.splitext(save_path)[1]:  
                if os.path.dirname(save_path) != '':
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)  # ensure parent dir exists
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(final_output, f, indent=2, ensure_ascii=False)
            else:
                # treat as directory -> auto-generate a filename
                if os.path.dirname(save_path) != '':
                    os.makedirs(save_path, exist_ok=True)
                save_path = os.path.join(save_path, "output.json")
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(final_output, f, indent=2, ensure_ascii=False)

        final_output["save_path"] = save_path
        
        return final_output

    # -----------------------
    # Introspection helpers
    # -----------------------
    def list_available_models(self) -> list:
        """Return a list of model IDs from /v1/models."""
        return list(self.lm_models.keys())

    def list_loaded_models(self) -> list:
        """Return the last known loaded models."""
        return [model_id for model_id, info in self.lm_models.items() if info["state"] == "loaded"]
