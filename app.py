"""Local-first safety alert prototype.

Never bind to 0.0.0.0 or publish publicly without user authentication,
network security, audit, rate-limit infrastructure and delivery tests.
"""
from __future__ import annotations
import base64
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ALERT_COOLDOWN_SECONDS = 60
lock = threading.Lock()
last_delivery_attempt = 0.0
MAX_BYTES = 2048


@dataclass(frozen=True)
class SmsConfiguration:
    account_sid: str
    auth_token: str
    sender: str
    receiver: str


def parse_port(value):
    """Parse an explicit unprivileged local-listener port."""
    try:
        port = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("PORT must be an integer") from error
    if not 1024 <= port <= 65535:
        raise ValueError("PORT must be between 1024 and 65535")
    return port


PORT = parse_port(os.environ.get("PORT", "8765"))


def validate_location(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Location must be an object")
    lat, lon = value.get("latitude"), value.get("longitude")
    if type(lat) not in (int, float) or type(lon) not in (int, float):
        raise ValueError("Location must have numeric latitude and longitude")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Location is out of range")
    return {"latitude": round(lat, 5), "longitude": round(lon, 5)}


def parse_alert_payload(payload):
    """Accept only an explicitly confirmed alert and optional location."""
    if not isinstance(payload, dict):
        raise ValueError("Alert payload must be an object")
    unexpected = set(payload) - {"confirm", "location"}
    if unexpected:
        raise ValueError("Alert payload contains unsupported fields")
    if payload.get("confirm") is not True:
        raise ValueError("Manual confirmation is required")
    return validate_location(payload.get("location"))


def create_alert_message(location=None):
    link = ""
    if location:
        link = (" Location shared by user: https://maps.google.com/?q="
                f"{location['latitude']},{location['longitude']}")
    return (
        "SAFETY ALERT: A trusted person manually activated an SOS request."
        " Please call them and check their safety. If there is immediate danger,"
        " contact local emergency services." + link
    )


def configured_sms():
    env_names = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                 "TWILIO_FROM_NUMBER", "ALERT_TO_NUMBER")
    values = [os.environ.get(key, "").strip() for key in env_names]
    if not all(values):
        return None
    sid, token, sender, receiver = values
    if not re.fullmatch(r"AC[0-9a-fA-F]{32}", sid):
        raise ValueError("Invalid Twilio account SID")
    if not all(re.fullmatch(r"\+[1-9]\d{7,14}", phone) for phone in (sender, receiver)):
        raise ValueError("Both configured phone numbers must be E.164 format")
    return SmsConfiguration(sid, token, sender, receiver)


def sms_mode():
    """Report misconfiguration safely without displaying credentials."""
    try:
        return "configured" if configured_sms() else "demo"
    except ValueError:
        return "misconfigured"


def send_sms(message, config, opener=urlopen):
    """Delivery is attempted, not guaranteed; Twilio status must be monitored."""
    uri = f"https://api.twilio.com/2010-04-01/Accounts/{config.account_sid}/Messages.json"
    body = urlencode({"To": config.receiver, "From": config.sender, "Body": message}).encode()
    credentials = base64.b64encode(f"{config.account_sid}:{config.auth_token}".encode()).decode()
    request = Request(
        uri, data=body,
        headers={"Authorization": f"Basic {credentials}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with opener(request, timeout=8) as response:
        result = json.loads(response.read(32768))
    if not result.get("sid"):
        raise RuntimeError("SMS provider did not acknowledge the request")
    return {"status": "submitted_to_provider", "provider_id": result["sid"]}


class Handler(BaseHTTPRequestHandler):
    def json_response(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            mode = sms_mode()
            self.json_response(200, {"mode": mode,
                                     "sms_configured": mode == "configured",
                                     "warning": "Not an emergency service. Delivery is never guaranteed."})
            return
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/index.html": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "application/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path not in assets:
            self.send_error(404)
            return
        name, mime = assets[path]
        data = (ROOT / "web" / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        global last_delivery_attempt
        if self.path != "/api/alerts":
            self.json_response(404, {"error": "Not found"})
            return
        # Local-only by default. Check Origin to reject cross-origin browser requests.
        origin = self.headers.get("Origin")
        expected = f"http://127.0.0.1:{PORT}"
        if origin and origin not in (expected, f"http://localhost:{PORT}"):
            self.json_response(403, {"error": "Cross-origin requests are disabled"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.json_response(415, {"error": "JSON requests are required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BYTES:
                self.json_response(413, {"error": "Invalid request size"})
                return
            payload = json.loads(self.rfile.read(size))
            location = parse_alert_payload(payload)
            settings = configured_sms()
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.json_response(400, {"error": str(error)})
            return

        if not settings:
            self.json_response(200, {"status": "demo_only", "message":
                               "SOS simulated locally. NO SMS or emergency service was contacted."})
            return

        with lock:
            now = time.monotonic()
            if now - last_delivery_attempt < ALERT_COOLDOWN_SECONDS:
                self.json_response(429, {"error": "Please wait before retrying an alert"})
                return
            last_delivery_attempt = now
        try:
            result = send_sms(create_alert_message(location), settings)
            self.json_response(202, result)
        except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError):
            self.json_response(502, {"error":
                               "SMS provider request failed. Call emergency services directly if needed."})

    def log_message(self, fmt, *args):
        # Avoid writing user location or message bodies to access logs.
        print("%s %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print(f"Women Safety prototype: http://127.0.0.1:{PORT}")
    print("LOCAL DEMO. This service is not a substitute for emergency services.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
