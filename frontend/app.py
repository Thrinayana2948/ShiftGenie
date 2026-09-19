"""ShiftGenie Streamlit frontend — premium workforce operations UI.

All data comes from the existing FastAPI backend; no scheduling/validation
logic is duplicated here. This file only presents backend responses.
"""

import html

import requests
import streamlit as st

BACKEND_URL = "https://shiftgenie.onrender.com"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

st.set_page_config(page_title="ShiftGenie", layout="wide")

# ---------------------------------------------------------------- theme ----

PALETTES = {
    "light": dict(
        canvas="#F4F5F8", panel="#FFFFFF", card="#FFFFFF", primary="#B832C7",
        secondary="#0284C7", text="#171522", muted="#6B6878", panel_text="#171522",
        success="#16A34A", warning="#D97706", error="#DC2626", border="#D9DCE5",
    ),
    "dark": dict(
        canvas="#13111C", panel="#181524", card="#1E1B2E", primary="#E056FD",
        secondary="#38BDF8", text="#F3F4F6", muted="#8B85A1", panel_text="#F3F4F6",
        success="#4ADE80", warning="#FBBF24", error="#F87171", border="#2A263D",
    ),
}

st.session_state.theme = st.session_state.get("theme_radio", "Light").lower()

P = PALETTES[st.session_state.theme]

def _rgb(h: str) -> str:
    h = h.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


PR, SE = _rgb(P["primary"]), _rgb(P["secondary"])
DARK = st.session_state.theme == "dark"
BTN_TEXT = "#13111C" if DARK else "#FFFFFF"
TRACK = "#141221" if DARK else "#E6E8EF"
INSET_BG = "#13111C" if DARK else "#F1F2F6"
SPEC = "rgba(255,255,255,0.06)" if DARK else f"rgba({PR},0.06)"
if DARK:
    SH = "0 1px 0 rgba(255,255,255,0.04) inset, 0 1px 2px rgba(0,0,0,0.4), 0 10px 22px -14px rgba(0,0,0,0.7)"
    SH_HOVER = "0 1px 0 rgba(255,255,255,0.06) inset, 0 2px 4px rgba(0,0,0,0.45), 0 16px 28px -14px rgba(0,0,0,0.85)"
    INSET = "inset 0 2px 5px rgba(0,0,0,0.5)"
    KEY_SH = "0 2px 0 rgba(0,0,0,0.5)"
else:
    SH = "0 1px 0 #FFFFFF inset, 0 1px 2px rgba(23,21,34,0.06), 0 10px 20px -14px rgba(23,21,34,0.22)"
    SH_HOVER = "0 1px 0 #FFFFFF inset, 0 2px 4px rgba(23,21,34,0.08), 0 16px 26px -14px rgba(23,21,34,0.32)"
    INSET = "inset 0 2px 5px rgba(23,21,34,0.14)"
    KEY_SH = "0 2px 0 rgba(23,21,34,0.12)"

st.markdown(
    f"""
<style>
@keyframes sg-pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.45; }} }}
@keyframes sg-rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes sg-grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}

.stApp {{ background: {P['canvas']}; color: {P['text']}; }}
.stApp::before {{
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(55% 38% at 12% 0%, rgba({PR},{0.09 if DARK else 0.06}) 0%, transparent 70%),
        radial-gradient(40% 32% at 100% 0%, rgba({SE},{0.08 if DARK else 0.06}) 0%, transparent 70%);
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ position: relative; z-index: 1; padding-top: 3rem; max-width: 1240px; animation: sg-rise .35s ease-out both; }}

h1, h2, h3, h4, p, span, label, div {{ color: {P['text']}; }}
h1 {{ font-weight: 700; letter-spacing: -0.02em; }}
h1::after {{ content: ""; display: block; width: 40px; height: 3px; margin-top: 10px; border-radius: 2px; background: {P['primary']}; }}
h2, h3 {{ font-weight: 600; letter-spacing: -0.01em; }}
[data-testid="stCaptionContainer"] {{ color: {P['muted']}; }}

/* ---- sidebar ---- */
section[data-testid="stSidebar"] {{ background: {P['panel']}; border-right: 1px solid {P['border']}; z-index: 2; }}
section[data-testid="stSidebar"] * {{ color: {P['panel_text']} !important; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{ color: {P['muted']} !important; }}
section[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 3px; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
    padding: 9px 12px; border-radius: 8px; border: 1px solid transparent; cursor: pointer;
    transition: background .15s ease, transform .15s ease, border-color .15s ease;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label > div > div:first-child {{ display: none; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: rgba({PR},0.08); transform: translateX(2px); }}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
    background: {INSET_BG}; border-color: {P['border']}; transform: none;
    box-shadow: {INSET}, inset 3px 0 0 {P['primary']};
}}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ font-weight: 600; }}
section[data-testid="stSidebar"] hr {{ border-color: {P['border']}; }}
.sg-brand {{ display: flex; align-items: center; gap: 10px; padding: 4px 0 2px; }}
.sg-brand-mark {{
    width: 26px; height: 26px; border-radius: 7px; display: grid; place-items: center;
    background: linear-gradient(135deg, {P['primary']}, {P['secondary']});
    box-shadow: 0 1px 0 rgba(255,255,255,0.3) inset, {KEY_SH};
}}
.sg-brand-mark i {{ width: 10px; height: 10px; border: 2px solid #fff; border-radius: 2px; display: block; }}
.sg-brand-name {{ font-weight: 700; letter-spacing: 0.16em; font-size: 0.92rem; }}
.sg-live {{ display: flex; align-items: center; gap: 8px; font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; padding: 2px 0 6px; }}
.sg-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; animation: sg-pulse 2.4s ease-in-out infinite; }}

/* ---- cards: physical depth + specular highlight ---- */
.sg-card {{
    background: {P['card']}; border: 1px solid {P['border']}; border-radius: 10px;
    padding: 16px 18px; margin-bottom: 12px; box-shadow: {SH}; position: relative; overflow: hidden;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}}
.sg-card::before {{
    content: ""; position: absolute; left: 0; top: 0; right: 0; height: 2px; opacity: 0;
    background: {P['primary']}; transition: opacity .18s ease;
}}
.sg-card::after {{
    content: ""; position: absolute; inset: 0; pointer-events: none; opacity: 0; transition: opacity .2s ease;
    background: linear-gradient(135deg, {SPEC} 0%, transparent 42%);
}}
.sg-card:hover {{ transform: perspective(900px) translateY(-2px) rotateX(0.4deg) scale(1.003); box-shadow: {SH_HOVER}; border-color: rgba({PR},0.45); }}
.sg-card:hover::before, .sg-card:hover::after {{ opacity: 1; }}
.sg-muted {{ color: {P['muted']}; font-size: 0.85rem; }}
.sg-metric-label {{ color: {P['muted']}; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; }}
.sg-metric-value {{ color: {P['text']}; font-size: 1.8rem; font-weight: 700; margin-top: 4px; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }}
.sg-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em; }}
.sg-badge::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: sg-pulse 2.4s ease-in-out infinite; }}
.sg-flow {{ color: {P['muted']}; font-size: 0.95rem; padding: 12px 16px; border-radius: 10px; border: 1px solid {P['border']}; background: {P['card']}; box-shadow: {SH}; }}
.sg-flow b {{ color: {P['text']}; }}

.sg-section {{
    display: flex; align-items: center; gap: 10px; margin: 24px 0 10px; font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.16em; text-transform: uppercase; color: {P['muted']};
}}
.sg-section::before {{ content: ""; width: 6px; height: 6px; border-radius: 2px; background: {P['primary']}; }}
.sg-section::after {{ content: ""; flex: 1; height: 1px; background: {P['border']}; }}

.sg-check {{ border-left: 3px solid {P['border']}; }}
.sg-check.ok {{ border-left-color: {P['success']}; }}
.sg-check.bad {{ border-left-color: {P['error']}; }}
.sg-check.warn {{ border-left-color: {P['warning']}; }}
.sg-check-label {{ font-weight: 600; margin-bottom: 8px; }}

.sg-health-row {{ display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid {P['border']}; font-size: 0.88rem; }}
.sg-health-row:last-child {{ border-bottom: none; }}

.sg-bars {{ display: grid; gap: 9px; }}
.sg-bar-row {{ display: grid; grid-template-columns: minmax(96px, 168px) 1fr auto; align-items: center; gap: 12px; font-size: 0.82rem; }}
.sg-bar-label {{ color: {P['text']}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.sg-bar-track {{ height: 10px; border-radius: 5px; background: {TRACK}; box-shadow: {INSET}; overflow: hidden; }}
.sg-bar-fill {{ height: 100%; border-radius: 5px; transform-origin: left; animation: sg-grow .45s ease-out both; }}
.sg-bar-val {{ color: {P['muted']}; font-variant-numeric: tabular-nums; min-width: 52px; text-align: right; font-weight: 600; }}

[data-testid="stDataFrame"] {{ border: 1px solid {P['border']}; border-radius: 10px; overflow: hidden; box-shadow: {SH}; }}

/* ---- buttons: raised keys ---- */
.stButton>button, [data-testid="stFormSubmitButton"]>button {{
    border-radius: 8px; font-weight: 600; letter-spacing: 0.01em; transform: translateY(0);
    transition: transform .12s ease, box-shadow .15s ease, filter .15s ease, border-color .15s ease;
}}
.stButton>button[kind="primary"], [data-testid="stFormSubmitButton"]>button[kind="primary"] {{
    background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0) 60%), {P['primary']};
    border: 1px solid rgba(0,0,0,0.28); color: {BTN_TEXT};
    box-shadow: 0 1px 0 rgba(255,255,255,0.28) inset, 0 2px 0 rgba(0,0,0,0.3), 0 8px 14px -8px rgba({PR},0.6);
}}
.stButton>button[kind="primary"] *, [data-testid="stFormSubmitButton"]>button[kind="primary"] * {{ color: {BTN_TEXT} !important; }}
.stButton>button[kind="secondary"], [data-testid="stFormSubmitButton"]>button[kind="secondary"] {{
    background: {P['card']}; border: 1px solid {P['border']}; color: {P['text']}; box-shadow: {KEY_SH};
}}
.stButton>button:hover, [data-testid="stFormSubmitButton"]>button:hover {{ transform: translateY(-1px); }}
.stButton>button[kind="primary"]:hover, [data-testid="stFormSubmitButton"]>button[kind="primary"]:hover {{
    box-shadow: 0 1px 0 rgba(255,255,255,0.3) inset, 0 3px 0 rgba(0,0,0,0.3), 0 12px 18px -8px rgba({PR},0.6); filter: brightness(1.05);
}}
.stButton>button[kind="secondary"]:hover, [data-testid="stFormSubmitButton"]>button[kind="secondary"]:hover {{ border-color: {P['primary']}; }}
.stButton>button:active, [data-testid="stFormSubmitButton"]>button:active {{
    transform: translateY(2px); box-shadow: {INSET}; filter: none;
}}

/* ---- inputs ---- */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {{
    background: {P['card']} !important; border-color: {P['border']} !important; border-radius: 8px !important;
}}
.stTextInput input, .stTextArea textarea, .stNumberInput input, [data-baseweb="select"] * {{ color: {P['text']} !important; -webkit-text-fill-color: {P['text']}; }}
[data-testid="stSelectbox"] [role="group"], [data-testid="stTextInput"] div:has(> input), [data-testid="stNumberInput"] div:has(> input),
[data-testid="stTextArea"] div:has(> textarea) {{
    background: {P['card']} !important; border-color: {P['border']} !important; border-radius: 8px;
}}
[data-testid="stSelectbox"] input, [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea {{
    color: {P['text']} !important; -webkit-text-fill-color: {P['text']};
}}
[role="listbox"] {{ background: {P['card']} !important; }}
[role="listbox"] [role="option"] {{ color: {P['text']} !important; }}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] ul {{ background: {P['card']} !important; }}
[data-baseweb="popover"] li {{ color: {P['text']} !important; }}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{ box-shadow: 0 0 0 3px rgba({PR},0.2) !important; }}
[data-testid="stExpander"] {{ border: 1px solid {P['border']}; border-radius: 10px; background: {P['card']}; box-shadow: {SH}; }}
[data-testid="stExpander"] summary {{
    background: {P['card']} !important; color: {P['text']} !important; border-radius: 10px;
    transition: background-image .15s ease;
}}
[data-testid="stExpander"] summary * {{ color: {P['text']} !important; }}
[data-testid="stExpander"] summary:hover {{ background-image: linear-gradient(rgba({PR},0.08), rgba({PR},0.08)); }}
[data-testid="stExpander"] details[open] > summary {{
    border-bottom: 1px solid {P['border']}; border-bottom-left-radius: 0; border-bottom-right-radius: 0;
}}
@media (prefers-color-scheme: {'light' if DARK else 'dark'}) {{
    [data-testid="stDataFrameResizable"] {{ filter: invert(1) hue-rotate(180deg); }}
}}
[data-testid="stAlert"] {{ border-radius: 10px; }}
hr {{ border-color: {P['border']}; }}

::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: {P['border']}; border-radius: 6px; }}
::-webkit-scrollbar-thumb:hover {{ background: {P['muted']}; }}

@media (prefers-reduced-motion: reduce) {{
    .sg-dot, .sg-badge::before, .block-container, .sg-bar-fill {{ animation: none !important; }}
    .sg-card, .stButton>button {{ transition: none !important; }}
}}
</style>
""",
    unsafe_allow_html=True,
)


def section(title: str):
    st.markdown(f'<div class="sg-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def bars(rows, empty: str):
    """rows: (label, percent, value_html, color). All values are computed from backend data."""
    if not rows:
        st.markdown(f'<div class="sg-card sg-muted">{html.escape(empty)}</div>', unsafe_allow_html=True)
        return
    items = "".join(
        f'<div class="sg-bar-row"><span class="sg-bar-label" title="{html.escape(l)}">{html.escape(l)}</span>'
        f'<div class="sg-bar-track"><div class="sg-bar-fill" style="width:{min(100, max(0, pct)):.0f}%;background:{c};"></div></div>'
        f'<span class="sg-bar-val">{v}</span></div>'
        for l, pct, v, c in rows
    )
    st.markdown(f'<div class="sg-card"><div class="sg-bars">{items}</div></div>', unsafe_allow_html=True)


def badge(text: str, kind: str) -> str:
    color = {"success": P["success"], "warning": P["warning"], "error": P["error"], "muted": P["muted"]}[kind]
    return f'<span class="sg-badge" style="background:{color}22;color:{color};">{html.escape(text)}</span>'


def metric_card(label: str, value: str, sub: str = "", kind: str = ""):
    sub_html = f'<div class="sg-muted">{html.escape(sub)}</div>' if sub else ""
    color = f' style="color:{P[kind]};"' if kind in ("success", "warning", "error") else ""
    st.markdown(
        f'<div class="sg-card"><div class="sg-metric-label">{html.escape(label)}</div>'
        f'<div class="sg-metric-value"{color}>{html.escape(str(value))}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str):
    st.markdown(f'<div class="sg-card sg-muted">{html.escape(message)}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------- backend ----

def api_get(path, timeout=5):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=timeout)
        return r if r.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def api_post(path, json=None, timeout=30):
    try:
        return requests.post(f"{BACKEND_URL}{path}", json=json, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return e


def backend_ok() -> bool:
    return api_get("/health") is not None


@st.cache_data(ttl=10, show_spinner=False)
def _cached_get(path: str):
    r = requests.get(f"{BACKEND_URL}{path}", timeout=30)
    r.raise_for_status()
    return r.json()


def refresh_data():
    _cached_get.clear()


def _fetch_list(path: str, label: str):
    try:
        return _cached_get(path)
    except requests.exceptions.RequestException as e:
        st.session_state["_fetch_failed"] = True
        st.error(f"Could not load {label} from the backend ({type(e).__name__}). Check the backend and try again.")
        return []


def get_employees():
    st.session_state["_fetch_failed"] = False
    return _fetch_list("/employees", "employees")


def get_shifts():
    return _fetch_list("/shifts", "shifts")


def flash(kind: str, msg: str):
    st.session_state["flash"] = (kind, msg)


def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        getattr(st, f[0])(f[1])


def shift_hours(start: str, end: str) -> float:
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    return (eh * 60 + em - (sh * 60 + sm)) / 60



def table(rows):
    st.dataframe(rows, use_container_width=True, hide_index=True)


def status_card(title: str, sub: str, kind: str, extra: str = ""):
    """kind: ok | warn | bad"""
    st.markdown(
        f'<div class="sg-card sg-check {kind}"><div class="sg-check-label">{html.escape(title)}</div>'
        f'<div class="sg-muted">{html.escape(sub)}</div>{extra}</div>',
        unsafe_allow_html=True,
    )


def run_generation(reset: bool = False):
    """Real scheduling action. reset=True restores the demo baseline and clears the current roster first.
    Returns an error message, or None on success (a summary is queued via flash)."""
    note = ""
    if reset:
        r = api_post("/demo/reset", timeout=180)
        if isinstance(r, Exception) or r is None or r.status_code != 200:
            return "Could not reset the demo data. Please try again."
        info = r.json()
        for k in ("schedule", "sim_result", "resolve_result", "req_result", "sim_scenario_key", "sim_params"):
            st.session_state.pop(k, None)
        refresh_data()
        note = f"Demo baseline restored ({info['employees_restored']} employee(s) reset, {info['employees_added']} added). "
    resp = api_post("/schedule/generate", timeout=120)
    if isinstance(resp, Exception) or resp is None:
        return "The backend is unavailable. Please try again."
    if resp.status_code != 200:
        return "Schedule generation failed."
    sc = resp.json()
    st.session_state.schedule = sc
    stt = sc["stats"]
    msg = (f"{note}Schedule generated: {stt['assignments']} assignments, {stt['coverage_ratio']:.0%} coverage, "
           f"{stt['violations']} violation(s), solved with {sc['solver']}.")
    flash("success" if sc["valid"] else "warning", msg)
    return None


def roster_rows(schedule, employees, shifts):
    emp = {str(e["id"]): e for e in employees}
    order = {d: i for i, d in enumerate(DAYS)}
    rows = []
    for sh in sorted(shifts, key=lambda x: (order.get(x["day_of_week"], 9), x["start_time"])):
        hrs = shift_hours(sh["start_time"], sh["end_time"])
        ids = schedule["assignments"].get(str(sh["id"]), [])
        base = {"Day": sh["day_of_week"], "Shift": sh["name"], "Time": f"{sh['start_time']}–{sh['end_time']}", "Hours": hrs}
        for eid in ids:
            e = emp.get(str(eid))
            rows.append({**base, "Employee": e["name"] if e else "—", "Role": e["role"] if e else "—", "Status": "Assigned"})
        for _ in range(max(0, sh["required_staff"] - len(ids))):
            rows.append({**base, "Employee": "Unfilled", "Role": "—", "Status": "Unfilled"})
    return rows


def render_generation_result(sc):
    stt = sc["stats"]
    if not sc["valid"]:
        status_card("No Valid Schedule Found", "The independent validator rejected every candidate schedule, so none is shown as valid.", "bad")
    elif sc["fully_covered"]:
        status_card("Schedule Generated", f"{stt['employees']} employees · {stt['shifts']} shifts · {stt['assignments']} assignments", "ok")
    else:
        gap = stt["required"] - stt["assignments"]
        status_card("Schedule Generated — Partial Coverage",
                    f"{stt['employees']} employees · {stt['shifts']} shifts · {gap} staff slot(s) could not be filled", "warn")
    c = st.columns(5)
    with c[0]:
        metric_card("Assignments", stt["assignments"], f"of {stt['required']} required")
    with c[1]:
        metric_card("Coverage", f"{stt['coverage_ratio'] * 100:.0f}%", kind="success" if sc["fully_covered"] else "warning")
    with c[2]:
        metric_card("Hard Violations", stt["violations"], "independent validator", "success" if not stt["violations"] else "error")
    with c[3]:
        ot = stt["overtime_hours"]
        metric_card("Overtime", "None" if not ot else f"{ot:.0f}h", "weekly limits enforced")
    with c[4]:
        sub = "validated" if not sc.get("fallback_reason") else "OR-Tools unavailable, fallback validated"
        metric_card("Solver Used", sc["solver"], sub)


def render_changes(ch, partial=False, counts=True):
    cnt = ch["counts"]
    c = st.columns(5) if counts else []
    for col, (label, key) in zip(c, [("Shifts changed", "shifts_changed"), ("Employees reassigned", "employees_reassigned"),
                                      ("Employees removed", "employees_removed"), ("New assignments", "new_assignments"),
                                      ("Unchanged shifts", "unchanged_shifts")]):
        with col:
            metric_card(label, cnt[key])
    if partial:
        st.caption("Best valid roster found — some shifts remain understaffed.")
    if ch["employees"]:
        st.markdown("**Employee changes**")
        table([{"Employee": r["employee"], "Before": r["before"], "After": r["after"], "Change": r["change"]} for r in ch["employees"]])
    changed = [r for r in ch["shifts"] if r["status"] == "Changed"]
    if changed:
        st.markdown("**Shift changes**")
        table([{"Shift": r["shift"], "Before": r["before"], "After": r["after"], "Change": r["change"]} for r in changed])
    elif not ch["employees"]:
        st.caption("No roster change was possible — the current roster is already the best valid arrangement."
                   if partial else "The roster did not need to change.")
    unchanged = [r for r in ch["shifts"] if r["status"] == "Unchanged"]
    if unchanged:
        with st.expander(f"Unchanged shifts ({len(unchanged)})", expanded=False):
            table([{"Shift": r["shift"], "Assigned": r["after"]} for r in unchanged])


# ------------------------------------------------------------------ nav -----

_online = backend_ok()
_dot = P["success"] if _online else P["error"]
_status = "System online" if _online else "Backend offline"
st.sidebar.markdown(
    '<div class="sg-brand"><div class="sg-brand-mark"><i></i></div><span class="sg-brand-name">SHIFTGENIE</span></div>'
    f'<div class="sg-live"><span class="sg-dot" style="background:{_dot};color:{_dot} !important;"></span>'
    f'<span style="color:{P["muted"]} !important;">{_status}</span></div>',
    unsafe_allow_html=True,
)
st.sidebar.caption("Workforce Operations")
page = st.sidebar.radio(
    "Navigate", ["Overview", "Generate", "Schedule", "Validate", "Simulate", "Workforce"], label_visibility="collapsed"
)
st.sidebar.divider()
st.sidebar.radio("Appearance", ["Light", "Dark"], key="theme_radio")
st.sidebar.divider()
st.sidebar.caption("ShiftGenie · Operations Console")

if not _online:
    st.error(f"Backend unavailable at {BACKEND_URL}. Start it with: uvicorn backend.main:app --reload")
    st.stop()

# --------------------------------------------------------------- pages -----

if page == "Overview":
    st.title("Overview")
    show_flash()
    employees = get_employees()
    shifts = get_shifts()
    schedule = st.session_state.get("schedule")
    emp_by_id = {str(e["id"]): e for e in employees}
    shift_by_id = {str(s["id"]): s for s in shifts}

    coverage, hours_by_emp, fully = [], {}, 0
    if schedule:
        for sh in shifts:
            got = len(schedule["assignments"].get(str(sh["id"]), []))
            coverage.append((sh["name"], got, sh["required_staff"]))
            fully += got >= sh["required_staff"]
        for sid, eids in schedule["assignments"].items():
            sh = shift_by_id.get(sid)
            if sh:
                for eid in eids:
                    hours_by_emp[str(eid)] = hours_by_emp.get(str(eid), 0.0) + shift_hours(sh["start_time"], sh["end_time"])
    violations = schedule["violations"] if schedule else []

    cols = st.columns(4)
    with cols[0]:
        metric_card("Employees", len(employees), "in database")
    with cols[1]:
        metric_card("Shifts", len(shifts), "in database")
    with cols[2]:
        if schedule:
            metric_card("Violations", len(violations), "validator result", "success" if not violations else "error")
        else:
            metric_card("Violations", "—", "no schedule checked yet")
    with cols[3]:
        if schedule:
            metric_card(
                "Schedule Status", "Valid" if not violations else "Conflict",
                f"{fully} of {len(shifts)} shifts fully covered", "success" if not violations else "error",
            )
        else:
            metric_card("Schedule Status", "Not generated", "run a schedule check")

    if st.button("Re-run Schedule Check" if schedule else "Run Schedule Check", type="secondary" if schedule else "primary"):
        with st.spinner("Solving and validating..."):
            err = run_generation()
        if err:
            st.error(err)
        else:
            st.rerun()

    left, right = st.columns(2)
    with left:
        section("Workforce by Role")
        role_counts = {}
        for e in employees:
            role_counts[e["role"]] = role_counts.get(e["role"], 0) + 1
        top = max(role_counts.values()) if role_counts else 1
        bars(
            [(r, n / top * 100, str(n), P["primary"]) for r, n in sorted(role_counts.items(), key=lambda kv: -kv[1])],
            "No employees found. Load the demo scenario from the Workforce page.",
        )
    with right:
        section("Schedule Health")
        if not schedule:
            empty_state("No schedule checked yet. Run a schedule check to see validator results.")
        else:
            def _n(key):
                return len([v for v in violations if key in v])

            short = len(shifts) - fully
            rows = [
                ("Coverage", badge("Satisfied", "success") if not short else badge(f"{short} shift(s) short", "warning")),
                ("Availability", badge("Satisfied", "success") if not _n("not available") else badge(f"{_n('not available')} issue(s)", "error")),
                ("Certifications", badge("Satisfied", "success") if not _n("lacks verified certification") else badge(f"{_n('lacks verified certification')} issue(s)", "error")),
                ("Rest", badge("Satisfied", "success") if not _n("insufficient rest") else badge(f"{_n('insufficient rest')} issue(s)", "error")),
                ("Violations", badge("None", "success") if not violations else badge(f"{len(violations)} found", "error")),
            ]
            body = "".join(f'<div class="sg-health-row"><span>{l}</span>{b}</div>' for l, b in rows)
            st.markdown(f'<div class="sg-card">{body}</div>', unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        section("Shift Coverage")
        cov_rows = []
        for name, got, need in coverage:
            full = got >= need
            color = P["success"] if full else (P["warning"] if got else P["error"])
            cov_rows.append((name, (got / need * 100) if need else 100, f'<span style="color:{color};">{got}/{need}</span>', color))
        bars(cov_rows, "No schedule checked yet. Coverage appears after a schedule check.")
    with right:
        section("Scheduled Hours")
        hour_rows = []
        for eid, h in sorted(hours_by_emp.items(), key=lambda kv: -kv[1]):
            e = emp_by_id.get(eid)
            if not e:
                continue
            cap = e["max_weekly_hours"] or 1
            hour_rows.append((f"{e['name']} · {e['role']}", h / cap * 100, f"{h:.0f} / {cap}h", P["secondary"]))
        bars(hour_rows, "No hours to show yet. Hours appear after a schedule check.")

elif page == "Generate":
    st.title("Generate Schedule")
    st.caption("Build a validated roster from your workforce and scheduling requirements.")
    show_flash()
    employees = get_employees()
    shifts = get_shifts()

    section("Workforce & Requirements")
    left, right = st.columns(2)
    role_counts = {}
    for e in employees:
        role_counts[e["role"]] = role_counts.get(e["role"], 0) + 1
    req_roles = sorted({r for sh in shifts for r in sh["required_roles"]})
    req_certs = sorted({c for sh in shifts for c in sh["required_certifications"]})
    with left:
        metric_card("Workforce", f"{len(employees)} employees",
                    " · ".join(f"{n} {r}" for r, n in sorted(role_counts.items(), key=lambda kv: -kv[1])) or "No employees loaded")
    with right:
        slots = sum(sh["required_staff"] for sh in shifts)
        detail = f"{slots} staff slots · roles: {', '.join(req_roles) or 'any'}"
        if req_certs:
            detail += f" · certification: {', '.join(req_certs)}"
        metric_card("Scheduling Requirements", f"{len(shifts)} shifts", detail)
    st.caption("Hard constraints: availability · role and verified certification · weekly-hour limits · "
               "minimum rest · no overlapping shifts · required staffing.")

    section("Action")
    b1, b2 = st.columns(2)
    with b1:
        go = st.button("Generate Schedule", type="primary")
    with b2:
        reset = st.button("Reset & Generate Demo Schedule", type="secondary")
    st.caption("Generate Schedule solves the current workforce and shifts. Reset & Generate restores the synthetic "
               "demo baseline, clears the current roster and solves again.")
    if go or reset:
        with st.spinner("Restoring demo data and solving..." if reset else "Solving and validating..."):
            err = run_generation(reset=reset)
        if err:
            st.error(err)
        else:
            st.rerun()

    section("Result")
    schedule = st.session_state.get("schedule")
    if not schedule:
        empty_state("No schedule generated yet. Click Generate Schedule.")
    else:
        render_generation_result(schedule)
        if schedule["violations"]:
            for v in schedule["violations"]:
                st.write(f"- {v}")
        section("Roster")
        table(roster_rows(schedule, employees, shifts))

    section("Describe Requirements (optional)")
    st.caption("Describe your staffing requirements in plain language and ShiftGenie will build a schedule from them.")
    text = st.text_area(
        "Staffing requirement",
        placeholder="I need 3 cashiers and 1 supervisor every Saturday and Sunday from 4 PM to 10 PM.",
        height=90,
    )
    if st.button("Generate from Requirement", type="secondary"):
        if not text.strip():
            st.warning("Enter a requirement first.")
        else:
            with st.spinner("Building your schedule..."):
                resp = api_post("/requirements/schedule", json={"text": text}, timeout=90)
            if isinstance(resp, Exception) or resp is None:
                st.error("The backend is unavailable. Please try again.")
            elif resp.status_code != 200:
                st.error("We couldn't understand that requirement. Try rephrasing it, or check the AI service.")
            else:
                st.session_state.req_result = resp.json()

    result = st.session_state.get("req_result")
    if result:
        pr = result["parsed_requirement"]
        m = result["metrics"]
        existing = result.get("mode") == "existing_shifts"
        ignored = {t.lower() for t in result.get("ignored_terms", [])}
        roles = [r for r in (pr.get("roles") or []) if r.lower() not in ignored]
        certs = [c for c in (pr.get("required_certifications") or []) if c.lower() not in ignored]

        if pr.get("shift_start_time") or pr.get("shift_end_time"):
            window = f"{pr.get('shift_start_time') or '—'} – {pr.get('shift_end_time') or '—'}"
        else:
            window = "Existing shifts" if existing else "Default shift hours"
        constraints = [f"Certified: {', '.join(certs)}"] if certs else []
        if pr.get("max_hours"):
            constraints.append(f"Max {pr['max_hours']}h / week")
        if pr.get("min_rest_hours"):
            constraints.append(f"Min rest {pr['min_rest_hours']}h")
        constraints.append("Availability & weekly hours enforced")

        section("Requirement Preview")
        preview = [
            ("Staff per shift", str(pr["staffing_count"]) if pr.get("staffing_count") else "As defined per shift"),
            ("Roles", ", ".join(roles) if roles else "Any eligible employee"),
            ("Days", ", ".join(pr.get("days") or []) or ("Existing schedule" if existing else "All days")),
            ("Time window", window),
            ("Constraints", " · ".join(constraints)),
        ]
        for col, (label, value) in zip(st.columns(5), preview):
            col.markdown(
                f'<div class="sg-card"><div class="sg-metric-label">{html.escape(label)}</div>'
                f'<div style="font-weight:600;margin-top:6px;font-size:0.95rem;">{html.escape(value)}</div></div>',
                unsafe_allow_html=True,
            )

        section("Requirement Result")
        total = m["shifts_evaluated"]
        short = len(m["understaffed_shifts"])
        viol = result["violations"]
        ok = result["feasible"]
        detail = ""
        if not ok and short:
            detail += f"<div style='margin-top:6px;'>{short} of {total} shifts remain understaffed.</div>"
        if not ok and viol:
            detail += f"<div style='margin-top:6px;'>{len(viol)} constraint violation(s) detected.</div>"
        status_card("Schedule Generated" if ok else "Schedule Could Not Be Fully Satisfied",
                    f"{total} shifts evaluated · {total - short} covered · {len(viol)} violation(s) · solved with {result.get('solver', 'OR-Tools')}",
                    "ok" if ok else "bad", detail)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Coverage", f"{m['coverage_ratio'] * 100:.0f}%", f"{m['assigned_staff_total']}/{m['required_staff_total']} slots")
        with c2:
            metric_card("Shifts Evaluated", total)
        with c3:
            metric_card("Understaffed", short, kind="warning" if short else "success")
        with c4:
            metric_card("Violations", len(viol), kind="error" if viol else "success")

        def _label(d):
            return f"{d['day'][:3]} {d['start']}–{d['end']}"

        under = [d for d in result.get("shift_details", []) if d["assigned"] < d["required"]]
        if under:
            section("Why?")
            none_elig = [d for d in under if d["eligible"] == 0]
            limited = [d for d in under if d["eligible"] > 0]
            lines = []
            if none_elig:
                lines.append(
                    f"No eligible employees are available for {len(none_elig)} shift(s): "
                    + ", ".join(_label(d) for d in none_elig[:8]) + ("…" if len(none_elig) > 8 else "")
                    + ". Availability, role or certification requirements cannot be met."
                )
            if limited:
                lines.append(
                    f"Eligible employees exist for {len(limited)} shift(s) but weekly-hour, rest or one-shift-per-day limits "
                    "prevent full coverage: " + ", ".join(_label(d) for d in limited[:8]) + ("…" if len(limited) > 8 else "") + "."
                )
            body = "".join(f"<div style='margin-bottom:6px;'>{html.escape(x)}</div>" for x in lines)
            st.markdown(f'<div class="sg-card">{body}</div>', unsafe_allow_html=True)
        if viol:
            for v in viol:
                st.write(f"- {v}")
        if result.get("ignored_terms"):
            st.caption("Generic terms not treated as filters: " + ", ".join(result["ignored_terms"]))

        with st.expander("Shift assignments", expanded=False):
            emp_names = {str(e["id"]): e["name"] for e in employees}
            table([
                {"Shift": _label(d), "Required": d["required"], "Assigned": d["assigned"],
                 "Employees": ", ".join(emp_names.get(str(i), str(i)) for i in result["assignments"].get(d["id"], [])) or "—"}
                for d in result.get("shift_details", [])
            ])
        with st.expander("Technical Details", expanded=False):
            st.caption(
                "The requirement is interpreted by Gemini into structured fields. The schedule is produced by the "
                "OR-Tools optimizer (with a constraint-respecting greedy fallback) and verified by an independent validator. "
                f"Solver: {result.get('solver', 'OR-Tools')}. Targets: "
                f"{'existing database shifts' if existing else 'shifts generated from the requirement'}."
            )
            st.json(pr)

elif page == "Schedule":
    st.title("Schedule")
    show_flash()
    if st.button("Regenerate Schedule", type="primary"):
        with st.spinner("Solving and validating..."):
            err = run_generation()
        if err:
            st.error(err)
        else:
            st.rerun()

    schedule = st.session_state.get("schedule")
    if not schedule:
        empty_state("No schedule generated yet. Click 'Regenerate Schedule' above.")
    else:
        employees = get_employees()
        shifts = get_shifts()
        rows = roster_rows(schedule, employees, shifts)
        section("Roster Summary")
        c = st.columns(4)
        with c[0]:
            metric_card("Shifts", len(shifts))
        with c[1]:
            metric_card("Assignments", sum(1 for r in rows if r["Status"] == "Assigned"))
        with c[2]:
            unf = sum(1 for r in rows if r["Status"] == "Unfilled")
            metric_card("Unfilled Slots", unf, "no one assigned", "warning" if unf else "success")
        with c[3]:
            metric_card("Scheduled Hours", f"{sum(r['Hours'] for r in rows if r['Status'] == 'Assigned'):.0f}h")
        section("Weekly Roster")
        table(rows)

elif page == "Validate":
    st.title("Validate")
    schedule = st.session_state.get("schedule")
    if not schedule:
        empty_state("No schedule to validate yet. Generate one on the Schedule page.")
    else:
        violations = schedule["violations"]
        st.subheader("Schedule Health")
        if not violations:
            st.markdown(f"### {badge('VALID', 'success')}", unsafe_allow_html=True)
        else:
            st.markdown(f"### {badge('CONFLICT DETECTED', 'error')}", unsafe_allow_html=True)

        checks = {
            "Availability": "not available",
            "Coverage": "overstaffed",
            "Required Roles": "lacks required role",
            "Certifications": "lacks verified certification",
            "Rest Periods": "insufficient rest",
            "Weekly Hours": "exceeds max weekly hours",
        }
        cols = st.columns(3)
        for i, (label, key) in enumerate(checks.items()):
            hits = [v for v in violations if key in v]
            with cols[i % 3]:
                st.markdown(
                    f'<div class="sg-card sg-check {"ok" if not hits else "bad"}"><div class="sg-check-label">{label}</div>{badge("Satisfied", "success") if not hits else badge(f"{len(hits)} issue(s)", "error")}</div>',
                    unsafe_allow_html=True,
                )

        if violations:
            st.subheader("Reported Violations")
            for v in violations:
                st.write(f"- {v}")

        st.subheader("Employee Workload")
        employees = {str(e["id"]): e for e in get_employees()}
        shifts = {str(s["id"]): s for s in get_shifts()}
        workload = {}
        for shift_id, emp_ids in schedule["assignments"].items():
            s = shifts.get(shift_id)
            if not s:
                continue
            for eid in emp_ids:
                w = workload.setdefault(eid, {"hours": 0.0, "shifts": 0})
                w["hours"] += shift_hours(s["start_time"], s["end_time"])
                w["shifts"] += 1
        rows = [
            {
                "Employee": employees.get(eid, {}).get("name", eid),
                "Role": employees.get(eid, {}).get("role", "—"),
                "Total Hours": w["hours"],
                "Shifts": w["shifts"],
                "Status": "Assigned",
            }
            for eid, w in workload.items()
        ]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            empty_state("No employees were assigned in this schedule.")

elif page == "Simulate":
    st.title("Simulate")
    st.caption("Test how your workforce responds to change. Each scenario is re-optimized and independently validated.")
    SCEN = {
        "Employee calls in sick": "employee_sick",
        "Employee becomes unavailable": "employee_unavailable",
        "Multiple employees unavailable": "multiple_unavailable",
        "Supervisor unavailable": "supervisor_unavailable",
        "Weekend demand increases": "weekend_demand",
        "Additional staffing requirement": "additional_staffing",
        "Reduce staff capacity": "reduce_capacity",
    }
    people = get_employees()
    emp_opts = {f"{e['name']} — {e['role']}": str(e["id"]) for e in people}
    sup_opts = {k: v for k, v in emp_opts.items() if k.endswith("— Supervisor")}
    AUTO = "Most-scheduled (automatic)"

    section("Scenario")
    choice = st.selectbox("Scenario", list(SCEN), label_visibility="collapsed")
    key = SCEN[choice]
    params = {}
    if key in ("employee_sick", "employee_unavailable"):
        who = st.selectbox("Employee", [AUTO] + list(emp_opts), key=f"sim_emp_{key}")
        if who != AUTO:
            params["employee_ids"] = [emp_opts[who]]
        if key == "employee_unavailable":
            days = st.multiselect("Unavailable on (leave empty for the whole week)", DAYS, key="sim_days_unavail")
            if days:
                params["days"] = days
    elif key == "multiple_unavailable":
        who = st.multiselect("Employees (leave empty to use the two most-scheduled)", list(emp_opts), key="sim_multi")
        if who:
            params["employee_ids"] = [emp_opts[w] for w in who]
    elif key == "supervisor_unavailable":
        who = st.selectbox("Supervisor", [AUTO] + list(sup_opts), key="sim_sup")
        if who != AUTO:
            params["employee_ids"] = [sup_opts[who]]
    elif key == "weekend_demand":
        params["percent"] = st.slider("Weekend demand increase (%)", 5, 100, 20, 5, key="sim_pct")
    elif key == "additional_staffing":
        params["extra_staff"] = int(st.number_input("Extra staff required per shift", 1, 5, 1, key="sim_extra"))
        days = st.multiselect("On days (leave empty for every day)", DAYS, key="sim_days_extra")
        if days:
            params["days"] = days
    elif key == "reduce_capacity":
        params["percent"] = st.slider("Weekly-hour capacity reduction (%)", 10, 80, 40, 10, key="sim_cap")

    if st.button("Run Simulation", type="primary"):
        with st.spinner("Re-optimizing the schedule..."):
            resp = api_post("/schedule/simulate", json={"scenario": key, "params": params}, timeout=120)
        if isinstance(resp, Exception) or resp is None:
            st.error("The backend is unavailable. Please try again.")
        elif resp.status_code != 200:
            st.error("The simulation could not be run.")
        else:
            st.session_state.sim_result = resp.json()
            st.session_state.sim_scenario_key = key
            st.session_state.sim_params = params
            st.session_state.pop("resolve_result", None)

    result = st.session_state.get("sim_result")
    if not result:
        empty_state("No simulation run yet. Choose a scenario and click 'Run Simulation'.")
    elif not result["available"]:
        st.warning(result["message"])
    else:
        imp, before, after = result["impact"], result["before"], result["after"]
        section("Feasibility")
        rec = result["recoverable"]
        status_card(
            "Recoverable" if rec else "Infeasible",
            result["explanation"], "ok" if rec else "bad",
            f'<div class="sg-muted" style="margin-top:8px;">{html.escape(result["scenario"])} — {html.escape(result["note"])}'
            f' Solver: {html.escape(result["solver"])} · independent validation {"passed" if result["valid"] else "failed"}.</div>',
        )

        section("Impact")
        c = st.columns(3)
        aff = imp["affected_employees"]
        with c[0]:
            metric_card("Employees Affected", len(aff) if aff else "None", ", ".join(f"{a['name']} ({a['role']})" for a in aff[:4]) or "Requirement change")
        with c[1]:
            metric_card("Affected Shifts", len(imp["affected_shifts"]), ", ".join(imp["affected_shifts"][:2]) + ("…" if len(imp["affected_shifts"]) > 2 else ""))
        with c[2]:
            metric_card("Affected Roles", len(imp["affected_roles"]), ", ".join(imp["affected_roles"]) or "—")
        cb, ca = imp["capacity_before"], imp["capacity_after"]
        table([
            {"Metric": "Staff required", "Before": cb["staff_required"], "After": ca["staff_required"]},
            {"Metric": "Staff available (qualified)", "Before": cb["staff_available"], "After": ca["staff_available"]},
            {"Metric": "Staff shortfall", "Before": cb["staff_shortfall"], "After": ca["staff_shortfall"]},
            {"Metric": "Required labor hours", "Before": f"{cb['hours_required']:.0f}h", "After": f"{ca['hours_required']:.0f}h"},
            {"Metric": "Available labor hours", "Before": f"{cb['hours_available']:.0f}h", "After": f"{ca['hours_available']:.0f}h"},
            {"Metric": "Labor-hour shortfall", "Before": f"{cb['hours_shortfall']:.0f}h", "After": f"{ca['hours_shortfall']:.0f}h"},
            {"Metric": "Unfilled slots after re-optimization", "Before": before["required_staff_total"] - before["assigned_staff_total"], "After": imp["unfilled_after"]},
            {"Metric": "Coverage", "Before": f"{imp['coverage_before']:.0%}", "After": f"{imp['coverage_after']:.0%}"},
        ])
        for rc in imp["role_coverage"]:
            lost = f" Lost on: {', '.join(rc['lost'])}." if rc["lost"] else ""
            st.markdown(
                f'<div class="sg-card"><b>{html.escape(rc["role"])} coverage</b>: {rc["before"]} shift(s) → {rc["after"]} shift(s).'
                f'<span class="sg-muted">{html.escape(lost)}</span></div>', unsafe_allow_html=True)

        section("Schedule Changes (Before → After)")
        render_changes(result["changes"], partial=not rec)
        if result.get("roster"):
            if rec:
                section("New Schedule")
                table(result["roster"])
            else:
                with st.expander("Best achievable roster (partial coverage)", expanded=False):
                    table(result["roster"])

        if not rec:
            if result["shortfalls"]:
                section("Shortfall")
                table([{"Shift": r["shift"], "Roles": ", ".join(r["roles"]), "Required": r["required"],
                        "Qualified available": r["qualified_available"], "Assigned": r["assigned"], "Why": r["reason"]}
                       for r in result["shortfalls"]])
            options = result.get("resolution_options", [])
            if options:
                section("Resolution Options")
                for o in options:
                    st.markdown(
                        f'<div class="sg-card"><b>{html.escape(o["label"])}</b>'
                        f'<div class="sg-muted">{html.escape(o["description"])}</div>'
                        f'<div style="margin-top:6px;">Expected impact: {html.escape(o["expected_impact"])}</div></div>',
                        unsafe_allow_html=True)
                labels = {o["label"]: o["key"] for o in options}
                pick = st.radio("Choose a resolution", list(labels), key="sim_resolution")
                st.caption("Applying a resolution re-runs the optimizer and the independent validator. "
                           "Nothing is saved to your workforce data.")
                if st.button("Apply Resolution", type="primary"):
                    with st.spinner("Applying resolution and re-validating..."):
                        resp = api_post("/schedule/resolve", json={
                            "scenario": st.session_state.sim_scenario_key, "resolution": labels[pick],
                            "params": st.session_state.get("sim_params") or {}}, timeout=120)
                    if isinstance(resp, Exception) or resp is None:
                        st.error("The backend is unavailable. Please try again.")
                    elif resp.status_code != 200:
                        st.error("The resolution could not be applied.")
                    else:
                        st.session_state.resolve_result = resp.json()

            rr = st.session_state.get("resolve_result")
            if rr and rr.get("available"):
                section("Resolution Result")
                a2 = rr["after"]
                if rr["verified"]:
                    status_card("Resolution Verified", f"{rr['resolution']} — the schedule is now feasible and passed independent validation.", "ok")
                else:
                    status_card("Resolution Not Sufficient",
                                f"{rr['resolution']} did not produce a fully valid schedule. The remaining conflict is shown below.", "bad")
                c = st.columns(4)
                with c[0]:
                    metric_card("Coverage", f"{a2['assigned_staff_total']}/{a2['required_staff_total']}",
                                kind="success" if rr["verified"] else "warning")
                with c[1]:
                    metric_card("Violations", a2["violations"], kind="success" if not a2["violations"] else "error")
                with c[2]:
                    metric_card("Shifts Changed", rr["changes"]["counts"]["shifts_changed"])
                with c[3]:
                    metric_card("Employees Reassigned", rr["changes"]["counts"]["employees_reassigned"])
                if a2["required_staff_total"] < before["required_staff_total"]:
                    st.caption(f"Required staff was lowered from {before['required_staff_total']} to {a2['required_staff_total']}.")
                if rr["verified"]:
                    render_changes(rr["changes"], counts=False)
                    section("Updated Schedule")
                    table(rr["roster"])
                elif rr.get("remaining_shortfalls"):
                    table([{"Shift": r["shift"], "Required": r["required"], "Qualified available": r["qualified_available"],
                            "Assigned": r["assigned"], "Why": r["reason"]} for r in rr["remaining_shortfalls"]])

        with st.expander("Technical Details", expanded=False):
            st.caption(f"Solver: {result['solver']}. Fallback: {result.get('fallback_reason') or 'not needed'}.")
            st.json({"scenario_params": st.session_state.get("sim_params") or {}, "summary": {"before": before, "after": after}})

elif page == "Workforce":
    st.title("Workforce")
    st.caption("Demo Scenario — Synthetic Retail Workforce Data (fictional, for demo purposes only)")
    show_flash()
    if st.button("Load Demo Scenario", type="primary"):
        r = api_post("/demo/load", timeout=90)
        if not isinstance(r, Exception) and r is not None and r.status_code == 200:
            d = r.json()
            refresh_data()
            flash("success", f"Demo scenario loaded: {d['employees_added']} employees added, "
                             f"{d['employees_skipped']} already present; {d['shifts_added']} shifts added.")
            st.rerun()
        else:
            st.error(f"Failed to load demo scenario: {r}")

    def employee_form(prefix, defaults=None):
        defaults = defaults or {}
        name = st.text_input("Name", value=defaults.get("name", ""), key=f"{prefix}_name")
        role = st.text_input("Role", value=defaults.get("role", ""), key=f"{prefix}_role")
        max_hours = st.number_input(
            "Max Weekly Hours", min_value=1, max_value=80,
            value=defaults.get("max_weekly_hours", 40), key=f"{prefix}_hours",
        )
        preferred_shift = st.text_input(
            "Preferred Shift", value=defaults.get("preferred_shift") or "", key=f"{prefix}_pref"
        )
        skills_default = ", ".join(s["name"] for s in defaults.get("skills", []))
        skills = st.text_input("Skills (comma-separated)", value=skills_default, key=f"{prefix}_skills")

        st.caption("Certifications (one per line: name,status,source)")
        certs_default = "\n".join(
            f"{c['name']},{c['verification_status']},{c.get('verification_source') or ''}"
            for c in defaults.get("certifications", [])
        )
        certs_text = st.text_area("Certifications", value=certs_default, key=f"{prefix}_certs")

        st.caption("Availability (one per line: day,start,end e.g. Monday,09:00,17:00)")
        avail_default = "\n".join(
            f"{a['day_of_week']},{a['start_time']},{a['end_time']}"
            for a in defaults.get("availabilities", [])
        )
        avail_text = st.text_area("Availability", value=avail_default, key=f"{prefix}_avail")

        skills_list = [s.strip() for s in skills.split(",") if s.strip()]
        certifications = []
        for line in certs_text.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if not parts or not parts[0]:
                continue
            certifications.append({
                "name": parts[0],
                "verification_status": parts[1] if len(parts) > 1 and parts[1] else "unverified",
                "verification_source": parts[2] if len(parts) > 2 and parts[2] else None,
            })
        availability = []
        for line in avail_text.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 3 and parts[0]:
                availability.append({"day_of_week": parts[0], "start_time": parts[1], "end_time": parts[2]})

        return {
            "name": name, "role": role, "max_weekly_hours": int(max_hours),
            "preferred_shift": preferred_shift or None, "skills": skills_list,
            "certifications": certifications, "availability": availability,
        }

    with st.expander("Add Employee"):
        with st.form("add_employee_form"):
            new_employee = employee_form("add")
            if st.form_submit_button("Add Employee", type="primary"):
                if not new_employee["name"] or not new_employee["role"]:
                    st.error("Name and role are required.")
                else:
                    r = api_post("/employees", json=new_employee)
                    if not isinstance(r, Exception) and r is not None and r.status_code == 200:
                        refresh_data()
                        flash("success", f"Added {new_employee['name']}.")
                        st.rerun()
                    else:
                        st.error(f"Failed to add employee: {r}")

    st.subheader("Current Employees")
    employees = get_employees()
    if not employees and not st.session_state.get("_fetch_failed"):
        empty_state("No employees stored yet.")
    editing = st.session_state.get("editing_emp")
    for emp in employees:
        with st.expander(f"{emp['name']} — {emp['role']} (id {emp['id']})", expanded=(editing == emp["id"])):
            st.write(f"Max weekly hours: {emp['max_weekly_hours']}")
            st.write(f"Preferred shift: {emp['preferred_shift'] or '-'}")
            st.write("Skills: " + (", ".join(s["name"] for s in emp["skills"]) or "-"))
            for c in emp["certifications"]:
                st.write(f"Certification: {c['name']} ({c['verification_status']})")
            for a in emp["availabilities"]:
                st.write(f"Availability: {a['day_of_week']} {a['start_time']}-{a['end_time']}")

            if editing != emp["id"]:
                if st.button("Edit", key=f"edit_btn_{emp['id']}"):
                    st.session_state["editing_emp"] = emp["id"]
                    st.rerun()
            else:
                st.markdown("**Edit**")
                with st.form(f"edit_form_{emp['id']}"):
                    updated = employee_form(f"edit_{emp['id']}", defaults=emp)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.form_submit_button("Save Changes", type="primary"):
                            r = requests.put(f"{BACKEND_URL}/employees/{emp['id']}", json=updated, timeout=30)
                            if r.status_code == 200:
                                st.session_state.pop("editing_emp", None)
                                refresh_data()
                                flash("success", "Updated.")
                                st.rerun()
                            else:
                                st.error(f"Failed to update: {r.text}")
                    with col2:
                        if st.form_submit_button("Delete Employee"):
                            r = requests.delete(f"{BACKEND_URL}/employees/{emp['id']}", timeout=30)
                            if r.status_code == 200:
                                st.session_state.pop("editing_emp", None)
                                refresh_data()
                                flash("success", "Deleted.")
                                st.rerun()
                            else:
                                st.error(f"Failed to delete: {r.text}")
                    with col3:
                        if st.form_submit_button("Close"):
                            st.session_state.pop("editing_emp", None)
                            st.rerun()
