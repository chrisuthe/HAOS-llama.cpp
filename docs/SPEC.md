# llama.cpp app for Home Assistant OS — spec

Status: draft, v0.1.0 implemented locally. Research behind each decision is in
[research.md](research.md).

## Goal

A Home Assistant app (formerly "add-on") that runs a llama.cpp server on the
Home Assistant OS machine itself, so that a local language model is available to
Home Assistant and to the LAN without a second computer.

The app is a thin package around upstream `llama-server`. It adds nothing to
llama.cpp; it makes it installable, configurable from the app's configuration
screen, and reachable.

## Non-goals

- No Home Assistant integration. Home Assistant 2026.8 ships a `llama.cpp`
  integration that talks to any OpenAI-compatible server; this app is the server
  for it.
- No model management UI of our own. Models arrive by Hugging Face reference or
  by copying a file into `/share`.
- No fork or patch of llama.cpp, and no build of it from source. The upstream
  image is the base.
- No NVIDIA (CUDA), ROCm, or Intel SYCL variants. Home Assistant OS ships no
  NVIDIA driver, and the others would each need their own image.

## What the user gets

1. Install the app, optionally set **Model**, start it.
2. **Open Web UI** shows the llama.cpp chat UI inside Home Assistant (ingress).
3. `http://<home-assistant>:8080/v1` is an OpenAI-compatible API, which is what
   the `llama.cpp` integration is pointed at.

## Design

### Image

`FROM ghcr.io/ggml-org/llama.cpp:server-vulkan-v0.5.0`, pinned by multi-arch
index digest, plus one file: the launcher. The Vulkan image is used for every
install because it also carries the CPU backends and falls back to them when no
GPU is visible, so one image covers both cases on `amd64` and `aarch64`.

The launcher is Python, standard library only, because the base image already
ships Python 3.14 and has no `jq`. Nothing is installed on top of upstream.

No s6-overlay and no bashio: there is one process. The launcher `exec`s
`llama-server`, with Docker's own init (`init: true`, the default) as PID 1.

### Launcher

`/usr/lib/llama-app/launch.py` reads `/data/options.json`, builds the
`llama-server` command line, and `exec`s it. It fails with exit 1 and a one-line
message when an option cannot be turned into a valid command.

| Option | Schema | Maps to | Unset means |
|---|---|---|---|
| `model` | `str?` | `--hf-repo`, `--model`, or `--models-dir` (below) | router mode |
| `context_size` | `int(0,)?` | `--ctx-size` | size from the model |
| `gpu_layers` | `auto`, `all`, or a number | `--n-gpu-layers` | `auto` |
| `threads` | `int(1,)?` | `--threads` | llama.cpp decides |
| `parallel` | `int(1,)?` | `--parallel` | llama.cpp decides |
| `api_key` | `password?` | `LLAMA_API_KEY` | no authentication |
| `hf_token` | `password?` | `HF_TOKEN` | anonymous downloads |
| `extra_args` | `str?` | appended verbatim, shell-split | nothing |

Every option is optional and defaults to llama.cpp's own default, so the app
does not carry a second set of defaults that can drift from upstream.
`extra_args` goes last so it can override anything, and is the escape hatch for
the several hundred flags this app does not surface.

Secrets go through the environment rather than the command line, which keeps
them out of the logged command and out of the process list.

`--host 0.0.0.0 --port 8080` are always passed. The port is explicit because
upstream has announced its default will move to 9931.

### Model selection

`model` decides the mode:

- **empty** — router mode: `--models-dir /share/llama_cpp/models`. Every model
  in that directory and in the download cache is offered, and each is loaded on
  the first request that names it.
- **a `.gguf` name**, or anything that is a file under the models directory —
  `--model <path>`. The path must resolve inside the models directory.
- **`user/repo` or `user/repo:quant`** — `--hf-repo`. llama.cpp downloads it
  into the cache on first start.
- anything else is rejected at start.

### Storage

Everything lives under `/share/llama_cpp`:

- `models/` — files the user copies in.
- `cache/` — Hugging Face downloads (`LLAMA_CACHE`).

`/share` rather than `/data` so that models can be copied in over Samba, and so
that the app's own backup does not grow by the size of every model. The cost is
that a full backup, which includes `/share`, does.

### Network

One port, 8080, serves both the API and the web UI.

- **Ingress** proxies the web UI into Home Assistant (`ingress_stream: true`,
  since completions are server-sent events).
- **Host port 8080** exposes the API to Home Assistant Core and to the LAN. The
  user can unmap it in the app's Network settings.

### GPU

`video: true` gives the container the DRM devices under `/dev/dri`, which is
what Vulkan needs. With no GPU visible, llama.cpp lists no devices and runs on
the CPU; no option has to change.

### Health

The upstream `HEALTHCHECK` on `/health` is removed. In single-model mode nothing
listens while a model downloads, and the Supervisor tracks a container's health
state, so a long download would read as an unhealthy app. No `watchdog` URL is
set, for the same reason. How the Supervisor acts on that state was read from
its source, not observed.
The Supervisor still restarts the app if the process exits.

## Verified, and not

Verified locally with podman on Fedora, amd64 (`scripts/smoke_test.sh` and
`tests/`):

- the image builds, and the launcher starts the server in single-model and
  router mode
- chat completions work in both modes; an API key is enforced and does not
  appear in the log
- a bad `model` stops the container with exit 1 and an explanation
- Vulkan offload works through the image with `/dev/dri` passed in (Radeon
  780M, RADV)

Not verified — these need a real Home Assistant OS install:

- the Supervisor accepts `config.yaml` and builds the Dockerfile on the device
- the web UI behind ingress. Its assets and most API calls are relative, but
  the model list and load calls are root-absolute strings in the bundle and
  depend on the UI prefixing its computed base path
- `video: true` is enough for Vulkan on Home Assistant OS, on Intel, AMD, and
  Raspberry Pi GPUs
- anything on `aarch64`

## Known gaps

- **Ingress rule.** The app documentation asks that an ingress app accept
  connections only from `172.30.32.2`. With one port for both UI and API, that
  holds only when the host port is unmapped. Splitting them needs a proxy in the
  container.
- **API key and ingress.** With `api_key` set, the web UI asks for the key; it
  is not injected.
- **No AppArmor profile**, so the security rating is the default plus ingress.
- **No hung-server detection**, since there is no health check.
- **No icon or logo.**
- **No published image.** `config.yaml` has no `image` key, so the Supervisor
  builds on the device. That means an ~880 MB base pull on install and no CI.

## Next

1. Install on a Home Assistant OS box as a local app and work through the
   "not verified" list.
2. Add CI that builds and publishes both architectures, and set `image:`.
3. AppArmor profile, icon and logo.
4. A health check that tolerates a download in progress.
