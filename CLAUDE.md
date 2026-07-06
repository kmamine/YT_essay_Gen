# CLAUDE.md

Project context for working in this repository. See SPEC.md for the full
technical spec — this file is operating instructions, not a duplicate of it.

## What this project is
An automated video essay pipeline: Wikipedia research -> opinionated script
generation -> per-subsection TTS + image generation -> section video assembly
-> final merge. See SPEC.md for stage-by-stage detail and the JSON schema
used to represent scripts.

## Working rules
- **Do not write or modify code unless explicitly asked to in the current
  message.** Planning, architecture discussion, and doc updates are fine by
  default; implementation is not, unless requested.
- Don't reach for frontend/UI tooling or scaffolding unless the task actually
  calls for a UI. This is a backend/CLI batch pipeline by default.
- Keep the opinion layer (`thesis`, `claim`, `evidence`) separate from raw
  Wikipedia facts in any data model — factual grounding and rhetorical
  framing should be checkable independently.
- Treat free-tier API rate limits as unconfirmed until checked live (e.g.
  Nano Banana quota via Google AI Studio) — don't hardcode numbers from blog
  posts as fact.

## Key components
- **Research**: Wikipedia API (needs descriptive User-Agent header).
- **Script/stance LLM**: Mistral free tier (primary), Groq/Cerebras
  (alt, higher throughput). Google/Gemini is scoped to image gen only, not
  used for text/LLM calls.
- **Image gen**: Pexels + Pixabay stock photo search (primary, free,
  LLM-judged relevance), fallback chain Nano Banana (Gemini 2.5 Flash
  Image — confirmed zero free-tier quota) -> Cloudflare Workers AI (SDXL)
  -> local FLUX.2-klein-4B-GGUF (last resort).
- **TTS**: Pocket TTS (Kyutai), local CPU, no rate limit.
- **Assembly**: ffmpeg, local, CPU-bound — expect this to be the slowest
  step on low-power hardware (target dev machine: i5-U, no GPU).
- **Publish**: manual — you upload to YouTube yourself. The pipeline
  produces the final .mp4 and stops there; it does not call the upload API.
- **Metrics**: YouTube Analytics API (views/retention/CTR — separate
  product from Data API, own-channel only) + YouTube Data API for
  comments/comment metrics. At 1-2 uploads/week, quota (10,000 units/day)
  is not a real constraint even with frequent polling.
- **Insights & feedback loop**: LLM extracts structured insights from
  metrics + comments per video, persisted in an insight store, queried
  before future stance/script generation as advisory (not authoritative)
  context.

## Conventions
- Language/runtime: Python (src-layout package `essaygen` under `src/`).
- Config: `.env` for secrets (`python-dotenv`/`pydantic-settings`),
  `config.yaml` for pipeline parameters (`PyYAML`/pydantic).
- CLI: Typer (`pipeline new/run/resume/status/publish/list`).
- Data models: pydantic throughout (`src/essaygen/models/`).
- TDD is the norm in this repo: write a failing test first, then the
  minimal implementation, for every behavior change.

## Current status
Core pipeline (research -> stance -> script -> tts -> image_gen ->
section_build -> final_merge) is implemented and unit-tested, with a live
end-to-end run verified (real Wikipedia, Mistral, Pocket TTS, ffmpeg;
placeholder images pending a working image-gen tier). Stages 7-11
(publish tracking, insight store, feedback loop) are not yet built.