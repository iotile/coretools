import time

class WaitStep (RecipeActionObject):
    def __init__(self, args):
        self._seconds = args['seconds']

    def run(self):
        time.sleep(self._seconds)
