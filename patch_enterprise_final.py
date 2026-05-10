import re

with open("app.py", "r") as f:
    code = f.read()

# 1. Inject Sidebar Rubric Settings at the very top right after st.set_page_config or st.markdown CSS
sidebar_code = """
import pandas as pd
import altair as alt

# --- Dynamic Rubric Settings (Sidebar) ---
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

def get_dynamic_labels():
    return {
        "skills_match": f"Skills Match ({st.session_state.get('w_skills', 30)}%)",
        "experience_relevance": f"Experience Relevance ({st.session_state.get('w_exp', 25)}%)",
        "education_certs": f"Education & Certs ({st.session_state.get('w_edu', 15)}%)",
        "project_portfolio": f"Project / Portfolio ({st.session_state.get('w_proj', 20)}%)",
        "communication_quality": f"Communication Quality ({st.session_state.get('w_comm', 10)}%)"
    }

DIM_LABELS = get_dynamic_labels() # For initial load, though we should call it dynamically.
"""

# We'll replace the static WEIGHTS and DIM_LABELS block with this
static_weights_target = """WEIGHTS = {"skills_match": 0.30, "experience_relevance": 0.25, "education_certs": 0.15, "project_portfolio": 0.20, "communication_quality": 0.10}
DIM_LABELS = {"skills_match": "Skills Match (30%)", "experience_relevance": "Experience Relevance (25%)", "education_certs": "Education & Certs (15%)", "project_portfolio": "Project / Portfolio (20%)", "communication_quality": "Communication Quality (10%)"}"""

if static_weights_target in code:
    code = code.replace(static_weights_target, sidebar_code)

# 2. Update compute_weighted to use dynamic weights
old_compute_weighted = """def compute_weighted(scores_dict):
    total = 0.0
    for dim, w in WEIGHTS.items():
        total += scores_dict.get(dim, {}).get("score", 0) * w * 10
    return round(total, 1)"""

new_compute_weighted = """def compute_weighted(scores_dict):
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
    return round(total, 1)"""

code = code.replace(old_compute_weighted, new_compute_weighted)

# Update references to DIM_LABELS to call get_dynamic_labels()
code = code.replace("DIM_LABELS.items()", "get_dynamic_labels().items()")


# 3. Update Tab 4 to include High-Fidelity Analytics
# Let's find "with tab4:" block and replace it
tab4_pattern = re.compile(r"with tab4:.*?(?=with tab5:)", re.DOTALL)
new_tab4 = """with tab4:
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

"""

code = tab4_pattern.sub(new_tab4, code)

# Let's add the block before the Analyze button to check if valid_weights is true
analyze_btn_target = """if st.button("🚀 Run AI Analysis", use_container_width=True):
            if not st.session_state["resumes"] or not job_role:"""

new_analyze_btn = """if st.button("🚀 Run AI Analysis", use_container_width=True):
            if not st.session_state.get('valid_weights', True):
                st.error("Cannot run analysis: Rubric weights must equal 100%. Adjust sliders in the sidebar.")
            elif not st.session_state["resumes"] or not job_role:"""

code = code.replace(analyze_btn_target, new_analyze_btn)

# Write back
with open("app.py", "w") as f:
    f.write(code)

