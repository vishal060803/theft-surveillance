import os
import sqlite3
import tempfile
import unittest

from backend.realtime_surveillance import (
    apply_retention_policy,
    create_evidence_backup,
    get_system_health_snapshot,
)


class Phase10SecurityDeploymentTests(unittest.TestCase):
    def test_get_system_health_snapshot_returns_monitoring_data(self):
        snapshot = get_system_health_snapshot()
        self.assertIn("cpu_usage", snapshot)
        self.assertIn("memory_usage", snapshot)
        self.assertIn("camera_health", snapshot)

    def test_apply_retention_policy_removes_old_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = os.path.join(tmpdir, "old_clip.mp4")
            recent_file = os.path.join(tmpdir, "recent_clip.mp4")
            with open(old_file, "w", encoding="utf-8") as handle:
                handle.write("old")
            with open(recent_file, "w", encoding="utf-8") as handle:
                handle.write("new")
            old_time = 1704067200
            os.utime(old_file, (old_time, old_time))

            old_ts = "2024-01-01T00:00:00"
            recent_ts = "2026-09-28T00:00:00"
            conn = sqlite3.connect(":memory:")
            cur = conn.cursor()
            cur.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, clip_path TEXT)")
            cur.execute("INSERT INTO events (ts, clip_path) VALUES (?, ?)", (old_ts, old_file))
            cur.execute("INSERT INTO events (ts, clip_path) VALUES (?, ?)", (recent_ts, recent_file))
            conn.commit()

            result = apply_retention_policy(base_dir=tmpdir, conn=conn, retention_days=30)
            self.assertGreaterEqual(result["deleted_events"], 1)
            self.assertFalse(os.path.exists(old_file))

    def test_create_evidence_backup_creates_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = os.path.join(tmpdir, "evidence")
            backup_dir = os.path.join(tmpdir, "backup")
            os.makedirs(evidence_dir, exist_ok=True)
            evidence_path = os.path.join(evidence_dir, "sample.mp4")
            with open(evidence_path, "w", encoding="utf-8") as handle:
                handle.write("demo")

            archive = create_evidence_backup(evidence_dir, backup_dir)
            self.assertTrue(os.path.exists(archive))


if __name__ == "__main__":
    unittest.main()
