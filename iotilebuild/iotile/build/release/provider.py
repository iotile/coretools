"""Superclass for ReleaseProvider objects that allow releasing IOTile components
"""

class ReleaseProvider(object):
    """Base class for release providers that allow releasing IOTile components

    ReleaseProviders has just two methods: stage, unstage, release and unrelease (if supported)

    All methods take in a release mode IOTile object.

    - stage should attempt to release the IOTile as much as possible without making it
      externally visible.  The purpose of stage is to allow a sequence of ReleaseProviders
      to be executed sequentially and then rolled back if one of them fails.  If staging
      does not make sense for a given provider, it can be implemented as a noop.

    - release should make the IOTile object externally visible and completely released.
      release can assume that stage has returned successfully before it has been run.

    - unstage should undo whatever is done in stage.  unstage will only be run if stage
      has completed successfully.  If an exception is raised during stage, it must clean
      up after itself before passing the exception back up the stack.

    - unrelease should undo whatever is done in release.  If release builds on something
      that is done in stage, then unrelease should also call unstage or implement the
      same functionality.

    Args:
        args (dict): Whatever arguments were specified for this release provider in module_settings.json
        component (IOTile): The IOTile object that should be released.  It must be a release mode IOTile
            object.
    """

    def __init__(self, component, args):
        self.component = component
        self.args = args

    def stage(self):
        """Stage this component for release
        """

        raise NotImplementedError("ReleaseProvider subclasses must override the stage method")

    def unstage(self):
        """Unstage this component assuming that stage succeeded
        """

        raise NotImplementedError("ReleaseProvider subclasses must override the unstage method")

    def release(self):
        """Release this component assuming that stage succeeded
        """

        raise NotImplementedError("ReleaseProvider subclasses must override the release method")

    def unrelease(self):
        """Unrelease this component assuming that release succeeded
        """

        raise NotImplementedError("ReleaseProvider subclasses must override the unrelease method")
