from pprint import pprint
from typing import Literal, Union, Optional

import orjson
from pydantic import BaseModel, validator, Extra, StrictStr, StrictInt, StrictFloat, Field, ValidationError
from json import JSONDecodeError

JSONSerializable = Union[dict, list, int, float, str, bool, None]

# def orjson_dumps(v, *, default=None):
#     # orjson.dumps returns bytes, to match standard json.dumps we need to decode
#     return orjson.dumps(v, default=default).decode()


class Error(BaseModel, extra=Extra.forbid):
    code: StrictInt
    message: StrictStr
    data: Optional[JSONSerializable]


class Request(BaseModel, extra=Extra.forbid):
    jsonrpc: Literal['2.0']
    method: StrictStr
    params: Optional[Union[list, dict]]
    id: Optional[Union[StrictStr, StrictInt, StrictFloat]]


class Response(BaseModel, extra=Extra.forbid):
    jsonrpc: Literal['2.0']
    result: Optional[JSONSerializable]
    error: Optional[Error]
    id: Union[StrictStr, StrictInt, StrictFloat, None] = Field(...)  # id can be null, but is required

    @validator('error', always=True)
    def mutually_exclusive(cls, v, values):  # TODO mutually exclusive in fields set
        if v is not None and values['result'] is not None:
            raise ValueError("'result' and 'error' are mutually exclusive.")
        return v


class JsonRpc:
    def __init__(self, methods: Optional[dict] = None):
        self.methods = methods if methods is not None else {}

    @staticmethod
    def _split_params(params):
        positional_params = []
        named_params = {}
        if isinstance(params, list):
            positional_params = params
        elif isinstance(params, dict):
            named_params = params.copy()
            positional_params = named_params.pop('__args', [])

        return positional_params, named_params

    def _process_request(self, request_obj: dict) -> Optional[Response]:
        try:
            request = Request.parse_obj(request_obj)
        except ValidationError as ve:
            return Response(jsonrpc='2.0', error=Error(code=-32600, message='Invalid Request', data=str(ve)), id=None)
        else:
            is_notification = 'id' not in request.__fields_set__
            try:
                method = self.methods[request.method]
            except KeyError:
                if is_notification:
                    # TODO logger
                    return
                return Response(jsonrpc='2.0',
                                error=Error(code=-32601,
                                            message='Method not found',
                                            data=f'Method "{request.method}" not found'),
                                id=request.id)

            try:
                positional_params, named_params = self._split_params(request.params)
                result = method(*positional_params, **named_params)
            except Exception as e:
                if is_notification:
                    # TODO logger
                    return
                return Response(jsonrpc='2.0',
                                error=Error(code=-32603,
                                            message='Internal error'),
                                id=request.id)  # TODO implement Invalid params
                # traceback_info = format_exc()
                #
                # if isinstance(err, TypeError) and "positional argument" in str(err):
                #     error = rpcerror.InvalidParams(data=traceback_info)
                # else:
                #     error = rpcerror.InternalError(message=str(err),
                #                                    data=traceback_info)
            else:
                if is_notification:
                    # TODO logger
                    return
                return Response(jsonrpc='2.0', result=result, id=request.id)

    def _load_request(self, raw_request: Union[str, bytes]) -> Union[dict, list[dict], None]:
        try:
            raw_request_obj = orjson.loads(raw_request)
        except JSONDecodeError as jde:
            return Response(jsonrpc='2.0',
                            error=Error(code=-32700, message='Parse error', data=str(jde)),
                            id=None).dict(exclude_unset=True)
        else:
            if isinstance(raw_request_obj, list):  # batch request
                if not raw_request_obj:
                    return Response(jsonrpc='2.0',
                                    error=Error(code=-32600, message='Invalid Request', data='empty batch request'),
                                    id=None).dict(exclude_unset=True)
                responses = []
                for request_obj in raw_request_obj:
                    if response := self._process_request(request_obj):
                        responses.append(response.dict(exclude_unset=True))
                if responses:
                    return responses
            else:
                if response := self._process_request(raw_request_obj):
                    return response.dict(exclude_unset=True)

    def call(self, request: Union[str, bytes]) -> bytes:
        return orjson.dumps(self._load_request(request))  # TODO determine what happens if encoding error


# def create_notification_dict(method, *args, **kwargs):
#     """
#     Returns a notification JSON-RPC-dictionary for a method
#
#     :param method: Name of the method
#     :param args: Positional parameters
#     :param kwargs: Named parameters
#     """
#
#     data = {"jsonrpc": "2.0", "method": str(method)}
#
#     if kwargs:
#         params = kwargs
#         if args:
#             params["__args"] = args
#     else:
#         params = args
#
#     if params:
#         data["params"] = params
#     return data


if __name__ == '__main__':
    rpc_methods = {'subtract': lambda a, b: a - b}
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