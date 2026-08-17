"""
Member Services Proactive Outreach - PROTOTYPE / PROOF OF CONCEPT

WHAT THIS IS:
A Streamlit demo built entirely on synthetic, randomly generated data. It
exists to support an internal pitch for real bulk claims-data access - it
is NOT a deployed system and is NOT connected to any real carrier portal,
insurance system, or actual member data.

WHAT IT AUTOMATES (in this prototype): detection of four issue categories,
matching claims to member records, categorization, and drafting of member
notifications + internal tickets.

WHAT IT DOES NOT DO: actually send anything, or actually contact a
provider/carrier. The "Send" buttons in the UI are SIMULATED ONLY - no real
email provider or SMS gateway is ever called; they exist to demonstrate what
a delivery/result report would look like. In a real version, sending member
messages and confirming external actions (like a provider's resubmission)
would still involve a human in the loop. Every "notification" below is a
DRAFT until (simulated-)sent.

Visual layout/styling lives in theme.py, kept separate from this file's
data flow so the two can change independently.

See README.md for the full design rationale and matching logic.
"""

import time

import altair as alt
import pandas as pd
import streamlit as st

import theme
from data_generation import generate_mock_data, generate_single_claim
from matching import match_claims, UNMATCHED
from notifications import (
    build_notifications_and_tickets,
    determine_issues,
    draft_internal_ticket,
    draft_member_notification,
    ISSUE_LABELS,
    DISPUTE_RISK,
    OUT_OF_NETWORK,
    COB_NEEDED,
    WRONG_CARRIER,
)
from sending import simulate_send

st.set_page_config(page_title="Member Services Proactive Outreach (Prototype)", layout="wide", page_icon="🩺")
st.markdown(theme.CSS, unsafe_allow_html=True)

PREVIEW_LIMIT = 50  # card-based views render at most this many rows; full data stays available via CSV/table

MATCH_METHOD_STYLE = {
    "member_id": "background-color:#0ca30c;color:#ffffff;font-weight:600;",
    "name_dob": "background-color:#fab219;color:#2b1d00;font-weight:600;",
    "unmatched": "background-color:#d03b3b;color:#ffffff;font-weight:600;",
}

UNMATCHED_REASON_LABELS = {
    "dob_mismatch": "🗓️ DOB mismatch (name found)",
    "name_mismatch": "📛 Name mismatch (DOB found)",
    "conflicting_partial_matches": "⚠️ Conflicting partial matches",
    "no_match": "❓ No match on name or DOB",
}

st.session_state.setdefault("send_results", {})
st.session_state.setdefault("last_bulk_send_log", None)

# --------------------------------------------------------------------------
# Sidebar controls
# --------------------------------------------------------------------------
st.sidebar.header("🎛️ Prototype controls")
st.sidebar.caption("All data below is synthetic and randomly generated on demand.")

n_members = st.sidebar.slider("Number of mock members", 20, 150, 50, step=10)

st.sidebar.divider()
st.sidebar.markdown("**📆 Claims volume assumption**")

daily_volume = st.sidebar.number_input(
    "Estimated claims processed per day (assumption — confirm with claims team)",
    min_value=100,
    max_value=5000,
    value=1000,
    step=100,
)
st.sidebar.caption(
    "This is an illustrative assumption for demo purposes only, not a verified figure. "
    "Our member base is 50,000+, but actual daily claim volume isn't confirmed yet - "
    "check this number with the claims team before using it for real planning."
)

days_to_simulate = st.sidebar.number_input("Number of days to simulate", min_value=1, max_value=30, value=10, step=1)

n_claims = int(daily_volume) * int(days_to_simulate)
st.sidebar.markdown(f"**→ Total simulated batch: {n_claims:,} claims** over {days_to_simulate} day(s)")

seed = st.sidebar.number_input("Random seed", value=42, step=1)
regenerate = st.sidebar.button("🔄 Regenerate mock data", width="stretch")

if "seed_bump" not in st.session_state:
    st.session_state.seed_bump = 0
if regenerate:
    st.session_state.seed_bump += 1

effective_seed = int(seed) + st.session_state.seed_bump

st.sidebar.divider()
st.sidebar.markdown(
    "**Dispute-risk rule** *(adjustable in `notifications.py`)*\n\n"
    "Billed amount is flagged as a possible dispute risk when it is **≥1.5x** "
    "the typical/expected cost for that service **and** at least **$150** "
    "above it."
)

# --------------------------------------------------------------------------
# Data generation (cached so slider tweaks elsewhere don't regenerate data)
# --------------------------------------------------------------------------
@st.cache_data
def load_data(n_members, n_claims, seed, n_days):
    members_df, claims_df = generate_mock_data(n_members=n_members, n_claims=n_claims, seed=seed, n_days=n_days)
    return members_df, claims_df


members_df, claims_df = load_data(n_members, n_claims, effective_seed, days_to_simulate)
matched_df = match_claims(members_df, claims_df)
notifications, tickets = build_notifications_and_tickets(matched_df)

tickets_df = pd.DataFrame(tickets)
notifications_df = pd.DataFrame(notifications)

# --------------------------------------------------------------------------
# Hero + prototype disclaimer
# --------------------------------------------------------------------------
st.markdown(
    theme.hero(
        "Member Services: Proactive Claim Issue Detection",
        "Catch out-of-network bills, COB gaps, and misrouted claims before the member "
        "ever sees a surprise bill - not after they call in confused about one.",
    ),
    unsafe_allow_html=True,
)
st.markdown(
    theme.proto_banner(
        "<b>Prototype / proof-of-concept only.</b> Built on 100% synthetic, made-up data. "
        "Not connected to any real carrier system, insurance portal, or actual member data. "
        "This demo automates detection, matching, categorization, and message <i>drafting</i> only - "
        "a real version would still route sending and provider confirmation through a person."
    ),
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Summary metrics
# --------------------------------------------------------------------------
total_claims = len(matched_df)
unmatched_count = int((matched_df["match_method"] == UNMATCHED).sum())
matched_count = total_claims - unmatched_count

# A claim can carry more than one issue at once - a primary category (out-of-
# network / COB / wrong carrier) AND a dispute-risk flag, since dispute risk
# is a separate amount-based check layered on top of whatever the carrier
# status already says. So "unique claims flagged" and "total issue instances"
# are genuinely different numbers, not a data bug - we show both below so the
# math is traceable instead of implying the categories are mutually exclusive.
flagged_claim_ids = tickets_df["claim_id"].nunique() if not tickets_df.empty else 0
total_issue_instances = len(tickets_df)
dispute_risk_count = int((tickets_df["issue_type"] == ISSUE_LABELS[DISPUTE_RISK]).sum()) if not tickets_df.empty else 0
notifications_count = len(notifications_df)  # one per notification-eligible issue instance (non-dispute-risk)
multi_issue_claim_count = (
    int((tickets_df.groupby("claim_id").size() > 1).sum()) if not tickets_df.empty else 0
)

st.markdown(theme.section_header("📊", "Summary"), unsafe_allow_html=True)
st.markdown(
    theme.tiles_row(
        [
            theme.tile(total_claims, "Total incoming claims", "📥", "ms-blue"),
            theme.tile(matched_count, "Matched to a member", "🔗", "ms-green"),
            theme.tile(unmatched_count, "Unmatched — needs manual review", "🚩", "ms-red"),
            theme.tile(flagged_claim_ids, "Unique claims flagged", "🏷️", "ms-orange"),
            theme.tile(total_issue_instances, "Total issue instances", "🧩", "ms-yellow"),
            theme.tile(notifications_count, "Member notifications drafted", "✉️", "ms-aqua"),
        ]
    ),
    unsafe_allow_html=True,
)
st.caption(
    f"**{notifications_count:,}** notification-eligible issue instances + **{dispute_risk_count:,}** "
    f"internal-only dispute-risk instances = **{total_issue_instances:,}** total issue instances, "
    f"spread across **{flagged_claim_ids:,}** unique flagged claims."
)
if multi_issue_claim_count:
    st.caption(
        f"**{multi_issue_claim_count:,}** of those claims carry more than one issue type at once "
        "(e.g. an out-of-network bill that's *also* priced well above the typical rate) - which is why "
        "total issue instances is higher than unique flagged claims. No member notification is "
        "auto-drafted for dispute-risk flags; see README."
    )

# --------------------------------------------------------------------------
# Breakdown by issue type - fixed color per category, never re-sorted
# --------------------------------------------------------------------------
st.markdown(theme.section_header("📈", "Breakdown by issue type"), unsafe_allow_html=True)

if not tickets_df.empty:
    st.caption(
        f"Counts below are issue **instances**, not unique claims - they sum to {total_issue_instances:,} "
        f"(matching the \"Total issue instances\" tile above), not {flagged_claim_ids:,}, because a claim "
        "can carry more than one issue type."
    )
    counts_by_label = tickets_df["issue_type"].value_counts().to_dict()
    breakdown = pd.DataFrame(
        {"Issue type": theme.ISSUE_ORDER, "Count": [counts_by_label.get(label, 0) for label in theme.ISSUE_ORDER]}
    )

    st.markdown(
        '<div class="ms-chip-row">'
        + "".join(f"{theme.issue_badge(label)} <span style='margin-right:1rem'>{counts_by_label.get(label, 0)}</span>" for label in theme.ISSUE_ORDER)
        + "</div>",
        unsafe_allow_html=True,
    )

    chart = (
        alt.Chart(breakdown)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=48)
        .encode(
            x=alt.X("Issue type:N", sort=theme.ISSUE_ORDER, axis=alt.Axis(labelAngle=0, title=None, labels=False)),
            y=alt.Y("Count:Q", title=None),
            color=alt.Color(
                "Issue type:N",
                scale=alt.Scale(domain=theme.ISSUE_ORDER, range=theme.ordered_issue_colors(theme.ISSUE_ORDER)),
                legend=None,
            ),
            tooltip=["Issue type", "Count"],
        )
        .properties(height=240)
    )
    st.altair_chart(chart, width="stretch")
else:
    st.info("No issues flagged in this run - try regenerating data or increasing claim count.")

# --------------------------------------------------------------------------
# Daily claims volume trend - ties directly to the days-simulated assumption
# --------------------------------------------------------------------------
st.markdown(
    theme.section_header(
        "📆",
        "Daily claims volume trend",
        f"Simulated at ~{daily_volume:,} claims/day over {days_to_simulate} day(s) — see the assumption note in the sidebar",
    ),
    unsafe_allow_html=True,
)

trend_c1, trend_c2 = st.columns(2)
with trend_c1:
    daily_totals = (
        matched_df.assign(date=pd.to_datetime(matched_df["date_of_service"]))
        .groupby("date")
        .size()
        .reset_index(name="Claims received")
    )
    total_trend = (
        alt.Chart(daily_totals)
        .mark_line(point=True, strokeWidth=2, color=theme.ISSUE_HEX["blue"])
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("Claims received:Q", title=None),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("Claims received:Q")],
        )
        .properties(height=240, title="Total claims received per day")
    )
    st.altair_chart(total_trend, width="stretch")
with trend_c2:
    if not tickets_df.empty:
        daily_issues = (
            tickets_df.assign(date=pd.to_datetime(tickets_df["date_of_service"]))
            .groupby(["date", "issue_type"])
            .size()
            .reset_index(name="Count")
        )
        stacked_trend = (
            alt.Chart(daily_issues)
            .mark_bar()
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("Count:Q", title=None, stack="zero"),
                color=alt.Color(
                    "issue_type:N",
                    scale=alt.Scale(domain=theme.ISSUE_ORDER, range=theme.ordered_issue_colors(theme.ISSUE_ORDER)),
                    legend=alt.Legend(title=None, orient="bottom", columns=2),
                ),
                order=alt.Order("issue_type:N", sort="ascending"),
                tooltip=[alt.Tooltip("date:T", title="Date"), "issue_type:N", "Count:Q"],
            )
            .properties(height=240, title="Flagged issues per day, by category")
        )
        st.altair_chart(stacked_trend, width="stretch")
    else:
        st.info("No flagged issues to trend in this run.")

# --------------------------------------------------------------------------
# Tabs: live demo / notifications / tickets / before-after / raw data
# --------------------------------------------------------------------------
tab_live, tab_notify, tab_tickets, tab_before_after, tab_data = st.tabs(
    ["🎬 Live Claim Walkthrough", "📨 Member Notifications", "🗂️ Internal Action Tickets", "⏱️ Before vs. After", "🔍 Matching Detail"]
)

with tab_live:
    st.markdown(
        "Simulates **one claim arriving and being processed end to end**, one step at a time: "
        "intake → matching → issue check (including an explicit **COB check**) → draft output. "
        "Each run uses a fresh random claim - nothing here is pulled from the batch tables above."
    )

    issue_options = {
        "Coordination of Benefits (COB) update needed": COB_NEEDED,
        "Out-of-network provider": OUT_OF_NETWORK,
        "Claim sent to wrong carrier": WRONG_CARRIER,
        "No issue (processed normally)": "processed_normally",
        "Random": None,
    }
    id_quality_options = {
        "Random": None,
        "Correct member ID present (matches instantly)": "correct",
        "Member ID missing (falls back to name + DOB)": "blank",
        "Member ID present but wrong (falls back to name + DOB)": "wrong",
        "Unmatchable (bad ID AND name/DOB - needs manual review)": "unmatchable",
    }
    dispute_options = {
        "Random chance (~18%)": None,
        "Force a dispute-risk spike (billed well above typical)": True,
        "Force a typical amount": False,
    }

    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        issue_choice = st.selectbox("Simulate this claim as:", options=list(issue_options.keys()), index=0)
    with lc2:
        id_quality_choice = st.selectbox("Member ID quality on this claim:", options=list(id_quality_options.keys()), index=0)
    with lc3:
        dispute_choice = st.selectbox("Dispute-risk amount:", options=list(dispute_options.keys()), index=0)

    run_demo = st.button("▶️ Run live walkthrough", type="primary", width="stretch")

    if run_demo:
        demo_claim = generate_single_claim(
            members_df,
            carrier_status=issue_options[issue_choice],
            id_quality=id_quality_options[id_quality_choice],
            force_dispute_risk=dispute_options[dispute_choice],
        )
        demo_matched = match_claims(members_df, pd.DataFrame([demo_claim])).iloc[0].to_dict()

        with st.status(f"Processing incoming claim {demo_claim['claim_id']}...", expanded=True) as status:
            st.write("**Step 1 — Claim received from carrier feed**")
            st.json(
                {
                    "claim_id": demo_claim["claim_id"],
                    "member_id": demo_claim["member_id"] or "(blank)",
                    "patient_name": demo_claim["patient_name"],
                    "date_of_birth": demo_claim["date_of_birth"],
                    "provider": demo_claim["provider"],
                    "service_type": demo_claim["service_type"],
                    "amount": demo_claim["amount"],
                }
            )
            time.sleep(0.8)

            st.write("**Step 2 — Matching to a member record**")
            if demo_matched["match_method"] == "member_id":
                st.success(f"Matched instantly on member/policy ID `{demo_claim['member_id']}`.")
            elif demo_matched["match_method"] == "name_dob":
                id_desc = "missing" if not demo_claim["member_id"] else f"not recognized (`{demo_claim['member_id']}`)"
                st.warning(f"Member/policy ID was {id_desc} — falling back to name + date of birth...")
                time.sleep(0.7)
                st.success(f"Matched on name + DOB to **{demo_matched['member_name_on_file']}**.")
            else:
                st.warning("No member/policy ID match, and no name + DOB match either.")
                time.sleep(0.7)
                st.error("🚩 Routed to **Unmatched — needs manual review**. No auto-draft without a confirmed identity.")
            time.sleep(0.6)

            if demo_matched["match_method"] != UNMATCHED:
                st.write(
                    f"Member on file: **{demo_matched['member_name_on_file']}** · "
                    f"{demo_matched['plan_type']} · {demo_matched['email']}"
                )
                time.sleep(0.5)

                st.write("**Step 3 — Checking for known issue patterns**")
                issues = determine_issues(demo_matched)
                cob_needed = COB_NEEDED in issues
                st.markdown(
                    f"- {'✅' if OUT_OF_NETWORK in issues else '➖'} Out-of-network provider\n"
                    f"- {'✅' if cob_needed else '➖'} **Coordination of Benefits (COB) update needed?** "
                    f"{'**→ YES**' if cob_needed else '→ No'}\n"
                    f"- {'✅' if WRONG_CARRIER in issues else '➖'} Claim sent to wrong carrier\n"
                    f"- {'✅' if DISPUTE_RISK in issues else '➖'} Possible dispute risk (predicted)"
                )
                time.sleep(0.8)

                if issues:
                    st.write("**Step 4 — Drafting outreach**")
                    time.sleep(0.5)
                    for issue in issues:
                        ticket = draft_internal_ticket(demo_matched, issue)
                        st.markdown(
                            f"{theme.issue_badge(ISSUE_LABELS[issue])} {theme.priority_badge(ticket['priority'])}",
                            unsafe_allow_html=True,
                        )
                        st.caption(ticket["next_step"])
                        message = draft_member_notification(demo_matched, issue)
                        if message:
                            contact = theme.contact_summary(demo_matched.get("email"), demo_matched.get("phone"))
                            st.markdown(f"**Member notification drafted → {contact}**")
                            st.markdown(theme.letter(message, ISSUE_LABELS[issue]), unsafe_allow_html=True)
                            time.sleep(0.5)
                            st.write("**Step 5 — Sending (simulated)**")
                            send_result = simulate_send(demo_matched.get("email"), demo_matched.get("phone"))
                            time.sleep(0.6)
                            st.markdown(theme.send_status_badge(send_result["overall_status"]), unsafe_allow_html=True)
                            for ch in send_result["channels"]:
                                icon = "✅" if ch["status"] == "sent" else "❌"
                                st.caption(f"{icon} {ch['channel']} → {ch['address']}: {ch['detail']}")
                            if send_result["overall_status"] == "no_contact_info":
                                st.caption("No email or phone on file for this member - cannot send.")
                        else:
                            st.caption(
                                "No member-facing message drafted for this one — internal review only "
                                "(dispute risk is a prediction, not a confirmed issue)."
                            )
                else:
                    st.success("No issues detected — claim processed normally. Nothing to draft.")

            status.update(label=f"Walkthrough complete — {demo_claim['claim_id']}", state="complete")
    else:
        st.info("Choose your scenario above (COB is pre-selected) and click **Run live walkthrough**.")

with tab_notify:
    st.markdown(
        "Drafts only, written in a warm member-advocate voice - never sounding like the carrier. "
        "**Dispute-risk flags never appear here** since nothing has actually gone wrong yet; "
        "they go to the internal ticket list instead."
    )
    st.caption(
        "🧪 **Sending is simulated.** No real email or SMS is ever sent - clicking Send randomly assigns a "
        "realistic delivery result so you can see what a real \"was it delivered\" report would look like. "
        "Members are notified on whichever channel(s) they have on file - email, phone, or both."
    )
    if notifications_df.empty:
        st.info("No member notifications to draft in this run.")
    else:
        issue_filter = st.multiselect(
            "Filter by issue type",
            options=sorted(notifications_df["issue_type"].unique()),
            default=sorted(notifications_df["issue_type"].unique()),
        )
        filtered = notifications_df[notifications_df["issue_type"].isin(issue_filter)]

        dl_col, send_col = st.columns(2)
        with dl_col:
            st.download_button(
                "⬇️ Download all matching notifications as CSV",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name="member_notifications.csv",
                mime="text/csv",
                width="stretch",
            )
        with send_col:
            send_all_clicked = st.button(
                f"📤 Send all {len(filtered):,} matching notifications (simulated)", type="primary", width="stretch"
            )

        if send_all_clicked:
            results_log = []
            progress = st.progress(0.0, text="Sending (simulated)...")
            n = len(filtered)
            for i, (_, row) in enumerate(filtered.iterrows()):
                result = simulate_send(row["email"], row["phone"])
                st.session_state.send_results[row["claim_id"]] = result
                channel_status = {c["channel"]: c["status"] for c in result["channels"]}
                results_log.append(
                    {
                        "claim_id": row["claim_id"],
                        "member_name": row["member_name"],
                        "issue_type": row["issue_type"],
                        "email": row["email"] or "",
                        "phone": row["phone"] or "",
                        "overall_status": result["overall_status"],
                        "email_status": channel_status.get("email", ""),
                        "phone_status": channel_status.get("phone (SMS)", ""),
                    }
                )
                if n <= 200 or i % max(n // 100, 1) == 0:
                    progress.progress(min((i + 1) / n, 1.0), text=f"Sending (simulated)... {i + 1:,}/{n:,}")
            progress.empty()
            st.session_state.last_bulk_send_log = pd.DataFrame(results_log)

        send_log = st.session_state.last_bulk_send_log
        if send_log is not None:
            status_counts = send_log["overall_status"].value_counts()
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("✅ Sent", int(status_counts.get("sent", 0)))
            r2.metric("⚠️ Partially sent", int(status_counts.get("partial", 0)))
            r3.metric("❌ Failed", int(status_counts.get("failed", 0)))
            r4.metric("🚫 No contact info", int(status_counts.get("no_contact_info", 0)))
            st.download_button(
                "⬇️ Download send results as CSV",
                data=send_log.to_csv(index=False).encode("utf-8"),
                file_name="notification_send_results.csv",
                mime="text/csv",
            )

        if len(filtered) > PREVIEW_LIMIT:
            st.caption(f"Showing the first {PREVIEW_LIMIT} of {len(filtered):,} matching drafts on screen — the rest are in the CSV above.")

        for _, row in filtered.head(PREVIEW_LIMIT).iterrows():
            claim_id = row["claim_id"]
            label = f"{claim_id} — {row['member_name']}  →  {theme.contact_summary(row['email'], row['phone'])}"
            with st.expander(label):
                st.markdown(theme.issue_badge(row["issue_type"]), unsafe_allow_html=True)
                st.markdown(theme.letter(row["message"], row["issue_type"]), unsafe_allow_html=True)

                send_this_col, result_col = st.columns([1, 2])
                with send_this_col:
                    if st.button("📤 Send (simulated)", key=f"send_{claim_id}"):
                        st.session_state.send_results[claim_id] = simulate_send(row["email"], row["phone"])
                result = st.session_state.send_results.get(claim_id)
                with result_col:
                    if result:
                        st.markdown(theme.send_status_badge(result["overall_status"]), unsafe_allow_html=True)
                        for ch in result["channels"]:
                            icon = "✅" if ch["status"] == "sent" else "❌"
                            st.caption(f"{icon} {ch['channel']} → {ch['address']}: {ch['detail']}")
                        if result["overall_status"] == "no_contact_info":
                            st.caption("No email or phone on file for this member - cannot send.")

with tab_tickets:
    st.markdown("Every flagged issue - including probabilistic dispute-risk flags - becomes an internal ticket with a next step already identified.")
    if tickets_df.empty:
        st.info("No internal tickets generated in this run.")
    else:
        priority_filter = st.multiselect(
            "Filter by priority", options=sorted(tickets_df["priority"].unique()), default=sorted(tickets_df["priority"].unique())
        )
        display_df = tickets_df[tickets_df["priority"].isin(priority_filter)]

        st.download_button(
            "⬇️ Download tickets as CSV",
            data=display_df.to_csv(index=False).encode("utf-8"),
            file_name="internal_action_tickets.csv",
            mime="text/csv",
        )
        if len(display_df) > PREVIEW_LIMIT:
            st.caption(f"Showing the first {PREVIEW_LIMIT} of {len(display_df):,} matching tickets on screen — the rest are in the CSV above or the table below.")

        for _, row in display_df.head(PREVIEW_LIMIT).iterrows():
            st.markdown(
                theme.ticket_card(row["claim_id"], row["member_name"], row["issue_type"], row["priority"], row["next_step"]),
                unsafe_allow_html=True,
            )

        with st.expander("📋 View as data table"):
            st.dataframe(display_df, hide_index=True, width="stretch")

with tab_before_after:
    st.markdown("Grounded in this run's own synthetic numbers - not industry estimates.")
    steps = [
        (
            "Issue detection",
            "Discovered when the member calls in, already confused about a bill.",
            f"{flagged_claim_ids} claim(s) auto-flagged the moment claims data is ingested.",
        ),
        (
            "Claim lookup",
            "Rep manually looks up each claim one at a time in the carrier's portal.",
            f"All {total_claims} claims matched & categorized in one pass.",
        ),
        (
            "Member identification",
            "Identity confirmed live, on the phone, while the member is already stressed.",
            f"{matched_count} claims matched automatically; {unmatched_count} clearly routed to manual review instead of guessed.",
        ),
        (
            "COB gaps",
            "Found only when the member calls about a stuck claim.",
            "Flagged immediately; team can reach out before it becomes a bill.",
        ),
        (
            "Wrong-carrier claims",
            "Found reactively during a member call.",
            "Flagged with the provider-contact next step already queued.",
        ),
        (
            "Dispute risk",
            "Not identified until the member actually disputes the charge.",
            f"{dispute_risk_count} claim(s) flagged probabilistically for internal review before billing - not sent to the member as fact.",
        ),
        (
            "Team workflow",
            "Manual, one claim at a time, no pre-filled next step.",
            "Ticket queue with next step pre-filled and exportable as CSV.",
        ),
    ]
    for step, today_text, after_text in steps:
        st.markdown(theme.versus_row(step, today_text, after_text), unsafe_allow_html=True)

with tab_data:
    st.markdown("Raw synthetic tables and full matching output, shown for transparency into how the matching logic worked on this run.")

    st.markdown(theme.section_header("🧭", "Matching method breakdown"), unsafe_allow_html=True)
    method_counts = matched_df["match_method"].value_counts().reset_index()
    method_counts.columns = ["Match method", "Count"]
    st.dataframe(
        method_counts.style.map(lambda v: MATCH_METHOD_STYLE.get(v, ""), subset=["Match method"]),
        hide_index=True,
        width="stretch",
    )

    st.markdown(theme.section_header("🚩", "Unmatched claims (needs manual review)"), unsafe_allow_html=True)
    unmatched_full = matched_df[matched_df["match_method"] == UNMATCHED].copy()
    if unmatched_full.empty:
        st.info("No unmatched claims in this run.")
    else:
        st.caption(
            "Each unmatched claim gets a specific diagnosis - not just \"unmatched\" - so a reviewer knows "
            "what to check (a typo'd DOB vs. a genuinely new member vs. a data mix-up) before manually "
            "resolving it. It also shows the **claim's issue type** (COB, out-of-network, wrong carrier, "
            "dispute risk) up front - that's a fact about the claim itself, from the carrier, so we already "
            "know it even before we know who the member is."
        )
        reason_counts = unmatched_full["unmatched_reason_code"].value_counts()
        st.markdown(
            '<div class="ms-chip-row">'
            + "".join(
                f"<span class='ms-badge ms-badge--yellow'>{UNMATCHED_REASON_LABELS.get(code, code)}: {count}</span>"
                for code, count in reason_counts.items()
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        # Issue type is a fact about the claim (carrier_status + billed amount vs.
        # expected) - it doesn't require a resolved member identity, so we can
        # show it for unmatched claims too, not just matched ones.
        unmatched_issue_lists = unmatched_full.apply(lambda r: determine_issues(r), axis=1)
        unmatched_full["likely_issue_type"] = unmatched_issue_lists.apply(
            lambda lst: ", ".join(ISSUE_LABELS[i] for i in lst) if lst else "No issue pattern detected"
        )
        issue_label_counts = pd.Series([ISSUE_LABELS[i] for lst in unmatched_issue_lists for i in lst]).value_counts()
        no_issue_count = int((unmatched_issue_lists.apply(len) == 0).sum())

        st.markdown("**What kind of issue are these unmatched claims?**")
        st.markdown(
            '<div class="ms-chip-row">'
            + "".join(f"{theme.issue_badge(label)} <span style='margin-right:1rem'>{count}</span>" for label, count in issue_label_counts.items())
            + (
                f"<span class='ms-badge' style='background:var(--ms-muted);color:#fff'>No issue pattern detected: {no_issue_count}</span>"
                if no_issue_count
                else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        unmatched_view = unmatched_full[
            ["claim_id", "member_id", "patient_name", "date_of_birth", "provider", "service_type", "amount", "likely_issue_type", "match_note"]
        ].rename(columns={"likely_issue_type": "Issue type (from claims data)", "match_note": "Why it didn't match a member"})
        st.dataframe(unmatched_view, hide_index=True, width="stretch")

    st.markdown(theme.section_header("📄", "Full matched claims table"), unsafe_allow_html=True)
    full_view = matched_df[
        [
            "claim_id", "member_id", "matched_member_id", "match_method", "match_note",
            "patient_name", "member_name_on_file", "email", "phone", "carrier_status",
            "service_type", "amount", "expected_amount", "date_of_service",
        ]
    ]
    st.dataframe(
        full_view.style.map(lambda v: MATCH_METHOD_STYLE.get(v, ""), subset=["match_method"]),
        hide_index=True,
        width="stretch",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(theme.section_header("🗃️", "Mock member database"), unsafe_allow_html=True)
        st.dataframe(members_df, hide_index=True, width="stretch")
    with col_b:
        st.markdown(theme.section_header("📬", "Mock incoming claims feed (raw, as received)"), unsafe_allow_html=True)
        st.dataframe(claims_df, hide_index=True, width="stretch")
