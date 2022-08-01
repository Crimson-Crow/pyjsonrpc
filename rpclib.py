from typing import Union, Optional
from json import JSONDecodeError
from pathlib import Path
from typing import Union, Optional

import orjson
from jsonschema_rs import JSONSchema, ValidationError

# JSONSerializable = Union[dict, list, int, float, str, bool, None]

# def orjson_dumps(v, *, default=None):
#     # orjson.dumps returns bytes, to match standard json.dumps we need to decode
#     return orjson.dumps(v, default=default).decode()

REQUEST_VALIDATOR: JSONSchema = JSONSchema.from_str(
    (Path(__file__).parent / 'schemas' / 'jsonrpc-request-2.0.json').read_text())
RESPONSE_VALIDATOR: JSONSchema = JSONSchema.from_str(
    (Path(__file__).parent / 'schemas' / 'jsonrpc-response-2.0.json').read_text())

# class Error(BaseModel, extra=Extra.forbid):
#     code: StrictInt
#     message: StrictStr
#     data: Optional[JSONSerializable]
#
#
# class Request(BaseModel, extra=Extra.forbid):
#     jsonrpc: Literal['2.0']
#     method: StrictStr
#     params: Optional[Union[list, dict]]
#     id: Optional[Union[StrictStr, StrictInt, StrictFloat]]
#
#
# class Response(BaseModel, extra=Extra.forbid):
#     jsonrpc: Literal['2.0']
#     result: Optional[JSONSerializable]
#     error: Optional[Error]
#     id: Union[StrictStr, StrictInt, StrictFloat, None] = Field(...)  # id can be null, but is required
#
#     @validator('error', always=True)
#     def mutually_exclusive(cls, v, values):  # TODO mutually exclusive in fields set
#         if v is not None and values['result'] is not None:
#             raise ValueError("'result' and 'error' are mutually exclusive.")
#         return v

class Error(dict):
    pass


class Request(dict):
    pass


class Response(dict):
    pass


class JsonRpc:
    def __init__(self, methods: Optional[dict] = None):
        self.methods = methods if methods is not None else {}

    # @staticmethod
    # def _split_params(params: list | dict) -> tuple[list, dict]:
    #     positional_params = []
    #     named_params = {}
    #     if isinstance(params, list):
    #         positional_params = params
    #     elif isinstance(params, dict):
    #         named_params = params
    #         # named_params = params.copy()
    #         # positional_params = named_params.pop('__args', [])
    #     return positional_params, named_params

    def _process_request(self, request: Request) -> Optional[Response]:
        try:
            REQUEST_VALIDATOR.validate(request)
        except ValidationError as ve:
            return Response(jsonrpc='2.0', error=Error(code=-32600, message='Invalid Request', data=str(ve)), id=None)
        is_not_notification = 'id' in request
        try:
            method = self.methods[request['method']]
        except KeyError:
            if not is_not_notification:
                return
            return Response(jsonrpc='2.0', error=Error(code=-32601, message='Method not found', id=request['id']))
        try:
            # positional_params, named_params = self._split_params(request.params)
            # result = method(*positional_params, **named_params)
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


if __name__ == '__main__':
    def asum(*args):
        return sum(args)
    rpc_methods = {'subtract': lambda a, b: a - b, 'sum': asum}
    rpc = JsonRpc(rpc_methods)
    req = '[]'
    print(rpc.call(req))
    req = '{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1'
    print(rpc.call(req))
    req = '{"jsonrpc": "3.0", "method": "subtract", "params": [42, 23], "id": 1}'
    print(rpc.call(req))
    req = '{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}'
    print(rpc.call(req))
    req = '{"jsonrpc": "2.0", "method": 3, "params": [42, 23], "id": 1}'
    print(rpc.call(req))
    # req = '[1,2,3]'
    # rpc.call(req)
    req = '''[
        {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
        {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
        {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
        {"foo": "boo"},
        {"jsonrpc": "2.0", "method": 1, "params": {"name": "myself"}, "id": "5"},
        {"jsonrpc": "2.0", "method": "get_data", "id": "9"}
    ]'''
    print(rpc.call(req))
