"""SD-card firmware updater for Inky Easel frames."""

import gc
import os
import time

try:
    import socket
except ImportError:
    socket = None

try:
    import uhashlib as hashlib
except ImportError:
    import hashlib

try:
    from urllib import urequest as _urequest
except ImportError:
    import urequest as _urequest


HTTP_TIMEOUT_SECONDS = 30
SD_ROOT = "/sd"
BACKUP_ROOT = "/sd/_firmware_backups"


def _set_timeout():
    if socket and hasattr(socket, "setdefaulttimeout"):
        socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)


def _mkdir(path):
    try:
        os.mkdir(path)
    except OSError:
        pass


def _hex_digest(digest):
    try:
        return digest.hex()
    except AttributeError:
        return "".join("{:02x}".format(b) for b in digest)


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            h.update(chunk)
    return _hex_digest(h.digest())


def _download(url, dest):
    _set_timeout()
    sock = _urequest.urlopen(url)
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = sock.read(1024)
                if not chunk:
                    break
                f.write(chunk)
    finally:
        sock.close()
        gc.collect()


def _backup_existing(files, version):
    stamp = str(int(time.time()))
    root = BACKUP_ROOT + "/" + (version or "unknown") + "-" + stamp
    _mkdir(BACKUP_ROOT)
    _mkdir(root)
    for entry in files:
        path = entry.get("path")
        if not path or "/" in path:
            continue
        src = SD_ROOT + "/" + path
        dst = root + "/" + path
        try:
            os.stat(src)
        except OSError:
            continue
        try:
            with open(src, "rb") as inf:
                outf = open(dst, "wb")
                try:
                    while True:
                        chunk = inf.read(1024)
                        if not chunk:
                            break
                        outf.write(chunk)
                finally:
                    outf.close()
        except Exception as e:
            print("Backup failed for", path, e)
            raise
    return root


def apply_update(update, current_version=None):
    if not update:
        return False
    files = update.get("files") or []
    version = update.get("version") or "unknown"
    print("Firmware update available:", version)

    pending = []
    for entry in files:
        path = entry.get("path")
        url = entry.get("url")
        expected = entry.get("sha256")
        if not path or "/" in path or not url or not expected:
            raise RuntimeError("Bad firmware manifest")
        dest = SD_ROOT + "/" + path + ".new"
        print("Downloading firmware", path)
        try:
            os.remove(dest)
        except OSError:
            pass
        _download(url, dest)
        actual = _sha256_file(dest)
        if actual != expected:
            raise RuntimeError("Checksum mismatch for {}".format(path))
        pending.append((path, dest))

    backup_dir = _backup_existing(files, current_version)
    print("Backed up old firmware to", backup_dir)

    for path, pending_path in pending:
        final_path = SD_ROOT + "/" + path
        try:
            os.remove(final_path)
        except OSError:
            pass
        os.rename(pending_path, final_path)

    print("Firmware update installed:", version)
    return True
