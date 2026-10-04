#!/usr/bin/env python3
"""Move the app to the latest llama.cpp release.

Rewrites the base image pin in the Dockerfile, bumps the app's patch version,
and adds a changelog entry. Does nothing when the pin is already current, or
when the release's image has not been published yet.

Needs skopeo. Set LLAMA_CPP_TAG to pin a specific release instead of the latest.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "llama_cpp/Dockerfile"
CONFIG = ROOT / "llama_cpp/config.yaml"
CHANGELOG = ROOT / "llama_cpp/CHANGELOG.md"

IMAGE = "ghcr.io/ggml-org/llama.cpp"
RELEASE_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
ARCHITECTURES = {"amd64", "arm64"}

FROM_LINE = re.compile(
    rf"^FROM {re.escape(IMAGE)}:server-vulkan-(?P<tag>\S+)@(?P<digest>sha256:[0-9a-f]{{64}})$",
    re.MULTILINE,
)
VERSION_LINE = re.compile(r'^version: "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)


def current_tag(dockerfile):
    match = FROM_LINE.search(dockerfile)
    if not match:
        raise SystemExit("no llama.cpp FROM line in the Dockerfile")
    return match["tag"]


def repin(dockerfile, tag, digest):
    return FROM_LINE.sub(f"FROM {IMAGE}:server-vulkan-{tag}@{digest}", dockerfile)


def bump_patch(config):
    match = VERSION_LINE.search(config)
    if not match:
        raise SystemExit("no version line in config.yaml")
    major, minor, patch = (int(part) for part in match.groups())
    version = f"{major}.{minor}.{patch + 1}"
    return VERSION_LINE.sub(f'version: "{version}"', config), version


def add_changelog_entry(changelog, version, tag):
    heading, _, rest = changelog.partition("\n## ")
    entry = f"## {version}\n\n- Update llama.cpp to {tag}.\n"
    return f"{heading}\n{entry}\n## {rest}" if rest else f"{heading}\n{entry}"


def latest_release_tag():
    request = urllib.request.Request(RELEASE_API)
    if os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["tag_name"]


def index_digest(tag):
    """Digest of the multi-arch index for `tag`, or None if it is not usable yet."""
    result = subprocess.run(
        ["skopeo", "inspect", "--raw", f"docker://{IMAGE}:server-vulkan-{tag}"],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    manifests = json.loads(result.stdout).get("manifests", [])
    published = {m.get("platform", {}).get("architecture") for m in manifests}
    # A release's architectures are pushed separately, so an index can be
    # visible before it is complete.
    if not ARCHITECTURES <= published:
        return None
    return "sha256:" + hashlib.sha256(result.stdout).hexdigest()


def set_output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as out:
            out.writelines(f"{key}={value}\n" for key, value in values.items())


def main():
    dockerfile = DOCKERFILE.read_text()
    old = current_tag(dockerfile)
    new = os.environ.get("LLAMA_CPP_TAG") or latest_release_tag()
    if new == old:
        print(f"already on llama.cpp {old}")
        set_output(changed="false")
        return 0

    digest = index_digest(new)
    if digest is None:
        print(f"llama.cpp {new} has no complete server-vulkan image yet")
        set_output(changed="false")
        return 0

    config, version = bump_patch(CONFIG.read_text())
    DOCKERFILE.write_text(repin(dockerfile, new, digest))
    CONFIG.write_text(config)
    CHANGELOG.write_text(add_changelog_entry(CHANGELOG.read_text(), version, new))
    print(f"llama.cpp {old} -> {new}, app version {version}")
    set_output(changed="true", tag=new, version=version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
