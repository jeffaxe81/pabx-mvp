"""Embed the shared AXE portal into the existing standalone HTML pages.

Both nginx and admin-api keep serving their original HTML without new
routes, a JavaScript build toolchain, or shared cross-origin asset requests.
Run with --check in CI to detect a stale embedded copy.
"""
import argparse
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    "webphone/index.html": ("telefonista", "Telefonista", "Atenda, disque e acompanhe as chamadas do seu ramal."),
    "webphone/painel-operacional.html": ("operacao", "Painel operacional", "Acompanhe filas, ramais e indicadores de atendimento."),
    "webphone/campanhas.html": ("campanhas", "Campanhas", "Organize a discagem e acompanhe os retornos de chamada."),
    "webphone/relatorios.html": ("relatorios", "Relatórios", "Consulte os resultados por período, atendente e empresa."),
    "admin/index.html": ("administracao", "Administração", "Gerencie ramais, atendimento e configurações do PABX."),
}
ICONS = {
    "telefonista": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2A19.8 19.8 0 0 1 3.1 5.2 2 2 0 0 1 5.1 3h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.6a2 2 0 0 1-.5 2.1L9 10.6a16 16 0 0 0 4.4 4.4l1.2-1.2a2 2 0 0 1 2.1-.5c.8.3 1.7.5 2.6.6a2 2 0 0 1 1.7 2z"/><path d="M15 3a6 6 0 0 1 6 6"/>',
    "operacao": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "campanhas": '<path d="m3 11 18-5v12L3 13zM7 14l1 6h4l-2-7"/>',
    "relatorios": '<path d="M3 3v18h18M8 16v-4M13 16V8M18 16V5"/>',
    "administracao": '<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7z"/><path d="m8 12 3 3 5-6"/>',
    "ramais": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h.01M15 11h.01M9 15h.01M15 15h.01"/>',
    "atendimento": '<path d="M3 12a9 9 0 0 1 18 0v6a3 3 0 0 1-3 3h-6"/><rect x="3" y="11" width="4" height="7" rx="2"/><rect x="17" y="11" width="4" height="7" rx="2"/>',
    "seguranca": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4M12 15v2"/>',
    "usuarios": '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-3-5"/>',
    "empresas": '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 21v-4h6v4M8 7h2M14 7h2M8 11h2M14 11h2"/>',
    "audios": '<path d="M9 18V5l12-2v13M9 8l12-2"/><ellipse cx="6" cy="18" rx="3" ry="3"/><ellipse cx="18" cy="16" rx="3" ry="3"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "collapse": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
}


def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'


def shell_start(page, title):
    labels = {"telefonista": "Telefonista", "operacao": "Painel operacional", "campanhas": "Campanhas", "relatorios": "Relatórios", "administracao": "Administração"}
    links = []
    for key, label in labels.items():
        active = ' aria-current="page"' if key == page else ''
        path = {"telefonista": "index.html", "operacao": "painel-operacional.html", "campanhas": "campanhas.html", "relatorios": "relatorios.html", "administracao": "/"}[key]
        links.append(f'<a class="axe-nav-link" data-axe-link="{key}" href="{path}" aria-label="{label}" title="{label}"{active}>{icon(key)}<span>{label}</span></a>')
    admin_menu = ''
    if page == 'administracao':
        sections = {"ramais": "Ramais", "atendimento": "Atendimento", "seguranca": "Segurança", "usuarios": "Usuários", "empresas": "Empresas", "audios": "Áudios e IA"}
        buttons = []
        for key, label in sections.items():
            restricted = ' data-axe-admin-only' if key in {'usuarios', 'empresas', 'audios'} else ''
            buttons.append(f'<button type="button" class="axe-section-button" data-axe-section="{key}" aria-label="{label}" aria-pressed="false" title="{label}"{restricted}>{icon(key)}<span>{label}</span></button>')
        admin_menu = '<div class="axe-admin-menu" id="axeAdminMenu" hidden><p class="axe-nav-label">Configurações</p>' + '\n'.join(buttons) + '</div>'
    content_tag = 'div' if page == 'telefonista' else 'main'
    return f'''<!-- AXE shell:start -->
<a class="axe-skip-link" href="#axeContent">Ir para o conteúdo</a>
<div class="axe-shell" id="axeShell">
  <aside class="axe-navigation" id="axeNavigation" aria-label="Menu do PABX">
    <div class="axe-brand">
      <span class="axe-brand-icon">{icon('telefonista')}</span>
      <div class="axe-brand-copy"><small>AXE Sistemas</small><strong>AXE PABX</strong></div>
    </div>
    <p class="axe-nav-label">Portal operacional</p>
    <nav class="axe-links" aria-label="Navegação principal">{' '.join(links)}</nav>
{admin_menu}
    <div class="axe-nav-footer">
      <p>Telefonia e atendimento<br>PABX-MVP</p>
      <button type="button" class="axe-collapse" id="axeCollapse" aria-label="Recolher menu" aria-expanded="true" aria-controls="axeNavigation">{icon('collapse')}<span>Recolher menu</span></button>
    </div>
  </aside>
  <div class="axe-workspace">
    <header class="axe-topbar">
      <button type="button" class="axe-mobile-toggle" id="axeMobileMenu" aria-label="Abrir menu" aria-controls="axeNavigation" aria-expanded="false">{icon('menu')}</button>
      <div class="axe-topbar-copy"><p>Portal operacional</p><small>AXE PABX · {escape(title)}</small></div>
      <span class="axe-product-badge">PABX-MVP</span>
    </header>
    <{content_tag} class="axe-content" id="axeContent" tabindex="-1">
<!-- AXE shell:content -->'''


def render_page(source, page, title, css, js):
    source = re.sub(r'<!-- AXE design:start -->.*?<!-- AXE design:end -->\s*', '', source, flags=re.S)
    source = re.sub(r'<!-- AXE shell:start -->.*?<!-- AXE shell:content -->\s*', '', source, flags=re.S)
    source = re.sub(r'<!-- AXE shell:close -->.*?<!-- AXE shell:end -->\s*', '', source, flags=re.S)
    source = re.sub(r'<!-- AXE navigation:start -->.*?<!-- AXE navigation:end -->\s*', '', source, flags=re.S)
    source = re.sub(r'<body(?: data-axe-page="[^"]+")?>\s*', f'<body data-axe-page="{page}">\n', source, count=1)
    source = source.replace('</head>', f'<!-- AXE design:start -->\n<style id="axeDesign">\n{css.rstrip()}\n</style>\n<!-- AXE design:end -->\n</head>', 1)
    source = source.replace(f'<body data-axe-page="{page}">', f'<body data-axe-page="{page}">\n{shell_start(page, title)}', 1)
    head, body = source.split('</head>', 1)
    content_tag = 'div' if page == 'telefonista' else 'main'
    close = f'''<!-- AXE shell:close -->
    </{content_tag}>
  </div>
</div>
<button type="button" class="axe-backdrop" id="axeBackdrop" aria-label="Fechar menu" tabindex="-1" hidden></button>
<!-- AXE shell:end -->
'''
    body = body.replace('<script>', close + '\n<script>', 1)
    source = head + '</head>' + body
    source = source.replace('</body>', f'<!-- AXE navigation:start -->\n<script>\n{js.rstrip()}\n</script>\n<!-- AXE navigation:end -->\n</body>', 1)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    css = (ROOT / 'ui/axe-ui.css').read_text(encoding='utf-8')
    js = (ROOT / 'ui/navigation.js').read_text(encoding='utf-8')
    changed = []
    for path, (page, title, _) in PAGES.items():
        file = ROOT / path
        original = file.read_text(encoding='utf-8')
        result = render_page(original, page, title, css, js)
        if original != result:
            changed.append(path)
            if not args.check:
                file.write_text(result, encoding='utf-8')
    if args.check and changed:
        parser.exit(1, 'HTML fora de sincronia: ' + ', '.join(changed) + '\nExecute python3 scripts/sync_ui.py\n')
    print('UI sincronizada: ' + str(len(PAGES)) + ' páginas.')


if __name__ == '__main__':
    main()
