"""scripts/deploy-release.sh against real git repositories and fake docker/curl/systemctl.

Checks the release gate (tag format, tag on main, CI success, clean checkout), the
backup, a successful deployment and the automatic rollback after failed checks.
"""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy-release.sh"

FAKE_DOCKER = r'''#!/usr/bin/env bash
echo "docker $*" >> "$FAKE_LOG"
args="$*"
case "$args" in
  "compose version") exit 0 ;;
  compose\ build*) [[ -n ${FAKE_BUILD_FAIL:-} ]] && exit 1; exit 0 ;;
  compose\ up*|compose\ stop*|compose\ start*) exit 0 ;;
  *"pg_isready"*) exit 0 ;;
  *"pg_dump"*) printf 'PGDMP-fake-dump'; exit 0 ;;
  *"pg_restore --list"*) cat > /dev/null; echo "; toc"; exit 0 ;;
  *"SELECT count(*) FROM editions"*) cat "$FAKE_DIR/editions"; exit 0 ;;
  "compose ps -q web") echo abc; exit 0 ;;
  *"tar czf"*) printf 'tar'; exit 0 ;;
  compose\ ps\ --format*) printf 'db running\npipeline running\nweb running\n'; exit 0 ;;
  *"schema_version"*) cat "$FAKE_DIR/schema"; exit 0 ;;
  compose\ logs*) echo "pipeline: cycle start 2026-11-26T00:00:00Z"; exit 0 ;;
  *"PRISM_DATA_TOKEN_FILE"*) exit 1 ;;
  image\ inspect\ -f*) echo "sha256:$(cat "$FAKE_DIR/image")"; exit 0 ;;
  image\ inspect*) exit 0 ;;
  image\ tag*) exit 0 ;;
  volume\ inspect*) exit 0 ;;
esac
echo "fake docker: unexpected: $args" >&2
exit 1
'''

FAKE_CURL = r'''#!/usr/bin/env bash
url=${!#}
case "$url" in
  *"/actions/runs?head_sha="*)
    sha=${url##*head_sha=}; sha=${sha%%&*}
    if [[ -f $FAKE_DIR/ci-$sha ]]; then cat "$FAKE_DIR/ci-$sha"; else echo '{"workflow_runs": []}'; fi ;;
  */healthz) echo ok ;;
  */api/v1/*) echo '[]' ;;
  */) echo '<html><div id="app"></div></html>' ;;
  *) exit 22 ;;
esac
'''

FAKE_SYSTEMCTL = r'''#!/usr/bin/env bash
case "$1" in
  is-active) exit 3 ;;
  is-enabled) exit 0 ;;
esac
exit 0
'''


GIT_ENV = dict(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.org")


def git(cwd, *args):
    return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args], cwd=cwd,
                          check=True, capture_output=True, text=True, env=dict(os.environ, **GIT_ENV)).stdout.strip()


class DeployReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = dict(os.environ, **GIT_ENV)
        origin = self.tmp / "prismaunfold.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, env=self.env)
        seed = self.tmp / "seed"
        subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True, env=self.env, capture_output=True)
        git(seed, "checkout", "-q", "-b", "main")
        (seed / "deploy/systemd").mkdir(parents=True)
        (seed / "README.md").write_text("v1\n")
        git(seed, "add", "-A"); git(seed, "commit", "-qm", "one")
        self.old = git(seed, "rev-parse", "HEAD")
        (seed / "README.md").write_text("v2\n")
        (seed / "scripts").mkdir()
        shutil.copy(SCRIPT, seed / "scripts/deploy-release.sh")
        git(seed, "add", "-A"); git(seed, "commit", "-qm", "two")
        self.new = git(seed, "rev-parse", "HEAD")
        git(seed, "tag", "-a", "v0.2.0", "-m", "release")
        git(seed, "checkout", "-q", "-b", "side")
        (seed / "README.md").write_text("side\n")
        git(seed, "commit", "-qam", "side")
        self.side = git(seed, "rev-parse", "HEAD")
        git(seed, "tag", "v0.2.1")
        git(seed, "push", "-q", "origin", "main", "side", "--tags")
        self.work = self.tmp / "unfold"
        subprocess.run(["git", "clone", "-q", str(origin), str(self.work)], check=True, env=self.env, capture_output=True)
        git(self.work, "checkout", "-q", "--detach", self.old)
        (self.work / ".env").write_text("POSTGRES_PASSWORD=secret\n")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, body in (("docker", FAKE_DOCKER), ("curl", FAKE_CURL), ("systemctl", FAKE_SYSTEMCTL)):
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        self.fake = self.tmp / "fake"
        self.fake.mkdir()
        (self.fake / "editions").write_text("3\n")
        (self.fake / "schema").write_text("2\n")
        (self.fake / "image").write_text("old\n")
        self.ci(self.new, "success")
        self.ci(self.side, "success")
        self.env.update(PATH=f"{bin_dir}:{os.environ['PATH']}", FAKE_DIR=str(self.fake), FAKE_LOG=str(self.tmp / "docker.log"),
                        UNFOLD_DIR=str(self.work), UNFOLD_REPO="prismaunfold.git", HOME=str(self.tmp / "home"),
                        WEB_URL="http://localhost:8080", VERIFY_TIMEOUT="3", GITHUB_API="https://api.example.org")
        (self.tmp / "home").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ci(self, sha, conclusion):
        (self.fake / f"ci-{sha}").write_text(json.dumps({"workflow_runs": [
            {"name": "CI", "status": "completed", "conclusion": conclusion}]}))

    def run_script(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env, capture_output=True, text=True, timeout=60)

    def head(self):
        return git(self.work, "rev-parse", "HEAD")

    def backups(self):
        base = self.tmp / "home/backups/prismunfold"
        return sorted(base.iterdir()) if base.exists() else []

    def test_deploys_a_verified_release_with_backup_and_state(self):
        result = self.run_script("deploy", "v0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(), self.new)
        backup, = self.backups()
        self.assertEqual((backup / "db.dump").read_text(), "PGDMP-fake-dump")
        self.assertIn("db.dump", (backup / "SHA256SUMS").read_text())
        self.assertEqual((backup / "config/.env").read_text(), "POSTGRES_PASSWORD=secret\n")
        self.assertEqual(oct((backup / "db.dump").stat().st_mode & 0o777), "0o600")
        self.assertIn(f"commit={self.old}", (backup / "manifest").read_text())
        state = self.tmp / "home/.local/state/prismunfold/deploy"
        self.assertEqual((state / "current").read_text().strip(), self.new)
        self.assertEqual((state / "previous").read_text().strip(), self.old)
        log = (self.tmp / "docker.log").read_text()
        self.assertIn("image tag prismunfold/pipeline:latest prismunfold/pipeline:rollback", log)
        self.assertNotIn("down", log)  # never `docker compose down`, never removes volumes
        self.assertNotIn(" rm", log)
        # Re-running the same release only verifies.
        again = self.run_script("deploy", "v0.2.0")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already checked out", again.stderr)
        self.assertEqual(len(self.backups()), 1)

    def test_refuses_anything_but_a_verified_release_on_main(self):
        cases = [(("deploy", "main"), "not a release tag"),
                 (("deploy", "v0.2.1"), "not on origin/main"),
                 (("deploy", "v9.9.9"), "does not exist")]
        for args, message in cases:
            result = self.run_script(*args)
            self.assertNotEqual(result.returncode, 0, args)
            self.assertIn(message, result.stderr, args)
        self.ci(self.new, "failure")
        result = self.run_script("deploy", "v0.2.0")
        self.assertIn("has not succeeded", result.stderr)
        self.assertEqual(self.head(), self.old)
        self.assertEqual(self.backups(), [])

    def test_refuses_a_locally_modified_checkout(self):
        (self.work / "README.md").write_text("local edit\n")
        result = self.run_script("deploy", "v0.2.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed locally", result.stderr)
        self.assertEqual(self.backups(), [])

    def test_failed_checks_roll_back_code_and_images(self):
        (self.fake / "schema").write_text("1\n")  # new version does not come up correctly
        result = self.run_script("deploy", "v0.2.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rolled back", result.stderr)
        self.assertEqual(self.head(), self.old)
        log = (self.tmp / "docker.log").read_text()
        self.assertIn("image tag prismunfold/web:rollback prismunfold/web:latest", log)
        self.assertEqual(len(self.backups()), 1)  # the pre-deployment backup is kept

    def test_unfold_update_deploys_the_newest_release_on_main_with_its_own_script(self):
        result = subprocess.run(["bash", str(ROOT / "deploy/unfold-update")], env=self.env, capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(), self.new)  # v0.2.0, not v0.2.1 from a side branch
        refused = subprocess.run(["bash", str(ROOT / "deploy/unfold-update"), "v0.2.1"], env=self.env,
                                 capture_output=True, text=True, timeout=60)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("not a release on origin/main", refused.stderr)
        status = subprocess.run(["bash", str(ROOT / "deploy/unfold-update"), "status"], env=self.env,
                                capture_output=True, text=True, timeout=60)
        self.assertIn(self.new, status.stdout)

    def test_restore_requires_confirmation_and_checksum(self):
        self.assertEqual(self.run_script("deploy", "v0.2.0").returncode, 0)
        backup, = self.backups()
        self.assertNotEqual(self.run_script("restore-db", str(backup)).returncode, 0)
        (backup / "db.dump").write_text("tampered")
        result = self.run_script("restore-db", str(backup), "--yes")
        self.assertIn("checksum mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
