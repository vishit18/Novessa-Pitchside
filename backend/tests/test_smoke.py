"""Placeholder so CI has something to run until the engine lands."""

import backend
import engine


def test_packages_import() -> None:
    assert backend.__name__ == "backend"
    assert engine.__name__ == "engine"
