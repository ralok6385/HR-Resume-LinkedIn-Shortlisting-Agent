import re

with open("app.py", "r") as f:
    code = f.read()

# 1. Update call_groq_score
old_prompt = """{"name": "candidate name", "scores": {"skills_match": {"score": 0, "justification": "one concise line"}, "experience_relevance": {"score": 0, "justification": "one concise line"}, "education_certs": {"score": 0, "justification": "one concise line"}, "project_portfolio": {"score": 0, "justification": "one concise line"}, "communication_quality": {"score": 0, "justification": "one concise line"}}, "recommendation": "hire"}"""
new_prompt = """{"name": "candidate name", "email": "email if found else none", "phone": "phone if found else none", "scores": {"skills_match": {"score": 0, "justification": "one concise line"}, "experience_relevance": {"score": 0, "justification": "one concise line"}, "education_certs": {"score": 0, "justification": "one concise line"}, "project_portfolio": {"score": 0, "justification": "one concise line"}, "communication_quality": {"score": 0, "justification": "one concise line"}}, "recommendation": "hire"}"""

code = code.replace(old_prompt, new_prompt)


# 2. Add Versus Mode at the top of Tab 2
# Let's insert Versus mode right after `results = st.session_state["results"]`
versus_code = """        results = st.session_state["results"]
        
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
                        
                        for dim, label in DIM_LABELS.items():
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
            st.markdown("<hr style='border-color:#e2e8f0; margin: 2rem 0;'>", unsafe_allow_html=True)
        
"""

code = code.replace('        results = st.session_state["results"]\n', versus_code)

# 3. Add Send Email Dispatch
# We need to find the draft email text area and add a button.
draft_email_target = """email_body = st.text_area("Drafted Email", email_body, height=300, key=f"email_area_{rank}")"""

new_draft_email = """email_body = st.text_area("Drafted Email", email_body, height=300, key=f"email_area_{rank}")
                        
                        col_send1, col_send2 = st.columns([1, 4])
                        with col_send1:
                            if st.button("🚀 Send Outreach Email", key=f"send_email_btn_{rank}"):
                                # Save contacted status to DB
                                db_hist = load_db()
                                for i, h in enumerate(db_hist):
                                    if h["name"] == c["name"] and h.get("evaluated_on") == c.get("evaluated_on"):
                                        db_hist[i]["pipeline_stage"] = "Contacted"
                                        break
                                save_db(db_hist)
                                st.toast(f"Email successfully dispatched to {c['name']} via simulated SendGrid!", icon="✅")
                                st.success("Email sent! Pipeline status updated to 'Contacted'.")"""

code = code.replace(draft_email_target, new_draft_email)

# 4. Show Pipeline Stage in ATS Database & Email/Phone in Profile
# Update show_candidate_profile to show contact info
profile_target = """st.markdown(f"### {cand['name']}")
    role = cand.get('applied_role', 'Unspecified Role')"""
new_profile = """st.markdown(f"### {cand['name']}")
    
    email = cand.get("email", "N/A")
    phone = cand.get("phone", "N/A")
    if email != "none" or phone != "none":
        st.markdown(f"<div style='font-size:0.9rem; color:#64748b; margin-top:-5px;'>📧 {email} &nbsp;|&nbsp; 📱 {phone}</div>", unsafe_allow_html=True)
        
    role = cand.get('applied_role', 'Unspecified Role')"""
code = code.replace(profile_target, new_profile)

# Update ATS DB Columns to show Pipeline Stage
old_ats_cols = """        cols = st.columns([2, 2, 1, 1, 1, 1])
        with cols[0]: st.markdown("**Candidate Name**")
        with cols[1]: st.markdown("**Applied Role**")
        with cols[2]: st.markdown("**Global Score**")
        with cols[3]: st.markdown("**Recommendation**")
        with cols[4]: st.markdown("**Evaluated On**")
        with cols[5]: st.markdown("**Action**")"""

new_ats_cols = """        cols = st.columns([2, 2, 1, 1, 1, 1.5, 1])
        with cols[0]: st.markdown("**Candidate Name**")
        with cols[1]: st.markdown("**Applied Role**")
        with cols[2]: st.markdown("**Score**")
        with cols[3]: st.markdown("**Decision**")
        with cols[4]: st.markdown("**Date**")
        with cols[5]: st.markdown("**Pipeline Stage**")
        with cols[6]: st.markdown("**Action**")"""

code = code.replace(old_ats_cols, new_ats_cols)

# Update the loop renderer
old_ats_loop = """        for idx, cand in enumerate(history_data):
            cols = st.columns([2, 2, 1, 1, 1, 1])
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

new_ats_loop = """        for idx, cand in enumerate(history_data):
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
                    show_candidate_profile(cand)"""
                    
code = code.replace(old_ats_loop, new_ats_loop)

with open("app.py", "w") as f:
    f.write(code)

