"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_dec_path(fixtures_dir: Path) -> Path:
    """Return path to sample .dec file."""
    return fixtures_dir / "sample.dec"
