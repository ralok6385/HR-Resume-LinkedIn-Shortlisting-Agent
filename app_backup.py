"""HR Resume Shortlisting Agent — Streamlit UI with all 4 working tabs."""
import sys, os, json, time, io, tempfile, logging
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent))
from config import LLMConfig, EmbeddingConfig, LLMProvider, SAMPLE_RESUMES_DIR, DATA_DIR, OUTPUT_DIR
from agent import ShortlistingAgent
from reports.generator import ReportGenerator

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Recruiter Command Center", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

# ── CSS ──
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,.stApp{font-family:'Inter',sans-serif;background:#090d16!important;color:#e2e8f0}
.block-container{padding-top:1rem!important}
[data-testid="stSidebar"]{background:#05080f!important;border-right:1px solid #131929}
[data-testid="stSidebar"] label{color:#64748b!important;font-size:.8rem!important}
[data-testid="stSidebar"] h3{color:#94a3b8!important;font-size:.9rem!important}
[data-testid="stSidebar"] hr{border-color:#131929!important}
textarea{background:#0c1018!important;color:#e2e8f0!important;border:1px solid #1a2235!important;border-radius:10px!important}
textarea:focus{border-color:#4f46e5!important;box-shadow:0 0 0 3px rgba(79,70,229,.12)!important}
[data-testid="stTextArea"]>div>div>textarea{background:#0c1018!important;color:#e2e8f0!important}
[data-testid="stTextInput"]>div>div>input{background:#0c1018!important;color:#e2e8f0!important;border:1px solid #1a2235!important;border-radius:10px!important}
[data-testid="stSelectbox"]>div>div{background:#0c1018!important;color:#e2e8f0!important;border:1px solid #1a2235!important;border-radius:10px!important}
[data-testid="stFileUploader"]>div{background:#0c1018!important;border:1.5px dashed #1e2d45!important;border-radius:12px!important}
[data-testid="stFileUploader"] button{background:#131929!important;color:#64748b!important;border:1px solid #1e2d45!important;border-radius:8px!important}
[data-testid="stFileUploader"] p,[data-testid="stFileUploader"] span,[data-testid="stFileUploader"] small{color:#475569!important}
[data-testid="stFileUploaderDropzone"]{background:#0c1018!important;border:none!important}
[data-testid="stTabs"] [role="tablist"]{background:#0c1018;border-bottom:1px solid #131929}
[data-testid="stTabs"] button[role="tab"]{background:transparent!important;color:#475569!important;font-weight:600!important;border:none!important;border-bottom:2px solid transparent!important}
[data-testid="stTabs"] button[role="tab"]:hover{color:#e2e8f0!important}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#818cf8!important;border-bottom-color:#818cf8!important}
.stButton>button{background:#0f1623!important;color:#64748b!important;border:1px solid #1a2235!important;border-radius:10px!important;font-weight:600!important}
.stButton>button:hover{background:#131929!important;color:#e2e8f0!important;border-color:#4f46e5!important}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#4f46e5,#7c3aed)!important;color:white!important;border:none!important;font-weight:700!important}
.stDownloadButton>button{background:#0f1623!important;color:#64748b!important;border:1px solid #1a2235!important;border-radius:10px!important;font-weight:600!important}
.stDownloadButton>button:hover{border-color:#4f46e5!important;color:#e2e8f0!important}
[data-testid="stProgress"]>div>div{background:#131929!important;border-radius:6px!important}
[data-testid="stProgress"]>div>div>div{background:linear-gradient(90deg,#6366f1,#8b5cf6)!important;border-radius:6px!important}
[data-testid="stExpander"]{background:#0c1018!important;border:1px solid #131929!important;border-radius:12px!important}
[data-testid="stExpander"] summary{color:#64748b!important;font-weight:600!important}
[data-testid="stExpander"] summary:hover{color:#e2e8f0!important}
[data-testid="stAlert"]{background:#0c1018!important;border-radius:10px!important;border-left:3px solid #4f46e5!important}
[data-testid="stAlert"] p{color:#64748b!important}
[data-testid="stMetric"]{background:#0c1018;border:1px solid #131929;border-radius:12px;padding:.75rem}
[data-testid="stMetricValue"]{color:#818cf8!important;font-weight:800!important}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:#090d16}::-webkit-scrollbar-thumb{background:#1a2235;border-radius:3px}
</style>""", unsafe_allow_html=True)

# ── Session State Init ──
for k, v in [("results", None), ("override_log", []), ("agent", None), ("ranked", None), ("jd_parsed", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ──
with st.sidebar:
    st.markdown("### ⚙️ LLM Configuration")
    provider = st.selectbox("Provider", ["claude", "gemini", "openai"], index=0)
    if provider == "claude":
        api_key = st.text_input("Anthropic API Key", type="password", value=os.getenv("ANTHROPIC_API_KEY", ""))
        model = st.selectbox("Model", ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"])
    elif provider == "gemini":
        api_key = st.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
        model = st.selectbox("Model", ["gemini-2.0-flash", "gemini-1.5-pro"])
    else:
        api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        model = st.selectbox("Model", ["gpt-4o", "gpt-4o-mini"])
    use_embeddings = st.checkbox("Semantic Matching", value=False)
    st.markdown("---")
    st.markdown("### 📂 Demo Data")
    use_sample = st.checkbox("Load sample JD & resumes", value=True)
    if st.session_state.results:
        st.markdown("---")
        st.metric("Candidates Scored", len(st.session_state.results))

# ── Header ──
st.markdown("""<div style="background:linear-gradient(180deg,#05080f,#090d16);border-bottom:1px solid #131929;
padding:1.25rem 1.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem">
<div style="width:8px;height:8px;border-radius:50%;background:#4f46e5;box-shadow:0 0 8px #4f46e5aa"></div>
<div><div style="font-size:.6rem;font-weight:700;letter-spacing:.18em;color:#374151;text-transform:uppercase">HR Resume & LinkedIn Shortlisting Agent</div>
<div style="font-size:1.5rem;font-weight:800;color:#f1f5f9;letter-spacing:-.025em">Recruiter Command Center</div></div>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📝 Input", "📊 Results", "🔧 Override", "📄 Report"])

# ════════════════════════════════════════════════════════════════
# TAB 1 — INPUT
# ════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("""<div style="background:linear-gradient(135deg,#0c1018,#0f172a,#111c30);border:1px solid #1e2d45;
    border-radius:18px;padding:2.25rem 2.5rem;margin-bottom:1.5rem;position:relative;overflow:hidden">
    <div style="font-size:.62rem;font-weight:700;letter-spacing:.18em;color:#6366f1;text-transform:uppercase;margin-bottom:.75rem">✦ AI Screening Workspace</div>
    <div style="font-size:1.9rem;font-weight:800;color:#f1f5f9;line-height:1.2;margin-bottom:1.5rem">Rank candidates with transparent evidence<br>& full HR control.</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;padding-top:1.25rem;border-top:1px solid #1a2235">
    <div><div style="font-size:.6rem;font-weight:700;letter-spacing:.12em;color:#374151;text-transform:uppercase">Rubric</div><div style="font-size:.82rem;font-weight:600;color:#94a3b8">5 weighted dimensions</div></div>
    <div><div style="font-size:.6rem;font-weight:700;letter-spacing:.12em;color:#374151;text-transform:uppercase">Exports</div><div style="font-size:.82rem;font-weight:600;color:#94a3b8">PDF, HTML, JSON, CSV</div></div>
    <div><div style="font-size:.6rem;font-weight:700;letter-spacing:.12em;color:#374151;text-transform:uppercase">Overrides</div><div style="font-size:.82rem;font-weight:600;color:#94a3b8">Audited recruiter notes</div></div>
    </div></div>""", unsafe_allow_html=True)

    col_jd, col_res = st.columns(2)
    with col_jd:
        st.markdown("#### 📋 Job Description")
        jd_text = ""
        if use_sample:
            p = DATA_DIR / "sample_jd.txt"
            if p.exists():
                jd_text = p.read_text()
                st.success("✅ Sample JD loaded")
        jd_input = st.text_area("Paste or edit JD:", value=jd_text, height=300, placeholder="Paste job description…")
        jd_up = st.file_uploader("Or upload JD file:", type=["txt","pdf","docx"], key="jd_up")
        if jd_up:
            jd_input = jd_up.read().decode("utf-8", errors="ignore")

    with col_res:
        st.markdown("#### 📄 Resumes & LinkedIn Profiles")
        resume_data = []
        if use_sample and SAMPLE_RESUMES_DIR.exists():
            for f in list(SAMPLE_RESUMES_DIR.glob("*.txt"))[:10]:
                resume_data.append({"name": f.name, "path": f, "text": f.read_text()})
            st.success(f"✅ {len(resume_data)} sample resumes loaded")
        uploaded = st.file_uploader("Upload resumes (PDF/DOCX/TXT):", type=["pdf","docx","txt"], accept_multiple_files=True, key="res_up")
        if uploaded:
            for uf in uploaded:
                c = uf.read()
                resume_data.append({"name": uf.name, "content": c, "text": c.decode("utf-8", errors="ignore") if uf.type == "text/plain" else ""})
        li_up = st.file_uploader("LinkedIn JSON:", type=["json"], accept_multiple_files=True, key="li_up")
        if resume_data or li_up:
            st.markdown(f"**{len(resume_data) + len(li_up or [])} profiles queued**")
            for r in resume_data:
                st.markdown(f"- 📄 {r['name']}")

    st.markdown("---")
    c1, c2, _ = st.columns([2, 1, 3])
    with c1:
        run = st.button("✦ Run Analysis", type="primary", use_container_width=True)
    with c2:
        if st.button("🗑️ Clear", use_container_width=True):
            for k in ["results", "override_log", "agent", "ranked", "jd_parsed"]:
                st.session_state[k] = [] if k == "override_log" else None
            st.rerun()

    if run:
        if not jd_input.strip():
            st.error("❌ Job Description is required.")
        elif not resume_data and not li_up:
            st.error("❌ Upload at least one resume.")
        else:
            kw = {"provider": LLMProvider(provider)}
            if provider == "claude":
                kw["anthropic_api_key"] = api_key; kw["claude_model"] = model
            elif provider == "gemini":
                kw["gemini_api_key"] = api_key; kw["gemini_model"] = model
            else:
                kw["openai_api_key"] = api_key; kw["openai_model"] = model
            llm_cfg = LLMConfig(**kw)
            if not llm_cfg.is_configured:
                st.warning("⚠️ No API key — heuristic mode.")

            agent = ShortlistingAgent(llm_config=llm_cfg, use_embeddings=use_embeddings)

            with st.status("Analyzing candidates…", expanded=True) as status:
                try:
                    st.write("📋 Parsing Job Description…")
                    agent.parse_job_description(jd_input)
                    st.session_state["jd_parsed"] = agent.job_requirements

                    total = len(resume_data) + len(li_up or [])
                    for i, rd in enumerate(resume_data):
                        st.write(f"📄 Scoring **{rd['name']}** ({i+1}/{total})…")
                        if "path" in rd:
                            agent.ingest_resume_file(rd["path"])
                        elif rd.get("content"):
                            agent.ingest_resume_bytes(rd["content"], rd["name"])
                        else:
                            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
                            tmp.write(rd["text"].encode()); tmp.close()
                            agent.ingest_resume_file(tmp.name)

                    for lf in (li_up or []):
                        st.write(f"🔗 Scoring LinkedIn **{lf.name}**…")
                        agent.ingest_linkedin_bytes(lf.read(), lf.name)

                    st.write("⚙️ Running 5-dimension rubric scoring…")
                    agent.score_all_candidates()

                    st.write("📊 Ranking candidates…")
                    agent.rank_candidates()

                    # Store results as plain dicts in session_state["results"]
                    results = []
                    for rc in agent.ranked:
                        s = rc.score
                        dim_map = {d.dimension: d for d in s.dimension_scores}
                        def _d(name):
                            d = dim_map.get(name)
                            return {"score": round(d.score, 1), "justification": d.justification} if d else {"score": 0, "justification": "N/A"}
                        results.append({
                            "name": s.candidate_name,
                            "scores": {
                                "skills_match": _d("Skills Match"),
                                "experience_relevance": _d("Experience Relevance"),
                                "education_certs": _d("Education & Certifications"),
                                "project_portfolio": _d("Project / Portfolio"),
                                "communication_quality": _d("Communication Quality"),
                            },
                            "weighted_total": round(s.total_weighted_score * 10, 1),
                            "recommendation": (
                                "hire" if s.recommendation in ("Hire", "Strong Hire")
                                else "maybe" if s.recommendation == "Maybe"
                                else "no-hire"
                            ),
                            "summary": s.overall_summary or "",
                        })
                    st.session_state["results"] = results
                    st.session_state["agent"] = agent
                    st.session_state["ranked"] = agent.ranked

                    status.update(label="✅ Done! Switch to Results tab.", state="complete")

                except Exception as e:
                    status.update(label="❌ Error", state="error")
                    st.error(f"Pipeline failed: {e}")
                    logging.exception("Pipeline error")

# ════════════════════════════════════════════════════════════════
# TAB 2 — RESULTS
# ════════════════════════════════════════════════════════════════
with tab2:
    if "results" not in st.session_state or not st.session_state["results"]:
        st.info("Run analysis from the Input tab first.")
    else:
        results = st.session_state["results"]
        candidates = sorted(results, key=lambda x: x["weighted_total"], reverse=True)

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Screened", len(candidates))
        c2.metric("Hire", sum(1 for c in candidates if c["recommendation"] == "hire"))
        c3.metric("Maybe", sum(1 for c in candidates if c["recommendation"] == "maybe"))
        c4.metric("No-Hire", sum(1 for c in candidates if c["recommendation"] == "no-hire"))
        st.markdown("---")

        # Ranked list with progress bars + badges + expanders
        for i, c in enumerate(candidates, 1):
            badge = "✅ Hire" if c["recommendation"] == "hire" else ("⚠️ Maybe" if c["recommendation"] == "maybe" else "❌ No-Hire")
            badge_color = "#22c55e" if c["recommendation"] == "hire" else ("#f59e0b" if c["recommendation"] == "maybe" else "#ef4444")
            bar_color = "#22c55e" if c["weighted_total"] >= 70 else ("#f59e0b" if c["weighted_total"] >= 45 else "#ef4444")

            col1, col2, col3 = st.columns([0.4, 3, 1])
            col1.markdown(f"<div style='font-size:1.2rem;font-weight:800;color:#6366f1;text-align:center;padding-top:.5rem'>#{i}</div>", unsafe_allow_html=True)
            col2.markdown(f"**{c['name']}**")
            col2.progress(int(min(c["weighted_total"], 100)), text=f"{c['weighted_total']:.1f}/100")
            col3.markdown(f"<div style='padding-top:.5rem;text-align:center'><span style='background:{badge_color}22;color:{badge_color};padding:.25rem .75rem;border-radius:20px;font-size:.8rem;font-weight:700'>{badge}</span></div>", unsafe_allow_html=True)

            with st.expander(f"▸ View {c['name']} breakdown"):
                for dim, val in c["scores"].items():
                    dim_label = dim.replace("_", " ").title()
                    score_color = "#22c55e" if val["score"] >= 7 else ("#f59e0b" if val["score"] >= 4.5 else "#ef4444")
                    st.markdown(f"**{dim_label}**: <span style='color:{score_color};font-weight:800'>{val['score']}/10</span> — {val['justification']}", unsafe_allow_html=True)
                if c.get("summary"):
                    st.info(f"📝 {c['summary']}")

# ════════════════════════════════════════════════════════════════
# TAB 3 — OVERRIDE
# ════════════════════════════════════════════════════════════════
with tab3:
    if "results" not in st.session_state or not st.session_state["results"]:
        st.info("Run analysis from the Input tab first.")
    else:
        st.markdown("### 🔧 Human-in-the-Loop Override")
        st.markdown("Adjust scores with your expert judgment. All changes are logged with timestamps.")

        if "override_log" not in st.session_state:
            st.session_state["override_log"] = []

        results = st.session_state["results"]
        names = [c["name"] for c in results]
        selected = st.selectbox("Select candidate to override:", names)
        candidate = next(c for c in results if c["name"] == selected)

        reason = st.text_input("Reason for override (required for audit trail):", placeholder="e.g., Known referral with strong domain knowledge…")

        st.markdown("#### Adjust dimension scores (0-10):")
        new_scores = {}
        cols = st.columns(5)
        dim_labels = {
            "skills_match": "Skills Match",
            "experience_relevance": "Experience Relevance",
            "education_certs": "Education & Certs",
            "project_portfolio": "Project/Portfolio",
            "communication_quality": "Communication",
        }
        for col, (dim, label) in zip(cols, dim_labels.items()):
            current = candidate["scores"][dim]["score"]
            new_scores[dim] = col.slider(label, 0, 10, int(current), key=f"slider_{dim}")

        new_rec = st.selectbox("New Recommendation:", ["hire", "maybe", "no-hire"], index=["hire","maybe","no-hire"].index(candidate["recommendation"]))

        if st.button("💾 Save Override", type="primary"):
            if not reason.strip():
                st.error("Reason is mandatory for the audit trail.")
            else:
                # Update the candidate in results
                for c in st.session_state["results"]:
                    if c["name"] == selected:
                        for dim, new_val in new_scores.items():
                            c["scores"][dim]["score"] = new_val
                            c["scores"][dim]["justification"] = f"[HR Override] {reason}"
                        weights = {"skills_match": 0.30, "experience_relevance": 0.25, "education_certs": 0.15, "project_portfolio": 0.20, "communication_quality": 0.10}
                        c["weighted_total"] = round(sum(c["scores"][d]["score"] * w * 10 for d, w in weights.items()), 1)
                        c["recommendation"] = new_rec
                        break

                st.session_state["override_log"].append({
                    "Candidate": selected,
                    "Reason": reason,
                    "New Recommendation": new_rec,
                    "New Scores": json.dumps({d: v for d, v in new_scores.items()}),
                    "Timestamp": str(datetime.now()),
                })
                st.success(f"Override saved for **{selected}** → {new_rec}")
                st.rerun()

        st.markdown("---")
        st.markdown("### 📜 Audit Log")
        if st.session_state["override_log"]:
            st.dataframe(pd.DataFrame(st.session_state["override_log"]), use_container_width=True, hide_index=True)
        else:
            st.info("No overrides applied yet.")

# ════════════════════════════════════════════════════════════════
# TAB 4 — REPORT
# ════════════════════════════════════════════════════════════════
with tab4:
    if "results" not in st.session_state or not st.session_state["results"]:
        st.info("Run analysis from the Input tab first.")
    else:
        results = st.session_state["results"]
        st.markdown("### 📄 Reports & Downloads")

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Screened", len(results))
        c2.metric("Hire", sum(1 for r in results if r["recommendation"] == "hire"))
        c3.metric("Maybe", sum(1 for r in results if r["recommendation"] == "maybe"))
        c4.metric("No-Hire", sum(1 for r in results if r["recommendation"] == "no-hire"))

        st.markdown("---")
        st.markdown("#### ⬇️ Download Reports")
        dc1, dc2, dc3 = st.columns(3)

        # JSON download
        with dc1:
            json_bytes = json.dumps(results, indent=2).encode()
            st.download_button("📘 Download JSON", json_bytes, "shortlist.json", "application/json", use_container_width=True)

        # CSV download
        with dc2:
            rows = []
            for r in results:
                row = {"name": r["name"], "weighted_total": r["weighted_total"], "recommendation": r["recommendation"]}
                for dim, val in r["scores"].items():
                    row[f"{dim}_score"] = val["score"]
                    row[f"{dim}_justification"] = val["justification"]
                rows.append(row)
            csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode()
            st.download_button("📗 Download CSV", csv_bytes, "shortlist.csv", "text/csv", use_container_width=True)

        # PDF download
        with dc3:
            if st.session_state.get("ranked") and st.session_state.get("agent"):
                agent = st.session_state["agent"]
                try:
                    gen = ReportGenerator()
                    stats = agent.get_summary_stats()
                    pdf_path = gen.generate_pdf(agent.ranked, agent.job_requirements, stats)
                    with open(pdf_path, "rb") as f:
                        st.download_button("📕 Download PDF", f.read(), pdf_path.name, "application/pdf", use_container_width=True)
                except Exception as e:
                    st.error(f"PDF error: {e}")
            else:
                st.download_button("📕 Download PDF", b"", "shortlist.pdf", "application/pdf", use_container_width=True, disabled=True)

        st.markdown("---")
        st.markdown("#### 🏆 Full Ranked Table")
        sorted_results = sorted(results, key=lambda x: x["weighted_total"], reverse=True)
        table_rows = []
        for i, r in enumerate(sorted_results, 1):
            table_rows.append({
                "Rank": i,
                "Candidate": r["name"],
                "Score": f"{r['weighted_total']:.1f}/100",
                "Recommendation": r["recommendation"].upper(),
                "Skills": r["scores"]["skills_match"]["score"],
                "Experience": r["scores"]["experience_relevance"]["score"],
                "Education": r["scores"]["education_certs"]["score"],
                "Portfolio": r["scores"]["project_portfolio"]["score"],
                "Communication": r["scores"]["communication_quality"]["score"],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        # Audit log
        if st.session_state.get("override_log"):
            st.markdown("---")
            st.markdown("#### 📜 Override Audit Trail")
            st.dataframe(pd.DataFrame(st.session_state["override_log"]), use_container_width=True, hide_index=True)
