"""The power cut tests the update, not dirty writes that created its QA fixture."""
import ast
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import pytest

from test_update_reboot_plan import candidate_plan, python_code


def test_flush_boundary_precedes_update_and_never_follows_it(tmp_path):
    plan, steps = candidate_plan(tmp_path)
    names = [s['step'] for s in plan['plan']]
    assert names.index('candidate-source-stage') < names.index('fixture-before-update')
    assert names.index('fixture-before-update') < names.index('fixture-host-sync') < names.index('update-apply')
    assert names.index('raw-after-reboot') < names.index('fixture-after-reboot') < names.index('candidate-after-reboot')
    assert '; sync' in steps['fixture-before-update']['argv'][-1]
    assert steps['fixture-host-sync']['argv'] == ['sync']
    assert all('sync' not in s.get('argv', []) and '; sync' not in str(s.get('argv', []))
               for s in plan['plan'][names.index('update-apply'):])
    assert not (tmp_path/'evidence').exists()


def fixture_home(tmp_path):
    h = tmp_path
    d = h/'.cache/wam-update-candidate'
    state = h/'.wizard-os'
    state.mkdir()
    (state/'release.json').write_text(json.dumps({'release':'0.3.32','status':'pinned'}))
    (state/'updates.json').write_text(json.dumps({'channel':'latest'}))
    for name in ('bin/wam', 'src/runner.py', 'src/get.sh', 'src/wam/cli.py', 'src/wam/updates.py',
                 'src/wam/__init__.py', 'original-release.json', 'candidate-exception.json',
                 'releases/latest', 'releases/stable'):
        p = d/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('fixture\n' if not name.endswith('__init__.py') else '')
    (d/'releases/0.3.33.json').write_text(json.dumps({'components':{'wizard-app-manager':{'commit':'a'*40}}}))
    return state, d


def exec_check(code, home):
    return subprocess.run(['python3', '-c', code], env={**os.environ, 'HOME':str(home)},
                          capture_output=True, text=True)


def test_fixture_inventory_detects_empty_wrapper_and_keeps_raw_state(tmp_path):
    _, steps = candidate_plan(tmp_path)
    state, d = fixture_home(tmp_path)
    before = python_code(steps['fixture-before-update'])
    after = python_code(steps['fixture-after-reboot'])
    for code in (before, after):
        compile(code, 'fixture-check', 'exec')
    assert exec_check(before, tmp_path).returncode == 0
    assert exec_check(after, tmp_path).returncode == 0
    (d/'bin/wam').write_text('')  # Exactly what the retained third VM contains.
    p = exec_check(after, tmp_path)
    assert p.returncode != 0
    assert str(d/'bin/wam') in p.stdout
    assert (d/'bin/wam').read_bytes() == b''  # Never restore or mask the fault.
    assert json.loads((state/'release.json').read_text())['status'] == 'pinned'


@pytest.mark.parametrize('bad', ['empty-wrapper', 'failed-base', 'wrong-candidate-manifest'])
def test_bad_base_or_fixture_is_rejected_before_cut(tmp_path, bad):
    _, steps = candidate_plan(tmp_path)
    state, d = fixture_home(tmp_path)
    if bad == 'empty-wrapper':
        (d/'bin/wam').write_text('')
    elif bad == 'failed-base':
        (state/'release.json').write_text(json.dumps({'release':'0.3.32','status':'install-failed'}))
    else:
        (d/'releases/0.3.33.json').write_text(json.dumps({'components':{'wizard-app-manager':{'commit':'b'*40}}}))
    p = exec_check(python_code(steps['fixture-before-update']), tmp_path)
    assert p.returncode != 0
    assert not (state/'qa-fixture-sha256.json').exists()


def json_runner(tmp_path, monkeypatch, wrapper):
    # Load only these helpers; never execute the harness's top-level VM lifecycle.
    source = Path(__file__).with_name('update_reboot.py').read_text()
    tree = ast.parse(source)
    names = {'run','out','as_json','wam_json','updates_state'}
    functions: list[ast.stmt] = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace: dict[str, Any] = dict(json=json, subprocess=subprocess, dry=False, root=tmp_path,
                                    receipt={'steps':[]}, save=lambda:None)
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'harness-functions', 'exec'), namespace)
    namespace['owner'] = lambda name, cmd, timeout, required: namespace['run'](
        name, ['bash','-c',cmd], timeout, required)
    bin_dir = tmp_path/'bin'
    bin_dir.mkdir()
    wam = bin_dir/'wam'
    wam.write_text(wrapper)
    wam.chmod(0o700)
    monkeypatch.setenv('PATH', str(bin_dir)+':'+os.environ['PATH'])
    return namespace['updates_state']


@pytest.mark.parametrize('wrapper,rc', [('', 0), ('#!/bin/sh\necho BROKEN_IMPORT >&2\nexit 7\n', 7)])
def test_wam_empty_success_and_error_preserve_rc_stderr_and_fail_fast(tmp_path, monkeypatch, wrapper, rc):
    run = json_runner(tmp_path, monkeypatch, wrapper)
    with pytest.raises(RuntimeError, match=f'exit={rc}, no valid JSON'):
        run('updates-after-reboot')
    log = (tmp_path/'updates-after-reboot.log').read_text()
    assert f'WAM_COMMAND_RC={rc}' in log
    if rc:
        assert 'BROKEN_IMPORT' in log


def test_wam_valid_json_still_works_with_rc_marker(tmp_path, monkeypatch):
    run = json_runner(tmp_path, monkeypatch, '#!/bin/sh\nprintf \'{"installed":"0.3.32"}\\n\'\n')
    assert run('updates-after-reboot') == {'installed':'0.3.32'}
    assert 'WAM_COMMAND_RC=0' in (tmp_path/'updates-after-reboot.log').read_text()
