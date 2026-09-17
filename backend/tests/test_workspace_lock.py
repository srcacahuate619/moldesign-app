import subprocess
import sys
from pathlib import Path

import pytest

from utils.procesos import BANDERAS_SIN_VENTANA
from utils.workspace_lock import WorkspaceLock


def test_workspace_lock_excludes_second_owner_and_releases(tmp_path):
    with WorkspaceLock(tmp_path):
        with pytest.raises(RuntimeError, match="otro backend"):
            with WorkspaceLock(tmp_path):
                pass
        with WorkspaceLock(tmp_path / "independent"):
            pass
    with WorkspaceLock(tmp_path):
        pass


def test_workspace_lock_is_released_after_abrupt_process_exit(tmp_path):
    backend = str(Path(__file__).resolve().parents[1])
    script = ("import sys,time; sys.path.insert(0,sys.argv[1]); "
              "from utils.workspace_lock import WorkspaceLock; "
              "lock=WorkspaceLock(sys.argv[2]); lock.__enter__(); "
              "print('locked',flush=True); time.sleep(30)")
    process = subprocess.Popen([sys.executable, "-c", script, backend, str(tmp_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, creationflags=BANDERAS_SIN_VENTANA)
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(RuntimeError, match="otro backend"):
            with WorkspaceLock(tmp_path):
                pass
    finally:
        process.kill()
        process.communicate(timeout=10)
    with WorkspaceLock(tmp_path):
        pass
