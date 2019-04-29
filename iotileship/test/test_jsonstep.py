import json
import pytest
from iotile.ship.actions.ModifyJsonStep import ModifyJsonStep

class mock_resource:
    def __init__(self, root):
        self.root = root

class test_harness:
    def __init__(self, path):
        self.resources = {'filesystem': mock_resource(path)}
        self.tested_json = path / "tested.json"
        self.expected_json = path / "expected.json"


    def init_data(self, original, expected):
        with open(str(self.tested_json), "w") as file:
            json.dump(original, file, indent=2)

        with open(str(self.expected_json), "w") as file:
            json.dump(expected, file, indent=2)


    def execute_test(self, args):
        step = ModifyJsonStep(args)
        step.run(self.resources)


    def check_success(self, expected):
        with open(str(self.tested_json), "r") as file:
            result = json.load(file)
            assert result == expected

        with open(str(self.tested_json), "r") as file:
            result_str = file.read()

        with open(str(self.expected_json), "r") as file:
            expected_str = file.read()

        assert result_str == expected_str


def test_str(tmp_path):
    harness = test_harness(tmp_path)
    data = {'iotile-id': '42', 'key2' : 'value2'}
    args = {'key': ['iotile-id'],
            'value': 'NEWVAL',
            'path': harness.tested_json}
    expected = {'iotile-id': 'NEWVAL', 'key2' : 'value2'}

    harness.init_data(data, expected)
    harness.execute_test(args)
    harness.check_success(expected)


def test_str_missing(tmp_path):
    harness = test_harness(tmp_path)
    data = {'iotile-id': '42', 'key2' : 'value2'}
    args = {'key': ['NEW'],
            'value': 'NEWVAL',
            'path': harness.tested_json}
    expected = {'iotile-id': '42', 'key2' : 'value2', 'NEW': 'NEWVAL'}

    # Make sure it fails without 'create' flag
    harness.init_data(data, expected)
    with pytest.raises(KeyError):
        harness.execute_test(args)

    # Make sure it works with 'create' flag
    args['create_if_missing'] = True
    harness.execute_test(args)
    harness.check_success(expected)


def test_two_deep(tmp_path):
    harness = test_harness(tmp_path)
    data = {'layer1': {'layer2': {'iotile-id': '42'}}, 'key2' : 'value2'}
    args = {'key': ['layer1', 'layer2', 'iotile-id'],
            'value': 'NEWVAL',
            'path': harness.tested_json}
    expected = {'layer1': {'layer2': {'iotile-id': 'NEWVAL'}}, 'key2' : 'value2'}

    harness.init_data(data, expected)
    harness.execute_test(args)
    harness.check_success(expected)
