from store import TranscriptStore


def test_last_revision_is_returned(tmp_path):
    store = TranscriptStore(tmp_path / "transcripts.jsonl")
    store.append({"filename": "a.wav", "transcript": "antigo"})
    store.append({"filename": "a.wav", "transcript": "corrigido"})
    assert store.find_by_filename("a.wav")["transcript"] == "corrigido"


def test_nondictionary_json_is_ignored(tmp_path):
    path = tmp_path / "transcripts.jsonl"
    path.write_text('[]\nnull\n{"filename":"a.wav"}\n', encoding="utf-8")
    store = TranscriptStore(path)
    assert store.load_all() == [{"filename": "a.wav"}]
    assert store.already_processed("a.wav")
