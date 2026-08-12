---
title: Klon Pad Rhyme Checker
emoji: 📜
colorFrom: red
colorTo: yellow
sdk: streamlit
sdk_version: 1.44.0
app_file: app.py
pinned: false
license: apache-2.0
---

# ผังกลอน — Klon Pad Rhyme Checker

Structural analysis for กลอนสี่ (Klon-4) and กลอนแปด (Klon-8): syllable
count, rhythm, and สัมผัส (rhyme) verification using the project's
`core.KhaveeVerifier`. Pronunciation lookup prioritizes the curated
`POETRY_OVERRIDES` dictionary and falls back to the PyThaiNLP engines.

This folder is a **self-contained Hugging Face Space** mirroring
`../ui/app.py`. Everything the app imports at runtime lives here, so the
folder can be pushed to Hugging Face as its own repository without the rest
of the research repository.

## What is in this Space

| File / folder              | Purpose                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| `app.py`                   | Streamlit entry point (identical to `ui/app.py`).                    |
| `checker.py`               | Analysis service (copy of `ui/checker.py`).                          |
| `core.py`                  | Vendored `KhaveeVerifier` (copy from repository root).               |
| `poetry_overrides.py`      | Curated pronunciation dictionary (copy from repository root).        |
| `live_preview_bridge/`     | Static Streamlit custom component for the rhyme-route diagram.       |
| `assets/fonts/`            | Decorative `SOV_sannoga2467` font (optional; graceful fallback).     |
| `requirements.txt`         | Runtime-only dependencies: `streamlit` + `pythainlp`.                |

`pandas`, `tqdm` and `ssg` are used only by build tooling/notebooks in the
parent repository and are intentionally omitted to keep the free-tier build
small and fast.

## Deploy to Hugging Face (free version)

### Option A — web UI (no local git)

1. Go to <https://huggingface.co/new-space>.
2. **Space name**: e.g. `klon-pad-rhyme-checker`.
3. **License**: Apache-2.0 (or your choice).
4. **SDK**: Streamlit.
5. **Hardware**: leave the default **CPU basic · 2 vCPU · 16 GB · Free** —
   the app is CPU-only, so the free tier is sufficient and costs nothing.
6. Create the Space, then upload these files in the **Files** tab:
   `app.py`, `checker.py`, `core.py`, `poetry_overrides.py`,
   `requirements.txt`, the `live_preview_bridge/` folder, the `assets/`
   folder, and (optionally) `.streamlit/config.toml`.
7. The Space builds automatically; open the **App** tab when it goes live.

### Option B — git push

```bash
# install the hub CLI if you haven't already
pip install -U "huggingface_hub[cli]"
huggingface-cli login

# create the Space (free hardware, Streamlit SDK)
huggingface-cli repo create klon-pad-rhyme-checker \
  --type space --space_sdk streamlit

# push this folder
cd huggingface_space
git init
git add .
git commit -m "Klon Pad Rhyme Checker on HF Spaces"
git remote add origin https://huggingface.co/spaces/<your-username>/klon-pad-rhyme-checker
git push --force origin main
```

> The README YAML frontmatter above already sets `sdk: streamlit`,
> `app_file: app.py` and a compatible `sdk_version`. No `Dockerfile` or
> `packages.txt` is needed — there are no system-level dependencies.

## Run locally (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes for the free tier

- **Hardware**: `CPU basic` is the default free hardware. Do not select a
  GPU — the app does not use one and paid hardware would be wasted.
- **Sleep**: free Spaces pause after ~48 hours of inactivity; they restart
  on the next visit (a cold start takes ~30–60 s).
- **RAM/CPU limits**: pythainlp's `newmm` tokenizer and the poem checker are
  lightweight, comfortably within the 16 GB free limit.
- **Licensed font**: `assets/fonts/SOV_sannoga2467.ttf` is only embedded
  client-side for the decorative title; the app still renders correctly
  without it via system fonts.
