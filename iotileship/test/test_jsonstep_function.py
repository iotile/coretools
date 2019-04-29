import pytest
from iotile.ship.actions.ModifyJsonStep import modify_dict

def test_str():
    data = {'iotile-id': '42', 'key2' : 'value2'}
    key = ['iotile-id']
    value = 'NEWVAL'
    expected = {'iotile-id': value, 'key2' : 'value2'}

    result = modify_dict(data, key, value)
    assert result == expected

    # Try to modify key that doesn't exist
    key = 'MISSING'
    with pytest.raises(KeyError):
        result = modify_dict(data, key, value)

    # Make sure we're not changing the original
    assert data == {'iotile-id': '42', 'key2' : 'value2'}


def test_str_missing():
    data = {'iotile-id': '42', 'key2' : 'value2',}
    key = ['NEW']
    value = 'NEWVAL'
    expected = {'iotile-id': '42', 'key2' : 'value2', 'NEW': 'NEWVAL'}

    with pytest.raises(KeyError):
        result = modify_dict(data, key, value)

    result = modify_dict(data, key, value, create_if_missing=True)
    assert result == expected


def test_one_deep():
    data = {'layer1': {'iotile-id': '42'}, 'key2' : 'value2'}
    key = ['layer1', 'iotile-id']
    value = 'NEWVAL'
    expected = {'layer1': {'iotile-id': value}, 'key2' : 'value2'}

    result = modify_dict(data, key, value)
    assert result == expected

    # Make sure we're not changing the original
    assert data == {'layer1': {'iotile-id': '42'}, 'key2' : 'value2'}


def test_one_deep_missing():
    data = {'layer1': {'iotile-id': '42'}, 'key2' : 'value2'}
    key = ['layer1', 'NEW']
    value = 'NEWVAL'
    expected = {'layer1': {'iotile-id': '42', 'NEW': 'NEWVAL'}, 'key2' : 'value2'}

    with pytest.raises(KeyError):
        result = modify_dict(data, key, value)

    result = modify_dict(data, key, value, create_if_missing=True)
    assert result == expected


def test_one_deep_missing_modify_first_layer():
    data = {'layer1': {'iotile-id': '42'}, 'key2' : 'value2'}
    key = ['NEW']
    value = 'NEWVAL'
    expected = {'layer1': {'iotile-id': '42'}, 'key2' : 'value2', 'NEW': 'NEWVAL'}

    with pytest.raises(KeyError):
        result = modify_dict(data, key, value)

    result = modify_dict(data, key, value, create_if_missing=True)
    assert result == expected


def test_two_deep():
    data = {'layer1': {'layer2': {'iotile-id': '42'}}, 'key2' : 'value2'}
    key = ['layer1', 'layer2', 'iotile-id']
    value = 'NEWVAL'
    expected = {'layer1': {'layer2': {'iotile-id': value}}, 'key2' : 'value2'}

    result = modify_dict(data, key, value)
    assert result == expected


def test_two_deep_change_middle():
    data = {'layer1': {'iotile-id': '42', 'layer2': {'key_l2' : 'val_l2'}}, 'key2' : 'value2'}
    key = ['layer1', 'iotile-id']
    value = 'NEWVAL'
    expected = {'layer1': {'iotile-id': value, 'layer2': {'key_l2' : 'val_l2'}}, 'key2' : 'value2'}

    result = modify_dict(data, key, value)
    assert result == expected


def test_keychain_includes_a_not_dict():
    data = {'layer1': {'layer2': {'iotile-id': '42'}}, 'key2' : 'NOTADICT'}
    key = ['key2', 'layer2', 'iotile-id']
    value = 'NEWVAL'

    with pytest.raises(ValueError):
        result = modify_dict(data, key, value) # pylint: disable=unused-variable
