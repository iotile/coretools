from __future__ import unicode_literals

def setup_plugin():
    u = 'build'
    v = 'iotile.build.build.build,build'

    d = 'depends'
    dv = 'iotile.build.dev,DependencyManager'

    b = 'release'
    bv = 'iotile.build.release.release,release'

    p = 'pull'
    pv = 'iotile.build.dev.pull_release,pull'

    return [(u,v), (d,dv), (b, bv), (p,pv)]
