/* Shared portal navigation, embedded by scripts/sync_ui.py. */
(function () {
  'use strict';

  function httpUrl(value, fallback) {
    if (value) {
      try {
        const url = new URL(value);
        if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) return url;
      } catch (_) { /* Invalid configuration falls back to the current portal. */ }
    }
    return fallback ? new URL(fallback) : null;
  }

  function buildPortalLinks(locationHref, options = {}) {
    const current = new URL(locationHref);
    const context = current.hash.startsWith('#axe?')
      ? new URLSearchParams(current.hash.slice(5)) : new URLSearchParams();
    const setting = (key) => current.searchParams.get(key) || context.get(key);
    const defaultWeb = new URL(options.isAdmin ? '/' : './', current);
    if (options.isAdmin) defaultWeb.port = '8082';
    const web = httpUrl(setting('web'), defaultWeb.href);
    web.search = ''; web.hash = '';
    if (!web.pathname.endsWith('/')) web.pathname += '/';
    const defaultAdmin = new URL('/', current);
    defaultAdmin.port = '8091';
    const admin = httpUrl(setting('admin'), defaultAdmin.href);
    admin.search = ''; admin.hash = '';
    const api = httpUrl(options.api !== undefined ? options.api : setting('api'));
    const config = new URLSearchParams({ web: web.href, admin: admin.href });
    if (api) config.set('api', api.href.replace(/\/$/, ''));
    const links = {};
    for (const [key, path] of Object.entries({
      telefonista: 'index.html', operacao: 'painel-operacional.html',
      campanhas: 'campanhas.html', relatorios: 'relatorios.html',
    })) {
      const url = new URL(path, web);
      url.search = config.toString();
      links[key] = url.href;
    }
    // admin-api accepts / and /index.html exactly; fragments do not reach it.
    admin.hash = `axe?${config.toString()}`;
    links.administracao = admin.href;
    return links;
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { buildPortalLinks };
  if (typeof document === 'undefined') return;

  const page = document.body.dataset.axePage;
  const shell = document.getElementById('axeShell');
  if (!shell) return;
  const nav = document.getElementById('axeNavigation');
  const toggle = document.getElementById('axeCollapse');
  const mobileToggle = document.getElementById('axeMobileMenu');
  const backdrop = document.getElementById('axeBackdrop');
  const mobile = window.matchMedia('(max-width: 760px)');
  const apiInput = document.getElementById('queueApiUrl');
  const storedApi = new URL(window.location.href).searchParams.get('api');
  if (apiInput && httpUrl(storedApi)) apiInput.value = storedApi;

  function updateLinks() {
    const links = buildPortalLinks(window.location.href, {
      isAdmin: page === 'administracao', api: apiInput ? apiInput.value.trim() : undefined,
    });
    document.querySelectorAll('[data-axe-link]').forEach((link) => {
      if (link.href !== links[link.dataset.axeLink]) link.href = links[link.dataset.axeLink];
      if (page === 'telefonista' && link.dataset.axeLink !== page) {
        // Switching portal screens must not unload a live WebRTC call.
        link.target = '_blank'; link.rel = 'noopener';
        link.title = `${link.getAttribute('aria-label')} (abre em outra aba)`;
      }
    });
  }
  updateLinks();
  const shortcutObserver = new MutationObserver(updateLinks);
  document.querySelectorAll('#opsPanelLink, #reportsLink').forEach(link => {
    shortcutObserver.observe(link, { attributes: true, attributeFilter: ['href'] });
  });
  if (apiInput) apiInput.addEventListener('input', updateLinks);
  document.querySelectorAll('[data-axe-link][aria-current="page"]').forEach((link) => {
    link.addEventListener('click', (event) => event.preventDefault());
  });
  document.querySelector('.axe-skip-link').addEventListener('click', (event) => {
    // The admin portal configuration lives in the fragment; leave it intact.
    event.preventDefault();
    const content = document.getElementById('axeContent');
    content.focus(); content.scrollIntoView({ block: 'start' });
  });

  const connectionHint = document.getElementById('connectionHint');
  if (connectionHint) {
    const views = ['idleView', 'incomingView', 'activeView', 'consultView'].map(id => document.getElementById(id));
    const updateHint = () => { connectionHint.hidden = views.some(view => view.style.display && view.style.display !== 'none'); };
    const observer = new MutationObserver(updateHint);
    views.forEach(view => observer.observe(view, { attributes: true, attributeFilter: ['style'] }));
    updateHint();
  }

  const storageKey = 'axe-pabx-navigation-collapsed';
  function setCollapsed(collapsed) {
    shell.classList.toggle('axe-collapsed', collapsed);
    toggle.setAttribute('aria-expanded', String(!collapsed));
    toggle.setAttribute('aria-label', collapsed ? 'Expandir menu' : 'Recolher menu');
    toggle.title = toggle.getAttribute('aria-label');
    try { localStorage.setItem(storageKey, String(collapsed)); } catch (_) { /* Storage is optional. */ }
  }
  try { setCollapsed(localStorage.getItem(storageKey) === 'true'); } catch (_) { setCollapsed(false); }
  toggle.addEventListener('click', () => setCollapsed(!shell.classList.contains('axe-collapsed')));

  function setMobileOpen(open, restoreFocus = false) {
    shell.classList.toggle('axe-menu-open', open);
    backdrop.hidden = !open;
    mobileToggle.setAttribute('aria-expanded', String(open));
    mobileToggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    nav.inert = mobile.matches && !open;
    nav.setAttribute('aria-hidden', String(mobile.matches && !open));
    document.body.classList.toggle('axe-menu-lock', open && mobile.matches);
    if (open) nav.querySelector('a').focus();
    else if (restoreFocus) mobileToggle.focus();
  }
  mobileToggle.addEventListener('click', () => setMobileOpen(!shell.classList.contains('axe-menu-open')));
  backdrop.addEventListener('click', () => setMobileOpen(false, true));
  mobile.addEventListener('change', () => setMobileOpen(false));
  setMobileOpen(false);
  document.addEventListener('keydown', (event) => {
    if (!mobile.matches || !shell.classList.contains('axe-menu-open')) return;
    if (event.key === 'Escape') { setMobileOpen(false, true); return; }
    if (event.key !== 'Tab') return;
    const items = [...nav.querySelectorAll('a, button')].filter((item) => item.getClientRects().length && !item.disabled);
    const first = items[0]; const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  // Keep wide tables scrollable inside their card instead of expanding the page.
  document.querySelectorAll('.axe-content table').forEach((table) => {
    if (table.parentElement.classList.contains('axe-table-scroll')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'axe-table-scroll';
    table.before(wrapper); wrapper.append(table);
  });

  if (page !== 'administracao') return;
  const app = document.getElementById('appScreen');
  const menu = document.getElementById('axeAdminMenu');
  const role = document.getElementById('myRoleBadge');
  const heading = document.getElementById('axeAdminHeading');
  const sectionButtons = [...menu.querySelectorAll('[data-axe-section]')];
  let selected = 'ramais';

  function showSection(section) {
    selected = section;
    document.querySelectorAll('[data-axe-admin-group]').forEach((panel) => {
      // hidden=false preserves inline role restrictions applied by the existing login.
      panel.hidden = panel.dataset.axeAdminGroup !== section;
    });
    sectionButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.axeSection === section)));
    heading.textContent = sectionButtons.find((button) => button.dataset.axeSection === section).getAttribute('aria-label');
  }
  function updateAdminAccess() {
    const loggedIn = app.style.display === 'block';
    const isAdmin = role.textContent.trim() === 'admin';
    menu.hidden = !loggedIn;
    sectionButtons.forEach((button) => { button.hidden = button.hasAttribute('data-axe-admin-only') && !isAdmin; });
    if (!loggedIn || sectionButtons.find((button) => button.dataset.axeSection === selected).hidden) showSection('ramais');
  }
  sectionButtons.forEach((button) => button.addEventListener('click', () => {
    showSection(button.dataset.axeSection);
    if (mobile.matches) setMobileOpen(false, true);
    heading.focus();
  }));
  new MutationObserver(updateAdminAccess).observe(app, { attributes: true, attributeFilter: ['style'] });
  new MutationObserver(updateAdminAccess).observe(role, { childList: true, characterData: true, subtree: true });
  showSection('ramais'); updateAdminAccess();
})();
