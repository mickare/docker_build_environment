from typing import Dict, List, Set

import docker
import os
import yaml
from docker import DockerClient
from docker.errors import ImageNotFound

from dbuild.config.config import Config
from dbuild.denvironment import BuildHandler, BuildContainer


def getOrCreateImage(client: DockerClient, config: Config):
    image_name = config["container.image"]
    # Load value from config or build one
    if "container.image" in config:
        try:
            return client.images.get(image_name)
        except ImageNotFound as e:
            print("Image '" + image_name + "' not found locally!")
            pass
        print("Pulling '" + image_name + "'")
        return client.images.pull(image_name)
    elif "container.build" in config:
        # Build from Dockerfile
        image_name = "devenv_" + config["container.name"]

        print(
            "Building from Dockerfile "
            + "'" + config["container.build.dockerfile"] + "'"
            + " in path '" + config["container.build.path"] + "'"
            + " the image '" + image_name + "'"
        )

        return client.images.build(
            path=config["container.build.path"],
            dockerfile=config["container.build.dockerfile"],
            network_mode=config["container.build.network_mode"],
            tag=image_name
        )


class DContext:
    def __init__(self, config: Config, default_workdir='/workdir/'):
        self.config = config
        self.client = None
        self.default_workdir = default_workdir
        self.reloadClient()
        self.handlers = set()  # type: Set[BuildHandler]

    def reloadClient(self):
        self.client = None
        if "docker" in self.config:
            section = self.config["docker"]
            assert isinstance(section, dict)
            if len(section) > 0:
                self.client = docker.DockerClient(**section)
        if self.client is None:
            self.client = docker.DockerClient.from_env()

    def exitGracefully(self, signum, frame):
        while self.handlers:
            self.handlers.pop().exitGracefully(signum, frame)

    def getDefaultWorkdir(self) -> str:
        return self.default_workdir

    def setDefaultWorkdir(self, workdir: str):
        self.default_workdir = workdir

    def getCurrentUser(self) -> str:
        return str(os.getuid()) + ":" + str(os.getgid())

    def clean(self):
        container = BuildContainer(client=self.client, name=self.config["container.name"],
                                   workdir=self.getDefaultWorkdir(), image=None, volumes=None)
        container.clean()

    def execute(self, cmd: List[str], workdir=None, user='', environment: Dict[str, str] = None):
        handler = BuildHandler(
            client=self.client,
            image=lambda: getOrCreateImage(client=self.client, config=self.config),
            name=self.config["container.name"],
            volumes=self.config.get(["container", "volumes"], {}),
            workdir=workdir if workdir is not None else self.getDefaultWorkdir()
        )
        self.handlers.add(handler)
        handler.start()
        handler.runCommand(cmd=cmd, environment=environment, privileged=False, user=user)
        handler.stop()
        self.handlers.remove(handler)
