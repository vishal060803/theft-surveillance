import unittest

import app as surveillance_app


class Phase8DashboardMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.client = surveillance_app.app.test_client()

    def test_dashboard_homepage_renders_monitoring_shell(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Security Operations Center', response.data)
        self.assertIn(b'Alerts Log', response.data)

    def test_health_endpoint_reports_monitoring_state(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get('status'), 'ok')
        self.assertIn('evidence_count', payload)
        self.assertIn('alerts_count', payload)

    def test_dashboard_summary_contains_operational_metrics(self):
        response = self.client.get('/dashboard/summary')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('alerts_total', payload)
        self.assertIn('evidence_total', payload)
        self.assertIn('hotspots', payload)

    def test_alerts_endpoint_is_available(self):
        response = self.client.get('/alerts')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('alerts', payload)
        self.assertIn('count', payload)


if __name__ == '__main__':
    unittest.main()
