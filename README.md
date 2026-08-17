# Faceless Studio

**Turn one idea into a finished faceless video, without a camera, a crew, or knowing how to edit.**

This is a Claude Code *skill* — a set of instructions Claude follows so it can act like a whole video
studio. You bring a topic. Claude does the research, writes the script, breaks it into beats, designs
the characters and the world, storyboards it, writes every prompt, and generates the clips with
sound. You approve things along the way. At the end you have a folder of numbered video files that
play in order.

You do not need to know how to code. You will type sentences to Claude and click Yes.

---

## Before you start

Three things. Two are free.

### 1. Claude Code

The app that runs this. Install it from **[claude.com/code](https://claude.com/code)** — there's a
desktop app for Mac and Windows, which is the easiest way in.

Sign in with your Claude account. A paid plan is required to do real work; see
[Costs](#what-this-costs) below.

### 2. Higgsfield, connected as a Connector

This is what actually generates the video. Everything in this skill runs through it.

1. Make an account at **[higgsfield.ai](https://higgsfield.ai)** and buy credits. Credits are how
   generation is paid for — a short first video runs somewhere around 150 of them.
2. In Claude Code, open **Settings → Connectors**, find **Higgsfield**, and connect it.
3. That's it. If Claude says it can't reach Higgsfield when you start, this is the step that didn't
   take — go back and reconnect.

### 3. Python 3

**Only needed for the optional watcher tool** at the bottom of this page. If you skip the watcher,
skip this too — the skill works completely without it.

Check whether you already have it. Open a terminal and type:

```bash
py --version
```

If that prints something like `Python 3.12.2`, you're done. If it says the command isn't found,
install it from **[python.org/downloads](https://www.python.org/downloads/)** — on Windows, tick
**"Add Python to PATH"** on the first screen of the installer.

---

## Setup

**1. Download this folder.** On the GitHub page, click the green **Code** button → **Download ZIP**.
Unzip it somewhere you'll find again — Documents is fine. You should end up with a folder called
`faceless-studio` containing `README.md`, `.claude`, and `tools`.

**2. Open that folder in Claude Code.** In the desktop app, use **Open Folder** and pick
`faceless-studio` itself — not the folder above it, not a folder inside it. Claude reads the skill
from `.claude/skills/`, so opening the wrong level means the skill never loads.

**3. Check the skill loaded.** Type `/` in the message box. You should see **`/faceless-studio`** in
the list. If you don't, you opened the wrong folder — go back to step 2.

That's the whole setup. Nothing to install, nothing to configure.

---

## Start

Type this as your first message:

```
/faceless-studio I want to make my first faceless video.
```

That's it. Claude takes it from there.

It will ask you a small number of questions — never more than three at a time — and propose one
concrete option rather than a menu. You can always overrule it. **You will be shown a full cost
estimate and asked to approve it before a single credit is spent.**

If you already know your topic, say so up front and you'll skip a round:

```
/faceless-studio I want to make a 30-second faceless video about deep-sea creatures.
```

### What happens, in order

| Step | What Claude does | What you do |
|---|---|---|
| 0 | Checks Higgsfield is connected and looks up today's live prices | nothing |
| 1 | Researches 2–3 videos that are already winning in your niche | paste 2–3 links, or let Claude propose them |
| 2 | Writes the concept, the script, and the beat sheet | approve the concept, then the beat sheet |
| 3 | Picks how sound works — usually generated with the video | nothing |
| 4 | Designs your characters and locations as reference images | approve the look |
| 5 | Draws the whole video as one storyboard grid | approve the board (changes here are nearly free) |
| 6 | Writes every prompt, shows the full bill, then generates | **approve the total**, then wait |
| 7 | Sorts the clips and checks every one for glitches | watch them |

You end up with a folder called `outputs/` full of clips named by their timestamp — `00_00.mp4`,
`00_07.mp4`, `00_16.mp4`. Drag them into any editor (CapCut is free) in that order and they're
already in sequence. That naming is doing most of the editing work for you.

---

## What this costs

Being straight with you about this, because there are two separate meters running.

**Higgsfield credits — the real money.** Every generated image and every second of generated video
costs credits, which you buy from Higgsfield. A first 30–60 second video targets **150 credits or
less**. Claude looks up live prices at the start and shows you a full itemised estimate before
generating anything. Nothing gets made without you approving that number.

**Your Claude plan — the other meter.** Everything Claude does here consumes usage on whatever plan
you're on. Planning, scripting and storyboarding are cheap. The optional watcher below is the one
genuinely expensive part, and it's covered in its own section.

**The tools in this repo cost nothing.** They're local Python and ffmpeg. They call no paid API and
hold no account of their own.

---

## Optional: the video watcher

**Everything above works without this. It is an upgrade, not a requirement.**

Lives in [`tools/video-watcher/`](tools/video-watcher/). It's a local tool that pulls a YouTube video
apart — one frame per shot, contact sheets with timestamps burned in, the transcript, cut pacing, an
audio energy curve — so that Claude can actually *look at* a video instead of guessing from its
transcript.

**What it changes.** Only STEP 1, the research step. Without it, Claude reads what it can find about
your reference videos and infers the rest, marking what was inferred. With it, Claude measures: the
real hook beat by beat, the real cut rate, the real on-screen typography. Everything downstream —
script, beat sheet, the LOOK that governs every image — is built on that research, so better
research is worth something. Every other step is byte-for-byte identical either way.

**To enable it:**

```bash
py -m pip install -r "tools/video-watcher/requirements.txt"
```

You also need **ffmpeg**, which pip can't install:

- Windows: `winget install Gyan.FFmpeg`
- macOS: `brew install ffmpeg`
- Debian/Ubuntu: `sudo apt install ffmpeg`

Then confirm everything is in place:

```bash
py "tools/video-watcher/watch_video.py" --check
```

Green across the board means Claude will use it automatically at STEP 1. You don't have to run it
yourself or ask for it. If anything is missing or broken, Claude says so in one line and falls back
to the normal research path — it never stops or nags you about it.

**What it honestly costs.** No API, no keys, no account, no subscription — it's ffmpeg and yt-dlp
running on your machine against public video. What it does cost is **your Claude usage**, because
analysis means Claude reading a large number of images:

| Run | Rough cost |
|---|---|
| The 60-second hook read the skill uses, per video | ~15–25K tokens of images |
| Three reference videos, i.e. one full research step | ~50–75K tokens |
| A complete teardown of one 8–10 minute video | ~150–250K tokens |

On a paid Claude plan a research step is a noticeable but ordinary chunk of a session. A full
teardown is a whole session on its own. If you're watching your usage, skip the watcher — the
default path costs a fraction of this and the skill is built to work well on it.

Full details in **[`tools/video-watcher/README.md`](tools/video-watcher/README.md)**.

---

## If something goes wrong

| Problem | Fix |
|---|---|
| `/faceless-studio` doesn't appear when you type `/` | You opened the wrong folder. Open `faceless-studio` itself — the one with `README.md` in it. |
| "Higgsfield is not connected" | Settings → Connectors → Higgsfield → connect. Then send your message again. |
| `py` isn't recognised | Python isn't installed, or wasn't added to PATH. Reinstall from python.org and tick **Add Python to PATH**. Only matters for the watcher. |
| `--check` complains about ffmpeg | Install it with the command for your OS above, then close and reopen your terminal so it picks up the new PATH. |
| A generated clip has warped hands or broken physics | Expected sometimes. Claude flags these before you do and offers the two real fixes: regenerate that beat, or cut around it. |
| The background music changes at every cut | Expected — Seedance bakes a different score into every clip even when told not to. Claude strips it with a free local tool (Demucs) keeping voices and sound effects, then one continuous music track goes under the whole film in the edit. |
| It's costing more credits than estimated | Stop and say so. Claude logs every credit spent in `project.md` next to the estimate, so the gap is visible and can be traced. |

---

## What's in here

```
faceless-studio/
├── README.md                              this file
├── .claude/skills/faceless-studio/
│   └── SKILL.md                           the studio itself - what Claude follows
└── tools/video-watcher/                   optional research tool
    ├── README.md                          how to install and run it
    ├── ANALYSIS-GUIDE.md                  what Claude does with a completed run
    ├── METHOD.md                          why it works the way it does
    ├── watch_video.py                     the pipeline
    ├── requirements.txt
    ├── config.example.json                copy to config.json to set your own rates
    ├── .env.example                       optional machine paths. No credentials exist.
    └── INDEX.template.md
```

Your video projects get created as new folders next to this README, one per video. Everything heavy
inside them — generated clips, character sheets, storyboards, downloaded video, watcher frames — is
gitignored, so nothing large or private ends up in version control. Your written work (the script,
the research notes, `project.md`) is plain text and stays visible, which is usually what you want.
