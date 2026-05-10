import re

with open("style.css", "r") as f:
    css = f.read()

# We need to add `flex: 1 !important;` and `display: flex; justify-content: center;` to the tab buttons
# And ensure the tab-list has `display: flex !important; width: 100% !important;`

old_tab_container = """div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    gap: 10px !important;
    background-color: #f1f5f9 !important;
    padding: 8px !important;
    border-radius: 100px !important;
    border: 1px solid #e2e8f0 !important;
    margin-bottom: 20px !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02) !important;
}"""

new_tab_container = """div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    display: flex !important;
    width: 100% !important;
    gap: 10px !important;
    background-color: #f1f5f9 !important;
    padding: 8px !important;
    border-radius: 100px !important;
    border: 1px solid #e2e8f0 !important;
    margin-bottom: 20px !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02) !important;
}"""

css = css.replace(old_tab_container, new_tab_container)

old_tab_btn = """div[data-testid="stTabs"] button[role="tab"], 
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
}"""

new_tab_btn = """div[data-testid="stTabs"] button[role="tab"], 
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    flex: 1 !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
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
    white-space: nowrap !important;
}"""

css = css.replace(old_tab_btn, new_tab_btn)

with open("style.css", "w") as f:
    f.write(css)

