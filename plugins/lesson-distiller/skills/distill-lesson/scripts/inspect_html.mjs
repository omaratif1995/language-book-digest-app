#!/usr/bin/env node
// Optional real-browser layout check. Requires Node >=22 and a local Chromium browser.
// No package download, browser installation, or access to the user's browser profile.
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [browser, input, output] = process.argv.slice(2);
if (!browser || !input || !output) {
  console.error('Usage: node inspect_html.mjs BROWSER_EXE SHEET.html NEW_QA_DIRECTORY');
  process.exit(2);
}
const outputDir = path.resolve(output);
await mkdir(outputDir); // Deliberately fails if present: preserve prior evidence.
const profile = await mkdtemp(path.join(tmpdir(), 'language-pack-browser-'));
let child;
let socket;
const pending = new Map();
let requestID = 0;
try {
  child = spawn(browser, [
    '--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-component-update', '--disable-sync',
    '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
  ], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
  const endpoint = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Browser startup timed out')), 20000);
    let buffer = '';
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('exit', code => { clearTimeout(timer); reject(new Error(`Browser exited: ${code}`)); });
    child.stderr.on('data', chunk => {
      buffer += chunk;
      const match = buffer.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) { clearTimeout(timer); resolve(match[1]); }
    });
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (pending.has(message.id)) {
      const { resolve, reject, timer } = pending.get(message.id);
      pending.delete(message.id);
      clearTimeout(timer);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    }
  });
  const call = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++requestID;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, 15000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await call('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await call('Target.attachToTarget', { targetId, flatten: true });
  const pageCall = (method, params) => call(method, params, sessionId);
  await pageCall('Page.enable');
  await pageCall('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  const reports = [];
  for (const [name, width, height, mobile] of [['desktop', 1280, 960, false], ['mobile', 390, 844, true]]) {
    await pageCall('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
    const loaded = new Promise((resolve, reject) => {
      const handler = event => {
        const message = JSON.parse(event.data);
        if (message.method === 'Page.loadEventFired' && message.sessionId === sessionId) {
          socket.removeEventListener('message', handler); clearTimeout(timer); resolve();
        }
      };
      const timer = setTimeout(() => { socket.removeEventListener('message', handler); reject(new Error('Page load timed out')); }, 15000);
      socket.addEventListener('message', handler);
    });
    await pageCall('Page.navigate', { url: pathToFileURL(path.resolve(input)).href });
    await loaded;
    const evaluated = await pageCall('Runtime.evaluate', { awaitPromise: true, returnByValue: true, expression: `
      (async () => {
        await document.fonts.ready;
        const records = [...document.querySelectorAll('.voc,.rule,.phrase')];
        const hidden = records.filter(el => {
          const s = getComputedStyle(el);
          return s.display === 'none' || s.visibility === 'hidden' || el.getBoundingClientRect().height === 0;
        }).map(el => el.id);
        return {
          viewport: innerWidth, documentWidth: document.documentElement.scrollWidth,
          sections: [...document.querySelectorAll('h2')].map(el => el.textContent.trim().replace(/^[0-9]+/, '').trim()),
          hiddenRecords: hidden,
          foldingElements: document.querySelectorAll('details,[hidden],[aria-hidden="true"]').length,
          forbiddenMetaPanels: document.querySelectorAll('.goal,.start,.legend,.study-nav,.source-note,.summary,.practice,.quiz').length,
          vocabularyCards: document.querySelectorAll('.voc').length,
          vocabularyWithExamples: [...document.querySelectorAll('.voc')].filter(el => el.querySelector('.ex mark')?.textContent.trim()).length,
          phraseCards: document.querySelectorAll('.phrase').length,
          phrasesWithExamples: [...document.querySelectorAll('.phrase')].filter(el => el.querySelector('.ex mark')?.textContent.trim()).length,
          grammarRules: document.querySelectorAll('.rule').length,
          grammarWithTwoExamples: [...document.querySelectorAll('.rule')].filter(el => el.querySelectorAll('.ex mark').length >= 2).length,
          brokenLocalLinks: [...document.querySelectorAll('a[href^="#"]')].filter(el => !document.getElementById(el.hash.slice(1))).map(el => el.hash),
          overflowing: [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 10).map(el => el.id || el.className || el.tagName)
        };
      })()` });
    if (evaluated.exceptionDetails) throw new Error(JSON.stringify(evaluated.exceptionDetails));
    const report = { name, ...evaluated.result.value };
    reports.push(report);
    for (const [section, index] of [['top', -1], ['vocabulary', 0], ['grammar', 1], ['redemittel', 2]]) {
      await pageCall('Runtime.evaluate', { expression: index < 0 ? 'scrollTo(0,0)' : `document.querySelectorAll('h2')[${index}].scrollIntoView()` });
      const screenshot = await pageCall('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      await writeFile(path.join(outputDir, `${name}-${section}.png`), Buffer.from(screenshot.data, 'base64'), { flag: 'wx' });
    }
  }
  const passed = reports.every(report => report.documentWidth <= report.viewport + 1 && JSON.stringify(report.sections) === JSON.stringify(['Wortschatz','Grammatik','Redemittel']) && !report.hiddenRecords.length && !report.foldingElements && !report.forbiddenMetaPanels && !report.brokenLocalLinks.length && !report.overflowing.length && report.vocabularyCards === report.vocabularyWithExamples && report.phraseCards === report.phrasesWithExamples && report.grammarRules === report.grammarWithTwoExamples);
  const result = { input: path.resolve(input), passed, limitation: 'Layout checks and screenshots are not a source or language review.', temporaryBrowserProfile: profile, reports };
  await writeFile(path.join(outputDir, 'layout-report.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = passed ? 0 : 1;
  await call('Browser.close').catch(() => {});
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  for (const entry of pending.values()) clearTimeout(entry.timer);
  socket?.close();
  child?.kill();
}
