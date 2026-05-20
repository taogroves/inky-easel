#!/usr/bin/env python3
"""Flash an Inky Easel setup bundle to a USB-connected Inky Frame (no SD card).

Accepts a folder or ZIP from the portal setup wizard (same files as the SD bundle).
Writes the app and generated config to internal flash and resets the board.

Requires: pip install mpremote
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Files the portal includes (see webserver/api/app/routers/setup.py).
BUNDLE_NAMES = frozenset(
    {
        "main.py",
        "flash_loader_main.py",
        "inky_easel_app.py",
        "frame_client.py",
        "battery.py",
        "display.py",
        "inky_helper.py",
        "secrets.py",
        "frame_config.py",
        "README.txt",
    }
)

# Copied to internal flash for SD-less installs (flash_loader stays SD-only).
FLASH_APP_FILES = frozenset(BUNDLE_NAMES - {"flash_loader_main.py", "README.txt"})


def _require_mpremote() -> str:
    exe = shutil.which("mpremote")
    if exe is None:
        print(
            "mpremote not found. Install it with:\n"
            "  pip install mpremote\n"
            "Then reconnect the Inky Frame over USB.",
            file=sys.stderr,
        )
        sys.exit(1)
    return exe


def _run_mpremote(mpremote: str, args: list[str], *, device: str | None) -> None:
    cmd = [mpremote]
    if device:
        cmd.extend(["connect", device])
    cmd.extend(args)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e


def list_devices(mpremote: str) -> None:
    subprocess.run([mpremote, "connect", "list"], check=False)


def load_bundle(path: Path) -> dict[str, str]:
    """Return {filename: text} from a portal bundle directory or ZIP."""
    if path.is_dir():
        root = path
        cleanup = None
    elif path.is_file() and path.suffix.lower() == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="inky-easel-bundle-")
        cleanup = tmp
        with zipfile.ZipFile(path) as zf:
            zf.extractall(tmp.name)
        root = Path(tmp.name)
    else:
        print(f"Bundle path must be a directory or .zip file: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        files: dict[str, str] = {}
        for child in root.iterdir():
            if not child.is_file():
                continue
            name = child.name
            if name.startswith(".") or name not in BUNDLE_NAMES:
                continue
            files[name] = child.read_text(encoding="utf-8")
        return files
    finally:
        if cleanup is not None:
            cleanup.cleanup()


def validate_bundle(files: dict[str, str], *, flash_app: bool) -> list[str]:
    required = FLASH_APP_FILES if flash_app else BUNDLE_NAMES - {"README.txt"}
    missing = sorted(required - files.keys())
    if missing:
        print("Bundle is missing required files:", ", ".join(missing), file=sys.stderr)
        print(
            "Generate a bundle from the portal setup wizard "
            "(directory write or ZIP download).",
            file=sys.stderr,
        )
        sys.exit(1)
    return sorted(files.keys() if not flash_app else (FLASH_APP_FILES & files.keys()))


def flash_bundle(
    bundle_path: Path,
    *,
    device: str | None,
    dry_run: bool,
    reset: bool,
    sd_loader: bool,
) -> None:
    files = load_bundle(bundle_path)

    if sd_loader:
        if "flash_loader_main.py" not in files:
            print("Bundle missing flash_loader_main.py", file=sys.stderr)
            sys.exit(1)
        to_flash = [("flash_loader_main.py", "main.py")]
        print("Installing SD loader as internal-flash main.py (one-time).")
    else:
        names = validate_bundle(files, flash_app=True)
        to_flash = [(name, name) for name in names]
        print(f"Flashing {len(to_flash)} files to internal flash (no SD card).")

    with tempfile.TemporaryDirectory(prefix="inky-easel-flash-") as tmp:
        tmp_path = Path(tmp)
        local_paths: list[Path] = []
        remote_paths: list[str] = []
        for local_name, remote_name in to_flash:
            dest = tmp_path / local_name
            dest.write_text(files[local_name], encoding="utf-8")
            local_paths.append(dest)
            remote_paths.append(f":{remote_name}")

        if dry_run:
            for local, remote in zip(local_paths, remote_paths):
                print(f"  {local.name} -> {remote}")
            print("(dry run — not copying)")
            return

        mpremote = _require_mpremote()

        # mpremote cp file1 file2 ... :dest only works for same basename; copy one-by-one.
        for local, remote in zip(local_paths, remote_paths):
            print(f"  {local.name} -> {remote}")
            _run_mpremote(mpremote, ["cp", str(local), remote], device=device)

        if reset:
            print("Resetting board...")
            _run_mpremote(mpremote, ["reset"], device=device)

    print("Done. Unplug USB if you want the frame to run on battery/Wi-Fi only.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flash an Inky Easel portal setup bundle to a USB-connected Inky Frame.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Downloads/inky-easel-living-room.zip
  %(prog)s ./my-bundle-folder
  %(prog)s bundle.zip --device /dev/tty.usbmodem101
  %(prog)s --list-devices
  %(prog)s bundle.zip --install-sd-loader   # one-time SD workflow loader only

The portal ZIP or folder from the setup wizard already contains secrets.py and
frame_config.py. For no SD card, all app files plus main.py are written to
internal flash; the frame runs inky_easel_app from there.
""",
    )
    parser.add_argument(
        "bundle",
        nargs="?",
        type=Path,
        help="Portal setup bundle (directory or .zip)",
    )
    parser.add_argument(
        "--device",
        "-d",
        metavar="PATH",
        help='mpremote device (e.g. /dev/tty.usbmodem101). Default: auto-detect',
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List USB serial devices mpremote can see, then exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be copied without touching the Pico",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not reset the board after copying",
    )
    parser.add_argument(
        "--install-sd-loader",
        action="store_true",
        help="Copy flash_loader_main.py to internal flash as main.py (SD-card workflow)",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices(_require_mpremote())
        return

    if args.bundle is None:
        parser.error("bundle path is required unless --list-devices is used")

    if not args.bundle.exists():
        print(f"Bundle not found: {args.bundle}", file=sys.stderr)
        sys.exit(1)

    flash_bundle(
        args.bundle.expanduser().resolve(),
        device=args.device,
        dry_run=args.dry_run,
        reset=not args.no_reset,
        sd_loader=args.install_sd_loader,
    )


if __name__ == "__main__":
    main()
