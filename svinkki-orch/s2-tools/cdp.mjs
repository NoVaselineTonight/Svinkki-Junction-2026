// Minimal CDP driver for headless Edge (agent-s2's own verification tool; not part of the repo).
// Usage: node cdp.mjs <script.mjs>  -- the script exports default async function(b) using the helpers below.
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9322;
const profile = mkdtempSync(join(tmpdir(), 's2edge-'));
const proc = spawn(EDGE, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--disable-extensions', '--window-size=390,844', 'about:blank'], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function targets() {
  for (let i = 0; i < 50; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json`); return await r.json(); } catch (e) { await sleep(200); }
  }
  throw new Error('no CDP');
}
const page = (await targets()).find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const waiting = new Map(); const logs = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
  if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.type + ': ' + m.params.args.map((a) => a.value ?? a.description).join(' '));
  if (m.method === 'Runtime.exceptionThrown') logs.push('EXCEPTION: ' + JSON.stringify(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
});
function send(method, params = {}) {
  return new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
}
await send('Runtime.enable');
await send('Page.enable');
const W = Number(process.env.W || 390), H = Number(process.env.H || 844);
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 2, mobile: true });
await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });

const b = {
  send, sleep, logs,
  async eval(expr) {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.result.exceptionDetails) throw new Error('eval failed: ' + expr + '\n' + JSON.stringify(r.result.exceptionDetails.exception?.description));
    return r.result.result.value;
  },
  async go(url) { await send('Page.navigate', { url }); await sleep(800); },
  async until(expr, ms = 15000) {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) { if (await b.eval(expr)) return true; await sleep(150); }
    throw new Error('timeout waiting for: ' + expr);
  },
  async shot(file) {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(file, Buffer.from(r.result.data, 'base64'));
  },
  async tap(x, y) {
    await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  },
  async back() { const h = await send('Page.getNavigationHistory'); const i = h.result.currentIndex; if (i > 0) await send('Page.navigateToHistoryEntry', { entryId: h.result.entries[i - 1].id }); await sleep(400); },
  async history() { const h = await send('Page.getNavigationHistory'); return h.result; },
};

const script = (await import('file:///' + process.argv[2].replace(/\\/g, '/'))).default;
let code = 0;
try { await script(b); } catch (e) { console.log('FAILED:', e.message); code = 1; }
if (logs.length) console.log('--- page console ---\n' + logs.join('\n'));
ws.close(); proc.kill();
process.exit(code);
