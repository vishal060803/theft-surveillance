import os
import sqlite3
import tempfile
import unittest

from backend.realtime_surveillance import (
    build_incident_summary,
    export_report_csv,
    get_report_window_data,
)


class Phase9ReportingTests(unittest.TestCase):
    def test_build_incident_summary_counts_events(self):
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event_type TEXT, note TEXT, clip_path TEXT, zone_name TEXT, risk_score REAL, event_class TEXT, metadata TEXT)"
        )
        cur.executemany(
            "INSERT INTO events (ts, event_type, note, clip_path, zone_name, risk_score, event_class, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-09-28T10:15:00", "WEAPON_DETECTED", "Weapon detected", "clip1.mp4", "cashier", 92.0, "weapon_seen", "{}"),
                ("2026-09-28T10:40:00", "SUSPICIOUS_PERSON", "Suspicious movement", "clip2.mp4", "restricted", 74.0, "loitering", "{}"),
                ("2026-09-28T11:00:00", "EMERGENCY_SIGNAL", "Emergency", "clip3.mp4", "exit", 99.0, "emergency_signal", "{}"),
            ],
        )
        conn.commit()

        summary = build_incident_summary(conn)
        self.assertEqual(summary["total_events"], 3)
        self.assertIn("WEAPON_DETECTED", summary["by_event_type"])
        self.assertIn("cashier", summary["by_zone"])
        self.assertGreaterEqual(summary["avg_risk"], 0)

    def test_get_report_window_data_returns_time_buckets(self):
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event_type TEXT, note TEXT, clip_path TEXT, zone_name TEXT, risk_score REAL, event_class TEXT, metadata TEXT)"
        )
        cur.executemany(
            "INSERT INTO events (ts, event_type, note, clip_path, zone_name, risk_score, event_class, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-09-28T08:00:00", "WEAPON_DETECTED", "Weapon", "clip1.mp4", "cashier", 90.0, "weapon_seen", "{}"),
                ("2026-09-28T09:00:00", "SUSPICIOUS_PERSON", "Suspicious", "clip2.mp4", "restricted", 70.0, "loitering", "{}"),
            ],
        )
        conn.commit()

        rows = get_report_window_data(conn, window="day")
        self.assertTrue(len(rows) >= 1)
        self.assertIn("total_events", rows[0])

    def test_export_report_csv_creates_report_file(self):
        rows = [
            {"day": "2026-09-28", "total_events": 3, "high_risk": 2, "avg_risk": 83.5},
            {"day": "2026-09-29", "total_events": 1, "high_risk": 0, "avg_risk": 48.0},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.csv")
            result = export_report_csv(rows, output_path)
            self.assertTrue(os.path.exists(result))
            with open(result, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("day", content)
            self.assertIn("total_events", content)


if __name__ == "__main__":
    unittest.main()
