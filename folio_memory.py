"""Conservative Linux RAM-session checks; not a secure-erasure guarantee."""
import ctypes
import gc
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path


def harden_process():
    """Disable process core dumps / ordinary same-user ptrace before plan entry."""
    if platform.system() != 'Linux':
        return False
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE = 4
            return False
        return libc.prctl(3, 0, 0, 0, 0) == 0  # PR_GET_DUMPABLE = 3
    except (OSError, ValueError, AttributeError):
        return False


def process_hardened():
    try:
        import resource
        return resource.getrlimit(resource.RLIMIT_CORE) == (0, 0) and ctypes.CDLL(None).prctl(3, 0, 0, 0, 0) == 0
    except (ImportError, OSError, ValueError, AttributeError):
        return False


def mount_for(path):
    try:
        result = subprocess.run(['findmnt', '--json', '--target', str(path), '--output', 'FSTYPE,OPTIONS'],
                                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=4)
        if result.returncode:
            return None
        items = json.loads(result.stdout)['filesystems']
        return items[0] if len(items) == 1 else None
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


def ram_backed(path, mount_reader=mount_for, depth=0):
    if depth > 3:
        return False
    mount = mount_reader(path)
    if not isinstance(mount, dict):
        return False
    if mount.get('fstype') in ('tmpfs', 'ramfs'):
        return True
    if mount.get('fstype') == 'overlay':
        options = dict(part.split('=', 1) for part in mount.get('options', '').split(',') if '=' in part)
        upper = options.get('upperdir')
        # No writable upper layer or inaccessible mount topology => fail closed.
        if upper and os.path.isabs(upper):
            return ram_backed(upper, mount_reader, depth + 1)
    return False


def memory_report(*, test_only_skip_path_check=False):
    if platform.system() != 'Linux':
        return {'safe': False, 'detail': 'RAM-only mode requires a nonpersistent live Linux session.'}
    try:
        rows = Path('/proc/swaps').read_text().splitlines()
        if not rows or not rows[0].startswith('Filename') or any(line.strip() for line in rows[1:]):
            return {'safe': False, 'detail': 'Swap is active or cannot be verified disabled.'}
        if not process_hardened():
            return {'safe': False, 'detail': 'Process dump protection is unavailable.'}
        # Check common OS/app scratch locations as well as the writable root layer.
        paths = ['/', str(Path.home()), tempfile.gettempdir(), '/var/tmp', '/var/log']
        for name in ('XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_RUNTIME_DIR'):
            if os.environ.get(name):
                paths.append(os.environ[name])
        if test_only_skip_path_check:
            return {'safe': True, 'path_check_skipped': True,
                    'detail': 'TEST MODE ONLY: RAM-backed path check skipped; do not enter real plan data.'}
        if not all(ram_backed(path) for path in paths):
            return {'safe': False, 'detail': 'Writable system/home/temp paths are not verifiably RAM-backed. Boot nonpersistent live Linux.'}
        return {'safe': True, 'detail': 'RAM-backed system paths, no active swap, process dumps disabled (OS-reported).'}
    except (OSError, ValueError):
        return {'safe': False, 'detail': 'RAM-session checks unavailable.'}


def discard_plan(plan):
    """Drop references, not secure overwrite: immutable strings may remain in RAM."""
    if isinstance(plan, dict):
        for value in list(plan.values()):
            discard_plan(value)
        plan.clear()
    elif isinstance(plan, list):
        for value in plan:
            discard_plan(value)
        plan.clear()
    gc.collect()
