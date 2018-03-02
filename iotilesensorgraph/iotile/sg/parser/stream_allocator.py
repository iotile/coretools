from ..stream import DataStream
from iotile.core.exceptions import ArgumentError


class StreamAllocator(object):
    """Singleton object for allocating and managing streams.

    The StreamAllocator is in charge of allocating streams as needed
    from the pool of available streams for different purposes.  It also
    keeps track of how many inputs are attached to a given stream and splits
    it when there are two many streams attached.

    Args:
        sensor_graph (SensorGraph): The sensor graph that we allocating
            streams for.
        model (DeviceModel): The device model we are allocating for.
            This is required so that the StreamAllocator knows when to
            split a stream into two since we're out of outputs.
    """

    StartingID = 0x400

    def __init__(self, sensor_graph, model):
        self.sensor_graph = sensor_graph
        self.model = model

        self._allocated_streams = {}
        self._next_id = {}

    def allocate_stream(self, stream_type, stream_id=None, previous=None, attach=False):
        """Allocate a new stream of the given type.

        The stream is allocated with an incremental ID starting at
        StreamAllocator.StartingID.  The returned data stream can always
        be used to to attach a NodeInput to this stream, however the
        attach_stream() function should always be called first since this
        stream's output may need to be split and a logically equivalent
        stream used instead to satisfy a device specific constraint on the
        maximum number of outputs attached to a given stream.

        You can call allocate_stream on the same stream multiple times without
        issue.  Subsequent calls to allocate_stream are noops.

        Args:
            stream_type (int): A stream type specified in the DataStream class
                like DataStream.ConstantType
            stream_id (int): The ID we would like to use for this stream, if
                this is not specified, an ID is automatically allocated.
            previous (DataStream): If this stream was automatically derived from
                another stream, this parameter should be a link to the old
                stream.
            attach (bool): Call attach_stream immediately before returning.  Convenience
                routine for streams that should immediately be attached to something.

        Returns:
            DataStream: The allocated data stream.
        """

        if stream_type not in DataStream.TypeToString:
            raise ArgumentError("Unknown stream type in allocate_stream", stream_type=stream_type)

        if stream_id is not None and stream_id >= StreamAllocator.StartingID:
            raise ArgumentError("Attempted to explicitly allocate a stream id in the internally managed id range", stream_id=stream_id, started_id=StreamAllocator.StartingID)

        # If the stream id is not explicitly given, we need to manage and track it
        # from our autoallocate range
        if stream_id is None:
            if stream_type not in self._next_id:
                self._next_id[stream_type] = StreamAllocator.StartingID

            stream_id = self._next_id[stream_type]
            self._next_id[stream_type] += 1

        # Keep track of how many downstream nodes are attached to this stream so
        # that we know when we need to split it into two.
        stream = DataStream(stream_type, stream_id)

        if stream not in self._allocated_streams:
            self._allocated_streams[stream] = (stream, 0, previous)

        if attach:
            stream = self.attach_stream(stream)

        return stream

    def attach_stream(self, stream):
        """Notify that we would like to attach a node input to this stream.

        The return value from this function is the DataStream that should be attached
        to since this function may internally allocate a new SGNode that copies the
        stream if there is no space in the output list to hold another input.

        This function should be called once for every node input before allocated a new
        sensor graph node that attaches to a stream that is managed by the StreamAllocator.

        Args:
            stream (DataStream): The stream (originally returned from allocate_stream)
                that we want to attach to.

        Returns:
            Datastream: A data stream, possible the same as stream, that should be attached
                to a node input.
        """

        curr_stream, count, prev = self._allocated_streams[stream]

        # Check if we need to split this stream and allocate a new one
        if count == (self.model.get(u'max_node_outputs') - 1):
            new_stream = self.allocate_stream(curr_stream.stream_type, previous=curr_stream)
            copy_desc = u"({} always) => {} using copy_all_a".format(curr_stream, new_stream)

            self.sensor_graph.add_node(copy_desc)
            self._allocated_streams[stream] = (new_stream, 1, curr_stream)

            # If we are splitting a constant stream, make sure we also duplicate the initialization value
            # FIXME: If there is no default value for the stream, that is probably a warning since all constant
            #        streams should be initialized with a value.
            if curr_stream.stream_type == DataStream.ConstantType and curr_stream in self.sensor_graph.constant_database:
                self.sensor_graph.add_constant(new_stream, self.sensor_graph.constant_database[curr_stream])

            return new_stream

        self._allocated_streams[stream] = (curr_stream, count + 1, prev)
        return curr_stream
