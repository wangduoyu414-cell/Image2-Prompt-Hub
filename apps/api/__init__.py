"""Public, read-only HTTP projection of active Content Core publications."""

from .main import app, create_app

__all__ = ["app", "create_app"]
