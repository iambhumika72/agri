"""
tests/conftest.py
==================
Shared pytest configuration and fixtures for the Agri platform test suite.

Sets asyncio mode to "auto" so every async test runs without needing
the @pytest.mark.asyncio decorator on each function.
"""

import pytest


def pytest_configure(config):
    """Register custom markers to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


# Tell pytest-asyncio to treat all async tests as asyncio tests automatically.
# This is equivalent to adding asyncio_mode = "auto" in pyproject.toml.
pytest_plugins = ("pytest_asyncio",)
