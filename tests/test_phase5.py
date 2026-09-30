import unittest

from backend.realtime_surveillance import classify_event, should_emit_event


class Phase5RiskScoringTests(unittest.TestCase):
    def test_classify_event_returns_valid_class_and_risk(self):
        event_class, risk_score, note = classify_event(
            event_type="SUSPICIOUS_PERSON",
            zone_name="restricted",
            suspicious_track_count=2,
            dwell_seconds=18,
            confidence=0.88,
            movement=70,
            speed=24,
            violence_detected=False,
        )
        self.assertIn(event_class, {
            "loitering",
            "entering_restricted_area",
            "suspicious_movement",
            "theft_attempt"
        })
        self.assertGreaterEqual(risk_score, 0)
        self.assertLessEqual(risk_score, 100)
        self.assertIn("risk", note.lower())

    def test_dedupe_blocks_repeated_alerts(self):
        first = should_emit_event("weapon_seen", "cashier")
        second = should_emit_event("weapon_seen", "cashier")
        self.assertTrue(first)
        self.assertFalse(second)


if __name__ == "__main__":
    unittest.main()
