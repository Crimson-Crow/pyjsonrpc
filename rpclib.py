import json
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, Callable, Any, TypeVar

from jsonschema_rs import JSONSchema

REQUEST_VALIDATOR: JSONSchema = JSONSchema.from_str(
    (Path(__file__).parent / 'schemas' / 'jsonrpc-request-2.0.json').read_text())
RESPONSE_VALIDATOR: JSONSchema = JSONSchema.from_str(
    (Path(__file__).parent / 'schemas' / 'jsonrpc-response-2.0.json').read_text())

Error = Request = Response = dict

T = TypeVar('T')
R = TypeVar('R')


class JsonRpc:
    def __init__(self, methods: Optional[dict[str, Callable]] = None, json_loads: Callable[[T], Any] = json.loads,
                 json_dumps: Callable[..., R] = json.dumps):
        self.methods = methods if methods is not None else {}
        self._json_loads = json_loads
        self._json_dumps = json_dumps

    def _process_request(self, request: Request) -> Optional[Response]:
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
            result = method(*params) if isinstance(params, list) else method(**params)
        except Exception as e:
            if not is_not_notification:
                return
            if isinstance(e, TypeError):  # TODO validate Invalid params implementation
                return Response(jsonrpc='2.0', error=Error(code=-32602, message='Invalid params', data=str(e)),
                                id=request['id'])
            else:
                return Response(jsonrpc='2.0', error=Error(code=-32603, message='Internal error', data=str(e)),
                                id=request['id'])
        if is_not_notification:
            return Response(jsonrpc='2.0', result=result, id=request['id'])

    def _parse_request(self, raw_request: T) -> Optional[Response | list[Response]]:
        try:
            request_obj: Request | list[Request] = self._json_loads(raw_request)
        except JSONDecodeError as jde:
            return Response(jsonrpc='2.0', error=Error(code=-32700, message='Parse error', data=str(jde)), id=None)
        if isinstance(request_obj, list):  # batch request
            if not request_obj:
                return Response(jsonrpc='2.0',
                                error=Error(code=-32600, message='Invalid Request', data='empty batch request'),
                                id=None)
            responses = []
            for r in request_obj:
                if response := self._process_request(r):
                    responses.append(response)
            if responses:
                return responses
        else:
            if response := self._process_request(request_obj):
                return response

    def call(self, request: T, **dumps_kwargs) -> R:
        if response := self._parse_request(request):
            return self._json_dumps(response, **dumps_kwargs)  # TODO determine what happens if encoding error
