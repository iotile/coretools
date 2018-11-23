from iotile.core.utilities.typedargs import context, annotated, param, return_type, iprint
from .resolverchain import DependencyResolverChain
from iotile.core.dev.semver import SemanticVersionRange

@param("name", "string", desc='The fully qualified name of the released component to pull')
@param("version", "string", desc='The semantic version range to pull')
@param("force", "bool", desc='If the component is already pulled, forcibly overwrite it')
def pull(name, version, force=False):
    """Pull a released IOTile component into the current working directory

    The component is found using whatever DependencyResolvers are installed and registered
    as part of the default DependencyResolverChain.  This is the same mechanism used in
    iotile depends update, so any component that can be updated using iotile depends update
    can be found and pulled using this method.
    """

    chain = DependencyResolverChain()

    ver = SemanticVersionRange.FromString(version)
    chain.pull_release(name, ver, force=force)
