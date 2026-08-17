"""
Small design system for the Streamlit UI: CSS + a handful of HTML-snippet
helpers, kept separate from app.py so layout/styling changes don't touch the
data logic.

Color choices follow a fixed categorical order (never re-assigned per-run,
never cycled) so the same issue type always reads as the same color
everywhere it appears - the chart, the notification cards, the ticket
badges. Palette values are a validated colorblind-safe set (light/dark
aware); status colors (good/warning/serious/critical) are kept separate
from the four category colors so a priority badge never gets mistaken for
an issue-type badge.
"""

import html

CSS = """
<style>
:root {
  --ms-surface: #fcfcfb;
  --ms-border: rgba(11,11,11,0.10);
  --ms-text: #0b0b0b;
  --ms-text-secondary: #52514e;

  /* Fixed categorical order - one color per issue type, used everywhere */
  --ms-blue:   #2a78d6;  /* Coordination of Benefits (COB) */
  --ms-orange: #eb6834;  /* Out-of-network provider */
  --ms-aqua:   #1baf7a;  /* Claim sent to wrong carrier */
  --ms-yellow: #eda100;  /* Possible dispute risk (predicted) */

  /* Status roles - reserved, never reused as a category color */
  --ms-green:   #0ca30c;
  --ms-amber:   #fab219;
  --ms-serious: #ec835a;
  --ms-red:     #d03b3b;
  --ms-muted:   #898781;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ms-surface: #1a1a19;
    --ms-border: rgba(255,255,255,0.10);
    --ms-text: #ffffff;
    --ms-text-secondary: #c3c2b7;
    --ms-blue:   #3987e5;
    --ms-orange: #d95926;
    --ms-aqua:   #199e70;
    --ms-yellow: #c98500;
  }
}

.ms-hero {
  padding: 1.9rem 2.1rem;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--ms-blue), var(--ms-aqua));
  color: #ffffff;
  margin-bottom: .9rem;
  box-shadow: 0 10px 28px rgba(0,0,0,0.16);
}
.ms-hero h1 { margin: 0 0 .4rem 0; font-size: 1.85rem; line-height:1.2; }
.ms-hero p { margin: 0; opacity: .93; font-size: 1.02rem; max-width: 62ch; }

.ms-proto-banner {
  display: flex; gap: .65rem; align-items: flex-start;
  background: rgba(250,178,25,0.12);
  border: 1px solid rgba(250,178,25,0.45);
  border-radius: 12px;
  padding: .8rem 1.05rem;
  margin: 0 0 1.3rem 0;
  font-size: .89rem;
  color: var(--ms-text);
}
.ms-proto-banner .icon { font-size: 1.15rem; line-height:1.3; }
.ms-proto-banner b { color: var(--ms-text); }

.ms-tiles { display: grid; grid-template-columns: repeat(6, 1fr); gap: .7rem; margin-bottom: 1.3rem; }
@media (max-width: 1200px) { .ms-tiles { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 700px) { .ms-tiles { grid-template-columns: repeat(2, 1fr); } }
.ms-tile {
  background: var(--ms-surface);
  border: 1px solid var(--ms-border);
  border-left: 4px solid var(--accent, var(--ms-blue));
  border-radius: 14px;
  padding: .95rem 1.05rem;
}
.ms-tile .ms-tile-top { display:flex; align-items:center; justify-content:space-between; }
.ms-tile .ms-tile-icon { font-size: 1.1rem; opacity: .85; }
.ms-tile .ms-tile-value { font-size: 1.65rem; font-weight: 700; color: var(--ms-text); line-height: 1.15; margin-top:.2rem; }
.ms-tile .ms-tile-label { font-size: .78rem; color: var(--ms-text-secondary); margin-top: .15rem; }

.ms-section-header { display: flex; align-items: baseline; gap: .5rem; margin: 1.6rem 0 .6rem 0; }
.ms-section-header .icon { font-size: 1.25rem; }
.ms-section-header .title { font-size: 1.15rem; font-weight: 700; color: var(--ms-text); }
.ms-section-header .sub { font-size: .85rem; color: var(--ms-text-secondary); }

.ms-badge {
  display: inline-flex; align-items: center; gap: .35rem;
  padding: .22rem .65rem; border-radius: 999px;
  font-size: .78rem; font-weight: 650; white-space: nowrap;
}
.ms-badge--blue   { background: var(--ms-blue);   color: #fff; }
.ms-badge--orange { background: var(--ms-orange); color: #fff; }
.ms-badge--aqua   { background: var(--ms-aqua);   color: #fff; }
.ms-badge--yellow { background: var(--ms-yellow); color: #241900; }

.ms-priority {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .16rem .58rem; border-radius: 999px;
  font-size: .74rem; font-weight: 700;
}
.ms-priority--high     { background: var(--ms-red);     color: #fff; }
.ms-priority--medium   { background: var(--ms-amber);   color: #2b1d00; }
.ms-priority--review   { background: var(--ms-serious); color: #2b0f00; }

.ms-sendstatus {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .16rem .58rem; border-radius: 999px;
  font-size: .74rem; font-weight: 700;
}
.ms-sendstatus--sent       { background: var(--ms-green); color: #fff; }
.ms-sendstatus--partial    { background: var(--ms-amber); color: #2b1d00; }
.ms-sendstatus--failed     { background: var(--ms-red);   color: #fff; }
.ms-sendstatus--no_contact { background: var(--ms-muted); color: #fff; }

.ms-chip-row { display: flex; flex-wrap: wrap; gap: .5rem; margin: .4rem 0 1rem 0; }

.ms-card {
  background: var(--ms-surface);
  border: 1px solid var(--ms-border);
  border-radius: 14px;
  padding: 1rem 1.15rem;
  margin-bottom: .65rem;
}

.ms-letter {
  background: var(--ms-surface);
  border: 1px solid var(--ms-border);
  border-left: 4px solid var(--accent, var(--ms-blue));
  border-radius: 10px;
  padding: 1rem 1.2rem;
  white-space: pre-wrap;
  font-size: .92rem;
  line-height: 1.55;
  color: var(--ms-text);
  margin: .5rem 0 1rem 0;
}

.ms-ticket-card {
  background: var(--ms-surface);
  border: 1px solid var(--ms-border);
  border-radius: 12px;
  padding: .85rem 1.05rem;
  margin-bottom: .55rem;
}
.ms-ticket-card .row1 { display:flex; align-items:center; justify-content:space-between; gap:.5rem; flex-wrap:wrap; }
.ms-ticket-card .claim { font-weight: 700; color: var(--ms-text); }
.ms-ticket-card .next-step { font-size: .87rem; color: var(--ms-text-secondary); margin-top: .4rem; }

.ms-versus { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin-bottom: .55rem; }
@media (max-width: 900px) { .ms-versus { grid-template-columns: 1fr; } }
.ms-versus-step { font-weight: 700; color: var(--ms-text); margin: 1.1rem 0 .4rem 0; font-size: .95rem; }
.ms-versus-col { border-radius: 12px; padding: .8rem 1rem; font-size: .87rem; line-height:1.45; }
.ms-versus-col .tag { font-weight: 700; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--ms-text-secondary); margin-bottom: .3rem; display:block; }
.ms-versus-col--before { background: rgba(208,59,59,0.08); border: 1px solid rgba(208,59,59,0.28); }
.ms-versus-col--after  { background: rgba(27,175,122,0.08); border: 1px solid rgba(27,175,122,0.30); }

[data-baseweb="tab-list"] { gap: 4px; }
[data-baseweb="tab"] { border-radius: 10px 10px 0 0 !important; }
[data-baseweb="tab-highlight"] { background-color: var(--ms-blue) !important; height: 3px !important; }
[data-testid="stSidebar"] { border-right: 1px solid var(--ms-border); }
</style>
"""

# One entry per issue-type label exactly as produced by notifications.ISSUE_LABELS.
ISSUE_STYLE = {
    "Coordination of Benefits (COB) update needed": {"class": "blue", "icon": "🔄"},
    "Out-of-network provider": {"class": "orange", "icon": "🌐"},
    "Claim sent to wrong carrier": {"class": "aqua", "icon": "📮"},
    "Possible dispute risk (predicted, not confirmed)": {"class": "yellow", "icon": "🔮"},
}

PRIORITY_STYLE = {
    "High": {"class": "high", "icon": "🔺"},
    "Medium": {"class": "medium", "icon": "➡️"},
    "Review": {"class": "review", "icon": "🔍"},
}

# Fixed slot order (never re-sorted by count) - drives both the chart and chip row.
ISSUE_ORDER = [
    "Coordination of Benefits (COB) update needed",
    "Out-of-network provider",
    "Claim sent to wrong carrier",
    "Possible dispute risk (predicted, not confirmed)",
]

# Light-mode hex per categorical class - Altair/Vega charts render server-side
# and can't consume CSS custom properties, so charts get raw hex here while
# HTML badges elsewhere keep using the CSS vars (which also cover dark mode).
ISSUE_HEX = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100"}


def ordered_issue_colors(labels: list) -> list:
    """Hex color for each label in `labels`, in the fixed categorical mapping."""
    return [ISSUE_HEX[ISSUE_STYLE[label]["class"]] for label in labels]


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def issue_badge(label: str) -> str:
    style = ISSUE_STYLE.get(label, {"class": "blue", "icon": "•"})
    return f'<span class="ms-badge ms-badge--{style["class"]}">{style["icon"]} {_esc(label)}</span>'


def priority_badge(priority: str) -> str:
    style = PRIORITY_STYLE.get(priority, {"class": "medium", "icon": "•"})
    return f'<span class="ms-priority ms-priority--{style["class"]}">{style["icon"]} {_esc(priority)}</span>'


SEND_STATUS_STYLE = {
    "sent": {"class": "sent", "icon": "✅", "label": "Sent"},
    "partial": {"class": "partial", "icon": "⚠️", "label": "Partially sent"},
    "failed": {"class": "failed", "icon": "❌", "label": "Failed"},
    "no_contact_info": {"class": "no_contact", "icon": "🚫", "label": "No contact info on file"},
}


def send_status_badge(overall_status: str) -> str:
    style = SEND_STATUS_STYLE.get(overall_status, {"class": "failed", "icon": "❌", "label": overall_status})
    return f'<span class="ms-sendstatus ms-sendstatus--{style["class"]}">{style["icon"]} {_esc(style["label"])}</span>'


def contact_summary(email: str, phone: str) -> str:
    """Plain text (no HTML) - safe to use directly in st.expander labels."""
    parts = []
    if email:
        parts.append(f"📧 {email}")
    if phone:
        parts.append(f"📱 {phone}")
    return " · ".join(parts) if parts else "⚠️ no contact info on file"


def hero(title: str, tagline: str) -> str:
    return f'<div class="ms-hero"><h1>{_esc(title)}</h1><p>{_esc(tagline)}</p></div>'


def proto_banner(text_html: str) -> str:
    return f'<div class="ms-proto-banner"><span class="icon">⚠️</span><div>{text_html}</div></div>'


def tile(value, label: str, icon: str, accent_var: str) -> str:
    return (
        f'<div class="ms-tile" style="--accent:var(--{accent_var})">'
        f'<div class="ms-tile-top"><span class="ms-tile-icon">{icon}</span></div>'
        f'<div class="ms-tile-value">{_esc(value)}</div>'
        f'<div class="ms-tile-label">{_esc(label)}</div>'
        f"</div>"
    )


def tiles_row(tiles_html: list) -> str:
    return '<div class="ms-tiles">' + "".join(tiles_html) + "</div>"


def section_header(icon: str, title: str, sub: str = "") -> str:
    sub_html = f'<span class="sub">{_esc(sub)}</span>' if sub else ""
    return (
        f'<div class="ms-section-header"><span class="icon">{icon}</span>'
        f'<span class="title">{_esc(title)}</span>{sub_html}</div>'
    )


def letter(message: str, issue_label: str) -> str:
    accent_class = ISSUE_STYLE.get(issue_label, {"class": "blue"})["class"]
    accent_var = {"blue": "ms-blue", "orange": "ms-orange", "aqua": "ms-aqua", "yellow": "ms-yellow"}[accent_class]
    return f'<div class="ms-letter" style="--accent:var(--{accent_var})">{_esc(message)}</div>'


def ticket_card(claim_id: str, member_name: str, issue_label: str, priority: str, next_step: str) -> str:
    return (
        '<div class="ms-ticket-card">'
        f'<div class="row1"><span class="claim">{_esc(claim_id)} — {_esc(member_name)}</span>'
        f"{priority_badge(priority)}</div>"
        f"<div>{issue_badge(issue_label)}</div>"
        f'<div class="next-step">{_esc(next_step)}</div>'
        "</div>"
    )


def versus_row(step: str, today_text: str, after_text: str) -> str:
    return (
        f'<div class="ms-versus-step">{_esc(step)}</div>'
        '<div class="ms-versus">'
        f'<div class="ms-versus-col ms-versus-col--before"><span class="tag">Today (reactive)</span>{_esc(today_text)}</div>'
        f'<div class="ms-versus-col ms-versus-col--after"><span class="tag">With this prototype</span>{_esc(after_text)}</div>'
        "</div>"
    )
