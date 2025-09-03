import requests
from types import MethodType

class Component:
    def __init__(self, ai_class, port: int):
        self.ai = ai_class
        self.port = port

        # Dynamically create methods based on ai_class methods
        created_methods = []
        for method_name in dir(ai_class):
            if method_name.startswith("_"):
                continue  # skip dunder/private methods
            
            # create a function bound to this instance
            def make_endpoint_func(name):
                def endpoint_func(self, **kwargs):
                    try:
                        r = requests.post(
                            f"http://localhost:{self.port}/{name}",
                            json=kwargs,
                            timeout=25 if name != "generate" else 120
                        )
                        r.raise_for_status()
                        return r.json()
                    except Exception as e:
                        raise RuntimeError(f"Error calling {name}: {e}")
                return endpoint_func

            # bind the function as a method
            func = make_endpoint_func(method_name)
            setattr(self, method_name, MethodType(func, self))
            created_methods.append(method_name)

        print(f"The following methods were created for the component {ai_class.__name__}:")
        print(created_methods)
