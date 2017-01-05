from iotile.build.dev.resolverchain import DependencyResolverChain

def test_resolverchain_defaults():
    """Make sure the ResolverChain is able to fetch default resolvers
    """
    
    chain = DependencyResolverChain()
    assert len(chain.rules) == 1
