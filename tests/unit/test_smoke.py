"""Smoke tests for the project skeleton."""


def test_package_version_is_defined() -> None:
    """Ensure package metadata is wired and importable."""
    from educonnect_engine import __version__

    assert __version__ == "0.1.0"
