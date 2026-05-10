import re

with open("style.css", "r") as f:
    css = f.read()

# I will replace the custom tab styling block (lines 844 to end of file, or specifically the tab parts).
# Let's find the start of the tab styles and replace them.

old_tab_style = re.compile(r"/\* ---------- Custom Tabs Styling ---------- \*/.*?(?=/\* Custom Input Card Styling \*/)", re.DOTALL)

new_tab_style = """/* ---------- Ultra Premium Tabs Styling ---------- */
div[data-testid="stTabs"] {
    margin-top: 2rem;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    gap: 10px !important;
    background-color: #f1f5f9 !important;
    padding: 8px !important;
    border-radius: 100px !important;
    border: 1px solid #e2e8f0 !important;
    margin-bottom: 20px !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02) !important;
}

div[data-testid="stTabs"] button[role="tab"], 
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    background-color: transparent !important;
    border: none !important;
    border-radius: 100px !important;
    padding: 1rem 1.5rem !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #64748b !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin: 0 !important;
    height: auto !important;
}

div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #334155 !important;
    background-color: rgba(255,255,255,0.5) !important;
    transform: translateY(-1px) !important;
}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4), 0 4px 6px -2px rgba(99, 102, 241, 0.2) !important;
    border: none !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    transform: translateY(-2px) !important;
}

"""

css = old_tab_style.sub(new_tab_style, css)

# There is also an "Aggressive forced expansion" block at the end of the file.
# We need to remove it or replace it because it will conflict with our new pill design.
aggressive_tab_style = re.compile(r"/\* Aggressive forced expansion for Streamlit Tabs \*/.*", re.DOTALL)

css = aggressive_tab_style.sub("", css)

with open("style.css", "w") as f:
    f.write(css)

