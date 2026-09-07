"""Local Windows/Unix file locks. Scope: one checkout on one computer, not a cluster."""
from contextlib import contextmanager
from pathlib import Path
import threading
import time
import os

_threads = {'budget': threading.RLock(), 'server': threading.RLock()}
_server_handle = None

def _file(name):
    folder = Path(__file__).resolve().parents[1] / 'instance'
    folder.mkdir(parents=True, exist_ok=True)
    handle = (folder / f'classroom-{name}.lock').open('a+b')
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b'0'); handle.flush()
    handle.seek(0)
    return handle

def _lock(handle):
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

def _unlock(handle):
    handle.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

@contextmanager
def budget_file_lock():
    with _threads['budget']:
        handle = _file('budget')
        until = time.monotonic() + 5
        try:
            while True:
                try:
                    _lock(handle); break
                except OSError:
                    if time.monotonic() >= until:
                        raise ValueError('预算账本忙，本次未发起云请求') from None
                    time.sleep(.01)
            try:
                yield
            finally:
                _unlock(handle)
        finally:
            handle.close()

def claim_server():
    global _server_handle
    with _threads['server']:
        if _server_handle is not None:
            return
        handle = _file('server')
        try:
            _lock(handle)
        except OSError:
            handle.close()
            raise ValueError('已有新版课堂后端运行；本期仅支持单进程，请勿同时启动多个后端或WSGI workers') from None
        _server_handle = handle  # OS releases the lock when this process exits.
