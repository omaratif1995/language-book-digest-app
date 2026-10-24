#!/usr/bin/env python3
"""Course-level audio: plan every unit's clips, synthesize them once, build MP3 listening episodes.

    course_audio.py plan     --course course.json                         # no network: write plan.json, list missing clips
    course_audio.py synth    --course course.json --confirm-external-tts  # synthesize missing clips into the cache
    course_audio.py episodes --course course.json --confirm-external-tts  # one MP3 per unit (needs ffmpeg)

Clip ids use the same scheme as embed_audio.build_plan, so a cache filled by either tool serves both.
Hosted synthesis sends the selected learner text to the Edge TTS service: obtain the user's approval first.
See references/course-app.md for course.json and the listening design.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_audio import AudioError, Clip, build_plan, require, speakable, synthesize  # noqa: E402

DEFAULT_VOICE = "de-DE-SeraphinaMultilingualNeural"
SECTIONS = ("Wortschatz", "Grammatik", "Redemittel")
BYTES_PER_SECOND = 6000   # edge-tts delivers 48 kbit/s constant-bitrate MP3
STEP = 0.4                # silence granularity in seconds


def load_course(path):
    path = Path(path).resolve()
    course = json.loads(path.read_text(encoding="utf-8-sig"))
    base = path.parent
    require(isinstance(course.get("units"), list) and course["units"], "course.json needs a non-empty units list")
    course["title"] = course.get("title") or "Course"
    course["voice"] = course.get("voice") or DEFAULT_VOICE
    course["cache"] = (base / course.get("cache", "_work/audio")).resolve()
    course["episodes_dir"] = (base / course.get("episodes_dir", "Audio")).resolve()
    seen = set()
    for unit in course["units"]:
        for key in ("id", "label", "lesson", "sheet"):
            require(unit.get(key), f"unit is missing {key}: {unit}")
        require(re.fullmatch(r"[A-Za-z0-9_-]+", unit["id"]) is not None, f"unit id must be a simple token: {unit['id']}")
        require(unit["id"] not in seen, f"duplicate unit id {unit['id']}")
        seen.add(unit["id"])
        unit["lesson"] = (base / unit["lesson"]).resolve()
        unit["sheet"] = (base / unit["sheet"]).resolve()
        require(unit["lesson"].is_file(), f"lesson file not found: {unit['lesson']}")
        require(unit["sheet"].is_file(), f"sheet file not found: {unit['sheet']}")
    return course


def clip_id(text, voice):
    """Same id scheme as embed_audio.build_plan."""
    spoken = speakable(text)
    require(spoken, "empty audio text")
    return "a_" + hashlib.sha256((voice + "\0" + spoken).encode("utf-8")).hexdigest()[:20], spoken


def unit_plan(lesson, voice):
    """Full narration (episodes) plus the keys the app needs: German controls, grammar explanation, sections."""
    clips, sequence, controls = build_plan(lesson, voice)

    def add(text):
        cid, spoken = clip_id(text, voice)
        clips.setdefault(cid, Clip(cid, spoken, voice))
        return cid

    grammar = {}
    for record in lesson["grammar"]:
        grammar[record["id"]] = {
            "title": add(record["title"]),
            "meaning": add("Meaning. " + record["meaning"]),
            "rule": add("Rule. " + record["rule"]),
            "contrast": add("Important. " + record["contrast"]) if record.get("contrast") else None,
        }
    plan = {"title": add(lesson["title"]), "sections": {name: add(name) for name in SECTIONS},
            "sequence": sequence, "controls": controls, "grammar": grammar}
    return clips, plan


def build_course_plan(course):
    all_clips, units = {}, {}
    for unit in course["units"]:
        lesson = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))
        clips, plan = unit_plan(lesson, course["voice"])
        all_clips.update(clips)
        units[unit["id"]] = plan
    plan = {"voice": course["voice"], "units": units, "texts": {cid: clip.text for cid, clip in all_clips.items()}}
    course["cache"].mkdir(parents=True, exist_ok=True)
    (course["cache"] / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return all_clips, plan


def missing(course, clips):
    folder = course["cache"] / "clips"
    return [cid for cid in clips if not (folder / f"{cid}.mp3").is_file()]


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which("ffmpeg")
        require(found, "ffmpeg is required: install ffmpeg or `py -3 -m pip install imageio-ffmpeg`")
        return found


def silence(course, seconds, ff):
    steps = max(1, min(25, round(seconds / STEP)))
    path = course["cache"] / "silence" / f"s{steps:02d}.mp3"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", f"{steps * STEP:.1f}", "-c:a", "libmp3lame", "-b:a", "48k", "-ar", "24000", "-ac", "1",
                        "-write_xing", "0", str(path)], check=True)
    return path


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*!„“]', "", name).strip()


async def announcements(course):
    import edge_tts
    paths = {}
    for unit in course["units"]:
        path = course["cache"] / "intro" / f"{unit['id']}.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            await edge_tts.Communicate(f"{course['title']}. {unit['label']}.", course["voice"]).save(str(path))
        paths[unit["id"]] = path
    return paths


def build_episodes(course, plan):
    """Listening order of the sheet; after each German item a pause about as long as the clip, to repeat it."""
    ff = ffmpeg_exe()
    intros = asyncio.run(announcements(course))
    course["episodes_dir"].mkdir(parents=True, exist_ok=True)
    clips_dir, total = course["cache"] / "clips", 0.0
    for number, unit in enumerate(course["units"], 1):
        unit_plan_ = plan["units"][unit["id"]]
        repeat = {cid: (0.8 if key.endswith("-head") else 1.0) for key, cid in unit_plan_["controls"].items()}
        parts, seconds = [intros[unit["id"]], silence(course, 0.8, ff)], 3.0
        for cid in unit_plan_["sequence"]:
            clip = clips_dir / f"{cid}.mp3"
            require(clip.is_file(), f"missing clip {cid}: run `course_audio.py synth` first")
            length = clip.stat().st_size / BYTES_PER_SECOND
            gap = 1.2 if plan["texts"][cid] in SECTIONS else 0.4 + (length * repeat[cid] + 0.4 if cid in repeat else 0)
            parts += [clip, silence(course, gap, ff)]
            seconds += length + max(STEP, round(gap / STEP) * STEP)
        listing = course["cache"] / "episodes" / f"{unit['id']}.txt"
        listing.parent.mkdir(parents=True, exist_ok=True)
        listing.write_text("".join("file '" + p.as_posix().replace("'", "'\\''") + "'\n" for p in parts), encoding="utf-8")
        lesson_title = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))["title"]
        title = lesson_title if lesson_title.startswith(unit["label"]) else f"{unit['label']} – {lesson_title}"
        target = course["episodes_dir"] / safe_name(f"{number:02d} {title}.mp3")
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-id3v2_version", "3", "-metadata", f"title={title}",
                        "-metadata", f"album={course['title']} – Hören und Nachsprechen", "-metadata", f"artist={course['title']}",
                        "-metadata", f"track={number}/{len(course['units'])}", str(target)], check=True)
        total += seconds
        print(f"{target.name}: about {seconds / 60:.0f} min", flush=True)
    print(f"EPISODES: {len(course['units'])} files, about {total / 3600:.1f} hours of listening")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("plan", "synth", "episodes"))
    parser.add_argument("--course", required=True, type=Path)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--confirm-external-tts", action="store_true",
                        help="Confirm that the selected lesson text may be sent to the Edge TTS service")
    args = parser.parse_args(argv)
    try:
        course = load_course(args.course)
        clips, plan = build_course_plan(course)
        todo = missing(course, clips)
        print(f"PLAN: {len(clips)} unique clips for {len(course['units'])} units; {len(todo)} not yet synthesized; "
              f"voice={course['voice']}; cache={course['cache']}")
        if args.command == "plan":
            return 0
        require(args.confirm_external_tts, "Hosted synthesis sends lesson text externally; obtain approval and pass --confirm-external-tts")
        require(1 <= args.concurrency <= 8, "Concurrency must be from 1 to 8")
        if todo:
            asyncio.run(synthesize({cid: clips[cid] for cid in todo}, course["cache"] / "clips", args.concurrency))
        seconds = sum((course["cache"] / "clips" / f"{cid}.mp3").stat().st_size for cid in clips) / BYTES_PER_SECOND
        print(f"SYNTH: all {len(clips)} clips cached, about {seconds / 60:.0f} minutes of speech")
        if args.command == "episodes":
            build_episodes(course, plan)
        return 0
    except (AudioError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
