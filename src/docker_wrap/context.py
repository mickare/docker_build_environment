import contextlib
import os
from typing import Dict, Union, List

from docker import DockerClient
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container as DockerContainer
from docker.models.images import Image as DockerImage

from docker_wrap.docker_wrap import logger


class ContainerContext:
    class Settings:
        stop_timeout = 10  # type: int

        def __init__(
                self,
                supplier: "ContainerSupplier",
                run_kwargs: Dict[str, Union[str, bool, Dict[str, str], List[str]]] = None
        ):
            assert supplier is not None
            self.supplier = supplier
            self.run_kwargs = run_kwargs if run_kwargs is not None else {}

    def __init__(
            self,
            name:
            str, client: DockerClient,
            settings: "ContainerContext.Settings"
    ):
        assert name
        assert client
        assert settings is not None
        self.name = name
        self.client = client
        self.settings = settings

    def get_container_name(self):
        return self.name + "_container"

    @contextlib.contextmanager
    def provide(self, **run_kwargs):
        """
        Provides a container a started container and then stops it again.
        Use in a "with" statement.

        with ctx.provide() as container:
            container.exec_run(...)

        :param run_kwargs: See https://docker-py.readthedocs.io/en/stable/containers.html for possible arguments.
        :return:
        """
        logger.debug("Providing container {}".format(self.get_container_name()))
        container = self.settings.supplier.create_or_get(self, **run_kwargs)
        try:
            container.start()
            yield container
        finally:
            container.stop(timeout=self.settings.stop_timeout)

    def clean(self, force=True, volumes=False):
        try:
            name = self.get_container_name()
            container = self.client.containers.get(name)
            logger.debug("Removing container {}".format(name))
            container.remove(force=force, volumes=volumes)
        except NotFound:
            pass

    def kill(self, signal=None):
        try:
            container = self.client.containers.get(self.get_container_name())
            container.kill(signal)
        except NotFound:
            pass


class ContainerSupplier:
    # instance variables with defaults
    _container = None  # type: DockerContainer

    def get_image_name(self, ctx: ContainerContext) -> str:
        raise NotImplementedError()

    def get_or_create_image(self, ctx: ContainerContext) -> DockerImage:
        """
        Gets or creates the image of this container source.

        :param ctx: The context to use
        :return: The image
        :raises docker.errors.ImageNotFound
        :raises docker.errors.APIError
        """
        raise NotImplementedError()

    def exists(self, ctx: ContainerContext) -> bool:
        try:
            self._container = ctx.client.containers.get(ctx.get_container_name())
            return True
        except NotFound as e:
            return False

    def create_or_get(self, ctx: ContainerContext, **run_kwargs) -> DockerContainer:
        if self.exists(ctx):
            return self._container
        name = ctx.get_container_name()
        logger.debug("Container {} does not exist. Creating one ...".format(name))
        image = self.get_or_create_image(ctx)

        kwargs = {}
        if ctx.settings.run_kwargs:
            kwargs.update(ctx.settings.run_kwargs)
        if run_kwargs:
            kwargs.update(run_kwargs)

        if "image" in kwargs:
            del kwargs["image"]
        if "name" in kwargs:
            del kwargs["name"]

        self._container = ctx.client.containers.create(
            image=image.id,
            name=name,
            **kwargs
        )
        return self._container


class BuildContainerSupplier(ContainerSupplier):

    def __init__(self, path: str, buildargs: Dict[str, str] = None,
                 suffix: str = '_image'):
        assert path
        assert suffix
        self._dockerfile_path = path
        self._buildargs = buildargs
        self._suffix = suffix
        self._image = None  # type: DockerImage

    def get_image_name(self, ctx: ContainerContext):
        return ctx.name + self._suffix

    def get_or_create_image(self, ctx: ContainerContext) -> DockerImage:
        if self._image is None:
            if os.path.isfile(self._dockerfile_path):
                path = os.path.abspath(os.path.dirname(self._dockerfile_path))
                dockerfile = os.path.basename(self._dockerfile_path)
            else:
                path = os.path.abspath(self._dockerfile_path)
                dockerfile = "Dockerfile"

            full_path = os.path.join(path, dockerfile)
            logger.debug("Building image from {} ...".format(full_path))
            assert os.path.isfile(full_path)  # Check if dockerfile exists

            buildargs = {}
            if ctx.settings.environment:
                buildargs.update(ctx.settings.environment)
            if self._buildargs:
                buildargs.update(buildargs)

            labels = {
                "docker-wrap.context": ctx.name,
                "docker-wrap.dockerfile": full_path
            }

            tag = self.get_image_name(ctx)

            self._image = ctx.client.images.build(
                path=path,
                dockerfile=dockerfile,
                tag=tag,
                buildargs=buildargs,
                network_mode="host",
                labels=labels
            )
            logger.debug("Image {} build".format(tag))
        return self._image


class ImageContainerSupplier(ContainerSupplier):

    def __init__(self, image_name: str):
        assert image_name
        self._image_name = image_name

    def get_image_name(self, ctx: ContainerContext):
        return self._image_name

    def get_or_create_image(self, ctx: ContainerContext) -> DockerImage:
        """
        Gets an the image of this container source.

        :param ctx: The context to use
        :return: The image
        :raises docker.errors.ImageNotFound
        :raises docker.errors.APIError
        """
        image_name = self.get_image_name(ctx)
        try:
            return ctx.client.images.get(image_name)
        except ImageNotFound:
            logger.debug("Image {} not found locally. Pulling ...".format(image_name))
            return ctx.client.images.pull(image_name)
