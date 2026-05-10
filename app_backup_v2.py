import streamlit as st
import json
import csv
import io
import time
import datetime
import re
import os
from groq import Groq

st.set_page_config(page_title="HR Shortlisting Agent", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
/* ── Premium CSS – works WITH config.toml dark theme ── */

/* ── Keyframe Animations ── */
@keyframes fadeInUp { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes pulseGlow { 0%, 100% { box-shadow: 0 0 20px rgba(139,92,246,0.15); } 50% { box-shadow: 0 0 40px rgba(139,92,246,0.3); } }
@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
@keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-6px); } }
@keyframes scaleIn { from { opacity: 0; transform: scale(0.92); } to { opacity: 1; transform: scale(1); } }
@keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }

/* ── Base ── */
html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
.stApp { background: #07060e !important; background-image: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(120,80,220,0.12), transparent), radial-gradient(ellipse 60% 40% at 80% 60%, rgba(56,100,220,0.06), transparent) !important; min-height: 100vh; }
.block-container { max-width: 1280px !important; padding: 1rem 2rem 4rem !important; }
/* Kill ALL white backgrounds in Streamlit containers */
.stApp, .stApp > div, .stApp [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"],
[data-testid="stAppViewBlockContainer"], [data-testid="stBottom"],
.stApp header, .stApp [data-testid="stHeader"],
[data-testid="stToolbar"], [data-testid="stDecoration"],
.main, .main .block-container, section[data-testid="stSidebar"],
[data-testid="stBottomBlockContainer"],
[data-testid="column"] > div, [data-testid="stColumn"] > div {
    background: transparent !important;
    background-color: transparent !important;
}

/* ── Header ── */
.main-header { text-align: center; padding: 2.5rem 0 1.5rem; animation: fadeInUp 0.8s ease-out; }
.main-header h1 { font-size: 3rem; font-weight: 800; background: linear-gradient(135deg, #c084fc, #818cf8, #60a5fa, #34d399); background-size: 200% auto; animation: gradientShift 4s ease infinite; -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; letter-spacing: -0.03em; line-height: 1.1; }
.main-header p { color: #64748b; font-size: 0.95rem; font-weight: 400; letter-spacing: 0.04em; }
.main-header .tag { display: inline-block; background: rgba(139,92,246,0.12); border: 1px solid rgba(139,92,246,0.2); color: #a78bfa; font-size: 0.7rem; font-weight: 600; padding: 4px 14px; border-radius: 100px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 1rem; }

/* ── Cards & Glassmorphism ── */
.card, .glass-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 1.75rem; margin-bottom: 1rem; backdrop-filter: blur(20px) saturate(150%); transition: all 0.4s cubic-bezier(0.16,1,0.3,1); }
.glass-card:hover { border-color: rgba(139,92,246,0.25); transform: translateY(-2px); box-shadow: 0 20px 60px -15px rgba(0,0,0,0.4); }

/* ── Badges ── */
.score-badge-hire { background: rgba(52,211,153,0.1); color: #34d399; border: 1px solid rgba(52,211,153,0.25); padding: 5px 16px; border-radius: 100px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; backdrop-filter: blur(8px); transition: all 0.3s ease; }
.score-badge-hire:hover { background: rgba(52,211,153,0.18); transform: scale(1.05); }
.score-badge-maybe { background: rgba(251,191,36,0.1); color: #fbbf24; border: 1px solid rgba(251,191,36,0.25); padding: 5px 16px; border-radius: 100px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; backdrop-filter: blur(8px); transition: all 0.3s ease; }
.score-badge-maybe:hover { background: rgba(251,191,36,0.18); transform: scale(1.05); }
.score-badge-nohire { background: rgba(248,113,113,0.1); color: #f87171; border: 1px solid rgba(248,113,113,0.25); padding: 5px 16px; border-radius: 100px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; backdrop-filter: blur(8px); transition: all 0.3s ease; }
.score-badge-nohire:hover { background: rgba(248,113,113,0.18); transform: scale(1.05); }

/* ── Rank & Dimension Scores ── */
.rank-number { font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: #8b5cf6; text-shadow: 0 0 30px rgba(139,92,246,0.3); }
.dim-label { font-size: 0.72rem; color: #64748b; margin-bottom: 4px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em; }
.dim-score { font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #e2e8f0; font-size: 1.1rem; }

/* ── Metric Cards ── */
.metric-card { background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.15); border-radius: 18px; padding: 1.25rem 1.5rem; text-align: center; backdrop-filter: blur(16px); transition: all 0.4s cubic-bezier(0.16,1,0.3,1); animation: fadeInUp 0.6s ease-out both; position: relative; overflow: hidden; }
.metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, rgba(139,92,246,0.5), transparent); opacity: 0; transition: opacity 0.3s ease; }
.metric-card:hover { border-color: rgba(139,92,246,0.35); transform: translateY(-4px); box-shadow: 0 16px 48px -12px rgba(139,92,246,0.15); }
.metric-card:hover::before { opacity: 1; }
.metric-value { font-size: 2.4rem; font-weight: 800; color: #a78bfa; font-family: 'JetBrains Mono', monospace; line-height: 1; margin-bottom: 4px; }
.metric-label { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; padding: 5px; }
.stTabs [data-baseweb="tab"] { border-radius: 12px; font-weight: 600; color: #475569; padding: 10px 20px !important; transition: all 0.3s cubic-bezier(0.16,1,0.3,1); font-size: 0.88rem; }
.stTabs [data-baseweb="tab"]:hover { color: #94a3b8; background: rgba(255,255,255,0.03); }
.stTabs [aria-selected="true"] { background: rgba(139,92,246,0.15) !important; color: #c084fc !important; box-shadow: 0 4px 12px -2px rgba(139,92,246,0.2); }

/* ── Buttons ── */
.stButton > button { border-radius: 12px; font-weight: 600; font-family: 'Inter', sans-serif !important; letter-spacing: 0.02em; transition: all 0.3s cubic-bezier(0.16,1,0.3,1); border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.04); color: #94a3b8; padding: 0.6rem 1.5rem; }
.stButton > button:hover { background: rgba(255,255,255,0.08); border-color: rgba(139,92,246,0.3); color: #e2e8f0; transform: translateY(-1px); box-shadow: 0 8px 24px -4px rgba(0,0,0,0.3); }
.stButton > button:active { transform: translateY(0px) scale(0.98); }
.stButton > button[kind="primary"] { background: linear-gradient(135deg, #8b5cf6, #6366f1, #4f46e5); border: none; color: white; padding: 0.7rem 2rem; font-weight: 700; box-shadow: 0 8px 32px -4px rgba(99,102,241,0.4); }
.stButton > button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 12px 40px -4px rgba(99,102,241,0.5); filter: brightness(1.1); }

/* ── Download Buttons ── */
.stDownloadButton > button { border-radius: 12px; font-weight: 600; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.04); color: #94a3b8; transition: all 0.3s ease; }
.stDownloadButton > button:hover { background: rgba(139,92,246,0.12); border-color: rgba(139,92,246,0.3); color: #c084fc; transform: translateY(-1px); }

/* ── Inputs (Nuclear Override) ── */
.stApp textarea,
.stApp input[type="text"],
.stApp input[type="password"],
.stApp [data-baseweb="textarea"] textarea,
.stApp [data-baseweb="input"] input,
.stApp [data-baseweb="base-input"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] div[data-baseweb="textarea"] textarea,
[data-testid="stTextInput"] div[data-baseweb="input"] input {
    background: rgba(15,14,30,0.95) !important;
    background-color: rgba(15,14,30,0.95) !important;
    border: 1px solid rgba(139,92,246,0.15) !important;
    border-radius: 14px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.3s ease, box-shadow 0.3s ease !important;
    caret-color: #a78bfa !important;
}
.stApp textarea:focus,
.stApp input[type="text"]:focus,
.stApp input[type="password"]:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stTextInput"] input:focus {
    border-color: rgba(139,92,246,0.5) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.1), 0 4px 20px rgba(139,92,246,0.12) !important;
    outline: none !important;
}
/* Textarea & input wrappers */
[data-testid="stTextArea"] > div,
[data-testid="stTextInput"] > div,
[data-testid="stTextArea"] > div > div,
[data-testid="stTextInput"] > div > div,
[data-baseweb="textarea"],
[data-baseweb="input"],
[data-baseweb="base-input"] {
    background: transparent !important;
    background-color: transparent !important;
    border-color: transparent !important;
}
/* Labels */
.stApp label,
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span,
.stTextInput label, .stTextArea label,
.stSelectbox label, .stSlider label,
.stFileUploader label {
    color: #94a3b8 !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
}
/* Placeholder text */
.stApp textarea::placeholder,
.stApp input::placeholder {
    color: #475569 !important;
    opacity: 1 !important;
}

/* ── Selectbox (Nuclear Override) ── */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] > div > div {
    background: rgba(15,14,30,0.95) !important;
    background-color: rgba(15,14,30,0.95) !important;
    border: 1px solid rgba(139,92,246,0.15) !important;
    border-radius: 14px !important;
    color: #e2e8f0 !important;
    transition: all 0.3s ease;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {
    border-color: rgba(139,92,246,0.35) !important;
}
[data-testid="stSelectbox"] span, [data-testid="stSelectbox"] div {
    color: #e2e8f0 !important;
}
/* Dropdown menu */
[data-baseweb="popover"], [data-baseweb="menu"],
ul[role="listbox"], [data-baseweb="popover"] > div {
    background: rgba(15,14,30,0.98) !important;
    background-color: rgba(15,14,30,0.98) !important;
    border: 1px solid rgba(139,92,246,0.2) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(20px) !important;
}
ul[role="listbox"] li,
[data-baseweb="menu"] [role="option"] {
    color: #cbd5e1 !important;
    background: transparent !important;
}
ul[role="listbox"] li:hover,
[data-baseweb="menu"] [role="option"]:hover {
    background: rgba(139,92,246,0.12) !important;
    color: #e2e8f0 !important;
}

/* ── File Uploader (Nuclear Override) ── */
[data-testid="stFileUploader"],
[data-testid="stFileUploader"] > div,
[data-testid="stFileUploader"] > div > div,
[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploaderDropzone"] > div {
    background: rgba(15,14,30,0.6) !important;
    background-color: rgba(15,14,30,0.6) !important;
    border-color: rgba(139,92,246,0.15) !important;
}
[data-testid="stFileUploader"] > section {
    border: 2px dashed rgba(139,92,246,0.2) !important;
    border-radius: 18px !important;
    padding: 1.25rem !important;
    transition: all 0.3s ease;
    background: rgba(15,14,30,0.6) !important;
}
[data-testid="stFileUploader"] > section:hover {
    border-color: rgba(139,92,246,0.4) !important;
    background: rgba(139,92,246,0.04) !important;
}
[data-testid="stFileUploader"] button,
[data-testid="stFileUploaderDropzone"] button {
    background: rgba(139,92,246,0.1) !important;
    border: 1px solid rgba(139,92,246,0.2) !important;
    border-radius: 10px !important;
    color: #a78bfa !important;
}
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] span {
    color: #64748b !important;
}

/* ── Progress Bars ── */
[data-testid="stProgress"] > div > div { background: rgba(255,255,255,0.04) !important; border-radius: 10px !important; height: 8px !important; overflow: hidden; }
[data-testid="stProgress"] > div > div > div { background: linear-gradient(90deg, #8b5cf6, #6366f1, #818cf8) !important; border-radius: 10px !important; transition: width 0.6s cubic-bezier(0.16,1,0.3,1); }

/* ── Expanders ── */
div[data-testid="stExpander"] { background: rgba(255,255,255,0.02) !important; border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 16px !important; transition: all 0.3s ease; }
div[data-testid="stExpander"]:hover { border-color: rgba(139,92,246,0.2) !important; }
div[data-testid="stExpander"] summary { color: #94a3b8 !important; font-weight: 600 !important; }
div[data-testid="stExpander"] summary:hover { color: #c084fc !important; }

/* ── Slider ── */
[data-testid="stSlider"] > div > div > div { color: #a78bfa !important; }

/* ── Alerts ── */
[data-testid="stAlert"] { background: rgba(255,255,255,0.03) !important; border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 14px !important; backdrop-filter: blur(8px); }

/* ── Status ── */
[data-testid="stStatusWidget"] { border-radius: 16px !important; border: 1px solid rgba(139,92,246,0.15) !important; }

/* ── Override Log ── */
.override-log-entry { background: rgba(251,191,36,0.05); border-left: 3px solid rgba(251,191,36,0.6); border-radius: 0 14px 14px 0; padding: 0.85rem 1.25rem; margin: 0.6rem 0; font-size: 0.82rem; color: #cbd5e1; backdrop-filter: blur(8px); transition: all 0.3s ease; animation: fadeIn 0.4s ease-out; }
.override-log-entry:hover { background: rgba(251,191,36,0.08); transform: translateX(4px); }

/* ── Empty States ── */
.empty-state { text-align: center; padding: 5rem 2rem; animation: fadeIn 0.8s ease-out; }
.empty-state .icon { font-size: 4rem; margin-bottom: 1rem; animation: float 3s ease-in-out infinite; }
.empty-state h3 { color: #94a3b8; font-weight: 600; margin: 0.75rem 0 0.5rem; }
.empty-state p { color: #475569; font-size: 0.9rem; }

/* ── Candidate Row ── */
.candidate-row { animation: fadeInUp 0.5s ease-out both; }

/* ── Dividers ── */
hr { border-color: rgba(255,255,255,0.04) !important; margin: 1.5rem 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,0.35); }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border-radius: 16px !important; overflow: hidden; border: 1px solid rgba(255,255,255,0.06) !important; }

/* ── Markdown H3 ── */
h3 { color: #e2e8f0 !important; font-weight: 700 !important; letter-spacing: -0.02em; }
p, li, span { color: #cbd5e1; }
strong { color: #e2e8f0; }

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

for key, default in {"results": [], "override_log": [], "jd_text": "", "resume_texts": [], "resume_names": [], "analysis_done": False}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.markdown("""<div class="main-header"><div class="tag">✦ AI-Powered Recruitment Intelligence</div><h1>HR Shortlisting Agent</h1><p>Rank candidates with transparent scoring · Override with full audit trails · Export production-ready reports</p></div>""", unsafe_allow_html=True)

WEIGHTS = {"skills_match": 0.30, "experience_relevance": 0.25, "education_certs": 0.15, "project_portfolio": 0.20, "communication_quality": 0.10}
DIM_LABELS = {"skills_match": "Skills Match (30%)", "experience_relevance": "Experience Relevance (25%)", "education_certs": "Education & Certs (15%)", "project_portfolio": "Project / Portfolio (20%)", "communication_quality": "Communication Quality (10%)"}

def score_color(score):
    if score >= 75: return "#34d399"
    elif score >= 50: return "#fbbf24"
    return "#f87171"

def badge_html(rec):
    rec = rec.lower().strip()
    if rec == "hire": return '<span class="score-badge-hire">✅ HIRE</span>'
    elif rec == "maybe": return '<span class="score-badge-maybe">🟡 MAYBE</span>'
    return '<span class="score-badge-nohire">❌ NO-HIRE</span>'

def compute_weighted(scores_dict):
    total = 0.0
    for dim, w in WEIGHTS.items():
        total += scores_dict.get(dim, {}).get("score", 0) * w * 10
    return round(total, 1)

def extract_text_from_upload(uploaded_file):
    fname = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if fname.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception: pass
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception: pass
    if fname.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception: pass
    try: return raw.decode("utf-8", errors="ignore")
    except Exception: return ""

def call_groq_score(jd, resume_text, name, api_key=None):
    client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))
    system_prompt = """You are an expert HR analyst. Score the candidate resume against the job description.
Respond ONLY with a single valid JSON object — no markdown, no explanation, no preamble.
Use this exact schema:
{"name": "candidate name", "scores": {"skills_match": {"score": 0, "justification": "one concise line"}, "experience_relevance": {"score": 0, "justification": "one concise line"}, "education_certs": {"score": 0, "justification": "one concise line"}, "project_portfolio": {"score": 0, "justification": "one concise line"}, "communication_quality": {"score": 0, "justification": "one concise line"}}, "recommendation": "hire"}
Each score must be an integer 0-10.
Scoring guide:
- skills_match (30%): 0=less than 30% match, 5=50-70% match, 10=85%+ match
- experience_relevance (25%): 0=unrelated, 5=adjacent domain, 10=exact match and seniority
- education_certs (15%): 0=below minimum, 5=meets minimum, 10=exceeds plus extra certs
- project_portfolio (20%): 0=none, 5=1-2 generic, 10=strong relevant portfolio
- communication_quality (10%): 0=poor structure, 5=adequate, 10=crisp and impactful
recommendation must be exactly one of: hire, maybe, no-hire"""
    user_prompt = f"JOB DESCRIPTION:\n{jd}\n\nCANDIDATE NAME: {name}\nRESUME:\n{resume_text[:4000]}"
    response = client.chat.completions.create(model="llama-3.3-70b-versatile", max_tokens=1000, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.1)
    raw_text = response.choices[0].message.content.strip()
    raw_text = re.sub(r"^```json\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)
    candidate = json.loads(raw_text)
    candidate["name"] = name
    candidate["weighted_total"] = compute_weighted(candidate["scores"])
    candidate["override_log"] = []
    return candidate

tab1, tab2, tab3, tab4 = st.tabs(["📋  Input & Analysis", "🏆  Results", "✏️  Override Scores", "📊  Report & Export"])

with tab1:
    col_jd, col_res = st.columns([1, 1], gap="large")
    with col_jd:
        st.markdown("### 📄 Job Description")
        jd_input = st.text_area("Paste the full JD here", value=st.session_state["jd_text"], height=300, placeholder="Paste the job description here...\n\nInclude: role, required skills, experience, qualifications.", label_visibility="collapsed")
        st.session_state["jd_text"] = jd_input
        if st.button("💡 Load Demo JD", use_container_width=True):
            st.session_state["jd_text"] = "Senior Backend Engineer — FinTech\n\nWe are looking for a Senior Backend Engineer with 5+ years of experience.\n\nRequired Skills:\n- Python (FastAPI / Django)\n- PostgreSQL, Redis\n- Microservices & REST APIs\n- Docker, Kubernetes\n- AWS (EC2, S3, Lambda)\n\nExperience:\n- 5+ years backend engineering\n- FinTech or payments domain preferred\n- Led teams or mentored junior engineers\n\nEducation:\n- B.Tech/B.E. in Computer Science or equivalent\n- AWS / GCP certifications a plus\n\nResponsibilities:\n- Design and build scalable payment APIs\n- Collaborate with product, data, and front-end teams\n- Code reviews and architecture decisions"
            st.rerun()
    with col_res:
        st.markdown("### 📎 Upload Resumes")
        uploaded_files = st.file_uploader("Upload PDF or DOCX resumes (max 20)", type=["pdf", "docx", "txt"], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded_files:
            st.markdown(f"**{len(uploaded_files)} file(s) ready:**")
            for f in uploaded_files: st.markdown(f"- `{f.name}`")
        st.markdown("**— or paste LinkedIn profile URL(s) —**")
        linkedin_input = st.text_area("LinkedIn URLs (one per line)", height=80, placeholder="https://linkedin.com/in/rahul-sharma\nhttps://linkedin.com/in/priya-mehta", label_visibility="collapsed")
        st.caption("ℹ️ LinkedIn URLs are sent to the LLM for context-based scoring.")
        st.markdown("**— or paste resume text manually —**")
        manual_name = st.text_input("Candidate name", placeholder="e.g. Rahul Sharma")
        manual_text = st.text_area("Resume text", height=120, placeholder="Paste resume content here...")
        if st.button("➕ Add Manual Resume", use_container_width=True):
            if manual_name and manual_text:
                st.session_state["resume_names"].append(manual_name.strip())
                st.session_state["resume_texts"].append(manual_text.strip())
                st.success(f"Added {manual_name}")
            else: st.warning("Enter both name and resume text.")
        if st.session_state["resume_names"]:
            st.markdown(f"**{len(st.session_state['resume_names'])} manual resume(s) added:**")
            for n in st.session_state["resume_names"]: st.markdown(f"- `{n}`")
            if st.button("🗑️ Clear manual resumes"):
                st.session_state["resume_names"] = []; st.session_state["resume_texts"] = []; st.rerun()
    st.divider()
    api_key_input = st.text_input("🔑 Groq API Key (leave blank to use default)", type="password", placeholder="gsk_...")
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)
    if run_btn:
        if not st.session_state["jd_text"].strip(): st.error("Please enter a Job Description first.")
        else:
            all_names, all_texts = [], []
            if uploaded_files:
                for uf in uploaded_files:
                    text = extract_text_from_upload(uf)
                    name = uf.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
                    all_names.append(name); all_texts.append(text)
            if linkedin_input and linkedin_input.strip():
                for url in linkedin_input.strip().splitlines():
                    url = url.strip()
                    if url and "linkedin.com" in url:
                        slug = url.rstrip("/").split("/")[-1]
                        name = slug.replace("-", " ").title() + " (LinkedIn)"
                        li_text = f"LinkedIn Profile URL: {url}\n\nNote: Full profile could not be scraped automatically. Score based on name/URL context only. Be conservative."
                        all_names.append(name); all_texts.append(li_text)
            all_names.extend(st.session_state["resume_names"]); all_texts.extend(st.session_state["resume_texts"])
            if not all_names: st.error("Upload at least one resume or add a manual entry.")
            else:
                key_to_use = api_key_input if api_key_input else os.getenv("GROQ_API_KEY")
                results, errors = [], []
                with st.status(f"🤖 Analyzing {len(all_names)} candidate(s)...", expanded=True) as status:
                    for i, (name, text) in enumerate(zip(all_names, all_texts), 1):
                        st.write(f"Scoring **{name}** ({i}/{len(all_names)})...")
                        try:
                            candidate = call_groq_score(st.session_state["jd_text"], text, name, api_key=key_to_use)
                            results.append(candidate)
                            st.write(f"✅ {name} → {candidate['weighted_total']}/100 · {candidate['recommendation'].upper()}")
                        except Exception as e:
                            errors.append(f"{name}: {str(e)}"); st.write(f"❌ {name} failed — {str(e)}")
                        time.sleep(0.3)
                    if results:
                        results.sort(key=lambda x: x["weighted_total"], reverse=True)
                        st.session_state["results"] = results; st.session_state["analysis_done"] = True
                        status.update(label=f"✅ Done! {len(results)} candidates scored.", state="complete")
                    else: status.update(label="❌ All candidates failed.", state="error")
                if errors: st.warning("Some errors:\n" + "\n".join(errors))
                if results: st.success("🎉 Analysis complete! Switch to the **Results** tab.")

with tab2:
    if not st.session_state["results"]:
        st.markdown('<div class="empty-state"><div class="icon">🔍</div><h3>No results yet</h3><p>Go to <strong>Input & Analysis</strong>, upload resumes, and click <strong>Run Analysis</strong> to begin.</p></div>', unsafe_allow_html=True)
    else:
        results = st.session_state["results"]
        st.markdown(f"### 🏆 Ranked Candidates ({len(results)} total)")
        for rank, c in enumerate(results, 1):
            total = c["weighted_total"]; rec = c.get("recommendation", "maybe"); color = score_color(total)
            with st.container():
                col_rank, col_name, col_bar, col_score, col_badge = st.columns([0.5, 2, 3, 1, 1.5])
                with col_rank: st.markdown(f'<div class="rank-number">#{rank}</div>', unsafe_allow_html=True)
                with col_name: st.markdown(f"**{c['name']}**")
                with col_bar: st.progress(int(total))
                with col_score: st.markdown(f'<div style="font-family:JetBrains Mono,monospace;font-size:1.1rem;font-weight:700;color:{color}">{total}</div>', unsafe_allow_html=True)
                with col_badge: st.markdown(badge_html(rec), unsafe_allow_html=True)
                with st.expander(f"📂 View {c['name']}'s full breakdown"):
                    dim_cols = st.columns(5)
                    for idx, (dim, label) in enumerate(DIM_LABELS.items()):
                        dim_data = c["scores"].get(dim, {}); s = dim_data.get("score", 0); j = dim_data.get("justification", "—")
                        with dim_cols[idx]:
                            st.markdown(f'<div class="dim-label">{label}</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="dim-score">{s}/10</div>', unsafe_allow_html=True)
                            st.progress(int(s * 10)); st.caption(j)
                    if c.get("override_log"):
                        st.markdown("**Override History:**")
                        for log in c["override_log"]:
                            st.markdown(f'<div class="override-log-entry">🕐 {log["timestamp"]} · <strong>{log["dimension"]}</strong>: {log["old_score"]} → {log["new_score"]} · <em>{log["reason"]}</em></div>', unsafe_allow_html=True)
                st.markdown("---")

with tab3:
    if not st.session_state["results"]:
        st.markdown('<div class="empty-state"><div class="icon">✏️</div><h3>Run analysis first</h3><p>Score overrides will appear here after candidates are analyzed.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown("### ✏️ Override Candidate Scores")
        st.caption("HR can adjust any dimension score. All changes are logged with timestamp and reason.")
        candidate_names = [c["name"] for c in st.session_state["results"]]
        selected_name = st.selectbox("Select candidate to override", candidate_names)
        cand_idx = candidate_names.index(selected_name)
        cand = st.session_state["results"][cand_idx]
        st.markdown(f"**Current weighted total:** `{cand['weighted_total']}/100`")
        ov_cols = st.columns(2); new_scores = {}
        for i, (dim, label) in enumerate(DIM_LABELS.items()):
            current = cand["scores"].get(dim, {}).get("score", 5)
            with ov_cols[i % 2]: new_scores[dim] = st.slider(label, 0, 10, int(current), key=f"slider_{dim}_{cand_idx}")
        override_reason = st.text_input("Reason for override (required)", placeholder="e.g. Verified extra AWS cert on LinkedIn", key=f"reason_{cand_idx}")
        if st.button("💾 Save Override", type="primary"):
            if not override_reason.strip(): st.error("Please provide a reason before saving.")
            else:
                changed = False
                for dim, new_val in new_scores.items():
                    old_val = cand["scores"][dim]["score"]
                    if new_val != old_val:
                        log_entry = {"candidate": selected_name, "dimension": DIM_LABELS[dim], "old_score": old_val, "new_score": new_val, "reason": override_reason.strip(), "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                        st.session_state["results"][cand_idx]["scores"][dim]["score"] = new_val
                        st.session_state["results"][cand_idx]["override_log"].append(log_entry)
                        st.session_state["override_log"].append(log_entry); changed = True
                if changed:
                    new_total = compute_weighted(st.session_state["results"][cand_idx]["scores"])
                    st.session_state["results"][cand_idx]["weighted_total"] = new_total
                    st.session_state["results"].sort(key=lambda x: x["weighted_total"], reverse=True)
                    st.success(f"✅ Override saved! New total: {new_total}/100"); st.rerun()
                else: st.info("No scores were changed.")
        if st.session_state["override_log"]:
            st.markdown("---"); st.markdown("### 📜 Full Override Log")
            for entry in reversed(st.session_state["override_log"]):
                st.markdown(f'<div class="override-log-entry">🕐 <strong>{entry["timestamp"]}</strong> · {entry["candidate"]} · {entry["dimension"]}: <strong>{entry["old_score"]} → {entry["new_score"]}</strong> · <em>{entry["reason"]}</em></div>', unsafe_allow_html=True)

with tab4:
    if not st.session_state["results"]:
        st.markdown('<div class="empty-state"><div class="icon">📊</div><h3>No data to report</h3><p>Complete an analysis first, then come back here to export.</p></div>', unsafe_allow_html=True)
    else:
        results = st.session_state["results"]
        hire_count = sum(1 for c in results if c.get("recommendation","").lower() == "hire")
        maybe_count = sum(1 for c in results if c.get("recommendation","").lower() == "maybe")
        nohire_count = sum(1 for c in results if c.get("recommendation","").lower() == "no-hire")
        avg_score = round(sum(c["weighted_total"] for c in results) / len(results), 1)
        m1, m2, m3, m4, m5 = st.columns(5)
        for col, val, label in [(m1, len(results), "Total Screened"), (m2, hire_count, "✅ Hire"), (m3, maybe_count, "🟡 Maybe"), (m4, nohire_count, "❌ No-Hire"), (m5, avg_score, "Avg Score")]:
            with col: st.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📋 Full Ranked Table")
        import pandas as pd
        table_data = []
        for rank, c in enumerate(results, 1):
            row = {"Rank": rank, "Candidate": c["name"], "Weighted Total": c["weighted_total"], "Recommendation": c.get("recommendation","—").upper()}
            for dim, label in DIM_LABELS.items(): row[label] = c["scores"].get(dim, {}).get("score", 0)
            table_data.append(row)
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("---"); st.markdown("### 📥 Export")
        dl1, dl2, dl3 = st.columns(3)
        with dl1: st.download_button("⬇️ Download JSON", json.dumps(results, indent=2, ensure_ascii=False), f"shortlist_{datetime.date.today()}.json", "application/json", use_container_width=True)
        with dl2:
            csv_buf = io.StringIO(); df.to_csv(csv_buf, index=False)
            st.download_button("⬇️ Download CSV", csv_buf.getvalue(), f"shortlist_{datetime.date.today()}.csv", "text/csv", use_container_width=True)
        with dl3:
            if st.session_state["override_log"]:
                st.download_button("⬇️ Download Override Log", json.dumps(st.session_state["override_log"], indent=2, ensure_ascii=False), f"overrides_{datetime.date.today()}.json", "application/json", use_container_width=True)
            else: st.info("No overrides recorded yet.")
        st.markdown("---"); st.markdown("### 🌐 Generate HTML Report")
        if st.button("Generate HTML Report", use_container_width=True):
            rows_html = ""
            for rank, c in enumerate(results, 1):
                rec = c.get("recommendation","maybe").lower()
                col = {"hire":"#34d399","maybe":"#fbbf24","no-hire":"#f87171"}.get(rec,"#94a3b8")
                rows_html += f'<tr><td style="text-align:center;font-weight:700">#{rank}</td><td style="font-weight:600">{c["name"]}</td><td style="text-align:center;font-weight:700;color:{col}">{c["weighted_total"]}</td><td style="text-align:center"><span style="background:{col}20;color:{col};border:1px solid {col};padding:3px 10px;border-radius:20px;font-size:0.8rem;font-weight:600">{rec.upper()}</span></td>'
                for dim in DIM_LABELS: rows_html += f'<td>{c["scores"].get(dim,{}).get("score","—")}/10</td>'
                rows_html += '</tr>'
            html_report = f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>HR Shortlist Report — {datetime.date.today()}</title><style>body{{font-family:Segoe UI,sans-serif;background:#0f0c29;color:#e2e8f0;padding:2rem}}h1{{background:linear-gradient(90deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}table{{width:100%;border-collapse:collapse;margin-top:1.5rem}}th{{background:#1e1b4b;padding:10px 14px;text-align:left;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.08em;color:#94a3b8}}td{{padding:10px 14px;border-bottom:1px solid #1e293b}}tr:hover{{background:rgba(255,255,255,0.03)}}.meta{{color:#64748b;font-size:0.9rem;margin-bottom:2rem}}</style></head><body><h1>🎯 HR Shortlist Report</h1><p class="meta">Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} · {len(results)} candidates · Avg score: {avg_score}/100</p><table><thead><tr><th>Rank</th><th>Candidate</th><th>Total</th><th>Decision</th><th>Skills</th><th>Experience</th><th>Education</th><th>Portfolio</th><th>Communication</th></tr></thead><tbody>{rows_html}</tbody></table></body></html>'
            st.download_button("⬇️ Download HTML Report", html_report, f"shortlist_report_{datetime.date.today()}.html", "text/html", use_container_width=True)
            st.success("HTML report generated!")
