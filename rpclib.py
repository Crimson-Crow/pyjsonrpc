import json
import logging
from traceback import format_exc

from . import rpcerror, rpcrequest, rpcresponse


def rpcmethod(func):
    """
    Decorator
    Sign the decorated method as JSON-RPC-Method
    """

    # Sign the function as JSON-RPC-Method
    func.rpcmethod = True

    # Return the function itself
    return func


class JsonRpc:
    """
    JSON-RPC
    """
    methods = {}

    def __init__(self, methods=None):
        """
        Initializes the JSON-RPC-Class

        :param methods: Json-RPC-Methods. `None` or dictionary with
            method names as keys and functions as values. Syntax::

                {
                    "<method_name>": <method_function>,
                    ...
                }
        """

        if methods is not None:
            self.methods = methods

    def _process_request(self, request):
        # Response data
        result = None
        error = None

        try:
            # Request data
            try:
                jsonrpc = request["jsonrpc"]
                method = request["method"]
            except KeyError:
                print("jsonrpc or method fields not found")  # TODO DEBUG
                print(request)
                raise rpcerror.InvalidRequest()

            # Test validity
            if jsonrpc != "2.0" or not method:
                print("jsonrpc != 2.0 or method is null")  # TODO DEBUG
                raise rpcerror.InvalidRequest()

            # Locate method
            if method not in self.methods:
                # Check if requested method is signed as *rpcmethod*
                _method = getattr(self, method, None)
                if callable(_method) and getattr(_method, "rpcmethod", False):
                    self.methods[method] = _method
                else:
                    raise rpcerror.MethodNotFound(
                        data=f"Method name: '{method}'")

            # Split positional and named params
            positional_params, named_params = request.get_splitted_params()
            # Call the method with parameters
            result = self.methods[method](*positional_params, **named_params)
        except rpcerror.JsonRpcError as err:
            error = err
        except Exception as err:
            traceback_info = format_exc()

            if isinstance(err, TypeError) and "positional argument" in str(err):
                error = rpcerror.InvalidParams(data=traceback_info)
            else:
                error = rpcerror.InternalError(message=str(err),
                                               data=traceback_info)

        if error:
            # Logging error
            logging.error(f"{error} -- {error.data}")

        try:
            id = request["id"]  # TODO CHANGE
        except KeyError:
            pass
        else:
            return rpcresponse.Response(
                jsonrpc="2.0",
                result=result,
                # error=error, #TODO TEMPORARY
                id=id)

    def call(self, json_request):
        """
        Parses the *json_request*, calls the function(s)
        and returns the *json_response*.

        :param json_request: JSON-RPC-string with one or more JSON-RPC-requests

        :return: JSON-RPC-string with one or more responses or None if no answer is expected.
        """

        try:
            # Single Request object or list of Request objects (batch)
            requests = rpcrequest.parse_request_json(json_request)
        except rpcerror.JsonRpcError as err:
            logging.error(f"{err} -- {err.data}")
            ret = rpcresponse.Response(jsonrpc="2.0", error=err, id=None)
        else:
            ret = [self._process_request(request)
                   for request in requests] if isinstance(
                requests, list) else self._process_request(requests)

        # TODO Check array of None for batch notifications
        # Return as JSON-string (batch or normal)
        if ret:
            return json.dumps(ret)

        # OLD CODE
        # # List for the responses
        # responses = []

        # # Every JSON-RPC request in a batch of requests (or a wrapped single request)
        # for request in requests if isinstance(requests, list) else [requests]:

        # # Return as JSON-string (batch or normal)
        # if responses:
        #     return rpcjson.dumps(
        #         responses if isinstance(requests, list) else responses[0])

    def __call__(self, json_request):
        """
        Redirects the requests to *self.call*
        """

        return self.call(json_request)

    def __getitem__(self, key):
        """
        Gets back the requested method
        """

        return self.methods[key]

    def __setitem__(self, key, value):
        """
        Appends or replaces a method
        """

        self.methods[key] = value

    def __delitem__(self, key):
        """
        Deletes a method
        """

        del self.methods[key]
