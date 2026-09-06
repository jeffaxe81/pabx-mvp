"""
Verificação estática do server.py quanto à detecção de fraude
(backlog #32) - mesmo padrão já usado em test_server_routes.py.
"""
from pathlib import Path

SERVER_PY = Path(__file__).parent.parent / "server.py"


def load_source():
    return SERVER_PY.read_text(encoding="utf-8")


def test_auto_block_disabled_by_default():
    source = load_source()
    assert 'FRAUD_AUTO_BLOCK = os.environ.get("FRAUD_AUTO_BLOCK", "false")' in source


def test_daily_cost_limit_disabled_by_default():
    source = load_source()
    assert 'FRAUD_DAILY_COST_LIMIT = float(os.environ.get("FRAUD_DAILY_COST_LIMIT", "0"))' in source


def test_auto_block_checks_feature_flag_before_calling_ami():
    """
    O bloqueio automático precisa checar FRAUD_AUTO_BLOCK antes de
    chamar a AMI - senão a "flag desligada por padrão" não protege
    nada de verdade.
    """
    source = load_source()
    fn_start = source.index("def check_call_volume")
    fn_end = source.index("\n\n\n", fn_start) if "\n\n\n" in source[fn_start:] else len(source)
    body = source[fn_start:fn_end]

    flag_pos = body.index("FRAUD_AUTO_BLOCK")
    block_call_pos = body.index("ami.block_number(")
    assert flag_pos < block_call_pos


def test_fraud_alerts_endpoint_registered():
    source = load_source()
    assert "/api/fraud-alerts" in source
    assert "fraud_alerts_log.list()" in source
