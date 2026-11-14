# Operational Safety Notes

SafeSignal is a local demonstration of a manually confirmed alert flow. It is
not an emergency dispatch service, a medical device, or an automated danger
detection system. The interface and server intentionally make fewer promises
than a production safety product would need to meet.

## Local-only boundary

The server listens on `127.0.0.1` and accepts browser requests only from the
matching localhost origins. Do not change that binding to an Internet-facing
address without authentication, HTTPS, durable rate limits, monitoring, access
controls, and a professional security review.

## SMS configuration

When every Twilio setting is absent, the app operates in demo mode and sends no
messages. A partial or malformed configuration is surfaced as unavailable; it
does not silently fall back to a pretend delivery. Credentials belong only in
private environment settings and must never be committed.

A successful provider response means that the provider accepted the request.
It does not prove delivery, receipt, or a successful emergency response. Any
real integration needs delivery callbacks, retry policy, provider monitoring,
and an opt-in trusted-contact process.

## Alert handling

The browser requires a manual confirmation before it posts an alert. Location
is optional, is rounded before inclusion, and is sent only for that alert; this
prototype does not store it. The server accepts a minimal JSON shape, rejects
cross-origin requests, limits request size, and applies a short local cooldown
to avoid accidental repeated submissions.

## Immediate danger

Use local emergency services and direct trusted-contact channels first. An app,
browser, device, network, or SMS provider can fail at the moment it is needed.
