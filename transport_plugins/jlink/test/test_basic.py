"""Basic tests of jlink transport plugin."""
import pytest

from iotile_transport_jlink.jlink import JLinkAdapter
from iotile_transport_jlink.multiplexers import *
from iotile_transport_jlink.devices import *

def test_jlink_parse_port():    
    #Empty port string
    jlink_test = JLinkAdapter("")
    assert jlink_test._device_info is None
    assert jlink_test._default_device_info is None
    assert jlink_test._jlink_serial is None
    assert jlink_test._mux_func is None

    #All strings Name
    jlink_test = JLinkAdapter("device=nrf52;serial=00000000;mux=ftdi")
    assert jlink_test._device_info is None
    assert jlink_test._default_device_info is NRF52
    assert jlink_test._jlink_serial == "00000000"
    assert jlink_test._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']

    #Unknown device
    with pytest.raises(ArgumentError):
        jlink_test = JLinkAdapter("device=error")

    #Unknown mux
    with pytest.raises(ArgumentError):
        jlink_test = JLinkAdapter("mux=error")

    #Bogus port string
    jlink_test = JLinkAdapter("error=error")

def test_jlink_parse_conn_string():
    #jlink no device and no mux set
    jlink_test = JLinkAdapter("")
    assert jlink_test._device_info is None
    assert jlink_test._channel is None
    assert jlink_test._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test._device_info is LPC824
    assert jlink_test._channel is None

    #jlink device set, no mux set
    jlink_test_dev = JLinkAdapter("device=nrf52")
    assert jlink_test_dev._parse_conn_string("")
    assert jlink_test_dev._mux_func is None
    assert jlink_test_dev._device_info is NRF52
    assert jlink_test_dev._channel is None
    assert jlink_test_dev._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test_dev._mux_func is None
    assert jlink_test_dev._device_info is LPC824
    assert jlink_test_dev._channel is None

    #jlink mux set, no device set
    jlink_test_mux = JLinkAdapter("mux=ftdi")
    assert not jlink_test_mux._parse_conn_string("")
    assert jlink_test_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_mux._device_info is None
    assert jlink_test_mux._channel is None
    assert jlink_test_mux._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_mux._device_info is LPC824
    assert jlink_test_mux._channel == 1

    #jlink mux set, no device set
    jlink_test_dev_mux = JLinkAdapter("device=nrf52;mux=ftdi")
    assert jlink_test_dev_mux._parse_conn_string(None)
    assert jlink_test_dev_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_dev_mux._device_info is NRF52
    assert jlink_test_dev_mux._channel is None
    assert jlink_test_dev_mux._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test_dev_mux._device_info is LPC824
    assert jlink_test_dev_mux._channel == 1

def test_jlink_parse_conn_string_repeat():
    """Tests to see if _parse_conn_string properly determines whether to disconnect 
    or connect jlink"""

    """Default is given"""
    jlink_test_mux = JLinkAdapter("mux=ftdi;device=nrf52")
    assert jlink_test_mux._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_mux._device_info is LPC824
    assert jlink_test_mux._channel == 1
    assert not jlink_test_mux._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_mux._device_info is LPC824
    assert jlink_test_mux._channel == 1

    """Default not given"""
    jlink_test_mux = JLinkAdapter("mux=ftdi")
    assert jlink_test_mux._parse_conn_string("device=lpc824;channel=1")
    assert jlink_test_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_mux._device_info is LPC824
    assert jlink_test_mux._channel == 1
    assert not jlink_test_mux._parse_conn_string("")
    assert jlink_test_mux._mux_func is KNOWN_MULTIPLEX_FUNCS['ftdi']
    assert jlink_test_mux._device_info is LPC824
    assert jlink_test_mux._channel == 1
