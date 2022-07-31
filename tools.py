from collections.abc import Iterable


class FilteredDict(dict):
    __slots__ = ("_allowed_keys",)

    def _process_args(self, mapping_or_iterable, kw_dict):
        kw_dict.update(mapping_or_iterable)
        return ((k, v) for k, v in kw_dict.items() if k in self._allowed_keys)

    def __init__(self, allowed_keys=None, mapping_or_iterable=(), **kwargs):
        if not isinstance(allowed_keys, Iterable):
            raise TypeError("'allowed_keys' is not iterable")
        self._allowed_keys = allowed_keys
        super().__init__(self._process_args(mapping_or_iterable, kwargs))

    def __setitem__(self, k, v):
        if k not in self._allowed_keys:
            raise KeyError(
                f"key: {k!r} not in allowed keys: {self._allowed_keys!r}")
        super().__setitem__(k, v)

    def setdefault(self, k, default=None):
        if k not in self._allowed_keys:
            raise KeyError(
                f"key: {k!r} not in allowed keys: {self._allowed_keys!r}")
        return super().setdefault(k, default)

    def update(self, mapping_or_iterable=(), **kwargs):
        super().update(self._process_args(mapping_or_iterable, kwargs))

    def copy(self):
        return type(self)(self._allowed_keys, self)

    @classmethod
    def fromkeys(cls, allowed_keys, keys, v=None):
        return cls(allowed_keys, ((k, v) for k in keys))

    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, super().__repr__())
