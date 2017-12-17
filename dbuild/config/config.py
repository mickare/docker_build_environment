from typing import Dict, Optional

import copy


class Config():
    def __init__(self, values: Dict = None, nullable: bool = False):
        self.values = dict() if values is None else values  # type: Dict
        self.nullable = nullable

    def _getDict(self, section: Dict, keys, makeparents: bool = False) -> Dict:
        assert isinstance(section, dict)
        if len(keys) > 0:
            key = keys[0]
            child = None
            if key not in section:
                if makeparents:
                    child = dict()
                    section[key] = child
                else:
                    raise KeyError("'" + str(key) + "' is not a key")
            else:
                child = section[key]
            return self._getDict(section=child, keys=keys[1:], makeparents=makeparents)
        return section

    def _hasKey(self, section: Dict, key) -> bool:
        return key in section and (self.nullable or section[key] is not None)

    def has(self, keys) -> bool:
        assert len(keys) > 0  # No keys check
        try:
            section = self._getDict(section=self.values, keys=keys[:-1])
            return self._hasKey(section=section, key=keys[-1])
        except:
            return False

    def get(self, keys, default=None) -> Optional:
        assert len(keys) > 0  # No keys check
        section = self._getDict(section=self.values, keys=keys[:-1])
        key = keys[-1]
        if self._hasKey(section=section, key=key):
            return section[key]
        if default is not None and callable(default):
            return default()
        else:
            return default

    def set(self, keys, value):
        assert len(keys) > 0  # No keys check
        section = self._getDict(section=self.values, keys=keys[:-1], makeparents=True)
        key = keys[-1]
        oldvalue = section[key] if key in section else None
        section[key] = value
        return oldvalue

    def _update(self, section: Dict, content: Dict):
        for k, v in content.items():
            if isinstance(v, dict):
                if k in section and isinstance(section[k], dict):
                    self._update(section=section[k], content=v)
                else:
                    section[k] = copy.deepcopy(v)
            else:
                section[k] = v

    def update(self, content):
        self._update(self.values, content)

    def __contains__(self, key):
        if isinstance(key, str):
            return self.has(key.split("."))
        else:
            raise TypeError("get key of type " + str(type(key)) + " is unsupported")

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.get(key.split("."))
        else:
            raise TypeError("get key of type " + str(type(key)) + " is unsupported")

    def __setitem__(self, key, value):
        if isinstance(key, str):
            return self.set(keys=key.split("."), value=value)
        else:
            raise TypeError("get key of type " + str(type(key)) + " is unsupported")

    def __str__(self):
        return str(self.values)
