import os
from typing import Dict

from docker import DockerClient
from docker.errors import NotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer

from docker_wrap.util.cache import Cache
from docker_wrap.util.signal_utils import get_signal_name


class ContainerContext:
    def __init__(self, client: DockerClient, name: str, working_dir: str, image, volumes):
        assert client is not None
        assert name is not None
        assert image is None or callable(image)
        assert volumes is None or callable(volumes)
        self.client = client
        self.name = name
        self._working_dir = working_dir
        self._image = image
        self._volumes = volumes
        self._container = Cache(self.__load_container)  # type: Cache[DockerContainer]

    @property
    def container(self):
        return self._container.value

    def clean(self):
        if self.exists():
            self.container.remove(force=True)

    def __load_container(self) -> DockerContainer:
        if not self.exists():
            return self.client.containers.create(
                name=self.name,
                image=self._image(),
                volumes=self._volumes(),
                tty=True,
                detach=True,
                working_dir=self._working_dir
            )

    def exists(self) -> bool:
        try:
            container = self.client.containers.get(self.name)
            assert container.image.id == self._image().id  # Container does exist already with another image! Do clean!
            self._container.unsafe = container
            return True
        except NotFound as e:
            return False

    def execute(self, cmd, environment=None, privileged=False, user=''):
        for line in self.container.exec_run(
                cmd=cmd,
                stream=True,
                environment=environment,
                privileged=privileged,
                user=user):
            print(line.decode())

    def start_up(self):
        if self.container.status != "running":
            self.container.start()

    def shut_down(self):
        if self.exists() and self.container.status == "running":
            self.container.stop()

    def kill(self, signum=None):
        if self.exists():
            self.container.kill(signal=signum)


class BuildHandler:
    def __init__(self, client: DockerClient, name: str, workdir: str, image, volumes):
        self.client = client
        self.name = name
        self.workdir = workdir

        # self.container = None  # type: BuildContainer
        self._container = Cache(self._make_container)
        self._image = Cache(self._make_image, image)
        self._volumes = Cache(self._make_volumes, volumes)

    def exit_gracefully(self, signum, frame):
        if self._container() is not None:
            print("Stopping container via signal: " + get_signal_name(signum))
            self._container().kill(signum=signum)
        self.stop()

    def _make_image(self, image) -> DockerImage:
        if isinstance(image, DockerImage):
            return image
        elif callable(image):
            img = image()
            assert isinstance(img, DockerImage)
            return img
        elif isinstance(image, str):
            return self.client.images.get(image)
        raise ValueError("Can't use type '" + str(type(image)) + "' to get image.")

    def _make_volumes(self, volumes) -> Dict[str, Dict]:
        assert isinstance(volumes, dict)  # Must be a dict of dicts (see docker-py run volumes dict)
        result = dict()  # type: Dict[str, Dict]
        for name_or_path, vol in volumes.items():

            if isinstance(vol, str):

            elif isinstance(vol, dict):
                assert "bind" in vol  # Volume must contain a bind path

                if name_or_path.startswith('.'):
                    name_or_path = os.path.abspath(name_or_path)

                result[name_or_path] = {
                    "bind": vol["bind"],
                    "mode": vol["mode"] if "mode" in vol else "ro"
                }
            else:
                raise ValueError("Invalid volume %s definition.", name_or_path)
        return result

    def _make_container(self):
        return BuildContainer(
            client=self.client,
            name=self.name,
            image=self._image,
            volumes=self._volumes,
            workdir=self.workdir
        )

    def start(self):
        if self._container() is not None:
            self._container().start_up()

    def stop(self):
        if self._container() is not None:
            self._container().shut_down()

    def runCommand(self, cmd, environment=None, privileged=False, user=''):
        self._container().execute(cmd=cmd, environment=environment, privileged=privileged, user=user)
