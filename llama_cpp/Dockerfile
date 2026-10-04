# Pinned by multi-arch index digest, so that amd64 and aarch64 both resolve from
# the one pin; the tag beside it is ignored by the engine and is there for the
# reader. The Vulkan build is used for every install: it carries the CPU
# backends too and falls back to them when no GPU is visible, which saves
# shipping two variants.
#
# The Supervisor no longer passes BUILD_FROM, so the base is named here.
# scripts/update_llama.py rewrites this line; keep it in this exact shape.
FROM ghcr.io/ggml-org/llama.cpp:server-vulkan-v0.5.0@sha256:be586c648cb79d2cd75d0c38a6541e1f16c47a7c6621d3e711470a467fc38744

LABEL \
    org.opencontainers.image.title="llama.cpp Home Assistant app" \
    org.opencontainers.image.description="llama.cpp server packaged as a Home Assistant app" \
    org.opencontainers.image.source="https://github.com/chrisuthe/HAOS-llama.cpp" \
    org.opencontainers.image.licenses="MIT"

COPY rootfs/ /

# Replaces the upstream `curl -f /health`, which fails for as long as a model is
# downloading or loading. With the app's Watchdog on, the Supervisor restarts an
# unhealthy app, so that check would restart it mid-download, every time.
HEALTHCHECK --interval=30s --timeout=15s --retries=3 \
    CMD ["/usr/bin/python3", "/usr/lib/llama-app/healthcheck.py"]

# The launcher and health check need only the Python the base image ships.
ENTRYPOINT ["/usr/bin/python3", "/usr/lib/llama-app/launch.py"]
