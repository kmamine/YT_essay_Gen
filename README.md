# YT Essay Gen

**Give it a topic. Get back an opinionated, narrated, captioned video essay.**

YT Essay Gen is a batch pipeline that researches a topic on Wikipedia, picks
a thesis, writes a scripted argument, generates narration and matching
visuals for every subsection, and assembles it all into a finished `.mp4` —
no manual editing required.

Full stage-by-stage design lives in [Spec.md](Spec.md); operating rules and
current build status are in [CLAUDE.md](CLAUDE.md).

## How it works

```mermaid
flowchart TD
    A["Topic string"] --> B["Research\n(Wikipedia API)"]
    B --> C["Stance\nLLM picks a thesis / angle"]
    C --> D["Script\nLLM writes full narration,\nsections -> subsections"]
    D --> E["Per-subsection generation"]

    subgraph E["Per-subsection generation (parallel)"]
        direction LR
        E1["TTS\nPocket TTS, local CPU"]
        E2["Image\nstock search -> AI gen fallback"]
    end

    E --> F["Section build\nKen Burns pan/zoom + audio sync (ffmpeg)"]
    F --> G["Final merge\nconcat sections + burned-in captions"]
    G --> H(["final.mp4"])
    H -.manual.-> I["Upload to YouTube"]

    style H fill:#2e7d32,color:#fff
    style I stroke-dasharray: 5 5
```

The opinion layer (`thesis`, `claim`, `evidence`) is always kept separate
from raw Wikipedia facts, so the rhetorical framing and the factual
grounding can be checked independently.

## Image generation: cheap and real before expensive and synthetic

Every subsection carries two prompts — a literal `stock_query` and an
AI-generation-style `image_prompt` — and the pipeline tries a real photo
before ever calling a generative model:

```mermaid
flowchart LR
    Q["stock_query"] --> P["Pexels search"]
    Q --> X["Pixabay search"]
    P --> J["LLM judge\npicks best match or none"]
    X --> J
    J -- "good match" --> S(["Use stock photo\n(free, no attribution)"])
    J -- "none qualify" --> N["Nano Banana\n(Gemini 2.5 Flash Image)"]
    N -- "quota exhausted" --> C["Cloudflare Workers AI\n(SDXL)"]
    C -- "unavailable" --> L["Local FLUX.2-klein\n(last resort, slow)"]

    style S fill:#2e7d32,color:#fff
    style N stroke-dasharray: 5 5
    style C stroke-dasharray: 5 5
    style L stroke-dasharray: 5 5
```

The judge weighs candidates in priority order — a real, on-topic photo beats
a generic illustration, which beats a same-era/culture "atmosphere" shot —
and only falls through to generation when nothing in the stock catalogs
clears the bar.

## What's built vs. what's next

```mermaid
flowchart LR
    subgraph Core["Core pipeline — done"]
        direction TB
        c1["research"] --> c2["stance"] --> c3["script"] --> c4["tts + image_gen"] --> c5["section_build"] --> c6["final_merge"]
    end
    subgraph Next["Publish & feedback loop — not yet built"]
        direction TB
        n1["publish tracking"] --> n2["insight store"] --> n3["feedback into next script"]
    end
    Core -.-> Next

    classDef done fill:#2e7d32,color:#fff;
    class c1,c2,c3,c4,c5,c6 done;
```

Publishing itself stays manual by design — the pipeline stops at the final
`.mp4`; you upload it yourself.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # or: source .venv/bin/activate  (Linux/macOS)
pip install -e ".[dev]"
```

Add your secrets to a `.env` file in the project root:

```
GOOGLE_STUDIO_API_KEY=...
MISTRAL_API_KEY=...
LLM_MODEL=mistral-large-latest
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
# optional: GROQ_API_KEY, CEREBRAS_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
```

Pipeline parameters (image-gen tiers, aspect ratio, captions, Ken Burns,
etc.) live in [`config.yaml`](config.yaml).

## Usage

| Command | Does |
|---|---|
| `pipeline new <slug> --topic "..."` | Start a new project |
| `pipeline run <slug>` | Run the pipeline end to end |
| `pipeline resume <slug>` | Resume from the last incomplete stage |
| `pipeline status <slug>` | Show per-stage progress |
| `pipeline list` | List all projects |

## Testing

TDD is the norm here — a failing test precedes every behavior change.

```bash
pytest
```

## Stack

Python 3.11+ · pydantic · Typer · httpx · ffmpeg · Wikipedia API · Mistral ·
Pexels/Pixabay · Pocket TTS (Kyutai) · Cloudflare Workers AI · FLUX.2-klein
