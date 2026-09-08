"""
Mesmo teste do resto do projeto - garante que o módulo importa de
verdade, sem erro de sintaxe escondido atrás de testes baseados em
texto.
"""
import importlib
import pkgutil
from pathlib import Path

SERVICE_DIR = Path(__file__).parent.parent


def test_every_module_is_importable():
    module_names = [
        name for _, name, is_pkg in pkgutil.iter_modules([str(SERVICE_DIR)])
        if not is_pkg
    ]
    assert module_names, "nenhum módulo encontrado - o teste em si está quebrado"

    for name in module_names:
        importlib.import_module(name)
