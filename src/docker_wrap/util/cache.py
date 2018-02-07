from typing import TypeVar, Generic, Callable, Any, Optional

T = TypeVar("T")


class Cache(Generic[T]):
    def __init__(self, func: Callable[[Any], T], *args, **kwargs):
        assert callable(func)
        self._func = func  # type: Callable[[Any], T]
        self._args = args
        self._kwargs = kwargs
        self._value = None  # type: T

    @property
    def value(self) -> T:
        if self._value is None:
            self._value = self._func(*self._args, **self._kwargs)
            assert self._value is not None
        return self._value

    @property
    def unsafe(self) -> Optional[T]:
        return self._value

    @unsafe.setter
    def unsafe(self, value):
        self._value = value
