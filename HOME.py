import streamlit as st
from streamlit_shortcuts import clear_shortcuts
clear_shortcuts()
st.set_page_config(page_title="分析工具集", layout="wide")
st.title("🧰 分析工具菜单")
st.markdown("请从左侧侧边栏选择需要使用的工具。")
st.write(f"Streamlit 版本: {st.__version__}")
