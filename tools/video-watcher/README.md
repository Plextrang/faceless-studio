# video-watcher

Optional. The faceless-studio skill works completely without this.

Turns a YouTube video into something Claude can actually study: one frame per shot plus dense
uniform fill, timestamped contact sheets, a clean transcript, pacing data and an audio energy curve.
Claude then reads those and writes a fixed-schema `NOTES.md` — hook beat by beat, animation
inventory with reproduction costs, on-screen text, structure, packaging, and a steal list.

Transcripts alone are useless for this. What matters is visual: what animation appears at what
moment, what the on-screen text says, how the hook is built shot by shot. Claude cannot ingest
video, but it can read a large number of images. This converts one into the other.

## What it needs

| | |
|---|---|
| **Python 3.8+** | you already have it if you followed the main README |
| **yt-dlp** | `py -m pip install -r requirements.txt` |
| **ffmpeg** | Windows `winget install Gyan.FFmpeg` · macOS `brew install ffmpeg` · Debian/Ubuntu `sudo apt install ffmpeg` |
| **Node.js** | optional — yt-dlp uses it as a JavaScript runtime for some videos. Skipped automatically when absent. |

No API keys. No accounts. No cookies. No browser profile. No paid services. Everything runs locally
against public video.

Check all of it at once, from the package root:

```bash
py "tools/video-watcher/watch_video.py" --check
```

## Run it

```bash
py "tools/video-watcher/watch_video.py" "<YOUTUBE_URL>"
```

Useful flags:

| Flag | Effect |
|---|---|
| `--hook-only` | first 60 seconds only. **Use this for 2–3 reference videos in one session.** |
| `--start SEC` / `--end SEC` | analyse one segment |
| `--slug NAME` | name the output folder yourself |
| `--root PATH` | where output goes; relative paths resolve against the package root |
| `--threshold N` | override the scene-detection threshold |
| `--no-download` | reuse an already-downloaded source |
| `--keep-source` | do not delete the source video when finished |
| `--check` | verify the toolchain and exit |

Resumable — existing frames, sheets and data are reused, so re-running is cheap. A completed video
re-runs in well under a second with no network.

## Where output goes

Default output root is `video-research/` at the package root, and it is gitignored. Nothing an
analysis produces is meant to be committed.

```
<package root>/
├── tools/video-watcher/     ← the tool. Ships in git.
└── video-research/          ← every analysis. Gitignored, never uploaded.
    ├── INDEX.md             one row per video, sorted by views ÷ subs
    └── <video-slug>/
        ├── NOTES.md         the deliverable
        ├── frames/          one JPEG per shot + fill frames
        ├── sheets/          3x3 contact sheets, 1568px, timestamps burned in
        └── data/            transcript, meta, pacing, cuts, audio, thumbnail
```

The faceless-studio skill overrides this per run so a project's research sits next to the project:

```bash
py "tools/video-watcher/watch_video.py" "<URL>" --hook-only --slug ref1 --root "my-video/research/watcher"
```

`my-video/research/watcher/` is gitignored too. The script refuses a `--root` inside
`tools/video-watcher/` rather than dropping 30 MB among the source files.

The source video is deleted automatically once frames and audio both succeed. Frames, sheets, CSVs
and `NOTES.md` are what gets kept; the source is disposable and re-downloadable.

## Configure it

Everything tunable lives in `config.json`. There isn't one yet — copy the example:

```bash
copy tools\video-watcher\config.example.json tools\video-watcher\config.json
```

(macOS/Linux: `cp`.) If you skip this, the tool reads `config.example.json` and runs fine.

What is worth setting:

- **`credits.rates`** — your generation provider's live prices. Ships as `null`, meaning *not
  configured*: cost rows say so instead of inventing a number.
- **`credits.budget_per_video`** — your ceiling for reproducing one video. Ships as `null`, meaning
  totals are reported with no within/over verdict.
- **`font_path`** — only if `--check` warns it could not find a bold sans font.
- **`detection`** — the pacing tuning. Read `METHOD.md` §4–6 before touching any of it; the defaults
  are the result of measurement.

`config.json` is gitignored. Your numbers stay yours.

`.env.example` covers the three optional environment overrides (`VIDEO_WATCHER_FFMPEG`,
`VIDEO_WATCHER_FONT`, `VIDEO_WATCHER_ROOT`). Most people never need it.

## What it costs

The pipeline itself is free — local tools, no API. The cost is **Claude's context**, because
analysis means reading a lot of images:

| Run | Rough cost |
|---|---|
| `--hook-only` (60s) | ~15–25K tokens of images |
| Full video (8–10 min) | ~150–250K tokens of images |

A full analysis is one video per session. Two or three `--hook-only` runs fit comfortably in one
session, which is exactly what the skill's research step uses.

## Known limits

Read these before trusting a number.

- **No audio content.** It measures loudness, not sound. It cannot hear music, tone, voice quality
  or what the music is doing — only where energy rises and falls.
- **No motion.** Frames are stills. Easing, speed ramps, transition style and camera movement are
  invisible except where consecutive frames imply them.
- **Screen-recording bias.** Cuts inside screen recordings barely change the pixels — same window
  chrome, same background — so they score below the detection threshold and get under-counted. On
  screen-recording-heavy videos the shot rate is reported as a **range**, not a figure, and the
  lower number is a floor rather than a measurement.
- **SSIM cannot adjudicate cuts.** Fast camera motion depresses SSIM exactly like a hard cut, so it
  ranks continuous moving shots as the most definite cuts. Disputed timestamps are settled by
  extracting before/after frame pairs and looking at them.
- **Cut detection is blind to slow morphing graphics.** This is why uniform fill exists, and in
  practice the fill frames carry more of the design work than the detected cuts do.
- **English captions required.** If a video has no captions at all, the pipeline stops and says so.
  Speech-to-text is not part of it.

## Files here

- `watch_video.py` — the pipeline. Everything up to analysis.
- `ANALYSIS-GUIDE.md` — what Claude does with a completed run, and the fixed `NOTES.md` schema.
- `METHOD.md` — the portable method: every design decision and the lesson behind it. No code, no
  machine paths. Someone with no access to this repo could rebuild the whole thing from it.
- `config.example.json` · `.env.example` · `requirements.txt` · `INDEX.template.md`
