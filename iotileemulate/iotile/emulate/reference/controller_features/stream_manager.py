""" A simple stream manager subsystem.

This subsystem is appropriate primarily for use with the emulated device adapter.
It supports receiving reports from the sensor-graph subsystem and queuing them
for transmission out of the streaming interface.

TODO:
  - [ ] Keep track of last attempt and last success times for streamers
"""


import logging
from collections import OrderedDict
from iotile.core.exceptions import InternalError
from iotile.core.hw.reports import IndividualReadingReport


class QueuedStreamer(object):
    def __init__(self, streamer, callback):
        self.status = 1
        self.streamer = streamer
        self.callback = callback
        self.initial_count = streamer.walker.count()

        self.sent_count = 0
        self.highest_ack = 0

    @property
    def remaining(self):
        return self.initial_count - self.sent_count

    def record_acknowledgement(self, ack):
        if ack > self.highest_ack:
            self.highest_ack = ack


class BasicStreamingSubsystem(object):
    """Container for a very basic streaming subsystem."""

    MAX_REPORT_SIZE = 3*64*1024

    def __init__(self, device, id_assigner):
        self.in_progress_streamers = OrderedDict()
        self._actively_streaming = False
        self._device = device
        self._logger = logging.getLogger(__name__)
        self._streamer_queue = []
        self._id_assigner = id_assigner

        self.get_timestamp = lambda: 0
        self.get_uptime = lambda: 0

    def in_progress(self):
        """Get a set of in progress streamers."""

        return set(self.in_progress_streamers)

    def clear_to_reset(self, _config_vars):
        """Clear all volatile information across a reset."""

        self.in_progress_streamers = {}

    def _finish_streaming(self, queued, success):
        """Notify that a report from a streamer has finished."""

        self._logger.debug("Streamer %d: finished, result was %s, ack was %d", queued.streamer.index, success, queued.highest_ack)

        if queued.streamer.index in self.in_progress_streamers:
            del self.in_progress_streamers[queued.streamer.index]

        if queued.callback is not None:
            queued.callback(queued.streamer.index, success, queued.highest_ack)

        if len(self.in_progress_streamers) == 0:
            self._actively_streaming = False
            return

        # Otherwise chain the next streamer to start
        next_index = next(iter(self.in_progress_streamers))
        next_queued = self.in_progress_streamers[next_index]

        self._logger.debug("Streamer %d: chained to begin when %d finished", next_index, queued.streamer.index)
        self._device.deferred_task(self._begin_streaming, next_queued)

    def _build_report(self, streamer):
        report_id = None
        if streamer.requires_id():
            report_id = self._id_assigner()

        return streamer.build_report(self._device.iotile_id, self.MAX_REPORT_SIZE, device_uptime=self.get_uptime(), report_id=report_id)

    def _begin_streaming(self, queued):
        report, num_readings, highest_id = self._build_report(queued.streamer)

        queued.sent_count += num_readings

        if isinstance(report, IndividualReadingReport):
            queued.record_acknowledgement(highest_id)

        self._logger.debug("Streamer %d: starting with report %s", queued.streamer.index, report)

        next_step = lambda sent: self._device.deferred_task(self._continue_streaming, queued, sent)
        self._device.stream(report, callback=next_step)


    def _continue_streaming(self, queued, success):
        if queued.remaining == 0 or not success:
            self._finish_streaming(queued, success)
            return

        # Otherwise we are streaming an individual report
        report, num_readings, highest_id = self._build_report(queued.streamer)

        queued.sent_count += num_readings

        if isinstance(report, IndividualReadingReport):
            queued.record_acknowledgement(highest_id)

        self._logger.debug("Streamer %d: continuing with report %s", queued.streamer.index, report)

        self._device.stream(report, callback=lambda sent: self._device.deferred_task(self._continue_streaming, queued, sent))

    def process_streamer(self, streamer, callback=None):
        """Start streaming a streamer.

        Args:
            streamer (DataStreamer): The streamer itself.
            callback (callable): An optional callable that will be called as:
                callable(index, success, highest_id_received_from_other_side)
        """

        index = streamer.index

        if index in self.in_progress_streamers:
            raise InternalError("You cannot add a streamer again until it has finished streaming.")

        queue_item = QueuedStreamer(streamer, callback)
        self.in_progress_streamers[index] = queue_item

        self._logger.debug("Streamer %d: queued to send %d readings", index, queue_item.initial_count)

        if not self._actively_streaming:
            self._actively_streaming = True
            self._device.deferred_task(self._begin_streaming, queue_item)


class StreamingSubsystemMixin(object):
    """Mixin for an IOTileController that implements the streaming subsystem.

    Depending on the desired level of realism, you can choose to use either a
    complete streaming emulation that will send each streaming report chunk by
    chunk with RPCs to a destination tile, or you can opt for the simpler
    basic streaming subsystem that just takes the report and queues it for
    processing.

    Args:
        basic (bool): Whether to use a basic model of report streaming or the
            complete simulation.  Defaults to True, which means basic.
    """

    def __init__(self, basic=True):
        if not basic:
            raise InternalError("Full stream manager support is not yet implemented")

        self.stream_manager = BasicStreamingSubsystem(self._device, self.sensor_log.allocate_id)
        self._post_config_subsystems.append(self.stream_manager)
