"""Streamlit operator console for manual, recommendation-only triage."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from incidentrag.approval.ui.api_client import (
    IncidentRAGAPIClient,
    IncidentRAGAPIError,
)

load_dotenv()

API_URL = os.getenv("INCIDENTRAG_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("INCIDENTRAG_API_KEY", "")
client = IncidentRAGAPIClient(API_URL, API_KEY)

st.set_page_config(page_title="IncidentRAG", page_icon="🚨", layout="wide")
st.markdown(
    """
    <style>
      .block-container {max-width: 1180px; padding-top: 2.5rem; padding-bottom: 4rem;}
      [data-testid="stMetric"] {background: #151922; border: 1px solid #2b3240;
        border-radius: 12px; padding: 14px 18px;}
      .issue-meta {color: #9aa4b2; font-size: .88rem; margin-bottom: .65rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _show_error(prefix: str, exc: IncidentRAGAPIError) -> None:
    status = f" (HTTP {exc.status_code})" if exc.status_code else ""
    st.error(f"{prefix}{status}: {exc}")
    if exc.status_code == 503:
        st.info(
            "Confirm that the backend can reach api.github.com and openrouter.ai, "
            "then restart the backend after updating .env."
        )


def _render_action(action: dict[str, Any], *, remediation: bool) -> None:
    risk = str(action.get("risk_level", "unknown")).lower()
    title = action.get("description", "Recommended action")
    heading = f"**{title}** · `{risk.upper()} risk`" if remediation else f"**{title}**"
    st.markdown(heading)
    if command := action.get("command"):
        st.code(command, language="bash")
    details: list[str] = []
    if action.get("expected_impact"):
        details.append(f"Expected impact: {action['expected_impact']}")
    if action.get("estimated_duration_seconds") is not None:
        details.append(f"Estimated duration: {action['estimated_duration_seconds']} seconds")
    if details:
        st.caption(" · ".join(details))
    if rollback := action.get("rollback_command"):
        with st.expander("Rollback command"):
            st.code(rollback, language="bash")


def _render_assessment(result: dict[str, Any]) -> None:
    source = result.get("source_issue", {})
    processing = result.get("processing", {})
    diagnosis = result.get("ai_hypotheses", {}).get("likely_diagnosis", {})

    st.divider()
    st.caption("COMPLETED ASSESSMENT")
    st.header(f"Issue #{source.get('number', '—')}: {source.get('title', 'Analysis')}")
    if source.get("html_url"):
        st.link_button("View source issue on GitHub", source["html_url"])

    confidence = float(result.get("confidence") or 0)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Confidence", f"{confidence:.0%}")
    metric_columns[1].metric("Evidence", len(result.get("retrieved_evidence", [])))
    metric_columns[2].metric(
        "Investigation steps", len(result.get("recommended_investigation", []))
    )
    metric_columns[3].metric(
        "Processing time", f"{float(processing.get('duration_ms') or 0) / 1000:.1f}s"
    )

    st.subheader("Likely diagnosis")
    st.write(diagnosis.get("statement", "No diagnosis was returned."))
    claim_columns = st.columns(2)
    claim_columns[0].progress(confidence, text="Overall confidence")
    if diagnosis.get("verified"):
        claim_columns[1].success("Grounding verified")
    else:
        claim_columns[1].warning("Grounding needs review")

    evidence_tab, investigate_tab, remediate_tab, details_tab = st.tabs(
        ["Evidence", "Investigation", "Remediation", "Processing details"]
    )
    with evidence_tab:
        evidence = result.get("retrieved_evidence", [])
        if not evidence:
            st.warning("No runbook evidence was returned. Review this result before acting.")
        for index, item in enumerate(evidence, 1):
            st.markdown(f"**{index}. {item.get('header_breadcrumb', 'Runbook evidence')}**")
            st.info(item.get("excerpt", ""))
            st.caption(
                f"Runbook: {item.get('runbook_id', 'unknown')} · "
                f"Relevance: {item.get('relevance', 'unknown')}"
            )
    with investigate_tab:
        actions = result.get("recommended_investigation", [])
        if not actions:
            st.write("No investigation steps were generated.")
        for action in actions:
            _render_action(action, remediation=False)
    with remediate_tab:
        st.warning(
            "Recommendations are read-only. Review and approve any operational change "
            "through your normal change process."
        )
        actions = result.get("proposed_remediation", [])
        if not actions:
            st.write("No remediation was proposed.")
        for action in actions:
            _render_action(action, remediation=True)
        if result.get("human_approval_required"):
            st.error("Human approval is required before executing proposed remediation.")
    with details_tab:
        st.json(result.get("facts_extracted", {}))
        for stage in processing.get("stages", []):
            st.write(f"✓ {stage.get('message', stage.get('stage', 'Completed'))}")
        missing = result.get("additional_information_required", [])
        if missing:
            st.markdown("**Additional information that would improve confidence**")
            for item in missing:
                st.write(f"- {item}")

    st.caption(result.get("disclaimer", ""))


st.title("IncidentRAG operator console")
st.caption(
    "Select a public Argo CD issue and run an evidence-grounded incident analysis. "
    "Operational execution remains disabled by default."
)

try:
    health = client.health()
    github = client.github_status()
    backend_online = health.get("status") == "ok"
except IncidentRAGAPIError as exc:
    backend_online = False
    github = {}
    _show_error("Backend connection failed", exc)

with st.sidebar:
    st.subheader("System status")
    if backend_online:
        st.success("Backend connected")
    else:
        st.error("Backend unavailable")
    st.markdown(f"**Repository**  \n`{github.get('repository', 'not configured')}`")
    authentication = "Authenticated" if github.get("authenticated") else "Public rate limit"
    st.markdown(f"**GitHub access**  \n{authentication}")
    st.caption(f"Backend: {API_URL}")

with st.form("issue-search"):
    search_columns = st.columns([2, 1, 0.55])
    keyword = search_columns[0].text_input(
        "Search terms", value="repo-server", placeholder="timeout, sync, TLS..."
    )
    component = search_columns[1].text_input(
        "Component label", placeholder="repo-server"
    )
    limit = search_columns[2].selectbox("Results", [1, 2], index=1)
    search = st.form_submit_button(
        "Find suitable issues", type="primary", use_container_width=True
    )

if search:
    st.session_state.pop("assessment", None)
    try:
        with st.spinner("Searching the configured GitHub repository..."):
            response = client.find_issues(
                keyword=keyword.strip(), component=component.strip(), limit=limit
            )
        st.session_state["issues"] = response.get("issues", [])
        st.session_state["repository"] = response.get("repository", "argoproj/argo-cd")
    except IncidentRAGAPIError as exc:
        st.session_state["issues"] = []
        _show_error("Issue search failed", exc)

issues = st.session_state.get("issues", [])
if search and not issues:
    st.warning("No suitable open bug issues matched those filters. Try broader search terms.")

if issues:
    st.subheader(f"Suitable issues from {st.session_state.get('repository', 'GitHub')}")
    selected = st.radio(
        "Select an issue to analyze",
        options=[issue["number"] for issue in issues],
        format_func=lambda number: next(
            f"#{issue['number']} — {issue['title']}"
            for issue in issues
            if issue["number"] == number
        ),
        label_visibility="collapsed",
    )
    selected_issue = next(issue for issue in issues if issue["number"] == selected)
    with st.container(border=True):
        st.subheader(f"#{selected_issue['number']} — {selected_issue['title']}")
        labels = " · ".join(selected_issue.get("labels", [])) or "No labels"
        st.markdown(
            f"<div class='issue-meta'>{labels} · suitability "
            f"{float(selected_issue.get('suitability_score') or 0):.0f}/100</div>",
            unsafe_allow_html=True,
        )
        reasons = selected_issue.get("selection_explanation", [])
        if reasons:
            st.write("Selected because " + ", ".join(reasons[:4]) + ".")
        preview = selected_issue.get("body", "").strip()
        if preview:
            with st.expander("Issue description"):
                st.write(preview)
        link_column, analyze_column = st.columns([1, 3])
        if selected_issue.get("html_url"):
            link_column.link_button(
                "Open on GitHub", selected_issue["html_url"], use_container_width=True
            )
        analyze = analyze_column.button(
            "Analyze selected issue", type="primary", use_container_width=True
        )
    if analyze:
        try:
            with st.status("Running IncidentRAG analysis...", expanded=True) as status:
                st.write("Fetching and sanitizing the selected GitHub issue")
                st.write("Retrieving relevant runbook evidence")
                st.write("Generating and verifying a structured assessment")
                result = client.analyze_issue(selected)
                status.update(label="Analysis complete", state="complete", expanded=False)
            st.session_state["assessment"] = result
        except IncidentRAGAPIError as exc:
            _show_error("Analysis failed", exc)

if assessment := st.session_state.get("assessment"):
    _render_assessment(assessment)
