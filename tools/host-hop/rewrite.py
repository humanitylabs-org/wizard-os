#!/usr/bin/env python3
"""host-hop: find and rewrite host-specific identity (tailnet name / IP) in configs.

  rewrite.py scan   ROOT TOKEN... > rewrite-targets.txt   list files that embed any TOKEN (generic scope rules)
  rewrite.py apply  TARGETS BACKUP_DIR OLD=NEW...          replace exact tokens in listed files, backup first
  rewrite.py restore BACKUP_DIR                            put backed-up originals back

Scope = configs only: systemd user units, Runtipi user-config/.env/app.env, ~/.wizard-os json/conf/yaml/py,
~/.hermes config/.env/scripts/cron jobs.json, app server sources under ~/apps. Excludes dev/qa/test/release
archives, backups, logs and evidence. Bare short names are only replaced in a host context
(URL, user@host, host:port, quoted host value), never in free prose.
"""
import os, re, shutil, sys, json

SCOPE = [
    ".config/systemd/user",
    "runtipi/user-config", "runtipi/.env", "runtipi/app-data",
    ".wizard-os",
    ".hermes/config.yaml", ".hermes/.env", ".hermes/scripts", ".hermes/cron/jobs.json",
    ".hermes/profiles",
    "apps",
]
EXCLUDE_RE = re.compile(
    r"(\.bak|\.backup|backup|\.rollback|rollback-|\.pre-|\.before|\.orig|~$|/dev/|/qa/|-qa|qa-|/test|test-|_test|"
    r"/tests?/|/releases?/|release-archive|/evidence/|/retired/|/logs?/|\.log$|\.jsonl$|HANDOFF\.md|/candidate/|"
    r"/staged-apps/|/node_modules/|/\.git/|/cache/|/sessions/|/state-snapshots/|/media/|/data/|\.sqlite|\.db$)", re.I)
CONF_EXT = {".service", ".timer", ".path", ".socket", ".conf", ".env", ".json", ".yml", ".yaml", ".toml",
            ".py", ".mjs", ".js", ".sh", ".ini", ".cfg", ""}
MAX = 4 * 1024 * 1024


def in_scope(rel):
    if EXCLUDE_RE.search("/" + rel):
        return False
    base = os.path.basename(rel)
    ext = os.path.splitext(base)[1]
    if base in ("app.env", ".env", "jobs.json", "config.yaml"):
        return True
    return ext in CONF_EXT


def walk(root):
    for s in SCOPE:
        p = os.path.join(root, s)
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for d, dirs, files in os.walk(p):
                rel = os.path.relpath(d, root)
                dirs[:] = [x for x in dirs if not EXCLUDE_RE.search("/" + rel + "/" + x + "/")]
                for f in files:
                    yield os.path.join(d, f)


def patterns(tokens):
    out = []
    for t in tokens:
        if "." in t:   # fqdn or ip: exact token, not part of a longer name/number
            out.append((t, re.compile(r"(?<![\w.-])" + re.escape(t) + r"(?![\w-]|\.\d)")))
        else:          # bare short host name: only in host context
            out.append((t, re.compile(r"(?:(?<=//)|(?<=@)|(?<=[\"' =])|(?<=^))" + re.escape(t) +
                                       r"(?=(?::\d)|[\"'/]|\s*$)", re.M)))
    return out


def scan(root, tokens):
    pats = patterns(tokens)
    for p in walk(root):
        rel = os.path.relpath(p, root)
        if not in_scope(rel) or os.path.islink(p):
            continue
        try:
            if os.path.getsize(p) > MAX:
                continue
            txt = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        hits = {t: len(rx.findall(txt)) for t, rx in pats}
        hits = {t: n for t, n in hits.items() if n}
        if hits:
            print(rel + "\t" + " ".join(f"{t}={n}" for t, n in hits.items()))


def apply(root, targets, backup, pairs):
    mapping = dict(x.split("=", 1) for x in pairs)
    pats = patterns(list(mapping))
    os.makedirs(backup, exist_ok=True)
    manifest, changed = [], 0
    for line in open(targets):
        if not line.strip() or line.startswith("#"):
            continue
        rel = line.split("\t")[0]
        p = os.path.join(root, rel)
        try:
            txt = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        new = txt
        for t, rx in pats:  # longest tokens first is guaranteed by caller ordering
            new = rx.sub(mapping[t], new)
        if new != txt:
            b = os.path.join(backup, rel)
            os.makedirs(os.path.dirname(b), exist_ok=True)
            if not os.path.exists(b):
                shutil.copy2(p, b)
            st = os.stat(p)
            tmp = p + ".host-hop.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(new)
            os.chmod(tmp, st.st_mode & 0o7777)
            try:
                os.chown(tmp, st.st_uid, st.st_gid)
            except PermissionError:
                pass
            os.replace(tmp, p)
            manifest.append(rel)
            changed += 1
    with open(os.path.join(backup, "MANIFEST"), "a") as fh:
        fh.write("\n".join(manifest) + ("\n" if manifest else ""))
    print(f"rewrote {changed} files", file=sys.stderr)


def restore(root, backup):
    m = os.path.join(backup, "MANIFEST")
    if not os.path.exists(m):
        return
    n = 0
    for rel in sorted(set(x.strip() for x in open(m) if x.strip())):
        b = os.path.join(backup, rel)
        if os.path.exists(b):
            shutil.copy2(b, os.path.join(root, rel))
            n += 1
    print(f"restored {n} files", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "scan":
        scan(sys.argv[2], sys.argv[3:])
    elif cmd == "apply":
        root = os.environ.get("HOP_HOME", os.path.expanduser("~"))
        apply(root, sys.argv[2], sys.argv[3], sys.argv[4:])
    elif cmd == "restore":
        restore(os.environ.get("HOP_HOME", os.path.expanduser("~")), sys.argv[2])
    else:
        sys.exit(__doc__)
