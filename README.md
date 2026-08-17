# Member Services: Proactive Claim Issue Detection (Prototype)
# Development timeline note
This project was built iteratively over about a week — including fixing a real bug where summary counts didn't reconcile (see "Why 'unique claims flagged' ≠ 'total issue instances'" above) and refining the matching and diagnosis logic based on testing. It was uploaded to GitHub as a single commit after development was complete, rather than committed incrementally during the build.
## What this is

A **prototype / proof-of-concept**, built to support an internal pitch for real
bulk claims-data access. It runs entirely on **synthetic, made-up data**
generated at runtime — it is **not a deployed system**, and it is **not
connected to any real carrier system, insurance portal, or actual member
data**, now or ever, in its current form.

It demonstrates one idea: instead of finding out about a claim issue when a
member calls in already confused about a bill, we could catch several common,
recognizable issue patterns the moment claims data arrives, match it to the
right member, and have a drafted notification and an internal action ticket
ready to go — before the member is ever surprised by a bill.

## What it automates vs. what it doesn't

**Automated in this prototype:**
- Detection of four issue categories from claims data
- Matching a claim to a member record (ID → name+DOB fallback → unmatched),
  with a specific diagnostic reason attached to every unmatched claim
- Categorization and prioritization
- Drafting of member notifications and internal tickets
- A **simulated** "Send" action with a real success/failure result, on
  whichever contact channel(s) - email, phone, or both - the member has on
  file

**NOT automated — still requires a human, even in a real version:**
- Actually sending any real message to a member. The "Send" buttons in the
  Notifications tab and the Live Claim Walkthrough are simulated only - no
  real email provider or SMS gateway is ever called (see `sending.py`).
  They exist to show what a delivery/result report would look like, not to
  send anything for real.
- Actually contacting a provider or carrier and confirming resubmission
- Actually updating COB or any record in a real system

Every "notification" in the UI is a draft until it's (simulated-)sent.

## Claims volume assumption

The sidebar's batch size is **not hardcoded** - it's derived from two adjustable
inputs:

- **Estimated claims processed per day** (default 1,000) - explicitly labeled
  as an assumption, with a caption clarifying it's illustrative for the demo,
  not a verified figure. Our member base is 50,000+, but actual daily claim
  volume hasn't been confirmed with the claims team yet; this input exists so
  that number can be swapped in later without touching any code.
- **Number of days to simulate** (default 10)

The two multiply into the total simulated batch size, shown live in the
sidebar (e.g. 1,000/day × 10 days = 10,000 claims). Each mock claim's
`date_of_service` is spread across that exact day window, which is what
powers the **Daily claims volume trend** charts on the main page (total
claims/day, and flagged issues/day by category).

Because bumping these inputs up can generate thousands of flagged claims, the
Member Notifications and Internal Action Tickets tabs cap their on-screen
card view at 50 rows for responsiveness - the full set is always available
via the CSV download button (or the data-table view for tickets).

## The four issue categories

1. **Out-of-network provider** — billed out-of-network, higher cost to the member.
2. **COB needs updating** — claim can't fully process without updated
   other-insurance info. Ticket: proactively contact member to confirm and update.
3. **Claim sent to the wrong carrier** — provider needs to resubmit. Ticket:
   contact provider, track resubmission until resolved.
4. **Possible dispute risk** — a *prediction*, not a confirmed issue, based on
   the billed amount being significantly higher than typical for that
   service (≥1.5x the expected cost **and** at least $150 above it — see
   `notifications.py`). Because this is probabilistic, **no member
   notification is auto-drafted for it** — it only ever produces an internal
   ticket for the team to review before the member is billed. We can't know a
   member will dispute something until they tell us, and telling a member
   "you might dispute this" before anything has actually gone wrong would be
   an odd, unearned thing to say.

## Why "unique claims flagged" ≠ "total issue instances"

A single claim can carry **more than one issue type at once** - most often a
primary category (out-of-network / COB / wrong carrier) *plus* a dispute-risk
flag, since dispute risk is a separate amount-based check layered on top of
whatever the carrier status already says. So two numbers in the Summary row
are genuinely different, not a bug:

- **Unique claims flagged** - `tickets_df["claim_id"].nunique()`. Each claim
  counted once, no matter how many issues it has.
- **Total issue instances** - `len(tickets_df)`. One row per issue, so a
  claim with two issues contributes two rows.

The traceable identity is:

```
notifications drafted (non-dispute-risk instances)
  + dispute-risk instances (internal-only, no notification)
  = total issue instances
```

...which is always higher than unique claims flagged whenever any claim has
more than one issue type. The Summary caption shows the count of claims
carrying more than one issue type explicitly, and the "Breakdown by issue
type" chart is issue **instances**, not unique claims - its bars sum to
"Total issue instances," not "Unique claims flagged."

## Live Claim Walkthrough tab

The UI's first tab processes a single fresh claim end to end, one step at a
time (intake → matching → issue check → draft output), instead of just
showing pre-computed batch results. You can force the scenario - e.g. pick
"Coordination of Benefits (COB) update needed" to specifically demo whether
a claim requires a COB update - or set it to "Random" and let the ID quality
and dispute-risk odds decide. Step 3 always shows an explicit **Yes/No**
answer to "Does this claim require a COB update?" alongside the other three
checks, since that's often the question being demoed.

## Sending notifications (simulated)

`sending.py` simulates delivering a drafted notification and reports a real
success/failure result - **no real email or SMS is ever sent**; no external
provider is ever called. It exists to show what a "was it actually
delivered" report would look like in a real version.

- **Channel logic**: a member is notified on whichever contact channel(s)
  they have on file - email, phone, or both. If they have neither, that's
  reported as its own distinct outcome (`no_contact_info`) rather than
  silently failing.
- **Result**: each channel gets a simulated ~95% success rate. The overall
  result per notification is `sent` (all channels succeeded), `partial`
  (some did), `failed` (none did), or `no_contact_info`.
- **Where to find it**: the Member Notifications tab has a per-notification
  "Send (simulated)" button and a "Send all" bulk action (with a live
  progress bar and a results summary - counts + downloadable CSV). The Live
  Claim Walkthrough's Step 5 runs the same simulated send automatically as
  part of the single-claim demo.

## Member matching logic

Claims data from a carrier does not include a member's email — only fields
like member/policy ID, patient name, and date of birth. Email only exists in
our own member database.

`matching.py` implements the matching exactly in this order:

1. **Member/policy ID** — if present on the claim and it exists in the member
   database, match on that.
2. **Fallback: patient name + date of birth** — used only if the ID is
   missing or doesn't match anyone. Name matching is case/whitespace
   insensitive; DOB must match exactly. If more than one member happens to
   share a name+DOB in the mock data, the match is still made but flagged
   with a note recommending manual confirmation.
3. **Unmatched — needs manual review** — if neither matches. The system never
   guesses at an identity. Every unmatched claim also gets a **specific
   diagnosis** (`matching.diagnose_unmatched`), not just a generic "unmatched"
   label - e.g. "a member named X exists, but the DOB on the claim doesn't
   match what's on file" vs. "no member matches this name or DOB at all."
   That's what lets a reviewer act on it (fix a typo, confirm a new member,
   flag a data mix-up) rather than starting from zero. See the "Unmatched
   claims" table and reason-code chips in the Matching Detail tab.

Once a claim is matched, the member's email/phone are pulled from the
**member database** (`members_df`), never from the claim itself, since the
claim never has them.

## Mock data

`data_generation.py` builds two tables fresh on every run (seeded, so results
are reproducible unless you hit "Regenerate"):

- **Member database**: `member_id, name, date_of_birth, email, phone,
  plan_type`. Not every member has both contact channels - ~92% have an
  email, ~55% have a phone, independently, so the mix includes email-only,
  phone-only, both, and (rarely) neither.
- **Incoming claims**: `claim_id, member_id, patient_name, date_of_birth,
  provider, service_type, amount, expected_amount, date_of_service,
  carrier_status`

Realistic messiness is built in on purpose:
- ~28% of claims have a missing or incorrect `member_id`
- ~8% of claims also have a corrupted name or DOB, so they're genuinely
  unmatchable — these are the ones that should land in "needs manual review"
- A subset of claims are billed well above the typical cost for that service,
  which is what feeds the dispute-risk heuristic

## Running it locally

Requires Python 3.9+.

```bash
cd member-services-prototype
pip install -r requirements.txt
streamlit run app.py
```

This opens the app at `http://localhost:8501`. Use the sidebar to change how
many mock members/claims are generated, adjust the random seed, or hit
"Regenerate mock data" to get a fresh synthetic dataset.

## Known limitations (it's a prototype)

- Name+DOB matching assumes reasonably clean spelling; it won't catch
  typo'd names (a real version would likely add fuzzy matching with a human
  review step for low-confidence matches).
- The dispute-risk threshold is a simple, hand-picked rule for demo
  purposes, not a trained model — a real version would likely calibrate this
  against actual historical dispute outcomes.
- No message is ever actually sent, and no provider/carrier is ever actually
  contacted — this is drafting and triage only.
- All data is synthetic and regenerated per session; nothing persists.
