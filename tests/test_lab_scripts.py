"""Offline command-contract tests: no cloud account, cluster or credentials are used."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
state = pathlib.Path(os.environ["MOCK_STATE"])
with (state / "calls.jsonl").open("a") as out:
    out.write(json.dumps([name] + args) + "\n")
def starts(*prefix):
    return args[:len(prefix)] == list(prefix)
def flag(prefix):
    return next(a.split("=", 1)[1] for a in args if a.startswith(prefix + "="))
if name == "git":
    if starts("diff"):
        sys.exit(1 if os.environ.get("MOCK_DIRTY") else 0)
    if starts("rev-parse"):
        print("abcdef1")
elif name == "gcloud":
    for prefix, item in [(("artifacts", "repositories"), "repo"),
                         (("iam", "service-accounts"), "sa"),
                         (("storage", "buckets"), "bucket")]:
        if starts(*prefix, "describe"):
            if os.environ.get("MOCK_DENIED"):
                print("PERMISSION_DENIED", file=sys.stderr)
                sys.exit(1)
            if not (state / item).exists():
                print("NOT_FOUND", file=sys.stderr)
                sys.exit(1)
        if starts(*prefix, "create"):
            (state / item).touch()
    if starts("projects", "describe"):
        print("123456789")
    if starts("container", "clusters", "describe"):
        if os.environ.get("MOCK_CUSTOM_NODE_SA"):
            print("custom-node@antojo-lab.iam.gserviceaccount.com")
        elif "--flatten=nodePools" not in args:
            print("default")
    if starts("artifacts", "repositories", "set-cleanup-policies"):
        policy = json.loads(pathlib.Path(flag("--policy")).read_text())
        (state / "cleanup.json").write_text(json.dumps(policy))
    if starts("storage", "buckets", "update"):
        policy = json.loads(pathlib.Path(flag("--lifecycle-file")).read_text())
        (state / "lifecycle.json").write_text(json.dumps(policy))
elif name == "helm":
    if starts("upgrade") and os.environ.get("MOCK_HELM_FAIL"):
        sys.exit(1)
elif name == "kubectl":
    if "deployments" in args:
        print("deployment.apps/frontend\ndeployment.apps/cartservice")
    if "svc" in args:
        print("203.0.113.10")
'''


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.bin = self.state / "bin"
        self.bin.mkdir()
        for name in ("gcloud", "git", "helm", "kubectl"):
            file = self.bin / name
            file.write_text(MOCK)
            file.chmod(0o755)
        self.env = {**os.environ, "MOCK_STATE": str(self.state),
                    "PATH": str(self.bin) + os.pathsep + os.environ["PATH"]}

    def run_script(self, name, **env):
        return subprocess.run(["bash", str(ROOT / "scripts" / name)],
                              env={**self.env, **env}, text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in
                (self.state / "calls.jsonl").read_text().splitlines()]

    def test_bootstrap_is_idempotent_and_scopes_iam(self):
        for _ in range(2):
            result = self.run_script("bootstrap-lab.sh")
            self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        for prefix in (["gcloud", "artifacts", "repositories", "create"],
                       ["gcloud", "iam", "service-accounts", "create"],
                       ["gcloud", "storage", "buckets", "create"]):
            self.assertEqual(sum(c[:len(prefix)] == prefix for c in calls), 1)
        writers = [c for c in calls if "--role=roles/artifactregistry.writer" in c]
        self.assertTrue(all(c[1:3] == ["artifacts", "repositories"] for c in writers))
        readers = [c for c in calls if "--role=roles/artifactregistry.reader" in c]
        self.assertTrue(all("--member=serviceAccount:123456789-compute@developer.gserviceaccount.com" in c for c in readers))
        self.assertFalse(any("--role=roles/editor" in c for c in calls))
        policy = json.loads((self.state / "cleanup.json").read_text())
        self.assertEqual(policy[1]["mostRecentVersions"]["keepCount"], 5)
        self.assertEqual(policy[0]["action"]["type"], "Delete")
        self.assertEqual(json.loads((self.state / "lifecycle.json").read_text())["rule"][0]["condition"]["age"], 1)

    def test_custom_node_account_is_discovered(self):
        result = self.run_script("bootstrap-lab.sh", MOCK_CUSTOM_NODE_SA="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any("--member=serviceAccount:custom-node@antojo-lab.iam.gserviceaccount.com" in c for c in self.calls()))

    def test_permission_error_does_not_attempt_creation(self):
        result = self.run_script("bootstrap-lab.sh", MOCK_DENIED="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("create" in c for c in self.calls()))

    def test_build_uses_one_sha_and_explicit_context(self):
        result = self.run_script("build-and-deploy.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("http://203.0.113.10", result.stdout)
        calls = self.calls()
        build = next(c for c in calls if c[1:3] == ["builds", "submit"])
        self.assertIn("--substitutions=_TAG=abcdef1", build)
        install = next(c for c in calls if c[:2] == ["helm", "upgrade"])
        self.assertIn("global.imageTag=abcdef1", install)
        self.assertIn("--atomic", install)
        self.assertIn("gke_antojo-lab_us-central1_antojo", install)
        self.assertTrue(all("--context=gke_antojo-lab_us-central1_antojo" in c for c in calls if c[0] == "kubectl"))
        self.assertEqual(sum("rollout" in c for c in calls), 2)

    def test_dirty_input_blocks_cloud_spending(self):
        result = self.run_script("build-and-deploy.sh", MOCK_DIRTY="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == "gcloud" for c in self.calls()))

    def test_failed_install_does_not_announce_success(self):
        result = self.run_script("build-and-deploy.sh", MOCK_HELM_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("http://", result.stdout)
        self.assertFalse(any("rollout" in c for c in self.calls()))


if __name__ == "__main__":
    unittest.main()
