import pytest
import threading

@pytest.fixture(scope='function', autouse=True)
def logging_fixture():
    # Runs before all tests
    yield
    for thread in threading.enumerate():
        print(thread)
    # Runs after all tests
    # Enumerate running threads here