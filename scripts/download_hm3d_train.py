#!/usr/bin/env python3
"""Download the three official HM3D v0.2 train archives on the server."""
import argparse
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "runtime/data_imports/hm3d_train_v0.2"
BASE = "https://api.matterport.com/resources/habitat/"
ARCHIVES = (
    "hm3d-train-semantic-configs-v0.2.tar",
    "hm3d-train-habitat-v0.2.tar",
    "hm3d-train-semantic-annots-v0.2.tar",
)


def curl_user_config(token, secret):
    for value in (token, secret):
        if not value or any(not 33 <= ord(char) <= 126 for char in value):
            raise ValueError("Enter the API token fields without whitespace.")
    if ":" in token:
        raise ValueError("The API token ID cannot contain a colon.")
    escaped = (token + ":" + secret).replace("\\", "\\\\").replace('"', '\\"')
    return ('user = "' + escaped + '"\n').encode("ascii")


def archive_info(path):
    with tarfile.open(path, mode="r:") as archive:
        members = 0
        for member in archive:
            if member.isfile():
                members += 1
        if not members:
            raise ValueError("Archive has no regular files.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest(), "files": members}


def download(name, credentials):
    output = ROOT / name
    if output.is_file():
        return archive_info(output)
    # A failed attempt has a separate staging file. Never append a login page
    # or replace a previously verified archive.
    partial = ROOT / (name + ".part")
    resume = []
    if partial.is_file():
        with partial.open("rb") as handle:
            prefix = handle.read(512)
        if prefix[257:263] in (b"ustar\0", b"ustar "):
            resume = ["--continue-at", "-"]
    command = [
        "curl", "--disable", "--config", "-", "--fail", "--location", "--silent", "--show-error",
        "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "15",
        "--retry", "2", "--retry-delay", "2", "--speed-time", "60", "--speed-limit", "1024",
        "--output", str(partial), "--write-out", "%{http_code}\t%{content_type}",
        *resume, BASE + name,
    ]
    response = subprocess.run(command, input=credentials, capture_output=True, check=False)
    status, _, content_type = response.stdout.decode("ascii", errors="replace").partition("\t")
    if response.returncode or content_type.lower().startswith("text/html"):
        raise RuntimeError(f"{name}: HTTP {status or 'unknown'}, curl exit {response.returncode}. "
                           "Check the HM3D token or server network and retry.")
    try:
        checked = archive_info(partial)
    except (tarfile.TarError, ValueError) as error:
        raise RuntimeError(f"{name}: the response is not a valid tar archive.") from error
    partial.rename(output)
    print(f"Verified {name} ({checked['bytes']:,} bytes, {checked['files']:,} files)", flush=True)
    return checked


def download_batch(credentials, first):
    files = {ARCHIVES[0]: first}
    for name in ARCHIVES[1:]:
        print(f"Downloading {name}", flush=True)
        files[name] = download(name, credentials)
    manifest = ROOT / "archives.json"
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"source": BASE, "files": files}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    print(f"All archives verified. Manifest: {manifest}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foreground", action="store_true", help="Keep the download attached to this terminal.")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Run this in an interactive SSH terminal, using ssh -t.")
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "download.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another HM3D download is running. Check download.log.\n")
        if (ROOT / "archives.json").is_file():
            print(f"The download is already verified: {ROOT / 'archives.json'}")
            return
        try:
            credentials = curl_user_config(
                getpass.getpass("Matterport API Token ID (hidden): "),
                getpass.getpass("Matterport API Token Secret (hidden): "),
            )
            first = download(ARCHIVES[0], credentials)
        except (ValueError, OSError, RuntimeError) as error:
            parser.exit(1, str(error) + "\n")
        if args.foreground:
            download_batch(credentials, first)
            return
        if os.fork():
            print(f"Server download started. Progress: {ROOT / 'download.log'}", flush=True)
            return
        os.setsid()
        with open(os.devnull, "rb") as source, (ROOT / "download.log").open("ab", buffering=0) as output:
            os.dup2(source.fileno(), 0)
            os.dup2(output.fileno(), 1)
            os.dup2(output.fileno(), 2)
            try:
                download_batch(credentials, first)
            except (OSError, RuntimeError, ValueError) as error:
                print(str(error), file=sys.stderr, flush=True)
                os._exit(1)
        os._exit(0)


if __name__ == "__main__":
    main()
