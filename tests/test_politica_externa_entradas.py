from pathlib import Path
import re
POLICY = (Path(__file__).resolve().parents[1] / 'asterisk/dialplan_politica_externa.conf').read_text()

def test_politica_inicia_negada_e_valida_antes_de_permitir():
    context = POLICY.split('[politica-externa]', 1)[1]
    allow = context.index('Set(GOSUB_RETVAL=ALLOW)')
    for fragment in ('Set(GOSUB_RETVAL=DENY)', 'REGEX("^t[0-9]+$"', 'REGEX("^[0-9]+$"'):
        assert context.index(fragment) < allow

def test_tenant_exige_identificador_numerico():
    pattern = re.compile(r'^t[0-9]+$')
    assert all(pattern.fullmatch(v) for v in ('t1', 't2', 't123'))
    assert all(not pattern.fullmatch(v) for v in ('', 'tenant1', 't1/../../', 't1;Dial', 'T1'))

def test_destino_exige_digitos():
    pattern = re.compile(r'^[0-9]+$')
    assert all(pattern.fullmatch(v) for v in ('1234', '0011442070000000', '5511999999999'))
    assert all(not pattern.fullmatch(v) for v in ('', '+55119999', '123/456', '123;Dial', '123 456'))
