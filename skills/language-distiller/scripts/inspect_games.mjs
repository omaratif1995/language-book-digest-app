#!/usr/bin/env node
// Real-browser check of a study app's games: plays them like a hurried thumb (check_games.js) at phone size.
import { spawn } from 'node:child_process';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const [browser, input, unitList] = process.argv.slice(2);
if (!browser || !input) {
  console.error('Usage: node inspect_games.mjs BROWSER_EXE STUDY_APP.html [UNIT,UNIT,...]   (default: the first two units)');
  process.exit(2);
}
const checker = await readFile(path.join(path.dirname(fileURLToPath(import.meta.url)), 'check_games.js'), 'utf8');

const profile = await mkdtemp(path.join(tmpdir(), 'language-pack-games-browser-'));
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
  const call = (method, params = {}, sessionId, ms = 20000) => new Promise((resolve, reject) => {
    const id = ++requestID;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, ms);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await call('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await call('Target.attachToTarget', { targetId, flatten: true });
  const pageCall = (method, params, ms) => call(method, params, sessionId, ms);
  await pageCall('Page.enable');
  await pageCall('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 2, mobile: true });
  await pageCall('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
  const loaded = new Promise((resolve, reject) => {
    const handler = event => {
      const message = JSON.parse(event.data);
      if (message.method === 'Page.loadEventFired' && message.sessionId === sessionId) {
        socket.removeEventListener('message', handler); clearTimeout(timer); resolve();
      }
    };
    const timer = setTimeout(() => { socket.removeEventListener('message', handler); reject(new Error('Page load timed out')); }, 60000);
    socket.addEventListener('message', handler);
  });
  await pageCall('Page.navigate', { url: pathToFileURL(path.resolve(input)).href });
  await loaded;
  const units = unitList ? JSON.stringify(unitList.split(',')) :
    "[...document.getElementById('pick').options].slice(0, 2).map(o => o.value)";
  const evaluated = await pageCall('Runtime.evaluate', {
    awaitPromise: true, returnByValue: true,
    expression: `window.GAME_CHECK = {units: ${units}, answers: 10};\n${checker}`,
  }, 30 * 60000);
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
