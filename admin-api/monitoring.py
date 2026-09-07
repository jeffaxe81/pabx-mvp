"""
PIN de monitoramento de chamada (backlog #42) - protege quem pode
usar escuta silenciosa/sussurro/intercalação. Guardado no AstDB
(família "monitoring-pin-{tenant}"), mesmo padrão do modo feriado e
da lista VIP.

Lógica pura de validação aqui - a escrita de verdade fica isolada no
server.py/ami_client.py, mesmo padrão do resto do projeto.
"""
import re

PIN_RE = re.compile(r"^[0-9]{4,10}$")


def validate_monitoring_pin_input(data: dict):
    """
    Retorna (ok, error_message, cleaned_pin). PIN só numérico, 4-10
    dígitos - curto o suficiente pra digitar rápido no teclado do
    telefone, longo o suficiente pra não ser "1234" por acidente
    (mas não impede escolher isso, a responsabilidade é de quem
    configura).
    """
    pin = (data.get("pin") or "").strip()
    if not PIN_RE.match(pin):
        return False, "PIN deve ter de 4 a 10 dígitos numéricos", None
    return True, None, pin
