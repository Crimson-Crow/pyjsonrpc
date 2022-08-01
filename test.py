from rpclib import JsonRpc

def setup():
    def asum(*args):
        return sum(args)
    rpc_methods = {'subtract': lambda a, b: a - b, 'sum': asum}
    return JsonRpc(rpc_methods)

def test(rpc):
    rpc.call('{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1')

if __name__ == '__main__':
    import timeit
    print(timeit.timeit('test(rpc)', globals=locals(), setup='rpc=setup()')/1000000)