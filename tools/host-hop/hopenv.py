#!/usr/bin/python3
"""Read hosts.env (bash syntax) for the Python tools. Bash itself parses it, so both sides agree."""
import os, pathlib, subprocess

D = pathlib.Path(__file__).resolve().parent


def env_path():
    return pathlib.Path(os.environ.get('HOP_ENV') or D / 'hosts.env')


def load(path=None):
    p = pathlib.Path(path or env_path())
    if not p.is_file():
        raise SystemExit('host-hop: missing ' + str(p) + ' (copy hosts.env.example)')
    out = subprocess.run(['bash', '-c', 'set -a; . "$1" >/dev/null; env -0', '_', str(p)],
                         env={'PATH': '/usr/bin:/bin'}, capture_output=True, check=True).stdout
    cfg = {}
    for item in out.split(b'\0'):
        k, sep, v = item.decode().partition('=')
        if sep and k.startswith('HOP_'):
            cfg[k] = v
    return cfg


def hv(cfg, kind, host):
    """Per-host value, e.g. hv(cfg, 'TSIP', 'target-host') -> HOP_TSIP_target_host."""
    return cfg.get('HOP_' + kind + '_' + host.replace('-', '_'), '')


def words(cfg, key):
    return cfg.get(key, '').split()
