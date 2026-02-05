"""StorageBackend protocol and MemoryBackend.

Storage backends persist session state, audit logs, and budget data.
The MemoryBackend is a simple in-memory implementation for development
and testing.
"""

from __future__ import annotations

from typing import Any, Protocol


class StorageBackend(Protocol):
    """Protocol for persistent storage of governance data."""

    def get(self, key: str) -> Any | None:
        """Retrieve a value by key."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Store a value by key."""
        ...

    def delete(self, key: str) -> None:
        """Delete a value by key."""
        ...

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with the given prefix."""
        ...


class MemoryBackend:
    """In-memory storage backend for development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]
