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
import html
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import speech  # noqa: E402
from study_pack import story_sentences  # noqa: E402

SECTIONS = ("Wortschatz", "Grammatik", "Redemittel", "Geschichte")


class AudioError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AudioError(message)


def esc(value):
    return html.escape(str(value), quote=True)


def speakable(value, lang="de"):
    """Turn visual lesson notation into text a voice can read naturally (see speech.speakable)."""
    return speech.speakable(value, lang)


Clip = speech.Clip


def voices_of(voices):
    """Accept a {"de": ..., "en": ...} mapping, or one voice name for both (tests, old callers)."""
    if voices is None:
        return dict(speech.DEFAULT_VOICES)
    if isinstance(voices, str):
        return {"de": voices, "en": voices}
    require(set(voices) >= {"de", "en"}, "voices needs a German ('de') and an English ('en') voice")
    return dict(voices)


def build_plan(lesson, voices=None, narration=None):
    """Clips, listening order, per-card controls and the spoken grammar explanations of one lesson.

    German text goes to the German voice, English text to the English voice; German words inside English
    text are detected and spoken in German. `narration` maps grammar ids to authored spoken explanations
    (English with German marked «…»); without one, meaning, rule, patterns and contrast are read.
    Returns (clips, sequence, controls, explain).
    """
    voices, narration = voices_of(voices), narration or {}
    clips, sequence, controls, explain = {}, [], {}, {}

    def add(value, kind, control=None):
        clip = speech.make_clip(value, kind, voices)
        clips.setdefault(clip.clip_id, clip)
        sequence.append(clip.clip_id)
        if control:
            require(control not in controls, f"Duplicate audio control {control}")
            controls[control] = clip.clip_id
        return clip.clip_id

    add(lesson["title"], "de")
    add("Wortschatz", "de")
    previous = None
    for record in lesson["vocabulary"]:
        if record["group"] != previous:
            add(record["group"], "de")
            previous = record["group"]
        head = ((record.get("article", "") + " ") if record.get("article") else "") + record["lemma"]
        add(head, "de", f'{record["id"]}-head')
        add(record["gloss"], "en")
        if record.get("forms", "").strip():
            add(record["forms"], "mix-de")
        for index, example in enumerate(record["examples"]):
            add(example["de"], "de", f'{record["id"]}-ex-{index}')
            add(example["en"], "en")

    add("Grammatik", "de")
    for record in lesson["grammar"]:
        gid = record["id"]
        chain = [add(record["title"], "en", f"{gid}-head")]
        if narration.get(gid):
            chain.append(add(narration[gid], "marked"))
        else:
            chain.append(add(record["meaning"], "en"))
            chain.append(add("How it works: " + record["rule"], "en"))
            for pattern in record["patterns"]:
                chain.append(add(pattern["label"] + ": " + pattern["form"], "en"))
            if record.get("contrast"):
                chain.append(add("Careful: " + record["contrast"], "en"))
        explain[gid] = chain
        for index, example in enumerate(record["examples"]):
            add(example["de"], "de", f'{gid}-ex-{index}')
            add(example["en"], "en")

    add("Redemittel", "de")
    previous = None
    for record in lesson["redemittel"]:
        if record["group"] != previous:
            add(record["group"], "de")
            previous = record["group"]
        add(record["frame"], "de", f'{record["id"]}-head')
        add(record["gloss"], "en")
        add(record["when"] + ((". " + record["register"]) if record.get("register") else ""), "en")
        for index, variant in enumerate(record.get("variants", [])):
            add(variant["form"], "de", f'{record["id"]}-variant-{index}')
            add(variant["usage"], "en")
        for index, example in enumerate(record["examples"]):
            add(example["de"], "de", f'{record["id"]}-ex-{index}')
            add(example["en"], "en")

    story = lesson.get("story")
    if story:                                     # the closing story: read straight through, one clip per sentence
        add("Geschichte", "de")
        add(story["title"], "de", "story-title")
        number = 0
        for paragraph in story["paragraphs"]:
            for sentence in story_sentences(paragraph["de"]):
                number += 1
                add(sentence, "de", f"story-s{number}")
    return clips, sequence, controls, explain


def lesson_plan(lesson, voices=None, narration=None):
    """build_plan plus what players need: title and section clips, story paragraphs, English example clips."""
    voices = voices_of(voices)
    clips, sequence, controls, explain = build_plan(lesson, voices, narration)

    def add(text, kind="de"):
        clip = speech.make_clip(text, kind, voices)
        clips.setdefault(clip.clip_id, clip)
        return clip.clip_id

    plan = {"title": add(lesson["title"]),
            "sections": {name: add(name) for name in SECTIONS if name != "Geschichte" or lesson.get("story")},
            "sequence": sequence, "controls": controls, "explain": explain, "story": [],
            "english": {f'{record["id"]}-ex-{index}': add(example["en"], "en")
                        for section in ("vocabulary", "grammar", "redemittel") for record in lesson[section]
                        for index, example in enumerate(record["examples"])}}
    number = 0
    for paragraph in (lesson.get("story") or {}).get("paragraphs", []):
        ids = []
        for _sentence in story_sentences(paragraph["de"]):
            number += 1
            ids.append(controls[f"story-s{number}"])
        plan["story"].append(ids)
    return clips, plan


# ---------------------------------------------------------------- listening orders ---
# Each step is [clip id, pause factor, id of the element to highlight, repeatable]. The pause after a clip is
# factor x its length (+0.35 s); a repeatable (German) step is played as often as the learner chose.
def listening_order(prefix, lesson, plan):
    """The whole lesson: German vocabulary and expressions, grammar explained, then the story read through."""
    c, seq = plan["controls"], []
    seq += [[plan["title"], 0.3, None, 0], [plan["sections"]["Wortschatz"], 0.3, None, 0]]
    for rec in lesson["vocabulary"]:
        seq.append([c[f'{rec["id"]}-head'], 0.6, prefix + rec["id"], 1])
        seq += [[c[f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1] for i in range(len(rec["examples"]))]
    if lesson["grammar"]:
        seq.append([plan["sections"]["Grammatik"], 0.3, None, 0])
    for rec in lesson["grammar"]:
        seq += [[cid, 0.15, prefix + rec["id"], 0] for cid in plan["explain"][rec["id"]]]
        seq += [[c[f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1] for i in range(len(rec["examples"]))]
    seq.append([plan["sections"]["Redemittel"], 0.3, None, 0])
    for rec in lesson["redemittel"]:
        seq.append([c[f'{rec["id"]}-head'], 0.8, prefix + rec["id"], 1])
        seq += [[c[f'{rec["id"]}-variant-{i}'], 0.8, prefix + rec["id"], 1] for i in range(len(rec.get("variants", [])))]
        seq += [[c[f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1] for i in range(len(rec["examples"]))]
    if plan["story"]:
        seq.append([plan["sections"]["Geschichte"], 0.3, None, 0])
        seq += [[step[0], step[1], step[2], 0] for step in story_order(prefix, plan)]
    return seq


def examples_order(prefix, lesson, plan):
    """Only the German example sentences, in reading order."""
    return [[plan["controls"][f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1]
            for section in ("vocabulary", "grammar", "redemittel") for rec in lesson[section]
            for i in range(len(rec["examples"]))]


def story_order(prefix, plan):
    """The story: title, then every sentence, with a longer breath at the end of each paragraph."""
    if not plan["story"]:
        return []
    seq, number = [[plan["controls"]["story-title"], 0.6, prefix + "story", 0]], 0
    for paragraph in plan["story"]:
        for index, cid in enumerate(paragraph):
            number += 1
            seq.append([cid, 0.9 if index == len(paragraph) - 1 else 0.25, f"{prefix}story-s{number}", 1])
    return seq


def number_examples(document, lesson):
    """Give every example an id (<card>-x<n>) so a listening session can highlight the sentence it plays."""
    for section, css in (("vocabulary", "voc"), ("grammar", "rule"), ("redemittel", "phrase")):
        for record in lesson[section]:
            def transform(block, rid=record["id"]):
                counter = iter(range(len(record["examples"]) + 1))
                return re.sub(r'<div class="ex">', lambda m: f'<div class="ex" id="{rid}-x{next(counter)}">', block)
            document = transform_card(document, css, record["id"], transform)
    return document


def inject_story_audio(document, plan, heads=None):
    """Audio on each story sentence, a 🔊 per paragraph and, optionally, the headword clip on underlined words."""
    controls = plan["controls"]
    document = re.sub(r'(<article class="story" id="story"><h3>.*?)(</h3>)', lambda m: m.group(1) + (
        '<button type="button" class="story-play" aria-label="Ganze Geschichte anh\u00f6ren" title="Ganze Geschichte anh\u00f6ren">'
        '\U0001f50a Ganze Geschichte</button>') + m.group(2), document, count=1, flags=re.S)
    document = re.sub(r'<span class="ss" id="story-s(\d+)">',
                      lambda m: f'<span class="ss" id="story-s{m.group(1)}" data-audio="{controls["story-s" + m.group(1)]}">',
                      document)
    document = re.sub(r'(<div class="story-p" id="story-p\d+">)', lambda m: m.group(1) + (
        '<button type="button" class="speak-button para-play" aria-label="Absatz anhören" title="Absatz anhören">🔊</button>'),
        document)
    if heads:
        document = re.sub(r'<span class="lw" data-card="([^"]+)"',
                          lambda m: m.group(0) + (f' data-h="{heads[m.group(1)]}"' if m.group(1) in heads else ""), document)
    return document


async def synthesize(clips, cache_dir, voices=None, concurrency=4):
    try:
        return await speech.synthesize(clips, cache_dir, voices_of(voices), concurrency)
    except speech.SpeechError as error:
        raise AudioError(str(error)) from error


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
  .listen-open,.story-play,.speak-button{border:1px solid rgba(255,255,255,.28);color:#fff;background:rgba(15,23,42,.55);font:inherit;cursor:pointer;box-shadow:none}
  .listen-open{border-radius:999px;padding:8px 15px;font-size:14px;font-weight:700;min-height:38px}
  .story-play{border-radius:999px;padding:6px 13px;font-size:13.5px;font-weight:700;min-height:34px;white-space:nowrap}
  .speak-button{width:29px;height:29px;border-radius:50%;padding:0;display:inline-grid;place-items:center;font-size:14px;line-height:1;flex:0 0 auto;vertical-align:middle}
  .speak-button:hover,.listen-open:hover,.story-play:hover,.speak-button:focus-visible,.listen-open:focus-visible,.story-play:focus-visible{background:#394151;outline:2px solid #f2d36b;outline-offset:2px}
  .speak-button.is-playing,.listen-open.is-playing,.story-play.is-playing{background:#0f766e;border-color:#6ee7b7;animation:pulse 1.6s ease-in-out infinite}
  @keyframes pulse{50%{box-shadow:0 0 0 6px rgba(110,231,183,.18)}}
  .voc .top,.phrase .head,.rule h3,.story h3{align-items:center}
  .phrase .head,.rule h3,.story h3{display:flex;gap:8px;justify-content:space-between;flex-wrap:wrap}
  .ex>.speak-button,.story-p>.para-play{float:right;margin:-1px 0 4px 8px}
  .variant>.speak-button{margin-left:7px}
  .ss[data-audio]{cursor:pointer;border-radius:5px;transition:background .2s}
  .ss.is-playing,.ss.follow{background:rgba(242,211,107,.16);outline:none}
  .follow{outline:2px solid var(--yellow);outline-offset:3px;border-radius:10px}
  .lp{margin:12px 0 4px;padding:12px;border:1px solid rgba(255,255,255,.2);border-radius:14px;background:rgba(15,23,42,.72)}
  .lp-modes{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:10px}
  .lp-modes button{font:inherit;font-size:15px;font-weight:700;min-height:46px;border-radius:12px;cursor:pointer;color:#1a1030;background:var(--accent2);border:0}
  .lp-modes button[data-m="ex"]{background:#f2d36b}
  .lp-modes button[data-m="story"]{background:#6ee7b7}
  .lp-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:7px 0 0}
  .lp-row>span{flex:0 0 92px;font-size:12.5px;color:#dbe2ea;letter-spacing:.3px}
  .lp-row .chips{display:flex;gap:6px;flex-wrap:wrap}
  .lp-row .chips button{font:inherit;font-size:13.5px;min-height:34px;padding:4px 11px;border-radius:999px;cursor:pointer;color:#fff;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.22)}
  .lp-row .chips button[aria-pressed="true"]{background:#f2d36b;color:#1a1030;border-color:#f2d36b;font-weight:700}
  .now{position:fixed;left:50%;bottom:calc(14px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:30;display:flex;align-items:center;gap:10px;
       max-width:calc(100% - 24px);padding:8px 8px 8px 16px;border-radius:999px;background:#0f766e;color:#ecfdf5;box-shadow:0 8px 24px rgba(0,0,0,.45);font-size:14px}
  .now span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .now button{font:inherit;font-size:14px;font-weight:700;border:0;border-radius:999px;padding:7px 13px;background:#ecfdf5;color:#064e3b;cursor:pointer;flex:none}
  .tip{position:absolute;z-index:40;max-width:min(300px,calc(100% - 16px));padding:8px 11px;border-radius:10px;background:#0b1220;color:#f8fafc;
       border:1px solid #f2d36b;font-size:14px;box-shadow:0 8px 22px rgba(0,0,0,.45)}
  .lw{cursor:help}
  [hidden]{display:none !important}
  @media(max-width:520px){.speak-button{width:32px;height:32px}}
  @media(prefers-reduced-motion:reduce){.speak-button.is-playing,.listen-open.is-playing{animation:none}}
"""

LISTEN_HTML = """<div class="lp" id="lp" hidden data-unit="">
<div class="lp-modes"><button type="button" data-m="all">▶ Ganze Lektion</button><button type="button" data-m="ex">▶ Nur Beispiele</button><button type="button" data-m="story">▶ Geschichte</button></div>
<div class="lp-row"><span>Jeder Satz</span><div class="chips" id="lp-each"></div></div>
<div class="lp-row"><span>Am Ende</span><div class="chips" id="lp-loop"></div></div>
<div class="lp-row"><span>🔊-Taste</span><div class="chips" id="lp-one"></div></div>
</div>
<div class="now" id="now" hidden><span id="now-t"></span><button type="button" id="now-x">⏹ Stopp</button></div>
<div class="tip" id="tip" hidden></div>
"""

# The listening engine shared by the course app and single audio sheets. The host defines d (document),
# load/save (settings), need(id) (base64 audio or '') and pending(id) (audio still arriving), and the
# objects SEQ, EXS and STO: per unit, the steps of "Ganze Lektion", "Nur Beispiele" and "Geschichte".
LISTEN_JS = r"""
  /* ---------------- listening: a 🔊 tap repeats, guided sessions repeat and loop ---------------- */
  var A=load('listen',{one:0,each:2,loop:1});     /* one: plays per 🔊 tap (0 = until tapped again); each: plays of every German sentence in a session; loop: start again at the end */
  var player=new Audio(), R=null, lastF=null, lock=null, tipT=null;
  var lp=d.getElementById('lp'), nowBar=d.getElementById('now'), nowT=d.getElementById('now-t'), tip=d.getElementById('tip');
  var LABEL={all:'Ganze Lektion',ex:'Nur Beispiele',story:'Geschichte'};
  function mark(el,on){ if(el) el.classList.toggle('is-playing',on); }
  function follow(el){ if(lastF) lastF.classList.remove('follow'); lastF=el||null; if(!el) return; el.classList.add('follow');
    var b=el.getBoundingClientRect(); if(b.top<90||b.bottom>innerHeight-90) el.scrollIntoView({block:'center',behavior:'smooth'}); }
  function wake(on){ try{ if(on&&!lock&&navigator.wakeLock) navigator.wakeLock.request('screen').then(function(l){ if(R) lock=l; else l.release(); },function(){});
    else if(!on&&lock){ lock.release(); lock=null; } }catch(e){} }
  function stopAll(){ player.pause(); player.onended=null; var r=R; R=null;
    if(r){ clearTimeout(r.t); mark(r.o.btn,false); if(r.o.btn&&r.o.btn.getAttribute('data-l')){ r.o.btn.textContent=r.o.btn.getAttribute('data-l'); r.o.btn.removeAttribute('data-l'); } }
    follow(null); wake(false); if(nowBar) nowBar.hidden=true; }
  function clip(id,done){ var data=need(id);
    if(!data&&pending(id)){ d.addEventListener('DOMContentLoaded',function(){ clip(id,done); },{once:true}); return true; }
    if(!data) return false;
    player.onended=done||null; player.src='data:audio/mpeg;base64,'+data; var p=player.play(); if(p) p.catch(function(){ stopAll(); }); return true; }
  /* items: [clip id, pause factor, element (or its id) to highlight, repeatable]; o: {btn, each, laps (0 = endless), follow, stop, label} */
  function run(items,o){ stopAll(); if(!items||!items.length) return; R={items:items,o:o,i:0,r:0,lap:1,t:null};
    mark(o.btn,true); if(o.btn&&o.stop){ o.btn.setAttribute('data-l',o.btn.textContent); o.btn.textContent=o.stop; }
    if(items.length>1||!o.laps) wake(true); step(); }
  function step(){ var r=R; if(!r) return;
    if(r.i>=r.items.length){
      if(!r.o.laps||r.lap<r.o.laps){ r.lap++; r.i=0; tick(r); r.t=setTimeout(step,r.items.length>1?1500:0); return; }
      stopAll(); return; }
    var it=r.items[r.i], reps=it[3]?(r.o.each||1):1;
    if(r.o.follow) follow(typeof it[2]==='string'?d.getElementById(it[2]):it[2]); tick(r);
    var ok=clip(it[0],function(){ if(R!==r) return; var dur=isFinite(player.duration)&&player.duration>0?player.duration:1.2; r.r++;
      if(r.r<reps){ r.t=setTimeout(step,Math.max(700,dur*850)); return; }      /* the same sentence again, after time to repeat it aloud */
      r.r=0; r.i++; r.t=setTimeout(step,dur*1000*it[1]+350); });
    if(!ok){ if(r.items.length===1){ stopAll(); return; } r.i++; r.t=setTimeout(step,0); } }
  function tick(r){ if(!nowBar) return; nowBar.hidden=false; var n=r.items.length, out=[r.o.label||'Wiedergabe'];
    if(n>1) out.push(Math.min(r.i+1,n)+' / '+n);
    if(n>1&&(r.o.each||1)>1) out.push('jeder Satz '+r.o.each+'×');
    if(r.o.laps!==1) out.push(r.o.laps?(r.lap+' / '+r.o.laps):(n>1?'⟳ Runde '+r.lap:'⟳ '+r.lap+'×'));
    nowT.textContent=out.join(' · '); }
  function chipRow(id,items,value,set){ var box=d.getElementById(id); box.innerHTML='';
    items.forEach(function(it){ var b=d.createElement('button'); b.type='button'; b.textContent=it[1]; b.setAttribute('aria-pressed',String(it[0]===value));
      b.addEventListener('click',function(){ set(it[0]); save('listen',A); panel(); }); box.appendChild(b); }); }
  function panel(){ chipRow('lp-each',[[1,'1×'],[2,'2×'],[3,'3×'],[5,'5×']],A.each,function(v){A.each=v;});
    chipRow('lp-loop',[[0,'Einmal'],[1,'⟳ Endlos']],A.loop,function(v){A.loop=v;});
    chipRow('lp-one',[[1,'1×'],[3,'3×'],[0,'∞ bis Stopp']],A.one,function(v){A.one=v;});
    var u=lp.getAttribute('data-unit'); lp.querySelector('[data-m="story"]').hidden=!(STO[u]&&STO[u].length); }
  function openPanel(btn){ var u=btn.getAttribute('data-unit'), row=btn.closest('.listen-row');
    if(!lp.hidden&&lp.getAttribute('data-unit')===u){ lp.hidden=true; return; }
    row.parentNode.insertBefore(lp,row.nextSibling); lp.setAttribute('data-unit',u); lp.hidden=false; panel(); }
  function session(u,m){ var src=m==='ex'?EXS:m==='story'?STO:SEQ; lp.hidden=true;
    run(src[u],{btn:d.querySelector('.listen-open[data-unit="'+u+'"]'),each:A.each,laps:A.loop?0:1,follow:true,stop:'⏹ Stopp',label:LABEL[m]}); }
  function gloss(w){ var t=w.getAttribute('title')||w.getAttribute('data-t'); if(!t||!tip) return;
    if(w.getAttribute('title')){ w.setAttribute('data-t',t); w.removeAttribute('title'); }      /* no native tooltip on top of ours */
    tip.textContent=t; tip.hidden=false; var b=w.getBoundingClientRect();
    tip.style.left=Math.max(8,Math.min(b.left+scrollX,scrollX+innerWidth-tip.offsetWidth-8))+'px'; tip.style.top=(b.bottom+scrollY+6)+'px';
    clearTimeout(tipT); tipT=setTimeout(function(){ tip.hidden=true; },3200);
    var h=w.getAttribute('data-h'); if(h) run([[h,0.4,null,0]],{laps:1,label:'Wort'}); }
  lp.addEventListener('click',function(e){ var b=e.target.closest('[data-m]'); if(b) session(lp.getAttribute('data-unit'),b.getAttribute('data-m')); });
  d.getElementById('now-x').addEventListener('click',stopAll);
  d.addEventListener('click',function(e){
    var b=e.target.closest('.speak-button,.explain-button,.listen-open,.story-play,.ss[data-audio],.lw'); if(!b) return;
    if(b.classList.contains('lw')){ gloss(b); return; }
    e.stopPropagation();
    if(R&&R.o.btn===b){ stopAll(); return; }
    if(b.classList.contains('listen-open')){ openPanel(b); return; }
    if(b.classList.contains('story-play')){ var u=b.closest('.unit')?b.closest('.unit').id:'L'; run(STO[u],{btn:b,each:1,laps:A.one,follow:true,stop:'\u23f9 Stopp',label:'Geschichte'}); return; }
    if(b.classList.contains('explain-button')){ run(b.getAttribute('data-chain').split(' ').map(function(id){ return [id,0.12,null,0]; }),{btn:b,laps:1,label:'Erklärung'}); return; }
    if(b.classList.contains('para-play')){ run([].map.call(b.closest('.story-p').querySelectorAll('.ss[data-audio]'),function(s){ return [s.getAttribute('data-audio'),0.3,s,0]; }),
      {btn:b,laps:A.one,follow:true,label:'Absatz'}); return; }
    var sentence=b.classList.contains('ss');
    run([[b.getAttribute('data-audio'),0.8,sentence?b:null,0]],{btn:b,laps:A.one,follow:sentence,label:sentence?'Satz':'Wiederholen'});
  },true);
"""

AUDIO_JS = r"""
<script>
(function(){
  'use strict';
  var d=document, P=__PAYLOADS__, SEQ={L:__SEQUENCE__}, EXS={L:__EXAMPLES__}, STO={L:__STORY__};
  function load(k,dflt){ try{ var v=localStorage.getItem('study-sheet:'+k); return v?JSON.parse(v):dflt; }catch(e){ return dflt; } }
  function save(k,v){ try{ localStorage.setItem('study-sheet:'+k,JSON.stringify(v)); }catch(e){} }
  function need(id){ return P[id]||''; }
  function pending(id){ return false; }
__LISTEN__
})();
</script>
"""


def inject_audio(document, lesson, payloads, plan):
    require('<meta name="study-pack-audio"' not in document, "Input already contains embedded audio")
    require(document.count("<h2") in (3, 4), "Input must contain the three teaching sections and at most a story")
    controls = plan["controls"]

    document = document.replace(
        '<meta name="study-pack-status"',
        '<meta name="study-pack-audio" content="embedded">\n<meta name="study-pack-status"', 1)
    require("</style>" in document, "HTML has no style block")
    document = document.replace("</style>", AUDIO_CSS + "\n</style>", 1)
    open_button = ('<div class="listen-row"><button type="button" class="listen-open" data-unit="L">'
                   '🎧 Anhören</button></div>')
    header_end = document.find("</header>")
    require(header_end >= 0, "HTML has no header")
    document = document[:header_end] + open_button + document[header_end:]
    document = document.replace("</header>", "</header>" + LISTEN_HTML, 1)

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

    document = number_examples(document, lesson)
    heads = {record["id"]: controls[f'{record["id"]}-head'] for record in lesson["vocabulary"] + lesson["redemittel"]}
    document = inject_story_audio(document, plan, heads)
    compact = lambda value: json.dumps(value, separators=(",", ":"))
    script = (AUDIO_JS.replace("__LISTEN__", LISTEN_JS)
              .replace("__SEQUENCE__", compact(listening_order("", lesson, plan)))
              .replace("__EXAMPLES__", compact(examples_order("", lesson, plan)))
              .replace("__STORY__", compact(story_order("", plan)))
              .replace("__PAYLOADS__", compact(payloads)))
    require("</body>" in document, "HTML has no body end tag")
    return document.replace("</body>", script + "\n</body>", 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--voice-de", default=speech.DEFAULT_VOICES["de"], help="German voice for all German text")
    parser.add_argument("--voice-en", default=speech.DEFAULT_VOICES["en"], help="English voice for glosses and explanations")
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
        voices = {"de": args.voice_de, "en": args.voice_en}
        clips, plan = lesson_plan(lesson, voices)
        print(f"AUDIO PLAN: {len(clips)} unique clips; {len(plan['sequence'])} listening steps; voices={voices}")
        paths = asyncio.run(synthesize(clips, args.cache_dir, voices, args.concurrency))
        payloads = {}
        for clip_id, path in paths.items():
            data = path.read_bytes()
            require(len(data) > 256, f"Audio clip is empty: {path}")
            payloads[clip_id] = base64.b64encode(data).decode("ascii")
        source = args.input.read_text(encoding="utf-8")
        output = inject_audio(source, lesson, payloads, plan)
        require("http://" not in output and "https://" not in output,
                "Output unexpectedly contains an external URL")
        require(output.count("data:audio/mpeg;base64,") == 1,
                "Embedded audio payload bank was not created exactly once")
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
        print(f"WROTE: {args.output} ({args.output.stat().st_size} bytes, fully embedded audio)")
        return 0
    except (AudioError, speech.SpeechError, OSError, json.JSONDecodeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
