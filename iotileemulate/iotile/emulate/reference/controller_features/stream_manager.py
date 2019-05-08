""" A simple stream manager subsystem.

This subsystem is appropriate primarily for use with the emulated device adapter.
It supports receiving reports from the sensor-graph subsystem and queuing them
for transmission out of the streaming interface.

TODO:
  - [ ] Keep track of last attempt and last success times for streamers
"""


import logging
from iotile.core.exceptions import InternalError
from iotile.core.hw.reports import IndividualReadingReport
from .controller_system import ControllerSubsystemBase


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


class BasicStreamingSubsystem(ControllerSubsystemBase):
    """Container for a very basic streaming subsystem."""

    MAX_REPORT_SIZE = 3*64*1024

    def __init__(self, emulator, device, id_assigner):
        super(BasicStreamingSubsystem, self).__init__(emulator)

        self._in_progress_streamers = set()
        self._queue = emulator.create_queue(register=False)
        self._actively_streaming = False
        self._device = device
        self._logger = logging.getLogger(__name__)
        self._streamer_queue = []
        self._id_assigner = id_assigner

        self.get_timestamp = lambda: 0
        self.get_uptime = lambda: 0

    async def _reset_vector(self):
        #FIXME: Clear all queued streamers on a reset

        self.initialized.set()

        while True:
            queued = await self._queue.get()

            try:
                success = False
                while queued.remaining > 0:
                    report, num_readings, highest_id = self._build_report(queued.streamer)
                    queued.sent_count += num_readings

                    if isinstance(report, IndividualReadingReport):
                        queued.record_acknowledgement(highest_id)

                    self._logger.debug("Streamer %d: starting with report %s", queued.streamer.index, report)
                    success = await self._device.stream(report)
                    self._logger.debug("Streamer %d: finished with success=%s", queued.streamer.index, success)
            except:  #pylint:disable=bare-except;This background worker should never die
                self._logger.exception("Exception during streaming of streamer %s", queued.streamer)
                success = False
            finally:
                self._in_progress_streamers.remove(queued.streamer.index)
                self._logger.debug("Current in_progress is %s", self._in_progress_streamers)

                if queued.callback is not None:
                    try:
                        queued.callback(queued.streamer.index, success, queued.highest_ack)
                    except: #pylint:disable=bare-except;This background worker should never die
                        self._logger.exception("Exception during completion callback of streamer %s", queued.streamer)

    def in_progress(self):
        """Get a set of in progress streamers."""

        return set(self._in_progress_streamers)

    def clear_to_reset(self, config_vars):
        """Clear all volatile information across a reset."""

        super(BasicStreamingSubsystem, self).clear_to_reset(config_vars)
        self._in_progress_streamers = set()

    def _build_report(self, streamer):
        report_id = None
        if streamer.requires_id():
            report_id = self._id_assigner()

        return streamer.build_report(self._device.iotile_id, self.MAX_REPORT_SIZE, device_uptime=self.get_uptime(), report_id=report_id)

    def process_streamer(self, streamer, callback=None):
        """Start streaming a streamer.

        Args:
            streamer (DataStreamer): The streamer itself.
            callback (callable): An optional callable that will be called as:
                callable(index, success, highest_id_received_from_other_side)
        """

        index = streamer.index

        if index in self._in_progress_streamers:
            raise InternalError("You cannot add a streamer again until it has finished streaming.")

        queue_item = QueuedStreamer(streamer, callback)
        self._in_progress_streamers.add(index)

        self._logger.debug("Streamer %d: queued to send %d readings", index, queue_item.initial_count)
        self._queue.put_nowait(queue_item)


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

    def __init__(self, emulator, basic=True):
        if not basic:
            raise InternalError("Full stream manager support is not yet implemented")

        self.stream_manager = BasicStreamingSubsystem(emulator, self._device, self.sensor_log.allocate_id)
        self._post_config_subsystems.append(self.stream_manager)
