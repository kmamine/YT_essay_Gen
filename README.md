# YT Essay Gen

Automated pipeline that turns a topic into an opinionated video essay:
Wikipedia research -> stance/thesis -> scripted argument -> per-subsection
narration + images -> assembled section videos -> final captioned `.mp4`.

Full stage-by-stage design lives in [Spec.md](Spec.md); operating rules and
current status are in [CLAUDE.md](CLAUDE.md).

## Pipeline

```
research -> stance -> script -> tts + image_gen -> section_build -> final_merge
```

- **Research** — Wikipedia API.
- **Stance** — LLM commits to a thesis/angle (not a neutral summary).
- **Script** — LLM writes the full narration, structured into sections and
  subsections, keeping opinion (`claim`/`evidence`) separate from raw facts.
- **TTS** — Pocket TTS (Kyutai), local, CPU-only.
- **Image gen** — stock photo search first (Pexels + Pixabay, pooled
  candidates judged by an LLM), falling back to AI generation (Nano Banana
  -> Cloudflare Workers AI SDXL -> local FLUX.2-klein) only when no stock
  photo is a good match.
- **Section build / final merge** — ffmpeg assembles each subsection's image
  (Ken Burns pan/zoom) against its narration audio, concatenates sections,
  and burns in captions.

Publishing is manual — the pipeline stops at the final `.mp4`. Metrics
tracking and the insight feedback loop (stages 7-11 in the spec) are not
yet built.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
```

Copy the required secrets into a `.env` file in the project root:

```
GOOGLE_STUDIO_API_KEY=...
MISTRAL_API_KEY=...
LLM_MODEL=mistral-large-latest
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
# optional: GROQ_API_KEY, CEREBRAS_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
```

Pipeline parameters (tiers, aspect ratio, captions, Ken Burns, etc.) live in
`config.yaml`.

## Usage

```bash
pipeline new <slug> --topic "..."
pipeline run <slug>
pipeline resume <slug>
pipeline status <slug>
pipeline list
```

## Testing

TDD is the norm in this repo — a failing test precedes every behavior
change.

```bash
pytest
```
