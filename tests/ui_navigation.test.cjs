const assert = require('node:assert/strict');
const test = require('node:test');
const { buildPortalLinks } = require('../ui/navigation.js');

test('links keep the configured queue API across operational screens', () => {
  const links = buildPortalLinks('http://192.0.2.10:8082/index.html?api=http%3A%2F%2F192.0.2.10%3A8090');
  const reports = new URL(links.relatorios);
  assert.equal(reports.origin, 'http://192.0.2.10:8082');
  assert.equal(reports.pathname, '/relatorios.html');
  assert.equal(reports.searchParams.get('api'), 'http://192.0.2.10:8090');
  assert.equal(new URL(links.administracao).origin, 'http://192.0.2.10:8091');
  assert.equal(new URL(links.administracao).search, '');
});

test('admin links carry portal context in the fragment accepted by the static server', () => {
  const links = buildPortalLinks('https://pbx.example/phone/index.html?api=https%3A%2F%2Fapi.example&admin=https%3A%2F%2Fadmin.example%2F');
  const admin = new URL(links.administracao);
  assert.equal(admin.origin, 'https://admin.example');
  assert.equal(admin.search, '');
  const returning = buildPortalLinks(admin.href, { isAdmin: true });
  const phone = new URL(returning.telefonista);
  assert.equal(phone.origin, 'https://pbx.example');
  assert.equal(phone.pathname, '/phone/index.html');
  assert.equal(phone.searchParams.get('api'), 'https://api.example');
});

test('a reverse proxy prefix remains part of every webphone link', () => {
  const links = buildPortalLinks('https://pbx.example/voice/relatorios.html');
  assert.equal(new URL(links.operacao).pathname, '/voice/painel-operacional.html');
  assert.equal(new URL(links.campanhas).pathname, '/voice/campanhas.html');
});

test('admin defaults point to the webphone port, not the provisioning port', () => {
  const links = buildPortalLinks('http://192.0.2.20:8091/', { isAdmin: true });
  assert.equal(new URL(links.telefonista).origin, 'http://192.0.2.20:8082');
  assert.equal(new URL(links.telefonista).pathname, '/index.html');
});

test('only portal configuration is copied, never credentials or arbitrary query values', () => {
  const links = buildPortalLinks('http://pbx.example:8082/?api=http%3A%2F%2Fapi.example&token=secret&password=secret&tenant=t1&key=secret');
  for (const href of Object.values(links)) {
    assert.equal(href.includes('secret'), false);
    const params = new URL(href).searchParams;
    for (const key of ['token', 'password', 'key', 'tenant']) assert.equal(params.has(key), false);
  }
});

test('navigation ignores script URLs and URLs with embedded credentials', () => {
  const links = buildPortalLinks('http://pbx.example:8082/index.html?admin=javascript%3Aalert(1)&web=https%3A%2F%2Fuser%3Apass%40evil.example%2F&api=javascript%3Aalert(1)');
  assert.equal(new URL(links.administracao).origin, 'http://pbx.example:8091');
  assert.equal(new URL(links.telefonista).origin, 'http://pbx.example:8082');
  assert.equal(new URL(links.relatorios).searchParams.has('api'), false);
});

test('editing the webphone API input updates links without changing page location', () => {
  const links = buildPortalLinks('http://pbx.example:8082/index.html?api=http%3A%2F%2Fold.example', { api: 'https://queue.example' });
  assert.equal(new URL(links.operacao).searchParams.get('api'), 'https://queue.example');
});
