"""Regressões dos caminhos de falha; somente a fronteira Docker é simulada."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lab import asterisk_lab as lab


@pytest.fixture
def committed_repo(tmp_path):
    root = tmp_path/'repo'
    shutil.copytree(ROOT/'asterisk', root/'asterisk', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('admin-api/tenants.py', 'scripts/secrets_generator.py'):
        target = root/name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    for args in (['init','-q'], ['add','.'],
                 ['-c','user.name=Lab Test','-c','user.email=lab@example.invalid','commit','-qm','fixture']):
        subprocess.run(['git','-C',str(root),*args], check=True, capture_output=True)
    return root


@pytest.mark.parametrize('ignored', [False, True])
def test_untracked_or_ignored_included_config_cannot_enter_sha_attributed_lab(committed_repo, tmp_path, ignored):
    extra = committed_repo/'asterisk/pjsip_tenants/t4.conf'
    if ignored:
        (committed_repo/'.git/info/exclude').write_text('asterisk/pjsip_tenants/t4.conf\n')
    extra.write_text('[t4-injected]\ntype=auth\npassword=UNTRACKED_PRIVATE\n')
    prepared = lab.prepare(committed_repo, tmp_path/'private')
    assert not (prepared['conf']/'pjsip_tenants/t4.conf').exists()
    assert all(b'UNTRACKED_PRIVATE' not in p.read_bytes()
               for p in prepared['conf'].rglob('*') if p.is_file())


class DockerBoundary:
    """Estado externo mínimo: objetos reais do laboratório controlados pelo runner."""
    def __init__(self, mode):
        self.mode = mode
        self.containers = {}
        self.original = lab.command

    def __call__(self, args, **kwargs):
        if args[0] != 'docker':
            return self.original(args, **kwargs)
        op = args[1]
        result = lambda code=0, output='': subprocess.CompletedProcess(args, code, output, '')
        if op == 'pull':
            return result()
        if op == 'image':
            return result(output=json.dumps([{'Id':'sha256:'+'a'*64, 'RepoDigests':[]}]))
        if op in ('run', 'create'):
            name = args[args.index('--name')+1]
            labels = {args[i+1].split('=',1)[0]:args[i+1].split('=',1)[1]
                      for i,v in enumerate(args) if v == '--label'}
            if self.mode == 'collision':
                self.containers[name] = {'Id':'b'*64, 'Config':{'Labels':{'io.axe.pabx.lab-owner':'someone-else'}}}
                return result(125)
            self.containers[name] = {'Id':'a'*64, 'Config':{'Labels':labels}}
            if self.mode == 'create_timeout':
                raise subprocess.TimeoutExpired(args, 30)
            return result(output='a'*64+'\n')
        if op == 'start':
            return result()
        if op == 'inspect':
            item = self.containers.get(args[2]) or next(
                (v for v in self.containers.values() if v['Id'] == args[2]), None)
            return result(output=json.dumps([item])) if item else result(1)
        if op == 'logs':
            if self.mode == 'logs_timeout':
                raise subprocess.TimeoutExpired(args, 30)
            return result()
        if op == 'rm':
            name = next((k for k,v in self.containers.items()
                         if k == args[-1] or v['Id'] == args[-1]), None)
            if name is not None:
                del self.containers[name]
            return result()
        if op == 'exec':
            raise subprocess.TimeoutExpired(args, 30)
        raise AssertionError(args)


def test_failed_creation_does_not_delete_name_collision(committed_repo, monkeypatch):
    boundary = DockerBoundary('collision')
    monkeypatch.setattr(lab, 'command', boundary)
    with pytest.raises(RuntimeError):
        lab.run(committed_repo, {})
    assert len(boundary.containers) == 1
    assert next(iter(boundary.containers.values()))['Id'] == 'b'*64


def test_creation_timeout_recovers_and_removes_only_owned_container(committed_repo, monkeypatch):
    boundary = DockerBoundary('create_timeout')
    monkeypatch.setattr(lab, 'command', boundary)
    with pytest.raises(subprocess.TimeoutExpired):
        lab.run(committed_repo, {})
    assert boundary.containers == {}


def test_log_timeout_does_not_skip_owned_container_removal(monkeypatch):
    boundary = DockerBoundary('logs_timeout')
    boundary.containers['axe-lab-owned'] = {
        'Id':'a'*64, 'Config':{'Labels':{'io.axe.pabx.lab-owner':'ours'}}}
    monkeypatch.setattr(lab, 'command', boundary)
    result = lab.cleanup_owned('axe-lab-owned', 'ours')
    assert result['removed'] is True
    assert result['retain_staging'] is False
    assert boundary.containers == {}
