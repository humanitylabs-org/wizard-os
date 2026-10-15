"""Offline regressions for split pins and the image-source proof boundary."""
import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_release", ROOT / "tools/check_release.py")
assert spec and spec.loader
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def bundled():
    return json.loads((ROOT / "releases/0.2.1.json").read_text())


def split():
    rel = bundled()
    shell = rel["images"].pop("wizard-shell")
    for name in ("wizard-ux", "wizard-agent-service"):
        rel["images"][name] = {"ref": f"ghcr.io/humanitylabs-org/{name}:test",
                               "digest": shell["digest"], "built_from": name,
                               "architectures": ["amd64", "arm64"]}
    for slot, name in (("shell", "wizard-ux"), ("agent-service", "wizard-agent-service")):
        rel["default_apps"][slot]["app"] = name
    return rel


class Shape(unittest.TestCase):
    def test_legacy_and_split_are_valid(self):
        self.assertEqual(check.shape(bundled()), [])
        self.assertEqual(check.shape(split()), [])

    def test_each_required_split_image(self):
        for name in ("wizard-app-manager", "wizard-ux", "wizard-agent-service"):
            rel = split()
            del rel["images"][name]
            with self.subTest(name=name):
                self.assertTrue(check.shape(rel))

    def test_mixed_bundle_and_split_rejected(self):
        rel = split()
        rel["images"]["wizard-shell"] = bundled()["images"]["wizard-shell"]
        self.assertTrue(check.shape(rel))

    def test_malformed_inputs_fail_shape_not_traceback(self):
        cases = [None, [], {}, {"version": "0.2.2", "components": []}]
        for key, value in (("components", {"x": None}), ("images", {"wizard-ux": None}),
                           ("default_apps", [])):
            rel = split()
            rel[key] = value
            cases.append(rel)
        for rel in cases:
            with self.subTest(rel=rel):
                self.assertTrue(check.shape(rel))

    def test_component_and_image_metadata_required(self):
        for field, value in (("built_from", None), ("built_from", "wizard-agent-service"),
                             ("ref", "https://not-an-image"), ("source_commit", "main"),
                             ("architectures", ["arm64"]), ("image_inputs", []),
                             ("image_inputs", ["!Dockerfile"]), ("image_workflow", "not-a-workflow")):
            rel = split()
            rel["images"]["wizard-ux"][field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(check.shape(rel))
        rel = split()
        del rel["components"]["wizard-app-manager"]["branch"]
        self.assertTrue(check.shape(rel))

    def test_whitespace_in_identifiers_is_not_repaired(self):
        for key in ("commit", "repo"):
            rel = split()
            rel["components"]["wizard-ux"][key] += "\n"
            self.assertTrue(check.shape(rel))

    def test_wrong_split_slot_fails(self):
        rel = split()
        rel["default_apps"]["agent-service"]["app"] = "wizard-shell"
        self.assertTrue(check.shape(rel))

    def test_digest_in_ref_must_agree(self):
        rel = split()
        rel["images"]["wizard-ux"]["ref"] = "ghcr.io/humanitylabs-org/wizard-ux@sha256:" + "0" * 64
        self.assertTrue(check.shape(rel))


class Inputs(unittest.TestCase):
    def compare(self, files, status="ahead"):
        response = subprocess.CompletedProcess([], 0, json.dumps({"status": status, "files": files}), "")
        with patch.object(check.subprocess, "run", return_value=response):
            return check.changed_inputs("org/repo", "a" * 40, "b" * 40,
                                        ["packages/**", "Dockerfile", ".github/workflows/image.yml"])

    def test_non_image_changes_allowed(self):
        self.assertEqual(self.compare([{"filename": "README.md"}]), ([], ""))

    def test_image_and_workflow_changes_rejected(self):
        for path in ("packages/api/index.ts", "Dockerfile", ".github/workflows/image.yml"):
            self.assertEqual(self.compare([{"filename": path}])[0], [path])

    def test_rename_out_of_inputs_is_a_change(self):
        self.assertEqual(self.compare([{"filename": "docs/old.ts", "previous_filename": "packages/old.ts"}])[0],
                         ["packages/old.ts"])

    def test_compare_cap_fails_closed(self):
        self.assertIsNone(self.compare([{"filename": f"docs/{i}"} for i in range(300)])[0])

    def test_diverged_base_rejected(self):
        self.assertIsNone(self.compare([], "diverged")[0])

    def test_workflow_without_path_filter_requires_exact_build(self):
        response = subprocess.CompletedProcess([], 0, base64.b64encode(b"on:\n  push:\n    branches: [main]").decode(), "")
        with patch.object(check.subprocess, "run", return_value=response):
            self.assertIsNone(check.workflow_paths("org/repo", "a" * 40, ".github/workflows/image.yml")[0])

    def test_full_online_path_rejects_omitted_workflow(self):
        rel = bundled()
        rel["images"]["wizard-app-manager"]["image_inputs"].remove(".github/workflows/image.yml")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "release.json"
            p.write_text(json.dumps(rel))
            def revision(ref, digest, architectures):
                if "wizard-app-manager" in ref:
                    return rel["images"]["wizard-app-manager"]["source_commit"], ""
                return rel["components"]["wizard-agent-service"]["commit"], ""
            with patch.object(check, "commit_exists", return_value=(True, "")), \
                 patch.object(check, "on_branch", return_value=(True, "")), \
                 patch.object(check, "digest_exists", return_value=(True, "")), \
                 patch.object(check, "image_revision", side_effect=revision), \
                 patch.object(check, "workflow_paths", return_value=(["Dockerfile"], "")), \
                 patch.object(check, "changed_inputs") as changed, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(check.main([str(p)]), 1)
                changed.assert_not_called()
                self.assertIn("missing .github/workflows/image.yml", output.getvalue())


class Provenance(unittest.TestCase):
    def registry(self, labels=(None, None), attested=(True, True), revisions=None, architectures=("amd64", "arm64")):
        revs = revisions or ("a" * 40, "a" * 40)
        top = {"manifests": []}
        responses = {"token": {"token": "anonymous"}, "manifests/top": top}
        for i, arch in enumerate(architectures):
            child = f"child{i}"
            top["manifests"].append({"digest": child, "platform": {"os": "linux", "architecture": arch}})
            responses[f"manifests/{child}"] = {"config": {"digest": f"config{i}"}}
            responses[f"blobs/config{i}"] = {"config": {"Labels": {"org.opencontainers.image.revision": labels[i]}}}
            if attested[i]:
                top["manifests"].append({"digest": f"att{i}", "platform": {"os": "unknown"}, "annotations": {
                    "vnd.docker.reference.type": "attestation-manifest", "vnd.docker.reference.digest": child}})
                responses[f"manifests/att{i}"] = {"layers": [{"digest": f"prov{i}", "annotations": {
                    "in-toto.io/predicate-type": "https://slsa.dev/provenance/v0.2"}}]}
                responses[f"blobs/prov{i}"] = {"metadata": {"vcs:revision": revs[i]}}
        def urlopen(req, **kwargs):
            url = req if isinstance(req, str) else req.full_url
            key = "token" if "/token?" in url else url.split("/org/repo/")[1]
            return io.BytesIO(json.dumps(responses[key]).encode())
        with patch.object(check.urllib.request, "urlopen", side_effect=urlopen):
            return check.image_revision("ghcr.io/org/repo:test", "top", ["amd64", "arm64"])

    def test_labels_on_both_platforms(self):
        self.assertEqual(self.registry(labels=("a" * 40, "a" * 40))[0], "a" * 40)

    def test_mixed_or_missing_labels_fail(self):
        self.assertIsNone(self.registry(labels=("a" * 40, None))[0])
        self.assertIsNone(self.registry(labels=("a" * 40, "b" * 40))[0])

    def test_provenance_required_for_every_platform(self):
        self.assertEqual(self.registry()[0], "a" * 40)
        self.assertIsNone(self.registry(attested=(True, False))[0])

    def test_different_provenance_revisions_fail(self):
        self.assertIsNone(self.registry(revisions=("a" * 40, "b" * 40))[0])

    def test_missing_architecture_fails(self):
        self.assertIsNone(self.registry(architectures=("amd64",))[0])


if __name__ == "__main__":
    unittest.main()
