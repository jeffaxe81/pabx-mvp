from store import TranscriptStore


def test_append_and_load(tmp_path):
    store = TranscriptStore(tmp_path / "transcripts.jsonl")
    store.append({"filename": "a.wav", "transcript": "oi"})
    store.append({"filename": "b.wav", "transcript": "tchau"})
    assert len(store.load_all()) == 2


def test_load_all_missing_file_returns_empty(tmp_path):
    store = TranscriptStore(tmp_path / "nao-existe.jsonl")
    assert store.load_all() == []


def test_find_by_filename(tmp_path):
    store = TranscriptStore(tmp_path / "transcripts.jsonl")
    store.append({"filename": "a.wav", "transcript": "oi"})
    result = store.find_by_filename("a.wav")
    assert result["transcript"] == "oi"


def test_find_by_filename_returns_none_when_missing(tmp_path):
    store = TranscriptStore(tmp_path / "transcripts.jsonl")
    assert store.find_by_filename("nao-existe.wav") is None


def test_already_processed(tmp_path):
    store = TranscriptStore(tmp_path / "transcripts.jsonl")
    assert store.already_processed("a.wav") is False
    store.append({"filename": "a.wav"})
    assert store.already_processed("a.wav") is True


def test_skips_corrupted_lines(tmp_path):
    path = tmp_path / "transcripts.jsonl"
    path.write_text('{"filename": "a.wav"}\nlixo corrompido\n')
    store = TranscriptStore(path)
    assert len(store.load_all()) == 1
