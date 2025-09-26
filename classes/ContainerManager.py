import os
import time
import docker
import requests
from classes.Client import Client


class ContainerManager:
    def __init__(self, image: str, port: int, name: str = None, use_gpu: bool = True):
        self.client = docker.from_env()
        self.image = image
        self.port = port
        fixed_image_name = image.replace(':', '_')
        self.name = name or f"{fixed_image_name}_{port}"
        self.container = None
        self.use_gpu = use_gpu
        
        # Setting volume path
        # On host: 
        #   The volume is on the project root directory, so you can use a relative path
        # On container: 
        #   You can also use a relative path. 
        #   Because the volume will be inside "/app/" and the working directory is also set to "/app/"
        self.volume_path = "volume"


    def _find_running_container(self):
        """
        Look for an already running container with the same name.
        """
        try:
            container = self.client.containers.get(self.name)
            if container.status == "running":
                return container
        except docker.errors.NotFound:
            return None
        return None

    def start(self):
        """
        Ensure a single instance of the container is running.
        If already running, reuse it. Otherwise, start a new one.
        """
        print(f"Checking for existing container {self.image}...")

        existing = self._find_running_container()
        if existing:
            if existing.status == "running":
                print(f"⚡ Container {self.name} is already running, reusing it")
                self.container = existing
                return
            else:
                print(f"🗑 Removing old stopped container {self.name}")
                existing.remove()

        print(f"Starting new container {self.image} as {self.name}...")

        # Set up host volume directory:
        full_host_volume = os.path.join(
            os.getcwd().replace('\\', '/'), self.volume_path
        ).replace('\\', '/')
        os.makedirs(self.volume_path, exist_ok=True)

        # Run container
        self.container = self.client.containers.run(
            self.image,
            name=self.name,
            detach=True,
            working_dir="/app/",
            ports={f"{self.port}/tcp": self.port},
            environment={},  # pass env vars if needed
            volumes={
                full_host_volume: {
                    "bind": "/app/" + self.volume_path,
                    "mode": "rw",
                }
            },
            device_requests=[
                docker.types.DeviceRequest(
                    count=-1,  # expose all GPUs
                    capabilities=[["gpu"]]
                )
            ] if self.use_gpu else None
        )

        # Wait until health is ok
        print(f"Checking container {self.image} until is OK...")
        for _ in range(50):
            if self.is_healthy():
                print(f"✅ {self.image} container ready")
                return
            time.sleep(5)

        raise RuntimeError(f"❌ {self.image} container failed to start")

    def stop(self):
        print(f"Stopping container {self.image}...")
        if self.container:
            self.container.stop()
            self.container.remove()
            self.container = None
            print(f"✅ {self.image} stopped successfully")
        else:
            print(f"ℹ️ No container for {self.image} was running")

    def restart(self):
        print(f"Restarting container {self.image}...")
        self.stop()
        self.start()

    def is_healthy(self):
        try:
            r = requests.get(f"http://localhost:{self.port}/health", timeout=2)
            return r.json().get("status") == "ok"
        except Exception:
            return False
        
    def create_client(self):
        """
        Create a Client instance based on the methods exposed
        by the container's /info/methods endpoint.
        """
        if not self.is_healthy():
            raise RuntimeError("Container is not healthy, cannot create client")

        try:
            r = requests.get(f"http://localhost:{self.port}/info/methods", timeout=5)
            r.raise_for_status()
            methods_dict = r.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch methods from container: {e}")

        return Client(methods_dict, self.port)
