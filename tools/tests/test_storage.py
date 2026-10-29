import importlib.util
from pathlib import Path
import pytest
import yaml

spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'check_wizard_md.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

@pytest.mark.parametrize('opts', [{'name':'fixed'}, {'external': True}, {'driver':'nfs'}, {'driver_opts':{'type':'none'}}])
def test_named_volume_refusals(opts):
    assert checker.storage_problems({}, {'volumes': {'state': opts}})

def test_portable_named_volumes_and_shares():
    assert not checker.storage_problems({'shares':[{'id':'login','path':'claude'}],
        'mounts':[{'app':'provider','share':'login','path':'/claude'}]}, {'volumes':{'state':None}})

@pytest.mark.parametrize('p', ['../outside','/absolute','a/../b','a//b','a\\b','$HOME','a:b','a,b','a\nb',''])
def test_unsafe_share_paths(p):
    assert checker.storage_problems({'shares':[{'id':'login','path':p}]},{})

@pytest.mark.parametrize('manifest', [
    {'shares':{}}, {'mounts':{}}, {'shares':[{'id':'login','path':'ok','read_only':True}]},
    {'mounts':[{'app':'provider','share':'login','path':'relative'}]},
    {'shares':[{'id':'login','path':'ok'},{'id':'login','path':'also'}]},
    {'mounts':[{'app':'provider','share':'login','path':'/a/../b'}]},
    {'shares':[{'id':[],'path':'ok'}]},
])
def test_shapes(manifest):
    assert checker.storage_problems(manifest,{})

def test_rule_is_wired_into_checker(tmp_path):
    (tmp_path/'wizard.md').write_text('---\nid: example\nruntime: {compose: compose.yml}\n---\n')
    (tmp_path/'compose.yml').write_text('services: {}\nvolumes:\n  state:\n    name: fixed\n')
    assert any(name == 'storage (rule 15)' and not ok for name,ok,_ in checker.check(tmp_path))
