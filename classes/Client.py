import requests
from types import MethodType

class Client:
    def __init__(self, methods_dict: dict, port: int):
        self.methods_dict = methods_dict
        self.port = port

        self.DEFAULT_TIMEOUT = 25
        self.DEFAULT_GENERATION_TIMEOUT = 120

        created_methods = []

        for method_name in methods_dict.keys():
            # create a function bound to this instance
            def make_endpoint_func(name):
                def endpoint_func(self, **kwargs):
                    try:
                        
                        # Set up timeout
                        if "client_timeout" in kwargs: client_timeout = kwargs["client_timeout"]
                        elif name == "generate": client_timeout = self.DEFAULT_GENERATION_TIMEOUT
                        else: client_timeout = self.DEFAULT_TIMEOUT

                        r = requests.post(
                            f"http://localhost:{self.port}/{name}",
                            json={k: v for k, v in kwargs.items() if k != "client_timeout"},
                            timeout=client_timeout
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

        print(f"📡 Client initialized with methods: {created_methods}")
