"""A simple console UI that displays a list of objects with a title.

The use case for this object is that you want to create a UI that shows a list of
information where individual lines could be changing and you want to update them
in place
like this:

<TITLE>
Item 1      Value 1
Item 2      Value 2
...

You could just write a new line to the console with every changing item but that
quickly gets unusable because things change too fast and unrelated lines stomp
on each other.

LinebufferUI provides a nice way to do this.  It has the following prerequisites:

1. There must be a polling function that will return a new line.  This is
   treated as an opaque object so it may have whatever format you want.  This
   function will be called in a loop to check for changes to the items that
   are being displayed. If you return a list from this function, it will be
   treated as multiple results. This means that your object type cannot be
   anything such that isinstance(object, list) is True otherwise it will be
   misinterpretted as multiple objects.
2. You must be able to calculate a single hashable value that determines for a result
   from your polling function, what line it corresponds to.  If you wish to exclude
   some results from your polling function, simply return None from this function and
   that specific result will be dropped.
3. You must be be able to implement a function that draws each line given your object.
4. You can optionally define a function that sorts your objects, which is called to
   get the final sorted list before these are rendered to the screen.

These 3 (optionally 4) functions are called for you in order to create a nice UI
that doesn't flicker or scroll.
"""

from collections import namedtuple
import time
from future.utils import viewvalues
from past.builtins import basestring
from iotile.core.exceptions import ExternalError

LineEntry = namedtuple("LineEntry", ['text', 'id', 'sort_key', 'object'])


class LinebufferUI:
    """A simple console UI that displays a list of items and updates them in place."""

    def __init__(self, poll_func, id_func, draw_func, sortkey_func=None, title=None):
        self.poll_func = poll_func
        self.id_func = id_func
        self.draw_func = draw_func
        self.sortkey_func = sortkey_func

        if isinstance(title, basestring):
            self.title_func = lambda x: title
        else:
            self.title_func = title

        self.items = {}

    def run(self, refresh_interval=0.05):
        """Set up the loop, check that the tool is installed"""
        try:
            from asciimatics.screen import Screen
        except ImportError:
            raise ExternalError("You must have asciimatics installed to use LinebufferUI", suggestion="pip install iotilecore[ui]")

        Screen.wrapper(self._run_loop, arguments=[refresh_interval])

    def _update_items(self, screen):
        new_items = self.poll_func()
        if new_items is None:
            return

        if not isinstance(new_items, list):
            new_items = [new_items]

        for item in new_items:
            id_val, entry = self._parse_and_format(item)
            if id_val is None:
                continue

            self.items[id_val] = entry

    def _run_loop(self, screen, refresh_interval):
        self.items = {}

        screen.clear()

        try:
            while True:
                self._update_items(screen)
                items = sorted(viewvalues(self.items), key=lambda x: x.sort_key)

                if self.title_func is not None:
                    lines = self.title_func(self.items)
                    for i, line in enumerate(lines):
                        screen.print_at(line, 0, i)

                for line_no, item in enumerate(items):
                    screen.print_at(item.text, 0, line_no + len(lines)+1)

                screen.refresh()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            pass

    def _parse_and_format(self, item):
        id_val = self.id_func(item)
        if id_val is None:
            return None, None

        text = self.draw_func(item)

        sort_key = id_val
        if self.sortkey_func is not None:
            sort_key = self.sortkey_func(item)

        return id_val, LineEntry(text, id_val, sort_key, item)
