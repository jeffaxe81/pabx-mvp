import pytest
from tenant_deprovisioning import tenant_config_paths

def test_deprovision_paths_reject_ambiguous_or_traversal_tenants(tmp_path):
    for invalid in ("../secret","t1/../../secret","t0","t1\nextra",[],None,True,"t"+"9"*40):
        with pytest.raises(ValueError):
            tenant_config_paths(tmp_path,invalid)
    paths=tenant_config_paths(tmp_path,"t12")
    assert len(paths)==8
    assert all(path.is_relative_to(tmp_path) for path in paths)
