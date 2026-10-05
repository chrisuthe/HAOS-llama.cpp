# llama.cpp app for Home Assistant OS — spec

Status: draft, v0.1.2 implemented. Research behind each decision is in
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
| `preload` | list of `str` | a generated `--models-preset` (below) | nothing preloaded |
| `thinking` | `bool` | `--reasoning off` when false | defaults to false |
| `context_size` | `int(0,)?` | `--ctx-size` | size from the model |
| `gpu_layers` | `auto`, `all`, or a number | `--n-gpu-layers` | `auto` |
| `threads` | `int(1,)?` | `--threads` | llama.cpp decides |
| `parallel` | `int(1,)?` | `--parallel` | defaults to 2 |
| `api_key` | `password?` | `LLAMA_API_KEY` | no authentication |
| `hf_token` | `password?` | `HF_TOKEN` | anonymous downloads |
| `extra_args` | `str?` | appended verbatim, shell-split | nothing |

Every option but `preload` and `thinking` is optional, and `preload` defaults
to an empty list. An unset option falls to llama.cpp's own default, so the app
does not carry a second set of defaults that can drift from upstream.
`parallel` and `thinking` are the exceptions.

`thinking` defaults to off, which passes `--reasoning off`. A reasoning model
otherwise thinks before every answer, and for the voice requests this app
mostly serves that is most of the wait. On passes nothing, leaving llama.cpp to
follow the model's chat template rather than forcing reasoning on a model
without it.

`config.yaml` defaults `parallel` to 2, where llama.cpp's automatic choice is 4
slots. The default lives in `config.yaml` rather than the launcher, so it shows
on the configuration screen. Because the Supervisor fills a missing option from
that default, getting llama.cpp's automatic choice back takes `--parallel -1`
in `extra_args`.

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

### Preloading

In router mode a model loads on the first request that names it. `preload`
lists models to load at startup instead. The launcher writes
`/data/preload.ini`, a router preset with one section per name carrying
`load-on-startup = true`, and passes it as `--models-preset`. A section whose
name matches a model from the models directory or the cache only adds that
setting to it.

Names are checked against the models directory first, because a section naming
no model is not an error to llama.cpp: it is listed as a model that never
finishes loading. A name shaped like a Hugging Face reference is passed
through, since the cache cannot be checked from the launcher.

`preload` is ignored, with a log line, when `model` is set: single-model mode
loads its model at startup already, and presets belong to the router.

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

`/usr/lib/llama-app/healthcheck.py` replaces the upstream `curl -f /health`. It
reports unhealthy only when the server is up but not answering:

| `GET /health` | Meaning | Verdict |
|---|---|---|
| 200 | serving | healthy |
| 503 | a model is still loading | healthy |
| connection refused | still downloading or starting | healthy |
| timeout, any other status or error | hung or broken | unhealthy |

A refused connection can count as healthy because the launcher `exec`s
`llama-server`: if the server dies, the container exits, which the Supervisor
handles on its own.

The upstream check cannot be kept. The Supervisor restarts an unhealthy app when
the user turns its Watchdog on, and upstream's check fails for as long as a
model downloads, so it would restart the app mid-download every time. A
`watchdog` URL in `config.yaml` has the same flaw and is not set.

Because the first check passes at once, the app shows as started while a model
is still downloading; the log is where progress shows.

In router mode `/health` is the router's own, so one hung model instance is not
detected.
The Supervisor still restarts the app if the process exits.

### Build and release

`.github/workflows/build.yml` runs on every push and pull request: workflow,
shell and app-manifest linting, then the unit tests and the smoke test on native
`amd64` and `aarch64` runners.

On `main` it also publishes. The publish job reads `version` from
`config.yaml` and, if `ghcr.io/chrisuthe/haos-llama-cpp:<version>` does not
exist yet, builds both architectures and pushes that tag and `latest`. A version
is therefore published exactly once, and a version bump on `main` is the
release; there are no git tags. The Dockerfile has no `RUN` step, so both
architectures build on one runner without emulation.

`config.yaml` names that image, so the Supervisor pulls it rather than building
on the device.

### Tracking llama.cpp

`.github/workflows/update-llama.yml` runs daily. `scripts/update_llama.py` asks
GitHub for upstream's latest full release — not the `bNNNNN` prereleases, which
appear several times a day — and, if the Dockerfile pins something else and the
release's `server-vulkan` image is complete for both architectures, repins the
`FROM` line by index digest, bumps the app's patch version, and adds a changelog
entry. The workflow then runs the tests against the result, commits to `main` as
the Actions bot, and starts Build, which publishes the new version.

There is no pull request in between. The app's version is its own and only says
"newer"; the changelog says which llama.cpp each one carries.

## Verified, and not

Verified locally with podman on Fedora, amd64 (`scripts/smoke_test.sh` and
`tests/`):

- the image builds, and the launcher starts the server in single-model and
  router mode
- chat completions work in both modes; an API key is enforced and does not
  appear in the log
- a bad `model` stops the container with exit 1 and an explanation
- the health check passes in both modes, including with an API key set, and
  its verdict table holds against local test servers
- during a Hugging Face download the server refuses connections, and the
  check, run through podman, reports healthy throughout
- Vulkan offload works through the image with `/dev/dri` passed in (Radeon
  780M, RADV)

Verified in CI, on native `amd64` and `aarch64` runners under docker: the unit
tests and the same smoke test, and the published image carrying both
architectures.

Verified on one Home Assistant OS install (2026-10-04, version 0.1.0):

- the store lists the app from the repository URL, and the Supervisor accepts
  `config.yaml` and pulls the published image
- the web UI works through ingress, including choosing and chatting with a
  model in router mode
- router mode starts with an empty models directory, and after a restart
  serves a model copied into `/share/llama_cpp/models`
- Home Assistant's `llama.cpp` integration works against this server
- updating an installed 0.1.0 to 0.1.1 keeps its options, and `preload` loads
  the named model at startup

Not verified:

- `video: true` is enough for Vulkan on Home Assistant OS, on Intel, AMD, and
  Raspberry Pi GPUs. Whether that install used a GPU was not recorded
- Home Assistant OS on `aarch64`
- a Hugging Face download on Home Assistant OS

## Known gaps

- **Ingress rule.** The app documentation asks that an ingress app accept
  connections only from `172.30.32.2`. With one port for both UI and API, that
  holds only when the host port is unmapped. Splitting them needs a proxy in the
  container.
- **API key and ingress.** With `api_key` set, the web UI asks for the key; it
  is not injected.
- **No AppArmor profile**, so the security rating is the default plus ingress.
- **A version can be visible before its image.** The store reads `version`
  from `main` as soon as it is pushed; the image follows a few minutes later,
  and not at all if the tests fail on `main`. An update attempted in that
  window fails to pull. The daily update tests on `amd64` before it commits, so
  only an `aarch64`-only failure can strand a version.

## Next

1. Work through the rest of the "not verified" list on Home Assistant OS.
2. Close the version-before-image window, by testing both architectures
   before the update commits or by publishing before the version lands.
3. AppArmor profile.
