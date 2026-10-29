"""Image/tag identity: a passing VM record must never vouch for a different source commit."""
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_release as cr

TAG = "818c13be1dc4fd28987e1e881a9408224afd4535"
OLD = "a28a5d03a9fa60418db5f44f3436fa2aa029c8f2"


class ImageRevision(unittest.TestCase):
    def registry(self, revisions):
        objects = {}

        def put(obj, kind):
            raw = json.dumps(obj).encode()
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            objects[f"{kind}/{digest}"] = raw
            return digest

        manifests = []
        for arch, rev in revisions.items():
            labels = {} if rev is None else {"org.opencontainers.image.revision": rev}
            cfg = put({"config": {"Labels": labels}}, "blobs")
            man = put({"config": {"digest": cfg}}, "manifests")
            manifests.append({"digest": man, "platform": {"os": "linux", "architecture": arch}})
        digest = put({"manifests": manifests}, "manifests")

        def open_(req, **kw):
            url = req if isinstance(req, str) else req.full_url
            if url.startswith("https://auth.docker.io/"):
                return io.BytesIO(b'{"token":"fixture"}')
            return io.BytesIO(objects[url.split("hermes-agent/", 1)[1]])
        return digest, objects, open_

    def test_both_platforms_match(self):
        digest, _, open_ = self.registry({"amd64": TAG, "arm64": TAG})
        with patch.object(cr.urllib.request, "urlopen", side_effect=open_):
            self.assertEqual(cr.dockerhub_image_revision(digest), (TAG, ""))

    def test_different_platform_commits_fail(self):
        digest, _, open_ = self.registry({"amd64": TAG, "arm64": OLD})
        with patch.object(cr.urllib.request, "urlopen", side_effect=open_):
            rev, why = cr.dockerhub_image_revision(digest)
        self.assertIsNone(rev)
        self.assertIn("different source revisions", why)

    def test_missing_label_or_platform_fails(self):
        for revisions in ({"amd64": None, "arm64": TAG}, {"amd64": TAG}):
            digest, _, open_ = self.registry(revisions)
            with self.subTest(revisions=revisions), patch.object(cr.urllib.request, "urlopen", side_effect=open_):
                self.assertIsNone(cr.dockerhub_image_revision(digest)[0])

    def test_registry_content_must_match_digest(self):
        digest, objects, open_ = self.registry({"amd64": TAG, "arm64": TAG})
        objects["manifests/" + digest] = b'{}'
        with patch.object(cr.urllib.request, "urlopen", side_effect=open_):
            self.assertIn("differs from its digest", cr.dockerhub_image_revision(digest)[1])

    def test_tested_pin_records_image_commit_and_refuses_mismatch(self):
        h = {"tag": "v0.21.6", "commit": TAG, "image": {
            "ref": "docker.io/nousresearch/hermes-agent:v0.21.6", "digest": "sha256:" + "1" * 64},
            "test_record": "docs/acceptance/hermes-v0.21.6.md", "rollback": None}
        rel = {"version": "0.3.39", "hermes": h}  # provenance shape independent of the new shared-lock gate
        self.assertTrue(any("commit must record" in e for e in cr.hermes_shape(rel)))
        h["image"]["commit"] = OLD
        self.assertTrue(any("differs from the upstream tag" in e for e in cr.hermes_shape(rel)))
        h["image"]["commit"] = TAG
        self.assertEqual(cr.hermes_shape(rel), [])

    def test_online_rejects_tag_image_mismatch_or_unknown_revision(self):
        h = {"tag": "v0.21.6", "commit": TAG, "image": {"digest": "sha256:" + "1" * 64, "commit": TAG}}
        for rev in (OLD, None, TAG):
            with self.subTest(rev=rev), patch.object(cr, "upstream_tag_commit", return_value=(TAG, "")), \
                    patch.object(cr, "dockerhub_digest_exists", return_value=(True, "")), \
                    patch.object(cr, "dockerhub_image_revision", return_value=(rev, "fixture")):
                ok, errors = cr.hermes_online({"hermes": h})
                self.assertEqual(bool(errors), rev != TAG, str((ok, errors)))


if __name__ == "__main__":
    unittest.main()
