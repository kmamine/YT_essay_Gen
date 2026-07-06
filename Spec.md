# Automated Video Essay Pipeline — Spec

## 1. Goal
Generate opinionated video essays automatically: research a topic on Wikipedia,
write a scripted argument (not a neutral summary), generate narration audio and
matching images per section, then assemble everything into a final video.
Target length is 15-30 minutes typically, occasionally 1hr+ at the extreme —
noted as a design constraint (not yet a tuned config knob): per-segment cost
in the pipeline (LLM calls, image tier calls) should stay flat regardless of
segment count, so a longer video is just "more of the same," not a different
code path.

## 2. Pipeline Stages

```
[1] Research      -> Wikipedia API
[2] Stance         -> LLM picks a thesis / angle on the topic
[3] Script gen     -> LLM writes full script, structured into sections/subsections
[4] Per-subsection -> TTS (narration audio) + Image gen (visual), in parallel
[5] Section build  -> sync images to audio timing, concat into one video/section
[6] Final merge    -> concat all section videos + burned-in captions (+ optional music/intro/outro)
```

### 2.1 Research
- Input: topic string.
- Query Wikipedia (REST API or `wikipedia` python lib) for the main article +
  linked/related pages as needed.
- Output: raw facts, key claims, dates, quotes — grounding material for stage 3.
- No hard rate limit; send a descriptive User-Agent header.

### 2.2 Stance (opinion layer)
- Input: research facts.
- LLM call that commits to a **thesis**: the argument, the angle, what the
  viewer should walk away believing. Optionally generate 2-3 candidate
  theses and pick/select the strongest.
- Output: `thesis` (1-2 sentences) + `angle` (why this framing, what's
  contrarian/surprising about it).

### 2.3 Script generation
- Input: research facts + thesis.
- LLM writes the full script structured as sections -> subsections.
- Prompted explicitly to argue the thesis: no hedging, direct judgments,
  rhetorical framing, facts stay accurate but interpretation is opinionated.
- Output schema (JSON):

```json
{
  "title": "string",
  "thesis": "string",
  "youtube_metadata": {
    "title": "string (YouTube-facing title, may differ from script title)",
    "description": "string",
    "tags": ["string"]
  },
  "sections": [
    {
      "id": "sec_01",
      "title": "string",
      "subsections": [
        {
          "id": "sec_01_sub_01",
          "narration": "string (script text to be spoken)",
          "claim": "string (the point being argued)",
          "evidence": "string (grounding fact, sourced from Wikipedia stage)",
          "image_prompt": "string (prompt for image generation)"
        }
      ]
    }
  ]
}
```

- Keep `claim`/`evidence` (opinion) separate from raw Wikipedia facts so
  factual accuracy can be checked independently of the rhetorical layer.

### 2.4 Per-subsection generation
For each subsection, in parallel:
- **TTS**: Pocket TTS renders `narration` -> `.wav`. Runs locally, CPU-only,
  no rate limit (bottlenecked by local CPU speed, not an API).
- **Image**: each subsection carries two distinct fields — `image_prompt`
  (AI-generation phrasing) and `stock_query` (short literal keywords for
  stock-photo search). Four-tier fallback chain, cheapest first:
  1. **Stock photo search** (Pexels + Pixabay, queried in parallel and
     pooled into one candidate set; an LLM-judge call picks the best match
     against `stock_query` or says none qualify). No attribution required
     from either provider. Real photos beat AI generation on both cost and,
     often, plausibility — only falls through to generation when no
     candidate clears the relevance bar.
  2. Nano Banana (Gemini 2.5 Flash Image, cloud) — confirmed **zero
     free-tier quota** as of 2026-07-06 (see §5), so this tier is currently
     dead weight until upgraded/re-keyed.
  3. Cloudflare Workers AI (SDXL, ~100k free calls/day) (cloud fallback)
  4. FLUX.2-klein-4B-GGUF (local, last resort) — accepted to be slow
     (minutes/image on this hardware); only invoked once all prior tiers
     are exhausted.

### 2.5 Section assembly
- For each section: hold each subsection's image for the duration of its
  audio clip with a Ken Burns pan/zoom effect, concat subsection audio
  clips, mux into one video file per section (ffmpeg).

### 2.6 Final merge
- Concatenate all section videos in order.
- Burned-in captions, sourced from the script JSON's `narration` text.
- Optional: intro/outro, background music bed.
- Output aspect ratio (16:9 or 9:16) is a runtime parameter chosen per
  generation run, not fixed.
- Output: final `.mp4`.

## 2.7 Publish & Feedback Loop

A layer on top of the core pipeline: publish to YouTube, track performance,
extract insights, and feed those insights back into future script/stance
generation.

```
[6] Final merge  -> (from core pipeline)
[7] Publish       -> manual (you upload to YouTube yourself)
[8] Track         -> YouTube Analytics API (views, watch time, retention, CTR)
                   -> YouTube Data API (comments + comment metrics)
[9] Insight gen    -> LLM analyzes metrics + comments -> structured insights
[10] Insight store -> persisted, keyed by topic/thesis/style
[11] Feedback       -> stage [2] Stance and [3] Script gen pull past insights
                       before generating the next video
```

### Publish
- **Manual step**: you upload the final video to YouTube yourself, via the
  normal YouTube UI. The pipeline's job ends at producing the final `.mp4`;
  it does not call `videos.insert`.
- **Metadata is auto-generated, not auto-submitted**: the script-gen stage
  should also output YouTube-ready metadata alongside the video — title,
  description, tags — as a separate text output (e.g. a `metadata.txt` or
  `metadata.json` next to the final `.mp4`). You copy/paste these into the
  YouTube upload form yourself; nothing calls the API to set them.
- At a cadence of 1-2 uploads/week, this also means the 1,600-unit upload
  quota cost never applies to the pipeline itself — quota is only spent on
  the tracking side (metrics + comments), which is comfortably small at
  this volume (see table below).

### Track — metrics
- **Views, watch time, average view duration, retention curve, CTR**: these
  live in the **YouTube Analytics API**, a separate product from the Data
  API. Requires OAuth from the channel owner; only works for videos on
  your own channel (not arbitrary third-party videos — not a concern here
  since this is your own channel).
- **Likes, comment count, basic stats**: available via YouTube Data API
  (`videos.list`), cheap (1 unit/call).

### Track — comments & comment metrics
- Fetch comment threads via YouTube Data API (`commentThreads.list`).
- Comment metrics to capture: comment count, like count per comment,
  reply count, rough sentiment/topic distribution (via LLM pass over
  comment text), and any recurring themes (praise, disagreement,
  factual corrections, requests for related topics).

### Insight generation
- Input: video metadata (topic, thesis, section structure) + metrics +
  comments.
- LLM call that extracts structured insights, e.g.: did the thesis land,
  where retention likely dropped (correlate with section timestamps),
  what audiences pushed back on, what topics/angles got positive comment
  sentiment, requests for follow-up topics.
- Output schema (JSON), one record per video:

```json
{
  "video_id": "string",
  "topic": "string",
  "thesis": "string",
  "metrics": {
    "views": 0,
    "avg_view_duration_sec": 0,
    "retention_curve": [],
    "ctr": 0.0,
    "likes": 0,
    "comment_count": 0
  },
  "comment_insights": {
    "sentiment_summary": "string",
    "recurring_themes": ["string"],
    "notable_pushback": ["string"],
    "follow_up_requests": ["string"]
  },
  "takeaways": ["string (actionable insight for future scripts)"]
}
```

### Insight store
- Persist one record per published video (flat files, JSON lines, or a
  lightweight DB — TBD at implementation time).
- Should be queryable by topic, thesis style, and performance tier (e.g.
  "top quartile by retention") so stage [2]/[3] can pull relevant precedent
  rather than the entire history every time.

### Feedback into generation
- Before stance/script generation (stages 2-3) for a new video, query the
  insight store for relevant past takeaways (same topic area, similar
  thesis style, or general channel-wide patterns) and include a condensed
  summary in the prompt context.
- This is advisory context, not a hard rule — the LLM should weigh past
  performance signals alongside the new topic's own material.

## 3. External Services & Constraints


| Component        | Service                          | Cost / Limit notes |
|-------------------|-----------------------------------|---------------------|
| Research          | Wikipedia API                     | Free, no hard limit, needs User-Agent |
| Script/stance LLM | Mistral (free tier)               | Free tier limits unconfirmed — verify live before relying on them |
| Script/stance LLM (alt) | Groq / Cerebras            | Higher throughput, open models |
| Image gen (primary) | Pexels + Pixabay stock photo search | Free, no attribution required; pooled candidates + LLM relevance judge; falls through to generation tiers if nothing qualifies |
| Image gen (fallback) | Nano Banana (Gemini 2.5 Flash Image) | Confirmed **zero** free-tier quota as of 2026-07-06 — dead until upgraded/re-keyed. Google API is scoped to image gen only, not used for text/LLM calls |
| Image gen (fallback) | Cloudflare Workers AI (SDXL)   | ~100,000 free calls/day |
| Image gen (fallback, quaternary) | FLUX.2-klein-4B-GGUF (local) | GGUF-quantized 4B model, CPU-only, slow (minutes/image) — last resort only |
| TTS               | Pocket TTS (Kyutai)                | Local, CPU-only, no rate limit |
| Video assembly    | ffmpeg                             | Local, CPU-bound (slowest step on low-power CPUs) |
| Publish (upload)  | Manual (you upload)                | No API quota cost — pipeline stops at final .mp4 |
| Metrics (views/retention/CTR) | YouTube Analytics API   | Separate product from Data API; OAuth from channel owner; own-channel videos only; negligible quota use at 1-2 videos/week |
| Comments          | YouTube Data API v3 (`commentThreads.list`) | ~1 unit/call; well under 10,000/day at this cadence, even with frequent polling |

## 4. Hardware Notes
- Target dev machine: i5-U class laptop (low-power, no dedicated GPU).
- Pocket TTS and ffmpeg run locally — functional but not fast on this class
  of CPU; batch/background processing recommended over real-time.
- Image generation should stay API-based (cloud) as the primary path — local
  diffusion is impractical on this hardware as a routine step (minutes/image).
  A local model (FLUX.2-klein-4B-GGUF) is used only as a rare, explicitly
  slow last-resort fallback when both cloud tiers are unavailable.

## 5. Open Questions
- ~~Confirm actual Nano Banana free-tier quota via AI Studio.~~ **Resolved
  2026-07-06**: confirmed live — this API key/project's free tier has a
  hard **zero quota** for `gemini-2.5-flash-preview-image`
  (`RESOURCE_EXHAUSTED`, `limit: 0`), not a soft/transient rate limit.
  Nano Banana cannot be used for image gen until this is upgraded to a
  paid tier or a different key/project is used. The Cloudflare SDXL and
  local FLUX fallback tiers become load-bearing, not just backup, until
  then.

## 6. Non-goals (for now)
- No multi-language support.
- No real-time/interactive generation — batch pipeline only.
- No cross-platform publishing (TikTok, Shorts repurposing, etc.) — YouTube
  only for now.
- No automated response to comments (reading/analyzing only, not replying).