"""Tools for automatically releasing built IOTile components
"""

import pkg_resources
from iotile.core.dev.iotileobj import IOTile
from iotile.core.utilities.typedargs import param
from iotile.core.exceptions import ArgumentError, DataError, BuildError, IOTileException

class ReleaseFailureError(BuildError):
    pass


class CleanReleaseFailureError(ReleaseFailureError):
    """The release process failed but it was rolled back successfully

    No intermediate release products should be left.
    """
    pass


class DirtyReleaseFailureError(ReleaseFailureError):
    """The release process failed and additionally there was an error rolling back

    There may be intermediate release products that need to be cleaned up.
    """
    pass


@param("component", "path", desc="Path to the iotile object that we should release")
def release(component):
    """Release an IOTile component using release providers

    Releasing an IOTile component means packaging up the products of its build process and storing 
    them somewhere.  The module_settings.json file of the IOTile component should have a 
    "release_steps" key that lists the release providers that will be used to release the various
    build products.  There are usually multiple release providers to, for example, send firmware
    images somewhere for future download, post the documentation and upload python support wheels
    to a PyPI index.
    """

    comp = IOTile(component)
    providers = _find_release_providers()

    #If we were given a dev mode component that has been built, get its release mode version
    if not comp.release and comp.release_date is not None:
        comp = IOTile(comp.output_folder)

    if not comp.release:
        raise ArgumentError("Attempting to release a dev mode IOTile component that has not been built.", suggestion='Use iotile build to build the component before releasing', component=comp)

    if not comp.can_release:
        raise ArgumentError("Attemping to release an IOTile component that does not specify release_steps and hence is not releasable", suggestion="Update module_settings.json to include release_steps", component=comp)

    configured_provs = []

    for step in comp.release_steps:
        if step.provider not in providers:
            raise DataError("Release step for component required unknown ReleaseProvider", provider=step.provider, known_providers=providers.keys())

        prov = providers[step.provider](comp, step.args)
        configured_provs.append(prov)

    #Attempt to stage releases for each provider and then release them all, rolling back if there is an error
    for i, prov in enumerate(configured_provs):
        try:
            prov.stage()
        except IOTileException, exc:
            try:
                #There was an error, roll back
                for j in xrange(0, i):
                    configured_provs[j].unstage()
            except Exception, unstage_exc:
                raise DirtyReleaseFailureError("Error staging release (COULD NOT ROLL BACK)", failed_step=i, original_exception=exc, operation='staging', failed_unstage=j, unstage_exception=unstage_exc)
            
            raise CleanReleaseFailureError("Error staging release (cleanly rolled back)", failed_step=i, original_exception=exc, operation='staging')
        except Exception, exc:
            raise DirtyReleaseFailureError("Error staging release due to unknown exception type (DID NOT ATTEMPT ROLL BACK)", failed_step=i, original_exception=exc, operation='staging')

    #Stage was sucessful, attempt to release
    for i, prov in enumerate(configured_provs):
        try:
            prov.release()
        except IOTileException, exc:
            try:
                #There was an error, roll back
                for j in xrange(0, i):
                    configured_provs[j].unrelease()
            except Exception, unstage_exc:
                raise DirtyReleaseFailureError("Error performing release (COULD NOT ROLL BACK)", failed_step=i, original_exception=exc, operation='release', failed_unrelease=j, unrelease_exception=unstage_exc)
            
            raise CleanReleaseFailureError("Error performing release (cleanly rolled back)", failed_step=i, original_exception=exc, operation='release')
        except Exception, exc:
            raise DirtyReleaseFailureError("Error performing release due to unknown exception type (DID NOT ATTEMPT ROLL BACK)", failed_step=i, original_exception=exc, operation='release')


def _find_release_providers():
    provs = {}

    for entry in pkg_resources.iter_entry_points('iotile.build.release_provider'):
        name = entry.name
        prov = entry.load()

        provs[name] = prov

    return provs