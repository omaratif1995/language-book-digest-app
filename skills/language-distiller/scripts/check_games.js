/* Plays every game of a built study app the way a hurried thumb does, and checks that each round makes sense.

   Run it inside the app page (inspect_games.mjs does that in headless Chrome; a browser console works too). It answers
   right with a double tap, taps again just after the next question appears, and reports:
   - a right answer that showed "wrong" for a moment (the flash learners notice),
   - a Hör-Bingo call whose sentence holds a second word of the card (two right answers),
   - a Satzbau sentence that is not 5–9 words, a Wortpaare round with two equal meanings, a Was-sagt-man option shown twice.
   Options: window.GAME_CHECK = {units: ['L01', 'L02'], answers: 10}. Resolves to {passed, units, problems}. */
(async () => {
  const opts = Object.assign({units: null, answers: 10}, window.GAME_CHECK || {});
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const until = async (test, ms = 4000) => { const end = Date.now() + ms; while (Date.now() < end) { if (test()) return true; await wait(40); } return false; };
  const $ = (sel, root = document) => root.querySelector(sel), $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const script = $$('script').map(s => s.text).find(t => t.includes(', G='));
  const G = JSON.parse(script.match(/, G=(\{.*?\});\n/s)[1].replace(/<\\\//g, '</'));
  const clipOf = {};                                   /* audio payload → clip id, to know which sentence Hör-Bingo plays */
  $$('script[type="text/plain"][id^="au-"]').forEach(block => block.textContent.split(';').forEach(pair => {
    const at = pair.indexOf(':'); if (at > 0) clipOf[pair.slice(at + 1)] = pair.slice(0, at); }));
  let played = '';
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () { this.muted = true;
    if (this.src.startsWith('data:audio/mpeg;base64,')) played = clipOf[this.src.slice(23)] || ''; return play.call(this); };
  const problems = [], report = {};
  const label = v => { const a = v.aa ? v.aa.join('/') : v.a; return a ? a + ' ' + v.w : v.w; };
  const tapTwice = async el => { el.click(); await wait(60); el.click(); };
  const flashed = () => !!$('#g-box .g-no, #g-box .r-opt.no, #g-box .a-card.bad');
  const close = async () => { const x = $('#g-box .g-close'); if (x) x.click(); await wait(250); };
  const ICON = {bingo: '🎱', paare: '🃏', satz: '🧩', art: '⚡', red: '💬'};           /* games are found by icon, in any language */
  const tileOf = key => $$('#g-menu .g-tile').find(t => $('.g-icon', t).textContent === ICON[key]);
  const start = async key => { const tile = tileOf(key); if (!tile) return false; tile.click(); await wait(400); return true; };

  async function bingo(u, g) {
    const r = {calls: 0, unclear: 0, flashes: 0};
    played = '';                                              /* the first call plays 0.3 s after the game opens */
    if (!await start('bingo')) return null;
    const board = $$('#g-box .b-cell').map(cell => g.v.findIndex(v => label(v) === cell.textContent.trim()));
    for (let guard = 0; guard < 40 && !$('#g-box .g-end'); guard++) {
      const cue = $('#g-box .b-cue');
      await until(() => $('.gap', cue) || played, 3000);
      const sentence = $('.gap', cue) ? cue.textContent : null;
      let word = -1, example = null;
      g.v.forEach((v, k) => v.x.forEach(x => { if ((sentence && x.de === sentence) || (!sentence && x.au === played)) { word = k; example = x; } }));
      if (!example) { problems.push(`${u} Hör-Bingo: could not tell which sentence was called`); break; }
      r.calls++;
      const own = board.indexOf(word), others = (example.m || []).filter(m => board.includes(m) && m !== word);   /* apps before 1.5 lack m */
      if (others.length) { r.unclear++; problems.push(`${u} Hör-Bingo: «${example.de}» holds ${others.length + 1} words of the card`); }
      const right = own >= 0 ? $$('#g-box .b-cell')[own] : $('#g-box .b-none');
      await wait(320);                                         /* the tap lock of a new call */
      await tapTwice(right);
      played = '';                                            /* listen for the next call */
      await wait(120);
      if (flashed()) { r.flashes++; problems.push(`${u} Hör-Bingo: a right answer showed wrong («${example.de}»)`); const next = $$('#g-box .g-acts button').pop(); if (next) next.click(); }
      const info = $('#g-box .g-info').textContent;
      await until(() => $('#g-box .g-end') || $('#g-box .g-info').textContent !== info, 4000);
      if (!$('#g-box .g-end')) { $$('#g-box .b-cell')[0].click(); await wait(80);  /* a stray tap right after the next call */
        if (flashed()) { r.flashes++; problems.push(`${u} Hör-Bingo: a tap right after a new call counted`); } }
    }
    await close(); return r;
  }

  async function satz(u, g) {
    const r = {sentences: 0, flashes: 0};
    if (!await start('satz')) return null;
    for (let guard = 0; guard < 12 && !$('#g-box .g-end'); guard++) {
      const s = g.s.find(x => x.en === $('#g-box .s-prompt').textContent);
      if (!s) { problems.push(`${u} Satzbau: unknown sentence`); break; }
      const want = s.de.trim().split(/\s+/);
      if (want.length < 5 || want.length > 9) problems.push(`${u} Satzbau: «${s.de}» has ${want.length} words`);
      r.sentences++;
      for (const w of want) { const tile = $$('#g-box .s-tile').find(t => !t.disabled && t.getAttribute('data-w') === w); await tapTwice(tile); }
      await wait(100);
      if (!$('#g-box .s-fb .g-ok')) { r.flashes++; problems.push(`${u} Satzbau: a right order was not accepted («${s.de}»)`); }
      $$('#g-box .g-acts button').pop().click(); await wait(250);
    }
    await close(); return r;
  }

  async function wendung(u, g) {
    const r = {questions: 0, flashes: 0};
    if (!await start('red')) return null;
    for (let guard = 0; guard < 12 && !$('#g-box .g-end'); guard++) {
      const sit = $('#g-box .r-sit div').textContent, phrase = g.r.find(x => x.w === sit);
      const options = $$('#g-box .r-opt').map(o => o.textContent);
      if (new Set(options).size !== options.length) problems.push(`${u} Was sagt man?: an option is shown twice («${sit}»)`);
      if (!phrase) { problems.push(`${u} Was sagt man?: unknown situation`); break; }
      r.questions++;
      await tapTwice($$('#g-box .r-opt').find(o => o.textContent === phrase.f)); await wait(100);
      if (flashed()) { r.flashes++; problems.push(`${u} Was sagt man?: a right answer showed wrong («${phrase.f}»)`); }
      $$('#g-box .g-acts button').pop().click(); await wait(250);
    }
    await close(); return r;
  }

  async function paare(u, g) {
    const r = {rounds: 0, flashes: 0};
    if (!await start('paare')) return null;
    for (let guard = 0; guard < 5 && !$('#g-box .g-end'); guard++) {
      const meanings = $$('#g-box .p-en').map(c => c.textContent);
      if (new Set(meanings).size !== meanings.length) problems.push(`${u} Wortpaare: two equal meanings in one round`);
      r.rounds++;
      for (const card of $$('#g-box .p-de')) {
        const v = g.v.find(x => label(x) === card.textContent.trim());
        card.click(); await wait(40);
        await tapTwice($$('#g-box .p-en').find(c => !c.disabled && c.textContent === v.g)); await wait(40);
      }
      if ($$('#g-box .p-card.shake').length) { r.flashes++; problems.push(`${u} Wortpaare: a right pair shook`); }
      const before = $('#g-box .g-info') && $('#g-box .g-info').textContent;
      await until(() => $('#g-box .g-end') || ($('#g-box .g-info') && $('#g-box .g-info').textContent !== before), 2000);
    }
    await close(); return r;
  }

  async function artikel(u) {
    const r = {answers: 0, flashes: 0};
    if (!await start('art')) return null;
    const nouns = Object.values(G).flatMap(unit => unit.v.filter(v => v.a));
    for (let n = 0; n < opts.answers; n++) {
      const word = $('#g-box .a-word').textContent, gloss = $('#g-box .a-gloss').textContent;
      const v = nouns.find(x => x.w === word && x.g === gloss) || nouns.find(x => x.w === word);
      const right = (v.aa || [v.a])[0], wrong = $$('#g-box .a-btns button').find(b => !(v.aa || [v.a]).includes(b.textContent));
      await tapTwice($$('#g-box .a-btns button').find(b => b.textContent === right));
      await until(() => $('#g-box .a-word').textContent !== word || $('#g-box .a-card.bad'), 1500);
      r.answers++;
      if ($('#g-box .a-card.bad')) { r.flashes++; problems.push(`${u} Der · Die · Das: a right article showed wrong (${right} ${word})`); await wait(1700); continue; }
      if (wrong) { wrong.click(); await wait(80);                 /* a late tap that lands on the next word */
        if ($('#g-box .a-card.bad')) { r.flashes++; problems.push(`${u} Der · Die · Das: a tap right after the next word counted`); await wait(1700); } }
      await wait(260);
    }
    await close(); return r;
  }

  document.getElementById('tab-g').click(); await wait(300);
  const pick = document.getElementById('pick');
  for (const u of opts.units || [...pick.options].map(o => o.value)) {
    pick.value = u; pick.dispatchEvent(new Event('change')); await wait(400);
    report[u] = {};
    for (const [key, run] of [['bingo', bingo], ['paare', paare], ['satz', satz], ['art', artikel], ['red', wendung]]) {
      if (tileOf(key)) report[u][key] = await run(u, G[u]);
    }
  }
  HTMLMediaElement.prototype.play = play;
  return {passed: problems.length === 0, units: report, problems};
})()
