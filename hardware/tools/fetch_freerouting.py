#!/usr/bin/env python3
"""Obtain the Freerouting 2.5.0 release jar the board design method routes with, and verify it.

The jar is fetched over HTTPS from the project's own release page into the path given, kept only when its
sha256 matches the one recorded here for that release, and left alone when it is already there and matches.
A file that does not match is removed and the command exits 1; an unreachable address exits 2.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.error
import urllib.request

URL = "https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar"
SHA256 = "f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7"


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def obtain(dest: str, url: str = URL, expected: str = SHA256) -> str:
    """Return "present" when dest already matches, "fetched" after a verified download.

    Raises ValueError, with dest removed, when the downloaded file does not match, and OSError when the
    address cannot be read.
    """
    if os.path.isfile(dest) and sha256_of(dest) == expected:
        return "present"
    folder = os.path.dirname(os.path.abspath(dest))
    os.makedirs(folder, exist_ok=True)
    handle, partial = tempfile.mkstemp(dir=folder, suffix=".part")
    try:
        with os.fdopen(handle, "wb") as out, urllib.request.urlopen(url, timeout=120) as response:
            for block in iter(lambda: response.read(1 << 20), b""):
                out.write(block)
        found = sha256_of(partial)
        if found != expected:
            raise ValueError(f"{url} has sha256 {found}, expected {expected}; not kept")
        os.replace(partial, dest)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    return "fetched"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dest", help="where the jar is kept")
    parser.add_argument("--url", default=URL, help="address to fetch from (default: the v2.5.0 release asset)")
    parser.add_argument("--sha256", default=SHA256, help="expected sha256 (default: the release's)")
    args = parser.parse_args(argv)
    try:
        state = obtain(args.dest, args.url, args.sha256)
    except ValueError as error:
        print(f"CHECK FAILED: {error}", file=sys.stderr)
        return 1
    except (OSError, urllib.error.URLError) as error:
        print(f"CANNOT RUN: {error}", file=sys.stderr)
        return 2
    print(f"freerouting 2.5.0 {state}: {args.dest} sha256 {args.sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
