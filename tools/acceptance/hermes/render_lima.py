#!/usr/bin/env python3
"""Render the mounted acceptance root without shell/YAML interpolation."""
import json
from pathlib import Path
import sys


def render(root):
    template = Path(__file__).with_name("lima.yaml").read_text()
    return template.replace("__ACCEPT_ROOT_JSON__", json.dumps(str(Path(root).expanduser().resolve())))


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(render(sys.argv[1]))
