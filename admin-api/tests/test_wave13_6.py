import pytest
from tenant_provisioning import build_tenant_files

def test_tenant_build_rejects_malicious_ids_before_rendering(tmp_path):
    for value in (None, True, [], "../t9", "t0", "t1/../../", "t1\nX", "t"+"9"*35):
        with pytest.raises(ValueError):
            build_tenant_files(tmp_path, value, {}, {})
