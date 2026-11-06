import pytest

import model_runner as mr


def test_resolve_model_dir_local(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    assert mr._resolve_model_dir(str(d)) == str(d)
    assert mr._resolve_model_dir("file://" + str(d)) == str(d)


def test_resolve_model_dir_missing():
    with pytest.raises(RuntimeError):
        mr._resolve_model_dir("/no/such/model/dir")


def test_valid_output():
    obj = mr.validate('{"intent":"weather_query","date":null,"time":null,"place":"london"}')
    assert obj is not None and obj["place"] == "london"


def test_wrong_number_of_keys():
    assert mr.validate('{"intent":"weather_query","date":null,"time":null}') is None


def test_bad_intent():
    assert mr.validate('{"intent":"foo","date":null,"time":null,"place":null}') is None


def test_non_string_slot():
    assert mr.validate('{"intent":"weather_query","date":5,"time":null,"place":null}') is None


def test_broken_json():
    assert mr.validate("not json at all") is None


def test_extract_json_from_noise():
    assert mr.extract_json('garbage {"intent":"x"} trailing') == '{"intent":"x"}'
    assert mr.extract_json('nested {"a":{"b":1}} end') == '{"a":{"b":1}}'
