"""
Mesmo teste do admin-api (test_module_importability.py) - o queue-api
tem o mesmo padrão de test_server_routes.py lendo server.py como
texto, então um erro de sintaxe também passaria despercebido sem isso.
"""
import importlib
import pkgutil
from pathlib import Path

SERVICE_DIR = Path(__file__).parent.parent


def test_every_module_in_queue_api_is_importable():
    module_names = [
        name for _, name, is_pkg in pkgutil.iter_modules([str(SERVICE_DIR)])
        if not is_pkg
    ]
    assert module_names, "nenhum módulo encontrado - o teste em si está quebrado"

    for name in module_names:
        importlib.import_module(name)
