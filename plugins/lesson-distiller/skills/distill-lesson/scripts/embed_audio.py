#!/usr/bin/env python3
"""Embed clear neural lesson audio and playback controls in a study-sheet copy.

The script sends the lesson's selected learner text to the configured Edge TTS
service during synthesis. It therefore requires an explicit confirmation flag.
The output itself is a single offline HTML file with no external media URLs.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass
import hashlib
import html
import json
from pathlib import Path
import re
import sys


class AudioError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AudioError(message)


def esc(value):
    return html.escape(str(value), quote=True)


def speakable(value):
    """Turn visual lesson notation into text a voice can read naturally."""
    text = str(value).strip()
    substitutions = (
        ("…", " "), ("...", " "), ("·", ". "), ("→", " wird zu "),
        (" + ", ", "), (" / ", " oder "), ("Akk.", "Akkusativ"),
        ("Dat.", "Dativ"), ("Nom.", "Nominativ"), ("Partizip II", "Partizip zwei"),
    )
    for old, new in substitutions:
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = re.sub(r"(?:,\s*){2,}", ", ", text).strip(" ,")
    return text


@dataclass(frozen=True)
class Clip:
    clip_id: str
    text: str
    voice: str


def build_plan(lesson, voice):
    clips = {}
    sequence = []
    controls = {}

    def add(value, control=None):
        text = speakable(value)
        require(text, f"Empty audio text for {control or 'sequence item'}")
        digest = hashlib.sha256((voice + "\0" + text).encode("utf-8")).hexdigest()[:20]
        clip_id = "a_" + digest
        clips.setdefault(clip_id, Clip(clip_id, text, voice))
        sequence.append(clip_id)
        if control:
            require(control not in controls, f"Duplicate audio control {control}")
            controls[control] = clip_id
        return clip_id

    add(lesson["title"])
    add("Wortschatz")
    previous = None
    for record in lesson["vocabulary"]:
        if record["group"] != previous:
            add(record["group"])
            previous = record["group"]
        head = ((record.get("article", "") + " ") if record.get("article") else "") + record["lemma"]
        add(head, f'{record["id"]}-head')
        add(record["gloss"])
        if record.get("forms", "").strip():
            add(record["forms"])
        for index, example in enumerate(record["examples"]):
            add(example["de"], f'{record["id"]}-ex-{index}')
            add(example["en"])

    add("Grammatik")
    for record in lesson["grammar"]:
        add(record["title"], f'{record["id"]}-head')
        add("Meaning. " + record["meaning"])
        add("Rule. " + record["rule"])
        for pattern in record["patterns"]:
            add(pattern["label"] + ". " + pattern["form"])
        if record.get("contrast"):
            add("Important. " + record["contrast"])
        for index, example in enumerate(record["examples"]):
            add(example["de"], f'{record["id"]}-ex-{index}')
            add(example["en"])

    add("Redemittel")
    previous = None
    for record in lesson["redemittel"]:
        if record["group"] != previous:
            add(record["group"])
            previous = record["group"]
        add(record["frame"], f'{record["id"]}-head')
        add(record["gloss"])
        add(record["when"] + ((". " + record["register"]) if record.get("register") else ""))
        for index, variant in enumerate(record.get("variants", [])):
            add(variant["form"], f'{record["id"]}-variant-{index}')
            add(variant["usage"])
        for index, example in enumerate(record["examples"]):
            add(example["de"], f'{record["id"]}-ex-{index}')
            add(example["en"])
    return clips, sequence, controls


async def synthesize(clips, cache_dir, concurrency=4):
    try:
        import edge_tts
    except ImportError as error:
        raise AudioError("edge-tts is required: py -3 -m pip install --user edge-tts") from error

    cache_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    async def one(clip):
        path = cache_dir / f"{clip.clip_id}.mp3"
        if path.exists() and path.stat().st_size > 256:
            return path
        async with semaphore:
            last_error = None
            for attempt in range(3):
                try:
                    temporary = path.with_suffix(f".attempt-{attempt}.mp3")
                    if temporary.exists():
                        temporary.unlink()
                    await edge_tts.Communicate(text=clip.text, voice=clip.voice).save(str(temporary))
                    require(temporary.exists() and temporary.stat().st_size > 256,
                            f"TTS returned empty audio for {clip.clip_id}")
                    temporary.replace(path)
                    return path
                except Exception as error:  # provider/network errors vary by release
                    last_error = error
                    await asyncio.sleep(0.75 * (attempt + 1))
            raise AudioError(f"TTS failed for {clip.clip_id}: {last_error}")

    paths = await asyncio.gather(*(one(clip) for clip in clips.values()))
    return {clip_id: path for clip_id, path in zip(clips, paths)}


def play_button(clip_id, label="Play audio"):
    return (f'<button type="button" class="speak-button" data-audio="{esc(clip_id)}" '
            f'aria-label="{esc(label)}" title="{esc(label)}">🔊</button>')


def transform_card(document, css_class, record_id, transform):
    opener = f'<article class="{css_class}" id="{esc(record_id)}">'
    start = document.find(opener)
    require(start >= 0, f"HTML is missing {css_class} card {record_id}")
    end = document.find("</article>", start)
    require(end >= 0, f"HTML card {record_id} is not closed")
    end += len("</article>")
    return document[:start] + transform(document[start:end]) + document[end:]


def inject_example_buttons(block, clip_ids, record_id):
    iterator = iter(clip_ids)
    count = 0

    def replacement(match):
        nonlocal count
        count += 1
        return match.group(0) + play_button(next(iterator), "Play German example")

    updated = re.sub(r'<div class="ex">', replacement, block)
    require(count == len(clip_ids),
            f"HTML/lesson example mismatch for {record_id}: HTML={count}, lesson={len(clip_ids)}")
    return updated


AUDIO_CSS = r"""
  .listen-row{display:flex;align-items:center;gap:9px;margin-top:13px;flex-wrap:wrap}
  .listen-all,.speak-button{border:1px solid rgba(255,255,255,.28);color:#fff;background:rgba(15,23,42,.55);font:inherit;cursor:pointer;box-shadow:none}
  .listen-all{border-radius:999px;padding:7px 13px;font-size:13px;font-weight:700}
  .speak-button{width:29px;height:29px;border-radius:50%;padding:0;display:inline-grid;place-items:center;font-size:14px;line-height:1;flex:0 0 auto;vertical-align:middle}
  .speak-button:hover,.listen-all:hover,.speak-button:focus-visible,.listen-all:focus-visible{background:#394151;outline:2px solid #f2d36b;outline-offset:2px}
  .speak-button.is-playing,.listen-all.is-playing{background:#0f766e;border-color:#6ee7b7}
  .voc .top,.phrase .head,.rule h3{align-items:center}
  .phrase .head,.rule h3{display:flex;gap:8px;justify-content:space-between}
  .ex>.speak-button{float:right;margin:-1px 0 4px 8px}
  .variant>.speak-button{margin-left:7px}
  @media(max-width:520px){.speak-button{width:32px;height:32px}.listen-all{min-height:36px}}
"""


AUDIO_JS = r"""
<script>
(() => {
  'use strict';
  const payloads = __PAYLOADS__;
  const order = __ORDER__;
  const player = new Audio();
  const full = document.getElementById('listen-all');
  let sequenceMode = false;
  let sequenceIndex = 0;
  let activeButton = null;

  function source(id) { return 'data:audio/mpeg;base64,' + payloads[id]; }
  function clearButton() {
    if (activeButton) activeButton.classList.remove('is-playing');
    activeButton = null;
  }
  function setFull(label, active) {
    full.textContent = label;
    full.classList.toggle('is-playing', active);
  }
  function loadAndPlay(id, button) {
    player.pause();
    clearButton();
    player.src = source(id);
    player.currentTime = 0;
    activeButton = button || null;
    if (activeButton) activeButton.classList.add('is-playing');
    const result = player.play();
    if (result) result.catch(() => {
      clearButton();
      if (sequenceMode) setFull('▶ Listen to full lesson', false);
      sequenceMode = false;
    });
  }
  function playSequence() {
    if (sequenceIndex >= order.length) {
      sequenceMode = false;
      sequenceIndex = 0;
      setFull('↻ Listen again', false);
      return;
    }
    setFull('❚❚ Pause lesson', true);
    loadAndPlay(order[sequenceIndex], null);
  }

  player.addEventListener('ended', () => {
    clearButton();
    if (sequenceMode) {
      sequenceIndex += 1;
      playSequence();
    }
  });

  document.querySelectorAll('.speak-button').forEach(button => {
    button.addEventListener('click', () => {
      const same = !sequenceMode && activeButton === button && !player.paused;
      sequenceMode = false;
      sequenceIndex = 0;
      setFull('▶ Listen to full lesson', false);
      if (same) {
        player.pause();
        player.currentTime = 0;
        clearButton();
      } else {
        loadAndPlay(button.dataset.audio, button);
      }
    });
  });

  full.addEventListener('click', () => {
    if (sequenceMode && !player.paused) {
      player.pause();
      setFull('▶ Resume lesson', false);
      return;
    }
    if (sequenceMode && player.paused && player.src) {
      setFull('❚❚ Pause lesson', true);
      player.play();
      return;
    }
    clearButton();
    sequenceMode = true;
    sequenceIndex = 0;
    playSequence();
  });
})();
</script>
"""


def inject_audio(document, lesson, payloads, sequence, controls):
    require('<meta name="study-pack-audio"' not in document, "Input already contains embedded audio")
    require(document.count("<h2") == 3, "Input must contain exactly three h2 sections")

    document = document.replace(
        '<meta name="study-pack-status"',
        '<meta name="study-pack-audio" content="embedded">\n<meta name="study-pack-status"', 1)
    require("</style>" in document, "HTML has no style block")
    document = document.replace("</style>", AUDIO_CSS + "\n</style>", 1)
    full_button = ('<div class="listen-row"><button type="button" class="listen-all" '
                   'id="listen-all">▶ Listen to full lesson</button></div>')
    header_end = document.find("</header>")
    require(header_end >= 0, "HTML has no header")
    document = document[:header_end] + full_button + document[header_end:]

    for record in lesson["vocabulary"]:
        def transform(block, record=record):
            head_id = controls[f'{record["id"]}-head']
            block, count = re.subn(
                r'(<div class="top"><span class="de">.*?</span>)(?=<span class="en">)',
                lambda match: match.group(1) + play_button(head_id, "Play German headword"),
                block, count=1, flags=re.S)
            require(count == 1, f"Cannot place headword audio for {record['id']}")
            ids = [controls[f'{record["id"]}-ex-{index}'] for index in range(len(record["examples"]))]
            return inject_example_buttons(block, ids, record["id"])
        document = transform_card(document, "voc", record["id"], transform)

    for record in lesson["grammar"]:
        def transform(block, record=record):
            head_id = controls[f'{record["id"]}-head']
            block, count = re.subn(
                r'(<h3>.*?</h3>)',
                lambda match: match.group(1)[:-5] + play_button(head_id, "Play grammar title") + "</h3>",
                block, count=1, flags=re.S)
            require(count == 1, f"Cannot place grammar-title audio for {record['id']}")
            ids = [controls[f'{record["id"]}-ex-{index}'] for index in range(len(record["examples"]))]
            return inject_example_buttons(block, ids, record["id"])
        document = transform_card(document, "rule", record["id"], transform)

    for record in lesson["redemittel"]:
        def transform(block, record=record):
            head_id = controls[f'{record["id"]}-head']
            block, count = re.subn(
                r'(<div class="head">.*?</div>)',
                lambda match: match.group(1)[:-6] + play_button(head_id, "Play German expression") + "</div>",
                block, count=1, flags=re.S)
            require(count == 1, f"Cannot place expression audio for {record['id']}")
            variant_ids = iter(controls[f'{record["id"]}-variant-{index}']
                               for index in range(len(record.get("variants", []))))
            seen = 0
            def variant_replacement(match):
                nonlocal seen
                seen += 1
                return match.group(1) + play_button(next(variant_ids), "Play German variant") + "</p>"
            block = re.sub(r'(<p class="variant">.*?)(</p>)', variant_replacement, block, flags=re.S)
            require(seen == len(record.get("variants", [])),
                    f"HTML/lesson variant mismatch for {record['id']}")
            ids = [controls[f'{record["id"]}-ex-{index}'] for index in range(len(record["examples"]))]
            return inject_example_buttons(block, ids, record["id"])
        document = transform_card(document, "phrase", record["id"], transform)

    script = AUDIO_JS.replace("__PAYLOADS__", json.dumps(payloads, separators=(",", ":")))
    script = script.replace("__ORDER__", json.dumps(sequence, separators=(",", ":")))
    require("</body>" in document, "HTML has no body end tag")
    return document.replace("</body>", script + "\n</body>", 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--voice", default="de-DE-SeraphinaMultilingualNeural")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--confirm-external-tts", action="store_true",
                        help="Confirm that selected lesson text may be sent to the Edge TTS service")
    args = parser.parse_args(argv)
    try:
        require(args.confirm_external_tts,
                "Hosted synthesis sends selected lesson text externally; obtain approval and pass --confirm-external-tts")
        require(args.input.resolve() != args.output.resolve(), "Never overwrite the input HTML")
        require(not args.output.exists(), "Output exists; choose a new test/version filename")
        require(args.output.suffix.lower() == ".html", "Output must be an HTML file")
        require(args.output.parent.is_dir(), "Output directory does not exist")
        require(1 <= args.concurrency <= 8, "Concurrency must be from 1 to 8")
        lesson = json.loads(args.lesson.read_text(encoding="utf-8"))
        require(isinstance(lesson, dict) and lesson.get("target_language", "").startswith("de"),
                "Lesson must be German v2 lesson data")
        for key in ("title", "vocabulary", "grammar", "redemittel"):
            require(key in lesson, f"Lesson is missing {key}")
        clips, sequence, controls = build_plan(lesson, args.voice)
        print(f"AUDIO PLAN: {len(clips)} unique clips; {len(sequence)} listening steps; voice={args.voice}")
        paths = asyncio.run(synthesize(clips, args.cache_dir, args.concurrency))
        payloads = {}
        for clip_id, path in paths.items():
            data = path.read_bytes()
            require(len(data) > 256, f"Audio clip is empty: {path}")
            payloads[clip_id] = base64.b64encode(data).decode("ascii")
        source = args.input.read_text(encoding="utf-8")
        output = inject_audio(source, lesson, payloads, sequence, controls)
        require("http://" not in output and "https://" not in output,
                "Output unexpectedly contains an external URL")
        require(output.count("data:audio/mpeg;base64,") == 1,
                "Embedded audio payload bank was not created exactly once")
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
        print(f"WROTE: {args.output} ({args.output.stat().st_size} bytes, fully embedded audio)")
        return 0
    except (AudioError, OSError, json.JSONDecodeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
