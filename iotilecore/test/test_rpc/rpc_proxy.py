from iotile.core.hw.proxy.proxy import TileBusProxyObject
from typedargs import context

@context("TestProxy2")
class TestTileProxy2(TileBusProxyObject):

    @classmethod
    def ModuleName(cls):
        return 'test42'

    def test_add_v1(self, a, b):
        res, = self.rpc(0x00, 0x00, a, b, arg_format="LL", result_format="L")
        return res

    def test_add_v2(self, a, b):
        res, = self.rpc_v2(0x0000, "LL", "L", a, b)
        return res

    def test_null_v1(self):
        self.rpc(0x11, 0x11)

    def test_null_v2(self):
        self.rpc_v2(0x1111, "", "")

    def test_invalid_arg_length_rpc_v1(self):
        error, = self.rpc(0x80, 0x91, 1, 2, bytes(15), arg_format="BB12s", result_format="L")
        return error

    def test_invalid_arg_length_rpc_v2(self):
        error, = self.rpc_v2(0x8091, "BB12s", "L", 1, 2, bytes(15))
        return error

    def test_invalid_args_missing_rpc_v1(self):
        error, = self.rpc(0xaa, 0xaa, arg_format="L", result_format="")
        return error

    def test_invalid_args_missing_rpc_v2(self):
        error, = self.rpc_v2(0xaaaa, "L", "")
        return error

    def test_rpc_does_not_exist_v1(self):
        error, = self.rpc(0xde, 0xad)

    def test_rpc_does_not_exist_v2(self):
        error, = self.rpc_v2(0xdead, "", "")
