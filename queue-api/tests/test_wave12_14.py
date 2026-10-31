from insights_cdr_integrity import cdr_invalid_disposition_structure

def test_cdr_integrity_flags_control_and_space_dispositions():
    records=[{"tenant":"t1","disposition":"ANSWERED"},
             {"tenant":"t1","disposition":" "},
             {"tenant":"t1","disposition":"BUSY\x00extra"},
             {"tenant":"t1","disposition":False},
             {"tenant":"t10","disposition":None}]
    assert cdr_invalid_disposition_structure(records,"t1")=={
        "tenant_records":4,"invalid_disposition":3}
