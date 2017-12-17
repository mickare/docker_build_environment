from typing import TypeVar, Generic, Callable, Any

T = TypeVar("T")


class Cache(Generic[T]):
    def __init__(self, func: Callable[[Any], T], *args, **kwargs):
        assert callable(func)
        self._func = func  # type: Callable[[Any], T]
        self._args = args
        self._kwargs = kwargs
        self._value = None  # type: T

    def __call__(self, *args, **kwargs):
        if self._value is None:
            self._value = self._func(*self._args, **self._kwargs)
        return self._value

    def get(self) -> T:
        return self._value
