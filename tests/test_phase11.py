import unittest

from backend.realtime_surveillance import (
    benchmark_detection_pipeline,
    evaluate_scene_conditions,
    measure_event_latency,
    run_validation_suite,
)


class Phase11ValidationTests(unittest.TestCase):
    def test_benchmark_detection_pipeline_returns_metrics(self):
        result = benchmark_detection_pipeline(
            true_positives=18,
            false_positives=2,
            false_negatives=3,
            model_versions=["yolov8s", "yolov10n"],
        )
        self.assertIn("precision", result)
        self.assertIn("false_alarm_rate", result)
        self.assertIn("model_versions", result)
        self.assertGreater(result["precision"], 0.0)

    def test_evaluate_scene_conditions_returns_condition_breakdown(self):
        result = evaluate_scene_conditions(
            lighting_score=0.8,
            crowd_density=0.75,
            video_quality=0.58,
        )
        self.assertIn("lighting", result)
        self.assertIn("crowd", result)
        self.assertIn("quality", result)
        self.assertIn("overall_readiness", result)

    def test_measure_event_latency_returns_timing_summary(self):
        result = measure_event_latency(detection_ms=220, alert_ms=450, review_ms=190)
        self.assertIn("detection_latency_ms", result)
        self.assertIn("alert_delay_ms", result)
        self.assertIn("review_time_ms", result)
        self.assertGreater(result["total_latency_ms"], 0)

    def test_run_validation_suite_generates_operation_summary(self):
        report = run_validation_suite(
            true_positives=20,
            false_positives=2,
            false_negatives=4,
            lighting_score=0.81,
            crowd_density=0.72,
            video_quality=0.66,
            detection_ms=240,
            alert_ms=500,
            review_ms=210,
        )
        self.assertIn("overall_status", report)
        self.assertIn("benchmark", report)
        self.assertIn("scene_conditions", report)
        self.assertIn("latency", report)


if __name__ == "__main__":
    unittest.main()
