#!/usr/bin/env python3
"""Fetch one digest-pinned public image on the host and write a `docker load` archive.

Docker inside a Lima vz guest on Thales fails GHCR blob downloads ("tls: bad record MAC") while the host fetches
them fine, so the harness downloads on the host and side-loads into the fresh VM. The archive keeps the registry's
config and layers byte for byte; every blob is checked against its digest, and the loaded image ID equals the
config digest, so the VM runs exactly the pinned image.

    fetch_image.py <registry>/<repo>@sha256:<index or manifest digest> <out.tar> [arch=arm64]
    fetch_image.py <image>:<tag> <out.tar>   (pins the tag to its current digest and prints it)
"""
import hashlib
import io
import json
import os
import sys
import tarfile
import time
import urllib.request

ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"])


def split(ref):
    """Return (registry host, repository, digest or tag)."""
    if "@" in ref:
        name, digest = ref.split("@", 1)
    else:
        name, digest = ref.rsplit(":", 1)
    host, repo = name.split("/", 1) if "/" in name else ("docker.io", name)
    if "." not in host:
        host, repo = "registry-1.docker.io", name
    if host == "docker.io":
        host = "registry-1.docker.io"
    if ":" in repo.rsplit("/", 1)[-1]:
        repo = repo.rsplit(":", 1)[0]
    return host, repo, digest


def token(host, repo):
    url = {"ghcr.io": f"https://ghcr.io/token?scope=repository:{repo}:pull",
           "registry-1.docker.io": f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"}[host]
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)["token"]


def get(url, tok, accept=None, tries=6):
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok, **({"Accept": accept} if accept else {})})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception as e:  # transient CDN errors: retry with backoff
            if attempt == tries:
                raise
            print(f"retry {attempt} {url[:80]}: {e}", file=sys.stderr)
            time.sleep(attempt * 3)


def blob(host, repo, tok, digest):
    data = get(f"https://{host}/v2/{repo}/blobs/{digest}", tok)
    if "sha256:" + hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit(f"digest mismatch for {digest}")
    return data


def main():
    ref, out = sys.argv[1], sys.argv[2]
    arch = sys.argv[3] if len(sys.argv) > 3 else "arm64"
    host, repo, digest = split(ref)
    if host == "registry-1.docker.io" and "/" not in repo:
        repo = "library/" + repo
    tok = token(host, repo)
    top_raw = get(f"https://{host}/v2/{repo}/manifests/{digest}", tok, ACCEPT)
    if not digest.startswith("sha256:"):  # a tag: pin it to what it resolves to now
        digest = "sha256:" + hashlib.sha256(top_raw).hexdigest()
    elif "sha256:" + hashlib.sha256(top_raw).hexdigest() != digest:
        raise SystemExit("index digest mismatch")
    top = json.loads(top_raw)
    manifest_digest = digest
    if "manifests" in top:
        pick = [m for m in top["manifests"] if m.get("platform", {}).get("architecture") == arch
                and m.get("platform", {}).get("os") == "linux"]
        if not pick:
            raise SystemExit(f"no linux/{arch} manifest in {ref}")
        manifest_digest = pick[0]["digest"]
    raw = get(f"https://{host}/v2/{repo}/manifests/{manifest_digest}", tok, ACCEPT)
    if "sha256:" + hashlib.sha256(raw).hexdigest() != manifest_digest:
        raise SystemExit("manifest digest mismatch")
    man = json.loads(raw)
    cfg_digest = man["config"]["digest"]
    files = {f"{cfg_digest[7:]}.json": blob(host, repo, tok, cfg_digest)}
    layers = []
    for layer in man["layers"]:
        name = f"{layer['digest'][7:]}/layer.tar"  # docker load accepts compressed layer blobs under this name
        files[name] = blob(host, repo, tok, layer["digest"])
        layers.append(name)
    tag = f"{host.replace('registry-1.docker.io', 'docker.io')}/{repo}:pinned-{digest[7:19]}"
    files["manifest.json"] = json.dumps([{"Config": f"{cfg_digest[7:]}.json", "RepoTags": [tag], "Layers": layers}]).encode()
    tmp = out + ".part"
    with tarfile.open(tmp, "w") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    os.replace(tmp, out)
    print(json.dumps({"ref": ref, "digest": digest, "arch": arch, "manifest": manifest_digest, "config": cfg_digest, "tag": tag,
                      "layers": len(layers)}))


if __name__ == "__main__":
    main()
