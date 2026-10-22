from sounds import list_sound_files


def test_only_safe_wav_files_are_listed(tmp_path):
    (tmp_path / "boas-vindas.wav").write_bytes(b"RIFF")
    (tmp_path / "Nome Invalido.wav").write_bytes(b"RIFF")
    (tmp_path / "nope.txt").write_bytes(b"no")
    names = [item["filename"] for item in list_sound_files(tmp_path)]
    assert names == ["boas-vindas.wav"]


def test_symlink_cannot_leak_external_file(tmp_path):
    outside = tmp_path.parent / ("external-" + tmp_path.name + ".wav")
    outside.write_bytes(b"outside")
    (tmp_path / "external.wav").symlink_to(outside)
    assert all(item["filename"] != "external.wav" for item in list_sound_files(tmp_path))
