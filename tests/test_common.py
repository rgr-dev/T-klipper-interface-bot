from interfaces.telegram_bot.handlers.common import parse_count

DEFAULT = 5
MAX_COUNT = 20


def test_parse_count_defaults_when_no_args():
    assert parse_count([], DEFAULT, MAX_COUNT) == DEFAULT


def test_parse_count_uses_first_arg():
    assert parse_count(["10"], DEFAULT, MAX_COUNT) == 10


def test_parse_count_ignores_garbage():
    assert parse_count(["no-es-un-numero"], DEFAULT, MAX_COUNT) == DEFAULT


def test_parse_count_is_capped_at_max():
    assert parse_count(["9999"], DEFAULT, MAX_COUNT) == MAX_COUNT


def test_parse_count_has_a_floor_of_one():
    assert parse_count(["-5"], DEFAULT, MAX_COUNT) == 1
