from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
DIAL = (ROOT / 'asterisk/extensions.conf').read_text(encoding='utf-8')
POLICY = (ROOT / 'asterisk/dialplan_politica_externa.conf').read_text(encoding='utf-8')

def section(name):
    start = DIAL.index('[' + name + ']')
    end = DIAL.find('\n[', start + 1)
    return DIAL[start:end if end >= 0 else None]

def test_isolamento_entre_t1_e_t2():
    for tenant, other in (('t1','t2'),('t2','t1')):
        block = section(tenant + '-internal')
        outgoing = block[block.index('exten => _0.,1,'): ]
        assert 'Set(TENANT=' + tenant + ')' in outgoing
        assert 'DB(blocklist-' + tenant + '/' in outgoing
        assert 'DB(blocklist-' + other + '/' not in outgoing
        assert 'Gosub(politica-externa,s,1)' in outgoing

def test_familia_de_politica_por_tenant():
    assert 'politica-externa-${TENANT}/internacional' in POLICY
    assert 'politica-externa-t1/internacional' not in POLICY
    assert 'politica-externa-t2/internacional' not in POLICY

def test_contextos_de_saida_nao_misturam_identidade():
    for tenant in ('t1','t2'):
        outgoing = section(tenant + '-internal')
        assert 'Set(TENANT=' + tenant + ')' in outgoing
        assert 'Set(TENANT=' + ('t2' if tenant == 't1' else 't1') + ')' not in outgoing
