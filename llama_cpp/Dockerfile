# ghcr.io/ggml-org/llama.cpp:server-vulkan-v0.5.0, by multi-arch index digest so
# that amd64 and aarch64 both resolve from the one pin. The Vulkan build is used
# for every install: it carries the CPU backends too and falls back to them when
# no GPU is visible, which saves shipping two variants.
#
# The Supervisor no longer passes BUILD_FROM, so the base is named here. Bump
# the tag in this comment, the digest, and `version` in config.yaml together.
FROM ghcr.io/ggml-org/llama.cpp@sha256:be586c648cb79d2cd75d0c38a6541e1f16c47a7c6621d3e711470a467fc38744

LABEL \
    org.opencontainers.image.title="llama.cpp Home Assistant app" \
    org.opencontainers.image.description="llama.cpp server packaged as a Home Assistant app" \
    org.opencontainers.image.source="https://github.com/chrisuthe/HAOS-llama.cpp" \
    org.opencontainers.image.licenses="MIT"

COPY rootfs/ /

# Drop the upstream check on /health. Nothing listens while a model downloads,
# which can take longer than any start period worth setting, and the Supervisor
# tracks a container's health state and can restart an app that reports
# unhealthy.
HEALTHCHECK NONE

# The launcher needs only the Python the base image already ships.
ENTRYPOINT ["/usr/bin/python3", "/usr/lib/llama-app/launch.py"]
