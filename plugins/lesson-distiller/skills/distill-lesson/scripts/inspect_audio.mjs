#!/usr/bin/env node
// Real-browser smoke test for the embedded individual and whole-lesson controls.
import { spawn } from 'node:child_process';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [browser, input] = process.argv.slice(2);
if (!browser || !input) {
  console.error('Usage: node inspect_audio.mjs BROWSER_EXE AUDIO_SHEET.html');
  process.exit(2);
}

const profile = await mkdtemp(path.join(tmpdir(), 'language-pack-audio-browser-'));
let child;
let socket;
const pending = new Map();
let requestID = 0;
try {
  child = spawn(browser, [
    '--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-component-update', '--disable-sync',
    '--autoplay-policy=no-user-gesture-required', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, 'about:blank',
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
    if (!pending.has(message.id)) return;
    const { resolve, reject, timer } = pending.get(message.id);
    pending.delete(message.id);
    clearTimeout(timer);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
  });
  const call = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++requestID;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, 20000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await call('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await call('Target.attachToTarget', { targetId, flatten: true });
  const pageCall = (method, params) => call(method, params, sessionId);
  await pageCall('Page.enable');
  const loaded = new Promise((resolve, reject) => {
    const handler = event => {
      const message = JSON.parse(event.data);
      if (message.method === 'Page.loadEventFired' && message.sessionId === sessionId) {
        socket.removeEventListener('message', handler); clearTimeout(timer); resolve();
      }
    };
    const timer = setTimeout(() => { socket.removeEventListener('message', handler); reject(new Error('Page load timed out')); }, 20000);
    socket.addEventListener('message', handler);
  });
  await pageCall('Page.navigate', { url: pathToFileURL(path.resolve(input)).href });
  await loaded;
  const evaluated = await pageCall('Runtime.evaluate', {
    awaitPromise: true, returnByValue: true, expression: `
      (async () => {
        const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
        const first = document.querySelector('.speak-button');
        const full = document.getElementById('listen-all');
        const meta = document.querySelector('meta[name="study-pack-audio"]')?.content;
        if (!first || !full) return { passed:false, error:'controls missing' };
        first.click();
        await wait(350);
        const individualStarted = first.classList.contains('is-playing');
        first.click();
        await wait(250);
        full.click();
        await wait(350);
        const wholeStarted = full.classList.contains('is-playing') && full.textContent.includes('Pause');
        full.click();
        const wholePaused = !full.classList.contains('is-playing') && full.textContent.includes('Resume');
        return {
          passed: meta === 'embedded' && individualStarted && wholeStarted && wholePaused,
          embeddedMeta: meta,
          speakerButtons: document.querySelectorAll('.speak-button').length,
          individualStarted, wholeStarted, wholePaused,
          wholeLabelAfterPause: full.textContent.trim(),
        };
      })()`
  });
  if (evaluated.exceptionDetails) throw new Error(JSON.stringify(evaluated.exceptionDetails));
  const result = evaluated.result.value;
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.passed ? 0 : 1;
  await call('Browser.close').catch(() => {});
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  for (const entry of pending.values()) clearTimeout(entry.timer);
  socket?.close();
  child?.kill();
}
