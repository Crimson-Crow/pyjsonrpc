#!/usr/bin/env python3
# coding: utf-8

import uuid
from collections.abc import Iterable, Mapping

from . import rpcerror, rpcjson

# TODO Implement __all__

class Request(dict):
    """
    JSON-RPC-Request
    """
    __slots__ = ()
    _OPT_KEYS = {"params", "id"}

    # TODO document params and id optional
    def __init__(self, jsonrpc=None, method=None, **kwargs):
        opt_args = {k:kwargs[k] for k in self._OPT_KEYS & kwargs.keys()}
        super().__init__(dict(jsonrpc=jsonrpc, method=str(method), **opt_args))

    def get_splitted_params(self):
        """
        Split positional and named params

        :returns: positional_params, named_params
        """

        positional_params = []
        named_params = {}
        params = self.get("params")
        if isinstance(params, Iterable):
            positional_params = params
        elif isinstance(params, Mapping):
            named_params = params.copy()
            positional_params = named_params.pop("__args", [])

        return positional_params, named_params

    @classmethod
    def from_string(cls, json_string):
        """
        Parses the Json-string and returns a Request-object or a
        list of Request-objects.

        :returns: Request-object or list of Request-objects

        :rtype: Request
        """

        # Parse
        try:
            data = rpcjson.loads(json_string)
        except rpcjson.JsonParseError as err:
            if err.msg == "Expecting value":
                raise rpcerror.InvalidRequest(data=err.msg)
            else:
                raise rpcerror.ParseError(data=err.msg)

        # Create request(s)
        # Not checking for ABCs because the json decoder uses this table:
        # https://docs.python.org/3/library/json.html#json.JSONDecoder
        if data:
            if isinstance(data, dict):
                return cls(**data)
            elif isinstance(data, list):
                return [
                    cls(**item) if isinstance(item, dict) else cls()
                    for item in data
                ]

        print("Empty json object/array or invalid type.")  # TODO DEBUG
        raise rpcerror.InvalidRequest()

    # Alias
    loads = from_string

    def to_string(self):
        """
        Returns a Json-string
        """

        # Return Json
        return rpcjson.dumps(self)

    # Alias
    dumps = to_string


# Alias for *Request.loads*
parse_request_json = Request.from_string


def create_notification_dict(method, *args, **kwargs):
    """
    Returns a notification JSON-RPC-dictionary for a method

    :param method: Name of the method
    :param args: Positional parameters
    :param kwargs: Named parameters
    """

    data = {"jsonrpc": "2.0", "method": str(method)}

    if kwargs:
        params = kwargs
        if args:
            params["__args"] = args
    else:
        params = args

    if params:  # params is an optional field
        data["params"] = params
    return data


def create_notification_json(method, *args, **kwargs):
    """
    Returns a notification JSON-RPC-String for a method

    :param method: Name of the method
    :param args: Positional parameters
    :param kwargs: Named parameters
    """

    return rpcjson.dumps(create_notification_dict(method, *args, **kwargs))


def create_request_dict(method, *args, **kwargs):
    """
    Returns a JSON-RPC-dictionary for a method

    :param method: Name of the method
    :param args: Positional parameters
    :param kwargs: Named parameters
    """

    data = create_notification_dict(method, *args, **kwargs)
    data["id"] = str(uuid.uuid4())
    return data


def create_request_json(method, *args, **kwargs):
    """
    Returns a JSON-RPC-String for a method

    :param method: Name of the method
    :param args: Positional parameters
    :param kwargs: Named parameters
    """

    return rpcjson.dumps(create_request_dict(method, *args, **kwargs))


# Alias
create_request_string = create_request_json
create_notification_string = create_notification_json
