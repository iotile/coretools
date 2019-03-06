from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotile.core.utilities.typedargs.annotate import annotated,param,return_type, context


class StreamerResult(dict):
    def __init__(self):
        self.comm_status = 0


@context("ReportTestDeviceProxy")
class ReportTestDeviceProxy(TileBusProxyObject):
    """A proxy object to correspond with ReportTestDevice
    """

    @classmethod
    def ModuleName(cls):
        return 'Rptdev'

    def sensor_graph(self):
        return self

    @return_type("integer")
    @param("index", "integer", desc="index of the acknowledgement")
    @param("force", "bool", desc="force insertion regardless of sequence check")
    @param("acknowledgement", "integer", desc="value of the acknowledgement")
    def acknowledge_streamer(self, index, force, acknowledgement):
        error, = self.rpc(0x20, 0x0f, index, force, acknowledgement, arg_format="HHL", result_format="L")

        return error

    @return_type("basic_dict")
    @param("index", "integer", desc="index of acknowledgement to query")
    def query_streamer(self, index):
        a, b, c, ack, d, e, f = self.rpc(0x20, 0x0a, index, arg_format="H", result_format="LLLLBBBx")

        result = StreamerResult()
        result["ack"] = ack

        return result
