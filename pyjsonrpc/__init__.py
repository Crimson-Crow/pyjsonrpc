import inspect
import json
import warnings
from collections.abc import Callable
from functools import singledispatch
from importlib.resources import read_text
from typing import Any, TypeVar, TypedDict, Literal, NotRequired, ParamSpec, Generic

from jsonschema_rs import JSONSchema

REQUEST_VALIDATOR: JSONSchema = JSONSchema.from_str(
    read_text(__package__, "jsonrpc-request-2.0.json")
)
RESPONSE_VALIDATOR: JSONSchema = JSONSchema.from_str(
    read_text(__package__, "jsonrpc-response-2.0.json")
)

ID = str | int | float | None


class Error(TypedDict):
    code: int
    message: str
    data: NotRequired[Any]


class Request(TypedDict):
    jsonrpc: Literal["2.0"]
    method: str
    params: NotRequired[list | dict]
    id: NotRequired[ID]


class Response(TypedDict):
    jsonrpc: Literal["2.0"]
    result: NotRequired[Any]
    error: NotRequired[Error]
    id: ID


class ErrorType:
    PARSE_ERROR = Error(code=-32700, message="Parse error")
    INVALID_REQUEST = Error(code=-32600, message="Invalid Request")
    METHOD_NOT_FOUND = Error(code=-32601, message="Method not found")
    INVALID_PARAMS = Error(code=-32602, message="Invalid params")
    INTERNAL_ERROR = Error(code=-32603, message="Internal error")


P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")


def split_params(params: tuple | dict) -> tuple[tuple, dict]:
    if isinstance(params, dict):
        args = params.pop("__args", ())
        kwargs = params
    else:
        args = params
        kwargs = {}
    return args, kwargs


def merge_params(args: tuple, kwargs: dict) -> tuple | dict:
    if kwargs:
        if args:
            kwargs["__args"] = args
        return kwargs
    elif args:
        return args


@singledispatch
def rpc_method(f: Callable[P, R]) -> Callable[P, R]:
    f._rpc_method = f.__name__
    return f


@rpc_method.register
def _(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        f._rpc_method = name
        return f

    return decorator


# def rpc_method(func_or_name: Callable | str) -> Callable:
#     if callable(func_or_name):
#         func_or_name._rpc_method = None
#         return func_or_name
#     elif isinstance(func_or_name, str):
#
#         def inner(func):
#             func._rpc_method = func_or_name
#             return func
#
#         return inner
#     else:
#         raise TypeError(
#             "Must be used as a plain decorator or with a single str argument"
#         )


class JsonRpc(Generic[T, R]):
    def __init__(
        self,
        methods: dict[str, Callable] | None = None,
        skip_validation: bool = False,
        json_loads: Callable[[T], Any] = json.loads,
        json_dumps: Callable[..., R] = json.dumps,
    ):
        self.methods = methods or {}
        self.skip_validation = skip_validation
        self._json_loads = json_loads
        self._json_dumps = json_dumps

        for method_name in dir(self):
            method = getattr(self, method_name)
            try:
                self.methods[method._rpc_method] = method
            except AttributeError:
                continue

    def _run(self, request: Request) -> Response | None:
        if not self.skip_validation and not REQUEST_VALIDATOR.is_valid(request):
            return Response(jsonrpc="2.0", error=ErrorType.INVALID_REQUEST, id=None)

        is_notif = "id" not in request
        try:
            method = self.methods[request["method"]]
        except KeyError:
            if is_notif:
                return
            return Response(
                jsonrpc="2.0", error=ErrorType.METHOD_NOT_FOUND, id=request["id"]
            )
        try:
            params = request["params"]
        except KeyError:
            args, kwargs = (), {}
        else:
            args, kwargs = split_params(params)
        try:
            result = method(*args, **kwargs)
        except Exception as e:
            error = ErrorType.INTERNAL_ERROR
            if isinstance(e, TypeError):  # TODO validate Invalid params implementation
                try:
                    inspect.signature(method).bind(*args, **kwargs)
                except TypeError:
                    error = ErrorType.INVALID_PARAMS

            if error == ErrorType.INTERNAL_ERROR:
                warnings.warn(RuntimeWarning(e))

            if is_notif:
                return
            return Response(
                jsonrpc="2.0", error=error | {"data": str(e)}, id=request["id"]
            )
        if not is_notif:
            return Response(jsonrpc="2.0", result=result, id=request["id"])

    def call(self, raw_request: T, **dumps_kwargs) -> R | None:
        try:
            request = self._json_loads(raw_request)
        except Exception as e:
            response = Response(
                jsonrpc="2.0",
                error=Error(**ErrorType.PARSE_ERROR, data=str(e)),
                id=None,
            )
        else:
            response = (
                [r for r in map(self._run, request) if r]
                if isinstance(request, list)
                else self._run(request)
            )
        return self._json_dumps(response, **dumps_kwargs) if response else None
        # TODO determine what happens if encoding error


# class JsonClient:
#     def __init__(
#         self, id_factory: Callable, json_loads=json.loads, json_dumps=json.dumps
#     ):
#         self.id_factory = id_factory
#         self._json_loads = json_loads
#         self._json_dumps = json_dumps
#
#     def build_request(self, method: str, *args, **kwargs):
#         return self._json_dumps(
#             Request(
#                 jsonrpc="2.0",
#                 method=method,
#                 params=merge_params(args, kwargs),
#                 id=self.id_factory(),
#             )
#         )


# class JsonRpcError(RuntimeError):
#     code = None
#     message = None
#     data = None
#
#     def __init__(self, code=None, message=None, data=None):
#         self.code = code or self.code
#         self.message = message or self.message
#         self.data = data
#         super().__init__(self.message)
#
#     def __str__(self):
#         return f"JsonRpcError({self.code}): {self.message}"
