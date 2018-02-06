class PromptStep (object):
    def __init__(self, args):
        self._message = args['message']

    def run(self):
        raw_input(self._message)
