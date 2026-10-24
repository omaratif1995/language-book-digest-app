#!/usr/bin/env python3
"""Build one offline study app from a course's reviewed sheets: Lernen (study + listening) and Üben (flashcards).

    build_course_app.py --course course.json --output Course_App_v1.html              # with audio from the cache
    build_course_app.py --course course.json --output Course_App_v1.html --no-audio   # study + practice only

Lernen: every reviewed sheet in course order, a 🔊 button on each German headword, example, phrase and variant,
a "🔊 Erklärung" button on each grammar point (English explanation), and "Ganze Lektion anhören", which plays the
unit as a guided listening session: German vocabulary and expressions with pauses to repeat, grammar explained
in English with German examples. Üben: one card per sheet card (rendered from the same sheet HTML), a small
spaced-repetition schedule, tap to flip, swipe or tap to grade, skip, short rounds and a daily summary.
Audio comes from `course_audio.py synth` and is embedded as base64 so the file works without a network.
See references/course-app.md.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import html
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_audio import AUDIO_CSS, AudioError, inject_example_buttons, play_button, require, transform_card  # noqa: E402
from course_audio import build_course_plan, ffmpeg_exe, load_course  # noqa: E402

KIND = {"voc": "w", "rule": "g", "phrase": "r"}


# ---------------------------------------------------------------- audio placement ---
def add_audio_buttons(page, lesson, unit_plan, used):
    """German 🔊 buttons (headwords, examples, phrases, variants) and a 🔊 Erklärung chain per grammar point."""
    controls = unit_plan["controls"]

    def take(key):
        used.add(controls[key])
        return controls[key]

    for rec in lesson["vocabulary"]:
        def voc(block, rec=rec):
            head = take(f'{rec["id"]}-head')
            block, n = re.subn(r'(<div class="top"><span class="de">.*?</span>)(?=<span class="en">)',
                               lambda m: m.group(1) + play_button(head, "Play German headword"), block, count=1, flags=re.S)
            require(n == 1, f"cannot place headword audio for {rec['id']}")
            return inject_example_buttons(block, [take(f'{rec["id"]}-ex-{i}') for i in range(len(rec["examples"]))], rec["id"])
        page = transform_card(page, "voc", rec["id"], voc)

    for rec in lesson["grammar"]:
        def rule(block, rec=rec):
            parts = unit_plan["grammar"][rec["id"]]
            chain = [parts["title"], parts["meaning"], parts["rule"]] + ([parts["contrast"]] if parts["contrast"] else [])
            used.update(chain)
            button = (f'<button type="button" class="explain-button" data-chain="{" ".join(chain)}" '
                      f'aria-label="Listen to the explanation">🔊 Erklärung</button>')
            block, n = re.subn(r"</h3>", lambda m: button + "</h3>", block, count=1)
            require(n == 1, f"cannot place explanation audio for {rec['id']}")
            return inject_example_buttons(block, [take(f'{rec["id"]}-ex-{i}') for i in range(len(rec["examples"]))], rec["id"])
        page = transform_card(page, "rule", rec["id"], rule)

    for rec in lesson["redemittel"]:
        def phrase(block, rec=rec):
            head = take(f'{rec["id"]}-head')
            block, n = re.subn(r'(<div class="head">.*?)(</div>)',
                               lambda m: m.group(1) + play_button(head, "Play German expression") + m.group(2), block, count=1, flags=re.S)
            require(n == 1, f"cannot place expression audio for {rec['id']}")
            variants = iter([take(f'{rec["id"]}-variant-{i}') for i in range(len(rec.get("variants", [])))])
            block = re.sub(r'(<p class="variant">.*?)(</p>)',
                           lambda m: m.group(1) + play_button(next(variants), "Play German variant") + m.group(2), block, flags=re.S)
            return inject_example_buttons(block, [take(f'{rec["id"]}-ex-{i}') for i in range(len(rec["examples"]))], rec["id"])
        page = transform_card(page, "phrase", rec["id"], phrase)
    return page


def listening(unit_id, lesson, unit_plan, used):
    """Guided listening order: [clip, pause factor, card element id]. Pause = factor x clip length (+0.35 s)."""
    c, seq = unit_plan["controls"], []

    def add(cid, factor, card=None):
        used.add(cid)
        seq.append([cid, factor, f"{unit_id}-{card}" if card else None])

    add(unit_plan["title"], 0.3)
    add(unit_plan["sections"]["Wortschatz"], 0.3)
    for rec in lesson["vocabulary"]:
        add(c[f'{rec["id"]}-head'], 0.6, rec["id"])
        for i in range(len(rec["examples"])):
            add(c[f'{rec["id"]}-ex-{i}'], 1.0, rec["id"])
    if lesson["grammar"]:
        add(unit_plan["sections"]["Grammatik"], 0.3)
    for rec in lesson["grammar"]:
        parts = unit_plan["grammar"][rec["id"]]
        for key in ("title", "meaning", "rule", "contrast"):
            if parts[key]:
                add(parts[key], 0.15, rec["id"])
        for i in range(len(rec["examples"])):
            add(c[f'{rec["id"]}-ex-{i}'], 1.0, rec["id"])
    add(unit_plan["sections"]["Redemittel"], 0.3)
    for rec in lesson["redemittel"]:
        add(c[f'{rec["id"]}-head'], 0.8, rec["id"])
        for i in range(len(rec.get("variants", []))):
            add(c[f'{rec["id"]}-variant-{i}'], 0.8, rec["id"])
        for i in range(len(rec["examples"])):
            add(c[f'{rec["id"]}-ex-{i}'], 1.0, rec["id"])
    return seq


def compressed(cache, clip_id, bitrate, ff):
    src = cache / "clips" / f"{clip_id}.mp3"
    dst = cache / "app" / bitrate / f"{clip_id}.mp3"
    if not dst.exists():
        require(src.is_file(), f"missing clip {clip_id}: run `course_audio.py synth` first")
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "22050",
                        "-c:a", "libmp3lame", "-b:a", bitrate, str(dst)], check=True)
    return base64.b64encode(dst.read_bytes()).decode("ascii")


# ---------------------------------------------------------------- page assets ---
APP_CSS = r"""
  .bar{position:sticky;top:0;z-index:5;margin:-24px -16px 18px;padding:10px 16px;background:rgba(23,25,31,.95);
       backdrop-filter:blur(8px);border-bottom:1px solid var(--line);display:none;gap:8px;flex-wrap:wrap;align-items:center}
  .js .bar{display:flex}
  @media(max-width:520px){.bar{margin:-14px -9px 14px;padding:10px 9px}}
  .bar select,.bar input,.bar button,.pr select,.pr button{font:inherit;font-size:15px;color:var(--ink);background:var(--card);
       border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-height:42px}
  .tabs{display:flex;gap:6px;flex-basis:100%}
  .tabs button{flex:1;font-weight:700;cursor:pointer}
  .tabs button[aria-pressed="true"],.pr .chips button[aria-pressed="true"]{background:var(--accent);color:#1a1030;border-color:var(--accent)}
  .bar select{flex:1 1 200px;min-width:0}
  .bar input{flex:1 1 160px;min-width:0}
  .bar .nav{width:44px;cursor:pointer}
  .bar .hits{flex-basis:100%;font-size:13px;color:var(--muted);display:none}
  .searching .bar .hits{display:block}
  .cover{text-align:center;margin:8px 0 22px;color:var(--muted);font-size:14px}
  .cover b{display:block;color:var(--ink);font-size:20px;margin-bottom:2px}
  .js .unit{display:none}
  .js .unit.on{display:block}
  .searching .unit{display:block}
  .searching article.miss,.searching .unit.empty{display:none !important}
  .searching h2,.searching .rule-under{display:none}
  section.unit + section.unit{margin-top:40px}
  .follow{outline:2px solid var(--yellow);outline-offset:3px;border-radius:12px}
  .explain-button{border:1px solid rgba(255,255,255,.28);color:#fff;background:rgba(15,23,42,.55);font:inherit;font-size:13px;
       font-weight:700;border-radius:999px;padding:4px 10px;margin-left:8px;cursor:pointer;white-space:nowrap}
  .explain-button.is-playing{background:#0f766e;border-color:#6ee7b7}
  .mode-practice .lernen{display:none}
  #practice{display:none}
  .mode-practice #practice{display:block}
  .mode-practice .lern-only{display:none !important}
  .tr-top{display:flex;align-items:center;gap:10px;margin:2px 0 12px}
  .tr-bar{flex:1;height:8px;border-radius:99px;background:var(--card);border:1px solid var(--line);overflow:hidden}
  .tr-bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),#34d399);transition:width .35s ease}
  .tr-count{font-size:14px;color:var(--muted);white-space:nowrap}
  .tr-streak{font-size:14px;white-space:nowrap}
  .fc{position:relative;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 18px;min-height:250px;
      box-shadow:0 10px 28px rgba(0,0,0,.3);overflow-wrap:anywhere;touch-action:pan-y;user-select:none;-webkit-user-select:none;
      transition:transform .22s ease,opacity .22s ease,border-color .15s}
  .fc.dragging{transition:none}
  .fc.hint-good{border-color:#34d399}
  .fc.hint-again{border-color:#f87171}
  .fc.fly-right{transform:translateX(120%) rotate(12deg);opacity:0}
  .fc.fly-left{transform:translateX(-120%) rotate(-12deg);opacity:0}
  .fc .tag{font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:12px}
  .fc .front{font-size:26px;font-weight:700;line-height:1.3}
  .fc .front .q-mean{display:block}
  .fc .front .q-when{display:block;font-size:15px;font-weight:400;color:var(--muted);margin-top:10px}
  .fc .tap{margin-top:28px;font-size:13px;color:var(--muted);text-align:center}
  .fc .back{margin-top:16px;border-top:1px dashed var(--line);padding-top:12px;animation:reveal .25s ease}
  .fc .back article{background:none;border:0;box-shadow:none;padding:0;margin:0}
  .fc .msg{text-align:center;padding:26px 4px}
  .fc .msg .big{font-size:40px;line-height:1.1;margin-bottom:8px}
  .fc .msg h3{margin:0 0 6px;font-size:22px}
  .fc .msg p{margin:4px 0;color:var(--muted)}
  @keyframes reveal{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  .acts{display:flex;gap:10px;margin:14px 0 6px}
  .acts button{flex:1;min-height:56px;font-size:17px;font-weight:700;border-radius:14px;cursor:pointer}
  .acts .main{background:var(--accent);color:#1a1030;border-color:var(--accent)}
  .acts .again{background:#5b2333;border-color:#9f3a55;color:#ffe4ea}
  .acts .good{background:#145c4d;border-color:#34d399;color:#e7fff6}
  .skip{display:block;margin:0 auto;background:none !important;border:0 !important;color:var(--muted) !important;font-size:14px !important;cursor:pointer;min-height:36px}
  .swipe-hint{text-align:center;font-size:12px;color:var(--muted);margin-top:2px}
  .settings{margin-top:24px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:rgba(36,39,46,.55)}
  .settings summary{cursor:pointer;color:var(--muted);font-size:14px;padding:4px 0}
  .settings[open] summary{margin-bottom:12px}
  .pr .group{margin:0 0 14px}
  .pr .lab{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
  .pr .chips{display:flex;flex-wrap:wrap;gap:6px}
  .pr .chips button{min-height:36px;padding:5px 10px;font-size:14px;cursor:pointer}
  .pr .stat{font-size:13px;color:var(--muted)}
  .pr .backup{display:flex;gap:8px;flex-wrap:wrap}
  .pr .backup button,.pr .backup label{font:inherit;font-size:14px;cursor:pointer;color:var(--ink);background:var(--card);
       border:1px solid var(--line);border-radius:10px;padding:8px 10px}
  .pr .backup input{display:none}
  @media(prefers-reduced-motion:reduce){.fc,.fc .back,.tr-bar i{transition:none;animation:none}}
"""

APP_JS = r"""
(function(){
  'use strict';
  var d=document, root=d.documentElement; root.classList.add('js');
  var A={}, IDX=__INDEX__, SEQ=__SEQUENCES__, CARDS=__CARDS__, ORDER=__ORDER__, CFG=__CONFIG__;
  var K=CFG.key;
  function load(k,dflt){try{var v=localStorage.getItem(K+':'+k);return v?JSON.parse(v):dflt;}catch(e){return dflt;}}
  function save(k,v){try{localStorage.setItem(K+':'+k,JSON.stringify(v));}catch(e){}}
  var ui=load('ui',{}), state=load('srs',{}), meta=load('meta',{day:0,fresh:0,extra:0,streak:0,last:-9,done:0,good:0});
  function today(){var t=new Date();return Math.floor((t.getTime()-t.getTimezoneOffset()*60000)/86400000);}

  /* ---------------- audio: single clips, chains, guided listening ---------------- */
  var player=new Audio(), active=null, run=null;
  function mark(el,on){ if(el) el.classList.toggle('is-playing',on); }
  function stopAll(){ player.pause(); player.onended=null; mark(active,false); active=null;
    if(run){ clearTimeout(run.timer); if(run.btn){ mark(run.btn,false); if(run.label) run.btn.textContent=run.label; } if(run.card) run.card.classList.remove('follow'); run=null; } }
  function need(id){ if(A[id]!==undefined) return A[id]; var k=IDX[id], el=k===undefined?null:d.getElementById('au-'+k);
    if(el && !el.getAttribute('data-read')){ el.textContent.split(';').forEach(function(p){ var i=p.indexOf(':'); if(i>0) A[p.slice(0,i)]=p.slice(i+1); }); el.setAttribute('data-read','1'); }
    return A[id]||''; }
  function clip(id,el,done){ var data=need(id);
    if(!data && IDX[id]!==undefined && d.readyState==='loading'){ mark(el,true);   /* audio still loading: play when it has arrived */
      d.addEventListener('DOMContentLoaded',function(){ mark(el,false); clip(id,el,done); },{once:true}); return; }
    if(!data){ if(done) setTimeout(done,0); return; }
    player.pause(); mark(active,false); active=el||null; mark(active,true);
    player.onended=function(){ mark(active,false); active=null; if(done) done(); };
    player.src='data:audio/mpeg;base64,'+data; var p=player.play(); if(p) p.catch(function(){ mark(active,false); active=null; }); }
  function chain(items,btn,label,follow){ stopAll(); run={i:0,timer:null,btn:btn,label:label,card:null}; mark(btn,true); if(label) btn.textContent='❚❚ Stopp';
    (function step(){ if(!run) return; if(run.card){ run.card.classList.remove('follow'); run.card=null; }
      if(run.i>=items.length){ stopAll(); return; }
      var it=items[run.i++];
      if(follow && it[2]){ var c=d.getElementById(it[2]); if(c){ c.classList.add('follow'); c.scrollIntoView({block:'center',behavior:'smooth'}); run.card=c; } }
      clip(it[0],null,function(){ if(!run) return; run.timer=setTimeout(step,(player.duration||1.2)*1000*it[1]+350); });
    })(); }
  d.addEventListener('click',function(e){
    var b=e.target.closest('.speak-button,.explain-button,.listen-all'); if(!b) return;
    e.stopPropagation();
    if(run && run.btn===b){ stopAll(); return; }
    if(b.classList.contains('listen-all')){ chain(SEQ[b.getAttribute('data-unit')],b,b.textContent,true); return; }
    if(b.classList.contains('explain-button')){ chain(b.getAttribute('data-chain').split(' ').map(function(id){return [id,0.12,null];}),b,null,false); return; }
    if(run) stopAll();
    if(active===b && !player.paused){ player.pause(); mark(b,false); active=null; return; }
    clip(b.getAttribute('data-audio'),b);
  },true);

  /* ---------------- Lernen: unit picker and search ---------------- */
  var units=[].slice.call(d.querySelectorAll('section.unit')), sel=d.getElementById('pick'), q=d.getElementById('q'), hits=d.getElementById('hits');
  function show(id,scroll){ if(!units.some(function(u){return u.id===id;})) id=units[0].id;
    units.forEach(function(u){u.classList.toggle('on',u.id===id);}); sel.value=id; ui.unit=id; save('ui',ui); if(scroll) window.scrollTo(0,0); }
  function step(n){ var i=units.findIndex(function(u){return u.id===sel.value;}); i=Math.max(0,Math.min(units.length-1,i+n)); stopAll(); show(units[i].id,true); }
  sel.addEventListener('change',function(){stopAll(); show(sel.value,true);});
  d.getElementById('prev').addEventListener('click',function(){step(-1);});
  d.getElementById('next').addEventListener('click',function(){step(1);});
  function norm(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/ß/g,'ss');}
  var arts=[].slice.call(d.querySelectorAll('section.unit article')).map(function(a){return [a,norm(a.textContent)];}), tq;
  q.addEventListener('input',function(){clearTimeout(tq); tq=setTimeout(search,150);});
  function search(){ var v=norm(q.value.trim());
    if(v.length<2){ d.body.classList.remove('searching'); arts.forEach(function(c){c[0].classList.remove('miss');}); units.forEach(function(u){u.classList.remove('empty');}); return; }
    d.body.classList.add('searching'); var n=0;
    arts.forEach(function(c){var m=c[1].indexOf(v)>=0; c[0].classList.toggle('miss',!m); if(m) n++;});
    units.forEach(function(u){u.classList.toggle('empty',!u.querySelector('article:not(.miss)'));});
    hits.textContent=n+(n===1?' Karte':' Karten')+' gefunden'; }

  /* ---------------- tabs ---------------- */
  var tabL=d.getElementById('tab-l'), tabP=d.getElementById('tab-p');
  function mode(m){ stopAll(); d.body.classList.toggle('mode-practice',m==='p'); tabL.setAttribute('aria-pressed',m!=='p'); tabP.setAttribute('aria-pressed',m==='p');
    ui.tab=m; save('ui',ui); if(m==='p') start(); window.scrollTo(0,0); }
  tabL.addEventListener('click',function(){mode('l');}); tabP.addEventListener('click',function(){mode('p');});

  /* ---------------- Üben: spaced repetition with rounds ---------------- */
  var DAYS=[0,1,3,7,14,30,60], KIND={w:'Wortschatz',g:'Grammatik',r:'Redemittel'};
  var S={units:ui.units||ORDER.slice(), kinds:ui.kinds||['w','g','r'], dir:ui.dir||'de', perDay:ui.perDay||CFG.perDay,
         auto:ui.auto!==false, round:(ui.round===undefined?10:ui.round), browse:!!ui.browse};
  var queue=[], cur=null, shown=false, view='card', ses={inRound:0,rg:0,ra:0}, bList=[], bIdx=0;
  var fc=d.getElementById('fc'), acts=d.getElementById('acts'), skipBtn=d.getElementById('skip');
  function persist(){ ui.units=S.units; ui.kinds=S.kinds; ui.dir=S.dir; ui.perDay=S.perDay; ui.auto=S.auto; ui.round=S.round; ui.browse=S.browse; save('ui',ui); }
  function pool(){ return CARDS.filter(function(c){return S.units.indexOf(c.u)>=0 && S.kinds.indexOf(c.k)>=0;}); }
  function newDay(){ var T=today(); if(meta.day!==T){ meta.day=T; meta.fresh=0; meta.extra=0; meta.done=0; meta.good=0; save('meta',meta); } }
  function start(){ newDay(); renderSettings();
    if(S.browse){ bList=pool(); bIdx=Math.min(bIdx,Math.max(0,bList.length-1)); cur=bList[bIdx]||null; shown=false; view=cur?'card':'empty'; render(); return; }
    var T=today(), p=pool();
    var due=p.filter(function(c){var s=state[c.id]; return s && s[1]<=T;}).sort(function(a,b){return state[a.id][1]-state[b.id][1]||state[a.id][0]-state[b.id][0];});
    var fresh=p.filter(function(c){return !state[c.id];}).slice(0,Math.max(0,S.perDay+meta.extra-meta.fresh));
    queue=[]; var i=0,j=0; while(i<due.length||j<fresh.length){ if(i<due.length) queue.push(due[i++]); if(i<due.length) queue.push(due[i++]); if(j<fresh.length) queue.push(fresh[j++]); }
    ses={inRound:0,rg:0,ra:0};
    if(!p.length){ cur=null; view='empty'; render(); return; }
    next(); }
  function next(){ cur=queue.shift()||null; shown=false; view=cur?'card':'done'; render(); if(cur) autoFront(); }
  function autoFront(){ if(S.auto && cur.k==='w' && S.dir==='de' && cur.fa) clip(cur.fa,null); }
  function autoBack(){ if(!S.auto) return; if(cur.k==='w' && S.dir==='en' && cur.fa) clip(cur.fa,null); else if(cur.k==='r' && cur.ba) clip(cur.ba,null); }
  function topbar(){ var t=d.getElementById('tr-count'), bar=d.getElementById('tr-fill'), st=d.getElementById('tr-streak');
    if(S.browse){ t.textContent=(bList.length?(bIdx+1)+' / '+bList.length:'0'); bar.style.width=(bList.length?100*(bIdx+1)/bList.length:0)+'%'; }
    else { var left=queue.length+(cur && view==='card'?1:0), all=(meta.done||0)+left; t.textContent='Heute '+(meta.done||0)+' / '+all; bar.style.width=(all?100*(meta.done||0)/all:0)+'%'; }
    st.textContent=meta.streak>0 && meta.last>=today()-1 ? '🔥 '+meta.streak : ''; }
  function msg(big,title,lines){ return '<div class="msg"><div class="big">'+big+'</div><h3>'+title+'</h3>'+lines.map(function(l){return '<p>'+l+'</p>';}).join('')+'</div>'; }
  function render(){ topbar(); fc.className='fc'; fc.style.transform=''; skipBtn.style.display='none'; d.getElementById('swipe-hint').style.display='none';
    if(view==='empty'){ fc.innerHTML=msg('🗂️','Keine Karten','<span>Wähle in den Einstellungen Lektionen und Teile.</span>'.split('|')); acts.innerHTML=''; return; }
    if(view==='done'){ var more=pool().some(function(c){return !state[c.id];});
      fc.innerHTML=msg('🎉','Fertig für heute!',[meta.done?meta.done+' Karten geübt · '+meta.good+' gewusst':'Heute ist nichts fällig.', meta.streak>1?'🔥 '+meta.streak+' Tage in Folge':'Bis morgen!']);
      acts.innerHTML=(more?'<button type="button" class="main" data-a="extra">+10 neue Karten</button>':'')+'<button type="button" data-a="browse">Durchblättern</button>'; return; }
    if(view==='round'){ fc.innerHTML=msg('💪','Runde geschafft!',['✓ '+ses.rg+' gewusst · ✗ '+ses.ra+' nochmal','Noch '+(queue.length+(cur?1:0))+' Karten für heute']);
      acts.innerHTML='<button type="button" class="main" data-a="resume">Weiter</button><button type="button" data-a="pause">Pause</button>'; return; }
    if(view==='paused'){ fc.innerHTML=msg('☕','Gute Pause!',['Dein Fortschritt ist gespeichert.']); acts.innerHTML='<button type="button" class="main" data-a="resume">Weiter lernen</button>'; return; }
    var reverse=(cur.k==='w' && S.dir==='en'), cls={w:'voc',g:'rule',r:'phrase'}[cur.k];
    fc.innerHTML='<div class="tag">'+cur.l+' · '+KIND[cur.k]+'</div><div class="front">'+(reverse?cur.r:cur.f)+'</div>'+
      (shown?'<div class="back"><article class="'+cls+'">'+cur.b+'</article></div>':'<div class="tap">Tippen zum Umdrehen</div>');
    if(S.browse){ acts.innerHTML='<button type="button" data-a="prev">‹</button><button type="button" class="main" data-a="flip">'+(shown?'Verstecken':'Antwort zeigen')+'</button><button type="button" data-a="nxt">›</button>'; return; }
    if(!shown){ acts.innerHTML='<button type="button" class="main" data-a="flip">Antwort zeigen</button>'; skipBtn.style.display='block'; }
    else { acts.innerHTML='<button type="button" class="again" data-a="again">✗ Nochmal</button><button type="button" class="good" data-a="good">✓ Gewusst</button>';
      d.getElementById('swipe-hint').style.display='block'; } }
  function reveal(){ if(view!=='card'||!cur||shown) return; shown=true; render(); autoBack(); }
  function grade(ok){ if(view!=='card'||!cur||!shown) return; var T=today(), s=state[cur.id], isNew=!s;
    if(isNew){ meta.fresh++; }
    if(meta.last!==T){ meta.streak=(meta.last===T-1?meta.streak:0)+1; meta.last=T; }
    if(ok){ var box=isNew?2:Math.min((s[0]||0)+1,6); state[cur.id]=[box,T+DAYS[box]]; meta.good=(meta.good||0)+1; ses.rg++; }
    else { state[cur.id]=[0,T]; ses.ra++; queue.splice(Math.min(3,queue.length),0,cur); }
    meta.done=(meta.done||0)+1; ses.inRound++; save('srs',state); save('meta',meta); if(navigator.vibrate) navigator.vibrate(12);
    if(S.round && ses.inRound>=S.round && queue.length){ ses.inRound=0; cur=null; view='round'; render(); ses.rg=0; ses.ra=0; return; }
    next(); }
  var busy=false;
  function fly(ok){ if(busy||view!=='card'||!shown) return; busy=true; fc.classList.add(ok?'fly-right':'fly-left');
    setTimeout(function(){ busy=false; grade(ok); },200); }
  function skip(){ if(view!=='card'||!cur||S.browse) return; queue.push(cur); next(); }
  function browseMove(n){ bIdx=Math.max(0,Math.min(bList.length-1,bIdx+n)); cur=bList[bIdx]; shown=false; render(); }
  acts.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; var a=b.getAttribute('data-a');
    if(a==='flip'){ if(S.browse){ shown=!shown; render(); if(shown) autoBack(); } else reveal(); }
    else if(a==='good') fly(true); else if(a==='again') fly(false);
    else if(a==='resume'){ next(); } else if(a==='pause'){ view='paused'; render(); }
    else if(a==='extra'){ meta.extra+=10; save('meta',meta); start(); }
    else if(a==='browse'){ S.browse=true; persist(); start(); }
    else if(a==='prev') browseMove(-1); else if(a==='nxt') browseMove(1); });
  skipBtn.addEventListener('click',skip);
  /* tap to flip, swipe to grade */
  var sx=0, sy=0, dx=0, dragging=false;
  fc.addEventListener('pointerdown',function(e){ if(e.target.closest('button')||view!=='card') return; dragging=true; sx=e.clientX; sy=e.clientY; dx=0; fc.classList.add('dragging'); });
  fc.addEventListener('pointermove',function(e){ if(!dragging) return; dx=e.clientX-sx; var dy=e.clientY-sy;
    if(shown && !S.browse && Math.abs(dx)>Math.abs(dy)){ fc.style.transform='translateX('+dx+'px) rotate('+(dx/28)+'deg)'; fc.classList.toggle('hint-good',dx>40); fc.classList.toggle('hint-again',dx<-40); } });
  function end(e){ if(!dragging) return; dragging=false; fc.classList.remove('dragging'); var dy=(e&&e.clientY!==undefined)?e.clientY-sy:0;
    if(shown && !S.browse && Math.abs(dx)>80){ fly(dx>0); return; }
    fc.style.transform=''; fc.classList.remove('hint-good','hint-again');
    if(Math.abs(dx)<10 && Math.abs(dy)<10){ if(S.browse){ shown=!shown; render(); if(shown) autoBack(); } else if(!shown) reveal(); } }
  fc.addEventListener('pointerup',end); fc.addEventListener('pointercancel',function(){ dragging=false; fc.classList.remove('dragging','hint-good','hint-again'); fc.style.transform=''; });
  d.addEventListener('keydown',function(e){ if(!d.body.classList.contains('mode-practice')||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
    if(e.key===' '||e.key==='Enter'){ e.preventDefault(); if(view==='card'){ if(S.browse){ shown=!shown; render(); } else if(!shown) reveal(); } else if(view==='round'||view==='paused') next(); }
    else if(e.key==='ArrowRight'||e.key==='2'){ if(S.browse) browseMove(1); else if(shown) fly(true); }
    else if(e.key==='ArrowLeft'||e.key==='1'){ if(S.browse) browseMove(-1); else if(shown) fly(false); }
    else if(e.key==='s'||e.key==='S') skip(); });

  /* ---------------- settings ---------------- */
  function chips(id,items,active,toggle){ var box=d.getElementById(id); box.innerHTML='';
    items.forEach(function(it){ var b=d.createElement('button'); b.type='button'; b.textContent=it[1]; b.setAttribute('aria-pressed',active.indexOf(it[0])>=0);
      b.addEventListener('click',function(){ toggle(it[0]); }); box.appendChild(b); }); }
  function renderSettings(){
    chips('s-units',CFG.units,S.units,function(u){ var i=S.units.indexOf(u); if(i>=0) S.units.splice(i,1); else S.units.push(u); persist(); start(); });
    chips('s-kinds',[['w','Wortschatz'],['g','Grammatik'],['r','Redemittel']],S.kinds,function(k){ var i=S.kinds.indexOf(k); if(i>=0) S.kinds.splice(i,1); else S.kinds.push(k); persist(); start(); });
    chips('s-dir',[['de','Deutsch → Englisch'],['en','Englisch → Deutsch']],[S.dir],function(v){ S.dir=v; persist(); renderSettings(); render(); });
    chips('s-new',[[5,'5'],[10,'10'],[15,'15'],[20,'20'],[25,'25'],[40,'40']],[S.perDay],function(v){ S.perDay=v; persist(); start(); });
    chips('s-round',[[10,'10'],[20,'20'],[0,'ohne Pause']],[S.round],function(v){ S.round=v; persist(); renderSettings(); });
    chips('s-mode',[[false,'Tagesplan'],[true,'Durchblättern']],[S.browse],function(v){ S.browse=v; persist(); start(); });
    chips('s-auto',[[true,'Ton an'],[false,'Ton aus']],[S.auto],function(v){ S.auto=v; persist(); renderSettings(); });
    var p=pool(), n={neu:0,lern:0,sicher:0,fest:0};
    p.forEach(function(c){ var s=state[c.id]; if(!s) n.neu++; else if(s[0]<=2) n.lern++; else if(s[0]<=4) n.sicher++; else n.fest++; });
    d.getElementById('s-stat').textContent='Neu '+n.neu+' · Lerne ich '+n.lern+' · Sicher '+n.sicher+' · Fest '+n.fest; }
  d.getElementById('all-u').addEventListener('click',function(){ S.units=S.units.length===ORDER.length?[]:ORDER.slice(); persist(); start(); });
  d.getElementById('save-btn').addEventListener('click',function(){
    var blob=new Blob([JSON.stringify({v:2,key:K,state:state,meta:meta})],{type:'application/json'}), a=d.createElement('a');
    a.href=URL.createObjectURL(blob); a.download=K+'-fortschritt-'+new Date().toISOString().slice(0,10)+'.json'; d.body.appendChild(a); a.click(); a.remove(); });
  d.getElementById('load-in').addEventListener('change',function(e){ var f=e.target.files[0]; if(!f) return; var r=new FileReader();
    r.onload=function(){ try{ var o=JSON.parse(r.result); if(o && o.state){ state=o.state; meta=o.meta||meta; save('srs',state); save('meta',meta); start(); alert('Fortschritt geladen.'); } }catch(err){ alert('Diese Datei ist keine Sicherung.'); } };
    r.readAsText(f); });

  show(ui.unit||units[0].id,false);
  mode(ui.tab==='p'?'p':'l');
})();
"""

PRACTICE = """
<section id="practice" class="pr" aria-label="Üben">
<div class="tr-top"><div class="tr-bar"><i id="tr-fill"></i></div><span class="tr-count" id="tr-count"></span><span class="tr-streak" id="tr-streak"></span></div>
<div class="fc" id="fc" aria-live="polite"></div>
<div class="acts" id="acts"></div>
<button type="button" class="skip" id="skip">Überspringen ›</button>
<div class="swipe-hint" id="swipe-hint">Tipp: nach rechts wischen = gewusst · nach links = nochmal</div>
<details class="settings"><summary>Einstellungen</summary>
<div class="group"><div class="lab">Lektionen <button type="button" id="all-u" style="min-height:28px;padding:2px 8px;font-size:12px;margin-left:6px">alle / keine</button></div><div class="chips" id="s-units"></div></div>
<div class="group"><div class="lab">Teile</div><div class="chips" id="s-kinds"></div></div>
<div class="group"><div class="lab">Richtung (Wortschatz)</div><div class="chips" id="s-dir"></div></div>
<div class="group"><div class="lab">Neue Karten pro Tag</div><div class="chips" id="s-new"></div></div>
<div class="group"><div class="lab">Pause nach … Karten</div><div class="chips" id="s-round"></div></div>
<div class="group"><div class="lab">Modus</div><div class="chips" id="s-mode"></div></div>
<div class="group"><div class="lab">Aussprache automatisch</div><div class="chips" id="s-auto"></div></div>
<div class="group"><div class="lab">Fortschritt</div><p class="stat" id="s-stat"></p>
<div class="backup"><button type="button" id="save-btn">Sichern</button><label for="load-in">Laden</label><input type="file" id="load-in" accept="application/json,.json"></div>
<p class="stat">Der Fortschritt bleibt in diesem Browser auf diesem Gerät. Mit „Sichern“ nimmst du ihn mit.</p></div>
</details>
</section>
"""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "course"


def build(course, output, audio=True, bitrate="32k", explain_bitrate="24k", placeholder_audio=False):
    plan = build_course_plan(course)[1] if audio else None
    css, sections, options, cards, sequences = None, [], [], [], {}
    used_german, used_explain, first_unit = set(), set(), {}
    for unit in course["units"]:
        uid, label = unit["id"], unit["label"]
        page = unit["sheet"].read_text(encoding="utf-8")
        require('name="study-pack-status" content="reviewed"' in page, f"{uid}: only reviewed sheets go into the app")
        lesson = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))
        css = css or re.search(r"<style>(.*?)</style>", page, re.S).group(1)
        if audio:
            unit_plan = plan["units"][uid]
            page = add_audio_buttons(page, lesson, unit_plan, used_german)
            sequences[uid] = listening(uid, lesson, unit_plan, set())
            for grammar_parts in unit_plan["grammar"].values():
                used_explain.update(v for v in grammar_parts.values() if v)
            used_german.update([unit_plan["title"]] + list(unit_plan["sections"].values()))
            for cid in used_german | used_explain:
                first_unit.setdefault(cid, len(sections))
        body = re.search(r'<main class="wrap">(.*?)</main>', page, re.S).group(1)
        if audio:
            body = body.replace("</header>", f'<div class="listen-row"><button type="button" class="listen-all" data-unit="{uid}">'
                                             f'▶ Ganze Lektion anhören</button></div></header>', 1)
        title = html.unescape(re.search(r"<h1>(.*?)</h1>", body).group(1))
        options.append(f'<option value="{uid}">{html.escape(label)} · {html.escape(title.split(" – ")[0])}</option>')
        for kind, cid, inner in re.findall(r'<article class="(voc|rule|phrase)" id="([^"]+)">(.*?)</article>', body, re.S):
            card = {"u": uid, "l": label, "id": f"{uid}-{cid}", "k": KIND[kind], "b": inner}
            if kind == "voc":
                m = re.search(r'<span class="de">(.*?)</span>(?:<button[^>]*>.*?</button>)?<span class="en">(.*?)</span>', inner, re.S)
                card.update(f=m.group(1), r=m.group(2))
                if audio:
                    card["fa"] = plan["units"][uid]["controls"][f"{cid}-head"]
            elif kind == "rule":
                card["f"] = re.sub(r"<button.*?</button>", "", re.search(r"<h3>(.*?)</h3>", inner, re.S).group(1), flags=re.S)
            else:
                meaning = re.search(r'<p class="meaning">(.*?)</p>', inner, re.S).group(1)
                when = re.search(r'<div class="when">(.*?)</div>', inner, re.S).group(1)
                card["f"] = f'<span class="q-mean">{meaning}</span><span class="q-when">{when}</span>'
                if audio:
                    card["ba"] = plan["units"][uid]["controls"][f"{cid}-head"]
            cards.append(card)
        body = re.sub(r' id="([^"]+)"', lambda m: f' id="{uid}-{m.group(1)}"', body)
        sections.append(f'<section class="unit" id="{uid}">{body}</section>')

    payloads = {}
    if audio and not placeholder_audio:
        ff = ffmpeg_exe()
        jobs = [(cid, bitrate) for cid in sorted(used_german)] + [(cid, explain_bitrate) for cid in sorted(used_explain - used_german)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for cid, data in zip([j[0] for j in jobs], pool.map(lambda j: compressed(course["cache"], j[0], j[1], ff), jobs)):
                payloads[cid] = data
    config = {"key": slug(course["title"]), "perDay": int(course.get("new_per_day", 20)),
              "units": [[u["id"], u["id"]] for u in course["units"]]}
    blocks = {}
    for cid, data in payloads.items():
        blocks.setdefault(first_unit[cid], []).append(f"{cid}:{data}")
    audio_blocks = "".join(f'<script type="text/plain" id="au-{k}">{";".join(v)}</script>\n' for k, v in sorted(blocks.items()))
    index = {cid: first_unit[cid] for cid in payloads}
    js = (APP_JS.replace("__INDEX__", json.dumps(index, separators=(",", ":")))
          .replace("__SEQUENCES__", json.dumps(sequences, separators=(",", ":")))
          .replace("__CARDS__", json.dumps(cards, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
          .replace("__ORDER__", json.dumps([u["id"] for u in course["units"]]))
          .replace("__CONFIG__", json.dumps(config, ensure_ascii=False)))
    subtitle = html.escape(course.get("subtitle", f"{len(course['units'])} Lektionen · Wortschatz · Grammatik · Redemittel"))
    doc = f"""<!DOCTYPE html>
<html lang="de"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="study-pack-app" content="course v1">
<title>{html.escape(course['title'])}</title>
<style>{css}{AUDIO_CSS if audio else ''}{APP_CSS}</style>
</head>
<body><main class="wrap">
<nav class="bar" aria-label="Navigation">
<div class="tabs"><button type="button" id="tab-l" aria-pressed="true">Lernen</button><button type="button" id="tab-p" aria-pressed="false">Üben</button></div>
<button class="nav lern-only" id="prev" type="button" aria-label="Vorherige Lektion">‹</button>
<select class="lern-only" id="pick" aria-label="Lektion wählen">{''.join(options)}</select>
<button class="nav lern-only" id="next" type="button" aria-label="Nächste Lektion">›</button>
<input class="lern-only" id="q" type="search" placeholder="Suchen…" aria-label="Suchen">
<div class="hits lern-only" id="hits"></div>
</nav>
<noscript><p class="cover">Audio und Üben brauchen einen Browser mit JavaScript.</p></noscript>
<div class="lernen">
<div class="cover"><b>{html.escape(course['title'])}</b>{subtitle}</div>
{''.join(sections)}
</div>
{PRACTICE}
</main>
<script>{js}</script>
{audio_blocks}
</body></html>
"""
    require("http://" not in doc and "https://" not in doc, "output unexpectedly contains an external URL")
    output = Path(output)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(doc)
    return {"cards": len(cards), "clips": len(payloads), "bytes": output.stat().st_size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--course", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-audio", action="store_true", help="Study and practice only, no embedded audio")
    parser.add_argument("--bitrate", default="32k", help="German clips (default 32k)")
    parser.add_argument("--explain-bitrate", default="24k", help="English grammar explanations (default 24k)")
    parser.add_argument("--placeholder-audio", action="store_true", help=argparse.SUPPRESS)  # silent buttons, for tests/screenshots
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), "output exists; choose a new versioned filename")
        require(args.output.suffix.lower() == ".html", "output must be an .html file")
        course = load_course(args.course)
        result = build(course, args.output, audio=not args.no_audio, bitrate=args.bitrate,
                       explain_bitrate=args.explain_bitrate, placeholder_audio=args.placeholder_audio)
        print(f"WROTE: {args.output} ({result['bytes'] / 1e6:.1f} MB): {len(course['units'])} units, "
              f"{result['cards']} cards, {result['clips']} embedded clips")
        return 0
    except (AudioError, OSError, json.JSONDecodeError, subprocess.CalledProcessError, AttributeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
