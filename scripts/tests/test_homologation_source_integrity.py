"""Runtime evidence cannot attribute uncommitted API code to a Git commit."""
import subprocess

from lab.asterisk_lab import source_checkout_clean


def git(root, *args):
    subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)


def test_dirty_or_untracked_queue_api_cannot_be_labeled_as_clean_head(tmp_path):
    git(tmp_path, 'init', '-q')
    api = tmp_path/'queue-api'
    api.mkdir()
    source = api/'server.py'
    source.write_text('VERSION = 1\n')
    git(tmp_path, 'add', 'queue-api/server.py')
    git(tmp_path, '-c', 'user.name=Lab Test', '-c', 'user.email=lab@example.invalid',
        'commit', '-qm', 'baseline')
    assert source_checkout_clean(tmp_path)
    source.write_text('VERSION = 2\n')
    assert not source_checkout_clean(tmp_path)
    git(tmp_path, 'add', 'queue-api/server.py')
    assert not source_checkout_clean(tmp_path)
    git(tmp_path, '-c', 'user.name=Lab Test', '-c', 'user.email=lab@example.invalid',
        'commit', '-qm', 'update')
    assert source_checkout_clean(tmp_path)
    (api/'injected_module.py').write_text('VERSION = 3\n')
    assert not source_checkout_clean(tmp_path)
