# llama.cpp app for Home Assistant

A Home Assistant app (formerly "add-on") that runs a
[llama.cpp](https://github.com/ggml-org/llama.cpp) server on the Home Assistant
OS machine: a chat web UI inside Home Assistant, and an OpenAI-compatible API
for Home Assistant's llama.cpp integration.

It is a thin package around the upstream `llama-server` image. See
[docs/SPEC.md](docs/SPEC.md) for the design and what is still unverified, and
[llama_cpp/DOCS.md](llama_cpp/DOCS.md) for the user documentation.

Experimental: not yet run on real Home Assistant OS hardware.

## Install as a local app

There is no published image yet, so Home Assistant builds the app on the device.

1. Copy the `llama_cpp` directory to `/addons/llama_cpp` on the Home Assistant
   machine (the `addons` share of the Samba app).
2. In **Settings → Apps → App store**, choose **Check for updates** from the
   menu. The app appears under **Local apps**.
3. Install it. The first install pulls a base image of about 880 MB.

## Layout

- `llama_cpp/` — the app: `config.yaml`, `Dockerfile`, and the launcher under
  `rootfs/`.
- `tests/` — unit tests for the launcher.
- `scripts/smoke_test.sh` — builds the image and runs it as the Supervisor
  would.

## Test

```sh
python3 -m unittest discover -s tests
./scripts/smoke_test.sh
```

The smoke test needs podman or docker, and network access for the base image
and a 1 MB test model.

## Updating llama.cpp

Change the tag and digest in `llama_cpp/Dockerfile`, bump `version` in
`llama_cpp/config.yaml`, and add a `CHANGELOG.md` entry. The digest is the
multi-arch index digest:

```sh
skopeo inspect --raw docker://ghcr.io/ggml-org/llama.cpp:server-vulkan-<tag> | sha256sum
```

## Licence

MIT — see [LICENSE](LICENSE). llama.cpp itself is also MIT licensed.
