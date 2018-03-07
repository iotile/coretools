"""Configuration object describing a streamer."""

from __future__ import unicode_literals, absolute_import, print_function
from future.utils import viewitems, python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError


@python_2_unicode_compatible
class DataStreamer(object):
    """In charge of streaming data remotely from a device via a communication tile.

    DataStreamers are created to listen for data from a stream, package it using some
    packaging scheme and then attempt to send it remotely when triggered (possibly
    automatically by the presence of data).  They can be configured to keep trying to
    send data until it is accepted by the other side.

    Args:
        selector (DataStreamSelector): The selector that chooses what readings will be
            streamed.
        dest_tile (SlotIdentifier): The destination tile that we will stream data to
        report_format (str): A string constant defined in DataStreamer.KnownFormats
        automatic (bool): Whether the streamer should trigger whenever there is data
            or wait until it is manually triggered
        report_type (str): A string constant defined in DataStreamer.KnownTypes
        with_other (int): The index of another streamer that this streamer should
            use to know when to trigger.  Defaults to None in which case the streamer
            triggers on its own.  The combination of automatic and with_other cannot
            be specified.
    """

    KnownTypes = {u'broadcast': 1, u'telegram': 1 << 1, u'synchronous': 1 << 2}
    KnownTypeCodes = {y: x for x, y in viewitems(KnownTypes)}
    KnownFormats = {u'individual': 0, u'hashedlist': 1, u'signedlist_userkey': 2, u'signedlist_devicekey': 3}
    KnownFormatCodes = {y: x for x, y in viewitems(KnownFormats)}

    def __init__(self, selector, dest_tile, report_format, automatic, report_type=u'telegram', with_other=None):
        report_format = str(report_format)
        report_type = str(report_type)

        if report_format not in DataStreamer.KnownFormats:
            raise ArgumentError("Unknown report format in DataStreamer constructor", report_format=report_format, known_formats=DataStreamer.KnownFormats.keys())

        if report_type not in DataStreamer.KnownTypes:
            raise ArgumentError("Unknown report type in DataStreamer constructor", report_type=report_type, known_types=DataStreamer.KnownTypes.keys())

        self.selector = selector
        self.dest = dest_tile
        self.format = report_format
        self.automatic = automatic
        self.report_type = report_type
        self.with_other = with_other

    def __str__(self):
        manual = "manual " if not self.automatic else ""
        realtime = "realtime " if self.format == 'individual' else ""

        security = ""
        if self.format == 'signedlist_userkey':
            security = "signed "

        to_slot = ""
        if not self.dest.controller:
            to_slot = " to " + str(self.dest)

        with_statement = ""
        if self.with_other is not None:
            with_statement = " with streamer %d" % self.with_other

        template = "{manual}{security}{realtime}streamer on {selector}{to_slot}{with_other}"
        return template.format(manual=manual, security=security, realtime=realtime, selector=self.selector,
                               with_other=with_statement, to_slot=to_slot)
