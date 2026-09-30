import sqlite3
import unittest

from backend.realtime_surveillance import (
    acknowledge_alert,
    build_alert_message,
    get_alert_priority,
    init_db,
    list_alerts,
)


class Phase7AlertWorkflowTests(unittest.TestCase):
    def test_get_alert_priority_returns_valid_level(self):
        self.assertEqual(get_alert_priority("weapon_seen", 92.0), "critical")
        self.assertEqual(get_alert_priority("suspicious_movement", 65.0), "high")

    def test_build_alert_message_includes_zone_and_risk(self):
        payload = build_alert_message(
            event_type="WEAPON_DETECTED",
            event_class="weapon_seen",
            zone_name="cashier",
            risk_score=92.0,
            note="Weapon detected",
        )
        self.assertIn("title", payload)
        self.assertIn("body", payload["body"])
        self.assertIn("cashier", payload["body"].lower())
        self.assertIn("92", payload["body"])

    def test_alert_acknowledgement_tracks_responder(self):
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event_type TEXT, event_class TEXT, zone_name TEXT, risk_score REAL, priority TEXT, status TEXT, responder TEXT, acknowledged_at TEXT, message TEXT)"
        )
        cur.execute(
            "INSERT INTO alerts (ts, event_type, event_class, zone_name, risk_score, priority, status, responder, acknowledged_at, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-09-28T10:00:00", "WEAPON_DETECTED", "weapon_seen", "cashier", 92.0, "critical", "open", None, None, "Weapon detected")
        )
        conn.commit()
        updated = acknowledge_alert(conn, 1, "security-01")
        self.assertTrue(updated["acknowledged"])
        self.assertEqual(updated["responder"], "security-01")
        self.assertEqual(updated["status"], "acknowledged")

    def test_list_alerts_reads_alert_rows(self):
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event_type TEXT, event_class TEXT, zone_name TEXT, risk_score REAL, priority TEXT, status TEXT, responder TEXT, acknowledged_at TEXT, message TEXT)"
        )
        cur.execute(
            "INSERT INTO alerts (ts, event_type, event_class, zone_name, risk_score, priority, status, responder, acknowledged_at, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-09-28T10:00:00", "WEAPON_DETECTED", "weapon_seen", "cashier", 92.0, "critical", "open", None, None, "Weapon detected")
        )
        conn.commit()
        alerts = list_alerts(conn)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["priority"], "critical")


if __name__ == "__main__":
    unittest.main()
