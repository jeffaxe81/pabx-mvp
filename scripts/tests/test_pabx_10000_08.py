"""AXE PABX puro: 1.000 relatórios simulados de CLI e AstDB, sem Asterisk real."""
import pytest
import asterisk_lab_audit as audit

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+7001:05d}") for i in range(1000)])
def test_cli_1000_tenant_did_and_runtime_evidence_records(case):
    tid=f"t{3+case}"
    did=str(5511910000000+case)
    expected={tid:did}
    outputs={}
    for key in audit.planned_commands(expected):
        if key=="version":
            out="Asterisk 22.11.0 Lab"
        elif key=="transports":
            out="Transport: transport-tls tls\nTransport: transport-wss wss"
        elif key=="ingress":
            out="tenant-did/\ndid-desconhecido\nHangup(21)"
        elif key=="astdb":
            owner=tid if case<500 else "t9999"
            out=f"/tenant-did/{did} : {owner}\n"
        elif key.startswith("endpoint:"):
            tenant=key.partition(":")[2]
            name=audit.STATIC_ENDPOINTS.get(tenant,tenant+"-recepcao")
            out=f"Endpoint: {name}/1001\ncontext : {tenant}-internal\n"
        else:
            tenant=key.partition(":")[2]
            out=f"[ Context '{tenant}-internal' created by 'pbx_config' ]"
        outputs[key]={"code":0,"output":out,"truncated":False}
    report=audit.check_snapshots(outputs,expected)
    assert report["checks"][f"endpoint_exists:{tid}"]
    assert report["checks"][f"endpoint_context:{tid}"]
    assert report["checks"][f"did_mapping:{tid}"] is (case<500)
    assert report["ready_for_call_homologation"] is (case<500)
    assert report["registration_verified"] is False
    assert did not in str(report)
