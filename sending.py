"""
Simulated notification delivery.

IMPORTANT: This never sends anything real. No email provider, SMS gateway,
or any other external service is ever called - "sending" here means
randomly assigning a plausible success/failure result so the UI has
something real to show for "was it actually sent." This exists to
demonstrate what a delivery/result report would look like in a real
version; wiring up an actual send is explicitly out of scope for this
prototype (see README) and would still involve a human/approval step.

Channel logic: a member is notified on whichever contact channel(s) they
have on file - email, phone, or both if both are present. If neither is on
file, that's reported as its own distinct outcome rather than silently
failing.
"""

import random

# Deliberately a separate, unseeded RNG - keeps "send" simulation results
# fresh on every click, and never touches the seeded RNG that the mock
# member/claims data generation relies on for reproducibility.
_rng = random.Random()

SEND_SUCCESS_RATE = 0.95

SENT = "sent"
PARTIAL = "partial"
FAILED = "failed"
NO_CONTACT_INFO = "no_contact_info"


def simulate_send(email: str, phone: str) -> dict:
    """Simulates sending one notification to whichever of email/phone the
    member has on file - both, if both are present.

    Returns:
        {
          "overall_status": "sent" | "partial" | "failed" | "no_contact_info",
          "channels": [{"channel": "email"|"phone (SMS)", "address": str,
                        "status": "sent"|"failed", "detail": str}, ...],
        }
    """
    channels = []

    if email:
        ok = _rng.random() < SEND_SUCCESS_RATE
        channels.append(
            {
                "channel": "email",
                "address": email,
                "status": SENT if ok else FAILED,
                "detail": "Delivered" if ok else "Simulated delivery failure (e.g. bounced address)",
            }
        )
    if phone:
        ok = _rng.random() < SEND_SUCCESS_RATE
        channels.append(
            {
                "channel": "phone (SMS)",
                "address": phone,
                "status": SENT if ok else FAILED,
                "detail": "Delivered" if ok else "Simulated delivery failure (e.g. invalid number)",
            }
        )

    if not channels:
        return {"overall_status": NO_CONTACT_INFO, "channels": []}

    statuses = [c["status"] for c in channels]
    if all(s == SENT for s in statuses):
        overall = SENT
    elif any(s == SENT for s in statuses):
        overall = PARTIAL
    else:
        overall = FAILED

    return {"overall_status": overall, "channels": channels}
