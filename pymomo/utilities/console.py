import sys
from pymomo.utilities.typedargs import type_system

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
        if type_system.interactive:
            sys.stdout.write(self.title + ": [" + "-"*40 + "]" + chr(8)*41)
            sys.stdout.flush()

        self.prog = 0

    def progress(self, x):
        x = int(x * 40 // self.count)

        if type_system.interactive:
            sys.stdout.write("#" * (x - self.prog))
            sys.stdout.flush()

        self.prog = x

    def end(self):
        if type_system.interactive:
            sys.stdout.write("#" * (40 - self.prog) + "]\n")
            sys.stdout.flush()
