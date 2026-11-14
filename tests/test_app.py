import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs
import app


class SafetyPrototypeTests(unittest.TestCase):
    def test_port_requires_unprivileged_integer(self):
        self.assertEqual(app.parse_port("8765"), 8765)
        for value in ("invalid", 80, 65536, None):
            with self.assertRaises(ValueError):
                app.parse_port(value)

    def test_valid_coordinates_are_rounded(self):
        self.assertEqual(app.validate_location({"latitude": 28.6139123, "longitude": 77.2090123}),
                         {"latitude": 28.61391, "longitude": 77.20901})

    def test_location_opt_in(self):
        self.assertIsNone(app.validate_location(None))
        self.assertNotIn("maps.google", app.create_alert_message(None))

    def test_invalid_location_rejected(self):
        for value in ({"latitude": 91, "longitude": 0}, {"latitude": True, "longitude": 0},
                      {"latitude": 1, "longitude": "0"}, []):
            with self.assertRaises(ValueError):
                app.validate_location(value)

    def test_message_includes_map_link_when_authorized(self):
        self.assertIn("maps.google.com/?q=28.6,77.2",
                      app.create_alert_message({"latitude": 28.6, "longitude": 77.2}))

    def test_sms_is_demo_without_credentials(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(app.configured_sms())

    def test_twilio_request_is_provider_ack_not_delivery(self):
        sid = "AC" + "a" * 32
        request_seen = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _): return b'{"sid":"SM123"}'
        def fake_open(req, timeout):
            request_seen.append((req, timeout))
            return Response()
        outcome = app.send_sms("SOS!", (sid, "secret", "+15551234567", "+15557654321"), fake_open)
        self.assertEqual(outcome["status"], "submitted_to_provider")
        self.assertEqual(parse_qs(request_seen[0][0].data.decode())["Body"], ["SOS!"])

    def test_misconfigured_sms_is_distinguished_from_demo(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "invalid",
                                      "TWILIO_AUTH_TOKEN": "secret",
                                      "TWILIO_FROM_NUMBER": "+15551234567",
                                      "ALERT_TO_NUMBER": "+15557654321"}, clear=True):
            self.assertEqual(app.sms_mode(), "misconfigured")

    def test_missing_sms_configuration_remains_demo(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app.sms_mode(), "demo")


if __name__ == "__main__":
    unittest.main()
