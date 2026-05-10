import re

with open("app.py", "r") as f:
    code = f.read()

# I want to replace the ATS Database loop from cols = st.columns... to the end of the loop
target_old = """        cols = st.columns([2, 2, 1, 1, 1, 1.5, 1])
        with cols[0]: st.markdown("**Candidate Name**")
        with cols[1]: st.markdown("**Applied Role**")
        with cols[2]: st.markdown("**Score**")
        with cols[3]: st.markdown("**Decision**")
        with cols[4]: st.markdown("**Date**")
        with cols[5]: st.markdown("**Pipeline Stage**")
        with cols[6]: st.markdown("**Action**")
        st.markdown("<hr style='margin-top:0; border-color:#e2e8f0;'>", unsafe_allow_html=True)
        
        for idx, cand in enumerate(history_data):
            cols = st.columns([2, 2, 1, 1, 1, 1.5, 1])
            with cols[0]:
                st.markdown(f"<div style='font-weight:600; color:#0f172a;'>{cand['name']}</div>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"<div style='color:#64748b; font-size:0.9rem;'>{cand.get('applied_role', 'General')}</div>", unsafe_allow_html=True)
            with cols[2]:
                score = cand.get('weighted_total', 0)
                st.markdown(f"<span style='color:{score_color(score)}; font-weight:700;'>{score}/100</span>", unsafe_allow_html=True)
            with cols[3]:
                rec = cand.get('recommendation', 'unknown')
                st.markdown(badge_html(rec), unsafe_allow_html=True)
            with cols[4]:
                st.markdown(f"<span style='color:#64748b; font-size:0.85rem;'>{cand.get('evaluated_on', 'Unknown').split(' ')[0]}</span>", unsafe_allow_html=True)
            with cols[5]:
                stage = cand.get('pipeline_stage', 'New')
                stage_color = '#3b82f6' if stage == 'Contacted' else '#94a3b8'
                st.markdown(f"<span style='background-color:{stage_color}20; color:{stage_color}; padding:4px 8px; border-radius:100px; font-size:0.75rem; font-weight:700; border: 1px solid {stage_color}40;'>{stage}</span>", unsafe_allow_html=True)
            with cols[6]:
                if st.button("View Profile", key=f"hist_btn_{idx}_{cand['name']}"):
                    show_candidate_profile(cand)
            st.markdown("<hr style='margin:10px 0; border-color:#f1f5f9;'>", unsafe_allow_html=True)"""

target_new = """        # Render Custom Table Header
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
                        show_candidate_profile(cand)"""

if target_old in code:
    code = code.replace(target_old, target_new)
    with open("app.py", "w") as f:
        f.write(code)
    print("Success")
else:
    print("Target not found")
