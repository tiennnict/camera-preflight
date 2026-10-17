import pytest

from camera_preflight import i18n
from camera_preflight.domain import Message
from camera_preflight.messages import MESSAGES


@pytest.fixture(autouse=True)
def _restore():
    yield
    i18n.set_language("en")


def test_every_message_is_translated_to_vietnamese():
    i18n.set_language("vi")
    for code, text in MESSAGES.items():
        assert i18n._(text), code
    assert i18n.render(Message(code="level.pass")) == "Đạt"


def test_english_is_source_text():
    i18n.set_language("en")
    assert i18n.render(Message(code="level.fail")) == "Fail"


def test_unknown_language_falls_back_to_detected():
    assert i18n.set_language("xx") in i18n.SUPPORTED


def test_params_are_formatted():
    from camera_preflight import messages

    messages.register({"test.param": i18n.N_("Value {v}")})
    try:
        assert i18n.render(Message(code="test.param", params={"v": 3})) == "Value 3"
    finally:
        del MESSAGES["test.param"]
