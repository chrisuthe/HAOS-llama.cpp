# llama.cpp

Runs a [llama.cpp](https://github.com/ggml-org/llama.cpp) server on this Home
Assistant system. It gives you a chat web UI inside Home Assistant and an
OpenAI-compatible API on port 8080.

## Getting a model

Models are GGUF files. There are two ways to provide one.

**Download from Hugging Face.** Set **Model** to a reference such as
`ggml-org/gemma-3-1b-it-GGUF:Q4_K_M` and start the app. The download happens on
the first start and is kept; watch the **Log** tab for progress. The web UI and
API are not available until it finishes.

**Copy a file in.** Put a `.gguf` file in `/share/llama_cpp/models` — the
`share` folder of the Samba or file editor apps — and set **Model** to its file
name.

Leave **Model** empty to offer every model in that folder, and every model
already downloaded. Each one is loaded the first time a request asks for it, and
the web UI shows a model picker. Restart the app after adding a model.

## Configuration

**Model**, **Preload**, **Parallel requests** and **Thinking** are shown; the rest are behind
"Show unused optional configuration options" and can be left unset.

| Option | Meaning |
|---|---|
| **Model** | A Hugging Face reference, a file name in `/share/llama_cpp/models`, or empty. |
| **Preload** | Models to load at startup when **Model** is empty. See below. |
| **Thinking** | Let reasoning models think before they answer. Off by default, for faster answers. |
| **Context size** | Prompt context in tokens. Unset or 0 takes the size from the model. |
| **GPU layers** | A number, `all`, or `auto`. Unset is `auto`. `0` stays on the CPU. |
| **CPU threads** | Threads used for generation. |
| **Parallel requests** | Requests served at once, each in its own slot. They share the context. Default 2. |
| **API key** | Require this key on every request. |
| **Hugging Face token** | For gated or private models. |
| **Extra arguments** | Any other `llama-server` arguments. They are applied last. |

## Keeping a model ready

A loaded model stays loaded. The wait is on the first request after the app
starts, while the model is read into memory.

- With **Model** set, that model is loaded as the app starts.
- With **Model** empty, models load on their first request. To load some at
  startup instead, list them under **Preload**, by the name the web UI shows or
  by file name. At most four models stay loaded at once.

A name under **Preload** that matches no model stops the app at start, with the
reason in the log.

## Using it from Home Assistant

Add the **llama.cpp** integration (Home Assistant 2026.8 or later) and give it
the URL `http://127.0.0.1:8080/v1`, plus the API key if you set one.

## Graphics cards

The app uses a GPU through Vulkan when Home Assistant OS exposes one, and the
CPU otherwise. Set **GPU layers** to `0` to force the CPU. NVIDIA cards are not
supported, because Home Assistant OS has no driver for them.

## Security

**Port 8080 is open to your network, and without an API key anyone who can
reach it can use the server.** Either set a key, or remove the port under
**Network** — the web UI inside Home Assistant keeps working, and the
integration then needs the app's internal hostname instead of `127.0.0.1`.

With an API key set, the web UI asks for it once, in its settings.

## Storage and backups

Models are kept in `/share/llama_cpp`, not in the app's own data, so they are
not part of this app's backup. A full backup includes `/share` and so includes
them.
