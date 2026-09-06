"""
Testes do webphone/service-worker.js. Não executa o service worker de
verdade (isso exigiria um navegador) - checa estaticamente que os
handlers essenciais existem e fazem o que deveriam.
"""
from pathlib import Path

SERVICE_WORKER = Path(__file__).parent.parent / "webphone" / "service-worker.js"


def load_source():
    return SERVICE_WORKER.read_text(encoding="utf-8")


def test_has_install_and_activate_lifecycle():
    source = load_source()
    assert "addEventListener('install'" in source
    assert "addEventListener('activate'" in source


def test_caches_the_app_shell():
    source = load_source()
    assert "./index.html" in source
    assert "./manifest.json" in source
    assert "caches.open(" in source


def test_listens_for_incoming_call_message_from_page():
    """
    É esse listener que recebe o aviso da página (index.html) de que
    uma chamada chegou, e é o que permite mostrar notificação nativa
    mesmo com a aba em segundo plano.
    """
    source = load_source()
    assert "addEventListener('message'" in source
    assert "incoming-call" in source
    assert "showNotification(" in source


def test_notification_requires_interaction_and_does_not_stack():
    """
    requireInteraction garante que a notificação não some sozinha
    antes da telefonista ver; tag+renotify garante que uma segunda
    chamada não empilha notificações antigas confusas.
    """
    source = load_source()
    assert "requireInteraction: true" in source
    assert "tag:" in source
    assert "renotify: true" in source


def test_notification_click_focuses_or_opens_window():
    source = load_source()
    assert "addEventListener('notificationclick'" in source
    assert "client.focus()" in source
    assert "openWindow(" in source


def test_fetch_handler_does_not_intercept_dynamic_requests():
    """
    Sanity check importante: o cache é só pro app shell. Se o
    fetch handler interceptasse tudo, dados da fila/gravações/
    métricas em tempo real poderiam vir de cache velho por engano.
    """
    source = load_source()
    fetch_start = source.index("addEventListener('fetch'")
    fetch_end = source.index("});", fetch_start)
    body = source[fetch_start:fetch_end]
    assert "isShellRequest" in body
    assert "if (!isShellRequest) return;" in body
