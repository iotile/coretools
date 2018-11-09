""" A simple stream manager subsystem.

This subsystem is appropriate primarily for use with the emulated device adapter.
It supports receiving reports from the sensor-graph subsystem and queuing them
for transmission out of the streaming interface.
"""


import logging
from iotile.core.exceptions import InternalError
from iotile.core.hw.reports import IndividualReadingReport


class BasicStreamingSubsystem(object):
    """Container for a very basic streaming subsystem."""

    MAX_REPORT_SIZE = 3*64*1024

    def __init__(self, device):
        self.in_progress_streamers = {}
        self._device = device
        self._logger = logging.getLogger(__name__)

    def in_progress(self):
        """Get a set of in progress streamers."""

        return set(self.in_progress_streamers)

    def clear_to_reset(self, _config_vars):
        """Clear all volatile information across a reset."""

        self.in_progress_streamers = {}

    def notify_streaming_finished(self, index, sent, ack):
        """Notify that a report from a streamer has finished."""

        self._logger.debug("Streamer %d: finished, result was %s, ack was %d", index, sent, ack)

        callback = None
        if index in self.in_progress_streamers:
            _streamer, _state, callback = self.in_progress_streamers[index]

            del self.in_progress_streamers[index]

        if callback is not None:
            callback(index, sent, ack)

    def _continue_streaming(self, index, success, highest_ack, remaining):
        if remaining == 0:
            self.notify_streaming_finished(index, success, highest_ack)
            return

        if index not in self.in_progress_streamers:
            self._logger.error("_continue_streaming could not find its streamer index %d", index)
            return

        streamer, _state, _callback = self.in_progress_streamers[index]

        # Otherwise we are streaming an individual report
        report = streamer.build_report(self._device.iotile_id, self.MAX_REPORT_SIZE, device_uptime=0)
        remaining -= 1

        if report.visible_readings[0].reading_id > highest_ack:
            highest_ack = report.visible_readings[0].reading_id

        self._device.stream(report, callback=lambda sent: self._device.deferred_task(self._continue_streaming, index, sent, highest_ack, remaining))

    def process_streamer(self, index, streamer, report_id=None, callback=None):
        """Start streaming a streamer.

        Args:
            index (int): The streamer index to track it
            streamer (DataStreamer): The streamer itself.
            report_id (int): An optional int if the streamer generates a report that needs
                to be serialized.
            callback (callable): An optional callable that will be called as:
                callable(index, success, highest_id_received_from_other_side)

        TODO:
            This needs a refactor for cleanliness.  The hacky check for
                IndividualReadingReport is not amazing.
        """

        if index in self.in_progress_streamers:
            raise InternalError("You cannot add a streamer again until it has finished streaming.")

        self.in_progress_streamers[index] = [streamer, 1, callback]

        initial_count = streamer.walker.count()

        report = streamer.build_report(self._device.iotile_id, self.MAX_REPORT_SIZE, device_uptime=0, report_id=report_id)

        to_ack = 0
        if isinstance(report, IndividualReadingReport):
            remaining = initial_count - 1
            to_ack = report.visible_readings[0].reading_id
        else:
            remaining = 0

        self._logger.debug("Streamer %d: starting, report %s", index, report)
        self._device.stream(report, callback=lambda sent: self._device.deferred_task(self._continue_streaming, index, sent, to_ack, remaining))


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

        self.stream_manager = BasicStreamingSubsystem(self._device)
        self._post_config_subsystems.append(self.stream_manager)
