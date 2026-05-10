import streamlit as st
import pandas as pd
import altair as alt

def render_radar_chart(scores_dict, candidate_name):
    """Renders a strength profile for a candidate."""
    data = []
    labels = {
        "skills_match": "Skills",
        "experience_relevance": "Exp",
        "education_certs": "Edu",
        "project_portfolio": "Proj",
        "communication_quality": "Comm"
    }
    for key, label in labels.items():
        score = scores_dict.get(key, {}).get("score", 0)
        data.append({"Dim": label, "Score": score})
    
    df = pd.DataFrame(data)
    chart = alt.Chart(df).mark_area(
        fillOpacity=0.2,
        fill="#6366f1",
        stroke="#6366f1",
        strokeWidth=2
    ).encode(
        x=alt.X('Dim:N', sort=None, title=None),
        y=alt.Y('Score:Q', scale=alt.Scale(domain=[0, 10]), title=None)
    ).properties(height=150)
    
    st.altair_chart(chart, use_container_width=True)

def render_comparison_chart(cand1, cand2):
    """Compare two candidates side-by-side."""
    data = []
    labels = {
        "skills_match": "Skills",
        "experience_relevance": "Exp",
        "education_certs": "Edu",
        "project_portfolio": "Proj",
        "communication_quality": "Comm"
    }
    
    for key, label in labels.items():
        data.append({
            "Dim": label, 
            "Score": cand1.get("scores", {}).get(key, {}).get("score", 0),
            "Candidate": cand1["name"]
        })
        data.append({
            "Dim": label, 
            "Score": cand2.get("scores", {}).get(key, {}).get("score", 0),
            "Candidate": cand2["name"]
        })
    
    df = pd.DataFrame(data)
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('Dim:N', sort=None),
        y=alt.Y('Score:Q', scale=alt.Scale(domain=[0, 10])),
        color='Candidate:N',
        strokeDash='Candidate:N'
    ).properties(height=300)
    
    st.altair_chart(chart, use_container_width=True)

def render_score_distribution(results):
    """Global scores breakdown."""
    if not results: return
    scores = [c["weighted_total"] for c in results]
    df = pd.DataFrame({"Score": scores})
    chart = alt.Chart(df).mark_bar(color="#6366f1", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Score:Q", bin=alt.Bin(maxbins=10), title="Score Range"),
        y=alt.Y('count()', title="Candidates")
    ).properties(height=200)
    st.altair_chart(chart, use_container_width=True)
