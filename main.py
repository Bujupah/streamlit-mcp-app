import streamlit as st
from st_pages import add_page_title, get_nav_from_toml

st.set_page_config(
    layout="wide",
    page_title="Assistant",
    page_icon="✨",
    initial_sidebar_state="expanded",
)

nav = get_nav_from_toml(".streamlit/pages.toml")

# st.logo("✨")

pg = st.navigation(nav, expanded=True, position="top")

add_page_title(pg)

pg.run()
