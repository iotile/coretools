# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import sys
from time import time
from iotile.core.utilities.typedargs import type_system

class ProgressBar:
    """
    A simple progress bar that updates itself in the console.

    If the program is being run in interactive mode, display the progress_bar
    otherwise do not display it
    """

    def __init__(self, title, count=100):
        self.title = title
        self.prog = 0 
        self.count = count


    def start(self):
        self.velocity = 0
        self.prog = 0
        self.start_time = time()

        if type_system.interactive:
            self.last_update = ""
            self._update()

    def _update(self, total=False):
        timestring = "Estimating time left"

        if self.velocity != 0.0:
            total_time = 1.0/self.velocity
            spent_time = self.current_time - self.start_time

            if total:
                time_left = spent_time
            else:
                time_left = total_time - spent_time

            units = "seconds"

            if time_left > 3600.:
                units = "hours"
                time_left /= 3600.0
            elif time_left > 60.0:
                units = "minutes"
                time_left /= 60.0

            comment = 'left'
            if total:
                comment = 'total'

            timestring = "%.1f %s %s" % (time_left, units, comment)

        if self.count > 0:
            x = int(self.prog * 40 // self.count)
        else:
            x = 0

        update_string = "%s: [%s%s] %s" % (self.title, '#'*x, '-'*(40-x), timestring)
        if len(update_string) < len(self.last_update):
            update_string += " "*(len(self.last_update) - len(update_string))


        #Erase the last update and write this one
        sys.stdout.write(chr(8)*len(self.last_update))
        sys.stdout.write(update_string)
        sys.stdout.flush()
        self.last_update = update_string

    def progress(self, x):
        self.current_time = time()

        if self.current_time > self.start_time and self.count > 0:
            self.velocity = (float(x)/self.count) / (self.current_time - self.start_time)

        self.prog = x

        if type_system.interactive:
            self._update()

    def end(self):
        self.prog = self.count
        if type_system.interactive:
            self._update(total=True)
            sys.stdout.write("\n")