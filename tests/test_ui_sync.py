"""The embedder must preserve business markup and be safe to run repeatedly."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_ui', ROOT / 'scripts/sync_ui.py')
sync_ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_ui)


def test_repeated_sync_does_not_duplicate_shell_or_rewrite_business_content():
    source = '''<!DOCTYPE html><html><head><title>PABX</title></head><body>

<button id="connectBtn">Conectar</button><script>connectBusinessLogic();</script>
</body></html>'''
    once = sync_ui.render_page(source, 'telefonista', 'Telefonista', ':root {color: teal}', 'navigatePortal();')
    twice = sync_ui.render_page(once, 'telefonista', 'Telefonista', ':root {color: teal}', 'navigatePortal();')
    assert twice == once
    assert twice.count('id="axeShell"') == 1
    assert twice.count('id="connectBtn"') == 1
    assert twice.count('connectBusinessLogic();') == 1


def test_new_shared_source_replaces_old_embedded_copy():
    source = '<html><head></head><body><div id="queueList"></div><script>pollQueue();</script></body></html>'
    before = sync_ui.render_page(source, 'operacao', 'Painel operacional', '.old-style {}', 'oldNavigation();')
    after = sync_ui.render_page(before, 'operacao', 'Painel operacional', '.new-style {}', 'newNavigation();')
    assert '.old-style' not in after
    assert 'oldNavigation();' not in after
    assert after.count('.new-style') == 1
    assert after.count('newNavigation();') == 1
    assert after.count('pollQueue();') == 1
