from rpclib import *
# from rpclib_pydantic import JsonRpc as JsonRpcP


def setup():
    def asum(*args):
        return sum(args)
    rpc_methods = {'subtract': lambda a, b: a - b, 'sum': asum}
    return JsonRpc(rpc_methods)

# def setup_p():
#     def asum(*args):
#         return sum(args)
#     rpc_methods = {'subtract': lambda a, b: a - b, 'sum': asum}
#     return JsonRpcP(rpc_methods)


def test(rpc):
    return rpc.call('{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}')


if __name__ == '__main__':
    # print(RESPONSE_VALIDATOR.is_valid({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": 3}))
    # print(RESPONSE_VALIDATOR.is_valid({"jsonrpc": "2.0", "result": 13, "id": 3}))
    # print(RESPONSE_VALIDATOR.is_valid({"jsonrpc": "2.0", "result": 13, "error": {"code": -32700, "message": "Parse error"}, "id": 3}))
    # print(RESPONSE_VALIDATOR.is_valid({"jsonrpc": "2.0", "id": 3}))
    print(RESPONSE_VALIDATOR.is_valid(Response(jsonrpc='2.0', error=Error(code=-32601, message='Method not found'), id=None)))


    def isum(*args):
        return sum(args)


    rpc_methods = {'subtract': lambda a, b: a - b, 'sum': isum}
    rpc = setup()
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
    req = '[1,2,3]'
    print(rpc.call(req))
    req = '''[
            {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
            {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": 2},
            {"foo": "boo"},
            {"jsonrpc": "2.0", "method": 1, "params": {"name": "myself"}, "id": "5"},
            {"jsonrpc": "2.0", "method": "get_data", "id": "9"}
        ]'''
    print(rpc.call(req))

    print('TIMEIT')
    print(test(setup()))
    # print(test(setup_p()))
    import timeit
    print(timeit.timeit('test(rpc)', globals=locals(), setup='rpc=setup()'))
    # print(timeit.timeit('test(rpc)', globals=locals(), setup='rpc=setup_p()'))

