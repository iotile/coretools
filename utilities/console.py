import sys

class ProgressBar:
    """
    A simple progress bar that updates itself in the console
    """

    def __init__(self, title, count=100):
        self.title = title
        self.prog = 0 
        self.count = count

    def start(self):
        sys.stdout.write(self.title + ": [" + "-"*40 + "]" + chr(8)*41)
        sys.stdout.flush()
        self.prog = 0

    def progress(self, x):
        x = int(x * 40 // self.count)
        sys.stdout.write("#" * (x - self.prog))
        sys.stdout.flush()
        self.prog = x

    def end(self):
        sys.stdout.write("#" * (40 - self.prog) + "]\n")
        sys.stdout.flush()