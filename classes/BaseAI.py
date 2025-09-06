import os
import json
from random import randint

class BaseAI:
    
    def __init__(self):
        """
        Every AI will:
        - Have their parameters saved on a params.json
        - Generate a response with self.params
        """
        self.params = {}
        self.default_params = {}
        self.params_path = "params.json"

    def set_default_params(self, params_path = None):
        """
        Method that sets parameters to their default settings
        """
        # Update params path attribute
        if params_path: 
            self.params_path = params_path

        # Check if params file exist
        if not os.path.exists(self.params_path):
            raise FileNotFoundError(f"Params json file not found: {self.params_path}")

        # Open and save configurations
        with open(self.params_path, "r", encoding="utf-8") as f:
            self.default_params = json.load(f)
        
        # Set the params to default params
        self.params = self.default_params

        return "Default Parameters were set successfully"

    def get_params(self) -> dict:
        """
        Method will return a dictionary with current params
        """
        safe_params = {}
        for k, v in self.params.items():
            try:
                json.dumps(v)  # test if serializable
                safe_params[k] = v
            except TypeError:
                safe_params[k] = str(v)  # fallback: convert to string
        return safe_params

    def set_params(self, **kwargs):
        """
        Method that allows to change a parameter
        - Checks if the parameter name exists
        - Checks if the parameter types match
        """
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
        
        return "All parameters were set successfully"

    def _generate_random(self) -> int:
        """
        Method that generates a random int to be used as a seed
        """
        return randint(0, 2**32 - 1)

    def generate(self) -> dict:
        """
        This method must be overwritten with the AI generation code
        """
        return {}

