import re

with open("app.py", "r") as f:
    content = f.read()

# 1. Update tab names
content = content.replace('"📊  Report & Export"', '"📈  Analytics & Export"')

# 2. Add Job Role input in Tab 1
old_input_header = """<div class="input-card"><div class="input-header"><div style="font-size:1.4rem">📄</div> Job description</div>"""
new_input_header = """<div class="input-card"><div class="input-header"><div style="font-size:1.4rem">📄</div> Job description</div>
        job_role = st.text_input("Job Role Title", placeholder="e.g. Senior Backend Engineer", value=st.session_state.get("job_role", ""))
        st.session_state["job_role"] = job_role"""
content = content.replace(old_input_header, new_input_header)

# 3. Inject role into candidate data during analysis loop
old_call = """candidate = call_groq_score(st.session_state["jd_text"], text, name, api_key=key_to_use, similarity=sim_score, pic_url=pic)
                            results.append(candidate)"""
new_call = """candidate = call_groq_score(st.session_state["jd_text"], text, name, api_key=key_to_use, similarity=sim_score, pic_url=pic)
                            candidate["applied_role"] = st.session_state.get("job_role", "Unspecified Role")
                            results.append(candidate)"""
content = content.replace(old_call, new_call)

# 4. Enhance the Profile Dialog with Progress Bars
old_dialog = """@st.dialog("Candidate Profile Analysis")
def show_candidate_profile(cand):
    st.markdown(f"### {cand['name']}")
    score = cand.get('weighted_total', 0)
    rec = cand.get('recommendation', 'unknown')
    st.markdown(f"**Final Score:** <span style='color:{score_color(score)}; font-weight:bold; font-size:1.2rem;'>{score}/100</span> &nbsp;&nbsp; | &nbsp;&nbsp; **Decision:** {badge_html(rec)}", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("#### Detailed Breakdown")
    for dim, label in DIM_LABELS.items():
        dim_data = cand.get("scores", {}).get(dim, {})
        dim_score = dim_data.get("score", 0)
        dim_just = dim_data.get("justification", "No justification provided.")
        st.markdown(f"**{label}**: `{dim_score}/10`")
        st.info(dim_just)
        
    st.markdown(f"<div style='margin-top:20px; font-size:0.8rem; color:gray;'>Evaluated on: {cand.get('evaluated_on', 'Unknown')}</div>", unsafe_allow_html=True)"""

new_dialog = """@st.dialog("Candidate Profile Analysis")
def show_candidate_profile(cand):
    st.markdown(f"### {cand['name']}")
    role = cand.get('applied_role', 'Unspecified Role')
    st.markdown(f"<div style='color:gray; font-size:0.9rem; margin-top:-10px; margin-bottom:15px;'>Applied for: <strong>{role}</strong></div>", unsafe_allow_html=True)
    
    score = cand.get('weighted_total', 0)
    rec = cand.get('recommendation', 'unknown')
    st.markdown(f"**Final Score:** <span style='color:{score_color(score)}; font-weight:bold; font-size:1.2rem;'>{score}/100</span> &nbsp;&nbsp; | &nbsp;&nbsp; **Decision:** {badge_html(rec)}", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("#### Visual Scorecard")
    for dim, label in DIM_LABELS.items():
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
        
    st.markdown(f"<div style='margin-top:20px; font-size:0.8rem; color:gray;'>Evaluated on: {cand.get('evaluated_on', 'Unknown')}</div>", unsafe_allow_html=True)"""
content = content.replace(old_dialog, new_dialog)

# 5. Add Role column to ATS Database
old_cols = """        cols = st.columns([2, 1, 1, 1, 1])
        with cols[0]: st.markdown("**Candidate Name**")
        with cols[1]: st.markdown("**Global Score**")
        with cols[2]: st.markdown("**Recommendation**")
        with cols[3]: st.markdown("**Evaluated On**")
        with cols[4]: st.markdown("**Action**")"""

new_cols = """        cols = st.columns([2, 2, 1, 1, 1, 1])
        with cols[0]: st.markdown("**Candidate Name**")
        with cols[1]: st.markdown("**Applied Role**")
        with cols[2]: st.markdown("**Global Score**")
        with cols[3]: st.markdown("**Recommendation**")
        with cols[4]: st.markdown("**Evaluated On**")
        with cols[5]: st.markdown("**Action**")"""
content = content.replace(old_cols, new_cols)

old_row = """            cols = st.columns([2, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f"<div style='font-weight:600; color:#0f172a;'>{cand['name']}</div>", unsafe_allow_html=True)
            with cols[1]:
                score = cand.get('weighted_total', 0)
                st.markdown(f"<span style='color:{score_color(score)}; font-weight:700;'>{score} / 100</span>", unsafe_allow_html=True)
            with cols[2]:
                rec = cand.get('recommendation', 'unknown')
                st.markdown(badge_html(rec), unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f"<span style='color:#64748b; font-size:0.85rem;'>{cand.get('evaluated_on', 'Unknown')}</span>", unsafe_allow_html=True)
            with cols[4]:
                if st.button("View Profile", key=f"hist_btn_{idx}_{cand['name']}"):
                    show_candidate_profile(cand)"""

new_row = """            cols = st.columns([2, 2, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f"<div style='font-weight:600; color:#0f172a;'>{cand['name']}</div>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"<div style='color:#64748b; font-size:0.9rem;'>{cand.get('applied_role', 'General')}</div>", unsafe_allow_html=True)
            with cols[2]:
                score = cand.get('weighted_total', 0)
                st.markdown(f"<span style='color:{score_color(score)}; font-weight:700;'>{score} / 100</span>", unsafe_allow_html=True)
            with cols[3]:
                rec = cand.get('recommendation', 'unknown')
                st.markdown(badge_html(rec), unsafe_allow_html=True)
            with cols[4]:
                st.markdown(f"<span style='color:#64748b; font-size:0.85rem;'>{cand.get('evaluated_on', 'Unknown')}</span>", unsafe_allow_html=True)
            with cols[5]:
                if st.button("View Profile", key=f"hist_btn_{idx}_{cand['name']}"):
                    show_candidate_profile(cand)"""
content = content.replace(old_row, new_row)

# 6. Completely Overhaul Tab 4 (Analytics)
old_tab4_start = "with tab4:"
# We need to replace the entire with tab4 block up to with tab5. We will use regex or careful replacement.
import re
tab4_pattern = re.compile(r"with tab4:.*?(?=with tab5:)", re.DOTALL)

new_tab4 = """with tab4:
    st.markdown('<div class="input-card"><div class="input-header"><div style="font-size:1.4rem">📈</div> Pipeline Analytics & Export</div>', unsafe_allow_html=True)
    
    db_history = load_db()
    if not db_history:
        st.info("Run an analysis to generate analytics.")
    else:
        total_evals = len(db_history)
        hires = sum(1 for c in db_history if c.get("recommendation", "").lower() == "hire")
        maybes = sum(1 for c in db_history if c.get("recommendation", "").lower() == "maybe")
        no_hires = sum(1 for c in db_history if c.get("recommendation", "").lower() == "no-hire")
        avg_score = round(sum(c.get("weighted_total", 0) for c in db_history) / total_evals, 1) if total_evals > 0 else 0
        
        # Render beautiful metrics
        st.markdown(f'''
        <div style="display:flex; gap:20px; margin-bottom:30px;">
            <div style="flex:1; background:#f8fafc; border:1px solid #e2e8f0; padding:20px; border-radius:12px; text-align:center;">
                <div style="font-size:0.9rem; color:#64748b; font-weight:600; text-transform:uppercase;">Total Candidates</div>
                <div style="font-size:2.5rem; color:#0f172a; font-weight:800;">{total_evals}</div>
            </div>
            <div style="flex:1; background:#f0fdf4; border:1px solid #bbf7d0; padding:20px; border-radius:12px; text-align:center;">
                <div style="font-size:0.9rem; color:#166534; font-weight:600; text-transform:uppercase;">Shortlisted</div>
                <div style="font-size:2.5rem; color:#15803d; font-weight:800;">{hires}</div>
            </div>
            <div style="flex:1; background:#fef2f2; border:1px solid #fecaca; padding:20px; border-radius:12px; text-align:center;">
                <div style="font-size:0.9rem; color:#991b1b; font-weight:600; text-transform:uppercase;">Rejected</div>
                <div style="font-size:2.5rem; color:#b91c1c; font-weight:800;">{no_hires}</div>
            </div>
            <div style="flex:1; background:#eff6ff; border:1px solid #bfdbfe; padding:20px; border-radius:12px; text-align:center;">
                <div style="font-size:0.9rem; color:#1e3a8a; font-weight:600; text-transform:uppercase;">Average Score</div>
                <div style="font-size:2.5rem; color:#1d4ed8; font-weight:800;">{avg_score}</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 💾 Export Data")
        
        # Keep the export functionality but clean it up
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.download_button(
                label="⬇️ Download Raw JSON Database",
                data=json.dumps(db_history, indent=2),
                file_name="ats_full_database.json",
                mime="application/json",
                use_container_width=True
            )
        with col_ex2:
            st.download_button(
                label="⬇️ Download CSV Report",
                data="Name,Role,Score,Recommendation\\n" + "\\n".join([f"{c['name']},{c.get('applied_role','General')},{c.get('weighted_total',0)},{c.get('recommendation','')}" for c in db_history]),
                file_name="ats_report.csv",
                mime="text/csv",
                use_container_width=True
            )
            
    st.markdown('</div>', unsafe_allow_html=True)

"""

content = tab4_pattern.sub(new_tab4, content)

with open("app.py", "w") as f:
    f.write(content)
