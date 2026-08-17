"""
Claim-to-member matching logic.

This is the core piece the whole prototype hinges on: claims data from the
carrier does NOT include a member email - only fields like member/policy
ID, patient name, and date of birth. To send anyone anything, or even to
know who a claim belongs to, we have to match it to OUR OWN member
database first, then pull the email from there.

Matching order (in priority):
    1. member_id, if present on the claim AND it exists in our member DB.
    2. Fallback: patient_name + date_of_birth (case/whitespace-insensitive
       name match, exact DOB match).
    3. If neither works: "Unmatched - needs manual review". We never guess.

A claim that matches on name+DOB is flagged as a "review_recommended"
match (rather than a rock-solid one) because names are not unique in real
populations. That distinction is preserved in the output so a real
implementation could route those matches through a lighter-touch human
sanity check before anything goes out to a member.
"""

import pandas as pd

UNMATCHED = "unmatched"
MATCH_BY_ID = "member_id"
MATCH_BY_NAME_DOB = "name_dob"


def _normalize_name(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


def build_lookup_indexes(members_df: pd.DataFrame):
    id_index = {row["member_id"]: row for row in members_df.to_dict("records")}

    name_dob_index = {}
    duplicate_keys = set()
    name_index = {}
    dob_index = {}
    for row in members_df.to_dict("records"):
        key = (_normalize_name(row["name"]), row["date_of_birth"])
        if key in name_dob_index:
            duplicate_keys.add(key)
        else:
            name_dob_index[key] = row
        name_index.setdefault(_normalize_name(row["name"]), []).append(row)
        dob_index.setdefault(row["date_of_birth"], []).append(row)

    return id_index, name_dob_index, duplicate_keys, name_index, dob_index


def diagnose_unmatched(claim: dict, name_index: dict, dob_index: dict) -> tuple:
    """Best-effort explanation of *why* a claim couldn't be matched, so a
    human reviewer knows what to check before manually resolving it and
    sending the member a notification. Checked independently of the actual
    matching logic - this never changes whether a claim matches, only what
    we tell a reviewer about a claim that already didn't.

    Returns (reason_code, reason_text).
    """
    member_id = str(claim.get("member_id") or "").strip()
    claim_name = claim.get("patient_name")
    name_key = _normalize_name(claim_name)
    dob = claim.get("date_of_birth")

    id_problem = (
        "No member/policy ID was present on the claim."
        if not member_id
        else f"Member/policy ID '{member_id}' was not found in the member database."
    )

    name_matches = name_index.get(name_key, [])
    dob_matches = dob_index.get(dob, [])

    if name_matches and not dob_matches:
        candidates = "; ".join(f"{m['member_id']} (DOB on file: {m['date_of_birth']})" for m in name_matches)
        return (
            "dob_mismatch",
            f"{id_problem} A member named '{claim_name}' exists, but the date of birth on the claim "
            f"({dob}) doesn't match what's on file - {candidates}. Possible DOB typo on the claim.",
        )
    if dob_matches and not name_matches:
        candidates = "; ".join(f"{m['member_id']} ({m['name']})" for m in dob_matches)
        return (
            "name_mismatch",
            f"{id_problem} A member with date of birth {dob} exists, but the name on the claim "
            f"('{claim_name}') doesn't match what's on file - {candidates}. Possible name typo or wrong record.",
        )
    if name_matches and dob_matches:
        return (
            "conflicting_partial_matches",
            f"{id_problem} Found a separate name match and a separate DOB match, but not on the same "
            "member record - likely two different people, or a data mix-up. Needs manual comparison.",
        )
    return (
        "no_match",
        f"{id_problem} No member in our database matches this name or date of birth either - this may "
        "be a new member, a data entry error on the claim, or claims data for the wrong member population.",
    )


def match_claim(claim: dict, id_index: dict, name_dob_index: dict, duplicate_keys: set):
    """Applies the ID -> name+DOB -> unmatched fallback to a single claim.

    Returns (matched_member_id, match_method, match_note)
    """
    claim_member_id = str(claim.get("member_id") or "").strip()

    # 1. Try member_id first.
    if claim_member_id and claim_member_id in id_index:
        return claim_member_id, MATCH_BY_ID, "Matched on member/policy ID."

    # 2. Fall back to patient name + date of birth.
    key = (_normalize_name(claim.get("patient_name")), claim.get("date_of_birth"))
    if key in name_dob_index:
        member = name_dob_index[key]
        note = "Matched on patient name + date of birth (member ID missing or invalid)."
        if key in duplicate_keys:
            note += " NOTE: multiple members share this name+DOB - recommend manual confirmation."
        return member["member_id"], MATCH_BY_NAME_DOB, note

    # 3. Neither worked - do not guess.
    return None, UNMATCHED, "No member/policy ID match and no name+DOB match. Needs manual review."


def match_claims(members_df: pd.DataFrame, claims_df: pd.DataFrame) -> pd.DataFrame:
    """Matches every claim to a member record and enriches it with the
    member's email/phone/plan_type pulled from OUR member database (never
    from the claim itself). Unmatched claims get a specific diagnostic
    reason instead of just "unmatched," so manual review has something to
    act on.
    """
    id_index, name_dob_index, duplicate_keys, name_index, dob_index = build_lookup_indexes(members_df)

    matched_ids, methods, notes, reason_codes = [], [], [], []
    for claim in claims_df.to_dict("records"):
        member_id, method, note = match_claim(claim, id_index, name_dob_index, duplicate_keys)
        reason_code = None
        if method == UNMATCHED:
            reason_code, note = diagnose_unmatched(claim, name_index, dob_index)
        matched_ids.append(member_id)
        methods.append(method)
        notes.append(note)
        reason_codes.append(reason_code)

    result = claims_df.copy()
    result["matched_member_id"] = matched_ids
    result["match_method"] = methods
    result["match_note"] = notes
    result["unmatched_reason_code"] = reason_codes

    members_lookup = members_df.set_index("member_id")[["name", "email", "phone", "plan_type"]].rename(
        columns={"name": "member_name_on_file"}
    )
    result = result.merge(
        members_lookup, how="left", left_on="matched_member_id", right_index=True
    )

    return result
