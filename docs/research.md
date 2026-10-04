# Research notes

Gathered 2026-10-04. Each item says where it came from, because several of
these facts are recent and will move.

## Home Assistant apps

Source: developers.home-assistant.io/docs/apps (configuration, presentation,
repository pages), and the Supervisor source for device policy.

- "Add-ons" are now called **apps**. The file formats did not change.
- Supported architectures are `amd64` and `aarch64` only.
- `build.yaml` is no longer read. `BUILD_FROM` is no longer passed as of
  Supervisor 2026.04.0, so a Dockerfile must name its base in `FROM`.
  `BUILD_VERSION` and `BUILD_ARCH` are still passed.
- With no `image` key in `config.yaml`, the Supervisor builds the Dockerfile on
  the device, with the app directory as the build context.
- A repository is a directory per app plus a root `repository.yaml` (`name`
  required; `url`, `maintainer` optional).
- Ingress: `ingress: true`, `ingress_port`, `ingress_stream` for streaming. The
  proxy strips its prefix and sends it in `X-Ingress-Path`. An ingress app is
  asked to accept connections only from `172.30.32.2`.
- Security rating starts at 5; `ingress: true` adds 2 and a custom
  `apparmor.txt` adds 1.
- `video: true` adds cgroup device rules for majors 29 (framebuffer), 81
  (video4linux) and 226 (DRM) — `supervisor/hardware/policy.py`. Major 226 is
  `/dev/dri/*`, the render nodes Vulkan opens.
- Health, from `supervisor/apps/app.py`: an app whose image has a health check
  stays in "startup" until Docker reports healthy or unhealthy, and the
  Supervisor waits up to 120 seconds for that. With the app's Watchdog on, the
  Supervisor restarts it when the container is unhealthy, failed or stopped.
- Schema types used here: `str`, `int(min,)`, `match(regex)`, `password`, with
  `?` for optional.

## llama.cpp

Source: the `server-vulkan-v0.5.0` image itself (`--help`, `--version`,
`--list-devices`, and a running server), plus `.devops/*.Dockerfile` and
`tools/server/README.md` upstream.

- Releases: `v0.5.0` (2026-09-23) is the latest non-prerelease; `bNNNNN` builds
  are published several times a day as prereleases. Images exist for both
  schemes, e.g. `server-v0.5.0`, `server-vulkan-v0.5.0`, `server-b11382`.
- `server` and `server-vulkan` are published for `linux/amd64` and
  `linux/arm64`. ROCm, MUSA, Intel SYCL and OpenVINO are amd64 only.
- `server-vulkan-v0.5.0`: index digest
  `sha256:be586c648cb79d2cd75d0c38a6541e1f16c47a7c6621d3e711470a467fc38744`,
  876 MB, Ubuntu 26.04, entrypoint `/app/llama-server`,
  `LLAMA_ARG_HOST=0.0.0.0`, reports `0.5.0-dev (build 11146)`. It has bash, curl
  and Python 3.14, and no jq.
- The Vulkan image is built with `GGML_BACKEND_DL=ON` and
  `GGML_CPU_ALL_VARIANTS=ON`: it ships every CPU backend variant alongside
  `libggml-vulkan.so`.
- With no GPU passed in, `--list-devices` prints `(none)` — the software
  rasteriser is not offered as a device, so the `auto` default cannot land on
  it. With `/dev/dri` passed in it lists the real GPU.
- Defaults in this version: `--ctx-size 0` (from the model), `--n-gpu-layers
  auto`, `--threads -1`, `--parallel -1` (auto), `--jinja` on, web UI on, port
  8080.
- The server logs that its default port will change to 9931 in a future release
  (llama.cpp PR 26508).
- **Router mode**: started without a model, the server offers every model in
  the cache (`LLAMA_CACHE`), in `--models-dir`, and in a `--models-preset` INI,
  and loads each on demand, up to `--models-max` (4) at once. Arguments and
  environment are inherited by each model instance. A model added to the cache
  needs a restart to be seen.
- `--api-key` also reads `LLAMA_API_KEY`; `--hf-token` reads `HF_TOKEN`.
- `/health` answers 200 once a model is loaded (and at once in router mode).
- The web UI is a SvelteKit static build with `paths.relative: true` and a hash
  router. `index.html` loads its bundle from `./_app/...` and computes its base
  from `location`. In the bundle, chat and `props` calls are `./`-relative; the
  model list, load and unload endpoints are written `/v1/models`,
  `/models/load`, `/models/unload`.
- The UI is only served to clients that accept gzip.

## Prior art

- `crysty0612/homeassistant-llamacpp-addon` — an existing add-on wrapping
  llama-server. Builds its own Vulkan and SYCL variants, has a separate
  management UI on a second port, per-model option lists, speculative decoding
  options, and uses `video: true` with a `/dev/dri/renderD128` path option. It
  is a much larger surface than this app aims for.
- Home Assistant's `llama.cpp` integration (2026.8) — connects to any
  OpenAI-compatible server, e.g. `http://localhost:8080/v1`, API key optional.
  Its documentation names no companion app and no discovery.
- `acon96/home-llm` and `skye-harris/hass_local_openai_llm` — custom
  integrations for the same job, also clients of a llama.cpp server.
