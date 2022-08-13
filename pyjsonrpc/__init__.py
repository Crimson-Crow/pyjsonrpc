import json
from collections.abc import Callable
from importlib.resources import read_text
from typing import Optional, Any, TypeVar, TypedDict, Literal, ParamSpec

from jsonschema_rs import JSONSchema

REQUEST_VALIDATOR: JSONSchema = JSONSchema.from_str(read_text(__package__, 'jsonrpc-request-2.0.json'))
RESPONSE_VALIDATOR: JSONSchema = JSONSchema.from_str(read_text(__package__, 'jsonrpc-response-2.0.json'))


class Error(TypedDict, total=False):
    code: int
    message: str
    data: Any


class Request(TypedDict, total=False):
    jsonrpc: Literal['2.0']
    method: str
    params: list | dict
    id: str | int | float | None


class Response(TypedDict, total=False):
    jsonrpc: Literal['2.0']
    result: Any
    error: Error
    id: str | int | float | None


T = TypeVar('T')
R = TypeVar('R')


def split_params(params: tuple | dict) -> tuple[tuple, dict]:
    if isinstance(params, dict):
        args = params.pop('__args', [])
        kwargs = params
    else:
        args = params
        kwargs = {}
    return args, kwargs


def merge_params(args: tuple, kwargs: dict) -> tuple | dict:
    if kwargs:
        if args:
            kwargs['__args'] = args
        return kwargs
    elif args:
        return args


def rpc_method(func_or_name: Callable | str) -> Callable:
    if callable(func_or_name):
        func_or_name._rpc_method = None
        return func_or_name
    elif isinstance(func_or_name, str):
        def inner(func):
            func._rpc_method = func_or_name
            return func
        return inner
    else:
        raise TypeError('Must be used as a plain decorator or with a single str argument')


class JsonRpc:
    def __init__(self, methods: Optional[dict[str, Callable]] = None, json_loads: Callable[[T], Any] = json.loads,
                 json_dumps: Callable[..., R] = json.dumps):
        self.methods = methods or {}
        self._json_loads = json_loads
        self._json_dumps = json_dumps

        for method_name in dir(self):
            method = getattr(self, method_name)
            if hasattr(method, '_rpc_method'):
                self.methods[method._rpc_method or method.__name__] = method

    def _run(self, request: Request) -> Optional[Response]:
        if not REQUEST_VALIDATOR.is_valid(request):
            return Response(jsonrpc='2.0', error=Error(code=-32600, message='Invalid Request'), id=None)
        is_not_notification = 'id' in request
        try:
            method = self.methods[request['method']]
        except KeyError:
            if not is_not_notification:
                return
            return Response(jsonrpc='2.0', error=Error(code=-32601, message='Method not found'), id=request['id'])
        try:
            params = request['params']
        except KeyError:
            args, kwargs = (), {}
        else:
            args, kwargs = split_params(params)
        try:
            result = method(*args, **kwargs)
        except Exception as e:
            if not is_not_notification:
                return
            if isinstance(e, TypeError):  # TODO validate Invalid params implementation
                return Response(jsonrpc='2.0', error=Error(code=-32602, message='Invalid params', data=str(e)), id=request['id'])
            else:
                return Response(jsonrpc='2.0', error=Error(code=-32603, message='Internal error', data=str(e)), id=request['id'])
        if is_not_notification:
            return Response(jsonrpc='2.0', result=result, id=request['id'])

    def call(self, raw_request: T, **dumps_kwargs) -> Optional[R]:
        try:
            request = self._json_loads(raw_request)
        except Exception as e:
            return Response(jsonrpc='2.0', error=Error(code=-32700, message='Parse error', data=str(e)), id=None)
        if response := [r for r in map(self._run, request) if r] if isinstance(request, list) else self._run(request):
            return self._json_dumps(response, **dumps_kwargs)  # TODO determine what happens if encoding error


class JsonClient:
    def __init__(self, id_factory: Callable, json_loads=json.loads, json_dumps=json.dumps):
        self.id_factory = id_factory
        self._json_loads = json_loads
        self._json_dumps = json_dumps

    def build_request(self, method: str, *args, **kwargs):
        return self._json_dumps(Request(jsonrpc='2.0', method=method, params=merge_params(args, kwargs),
                                        id=self.id_factory()))


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
