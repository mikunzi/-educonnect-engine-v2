"""Unit tests for shared Result type."""

import pytest

from educonnect_engine.shared.result import Result


def test_result_ok_branch() -> None:
    result: Result[int, str] = Result.ok(42)

    assert result.is_ok is True
    assert result.is_err is False
    assert result.value == 42
    with pytest.raises(ValueError, match="result does not contain an error"):
        _ = result.error


def test_result_err_branch() -> None:
    result: Result[int, str] = Result.err("boom")

    assert result.is_ok is False
    assert result.is_err is True
    assert result.error == "boom"
    with pytest.raises(ValueError, match="result does not contain a value"):
        _ = result.value


def test_result_rejects_invalid_state_none_none() -> None:
    with pytest.raises(ValueError, match="result must contain either value or error"):
        Result[int, str]()


def test_result_rejects_invalid_state_both_set() -> None:
    with pytest.raises(ValueError, match="result must contain either value or error"):
        Result[int, str](_value=1, _error="x")
