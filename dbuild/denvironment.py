from typing import Dict

import os
from docker import DockerClient
from docker.errors import NotFound, ImageNotFound
from docker.models.images import Image

from dbuild.config.config import Config
from dbuild.util.cache import Cache
from dbuild.util.signal_utils import getSignalName


class BuildContainer:
    def __init__(self, client: DockerClient, name: str, workdir: str, image, volumes):
        assert client is not None
        assert name is not None
        assert callable(image)
        assert callable(volumes)
        self.client = client
        self.name = name
        self.workdir = workdir
        self._image = image
        self._volumes = volumes
        self._container = Cache(self._makeContainer)

    def clean(self):
        if self.checkExists():
            self._container().remove(force=True)

    def _makeContainer(self):
        try:
            container = self.client.containers.get(self.name)
            assert container.image.id == self._image().id  # Container does exist already with another image! Do clean!
            return container
        except NotFound as e:
            pass
        return self.client.containers.create(
            name=self.name,
            image=self._image(),
            volumes=self._volumes(),
            tty=True,
            detach=True,
            working_dir=self.workdir
        )

    def checkExists(self) -> bool:
        try:
            container = self.client.containers.get(self.name)
            assert container.image.id == self._image().id  # Container does exist already with another image! Do clean!
            self._container._value = container
            return True
        except NotFound as e:
            return False

    def exec(self, cmd, environment=None, privileged=False, user=''):
        for line in self._container().exec_run(
                cmd=cmd,
                stream=True,
                environment=environment,
                privileged=privileged,
                user=user):
            print(line.decode())

    def startUp(self):
        if self._container().status != "running":
            self._container().start()

    def shutDown(self):
        if self.checkExists() and self._container().status == "running":
            self._container().stop()

    def kill(self, signum=None):
        if self.checkExists():
            self._container().kill(signal=signum)



class BuildEnvironment():
    def __init__(self, client: DockerClient, name: str, workdir: str, image, volumes):
        self.client = client
        self.name = name
        self.workdir = workdir

        # self.container = None  # type: BuildContainer
        self._container = Cache(self._makeContainer)
        self._image = Cache(self._makeImage, image)
        self._volumes = Cache(self._makeVolumes, volumes)

    def exitGracefully(self, signum, frame):
        if self._container() is not None:
            print("Stopping container via signal: " + getSignalName(signum))
            self._container().kill(signum=signum)
        self.stop()

    def _makeImage(self, image) -> Image:
        if callable(image):
            return image()
        elif isinstance(image, Image):
            return image
        elif isinstance(image, str):
            return self.client.images.get(image)
        raise ValueError("Can't use type '" + str(type(image)) + "' to get image.")

    def _makeVolumes(self, volumes) -> Dict[str, Dict]:
        assert isinstance(volumes, dict)  # Must be a dict of dicts (see docker-py run volumes dict)
        result = dict()  # type: Dict[str, Dict]
        for nameOrPath, vol in volumes.items():
            assert isinstance(vol, dict)
            assert "bind" in vol  # Volume must contain a bind path

            if nameOrPath.startswith('.'):
                nameOrPath = os.path.abspath(nameOrPath)

            result[nameOrPath] = {
                "bind": vol["bind"],
                "mode": vol["mode"] if "mode" in vol else "ro"
            }
        return result

    def _makeContainer(self):
        return BuildContainer(
            client=self.client,
            name=self.name,
            image=self._image,
            volumes=self._volumes,
            workdir=self.workdir
        )

    def start(self):
        if self._container() is not None:
            self._container().startUp()

    def stop(self):
        if self._container() is not None:
            self._container().shutDown()

    def runCommand(self, cmd, environment=None, privileged=False, user=''):
        self._container().exec(cmd=cmd, environment=environment, privileged=privileged, user=user)



def getOrCreateImage(client: DockerClient, config: Config):
    image_name = config["container.image"]
    # Load value from config or build one
    if "container.image" in config:
        try:
            print("Getting image '" + image_name + "'...")
            return client.images.get(image_name)
        except ImageNotFound as e:
            print("Not found locally!")
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
