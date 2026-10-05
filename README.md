# llama.cpp app for Home Assistant OS

A Home Assistant app (formerly "add-on") that runs a
[llama.cpp](https://github.com/ggml-org/llama.cpp) server on the Home Assistant
OS machine: a chat web UI inside Home Assistant, and an OpenAI-compatible API
for Home Assistant's llama.cpp integration.

It is a thin package around the upstream `llama-server` image. See
[docs/SPEC.md](docs/SPEC.md) for the design and what is still unverified, and
[llama_cpp/DOCS.md](llama_cpp/DOCS.md) for the user documentation.

Experimental: it runs on Home Assistant OS, but GPU offload there is untested.

## Install

[![Add this repository to your Home Assistant instance.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fchrisuthe%2FHAOS-llama.cpp)

1. Use the button above. Or, in **Settings → Apps → App store**, open the menu,
   choose **Repositories**, and add
   `https://github.com/chrisuthe/HAOS-llama.cpp`.
2. Install **llama.cpp** from the store. The image is about 880 MB.

## Layout

- `llama_cpp/` — the app: `config.yaml`, `Dockerfile`, the store listing
  (`README.md`, `DOCS.md`, `icon.png`, `logo.png`), and the launcher under
  `rootfs/`.
- `tests/` — unit tests for the launcher.
- `scripts/smoke_test.sh` — builds the image and runs it as the Supervisor
  would.
- `scripts/update_llama.py` — moves the app to a newer llama.cpp release.
- `.github/workflows/` — tests, publishing, and the daily llama.cpp update.

## Test

```sh
python3 -m unittest discover -s tests
./scripts/smoke_test.sh
```

The smoke test needs podman or docker, and network access for the base image
and a 1 MB test model.

## Releases

Every push to `main` is tested on both architectures. If the `version` in
`llama_cpp/config.yaml` has no published image yet, CI builds and pushes
`ghcr.io/chrisuthe/haos-llama-cpp` for it, so a version bump on `main` is a
release.

## Updating llama.cpp

A daily workflow moves the app to upstream's latest full release: it repins the
base image, bumps the patch version, adds a changelog entry, runs the tests,
and commits to `main`, which publishes it. To do the same by hand (needs
skopeo):

```sh
python3 scripts/update_llama.py                      # latest release
LLAMA_CPP_TAG=v0.5.0 python3 scripts/update_llama.py  # a specific one
```

## Licence

MIT — see [LICENSE](LICENSE). llama.cpp itself is also MIT licensed.

`llama_cpp/icon.png` and `llama_cpp/logo.png` are llama.cpp's own artwork,
resized from `media/llama1-icon.png` and `media/llama1-logo.png` in its
repository, and are covered by its MIT licence: Copyright (c) 2023-2026 The
ggml authors.
