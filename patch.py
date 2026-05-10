import re

with open("app.py", "r") as f:
    content = f.read()

dialog_func = """
@st.dialog("Candidate Profile Analysis")
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
        
    st.markdown(f"<div style='margin-top:20px; font-size:0.8rem; color:gray;'>Evaluated on: {cand.get('evaluated_on', 'Unknown')}</div>", unsafe_allow_html=True)

with tab5:
"""

# Replace the "with tab5:" line to insert the dialog function right before it
content = content.replace("with tab5:", dialog_func)

# Replace the button logic to call the dialog
old_button_logic = """if st.button("View Profile", key=f"hist_btn_{idx}_{cand['name']}", help="This would open the full historical profile in a production app"):
                    st.toast(f"Loading {cand['name']}'s historical file...", icon="📂")"""

new_button_logic = """if st.button("View Profile", key=f"hist_btn_{idx}_{cand['name']}"):
                    show_candidate_profile(cand)"""

content = content.replace(old_button_logic, new_button_logic)

with open("app.py", "w") as f:
    f.write(content)

