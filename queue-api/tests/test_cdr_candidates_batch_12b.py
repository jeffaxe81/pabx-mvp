import pytest
from recording_cdr_candidates import propose_candidates

def test_direct_candidate_builder_rejects_excessive_cdr_batch(tmp_path):
    with pytest.raises(ValueError, match="lote CDR"):
        propose_candidates(tmp_path, [{"Event":"Cdr"}] * 10001)

def test_direct_candidate_builder_rejects_non_collection(tmp_path):
    for raw in (None, "{}", {"Event":"Cdr"}, True):
        with pytest.raises(ValueError, match="lote CDR"):
            propose_candidates(tmp_path, raw)
