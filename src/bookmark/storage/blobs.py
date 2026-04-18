"""Content-addressed blob store for bookmark-cli.

Blobs are stored at:
    $BOOKMARK_HOME/blobs/<sha256[:2]>/<sha256[2:]>

The blob store is write-once and immutable — the same content always has the
same address. Compression (gzip) is applied by default and can be disabled
via config.

See design doc §10 for blob store design.
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path


class BlobStore:
    """Simple content-addressed blob store backed by the filesystem."""

    def __init__(self, home: Path, compress: bool = True) -> None:
        self.blobs_dir = home / "blobs"
        self.compress = compress
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key_to_path(self, key: str) -> Path:
        """Map a SHA-256 hex key to its filesystem path."""
        return self.blobs_dir / key[:2] / key[2:]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, data: str) -> str:
        """Write *data* (a UTF-8 string) to the blob store.

        Returns the SHA-256 hex digest (content address).
        Idempotent: writing the same content twice is a no-op.
        """
        raw = data.encode("utf-8")
        key = hashlib.sha256(raw).hexdigest()
        path = self._key_to_path(key)

        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            if self.compress:
                path.write_bytes(gzip.compress(raw, compresslevel=6))
            else:
                path.write_bytes(raw)

        return key

    def read(self, key: str) -> str | None:
        """Read a blob by its SHA-256 hex key.

        Returns None if the blob does not exist.
        """
        path = self._key_to_path(key)
        if not path.exists():
            return None
        raw = path.read_bytes()
        if self.compress:
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass  # already uncompressed (e.g. written without compression)
        return raw.decode("utf-8")

    def exists(self, key: str) -> bool:
        """Return True if a blob with *key* exists in the store."""
        return self._key_to_path(key).exists()
