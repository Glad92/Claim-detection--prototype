"""
Mock data generation for the Member Services Proactive Outreach prototype.

IMPORTANT: All data produced here is synthetic / randomly generated. Nothing
in this module reads from, writes to, or connects to any real carrier
system, insurance portal, or member database. It exists purely to give the
rest of the prototype something realistic-looking to operate on.

Two tables are produced, mirroring the real-world data separation this
system is designed around:

1. Member database (`members_df`) - stands in for OUR OWN internal member
   records. This is the only place an email address or phone number lives.
2. Incoming claims (`claims_df`) - stands in for a raw claims feed from the
   carrier. Carrier data never includes a member email, and identifiers are
   frequently missing or wrong - that messiness is intentionally simulated
   below so the matching logic in matching.py has something real to do.
"""

import random
import string
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker()

PLAN_TYPES = ["PPO Gold", "PPO Silver", "HMO Standard", "HDHP Bronze", "EPO Plus"]

SERVICE_TYPES = {
    # service_type: "typical"/expected billed amount for that service
    "Office Visit": 150,
    "Specialist Consult": 275,
    "Lab Work": 120,
    "X-Ray": 220,
    "Physical Therapy": 140,
    "MRI": 1400,
    "Emergency Room Visit": 1800,
    "Outpatient Surgery": 4200,
}

CARRIER_STATUSES = [
    ("processed_normally", 0.55),
    ("out_of_network", 0.15),
    ("cob_needed", 0.12),
    ("wrong_carrier", 0.10),
    ("processed_normally", 0.08),  # extra weight toward normal claims
]


def _weighted_choice(pairs):
    values, weights = zip(*pairs)
    return random.choices(values, weights=weights, k=1)[0]


def _random_dob(min_age=18, max_age=85):
    today = date.today()
    age_days = random.randint(min_age * 365, max_age * 365)
    return today - timedelta(days=age_days)


def _garbled_id(length=8):
    """Produces an ID-shaped string that (almost certainly) matches nobody."""
    return "MBR-" + "".join(random.choices(string.digits, k=length))


def _random_phone():
    return f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"


def generate_members(n_members: int, seed: int) -> pd.DataFrame:
    """Generates the internal member database table.

    Columns: member_id, name, date_of_birth, email, phone, plan_type

    Not every member has both contact channels on file - that's realistic,
    and it's what makes the "email, phone, or both" send logic meaningful:
    ~92% have an email on file, ~55% have a phone on file, independently,
    so the mix naturally includes email-only, phone-only, both, and (rarely)
    neither.
    """
    random.seed(seed)
    Faker.seed(seed)

    records = []
    for i in range(n_members):
        member_id = f"MBR-{10000 + i}"
        name = fake.name()
        dob = _random_dob()

        has_email = random.random() < 0.92
        has_phone = random.random() < 0.55
        if not has_email and not has_phone:
            # Don't let "no contact info at all" dominate the demo - force one.
            if random.random() < 0.5:
                has_email = True
            else:
                has_phone = True

        # Email/phone live ONLY here - the claims feed never carries them.
        email = fake.free_email() if has_email else ""
        phone = _random_phone() if has_phone else ""
        plan_type = random.choice(PLAN_TYPES)
        records.append(
            {
                "member_id": member_id,
                "name": name,
                "date_of_birth": dob.isoformat(),
                "email": email,
                "phone": phone,
                "plan_type": plan_type,
            }
        )
    return pd.DataFrame(records)


def generate_claims(members_df: pd.DataFrame, n_claims: int, seed: int, n_days: int = 90) -> pd.DataFrame:
    """Generates an incoming claims feed with realistic messiness.

    Columns: claim_id, member_id, patient_name, date_of_birth, provider,
    service_type, amount, expected_amount, date_of_service, carrier_status

    Messiness modeled:
    - ~28% of claims have a missing or incorrect member_id (carrier feeds
      routinely drop or mis-key this field).
    - ~8% of claims additionally have a slightly corrupted patient name or
      date of birth, so they cannot be recovered even by the name+DOB
      fallback - these should end up "Unmatched - needs manual review".
    - A subset of claims are billed well above the typical/expected cost
      for that service, which is what the dispute-risk heuristic looks for.

    date_of_service is spread across the most recent `n_days` days (today
    included), so the batch lines up with whatever "days simulated" window
    the caller asked for - that's what makes a daily-volume trend chart
    meaningful rather than arbitrary.
    """
    random.seed(seed + 1)
    Faker.seed(seed + 1)

    providers = [fake.company() + " " + random.choice(["Clinic", "Medical Group", "Hospital", "Health Center"]) for _ in range(25)]

    member_records = members_df.to_dict("records")

    records = []
    for i in range(n_claims):
        claim_id = f"CLM-{50000 + i}"
        true_member = random.choice(member_records)

        patient_name = true_member["name"]
        dob = true_member["date_of_birth"]

        # ~8% of claims: corrupt identity fields so nothing can match them.
        truly_unmatchable = random.random() < 0.08
        if truly_unmatchable:
            patient_name = fake.name()  # unrelated name
            dob = _random_dob().isoformat()  # unrelated DOB

        # member_id messiness (independent of the identity corruption above)
        r = random.random()
        if truly_unmatchable:
            member_id = "" if random.random() < 0.5 else _garbled_id()
        elif r < 0.72:
            member_id = true_member["member_id"]  # correct
        elif r < 0.86:
            member_id = ""  # blank / dropped
        else:
            member_id = _garbled_id()  # present but wrong

        service_type = random.choice(list(SERVICE_TYPES.keys()))
        expected_amount = SERVICE_TYPES[service_type]

        # Amount: normally close to expected, sometimes a dispute-risk spike.
        if random.random() < 0.18:
            amount = round(expected_amount * random.uniform(1.6, 3.2), 2)
        else:
            amount = round(expected_amount * random.uniform(0.85, 1.25), 2)

        carrier_status = _weighted_choice(CARRIER_STATUSES)

        date_of_service = (date.today() - timedelta(days=random.randint(0, max(n_days - 1, 0)))).isoformat()

        records.append(
            {
                "claim_id": claim_id,
                "member_id": member_id,
                "patient_name": patient_name,
                "date_of_birth": dob,
                "provider": random.choice(providers),
                "service_type": service_type,
                "amount": amount,
                "expected_amount": expected_amount,
                "date_of_service": date_of_service,
                "carrier_status": carrier_status,
            }
        )
    return pd.DataFrame(records)


def generate_mock_data(n_members: int = 50, n_claims: int = 90, seed: int = 42, n_days: int = 90):
    members_df = generate_members(n_members, seed)
    claims_df = generate_claims(members_df, n_claims, seed, n_days=n_days)
    return members_df, claims_df


def generate_single_claim(members_df: pd.DataFrame, carrier_status=None, id_quality=None, force_dispute_risk=None) -> dict:
    """Generates one on-demand claim for the "Live Claim Walkthrough" demo.

    Deliberately does NOT reseed random/Faker - it draws from whatever state
    the process is currently in, so repeated calls (e.g. clicking "run
    walkthrough" again) produce a genuinely different claim each time,
    which is the point of a live/interactive demo.

    carrier_status: force one of "out_of_network", "cob_needed",
        "wrong_carrier", "processed_normally", or None for random.
    id_quality: force one of "correct", "blank", "wrong", "unmatchable",
        or None for random.
    force_dispute_risk: True to force a dispute-risk amount spike, False to
        force a typical amount, or None for the normal random chance.
    """
    true_member = random.choice(members_df.to_dict("records"))
    patient_name = true_member["name"]
    dob = true_member["date_of_birth"]

    if id_quality is None:
        id_quality = random.choices(
            ["correct", "blank", "wrong", "unmatchable"], weights=[0.5, 0.2, 0.2, 0.1]
        )[0]

    if id_quality == "unmatchable":
        patient_name = fake.name()
        dob = _random_dob().isoformat()
        member_id = "" if random.random() < 0.5 else _garbled_id()
    elif id_quality == "correct":
        member_id = true_member["member_id"]
    elif id_quality == "blank":
        member_id = ""
    else:  # "wrong"
        member_id = _garbled_id()

    service_type = random.choice(list(SERVICE_TYPES.keys()))
    expected_amount = SERVICE_TYPES[service_type]

    if force_dispute_risk is True:
        amount = round(expected_amount * random.uniform(1.6, 3.2), 2)
    elif force_dispute_risk is False:
        amount = round(expected_amount * random.uniform(0.85, 1.25), 2)
    elif random.random() < 0.18:
        amount = round(expected_amount * random.uniform(1.6, 3.2), 2)
    else:
        amount = round(expected_amount * random.uniform(0.85, 1.25), 2)

    if carrier_status is None:
        carrier_status = _weighted_choice(CARRIER_STATUSES)

    provider = fake.company() + " " + random.choice(["Clinic", "Medical Group", "Hospital", "Health Center"])
    claim_id = "CLM-DEMO-" + "".join(random.choices(string.digits, k=5))
    date_of_service = (date.today() - timedelta(days=random.randint(1, 90))).isoformat()

    return {
        "claim_id": claim_id,
        "member_id": member_id,
        "patient_name": patient_name,
        "date_of_birth": dob,
        "provider": provider,
        "service_type": service_type,
        "amount": amount,
        "expected_amount": expected_amount,
        "date_of_service": date_of_service,
        "carrier_status": carrier_status,
    }
