"""
Issue detection + drafting logic.

Given matched claims, this module:
  1. Determines which of the four issue categories (if any) apply.
  2. Drafts a member-facing notification in a warm "member advocate" voice
     for the three CONFIRMED issue categories.
  3. Drafts an internal action ticket with a concrete next step for ALL
     flagged issues, including dispute risk.

Design decision worth calling out: "possible dispute risk" is a
PREDICTION, not a confirmed fact about the claim - we flag it internally
for the team to review before the member is ever billed, but we do NOT
auto-send a member-facing message for it. Telling a member "you might
dispute this" before anything has gone wrong would be strange and could
create the very anxiety this whole system is trying to prevent. A human
decides, after reviewing the internal flag, whether outreach is warranted.
"""

import re

OUT_OF_NETWORK = "out_of_network"
COB_NEEDED = "cob_needed"
WRONG_CARRIER = "wrong_carrier"
DISPUTE_RISK = "dispute_risk"

ISSUE_LABELS = {
    OUT_OF_NETWORK: "Out-of-network provider",
    COB_NEEDED: "Coordination of Benefits (COB) update needed",
    WRONG_CARRIER: "Claim sent to wrong carrier",
    DISPUTE_RISK: "Possible dispute risk (predicted, not confirmed)",
}

# A claim counts as a dispute-risk candidate when the billed amount is both
# meaningfully higher in relative terms AND in absolute dollars than the
# typical/expected cost for that service - avoids flagging tiny claims
# where a 2x multiple is still only a few dollars.
DISPUTE_RISK_RATIO_THRESHOLD = 1.5
DISPUTE_RISK_ABS_THRESHOLD = 150


def _first_name(full_name: str) -> str:
    if not full_name or not isinstance(full_name, str):
        return "there"
    return full_name.strip().split()[0]


def is_dispute_risk(amount: float, expected_amount: float) -> bool:
    if not expected_amount:
        return False
    ratio = amount / expected_amount
    return ratio >= DISPUTE_RISK_RATIO_THRESHOLD and (amount - expected_amount) >= DISPUTE_RISK_ABS_THRESHOLD


def determine_issues(claim_row) -> list:
    """Returns the list of issue-type codes that apply to a matched claim.

    A single claim can carry more than one issue (e.g. an out-of-network
    claim that is ALSO billed well above the typical rate for that
    service).
    """
    issues = []
    if claim_row.get("carrier_status") in (OUT_OF_NETWORK, COB_NEEDED, WRONG_CARRIER):
        issues.append(claim_row["carrier_status"])

    if is_dispute_risk(claim_row.get("amount"), claim_row.get("expected_amount")):
        issues.append(DISPUTE_RISK)

    return issues


def _money(x):
    return f"${x:,.2f}"


def draft_member_notification(claim_row, issue_type: str) -> str:
    """Warm, plain-language, member-advocate-voice draft. Never speaks as
    the carrier - always as the member's own support team.
    """
    first_name = _first_name(claim_row.get("member_name_on_file"))
    provider = claim_row.get("provider")
    service = claim_row.get("service_type")
    amount = _money(claim_row.get("amount"))
    dos = claim_row.get("date_of_service")

    if issue_type == OUT_OF_NETWORK:
        return (
            f"Hi {first_name},\n\n"
            f"We noticed your recent visit for {service} on {dos} with {provider} was billed "
            f"as out-of-network, which can mean a higher cost to you than expected. "
            f"We wanted to reach out before this becomes a surprise on a bill.\n\n"
            f"One thing that would help: if you already received a network exception waiver "
            f"for this specific service, please let us know. We're not able to see waiver "
            f"approvals on our end, so we can only account for it once you tell us.\n\n"
            f"We're here for you,\nYour Member Services Team"
        )

    if issue_type == COB_NEEDED:
        return (
            f"Hi {first_name},\n\n"
            f"A recent claim for {service} on {dos} can't fully process yet because your plan "
            f"needs an updated picture of any other insurance coverage you may have (this is "
            f"called Coordination of Benefits, or COB). This is a routine step, not a bill.\n\n"
            f"If you have other coverage - through a spouse's plan, Medicare, or otherwise - "
            f"just reply and let us know, or give us a call and we'll update it together in a "
            f"couple of minutes. If you don't have other coverage, let us know that too and "
            f"we'll get it confirmed on your file.\n\n"
            f"We're here for you,\nYour Member Services Team"
        )

    if issue_type == WRONG_CARRIER:
        return (
            f"Hi {first_name},\n\n"
            f"Your claim for {service} on {dos} with {provider} appears to have been sent to "
            f"the wrong insurance carrier by the provider's billing office. This is a routing "
            f"mix-up on their end, not something you did.\n\n"
            f"We're already reaching out to {provider} to get this resubmitted to the correct "
            f"carrier, and we'll track it until it's resolved. No action is needed from you "
            f"right now - we just wanted you to hear it from us first.\n\n"
            f"We're here for you,\nYour Member Services Team"
        )

    # Dispute risk is intentionally NOT member-facing - see module docstring.
    return ""


def draft_internal_ticket(claim_row, issue_type: str) -> dict:
    first_name = _first_name(claim_row.get("member_name_on_file"))
    provider = claim_row.get("provider")

    next_steps = {
        OUT_OF_NETWORK: (
            "Review out-of-network exception/appeal eligibility for this claim; "
            "contact member to discuss in-network alternatives or exception request. "
            "Also confirm whether the member already holds a network exception waiver "
            "for this service (not visible on our end - member outreach is the only way to know)."
        ),
        COB_NEEDED: (
            "Proactively contact member to confirm other insurance (COB) status "
            "and update the carrier record accordingly."
        ),
        WRONG_CARRIER: (
            f"Contact {provider} billing office to confirm resubmission to the correct "
            "carrier; track claim status until it reprocesses successfully."
        ),
        DISPUTE_RISK: (
            "Flag for internal review before the member is billed - billed amount is "
            "significantly above the typical/expected cost for this service. Determine "
            "whether proactive outreach is warranted (probabilistic flag, not a confirmed issue)."
        ),
    }

    priority = "High" if issue_type in (OUT_OF_NETWORK, WRONG_CARRIER) else (
        "Medium" if issue_type == COB_NEEDED else "Review"
    )

    return {
        "claim_id": claim_row.get("claim_id"),
        "member_id": claim_row.get("matched_member_id"),
        "member_name": claim_row.get("member_name_on_file"),
        "issue_type": ISSUE_LABELS[issue_type],
        "priority": priority,
        "next_step": next_steps[issue_type],
        "provider": provider,
        "service_type": claim_row.get("service_type"),
        "amount": claim_row.get("amount"),
        "expected_amount": claim_row.get("expected_amount"),
        "date_of_service": claim_row.get("date_of_service"),
        "match_method": claim_row.get("match_method"),
        "status": "Open",
    }


def build_notifications_and_tickets(matched_claims_df):
    """Iterates matched, flagged claims and produces notification + ticket
    records. Unmatched claims are skipped here - they get surfaced
    separately in the UI as "needs manual review" instead.
    """
    notifications = []
    tickets = []

    for claim_row in matched_claims_df.to_dict("records"):
        if claim_row.get("match_method") == "unmatched":
            continue

        issues = determine_issues(claim_row)
        for issue_type in issues:
            ticket = draft_internal_ticket(claim_row, issue_type)
            tickets.append(ticket)

            message = draft_member_notification(claim_row, issue_type)
            if message:  # empty for dispute_risk by design
                notifications.append(
                    {
                        "claim_id": claim_row.get("claim_id"),
                        "member_id": claim_row.get("matched_member_id"),
                        "member_name": claim_row.get("member_name_on_file"),
                        "email": claim_row.get("email"),
                        "phone": claim_row.get("phone"),
                        "issue_type": ISSUE_LABELS[issue_type],
                        "message": message,
                    }
                )

    return notifications, tickets
