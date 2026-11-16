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

    def test_alert_cooldown_uses_injected_monotonic_clock(self):
        clock = [100.0]
        cooldown = app.AlertCooldown(60, clock=lambda: clock[0])
        self.assertTrue(cooldown.try_acquire())
        self.assertFalse(cooldown.try_acquire())
        clock[0] += 60
        self.assertTrue(cooldown.try_acquire())
        with self.assertRaises(ValueError):
            app.AlertCooldown(0)

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

    def test_alert_payload_requires_explicit_minimal_confirmation(self):
        self.assertEqual(app.parse_alert_payload({"confirm": True}), None)
        self.assertEqual(app.parse_alert_payload({"confirm": True, "location": {"latitude": 0, "longitude": 0}}),
                         {"latitude": 0, "longitude": 0})
        for payload in ({}, {"confirm": False}, {"confirm": True, "note": "extra"}, []):
            with self.assertRaises(ValueError):
                app.parse_alert_payload(payload)

    def test_request_body_requires_valid_utf8_json(self):
        self.assertEqual(app.decode_json_body(b'{"confirm": true}'), {"confirm": True})
        for body in (b"not-json", b"\xff\xfe"):
            with self.assertRaises(ValueError):
                app.decode_json_body(body)

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
        outcome = app.send_sms("SOS!", app.SmsConfiguration(sid, "secret", "+15551234567", "+15557654321"), fake_open)
        self.assertEqual(outcome["status"], "submitted_to_provider")
        self.assertEqual(parse_qs(request_seen[0][0].data.decode())["Body"], ["SOS!"])

    def test_sms_configuration_is_immutable(self):
        config = app.SmsConfiguration("AC" + "a" * 32, "b" * 32, "+15551234567", "+15557654321")
        with self.assertRaises(AttributeError):
            config.sender = "+15550000000"

    def test_malformed_twilio_auth_token_is_not_treated_as_configured(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "AC" + "a" * 32,
                                      "TWILIO_AUTH_TOKEN": "not-a-token",
                                      "TWILIO_FROM_NUMBER": "+15551234567",
                                      "ALERT_TO_NUMBER": "+15557654321"}, clear=True):
            with self.assertRaisesRegex(ValueError, "authentication token"):
                app.configured_sms()
            self.assertEqual(app.sms_mode(), "misconfigured")

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

    def test_runtime_status_never_includes_provider_credentials(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            status = app.runtime_status()
        self.assertEqual(status["mode"], "demo")
        self.assertFalse(status["sms_configured"])
        self.assertIn("not an emergency service", status["warning"].lower())
        self.assertNotIn("token", str(status).lower())

    def test_security_headers_protect_static_and_api_responses(self):
        headers = app.security_headers("application/json", 42)
        self.assertEqual(headers["Content-Length"], "42")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("geolocation", headers["Permissions-Policy"])

    def test_only_local_browser_origins_are_allowed(self):
        self.assertTrue(app.is_allowed_local_origin(None, port=8765))
        self.assertTrue(app.is_allowed_local_origin("http://127.0.0.1:8765", port=8765))
        self.assertTrue(app.is_allowed_local_origin("http://localhost:8765", port=8765))
        self.assertFalse(app.is_allowed_local_origin("https://example.com", port=8765))
        self.assertFalse(app.is_allowed_local_origin("http://127.0.0.1:8766", port=8765))


if __name__ == "__main__":
    unittest.main()
