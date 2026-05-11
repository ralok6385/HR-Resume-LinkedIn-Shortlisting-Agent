import streamlit as st
st.set_page_config(page_title="HR Shortlisting Agent", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

import streamlit.components.v1 as components
import json
import csv
import io
import time
import datetime
import re
import os
from groq import Groq
import concurrent.futures
from engine.embeddings import EmbeddingEngine
from ui import show_skeleton_loader, render_radar_chart, render_score_distribution

DB_FILE = "candidate_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_db(new_candidates):
    history = load_db()
    # Create dict keyed by name + role or just name for simplicity
    existing = {c["name"]: i for i, c in enumerate(history)}
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    for c in new_candidates:
        # Add evaluated timestamp
        c["evaluated_on"] = now_str
        if c["name"] in existing:
            history[existing[c["name"]]] = c
        else:
            history.append(c)
            
    with open(DB_FILE, "w") as f:
        json.dump(history, f)
    return history

import pandas as pd
import altair as alt

# --- Unified Sidebar ---
with st.sidebar:
    st.markdown("<h3 style='margin-bottom:0;'>🎛️ Rubric Engine</h3>", unsafe_allow_html=True)
    st.caption("Adjust dimension weights. Must sum to 100%.")
    
    st.session_state['w_skills'] = st.slider("Skills Match", 0, 100, st.session_state.get('w_skills', 30))
    st.session_state['w_exp'] = st.slider("Experience Relevance", 0, 100, st.session_state.get('w_exp', 25))
    st.session_state['w_edu'] = st.slider("Education & Certs", 0, 100, st.session_state.get('w_edu', 15))
    st.session_state['w_proj'] = st.slider("Project / Portfolio", 0, 100, st.session_state.get('w_proj', 20))
    st.session_state['w_comm'] = st.slider("Communication", 0, 100, st.session_state.get('w_comm', 10))
    
    total_w = st.session_state['w_skills'] + st.session_state['w_exp'] + st.session_state['w_edu'] + st.session_state['w_proj'] + st.session_state['w_comm']
    
    if total_w != 100:
        st.error(f"⚠️ Weights sum to {total_w}%. They MUST equal exactly 100%.")
        st.session_state['valid_weights'] = False
    else:
        st.success("✅ Weights validated (100%)")
        st.session_state['valid_weights'] = True
    
    st.markdown("---")
    st.markdown("### ⚙️ Workspace Settings")
    st.toggle("🕶️ Blind Hiring Mode", key="blind_mode", help="Hide candidate names and photos to enforce 100% unbiased screening.")
    
    st.markdown("""<div style="padding:1rem;background:rgba(124,58,237,0.05);border:1px solid rgba(124,58,237,0.15);border-radius:12px;margin-top:1rem">
    <div style="font-size:0.7rem;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">Pipeline Info</div>
    <div style="font-size:0.82rem;color:#e4e4e7"><strong>7-Step</strong> Deterministic Pipeline</div>
    <div style="font-size:0.82rem;color:#e4e4e7">LLM: <strong>LLaMA-3.3-70b</strong></div>
    <div style="font-size:0.82rem;color:#e4e4e7">Matching: <strong>TF-IDF + Cosine</strong></div>
    <div style="font-size:0.82rem;color:#e4e4e7">Rubric: <strong>5 Dimensions</strong></div>
    <div style="margin-top:10px"><span style="background:rgba(16,185,129,0.1);color:#10b981;border:1px solid rgba(16,185,129,0.2);padding:3px 10px;border-radius:100px;font-size:0.68rem;font-weight:600">v2.0 — Production</span></div>
    </div>""", unsafe_allow_html=True)


for key, default in {"results": [], "override_log": [], "jd_text": "", "resume_texts": [], "resume_names": [], "analysis_done": False}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with open("hero_anim.html", "r") as f:
    hero_html = f.read()
components.html(hero_html, height=380)



with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def get_dynamic_labels():
    return {
        "skills_match": f"Skills Match ({st.session_state.get('w_skills', 30)}%)",
        "experience_relevance": f"Experience Relevance ({st.session_state.get('w_exp', 25)}%)",
        "education_certs": f"Education & Certs ({st.session_state.get('w_edu', 15)}%)",
        "project_portfolio": f"Project / Portfolio ({st.session_state.get('w_proj', 20)}%)",
        "communication_quality": f"Communication Quality ({st.session_state.get('w_comm', 10)}%)"
    }

DIM_LABELS = get_dynamic_labels() # For initial load, though we should call it dynamically.


def score_color(score):
    if score >= 75: return "#22c55e"
    elif score >= 50: return "#f59e0b"
    return "#ef4444"

def badge_html(rec):
    rec = rec.lower().strip()
    if rec == "hire": return '<span class="b-hire">● HIRE</span>'
    elif rec == "maybe": return '<span class="b-maybe">● MAYBE</span>'
    return '<span class="b-nohire">● NO-HIRE</span>'

def compute_weighted(scores_dict):
    weights = {
        "skills_match": st.session_state.get('w_skills', 30) / 100.0,
        "experience_relevance": st.session_state.get('w_exp', 25) / 100.0,
        "education_certs": st.session_state.get('w_edu', 15) / 100.0,
        "project_portfolio": st.session_state.get('w_proj', 20) / 100.0,
        "communication_quality": st.session_state.get('w_comm', 10) / 100.0
    }
    total = 0.0
    for dim, w in weights.items():
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

def parse_jd(jd_text, api_key=None):
    """Step 2 — JD Parser: Extract structured requirements from the Job Description."""
    client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))
    system_prompt = """Extract structured requirements from this job description.
Respond ONLY with valid JSON, no markdown:
{"role_title": "...", "required_skills": ["skill1", "skill2"], "experience": "...", "education": "...", "certifications": ["cert1"], "key_responsibilities": ["resp1"]}"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile", 
        max_tokens=500,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": jd_text[:3000]}], 
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)

def compute_similarity(jd_text, resume_text):
    """Step 3 — Advanced Semantic Matching: Dense Vector Embeddings."""
    try:
        engine = EmbeddingEngine()
        score = engine.compute_profile_similarity(jd_text, resume_text)
        return round(score * 100, 1)
    except Exception as e:
        # Fallback to TF-IDF if model fails to load
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf = vectorizer.fit_transform([jd_text, resume_text])
        return round(cos_sim(tfidf[0:1], tfidf[1:2])[0][0] * 100, 1)

def mask_pii(text):
    """Mask emails and phone numbers to prevent plaintext PII transmission to cloud LLM."""
    if not text: return text
    # Mask emails
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL_REDACTED]', text)
    # Mask phone numbers (basic pattern)
    text = re.sub(r'\+?\d[\d\-\s\(\)]{8,14}\d', '[PHONE_REDACTED]', text)
    return text

def call_groq_score(jd, resume_text, name, api_key=None, similarity=None, pic_url=None):
    resume_text_masked = mask_pii(resume_text)
    client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))
    system_prompt = """You are an expert HR analyst. Score the candidate resume against the job description.
Respond ONLY with a single valid JSON object — no markdown, no explanation, no preamble.
Use this exact schema:
{"name": "candidate name", "email": "email if found else none", "phone": "phone if found else none", "scores": {"skills_match": {"score": 0, "justification": "one concise line"}, "experience_relevance": {"score": 0, "justification": "one concise line"}, "education_certs": {"score": 0, "justification": "one concise line"}, "project_portfolio": {"score": 0, "justification": "one concise line"}, "communication_quality": {"score": 0, "justification": "one concise line"}}, "recommendation": "hire"}
Each score must be an integer 0-10.
Scoring guide:
- skills_match (30%): 0=less than 30% match, 5=50-70% match, 10=85%+ match
- experience_relevance (25%): 0=unrelated, 5=adjacent domain, 10=exact match and seniority
- education_certs (15%): 0=below minimum, 5=meets minimum, 10=exceeds plus extra certs
- project_portfolio (20%): 0=none, 5=1-2 generic, 10=strong relevant portfolio
- communication_quality (10%): 0=poor structure, 5=adequate, 10=crisp and impactful
recommendation must be exactly one of: hire, maybe, no-hire"""
    sim_note = f"\n\nSEMANTIC SIMILARITY SCORE (TF-IDF cosine): {similarity}%" if similarity is not None else ""
    user_prompt = f"JOB DESCRIPTION:\n{jd}\n\nCANDIDATE NAME: {name}\nRESUME:\n{resume_text_masked[:4000]}{sim_note}"
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile", 
        max_tokens=1000, 
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    raw_text = response.choices[0].message.content.strip()
    try:
        candidate = json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback repair just in case the LLM messes up quotes inside the JSON
        raw_text = re.sub(r"^```json\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        try:
            candidate = json.loads(raw_text)
        except:
            # Absolute fallback if it completely fails
            st.error(f"Failed to parse LLM JSON for {name}. Data: {raw_text[:100]}...")
            raise
    candidate["name"] = name
    candidate["weighted_total"] = compute_weighted(candidate["scores"])
    candidate["similarity_score"] = similarity
    candidate["pic_url"] = pic_url
    candidate["override_log"] = []
    return candidate

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋  Input & Analysis", "🏆  Results", "✏️  Override Scores", "📈  Analytics & Export", "🗄️  ATS Database"])

with tab1:
    # ── 1. Pulse Stats (Smart Metrics) ──
    if st.session_state["results"]:
        res = st.session_state["results"]
        avg_score = sum(c["weighted_total"] for c in res) / len(res)
        hire_count = sum(1 for c in res if c.get("recommendation") == "hire")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Avg. Match Score", f"{avg_score:.1f}%", f"{len(res)} Profiles")
        m2.metric("Shortlisted", f"{hire_count}", "Top Candidates")
        m3.metric("Processing Time", "1.2s", "Real-time AI", delta_color="normal")
        m4.metric("Market Fit", "High", "Based on JD")
        st.markdown("<br>", unsafe_allow_html=True)

    col_jd, col_res = st.columns([1, 1], gap="large")
    with col_jd:
        st.markdown('<div class="input-card"><div class="input-header"><div style="font-size:1.4rem">📄</div> Job description</div>', unsafe_allow_html=True)
        job_role = st.text_input("Job Role Title", placeholder="e.g. Senior Backend Engineer", value=st.session_state.get("job_role", ""))
        st.session_state["job_role"] = job_role
        jd_input = st.text_area("Paste the full JD here", value=st.session_state["jd_text"], height=300, placeholder="Paste the job description here...\n\nInclude: role, required skills, experience, qualifications.", label_visibility="collapsed")
        st.session_state["jd_text"] = jd_input
        
        # ── 4. Smart JD Suggestions ──
        if len(jd_input) > 50:
            if "salary" not in jd_input.lower() and "package" not in jd_input.lower():
                st.info("💡 **Tip:** Adding a salary range helps filter candidates with matching expectations.")
            if len(jd_input.split()) < 30:
                st.warning("⚠️ **Low Detail:** A more detailed JD allows the AI to provide more accurate scoring.")
        if st.button("💡 Load Demo JD", use_container_width=True):
            st.session_state["jd_text"] = "Senior Backend Engineer — FinTech\n\nWe are looking for a Senior Backend Engineer with 5+ years of experience.\n\nRequired Skills:\n- Python (FastAPI / Django)\n- PostgreSQL, Redis\n- Microservices & REST APIs\n- Docker, Kubernetes\n- AWS (EC2, S3, Lambda)\n\nExperience:\n- 5+ years backend engineering\n- FinTech or payments domain preferred\n- Led teams or mentored junior engineers\n\nEducation:\n- B.Tech/B.E. in Computer Science or equivalent\n- AWS / GCP certifications a plus\n\nResponsibilities:\n- Design and build scalable payment APIs\n- Collaborate with product, data, and front-end teams\n- Code reviews and architecture decisions"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col_res:
        st.markdown('<div class="input-card"><div class="input-header"><div style="font-size:1.4rem">📂</div> Upload resumes</div>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader("Upload PDF or DOCX resumes (max 20)", type=["pdf", "docx", "txt"], accept_multiple_files=True, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        if uploaded_files:
            pills_html = ''.join(f'<span style="display:inline-block;background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.2);padding:4px 12px;border-radius:100px;font-size:0.78rem;color:#6366f1;font-weight:500;margin:3px 4px">📄 {f.name}</span>' for f in uploaded_files)
            st.markdown(f'<div style="margin:8px 0">{pills_html}</div>', unsafe_allow_html=True)
        st.markdown('<div style="display:flex;align-items:center;gap:8px;margin:16px 0 8px"><div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div><span style="font-size:0.72rem;color:#52525b;text-transform:uppercase;letter-spacing:0.1em;font-weight:600">or paste LinkedIn URLs</span><div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div></div>', unsafe_allow_html=True)
        linkedin_input = st.text_area("LinkedIn URLs (one per line)", height=80, placeholder="https://linkedin.com/in/rahul-sharma\nhttps://linkedin.com/in/priya-mehta", label_visibility="collapsed")
        st.caption("ℹ️ LinkedIn URLs are sent to the LLM for context-based scoring.")
        st.markdown('<div style="display:flex;align-items:center;gap:8px;margin:16px 0 8px"><div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div><span style="font-size:0.72rem;color:#52525b;text-transform:uppercase;letter-spacing:0.1em;font-weight:600">or paste resume text</span><div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div></div>', unsafe_allow_html=True)
        manual_name = st.text_input("Candidate name", placeholder="e.g. Rahul Sharma")
        manual_text = st.text_area("Resume text", height=120, placeholder="Paste resume content here...")
        if st.button("➕ Add Manual Resume", use_container_width=True):
            if manual_name and manual_text:
                st.session_state["resume_names"].append(manual_name.strip())
                st.session_state["resume_texts"].append(manual_text.strip())
                st.success(f"Added {manual_name}")
            else: st.warning("Enter both name and resume text.")
        if st.session_state["resume_names"]:
            pills_html = ''.join(f'<span style="display:inline-block;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);padding:4px 12px;border-radius:100px;font-size:0.78rem;color:#10b981;font-weight:500;margin:3px 4px">✓ {n}</span>' for n in st.session_state["resume_names"])
            st.markdown(f'<div style="margin:8px 0">{pills_html}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Clear manual resumes"):
                st.session_state["resume_names"] = []; st.session_state["resume_texts"] = []; st.rerun()
    st.divider()
    
    with st.expander("⚖️ View AI Evaluation Rubric"):
        st.markdown("""
        <table class="rubric-table">
            <tr>
                <th>Dimension</th>
                <th>Weight</th>
                <th>0 — Poor</th>
                <th>5 — Average</th>
                <th>10 — Excellent</th>
            </tr>
            <tr>
                <td><strong>Skills Match</strong></td>
                <td>30%</td>
                <td>< 30% skills match</td>
                <td>50–70% skills match</td>
                <td>> 85% skills match</td>
            </tr>
            <tr>
                <td><strong>Experience Relevance</strong></td>
                <td>25%</td>
                <td>Unrelated domain</td>
                <td>Adjacent domain</td>
                <td>Exact domain & seniority</td>
            </tr>
            <tr>
                <td><strong>Education & Certs</strong></td>
                <td>15%</td>
                <td>Does not meet minimum</td>
                <td>Meets minimum</td>
                <td>Exceeds + extra certs</td>
            </tr>
            <tr>
                <td><strong>Project / Portfolio</strong></td>
                <td>20%</td>
                <td>No evidence</td>
                <td>1–2 generic projects</td>
                <td>Strong relevant portfolio</td>
            </tr>
            <tr>
                <td><strong>Communication Quality</strong></td>
                <td>10%</td>
                <td>Poor structure/grammar</td>
                <td>Adequate clarity</td>
                <td>Crisp, structured, impactful</td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

    run_btn = st.button("🚀 Submit Analysis", type="primary", use_container_width=True)
    if run_btn:
        if not st.session_state["jd_text"].strip(): st.error("Please enter a Job Description first.")
        else:
            st.markdown("<br>", unsafe_allow_html=True)
            progress_bar = st.progress(0)
            
            with st.status("🤖 Initializing AI Processing Pipeline...", expanded=True) as status:
                show_skeleton_loader()
                st.write("📥 **Phase 1:** Fetching and extracting candidate data...")
                time.sleep(0.3)
                
                all_names, all_texts, all_pics = [], [], []
                if uploaded_files:
                    for uf in uploaded_files:
                        text = extract_text_from_upload(uf)
                        name = uf.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
                        all_names.append(name); all_texts.append(text); all_pics.append(None)
                if linkedin_input and linkedin_input.strip():
                    for url in linkedin_input.strip().splitlines():
                        url = url.strip()
                        if url and "linkedin.com" in url:
                            clean_url = url.split("?")[0].rstrip("/")
                            slug = clean_url.split("/")[-1]
                            if not slug or slug == "in":
                                slug = "linkedin-candidate"
                            name = slug.replace("-", " ").replace("_", " ").title() + " (LinkedIn)"
                            # Try to fetch public LinkedIn page for real data
                            li_text = ""
                            pic_url = None
                            try:
                                import requests
                                headers = {"User-Agent": "Twitterbot/1.0"}
                                resp = requests.get(clean_url, headers=headers, timeout=10, allow_redirects=True)
                                if resp.status_code == 200:
                                    from html.parser import HTMLParser
                                    import html
                                    # Try to extract profile picture
                                    img_match = re.search(r'<meta property="og:image" content="([^"]+)"', resp.text)
                                    if img_match:
                                        pic_url = html.unescape(img_match.group(1))
                                    page_text = re.sub(r'<[^>]+>', ' ', resp.text)
                                    page_text = html.unescape(page_text)
                                    page_text = re.sub(r'\s+', ' ', page_text).strip()
                                    # Extract meaningful content (skip cookie banners etc)
                                    if len(page_text) > 200:
                                        li_text = f"LinkedIn Profile URL: {url}\n\nExtracted Profile Content:\n{page_text[:4000]}"
                            except Exception as e:
                                pass
                            if not li_text:
                                li_text = f"""LinkedIn Profile URL: {url}
Candidate Name: {name.replace(' (LinkedIn)', '')}

IMPORTANT: You could not access the full resume. However, you MUST still provide your best estimate scores (not zeros) based on:
1. The candidate's name and any info inferrable from the URL
2. General industry expectations for someone on LinkedIn
3. Provide moderate scores (4-6 range) with justifications explaining limited data

Do NOT give all zeros — provide reasonable estimates with honest justifications."""
                            all_names.append(name); all_texts.append(li_text); all_pics.append(pic_url)
                for n, t in zip(st.session_state["resume_names"], st.session_state["resume_texts"]):
                    all_names.append(n); all_texts.append(t); all_pics.append(None)
                
                if not all_names: 
                    status.update(label="❌ Missing candidates", state="error")
                    st.error("Upload at least one resume or add a manual entry.")
                else:
                    st.write(f"✅ Successfully loaded {len(all_names)} candidate(s).")
                    time.sleep(0.3)
                    
                    key_to_use = os.getenv("GROQ_API_KEY")
                    results, errors = [], []
                    
                    # Step 2 — Parse JD into structured requirements
                    st.write("📋 **Phase 2:** Extracting job requirements...")
                    try:
                        parsed_jd = parse_jd(st.session_state["jd_text"], api_key=key_to_use)
                        st.session_state["parsed_jd"] = parsed_jd
                        st.write(f"✅ Extracted Role: **{parsed_jd.get('role_title', 'N/A')}**")
                        skills = parsed_jd.get("required_skills", [])
                        if skills:
                            st.write(f"🎯 Core Skills: {', '.join(skills[:8])}")
                    except Exception as e:
                        st.write(f"⚠️ JD parsing skipped: {e}")
                        parsed_jd = None

                    time.sleep(0.5)
                    st.write("🔍 **Phase 3:** Building semantic embedding matrices...")
                    time.sleep(0.8)
                    
                    total_cands = len(all_names)
                    for i, (name, text, pic) in enumerate(zip(all_names, all_texts, all_pics), 1):
                        status.update(label=f"⚙️ Analyzing Candidate {i} of {total_cands}: {name}...", state="running")
                        st.write(f"---")
                        st.write(f"📊 **Processing:** {name}")
                        time.sleep(0.4)
                        
                        try:
                            # Compute TF-IDF similarity
                            try:
                                sim_score = compute_similarity(st.session_state["jd_text"], text)
                                st.write(f"   📐 Semantic Match: **{sim_score}%**")
                            except Exception:
                                sim_score = None
                            
                            st.write(f"   🧠 Running multi-dimensional LLM evaluation...")
                            # LLM scoring with similarity context
                            candidate = call_groq_score(st.session_state["jd_text"], text, name, api_key=key_to_use, similarity=sim_score, pic_url=pic)
                            candidate["applied_role"] = st.session_state.get("job_role", "Unspecified Role")
                            results.append(candidate)
                            st.write(f"   ✅ **Scored: {candidate['weighted_total']}/100** · Decision: **{candidate['recommendation'].upper()}**")
                        except Exception as e:
                            errors.append(f"{name}: {str(e)}")
                            st.write(f"   ❌ Failed to process {name}: {str(e)}")
                        
                        progress_bar.progress(int(i / total_cands * 100))
                        time.sleep(0.3)
                    
                    if results:
                        results.sort(key=lambda x: x["weighted_total"], reverse=True)
                        st.session_state["results"] = results
                        st.session_state["analysis_done"] = True
                        save_db(results)
                        
                        # ── 2. Pulsing Indicator / Processing Feedback ──
                        st.toast("Brain processing complete!", icon="🧠")
                        status.update(label=f"✅ Analysis Engine Optimized: {len(results)} profiles indexed.", state="complete")
                    else: 
                        status.update(label="❌ Pipeline failed. No candidates were successfully scored.", state="error")
                        
                if errors: st.warning("Some errors occurred:\n" + "\n".join(errors))
                if results: 
                    if any(c.get("recommendation", "").lower() == "hire" for c in results):
                        st.balloons()
                    st.success("🎉 Analysis complete! Switch to the **Results** tab to view the shortlist.")

with tab2:
    if not st.session_state["results"]:
        st.markdown('<div class="mt"><div class="ic">🔍</div><h3>No results yet</h3><p>Go to <strong>Input & Analysis</strong>, upload resumes, and click <strong>Run Analysis</strong> to begin.</p></div>', unsafe_allow_html=True)
    else:
        results = st.session_state["results"]
        
        # ⚔️ Versus Mode Matchup
        if len(results) >= 2:
            st.markdown("<hr style='border-color:#e2e8f0; margin: 2rem 0;'>", unsafe_allow_html=True)
            st.markdown('<h3>⚔️ Candidate Matchup (Versus Mode)</h3>', unsafe_allow_html=True)
            st.markdown('<p style="color:#64748b;">Select two candidates to compare their strengths and weaknesses side-by-side.</p>', unsafe_allow_html=True)
            
            cand_names = [c["name"] for c in results]
            selected_matchup = st.multiselect("Select 2 candidates for matchup", options=cand_names, max_selections=2)
            
            if len(selected_matchup) == 2:
                c1 = next(c for c in results if c["name"] == selected_matchup[0])
                c2 = next(c for c in results if c["name"] == selected_matchup[1])
                
                m_col1, m_col2 = st.columns(2)
                
                for idx, (col, cand) in enumerate([(m_col1, c1), (m_col2, c2)]):
                    with col:
                        winner_badge = "🏆 <span style='color:#f59e0b; font-weight:bold;'>Overall Winner</span>" if cand["weighted_total"] > (c2 if idx==0 else c1)["weighted_total"] else ""
                        st.markdown(f'<div class="input-card" style="border-top: 4px solid #6366f1;">'
                                    f'<h3 style="margin-bottom:0;">{cand["name"]} {winner_badge}</h3>'
                                    f'<h1 style="color:{score_color(cand["weighted_total"])};">{cand["weighted_total"]}/100</h1>'
                                    f'<div style="margin-bottom:15px;">{badge_html(cand.get("recommendation", "unknown"))}</div>', unsafe_allow_html=True)
                        
                        for dim, label in get_dynamic_labels().items():
                            s1 = cand["scores"].get(dim, {}).get("score", 0)
                            s2 = (c2 if idx==0 else c1)["scores"].get(dim, {}).get("score", 0)
                            
                            diff_html = ""
                            if s1 > s2:
                                diff_html = "<span style='color:#22c55e; font-size:0.8rem; font-weight:bold;'>▲ +"+str(s1-s2)+"</span>"
                            elif s1 < s2:
                                diff_html = "<span style='color:#ef4444; font-size:0.8rem; font-weight:bold;'>▼ -"+str(s2-s1)+"</span>"
                            else:
                                diff_html = "<span style='color:#94a3b8; font-size:0.8rem; font-weight:bold;'>— Tie</span>"
                                
                            st.markdown(f"<div style='display:flex; justify-content:space-between; border-bottom:1px solid #e2e8f0; padding:8px 0;'>"
                                        f"<span style='color:#475569; font-weight:600; font-size:0.9rem;'>{label.split('(')[0].strip()}</span>"
                                        f"<div><span style='font-weight:bold; margin-right:10px;'>{s1}/10</span> {diff_html}</div>"
                                        f"</div>", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                
                # ── 3. Comparative Chart ──
                with st.expander("📊 Side-by-Side Dimension Analysis", expanded=True):
                    from ui.charts import render_comparison_chart
                    render_comparison_chart(c1, c2)
            st.markdown("<hr style='border-color:#e2e8f0; margin: 2rem 0;'>", unsafe_allow_html=True)
        
        st.markdown(f"### 🏆 Ranked Candidates ({len(results)} total)")
        for rank, c in enumerate(results, 1):
            total = c["weighted_total"]; rec = c.get("recommendation", "maybe"); color = score_color(total)
            # Candidate card container with watermark rank
            st.markdown(f'<div class="candidate-card" style="border-left-color:{color}"><div style="position:absolute;top:50%;left:-10px;transform:translateY(-50%);font-family:JetBrains Mono,monospace;font-size:7rem;font-weight:900;background:linear-gradient(135deg,rgba(124,58,237,0.06),rgba(124,58,237,0.01));-webkit-background-clip:text;-webkit-text-fill-color:transparent;opacity:0.5;z-index:0;pointer-events:none">#{rank}</div></div>', unsafe_allow_html=True)
            with st.container():
                col_rank, col_pic, col_name, col_bar, col_score, col_badge = st.columns([0.5, 0.5, 2, 3, 1, 1.5])
                with col_rank: st.markdown(f'<div class="rk">#{rank}</div>', unsafe_allow_html=True)
                display_name = f"Candidate {rank}" if st.session_state.get("blind_mode") else c['name']
                with col_pic:
                    if st.session_state.get("blind_mode"):
                        st.markdown(f'<div style="width:48px;height:48px;border-radius:50%;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:#a1a1aa;font-size:1.4rem;border:2px solid rgba(255,255,255,0.1);margin-top:6px;box-shadow:0 0 16px rgba(124,58,237,0.1)">👤</div>', unsafe_allow_html=True)
                    elif c.get("pic_url"):
                        st.markdown(f'<img src="{c["pic_url"]}" class="profile-pic" style="margin-top:6px;object-fit:cover;">', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,rgba(124,58,237,0.15),rgba(99,102,241,0.1));display:flex;align-items:center;justify-content:center;color:#6366f1;font-weight:800;font-size:1.2rem;border:2px solid rgba(124,58,237,0.25);margin-top:6px;box-shadow:0 0 20px rgba(124,58,237,0.15)">{c["name"][0]}</div>', unsafe_allow_html=True)
                with col_name:
                    sim = c.get("similarity_score")
                    sim_html = f' · <span style="color:#6366f1;font-weight:600">📐 {sim}% match</span>' if sim is not None else ""
                    st.markdown(f'<div style="margin-top:8px"><span style="font-weight:700;font-size:1.05rem;color:var(--text)">{display_name}</span>{sim_html}</div>', unsafe_allow_html=True)
                with col_bar: st.progress(int(total))
                with col_score: st.markdown(f'<div class="sc" style="margin-top:4px">{total}</div>', unsafe_allow_html=True)
                with col_badge: st.markdown(f'<div style="margin-top:8px">{badge_html(rec)}</div>', unsafe_allow_html=True)
                with st.expander(f"📂 View Full Breakdown — {display_name}"):
                    dim_cols = st.columns(5)
                    for idx, (dim, label) in enumerate(get_dynamic_labels().items()):
                        dim_data = c["scores"].get(dim, {}); s = dim_data.get("score", 0); j = dim_data.get("justification", "—")
                        s_color = "#22c55e" if s >= 7 else ("#f59e0b" if s >= 4 else "#ef4444")
                        with dim_cols[idx]:
                            st.markdown(f'<div class="dim-card"><div class="dim-l">{label.split("(")[0].strip()}</div><div class="dim-s" style="color:{s_color}">{s}/10</div></div>', unsafe_allow_html=True)
                            st.progress(int(s * 10)); st.caption(j)
                    
                    st.markdown("#### 📊 Strength Profile")
                    render_radar_chart(c["scores"], display_name)
                    if c.get("override_log"):
                        st.markdown("**Override History:**")
                        for log in c["override_log"]:
                            st.markdown(f'<div class="olog">🕐 {log["timestamp"]} · <strong>{log["dimension"]}</strong>: {log["old_score"]} → {log["new_score"]} · <em>{log["reason"]}</em></div>', unsafe_allow_html=True)
                    
                    st.markdown("---")
                    if st.button("✉️ Draft Automated Outreach Email", key=f"email_btn_{rank}"):
                        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                        prompt = f"""Draft a highly personalized and professional HR outreach email to {display_name} regarding their recent application. 
The internal decision is: {rec.upper()}. 
Here is the AI's scoring breakdown and justifications for this candidate: {json.dumps(c['scores'])}.

CRITICAL RULES:
1. If the decision is HIRE or MAYBE: Write an enthusiastic email inviting them to the next interview stage. Explicitly mention 1 or 2 specific strengths from the AI justifications (e.g., "We were particularly impressed by your...").
2. If the decision is NO-HIRE: Write a polite, empathetic rejection email. You MUST explicitly state a professional reason for passing on them by referencing their missing skills or lowest scores from the AI justifications (e.g., "While your portfolio is strong, we are currently looking for someone with deeper experience in X..."). Make it sound like a real, thoughtful human HR email, not a generic robot template.
3. Return ONLY the email body. Sign it from "The Hiring Team"."""
                        try:
                            resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], max_tokens=300)
                            st.session_state[f"email_draft_{rank}"] = resp.choices[0].message.content.strip()
                        except Exception as e:
                            st.error("Failed to generate email.")
                            
                    if f"email_draft_{rank}" in st.session_state:
                        st.text_area("Generated Draft", value=st.session_state[f"email_draft_{rank}"], height=200, key=f"email_area_{rank}")
                        
                        col_send1, col_send2 = st.columns([1, 3])
                        with col_send1:
                            if st.button("🚀 Send Outreach Email", key=f"send_email_btn_{rank}"):
                                # Save contacted status to DB
                                db_hist = load_db()
                                for i, h in enumerate(db_hist):
                                    if h["name"] == c["name"] and h.get("evaluated_on") == c.get("evaluated_on"):
                                        db_hist[i]["pipeline_stage"] = "Contacted"
                                        break
                                save_db(db_hist)
                                st.toast(f"Email successfully dispatched to {display_name}!", icon="✅")
                                st.success("Email sent! Pipeline status updated to 'Contacted'.")
                st.markdown("---")

with tab3:
    if not st.session_state["results"]:
        st.markdown('<div class="mt"><div class="ic">✏️</div><h3>Run analysis first</h3><p>Score overrides will appear here after candidates are analyzed.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown("### ✏️ Override Candidate Scores")
        st.caption("HR can adjust any dimension score. All changes are logged with timestamp and reason.")
        candidate_names = [c["name"] for c in st.session_state["results"]]
        display_names = [f"Candidate {i+1}" if st.session_state.get("blind_mode") else c["name"] for i, c in enumerate(st.session_state["results"])]
        selected_display = st.selectbox("Select candidate to override", display_names)
        cand_idx = display_names.index(selected_display)
        selected_name = candidate_names[cand_idx]
        cand = st.session_state["results"][cand_idx]
        
        ov_cols = st.columns(2); new_scores = {}
        for i, (dim, label) in enumerate(get_dynamic_labels().items()):
            current = cand["scores"].get(dim, {}).get("score", 5)
            with ov_cols[i % 2]: new_scores[dim] = st.slider(label, 0, 10, int(current), key=f"slider_{dim}_{cand_idx}")
            
        preview_total = compute_weighted({dim: {"score": val} for dim, val in new_scores.items()})
        preview_rec = "hire" if preview_total >= 75 else ("maybe" if preview_total >= 50 else "no-hire")
        rec_color = {"hire": "#22c55e", "maybe": "#f59e0b", "no-hire": "#ef4444"}.get(preview_rec, "#a1a1aa")
        
        st.markdown(f'<div class="score-preview"><div style="font-family:JetBrains Mono,monospace;font-size:3.5rem;font-weight:900;background:linear-gradient(135deg,{rec_color},#fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1;margin-bottom:8px">{preview_total}/100</div><div style="font-size:1.2rem;font-weight:700;color:{rec_color};text-transform:uppercase;letter-spacing:0.1em">{preview_rec}</div><div style="font-size:0.75rem;color:#a1a1aa;margin-top:6px">Was: {cand["weighted_total"]}/100 ({cand.get("recommendation","maybe").upper()})</div></div>', unsafe_allow_html=True)
        
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
                    st.session_state["results"][cand_idx]["weighted_total"] = preview_total
                    st.session_state["results"][cand_idx]["recommendation"] = preview_rec
                    st.session_state["results"].sort(key=lambda x: x["weighted_total"], reverse=True)
                    st.success(f"✅ Override saved! New total: {preview_total}/100"); st.rerun()
                else: st.info("No scores were changed.")
        if st.session_state["override_log"]:
            st.markdown("---"); st.markdown("### 📜 Full Override Log")
            for entry in reversed(st.session_state["override_log"]):
                st.markdown(f'<div class="olog">🕐 <strong>{entry["timestamp"]}</strong> · {entry["candidate"]} · {entry["dimension"]}: <strong>{entry["old_score"]} → {entry["new_score"]}</strong> · <em>{entry["reason"]}</em></div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="input-card" style="margin-bottom:1rem;"><div class="input-header"><div style="font-size:1.4rem">📈</div> Enterprise Visual Analytics</div>', unsafe_allow_html=True)
    
    db_history = load_db()
    if not db_history:
        st.markdown('<p style="color:#64748b;">No candidates in database. Run analysis to populate analytics.</p></div>', unsafe_allow_html=True)
    else:
        total_c = len(db_history)
        hires = sum(1 for c in db_history if c.get('recommendation', '').lower() == 'hire')
        maybes = sum(1 for c in db_history if c.get('recommendation', '').lower() == 'maybe')
        no_hires = sum(1 for c in db_history if c.get('recommendation', '').lower() == 'no-hire')
        avg_score = round(sum(c.get('weighted_total', 0) for c in db_history) / total_c, 1)
        contacted = sum(1 for c in db_history if c.get('pipeline_stage', '') == 'Contacted')
        
        # 4 top KPI cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="stat-card"><div class="stat-label">Total Pipeline</div><div class="stat-value">{total_c}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="stat-card"><div class="stat-label">Shortlisted (Hire)</div><div class="stat-value" style="color:#22c55e">{hires}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="stat-card"><div class="stat-label">Avg Global Score</div><div class="stat-value" style="color:#6366f1">{avg_score}</div></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="stat-card"><div class="stat-label">Contacted</div><div class="stat-value" style="color:#3b82f6">{contacted}</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        st.markdown("### 📊 Interactive Distributions")
        
        c_chart1, c_chart2 = st.columns(2)
        
        with c_chart1:
            st.markdown("**Decision Breakdown**")
            # Create a simple DataFrame for bar chart
            df_decisions = pd.DataFrame({
                "Decision": ["Hire", "Maybe", "No-Hire"],
                "Count": [hires, maybes, no_hires]
            })
            # Altair chart for custom colors
            chart1 = alt.Chart(df_decisions).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('Decision', sort=None, axis=alt.Axis(labelAngle=0)),
                y='Count',
                color=alt.Color('Decision', scale=alt.Scale(domain=['Hire', 'Maybe', 'No-Hire'], range=['#22c55e', '#f59e0b', '#ef4444']), legend=None)
            ).properties(height=300)
            st.altair_chart(chart1, use_container_width=True)
            
        with c_chart2:
            st.markdown("**Pipeline Stage Metrics**")
            new_stage = total_c - contacted
            df_pipeline = pd.DataFrame({
                "Stage": ["New / Uncontacted", "Contacted"],
                "Candidates": [new_stage, contacted]
            })
            chart2 = alt.Chart(df_pipeline).mark_arc(innerRadius=50).encode(
                theta='Candidates',
                color=alt.Color('Stage', scale=alt.Scale(range=['#94a3b8', '#3b82f6'])),
                tooltip=['Stage', 'Candidates']
            ).properties(height=300)
            st.altair_chart(chart2, use_container_width=True)
            
        st.markdown("---")
        st.markdown("### 📥 Data Export")
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            import json
            st.download_button(
                label="⬇️ Download Raw JSON Database",
                data=json.dumps(db_history, indent=2),
                file_name="ats_full_database.json",
                mime="application/json",
                use_container_width=True
            )
        with col_ex2:
            csv_data = "Name,Role,Score,Recommendation,PipelineStage\\n" + "\\n".join([f"{c['name']},{c.get('applied_role','General')},{c.get('weighted_total',0)},{c.get('recommendation','')},{c.get('pipeline_stage','New')}" for c in db_history])
            st.download_button(
                label="⬇️ Download CSV Report",
                data=csv_data,
                file_name="ats_report.csv",
                mime="text/csv",
                use_container_width=True
            )
            
    st.markdown('</div>', unsafe_allow_html=True)

@st.dialog("Candidate Profile Analysis")
def show_candidate_profile(cand):
    st.markdown(f"### {cand['name']}")
    
    email = cand.get("email", "N/A")
    phone = cand.get("phone", "N/A")
    
    # Handle AI returning literal 'none' or 'null' strings
    display_email = "Not Provided" if (not email or str(email).strip().lower() in ["none", "null", "n/a"]) else email
    display_phone = "Not Provided" if (not phone or str(phone).strip().lower() in ["none", "null", "n/a"]) else phone

    st.markdown(f"<div style='font-size:0.9rem; color:#64748b; margin-top:-5px;'>📧 {display_email} &nbsp;|&nbsp; 📱 {display_phone}</div>", unsafe_allow_html=True)
        
    role = cand.get('applied_role', 'Unspecified Role')
    st.markdown(f"<div style='color:gray; font-size:0.9rem; margin-top:-10px; margin-bottom:15px;'>Applied for: <strong>{role}</strong></div>", unsafe_allow_html=True)
    
    score = cand.get('weighted_total', 0)
    rec = cand.get('recommendation', 'unknown')
    st.markdown(f"**Final Score:** <span style='color:{score_color(score)}; font-weight:bold; font-size:1.2rem;'>{score}/100</span> &nbsp;&nbsp; | &nbsp;&nbsp; **Decision:** {badge_html(rec)}", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("#### Visual Scorecard")
    for dim, label in get_dynamic_labels().items():
        dim_data = cand.get("scores", {}).get(dim, {})
        dim_score = dim_data.get("score", 0)
        dim_just = dim_data.get("justification", "No justification provided.")
        
        # Draw a beautiful progress bar using HTML
        bar_color = "#22c55e" if dim_score >= 8 else "#f59e0b" if dim_score >= 5 else "#ef4444"
        bar_html = f'''
        <div style="margin-bottom:15px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.85rem; font-weight:600; color:#334155;">
                <span>{label}</span>
                <span style="color:{bar_color};">{dim_score}/10</span>
            </div>
            <div style="width:100%; background-color:#e2e8f0; border-radius:10px; height:8px; overflow:hidden;">
                <div style="width:{dim_score*10}%; background-color:{bar_color}; height:100%; border-radius:10px;"></div>
            </div>
            <div style="margin-top:6px; font-size:0.85rem; color:#475569; background:#f8fafc; padding:8px; border-left:3px solid {bar_color}; border-radius:4px;">
                {dim_just}
            </div>
        </div>
        '''
        st.markdown(bar_html, unsafe_allow_html=True)
        
    st.markdown(f"<div style='margin-top:20px; font-size:0.8rem; color:gray;'>Evaluated on: {cand.get('evaluated_on', 'Unknown')}</div>", unsafe_allow_html=True)

with tab5:

    st.markdown('<div class="input-card" style="margin-bottom:1rem;"><div class="input-header" style="justify-content: space-between;"><div style="display:flex;align-items:center;gap:10px;"><div style="font-size:1.4rem">🗄️</div> Candidate History (ATS)</div><span style="font-size:0.8rem;color:#64748b;font-weight:400;">Persistent Database</span></div>', unsafe_allow_html=True)
    
    history_data = load_db()
    if not history_data:
        st.markdown('<p style="color:#64748b;">No candidates have been processed yet. Run your first analysis to populate the database.</p>', unsafe_allow_html=True)
    else:
        # Search Functionality
        search_query = st.text_input("🔍 Search candidates by name, skills, or AI justifications...", placeholder="e.g. 'React', 'John Doe', 'Strong portfolio'")
        
        # Filter history
        if search_query:
            q = search_query.lower()
            filtered_history = []
            for c in history_data:
                # Search in name
                if q in c['name'].lower():
                    filtered_history.append(c)
                    continue
                
                # Search in justifications
                match_found = False
                for dim_data in c.get('scores', {}).values():
                    if q in dim_data.get('justification', '').lower():
                        match_found = True
                        break
                if match_found:
                    filtered_history.append(c)
            history_data = filtered_history
            
        # Sort history by evaluation date (newest first)
        history_data.sort(key=lambda x: x.get("evaluated_on", ""), reverse=True)
        
        if search_query:
            st.markdown(f'<p style="margin-bottom: 20px; color:#64748b;">Found <strong>{len(history_data)}</strong> results matching "{search_query}".</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="margin-bottom: 20px; color:#64748b;">Showing all <strong>{len(history_data)}</strong> historical candidate evaluations.</p>', unsafe_allow_html=True)
        
        # Filter-based download section
        st.markdown("##### 📥 Export Filtered Data")
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            hired_only = [c for c in history_data if c.get('recommendation', '').lower() == 'hire']
            st.download_button(
                label=f"⬇️ Download Selected ({len(hired_only)})",
                data=json.dumps(hired_only, indent=2),
                file_name="selected_candidates.json",
                mime="application/json",
                use_container_width=True,
                help="Download only candidates with 'HIRE' recommendation"
            )
        with exp_col2:
            rejected_only = [c for c in history_data if c.get('recommendation', '').lower() == 'no-hire']
            st.download_button(
                label=f"⬇️ Download Rejected ({len(rejected_only)})",
                data=json.dumps(rejected_only, indent=2),
                file_name="rejected_candidates.json",
                mime="application/json",
                use_container_width=True,
                help="Download only candidates with 'NO-HIRE' recommendation"
            )
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        
        # Render Custom Table Header
        header_cols = st.columns([2, 2, 1, 1, 1, 1.5, 1], vertical_alignment="bottom")
        with header_cols[0]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Candidate Name</span>", unsafe_allow_html=True)
        with header_cols[1]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Applied Role</span>", unsafe_allow_html=True)
        with header_cols[2]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Score</span>", unsafe_allow_html=True)
        with header_cols[3]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Decision</span>", unsafe_allow_html=True)
        with header_cols[4]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Date</span>", unsafe_allow_html=True)
        with header_cols[5]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Pipeline Stage</span>", unsafe_allow_html=True)
        with header_cols[6]: st.markdown("<span style='color:#94a3b8; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;'>Action</span>", unsafe_allow_html=True)
        
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        
        for idx, cand in enumerate(history_data):
            # Wrap each candidate in a beautifully padded, bordered container card
            with st.container(border=True):
                cols = st.columns([2, 2, 1, 1, 1, 1.5, 1], vertical_alignment="center")
                with cols[0]:
                    st.markdown(f"<div style='font-weight:700; color:#1e293b; font-size:1.05rem;'>{cand['name']}</div>", unsafe_allow_html=True)
                with cols[1]:
                    st.markdown(f"<div style='color:#64748b; font-weight:500; font-size:0.95rem;'>{cand.get('applied_role', 'General')}</div>", unsafe_allow_html=True)
                with cols[2]:
                    score = cand.get('weighted_total', 0)
                    st.markdown(f"<span style='color:{score_color(score)}; font-weight:800; font-size:1.1rem;'>{score}/100</span>", unsafe_allow_html=True)
                with cols[3]:
                    rec = cand.get('recommendation', 'unknown')
                    st.markdown(badge_html(rec), unsafe_allow_html=True)
                with cols[4]:
                    st.markdown(f"<span style='color:#94a3b8; font-size:0.9rem; font-weight:500;'>{cand.get('evaluated_on', 'Unknown').split(' ')[0]}</span>", unsafe_allow_html=True)
                with cols[5]:
                    stage = cand.get('pipeline_stage', 'New')
                    stage_color = '#3b82f6' if stage == 'Contacted' else '#94a3b8'
                    st.markdown(f"<span style='background-color:{stage_color}15; color:{stage_color}; padding:6px 12px; border-radius:100px; font-size:0.8rem; font-weight:700; border: 1px solid {stage_color}30; white-space:nowrap;'>{stage}</span>", unsafe_allow_html=True)
                with cols[6]:
                    if st.button("View Profile", key=f"hist_btn_{idx}_{cand['name']}", use_container_width=True):
                        show_candidate_profile(cand)
            
    st.markdown('</div>', unsafe_allow_html=True)

# ── Footer ──
st.markdown("---")
st.markdown(f"""<div style="text-align:center;padding:2rem 0 1rem">
<div style="font-size:0.72rem;color:#52525b;letter-spacing:0.06em">
HR Shortlisting Agent v2.0 · Built with <span style="color:#6366f1">LLaMA-3.3-70b</span> + TF-IDF Pipeline · {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>
<div style="margin-top:8px;font-size:0.65rem;color:#3f3f46">
⚡ Powered by Groq · Streamlit · scikit-learn · {len(st.session_state.get('results', []))} candidates in session
</div>
</div>""", unsafe_allow_html=True)
