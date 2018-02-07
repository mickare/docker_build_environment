from typing import Dict, Optional, List

import copy

import functools


class Config:
    def __init__(self, values: Dict = None, nullable: bool = False):
        self.values = dict() if values is None else values  # type: Dict
        self.nullable = nullable

    class Section:

        @classmethod
        def handles(cls, delegate):
            return False

        @classmethod
        def wrap(cls, config: "Config", delegate):
            raise NotImplementedError()

        def __contains__(self, key) -> bool:
            raise NotImplementedError()

        def __getitem__(self, key):
            raise NotImplementedError()

        def __setitem__(self, key, value):
            raise NotImplementedError()

        def get_section(self, keys: List, make_parents: bool = False) -> "Config.Section":
            raise NotImplementedError

    class ContainerSection(Section):

        @classmethod
        def handles(cls, delegate):
            return hasattr(delegate, "__getitem__") and hasattr(delegate, "__contains__")

        @classmethod
        def wrap(cls, config: "Config", delegate):
            assert cls.handles(delegate)
            return cls(config, delegate)

        def __init__(self, config: "Config", delegate):
            assert config is not None
            assert self.__class__.handles(delegate)
            self.config = config
            self.delegate = delegate

        def __contains__(self, key) -> bool:
            return key in self.delegate and (self.config.nullable or self.delegate[key] is not None)

        def __getitem__(self, key):
            return self.delegate[key]

        def __setitem__(self, key, value):
            self.delegate[key] = value

        def get_section(self, keys: List, make_parents: bool = False) -> "Config.Section":
            if len(keys) == 0:
                return self
            key = keys[0]

            if key in self.delegate:
                next_delegate = self.delegate[key]
            elif make_parents:
                next_delegate = dict()
                self.delegate[key] = next_delegate
            else:
                raise KeyError("'%s' is not a key" % key)
            return self.config._wrap_section(next_delegate).get_section(keys[:-1], make_parents)

    class ListSection(Section):

        @classmethod
        def handles(cls, delegate):
            return isinstance(delegate, Dict)

        @classmethod
        def wrap(cls, config: "Config", delegate):
            assert cls.handles(delegate)
            return cls(config, delegate)

        def __init__(self, config: "Config", delegate: List):
            assert config is not None
            assert isinstance(delegate, List)
            self.config = config
            self.delegate = delegate  # type: List

        def __contains__(self, key) -> bool:
            key = int(key)
            return key < len(self.delegate) and (self.config.nullable or self.delegate[key] is not None)

        def __getitem__(self, key):
            return self.delegate[key]

        def __setitem__(self, key, value):
            self.delegate[int(key)] = value

        def get_section(self, keys: List, make_parents: bool = False) -> "Config.Section":
            if len(keys) == 0:
                return self
            key = int(keys[0])

            if key < len(self.delegate):
                next_delegate = self.delegate[key]
            elif make_parents and key == len(self.delegate):
                next_delegate = dict()
                self.delegate.append(next_delegate)
            else:
                raise KeyError("'%s' is not a key" % key)
            return self.config._wrap_section(next_delegate).get_section(keys[:-1], make_parents)

    def _wrap_section(self, section):
        assert section is not None
        if Config.ListSection.handles(section):
            return Config.ListSection.wrap(self, section)
        elif Config.ContainerSection.handles(section):
            return Config.ContainerSection.wrap(self, section)
        else:
            raise KeyError("unsupported section of type %s" % type(section))

    def _get_section(self, section, keys: List, make_parents: bool = False) -> "Config.Section":
        return self._wrap_section(section).get_section(keys, make_parents)

    def __has(self, keys) -> bool:
        assert len(keys) > 0  # No keys check
        try:
            section = self._get_section(section=self.values, keys=keys[:-1])
            return keys[-1] in section
        except KeyError:
            return False

    def __get(self, keys, default=None) -> Optional:
        assert len(keys) > 0  # No keys check
        section = self._get_section(section=self.values, keys=keys[:-1])
        key = keys[-1]
        if key in section:
            return section[key]
        if default is not None and callable(default):
            return default()
        else:
            return default

    def __set(self, keys, value):
        assert len(keys) > 0  # No keys check
        section = self._get_section(section=self.values, keys=keys[:-1], make_parents=True)
        key = keys[-1]
        old_value = section[key] if key in section else None
        section[key] = value
        return old_value

    def __update(self, section: Dict, content: Dict):
        for k, v in content.items():
            if isinstance(v, dict):
                if k in section and isinstance(section[k], dict):
                    self.__update(section=section[k], content=v)
                else:
                    section[k] = copy.deepcopy(v)
            else:
                section[k] = v

    def update(self, content):
        self.__update(self.values, content)

    def __contains__(self, key):
        if isinstance(key, str):
            return self.__has(key.split("."))
        else:
            raise TypeError("get key of type " + str(type(key)) + " is unsupported")

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.__get(key.split("."))
        else:
            raise TypeError("get key of type " + str(type(key)) + " is unsupported")

    def __setitem__(self, key, value):
        if isinstance(key, str):
            return self.__set(keys=key.split("."), value=value)
        else:
            raise TypeError("get key of type " + str(type(key)) + " is unsupported")

    def __str__(self):
        return str(self.values)
