# SafeSignal — AI & IoT Women Safety Research + Working MVP

SafeSignal turns the existing conceptual research on proactive safety monitoring into a **working, local-first proof of concept**: a responsive SOS interface, location opt-in, trusted-contact SMS provider integration, and a check-in reminder.

**Prototype, not a certified safety product.** It does not predict assault, automatically detect danger, dispatch emergency personnel, or guarantee delivery. The paper describes future AI/IoT capabilities; those remain **research proposals**, not shipped functionality.

## What works today

- Manual SOS flow with explicit confirmation.
- Optional, user-approved coarse location sharing through the browser Geolocation API.
- Server-side SMS sending using Twilio **only when all credentials and a trusted opt-in contact are configured**.
- Clear simulation status in the UI when credentials are absent: **no messages are sent**.
- Provider acknowledgement distinguished from actual delivery.
- 60-second rate limit to reduce repeated outbound message requests.
- Check-in timer and local reminder (only while the page is open).
- Standard-library Python backend and frontend; no Python packages required.
- Unit tests and automated CI.

## Getting started

```bash
python app.py
```

Open **http://127.0.0.1:8765**. This is the default safe **demo mode**.

```bash
python -m unittest discover -s tests -v
```

## Optional actual SMS integration

Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` and `ALERT_TO_NUMBER` in **private server environment settings**. All four are required; the contact must have opted in. Do not publicly expose this server.

The backend requests a message via Twilio; **a 202 response means Twilio accepted the request, not that it was received**. Configure delivery callbacks, escalation logic, monitoring and provider failure recovery before relying on it.

## Privacy and security limitations

- The app binds to `127.0.0.1`; it is intentionally **not production deployable** as-is.
- There is **no public-user authentication**. Deploying on the Internet or modifying it to bind on all interfaces without strong authentication, HTTPS, consent, durable rate limits and security review would be unsafe.
- No database, telemetry or location storage. Location is requested only after the user opts in and activates an alert.
- Alerts use a server-controlled preconfigured trusted contact, preventing arbitrary recipient entry.
- Browser check-in reminders are not guaranteed if the device sleeps, the tab closes, or connectivity fails.
- In urgent danger, **call local emergency services directly** and use other trusted channels.

See [Operational Safety Notes](OPERATIONAL_SAFETY.md) for the local-only
boundary, provider limitations, credential handling, and alert-flow safeguards.

## Roadmap for real-world feasibility

1. Mobile-first app with background check-ins, power/battery-state warnings and tested offline fallbacks.
2. Consent-based identity and trusted-contact management, delivery confirmations and opt-out.
3. Emergency response partnerships and measured field reliability, accessibility and privacy/security reviews.
4. Only after validated datasets and evaluation, research AI-based risk signals with low false-alarm burden and human confirmation.

The original research paper remains in the repository as `Research Paper (4).pdf`; the document describes a proposal rather than the deployed software. The original README contained dead placeholder links; this revision removes them.
