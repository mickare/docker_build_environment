#
from enum import IntEnum
from typing import List, Dict, Optional

import yaml

from docker_wrap.context import BuildContainerSupplier, ImageContainerSupplier, ContainerSupplier


class ConfigSource:
    # instance variables with default
    _loaded = False
    _config = None

    @property
    def config(self) -> "Config":
        if not self._loaded:
            self.reload()
        return self._config

    def reload(self):
        raise NotImplementedError()

    def __str__(self):
        return "unknown"


class FileConfigSource(ConfigSource):

    def __init__(self, file: str):
        self.file = file

    def reload(self):
        with open(file=self.file, mode='r') as f:
            self._config = Config(source=self, values=yaml.load(f))
            self._loaded = True

    def __str__(self):
        return "Configfile \"%s\"" % self.file


class Config:
    def __init__(self, source: ConfigSource, values):
        self.source = source
        self.container = ContainerConfig(self, values["container"])


class ConfigError(Exception):
    def __init__(self, config: Config, msg):
        super(msg)
        self.config = config

    def __str__(self):
        return "Config error in " + str(self.config.source) + ": " + super(ConfigError, self).__str__()


class VolumeConfig:

    def __init__(self, config: Config, values):
        self.volumes = [VolumeConfig.Entry(config, v) for v in values.get("volumes", [])]

    class Entry:
        # instance variables with defaults
        mode = 'rw'

        def __init__(self, config: Config, values):
            if isinstance(values, str):
                self.host_path, self.mount_path, *rest = values.split(':', 3)
                if len(rest) == 1:
                    self.mode = rest[0]
                elif len(rest) > 1:
                    raise ConfigError(config, "Invalid volume string: %s" % values)
            elif isinstance(values, dict):
                self.host_path = values["host"]
                self.mount_path = values["mount"]
                self.mode = values.get("mode", self.mode)
            assert self.host_path
            assert self.mount_path
            assert self.mode


class EnvironmentConfig:
    # instance variables with defaults
    _values = dict()  # type: Dict[str, str]

    def __init__(self, config: Config, values):
        if isinstance(values, List):

            def check_env(l):
                for line in l:
                    assert isinstance(line, str)
                    k, v = line.split('=', 2)
                    assert k  # Key is not empty
                    yield k, v

            self._values = dict(check_env(values))

        elif isinstance(values, Dict):

            def check_env(d):
                for k, v in d:
                    assert isinstance(k, str)  # Environment variable key is not a string!
                    assert isinstance(v, str)  # Environment variable content is not a string!
                    assert k  # Key is not empty
                    yield k, v

            self._values = dict(check_env(values))

        else:
            raise ConfigError(config, "Invalid environment variables definition: %s" % type(values))

    @property
    def values(self):
        return self._values.copy()

    def get_default(self, defaults: Optional[Dict[str, str]]) -> Dict[str, str]:
        result = self.values.copy()
        if defaults:
            for k, v in defaults:
                result.setdefault(k, v)
        return result


class ContainerNetworkConfig:
    class Mode(IntEnum):
        BRIDGE = 1
        NONE = 2
        HOST = 3

        @classmethod
        def from_string(cls, name: str):
            return cls[name.upper()]

    class Entry:
        options = None

        def __init__(self, config: Config, values, network=None):
            if isinstance(values, str):
                self.network = values
            elif isinstance(values, Dict):
                assert network is not None
                self.network = network
                self.options = values

    # instance variables with defaults
    networks = []  # type: List[Entry]
    _use_networks = False
    network_mode = Mode.HOST  # type: Mode

    def __init__(self, config: Config, values):
        if "network" in values and "network_mode" in values:
            raise ConfigError(config, "network is incompatible with network_mode")

        if "networks" in values:
            networks = values["networks"]
            self._use_networks = True
            if isinstance(networks, List):
                self.networks = []
                for line in networks:
                    assert isinstance(line, str)
                    assert line
                    self.networks.append(ContainerNetworkConfig.Entry(config, line))
            elif isinstance(networks, Dict):
                self.networks = []
                for k, v in networks:
                    assert isinstance(k, str)
                    assert k
                    self.networks.append(ContainerNetworkConfig.Entry(config, v, network=k))
            else:
                raise ConfigError(config, "Invalid networks configuration type: %s" % type(networks))
        elif "network_mode" in values:
            network_mode = values["network_mode"]
            network_mode = network_mode.lower() if network_mode is not None else "none"
            try:
                self.network_mode = ContainerNetworkConfig.Mode.from_string(network_mode)
                self._use_networks = False
            except KeyError as e:
                raise ConfigError(config, "Invalid network mode %s" % network_mode) from e

    @property
    def use_networks(self):
        return self._use_networks


class ContainerSupplierConfig:
    def to_supplier(self) -> ContainerSupplier:
        raise NotImplementedError()


class ContainerBuildConfig(ContainerSupplierConfig):
    path = None  # type: str
    buildargs = {}  # type: Dict[str, str]
    suffix = '_image'

    def __init__(self, config: Config, values):
        if isinstance(values, str):
            self.path = values
        elif isinstance(values, dict):
            self.path = values["path"]
            self.buildargs = values.get("buildargs", {})
        else:
            raise ConfigError(config, "Invalid build definition: %s" % type(values))
        assert self.path

    def to_supplier(self) -> BuildContainerSupplier:
        return BuildContainerSupplier(path=self.path, buildargs=self.buildargs, suffix=self.suffix)


class ContainerImageConfig(ContainerSupplierConfig):
    image_name = None  # type: str

    def __init__(self, config: Config, values):
        if isinstance(values, str):
            self.image_name = values
        else:
            raise ConfigError(config, "Invalid image definition: %s" % type(values))
        assert self.image_name

    def to_supplier(self) -> ImageContainerSupplier:
        return ImageContainerSupplier(image_name=self.image_name)


class ContainerConfig:
    # instance variables with defaults
    image = None
    build = None
    network_mode = None

    def __init__(self, config: Config, values):
        if "image" in values and "build" in values:
            raise ConfigError(config, "Can not use image {} and build the container {}".format(values["image"],
                                                                                               values["build"]))
        elif "image" in values:
            self.image = values["image"]
        elif "build" in values:
            self.build = values["build"]
        else:
            raise ConfigError(config, "Missing information: either \"image\" or \"build\"")

        self.volumes = VolumeConfig(config, values.get("volumes", []))
        self.environment = EnvironmentConfig(config, values.get("environment", dict()))
        self.network = ContainerNetworkConfig(config, values)
