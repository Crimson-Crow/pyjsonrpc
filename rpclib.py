from typing import Union, Optional
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

import orjson
from jsonschema_rs import JSONSchema


REQUEST_VALIDATOR: JSONSchema = JSONSchema.from_str(
    (Path(__file__).parent / 'schemas' / 'jsonrpc-request-2.0.json').read_text())
RESPONSE_VALIDATOR: JSONSchema = JSONSchema.from_str(
    (Path(__file__).parent / 'schemas' / 'jsonrpc-response-2.0.json').read_text())


Error = Request = Response = dict


class JsonRpc:
    def __init__(self, methods: Optional[dict] = None):
        self.methods = methods if methods is not None else {}

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

    def _parse_request(self, request_str: str | bytes) -> Optional[dict | list[dict]]:
        try:
            request_obj = orjson.loads(request_str)
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

    def call(self, request: str | bytes) -> bytes:
        if response := self._parse_request(request):
            return orjson.dumps(response)  # TODO determine what happens if encoding error
