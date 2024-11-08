from __future__ import annotations

__all__ = ["rpc_method", "JsonRpcServer", "JsonRpcError"]

import inspect
import logging
from typing import TYPE_CHECKING, Any, TypeVar, overload

from orjson import Fragment, dumps, loads

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Sequence

    F = TypeVar("F", bound=Callable[..., Any])


_LOGGER = logging.getLogger("pyjsonrpcserver")
_SENTINEL = object()
_ID = (str, int, float, type(None))
_REQUEST_KEYS = frozenset(("jsonrpc", "method", "params", "id"))


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"[{code}] {message}" + ("" if data is None else f": {data}"))
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        to_return = {"code": self.code, "message": self.message}
        if self.data is not None:  # pragma: no cover
            to_return["data"] = self.data
        return to_return


class _Error:
    PARSE_ERROR = {"code": -32700, "message": "Parse error"}
    INVALID_REQUEST = {"code": -32600, "message": "Invalid Request"}
    METHOD_NOT_FOUND = {"code": -32601, "message": "Method not found"}
    INVALID_PARAMS = {"code": -32602, "message": "Invalid params"}
    INTERNAL_ERROR = {"code": -32603, "message": "Internal error"}


def _respond(
    obj: Any,
    *,
    # mypy poorly supports sentinels
    id: str | float | None | _SENTINEL = None,  # type: ignore[valid-type] # noqa: A002
    error: bool | Any = True,
) -> dict[str, Any] | None:
    if id is _SENTINEL:
        return None
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": id}
    if error:
        response["error"] = obj if error is True else dict(obj, data=error)
    else:
        response["result"] = obj
    return response


@overload
def rpc_method(_func: F) -> F: ...  # pragma: no cover


@overload
def rpc_method(*, name: str | None = None) -> Callable[[F], F]: ...  # pragma: no cover


def rpc_method(
    _func: F | None = None, *, name: str | None = None
) -> Callable[[F], F] | F:
    def decorator(f: F, /) -> F:
        try:
            f.__rpc__ = name  # type: ignore[attr-defined]
        except (AttributeError, TypeError) as e:
            msg = "Could not set the __rpc__ magic attribute"
            raise type(e)(msg) from e
        return f

    return decorator if _func is None else decorator(_func)


class JsonRpcServer:
    def __init__(
        self,
        methods: dict[str, Callable[..., Any]] | None = None,
        *,
        dumps_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._methods = methods or {}
        self._dumps_kwargs = dumps_kwargs or {}
        self.add_object(self)

    def add_object(self, obj: Any, *, prefix: str = "") -> None:
        for name, method in inspect.getmembers(obj, inspect.isroutine):
            try:
                self.add_method(method, name=prefix + (method.__rpc__ or name))  # type: ignore[union-attr]
            except AttributeError:  # noqa: PERF203
                continue

    def add_method(
        self, method: Callable[..., Any], *, name: str | None = None
    ) -> None:
        name = name or getattr(method, "__rpc__", None) or method.__name__
        if name in self._methods:
            msg = f"Method '{name}' already registered"
            raise ValueError(msg)
        self._methods[name] = method

    def _run(self, request: dict[str, Any]) -> dict[str, Any] | None:  # noqa: C901, PLR0911, PLR0912
        # Validate "jsonrpc" entry
        try:
            if request["jsonrpc"] != "2.0":
                return _respond(
                    _Error.INVALID_REQUEST,
                    error=f"Wrong rpc version (got '{request['jsonrpc']!s}')",
                )
        except KeyError:
            return _respond(_Error.INVALID_REQUEST, error="Missing 'jsonrpc' key")
        except TypeError:
            return _respond(
                _Error.INVALID_REQUEST,
                error=f"Not an object (type: {type(request)})",
            )

        if not request.keys() <= _REQUEST_KEYS:
            extra = request.keys() - _REQUEST_KEYS
            return _respond(_Error.INVALID_REQUEST, error=f"Extra keys : {extra}")

        # Extract and validate "id" entry
        id = request.get("id", _SENTINEL)  # noqa: A001
        if not isinstance(id, _ID) and id is not _SENTINEL:
            return _respond(
                _Error.INVALID_REQUEST,
                error=f"'id' must be a number, string or null (type: {type(id)})",
            )

        # Extract and validate "method" entry
        try:
            method_name = request["method"]
        except KeyError:
            return _respond(_Error.INVALID_REQUEST, error="Missing 'method' key")
        if not isinstance(method_name, str):
            return _respond(
                _Error.INVALID_REQUEST,
                error=f"'method' must be a string (type: {type(method_name)})",
            )

        # Extract and validate "params" entry
        args: Sequence[Any] = ()
        kwargs = {}
        if "params" in request:  # LBYL because its absence is not exceptional behavior
            params = request["params"]
            if isinstance(params, dict):
                kwargs = params
            elif isinstance(params, list):
                args = params
            else:
                return _respond(
                    _Error.INVALID_REQUEST,
                    error=f"'params' must be an array or an object (type: {type(params)})",
                )

        # Find rpc method in registry
        try:
            method = self._methods[method_name]
        except KeyError:
            return _respond(_Error.METHOD_NOT_FOUND, id=id)

        # Call method and handle error
        try:
            try:
                result = method(*args, **kwargs)
            except JsonRpcError as e:  # Custom error
                return _respond(e.to_dict(), id=id)
            except TypeError as e:
                try:  # Check if it is caused by invalid params
                    inspect.signature(method).bind(*args, **kwargs)
                except TypeError:
                    return _respond(_Error.INVALID_PARAMS, id=id, error=str(e))
                raise
        except Exception as e:
            _LOGGER.exception(
                "[id: %s] An exception occurred while calling rpc method '%s'",
                "notification" if id is _SENTINEL else str(id),
                method_name,
            )
            return _respond(_Error.INTERNAL_ERROR, id=id, error=str(e))
        return _respond(result, id=id, error=False)

    def _process(
        self, raw_request: bytes | bytearray | memoryview | str
    ) -> dict[str, Any] | list[Fragment] | None:
        try:
            request: dict[str, Any] | list[dict[str, Any]] = loads(raw_request)
        except ValueError as e:
            return _respond(_Error.PARSE_ERROR, error=str(e))
        if isinstance(request, list):  # Batch request
            if not request:
                return _respond(_Error.INVALID_REQUEST, error="Empty batch")
            return [
                Fragment(self._encode(response))
                for r in request
                if (response := self._run(r))  # None (notification) check
            ]
        return self._run(request)

    @overload
    def _encode(self, response: None) -> None: ...  # pragma: no cover

    @overload
    def _encode(self, response: list[Fragment]) -> bytes | None: ...  # pragma: no cover

    @overload
    def _encode(self, response: dict[str, Any]) -> bytes: ...  # pragma: no cover

    def _encode(self, response: dict[str, Any] | list[Fragment] | None) -> bytes | None:
        if not response:  # Notification or empty list (batch response)
            return None
        try:
            return dumps(response, **self._dumps_kwargs)
        except TypeError as e:
            if isinstance(response, list):  # pragma: no cover
                msg = "Should never happen: we are joining fragments of already serialized responses if this is a batch at this point"
                raise RuntimeError(msg) from e  # noqa: TRY004
            id = response["id"]  # noqa: A001
            _LOGGER.exception("[id:%s] Unserializable response", str(id))
            return self._encode(_respond(_Error.INTERNAL_ERROR, id=id, error=str(e)))

    def call(self, request: bytes | bytearray | memoryview | str) -> bytes | None:
        return self._encode(self._process(request))
