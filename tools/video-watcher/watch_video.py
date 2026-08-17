"""
video-watcher pipeline: URL -> frames, contact sheets, transcript, pacing, audio.

Everything up to analysis. The analysis procedure and the NOTES.md schema live in
ANALYSIS-GUIDE.md next to this file.

Local only: yt-dlp, ffmpeg, Python stdlib. No API keys, no accounts, no cookies,
no paid services. Nothing here reads a credential or a browser profile.

Every tunable lives in config.json (copy config.example.json). Paths resolve from
this file's own location, so the package works from any folder on any machine.

Windows-first but portable. All paths are pathlib objects passed to subprocess as
list args, so spaces in paths never touch a shell.
"""
import argparse
import csv
import json
import os
import re
import shutil
import statistics as st
import subprocess
import sys
from pathlib import Path

# ------------------------------------------------------------- locations ----
# <package root>/tools/video-watcher/watch_video.py
#   parents[0] == tools/video-watcher   (the tool)
#   parents[2] == the package root      (what gets uploaded)
TOOL_DIR = Path(__file__).resolve().parent
PKG_ROOT = Path(__file__).resolve().parents[2]

TAG = re.compile(r'<[^>]*>')
PTS = re.compile(r'pts_time:([0-9.]+)')
COLS, ROWS = 3, 3
CW, CH = 522, 294          # 3x3 -> 1566x882, long edge under 1568
PER = COLS * ROWS

# Candidate bold sans fonts, in order. First one that exists wins. Override with
# config.json "font_path" or the VIDEO_WATCHER_FONT environment variable.
FONT_CANDIDATES = [
    r'C:\Windows\Fonts\arialbd.ttf',
    r'C:\Windows\Fonts\segoeuib.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/Library/Fonts/Arial Bold.ttf',
]

DEFAULTS = {
    'output_root': 'video-research',
    'font_path': None,
    'credits': {
        'rates': {'still_image': None, 'short_clip_3s': None,
                  'clip_5s_720p': None, 'coded_template': 0},
        'budget_per_video': {'min': None, 'max': None},
        'unit_label': 'credits',
    },
    'detection': {
        'base_threshold': 0.20,
        'threshold_ladder': [0.15, 0.12],
        'secondary_threshold': 0.12,
        'merge_window': 1.0,
        'min_merged_per_min': 4.0,
        'band': [5.0, 30.0],
        'gap_limit': 15.0,
        'fill_every': 5.0,
        'dead_ssim': 0.97,
    },
    'download': {'max_height': 720},
}


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if k.startswith('_'):       # "_comment" keys are documentation, not config
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    """config.json if the user made one, otherwise config.example.json, otherwise
    the built-in defaults. Never fails on a fresh copy."""
    cfg, src = DEFAULTS, 'built-in defaults'
    for name in ('config.json', 'config.example.json'):
        p = TOOL_DIR / name
        if p.exists():
            try:
                cfg = deep_merge(DEFAULTS, json.loads(p.read_text(encoding='utf-8')))
                src = name
            except json.JSONDecodeError as e:
                sys.exit(f'FATAL: {p} is not valid JSON: {e}')
            break
    return cfg, src


CFG, CFG_SRC = load_config()
_D = CFG['detection']
BASE_THRESHOLD = float(_D['base_threshold'])
THRESHOLD_LADDER = [float(x) for x in _D['threshold_ladder']]
SECONDARY = float(_D['secondary_threshold'])
MERGE_WINDOW = float(_D['merge_window'])
MIN_MERGED_PER_MIN = float(_D['min_merged_per_min'])
BAND = tuple(float(x) for x in _D['band'])
GAP_LIMIT = float(_D['gap_limit'])
FILL_EVERY = float(_D['fill_every'])
DEAD_SSIM = float(_D['dead_ssim'])
MAX_HEIGHT = int(CFG['download']['max_height'])

FFMPEG = os.environ.get('VIDEO_WATCHER_FFMPEG') or 'ffmpeg'


def resolve_font():
    for cand in (os.environ.get('VIDEO_WATCHER_FONT'), CFG.get('font_path')):
        if cand and Path(cand).exists():
            return Path(cand)
    for cand in FONT_CANDIDATES:
        if Path(cand).exists():
            return Path(cand)
    return None


FONT = resolve_font()


def ff_escape(p):
    """ffmpeg's filter parser splits options on ':' and treats '\\' as an escape,
    so a path has to be normalised and its drive-letter colon escaped before it
    can go inside fontfile='...'."""
    return str(p).replace('\\', '/').replace(':', r'\:')


def mmss(s):
    return f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True,
                              errors='ignore', **kw)
    except subprocess.CalledProcessError as e:
        # Show the tool's real error, not a Python traceback.
        tail = [l for l in (e.stderr or e.stdout or '').strip().split('\n') if l.strip()]
        sys.exit('FATAL: yt-dlp failed.\n' + '\n'.join(tail[-6:] or ['(no output)']))


def ytdlp(args):
    """No cookies, no browser profile, no credentials - by design. Node is used
    as yt-dlp's JS runtime when it is installed, and skipped when it is not,
    rather than failing outright on a machine without it."""
    cmd = [sys.executable, '-m', 'yt_dlp']
    if shutil.which('node'):
        cmd += ['--js-runtimes', 'node']
    return cmd + args


def log(msg):
    print(msg, flush=True)


# -------------------------------------------------------------- preflight ----
def preflight(verbose=True):
    """Everything a fresh copy needs, checked in one place, with real fixes."""
    problems = []

    def ok(label, detail):
        if verbose:
            log(f'  OK   {label:<9} {detail}')

    v = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    if sys.version_info < (3, 8):
        problems.append(f'Python {v} is too old. Install Python 3.8 or newer.')
    else:
        ok('python', v)

    try:
        ok('yt-dlp', run([sys.executable, '-m', 'yt_dlp', '--version']).stdout.strip())
    except SystemExit:
        problems.append('yt-dlp is not installed. Fix:  py -m pip install -r "'
                        + str(TOOL_DIR / 'requirements.txt') + '"')

    if shutil.which(FFMPEG):
        first = subprocess.run([FFMPEG, '-version'], capture_output=True,
                               text=True, errors='ignore').stdout.split('\n')[0]
        ok('ffmpeg', first[:58])
    else:
        problems.append(
            'ffmpeg is not on PATH. Fix: install it (Windows: winget install '
            'Gyan.FFmpeg | macOS: brew install ffmpeg | Debian/Ubuntu: sudo apt '
            'install ffmpeg), or set VIDEO_WATCHER_FFMPEG to its full path.')

    if shutil.which('node'):
        ok('node', subprocess.run(['node', '--version'], capture_output=True,
                                  text=True, errors='ignore').stdout.strip())
    elif verbose:
        log('  WARN node      not found. yt-dlp usually works without it, but '
            'some videos need a JS runtime. Install Node if downloads fail.')

    if FONT:
        ok('font', str(FONT))
    elif verbose:
        log('  WARN font      no bold sans font found; sheet timestamps will use '
            "ffmpeg's default face. Set \"font_path\" in config.json to fix.")

    ok('config', CFG_SRC)
    return problems


# ------------------------------------------------------------- transcript ----
def ts_to_sec(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_vtt(path):
    """Line-based. Whitespace-only separators make blank-line splitting unsafe,
    and YouTube emits ~10ms 'settle' cues that duplicate the previous line."""
    lines = Path(path).read_text(encoding='utf-8', errors='ignore').split('\n')
    raw, cur = [], None
    for line in lines:
        if '-->' in line:
            if cur:
                raw.append(cur)
            a, rest = line.split('-->')
            cur = {'start': ts_to_sec(a.strip()),
                   'end': ts_to_sec(rest.strip().split(' ')[0]),
                   'body': []}
        elif cur is not None:
            t = TAG.sub('', line).strip()
            if t:
                cur['body'].append(t)
    if cur:
        raw.append(cur)

    cues = [(c['start'], c['body'][-1]) for c in raw
            if c['end'] - c['start'] >= 0.1 and c['body']]
    out, prev = [], None
    for start, text in cues:
        if text and text != prev:
            out.append((start, text))
            prev = text
    return out


# One English track is all the pipeline reads. A wildcard like 'en.*' also
# matches YouTube's auto-TRANSLATED tracks (en-ar, en-es, ...), which can be
# dozens of extra requests - enough to earn an HTTP 429 that kills the run
# after the track we actually wanted has already downloaded.
SUB_LANGS = 'en,en-orig,en-US,en-GB'
SUB_LANGS_FALLBACK = 'en.*'


def fetch_subs(d, url, langs, soft):
    args = ['--skip-download', '--write-auto-subs', '--write-subs',
            '--sub-langs', langs, '--sub-format', 'vtt', '--write-info-json',
            '--retries', '5', '--extractor-retries', '3',
            '-o', str(d / '%(id)s'), url]
    if soft:
        subprocess.run(ytdlp(args), capture_output=True, text=True, errors='ignore')
    else:
        run(ytdlp(args))


def step_transcript(d, url):
    subs = sorted(d.glob('*.en*.vtt'))
    info = next(iter(d.glob('*.info.json')), None)
    if not subs or not info:
        log('[1/6] transcript + metadata')
        # Narrow pass first, tolerant of failure. Only if it comes back with
        # nothing usable do we widen and let the real error through.
        fetch_subs(d, url, SUB_LANGS, soft=True)
        subs = sorted(d.glob('*.en*.vtt'))
        info = next(iter(d.glob('*.info.json')), None)
        if not subs or not info:
            log('   narrow caption pass incomplete - retrying wider')
            fetch_subs(d, url, SUB_LANGS_FALLBACK, soft=False)
            subs = sorted(d.glob('*.en*.vtt'))
            info = next(iter(d.glob('*.info.json')), None)
    else:
        log('[1/6] transcript + metadata (cached)')

    if not info:
        sys.exit('FATAL: no info JSON produced. Check the URL.')
    if not subs:
        sys.exit('FATAL: no English captions exist for this video. '
                 'Speech-to-text is not part of this pipeline. Stopping.')

    # Prefer the manual track over the auto one when both exist
    pick = next((s for s in subs if '.en.' in s.name), subs[0])
    cues = parse_vtt(pick)
    (d / 'data' / 'transcript.txt').write_text(
        '\n'.join(f'[{mmss(s)}] {t}' for s, t in cues), encoding='utf-8')

    j = json.loads(info.read_text(encoding='utf-8'))
    meta = {k: j.get(k) for k in
            ('id', 'title', 'channel', 'channel_follower_count', 'duration',
             'view_count', 'like_count', 'comment_count', 'upload_date',
             'webpage_url', 'description', 'thumbnail', 'tags', 'chapters',
             'fps', 'width', 'height')}
    meta['duration_mmss'] = mmss(j.get('duration') or 0)
    (d / 'data' / 'meta.json').write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')

    # Thumbnail is required by the packaging section of the schema
    thumb = d / 'data' / 'thumbnail.jpg'
    if meta.get('thumbnail') and not thumb.exists():
        try:
            import urllib.request
            urllib.request.urlretrieve(meta['thumbnail'], thumb)
        except Exception as e:
            log(f'   ! thumbnail download failed: {e}')

    words = sum(len(t.split()) for _, t in cues)
    dur = meta.get('duration') or 1
    log(f'   {len(cues)} cues, {words} words, {words / (dur / 60):.0f} wpm')
    return meta


# --------------------------------------------------------------- download ----
def find_source(d):
    """A finished source only. `.part` and `.ytdl` are yt-dlp's in-progress
    leftovers and must never be mistaken for a usable download."""
    return next((p for p in sorted(d.glob('source.*'))
                 if p.suffix.lower() not in ('.txt', '.json', '.part', '.ytdl')),
                None)


def source_still_needed(d):
    """The source is deleted once frames and audio succeed. On a re-run, only
    re-download if something that needs it is actually missing."""
    cuts = d / 'data' / 'cuts.csv'
    if not cuts.exists() or not (d / 'data' / 'loudness_m.txt').exists():
        return True
    rows = list(csv.DictReader(open(cuts, encoding='utf-8')))
    if not rows:
        return True
    return any(not (d / 'frames' /
                    f"{int(r['index']):03d}_{r['timestamp_mmss'].replace(':', '')}.jpg").exists()
               for r in rows)


def fetch_source(d, url, fmt, soft):
    args = ['-f', fmt, '--retries', '5', '--fragment-retries', '5',
            '--no-progress', '-o', str(d / 'source.%(ext)s'), url]
    if soft:
        subprocess.run(ytdlp(args), capture_output=True, text=True, errors='ignore')
    else:
        run(ytdlp(args))


def clear_partials(d):
    for p in d.glob('source.*'):
        if p.suffix.lower() in ('.part', '.ytdl'):
            p.unlink()


def step_download(d, url, no_download):
    src = find_source(d)
    if src:
        log(f'[2/6] source (cached: {src.name})')
        return src
    if not source_still_needed(d):
        log('[2/6] source not needed - frames and audio already complete')
        return None
    if no_download:
        sys.exit('FATAL: --no-download given but no source file found.')

    h = MAX_HEIGHT
    log(f'[2/6] downloading {h}p source')
    # Adaptive (separate video + audio) gives the resolution this pipeline wants.
    # It is also what YouTube 403s first on a throttled connection, so failure
    # here is common and is not fatal.
    fetch_source(d, url, f'bv*[height<={h}][vcodec!*=av01]+ba/bv*[height<={h}]+ba',
                 soft=True)
    src = find_source(d)
    stream = 'adaptive'

    if not src:
        # Progressive is one pre-muxed file. It always works when adaptive does
        # not, and on YouTube it tops out around 360p.
        clear_partials(d)
        log('   ! adaptive streams unavailable (HTTP 403 is the usual cause).')
        log('   ! falling back to a progressive stream - typically 360p.')
        fetch_source(d, url, f'b[height<={h}]/b', soft=False)
        src = find_source(d)
        stream = 'progressive'

    if not src:
        sys.exit('FATAL: download produced no source file.')

    # Resolution decides whether on-screen text is readable at all, so the
    # analysis has to know which stream it got rather than assume 720p.
    note = ('720p adaptive stream - on-screen text is readable at full frame '
            'resolution.' if stream == 'adaptive' else
            'PROGRESSIVE FALLBACK, typically 360p. On-screen text may be '
            'unreadable in the microscope pass. Say so in the notes rather '
            'than guessing at text you cannot actually read.')
    (d / 'data' / 'source_quality.json').write_text(
        json.dumps({'stream': stream, 'file': src.name,
                    'requested_max_height': h, 'note': note}, indent=2),
        encoding='utf-8')
    if stream == 'progressive':
        log(f'   ! {note}')
    return src


# ----------------------------------------------------------------- cuts ------
def detect(src, threshold, start, dur):
    cmd = [FFMPEG, '-hide_banner']
    if start:
        cmd += ['-ss', f'{start:.3f}']
    if dur:
        cmd += ['-t', f'{dur:.3f}']
    cmd += ['-i', str(src), '-filter:v',
            f"select='gt(scene,{threshold})',showinfo", '-f', 'null', '-']
    p = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    return sorted({round(float(m) + start, 3) for m in PTS.findall(p.stderr)})


def merge_shots(times, window=MERGE_WINDOW):
    """Collapse detections closer than `window`. High-motion animation trips
    scene detection repeatedly inside one continuous shot; merging is what
    turns raw detections into an honest shot count."""
    if not times:
        return []
    out = [times[0]]
    for t in times[1:]:
        if t - out[-1] >= window:
            out.append(t)
    return out


def ssim_pair(a, b):
    p = subprocess.run([FFMPEG, '-hide_banner', '-i', str(a), '-i', str(b),
                        '-lavfi', 'ssim', '-f', 'null', '-'],
                       capture_output=True, text=True, errors='ignore')
    m = re.search(r'All:([0-9.]+)', p.stderr)
    return float(m.group(1)) if m else None


def step_cuts(d, src, meta, threshold_override, start, end):
    duration = float(meta.get('duration') or 0)
    win_start = start or 0.0
    win_end = end if end else duration
    win_dur = win_end - win_start

    cuts_csv = d / 'data' / 'cuts.csv'
    if cuts_csv.exists():
        log('[3/6] cut detection (cached)')
        rows = list(csv.DictReader(open(cuts_csv, encoding='utf-8')))
        return json.loads((d / 'data' / 'pacing.json').read_text()), rows

    log('[3/6] cut detection')

    def pass_at(threshold):
        """Detect, then seed the opening frame before merging so raw and merged
        counts stay consistent. A hard cut at the window start is never detected."""
        r = detect(src, threshold, win_start, win_dur)
        if not r or r[0] > win_start + 1.0:
            r.insert(0, win_start)
        return r, merge_shots(r)

    tried = []
    if threshold_override:
        thr = threshold_override
        raw, merged = pass_at(thr)
        tried.append((thr, len(raw), len(merged)))
    else:
        thr = BASE_THRESHOLD
        raw, merged = pass_at(thr)
        tried.append((thr, len(raw), len(merged)))
        # Only lower if we are genuinely missing cuts. Never to hit a target.
        for nxt in THRESHOLD_LADDER:
            if len(merged) / (win_dur / 60) >= MIN_MERGED_PER_MIN:
                break
            log(f'   {len(merged) / (win_dur / 60):.1f} merged/min < '
                f'{MIN_MERGED_PER_MIN} -> retry at {nxt}')
            thr = nxt
            raw, merged = pass_at(thr)
            tried.append((thr, len(raw), len(merged)))

    # Cuts inside screen recordings score under the base threshold - window
    # chrome and background barely change across them - so those videos
    # under-count. Always compute the secondary reference now, while the source
    # still exists, so the analysis can report a range without re-downloading.
    if abs(thr - SECONDARY) < 1e-6:
        sec_merged = merged
    else:
        _, sec_merged = pass_at(SECONDARY)
    secondary = {'threshold': SECONDARY,
                 'merged_shots': len(sec_merged),
                 'merged_shots_per_min': round(len(sec_merged) / (win_dur / 60), 1)}

    shots = set(merged)

    # Uniform fill. Cut detection is blind to slow morphing motion graphics,
    # so long gaps are sampled densely rather than trusted as static.
    low_cut, filled = [], list(merged)
    bounds = merged + [win_end]
    for a, b in zip(bounds, bounds[1:]):
        if b - a > GAP_LIMIT:
            low_cut.append([a, b])
            t = a + FILL_EVERY
            while t < b - 1.0:
                filled.append(round(t, 3))
                t += FILL_EVERY
    filled = sorted(set(filled))

    with open(cuts_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['index', 'timestamp_sec', 'timestamp_mmss', 'source'])
        for i, t in enumerate(filled, 1):
            w.writerow([i, f'{t:.3f}', mmss(t), 'shot' if t in shots else 'fill'])
    rows = list(csv.DictReader(open(cuts_csv, encoding='utf-8')))

    per_min = len(merged) / (win_dur / 60)
    gaps = [b - a for a, b in zip(merged, merged[1:])]
    pacing = {
        'threshold_used': thr,
        'threshold_attempts': [{'threshold': t, 'raw': r, 'merged': m} for t, r, m in tried],
        'window': [win_start, win_end],
        'raw_detections': len(raw),
        'merged_shots': len(merged),
        'merged_shots_per_min': round(per_min, 1),
        'raw_detections_per_min': round(len(raw) / (win_dur / 60), 1),
        'secondary_low_threshold': secondary,
        'in_band': BAND[0] <= per_min <= BAND[1],
        'band': list(BAND),
        'median_shot_sec': round(st.median(gaps), 2) if gaps else None,
        'mean_shot_sec': round(st.mean(gaps), 2) if gaps else None,
        'longest_shot_sec': round(max(gaps), 1) if gaps else None,
        'total_frames': len(filled),
        'fill_frames': len(filled) - len(merged),
        'low_cut_sections': [],
    }
    buckets = {}
    for t in merged:
        buckets[int((t - win_start) // 60)] = buckets.get(int((t - win_start) // 60), 0) + 1
    praw = {}
    for t in raw:
        praw[int((t - win_start) // 60)] = praw.get(int((t - win_start) // 60), 0) + 1
    pacing['buckets'] = [
        {'bucket': f'{mmss(win_start + b * 60)}-{mmss(min(win_start + (b + 1) * 60, win_end))}',
         'merged': buckets.get(b, 0), 'raw': praw.get(b, 0)}
        for b in range(int(win_dur // 60) + 1)]
    pacing['low_cut_raw'] = low_cut
    (d / 'data' / 'pacing.json').write_text(json.dumps(pacing, indent=2), encoding='utf-8')

    log(f'   threshold {thr}  raw {len(raw)}  merged {len(merged)} '
        f'({per_min:.1f}/min)  fills {len(filled) - len(merged)}  total {len(filled)}')
    log(f'   {SECONDARY} reference: {secondary["merged_shots"]} merged '
        f'({secondary["merged_shots_per_min"]}/min) - use as the upper end of the '
        f'range if section 7 shows this is screen-recording heavy')
    if not pacing['in_band']:
        log(f'   ! OUTSIDE BAND {BAND[0]}-{BAND[1]} merged/min. Reported, not chased.')
    return pacing, rows


def classify_low_cut(d, pacing, rows):
    """A low-cut section is only a true dead zone if its fill frames come back
    visually near-identical. Otherwise it is dense animation the detector
    cannot see, which is the opposite of dead."""
    if not pacing.get('low_cut_raw'):
        (d / 'data' / 'low_cut_sections.csv').write_text(
            'start_sec,end_sec,start_mmss,end_mmss,length_sec,mean_ssim,verdict\n',
            encoding='utf-8')
        return
    frames = d / 'frames'
    out = []
    for a, b in pacing['low_cut_raw']:
        inside = [r for r in rows if a <= float(r['timestamp_sec']) <= b]
        paths = [frames / f"{int(r['index']):03d}_{r['timestamp_mmss'].replace(':', '')}.jpg"
                 for r in inside]
        paths = [p for p in paths if p.exists()]
        scores = [s for s in (ssim_pair(x, y) for x, y in zip(paths, paths[1:]))
                  if s is not None]
        mean = round(st.mean(scores), 4) if scores else None
        verdict = ('dead zone' if mean is not None and mean >= DEAD_SSIM
                   else 'low-cut, visually active')
        out.append([f'{a:.3f}', f'{b:.3f}', mmss(a), mmss(b), f'{b - a:.1f}',
                    mean if mean is not None else '', verdict])
    with open(d / 'data' / 'low_cut_sections.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['start_sec', 'end_sec', 'start_mmss', 'end_mmss',
                    'length_sec', 'mean_ssim', 'verdict'])
        w.writerows(out)
    pacing['low_cut_sections'] = [
        {'start_mmss': r[2], 'end_mmss': r[3], 'length_sec': float(r[4]),
         'mean_ssim': r[5], 'verdict': r[6]} for r in out]
    pacing.pop('low_cut_raw', None)
    (d / 'data' / 'pacing.json').write_text(json.dumps(pacing, indent=2), encoding='utf-8')
    for r in out:
        log(f'   {r[2]}-{r[3]} ({r[4]}s) ssim={r[5]} -> {r[6]}')


# --------------------------------------------------------------- frames ------
def step_frames(d, src, rows):
    frames = d / 'frames'
    frames.mkdir(exist_ok=True)
    made = skipped = 0
    for r in rows:
        t = float(r['timestamp_sec'])
        seek = t + 0.10 if r['source'] == 'shot' else t
        out = frames / f"{int(r['index']):03d}_{r['timestamp_mmss'].replace(':', '')}.jpg"
        if out.exists() and out.stat().st_size > 0:
            skipped += 1
            continue
        subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error',
                        '-ss', f'{seek:.3f}', '-i', str(src),
                        '-frames:v', '1', '-q:v', '3', '-y', str(out)], check=True)
        made += 1
    log(f'[4/6] frames: {made} new, {skipped} reused, {len(rows)} total')
    return made + skipped == len(rows)


# --------------------------------------------------------------- sheets ------
def esc(s):
    return s.replace(':', r'\:')


def step_sheets(d, rows):
    sheets = d / 'sheets'
    sheets.mkdir(exist_ok=True)
    frames = d / 'frames'
    files = []
    for r in rows:
        p = frames / f"{int(r['index']):03d}_{r['timestamp_mmss'].replace(':', '')}.jpg"
        if p.exists():
            files.append((p, int(r['index']), r['timestamp_mmss'], r['source']))

    # The timestamp burned into every cell is what makes a sheet referenceable.
    # A missing font must not take the sheets down with it.
    face = f"fontfile='{ff_escape(FONT)}'" if FONT else "font='Sans'"

    n = (len(files) + PER - 1) // PER
    index_rows = []
    for s in range(n):
        out = sheets / f'sheet_{s + 1:03d}.jpg'
        chunk = files[s * PER:(s + 1) * PER]
        index_rows.append([out.name, f'{chunk[0][2]}-{chunk[-1][2]}',
                           ' '.join(f'{i:03d}={t}' for _, i, t, _ in chunk)])
        if out.exists() and out.stat().st_size > 0:
            continue
        cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error']
        for p, _, _, _ in chunk:
            cmd += ['-i', str(p)]
        for _ in range(PER - len(chunk)):
            cmd += ['-f', 'lavfi', '-i', f'color=c=#101010:s={CW}x{CH}']
        parts = []
        for i in range(PER):
            if i < len(chunk):
                _, idx, ts, srctype = chunk[i]
                tag = f'{idx:03d}  {ts}' + ('  ~' if srctype == 'fill' else '')
                parts.append(
                    f'[{i}:v]scale={CW}:{CH}:force_original_aspect_ratio=decrease,'
                    f'pad={CW}:{CH}:(ow-iw)/2:(oh-ih)/2:color=#101010,'
                    f"drawtext={face}:text='{esc(tag)}':fontcolor=white:"
                    f'fontsize=21:box=1:boxcolor=black@0.65:boxborderw=5:x=7:y=7[v{i}]')
            else:
                parts.append(f'[{i}:v]scale={CW}:{CH}[v{i}]')
        layout = '|'.join(f'{(i % COLS) * CW}_{(i // COLS) * CH}' for i in range(PER))
        fc = ';'.join(parts) + ';' + ''.join(f'[v{i}]' for i in range(PER)) + \
            f'xstack=inputs={PER}:layout={layout}[out]'
        cmd += ['-filter_complex', fc, '-map', '[out]', '-frames:v', '1',
                '-q:v', '3', '-y', str(out)]
        subprocess.run(cmd, check=True)
    with open(d / 'data' / 'sheet_index.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['sheet', 'span_mmss', 'cells'])
        w.writerows(index_rows)
    log(f'[5/6] sheets: {n} from {len(files)} frames')


# ---------------------------------------------------------------- audio ------
def step_audio(d, src, rows, start, end):
    mfile = d / 'data' / 'loudness_m.txt'
    if not mfile.exists():
        cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error']
        if start:
            cmd += ['-ss', f'{start:.3f}']
        if end:
            cmd += ['-t', f'{end - (start or 0):.3f}']
        # ffmpeg's filter parser splits options on ':', so an absolute path with
        # a drive letter cannot go in file=. Run from data/ and use a bare name.
        cmd += ['-i', str(src), '-af',
                'ebur128=metadata=1,ametadata=print:key=lavfi.r128.M:file=loudness_m.txt',
                '-f', 'null', '-']
        subprocess.run(cmd, check=True, cwd=str(d / 'data'))
    if not mfile.exists() or mfile.stat().st_size == 0:
        log('[6/6] audio: ebur128 produced nothing')
        return False

    off = start or 0.0
    txt = mfile.read_text(errors='ignore').split('\n')
    samples, t = [], None
    for line in txt:
        m = re.match(r'frame:\d+\s+pts:\S+\s+pts_time:([0-9.]+)', line)
        if m:
            t = float(m.group(1)) + off
            continue
        m = re.match(r'lavfi\.r128\.M=(-?[0-9.]+)', line)
        if m and t is not None:
            samples.append((t, max(float(m.group(1)), -70.0)))
            t = None
    if not samples:
        return False

    per_sec = {}
    for tt, v in samples:
        per_sec.setdefault(int(tt), []).append(v)
    curve = [(s, round(st.mean(vs), 2)) for s, vs in sorted(per_sec.items())]
    with open(d / 'data' / 'audio_energy.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['timestamp_sec', 'lufs'])
        w.writerows(curve)

    vals = [v for _, v in curve]
    med = st.median(vals)
    lut = dict(curve)

    # Risers: smoothed rise to a high peak, landing in near-silence. Speech
    # alone swings several LU per second, so an unsmoothed test fires constantly.
    sm = []
    for i, (s_, _) in enumerate(curve):
        win = [v for _, v in curve[max(0, i - 1):i + 2]]
        sm.append((s_, st.mean(win)))
    risers, i = [], 1
    while i < len(sm) - 3:
        j = i
        while j < len(sm) - 1 and sm[j + 1][1] >= sm[j][1] - 0.3:
            j += 1
        rise_len, rise_amt = sm[j][0] - sm[i][0], sm[j][1] - sm[i][1]
        if rise_len >= 2 and rise_amt >= 5 and sm[j][1] >= med + 1.5:
            after = [v for s_, v in sm if sm[j][0] < s_ <= sm[j][0] + 3]
            if after and min(after) <= med - 4 and sm[j][1] - min(after) >= 6:
                risers.append({'peak_mmss': mmss(sm[j][0]),
                               'rise_lu': round(rise_amt, 1),
                               'drop_lu': round(sm[j][1] - min(after), 1)})
            i = j + 1
            continue
        i = j + 1 if j > i else i + 1

    raw = {round(tt, 1): v for tt, v in samples}

    def swing(tt):
        a, b = raw.get(round(tt - 0.4, 1)), raw.get(round(tt + 0.4, 1))
        return abs(b - a) if a is not None and b is not None else None

    base = [x for x in (swing(round(tt, 1)) for tt, _ in samples) if x is not None]
    all_delta = st.mean(base) if base else 0.0
    shots = [r for r in rows if r['source'] == 'shot']
    cd, aligned = [], []
    for r in shots:
        tt = float(r['timestamp_sec'])
        dv = swing(round(tt, 1))
        if dv is not None:
            cd.append(dv)
        aligned.append([r['index'], f'{tt:.3f}', r['timestamp_mmss'],
                        lut.get(int(tt), ''), round(dv, 2) if dv is not None else ''])
    with open(d / 'data' / 'audio_cuts_aligned.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['index', 'timestamp_sec', 'timestamp_mmss', 'lufs', 'abs_delta_lufs'])
        w.writerows(aligned)
    ratio = (st.mean(cd) / all_delta) if cd and all_delta else 0.0

    runs, cur = [], None
    for s_, v in curve:
        lab = 'low' if v < med - 3 else ('high' if v > med + 2 else 'mid')
        if cur and cur['label'] == lab:
            cur['end'] = s_
        else:
            if cur and cur['end'] - cur['start'] >= 5:
                runs.append(cur)
            cur = {'label': lab, 'start': s_, 'end': s_}
    if cur and cur['end'] - cur['start'] >= 5:
        runs.append(cur)

    summary = {
        'risers': risers,
        'beat_alignment_ratio': round(ratio, 2),
        'beat_verdict': ('cuts land on loudness inflections (beat-cut)' if ratio >= 1.35
                         else 'cuts are NOT loudness-aligned' if ratio <= 1.1
                         else 'weak / partial alignment'),
        'energy_runs': [{'label': r['label'], 'start_mmss': mmss(r['start']),
                         'end_mmss': mmss(r['end']), 'len_sec': r['end'] - r['start']}
                        for r in runs if r['label'] != 'mid'],
    }
    (d / 'data' / 'audio_summary.json').write_text(
        json.dumps(summary, indent=2), encoding='utf-8')
    log(f'[6/6] audio: {len(risers)} risers, beat ratio {ratio:.2f} '
        f'-> {summary["beat_verdict"]}')
    return True


# ----------------------------------------------------------------- main ------
def slugify(s):
    s = re.sub(r'[^a-zA-Z0-9]+', '-', (s or '').lower()).strip('-')
    return '-'.join(s.split('-')[:7]) or 'video'


def resolve_root(arg_root):
    """Precedence: --root, then VIDEO_WATCHER_ROOT, then config output_root.
    A relative value resolves against the package root, never the working
    directory, so the same command works from anywhere."""
    val = arg_root or os.environ.get('VIDEO_WATCHER_ROOT') or CFG['output_root']
    p = Path(val)
    return p.resolve() if p.is_absolute() else (PKG_ROOT / p).resolve()


def main():
    ap = argparse.ArgumentParser(
        description='Video -> frames, sheets, transcript, pacing, audio.')
    ap.add_argument('url', nargs='?', help='YouTube URL')
    ap.add_argument('--slug', help='folder name (default: derived from title)')
    ap.add_argument('--root', default=None,
                    help='output root; a relative path resolves against the '
                         f'package root (default: {CFG["output_root"]})')
    ap.add_argument('--start', type=float, help='analyse from this second')
    ap.add_argument('--end', type=float, help='analyse until this second')
    ap.add_argument('--hook-only', action='store_true', help='first 60s only, dense')
    ap.add_argument('--threshold', type=float, help='override scene threshold')
    ap.add_argument('--no-download', action='store_true', help='reuse existing source')
    ap.add_argument('--keep-source', action='store_true', help='do not delete source when done')
    ap.add_argument('--check', action='store_true',
                    help='check that everything is installed, then exit')
    a = ap.parse_args()

    if a.check:
        log('preflight:')
        problems = preflight()
        if problems:
            log('\nNOT READY:')
            for p in problems:
                log(f'  - {p}')
            sys.exit(1)
        log('\nReady. Try:  py "tools/video-watcher/watch_video.py" "<URL>" --hook-only')
        return

    problems = preflight(verbose=False)
    if problems:
        sys.exit('FATAL: the pipeline is missing something it needs.\n  - '
                 + '\n  - '.join(problems)
                 + '\nRun with --check for the full report.')

    if not a.url and not a.slug:
        sys.exit('FATAL: give a URL (or --slug to resume an existing folder).')

    start, end = a.start, a.end
    if a.hook_only:
        start, end = 0.0, 60.0

    root = resolve_root(a.root)
    # The tool folder ships the tool and nothing else. Analysis output is bulky
    # and disposable; it never belongs among the source files.
    if root == TOOL_DIR or TOOL_DIR in root.parents:
        sys.exit(f'FATAL: --root {root} is inside the tool folder ({TOOL_DIR}).\n'
                 f'Point it at a project folder instead, e.g. '
                 f'--root "my-video/research/watcher".')
    created = not root.exists()
    root.mkdir(parents=True, exist_ok=True)
    if created:
        log(f'created output root {root}')

    # A fresh copy has no live index. Seed it from the template that ships here.
    index = root / 'INDEX.md'
    tmpl = TOOL_DIR / 'INDEX.template.md'
    if not index.exists() and tmpl.exists():
        txt = re.sub(r'\nScaffold only\..*?\n\n', '\n',
                     tmpl.read_text(encoding='utf-8'), flags=re.S)
        index.write_text(txt, encoding='utf-8')
        log(f'seeded {index} from INDEX.template.md')

    slug = a.slug
    if not slug:
        t = run(ytdlp(['--skip-download', '--print', '%(title)s', a.url])).stdout.strip()
        slug = slugify(t.split('\n')[-1])
    d = root / slug
    for sub in ('frames', 'sheets', 'data'):
        (d / sub).mkdir(parents=True, exist_ok=True)
    log(f'== {slug}\n== {d}')

    # The analysis step prices things in credits. Rates and budget belong to
    # whoever is running this, not to the tool, so they travel with the run
    # instead of being baked into the instructions.
    (d / 'data' / 'cost_config.json').write_text(
        json.dumps(CFG['credits'], indent=2), encoding='utf-8')

    meta = step_transcript(d, a.url)
    src = step_download(d, a.url, a.no_download)
    if a.hook_only:
        log('   --hook-only: analysing 0:00-1:00')

    pacing, rows = step_cuts(d, src, meta, a.threshold, start, end)
    frames_ok = step_frames(d, src, rows)
    classify_low_cut(d, pacing, rows)
    step_sheets(d, rows)
    audio_ok = step_audio(d, src, rows, start, end)

    if src and src.exists():
        if frames_ok and audio_ok and not a.keep_source:
            size = src.stat().st_size / 1e6
            src.unlink()
            log(f'   source deleted ({size:.0f} MB) - frames and audio both succeeded')
        elif not a.keep_source:
            log('   source KEPT - a step did not fully succeed')

    log('\n---- READY FOR ANALYSIS ----')
    log(f'sheets  : {d / "sheets"}')
    log(f'frames  : {d / "frames"}')
    log(f'data    : {d / "data"}')
    log(f'pacing  : merged {pacing["merged_shots"]} shots, '
        f'{pacing["merged_shots_per_min"]}/min '
        f'(raw detections {pacing["raw_detections"]})')
    if not pacing['in_band']:
        log(f'          OUTSIDE band {BAND[0]}-{BAND[1]}/min - report it, do not chase it')
    log(f'next    : follow {TOOL_DIR / "ANALYSIS-GUIDE.md"}')


if __name__ == '__main__':
    main()
