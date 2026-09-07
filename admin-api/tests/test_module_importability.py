"""
Auditoria encontrou um erro de sintaxe real em ami_client.py que
nunca foi pego por nenhum teste, porque test_server_security.py só lê
server.py como TEXTO (pra checar decisões de segurança), nunca faz
`import server` de verdade - e nenhum outro teste importava
ami_client.py diretamente. Este teste fecha esse buraco: importa cada
módulo Python do serviço de verdade, garantindo que pelo menos
compila e roda o nível de módulo sem erro.
"""
import importlib
import pkgutil
from pathlib import Path

SERVICE_DIR = Path(__file__).parent.parent


def test_every_module_in_admin_api_is_importable():
    module_names = [
        name for _, name, is_pkg in pkgutil.iter_modules([str(SERVICE_DIR)])
        if not is_pkg
    ]
    assert module_names, "nenhum módulo encontrado - o teste em si está quebrado"

    for name in module_names:
        importlib.import_module(name)  # lança exceção se houver erro de sintaxe/import
