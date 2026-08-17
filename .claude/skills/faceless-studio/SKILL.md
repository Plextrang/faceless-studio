---
name: faceless-studio
description: Turns one person into a full faceless video studio using Seedance 2.5 on Higgsfield. Use whenever the user wants to make a faceless video or faceless channel content: an idea becomes research, script, beat sheet, characters, world, storyboard, prompts, and finished clips with sound. Trigger on "faceless video", "faceless channel", "make me a video with Seedance", "/faceless-studio", or any request to plan and generate an AI video end to end.
---

# FACELESS STUDIO

One person, full studio. This skill takes a topic and walks it to finished, sorted, ready-to-edit video clips with sound, generated with Seedance 2.5 through the Higgsfield MCP. The user makes decisions; the skill does the work.

Built for beginners. Nothing in the core path requires anything beyond this skill file and a connected Higgsfield MCP.

## OPERATING RULES (read first, apply everywhere)

1. **Story first, spend last.** No generation happens until the plan is approved with a credit estimate next to it.
2. **Never more than 3 questions at a time.** Propose ONE concrete option, not five. Fill every gap you can yourself, then say what you decided so the user can overrule it.
3. **Point, never re-describe.** Once a character or location has an approved reference image and an ID like `@rider`, every later prompt points to the ID and the reference. Re-describing from memory is how characters drift.
4. **One focus per output.** When you show the user something to approve, show one thing: the concept, or the beat sheet, or the cast. Never three at once.
5. **Cheap pass before real pass.** Test risky shots at low resolution and judge ONLY motion, consistency, and logic. Never judge realism at 480p. Pretty is not on the test.
6. **Timestamps are filenames.** Every generated file is named by its script timestamp (`00_07.mp4` = the clip that starts at 0:07). Sorted folder = edit order. This one convention removes most of the editing work.
7. **Honesty on flaws.** If a clip has warped hands, physics glitches, or continuity breaks, say so before the user notices, and offer the two real fixes: regenerate, or plan the cut-around. Never present a broken clip as fine.
8. **Log every credit spent.** Keep a running cost line in `project.md`. The user should always know what this video cost so far.

## PROJECT STRUCTURE

On start, create a project folder and keep everything in it:

```
<video-name>/
  project.md          <- decisions, IDs, credit log (the skill maintains this)
  research/notes.md   <- STEP 1 output
  script/             <- script, beat sheet, VO, timestamped transcript
  cast/               <- character sheets (one grid image per character)
  world/              <- environment plates + LOOK.md
  boards/             <- storyboard grids
  prompts/            <- final per-beat prompts, one file, reviewable
  outputs/            <- generated clips, timestamp-named
```

## STEP 0 - SETUP CHECK

Confirm the Higgsfield MCP is connected (any `mcp__Higgsfield__*` tool responds). If not, stop and give the user the one-line fix: connect Higgsfield in Settings -> Connectors, then rerun. Do not continue without it.

Confirm Seedance 2.5 availability and pull LIVE pricing for stills and video seconds before any budget talk (`models_explore` / plans info). Never quote remembered prices. Write the live rates into `project.md`.

Facts that govern generation planning: Seedance 2.5 does 4 to 30 second single generations, native audio including speech and lip sync, 480p/720p, modes t2v / omni_reference (image references) / video_edit / video_extension.

This repo ships an optional research tool at `tools/video-watcher/` (see STEP 1 POWER MODE). It is never required — do not check for it here, and do not mention it unless STEP 1 reaches it.

## STEP 1 - RESEARCH: WHAT'S ALREADY WINNING

Goal: ground the video in formats that are proven in the user's niche, instead of guessing.

**Interface contract (fixed, both paths write the same file):**

- INPUT: 2 or 3 reference videos in the target niche, ideally outliers (views far above the channel's subscriber count).
- OUTPUT: `research/notes.md` with exactly these sections:
  - `## Winners` : each video's title, channel, views vs subs, one line on why it works
  - `## Hook pattern` : what the first 30 seconds do, beat by beat
  - `## Style words` : 5 to 10 concrete visual adjectives (these feed STEP 4's LOOK)
  - `## Beat cadence` : typical scene length in seconds, and where the pace peaks
  - `## Title + thumbnail patterns` : the promise structure the niche clicks on
- STEP 2 consumes Hook pattern and Beat cadence. STEP 4 consumes Style words. Do not change this schema.

**Default path (no extra tools, works for everyone):**

1. Ask the user for 2 or 3 links to videos they wish they had made, or propose a niche's known winners and let them pick.
2. Pull whatever is accessible for each (transcript, description, visible stats). Ask the user to describe or screenshot each thumbnail if needed.
3. Fill the schema above yourself. Where data is missing, infer carefully and mark it as inferred.

Keep this step under 15 minutes. It is grounding, not a research project.

**POWER MODE (optional):** if `tools/video-watcher/watch_video.py` exists in this repo, it replaces
step 2 of the default path with measured data instead of inference. Everything else is identical —
same three questions, same fixed schema, same 15-minute ceiling. The watcher is never a requirement.

*Gate.* Run this first, from the repo root. If it fails for any reason, say so in one line and run
the default path. Do not debug it here; research is not the place to fix a tool.

```
py "tools\video-watcher\watch_video.py" --check
```

*Run.* One command per reference video, from the repo root. `<video-name>` is the project folder from
PROJECT STRUCTURE:

```
py "tools\video-watcher\watch_video.py" "<URL 1>" --hook-only --slug ref1 --root "<video-name>\research\watcher"
py "tools\video-watcher\watch_video.py" "<URL 2>" --hook-only --slug ref2 --root "<video-name>\research\watcher"
py "tools\video-watcher\watch_video.py" "<URL 3>" --hook-only --slug ref3 --root "<video-name>\research\watcher"
```

`--hook-only` is deliberate and not a shortcut. A full run is 150–250K tokens of images, which is one
video per session; the hook-only run is roughly a tenth of that, which is what lets all three
references land in the same session. The first 60 seconds is also exactly what this step needs.
Drop `--hook-only` only if the user asks for a full teardown of one video, and then run only that one.

*Read.* Per reference, follow `tools/video-watcher/ANALYSIS-GUIDE.md`: the data files first
(`data\meta.json`, `data\transcript.txt`, `data\pacing.json`, `data\thumbnail.jpg`), then a survey
pass over `sheets\`, then a microscope pass on flagged frames in `frames\`. Cap image reads at 60 per
batch. Writing each reference's own `NOTES.md` is optional here and stays inside `research\watcher\`.

*Map into `research/notes.md`.* The schema above is FIXED — the watcher fills it, never changes it,
and nothing downstream can tell which path produced the file.

| Section | Filled from | How |
|---|---|---|
| `## Winners` | `data\meta.json` header stats | title, channel, `view_count` vs `channel_follower_count` (give the multiplier, one decimal), then one line on why it works, drawn from that video's hook map |
| `## Hook pattern` | the hook map, 0:00–0:45 | beat by beat across all references; write the pattern they SHARE, and note where one deviates. Verbatim line + what is on screen + what the beat is doing |
| `## Beat cadence` | `data\pacing.json` | typical scene length = 60 ÷ `merged_shots_per_min`, in seconds; peaks from the `buckets` curve. If `secondary_low_threshold` matters (screen-recording heavy), give a range and say it is a floor |
| `## Style words` | animation inventory + composition mix + on-screen typography | compress into 5–10 concrete visual adjectives. Adjectives only — no table, no percentages. This is what STEP 4's LOOK paragraph is built from, so vague words here cost real credits later |
| `## Title + thumbnail patterns` | `data\thumbnail.jpg` + the title in `meta.json` | the promise structure: what the title claims, what the thumbnail shows, whether they extend each other or repeat each other |

*Rules.*
- Per video, not all-or-nothing. If one reference fails to download or has no captions, fill that
  video's rows the default way and keep the watcher results for the other two.
- Never block on the watcher. Missing, broken, or slow — the default path runs and STEP 2 proceeds.
- Everything under `research\watcher\` is working material and is gitignored. `research/notes.md` is
  the deliverable and the only file STEP 2 and STEP 4 read.

## STEP 2 - CONCEPT, SCRIPT, BEAT SHEET

1. Interview, max 3 questions: niche/topic (or propose one from research), target length as a RANGE — never an exact number: propose ranges like 15–30s, 30–45s, 45–75s (default 30–45s for a first video), narrated or native-sound (see STEP 3). The chosen range sizes ONLY the script's word budget. Final runtime is an OUTPUT of the story and the audio's natural pace — never compress, speed up, or re-pace audio or video to hit a number. (An exact target forced audio speed-ups in a past video; a range never does.)
2. Propose ONE concept with a working title, a one-line premise, and the emotional shape (what the viewer feels at start, middle, end). Get approval.
3. Write the script. For narrated videos: about 2.4 words per second of runtime (a 30s video is roughly 70 to 80 words). Written for the ear, short sentences, no filler.
4. Build the beat sheet like an editor spending a budget of seconds. Every beat gets: a name, a time range, a shot type (WIDE / MED / CU / OTS / TRACKING), and how it ends. Beats run 2 to 6 seconds for a starter video. Every second of runtime is assigned to a beat; nothing is left vague.
5. Show the beat sheet as one table. Get approval before anything visual exists.

## STEP 3 - SOUND: PICK ONE PATH

**Path B - native sound (only for videos with NO narration).** Seedance 2.5 renders audio with the video. Write sound INTO each beat: ambience, SFX, and diegetic spoken lines (with lip sync) go in the prompt. Skip voiceover entirely. Fastest path to a finished single-clip piece. This path is for diegetic sound only — the moment the video has narration, it is Path A. Never split narration across clips.

Path B hard-won rules (learned on a real delivery; they save a full rework):
- **Music is a GLOBAL element, same law as narration: one continuous edit-stage track, never per-clip.** Seedance bakes background score into clips even when every prompt says "no music" — treat that instruction as a request it will ignore. Two acceptable strategies, offer both: (a) DEFAULT: generate with native audio ON (keeps giggles/SFX), then strip the baked score per clip at assembly via source separation (STEP 7), and lay ONE real full-length music track in the edit; or (b) generate with audio OFF entirely (silent clips — loses SFX too, all sound built in the edit). Truly continuous generated music across clips is impossible in this stack: each clip composes independently and Higgsfield has no standalone music model. Do NOT try to hide loud baked music by ducking (still audible, fights the bed's key), and do NOT loop a ~5-second isolated music stem into a full-length bed (audibly repetitive — a real track or nothing).
- **Sparse diegetic dialogue is allowed and often lands the theme** (a parent's one-liner, a name, a goodnight). Generate the line INSIDE the clip — native speech is lip-synced and sits in the scene's acoustics. Never lay dry TTS over a finished clip: a studio-dry line on an ambient mix reads robotic and pasted-on, and no timing tweak fixes it.
- **Voice consistency across clips:** isolate the first good take's voice (Demucs vocals stem), upload it, and attach it as `audio_references` on every later clip that character speaks in.
- **Audio transplant is a free repair:** a good voice take on a bad visual take is salvageable — mix its vocals stem onto a better take's picture. Prefer lines placed where the speaker's mouth isn't prominent (off-screen, leaning in, back turned) so transplants carry no lip-sync risk.

**Path A - narrated (any video with a voiceover; the default for multi-clip videos).** ONE continuous voiceover track, never per-clip narration. Generating narration inside each clip — even with a cloned voice reference — matches the tone but not the tempo: every clip gets its own speaking speed and the video feels inconsistent. The required pipeline, voiceover first, visuals second:
1. Generate the ENTIRE script as one continuous TTS voiceover track (Higgsfield Seed Audio; a voice can be cloned from a reference sample via `audio_references`).
2. Find sentence boundaries with ffmpeg `silencedetect`.
3. Cut the script into beats at the silence midpoints. Each beat's clip duration is derived FROM its audio segment, rounded UP to the model's minimum clip length. Update the beat sheet's time ranges to these measured boundaries — they are also the filenames.
4. Video clips are generated with AMBIENCE ONLY — no speech, no narration, no music in any clip prompt (enforced in STEP 6).
5. Assembly trims each clip to its audio segment and lays the single VO track over the whole cut (STEP 7).

**Hard rule: runtime is an OUTPUT, never an input.** Total video length falls out of the narration's natural pace. Never compress, speed up, or re-pace the audio to hit a target length — stretch the video plan to fit the audio instead.

State which path you chose and why in one line. Let the user overrule.

## STEP 4 - CAST AND WORLD

**Characters. One grid image per character, not many singles.**
- Generate a single character sheet: 4-panel turnaround on a plain neutral grey background.
- Specify concretely: age, build and posture, hair (length, colour, how it sits), face (brows, eyes, nose, shape, facial hair), one or two distinguishing marks, every garment (fabric, cut, colour, condition), footwear.
- Get approval, save it in `cast/`, assign an ID (`@rider`). From here on, point.

**Environments. One plate per location.**
- One image per location, shot from an angle, never straight on (straight-on reads as a flat backdrop and gives the camera nowhere to go).
- Every plate carries the LOOK paragraph word for word, so the whole world matches before the film exists.

**The LOOK paragraph (the single biggest quality lever).**
- Ask the user for one reference still: a frame from any film or photo they want this video to feel like. If they have none, propose one based on `## Style words` from research.
- From that reference, write ONE paragraph covering, in order: capture medium, lighting, camera behavior, lens character, halation, grain, tone curve, colour, dynamic range. Describe the look ONLY: no subjects, no objects, no story. It must apply to any image.
- Save as `world/LOOK.md`. Paste it into every image and video prompt from now on. Ungraded AI output looks like AI; the LOOK is what makes it look shot.

## STEP 5 - STORYBOARD

- Render the storyboard as ONE grid image (up to 9 beats per grid), each cell labelled with beat number, time range, and shot type. One image costs a fraction of nine and doubles as a reviewable artifact.
- Walk the user through it beat by beat. Revisions are made in plain language ("beat 12: he should face the camera when he's grabbed"), then re-render the grid.
- Plan on-screen text NOW, as editor overlays. Motion-first clips (STEP 6) do not use a locked start frame, and without one, generated on-screen text garbles — baked-in labels only survive when a shot uses `start_image`. So any label, date, or title a beat needs is marked on the board as a hand-lettered overlay to be added in the edit, never asked of the generator.
- Do not pass this gate until the user approves the board. Storyboard changes are nearly free; render changes are not.

## STEP 6 - PROMPTS, BUDGET GATE, GENERATE

**Write the per-beat prompts — motion-first, never "living stills."** Animating an approved still with "subtle motion, locked camera" produces an animated picture — a GIF feel, not film. Every prompt must pass this checklist:
- Under 50 words each.
- Priority order: motion, mood, camera movement. Write camera moves as what you would SEE ("the background stretches away behind him"), never jargon.
- Use `image_references` (omni_reference) for style and identity consistency, NOT `start_image`. Reserve `start_image` only for a shot where one exact opening frame is mandatory (including any shot that must carry baked-in text).
- Every shot gets a real camera move with parallax: push-in, dolly, tracking, tilt, slow orbit. A locked frame is a rare deliberate choice, never the default.
- A character in the shot must COMPLETE an action with a beginning and an end (walk, turn, reach, react) — not just sway or flicker.
- The scene should EVOLVE during the shot: light dies, weather worsens, a crowd reacts in a wave.
- Design shot-to-shot FLOW across the whole video: consistent motion direction for traveling elements, and match-cut handoffs (one shot ends tilting up to the sky, the next opens on the sky; one shot pushes into blackness, the next emerges from it).
- Reference cast and world by ID + attached reference image, plus the LOOK paragraph.
- Sound in the prompt follows STEP 3's path. Narrated path: every clip prompt carries "ambient sound only, absolutely no speech, no narration, no music" — the single VO track is the only voice in the video. Native-sound path: include the beat's ambience/SFX/spoken diegetic line — and still write "no music", knowing Seedance bakes a score anyway; it gets stripped at STEP 7.
- A camera that EXITS the room (pulling back through a window or door) risks a collapsed, dead-space exterior — the environment outside the opening never materializes. Either describe the exterior explicitly in the prompt ("the house's outer wall and roof visible against the night sky") or plan the beat so a failed take is fixable by audio transplant onto an earlier good take (STEP 3).
- If a submission comes back intercepted by a Higgsfield preset recommendation instead of generating (e.g. "IN THE DARK"), that is not a failure and nothing was billed — resubmit the identical request with `declined_preset_id` set to the offered preset id.
- No text overlays, no logos, no captions in the generated footage — without a locked start frame, generated text garbles. Text belongs to the edit as the overlays planned in STEP 5, where it stays consistent.
- Save the full prompt list to `prompts/` as one reviewable file.

**Budget gate (hard):**
- Show the full generation plan as a table: beat, mode, duration, resolution, credits each, total. Use the LIVE rates from STEP 0.
- Starter target: 150 credits or less for a 30 to 60 second video. If the plan is over, offer the cuts (fewer beats, shorter beats, stills with a slow push for low-motion moments — done as a pan/zoom on the still in the edit, not as a "subtle motion" video generation, which produces the living-still look banned in the prompt rules). On the narrated path, cuts change the visuals only — never shorten or re-pace the VO to save credits.
- Generate NOTHING until the user approves the total.

**Generate:**
- Cheap pass first: the 2 or 3 riskiest beats (character interaction, physics, hands) at 480p. Grade them on motion / consistency / logic only — AND on Rule-of-motion compliance: if a clip reads as an animated picture (no parallax, no completed action, no evolution), that is a failed clip; fix it at the prompt level before the final pass.
- Narrated path: each clip's duration comes FROM its audio segment (STEP 3), rounded up to the model's minimum. Never trim the audio to fit a clip — generate the clip long enough for the audio.
- Final pass at 480p; 1080p comes from the single final upscale in STEP 7 (see CREDIT DISCIPLINE — 720p generation costs 2.6x per second and is never the default). Long continuous shots: generate the base clip, then video_extension rather than one oversized prompt.
- Name every file by its beat's start timestamp: `00_00.mp4`, `00_07.mp4`, `00_16.mp4` into `outputs/`.
- Log actual credits spent per clip in `project.md` next to the estimate.

## STEP 7 - ASSEMBLE AND QC

1. Sort `outputs/` by filename. That is the edit order. Drop the sorted clips into any editor (CapCut works) in order. On the narrated path, assembly follows the STEP 3 pipeline: trim each clip to its exact audio segment, concat in filename order, duck the clips' ambience to ~30% volume, then lay the single VO track over the whole cut. The VO is the master clock — never re-pace it to fit the picture.
2. On the native-sound path, run the DE-SCORING pass before any music is added: Seedance will have baked a different score into every clip (it ignores "no music"), and per-clip scores reset at every cut. Separate each clip's audio with Demucs (free, local, ~5s/clip on CPU: `py -m demucs -n htdemucs <clip>.wav`), rebuild each clip keeping ONLY the vocals + drums stems (voices, giggles, splashes, transient SFX survive; melody and bass die). Know the tradeoff: tonal SFX — birdsong, crickets, chimes — travels with the music stem and is lost; re-add those from the editor's free SFX library. Then lay ONE continuous full-length music track under the whole cut, ~12 dB below the dialogue, faded in/out, and loudness-normalize the final mix (I=-16). Never loop a short isolated stem as the bed.
3. Captions and music are edit-stage decisions, not generation decisions. Keep captions in one consistent style; keep music under narration, never over it. Music sources that are safe for a monetized channel: YouTube Audio Library (free, zero-claim), Pixabay Music (free), or a paid AI-music tier (Suno/Udio — free tiers are non-commercial). The Higgsfield MCP cannot generate standalone music.
4. QC checklist, in this order, before calling it done:
   - Watch EVERY clip fully. Never ship a clip you have not watched to the end.
   - Hands, faces, physics: any glitch gets named, then regenerated or cut around.
   - Continuity: same character, same wardrobe, same light across beats. If one beat drifts, that beat is regenerated by pointing at the reference, not by re-describing.
   - Sound: levels consistent across clips; native-audio clips do not fight the music bed.
5. Final polish: after assembly and QC, offer a 1080p upscale of the finished film as the standard closing step. Upload the final mixed file, then `upscale_video` (provider bytedance, preset aigc, target 1080p, 24fps). It preserves the audio mix and costs ~0.02 cr/second (~1.3 cr for a 60s film — confirm the actual charge in `transactions` afterward; this tool has no cost preflight).
6. Close the project: final cost total in `project.md`, one line on what to do differently next video. The second video is where the studio gets fast.

## CREDIT DISCIPLINE (reference)

- Rates change. Pull live pricing at STEP 0; never trust remembered numbers, including numbers in this file.
- The cost order is stable even when prices move: stills are cheap, video seconds are expensive, resolution multiplies cost. Spend video credits on beats with essential motion; a still with a slow push covers low-motion beats for a fraction of the price.
- Generate clips at 480p and upscale ONLY the final assembled film once (STEP 7's final polish) — this delivers 1080p output at a fraction of the cost of generating every clip (and every retry) at 720p, whose per-second rate is 2.6x higher. 480p generation + single final upscale is the default economic strategy.
- Storyboards as grids, characters as single turnaround sheets, environments as single plates: one image each. This is where beginners accidentally spend 5x.
