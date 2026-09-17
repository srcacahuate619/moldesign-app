"""Una sola instancia del backend puede reconciliar/escribir el mismo almacén."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile


class WorkspaceLock:
    def __init__(self, workspace):
        identity = os.path.normcase(str(Path(workspace).resolve()))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        self.path = Path(tempfile.gettempdir()) / "moldesign-workspace-locks" / f"{digest}.lock"
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if self.path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RuntimeError("El almacén de MolDesign está en uso por otro backend; cierre esa instancia antes de abrir otra.") from exc
        self.file = handle
        return self

    def __exit__(self, *args):
        if self.file is not None:
            try:
                self.file.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            finally:
                self.file.close()
                self.file = None
        # No unlink: otro proceso podría abrir un inode distinto del bloqueado.
