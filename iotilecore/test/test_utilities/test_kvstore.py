import pytest
import os
from iotile.core.utilities.kvstore_json import JSONKVStore
from iotile.core.utilities.kvstore_sqlite import SQLiteKVStore


@pytest.fixture(scope='function', params=['json', 'sqlite'])
def kvstore(request):
    if request.param == 'json':
        store = JSONKVStore('testkv_store.json', respect_venv=True)
    else:
        store = SQLiteKVStore('testkv_store.db', respect_venv=True)

    store.clear()
    return store

def test_json_kvstore(kvstore):
    """Test functionality of a kvstore
    """

    with pytest.raises(KeyError):
        kvstore.get('a')

    assert kvstore.try_get('a') is None

    kvstore.set('a', 'value')

    assert kvstore.get('a') == 'value'
    assert len(kvstore.get_all()) == 1

    kvstore.clear()
    assert len(kvstore.get_all()) == 0

    kvstore.set('config:a', 'value2')

    assert kvstore.get('config:a') == 'value2'
