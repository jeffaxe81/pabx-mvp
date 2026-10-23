const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');

test('webphone loads a real local JsSIP bundle with matching SRI and API', () => {
  const html = fs.readFileSync('webphone/index.html', 'utf8');
  const tag = html.match(/<script src="(vendor\/jssip-[^"]+\.js)" integrity="([^"]+)"[^>]*><\/script>/);
  assert.ok(tag, 'the real SIP dependency must be available locally');
  const code = fs.readFileSync('webphone/' + tag[1]);
  assert.equal(tag[2], 'sha384-' + crypto.createHash('sha384').update(code).digest('base64'));
  const context = vm.createContext({ window: {}, console, setTimeout, clearTimeout, navigator: { userAgent: 'AXE Lab' } });
  vm.runInContext(code.toString(), context, { timeout: 3000 });
  assert.equal(context.JsSIP.version, '3.10.1');
  assert.equal(typeof context.JsSIP.UA, 'function');
  assert.equal(typeof context.JsSIP.WebSocketInterface, 'function');
});

test('rebuilding the pinned SIP package reproduces the shipped asset', () => {
  assert.doesNotThrow(() => execFileSync(process.execPath, ['scripts/build_webphone_sip.cjs', '--check'], { stdio: 'pipe' }));
});
