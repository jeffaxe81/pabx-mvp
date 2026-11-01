from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DIAL = (ROOT / 'asterisk/extensions.conf').read_text()
DYNAMIC = (ROOT / 'admin-api/tenants.py').read_text()

def test_tenant_dinamico_verifica_politica_antes_do_tronco():
    start = DYNAMIC.index('exten => _0.,1,Set(DESTINO=')
    end = DYNAMIC.index('exten => numero-bloqueado,1', start)
    outbound = DYNAMIC[start:end]
    assert outbound.index('Set(TENANT={tenant_id})') < outbound.index('Gosub(politica-externa,s,1)')
    assert outbound.index('Gosub(politica-externa,s,1)') < outbound.index('Dial(PJSIP/')

def test_tenant_dinamico_nao_usa_blocklist_estatica():
    start = DYNAMIC.index('exten => _0.,1,Set(DESTINO=')
    end = DYNAMIC.index('exten => numero-bloqueado,1', start)
    outbound = DYNAMIC[start:end]
    assert 'DB(blocklist-{tenant_id}/' in outbound
    assert 'DB(blocklist-t1/' not in outbound
    assert 'DB(blocklist-t2/' not in outbound
