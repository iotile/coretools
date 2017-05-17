
Creating Your First IOTile Device
---------------------------------

There are two kinds of IOTile Devices, real and virtual.  Real devices are physical
objects that let you either sense or control things around you.  Virtual devices
are programs that act as if they are real IOTile Devices.  

Virtual devices are indistinguishable from real IOTile devices, except for the 
fact that you can't actually touch them.  In particular, virtual IOTile devices
interact with the rest of CoreTools the same way a real device would, so they are 
particularly useful for tutorials like this one.

We're going to make a simple virtual IOTile Device that will stream you fake temperature
data when you connect to it.  It will also have one command that will send you a random 
temperature value back to you whatever you call it.  Then we're going to interact with the 
device as if it were a real IOTile device.

Goals
#####

1. Introduce the concept of Python Proxy Modules, that are used to wrap low-level access to
   IOTile devices in a python compatible API

2. Introduce Virtual Devices and show how you can use them to quickly mock up what a real 
   IOTile device could look like and use them with the rest of CoreTools.

3. Introduce Support Packages, which are pip installable packages that contain all of the
   necessary python modules to interact with an IOTile Device.  They are usually produced
   as part of the build process for the device.

.. note::

    For this tutorial, you are going to need to have CoreTools installed.  It's best to create
    a new virtual environment for this walkthrough so that you have a clean slate and don't
    pollute any other CoreTools installations you have with the products of this walkthrough.

Background
##########

When you send commands to an IOTile device, the commands all take the form of remote procedure
calls (RPCs).  Basically you send an ID indicating what function you want the device to execute,
followed by the arguments.  The device synchronously executes the function and returns the response
back to you as if you had just invoked a function locally on your own computer.

Since IOTile devices typically contain small embedded microcontrollers, the low-level binary encoding
for how RPCs are transmitted to the device is not user-friendly, e.g. the RPCs are identified with unique
16-bit numbers rather than string names and all arguments and responses are packed into 20 byte
binary buffers.  

So, instead of directly building these low-level RPC payloads and manually decoding the responses, CoreTools
wraps them inside a python class where the methods on the class take in normal python objects as 
arguments, build the RPC payload and decode the response back into normal python objects.  These
wrappers are called **Proxy Objects** and the python modules that contain them are called **Python
Proxy Modules**.  

Every IOTile device should have at least one python proxy module that allows you to access its functionality
from python.  Many IOTile devices internally consist of several distinct parts called Tiles, each of which
is independent and has its own proxy module.  For now though, we won't have to worry about multiple
proxy modules.  

The goal of this tutorial is walk you through creating a proxy module.  Rather than wrapping a physical 
IOTile device though, we'll wrap a virtual device so you don't need any hardware to follow the walk through.

Getting Started
###############

Before we can start working on our proxy module, we first need to get some boilerplate out of the way.  We need
to create an IOTile component that will contain our proxy module.

.. important::
    
    Pretty much everything in the IOTile world (except CoreTools itself) starts its life as an IOTile Component.
    Components are like packages in ``npm``, or distributions in ``PyPI``.  They are just directories with a
    ``module_settings.json`` file that lets CoreTools know what to do with the files inside the folder.

So, let's create an empty Component to contain our proxy module::

    $ mkdir test_component
    $ cd test_component
    $ mkdir python
    $ touch python/demo_proxy.py
    $ touch module_settings.json
    $ ls
    module_settings.json    python

Now we need to add enough information to ``module_settings.json`` to identify this folder as an IOTile component and
point out that ``demo_proxy.py`` should be treated as a proxy module.  We'll call our component ``demo_component`` and
put it in the ``walkthrough`` namespace (called a domain).  These names can be anything but should be unique if you
every want to share your component with anyone else.

Save the following to your ``module_settings.json`` file::

    {
        "module_name": "demo_component",
        "modules":
        {
            "demo_component":
            {
                "version": "0.0.1",

                "products":
                {
                    "python/demo_proxy.py": "proxy_module"
                },

                "domain": "walkthrough"
            }
        }
    }

This is the minimum needed in a ``module_settings.json`` file to identify the component and point out that we have a proxy
module defined in ``python/demo_proxy.py``.  In more complicated components, there are many different kinds of products that
could be generated and would be listed along with the proxy module in the ``products`` section of the file.

Now that we have an IOTile component, we need to tell CoreTools about it by adding it to the Component Registry (this command
should be run from the ``test_component`` directory::
    
    $ iotile registry add_component .
    $ iotile registry list_components
    walkthroughs/demo_component

.. important::

    The Component Registry is a file maintained in each virtualenv that contains a CoreTools installation.  It lists what
    iotile components have been installed so that CoreTools knows to look in those directories for things like proxy modules.

    **Any changes you make to your Component Registry only affect your current virtual environment.**

Now you have your component registered with CoreTools so we need to create a simple virtual device that it can interact with.


Creating a Virtual Device
#########################

Virtual IOTile devices are just python scripts that define a class that inherits from ``VirtualIOTileDevice``.  We're going to
create a demo device.  Just like above there is a bit of boilerplate that is required for the device to support the necessary
RPC for CoreTools be able to identify its name and match it with a Proxy Module.  

Create a file named ``demo_device.py`` in your current working directory with the following contents::

    """Virtual IOTile device for CoreTools Walkthrough
    """

    from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc


    class DemoVirtualDevice(VirtualIOTileDevice):
        """A simple virtual IOTile device that has an RPC to read fake temperature

        Args:
            args (dict): Any arguments that you want to pass to create this device.
        """

        def __init__(self, args):
            super(DemoVirtualDevice, self).__init__(1, 'Demo01')

        @rpc(8, 0x0004, "", "H6sBBBB")
        def controller_status(self):
            """Return the name of the controller as a 6 byte string
            """

            status = (1 << 1) | (1 << 0)  # Report configured and running
            return [0xFFFF, self.name, 1, 0, 0, status]

Note how this is just a normal python class and it has one function ``controller_status`` that is
decorated with an ``@rpc`` decorator.  This decorator is how we mark what python functions in our
class are really mocking the RPCs present in a real IOTile device.  For more information on the ``rpc``
decorator, we can see its documentation below.

.. py:module:: iotile.core.hw.virtual.virtualdevice
.. autofunction:: rpc


There are a couple of other things to note about our ``DemoVirtualDevice``.  We gave it a name of ``Demo01``.  All IOTile
devices have a 6 character name that is used to match the device with its associated proxy module by looking for matching
names.  We also gave the device an IOTile ID of 1, which we'll use to connect to the device.

So, let's try to interact with our virtual device::

    $ iotile hw --port=virtual:./demo_device.py
    (HardwareManager) connect_direct 1
    (HardwareManager) controller
    HardwareError: Could not find proxy object for tile
    Additional Information:
    known_names: ['Simple', 'NO APP']
    name: 'Demo01'
    (HardwareManager) quit
    $

We told the ``iotile`` tool that we wanted to connect to an IOTile device that was virtual and implemented in the python module
``./demo_device.py``.  We connected to it (``connect_direct 1``) and tried to get a proxy object for it using the ``controller``
command but we were told that CoreTools couldn't find a proxy module for it.  

This makes sense because we haven't created the proxy module yet.  So, lets create a basic proxy module and try again.  Add the
following to ``demo_proxy.py``::

    from iotile.core.hw.proxy.proxy import TileBusProxyObject
    from iotile.core.utilities.typedargs.annotate import return_type, context, param
    import struct

    @context("DemoProxy")
    class DemoProxyObject(TileBusProxyObject):
        """A demo proxy object for the CoreTools walkthrough
        """

        @classmethod
        def ModuleName(cls):
            """The 6 byte name by which CoreTools matches us with an IOTile Device
            """

            return 'Demo01'

The only required function that we need to implement is the classmethod ``ModuleName`` that tells CoreTools what IOTile devices
should load this proxy module.  Now let's try to connect to our virtual device again::

    $ iotile hw --port=virtual:./demo_device.py connect_direct 1 controller
    (DemoProxy) quit
    $

This time CoreTools looked through the registry and found a matching proxy object (our DemoProxy object).  Now we're ready to start
adding some functions to our virtual device and wrapping them in the proxy object so we can test them out from the command line.

Adding an RPC That Returns Data
###############################

Let's add an RPC to our virtual device name ``get_temperature`` that returns the (fake) temperature of the device.  Add the following to 
your demo_device.py DemoVirtualDevice class::

    
    @rpc(8, 0x8000, "", "L")
    def get_temperature(self):
        """Get the current temperature of the device in degrees kelvin

        Returns:
            list  a list with a single value containing the device temperature
        """

        return [273]

This defines an RPC with id ``0x8000`` that returns a single 32-bit integer (the ``L`` result format) with the fixed value 273.  Now we 
need to add a function to our proxy object that calls this RPC.  

Add the following to your ``demo_proxy.py`` ``DemoProxyObject`` class::
    
    @return_type("float")
    def get_temperature(self):
        temp, = self.rpc(0x80, 0x00, result_format="L")
        return float(temp)

.. note::
    The decorator on this function is what allows ``iotile`` to print the function's return value on the command line.  There is more information
    about these type annotations in the section on ``typedargs``.  

Now let's call our new RPC::

    $ iotile hw --port=virtual:./demo_device.py connect_direct 1 controller
    (DemoProxy) <TAB><TAB>
    back             get_temperature  quit             status           tile_status
    config_manager   help             reset            tile_name        tile_version
    (DemoProxy) get_temperature
    273.0
    (DemoProxy) quit
    $

Internally this worked because our type annotation in DemoProxyObject told the ``iotile`` tool that this function could be called from the command
line.  So when we typed ``get_temperature`` we invoked that function in ``DemoProxyObject``.  Internally it used the ``self.rpc`` function provided
by ``TileBusProxyObject`` to invoke an RPC on our virtual device, which sent back the temperature value 273 that it then returned and ``iotile`` 
printed for us using the ``return_type`` type annotation to know that we wanted it to print the result as a floating point number.

If we had been talking to a physical IOTile device rather than a virtual one, nothing would be different except for the argument that we passed to
``--port`` in HardwareManager that tells it what transport mechanism to use to send RPCs and receive their responses.

Adding a More Complex RPC
#########################


Let's say that our device actually can store the last 5 temperature values that its recorded and has an RPC that allows us to query them all.  We want
to print those values as a list.  First lets implement the underlying RPC on the virtual device::

    @rpc(8, 0x8001, "", "LLLLL")
    def historical_temps(self):
        """Get a list of 5 temperatures from the device in degrees kelvin

        Returns:
            list  a list with a single value containing the device temperature
        """

        return [273, 280, 215, 315, 300]

Then we need to add a corresponding call on the proxy object::

    @return_type("list(float)")
    def historical_temps(self):
        temps = self.rpc(0x80, 0x01, result_format="LLLLL")
        return [float(x) for x in temps]

.. note::
    See how we used a complex type annotations ``list(float)`` to tell ``typedargs`` how to print our return value even though it wasn't
    a simple primitive type.

Now we can call it::

    $ iotile hw --port=virtual:./demo_device.py connect_direct 1 controller
    (DemoProxy) historical_temps
    273.0
    280.0
    215.0
    315.0
    300.0
    (DemoProxy) quit
    $

Setting Values Using an RPC
###########################

Up until now, we've only received information from RPCs, so lets create one that lets us set the temperature that the virtual device returns when you 
call `get_temperature`.  We'll need to create a member variable to store the temperature and a new RPC `set_temperature` that sets its value.  Adjust
``demo_device.py`` to look like this::

    """Virtual IOTile device for CoreTools Walkthrough
    """

    from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc


    class DemoVirtualDevice(VirtualIOTileDevice):
        """A simple virtual IOTile device that has an RPC to read fake temperature

        Args:
            args (dict): Any arguments that you want to pass to create this device.
        """

        def __init__(self, args):
            super(DemoVirtualDevice, self).__init__(1, 'Demo01')
            self.temp = 273

        @rpc(8, 0x0004, "", "H6sBBBB")
        def controller_status(self):
            """Return the name of the controller as a 6 byte string
            """

            status = (1 << 1) | (1 << 0)  # Report configured and running
            return [0xFFFF, self.name, 1, 0, 0, status]

        @rpc(8, 0x8000, "", "L")
        def get_temperature(self):
            """Get the current temperature of the device in degrees kelvin

            Returns:
                list  a list with a single value containing the device temperature
            """

            return [self.temp]

        @rpc(8, 0x8002, "L")
        def set_temperature(self, new_temp):
            """Set the current temperature of the device in degrees kelvin
            """

            self.temp = new_temp
            return []

        @rpc(8, 0x8001, "", "LLLLL")
        def historical_temps(self):
            """Get a list of 5 temperatures from the device in degrees kelvin

            Returns:
                list: a list with 5 historical temperatures
            """

            return [273, 280, 215, 315, 300]

Now add a new annotated RPC wrapper to ``DemoProxyObject``::

    @param("new_temp", "integer")
    def set_temperature(self, new_temp):
        args = struct.pack("<L", new_temp)

        self.rpc(0x80, 0x02, args)

.. important::
    
    When you write a proxy module method that takes arguments, you need to tell ``typedargs`` what type they are so that it can convert them
    to the appropriate python types when you enter them on the command line.  In this case we're telling ``typedargs`` that we take one parameter
    ``new_temp`` that is an integer.  That's all we need to say and ``typedargs`` takes care of interpreting our command line input into a native
    python integer and passing that to ``set_temperature``.

Note that we need to explicitly pack our arguments into a binary structure using struct.pack.  In this case we're packing new_temp into a little-endian
32 bit integer.

Let's try out our ``set_temperature`` and ``get_temperature`` functions::

    $ iotile hw --port=virtual:./demo_device.py connect_direct 1 controller
    (DemoProxy) get_temperature
    273.0
    (DemoProxy) set_temperature 15
    (DemoProxy) get_temperature
    15.0
    (DemoProxy) set_temperature 275
    (DemoProxy) get_temperature
    275.0
    (DemoProxy) quit
    $

Next Steps
##########

This concludes the tutorial on creating proxy modules.  It's a pretty simple proxy module that we made that just sets one number but one of the
core principles of IOTile is that everything we do should be as reusable as possible, so in future tutorials we'll take the exact same proxy module and
virtual device and show how you can access them over MQTT from anywhere in the world or over Bluetooth Low Energy without doing any additional work.

You may already be able to think of what you would want to do with a virtual device running on your computer that would let you run a python function
from anywhere in the world.