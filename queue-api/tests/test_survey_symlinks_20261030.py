import pytest
from survey import SurveyStore

def test_survey_file_symlink_refuses_read_and_write(tmp_path):
    target = tmp_path / "private.jsonl"
    target.write_text('{"score": 5}\n', encoding="utf-8")
    link = tmp_path / "survey.jsonl"
    link.symlink_to(target)
    store = SurveyStore(link)
    assert store.load_all() == []
    with pytest.raises(ValueError):
        store.append({"score": 1})
    assert target.read_text() == '{"score": 5}\n'
