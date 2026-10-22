/* Optional browser regression suite: npm install --no-save playwright,
   npx playwright install chromium, node --test tests/ui_browser.test.cjs.
   APIs below are test fixtures; this does not make SIP calls. */
const assert = require('node:assert/strict');
const { test, before, after } = require('node:test');
const { chromium } = require('playwright');
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
let browser, server, origin;
let fixtureRole = 'admin';
const metrics = { total_calls: 120, answered_calls: 112, missed_calls: 8, average_talk_seconds: 142, missed_rate_percent: 6.7 };
const extension = { name: 'vendas-1', display_name: 'Vendas 1', number: '1100', tenant: 't1', email: '' };

before(async () => {
  server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname.startsWith('/api/')) {
      const fixtures = {
        '/api/login': { token: 'fixture-session', role: fixtureRole }, '/api/logout': {},
        '/api/extensions': { extensions: [extension] }, '/api/blocklist': { numbers: [] },
        '/api/vip': { vips: [] }, '/api/config/modo-feriado': { enabled: false },
        '/api/config/overflow-timeout': { timeout: 45 },
        '/api/users': { users: [{ username: 'operador', role: 'supervisor', totp_enabled: false }] },
        '/api/tenants': { tenants: [] }, '/api/monitoring-pin': { configured: false }, '/api/sounds': { sounds: [] },
        '/api/metrics/today': metrics, '/api/reports': metrics,
        '/api/extension-states': { extensions: [{ exten: '1100', status_label: 'livre' }] },
        '/api/queue': { waiting: [] }, '/api/fraud-alerts': { alerts: [] }, '/api/quality': { quality_reports: [] },
        '/api/metrics/sla': { queues: {} }, '/api/reports/pauses': { by_reason: {} },
        '/api/metrics/sla/history': { by_date: {} }, '/api/campaigns': { campaigns: [] }, '/api/callbacks': { callbacks: [] },
      };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(fixtures[url.pathname] || {})); return;
    }
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    if (!file.startsWith(root + path.sep)) { res.writeHead(404); res.end(); return; }
    try {
      const contents = await fs.readFile(file);
      const mime = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png' }[path.extname(file)];
      res.writeHead(200, { 'Content-Type': mime || 'application/octet-stream' }); res.end(contents);
    } catch (_) { res.writeHead(404); res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({
    headless: true, executablePath: process.env.PABX_BROWSER_EXECUTABLE || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
});
after(async () => {
  if (browser) await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
});

function portalUrl(file) {
  const config = new URLSearchParams({ api: origin, web: origin + '/webphone/', admin: origin + '/admin/index.html' });
  return `${origin}/${file}${file.startsWith('admin/') ? '#axe?' : '?'}${config}`;
}
async function openPage(file, viewport = { width: 1366, height: 900 }) {
  const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
  await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(portalUrl(file));
  return { context, page, errors };
}
async function screenshot(page, name) {
  if (!process.env.PABX_UI_SCREENSHOTS_DIR) return;
  await fs.mkdir(process.env.PABX_UI_SCREENSHOTS_DIR, { recursive: true });
  await page.screenshot({ path: path.join(process.env.PABX_UI_SCREENSHOTS_DIR, name + '.png'), fullPage: true });
}
async function login(page, role) {
  fixtureRole = role;
  await page.locator('#loginPass').fill('fixture-password');
  await page.locator('#loginBtn').click();
  await page.locator('#axeAdminMenu').waitFor({ state: 'visible' });
}

for (const [file, pageName] of [
  ['webphone/index.html', 'telefonista'], ['webphone/painel-operacional.html', 'operacao'],
  ['webphone/campanhas.html', 'campanhas'], ['webphone/relatorios.html', 'relatorios'], ['admin/index.html', 'administracao'],
]) {
  test(`${pageName}: portal loads without script errors or page overflow`, async () => {
    const { context, page, errors } = await openPage(file);
    try {
      assert.equal(await page.locator('[data-axe-link][aria-current="page"]').getAttribute('data-axe-link'), pageName);
      assert.deepEqual(await page.evaluate(() => {
        const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
        return ids.filter((id, i) => ids.indexOf(id) !== i);
      }), []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      await screenshot(page, pageName + '-desktop');
    } finally { await context.close(); }
  });
}

test('collapse preference survives reload and active portal links do not reload the console', async () => {
  const { context, page, errors } = await openPage('webphone/index.html');
  try {
    await page.locator('#axeCollapse').click();
    assert.equal(await page.locator('#axeShell').evaluate(el => el.classList.contains('axe-collapsed')), true);
    await page.reload();
    assert.equal(await page.locator('#axeCollapse').getAttribute('aria-expanded'), 'false');
    await page.evaluate(() => { window.consoleMarker = 'preserved'; });
    await page.locator('[data-axe-link="telefonista"]').click();
    assert.equal(await page.evaluate(() => window.consoleMarker), 'preserved');
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});

test('connection guidance disappears when an existing call view becomes visible', async () => {
  const { context, page } = await openPage('webphone/index.html');
  try {
    assert.equal(await page.locator('#connectionHint').isVisible(), true);
    await page.locator('#idleView').evaluate(el => { el.style.display = 'flex'; });
    await page.locator('#connectionHint').waitFor({ state: 'hidden' });
    await page.locator('#idleView').evaluate(el => { el.style.display = 'none'; });
    await page.locator('#connectionHint').waitFor({ state: 'visible' });
  } finally { await context.close(); }
});

for (const width of [1366, 1024, 900, 768, 390, 360]) {
  test(`telefonista: dialpad stays within the viewport at ${width}px`, async () => {
    const { context, page } = await openPage('webphone/index.html', { width, height: 900 });
    try {
      await page.locator('#idleView').evaluate(el => { el.style.display = 'flex'; });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    } finally { await context.close(); }
  });
}

test('operational shortcuts open a separate tab and preserve the configured API', async () => {
  const { context, page } = await openPage('webphone/index.html');
  try {
    await page.locator('#queueApiUrl').fill(origin);
    const popupPromise = page.waitForEvent('popup');
    await page.locator('.axe-links [data-axe-link="operacao"]').click();
    const popup = await popupPromise;
    await popup.waitForLoadState();
    assert.equal(new URL(popup.url()).pathname, '/webphone/painel-operacional.html');
    assert.equal(new URL(popup.url()).searchParams.get('api'), origin);
    assert.equal(new URL(page.url()).pathname, '/webphone/index.html');
  } finally { await context.close(); }
});

test('the existing reports shortcut preserves the configured administration portal', async () => {
  const { context, page } = await openPage('webphone/painel-operacional.html');
  try {
    await page.locator('#reportsLink').click();
    await page.waitForURL('**/relatorios.html?**');
    const admin = new URL(await page.locator('[data-axe-link="administracao"]').getAttribute('href'));
    assert.equal(admin.origin, origin);
    assert.equal(admin.pathname, '/admin/index.html');
  } finally { await context.close(); }
});

test('the existing phone shortcut retains portal context after the registration handler updates its href', async () => {
  const { context, page } = await openPage('webphone/index.html');
  try {
    // This is the exact href/style update performed by the existing registration handler.
    await page.locator('#opsPanelLink').evaluate((el, api) => {
      el.href = `painel-operacional.html?api=${encodeURIComponent(api)}`;
      el.style.display = 'block';
    }, origin);
    const popupPromise = page.waitForEvent('popup');
    await page.locator('#opsPanelLink').click();
    const popup = await popupPromise;
    await popup.waitForLoadState();
    const admin = new URL(await popup.locator('[data-axe-link="administracao"]').getAttribute('href'));
    assert.equal(admin.origin, origin);
    assert.equal(admin.pathname, '/admin/index.html');
  } finally { await context.close(); }
});

test('the keyboard skip link preserves the admin portal configuration through reload', async () => {
  const { context, page } = await openPage('admin/index.html');
  try {
    const config = new URL(page.url()).hash;
    await page.locator('.axe-skip-link').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'axeContent');
    assert.equal(new URL(page.url()).hash, config);
    await page.reload();
    const phone = new URL(await page.locator('[data-axe-link="telefonista"]').getAttribute('href'));
    assert.equal(phone.origin, origin);
    assert.equal(phone.pathname, '/webphone/index.html');
    assert.equal(phone.searchParams.get('api'), origin);
  } finally { await context.close(); }
});

test('mobile menu supports Escape, restores focus and keeps the page within the viewport', async () => {
  const { context, page } = await openPage('webphone/painel-operacional.html', { width: 390, height: 844 });
  try {
    assert.equal(await page.locator('#axeNavigation').evaluate(el => el.inert), true);
    await page.locator('#axeMobileMenu').click();
    assert.equal(await page.locator('#axeNavigation').evaluate(el => el.inert), false);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#axeMobileMenu').getAttribute('aria-expanded'), 'false');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'axeMobileMenu');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await screenshot(page, 'operacao-mobile');
  } finally { await context.close(); }
});

test('administration displays the selected section and hides it again after logout', async () => {
  const { context, page, errors } = await openPage('admin/index.html');
  try {
    await login(page, 'admin');
    assert.equal(await page.locator('#extensionFormCard').isVisible(), true);
    assert.equal(await page.locator('#usersFormCard').isVisible(), false);
    await screenshot(page, 'administracao-ramais');
    await page.locator('[data-axe-section="usuarios"]').click();
    assert.equal(await page.locator('#usersFormCard').isVisible(), true);
    assert.equal(await page.locator('#extensionFormCard').isVisible(), false);
    await page.locator('[data-axe-section="atendimento"]').click();
    assert.equal(await page.locator('#holidayModeBtn').isVisible(), true);
    assert.equal(await page.locator('#vipFormCard').isVisible(), true);
    await page.locator('#logoutBtn').click();
    await page.locator('#loginScreen').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#axeAdminMenu').isVisible(), false);
    assert.equal(await page.locator('#appScreen').isVisible(), false);
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});

test('supervisor navigation preserves the existing administration restrictions', async () => {
  const { context, page, errors } = await openPage('admin/index.html', { width: 390, height: 844 });
  try {
    await login(page, 'supervisor');
    await page.locator('#axeMobileMenu').click();
    assert.equal(await page.locator('[data-axe-section="usuarios"]').isVisible(), false);
    assert.equal(await page.locator('[data-axe-section="empresas"]').isVisible(), false);
    assert.equal(await page.locator('[data-axe-section="audios"]').isVisible(), false);
    await page.locator('[data-axe-section="seguranca"]').click();
    assert.equal(await page.locator('#totpSetupBtn').isVisible(), true);
    assert.equal(await page.locator('#monitoringPinCard').isVisible(), false);
    assert.equal(await page.locator('#blocklistFormCard').isVisible(), false);
    assert.equal(await page.locator('#extensionFormCard').isVisible(), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    await screenshot(page, 'administracao-supervisor-mobile');
  } finally { await context.close(); }
});

test('administration treats hostile API values as text, never HTML', async () => {
  const { context, page, errors } = await openPage('admin/index.html');
  const hostile = '<img src=x onerror="window.__pabxXssTriggered=1">';
  const mock = {
    '/api/extensions': { extensions: [{ name: 'vendas-1', display_name: hostile, number: 1100, tenant: 't1' }] },
    '/api/blocklist': { numbers: [hostile] },
    '/api/vip': { vips: [{ number: '11999999999', target_extension: hostile }] },
    '/api/users': { users: [{ username: hostile, role: 'supervisor' }] },
  };
  try {
    await page.route('**/api/**', async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (mock[pathname]) {
        await route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify(mock[pathname]) });
      } else {
        await route.continue();
      }
    });
    await login(page, 'admin');
    for (const id of ['extensionsTableBody', 'blocklistTableBody', 'vipTableBody', 'usersTableBody']) {
      await page.locator('#' + id + ' tr').first().waitFor();
      assert.equal(await page.locator('#' + id + ' img').count(), 0);
      assert.ok((await page.locator('#' + id).innerText()).includes(hostile));
    }
    assert.equal(await page.evaluate(() => window.__pabxXssTriggered || 0), 0);
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});
