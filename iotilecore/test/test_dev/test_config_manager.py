import pytest
from iotile.core.exceptions import ArgumentError
from iotile.core.dev.config import ConfigManager


def test_format_default():
    """Test formatting of config variable defaults
    """

    man = ConfigManager()
    man.add_variable('test:var', 'bool', 'test variable', 'false')
    desc = man.describe('test:var')

    assert desc == 'test:var (bool): test variable [default: false]'


def test_format_nodefault():
    """Test formatting of config variable without a default value
    """

    man = ConfigManager()
    man.add_variable('test:var', 'bool', 'test variable')
    desc = man.describe('test:var')

    assert desc == 'test:var (bool): test variable [no default]'


def test_list_vars():
    """Test listing variables using a glob
    """

    man = ConfigManager()
    man.add_variable('test:var', 'bool', 'test variable', 'false')
    man.add_variable('test:var2', 'bool', 'test variable', 'false')
    man.add_variable('test2:var', 'bool', 'test variable', 'false')
    man.add_variable('test:hello', 'string', 'test variable', 'false')

    # Note that other plugins may register config vars here
    assert len(man.list("*")) >= 4
    assert len(man.list('test:*')) == 3
    assert len(man.list('test:var*')) == 2
    assert len(man.list('test:hello')) == 1


def test_getting_and_setting():
    """Test setting and getting variables with correct types
    """

    man = ConfigManager()
    man.add_variable('test:var', 'bool', 'test variable', 'false')

    val = man.get('test:var')
    assert val is False

    man.set('test:var', 'true')
    assert man.get('test:var') is True

    # Make sure we can get and set without a default value
    man.add_variable('test:var2', 'bool', 'test variable')

    with pytest.raises(ArgumentError):
        man.get('test:var2')

    man.set('test:var2', 'True')
    assert man.get('test:var2') is True
    man.set('test:var2', 'False')
    assert man.get('test:var2') is False

    # Make sure removing a variable works
    man.remove('test:var2')
    with pytest.raises(ArgumentError):
        man.get('test:var2')

    man.remove('test:var')
    assert man.get('test:var') is False


def test_setting_config_function():
    """Test adding a config function to ConfigManager
    """

    man = ConfigManager()

    def conf_function(self, arg1):
        if arg1 == 5:
            raise ArgumentError("test")

        return arg1

    with pytest.raises(AttributeError):
        man.test_conf(5)

    man.add_function('test_conf', conf_function)

    with pytest.raises(ArgumentError):
        man.test_conf(5)

    assert man.test_conf(3) == 3
