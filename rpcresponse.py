import json

from . import rpcerror
from .tools import FilteredDict


class Response(FilteredDict):
    """
    Represents a JSON-RPC-response.
    """
    __slots__ = ()
    _ALLOWED_KEYS = ("jsonrpc", "result", "error", "id")

    def _ensure_error(self):
        if "error" in self:
            try:
                del self["result"]
            except:
                pass
            else:
                from warnings import warn
                warn(
                    "Cannot have both 'error' and 'result' keys in Response dict. 'result' was ignored."
                )

    @staticmethod
    def _wrap_error(error):  # TODO remove
        if isinstance(error, rpcerror.JsonRpcError):
            err = {"code": error.code, "message": error.message}
            if error.data is not None:
                err["data"] = error.data
            error = err
        # elif isinstance(error, dict) and "code" in error: # TODO mapping
        #     try:
        #         error = rpcerror.jsonrpcerrors[error["code"]](error)
        #     except:
        #         error = rpcerror.JsonRpcError(error)
        # elif isinstance(error, str):
        #     error = rpcerror.InternalError(message=error)
        # else:
        #     raise ValueError("Provided value for key 'error' cannot be serialized to a JsonRpcError")
        return error

    def __init__(self, jsonrpc=None, id=None, **kwargs):
        try:
            kwargs["error"] = self._wrap_error(kwargs["error"])  # TODO remove
        except:
            pass
        super().__init__(self._ALLOWED_KEYS, jsonrpc=jsonrpc, id=id, **kwargs)
        self._ensure_error()

    def __setitem__(self, k, v):
        if k == 'error':
            v = self._wrap_error(v)
        super().__setitem__(k, v)
        self._ensure_error()

    def setdefault(self, k, default=None):
        if k == 'error':
            default = self._wrap_error(default)
        ret = super().setdefault(k, default)
        self._ensure_error()
        return ret

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._ensure_error()

    # def to_dict(self):
    #     """
    #     Returns the response object as dictionary.
    #     """

    #     retdict = {"jsonrpc": self.jsonrpc}
    #     if self.error:
    #         retdict["error"] = error = {}
    #         error["code"] = self.error.code
    #         error["message"] = self.error.message
    #         if self.error.data:
    #             error["data"] = self.error.data
    #     else:
    #         retdict["result"] = self.result

    #     retdict["id"] = self.id

    #     # Finished
    #     return retdict

    def to_string(self):
        """
        Returns the response as JSON-string
        """

        return json.dumps(self)

    # Alias
    dumps = to_string

    # @classmethod
    # def from_dict(cls, data):
    #     """
    #     Returns a Response-object, created from dictionary
    #     """

    #     error = data.get("error")
    #     if error:
    #         result = None
    # if isinstance(error, str):
    #     # String Error
    #     error = rpcerror.InternalError(message=error)
    # elif "code" in error:
    #     # JSON-RPC Standard Error
    #     error = rpcerror.JsonRpcError(code=error.get("code"),
    #                                   message=error.get("message"),
    #                                   data=error.get("data"))
    # else:
    #     error = rpcerror.InternalError(
    #         data="\n".join(["%s: %s" % (k, v) for k, v in error]))
    #     else:
    #         result = data.get("result")
    #         error = None

    #     return cls(jsonrpc=data.get("jsonrpc"),
    #                result=result,
    #                error=error,
    #                id=data.get("id"))

    @classmethod
    def from_string(cls, json_string):
        """
        Returns a Response-object or a list with Response-objects
        """

        # Parse
        try:
            data = json.loads(json_string)
        except json.JsonParseError as err:
            if err.msg == "Expecting value":
                raise rpcerror.InvalidResponse(data=err.msg)
            else:
                raise rpcerror.ParseError(data=err.msg)

        # Create response(s)
        # Not checking for ABCs because the json decoder uses this table:
        # https://docs.python.org/3/library/json.html#json.JSONDecoder
        if data:
            if isinstance(data, dict):
                return cls(**data)
            elif isinstance(data, list):
                return (cls(**item) if isinstance(item, dict) else cls()
                        for item in data)

        raise rpcerror.InvalidResponse()

    # Alias
    loads = from_string


# Aliases
parse_response_json = Response.from_string
parse_response_string = Response.from_string
