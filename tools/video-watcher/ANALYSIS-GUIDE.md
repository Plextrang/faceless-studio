# Analysis guide — what to do with a completed run

`watch_video.py` stops at the data. This file is the other half: how to read what it produced and
what to write. Claude follows this after every run.

Transcripts alone are useless here; the information needed is visual. The pipeline's whole job is
turning one video into the densest useful set of images plus text, and this guide is how that gets
read.

**Core design decision: one frame per detected shot, plus dense uniform fill — never uniform
sampling alone.** Uniform sampling lands mid-shot and misses short animations. An animation
appearing IS a scene change. But cut detection is blind to slow morphing motion graphics, so uniform
fill covers what it cannot see. In practice the fill frames carry more of the design work than the
detected cuts do.

Local only: yt-dlp, ffmpeg, Python stdlib. No MCP servers, no APIs, no accounts, no paid services.

---

## Run the pipeline

From the package root (the folder holding `README.md`):

```
py "tools/video-watcher/watch_video.py" "<URL>"
```

Check the toolchain first on a fresh copy:

```
py "tools/video-watcher/watch_video.py" --check
```

Output lands in the configured output root — `video-research/` by default, relative to the package
root, and gitignored. Override per run with `--root`, which is how a faceless-studio project keeps
its research next to itself:

```
py "tools/video-watcher/watch_video.py" "<URL>" --root "<project>/research/watcher"
```

Produces `<root>/<slug>/` containing `frames/`, `sheets/`, `data/`, and later your `NOTES.md`.

Flags:
- `--slug NAME` — folder name (default: derived from the title)
- `--root PATH` — output root; relative paths resolve against the package root
- `--start SEC` / `--end SEC` — analyse a segment only
- `--hook-only` — first 60 seconds only, dense. **Use this when analysing more than one video in a
  session.**
- `--threshold N` — override the scene threshold
- `--no-download` — reuse an already-downloaded source
- `--keep-source` — do not delete the source file when done
- `--check` — verify Python, yt-dlp, ffmpeg, Node and the font, then exit

Resumable. Existing frames, sheets and data are reused, so re-running is cheap — a completed video
re-runs in well under a second with no network.

The script deletes the source video once frames and audio both succeed. Frames, sheets, CSVs and
`NOTES.md` are what gets kept; the source is disposable and re-downloadable.

Quote every path. These live under paths with spaces in them.

---

## Session budget — read before running

A **full** analysis is roughly 150–250K tokens of images. That is one video per session.

A `--hook-only` run is roughly a tenth of that, which is what makes two or three reference videos
possible in one session. When the goal is a hook pattern, a cadence and a style vocabulary rather
than a complete teardown, `--hook-only` is the correct setting and not a compromise.

Never silently reduce frame counts to save tokens. If a video would produce an unreasonable number
of frames, say the number and let the user decide.

---

## What the pipeline decides, so you do not have to

**Pacing.** Detection runs at a fixed base threshold (0.20 by default). Detections closer than 1.0s
are merged into one shot, because high-motion animation (camera push-ins) trips scene detection
repeatedly inside a single continuous shot. **Merged shots is the pacing number. Raw detections get
one line, never a table.** The threshold only drops (0.15, then 0.12) if merged shots/min falls
under 4, which means cuts are genuinely being missed. Band is 5–30 merged shots/min. If a video
lands outside it, say so in the report and move on — do not chase it with the threshold.

**Low-cut sections.** Any gap over 15s gets fill frames every 5s. These are reported as *low-cut
sections* and you describe what is actually in them. The pipeline runs SSIM across each section's
fill frames; only a section whose frames come back near-identical (≥0.97) is flagged a real **dead
zone**. Everything else is dense animation the detector could not see — the opposite of dead.

All of these live in `config.json` under `detection`. Changing them changes the numbers; do not,
without a reason from `METHOD.md`.

## SSIM cannot adjudicate cuts

**Fast camera motion depresses SSIM identically to a hard cut, so it ranks continuous moving shots
as the most definite cuts. Adjudicate disputed timestamps by extracting before/after frame pairs and
looking at them. SSIM remains valid ONLY for the dead-zone check, comparing near-identical static
fill frames.**

This was learned the hard way: on the first video analysed, SSIM's three most confident "real cuts"
(0.43–0.63) were all one continuous shot with a camera push. The dead-zone check is a different
question — "did anything change at all" — and SSIM answers that correctly.

To adjudicate: extract frames at `t-0.45` and `t+0.45`, tile them into labelled BEFORE/AFTER pairs,
and read them. Never trust a number here.

## Screen-recording bias

Cuts inside screen recordings score under the base threshold, because window chrome and background
barely change across them. Videos built on screen recordings therefore **under-count**.

1. Decide from the composition mix in section 7. If screen recording is roughly a third or more of
   runtime, treat the video as screen-recording heavy.
2. In section 4, state explicitly that **merged shots/min is a floor, not a measurement**, and why.
3. Report both numbers as a range. The pipeline always computes a secondary low-threshold pass
   during the run and stores it in `pacing.json` under `secondary_low_threshold` — the source is
   deleted after extraction, so this cannot be recomputed later. Use the base threshold's number as
   the floor and the secondary as the ceiling: "between X and Y per minute". Do not present either
   end as the true figure.

---

## Build hierarchy — read before writing 3b

Cheapest first. Route every animation to the highest tier it can be done in.

1. **Coded template (Remotion, or plain HTML/CSS) — FREE, 0 credits.** Deterministic text, reusable
   forever, no model drift. This is the right route for **type, cards, diagrams, charts, wipes,
   lower-thirds, counters, timelines, UI mockups, and anything that repeats**. A repeating card
   template is a **Yes, build once** — never a No.
2. **Generated stills + video — costs credits, non-deterministic.** Correct only for photoreal,
   textured or illustrated b-roll that code cannot make: claymation, felt, 3D renders, cinematic
   scenes, characters.
3. **If the answer would be "do it in After Effects", the answer is a coded template.** Do not mark
   anything No because it needs a compositor you do not own.

Note that competitor motion graphics that look like After Effects are usually coded — flat vector,
crisp type, glass cards, gradient fields and spring easing all point that way. Assume code unless
there is real evidence otherwise.

**Separate assets from composition before costing any row.**
**Assets** are the images and clips *inside* the video — illustrations, characters, textures,
b-roll. They route to generation and cost credits.
**Composition** is the edit itself — how cards animate in, how type reveals, transitions, layout,
lower-thirds. It routes to code and costs nothing after the build.
A competitor can use generated assets inside a coded composition, and usually does: a title card
holding a generated illustration is an asset (costs credits) inside a composition (free). Cost only
the asset. Pricing a whole graphic sequence as generation because it looks polished is the single
mistake that inverts this analysis.

**Credit rates and budget come from the run, not from this file.** Read
`<run folder>/data/cost_config.json`, which the pipeline writes from `config.json`:

- `rates` — price per still, per short clip, per longer clip. A `null` rate means **not configured**:
  report that row as "rate not configured" rather than inventing a number.
- `budget_per_video` — the operator's ceiling. If `min` and `max` are `null`, **report the total and
  give no within/over verdict.** Do not substitute a remembered figure.

Rates move constantly. If the user has live pricing in front of them, prefer it and offer to write
it into `config.json`.

---

## Analysis

Read `data/transcript.txt`, `data/meta.json`, `data/pacing.json`, `data/audio_summary.json`,
`data/low_cut_sections.csv`, `data/source_quality.json` and `data/cost_config.json` first.
Then the sheets.

**Check `source_quality.json` before reading any frame.** If `stream` is `progressive`, the
download fell back to roughly 360p because adaptive streams were unavailable. On-screen text
will often be genuinely unreadable at that size. Say so in section 5 and leave the entry out
rather than guessing at text you cannot actually read.

**Maximum 60 images per read batch.** After each batch append findings to a working file and drop
those images from context. Notes persist, frames do not need to. The API caps at 100 images per
request, so accumulating across turns will eventually fail outright.

**Survey pass.** Read all sheets in order. Build a rough timeline and flag every timestamp that
looks like an animation, title card, graphic, chapter transition, or distinctive composition.

**Microscope pass.** Load flagged frames individually at full resolution from `frames/`. Read
on-screen text, describe animation style, note colour and layout. Expect 30–60 frames. Always
microscope the first 45 seconds densely regardless of what the survey flagged, because the hook
decides everything.

Sheets are for structure, not for reading text. Cells downscale to ~520x290 — enough to see that a
title card appeared, not enough to read it. Reading happens in the microscope pass.

---

## Output schema — NOTES.md

Fixed structure, identical every video, so these compound into a comparable library.
Write findings only. No preamble, no "this video demonstrates", no summary paragraph at the top.
These are reference material, not essays.

1. **Header.** Title, channel, duration, views, upload date, URL, date watched. Note sponsorship if
   present.

2. **Hook map, 0:00–0:45.** Beat by beat. Each beat: timestamp, what is said verbatim from the
   transcript, what is on screen from the frames, and what the beat is doing (claim, credibility,
   promise, teaser, pattern interrupt).

3. **Animation inventory.** Table: timestamp, duration, type, style description, what narration beat
   it covers, whether text is baked in.

3b. **Reproduction cost.** Immediately after the animation inventory. One row per inventory row.
   See the build hierarchy above — get the route right before costing it.
   Columns: timestamp, route (Coded / Generated / Hybrid), buildable (Yes / Partial / No), stills,
   renders, **estimated credits**, notes. Mark repeating templates as build-once and say how many
   times they are reused. Total the credits at the bottom against the budget from
   `data/cost_config.json`, with a verdict: within budget, or X times over. **If over, name the
   cheapest viable subset** — what to build, what to cut, what to substitute with a coded template.
   If no budget is configured, give the total and skip the verdict.
   Separate "can be built" from "is worth building". A 40-still generated montage can be
   technically buildable and still financially wrong. Say both.

4. **Pacing.** Merged shots per minute overall, the per-60s bucket curve (merged only — one table,
   not two), fastest and slowest stretches with timestamps, longest single shot, low-cut sections
   with what is in them, and any true dead zones. Add one line noting raw detection count and that
   high-motion animation inflates it. State if the video is outside the 5–30 band.

5. **On-screen text log.** Timestamp and verbatim text for every readable title, label, caption or
   callout. Note any repeating typographic system at the end.

6. **Segment structure.** Where each section starts and ends, what it delivers, and at what
   percentage of runtime the first real value lands.

7. **Composition mix.** Rough percentage split of talking head, screen recording, b-roll, full-frame
   graphics.

8. **Audio structure.** Findings only: are cuts beat-aligned or not, how many risers-into-breaks and
   where, where the energy actually comes from, music-bed versus dry sections. **No LUFS, LRA or
   median figures — they are noise.**

9. **Packaging.** Thumbnail described from `data/thumbnail.jpg`, the title, and how the two relate.
   Do they extend each other or repeat each other.

10. **Steal list.** Three to six specific, copyable techniques with timestamps. Concrete moves, not
    general praise.

Sections 2, 3, 3b, 7, 9 and 10 carry most of the value. Weight the effort accordingly.

**On a `--hook-only` run:** sections 1, 2, 3, 5, 9 and 10 are complete. Section 4 covers the first
minute only — say so. Sections 6 and 8 are not answerable and should be marked "not covered
(hook-only run)" rather than guessed.

---

## After every run — update the index

Append one row to the live index at `<output root>/INDEX.md`. Never rewrite existing rows. The
tool's `INDEX.template.md` is a headers-only scaffold; the script seeds the live index from it on
first run. Do not append rows to the template.

| Column | Source |
|---|---|
| Title, Channel, Subs, Views, Duration, Uploaded | `data/meta.json` |
| Multiplier | views ÷ subs, one decimal, e.g. `4.4x` |
| Analyzed | today's date |
| Takeaway | one line, the single most transferable finding |

The multiplier is the reason the index exists: it separates videos that outperformed their channel
from videos that merely have a big channel behind them. Sort your attention by it.

---

## Rules

- If a step fails, show the actual error before proposing a fix. Do not guess at causes.
- Fix problems yourself where you can rather than handing them back.
- If no captions exist at all, stop and say so. Speech-to-text is not part of this pipeline.
- Quote every path. Windows paths with spaces are the normal case here.
