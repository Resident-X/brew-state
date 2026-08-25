#!/usr/bin/env python3
"""Fetch what the emulation tier needs and cannot carry in the tree.

Two things arrive here: the emulator the tier runs the artefact under, and the
register description its peripheral models are checked against. Neither is
committed. The emulator is a two-hundred-megabyte platform-specific build; the
register description is ST's, redistributed under terms this repository does not
hold. What makes both reproducible is not that they sit in the tree but that
they are named by digest: a fetch that produces different bytes fails here
rather than being noticed later as a difference in a result.

Everything lands under .tooling/, which the repository ignores, so the working
tree after provisioning is the working tree before it.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pins.json")


def repository_root():
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def tooling_root():
    return os.path.join(repository_root(), ".tooling")


def platform_key():
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in ("arm64", "aarch64"):
        return "darwin-arm64"
    if system == "linux" and machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    if system == "linux" and machine in ("aarch64", "arm64"):
        return "linux-aarch64"
    raise SystemExit(
        "no pinned emulator build for %s/%s -- add one to %s once its digest is known"
        % (system, machine, PINS))


def digest_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, destination, expected_sha256):
    """Download `url` to `destination` unless it is already the expected bytes."""
    if os.path.exists(destination) and digest_of(destination) == expected_sha256:
        return False
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    handle, staging = tempfile.mkstemp(dir=os.path.dirname(destination))
    os.close(handle)
    try:
        with urllib.request.urlopen(url) as response, open(staging, "wb") as out:
            shutil.copyfileobj(response, out)
        actual = digest_of(staging)
        if actual != expected_sha256:
            raise SystemExit(
                "%s does not carry the pinned bytes:\n  expected %s\n  received %s"
                % (url, expected_sha256, actual))
        os.replace(staging, destination)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)
    return True


def extract_dmg(image, destination):
    mounted = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-mountrandom", tempfile.gettempdir(), image],
        check=True, capture_output=True, text=True)
    point = mounted.stdout.strip().splitlines()[-1].split("\t")[-1].strip()
    try:
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(point, destination, symlinks=True)
    finally:
        subprocess.run(["hdiutil", "detach", point], check=False, capture_output=True)


def extract_tarball(archive, destination):
    shutil.rmtree(destination, ignore_errors=True)
    os.makedirs(destination, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(destination)


def find_emulator(root):
    """The emulator's own launcher, wherever this platform's build puts it."""
    candidates = []
    for directory, _, files in os.walk(root):
        for name in files:
            if name == "renode":
                candidates.append(os.path.join(directory, name))
    if not candidates:
        raise SystemExit("no `renode` launcher under %s" % root)
    return sorted(candidates, key=len)[0]


def provision(pins, quiet=False):
    def say(message):
        if not quiet:
            print(message)

    tooling = tooling_root()
    key = platform_key()
    build = pins["renode"]["platforms"][key]
    version = pins["renode"]["version"]

    downloads = os.path.join(tooling, "downloads")
    archive = os.path.join(downloads, os.path.basename(build["url"]))
    tree = os.path.join(tooling, "renode-%s-%s" % (version, key))
    marker = os.path.join(tree, ".provisioned")

    fetched = fetch(build["url"], archive, build["sha256"])
    if fetched or not os.path.exists(marker):
        say("extracting %s" % os.path.basename(archive))
        if build["format"] == "dmg":
            extract_dmg(archive, tree)
        else:
            extract_tarball(archive, tree)
        with open(marker, "w") as handle:
            handle.write(build["sha256"] + "\n")
    emulator = find_emulator(tree)
    os.chmod(emulator, os.stat(emulator).st_mode | 0o111)
    say("emulator: %s" % emulator)

    svd = pins["svd"]
    svd_path = os.path.join(tooling, "svd", "%s.svd" % svd["device"])
    licence_path = os.path.join(tooling, "svd", "%s.licence.html" % svd["device"])
    fetch(svd["url"], svd_path, svd["sha256"])
    fetch(svd["licence_url"], licence_path, svd["licence_sha256"])
    say("register description: %s (licence beside it in %s)" % (svd_path, os.path.basename(licence_path)))

    return {"emulator": emulator, "svd": svd_path, "svd_licence": licence_path}


def load_pins():
    with open(PINS, encoding="utf-8") as handle:
        return json.load(handle)


def ensure(quiet=True):
    """What the runner calls: provision if needed, and say where things are."""
    return provision(load_pins(), quiet=quiet)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args(argv)
    provision(load_pins(), quiet=arguments.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
