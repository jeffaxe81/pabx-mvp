"""Every explicit MixMonitor path must isolate tenant and call identity."""
import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]


def recording_routes(content):
    context = extension = None
    rows = []
    for line in content.splitlines():
        section = re.fullmatch(r'\[([^]]+)\]', line.strip())
        if section:
            context = section[1]
        entry = re.match(r'\s*exten\s*=>\s*([^,]+),', line)
        if entry:
            extension = entry[1]
        if not line.lstrip().startswith(';') and 'MixMonitor(' in line:
            rows.append((context, extension, line))
    return rows


def assert_private_recording_paths(rows):
    assert rows
    for context, extension, line in rows:
        tenant = (extension.split('-', 1)[0] if context == 'pickup-target'
                  else context.removesuffix('-internal'))
        assert re.fullmatch(r't[1-9][0-9]*', tenant)
        assert '${FILTER(0-9,${CALLERID(num)})}' in line, (context, extension)
        assert '${UNIQUEID}.wav,b)' in line, (context, extension)
        destination = 'pickup' if context == 'pickup-target' else extension
        assert '-'+tenant+'-'+destination+'-${UNIQUEID}.wav,b)' in line, (context, extension)
        assert '-${CALLERID(num)}-' not in line


def test_all_static_mixmonitor_paths_are_separate_per_tenant_and_call():
    rows = recording_routes((ROOT/'asterisk/extensions.conf').read_text(encoding='utf-8'))
    assert {(context, extension) for context, extension, _ in rows} == {
        ('t1-internal', '1010'), ('t1-internal', '1011'),
        ('t2-internal', '1010'), ('t2-internal', '1011'),
        ('pickup-target', 't1-recepcao'), ('pickup-target', 't1-recepcao-2'),
        ('pickup-target', 't2-recepcao'), ('pickup-target', 't2-recepcao-2'),
    }
    assert_private_recording_paths(rows)


@pytest.mark.parametrize('tenant', ['t3', 't10'])
def test_generated_tenant_operator_recordings_are_unique_and_sanitized(tenant):
    spec = importlib.util.spec_from_file_location('safe_recording_tenants', ROOT/'admin-api/tenants.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = recording_routes(module.render_tenant_extensions(tenant))
    assert {(context, extension) for context, extension, _ in rows} == {
        (tenant+'-internal', '1010'), (tenant+'-internal', '1011'),
    }
    assert_private_recording_paths(rows)
