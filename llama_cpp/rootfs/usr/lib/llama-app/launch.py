#!/usr/bin/env python3
"""Translate the app's Home Assistant options into a llama-server command line."""

import json
import os
import re
import shlex
import sys
from pathlib import Path

OPTIONS_FILE = Path("/data/options.json")
STORAGE_DIR = Path("/share/llama_cpp")
SERVER = "/app/llama-server"
# Passed explicitly: upstream has announced that its default port will change,
# and config.yaml maps and proxies this one.
PORT = 8080

HF_REF = re.compile(r"^[^/\s:]+/[^/\s:]+(:[^/\s:]+)?$")

# Option name -> llama-server flag, for options that pass straight through.
PASSTHROUGH = {
    "context_size": "--ctx-size",
    "gpu_layers": "--n-gpu-layers",
    "threads": "--threads",
    "parallel": "--parallel",
}


class ConfigError(Exception):
    """An option value the server cannot be started with."""


def _is_set(value):
    return value is not None and value != ""


def model_args(model, models_dir):
    """Pick the flag for `model`: a GGUF file, a Hugging Face reference, or none."""
    if not _is_set(model):
        # No model means router mode: serve whatever is in the directory and
        # the download cache, loading each on demand.
        return ["--models-dir", str(models_dir)]

    root = models_dir.resolve()
    candidate = (models_dir / model).resolve()
    if model.endswith(".gguf") or candidate.is_file():
        if root not in candidate.parents:
            raise ConfigError(f"model {model!r} is outside {models_dir}")
        if not candidate.is_file():
            raise ConfigError(f"model file {candidate} does not exist")
        return ["--model", str(candidate)]

    if HF_REF.match(model):
        return ["--hf-repo", model]

    raise ConfigError(
        f"model {model!r} is neither a .gguf file in {models_dir} nor a "
        "Hugging Face reference like user/repo:Q4_K_M"
    )


def build_argv(options, models_dir):
    argv = [SERVER, "--host", "0.0.0.0", "--port", str(PORT)]
    argv += model_args(options.get("model"), models_dir)
    for name, flag in PASSTHROUGH.items():
        if _is_set(options.get(name)):
            argv += [flag, str(options[name])]
    # Last, so that an extra argument overrides anything set above.
    if _is_set(options.get("extra_args")):
        try:
            argv += shlex.split(options["extra_args"])
        except ValueError as err:
            raise ConfigError(f"extra_args cannot be parsed: {err}") from err
    return argv


def build_env(options, environ, cache_dir):
    env = dict(environ)
    env["LLAMA_CACHE"] = str(cache_dir)
    # Secrets go through the environment so they stay out of the logged
    # command line and out of the process list.
    if _is_set(options.get("api_key")):
        env["LLAMA_API_KEY"] = options["api_key"]
    if _is_set(options.get("hf_token")):
        env["HF_TOKEN"] = options["hf_token"]
    return env


def main():
    models_dir = STORAGE_DIR / "models"
    cache_dir = STORAGE_DIR / "cache"
    try:
        options = json.loads(OPTIONS_FILE.read_text())
        models_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        argv = build_argv(options, models_dir)
    except (OSError, ValueError, ConfigError) as err:
        print(f"llama-app: {err}", file=sys.stderr, flush=True)
        return 1
    print(f"llama-app: starting {shlex.join(argv)}", flush=True)
    os.execve(SERVER, argv, build_env(options, os.environ, cache_dir))


if __name__ == "__main__":
    sys.exit(main())
