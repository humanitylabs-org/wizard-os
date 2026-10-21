"""Rule 14: runtime.package (source | build | image). Run directly or with unittest."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('checker', ROOT / 'tools/check_wizard_md.py')
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

PY = 'python:3.12-alpine@sha256:' + 'a' * 64
WIZARD = """---
wizard: 0.2
id: demo
name: Demo
type: service
version: 0.1.0
summary: A demo app.
license: MIT
source: https://github.com/example/demo
runtime:
  kind: runtipi
  config: runtipi/config.json
  compose: runtipi/docker-compose.yml
{package}
mcp: {{path: /mcp, port: 8080}}
skill: skill/SKILL.md
---
"""


def repo(package: str | None, compose: str, files: dict[str, str] | None = None) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / 'runtipi').mkdir()
    (d / 'skill').mkdir()
    (d / 'wizard.md').write_text(WIZARD.format(package=f'  package: {package}' if package else ''))
    (d / 'runtipi/config.json').write_text('{"id": "demo"}')
    (d / 'runtipi/docker-compose.yml').write_text(compose)
    (d / 'skill/SKILL.md').write_text('---\nname: demo\ndescription: d\n---\n')
    for k, v in (files or {}).items():
        (d / k).parent.mkdir(parents=True, exist_ok=True)
        (d / k).write_text(v)
    return d


def packaging(d: Path) -> tuple[bool, str] | None:
    for name, ok, detail in checker.check(d):
        if name.startswith('packaging'):
            return ok, detail
    return None


SOURCE = f"""services:
  demo:
    image: {PY}
    command: [python, /app/server.py]
    volumes: ['${{APP_SOURCE_DIR}}/app:/app:ro', '${{APP_DATA_DIR}}/data:/data']
"""


class Packaging(unittest.TestCase):
    def test_legacy_apps_without_package_are_not_judged(self):
        self.assertIsNone(packaging(repo(None, 'services: {demo: {image: "ghcr.io/x/demo:latest"}}')))

    def test_source_app_passes(self):
        self.assertEqual(packaging(repo('source', SOURCE)), (True, ''))

    def test_unknown_package_fails(self):
        ok, detail = packaging(repo('docker', SOURCE))
        self.assertFalse(ok)
        self.assertIn('source, build or image', detail)

    def test_floating_tags_fail_for_every_package(self):
        for tag in ('python:3.12-alpine', 'ghcr.io/x/demo:latest', '${IMG:-ghcr.io/x/demo:0.1.0}'):
            ok, detail = packaging(repo('image', f'services: {{demo: {{image: "{tag}"}}}}'))
            self.assertFalse(ok, tag)
            self.assertIn('not pinned by digest', detail)

    def test_env_default_with_digest_passes(self):
        img = '${IMG:-ghcr.io/x/demo@sha256:' + 'b' * 64 + '}'
        self.assertEqual(packaging(repo('image', f'services: {{demo: {{image: "{img}"}}}}')), (True, ''))

    def test_source_app_must_mount_its_code_read_only(self):
        ok, detail = packaging(repo('source', SOURCE.replace(':/app:ro', ':/app')))
        self.assertFalse(ok)
        self.assertIn('read-only', detail)
        ok, detail = packaging(repo('source', f'services: {{demo: {{image: "{PY}"}}}}'))
        self.assertFalse(ok)
        self.assertIn('mount their code', detail)

    def test_source_and_image_apps_build_nothing(self):
        for pkg in ('source', 'image'):
            ok, detail = packaging(repo(pkg, SOURCE + '    build: .\n'))
            self.assertFalse(ok, pkg)
            self.assertIn('remove build:', detail)

    def test_build_app_with_hash_locked_pins_passes(self):
        df = f'FROM {PY}\nCOPY requirements.txt /r.txt\nRUN apk add --no-cache ffmpeg && pip install --no-cache-dir -r /r.txt\n'
        compose = 'services:\n  demo:\n    build: {context: ., dockerfile: app/Dockerfile}\n'
        d = repo('build', compose, {'app/Dockerfile': df, 'requirements.txt': 'pyyaml==6.0.3 \\\n    --hash=sha256:' + 'c' * 64 + '\n'})
        self.assertEqual(packaging(d), (True, ''))

    def test_build_app_rejects_unpinned_base_unlocked_pip_and_compiling(self):
        df = 'FROM python:3.12-slim AS base\nFROM base\nRUN pip install PyYAML==6.0.3\nRUN npm ci && npm run build\n'
        d = repo('build', 'services: {demo: {build: .}}', {'Dockerfile': df})
        ok, detail = packaging(d)
        self.assertFalse(ok)
        self.assertIn('FROM python:3.12-slim is not pinned', detail)
        self.assertNotIn('FROM base', detail)  # a named earlier stage is fine
        self.assertIn('pip install is not hash-locked', detail)
        self.assertIn('compiles or bundles', detail)

    def test_build_context_stays_inside_the_repo(self):
        for ctx in ('/etc', '..', '${APP_SOURCE_DIR}'):
            ok, detail = packaging(repo('build', f'services: {{demo: {{build: {{context: "{ctx}"}}}}}}'))
            self.assertFalse(ok, ctx)
            self.assertIn('inside the repo', detail)

    def test_build_app_needs_a_build_section(self):
        ok, detail = packaging(repo('build', SOURCE))
        self.assertFalse(ok)
        self.assertIn('need a build:', detail)


if __name__ == '__main__':
    unittest.main()
