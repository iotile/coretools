How CoreTools Works
===================

CoreTools is architected to be modular in two major ways.  

The first way is that it is distributed as a series of packages, so you can pick
what you need to install depending on what you want to do.  If you don't plan on 
building your own firmware, there's no reason to install ``iotile-build``.  
Everything else works perfectly without it.

The second way is that CoreTools uses plugins heavily in order to allow users
to swap in replacement functionality as needed.  For example, whenever CoreTools
needs to search for a virtual IOTile Device it uses ``pkg_resources`` to look
for all entry_points in the group ``iotile.virtual_device``.  You can provide
your own virtual device by just pip installing a package that contains the 
correct entry point. 

Packages in CoreTools
---------------------

iotile-core
    The foundation of CoreTools, providing access to IOTile devices via 
    HardwareManager as well as common utilities, the typedargs annotation system
    for the ``iotile`` tool and the ``virtual_device`` host program for creating
    virtual IOTile devices.

iotile-gateway
    Components for creating gateways that provide cloud access to IOTile devices
    that otherwise would not have a built-in long-range communication mechanism.

iotile_transport_bled112
    A package that provides cross-platform access to IOTile devices over Bluetooth
    Smart using a specific BLE dongle (the BLED112) produced by Silicon Labs

iotile-build
    The foundation of the IOTile build system that defines how hardware and firmware
    designs are built and released.

iotile-test
    Mocks and routines for testing CoreTools and exercising its features.  

How the IOTile Tool Works
-------------------------

The ``iotile`` tool is a command line wrapper that provides a REPL for calling
functions and classes defined inside CoreTools or one of its installed plugins.

The tool works by parsing commands given on the command line into python functions
that can be executed.  Once a function is parsed, it is called and the return value
is either printed or, if the function returns a specially decorated **context** 
object, that object is set as the current context and used for resolving further 
commands.

For example, consider the following ``iotile`` command line::

    iotile hw --port=virtual:simple connect_direct 1 controller quit

The IOTile tool parses the command from left to right lazily until it has enough
information to execute a command.  It starts in the **root context**. The root
context only has a few commands defined as seen in ``iotile.core.scripts.iotile_script.py``::

    shell = HierarchicalShell('iotile', no_rc=norc)
        
    shell.root_add("registry", "iotile.core.dev.annotated_registry,registry")
    shell.root_add('hw', "iotile.core.hw.hwmanager,HardwareManager")

``shell.root_add`` maps a string to a python callable.  In this case ``hw`` is
mapped to the HardwareManager class.  Since HardwareManager is a class, it is
created and the argument ``port=virtual:simple`` is passed to ``__init__()`` as
a keyword argument (since it was passed using --port rather than as a positional
argument.

The result is an instance of the HardwareManager class, which is itself a **context**
so processing of the command line continues.  The next portion of the command line
is ``connect_direct 1``, which is a method defined in HardwareManager.  Since 1
was a positional argument on the command line, it is passed as positional argument
to ``connect_direct.

.. py:module:: iotile.core.hw.hwmanager

.. autoclass:: HardwareManager
    :members: connect_direct, controller

``connect_direct`` does not return a context so the context for executing commands
remains the HardwareManager instance.  The next chunk of the command line is
``controller``, which is another method of HardwareManager so that method is called
and it returns a TileBusProxyObject that is a context.  Finally the ``quit``
command is built-in to the ``iotile`` tool and quits.

So the flow is:

1. --port=virtual:simple creates a HardwareManager instance
2. connect_direct 1 calls a method on that instance
3. controller calls a method on that instance that changes the current context
4. quit terminates the shell.
   
To see how this works explicitly, we can execute the commands one by one and view
how the current context changes as the result of each command::

    $ iotile
    (root) hw --port=virtual:simple
    (HardwareManager) connect_direct 1
    (HardwareManager) controller
    (SimpleProxy) quit

.. note::
    
    The key idea is that every command in the ``iotile`` tool is a single python
    function call and the arguments on the command line are arguments passed to
    the function.  

Type Conversions and Pretty-Printing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Since ``iotile`` commands call the same python functions that you would invoke
directly from a python script, there needs to be some mapping between the strings
that you pass on the command line and the native python types that the API functions
accept as parameters.  This mapping and conversion is the done by the ``typedargs`` 
package that is part of ``iotile-core``.  See :ref:`typedargs-reference` for more
details.

Adding Your Own Commands to the IOTile Tool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Any python package can add its own commands to the IOTile tool by registering a
``pkg_resources`` entry point with the group name ``iotile.plugin``.  See
:ref:`extensibility` for more information.

.. _extensibility:

Extensibility via Entry Points
------------------------------

There are many parts of CoreTools that can be extended.  For example, there are
many different ways to talk to IOTile devices, including USB, BLE, Serial, etc.
It would overly bloat CoreTools to include every possible way you could want to
talk to an IOTile device.  On the other hand, many parts of CoreTools depend deeply
on the ability to talk to an IOTile device, irrespective of how it happens to be
connected.  

To allow for users to swap in new functionality into CoreTools, key areas are 
delegated to plugins with a few default versions included and a mechanism to 
easily add others.  

The plugin mechanism is based on standard Python ``entry_points`` as defined
in `pkg_resources`_.

Any python distribution can define an entry point with a group name.  When CoreTools
needs to look for a plugin, it searches all of the installed python distributions
for entry points with the desired group name.  

.. warning::
    
    Because of the ability to modify CoreTools through entry points, it is important
    to isolate different projects based on CoreTools from each other in their
    own virtual environments.  This is especially important in production settings
    where careful control of the installed CoreTools plugins is essential for 
    safe and robust usage.

Entry points are defined in a package's ``setup.py`` file.  For example, 
the ``iotile-core`` package defines a number of entry points::

    setup(
        ...
        entry_points={
            'console_scripts': [
                'iotile = iotile.core.scripts.iotile_script:main',
                'virtual_device = iotile.core.scripts.virtualdev_script:main'
            ],
            'iotile.cmdstream': [
                'ws = iotile.core.hw.transport.websocketstream:WebSocketStream',
                'recorded = iotile.core.hw.transport.recordedstream:RecordedStream'
            ],
            'iotile.device_adapter': [
                'virtual = iotile.core.hw.transport.virtualadapter:VirtualDeviceAdapter'
                ],
            'iotile.report_format': [
                'individual = iotile.core.hw.reports.individual_format:IndividualReadingReport',
                'signed_list = iotile.core.hw.reports.signed_list_format:SignedListReport'
            ],
            'iotile.auth_provider': [
                'BasicAuthProvider = iotile.core.hw.auth.basic_auth_provider:BasicAuthProvider',
                'EnvAuthProvider = iotile.core.hw.auth.env_auth_provider:EnvAuthProvider',
                'ChainedAuthProvider = iotile.core.hw.auth.auth_chain:ChainedAuthProvider'
            ],
            'iotile.default_auth_providers': [
                'BasicAuthProvider = iotile.core.hw.auth.default_providers:DefaultBasicAuth',
                'EnvAuthProvider = iotile.core.hw.auth.default_providers:DefaultEnvAuth'
            ]
        })

Currently, the following entry points are used:

iotile.plugin
    Injects a new command into the root context of the iotile tool.  See :ref:`plugins`.

iotile.virtual_device
    A python class that inherits from VirtualIOTileDevice and provides methods
    that implement TileBus RPCs.  Virtual devices can be accessed in exactly the
    same way that physical IOTile devices are accessed.  See :ref:`virtualdevice`.

iotile.device_adapter
    Classes that allow access to an IOTile device over some kind of transport 
    mechanism such as USB, BLE, http, etc.  See :ref:`adapters`.

iotile.virtual_interface
    Classes the provide access to a virtual IOTile device (i.e. one that does not
    actually exist as real hardware over some kind of transport mechanism.  You 
    can think of virtual interfaces as the server portion of connecting to an
    IOTile device, whereas device adapters are the client portion.  For example,
    using a BLE virtual interface, you could turn a regular computer into an IOTile
    compatible device that would respond to RPCs. See :ref:`virtual_interface`.

iotile.report_format
    Classes that provide methods for IOTile devices to package and send data to
    the cloud.  These are packet formats for packing, signing and potentially
    encrypting data from an IOTile device.  See :ref:`report_formats`.

iotile.auth_provider
    Classes that provide the ability to authenticate and/or encrypt reports
    from IOTile Devices.  See :ref:`auth_provider`.

iotile.default_auth_providers
    The ordered list of AuthProvider classes that are used by default to sign,
    verify, encrypt or decrypt reports from IOTile devices.  Packages can insert
    their own AuthProvider classes into the default authentication process using
    this hook. See :ref:`default_auth`.


.. _`pkg_resources`: http://setuptools.readthedocs.io/en/latest/pkg_resources.html#entry-points