import os
import json
import uvicorn

from openai import OpenAI as OpenAIClient
from dotenv import load_dotenv
from jsonschema import Draft7Validator

from classes.BaseAI import BaseAI
from classes.Server import Server


class OpenAI(BaseAI):

    def __init__(
            self, 
            model_name: str = "gpt-5-mini", 
            models_path: str = "models.json"
        ):

        super().__init__()

        # Set a default json schema
        self.schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"}
            },
            "required": ["answer"]
        }
        
        # Set up model name/path
        self.model_name = None
        self.models_path = None
        self.set_model_name(model_name, models_path)

        # Set default params
        self.set_default_params("params.json")

        # Load API key from .env
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        
        # Load API endpoint from .env
        self.api_endpoint = os.getenv("OPENAI_API_ENDPOINT")
        if not self.api_endpoint:
            raise ValueError("OPENAI_API_ENDPOINT not set in environment")

        # Store client configuration but don't create the client yet
        self._client_config = {
            "api_key": self.api_key,
            "base_url": self.api_endpoint,
        }
        self.client = OpenAIClient(**self._client_config)

    def set_schema(self, schema: dict):
        try:
            Draft7Validator.check_schema(schema.copy())
            self.schema = schema.copy()
            return "Json schema was set successfully"
        except Exception as e:
             raise ValueError(f"The json schema is not valid: {e}")

    def get_schema(self):
        return self.schema.copy()

    def set_model_name(self, model_name: str, models_path: str|None = None):

        if models_path:
            self.models_path = models_path

        # Check if models file exist
        if not os.path.exists(self.models_path):
            raise FileNotFoundError(f"Models json file not found: {self.models_path}")

        # Open and save configurations
        with open(self.models_path, "r", encoding="utf-8") as f:
            dic = json.load(f)

        # Check if model name is on models key
        if model_name not in dic["models"]:
            raise ValueError(f"Model not found in models list: {model_name}")

        self.model_name = model_name
        return "Model name was set successfully"      


    def generate(self, prompt: str, save_path: str|None = None) -> dict:

        # Build response format:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "strict": True,
                "schema": self.schema
            }
        }

        # Build and send request parameters
        completion = self.client.chat.completions.create(
            model=self.model_name,  # This must coincide with a deployment name in Azure OpenAI
            messages=[{
                "role": "user", 
                "content": prompt
            }],
            response_format=response_format,
            seed=self._generate_random(),
            **self.params
        )
    
        try:
            output_json = json.loads(completion.choices[0].message.content)
        except json.JSONDecodeError:
            output_json = completion.choices[0].message.content

        final_output = {
            "model": self.model_name,
            "input": prompt,
            "schema": self.schema,
            "parameters": self.params,
            "output": output_json,
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
    
if __name__ == "__main__":
    openai_server = Server(ai_class=OpenAI)
    app = openai_server.app
    uvicorn.run(app, host="0.0.0.0", port=8000)