#!/usr/bin/env python3
"""Smoke-test a Wizard app the way the App Manager will run it (spec/WIZARD_MD.md "Packaging").

Usage: app_source_smoke.py <repo-dir> [--keep]

Copies the tracked files of <repo-dir> (no .git) to a scratch APP_SOURCE_DIR, resolves the Runtipi
variables (APP_SOURCE_DIR, APP_DATA_DIR, ROOT_FOLDER_HOST, APP_PORT), drops x-runtipi, applies the
App Manager's build rewrite for `package: build`, starts the app with docker compose, waits for the
main service's internal_port to answer HTTP on 127.0.0.1, prints the docker arch and result, then
tears everything down. Exit 0 only when the main port answered with a status < 500.
"""
import json, os, pathlib, random, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
import yaml

repo = pathlib.Path(sys.argv[1]).resolve()
keep = "--keep" in sys.argv
text = (repo / "wizard.md").read_text()
fm = yaml.safe_load(text.split("---", 2)[1])
rt = fm.get("runtime") or {}
pkg = rt.get("package")
app = fm["id"]
compose = yaml.safe_load((repo / rt["compose"]).read_text())

root = pathlib.Path(tempfile.mkdtemp(prefix=f"smoke-{app}-", dir=os.environ.get("SMOKE_ROOT") or None))
src = root / "source"
files = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True, check=True).stdout.split(b"\0")
for f in filter(None, files):
    p = repo / f.decode()
    if p.is_file() or p.is_symlink():
        (src / f.decode()).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, src / f.decode(), follow_symlinks=False)
data = root / "app-data"
media = root / "root" / "media"
data.mkdir(); media.mkdir(parents=True)
port = random.randint(20000, 40000)
env = {"APP_SOURCE_DIR": str(src), "APP_DATA_DIR": str(data), "ROOT_FOLDER_HOST": str(root / "root"),
       "APP_PORT": str(port), "APP_ID": f"{app}-smoke", "APP_NAME": app, "APP_DOMAIN": "localhost",
       "LOCAL_DOMAIN": "localhost", "APP_PROTOCOL": "http", "APP_HOST": "127.0.0.1", "TZ": "UTC"}
main, internal = None, None
compose.pop("x-runtipi", None)
for name, svc in (compose.get("services") or {}).items():
    xr = svc.pop("x-runtipi", None) or {}
    if xr.get("is_main"):
        main, internal = name, xr.get("internal_port")
        svc["ports"] = [f"127.0.0.1:{port}:{internal}"]
    if pkg == "build" and svc.get("build"):
        b = {"context": svc["build"]} if isinstance(svc["build"], str) else dict(svc["build"])
        b["context"] = str(src / (b.get("context") or "."))
        svc["build"], svc["image"], svc["pull_policy"] = b, f"wizard-local/{app}-{name}:smoke", "build"
    svc.pop("networks", None)
compose.pop("networks", None)
(root / "docker-compose.yml").write_text(yaml.safe_dump(compose, sort_keys=False))
proj = f"smoke-{app}-{port}"
dc = ["docker", "compose", "-p", proj, "-f", str(root / "docker-compose.yml")]
arch = subprocess.run(["docker", "info", "--format", "{{.Architecture}}"], capture_output=True, text=True).stdout.strip()
print(f"app={app} package={pkg} arch={arch} main={main}:{internal} host_port={port}")
ok = False
try:
    up = subprocess.run(dc + ["up", "-d", "--quiet-pull"], env={**os.environ, **env}, capture_output=True, text=True, timeout=1500)
    if up.returncode:
        print("compose up failed:\n" + (up.stderr or up.stdout)[-3000:])
    else:
        deadline = time.time() + 120
        while time.time() < deadline and not ok:
            for path in ("/healthz", "/health", "/"):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
                        ok = r.status < 500
                        print(f"HTTP {r.status} {path}")
                except urllib.error.HTTPError as e:
                    if e.code < 500:
                        ok = True
                        print(f"HTTP {e.code} {path}")
                except Exception:
                    pass
                if ok:
                    break
            time.sleep(2)
        if not ok:
            print(subprocess.run(dc + ["logs", "--tail", "40"], env={**os.environ, **env}, capture_output=True, text=True).stdout[-3000:])
finally:
    if not keep:
        subprocess.run(dc + ["down", "-v", "--rmi", "local"], env={**os.environ, **env}, capture_output=True)
        shutil.rmtree(root, ignore_errors=True)
print("SMOKE", "PASS" if ok else "FAIL", app, arch)
sys.exit(0 if ok else 1)
