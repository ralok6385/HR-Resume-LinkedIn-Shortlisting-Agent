import re

with open("app.py", "r") as f:
    content = f.read()

# I will replace the tab5 header and data loading logic to include a search bar
old_logic = """    history_data = load_db()
    if not history_data:
        st.markdown('<p style="color:#64748b;">No candidates have been processed yet. Run your first analysis to populate the database.</p>', unsafe_allow_html=True)
    else:
        # Sort history by evaluation date (newest first)
        history_data.sort(key=lambda x: x.get("evaluated_on", ""), reverse=True)
        
        st.markdown(f'<p style="margin-bottom: 20px; color:#64748b;">Showing <strong>{len(history_data)}</strong> historical candidate evaluations.</p>', unsafe_allow_html=True)"""


new_logic = """    history_data = load_db()
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
            st.markdown(f'<p style="margin-bottom: 20px; color:#64748b;">Showing all <strong>{len(history_data)}</strong> historical candidate evaluations.</p>', unsafe_allow_html=True)"""

content = content.replace(old_logic, new_logic)

with open("app.py", "w") as f:
    f.write(content)
