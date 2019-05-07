Getting Started
===============

CoreTools is distributed using normal pip installable packages on PYPI.  It is
recommended that you install everything in a virtual environment since CoreTools
is highly extensible and the IOTile devices you interact with may require
plugins or extensions that should not pollute your global site-packages.


.. note::
    On Windows you may need to install Python 3.5+ since it does not come
    preinstalled.  Any distribution should work but CoreTools is tested using
    the official `Python for Windows`_ distribution running under PowerShell.  

Installation Requirements
-------------------------

CoreTools is cross-platform and is tested on Mac OS, Linux and Windows.  It 
currently requires Python 3.5+.

.. note::
    
    It is recommended to always install coretools into a virtual environment.
    This allows you to separate any plugins that you may install on top of
    CoreTools on a project by project basis::

        pip install virtualenv
        virtualenv --python=python3.5 iotile

        #On Mac/Linux
        source iotile/bin/activate

        #On Windows Powershell
        iotile/Scripts/activate.ps1

        #On Windows CMD
        iotile\Scripts\activate.bat

Note that *virtualenv* only needs to be installed once; iotile must be activated in a every new virtual enviroment. 

Installing CoreTools is just a normal pip install:

    pip install iotile-core iotile-test iotile-emulate iotile-transport-bled112

.. seealso::
    If you plan on building your own IOTile device, you should also install 
    iotile-build but there are additional requirements to use iotile-build that 
    must be installed separately, see :ref:`build-reqs`.

.. _first-steps:

First Steps
-----------

The easiest way to try out your new CoreTools installation is by using the 
``iotile`` tool that is installed as a console script by ``iotile-core``.

The iotile tool provides command line access to key parts of the IOTile API.  It
allows many tasks to be performed without writing python scripts.

.. note::
    Everything that you can do with the ``iotile`` tool, you can also do from
    a python script.  This makes the ``iotile`` tool an ideal way to perform
    quick tasks that you could then wrap up into a script later if you find 
    yourself doing the same thing repeatedly.

Let's get started by trying to talk to an IOTile device.  Let's say you have
a simple piece of IOTile based hardware and you want to connect to it and send
it commands.  In this example we're going to be using a virtual IOTile device
that doesn't require any physical hardware but the process to talk to a real
device is exactly the same::

    iotile hw --port=virtual:simple
    (HardwareManager) quit

By using the ``iotile hw`` command, we're attempting to connect to an IOTile
Device.  In this case we're telling the tool that we want to connect to a virtual
device using the ``virtual`` port.  The remaining argument tells the tool which
installed virtual device we would like to load.  The ``quit`` command always
quits the shell.

Like a normal shell, we can use <TAB> to see a list of supported commands::

    iotile hw --port=virtual:simple
    (HardwareManager) 
    app                  controller           enable_broadcasting  help                 watch_reports
    back                 count_reports        enable_streaming     quit                 watch_scan
    close                debug                enable_tracing       reset
    connect              disconnect           get                  scan
    connect_direct       dump_trace           heartbeat            watch_broadcasts

At this point, we have not connected to the ``simple`` device yet, so let's 
connect directly to it::

    (HardwareManager) connect_direct 1

Since this is an example device, it has a hard-coded unique identifier of 1. 
In real life, devices would have their unique identifiers set at the factory
and printed on the device.  

Now that we have connected to the device, we can send it commands.  Every IOTile 
Device has one component that acts as a Controller and handles communication
with the external world.  We can get access to this device's controller using
the ``controller`` command::

    (HardwareManager) controller
    (SimpleProxy) <TAB>
    back              config_manager    help              reset             tile_name         tile_version
    check_hardware    hardware_version  quit              status            tile_status

Notice how the prompt changes to indicate what context we're in.  When we typed
``controller`` we moved from the ``HardwareManager`` context to the ``SimpleProxy``
context that is a python representation (or Proxy object) for the physical controller
hardware that we are talking to.

.. note::
    When you are talking to an IOTile device, commands that you enter are sent
    to the IOTile Device as Remote Procedure Calls (RPCs) and the response from
    the device is routed back to you and displayed.  This means that the ``iotile``
    tool effectively becomes a REPL for your IOTile Device.

The only commands that are supported by the ``simple`` device are RPCs to query
its name, version and status, so lets try those::

    (SimpleProxy) tile_name
    Simple
    (SimpleProxy) tile_version
    [1, 0, 0]
    (SimpleProxy) tile_status
    configured: True
    debug_mode: False
    app_running: True
    trapped: False
    (SimpleProxy)

The results of each command are printed in the console for you.  We can see
that this device is named 'Simple' and has version 1.0.0.  It's reporting its
status as configured and running with no errors and not currently in debug mode.

Writing Scripts
---------------

Every action you take in the ``iotile`` tool maps 1:1 to exactly one python
function or method.  So it's easy to take something that's done in the ``iotile`` 
tool and turn it into a python script.  For example, lets create a script that
connects to the same device we just used in :ref:`first-steps` and gets its 
version::

    from iotile.core.hw.hwmanager import HardwareManager

    with HardwareManager(port='virtual:simple') as hw:
        hw.connect_direct('1')
        con = hw.controller()
        version = con.tile_version()

        print("Tile Version: {}".format(version))

Save this script as ``example.py`` and let's run it::

    python example.py
    Tile Version: (1, 0, 0)

Clearly, this code creates a hardware manager and finds the version number.
The manager is instantiated in the with-as statement. The following 3 lines
connect, gain control, and find the version respectively.

Note how every command in the script mapped to a single line in ``iotile`` and
how the arguments you passed were the same.  There is always a 1:1 mapping like
this between the ``iotile`` tool and python scripts.  

That's it, you now know the basics of using CoreTools to interact with IOTile
Devices and transform ``iotile`` shell commands into python scripts.

.. _`Python for Windows`: https://www.python.org/downloads/windows/
