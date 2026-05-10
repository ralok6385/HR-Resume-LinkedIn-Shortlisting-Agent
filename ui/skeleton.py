import streamlit as st

def show_skeleton_loader():
    """Shimmering skeleton for processing state."""
    st.markdown('''
        <div style="margin: 20px 0;">
            <div class="skeleton-box" style="height: 40px; width: 60%; margin-bottom: 10px;"></div>
            <div class="skeleton-box" style="height: 120px; width: 100%; margin-bottom: 10px;"></div>
            <div class="skeleton-box" style="height: 20px; width: 90%;"></div>
        </div>
    ''', unsafe_allow_html=True)
