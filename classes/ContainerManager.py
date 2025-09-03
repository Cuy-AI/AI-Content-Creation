import docker
import requests
import time
import os

class ContainerManager:
    def __init__(self, image: str, port: int, name: str = None, use_gpu: bool = True):
        self.client = docker.from_env()
        self.image = image
        self.port = port
        fixed_image_name = image.replace(':', '_')
        self.name = name or f"{fixed_image_name}_{port}"
        self.container = None
        self.use_gpu = use_gpu
        
        # Set host volume paths
        self.host_volume = f'volume'
        self.full_host_volume = os.path.join(
            os.getcwd().replace('\\', '/'), self.host_volume
        ).replace('\\', '/')
        os.makedirs(self.host_volume, exist_ok=True)  # ensure dir exists

        # Set container volume path
        self.container_volume = "/app/volume"

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

        # Run container
        self.container = self.client.containers.run(
            self.image,
            name=self.name,
            detach=True,
            ports={f"{self.port}/tcp": self.port},
            environment={},  # pass env vars if needed
            volumes={
                self.full_host_volume: {
                    "bind": self.container_volume,
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
