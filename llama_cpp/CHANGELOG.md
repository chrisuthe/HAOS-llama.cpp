# Changelog

## 0.1.2

- Default to two parallel requests instead of llama.cpp's four. Set **Parallel
  requests** to change it.
- Add a Thinking option, off by default. Models that reason before answering
  now answer directly; turn it on to get the reasoning back.
- Add an icon and logo to the store listing.
- Stop the harmless `LLAMA_ARG_HOST` warning at every start.

## 0.1.1

- Add a Preload option, to load models at startup when no single model is set.

## 0.1.0

- First version, on llama.cpp v0.5.0.
