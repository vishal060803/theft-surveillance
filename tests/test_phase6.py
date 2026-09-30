import json
import os
import tempfile
import unittest

from backend.realtime_surveillance import build_evidence_metadata, export_events_csv, list_evidence


class Phase6EvidenceTests(unittest.TestCase):
    def test_build_evidence_metadata_includes_required_fields(self):
        metadata = build_evidence_metadata(
            camera_id="cam-1",
            event_type="WEAPON_DETECTED",
            confidence=0.91,
            zone_name="cashier",
            risk_score=90.5,
            frames_before=120,
            frames_after=80,
            location={"lat": 12.9, "lon": 77.6},
        )
        self.assertIn("timestamp", metadata)
        self.assertIn("camera_id", metadata)
        self.assertIn("event_type", metadata)
        self.assertIn("confidence", metadata)
        self.assertIn("zone", metadata)
        self.assertIn("location", metadata)
        self.assertIn("risk_score", metadata)
        self.assertEqual(metadata["camera_id"], "cam-1")

    def test_export_events_csv_returns_csv_content(self):
        records = [
            {
                "timestamp": "2026-09-28T10:00:00",
                "camera_id": "cam-1",
                "event_type": "SUSPICIOUS_PERSON",
                "zone": "restricted",
                "risk_score": 81.5,
                "confidence": 0.87,
                "event_class": "loitering",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "events.csv")
            result_path = export_events_csv(records, output_path)
            self.assertTrue(os.path.exists(result_path))
            with open(result_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("event_type", content)
            self.assertIn("SUSPICIOUS_PERSON", content)

    def test_list_evidence_returns_video_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clip_path = os.path.join(tmpdir, "sample_event.mp4")
            with open(clip_path, "wb") as fh:
                fh.write(b"video")
            meta = {
                "timestamp": "2026-09-28T10:00:00",
                "camera_id": "cam-2",
                "event_type": "WEAPON_DETECTED",
                "zone": "storage",
                "risk_score": 88.0,
                "confidence": 0.9,
                "event_class": "weapon_seen",
            }
            with open(clip_path + ".json", "w", encoding="utf-8") as fh:
                json.dump(meta, fh)
            entries = list_evidence(tmpdir)
            self.assertTrue(any(item.get("clip_path", "").endswith("sample_event.mp4") for item in entries))


if __name__ == "__main__":
    unittest.main()
