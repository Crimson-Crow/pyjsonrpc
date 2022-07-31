jsonrpcerrors = {}


class JsonRpcError(RuntimeError):
    code = None
    message = None
    data = None

    def __init__(self, code=None, message=None, data=None):
        self.code = code or self.code
        self.message = message or self.message
        self.data = data
        super().__init__(self.message)

    def __str__(self):
        return f"JsonRpcError({self.code}): {self.message}"


jsonrpcerrors[JsonRpcError.code] = JsonRpcError


class ParseError(JsonRpcError):
    code = -32700
    message = "Invalid JSON was received."


jsonrpcerrors[ParseError.code] = ParseError


# Server specific errors


class InvalidRequest(JsonRpcError):
    code = -32600
    message = "The JSON is not a valid Request object."


jsonrpcerrors[InvalidRequest.code] = InvalidRequest


class MethodNotFound(JsonRpcError):
    code = -32601
    message = "The method does not exist / is not available."


jsonrpcerrors[MethodNotFound.code] = MethodNotFound


class InvalidParams(JsonRpcError):
    code = -32602
    message = "Invalid method parameter(s)."


jsonrpcerrors[InvalidParams.code] = InvalidParams


class InternalError(JsonRpcError):
    code = -32603
    message = "Internal JSON-RPC error."


jsonrpcerrors[InternalError.code] = InternalError


# Client specific errors


class InvalidResponse(JsonRpcError):
    message = "The JSON is not a valid Response object."
