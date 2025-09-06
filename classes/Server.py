import json
import asyncio
from fastapi import FastAPI, Request, HTTPException
from classes.BaseAI import BaseAI
import inspect
import traceback
import logging

class Server:
    def __init__(self, ai_class=BaseAI):
        self.app = FastAPI()
        self.AI = ai_class()  # Single instance that persists
        self.lock = asyncio.Lock()
        self._register_routes_from_ai()

    def _register_routes_from_ai(self):
        """
        Automatically register all public methods of the AI class
        as FastAPI endpoints.
        """
        all_methods = [
            method_name for method_name in dir(self.AI)
            if callable(getattr(self.AI, method_name)) and not method_name.startswith('_')
        ]

        for method_name in all_methods:
            # Create endpoint function that captures the method name
            def make_endpoint(method_name):
                async def endpoint(request: Request):
                    async with self.lock:
                        try:
                            # Get the actual method from the persistent AI instance
                            method_obj = getattr(self.AI, method_name)
                            
                            body = await request.json() if request.method != "GET" else {}
                            
                            # Call the method on the persistent instance
                            result = method_obj(**body) if body else method_obj()
                            
                            return {"status": "ok", "method": method_name, "answer": result}
                        except Exception as e:
                            tb = traceback.format_exc()
                            logging.error(f"Error in {method_name}: {e}\n{tb}")
                            print(f"Error in {method_name}: {e}\n{tb}")
                            raise HTTPException(status_code=400, detail=f"{method_name} failed: {str(e)}")
                
                return endpoint
            
            # Register the endpoint
            endpoint_func = make_endpoint(method_name)
            self.app.post(f"/{method_name}")(endpoint_func)

        # Add a health check endpoint
        @self.app.get("/health")
        async def health():
            return {"status": "ok"}
        
        # New endpoint: list all methods with parameter names
        @self.app.get("/info/methods")
        async def list_methods():
            methods_info = {}
            for method_name in all_methods:
                method_obj = getattr(self.AI, method_name)
                sig = inspect.signature(method_obj)
                # Exclude "self" if present
                params = [p.name for p in sig.parameters.values() if p.name != "self"]
                methods_info[method_name] = params
            return methods_info

