import streamlit as st
import pandas as pd

def load_css():
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def stat_card(label, value, trend=None, trend_up=True, icon="📊"):
    trend_html = ""
    if trend:
        cls = "stat-trend-up" if trend_up else "stat-trend-down"
        arrow = "▲" if trend_up else "▼"
        trend_html = f"<div><span class='{cls}'>{arrow} {trend}</span></div>"
    return f"""
    <div class='stat-card'>
        <div class='stat-label'>{icon} {label}</div>
        <div class='stat-value'>{value}</div>
        {trend_html}
    </div>
    """

def badge(text, type_="primary"):
    colors = {
        "high": "#34C48B18", "medium": "#F5A62318", "low": "#F0656518",
        "primary": "#EEF3FF"
    }
    text_colors = {
        "high": "#34C48B", "medium": "#F5A623", "low": "#F06565",
        "primary": "#4F7FFA"
    }
    bg = colors.get(type_.lower(), "#EEF3FF")
    tc = text_colors.get(type_.lower(), "#4F7FFA")
    return f"<span class='badge' style='background:{bg}; color:{tc};'>{text}</span>"