import os
import json
from random import randint
from openai import OpenAI
from dotenv import load_dotenv

class OpenRouteLM:

    def __init__(
            self, 
            model_name: str = "openai/gpt-oss-20b:free", 
            schema: dict = None,
            params_path: str = "lm/params.json",
            models_path: str = "lm/models.json"
        ):
        
        # Set up model name/path
        self.model_name = self._set_model_name(model_name, models_path)
        self.models_path = models_path

        # Load default params
        self.default_params = self._load_default_params(params_path)
        self.params_path = params_path
        self.params = self.default_params

        # Set json schema for response
        self.set_schema(schema)

        # Load API key from.env
        load_dotenv()
        self.api_key = os.getenv("LLM_OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("LLM_OPENROUTER_API_KEY not set in environment")
        
        # Create OpenAI Client
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )


    def _load_default_params(self, params_path: str) -> dict:

        # Check if params file exist
        if not os.path.exists(params_path):
            raise FileNotFoundError(f"Params json file not found: {params_path}")

        # Open and save configurations
        with open(params_path, "r", encoding="utf-8") as f:
            default_params = json.load(f)

        return default_params


    def _set_model_name(self, model_name: str, models_path: str):
         # Check if models file exist
        if not os.path.exists(models_path):
            raise FileNotFoundError(f"Models json file not found: {models_path}")

        # Open and save configurations
        with open(models_path, "r", encoding="utf-8") as f:
            dic = json.load(f)

        # Check if model name is on models key
        if model_name not in dic["models"]:
            raise ValueError(f"Model not found in models list: {model_name}")

        return model_name


    def get_parameters(self) -> dict:
        # Return a copy of the current parameters
        return self.params.copy()
    
    def get_schema(self) -> dict:
        # Return a copy of the current schema
        return self.schema.copy()
    

    def set_parameters(self, **kwargs):
        # For every parameter
        for key, value in kwargs.items():
            # Check if the parameter exists
            if key in self.params:
                # Check if the type is correct
                if isinstance(value, type(self.params[key])):
                    self.params[key] = value
                else:
                    raise TypeError(f"Expected type {type(self.params[key])} for parameter '{key}', got {type(value)}")
            else:
                raise KeyError(f"Unknown parameter '{key}' for model '{self.model_name}'")
            

    def set_schema(self, schema: dict):
        if schema:
            self.schema = schema
        else:
            self.schema = {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                },
                "required": ["answer"]
            }

        self.response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "strict": True,
                "schema": self.schema
            }
        }



    def generate(self, prompt: str, save_path: str = None, fix_prompt_with_schema: bool = False) -> dict:

        # Fix prompt
        if fix_prompt_with_schema:
            schema_str = json.dumps(self.schema, indent=2)
            prompt = (
                "Respond ONLY with a valid JSON object matching this schema.\n"
                "IMPORTANT:\n"
                "- Do NOT include any Markdown formatting (no ```json, no triple backticks).\n"
                "- Do NOT include explanations, comments, or text outside the JSON.\n"
                "- Always complete the JSON with all required fields.\n"
                "- Output must be pure JSON only.\n\n"
                f"Schema:\n{schema_str}\n\n"
                "Prompt:\n"
                f"{prompt}"
            )

        # Build and send request parameters
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{
                "role": "user", 
                "content": prompt
            }],
            response_format=self.response_format,
            seed=randint(0, 2**32 - 1),
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
            "output": output_json
        }

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(final_output, f, indent=2, ensure_ascii=False)
        
        return final_output