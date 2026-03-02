"""
Market Analysis Pro v3.0
========================
Professional market analysis platform with:
- Risk Exposure Engine (crash probability, 6-module scoring)
- Multi-Horizon Stock Scoring with explanations
- Congress Insider Trades + Polymarket Smart Money
- Monetary Plumbing & Macro Analysis

Run: streamlit run webapp/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Paths setup
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'webapp'))

# Import data providers
from webapp.data.providers import (
    get_congress_trades,
    get_stock_data,
    get_multi_horizon_scores,
    get_monetary_data,
    get_congress_trades_for_ticker,
    get_congress_stats,
    get_top_traded_tickers,
    filter_congress_trades,
    get_market_indices,
    get_vix,
    get_all_scores_batch,
    get_risk_exposure_score,
    get_score_explanation,
    calculate_konkorde,
    get_all_ticker_changes,
    get_global_futures,
    get_earnings_calendar,
    get_market_news,
)

from webapp.config import TICKER_UNIVERSE, HIGH_PROFILE_POLITICIANS

# Page config
st.set_page_config(
    page_title="Market Analysis Pro",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS - TradingView-inspired dark terminal theme
st.markdown("""
<style>
    /* ===== TRADINGVIEW COLOR PALETTE ===== */
    :root {
        --bg-primary: #0d1117;
        --bg-card: #161b22;
        --bg-card-hover: #1c2333;
        --border: #21262d;
        --border-light: #30363d;
        --text-primary: #e6edf3;
        --text-secondary: #8b949e;
        --text-muted: #6e7681;
        --green: #3fb950;
        --green-dim: rgba(63, 185, 80, 0.15);
        --red: #f85149;
        --red-dim: rgba(248, 81, 73, 0.15);
        --blue: #58a6ff;
        --blue-dim: rgba(88, 166, 255, 0.15);
        --yellow: #d29922;
        --yellow-dim: rgba(210, 153, 34, 0.15);
        --purple: #bc8cff;
        --purple-dim: rgba(188, 140, 255, 0.15);
        --orange: #f0883e;
    }

    .main-header {
        font-size: 1.4rem;
        font-weight: bold;
        color: var(--text-primary);
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 0.75rem;
        color: var(--text-secondary);
        margin-top: 0;
    }

    /* Section headers — compact */
    .section-header {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 10px 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border);
    }
    .section-header h3 {
        margin: 0;
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--text-primary);
        letter-spacing: 0.3px;
    }
    .section-header .section-icon {
        font-size: 0.82rem;
    }
    .section-header .section-badge {
        background: var(--blue-dim);
        color: var(--blue);
        font-size: 0.55rem;
        padding: 1px 6px;
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    /* ===== TICKER STRIP ===== */
    .ticker-strip {
        display: flex;
        gap: 0;
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 6px;
        overflow-x: auto;
        scrollbar-width: none;
        margin-bottom: 8px;
    }
    .ticker-strip::-webkit-scrollbar { display: none; }
    .ticker-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-right: 1px solid var(--border);
        white-space: nowrap;
        min-width: 140px;
        flex: 0 0 auto;
    }
    .ticker-item:last-child { border-right: none; }
    .ticker-item .t-name {
        font-size: 0.6rem;
        color: var(--text-muted);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .ticker-item .t-price {
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .ticker-item .t-change {
        font-size: 0.65rem;
        font-weight: 600;
    }
    .ticker-item .t-spark {
        width: 40px;
        height: 16px;
    }
    .ticker-item .t-spark svg {
        width: 100%;
        height: 100%;
    }

    /* ===== RISK GAUGE ===== */
    .risk-gauge {
        text-align: center;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid;
    }
    .risk-gauge-score {
        font-size: 2rem;
        font-weight: bold;
        line-height: 1;
    }
    .risk-gauge-label {
        font-size: 0.75rem;
        margin-top: 3px;
        font-weight: 600;
    }
    .prob-card {
        background: var(--bg-card);
        padding: 6px;
        border-radius: 6px;
        text-align: center;
        border: 1px solid var(--border);
        transition: border-color 0.2s;
    }
    .prob-card:hover { border-color: var(--border-light); }
    .prob-value {
        font-size: 1rem;
        font-weight: bold;
    }
    .prob-label {
        font-size: 0.58rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }

    /* Module breakdown bars */
    .module-bar {
        background: var(--bg-card);
        border-radius: 6px;
        padding: 6px 10px;
        margin-bottom: 4px;
        border-left: 3px solid;
        transition: background 0.2s;
    }
    .module-bar:hover { background: var(--bg-card-hover); }
    .module-bar-inner {
        height: 4px;
        border-radius: 2px;
        background: var(--border);
        overflow: hidden;
        margin-top: 4px;
    }
    .module-bar-fill {
        height: 100%;
        border-radius: 2px;
        transition: width 0.5s ease;
    }

    /* Alert items — compact */
    .alert-item {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-left: 2px solid var(--red);
        border-radius: 4px;
        padding: 4px 8px;
        margin-bottom: 3px;
        font-size: 0.68rem;
        color: var(--text-secondary);
        transition: background 0.2s;
    }
    .alert-item:hover { background: var(--bg-card-hover); }
    .alert-item.warning { border-left-color: var(--yellow); }
    .alert-item.info { border-left-color: var(--blue); }

    /* Factor pills */
    .factor-pill-bull {
        background: var(--green-dim);
        border: 1px solid var(--green);
        padding: 2px 7px;
        border-radius: 12px;
        margin: 1px;
        display: inline-block;
        font-size: 0.65rem;
    }
    .factor-pill-bear {
        background: var(--red-dim);
        border: 1px solid var(--red);
        padding: 2px 7px;
        border-radius: 12px;
        margin: 1px;
        display: inline-block;
        font-size: 0.65rem;
    }

    /* ===== MARKET CARDS ===== */
    .market-card {
        background: var(--bg-card);
        padding: 10px;
        border-radius: 6px;
        border: 1px solid var(--border);
        transition: all 0.2s ease;
    }
    .market-card:hover {
        border-color: var(--border-light);
        background: var(--bg-card-hover);
    }
    .signal-badge {
        padding: 2px 7px;
        border-radius: 8px;
        font-size: 0.65rem;
        font-weight: bold;
        display: inline-block;
    }

    /* ===== SECTOR HEATMAP ===== */
    .heatmap-section {
        margin: 8px 0 16px 0;
    }
    .heatmap-sector-label {
        font-size: 0.6rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: var(--text-muted);
        font-weight: 600;
        margin: 6px 0 4px 0;
    }
    .heatmap-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(75px, 1fr));
        gap: 2px;
    }
    .heatmap-cell {
        padding: 5px 4px;
        border-radius: 3px;
        text-align: center;
        cursor: pointer;
        transition: all 0.15s ease;
        border: 1px solid transparent;
    }
    .heatmap-cell:hover {
        border-color: rgba(255,255,255,0.3);
        transform: scale(1.05);
        z-index: 2;
    }
    .heatmap-cell .hm-ticker {
        font-size: 0.62rem;
        font-weight: 700;
        color: rgba(255,255,255,0.95);
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }
    .heatmap-cell .hm-change {
        font-size: 0.55rem;
        font-weight: 600;
        color: rgba(255,255,255,0.85);
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }

    /* ===== STYLED TABLES ===== */
    .styled-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        border-radius: 8px;
        overflow: hidden;
        background: var(--bg-card);
        border: 1px solid var(--border);
        font-size: 0.72rem;
    }
    .styled-table thead tr {
        background: rgba(88, 166, 255, 0.06);
    }
    .styled-table th {
        padding: 7px 10px;
        text-align: left;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        font-size: 0.58rem;
        letter-spacing: 0.5px;
        border-bottom: 1px solid var(--border);
    }
    .styled-table td {
        padding: 6px 10px;
        color: var(--text-primary);
        border-bottom: 1px solid rgba(48, 54, 61, 0.5);
    }
    .styled-table tbody tr {
        transition: all 0.2s ease;
    }
    .styled-table tbody tr:hover {
        background: rgba(88, 166, 255, 0.06);
    }
    .styled-table tbody tr:nth-child(even) {
        background: rgba(255, 255, 255, 0.01);
    }

    /* Score cell with inline bar */
    .score-cell {
        position: relative;
        font-weight: 700;
        font-size: 0.75rem;
    }
    .score-bar-bg {
        width: 100%;
        height: 4px;
        background: var(--border);
        border-radius: 2px;
        margin-top: 4px;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 2px;
        transition: width 0.4s ease;
    }

    /* Signal pills */
    .signal-pill {
        padding: 2px 8px;
        border-radius: 16px;
        font-size: 0.6rem;
        font-weight: 600;
        display: inline-block;
        letter-spacing: 0.3px;
    }
    .signal-pill-strong-buy { background: var(--green-dim); color: var(--green); border: 1px solid rgba(63, 185, 80, 0.3); }
    .signal-pill-buy { background: var(--blue-dim); color: var(--blue); border: 1px solid rgba(88, 166, 255, 0.3); }
    .signal-pill-accumulate { background: var(--purple-dim); color: var(--purple); border: 1px solid rgba(188, 140, 255, 0.3); }
    .signal-pill-hold { background: var(--yellow-dim); color: var(--yellow); border: 1px solid rgba(210, 153, 34, 0.3); }
    .signal-pill-reduce { background: rgba(240, 136, 62, 0.15); color: var(--orange); border: 1px solid rgba(240, 136, 62, 0.3); }
    .signal-pill-sell { background: var(--red-dim); color: var(--red); border: 1px solid rgba(248, 81, 73, 0.3); }

    /* Action column */
    .action-chip {
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 600;
        display: inline-block;
    }
    .action-strong-buy { background: var(--green-dim); color: var(--green); }
    .action-buy { background: var(--blue-dim); color: var(--blue); }
    .action-accumulate { background: var(--purple-dim); color: var(--purple); }
    .action-hold { background: var(--yellow-dim); color: var(--yellow); }
    .action-reduce { background: rgba(240, 136, 62, 0.15); color: var(--orange); }
    .action-sell { background: var(--red-dim); color: var(--red); }

    /* ===== FUNDAMENTAL CARDS ===== */
    .fund-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px;
    }
    .fund-card-title {
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: var(--text-muted);
        font-weight: 600;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border);
    }
    .fund-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;
        border-bottom: 1px solid rgba(48, 54, 61, 0.4);
    }
    .fund-row:last-child { border-bottom: none; }
    .fund-label { color: var(--text-secondary); font-size: 0.7rem; }
    .fund-value { font-weight: 600; font-size: 0.75rem; }

    /* Valuation model cards */
    .val-model-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .val-model-card:hover { border-color: var(--border-light); }
    .val-model-name {
        font-size: 0.6rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: var(--text-muted);
        margin-bottom: 4px;
    }
    .val-model-price {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 3px;
    }
    .val-model-upside {
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 10px;
        display: inline-block;
    }

    /* ===== MOVER CARDS ===== */
    .mover-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 6px 10px;
        margin-bottom: 3px;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .mover-card:hover {
        border-color: var(--blue);
        background: var(--bg-card-hover);
    }
    .rank-badge {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: var(--border);
        color: var(--text-muted);
        font-size: 0.55rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .mover-info {
        flex: 0 0 auto;
        min-width: 55px;
    }
    .mover-ticker {
        font-weight: 700;
        font-size: 0.78rem;
        color: var(--text-primary);
    }
    .mover-name {
        font-size: 0.62rem;
        color: var(--text-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 110px;
    }
    .mover-spark {
        flex: 1 1 auto;
        min-width: 60px;
        height: 28px;
    }
    .mover-spark svg, .idx-spark svg {
        width: 100%;
        height: 100%;
    }
    .mover-price-col {
        text-align: right;
        flex: 0 0 auto;
        min-width: 70px;
    }
    .mover-price {
        font-weight: 600;
        font-size: 0.75rem;
        color: var(--text-primary);
    }
    .mover-change {
        font-size: 0.65rem;
        font-weight: 600;
    }
    .mover-section-title {
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: var(--text-muted);
        font-weight: 600;
        margin-bottom: 6px;
        padding-bottom: 4px;
        border-bottom: 1px solid var(--border);
    }

    /* ===== MINI GAUGES & SCORE RINGS ===== */
    .gauge-row {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
    }
    .mini-gauge {
        flex: 1;
        min-width: 90px;
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 8px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .mini-gauge:hover { border-color: var(--border-light); }
    .mini-gauge svg { display: block; margin: 0 auto 4px auto; }
    .mini-gauge .gauge-label {
        font-size: 0.58rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.4px;
        font-weight: 600;
    }
    .mini-gauge .gauge-value {
        font-size: 0.9rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-top: 1px;
    }

    .score-ring-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 8px;
        text-align: center;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .score-ring-card:hover {
        border-color: var(--blue);
        background: var(--bg-card-hover);
    }

    /* ===== CONGRESS TABLE ===== */
    .congress-summary {
        display: flex;
        gap: 8px;
        margin-bottom: 8px;
    }
    .congress-stat {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 6px 10px;
        text-align: center;
        flex: 1;
    }
    .congress-stat .stat-value {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .congress-stat .stat-label {
        font-size: 0.55rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }

    /* ===== FLUSH TOP — absolute zero gap above nav ===== */
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    .stApp > header,
    iframe[title="streamlit_status_widget"] {
        display: none !important;
        height: 0 !important;
        max-height: 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    .stApp { margin-top: 0 !important; padding-top: 0 !important; }
    .st-emotion-cache-zy6yx3 { padding: 0rem 1rem 10rem !important; }
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > div,
    .appview-container,
    .main,
    section.main {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    /* Kill any top spacing from block container */
    .main .block-container:first-child,
    [data-testid="stAppViewBlockContainer"] {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    /* Kill first element top margin inside block */
    [data-testid="stVerticalBlock"]:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    [data-testid="stVerticalBlock"] > div:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* ===== SCREEN WIDTH OPTIMIZATION ===== */
    .main .block-container,
    section.main .block-container,
    [data-testid="stAppViewBlockContainer"] {
        max-width: 95vw !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    /* Ultrawide (2560px+) */
    @media (min-width: 2560px) {
        .main .block-container,
        section.main .block-container,
        [data-testid="stAppViewBlockContainer"] {
            max-width: 96vw !important;
            padding-left: 2.5rem !important;
            padding-right: 2.5rem !important;
        }
        .styled-table { font-size: 0.92rem; }
        .styled-table th { font-size: 0.78rem; padding: 14px 20px; }
        .styled-table td { padding: 12px 20px; font-size: 0.88rem; }
        .fund-card { padding: 24px; }
        .prob-card { padding: 16px; }
        .mover-card { padding: 14px 22px; gap: 18px; min-height: 65px; }
        .mover-ticker { font-size: 1.05rem; }
        .mover-name { max-width: 200px; font-size: 0.75rem; }
        .mover-spark { min-width: 180px; height: 48px; }
        .mover-price { font-size: 1rem; }
        .mover-change { font-size: 0.85rem; }
        .mover-price-col { min-width: 90px; }
        .mover-section-title { font-size: 0.85rem; letter-spacing: 1.2px; margin-bottom: 10px; }
        .idx-spark { height: 56px !important; max-width: 60% !important; }
        .market-card { padding: 20px !important; }
        .main-header { font-size: 2.6rem; }
        .sub-header { font-size: 1.05rem; }
        .risk-gauge-score { font-size: 4rem; }
        .risk-gauge-label { font-size: 1.3rem; }
        .module-bar { padding: 14px 18px; }
        .ticker-item { padding: 12px 22px; }
        .ticker-item .t-price { font-size: 1rem; }
        .heatmap-grid { grid-template-columns: repeat(auto-fill, minmax(95px, 1fr)); gap: 4px; }
        .heatmap-cell { padding: 10px 8px; }
        .heatmap-cell .hm-ticker { font-size: 0.8rem; }
        .heatmap-cell .hm-change { font-size: 0.72rem; }
    }

    /* Super ultrawide (3200px+) */
    @media (min-width: 3200px) {
        .mover-card { padding: 16px 26px; gap: 22px; min-height: 75px; }
        .mover-ticker { font-size: 1.15rem; }
        .mover-name { max-width: 260px; font-size: 0.82rem; }
        .mover-spark { min-width: 250px; height: 56px; }
        .mover-price { font-size: 1.1rem; }
        .mover-change { font-size: 0.92rem; }
        .mover-price-col { min-width: 105px; }
        .mover-section-title { font-size: 0.92rem; }
        .styled-table { font-size: 0.95rem; }
        .styled-table th { font-size: 0.82rem; padding: 16px 22px; }
        .styled-table td { padding: 14px 22px; }
        .fund-card { padding: 28px; }
        .idx-spark { height: 65px !important; }
        .market-card { padding: 24px !important; }
        .ticker-item { padding: 14px 26px; }
        .ticker-item .t-price { font-size: 1.1rem; }
        .ticker-item .t-spark { width: 70px; height: 28px; }
        .heatmap-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 5px; }
        .heatmap-cell { padding: 12px 10px; }
        .heatmap-cell .hm-ticker { font-size: 0.88rem; }
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        min-width: 260px;
        max-width: 300px;
    }

    /* Plotly chart container background */
    [data-testid="stPlotlyChart"] {
        background-color: #0d1117 !important;
    }

    /* ===== GLOBAL COMPACT OVERRIDES ===== */
    /* Streamlit element spacing */
    [data-testid="stVerticalBlock"] > div { margin-bottom: 0 !important; }
    .stMarkdown { margin-bottom: 0 !important; }

    /* Streamlit buttons — global micro */
    .stButton > button {
        padding: 1px 6px !important;
        font-size: 0.55rem !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.1 !important;
        border-radius: 3px !important;
    }

    /* Tabs — compact */
    .stTabs [data-baseweb="tab-list"] { gap: 4px !important; }
    .stTabs [data-baseweb="tab"] {
        padding: 4px 12px !important;
        font-size: 0.62rem !important;
    }

    /* Expanders — compact */
    .streamlit-expanderHeader {
        font-size: 0.68rem !important;
        padding: 4px 8px !important;
    }

    /* Checkbox labels */
    .stCheckbox label span {
        font-size: 0.68rem !important;
    }

    /* Spinner text */
    .stSpinner > div { font-size: 0.62rem !important; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HELPERS
# =============================================================================
def _esc(text):
    """Escape $ signs so Streamlit markdown doesn't treat them as LaTeX."""
    return str(text).replace('$', '&#36;')


# =============================================================================
# SESSION STATE
# =============================================================================
def init_session_state():
    if 'selected_ticker' not in st.session_state:
        st.session_state.selected_ticker = 'NVDA'
    if 'navigate_to' not in st.session_state:
        st.session_state.navigate_to = None
    if 'current_page_index' not in st.session_state:
        st.session_state.current_page_index = 0
    if 'lang' not in st.session_state:
        st.session_state.lang = 'es'


# =============================================================================
# TRANSLATIONS
# =============================================================================
_T = {
    'es': {
        'nav': 'Navegacion',
        'dashboard': '🏠 Dashboard',
        'stock_analysis': '📊 Stock Analysis',
        'signals': '🔍 Signals',
        'filters': 'Filtros',
        'horizon': 'Horizonte',
        'min_score': 'Score minimo',
        'clean_cache': 'Limpiar Cache',
        'cache_cleaned': 'Cache limpiado',
        'universe': 'Universo',
        'politicians': 'Politicos',
        'hz_short': 'Corto Plazo (1-4 sem)',
        'hz_mid': 'Medio Plazo (1-6 mes)',
        'hz_long': 'Largo Plazo (6+ mes)',
        'market_overview': 'Market Overview',
        'market_subtitle': 'Panel de inteligencia de mercado en tiempo real',
        'global_futures': 'Global Futures & Indices',
        'risk_center': 'Risk Command Center',
        'module_breakdown': 'Module Breakdown',
        'alerts_patterns': 'Alerts & Patterns',
        'sector_heatmap': 'Sector Heatmap',
        'market_movers': 'Market Movers',
        'gainers': 'Top Gainers',
        'losers': 'Top Losers',
        'most_active': 'Most Active',
        'unusual_vol': 'Unusual Volume',
        'liquidity': 'Liquidity & Top Picks',
        'congress': 'Congress Insider Trades',
        'load_congress': 'Cargar Congress Trades',
        'earnings_cal': 'Earnings Calendar — Proximos 30 Dias',
        'top_news': 'Top Market News',
        'all_stocks': 'All Stocks Table',
        'search_ticker': 'Buscar ticker',
        'signals_page': 'Signals & Intelligence',
        'signals_subtitle': 'Congress insider trades + Polymarket smart money',
        'val_models': 'Modelos de Valoracion',
        'val_interp': 'Interpretacion de modelos de valoracion',
        'val_verdict': 'Veredicto valoracion',
        'val_insufficient': 'Datos insuficientes para modelos de valoracion (se necesita EPS, Book Value y FCF)',
        'intelligent_analysis': 'Analisis Inteligente',
        'no_signals': 'Sin datos FRED (API key no configurada)',
        'economic_indicators': 'Indicadores Economicos',
    },
    'en': {
        'nav': 'Navigation',
        'dashboard': '🏠 Dashboard',
        'stock_analysis': '📊 Stock Analysis',
        'signals': '🔍 Signals',
        'filters': 'Filters',
        'horizon': 'Horizon',
        'min_score': 'Min score',
        'clean_cache': 'Clear Cache',
        'cache_cleaned': 'Cache cleared',
        'universe': 'Universe',
        'politicians': 'Politicians',
        'hz_short': 'Short Term (1-4 wk)',
        'hz_mid': 'Medium Term (1-6 mo)',
        'hz_long': 'Long Term (6+ mo)',
        'market_overview': 'Market Overview',
        'market_subtitle': 'Real-time market intelligence dashboard',
        'global_futures': 'Global Futures & Indices',
        'risk_center': 'Risk Command Center',
        'module_breakdown': 'Module Breakdown',
        'alerts_patterns': 'Alerts & Patterns',
        'sector_heatmap': 'Sector Heatmap',
        'market_movers': 'Market Movers',
        'gainers': 'Top Gainers',
        'losers': 'Top Losers',
        'most_active': 'Most Active',
        'unusual_vol': 'Unusual Volume',
        'liquidity': 'Liquidity & Top Picks',
        'congress': 'Congress Insider Trades',
        'load_congress': 'Load Congress Trades',
        'earnings_cal': 'Earnings Calendar — Next 30 Days',
        'top_news': 'Top Market News',
        'all_stocks': 'All Stocks Table',
        'search_ticker': 'Search ticker',
        'signals_page': 'Signals & Intelligence',
        'signals_subtitle': 'Congress insider trades + Polymarket smart money',
        'val_models': 'Valuation Models',
        'val_interp': 'Valuation model interpretation',
        'val_verdict': 'Valuation verdict',
        'val_insufficient': 'Insufficient data for valuation models (EPS, Book Value and FCF required)',
        'intelligent_analysis': 'Intelligent Analysis',
        'no_signals': 'No FRED data (API key not set)',
        'economic_indicators': 'Economic Indicators',
    },
}


def t(key: str) -> str:
    """Get translated string for current language."""
    lang = st.session_state.get('lang', 'es')
    return _T.get(lang, _T['es']).get(key, _T['es'].get(key, key))


def navigate_to_stock(ticker: str):
    st.session_state.selected_ticker = ticker
    st.session_state.navigate_to = 'stock_analysis'


# =============================================================================
# HELPER COMPONENTS
# =============================================================================

def render_signal_badge(signal: str) -> str:
    """Return HTML for a signal badge with appropriate color."""
    signal_upper = str(signal).upper()
    if 'STRONG' in signal_upper and 'BUY' in signal_upper:
        return f'<span class="signal-badge" style="background:#3fb950;color:#0d1117;">STRONG BUY</span>'
    elif 'BUY' in signal_upper:
        return f'<span class="signal-badge" style="background:#58a6ff;color:#0d1117;">BUY</span>'
    elif 'ACCUMULATE' in signal_upper:
        return f'<span class="signal-badge" style="background:#bc8cff;color:#0d1117;">ACCUMULATE</span>'
    elif 'HOLD' in signal_upper:
        return f'<span class="signal-badge" style="background:#d29922;color:#0d1117;">HOLD</span>'
    elif 'REDUCE' in signal_upper:
        return f'<span class="signal-badge" style="background:#f0883e;color:#0d1117;">REDUCE</span>'
    elif 'SELL' in signal_upper:
        return f'<span class="signal-badge" style="background:#f85149;color:#0d1117;">SELL</span>'
    return f'<span class="signal-badge" style="background:#30363d;color:#8b949e;">{signal}</span>'


def get_regime_color(score: int) -> str:
    if score >= 80: return '#f85149'
    if score >= 60: return '#f0883e'
    if score >= 40: return '#d29922'
    if score >= 20: return '#3fb950'
    return '#3fb950'


def render_fund_card(title: str, rows: list) -> str:
    """Render a fundamental analysis card with rows of (label, value, color)."""
    rows_html = ""
    for label, value, color in rows:
        rows_html += f'''<div class="fund-row">
            <span class="fund-label">{label}</span>
            <span class="fund-value" style="color:{color};">{value}</span>
        </div>'''
    return f'''<div class="fund-card">
        <div class="fund-card-title">{title}</div>
        {rows_html}
    </div>'''


@st.cache_data(ttl=300, show_spinner=False)
def get_market_overview_data():
    """Get market overview data for dashboard with sparkline history."""
    import yfinance as yf
    tickers_info = {
        'SPY': {'name': 'S&P 500', 'emoji': '🇺🇸'},
        'QQQ': {'name': 'Nasdaq 100', 'emoji': '💻'},
        'DIA': {'name': 'Dow Jones', 'emoji': '🏭'},
        'IWM': {'name': 'Russell 2000', 'emoji': '📊'},
        '^VIX': {'name': 'VIX', 'emoji': '😰'},
        'GLD': {'name': 'Oro', 'emoji': '🥇'},
        'USO': {'name': 'Petroleo', 'emoji': '🛢'},
        'BTC-USD': {'name': 'Bitcoin', 'emoji': '₿'},
        'ETH-USD': {'name': 'Ethereum', 'emoji': 'Ξ'},
    }
    results = {}
    for ticker, info in tickers_info.items():
        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period='1mo')
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = ((current / prev) - 1) * 100
                results[ticker] = {
                    'name': info['name'], 'emoji': info['emoji'],
                    'price': current, 'change': change,
                    'sparkline': hist['Close'].tolist()[-20:],
                }
        except Exception:
            pass
    return results


def _svg_sparkline(prices: list, color: str, width: int = 80, height: int = 32) -> str:
    """Generate an SVG sparkline from a list of prices."""
    if not prices or len(prices) < 2:
        return ''
    mn, mx = min(prices), max(prices)
    rng = mx - mn if mx != mn else 1
    n = len(prices)
    pad = 2
    points = []
    for i, p in enumerate(prices):
        x = pad + (i / (n - 1)) * (width - 2 * pad)
        y = pad + (1 - (p - mn) / rng) * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(points)
    # Fill area under curve
    fill_points = polyline + f" {width - pad:.1f},{height - pad:.1f} {pad:.1f},{height - pad:.1f}"
    # Determine fill color with transparency
    if '#3fb950' in color or '#10B981' in color:
        fill_rgba = 'rgba(63,185,80,0.15)'
    elif '#f85149' in color or '#EF4444' in color:
        fill_rgba = 'rgba(248,81,73,0.15)'
    else:
        fill_rgba = 'rgba(88,166,255,0.15)'

    return f'''<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <polygon points="{fill_points}" fill="{fill_rgba}"/>
        <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>'''


@st.cache_data(ttl=300, show_spinner=False)
def get_market_movers():
    """Fetch top gainers, top losers, and most active from TICKER_UNIVERSE."""
    import yfinance as yf

    tickers = list(TICKER_UNIVERSE)
    results = []

    # Batch download 5d history for all tickers
    try:
        data = yf.download(tickers, period='1mo', group_by='ticker', progress=False, threads=True)
    except Exception:
        return {'gainers': [], 'losers': [], 'active': []}

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                hist = data
            else:
                hist = data[ticker] if ticker in data.columns.get_level_values(0) else None

            if hist is None or hist.empty:
                continue

            closes = hist['Close'].dropna()
            volumes = hist['Volume'].dropna()

            if len(closes) < 2:
                continue

            current = closes.iloc[-1]
            prev = closes.iloc[-2]
            change_pct = ((current / prev) - 1) * 100

            # Get company name from yfinance (cached)
            try:
                info = yf.Ticker(ticker).fast_info
                name = getattr(info, 'short_name', ticker) or ticker
                # Truncate long names
                if len(name) > 20:
                    name = name[:18] + '...'
            except Exception:
                name = ticker

            avg_vol = volumes.mean() if len(volumes) > 1 else 0
            last_vol = volumes.iloc[-1] if len(volumes) > 0 else 0

            results.append({
                'ticker': ticker,
                'name': name,
                'price': float(current),
                'change': float(change_pct),
                'volume': float(last_vol),
                'avg_volume': float(avg_vol),
                'sparkline': closes.tolist()[-20:],  # Last 20 data points
            })
        except Exception:
            continue

    if not results:
        return {'gainers': [], 'losers': [], 'active': []}

    # Sort for each category
    by_change = sorted(results, key=lambda x: x['change'], reverse=True)
    gainers = [r for r in by_change if r['change'] > 0][:5]
    losers = sorted([r for r in results if r['change'] < 0], key=lambda x: x['change'])[:5]
    active = sorted(results, key=lambda x: x['volume'], reverse=True)[:5]
    # Unusual volume: stocks where last volume > 2x average
    unusual = sorted(
        [r for r in results if r['avg_volume'] > 0 and r['volume'] / r['avg_volume'] > 2.0],
        key=lambda x: x['volume'] / x['avg_volume'] if x['avg_volume'] > 0 else 0,
        reverse=True
    )[:5]

    return {'gainers': gainers, 'losers': losers, 'active': active, 'unusual': unusual}


def _render_mover_card(stock: dict, key_prefix: str, idx: int, rank: int = 0) -> str:
    """Render a single stock mover card as HTML with rank badge."""
    change = stock['change']
    color = '#3fb950' if change >= 0 else '#f85149'
    arrow = '▲' if change >= 0 else '▼'
    price = stock['price']

    if price >= 1000:
        price_str = f"{price:,.0f}"
    elif price >= 1:
        price_str = f"{price:,.2f}"
    else:
        price_str = f"{price:.4f}"

    spark_svg = _svg_sparkline(stock['sparkline'], color)
    rank_html = f'<div class="rank-badge">{rank}</div>' if rank else ''

    return f'''<div class="mover-card">
        {rank_html}
        <div class="mover-info">
            <div class="mover-ticker">{stock['ticker']}</div>
            <div class="mover-name">{stock['name']}</div>
        </div>
        <div class="mover-spark">{spark_svg}</div>
        <div class="mover-price-col">
            <div class="mover-price">{price_str}</div>
            <div class="mover-change" style="color:{color};">{arrow} {abs(change):.2f}%</div>
        </div>
    </div>'''


def _render_economic_indicators(indicators: dict) -> str:
    """Render economic indicators grid - employment, inflation, GDP, etc."""
    # Map of indicators with display info
    indicator_map = {
        'unemployment': {'label': 'Unemployment', 'label_es': 'Desempleo', 'unit': '%', 'decimals': 1, 'good': 'low'},
        'cpi_yoy': {'label': 'CPI (YoY)', 'label_es': 'IPC (YoY)', 'unit': '%', 'decimals': 1, 'good': 'low'},
        'pce_yoy': {'label': 'PCE (YoY)', 'label_es': 'PCE (YoY)', 'unit': '%', 'decimals': 1, 'good': 'low'},
        'gdp_growth': {'label': 'GDP Growth', 'label_es': 'PIB', 'unit': '%', 'decimals': 1, 'good': 'high'},
        'fed_funds': {'label': 'Fed Funds', 'label_es': 'Fed Funds', 'unit': '%', 'decimals': 2, 'good': 'neutral'},
        'yield_curve': {'label': '10Y-2Y', 'label_es': '10Y-2Y', 'unit': '%', 'decimals': 2, 'good': 'high'},
        'jobless_claims': {'label': 'Jobless Claims', 'label_es': 'Paro Semanal', 'unit': 'K', 'decimals': 0, 'good': 'low', 'scale': 0.001},
        'nonfarm_payrolls': {'label': 'Nonfarm Payrolls', 'label_es': 'Nóminas', 'unit': 'K', 'decimals': 0, 'good': 'high', 'scale': 0.001},
        'consumer_sentiment': {'label': 'Consumer Sent.', 'label_es': 'Confianza', 'unit': '', 'decimals': 1, 'good': 'high'},
        'oil_wti': {'label': 'Oil (WTI)', 'label_es': 'Petróleo', 'unit': '$', 'decimals': 2, 'good': 'neutral'},
        'dollar_index': {'label': 'Dollar Index', 'label_es': 'Índice Dólar', 'unit': '', 'decimals': 2, 'good': 'neutral'},
    }

    cards_html = ''
    for key, info in indicator_map.items():
        if key not in indicators:
            continue

        data = indicators[key]
        value = data['value']
        change = data.get('change', 0)

        # Apply scale if needed
        scale = info.get('scale', 1)
        value = value * scale
        change = change * scale

        # Format value
        decimals = info['decimals']
        unit = info['unit']
        if unit == '$':
            value_str = f'&#36;{value:.{decimals}f}'
            change_str = f'&#36;{abs(change):.{decimals}f}'
        elif unit == 'K':
            value_str = f'{value:.{decimals}f}K'
            change_str = f'{abs(change):.{decimals}f}K'
        else:
            value_str = f'{value:.{decimals}f}{unit}'
            change_str = f'{abs(change):.{decimals}f}{unit}'

        # Color coding
        change_color = '#3fb950' if change >= 0 else '#f85149'
        arrow = '▲' if change >= 0 else '▼'

        # Use translated label
        lang = st.session_state.get('lang', 'es')
        label = info.get(f'label_{lang}', info['label'])

        cards_html += (
            f'<div style="background:#161b22; padding:10px 12px; border-radius:6px; border:1px solid #21262d;">'
            f'<div style="font-size:0.65rem; color:#6e7681; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>'
            f'<div style="font-size:1.1rem; font-weight:700; color:#e6edf3; margin-bottom:2px;">{value_str}</div>'
            f'<div style="font-size:0.7rem; color:{change_color};">{arrow} {change_str}</div>'
            f'</div>'
        )

    return f'<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin-bottom:20px;">{cards_html}</div>'


def _render_ticker_strip(market_data: dict, futures_data: dict = None) -> str:
    """Render horizontal ticker strip with all instruments including futures."""
    # Original ETF tickers with sparklines
    order = ['SPY', 'QQQ', 'DIA', 'IWM', '^VIX', 'GLD', 'USO', 'BTC-USD', 'ETH-USD']
    items = []
    for ticker in order:
        if ticker not in market_data:
            continue
        d = market_data[ticker]
        chg = d['change']
        chg_color = '#3fb950' if chg >= 0 else '#f85149'
        if ticker == '^VIX':
            chg_color = '#f85149' if chg >= 0 else '#3fb950'
        arrow = '▲' if chg >= 0 else '▼'
        price = d['price']
        if 'BTC' in ticker or 'ETH' in ticker:
            price_fmt = f"&#36;{price:,.0f}"
        elif ticker == '^VIX':
            price_fmt = f"{price:.2f}"
        else:
            price_fmt = f"&#36;{price:,.2f}"
        spark = _svg_sparkline(d.get('sparkline', []), chg_color, width=50, height=22)
        items.append(f'''<div class="ticker-item">
            <span class="t-name">{d['emoji']} {d['name']}</span>
            <span class="t-price">{price_fmt}</span>
            <span class="t-change" style="color:{chg_color};">{arrow}{abs(chg):.2f}%</span>
            <span class="t-spark">{spark}</span>
        </div>''')

    # Add futures/rates/commodities from global futures data
    if futures_data:
        futures_order = [
            ('ES=F', '📈'), ('NQ=F', '💻'), ('YM=F', '🏭'), ('RTY=F', '📊'),
            ('^STOXX50E', '🇪🇺'), ('^GDAXI', '🇩🇪'), ('^N225', '🇯🇵'),
            ('GC=F', '🥇'), ('SI=F', '🥈'), ('CL=F', '🛢'), ('NG=F', '🔥'), ('HG=F', '🔶'),
            ('^TNX', '📉'), ('^TYX', '📉'), ('^FVX', '📉'), ('^IRX', '📉'),
            ('DX-Y.NYB', '💵'), ('EURUSD=X', '💶'), ('GBPUSD=X', '💷'),
            ('SOL-USD', '☀'),
        ]
        # Skip tickers already shown via ETF equivalents
        shown_names = {d.get('name', '').lower() for d in market_data.values()}
        for sym, emoji in futures_order:
            if sym not in futures_data:
                continue
            fd = futures_data[sym]
            # Skip if similar name already in strip
            if any(n in fd['name'].lower() for n in ['s&p', 'nasdaq', 'dow', 'russell', 'vix', 'gold', 'bitcoin', 'ethereum'] if n in shown_names):
                continue
            chg = fd.get('change_pct', fd.get('change', 0))
            chg_color = '#3fb950' if chg >= 0 else '#f85149'
            if fd['type'] == 'rate':
                chg_color = '#f85149' if chg >= 0 else '#3fb950'  # Rising rates = red
            arrow = '▲' if chg >= 0 else '▼'
            price = fd['price']
            if fd['type'] in ('rate',):
                price_fmt = f"{price:.2f}%"
            elif fd['type'] in ('fx',) and price < 10:
                price_fmt = f"{price:.4f}"
            elif price >= 10000:
                price_fmt = f"&#36;{price:,.0f}"
            elif price >= 100:
                price_fmt = f"&#36;{price:,.1f}"
            else:
                price_fmt = f"&#36;{price:,.2f}"
            items.append(f'''<div class="ticker-item">
                <span class="t-name">{emoji} {fd['name']}</span>
                <span class="t-price">{price_fmt}</span>
                <span class="t-change" style="color:{chg_color};">{arrow}{abs(chg):.2f}%</span>
            </div>''')

    return f'<div class="ticker-strip">{"".join(items)}</div>'


def _heatmap_color(change_pct: float) -> str:
    """Return background color for heatmap cell based on daily change %."""
    if change_pct >= 5:
        return '#1a6334'
    elif change_pct >= 3:
        return '#196c2e'
    elif change_pct >= 1.5:
        return '#1a7f37'
    elif change_pct >= 0.5:
        return '#238636'
    elif change_pct >= 0:
        return '#2ea043'
    elif change_pct >= -0.5:
        return '#da3633'
    elif change_pct >= -1.5:
        return '#c93c37'
    elif change_pct >= -3:
        return '#b62324'
    elif change_pct >= -5:
        return '#9e1c1c'
    else:
        return '#8b1a1a'


# Sector groupings for heatmap
SECTOR_MAP = {
    'Big Tech': ['AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'TSLA', 'NFLX'],
    'Semiconductors': ['AVGO', 'AMD', 'INTC', 'QCOM', 'MU', 'ASML', 'TSM', 'AMAT', 'LRCX', 'MRVL'],
    'Software': ['CRM', 'ORCL', 'IBM', 'NOW', 'ADBE', 'PLTR', 'SNOW', 'DDOG', 'ZS', 'CRWD'],
    'Fintech': ['V', 'MA', 'PYPL', 'SQ', 'COIN', 'HOOD'],
    'Banks': ['JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'SCHW', 'BLK'],
    'Healthcare': ['UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'GILD', 'BMY', 'AMGN', 'REGN', 'MRNA', 'VRTX'],
    'Consumer': ['PG', 'KO', 'PEP', 'WMT', 'COST', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW'],
    'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY'],
    'Defense': ['LMT', 'RTX', 'NOC', 'GD', 'BA', 'HII'],
    'Industrials': ['CAT', 'DE', 'UNP', 'UPS', 'FDX', 'HON'],
    'Telecom/Media': ['VZ', 'T', 'TMUS', 'DIS', 'CMCSA', 'CHTR'],
    'Other': ['UBER', 'ABNB', 'SHOP', 'SPOT', 'AMT', 'PLD', 'NEE', 'DUK', 'SO'],
}


def _render_futures_board(futures_data: dict) -> str:
    """Render global futures board grouped by region/type."""
    regions = {
        'US Equity Futures': [t for t, d in futures_data.items() if d['region'] == 'US' and d['type'] == 'equity'],
        'Europe': [t for t, d in futures_data.items() if d['region'] == 'Europe'],
        'Asia': [t for t, d in futures_data.items() if d['region'] == 'Asia'],
        'Commodities': [t for t, d in futures_data.items() if d['type'] == 'commodity'],
        'Bonds': [t for t, d in futures_data.items() if d['type'] == 'bond'],
        'Crypto': [t for t, d in futures_data.items() if d['type'] == 'crypto'],
    }

    html = '<div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px;">'

    for region_name, tickers in regions.items():
        if not tickers:
            continue

        # Region header color
        region_colors = {
            'US Equity Futures': '#58a6ff', 'Europe': '#bc8cff', 'Asia': '#d29922',
            'Commodities': '#f0883e', 'Bonds': '#8b949e', 'Crypto': '#3fb950',
        }
        r_color = region_colors.get(region_name, '#8b949e')

        html += f'''<div style="flex:1; min-width:200px; background:#161b22; border:1px solid #21262d; border-radius:8px; padding:10px; border-top:2px solid {r_color};">
            <div style="font-size:0.7rem; text-transform:uppercase; letter-spacing:0.8px; color:{r_color}; font-weight:600; margin-bottom:8px;">{region_name}</div>'''

        for ticker in tickers:
            d = futures_data[ticker]
            chg = d['change_pct']
            price = d['price']
            name = d['name']
            color = '#3fb950' if chg >= 0 else '#f85149'
            arrow = '&#9650;' if chg >= 0 else '&#9660;'
            bg = f'rgba(63,185,80,0.06)' if chg >= 0 else f'rgba(248,81,73,0.06)'

            # Format price based on type
            if d['type'] == 'crypto' and price > 1000:
                price_fmt = f"&#36;{price:,.0f}"
            elif d['type'] == 'commodity' or price > 100:
                price_fmt = f"{price:,.2f}"
            else:
                price_fmt = f"{price:,.2f}"

            html += f'''<div style="display:flex; justify-content:space-between; align-items:center; padding:5px 6px; margin:2px 0; border-radius:4px; background:{bg};">
                <span style="font-size:0.78rem; color:#e6edf3; font-weight:500;">{name}</span>
                <div style="text-align:right;">
                    <span style="font-size:0.78rem; color:#8b949e; margin-right:6px;">{price_fmt}</span>
                    <span style="font-size:0.78rem; font-weight:700; color:{color};">{arrow} {chg:+.2f}%</span>
                </div>
            </div>'''

        html += '</div>'

    html += '</div>'

    # Summary bar: count green vs red
    greens = sum(1 for d in futures_data.values() if d['change_pct'] >= 0)
    reds = len(futures_data) - greens
    total = len(futures_data)
    green_pct = (greens / total * 100) if total > 0 else 50
    html += f'''<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
        <span style="font-size:0.72rem; color:#3fb950; font-weight:600;">{greens} &#9650;</span>
        <div style="flex:1; height:4px; border-radius:2px; background:#f85149; overflow:hidden;">
            <div style="width:{green_pct:.0f}%; height:100%; background:#3fb950;"></div>
        </div>
        <span style="font-size:0.72rem; color:#f85149; font-weight:600;">{reds} &#9660;</span>
    </div>'''

    return html


def _render_sector_heatmap(ticker_changes: dict) -> str:
    """Render Finviz-style sector heatmap."""
    html_parts = ['<div class="heatmap-section">']
    for sector, tickers in SECTOR_MAP.items():
        cells = []
        for t in tickers:
            if t not in ticker_changes:
                continue
            chg = ticker_changes[t].get('change', 0)
            bg = _heatmap_color(chg)
            sign = '+' if chg >= 0 else ''
            cells.append(
                f'<div class="heatmap-cell" style="background:{bg};" title="{t}: {sign}{chg:.2f}%">'
                f'<div class="hm-ticker">{t}</div>'
                f'<div class="hm-change">{sign}{chg:.1f}%</div>'
                f'</div>'
            )
        if cells:
            html_parts.append(f'<div class="heatmap-sector-label">{sector}</div>')
            html_parts.append(f'<div class="heatmap-grid">{"".join(cells)}</div>')
    html_parts.append('</div>')
    return ''.join(html_parts)


import math

def _svg_mini_gauge(value: float, max_val: float, label: str, color: str, size: int = 80) -> str:
    """SVG circular arc gauge for dashboard indicators."""
    pct = min(max(value / max_val, 0), 1)
    r = (size - 10) / 2
    cx = cy = size / 2
    # Arc from -135 to +135 degrees (270 degree sweep)
    start_angle = -225
    sweep = 270
    end_angle = start_angle + sweep * pct
    # Convert to radians
    sa = math.radians(start_angle)
    ea = math.radians(end_angle)
    bg_ea = math.radians(start_angle + sweep)
    # Arc points
    x1_bg = cx + r * math.cos(sa)
    y1_bg = cy + r * math.sin(sa)
    x2_bg = cx + r * math.cos(bg_ea)
    y2_bg = cy + r * math.sin(bg_ea)
    x1 = cx + r * math.cos(sa)
    y1 = cy + r * math.sin(sa)
    x2 = cx + r * math.cos(ea)
    y2 = cy + r * math.sin(ea)
    large_bg = 1 if sweep > 180 else 0
    large_fg = 1 if (sweep * pct) > 180 else 0

    return f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <path d="M {x1_bg:.1f} {y1_bg:.1f} A {r:.1f} {r:.1f} 0 {large_bg} 1 {x2_bg:.1f} {y2_bg:.1f}"
              fill="none" stroke="#21262d" stroke-width="6" stroke-linecap="round"/>
        <path d="M {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large_fg} 1 {x2:.1f} {y2:.1f}"
              fill="none" stroke="{color}" stroke-width="6" stroke-linecap="round"/>
    </svg>'''


def _svg_score_ring(score: float, size: int = 60) -> str:
    """SVG circular score ring indicator."""
    pct = min(max(score / 100, 0), 1)
    r = (size - 8) / 2
    cx = cy = size / 2
    circumference = 2 * math.pi * r
    offset = circumference * (1 - pct)
    if score >= 70:
        color = '#3fb950'
    elif score >= 50:
        color = '#58a6ff'
    elif score >= 35:
        color = '#d29922'
    else:
        color = '#f85149'

    return f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#21262d" stroke-width="5"/>
        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="5"
                stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{offset:.1f}"
                stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
        <text x="{cx}" y="{cy + 1}" text-anchor="middle" dominant-baseline="middle"
              fill="{color}" font-size="{size * 0.28:.0f}" font-weight="700">{score:.0f}</text>
    </svg>'''


# =============================================================================
# MAIN APP
# =============================================================================
def main():
    init_session_state()

    pages = [
        "🏠 Dashboard",
        "📊 Stock Analysis",
        "🔍 Signals",
    ]

    # Handle programmatic navigation
    if st.session_state.navigate_to == 'stock_analysis':
        st.session_state.current_page_index = 1
        st.session_state.navigate_to = None

    # =========================================================================
    # TOP NAVIGATION BAR (replaces sidebar)
    # =========================================================================
    st.markdown("""
    <style>
        /* Hide default sidebar */
        [data-testid="stSidebar"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        button[kind="header"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    # Ultra-compact nav bar
    st.markdown("""
    <style>
        /* Micro nav buttons */
        div[data-testid="stHorizontalBlock"] button[kind="secondary"],
        div[data-testid="stHorizontalBlock"] button[kind="primary"] {
            padding: 1px 6px !important;
            font-size: 0.55rem !important;
            min-height: 0 !important;
            height: auto !important;
            line-height: 1.1 !important;
            border-radius: 3px !important;
            letter-spacing: 0.2px !important;
            font-weight: 600 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Logo + Nav in one tight row
    nav_cols = st.columns([2.5, 1.5, 1.5, 1.5, 0.6, 0.6, 4.8])
    with nav_cols[0]:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:4px; padding:0; margin:0;">
            <span style="font-size:0.65rem;">🏛</span>
            <span style="font-size:0.6rem; font-weight:800; color:#e6edf3; letter-spacing:0.6px; font-family:'Georgia',serif; line-height:1;">STRATEGOS<span style="color:#d29922;">.</span>MARKETS</span>
        </div>
        """, unsafe_allow_html=True)
    with nav_cols[1]:
        if st.button("Dashboard", use_container_width=True,
                     type="primary" if st.session_state.current_page_index == 0 else "secondary",
                     key="nav_dash"):
            st.session_state.current_page_index = 0
            st.rerun()
    with nav_cols[2]:
        if st.button("Stocks", use_container_width=True,
                     type="primary" if st.session_state.current_page_index == 1 else "secondary",
                     key="nav_stock"):
            st.session_state.current_page_index = 1
            st.rerun()
    with nav_cols[3]:
        if st.button("Signals", use_container_width=True,
                     type="primary" if st.session_state.current_page_index == 2 else "secondary",
                     key="nav_signals"):
            st.session_state.current_page_index = 2
            st.rerun()
    with nav_cols[4]:
        lang = st.session_state.lang
        if st.button("🇪🇸" if lang == 'en' else "🇬🇧", use_container_width=True, key="nav_lang"):
            st.session_state.lang = 'en' if lang == 'es' else 'es'
            st.rerun()
    with nav_cols[5]:
        if st.button("🗑", use_container_width=True, key="nav_cache"):
            st.cache_data.clear()
            st.rerun()

    page = pages[st.session_state.current_page_index]

    # Main content
    if "Dashboard" in page:
        show_dashboard()
    elif "Stock Analysis" in page:
        show_stock_analysis()
    elif "Signals" in page:
        show_signals()


def _show_risk_command_center(risk_data, module_scores, crash_probs, score, regime, regime_color, alerts, go):
    """Unified Risk Command Center — gauge, modules, allocation, alerts."""
    regime_level = regime.get('level', 'CAUTELA')
    module_explanations = risk_data.get('module_explanations', {})
    allocation = risk_data.get('allocation', {})

    # Section header
    st.markdown(f"""<div class="section-header">
        <span class="section-icon">🛡</span>
        <h3>Risk Command Center</h3>
        <span class="section-badge" style="background:{regime_color}22; color:{regime_color};">{regime_level} · {score:.0f}/100</span>
    </div>""", unsafe_allow_html=True)

    # --- ROW 1: Gauge + Alerts + 30-Day Probabilities ---
    col_gauge, col_alerts_r, col_probs = st.columns([1, 1, 1])

    with col_gauge:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title={'text': f"RISK EXPOSURE<br><span style='font-size:0.75em;color:{regime_color}'>{regime_level}</span>", 'font': {'size': 12}},
            number={'font': {'size': 28}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': '#30363d'},
                'bar': {'color': regime_color},
                'bgcolor': '#161b22',
                'steps': [
                    {'range': [0, 20], 'color': 'rgba(63,185,80,0.12)'},
                    {'range': [20, 40], 'color': 'rgba(63,185,80,0.08)'},
                    {'range': [40, 60], 'color': 'rgba(210,153,34,0.12)'},
                    {'range': [60, 80], 'color': 'rgba(240,136,62,0.12)'},
                    {'range': [80, 100], 'color': 'rgba(248,81,73,0.15)'},
                ],
                'threshold': {'line': {'color': '#e6edf3', 'width': 3}, 'thickness': 0.8, 'value': score},
            },
        ))
        fig.update_layout(height=200, margin=dict(l=15, r=15, t=55, b=5),
                          paper_bgcolor='rgba(0,0,0,0)', font={'color': '#e6edf3', 'size': 11})
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_alerts_r:
        st.markdown(f'<div style="font-size:0.62rem; text-transform:uppercase; letter-spacing:0.6px; color:#6e7681; font-weight:600; margin-bottom:4px;">{t("alerts_patterns")}</div>', unsafe_allow_html=True)
        action = regime.get('action', '')
        if action:
            st.markdown(f'<div class="alert-item info" style="border-left-color:#58a6ff;">{_esc(action)}</div>', unsafe_allow_html=True)
        if alerts:
            for a in alerts[:6]:
                sev_cls = 'alert-item'
                if 'CRITICO' in a or 'MAXIMA' in a or 'ROJA' in a:
                    sev_cls = 'alert-item'
                elif 'WARNING' in a.upper() or 'CAUTELA' in a:
                    sev_cls = 'alert-item warning'
                else:
                    sev_cls = 'alert-item info'
                st.markdown(f'<div class="{sev_cls}">{_esc(a[:120])}</div>', unsafe_allow_html=True)
        if not alerts and not action:
            st.markdown('<div class="alert-item info" style="border-left-color:#3fb950;">No active alerts</div>', unsafe_allow_html=True)

    with col_probs:
        st.markdown('<div style="font-size:0.62rem; text-transform:uppercase; letter-spacing:0.6px; color:#6e7681; font-weight:600; margin-bottom:4px;">30-Day Probabilities</div>', unsafe_allow_html=True)
        for key, color in [('correction_5pct', '#d29922'), ('correction_10pct', '#f0883e'), ('crash_20pct', '#f85149'), ('rally_5pct', '#3fb950')]:
            prob = crash_probs.get(key, {})
            pval = prob.get('probability', 0)
            plabel = prob.get('label', key)
            reasoning = prob.get('reasoning', '')
            st.markdown(f"""
            <div style="background:#161b22; padding:4px 8px; border-radius:4px; margin-bottom:3px; border-left:2px solid {color};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.68rem; color:#e6edf3;">{_esc(plabel)}</span>
                    <span style="font-size:0.85rem; font-weight:700; color:{color};">{pval:.0f}%</span>
                </div>
                <div style="font-size:0.58rem; color:#6e7681; line-height:1.2;">{_esc(str(reasoning)[:60])}</div>
            </div>""", unsafe_allow_html=True)

    # --- ROW 2: 6 Module horizontal bar ---
    module_weights = {
        'liquidity_stress': 25, 'market_technicals': 20, 'valuation_excess': 15,
        'volatility_regime': 15, 'positioning_crowding': 15, 'macro_deterioration': 10,
    }
    module_names = {
        'liquidity_stress': ('Liquidity', '#58a6ff'),
        'market_technicals': ('Technicals', '#bc8cff'),
        'valuation_excess': ('Valuation', '#d29922'),
        'volatility_regime': ('Volatility', '#f0883e'),
        'positioning_crowding': ('Positioning', '#3fb950'),
        'macro_deterioration': ('Macro', '#f85149'),
    }
    mod_html = '<div style="display:flex; gap:4px; overflow-x:auto; margin:6px 0;">'
    for key, (name, color) in module_names.items():
        ms = module_scores.get(key, 0)
        if isinstance(ms, dict):
            ms = ms.get('score', 0)
        pct = min(max(ms, 0), 100)
        weight = module_weights.get(key, 0)
        wc = round(pct * weight / 100, 1)
        sev_info = module_explanations.get(key, {})
        severity = sev_info.get('severity', 'BAJO')
        sev_colors = {'CRITICO': '#f85149', 'ELEVADO': '#f0883e', 'MODERADO': '#d29922', 'BAJO': '#3fb950'}
        sev_color = sev_colors.get(severity, '#8b949e')
        mod_html += f'''<div style="flex:1; min-width:100px; background:#161b22; padding:4px 8px; border-radius:4px; border-top:2px solid {color};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.6rem; color:#8b949e;">{name}</span>
                <span style="font-size:0.72rem; font-weight:700; color:{color};">{pct:.0f}</span>
            </div>
            <div style="background:#21262d; height:2px; border-radius:1px; margin:3px 0;">
                <div style="height:100%; width:{pct}%; background:{color}; border-radius:1px;"></div>
            </div>
            <div style="font-size:0.5rem; color:#6e7681;">{weight}%→{wc}pts <span style="color:{sev_color}; font-weight:600;">{severity}</span></div>
        </div>'''
    mod_html += '</div>'
    st.markdown(mod_html, unsafe_allow_html=True)

    # --- ROW 3: Allocation (visible) ---
    if allocation:
        # Determine investor profile label based on risk regime
        if score >= 80:
            _profile_label = "Conservador / Capital Preservation"
            _profile_desc = "Prioriza preservar capital. Minima exposicion a riesgo."
            _profile_color = "#f85149"
        elif score >= 60:
            _profile_label = "Defensivo / Risk-Off"
            _profile_desc = "Reduce exposicion significativa. Solo blue chips y dividendo."
            _profile_color = "#f0883e"
        elif score >= 40:
            _profile_label = "Moderado / Balanced"
            _profile_desc = "Diversificacion equilibrada con sesgo defensivo."
            _profile_color = "#d29922"
        elif score >= 20:
            _profile_label = "Crecimiento / Growth"
            _profile_desc = "Condiciones favorables. Mayor peso en renta variable y growth."
            _profile_color = "#3fb950"
        else:
            _profile_label = "Agresivo / Full Risk-On"
            _profile_desc = "Maxima exposicion a risk assets. Growth, small caps, crypto."
            _profile_color = "#58a6ff"

        st.markdown(f"""<div style="font-size:0.6rem; text-transform:uppercase; letter-spacing:0.6px; color:#6e7681; font-weight:600; margin:8px 0 2px 0;">Recommended Allocation</div>
<div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
<span style="background:{_profile_color}22; color:{_profile_color}; padding:2px 8px; border-radius:4px; font-size:0.6rem; font-weight:700;">{_profile_label}</span>
</div>
<div style="font-size:0.58rem; color:#8b949e; margin-bottom:6px; line-height:1.3;">{_profile_desc} Esta allocation es reactiva al riesgo de mercado actual (score {score}/100) y asume un inversor europeo (EUR) con horizonte medio-largo plazo. No es personalizada — ajusta segun tu tolerancia al riesgo real.</div>""", unsafe_allow_html=True)
        col_alloc, col_detail = st.columns([1, 1])
        with col_alloc:
            alloc_labels = ['Equity', 'Bonds', 'Cash', 'Gold', 'Commodities', 'Crypto', 'Alternatives']
            alloc_values = [allocation.get('equity', 0), allocation.get('bonds', 0), allocation.get('cash', 0),
                            allocation.get('gold_physical', 0), allocation.get('commodities', 0),
                            allocation.get('crypto', 0), allocation.get('alternatives', 0)]
            alloc_colors = ['#58a6ff', '#3fb950', '#d29922', '#f0883e', '#bc8cff', '#39d2c0', '#8b949e']
            filtered = [(l, v, c) for l, v, c in zip(alloc_labels, alloc_values, alloc_colors) if v > 0]
            if filtered:
                f_labels, f_values, f_colors = zip(*filtered)
            else:
                f_labels, f_values, f_colors = alloc_labels, alloc_values, alloc_colors
            fig_alloc = go.Figure(data=[go.Pie(
                labels=list(f_labels), values=list(f_values),
                hole=0.45, marker_colors=list(f_colors),
                textinfo='label+percent', textposition='outside',
            )])
            fig_alloc.update_layout(height=180, margin=dict(l=5, r=5, t=5, b=5),
                                     paper_bgcolor='rgba(0,0,0,0)', font={'color': '#e6edf3', 'size': 9}, showlegend=False)
            st.plotly_chart(fig_alloc, use_container_width=True, config={'displayModeBar': False})
            rationale = allocation.get('rationale', [])
            if rationale:
                for r in rationale:
                    st.markdown(f'<div style="font-size:0.62rem; color:#8b949e; padding:0;">- {_esc(r)}</div>', unsafe_allow_html=True)

        with col_detail:
            equity_sectors = allocation.get('equity_sectors', {})
            if equity_sectors:
                st.markdown('<div style="font-size:0.6rem; text-transform:uppercase; letter-spacing:0.6px; color:#58a6ff; font-weight:600; margin-bottom:4px;">Equity Sector Tilt</div>', unsafe_allow_html=True)
                for sector, pct in equity_sectors.items():
                    st.markdown(f'''<div style="display:flex; align-items:center; gap:4px; margin:1px 0;">
                        <span style="font-size:0.62rem; color:#e6edf3; min-width:100px;">{sector}</span>
                        <div style="flex:1; height:4px; background:#21262d; border-radius:2px; overflow:hidden;">
                            <div style="width:{pct}%; height:100%; background:#58a6ff; border-radius:2px;"></div>
                        </div>
                        <span style="font-size:0.62rem; color:#58a6ff; font-weight:600; min-width:24px; text-align:right;">{pct}%</span>
                    </div>''', unsafe_allow_html=True)

            bond_detail = allocation.get('bond_detail', {})
            bond_strategy = allocation.get('bond_strategy', '')
            if bond_detail:
                strat_label = {'long_duration': 'LONG', 'short_duration': 'SHORT', 'mixed_duration': 'MIX'}.get(bond_strategy, '')
                strat_color = {'long_duration': '#3fb950', 'short_duration': '#f0883e', 'mixed_duration': '#d29922'}.get(bond_strategy, '#8b949e')
                st.markdown(f'''<div style="font-size:0.6rem; text-transform:uppercase; color:#3fb950; font-weight:600; margin:8px 0 3px;">
                    Bonds <span style="background:{strat_color}22; color:{strat_color}; padding:1px 5px; border-radius:3px; font-size:0.55rem;">{strat_label}</span>
                </div>''', unsafe_allow_html=True)
                bond_names = {'govt_short': ('Govt 1-3Y', '#58a6ff'), 'govt_long': ('Govt 7-20Y', '#3fb950'),
                              'corp_ig': ('Corp IG', '#d29922'), 'inflation_linked': ('TIPS', '#f0883e'), 'high_yield': ('HY', '#f85149')}
                for bk, (bname, bcolor) in bond_names.items():
                    bpct = bond_detail.get(bk, 0)
                    if bpct > 0:
                        st.markdown(f'''<div style="display:flex; align-items:center; gap:4px; margin:1px 0;">
                            <span style="font-size:0.6rem; color:#e6edf3; min-width:70px;">{bname}</span>
                            <div style="flex:1; height:4px; background:#21262d; border-radius:2px;">
                                <div style="width:{bpct}%; height:100%; background:{bcolor};"></div>
                            </div>
                            <span style="font-size:0.6rem; color:{bcolor}; font-weight:600;">{bpct}%</span>
                        </div>''', unsafe_allow_html=True)

    # --- ROW 4: Module detail expanders ---
    for key, (name, color) in module_names.items():
        mod_info = module_explanations.get(key, {})
        mod_signals = mod_info.get('signals', [])
        mod_alerts = mod_info.get('alerts', [])
        ms = module_scores.get(key, 0)
        if isinstance(ms, dict):
            ms = ms.get('score', 0)
        pct = min(max(ms, 0), 100)
        weight = module_weights.get(key, 0)
        wc = round(ms * weight / 100, 1)
        severity = mod_info.get('severity', 'BAJO' if ms < 30 else ('MODERADO' if ms < 50 else ('ELEVADO' if ms < 70 else 'CRITICO')))
        sev_colors = {'CRITICO': '#f85149', 'ELEVADO': '#f0883e', 'MODERADO': '#d29922', 'BAJO': '#3fb950'}
        sev_color = sev_colors.get(severity, '#8b949e')

        if key == 'market_technicals' and 'grouped_signals' in mod_info:
            with st.expander(f"{name} — {pct:.0f}/100 (w:{weight}%) → {wc}pts", expanded=False):
                grouped = mod_info['grouped_signals']
                asset_scores = mod_info.get('asset_scores', {})
                for asset_name, details in grouped.items():
                    a_score = None
                    for tk, nm in [('SPY','S&P 500'),('QQQ','Nasdaq 100'),('IWM','Russell 2000'),
                                   ('GLD','Gold ETF'),('SLV','Silver ETF'),('XLE','Energy'),
                                   ('XLF','Financials'),('TLT','Long Treasuries'),('HYG','High Yield Bonds'),('DXY','Dollar Index')]:
                        if nm == asset_name:
                            a_score = asset_scores.get(tk)
                            break
                    score_txt = f" (risk: {a_score}/100)" if a_score is not None else ""
                    st.markdown(f"**{asset_name}**{score_txt}")
                    for d in details:
                        st.markdown(f"  - {_esc(d)}")
                if mod_alerts:
                    for alert in mod_alerts[:5]:
                        st.error(_esc(str(alert)))
        else:
            if mod_signals or mod_alerts:
                with st.expander(f"{name} — {pct:.0f}/100 (w:{weight}%) → {wc}pts", expanded=False):
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="background:{sev_color}22; color:{sev_color}; padding:2px 10px; border-radius:10px; font-size:0.75rem; font-weight:600;">{severity}</span>
                    </div>
                    <div style="background:#21262d; border-radius:8px; padding:3px; margin-bottom:10px;">
                        <div style="background:{color}; width:{pct}%; height:8px; border-radius:8px;"></div>
                    </div>""", unsafe_allow_html=True)
                    if mod_signals:
                        for sig in mod_signals[:10]:
                            st.markdown(f"- {_esc(str(sig))}")
                    if mod_alerts:
                        for alert in mod_alerts:
                            st.error(_esc(str(alert)))


# =============================================================================
# PAGE 1: DASHBOARD (TradingView-inspired)
# =============================================================================
def show_dashboard():
    """Professional trading terminal dashboard."""
    import plotly.graph_objects as go

    # Compact date line
    st.markdown(f"""
    <div style="display:flex; justify-content:flex-end; margin-bottom:2px;">
        <span style="color:#6e7681; font-size:0.6rem;">{datetime.now().strftime('%d %b %Y')} · <span style="color:#58a6ff;">{datetime.now().strftime('%H:%M')}</span></span>
    </div>
    """, unsafe_allow_html=True)

    # =========================================================================
    # SECTION A: TICKER STRIP (with futures)
    # =========================================================================
    with st.spinner("Loading market data..."):
        market_data = get_market_overview_data()
    try:
        gf_strip = get_global_futures()
    except Exception:
        gf_strip = {}
    if market_data:
        st.markdown(_render_ticker_strip(market_data, gf_strip), unsafe_allow_html=True)

    # =========================================================================
    # GLOBAL INTELLIGENCE PANEL (worldmonitor-style)
    # =========================================================================
    gf = gf_strip  # Reuse futures data from ticker strip

    # --- Row: Bloomberg TV (small) + Global Markets Grid + Quick Intel ---
    col_video, col_markets, col_intel = st.columns([2, 5, 3])

    with col_video:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:4px; margin-bottom:1px;">
            <span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:#f85149;animation:blink 2s infinite;"></span>
            <span style="font-size:0.55rem; color:#e6edf3; font-weight:600; letter-spacing:0.5px;">LIVE</span>
        </div>
        <style>@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0.4;} }</style>
        """, unsafe_allow_html=True)
        st.video("https://www.youtube.com/watch?v=iEpJwprxDdk", autoplay=True, muted=True)

    with col_markets:
        # Global Markets Table — Spot (C) vs Futures (F) side by side
        # Each row: Asset | Spot price + chg | Futures price + chg
        market_table_rows = [
            # (label, spot_sym, futures_sym, color)
            ('S&P 500',     '^GSPC',    'ES=F',    '#58a6ff'),
            ('Nasdaq',      '^IXIC',    'NQ=F',    '#bc8cff'),
            ('Dow Jones',   '^DJI',     'YM=F',    '#3fb950'),
            ('Russell 2000','^RUT',     'RTY=F',   '#d29922'),
            ('EuroStoxx 50','^STOXX50E', None,     '#bc8cff'),
            ('DAX',         '^GDAXI',   None,      '#58a6ff'),
            ('FTSE 100',    '^FTSE',    None,       '#3fb950'),
            ('Nikkei 225',  '^N225',    None,       '#d29922'),
            ('Gold',        'GC=F',     None,       '#d29922'),
            ('Silver',      'SI=F',     None,       '#8b949e'),
            ('WTI Oil',     'CL=F',     'BZ=F',    '#f0883e'),
            ('Nat Gas',     'NG=F',     None,       '#39d2c0'),
            ('Copper',      'HG=F',     None,       '#bc8cff'),
            ('10Y Bond',    '^TNX',     'ZN=F',    '#58a6ff'),
            ('30Y Bond',    '^TYX',     'ZB=F',    '#bc8cff'),
            ('5Y Yield',    '^FVX',     None,       '#d29922'),
            ('3M T-Bill',   '^IRX',     None,       '#8b949e'),
            ('DXY',         'DX-Y.NYB', None,       '#3fb950'),
            ('EUR/USD',     'EURUSD=X', None,       '#d29922'),
            ('GBP/USD',     'GBPUSD=X', None,       '#58a6ff'),
            ('USD/JPY',     'JPY=X',    None,       '#f0883e'),
            ('VIX',         '^VIX',     None,       '#f85149'),
            ('Bitcoin',     'BTC-USD',  None,       '#f0883e'),
            ('Ethereum',    'ETH-USD',  None,       '#bc8cff'),
            ('Solana',      'SOL-USD',  None,       '#39d2c0'),
        ]

        # Label for second column based on asset
        _fut_labels = {
            'ES=F': 'Fut', 'NQ=F': 'Fut', 'YM=F': 'Fut', 'RTY=F': 'Fut',
            'BZ=F': 'Brent', 'ZN=F': 'Fut', 'ZB=F': 'Fut',
        }

        def _fmt_p(sym, price):
            """Format price based on instrument type."""
            typ = gf.get(sym, {}).get('type', '')
            if typ in ('rate',):
                return f'{price:.2f}%'
            if typ in ('fx',) and price < 10:
                return f'{price:.4f}'
            if price >= 10000:
                return f'&#36;{price:,.0f}'
            if price >= 100:
                return f'&#36;{price:,.1f}'
            return f'&#36;{price:,.2f}'

        def _chg_html(chg, sym=''):
            """Format change % with color and arrow."""
            is_rate = gf.get(sym, {}).get('type', '') == 'rate'
            is_vix = 'VIX' in sym
            if is_rate or is_vix:
                c = '#f85149' if chg >= 0 else '#3fb950'
            else:
                c = '#3fb950' if chg >= 0 else '#f85149'
            a = '▲' if chg >= 0 else '▼'
            s = '+' if chg >= 0 else ''
            return f'<span style="font-size:0.5rem; color:{c}; font-weight:600;">{a}{s}{chg:.2f}%</span>'

        # Group rows by category for visual separation
        _categories = [
            ('US INDICES', 0, 4), ('EU / ASIA', 4, 8), ('COMMODITIES', 8, 13),
            ('RATES', 13, 17), ('FX & VOL', 17, 22), ('CRYPTO', 22, 25),
        ]

        grid_html = '<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:4px;">'
        for cat_name, start, end in _categories:
            rows = market_table_rows[start:end]
            # Check if any row in this category has a futures counterpart
            has_futures = any(r[2] is not None and r[2] in gf for r in rows)

            grid_html += f'<div style="background:#161b22; border:1px solid #21262d; border-radius:6px; padding:4px 6px;">'
            # Header with column labels
            if has_futures:
                grid_html += f'''<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #21262d; padding-bottom:2px; margin-bottom:3px;">
                    <span style="font-size:0.5rem; text-transform:uppercase; letter-spacing:0.8px; color:#6e7681; font-weight:600;">{cat_name}</span>
                    <div style="display:flex; gap:8px;">
                        <span style="font-size:0.45rem; color:#58a6ff; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">Spot</span>
                        <span style="font-size:0.45rem; color:#d29922; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">Futures</span>
                    </div>
                </div>'''
            else:
                grid_html += f'<div style="font-size:0.5rem; text-transform:uppercase; letter-spacing:0.8px; color:#6e7681; font-weight:600; margin-bottom:3px; border-bottom:1px solid #21262d; padding-bottom:2px;">{cat_name}</div>'

            for label, spot_sym, fut_sym, color in rows:
                sd = gf.get(spot_sym, {})
                sp = sd.get('price', 0)
                sc = sd.get('change', 0)
                if sp == 0:
                    continue

                if fut_sym and fut_sym in gf:
                    fd = gf[fut_sym]
                    fp = fd.get('price', 0)
                    fc = fd.get('change', 0)
                    fl = _fut_labels.get(fut_sym, 'Fut')
                    grid_html += f'''<div style="display:flex; justify-content:space-between; align-items:center; padding:2px 0; border-bottom:1px solid #1c2333;">
                        <span style="font-size:0.6rem; color:{color}; font-weight:600; min-width:60px;">{label}</span>
                        <div style="display:flex; gap:6px; align-items:center;">
                            <div style="text-align:right; border-right:1px solid #30363d; padding-right:6px;">
                                <span style="font-size:0.45rem; color:#58a6ff; font-weight:600;">C</span>
                                <span style="font-size:0.6rem; color:#e6edf3; font-weight:700; margin-left:2px;">{_fmt_p(spot_sym, sp)}</span>
                                {_chg_html(sc, spot_sym)}
                            </div>
                            <div style="text-align:right;">
                                <span style="font-size:0.45rem; color:#d29922; font-weight:600;">{fl[0]}</span>
                                <span style="font-size:0.6rem; color:#e6edf3; font-weight:700; margin-left:2px;">{_fmt_p(fut_sym, fp)}</span>
                                {_chg_html(fc, fut_sym)}
                            </div>
                        </div>
                    </div>'''
                else:
                    grid_html += f'''<div style="display:flex; justify-content:space-between; align-items:center; padding:2px 0; border-bottom:1px solid #1c2333;">
                        <span style="font-size:0.6rem; color:{color}; font-weight:600;">{label}</span>
                        <div style="text-align:right;">
                            <span style="font-size:0.65rem; color:#e6edf3; font-weight:700;">{_fmt_p(spot_sym, sp)}</span>
                            {_chg_html(sc, spot_sym)}
                        </div>
                    </div>'''

            grid_html += '</div>'
        grid_html += '</div>'
        st.markdown(grid_html, unsafe_allow_html=True)

    with col_intel:
        # News + Expanders stacked
        try:
            news = get_market_news()
            if news:
                st.markdown('<div style="font-size:0.5rem; text-transform:uppercase; letter-spacing:0.8px; color:#6e7681; font-weight:600; margin-bottom:3px;">HEADLINES</div>', unsafe_allow_html=True)
                news_html = ''
                for item in news[:6]:
                    title = item.get('title', '')
                    link = item.get('link', '')
                    source = item.get('source', '')
                    if title:
                        news_html += f'''<a href="{link}" target="_blank" style="text-decoration:none; display:block; margin-bottom:1px;">
                            <div style="background:#161b22; padding:3px 5px; border-radius:3px; border-left:2px solid #30363d;">
                                <div style="font-size:0.58rem; color:#e6edf3; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{_esc(title[:65])}</div>
                                <div style="font-size:0.45rem; color:#6e7681;">{_esc(source[:20])}</div>
                            </div></a>'''
                st.markdown(news_html, unsafe_allow_html=True)
        except Exception:
            pass

    # --- Full-width Economic Indicators strip ---
    try:
        from webapp.data.providers import get_economic_indicators
        economic_data = get_economic_indicators()
        if economic_data:
            econ_items = [
                ('unemployment', 'Unemp', '%', '#f85149', 1),
                ('cpi_yoy', 'CPI', '%', '#f0883e', 1),
                ('pce_yoy', 'PCE', '%', '#d29922', 1),
                ('gdp_growth', 'GDP', '%', '#3fb950', 1),
                ('fed_funds', 'Fed Rate', '%', '#58a6ff', 2),
                ('yield_curve', '10Y-2Y', '%', '#bc8cff', 2),
                ('consumer_sentiment', 'Sentiment', '', '#39d2c0', 1),
                ('nonfarm_payrolls', 'Payrolls', 'K', '#d29922', 0),
            ]
            econ_html = '<div style="display:flex; gap:3px; flex-wrap:wrap; margin-top:4px;">'
            for key, label, unit, color, dec in econ_items:
                if key in economic_data:
                    val = economic_data[key]
                    if key == 'nonfarm_payrolls':
                        val = val / 1000
                    prev = economic_data.get(f'{key}_prev', val)
                    if key == 'nonfarm_payrolls' and prev:
                        prev = prev / 1000
                    chg_color = '#3fb950' if val >= (prev or val) else '#f85149'
                    arrow = '▲' if val >= (prev or val) else '▼'
                    econ_html += f'''<div style="background:#161b22;border:1px solid #21262d;border-radius:3px;padding:2px 5px;display:flex;align-items:center;gap:3px;">
                        <span style="font-size:0.5rem;color:#6e7681;">{label}</span>
                        <span style="font-size:0.62rem;color:{color};font-weight:700;">{val:.{dec}f}{unit}</span>
                        <span style="font-size:0.45rem;color:{chg_color};">{arrow}</span>
                    </div>'''
            econ_html += '</div>'
            st.markdown(econ_html, unsafe_allow_html=True)
    except Exception:
        pass

    # =========================================================================
    # RISK COMMAND CENTER (under Bloomberg TV area)
    # =========================================================================
    with st.spinner("Computing risk exposure..."):
        risk_data = get_risk_exposure_score()

    score = risk_data.get('final_score', 50)
    regime = risk_data.get('regime', {})
    regime_level = regime.get('level', 'CAUTELA')
    regime_color = get_regime_color(score)
    crash_probs = risk_data.get('crash_probabilities', {})
    module_scores = risk_data.get('module_scores', {})
    alerts = risk_data.get('alerts', [])

    _show_risk_command_center(risk_data, module_scores, crash_probs, score, regime, regime_color, alerts, go)

    # =========================================================================
    # SECTION D: SECTOR HEATMAP
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">🗺</span>
        <h3>Sector Heatmap</h3>
        <span class="section-badge">DAILY</span>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading sector data..."):
        ticker_changes = get_all_ticker_changes()
    if ticker_changes:
        st.markdown(_render_sector_heatmap(ticker_changes), unsafe_allow_html=True)
    else:
        st.caption("Sector data unavailable")

    # =========================================================================
    # SECTION D2: SECTOR MOMENTUM
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">📈</span>
        <h3>Sector Momentum</h3>
        <span class="section-badge">ETF-BASED</span>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading sector momentum..."):
        from webapp.data.providers import get_sector_momentum
        sector_mom = get_sector_momentum()

    if sector_mom:
        # Sort by 1M momentum
        sorted_sectors = sorted(sector_mom.items(), key=lambda x: x[1]['mom_1m'], reverse=True)

        def _mom_bar(val, max_abs=15):
            """Render a horizontal momentum bar."""
            clamped = max(min(val, max_abs), -max_abs)
            pct = abs(clamped) / max_abs * 50
            color = '#3fb950' if val >= 0 else '#f85149'
            sign = '+' if val >= 0 else ''
            if val >= 0:
                return f'''<div style="display:flex;align-items:center;gap:4px;">
                    <div style="width:50%;text-align:right;"><div style="display:inline-block;height:10px;width:{pct}%;background:{color};border-radius:2px;"></div></div>
                    <div style="width:50%;"><span style="font-size:0.65rem;color:{color};font-weight:600;">{sign}{val:.1f}%</span></div>
                </div>'''
            else:
                return f'''<div style="display:flex;align-items:center;gap:4px;">
                    <div style="width:50%;text-align:right;"><span style="font-size:0.65rem;color:{color};font-weight:600;">{sign}{val:.1f}%</span></div>
                    <div style="width:50%;"><div style="display:inline-block;height:10px;width:{pct}%;background:{color};border-radius:2px;"></div></div>
                </div>'''

        rows_html = ''
        for sector_name, mom in sorted_sectors:
            color_1w = '#3fb950' if mom['mom_1w'] >= 0 else '#f85149'
            color_1m = '#3fb950' if mom['mom_1m'] >= 0 else '#f85149'
            color_3m = '#3fb950' if mom['mom_3m'] >= 0 else '#f85149'
            sign_1w = '+' if mom['mom_1w'] >= 0 else ''
            sign_1m = '+' if mom['mom_1m'] >= 0 else ''
            sign_3m = '+' if mom['mom_3m'] >= 0 else ''
            rows_html += f'''<tr>
                <td style="padding:5px 8px;font-size:0.7rem;color:#e6edf3;font-weight:500;white-space:nowrap;">{sector_name}</td>
                <td style="padding:5px 4px;font-size:0.6rem;color:#8b949e;">{mom['etf']}</td>
                <td style="padding:5px 8px;text-align:right;font-size:0.7rem;color:{color_1w};font-weight:600;">{sign_1w}{mom['mom_1w']:.1f}%</td>
                <td style="padding:5px 8px;text-align:right;font-size:0.7rem;color:{color_1m};font-weight:600;">{sign_1m}{mom['mom_1m']:.1f}%</td>
                <td style="padding:5px 8px;text-align:right;font-size:0.7rem;color:{color_3m};font-weight:600;">{sign_3m}{mom['mom_3m']:.1f}%</td>
            </tr>'''

        st.markdown(f'''
        <div style="background:#161b22;border:1px solid #21262d;border-radius:10px;overflow:hidden;">
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="border-bottom:1px solid #30363d;">
                        <th style="padding:6px 8px;text-align:left;font-size:0.6rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;">Sector</th>
                        <th style="padding:6px 4px;text-align:left;font-size:0.6rem;color:#8b949e;text-transform:uppercase;">ETF</th>
                        <th style="padding:6px 8px;text-align:right;font-size:0.6rem;color:#8b949e;text-transform:uppercase;">1W</th>
                        <th style="padding:6px 8px;text-align:right;font-size:0.6rem;color:#8b949e;text-transform:uppercase;">1M</th>
                        <th style="padding:6px 8px;text-align:right;font-size:0.6rem;color:#8b949e;text-transform:uppercase;">3M</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.caption("Sector momentum data unavailable")

    # =========================================================================
    # SECTION E: MARKET MOVERS (4 columns)
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">🔥</span>
        <h3>Market Movers</h3>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading movers..."):
        movers = get_market_movers()

    col_gain, col_lose, col_active, col_unusual = st.columns(4)

    with col_gain:
        st.markdown('<div class="mover-section-title">🟢 Top Gainers</div>', unsafe_allow_html=True)
        for i, stock in enumerate(movers.get('gainers', [])):
            html = _render_mover_card(stock, 'gain', i, rank=i+1)
            st.markdown(html, unsafe_allow_html=True)
            if st.button(f"→ {stock['ticker']}", key=f"mg_{stock['ticker']}_{i}", use_container_width=True):
                navigate_to_stock(stock['ticker'])
                st.rerun()
        if not movers.get('gainers'):
            st.caption("No data")

    with col_lose:
        st.markdown('<div class="mover-section-title">🔴 Top Losers</div>', unsafe_allow_html=True)
        for i, stock in enumerate(movers.get('losers', [])):
            html = _render_mover_card(stock, 'lose', i, rank=i+1)
            st.markdown(html, unsafe_allow_html=True)
            if st.button(f"→ {stock['ticker']}", key=f"ml_{stock['ticker']}_{i}", use_container_width=True):
                navigate_to_stock(stock['ticker'])
                st.rerun()
        if not movers.get('losers'):
            st.caption("No data")

    with col_active:
        st.markdown('<div class="mover-section-title">📊 Most Active</div>', unsafe_allow_html=True)
        for i, stock in enumerate(movers.get('active', [])):
            html = _render_mover_card(stock, 'active', i, rank=i+1)
            st.markdown(html, unsafe_allow_html=True)
            if st.button(f"→ {stock['ticker']}", key=f"ma_{stock['ticker']}_{i}", use_container_width=True):
                navigate_to_stock(stock['ticker'])
                st.rerun()
        if not movers.get('active'):
            st.caption("No data")

    with col_unusual:
        st.markdown('<div class="mover-section-title">⚡ Unusual Volume</div>', unsafe_allow_html=True)
        for i, stock in enumerate(movers.get('unusual', [])):
            vol_ratio = stock['volume'] / stock['avg_volume'] if stock['avg_volume'] > 0 else 0
            html = _render_mover_card(stock, 'unusual', i, rank=i+1)
            st.markdown(html, unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center; font-size:0.55rem; color:#d29922; margin:-2px 0 3px 0;">{vol_ratio:.1f}x avg vol</div>', unsafe_allow_html=True)
            if st.button(f"→ {stock['ticker']}", key=f"mu_{stock['ticker']}_{i}", use_container_width=True):
                navigate_to_stock(stock['ticker'])
                st.rerun()
        if not movers.get('unusual'):
            st.caption("No unusual volume detected")

    # =========================================================================
    # SECTION F: LIQUIDITY INDICATORS + TOP PICKS
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">💧</span>
        <h3>Market Conditions &amp; Top Picks</h3>
    </div>""", unsafe_allow_html=True)

    col_indicators, col_picks = st.columns([1, 2])

    with col_indicators:
        monetary = get_monetary_data()
        vix_data = get_vix()
        vix = vix_data.get('current', 15)
        regime_mon = monetary.get('regime', {})
        regime_name = regime_mon.get('name', 'NEUTRAL') if isinstance(regime_mon, dict) else 'NEUTRAL'
        net_liq = monetary.get('net_liquidity', {})
        liq_value = net_liq.get('current', 5800) if isinstance(net_liq, dict) else 5800

        # Market status
        if vix < 18 and regime_name == 'ABUNDANT':
            status_emoji, status_text, status_color = '🟢', 'RISK ON', '#3fb950'
        elif vix > 25 or regime_name == 'SCARCE':
            status_emoji, status_text, status_color = '🔴', 'RISK OFF', '#f85149'
        else:
            status_emoji, status_text, status_color = '🟡', 'NEUTRAL', '#d29922'

        st.markdown(f"""
        <div style="background:#161b22; border:1px solid {status_color}; border-radius:8px;
                    padding:10px; text-align:center; margin-bottom:8px;">
            <div style="font-size:1.2rem;">{status_emoji}</div>
            <div style="font-size:0.82rem; font-weight:700; color:{status_color};">{status_text}</div>
            <div style="font-size:0.58rem; color:#6e7681; margin-top:2px;">Regime: {regime_name}</div>
        </div>
        """, unsafe_allow_html=True)

        # Mini gauges
        vix_color = '#3fb950' if vix < 18 else ('#d29922' if vix < 25 else '#f85149')
        vix_gauge = _svg_mini_gauge(vix, 50, 'VIX', vix_color, size=70)
        liq_pct = min(liq_value / 8000, 1)
        liq_color = '#3fb950' if liq_pct > 0.7 else ('#d29922' if liq_pct > 0.5 else '#f85149')
        liq_gauge = _svg_mini_gauge(liq_value, 8000, 'Liquidity', liq_color, size=70)

        st.markdown(f"""
        <div style="display:flex; gap:6px;">
            <div class="mini-gauge" style="padding:8px;">
                {vix_gauge}
                <div class="gauge-label">VIX</div>
                <div class="gauge-value" style="font-size:0.9rem;">{vix:.1f}</div>
            </div>
            <div class="mini-gauge" style="padding:8px;">
                {liq_gauge}
                <div class="gauge-label">Net Liq</div>
                <div class="gauge-value" style="font-size:0.9rem;">&#36;{liq_value/1000:.1f}T</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_picks:
        st.markdown('<div style="font-size:0.6rem; text-transform:uppercase; letter-spacing:0.6px; color:#6e7681; font-weight:600; margin-bottom:6px;">Top Picks (click to analyze)</div>', unsafe_allow_html=True)
        tab_cp, tab_mp, tab_lp = st.tabs(["Short Term", "Medium Term", "Long Term"])

        with tab_cp:
            with st.spinner(""):
                short_tickers = ['NVDA', 'AVGO', 'MSFT', 'META', 'GOOGL', 'AMD', 'AAPL']
                scores_df = get_multi_horizon_scores(short_tickers)
                if not scores_df.empty:
                    scores_df = scores_df.sort_values('Score CP', ascending=False).head(5)
                    picks_html = '<div style="display:flex; gap:6px; flex-wrap:wrap;">'
                    for _, row in scores_df.iterrows():
                        s = row['Score CP']
                        ring = _svg_score_ring(s, size=52)
                        signal = row.get('Señal CP', '')
                        picks_html += f'''<div class="score-ring-card" style="flex:1; min-width:100px;">
                            {ring}
                            <div style="font-size:0.88rem; font-weight:700; color:#e6edf3; margin-top:4px;">{row['Ticker']}</div>
                            <div style="font-size:0.62rem; color:#8b949e;">{signal}</div>
                        </div>'''
                    picks_html += '</div>'
                    st.markdown(picks_html, unsafe_allow_html=True)
                    # Navigation buttons
                    btn_cols = st.columns(len(scores_df))
                    for i, (_, row) in enumerate(scores_df.iterrows()):
                        with btn_cols[i]:
                            if st.button(f"→ {row['Ticker']}", key=f"top_cp_{row['Ticker']}", use_container_width=True):
                                navigate_to_stock(row['Ticker'])
                                st.rerun()

        with tab_mp:
            with st.spinner(""):
                mp_tickers = ['NVDA', 'AVGO', 'MSFT', 'META', 'GOOGL', 'AMD', 'AAPL', 'CRM', 'PLTR', 'GS']
                scores_mp_df = get_multi_horizon_scores(mp_tickers)
                if not scores_mp_df.empty:
                    scores_mp_df = scores_mp_df.sort_values('Score MP', ascending=False).head(5)
                    picks_html = '<div style="display:flex; gap:6px; flex-wrap:wrap;">'
                    for _, row in scores_mp_df.iterrows():
                        s = row['Score MP']
                        ring = _svg_score_ring(s, size=52)
                        signal = row.get('Señal MP', '')
                        picks_html += f'''<div class="score-ring-card" style="flex:1; min-width:100px;">
                            {ring}
                            <div style="font-size:0.88rem; font-weight:700; color:#e6edf3; margin-top:4px;">{row['Ticker']}</div>
                            <div style="font-size:0.62rem; color:#8b949e;">{signal}</div>
                        </div>'''
                    picks_html += '</div>'
                    st.markdown(picks_html, unsafe_allow_html=True)
                    btn_cols = st.columns(len(scores_mp_df))
                    for i, (_, row) in enumerate(scores_mp_df.iterrows()):
                        with btn_cols[i]:
                            if st.button(f"→ {row['Ticker']}", key=f"top_mp_{row['Ticker']}", use_container_width=True):
                                navigate_to_stock(row['Ticker'])
                                st.rerun()

        with tab_lp:
            with st.spinner(""):
                long_tickers = ['GILD', 'BMY', 'PFE', 'JNJ', 'PG', 'KO', 'UNH']
                scores_df = get_multi_horizon_scores(long_tickers)
                if not scores_df.empty:
                    scores_df = scores_df.sort_values('Score LP', ascending=False).head(5)
                    picks_html = '<div style="display:flex; gap:6px; flex-wrap:wrap;">'
                    for _, row in scores_df.iterrows():
                        s = row['Score LP']
                        ring = _svg_score_ring(s, size=52)
                        signal = row.get('Señal LP', '')
                        picks_html += f'''<div class="score-ring-card" style="flex:1; min-width:100px;">
                            {ring}
                            <div style="font-size:0.88rem; font-weight:700; color:#e6edf3; margin-top:4px;">{row['Ticker']}</div>
                            <div style="font-size:0.62rem; color:#8b949e;">{signal}</div>
                        </div>'''
                    picks_html += '</div>'
                    st.markdown(picks_html, unsafe_allow_html=True)
                    btn_cols = st.columns(len(scores_df))
                    for i, (_, row) in enumerate(scores_df.iterrows()):
                        with btn_cols[i]:
                            if st.button(f"→ {row['Ticker']}", key=f"top_lp_{row['Ticker']}", use_container_width=True):
                                navigate_to_stock(row['Ticker'])
                                st.rerun()

    # =========================================================================
    # SECTION G: CONGRESS TRADES (lazy-loaded on demand)
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">🏛</span>
        <h3>Congress Insider Trades</h3>
        <span class="section-badge">30D</span>
    </div>""", unsafe_allow_html=True)

    _show_congress = st.checkbox("Load Congress Trades", value=False, key="dash_congress_load",
                                  help="Click to load congress trading data (slow API)")
    if _show_congress:
        with st.spinner("Loading congress trades..."):
            congress_stats = get_congress_stats(days=30)
        total_trades = congress_stats.get('total_trades', 0)
        buys = congress_stats.get('buys', 0)
        sells = congress_stats.get('sells', 0)
        politicians = congress_stats.get('total_politicians', 0)

        # Summary bar
        buy_pct = (buys / total_trades * 100) if total_trades > 0 else 50
        st.markdown(f"""
        <div class="congress-summary">
            <div class="congress-stat">
                <div class="stat-value">{total_trades}</div>
                <div class="stat-label">Total Trades</div>
            </div>
            <div class="congress-stat" style="border-color:#3fb950;">
                <div class="stat-value" style="color:#3fb950;">{buys}</div>
                <div class="stat-label">Buys</div>
            </div>
            <div class="congress-stat" style="border-color:#f85149;">
                <div class="stat-value" style="color:#f85149;">{sells}</div>
                <div class="stat-label">Sells</div>
            </div>
            <div class="congress-stat">
                <div class="stat-value">{politicians}</div>
                <div class="stat-label">Politicians</div>
            </div>
        </div>
        <div style="background:#21262d; border-radius:4px; height:6px; margin-bottom:12px; overflow:hidden;">
            <div style="background:#3fb950; height:100%; width:{buy_pct:.0f}%; border-radius:4px;"></div>
        </div>
        """, unsafe_allow_html=True)

        trades_df = get_congress_trades(days=30)
        if not trades_df.empty:
            if 'disclosed_date' in trades_df.columns:
                trades_sorted = trades_df.sort_values('disclosed_date', ascending=False)
            elif 'traded_date' in trades_df.columns:
                trades_sorted = trades_df.sort_values('traded_date', ascending=False)
            else:
                trades_sorted = trades_df

            # Styled HTML table
            table_html = '''<table class="styled-table"><thead><tr>
                <th>Politician</th><th>Ticker</th><th>Type</th><th>Amount</th><th>Date</th>
            </tr></thead><tbody>'''
            for _, trade in trades_sorted.head(8).iterrows():
                politician = _esc(str(trade.get('politician', 'Unknown')))
                ticker = trade.get('ticker', 'N/A')
                tx_type = trade.get('transaction_type', '')
                amount = _esc(str(trade.get('amount_range', 'N/A')))
                date_val = trade.get('disclosed_date', trade.get('traded_date', ''))
                date_str = str(date_val)[:10] if date_val else ''
                is_insider = trade.get('committee_relevant', False) if 'committee_relevant' in trades_sorted.columns else False
                insider_badge = ' <span style="background:rgba(248,81,73,0.2);color:#f85149;padding:1px 5px;border-radius:4px;font-size:0.6rem;font-weight:600;">INSIDER</span>' if is_insider else ''
                if 'buy' in str(tx_type).lower():
                    type_pill = '<span style="background:rgba(63,185,80,0.15); color:#3fb950; padding:2px 8px; border-radius:10px; font-size:0.7rem; font-weight:600;">BUY</span>'
                else:
                    type_pill = '<span style="background:rgba(248,81,73,0.15); color:#f85149; padding:2px 8px; border-radius:10px; font-size:0.7rem; font-weight:600;">SELL</span>'
                table_html += f'<tr><td>{politician}{insider_badge}</td><td style="color:#58a6ff; font-weight:600;">{ticker}</td><td>{type_pill}</td><td>{amount}</td><td style="color:#8b949e;">{date_str}</td></tr>'
            table_html += '</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)

            # Navigation buttons for tickers
            unique_tickers = trades_sorted.head(8)['ticker'].dropna().unique()[:5]
            if len(unique_tickers) > 0:
                btn_cols = st.columns(len(unique_tickers))
                for i, ticker in enumerate(unique_tickers):
                    with btn_cols[i]:
                        if ticker and ticker != 'N/A':
                            if st.button(f"→ {ticker}", key=f"cv_{ticker}_{i}", use_container_width=True):
                                navigate_to_stock(ticker)
                                st.rerun()

    col_spacer, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("View All Trades →", key="goto_signals", use_container_width=True):
            st.session_state.current_page_index = 2
            st.rerun()

    # =========================================================================
    # SECTION G2: EARNINGS CALENDAR
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">📅</span>
        <h3>Earnings Calendar — Next 30 Days</h3>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading earnings calendar..."):
        earnings = get_earnings_calendar(tuple(TICKER_UNIVERSE))

    if earnings:
        # Group by date
        from collections import defaultdict
        earn_by_date = defaultdict(list)
        for e in earnings:
            earn_by_date[e['date']].append(e)

        dates_sorted = sorted(earn_by_date.keys())
        for date_str in dates_sorted:
            items = earn_by_date[date_str]
            # Date header
            try:
                from datetime import datetime as _dt
                d = _dt.strptime(date_str, '%Y-%m-%d')
                day_label = d.strftime('%a %d %b')
            except Exception:
                day_label = date_str

            # Days until
            try:
                from datetime import date as _date
                days_until = (_dt.strptime(date_str, '%Y-%m-%d').date() - _date.today()).days
                if days_until == 0:
                    badge = '<span style="background:rgba(248,81,73,0.2); color:#f85149; padding:2px 8px; border-radius:10px; font-size:0.65rem; font-weight:600;">TODAY</span>'
                elif days_until == 1:
                    badge = '<span style="background:rgba(210,153,34,0.2); color:#d29922; padding:2px 8px; border-radius:10px; font-size:0.65rem; font-weight:600;">TOMORROW</span>'
                elif days_until <= 7:
                    badge = f'<span style="background:rgba(88,166,255,0.15); color:#58a6ff; padding:2px 8px; border-radius:10px; font-size:0.65rem; font-weight:600;">in {days_until}d</span>'
                else:
                    badge = f'<span style="color:#6e7681; font-size:0.65rem;">in {days_until}d</span>'
            except Exception:
                badge = ''

            cards_html = f'<div style="margin-bottom:8px;"><span style="color:#8b949e; font-size:0.8rem; font-weight:600;">{_esc(day_label)}</span> {badge}</div>'
            cards_html += '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px;">'
            for item in items:
                ticker = item['ticker']
                company = _esc(item.get('company', ticker)[:20])
                eps = item.get('eps_estimate')
                rev = item.get('revenue_estimate')
                mcap = item.get('market_cap', 0)
                # Market cap size indicator
                if mcap and mcap > 200e9:
                    cap_dot = '<span style="color:#d29922;">&#9679;</span>'
                elif mcap and mcap > 50e9:
                    cap_dot = '<span style="color:#58a6ff;">&#9679;</span>'
                else:
                    cap_dot = '<span style="color:#6e7681;">&#9679;</span>'

                eps_str = f'EPS est: &#36;{eps:.2f}' if eps is not None else ''
                rev_str = ''
                if rev is not None:
                    if rev >= 1e9:
                        rev_str = f'Rev est: &#36;{rev/1e9:.1f}B'
                    elif rev >= 1e6:
                        rev_str = f'Rev est: &#36;{rev/1e6:.0f}M'
                detail = f'<span style="color:#6e7681; font-size:0.65rem;">{eps_str}{" | " + rev_str if rev_str and eps_str else rev_str}</span>'

                cards_html += f'''<div style="background:#161b22; border:1px solid #21262d; border-radius:8px; padding:8px 12px; min-width:140px; cursor:pointer;" title="{_esc(item.get('company', ticker))}">
                    <div style="display:flex; align-items:center; gap:6px;">
                        {cap_dot}
                        <span style="color:#58a6ff; font-weight:700; font-size:0.8rem;">{ticker}</span>
                        <span style="color:#8b949e; font-size:0.7rem;">{company}</span>
                    </div>
                    {f'<div style="margin-top:4px;">{detail}</div>' if detail.strip() else ''}
                </div>'''
            cards_html += '</div>'
            st.markdown(cards_html, unsafe_allow_html=True)

        # Navigation buttons for earnings tickers
        earn_tickers = [e['ticker'] for e in earnings[:8]]
        if earn_tickers:
            btn_cols = st.columns(min(len(earn_tickers), 8))
            for i, ticker in enumerate(earn_tickers):
                with btn_cols[i]:
                    if st.button(f"→ {ticker}", key=f"earn_{ticker}_{i}", use_container_width=True):
                        navigate_to_stock(ticker)
                        st.rerun()
    else:
        st.markdown('<div style="color:#6e7681; padding:16px; text-align:center;">No earnings scheduled in the next 30 days for tracked tickers.</div>', unsafe_allow_html=True)

    # =========================================================================
    # SECTION G3: TOP MARKET NEWS
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">📰</span>
        <h3>Top Market News</h3>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading news..."):
        news_items = get_market_news()

    if news_items:
        news_html = '<div style="display:flex; flex-direction:column; gap:6px;">'
        for i, item in enumerate(news_items[:12]):
            title = _esc(item.get('title', ''))
            publisher = _esc(item.get('publisher', ''))
            pub_date = _esc(item.get('date', ''))
            link = item.get('link', '')
            tickers = item.get('tickers', [])

            ticker_pills = ''
            for tk in tickers[:3]:
                if tk:
                    ticker_pills += f'<span style="background:rgba(88,166,255,0.1); color:#58a6ff; padding:1px 6px; border-radius:8px; font-size:0.6rem; font-weight:600; margin-left:4px;">{_esc(str(tk))}</span>'

            # Alternate slight shading
            bg = '#161b22' if i % 2 == 0 else '#0d1117'

            inner = f'''<div style="flex:1; min-width:0;">
                    <div style="color:#e6edf3; font-size:0.8rem; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{title}</div>
                    <div style="display:flex; align-items:center; gap:8px; margin-top:3px;">
                        <span style="color:#6e7681; font-size:0.65rem;">{publisher}</span>
                        <span style="color:#30363d;">|</span>
                        <span style="color:#6e7681; font-size:0.65rem;">{pub_date}</span>
                        {ticker_pills}
                    </div>
                </div>'''

            if link:
                news_html += f'''<a href="{link}" target="_blank" style="text-decoration:none; display:block;">
                    <div style="background:{bg}; border:1px solid #21262d; border-radius:6px; padding:10px 14px; display:flex; justify-content:space-between; align-items:center; cursor:pointer;">
                        {inner}
                    </div></a>'''
            else:
                news_html += f'''<div style="background:{bg}; border:1px solid #21262d; border-radius:6px; padding:10px 14px; display:flex; justify-content:space-between; align-items:center;">
                    {inner}
                </div>'''
        news_html += '</div>'
        st.markdown(news_html, unsafe_allow_html=True)

        # Navigation buttons for tickers mentioned in news
        news_tickers = []
        for item in news_items:
            for tk in item.get('tickers', []):
                if tk and tk not in news_tickers and tk in TICKER_UNIVERSE:
                    news_tickers.append(tk)
                if len(news_tickers) >= 6:
                    break
            if len(news_tickers) >= 6:
                break
        if news_tickers:
            btn_cols = st.columns(len(news_tickers))
            for i, ticker in enumerate(news_tickers):
                with btn_cols[i]:
                    if st.button(f"→ {ticker}", key=f"news_{ticker}_{i}", use_container_width=True):
                        navigate_to_stock(ticker)
                        st.rerun()
    else:
        st.markdown('<div style="color:#6e7681; padding:16px; text-align:center;">No news available at this time.</div>', unsafe_allow_html=True)

    # =========================================================================
    # SECTION H: ALL STOCKS TABLE
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">📋</span>
        <h3>All Stocks — Multi-Horizon Scores</h3>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])
    with col1:
        horizon_view = st.selectbox("Sort by", ["Short Term", "Medium Term", "Long Term"], key="dash_hz")

    with st.spinner("Computing scores..."):
        all_tickers = tuple(TICKER_UNIVERSE)
        all_scores_df = get_all_scores_batch(all_tickers)

    if not all_scores_df.empty:
        sort_map = {"Short Term": "Score CP", "Medium Term": "Score MP", "Long Term": "Score LP"}
        signal_map = {"Short Term": "Señal CP", "Medium Term": "Señal MP", "Long Term": "Señal LP"}
        sort_col = sort_map[horizon_view]
        signal_col = signal_map[horizon_view]
        sorted_df = all_scores_df.sort_values(sort_col, ascending=False).copy()

        display_cols = ['Ticker', 'Empresa', 'Sector', 'Precio',
                        'Score CP', 'Señal CP', 'Score MP', 'Señal MP', 'Score LP', 'Señal LP']
        available_cols = [c for c in display_cols if c in sorted_df.columns]

        # Summary metrics with styled cards
        n_strong = len(sorted_df[sorted_df[signal_col].str.contains('STRONG', case=False, na=False)])
        n_buys = len(sorted_df[sorted_df[signal_col].str.contains('BUY|ACCUMULATE', case=False, na=False)])
        n_sells = len(sorted_df[sorted_df[signal_col].str.contains('SELL|REDUCE', case=False, na=False)])
        avg_score = sorted_df[sort_col].mean()

        st.markdown(f"""
        <div style="display:flex; gap:10px; margin-bottom:12px;">
            <div class="congress-stat" style="border-color:#3fb950;">
                <div class="stat-value" style="color:#3fb950;">{n_strong}</div>
                <div class="stat-label">Strong Buys</div>
            </div>
            <div class="congress-stat" style="border-color:#58a6ff;">
                <div class="stat-value" style="color:#58a6ff;">{n_buys}</div>
                <div class="stat-label">Buy Signals</div>
            </div>
            <div class="congress-stat" style="border-color:#f85149;">
                <div class="stat-value" style="color:#f85149;">{n_sells}</div>
                <div class="stat-label">Sell Signals</div>
            </div>
            <div class="congress-stat">
                <div class="stat-value">{avg_score:.0f}</div>
                <div class="stat-label">Avg Score</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        def get_action(signal):
            s = str(signal).upper()
            if 'STRONG' in s and 'BUY' in s: return 'COMPRAR FUERTE'
            if 'BUY' in s: return 'COMPRAR'
            if 'ACCUMULATE' in s: return 'ACUMULAR'
            if 'HOLD' in s: return 'MANTENER'
            if 'REDUCE' in s: return 'REDUCIR'
            if 'SELL' in s: return 'VENDER'
            return 'ESPERAR'

        sorted_df['Accion'] = sorted_df[signal_col].apply(get_action)
        table_cols = [c for c in available_cols + ['Accion'] if c in sorted_df.columns]

        st.caption("Click a row to analyze the stock. Click column headers to sort.")

        event = st.dataframe(
            sorted_df[table_cols],
            use_container_width=True,
            hide_index=True,
            height=520,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                "Empresa": st.column_config.TextColumn("Company", width="medium"),
                "Sector": st.column_config.TextColumn("Sector", width="small"),
                "Precio": st.column_config.TextColumn("Price", width="small"),
                "Score CP": st.column_config.ProgressColumn("ST Score", min_value=0, max_value=100, format="%d"),
                "Score MP": st.column_config.ProgressColumn("MT Score", min_value=0, max_value=100, format="%d"),
                "Score LP": st.column_config.ProgressColumn("LT Score", min_value=0, max_value=100, format="%d"),
                "Señal CP": st.column_config.TextColumn("ST Signal", width="small"),
                "Señal MP": st.column_config.TextColumn("MT Signal", width="small"),
                "Señal LP": st.column_config.TextColumn("LT Signal", width="small"),
                "Accion": st.column_config.TextColumn("Action", width="medium"),
            },
        )

        if event and event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_ticker = sorted_df.iloc[selected_idx]['Ticker']
            navigate_to_stock(selected_ticker)
            st.rerun()

        csv = sorted_df[table_cols].to_csv(index=False)
        st.download_button("Export CSV", data=csv, file_name=f"stocks_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

    # =========================================================================
    # SECTION J: MONETARY PLUMBING
    # =========================================================================
    st.markdown("""<div class="section-header">
        <span class="section-icon">🔧</span>
        <h3>Monetary Plumbing</h3>
        <span class="section-badge">MACRO</span>
    </div>""", unsafe_allow_html=True)

    monetary = get_monetary_data()
    net_liq = monetary.get('net_liquidity', {})
    vol_data = monetary.get('volatility', {})
    credit_data = monetary.get('credit', {})
    japan_data = monetary.get('japan', {})
    regime_mon = monetary.get('regime', {})

    liq_current = net_liq.get('current', 5800) if isinstance(net_liq, dict) else 5800
    liq_change = net_liq.get('change_1m', 0) if isinstance(net_liq, dict) else 0
    vix_val = vol_data.get('vix', 15) if isinstance(vol_data, dict) else 15
    move_val = vol_data.get('move', 90) if isinstance(vol_data, dict) else 90
    spread_val = credit_data.get('ig_spread', 100) if isinstance(credit_data, dict) else 100
    usdjpy_data = japan_data.get('usdjpy', {}) if isinstance(japan_data, dict) else {}
    usdjpy_val = usdjpy_data.get('current', 155) if isinstance(usdjpy_data, dict) else 155

    # Monetary metrics as styled cards
    mon_metrics = [
        ('Net Liquidity', f"&#36;{liq_current/1000:.1f}T", f"{liq_change:+.1f}%", '#3fb950' if liq_change > 0 else '#f85149'),
        ('VIX', f"{vix_val:.1f}", '', '#3fb950' if vix_val < 18 else ('#f85149' if vix_val > 25 else '#d29922')),
        ('MOVE', f"{move_val:.0f}", '', '#3fb950' if move_val < 95 else ('#f85149' if move_val > 120 else '#d29922')),
        ('IG Spread', f"{spread_val:.0f} bps", '', '#3fb950' if spread_val < 100 else '#f85149'),
        ('USD/JPY', f"{usdjpy_val:.1f}", '', '#58a6ff'),
    ]
    mon_html = '<div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px;">'
    for label, value, delta, color in mon_metrics:
        delta_html = f'<div style="font-size:0.7rem; color:{color};">{delta}</div>' if delta else ''
        mon_html += f'''<div style="flex:1; min-width:130px; background:#161b22; border:1px solid #21262d; border-radius:8px; padding:10px 14px; text-align:center;">
            <div style="font-size:0.7rem; color:#6e7681; text-transform:uppercase; letter-spacing:0.5px;">{label}</div>
            <div style="font-size:1.3rem; font-weight:700; color:{color};">{value}</div>
            {delta_html}
        </div>'''
    mon_html += '</div>'
    st.markdown(mon_html, unsafe_allow_html=True)

    # Regime + Traffic Light + Strategy
    regime_name = regime_mon.get('name', 'NEUTRAL') if isinstance(regime_mon, dict) else 'NEUTRAL'
    regime_score_mon = regime_mon.get('score', 50) if isinstance(regime_mon, dict) else 50

    signals_light = {
        'VIX': ('#3fb950', 'OK') if vix_val < 18 else (('#d29922', 'WATCH') if vix_val < 25 else ('#f85149', 'ALERT')),
        'MOVE': ('#3fb950', 'OK') if move_val < 95 else (('#d29922', 'WATCH') if move_val < 120 else ('#f85149', 'ALERT')),
        'Spreads': ('#3fb950', 'OK') if spread_val < 100 else (('#d29922', 'WATCH') if spread_val < 150 else ('#f85149', 'ALERT')),
        'Liquidity': ('#3fb950', 'RISING') if liq_change > 0 else (('#d29922', 'FLAT') if liq_change > -2 else ('#f85149', 'DRAINING')),
        'Yen Carry': ('#3fb950', 'SAFE') if 145 < usdjpy_val < 158 else ('#d29922', 'WATCH'),
    }

    col_regime, col_traffic, col_strat = st.columns(3)
    with col_regime:
        regime_color_mon = '#3fb950' if regime_name == 'ABUNDANT' else ('#f85149' if regime_name == 'SCARCE' else '#d29922')
        st.markdown(f'''<div style="background:#161b22; border:1px solid #21262d; border-radius:8px; padding:14px; text-align:center;">
            <div style="font-size:0.7rem; color:#6e7681; text-transform:uppercase;">Liquidity Regime</div>
            <div style="font-size:1.5rem; font-weight:700; color:{regime_color_mon}; margin:6px 0;">{regime_name}</div>
            <div style="background:#21262d; border-radius:4px; height:6px; overflow:hidden;">
                <div style="background:{regime_color_mon}; height:100%; width:{min(regime_score_mon, 100)}%;"></div>
            </div>
        </div>''', unsafe_allow_html=True)

    with col_traffic:
        traffic_html = '<div style="background:#161b22; border:1px solid #21262d; border-radius:8px; padding:14px;">'
        traffic_html += '<div style="font-size:0.7rem; color:#6e7681; text-transform:uppercase; margin-bottom:8px;">Risk Traffic Light</div>'
        for ind, (color, status) in signals_light.items():
            traffic_html += f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;"><span style="color:#e6edf3; font-size:0.85rem;">{ind}</span><span style="background:{color}22; color:{color}; padding:1px 8px; border-radius:10px; font-size:0.7rem; font-weight:600;">{status}</span></div>'
        traffic_html += '</div>'
        st.markdown(traffic_html, unsafe_allow_html=True)

    with col_strat:
        green_count = sum(1 for _, (c, _) in signals_light.items() if c == '#3fb950')
        if green_count >= 4:
            strat_label, strat_color, strat_text = 'RISK-ON', '#3fb950', 'Growth, small caps, high beta'
        elif green_count >= 2:
            strat_label, strat_color, strat_text = 'NEUTRAL', '#d29922', 'Quality + momentum, tight stops'
        else:
            strat_label, strat_color, strat_text = 'RISK-OFF', '#f85149', 'Cash, defensives, hedges'
        st.markdown(f'''<div style="background:#161b22; border:1px solid #21262d; border-radius:8px; padding:14px; text-align:center;">
            <div style="font-size:0.7rem; color:#6e7681; text-transform:uppercase;">Strategy</div>
            <div style="font-size:1.5rem; font-weight:700; color:{strat_color}; margin:6px 0;">{strat_label}</div>
            <div style="font-size:0.82rem; color:#8b949e;">{strat_text}</div>
        </div>''', unsafe_allow_html=True)

    # Detailed tabs in expander
    with st.expander("Detailed Liquidity / Volatility / Credit / Carry Trade"):
        dtab1, dtab2, dtab3, dtab4 = st.tabs(["Liquidity", "Volatility", "Credit", "Carry Trade"])

        with dtab1:
            st.markdown(f"""
            #### Net Fed Liquidity: &#36;{liq_current/1000:.2f}T ({liq_change:+.1f}% 1M)

            **Formula:** Fed Balance Sheet - TGA - Reverse Repo

            | Level | Interpretation |
            |-------|----------------|
            | >&#36;6T | Abundant - Rally mode |
            | &#36;5-6T | Neutral - Sideways |
            | <&#36;5T | Scarce - Correction |

            **Correlation with SPX:** ~0.85 since 2020
            """)
            if liq_change < 0:
                st.warning("Liquidity FALLING - Headwind for risk assets")
            else:
                st.success("Liquidity RISING - Tailwind for equities")

        with dtab2:
            st.markdown(f"**VIX:** {vix_val:.1f} | **MOVE:** {move_val:.0f}")
            if vix_val < 20 and move_val > 110:
                st.warning("DIVERGENCE: Equity vol low vs bond vol high")

        with dtab3:
            st.markdown(f"""
            #### IG Spread: {spread_val:.0f} bps

            | Level | Meaning |
            |-------|---------|
            | <90 bps | Extreme risk-on |
            | 90-120 bps | Normal |
            | >120 bps | Moderate stress |
            | >160 bps | Credit crisis |
            """)
            if spread_val > 100:
                st.warning(f"IG Spread elevated ({spread_val:.0f} bps) - Reduce high-beta")

        with dtab4:
            st.markdown(f"""
            #### USD/JPY: {usdjpy_val:.1f}

            | Level | Risk |
            |-------|------|
            | >158 | BoJ intervention |
            | 145-158 | Comfort zone |
            | <145 | Unwind risk |
            | <140 | Flash crash risk |
            """)


# =============================================================================
# PAGE 2: STOCK ANALYSIS
# =============================================================================
def show_stock_analysis():
    """Unified stock analysis with score explanation."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import yfinance as yf

    st.markdown('<p class="main-header">📊 Stock Analysis</p>', unsafe_allow_html=True)

    default_ticker = st.session_state.get('selected_ticker', 'NVDA')
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.text_input("Ticker", default_ticker, key="analysis_ticker").upper()
        if ticker != st.session_state.get('selected_ticker'):
            st.session_state.selected_ticker = ticker
    with col2:
        st.write("")

    if not ticker:
        return

    st.markdown("---")

    with st.spinner(f"Cargando {ticker}..."):
        data = get_stock_data(ticker)

    if not data or not isinstance(data, dict):
        st.error(f"Error: No data available for {ticker}")
        return

    if 'error' in data:
        st.error(f"Error: {data['error']}")
        return

    # =========================================================================
    # HEADER: PRICE + SCORES BAR
    # =========================================================================
    price = data.get('price', 0)
    change_pct = data.get('change_pct', 0)
    company_name = data.get('company_name', ticker)
    sector = data.get('sector', 'N/A')
    industry = data.get('industry', 'N/A')
    price_color = "#10B981" if change_pct >= 0 else "#EF4444"
    change_sym = "▲" if change_pct >= 0 else "▼"

    scores_df = get_multi_horizon_scores([ticker])
    if not scores_df.empty:
        row = scores_df.iloc[0]
        score_cp = row.get('Score CP', 0)
        score_mp = row.get('Score MP', 0)
        score_lp = row.get('Score LP', 0)
        signal_cp = row.get('Señal CP', 'N/A')
        signal_mp = row.get('Señal MP', 'N/A')
        signal_lp = row.get('Señal LP', 'N/A')
    else:
        score_cp = score_mp = score_lp = 0
        signal_cp = signal_mp = signal_lp = 'N/A'

    # Header + Score badges
    col_h1, col_h2 = st.columns([3, 2])
    with col_h1:
        st.markdown(f"""
        <div style="background:#161b22; padding:18px; border-radius:10px;">
            <div style="display:flex; align-items:center; gap:15px;">
                <div>
                    <h1 style="margin:0; font-size:2rem;">{ticker}</h1>
                    <p style="margin:3px 0 0 0; color:#888; font-size:0.85rem;">{company_name}</p>
                    <p style="margin:2px 0 0 0; color:#666; font-size:0.75rem;">{sector} · {industry}</p>
                </div>
                <div style="margin-left:auto; text-align:right;">
                    <div style="font-size:2rem; font-weight:bold;">&#36;{price:.2f}</div>
                    <div style="color:{price_color}; font-size:1.1rem;">{change_sym} {abs(change_pct):.2f}%</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    def score_color(s):
        if s >= 60: return '#10B981'
        if s >= 50: return '#3B82F6'
        if s >= 40: return '#F59E0B'
        return '#EF4444'

    with col_h2:
        st.markdown(f"""
        <div style="background:#161b22; padding:12px; border-radius:10px; height:100%;">
            <div style="font-size:0.75rem; color:#888; margin-bottom:8px;">SCORES MULTI-HORIZONTE</div>
            <div style="display:flex; gap:10px;">
                <div style="flex:1; text-align:center; background:#16213e; padding:8px; border-radius:8px;">
                    <div style="font-size:0.65rem; color:#888;">Corto</div>
                    <div style="font-size:1.4rem; font-weight:bold; color:{score_color(score_cp)};">{score_cp:.0f}</div>
                    <div>{render_signal_badge(signal_cp)}</div>
                </div>
                <div style="flex:1; text-align:center; background:#16213e; padding:8px; border-radius:8px;">
                    <div style="font-size:0.65rem; color:#888;">Medio</div>
                    <div style="font-size:1.4rem; font-weight:bold; color:{score_color(score_mp)};">{score_mp:.0f}</div>
                    <div>{render_signal_badge(signal_mp)}</div>
                </div>
                <div style="flex:1; text-align:center; background:#16213e; padding:8px; border-radius:8px;">
                    <div style="font-size:0.65rem; color:#888;">Largo</div>
                    <div style="font-size:1.4rem; font-weight:bold; color:{score_color(score_lp)};">{score_lp:.0f}</div>
                    <div>{render_signal_badge(signal_lp)}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================================
    # SCORE EXPLANATION PANEL - Always visible, prominent
    # =========================================================================
    explanation = get_score_explanation(ticker, skip_congress=True) or {}
    if explanation and 'error' not in explanation:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, rgba(26,26,46,0.95), rgba(22,33,62,0.95));
                    border:1px solid rgba(99,102,241,0.3); border-radius:12px; padding:18px; margin:12px 0;">
            <div style="font-size:0.8rem; text-transform:uppercase; letter-spacing:0.8px; color:#a5b4fc; font-weight:600; margin-bottom:8px;">
                Analisis del Score
            </div>
            <div style="font-size:0.95rem; color:#e2e8f0; line-height:1.5;">{explanation.get('summary', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        for horizon_key, horizon_label, hz_color in [
            ('short_term', 'Corto Plazo', '#3B82F6'),
            ('medium_term', 'Medio Plazo', '#8B5CF6'),
            ('long_term', 'Largo Plazo', '#10B981')
        ]:
            hz_data = explanation.get(horizon_key, {})
            hz_score = hz_data.get('score', 0)
            hz_signal = hz_data.get('signal', 'N/A')
            bull = hz_data.get('bullish_factors', [])
            bear = hz_data.get('bearish_factors', [])

            sc = score_color(hz_score)
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px; margin:10px 0 4px 0;">
                <span style="font-weight:700; color:{hz_color}; font-size:0.9rem;">{horizon_label}</span>
                <span style="font-size:1.3rem; font-weight:800; color:{sc};">{hz_score:.0f}</span>
                <span style="font-size:0.75rem; color:#94a3b8;">{hz_signal}</span>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if bull:
                    bull_html = " ".join([f'<span class="factor-pill-bull">+{f[1]:.0f} {f[0]}</span>' for f in bull])
                    st.markdown(bull_html, unsafe_allow_html=True)
                    for f in bull:
                        st.caption(f"  ↑ {f[0]}: {f[2]}")
                else:
                    st.caption("Sin factores alcistas destacados")
            with c2:
                if bear:
                    bear_html = " ".join([f'<span class="factor-pill-bear">-{f[1]:.0f} {f[0]}</span>' for f in bear])
                    st.markdown(bear_html, unsafe_allow_html=True)
                    for f in bear:
                        st.caption(f"  ↓ {f[0]}: {f[2]}")
                else:
                    st.caption("Sin riesgos destacados")

    # =========================================================================
    # COMPANY OVERVIEW: Business, Cash Flow, Sector Trends
    # =========================================================================
    description = data.get('description', '')
    revenue = data.get('revenue', 0)
    free_cash_flow = data.get('free_cash_flow', 0)
    revenue_growth = data.get('revenue_growth', 0)
    profit_margin = data.get('profit_margin', 0)
    operating_margin = data.get('operating_margin', 0)
    employees = data.get('employees', 0)
    website = data.get('website', '')
    country = data.get('country', 'N/A')

    if description:
        def _fmt_num(n):
            if not n: return 'N/A'
            if abs(n) >= 1e12: return f"&#36;{n/1e12:.1f}T"
            if abs(n) >= 1e9: return f"&#36;{n/1e9:.1f}B"
            if abs(n) >= 1e6: return f"&#36;{n/1e6:.0f}M"
            return f"&#36;{n:,.0f}"

        fcf_color = '#3fb950' if free_cash_flow and free_cash_flow > 0 else '#f85149'
        rev_color = '#3fb950' if revenue_growth >= 0 else '#f85149'
        rev_sign = '+' if revenue_growth >= 0 else ''

        st.markdown(f"""
        <div style="background:#161b22; border:1px solid #21262d; border-radius:10px; padding:18px; margin:12px 0;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                <div style="font-size:0.8rem; text-transform:uppercase; letter-spacing:0.8px; color:#58a6ff; font-weight:600;">
                    Business Overview
                </div>
                <div style="display:flex; gap:8px; font-size:0.7rem;">
                    {'<span style="color:#8b949e;">'+country+'</span>' if country != 'N/A' else ''}
                    {'<span style="color:#6e7681;">·</span><span style="color:#8b949e;">'+f"{employees:,}"+' employees</span>' if employees else ''}
                </div>
            </div>
            <div style="font-size:0.85rem; color:#c9d1d9; line-height:1.65; margin-bottom:16px;">
                {_esc(description)}
            </div>
            <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; border-top:1px solid #21262d; padding-top:14px;">
                <div style="background:#0d1117; padding:10px; border-radius:6px; border:1px solid #21262d;">
                    <div style="font-size:0.65rem; color:#6e7681; text-transform:uppercase;">Revenue</div>
                    <div style="font-size:1.1rem; font-weight:600; color:#e6edf3;">{_fmt_num(revenue)}</div>
                    <div style="font-size:0.7rem; color:{rev_color};">{rev_sign}{revenue_growth:.1f}% YoY</div>
                </div>
                <div style="background:#0d1117; padding:10px; border-radius:6px; border:1px solid #21262d;">
                    <div style="font-size:0.65rem; color:#6e7681; text-transform:uppercase;">Free Cash Flow</div>
                    <div style="font-size:1.1rem; font-weight:600; color:{fcf_color};">{_fmt_num(free_cash_flow)}</div>
                    <div style="font-size:0.7rem; color:#8b949e;">{'Cash machine' if free_cash_flow and free_cash_flow > 1e9 else ('Positive' if free_cash_flow and free_cash_flow > 0 else 'Negative')}</div>
                </div>
                <div style="background:#0d1117; padding:10px; border-radius:6px; border:1px solid #21262d;">
                    <div style="font-size:0.65rem; color:#6e7681; text-transform:uppercase;">Profit Margin</div>
                    <div style="font-size:1.1rem; font-weight:600; color:{'#3fb950' if profit_margin > 15 else ('#d29922' if profit_margin > 5 else '#f85149')};">{profit_margin:.1f}%</div>
                    <div style="font-size:0.7rem; color:#8b949e;">Op: {operating_margin:.1f}%</div>
                </div>
                <div style="background:#0d1117; padding:10px; border-radius:6px; border:1px solid #21262d;">
                    <div style="font-size:0.65rem; color:#6e7681; text-transform:uppercase;">Sector</div>
                    <div style="font-size:0.85rem; font-weight:600; color:#bc8cff;">{_esc(sector)}</div>
                    <div style="font-size:0.7rem; color:#8b949e;">{_esc(industry)}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================================
    # 4 TABS: Technical, Fundamental, Options, Intelligence
    # =========================================================================
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Chart & Tecnicos", "📊 Fundamentales", "🔗 Options & Gamma", "🔍 Intelligence"])

    with tab1:
        _show_technical_tab(ticker, data)

    with tab2:
        _show_fundamental_tab(ticker, data)

    with tab3:
        _show_options_tab(ticker, data)

    with tab4:
        _show_intelligence_tab(ticker, data)


def _show_technical_tab(ticker: str, data: dict):
    """Technical analysis tab."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import yfinance as yf

    # Timeframe selector (period + interval like TradingView)
    col_tf, col_kr = st.columns([2, 1])
    with col_tf:
        # Map: label -> (period, interval)
        # TradingView convention: label = candle size
        timeframes = {
            "5m":  ("5d",  "5m"),     # 5 días de velas de 5 min (intraday)
            "15m": ("10d", "15m"),    # 10 días de velas de 15 min
            "1h":  ("1mo", "1h"),     # 1 mes de velas de 1 hora
            "1D":  ("6mo", "1d"),     # 6 meses de velas diarias
            "1W":  ("2y",  "1wk"),    # 2 años de velas semanales
            "1M":  ("10y", "1mo"),    # 10 años de velas mensuales
        }
        selected_tf = st.radio("Temporalidad", list(timeframes.keys()), index=3, horizontal=True, key="chart_tf")
        chart_period, chart_interval = timeframes[selected_tf]
    with col_kr:
        konkorde_y = st.slider("Rango Y Konkorde", 10, 100, 30, 5)

    # Reload hist for selected period + interval (with retry on rate limit)
    try:
        import time as _time
        stock = yf.Ticker(ticker)
        for _attempt in range(3):
            try:
                hist = stock.history(period=chart_period, interval=chart_interval)
                if not hist.empty:
                    data['history'] = hist
                break
            except Exception as _e:
                if 'too many requests' in str(_e).lower() or '429' in str(_e):
                    _time.sleep(2 * (2 ** _attempt))
                else:
                    break
    except Exception:
        pass

    col_chart, col_indicators = st.columns([2, 1])

    with col_chart:
        hist = data.get('history')
        if hist is not None and not hist.empty:
            import json as _json
            from streamlit_lightweight_charts import renderLightweightCharts

            konkorde = calculate_konkorde(hist)

            # Prepare dataframe for lightweight-charts
            _df = hist.copy()
            _df = _df.reset_index()
            # Handle both 'Date' and 'Datetime' index names
            _time_col = _df.columns[0]
            _df = _df.rename(columns={_time_col: 'time', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})

            # Drop rows with NaN OHLC (critical - lightweight-charts crashes on null)
            _df = _df.dropna(subset=['open', 'high', 'low', 'close'])

            # Format timestamps: lightweight-charts needs epoch seconds (int) for proper handling
            _df['time'] = pd.to_datetime(_df['time']).astype('int64') // 10**9  # Unix epoch seconds

            # SMA + Bollinger Bands
            _df['sma20'] = _df['close'].rolling(20).mean()
            _std20 = _df['close'].rolling(20).std()
            _df['bb_upper'] = _df['sma20'] + 2 * _std20
            _df['bb_lower'] = _df['sma20'] - 2 * _std20

            # Volume colors
            _df['color'] = np.where(_df['close'] >= _df['open'], 'rgba(63,185,80,0.7)', 'rgba(248,81,73,0.7)')

            COLOR_BULL = 'rgba(63,185,80,0.9)'
            COLOR_BEAR = 'rgba(248,81,73,0.9)'

            # Helper: convert df to records, replacing NaN with 0
            def _to_records(df):
                return _json.loads(df.fillna(0).to_json(orient='records'))

            # Convert to JSON records
            _candles = _to_records(_df[['time','open','high','low','close']])

            _sma20_data = _to_records(_df[['time','sma20']].dropna().rename(columns={'sma20':'value'}))
            _bb_upper_data = _to_records(_df[['time','bb_upper']].dropna().rename(columns={'bb_upper':'value'}))
            _bb_lower_data = _to_records(_df[['time','bb_lower']].dropna().rename(columns={'bb_lower':'value'}))

            # Konkorde data - fill NaN with 0 to prevent null crashes
            _k_df = _df[['time']].copy()
            _k_verde_vals = konkorde['verde'].values[:len(_k_df)] if not konkorde['verde'].empty else np.zeros(len(_k_df))
            _k_azul_vals = konkorde['azul'].values[:len(_k_df)] if not konkorde['azul'].empty else np.zeros(len(_k_df))
            _k_marron_vals = konkorde['marron'].values[:len(_k_df)] if not konkorde['marron'].empty else np.zeros(len(_k_df))
            _k_media_vals = konkorde['media'].values[:len(_k_df)] if not konkorde['media'].empty else np.zeros(len(_k_df))

            # Replace NaN in konkorde arrays
            _k_df['verde'] = np.nan_to_num(_k_verde_vals, nan=0.0)
            _k_df['azul'] = np.nan_to_num(_k_azul_vals, nan=0.0)
            _k_df['marron'] = np.nan_to_num(_k_marron_vals, nan=0.0)
            _k_df['media'] = np.nan_to_num(_k_media_vals, nan=0.0)

            # Colors for konkorde histograms
            _k_verde = _k_df[['time','verde']].rename(columns={'verde':'value'}).copy()
            _k_verde['color'] = np.where(_k_verde['value'] >= 0, 'rgba(63,185,80,0.5)', 'rgba(63,185,80,0.2)')
            _k_azul = _k_df[['time','azul']].rename(columns={'azul':'value'}).copy()
            _k_azul['color'] = np.where(_k_azul['value'] >= 0, 'rgba(88,166,255,0.5)', 'rgba(88,166,255,0.2)')
            _k_marron = _to_records(_k_df[['time','marron']].rename(columns={'marron':'value'}))
            _k_media = _to_records(_k_df[['time','media']].rename(columns={'media':'value'}))

            _k_verde_json = _to_records(_k_verde)
            _k_azul_json = _to_records(_k_azul)

            # Volume bar data for volume pane - fill NaN volume with 0
            _vol_bar = _df[['time','volume']].fillna(0).rename(columns={'volume':'value'}).copy()
            _vol_bar['color'] = _df['color']
            _vol_bar_json = _to_records(_vol_bar)

            # Chart layout config (TradingView dark theme)
            _base_layout = {
                "layout": {"background": {"type": "solid", "color": "#0d1117"}, "textColor": "#e6edf3"},
                "grid": {"vertLines": {"color": "#21262d"}, "horzLines": {"color": "#21262d"}},
                "crosshair": {"mode": 0},
                "priceScale": {"borderColor": "#30363d"},
                "timeScale": {"borderColor": "#30363d", "barSpacing": 10},
            }

            # Pane 1: Candlestick + SMA + BB
            _chart_price = {
                **_base_layout,
                "height": 400,
                "watermark": {"visible": True, "fontSize": 48, "horzAlign": "center", "vertAlign": "center",
                              "color": "rgba(88,166,255,0.08)", "text": f"{ticker}"},
            }
            _series_price = [
                {"type": "Candlestick", "data": _candles, "options": {
                    "upColor": COLOR_BULL, "downColor": COLOR_BEAR,
                    "borderVisible": False, "wickUpColor": COLOR_BULL, "wickDownColor": COLOR_BEAR
                }},
                {"type": "Line", "data": _sma20_data, "options": {"color": "#d29922", "lineWidth": 1, "title": "SMA20"}},
                {"type": "Line", "data": _bb_upper_data, "options": {"color": "rgba(139,148,158,0.5)", "lineWidth": 1, "lineStyle": 2}},
                {"type": "Line", "data": _bb_lower_data, "options": {"color": "rgba(139,148,158,0.5)", "lineWidth": 1, "lineStyle": 2}},
            ]

            # Pane 2: Konkorde
            _chart_konkorde = {
                "height": 200,
                "layout": {"background": {"type": "solid", "color": "#0d1117"}, "textColor": "#e6edf3"},
                "grid": {"vertLines": {"color": "rgba(33,38,45,0)"}, "horzLines": {"color": "#21262d"}},
                "timeScale": {"visible": False},
                "watermark": {"visible": True, "fontSize": 18, "horzAlign": "left", "vertAlign": "top",
                              "color": "rgba(88,166,255,0.4)", "text": "Konkorde 2.0"},
            }
            _series_konkorde = [
                {"type": "Histogram", "data": _k_verde_json, "options": {"priceScaleId": "konkorde", "title": "Retail"}},
                {"type": "Histogram", "data": _k_azul_json, "options": {"priceScaleId": "konkorde", "title": "Institucional"}},
                {"type": "Line", "data": _k_marron, "options": {"color": "#f0883e", "lineWidth": 2, "priceScaleId": "konkorde", "title": "Tendencia"}},
                {"type": "Line", "data": _k_media, "options": {"color": "#ffffff", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "konkorde", "title": "Media"}},
            ]

            # Pane 3: Volume
            _chart_volume = {
                "height": 120,
                "layout": {"background": {"type": "solid", "color": "#0d1117"}, "textColor": "#e6edf3"},
                "grid": {"vertLines": {"color": "rgba(33,38,45,0)"}, "horzLines": {"color": "#21262d"}},
                "timeScale": {"visible": True, "borderColor": "#30363d"},
                "watermark": {"visible": True, "fontSize": 18, "horzAlign": "left", "vertAlign": "top",
                              "color": "rgba(88,166,255,0.4)", "text": "Volumen"},
            }
            _series_volume = [
                {"type": "Histogram", "data": _vol_bar_json, "options": {
                    "priceFormat": {"type": "volume"}, "priceScaleId": ""
                }, "priceScale": {"scaleMargins": {"top": 0, "bottom": 0}, "alignLabels": False}},
            ]

            # Render multi-pane chart
            renderLightweightCharts([
                {"chart": _chart_price, "series": _series_price},
                {"chart": _chart_konkorde, "series": _series_konkorde},
                {"chart": _chart_volume, "series": _series_volume},
            ], key=f"lwc_{ticker}_{selected_tf}")

            # Konkorde interpretation
            if not konkorde['azul'].empty:
                la = konkorde['azul'].iloc[-1]
                lv = konkorde['verde'].iloc[-1]
                if la > 0 and lv > 0:
                    st.success("**Konkorde:** Institucionales Y retail comprando - Tendencia alcista fuerte")
                elif la > 0 and lv < 0:
                    st.info("**Konkorde:** Institucionales acumulando, retail vendiendo - Posible suelo")
                elif la < 0 and lv > 0:
                    st.warning("**Konkorde:** Institucionales distribuyendo, retail comprando - Precaucion")
                else:
                    st.error("**Konkorde:** Ambos vendiendo - Tendencia bajista")

    with col_indicators:
        st.markdown("### Indicadores Clave")
        rsi = data['rsi']
        rsi_color = "🟢" if rsi < 30 else ("🔴" if rsi > 70 else "🟡")
        rsi_signal = "Sobreventa" if rsi < 30 else ("Sobrecompra" if rsi > 70 else "Neutral")
        st.metric("RSI (14)", f"{rsi:.1f} {rsi_color}", rsi_signal)

        macd_emoji = "🟢" if data['macd_bullish'] else "🔴"
        st.metric("MACD", f"{data['macd_signal']} {macd_emoji}")

        vwap = data['vwap']
        above_vwap = data['price'] > vwap if vwap > 0 else False
        st.metric("VWAP", f"${vwap:.2f}", "Por encima" if above_vwap else "Por debajo")

        vol_ratio = data['volume_ratio']
        vol_sig = "Alto" if vol_ratio > 1.5 else ("Bajo" if vol_ratio < 0.7 else "Normal")
        st.metric("Vol vs Media", f"{vol_ratio:.1f}x", vol_sig)

        st.markdown("---")
        st.metric("Mom 1M", f"{data['momentum_1m']:+.1f}%")
        st.metric("Mom 3M", f"{data['momentum_3m']:+.1f}%")

    # Technical bias summary
    bull_sig = sum([data['rsi'] < 40, data['macd_bullish'], data['momentum_1m'] > 0])
    bear_sig = sum([data['rsi'] > 60, not data['macd_bullish'], data['momentum_1m'] < 0])
    if bull_sig > bear_sig:
        st.success(f"**Sesgo Tecnico: ALCISTA** ({bull_sig}/3 positivas) | RSI: {data['rsi']:.1f} | MACD: {data['macd_signal']} | Mom: {data['momentum_1m']:+.1f}%")
    elif bear_sig > bull_sig:
        st.error(f"**Sesgo Tecnico: BAJISTA** ({bear_sig}/3 negativas) | RSI: {data['rsi']:.1f} | MACD: {data['macd_signal']} | Mom: {data['momentum_1m']:+.1f}%")
    else:
        st.warning(f"**Sesgo Tecnico: NEUTRAL** | RSI: {data['rsi']:.1f} | MACD: {data['macd_signal']} | Mom: {data['momentum_1m']:+.1f}%")


def _show_options_tab(ticker: str, data: dict):
    """Options & Gamma Analysis — MenthorQ-style GEX with horizontal bars, profile lines, and plain-language interpretation."""
    import yfinance as yf
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from datetime import datetime, timedelta
    import numpy as np
    import pandas as pd

    price = data.get('price', 0) or 0
    if price == 0:
        st.warning("Precio no disponible.")
        return

    st.markdown("### Options & Gamma Analysis")

    # Fetch options data (with retry on rate limit)
    import time as _time
    stock = yf.Ticker(ticker)
    expirations = None
    for _attempt in range(3):
        try:
            expirations = stock.options
            break
        except Exception as e:
            if 'too many requests' in str(e).lower() or '429' in str(e):
                _time.sleep(2 * (2 ** _attempt))
            else:
                st.error(f"Error obteniendo opciones: {e}")
                return
    if expirations is None:
        st.error("Rate limited por yfinance. Espera unos segundos y recarga.")
        return

    if not expirations:
        st.warning(f"No hay datos de opciones para {ticker}")
        return

    # Controls row
    col_exp, col_multi, col_info = st.columns([2, 1, 3])
    with col_exp:
        selected_exp = st.selectbox("Expiracion", expirations[:12], key=f"opt_exp_{ticker}")
    with col_multi:
        multi_exp = st.checkbox("Multi-Exp GEX", value=True, key=f"multi_gex_{ticker}",
                                help="Aggregate gamma across nearest 4 expirations for stronger signal")

    try:
        chain = stock.option_chain(selected_exp)
        calls = chain.calls.copy()
        puts = chain.puts.copy()
    except Exception as e:
        st.error(f"Error: {e}")
        return

    if calls.empty and puts.empty:
        st.warning("No hay datos de opciones para esta expiracion.")
        return

    # Clean NaN in openInterest/volume globally
    for df in [calls, puts]:
        for col in ['openInterest', 'volume']:
            if col in df.columns:
                df[col] = df[col].fillna(0).astype(float)
            else:
                df[col] = 0.0

    exp_date = datetime.strptime(selected_exp, '%Y-%m-%d')
    dte = max((exp_date - datetime.now()).days, 1)
    total_call_oi = int(calls['openInterest'].sum())
    total_put_oi = int(puts['openInterest'].sum())
    total_oi = total_call_oi + total_put_oi

    with col_info:
        st.markdown(f"""
        <div style="background:#161b22; padding:10px 14px; border-radius:8px; margin-top:24px;">
            <span style="color:#8b949e; font-size:0.8rem;">DTE: </span>
            <span style="color:#e6edf3; font-weight:700;">{dte}d</span>
            <span style="color:#8b949e; font-size:0.8rem; margin-left:12px;">OI: </span>
            <span style="color:#e6edf3;">{total_oi:,} ({total_call_oi:,}C / {total_put_oi:,}P)</span>
            <span style="color:#8b949e; font-size:0.8rem; margin-left:12px;">Spot: </span>
            <span style="color:#d29922; font-weight:600;">&#36;{price:.2f}</span>
        </div>""", unsafe_allow_html=True)

    # =====================================================================
    # COMPUTE IV METRICS
    # =====================================================================
    atm_range = (price * 0.95, price * 1.05)
    atm_calls = calls[(calls['strike'] >= atm_range[0]) & (calls['strike'] <= atm_range[1])]
    atm_puts = puts[(puts['strike'] >= atm_range[0]) & (puts['strike'] <= atm_range[1])]
    atm_call_iv = float(atm_calls['impliedVolatility'].mean() * 100) if not atm_calls.empty else 0
    atm_put_iv = float(atm_puts['impliedVolatility'].mean() * 100) if not atm_puts.empty else 0
    avg_iv = (atm_call_iv + atm_put_iv) / 2 if atm_call_iv > 0 and atm_put_iv > 0 else max(atm_call_iv, atm_put_iv)

    total_call_vol = int(calls['volume'].sum())
    total_put_vol = int(puts['volume'].sum())
    pc_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
    pc_ratio_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0

    # Expected move from ATM straddle
    atm_strike_idx = (calls['strike'] - price).abs().idxmin() if not calls.empty else None
    expected_move_pct = 0
    straddle_price = 0
    if atm_strike_idx is not None:
        atm_call_price = float(calls.loc[atm_strike_idx, 'lastPrice']) if 'lastPrice' in calls.columns else 0
        atm_strike_val = float(calls.loc[atm_strike_idx, 'strike'])
        atm_put_row = puts[puts['strike'] == atm_strike_val]
        atm_put_price = float(atm_put_row['lastPrice'].iloc[0]) if not atm_put_row.empty else 0
        straddle_price = atm_call_price + atm_put_price
        expected_move_pct = (straddle_price / price * 100) if price > 0 else 0

    # Skew
    otm_puts = puts[puts['strike'] < price * 0.95]
    otm_calls = calls[calls['strike'] > price * 1.05]
    put_iv_avg = float(otm_puts['impliedVolatility'].mean() * 100) if not otm_puts.empty else 0
    call_iv_avg = float(otm_calls['impliedVolatility'].mean() * 100) if not otm_calls.empty else 0
    skew = put_iv_avg - call_iv_avg

    # Metric cards
    iv_color = '#f85149' if avg_iv > 60 else ('#f0883e' if avg_iv > 40 else ('#d29922' if avg_iv > 25 else '#3fb950'))
    pc_color = '#f85149' if pc_ratio_oi > 1.2 else ('#3fb950' if pc_ratio_oi < 0.7 else '#d29922')
    skew_color = '#f85149' if skew > 15 else ('#d29922' if skew > 5 else '#3fb950')

    def _opt_card(label, value, color, sublabel=""):
        return f'''<div style="background:#161b22; padding:10px; border-radius:8px; text-align:center; border-top:2px solid {color};">
            <div style="font-size:0.65rem; color:#6e7681; text-transform:uppercase;">{label}</div>
            <div style="font-size:1.3rem; font-weight:700; color:{color};">{value}</div>
            <div style="font-size:0.65rem; color:#8b949e;">{sublabel}</div>
        </div>'''

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(_opt_card("ATM IV", f"{avg_iv:.0f}%", iv_color, f"Call: {atm_call_iv:.0f}% | Put: {atm_put_iv:.0f}%"), unsafe_allow_html=True)
    with c2:
        st.markdown(_opt_card("Expected Move", f"±{expected_move_pct:.1f}%", '#58a6ff', f"Straddle: &#36;{straddle_price:.2f}"), unsafe_allow_html=True)
    with c3:
        pc_label = "BEARISH" if pc_ratio_oi > 1.0 else "BULLISH"
        st.markdown(_opt_card("Put/Call OI", f"{pc_ratio_oi:.2f}", pc_color, f"{pc_label} | Vol: {pc_ratio_vol:.2f}"), unsafe_allow_html=True)
    with c4:
        skew_label = "FEAR" if skew > 10 else ("NEUTRAL" if skew > 0 else "GREED")
        st.markdown(_opt_card("Skew", f"{skew:+.1f}pp", skew_color, f"Put-Call IV gap ({skew_label})"), unsafe_allow_html=True)
    with c5:
        st.markdown(_opt_card("Total OI", f"{total_oi:,}", '#58a6ff', f"Calls: {total_call_oi:,} | Puts: {total_put_oi:,}"), unsafe_allow_html=True)

    # =====================================================================
    # ADVANCED SKEW ANALYSIS - 25-Delta Risk Reversal
    # =====================================================================
    st.markdown("---")
    st.markdown("### 📊 Advanced SKEW Analysis (25Δ Risk Reversal)")

    try:
        from webapp.data.providers import (
            calculate_25d_risk_reversal,
            track_skew_history,
            get_skew_percentile
        )

        # Calculate 25D Risk Reversal
        rr_data = calculate_25d_risk_reversal(calls, puts, price, dte)

        if rr_data['rr_25d'] != 0:
            # Track history
            track_skew_history(ticker, rr_data['rr_25d'], price)

            # Get percentile stats
            percentile_data = get_skew_percentile(ticker, rr_data['rr_25d'])

            # Color coding based on percentile
            if percentile_data['percentile'] >= 90:
                skew_status_color = '#f85149'  # Red - Extreme
                skew_icon = '🔴'
            elif percentile_data['percentile'] >= 75:
                skew_status_color = '#f0883e'  # Orange - Elevated
                skew_icon = '🟠'
            elif percentile_data['percentile'] >= 25:
                skew_status_color = '#d29922'  # Yellow - Normal
                skew_icon = '🟡'
            else:
                skew_status_color = '#3fb950'  # Green - Low
                skew_icon = '🟢'

            # Bias color (independent of percentile)
            bias_color = '#f85149' if rr_data['rr_25d'] > 10 else ('#f0883e' if rr_data['rr_25d'] > 5 else '#3fb950')

            # Main SKEW card
            trading_impl = ''
            if percentile_data['percentile'] >= 75:
                trading_impl = '<strong style="color: #f85149;">High SKEW = Expensive Puts</strong><br>• Consider selling put spreads to capture inflated premium<br>• Reduce long exposure or tighten stops<br>• Monitor for divergence resolution (price drop or hedge unwind)'
            elif percentile_data['percentile'] >= 25:
                trading_impl = 'SKEW in normal range - standard options pricing.'
            else:
                trading_impl = '<strong style="color: #3fb950;">Low SKEW = Cheap Protection</strong><br>• Consider buying puts for portfolio insurance<br>• Long premium strategies may be favorable<br>• Market complacency - good time to hedge'

            skew_card_html = f"""<div style="background: linear-gradient(135deg, #161b22 0%, #0d1117 100%); border: 2px solid {skew_status_color}; border-radius: 12px; padding: 20px; margin: 16px 0;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
<div>
<span style="font-size: 0.75rem; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px;">25-Delta Risk Reversal</span>
<div style="font-size: 2.5rem; font-weight: 700; color: {bias_color}; margin-top: 4px;">{rr_data['rr_25d']:+.2f}<span style="font-size: 1.5rem;">pp</span></div>
</div>
<div style="text-align: right;">
<div style="font-size: 3rem; line-height: 1;">{skew_icon}</div>
<div style="font-size: 0.8rem; color: {skew_status_color}; font-weight: 600; margin-top: 4px;">{percentile_data['status']}</div>
</div>
</div>
<div style="margin: 16px 0;">
<div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
<span style="font-size: 0.7rem; color: #8b949e;">Percentile (last 90 days)</span>
<span style="font-size: 0.8rem; color: #e6edf3; font-weight: 600;">{percentile_data['percentile']:.1f}%</span>
</div>
<div style="background: #21262d; border-radius: 10px; height: 20px; overflow: hidden; position: relative;">
<div style="background: linear-gradient(90deg, #3fb950 0%, #d29922 50%, #f0883e 75%, #f85149 90%); width: {percentile_data['percentile']}%; height: 100%; border-radius: 10px; transition: width 0.3s ease;"></div>
<div style="position: absolute; left: 25%; top: 0; width: 1px; height: 100%; background: #30363d;"></div>
<div style="position: absolute; left: 50%; top: 0; width: 1px; height: 100%; background: #30363d;"></div>
<div style="position: absolute; left: 75%; top: 0; width: 1px; height: 100%; background: #30363d;"></div>
<div style="position: absolute; left: 90%; top: 0; width: 2px; height: 100%; background: #f85149;"></div>
</div>
<div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.65rem; color: #6e7681;">
<span>0</span><span>25</span><span>50</span><span>75</span><span style="color: #f85149;">90</span><span>100</span>
</div>
</div>
<div style="background: rgba(88, 166, 255, 0.1); border-left: 3px solid #58a6ff; padding: 12px; border-radius: 4px; margin: 16px 0;">
<div style="font-size: 0.75rem; color: #58a6ff; font-weight: 600; margin-bottom: 4px;">INTERPRETATION</div>
<div style="font-size: 0.85rem; color: #e6edf3; line-height: 1.5;">{rr_data['interpretation']}</div>
</div>
<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px;">
<div style="background: #0d1117; padding: 10px; border-radius: 6px; border: 1px solid #21262d;">
<div style="font-size: 0.65rem; color: #6e7681; text-transform: uppercase;">Current</div>
<div style="font-size: 1.1rem; font-weight: 600; color: {bias_color};">{percentile_data['current']:+.2f}pp</div>
</div>
<div style="background: #0d1117; padding: 10px; border-radius: 6px; border: 1px solid #21262d;">
<div style="font-size: 0.65rem; color: #6e7681; text-transform: uppercase;">30D Avg</div>
<div style="font-size: 1.1rem; font-weight: 600; color: #8b949e;">{percentile_data['avg_30d']:+.2f}pp</div>
</div>
<div style="background: #0d1117; padding: 10px; border-radius: 6px; border: 1px solid #21262d;">
<div style="font-size: 0.65rem; color: #6e7681; text-transform: uppercase;">90D Range</div>
<div style="font-size: 1.1rem; font-weight: 600; color: #8b949e;">{percentile_data['min_90d']:.1f} to {percentile_data['max_90d']:.1f}</div>
</div>
</div>
<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #21262d;">
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 0.75rem;">
<div>
<span style="color: #6e7681;">25&#916; Put Strike:</span>
<span style="color: #f85149; font-weight: 600; margin-left: 8px;">&#36;{rr_data['put_25d_strike']:.2f}</span>
<span style="color: #8b949e; margin-left: 8px;">(IV: {rr_data['put_25d_iv']:.1f}%)</span>
</div>
<div>
<span style="color: #6e7681;">25&#916; Call Strike:</span>
<span style="color: #3fb950; font-weight: 600; margin-left: 8px;">&#36;{rr_data['call_25d_strike']:.2f}</span>
<span style="color: #8b949e; margin-left: 8px;">(IV: {rr_data['call_25d_iv']:.1f}%)</span>
</div>
</div>
</div>
<div style="margin-top: 16px; padding: 12px; background: rgba(139, 148, 158, 0.1); border-radius: 6px;">
<div style="font-size: 0.7rem; color: #8b949e; text-transform: uppercase; margin-bottom: 6px;">Trading Implications</div>
<div style="font-size: 0.8rem; color: #e6edf3; line-height: 1.6;">{trading_impl}</div>
</div>
</div>"""
            st.markdown(skew_card_html, unsafe_allow_html=True)

        else:
            st.info("📊 Unable to calculate 25Δ Risk Reversal - insufficient options data with valid IVs")

    except ImportError:
        # Fallback to basic skew if advanced functions not available
        st.info("📊 Advanced SKEW analysis requires scipy. Showing basic skew above.")
    except Exception as e:
        st.warning(f"⚠️ Could not calculate advanced SKEW: {str(e)}")

    # =====================================================================
    # STRATEGY RECOMMENDER
    # =====================================================================
    st.markdown("---")
    st.markdown("### 🎯 Options Strategy Recommendation")

    try:
        from webapp.data.providers import recommend_options_strategy

        # Use pc_ratio_oi as the primary put/call ratio
        pc_ratio = pc_ratio_oi if 'pc_ratio_oi' in dir() else 0

        # Get GEX context
        rec_skew = rr_data['rr_25d'] if 'rr_data' in locals() and rr_data else skew
        rec_regime = regime if '_gex_computed' in locals() and _gex_computed else 'N/A'
        rec_net_gex = total_net_gex if '_gex_computed' in locals() and _gex_computed else 0
        rec_call_wall = call_wall if '_gex_computed' in locals() and _gex_computed else 0
        rec_put_wall = put_wall if '_gex_computed' in locals() and _gex_computed else 0

        # Pass actual chain data for real strike selection
        rec_calls = calls if 'calls' in locals() else None
        rec_puts = puts if 'puts' in locals() else None

        strategy = recommend_options_strategy(
            price=price, skew=rec_skew, gamma_regime=rec_regime,
            avg_iv=avg_iv, pc_ratio=pc_ratio, dte=dte,
            calls_df=rec_calls, puts_df=rec_puts,
            net_gex_value=rec_net_gex,
            call_wall=rec_call_wall, put_wall=rec_put_wall
        )

        # Display card - split into smaller st.markdown calls to avoid Streamlit HTML parsing issues
        risk_color = '#3fb950' if strategy['risk_level'] == 'low' else ('#d29922' if strategy['risk_level'] == 'medium' else '#f85149')

        # Header section
        st.markdown(f'<div style="background: linear-gradient(135deg, #161b22 0%, #0d1117 100%); border: 2px solid {risk_color}; border-radius: 12px 12px 0 0; padding: 20px 20px 10px 20px; margin-top: 16px;"><div style="display: flex; justify-content: space-between; align-items: start;"><div><div style="font-size: 0.7rem; color: #6e7681; text-transform: uppercase;">Recommended Strategy for {ticker} @ &#36;{price:.2f}</div><div style="font-size: 1.8rem; font-weight: 700; color: #58a6ff; margin-top: 4px;">{strategy["name"]}</div><div style="font-size: 0.8rem; color: #8b949e; margin-top: 4px; font-style: italic;">{strategy["description"]}</div></div><div style="background: {risk_color}; color: #0d1117; padding: 6px 12px; border-radius: 6px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">{strategy.get("risk_level", "MEDIUM")} RISK</div></div><div style="display: inline-block; background: rgba(88, 166, 255, 0.2); color: #58a6ff; padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-top: 10px;">Market Bias: {strategy["market_bias"].upper()}</div></div>', unsafe_allow_html=True)

        # Warning (if any)
        if 'warning' in strategy:
            st.markdown(f'<div style="background: rgba(248, 81, 73, 0.15); border-left: 3px solid #f85149; padding: 10px; margin: 0 20px; border-radius: 4px;"><div style="font-size: 0.8rem; color: #f85149; font-weight: 600;">{strategy.get("warning", "")}</div></div>', unsafe_allow_html=True)

        # Strikes with real chain details
        strike_details = strategy.get('strike_details', {})
        strikes_html = ''
        for k, v in strategy['strikes'].items():
            if not isinstance(v, (int, float)):
                continue
            label = k.replace("_", " ").title()
            detail = strike_details.get(k, '')
            detail_html = f'<span style="color:#6e7681; font-size:0.65rem; margin-left:8px;">{detail}</span>' if detail else ''
            strikes_html += f'<div style="margin:4px 0;"><span style="color:#8b949e;">{label}:</span> <span style="color:#58a6ff; font-weight:600;">&#36;{v:.2f}</span>{detail_html}</div>'
        st.markdown(f'<div style="background:#0d1117; border:1px solid #21262d; border-radius:8px; padding:14px; margin:8px 0;"><div style="font-size:0.75rem; color:#e6edf3; font-weight:600; margin-bottom:8px;">Strikes &amp; Mechanics</div>{strikes_html}</div>', unsafe_allow_html=True)

        # GEX context note
        gex_note = strategy.get('gex_note', '')
        if gex_note:
            st.markdown(f'<div style="padding:8px 12px; background:rgba(210,153,34,0.1); border-left:3px solid #d29922; border-radius:4px; margin-bottom:8px;"><div style="font-size:0.7rem; color:#d29922; font-weight:600;">GEX Context</div><div style="font-size:0.75rem; color:#e6edf3; margin-top:4px;">{gex_note}</div></div>', unsafe_allow_html=True)

        # Greeks Impact
        st.markdown(f'<div style="padding:10px; background:rgba(188,140,255,0.1); border-left:3px solid #bc8cff; border-radius:4px; margin-bottom:8px;"><div style="font-size:0.7rem; color:#bc8cff; font-weight:600;">Greeks Impact</div><div style="font-size:0.75rem; color:#e6edf3; margin-top:4px;">{strategy["greeks_impact"]}</div></div>', unsafe_allow_html=True)

        # Pros and Cons as two columns
        col_pros, col_cons = st.columns(2)
        with col_pros:
            pros_items = ''.join([f'<div style="color: #3fb950; font-size: 0.75rem; margin: 3px 0;">+ {p}</div>' for p in strategy.get('pros', [])])
            st.markdown(f'<div style="font-size: 0.75rem; color: #3fb950; font-weight: 600; margin-bottom: 4px;">Pros</div>{pros_items}', unsafe_allow_html=True)
        with col_cons:
            cons_items = ''.join([f'<div style="color: #f85149; font-size: 0.75rem; margin: 3px 0;">- {c}</div>' for c in strategy.get('cons', [])])
            st.markdown(f'<div style="font-size: 0.75rem; color: #f85149; font-weight: 600; margin-bottom: 4px;">Cons</div>{cons_items}', unsafe_allow_html=True)

        # Bias score indicator
        bs = strategy.get('bias_score', 0)
        bs_label = 'BULLISH' if bs >= 2 else ('BEARISH' if bs <= -2 else 'NEUTRAL')
        bs_color = '#3fb950' if bs >= 2 else ('#f85149' if bs <= -2 else '#d29922')
        bias_bar = f'<span style="color:{bs_color}; font-weight:700;">{bs_label} ({bs:+d})</span> = P/C + SKEW + GEX composite'

        # Context footer
        st.markdown(f'<div style="padding:8px 12px; border-top:1px solid #21262d; font-size:0.7rem; color:#6e7681; background:#161b22; border-radius:0 0 12px 12px; margin-bottom:16px;"><strong>Bias:</strong> {bias_bar}<br><strong>Context:</strong> SKEW {strategy["context"]["skew"]} | IV {strategy["context"]["avg_iv"]} | {strategy["context"]["gamma_regime"]} | P/C {strategy["context"]["pc_ratio"]} | DTE {strategy["context"]["dte"]}d</div>', unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"⚠️ Could not generate strategy: {str(e)}")

    # =====================================================================
    # SKEW HISTORICAL CHART
    # =====================================================================
    st.markdown("---")
    st.markdown("### 📈 SKEW Historical Timeline (MenthorQ Style)")

    try:
        from webapp.data.providers import create_skew_historical_chart

        skew_chart = create_skew_historical_chart(ticker)

        if skew_chart:
            st.plotly_chart(skew_chart, use_container_width=True, key=f"skew_hist_{ticker}")
            st.markdown("""
            <div style="font-size: 0.7rem; color: #6e7681; padding: 10px; background: #161b22; border-radius: 6px; margin-top: 8px;">
                <strong>📊 How to Read:</strong><br>
                • <strong>Top Panel:</strong> Price candlesticks<br>
                • <strong>Bottom Panel:</strong> 25Δ Risk Reversal timeline<br>
                • <span style="color: #f85149;">Red zone (PUT BIAS)</span>: SKEW above avg → Institutions hedging<br>
                • <span style="color: #3fb950;">Green zone (CALL BIAS)</span>: SKEW below avg → Lower fear<br>
                • <span style="color: #ffffff;">White line</span>: Current 25D RR<br>
                • <span style="color: #d29922;">Yellow line</span>: 30-day average<br>
                <br>
                <strong>Divergence Alert:</strong> If price ↑ but SKEW ↑ = Institutions buying protection despite rally = Caution!
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("📊 SKEW chart requires ≥2 days of data. Check back tomorrow!")

    except Exception as e:
        st.warning(f"⚠️ Could not create SKEW chart: {str(e)}")

    # =====================================================================
    # CHECK MINIMUM OI FOR GEX ANALYSIS
    # =====================================================================
    MIN_OI_FOR_GEX = 100  # Need at least 100 total OI for meaningful GEX
    if total_oi < MIN_OI_FOR_GEX:
        st.markdown(f"""<div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:20px; margin:16px 0; text-align:center;">
            <div style="font-size:1.1rem; color:#d29922; font-weight:600;">Insufficient Options Data for GEX Analysis</div>
            <div style="color:#8b949e; margin-top:8px; font-size:0.8rem;">
                Total OI = {total_oi:,} (minimum {MIN_OI_FOR_GEX:,} needed). This ticker has very low options activity.<br>
                Try a more liquid ticker (e.g. SPY, AAPL, NVDA, TSLA, QQQ, MSFT, META, AMZN) or a further expiration date.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    st.markdown("---")

    # =====================================================================
    # COMPUTE GEX — Multi-expiration aggregated
    # =====================================================================
    strike_range = (price * 0.85, price * 1.15)
    calls_f = calls[(calls['strike'] >= strike_range[0]) & (calls['strike'] <= strike_range[1])].copy()
    puts_f = puts[(puts['strike'] >= strike_range[0]) & (puts['strike'] <= strike_range[1])].copy()

    exps_to_use = expirations[:4] if multi_exp else [selected_exp]
    gex_data = []
    call_gex_data = []
    put_gex_data = []

    for exp_i in exps_to_use:
        try:
            if exp_i == selected_exp:
                c_df, p_df = calls_f, puts_f
            else:
                ch = stock.option_chain(exp_i)
                c_df = ch.calls[(ch.calls['strike'] >= strike_range[0]) & (ch.calls['strike'] <= strike_range[1])].copy()
                p_df = ch.puts[(ch.puts['strike'] >= strike_range[0]) & (ch.puts['strike'] <= strike_range[1])].copy()
                for df_ in [c_df, p_df]:
                    if 'openInterest' in df_.columns:
                        df_['openInterest'] = df_['openInterest'].fillna(0).astype(float)
                    else:
                        df_['openInterest'] = 0.0

            exp_date_i = datetime.strptime(exp_i, '%Y-%m-%d')
            dte_i = max((exp_date_i - datetime.now()).days, 1)
            dte_weight = 1.0 / (dte_i ** 0.5)

            # Sigma based on IV + DTE for gaussian width
            avg_iv_dec = max(avg_iv / 100, 0.15)
            sigma_pct = max(avg_iv_dec * (dte_i / 365) ** 0.5, 0.02)

            for _, row in c_df.iterrows():
                strike = row['strike']
                oi = float(row.get('openInterest', 0) or 0)
                if oi > 0:
                    moneyness = (strike - price) / price
                    gamma_proxy = np.exp(-0.5 * (moneyness / sigma_pct) ** 2)
                    gex = oi * gamma_proxy * 100 * dte_weight
                    gex_data.append({'strike': strike, 'gex': gex})
                    call_gex_data.append({'strike': strike, 'gex': gex})
            for _, row in p_df.iterrows():
                strike = row['strike']
                oi = float(row.get('openInterest', 0) or 0)
                if oi > 0:
                    moneyness = (strike - price) / price
                    gamma_proxy = np.exp(-0.5 * (moneyness / sigma_pct) ** 2)
                    gex = -oi * gamma_proxy * 100 * dte_weight
                    gex_data.append({'strike': strike, 'gex': gex})
                    put_gex_data.append({'strike': strike, 'gex': abs(gex)})
        except Exception:
            continue

    # =====================================================================
    # COMPUTE KEY GAMMA LEVELS
    # =====================================================================
    gamma_wall = call_wall = put_wall = hvl = price
    max_pain_strike = price
    total_net_gex = 0
    _gex_computed = False
    regime = "N/A"
    regime_detail = ""
    regime_color = '#8b949e'

    if gex_data:
        gex_df = pd.DataFrame(gex_data)
        net_gex = gex_df.groupby('strike')['gex'].sum().reset_index().sort_values('strike')

        call_gex_agg = pd.DataFrame(call_gex_data).groupby('strike')['gex'].sum().reset_index() if call_gex_data else pd.DataFrame({'strike': [price], 'gex': [0]})
        put_gex_agg = pd.DataFrame(put_gex_data).groupby('strike')['gex'].sum().reset_index() if put_gex_data else pd.DataFrame({'strike': [price], 'gex': [0]})

        # Call Wall = highest call gamma strike ABOVE current price (resistance)
        calls_above = call_gex_agg[call_gex_agg['strike'] >= price]
        if not calls_above.empty:
            call_wall = float(calls_above.loc[calls_above['gex'].idxmax(), 'strike'])
        else:
            call_wall = float(call_gex_agg.loc[call_gex_agg['gex'].idxmax(), 'strike'])
        # Put Wall = highest put gamma strike BELOW current price (support)
        puts_below = put_gex_agg[put_gex_agg['strike'] <= price]
        if not puts_below.empty:
            put_wall = float(puts_below.loc[puts_below['gex'].idxmax(), 'strike'])
        else:
            put_wall = float(put_gex_agg.loc[put_gex_agg['gex'].idxmax(), 'strike'])
        # Gamma Wall = highest absolute net gamma
        net_gex['abs_gex'] = net_gex['gex'].abs()
        gamma_wall = float(net_gex.loc[net_gex['abs_gex'].idxmax(), 'strike'])

        # HVL: zero-cross of net GEX nearest to spot
        hvl = price
        min_hvl_dist = float('inf')
        sg = net_gex.reset_index(drop=True)
        for i in range(len(sg) - 1):
            g1, g2 = sg.iloc[i]['gex'], sg.iloc[i + 1]['gex']
            s1, s2 = sg.iloc[i]['strike'], sg.iloc[i + 1]['strike']
            if g1 * g2 < 0:
                cross = s1 + (s2 - s1) * abs(g1) / (abs(g1) + abs(g2))
                dist = abs(cross - price)
                if dist < min_hvl_dist:
                    min_hvl_dist = dist
                    hvl = cross

        total_net_gex = net_gex['gex'].sum()

        # Max pain
        all_strikes = sorted(set(calls_f['strike'].tolist() + puts_f['strike'].tolist()))
        if all_strikes:
            min_pain = float('inf')
            for s in all_strikes:
                cp = calls_f[calls_f['strike'] < s]
                pp = puts_f[puts_f['strike'] > s]
                pain = 0
                if len(cp) > 0:
                    pain += (cp['openInterest'] * (s - cp['strike'])).sum()
                if len(pp) > 0:
                    pain += (pp['openInterest'] * (pp['strike'] - s)).sum()
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = s

        # Regime
        if total_net_gex > 0:
            regime = "POSITIVE GAMMA"
            regime_detail = "Dealers are net long gamma. They sell into rallies and buy dips, dampening volatility. Price tends to stay pinned near high-gamma strikes."
            regime_color = '#3fb950'
        else:
            regime = "NEGATIVE GAMMA"
            regime_detail = "Dealers are net short gamma. They buy into rallies and sell into dips, amplifying moves. Expect larger-than-normal price swings."
            regime_color = '#f85149'

        _gex_computed = True

        # GEX Profile line (cumulative from bottom)
        net_gex_sorted = net_gex.sort_values('strike')
        net_gex_sorted['cum_gex'] = net_gex_sorted['gex'].cumsum()

        # Green/red clusters
        green_zone_min = net_gex_sorted[net_gex_sorted['gex'] > 0]['strike'].min() if (net_gex_sorted['gex'] > 0).any() else price
        green_zone_max = net_gex_sorted[net_gex_sorted['gex'] > 0]['strike'].max() if (net_gex_sorted['gex'] > 0).any() else price
        red_zone_min = net_gex_sorted[net_gex_sorted['gex'] < 0]['strike'].min() if (net_gex_sorted['gex'] < 0).any() else price
        red_zone_max = net_gex_sorted[net_gex_sorted['gex'] < 0]['strike'].max() if (net_gex_sorted['gex'] < 0).any() else price

        # =====================================================================
        # MAIN GEX CHART — Horizontal bars (strike on Y-axis, GEX on X-axis)
        # =====================================================================
        st.markdown(f"""<div style="font-size:0.9rem; font-weight:700; color:#e6edf3; margin-bottom:4px;">
            Net GEX {'All Expirations' if multi_exp else selected_exp} for {ticker}
        </div>
        <div style="font-size:0.7rem; color:#6e7681; margin-bottom:10px;">
            Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Spot: &#36;{price:.2f}
        </div>""", unsafe_allow_html=True)

        fig = make_subplots(rows=1, cols=1)

        # Horizontal bars: green = positive gamma, red/orange = negative
        bar_colors = ['rgba(63,185,80,0.75)' if v >= 0 else 'rgba(248,81,73,0.75)' for v in net_gex_sorted['gex']]
        fig.add_trace(go.Bar(
            y=net_gex_sorted['strike'], x=net_gex_sorted['gex'],
            orientation='h', marker_color=bar_colors,
            name='Net GEX', showlegend=True,
            hovertemplate='Strike: $%{y:.0f}<br>GEX: %{x:,.0f}<extra></extra>'
        ))

        # GEX Profile line (cumulative — like MenthorQ's yellow line)
        max_abs_cum = max(abs(net_gex_sorted['cum_gex'].max()), abs(net_gex_sorted['cum_gex'].min()), 1)
        max_abs_gex = max(abs(net_gex_sorted['gex'].max()), abs(net_gex_sorted['gex'].min()), 1)
        scale = max_abs_gex / max_abs_cum if max_abs_cum > 0 else 1
        fig.add_trace(go.Scatter(
            y=net_gex_sorted['strike'], x=net_gex_sorted['cum_gex'] * scale,
            mode='lines', name='GEX Profile',
            line=dict(color='#d29922', width=2.5),
            hovertemplate='Strike: $%{y:.0f}<br>Cumulative GEX: %{x:,.0f}<extra></extra>'
        ))

        # --- Horizontal reference lines for key levels ---
        # Spot price
        fig.add_hline(y=price, line_dash="dash", line_color="#ffffff", line_width=1.5,
                       annotation_text=f"Spot: &#36;{price:.0f}", annotation_position="top right",
                       annotation_font=dict(color='#ffffff', size=10))
        # Call Wall (resistance)
        fig.add_hline(y=call_wall, line_dash="dot", line_color='#f85149', line_width=1.5,
                       annotation_text=f"Call Resistance: &#36;{call_wall:.0f}", annotation_position="top right",
                       annotation_font=dict(color='#f85149', size=9))
        # Put Wall (support)
        fig.add_hline(y=put_wall, line_dash="dot", line_color='#3fb950', line_width=1.5,
                       annotation_text=f"Put Support: &#36;{put_wall:.0f}", annotation_position="bottom right",
                       annotation_font=dict(color='#3fb950', size=9))
        # HVL
        if abs(hvl - price) > price * 0.003:
            fig.add_hline(y=hvl, line_dash="longdash", line_color='#f0883e', line_width=1.5,
                           annotation_text=f"HVL: &#36;{hvl:.0f}", annotation_position="bottom left",
                           annotation_font=dict(color='#f0883e', size=9))

        fig.update_layout(
            height=500, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(13,17,23,0.5)',
            font={'color': '#e6edf3', 'size': 10},
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0.5, xanchor="center",
                         font=dict(size=10)),
            xaxis=dict(gridcolor='#21262d', title='GEX', zeroline=True, zerolinecolor='#30363d', zerolinewidth=1),
            yaxis=dict(gridcolor='#21262d', title='Strike Price', tickformat='$,.0f'),
            bargap=0.15,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # =====================================================================
        # KEY LEVELS LEGEND + SUMMARY
        # =====================================================================
        st.markdown(f"""
        <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px;">
            <div style="background:#161b22; padding:8px 12px; border-radius:6px; border-left:3px solid {regime_color}; flex:1.5; min-width:200px;">
                <div style="font-size:0.65rem; color:#6e7681;">GAMMA REGIME</div>
                <div style="font-size:0.85rem; color:{regime_color}; font-weight:700;">{regime}</div>
            </div>
            <div style="background:#161b22; padding:8px 12px; border-radius:6px; border-left:3px solid #f85149; min-width:110px;">
                <div style="font-size:0.65rem; color:#6e7681;">Call Resistance</div>
                <div style="font-size:0.9rem; color:#f85149; font-weight:700;">&#36;{call_wall:.0f}</div>
            </div>
            <div style="background:#161b22; padding:8px 12px; border-radius:6px; border-left:3px solid #3fb950; min-width:110px;">
                <div style="font-size:0.65rem; color:#6e7681;">Put Support</div>
                <div style="font-size:0.9rem; color:#3fb950; font-weight:700;">&#36;{put_wall:.0f}</div>
            </div>
            <div style="background:#161b22; padding:8px 12px; border-radius:6px; border-left:3px solid #f0883e; min-width:90px;">
                <div style="font-size:0.65rem; color:#6e7681;">HVL</div>
                <div style="font-size:0.9rem; color:#f0883e; font-weight:700;">&#36;{hvl:.0f}</div>
            </div>
            <div style="background:#161b22; padding:8px 12px; border-radius:6px; border-left:3px solid #bc8cff; min-width:90px;">
                <div style="font-size:0.65rem; color:#6e7681;">Max Pain</div>
                <div style="font-size:0.9rem; color:#bc8cff; font-weight:700;">&#36;{max_pain_strike:.0f}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        # =====================================================================
        # DYNAMIC GEX INTERPRETATION — reads the actual chart data
        # =====================================================================
        st.markdown("#### Interpretacion del grafico")

        # --- Analyze the GEX shape ---
        # Count positive/negative bars above and below spot
        above_spot = net_gex_sorted[net_gex_sorted['strike'] > price]
        below_spot = net_gex_sorted[net_gex_sorted['strike'] < price]
        pos_above = (above_spot['gex'] > 0).sum()
        neg_above = (above_spot['gex'] < 0).sum()
        pos_below = (below_spot['gex'] > 0).sum()
        neg_below = (below_spot['gex'] < 0).sum()
        total_above = len(above_spot)
        total_below = len(below_spot)

        # GEX concentration (where is most gamma?)
        gex_max_strike = float(net_gex_sorted.loc[net_gex_sorted['gex'].abs().idxmax(), 'strike'])
        gex_max_val = float(net_gex_sorted.loc[net_gex_sorted['gex'].abs().idxmax(), 'gex'])

        # Gamma asymmetry: more gamma above or below price?
        gex_above_total = above_spot['gex'].sum() if not above_spot.empty else 0
        gex_below_total = below_spot['gex'].sum() if not below_spot.empty else 0

        # Profile shape: is cumulative rising or falling near spot?
        cum_at_spot_idx = (net_gex_sorted['strike'] - price).abs().idxmin()
        cum_at_spot = float(net_gex_sorted.loc[cum_at_spot_idx, 'cum_gex'])
        cum_max = float(net_gex_sorted['cum_gex'].max())
        cum_min = float(net_gex_sorted['cum_gex'].min())

        # Price range between key levels
        range_pw_cw = abs(call_wall - put_wall)
        range_pw_cw_pct = (range_pw_cw / price * 100) if price > 0 else 0

        interp = []

        # 1/ CHART LEGEND
        interp.append(f'<b style="color:#3fb950;">Barras verdes</b> = gamma positiva (dealers frenan el movimiento). <b style="color:#f85149;">Barras rojas</b> = gamma negativa (dealers amplifican el movimiento). <b style="color:#d29922;">Linea amarilla</b> = perfil GEX acumulado. <b style="color:#ffffff;">Linea blanca</b> = precio actual de {ticker}.')

        # 2/ READING THE CHART — what is the shape telling us?
        if pos_above > neg_above and total_above > 0:
            pct_pos_above = (pos_above / total_above * 100) if total_above > 0 else 0
            interp.append(f'<b style="color:#58a6ff;">Lectura del grafico:</b> Por encima del precio, <b>{pct_pos_above:.0f}% de los strikes tienen gamma positiva</b> (barras verdes). Esto forma un "muro" de amortiguacion que <b>frena los rallies</b>. El precio necesita un catalizador fuerte (earnings, news) para romper la zona &#36;{call_wall:.0f}.')
        elif neg_above > pos_above and total_above > 0:
            interp.append(f'<b style="color:#58a6ff;">Lectura del grafico:</b> Por encima del precio hay <b>predominancia de gamma negativa</b> (barras rojas). Si el precio sube, los dealers compran para cubrir, <b>acelerando el rally</b>. Un breakout por encima de &#36;{call_wall:.0f} podria generar un movimiento explosivo.')
        else:
            interp.append(f'<b style="color:#58a6ff;">Lectura del grafico:</b> La distribucion de gamma alrededor del precio es <b>relativamente equilibrada</b>. No hay sesgo claro por parte de dealers — el precio puede moverse en cualquier direccion sin amplificacion significativa.')

        # 3/ REGIME — what it means practically
        if total_net_gex > 0:
            if gex_above_total > 0 and gex_below_total < 0:
                interp.append(f'<b style="color:#3fb950;">Regimen actual: GAMMA POSITIVA.</b> El precio esta "atrapado" en una zona de amortiguacion. Los dealers mantienen posiciones que les obligan a <b>vender en rallies y comprar en caidas</b>. Esto crea un efecto de <b>"pinning"</b> — el precio tiende a quedarse pegado cerca de los strikes con mas OI. Espera movimiento lateral/contenido mientras se mantenga entre &#36;{put_wall:.0f} y &#36;{call_wall:.0f}.')
            else:
                interp.append(f'<b style="color:#3fb950;">Regimen actual: GAMMA POSITIVA.</b> Net GEX positivo. Los dealers actuan como <b>amortiguadores</b> del mercado. El precio tiende a moverse menos de lo que la volatilidad implicita sugiere.')
        else:
            if abs(gex_below_total) > abs(gex_above_total) * 1.5:
                interp.append(f'<b style="color:#f85149;">Regimen actual: GAMMA NEGATIVA (sesgo bajista).</b> Hay mucho mas gamma negativa por debajo del precio que por encima. Si el precio cae, los dealers venden para cubrir, <b>acelerando la caida</b>. Es como una "rampa" hacia abajo — cada tick a la baja genera mas venta. <b>Cuidado con breaks debajo de &#36;{put_wall:.0f}.</b>')
            elif abs(gex_above_total) > abs(gex_below_total) * 1.5:
                interp.append(f'<b style="color:#f85149;">Regimen actual: GAMMA NEGATIVA (sesgo alcista).</b> La gamma negativa esta concentrada <b>por encima del precio</b>. Un movimiento al alza podria ser amplificado por dealer hedging. Si rompe &#36;{call_wall:.0f}, espera <b>aceleracion del rally</b>.')
            else:
                interp.append(f'<b style="color:#f85149;">Regimen actual: GAMMA NEGATIVA.</b> Los dealers amplifican los movimientos en ambas direcciones. <b>Volatilidad esperada mayor</b> de lo normal. Movimientos bruscos son mas probables.')

        # 4/ KEY LEVELS — what they are and what happens if broken
        pct_to_cw = ((call_wall - price) / price * 100)
        pct_to_pw = ((price - put_wall) / price * 100)

        if pct_to_cw > 0:
            interp.append(f'<b style="color:#f85149;">Call Resistance &#36;{call_wall:.0f}</b> (+{pct_to_cw:.1f}% arriba): Maxima concentracion de gamma de calls. Actua como <b>techo</b>. Si se rompe, los dealers que vendieron calls deben comprar acciones para cubrir → <b>short gamma squeeze al alza</b>. Si no se rompe, el precio rebota hacia abajo desde esta zona.')
        else:
            interp.append(f'<b style="color:#f85149;">Call Resistance &#36;{call_wall:.0f}</b>: El precio YA ESTA por encima del Call Wall. Los dealers estan en <b>modo de persecucion</b> — comprando para cubrir. Si la presion se mantiene, el proximo nivel de resistencia es el siguiente strike con gamma significativa.')

        if pct_to_pw > 0:
            interp.append(f'<b style="color:#3fb950;">Put Support &#36;{put_wall:.0f}</b> (-{pct_to_pw:.1f}% abajo): Maxima concentracion de gamma de puts. Actua como <b>suelo</b>. Si se rompe, dealers que vendieron puts deben vender acciones para cubrir → <b>gamma avalanche a la baja</b>. Mientras se mantenga, funciona como nivel de soporte.')
        else:
            interp.append(f'<b style="color:#3fb950;">Put Support &#36;{put_wall:.0f}</b>: El precio YA ESTA por debajo del Put Wall. Los dealers estan vendiendo para cubrir → <b>presion bajista activa</b>. Buscar estabilizacion en el siguiente cluster de gamma.')

        # 5/ PROFILE LINE — what the yellow line shape tells us
        if cum_at_spot > cum_max * 0.7 and cum_max > 0:
            interp.append(f'<b style="color:#d29922;">Perfil GEX (linea amarilla):</b> El perfil acumulado esta cerca de su maximo en el precio actual. Esto indica que <b>la mayor parte del gamma positivo esta por debajo del precio</b>. Hay "colchon" a la baja pero <b>poco soporte gamma al alza</b>.')
        elif cum_at_spot < cum_min * 0.7 and cum_min < 0:
            interp.append(f'<b style="color:#d29922;">Perfil GEX (linea amarilla):</b> El perfil acumulado esta en zona baja. La <b>mayor parte del gamma negativo esta por debajo del precio</b>. Si cae, entra en zona de amplificacion. El perfil sugiere <b>mayor riesgo a la baja</b>.')
        else:
            interp.append(f'<b style="color:#d29922;">Perfil GEX (linea amarilla):</b> El perfil muestra una transicion de gamma negativa (izquierda) a positiva (derecha) o viceversa. El punto donde la linea cruza cero es el <b>HVL</b> — el nivel donde el regimen de volatilidad cambia.')

        # 6/ MAX PAIN GRAVITY
        mp_dist_pct = ((price - max_pain_strike) / price * 100) if price > 0 else 0
        if abs(mp_dist_pct) > 3:
            mp_dir = "por encima" if mp_dist_pct > 0 else "por debajo"
            interp.append(f'<b style="color:#bc8cff;">Max Pain &#36;{max_pain_strike:.0f}</b>: El precio esta {abs(mp_dist_pct):.1f}% {mp_dir} del punto de maximo dolor para compradores de opciones. A medida que se acerca el vencimiento, hay una "fuerza gravitacional" que atrae el precio hacia Max Pain. Esto es mas relevante en las ultimas 2-3 sesiones antes del vencimiento.')
        else:
            interp.append(f'<b style="color:#bc8cff;">Max Pain &#36;{max_pain_strike:.0f}</b>: El precio esta <b>muy cerca de Max Pain</b>. Las opciones vencen con el minimo valor posible para compradores. Esta es una posicion de <b>equilibrio</b> — poca presion de hedging en cualquier direccion.')

        # 7/ EXPECTED MOVE
        if expected_move_pct > 0:
            up_t = price * (1 + expected_move_pct / 100)
            dn_t = price * (1 - expected_move_pct / 100)
            # Is call_wall within expected move?
            cw_within = abs(pct_to_cw) < expected_move_pct
            pw_within = abs(pct_to_pw) < expected_move_pct
            em_note = ""
            if cw_within and pw_within:
                em_note = " <b>Ambos muros gamma estan dentro del expected move</b> — si el precio se mueve, probablemente testee alguno de ellos."
            elif cw_within:
                em_note = f" El <b>Call Resistance esta dentro del rango esperado</b> — el rally podria frenarse en &#36;{call_wall:.0f}."
            elif pw_within:
                em_note = f" El <b>Put Support esta dentro del rango esperado</b> — una caida podria acelerarse al romper &#36;{put_wall:.0f}."
            interp.append(f'<b>Expected Move ±{expected_move_pct:.1f}%</b> (&#36;{dn_t:.0f} — &#36;{up_t:.0f}) para {selected_exp}. El mercado de opciones esta "apostando" a que el precio se mantendra en este rango con ~68% de probabilidad.{em_note}')

        # 8/ P/C RATIO CONTEXT
        if pc_ratio_oi > 1.3:
            interp.append(f'<b>Put/Call OI = {pc_ratio_oi:.2f}</b> — Ratio alto. Hay <b>mucha mas proteccion put que especulacion call</b>. Paradojicamente, esto puede ser contrarian bullish: demasiado pesimismo puede generar un short squeeze si el catalizador es positivo.')
        elif pc_ratio_oi < 0.6:
            interp.append(f'<b>Put/Call OI = {pc_ratio_oi:.2f}</b> — Ratio bajo. <b>Poca proteccion put vs calls</b>. El mercado esta complaciente — vulnerable a una caida sorpresa porque pocos estan cubiertos.')
        elif pc_ratio_oi > 0:
            interp.append(f'<b>Put/Call OI = {pc_ratio_oi:.2f}</b> — Ratio normal. El posicionamiento esta equilibrado sin sesgo extremo.')

        # 9/ STRATEGY SUGGESTIONS
        strategy_items = []
        if total_net_gex > 0 and range_pw_cw_pct < 8:
            strategy_items.append(('Iron Condor / Credit Spread', 'Gamma positiva + rango estrecho entre walls = <b>venta de prima favorable</b>. El pinning effect mantiene el precio dentro del rango.'))
            strategy_items.append(('Sell Straddle/Strangle', f'Vender volatilidad cerca de &#36;{gamma_wall:.0f} (gamma wall). Dealers comprimen el rango — beneficia vendedores de opciones.'))
        elif total_net_gex > 0 and range_pw_cw_pct >= 8:
            strategy_items.append(('Bull/Bear Credit Spread', f'Gamma positiva pero rango amplio ({range_pw_cw_pct:.0f}%). Vende spreads fuera del rango &#36;{put_wall:.0f}—&#36;{call_wall:.0f}.'))
        elif total_net_gex < 0 and abs(pct_to_cw) < 3:
            strategy_items.append(('Call Debit Spread', f'Gamma negativa con precio cerca del Call Wall. Un break por encima de &#36;{call_wall:.0f} puede generar <b>gamma squeeze alcista</b>. Spread con riesgo definido.'))
            strategy_items.append(('Put como proteccion', f'Si tienes posicion larga, compra put cerca de &#36;{put_wall:.0f} — gamma negativa amplifica caidas si falla el breakout.'))
        elif total_net_gex < 0 and abs(pct_to_pw) < 3:
            strategy_items.append(('Put Debit Spread', f'Gamma negativa con precio cerca del Put Wall. Un break por debajo de &#36;{put_wall:.0f} puede generar <b>gamma avalanche bajista</b>.'))
            strategy_items.append(('Protective Call', f'Si estas corto, protege con call en &#36;{call_wall:.0f} — gamma negativa puede rebotar agresivamente.'))
        else:
            if total_net_gex < 0:
                strategy_items.append(('Straddle / Long Volatility', 'Gamma negativa = dealers amplifican. <b>Compra de volatilidad</b> favorecida. El precio se movera mas de lo esperado.'))
                strategy_items.append(('Wider Stops', 'En regimen de gamma negativa, los stops ajustados se ejecutan facilmente. Usa stops mas amplios o opciones en lugar de stops.'))
            else:
                strategy_items.append(('Mean Reversion', f'Gamma positiva favorece <b>comprar dips</b> cerca de &#36;{put_wall:.0f} y <b>vender rallies</b> cerca de &#36;{call_wall:.0f}. Dealers frenan los extremos.'))

        # 10/ DIRECTIONAL CONCLUSION
        bullish_points = 0
        bearish_points = 0
        if total_net_gex > 0:
            bullish_points += 1  # stability favors holders
        else:
            bearish_points += 1  # amplification = risk
        if pct_to_cw > pct_to_pw and pct_to_pw > 0:
            bullish_points += 1  # more room to upside
        elif pct_to_pw > pct_to_cw and pct_to_cw > 0:
            bearish_points += 1  # more room to downside
        if pc_ratio_oi > 1.2:
            bullish_points += 1  # contrarian
        elif pc_ratio_oi < 0.7:
            bearish_points += 1  # complacency
        if mp_dist_pct > 2:
            bearish_points += 1  # above max pain = gravity down
        elif mp_dist_pct < -2:
            bullish_points += 1  # below max pain = gravity up
        if skew > 10:
            bearish_points += 1  # fear
        elif skew < -3:
            bullish_points += 1

        if bullish_points > bearish_points + 1:
            directional = f'<b style="color:#3fb950;">SESGO ALCISTA</b> por estructura gamma. El posicionamiento de opciones favorece estabilidad o movimiento al alza. La estructura de mercado "empuja" levemente hacia arriba (gravedad max pain, gamma positiva, o exceso de puts).'
        elif bearish_points > bullish_points + 1:
            directional = f'<b style="color:#f85149;">SESGO BAJISTA</b> por estructura gamma. El posicionamiento de opciones crea vulnerabilidad a la baja (gamma negativa, precio sobre max pain, skew de miedo, o complacencia en cobertura).'
        else:
            directional = f'<b style="color:#d29922;">NEUTRAL / SIN SESGO CLARO</b> por estructura gamma. Los factores alcistas y bajistas estan equilibrados. El precio probablemente se mueva por <b>catalizadores fundamentales</b> (earnings, macro, news) mas que por flujos de gamma.'

        interp.append(f'<b style="color:#d29922;">Conclusion direccional:</b> {directional}')

        # Render interpretation
        for i, text in enumerate(interp):
            border_color = '#30363d'
            if i == len(interp) - 1:
                border_color = '#d29922'  # highlight conclusion
            st.markdown(f"""<div style="background:#161b22; padding:8px 14px; border-radius:6px; margin-bottom:4px; border-left:3px solid {border_color};">
                <span style="color:#6e7681; font-size:0.7rem; font-weight:700;">{i+1}/</span>
                <span style="font-size:0.78rem; color:#e6edf3;"> {text}</span>
            </div>""", unsafe_allow_html=True)

        # Strategies section
        if strategy_items:
            st.markdown("#### Estrategias sugeridas")
            for strat_name, strat_desc in strategy_items:
                st.markdown(f"""<div style="background:#161b22; padding:10px 14px; border-radius:6px; margin-bottom:4px; border-left:3px solid #58a6ff;">
                    <div style="color:#58a6ff; font-size:0.8rem; font-weight:700;">{strat_name}</div>
                    <div style="color:#e6edf3; font-size:0.75rem; margin-top:3px;">{strat_desc}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown('<div style="color:#6e7681; font-size:0.65rem; margin-top:6px;">Gamma no predice direccion. Describe <b>como</b> se movera el precio una vez que empiece a moverse. Esto NO es consejo financiero. El analisis gamma es un factor mas — no operes basandote solo en GEX.</div>', unsafe_allow_html=True)

    # =====================================================================
    # ROW 3: IV SMILE + TOP STRIKES TABLE
    # =====================================================================
    st.markdown("---")
    col_smile, col_table = st.columns([1, 1])

    with col_smile:
        st.markdown("#### IV Smile / Skew")
        if not calls_f.empty and not puts_f.empty:
            fig_smile = go.Figure()
            c_iv = calls_f[['strike', 'impliedVolatility']].dropna()
            p_iv = puts_f[['strike', 'impliedVolatility']].dropna()
            if not c_iv.empty:
                fig_smile.add_trace(go.Scatter(x=c_iv['strike'], y=c_iv['impliedVolatility'] * 100,
                                                mode='lines+markers', name='Call IV', line=dict(color='#58a6ff', width=2),
                                                marker=dict(size=4)))
            if not p_iv.empty:
                fig_smile.add_trace(go.Scatter(x=p_iv['strike'], y=p_iv['impliedVolatility'] * 100,
                                                mode='lines+markers', name='Put IV', line=dict(color='#f85149', width=2),
                                                marker=dict(size=4)))
            fig_smile.add_vline(x=price, line_dash="dash", line_color="#d29922")
            fig_smile.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=30),
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                     font={'color': '#e6edf3', 'size': 10},
                                     legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                                     xaxis=dict(title="Strike", gridcolor='#21262d'),
                                     yaxis=dict(title="IV %", gridcolor='#21262d'))
            st.plotly_chart(fig_smile, use_container_width=True, config={'displayModeBar': False})

    with col_table:
        st.markdown("#### Top Strikes by OI")
        all_strikes_data = []
        for _, r in calls_f.iterrows():
            s = r['strike']
            c_oi = int(r.get('openInterest', 0))
            c_vol = int(r.get('volume', 0) if pd.notna(r.get('volume')) else 0)
            c_iv_v = r.get('impliedVolatility', 0)
            c_iv_v = float(c_iv_v * 100) if pd.notna(c_iv_v) else 0
            p_row = puts_f[puts_f['strike'] == s]
            p_oi = int(p_row['openInterest'].iloc[0]) if not p_row.empty else 0
            p_vol = int(p_row['volume'].iloc[0]) if not p_row.empty and pd.notna(p_row['volume'].iloc[0]) else 0
            p_iv_v = float(p_row['impliedVolatility'].iloc[0] * 100) if not p_row.empty and pd.notna(p_row['impliedVolatility'].iloc[0]) else 0
            t_oi = c_oi + p_oi
            if t_oi > 0:
                all_strikes_data.append({
                    'Strike': f"${s:.0f}", 'Call OI': f"{c_oi:,}", 'Put OI': f"{p_oi:,}",
                    'Total OI': t_oi, 'Call IV': f"{c_iv_v:.0f}%", 'Put IV': f"{p_iv_v:.0f}%",
                    'Vol': f"{c_vol + p_vol:,}",
                })
        if all_strikes_data:
            top_df = pd.DataFrame(all_strikes_data).sort_values('Total OI', ascending=False).head(15)
            top_df['Total OI'] = top_df['Total OI'].apply(lambda x: f"{x:,}")
            st.dataframe(top_df, hide_index=True, use_container_width=True, height=300)

    # =====================================================================
    # STRIKE SELECTION USING GAMMA LEVELS
    # =====================================================================
    if _gex_computed:
        st.markdown("---")
        st.markdown("#### Strike Selection — Gamma Levels")

        atm5 = round(price / 5) * 5
        cw5 = round(call_wall / 5) * 5
        pw5 = round(put_wall / 5) * 5
        hvl5 = round(hvl / 5) * 5

        col_bull, col_bear = st.columns(2)

        with col_bull:
            st.markdown('<div style="font-size:0.8rem; color:#3fb950; font-weight:700; margin-bottom:6px;">CALLS (Bullish)</div>', unsafe_allow_html=True)
            recs = []
            recs.append((atm5, 'HIGH', 'ATM — max delta, near dealer flows'))
            if cw5 > price:
                recs.append((cw5, 'HIGH', f'Near Call Resistance — dealer hedging flips if broken'))
            if cw5 > atm5:
                recs.append((atm5, 'SPREAD', f'Bull Spread: Buy &#36;{atm5} / Sell &#36;{cw5}'))
            for strike, q, reason in recs:
                badge_c = '#3fb950' if q == 'HIGH' else '#58a6ff'
                st.markdown(f'''<div style="background:#161b22; padding:8px 12px; border-radius:6px; margin-bottom:4px; border-left:2px solid #3fb950;">
                    <span style="color:#3fb950; font-weight:700;">&#36;{strike}</span>
                    <span style="background:rgba(63,185,80,0.15); color:{badge_c}; padding:1px 6px; border-radius:8px; font-size:0.6rem; font-weight:700; margin-left:6px;">{q}</span>
                    <div style="color:#8b949e; font-size:0.7rem; margin-top:2px;">{reason}</div>
                </div>''', unsafe_allow_html=True)

        with col_bear:
            st.markdown('<div style="font-size:0.8rem; color:#f85149; font-weight:700; margin-bottom:6px;">PUTS (Bearish / Hedge)</div>', unsafe_allow_html=True)
            recs = []
            recs.append((atm5, 'HIGH', 'ATM — max delta, best protection'))
            if pw5 < price:
                recs.append((pw5, 'HIGH', f'Near Put Support — dealer hedging flips if broken'))
            if hvl5 < price and hvl5 != pw5:
                recs.append((hvl5, 'HIGH', f'Near HVL — gamma regime transition zone'))
            if pw5 < atm5:
                recs.append((atm5, 'SPREAD', f'Bear Spread: Buy &#36;{atm5} / Sell &#36;{pw5}'))
            for strike, q, reason in recs:
                badge_c = '#f85149' if q == 'HIGH' else '#58a6ff'
                st.markdown(f'''<div style="background:#161b22; padding:8px 12px; border-radius:6px; margin-bottom:4px; border-left:2px solid #f85149;">
                    <span style="color:#f85149; font-weight:700;">&#36;{strike}</span>
                    <span style="background:rgba(248,81,73,0.12); color:{badge_c}; padding:1px 6px; border-radius:8px; font-size:0.6rem; font-weight:700; margin-left:6px;">{q}</span>
                    <div style="color:#8b949e; font-size:0.7rem; margin-top:2px;">{reason}</div>
                </div>''', unsafe_allow_html=True)

        with st.expander("How to read Gamma Levels (for beginners)"):
            st.markdown(f"""<div style="font-size:0.75rem; color:#8b949e; line-height:1.7;">
            <b style="color:#3fb950;">Green bars (Positive Gamma)</b> — These strikes have net positive dealer gamma. When price is near these bars, dealers sell into rallies and buy dips → <b>price stabilizes</b> (like shock absorbers).<br><br>
            <b style="color:#f85149;">Red bars (Negative Gamma)</b> — Net negative dealer gamma. Dealers buy into rallies and sell into dips → <b>moves accelerate</b> (like removing brakes).<br><br>
            <b style="color:#f85149;">Call Resistance (&#36;{call_wall:.0f})</b> — Strike where call gamma is highest. Acts as a <b>ceiling</b>. If price pushes through, dealer hedging reverses and the move <b>accelerates upward</b>.<br><br>
            <b style="color:#3fb950;">Put Support (&#36;{put_wall:.0f})</b> — Strike where put gamma is highest. Acts as a <b>floor</b>. If price drops below, dealer hedging reverses and the move <b>accelerates downward</b>.<br><br>
            <b style="color:#f0883e;">HVL (&#36;{hvl:.0f})</b> — Volatility pivot. Above HVL = dampened moves. Below HVL = amplified moves.<br><br>
            <b style="color:#d29922;">GEX Profile (yellow line)</b> — Cumulative gamma exposure. Shows the overall "shape" of dealer positioning across all strikes.<br><br>
            <b>Remember:</b> Gamma doesn't predict direction. It describes <b>how</b> price moves once it starts moving.
            </div>""", unsafe_allow_html=True)


def _show_fundamental_tab(ticker: str, data: dict):
    """Fundamental analysis tab with intelligent comments and valuation models."""
    import math

    # =========================================================================
    # ROW 1: STYLED RATIO CARDS (4 columns)
    # =========================================================================
    def _val(v, fmt=".1f", suffix="", prefix=""):
        """Safe format a value."""
        if v is None or v == 0:
            return "N/A"
        try:
            return f"{prefix}{v:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

    def _ratio_color(val, good_threshold, bad_threshold, lower_is_better=False):
        """Return color based on value thresholds."""
        if val is None or val == 0:
            return "#94a3b8"
        if lower_is_better:
            if val <= good_threshold: return "#10B981"
            if val >= bad_threshold: return "#EF4444"
            return "#F59E0B"
        else:
            if val >= good_threshold: return "#10B981"
            if val <= bad_threshold: return "#EF4444"
            return "#F59E0B"

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        pe = data.get('pe_ratio', 0) or 0
        fwd_pe = data.get('forward_pe', 0) or 0
        ps = data.get('ps_ratio', 0) or 0
        pb = data.get('pb_ratio', 0) or 0
        ev_ebitda = data.get('ev_ebitda', 0) or 0
        peg = data.get('peg_ratio', 0) or 0
        ev_rev = data.get('ev_revenue', 0) or 0

        # FCF Yield
        fcf = data.get('free_cash_flow', 0) or 0
        mcap = data.get('market_cap', 0) or 0
        fcf_yield = (fcf / mcap * 100) if mcap > 0 and fcf else 0

        card = render_fund_card("Valoracion", [
            ("P/E", _val(pe), _ratio_color(pe, 18, 35, True)),
            ("Fwd P/E", _val(fwd_pe), _ratio_color(fwd_pe, 16, 30, True)),
            ("P/S", _val(ps, ".2f"), _ratio_color(ps, 3, 10, True)),
            ("P/B", _val(pb, ".2f"), _ratio_color(pb, 3, 8, True)),
            ("EV/EBITDA", _val(ev_ebitda), _ratio_color(ev_ebitda, 12, 25, True)),
            ("PEG Ratio", _val(peg, ".2f"), _ratio_color(peg, 1.0, 2.0, True)),
            ("EV/Revenue", _val(ev_rev, ".1f"), _ratio_color(ev_rev, 5, 15, True)),
            ("FCF Yield", _val(fcf_yield, ".1f", "%"), _ratio_color(fcf_yield, 5, 2, False)),
        ])
        st.markdown(card, unsafe_allow_html=True)

    with col2:
        roe = data.get('roe', 0) or 0
        roa = data.get('roa', 0) or 0
        gm = data.get('gross_margin', 0) or 0
        om = data.get('operating_margin', 0) or 0
        nm = data.get('profit_margin', 0) or 0
        rev_growth = data.get('revenue_growth', 0) or 0
        earn_growth = data.get('earnings_growth', 0) or 0

        card = render_fund_card("Rentabilidad", [
            ("ROE %", _val(roe, ".1f", "%"), _ratio_color(roe, 15, 5, False)),
            ("ROA %", _val(roa, ".1f", "%"), _ratio_color(roa, 8, 2, False)),
            ("M. Bruto %", _val(gm, ".1f", "%"), _ratio_color(gm, 40, 20, False)),
            ("M. Operativo %", _val(om, ".1f", "%"), _ratio_color(om, 15, 5, False)),
            ("M. Neto %", _val(nm, ".1f", "%"), _ratio_color(nm, 10, 0, False)),
            ("Crec. Revenue %", _val(rev_growth, "+.1f", "%"), _ratio_color(rev_growth, 10, -5, False)),
            ("Crec. BPA %", _val(earn_growth, "+.1f", "%"), _ratio_color(earn_growth, 10, -5, False)),
        ])
        st.markdown(card, unsafe_allow_html=True)

    with col3:
        qr = data.get('quick_ratio', 0) or 0
        cr = data.get('current_ratio', 0) or 0
        d2e = data.get('debt_to_equity', 0) or 0
        total_debt = data.get('total_debt', 0) or 0
        total_cash = data.get('total_cash', 0) or 0
        ebitda_val = data.get('ebitda', 0) or 0

        # Calculated ratios
        debt_ebitda = total_debt / ebitda_val if ebitda_val > 0 else 0
        net_debt = total_debt - total_cash
        net_debt_ebitda = net_debt / ebitda_val if ebitda_val > 0 else 0
        cash_ratio = total_cash / total_debt if total_debt > 0 else (99.9 if total_cash > 0 else 0)
        # Interest coverage estimate (EBITDA / estimated interest)
        est_interest = total_debt * 0.05  # assume ~5% avg rate
        int_coverage = ebitda_val / est_interest if est_interest > 0 else 0

        card = render_fund_card("Deuda y Liquidez", [
            ("Quick Ratio", _val(qr, ".2f"), _ratio_color(qr, 1.0, 0.5, False)),
            ("Current Ratio", _val(cr, ".2f"), _ratio_color(cr, 1.5, 0.8, False)),
            ("D/E %", _val(d2e, ".0f", "%"), _ratio_color(d2e, 50, 150, True)),
            ("Deuda/EBITDA", _val(debt_ebitda, ".1f", "x"), _ratio_color(debt_ebitda, 2, 4, True)),
            ("Deuda Neta/EBITDA", _val(net_debt_ebitda, ".1f", "x"), _ratio_color(net_debt_ebitda, 1.5, 3, True)),
            ("Cash Ratio", _val(cash_ratio, ".2f"), _ratio_color(cash_ratio, 0.5, 0.2, False)),
            ("Cobertura Int. (est)", _val(int_coverage, ".1f", "x"), _ratio_color(int_coverage, 5, 2, False)),
        ])
        st.markdown(card, unsafe_allow_html=True)

    with col4:
        dy = data.get('dividend_yield', 0) or 0
        beta = data.get('beta', 1) or 1
        inst_own = data.get('institutional_ownership', 0) or 0
        insider_own = data.get('insider_ownership', 0) or 0
        w52h = data.get('52w_high', 0) or 0
        w52l = data.get('52w_low', 0) or 0
        price = data.get('price', 0) or 0
        pct_from_high = ((price - w52h) / w52h * 100) if w52h > 0 else 0

        card = render_fund_card("Perfil", [
            ("Div. Yield %", _val(dy, ".2f", "%"), _ratio_color(dy, 2.0, 0, False)),
            ("Beta", _val(beta, ".2f"), "#F59E0B" if beta > 1.3 else ("#10B981" if beta < 0.8 else "#94a3b8")),
            ("% Institucional", _val(inst_own, ".1f", "%"), "#94a3b8"),
            ("% Insider", _val(insider_own, ".1f", "%"), "#94a3b8"),
            ("52W High", f"${w52h:.2f}" if w52h else "N/A", "#94a3b8"),
            ("52W Low", f"${w52l:.2f}" if w52l else "N/A", "#94a3b8"),
            ("Vs. 52W High", _val(pct_from_high, "+.1f", "%"), "#10B981" if pct_from_high > -5 else ("#F59E0B" if pct_from_high > -20 else "#EF4444")),
        ])
        st.markdown(card, unsafe_allow_html=True)

    # =========================================================================
    # ROW 2: VALUATION MODELS
    # =========================================================================
    st.markdown("---")
    st.markdown("### Modelos de Valoracion")

    eps = data.get('trailing_eps', 0) or 0
    fwd_eps = data.get('forward_eps', 0) or 0
    book_val = data.get('book_value', 0) or 0
    earnings_growth_rate = data.get('earnings_growth', 0) or 0
    rev_growth_rate = data.get('revenue_growth', 0) or 0
    shares = data.get('shares_outstanding', 0) or 0

    models = []

    # 1. Graham Number: sqrt(22.5 * EPS * Book Value)
    if eps > 0 and book_val > 0:
        graham = math.sqrt(22.5 * eps * book_val)
        models.append(("Graham Number", graham, "sqrt(22.5 x EPS x BV)"))

    # 2. DCF Simplified (Gordon Growth)
    if fcf > 0 and shares > 0:
        growth = min(max(rev_growth_rate / 100, 0.02), 0.15)  # clamp 2-15%
        discount_rate = 0.10  # 10% WACC
        terminal_g = 0.025  # 2.5% terminal growth
        # 5-year explicit + terminal
        dcf_value = 0
        current_fcf = fcf
        for yr in range(1, 6):
            current_fcf *= (1 + growth)
            dcf_value += current_fcf / ((1 + discount_rate) ** yr)
        # Terminal value
        terminal_val = current_fcf * (1 + terminal_g) / (discount_rate - terminal_g)
        dcf_value += terminal_val / ((1 + discount_rate) ** 5)
        dcf_per_share = dcf_value / shares
        if 0 < dcf_per_share < price * 10:  # sanity check
            models.append(("DCF (5Y+Terminal)", dcf_per_share, f"g={growth*100:.0f}%, WACC=10%"))

    # 3. Earnings Power Value (EPV)
    if eps > 0:
        # EPV = Normalized Earnings / Cost of Capital
        cost_of_equity = 0.08 + (beta - 1) * 0.05  # CAPM-like
        cost_of_equity = max(cost_of_equity, 0.06)
        epv = eps / cost_of_equity
        if 0 < epv < price * 10:
            models.append(("EPV (Greenwald)", epv, f"EPS/{cost_of_equity*100:.0f}% CoE"))

    # 4. Peter Lynch Fair Value (PEG-based)
    if eps > 0 and earnings_growth_rate > 0:
        lynch_pe = min(earnings_growth_rate, 25)  # cap PE at growth rate, max 25
        lynch_val = eps * lynch_pe
        if lynch_val > 0:
            models.append(("Lynch Fair Value", lynch_val, f"EPS x Growth({lynch_pe:.0f})"))

    # 5. Reverse DCF (what growth is priced in)
    if eps > 0 and price > 0:
        implied_pe = price / eps if eps > 0 else 0
        # Implied growth from current PE
        implied_growth = max((implied_pe - 8) / 2, 0)  # rough formula
        models.append(("Implied Growth", implied_growth, f"P/E={implied_pe:.0f} implica ~{implied_growth:.0f}% CAGR"))

    if models:
        model_cols = st.columns(min(len(models), 5))
        model_results = []  # Collect for interpretation
        for i, (name, value, desc) in enumerate(models):
            if i >= 5:
                break
            with model_cols[i]:
                if name == "Implied Growth":
                    color = "#10B981" if value < earnings_growth_rate else "#EF4444"
                    st.markdown(f"""
                    <div class="val-model-card">
                        <div class="val-model-name">{name}</div>
                        <div class="val-model-price" style="color:{color};">{value:.0f}%</div>
                        <div style="font-size:0.7rem; color:#888;">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    model_results.append((name, value, 0, desc))
                else:
                    upside = ((value - price) / price * 100) if price > 0 else 0
                    up_color = "#10B981" if upside > 10 else ("#F59E0B" if upside > -10 else "#EF4444")
                    up_bg = f"rgba(16,185,129,0.15)" if upside > 10 else (f"rgba(245,158,11,0.15)" if upside > -10 else f"rgba(239,68,68,0.15)")
                    st.markdown(f"""
                    <div class="val-model-card">
                        <div class="val-model-name">{name}</div>
                        <div class="val-model-price" style="color:{up_color};">&#36;{value:.2f}</div>
                        <div class="val-model-upside" style="color:{up_color}; background:{up_bg};">{upside:+.1f}%</div>
                        <div style="font-size:0.65rem; color:#666; margin-top:6px;">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    model_results.append((name, value, upside, desc))

        # ---- MODEL INTERPRETATION ----
        interpretations = []
        for name, value, upside, desc in model_results:
            if name == "Graham Number":
                if upside > 20:
                    interpretations.append(f'<b style="color:#3fb950;">Graham Number (&#36;{value:.0f}, {upside:+.0f}%)</b>: Segun el modelo conservador de Benjamin Graham (basado en EPS y Book Value), la accion cotiza <b>significativamente por debajo</b> de su valor intrinseco. Sugiere margen de seguridad amplio para inversores value.')
                elif upside > 0:
                    interpretations.append(f'<b style="color:#d29922;">Graham Number (&#36;{value:.0f}, {upside:+.0f}%)</b>: Ligero descuento vs valor intrinseco Graham. El margen de seguridad existe pero es reducido.')
                else:
                    interpretations.append(f'<b style="color:#f85149;">Graham Number (&#36;{value:.0f}, {upside:+.0f}%)</b>: La accion cotiza <b>por encima</b> del valor conservador de Graham. Esto no significa que este cara necesariamente — Graham es muy conservador y no captura crecimiento futuro.')
            elif name == "DCF (5Y+Terminal)":
                if upside > 30:
                    interpretations.append(f'<b style="color:#3fb950;">DCF (&#36;{value:.0f}, {upside:+.0f}%)</b>: El flujo de caja libre descontado a 5 anos + valor terminal ({desc}) sugiere la accion esta <b>muy infravalorada</b>. Asume que el FCF actual crece al ritmo de los ingresos y se descuenta al 10% WACC.')
                elif upside > 0:
                    interpretations.append(f'<b style="color:#d29922;">DCF (&#36;{value:.0f}, {upside:+.0f}%)</b>: El DCF sugiere un descuento moderado. Los supuestos ({desc}) son conservadores — cambios en la tasa de crecimiento o WACC alteran significativamente el resultado.')
                else:
                    interpretations.append(f'<b style="color:#f85149;">DCF (&#36;{value:.0f}, {upside:+.0f}%)</b>: El precio actual ya descuenta un crecimiento superior al estimado. El mercado esta pagando una prima por expectativas de crecimiento futuro o por calidad del negocio.')
            elif name == "EPV (Greenwald)":
                if upside > 20:
                    interpretations.append(f'<b style="color:#3fb950;">EPV Greenwald (&#36;{value:.0f}, {upside:+.0f}%)</b>: El Earnings Power Value (beneficios normalizados / coste de capital) sugiere infravaloración. EPV mide el valor <b>sin crecimiento</b> — si hay upside, el mercado no esta pagando por el crecimiento.')
                elif upside < -20:
                    interpretations.append(f'<b style="color:#f85149;">EPV Greenwald (&#36;{value:.0f}, {upside:+.0f}%)</b>: El precio descuenta <b>mucho crecimiento futuro</b>. Si ese crecimiento no se materializa, hay riesgo de correccion significativa.')
                else:
                    interpretations.append(f'<b style="color:#d29922;">EPV Greenwald (&#36;{value:.0f}, {upside:+.0f}%)</b>: Precio alineado con el poder de beneficios actual. Rentabilidad futura dependera del crecimiento.')
            elif name == "Lynch Fair Value":
                if upside > 15:
                    interpretations.append(f'<b style="color:#3fb950;">Lynch Fair Value (&#36;{value:.0f}, {upside:+.0f}%)</b>: Segun Peter Lynch, un P/E justo iguala la tasa de crecimiento de beneficios. La accion cotiza por debajo de ese nivel — potencial <b>PEG favorable</b>.')
                elif upside < -15:
                    interpretations.append(f'<b style="color:#f85149;">Lynch Fair Value (&#36;{value:.0f}, {upside:+.0f}%)</b>: El mercado paga un P/E muy superior al crecimiento. Lynch evitaria esta accion a estos precios.')
                else:
                    interpretations.append(f'<b style="color:#d29922;">Lynch Fair Value (&#36;{value:.0f}, {upside:+.0f}%)</b>: Precio razonable segun el ratio PEG (P/E vs growth). Ni cara ni barata por este metodo.')
            elif name == "Implied Growth":
                actual_g = earnings_growth_rate
                if value > actual_g * 1.5 and actual_g > 0:
                    interpretations.append(f'<b style="color:#f85149;">Crecimiento implicito: {value:.0f}% CAGR</b> vs crecimiento real de BPA: {actual_g:.0f}%. El mercado esta descontando un crecimiento <b>muy superior al actual</b>. Si no se acelera, el P/E deberia comprimirse.')
                elif value < actual_g * 0.7 and actual_g > 0:
                    interpretations.append(f'<b style="color:#3fb950;">Crecimiento implicito: {value:.0f}% CAGR</b> vs crecimiento real de BPA: {actual_g:.0f}%. El mercado descuenta <b>menos crecimiento del real</b>. Si se mantiene el ritmo actual, el P/E podria expandirse.')
                else:
                    interpretations.append(f'<b style="color:#d29922;">Crecimiento implicito: {value:.0f}% CAGR</b> — alineado con el crecimiento actual ({actual_g:.0f}%). Precio razonablemente valorado por este metodo.')

        # Aggregate conclusion
        price_models = [r for r in model_results if r[0] != "Implied Growth"]
        if price_models:
            avg_upside = sum(r[2] for r in price_models) / len(price_models)
            bullish_count = sum(1 for r in price_models if r[2] > 10)
            bearish_count = sum(1 for r in price_models if r[2] < -10)

            if avg_upside > 20 and bullish_count >= len(price_models) * 0.6:
                verdict = f'<b style="color:#3fb950;">INFRAVALORADA</b> segun {bullish_count}/{len(price_models)} modelos (upside medio: {avg_upside:+.0f}%). Multiples metodologias coinciden en que el precio actual ofrece margen de seguridad.'
            elif avg_upside < -20 and bearish_count >= len(price_models) * 0.6:
                verdict = f'<b style="color:#f85149;">SOBREVALORADA</b> segun {bearish_count}/{len(price_models)} modelos (downside medio: {avg_upside:+.0f}%). La prima que paga el mercado requiere un crecimiento excepcional para justificarse.'
            elif avg_upside > 5:
                verdict = f'<b style="color:#d29922;">LIGERAMENTE INFRAVALORADA</b> (upside medio: {avg_upside:+.0f}%). Algunos modelos ven valor, otros estan neutrales.'
            elif avg_upside < -5:
                verdict = f'<b style="color:#d29922;">LIGERAMENTE SOBREVALORADA</b> (downside medio: {avg_upside:+.0f}%). No es extremo, pero el riesgo-retorno no es optimo.'
            else:
                verdict = f'<b style="color:#8b949e;">PRECIO JUSTO</b> (variacion media: {avg_upside:+.0f}%). Los modelos sugieren que el mercado esta valorando correctamente.'
            interpretations.append(f'<b style="color:#58a6ff;">Veredicto valoracion:</b> {verdict}')

        if interpretations:
            with st.expander("Interpretacion de modelos de valoracion", expanded=True):
                for interp in interpretations:
                    st.markdown(f'<div style="background:#161b22; padding:8px 12px; border-radius:6px; margin-bottom:4px; border-left:3px solid #30363d; font-size:0.78rem; color:#e6edf3; line-height:1.5;">{interp}</div>', unsafe_allow_html=True)
    else:
        st.info("Datos insuficientes para modelos de valoracion (se necesita EPS, Book Value y FCF)")

    # =========================================================================
    # ROW 3: INTELLIGENT ANALYSIS
    # =========================================================================
    st.markdown("---")
    st.markdown("### Analisis Inteligente")

    pe_val = data.get('pe_ratio', 0) or 0
    sector = data.get('sector', '')
    benchmarks = {'Technology': 30, 'Healthcare': 22, 'Financial Services': 14, 'Consumer Cyclical': 20, 'Energy': 12, 'Industrials': 18}
    bench = benchmarks.get(sector, 20)
    if pe_val and pe_val > 0:
        if pe_val > bench * 1.5:
            st.warning(f"**P/E:** {pe_val:.1f} MUY ALTO vs sector ({bench}). Requiere crecimiento excepcional.")
        elif pe_val < bench * 0.7:
            st.success(f"**P/E:** {pe_val:.1f} BAJO vs sector ({bench}). Posible oportunidad value.")
        else:
            st.info(f"**P/E:** {pe_val:.1f} en linea con sector ({bench}).")

    roe_val = data.get('roe', 0) or 0
    d2e_val = data.get('debt_to_equity', 0) or 0
    if roe_val:
        if roe_val > 25:
            extra = f" (cuidado: D/E alto {d2e_val:.0f}%)" if d2e_val and d2e_val > 150 else ""
            st.success(f"**ROE:** {roe_val:.1f}% EXCEPCIONAL{extra}. Ventajas competitivas fuertes.")
        elif roe_val > 15:
            st.info(f"**ROE:** {roe_val:.1f}% BUENO. Genera valor para accionistas.")
        elif roe_val > 0:
            st.warning(f"**ROE:** {roe_val:.1f}% BAJO. No supera costo de capital tipico.")
        else:
            st.error(f"**ROE:** {roe_val:.1f}% NEGATIVO. Destruye valor.")

    pm = data.get('profit_margin', 0) or 0
    if pm:
        if pm > 20:
            st.success(f"**Margen Neto:** {pm:.1f}% EXCELENTE. Muy rentable.")
        elif pm > 10:
            st.info(f"**Margen Neto:** {pm:.1f}% BUENO. Rentabilidad solida.")
        elif pm > 0:
            st.warning(f"**Margen Neto:** {pm:.1f}% BAJO. Poco margen de error.")
        else:
            st.error(f"**Margen Neto:** {pm:.1f}% NEGATIVO. Opera con perdidas.")

    # Debt analysis
    if debt_ebitda > 0:
        if debt_ebitda > 4:
            st.error(f"**Apalancamiento:** Deuda/EBITDA={debt_ebitda:.1f}x MUY ALTO. Riesgo de solvencia.")
        elif debt_ebitda > 2.5:
            st.warning(f"**Apalancamiento:** Deuda/EBITDA={debt_ebitda:.1f}x ELEVADO. Monitorear.")
        elif debt_ebitda > 0:
            st.success(f"**Apalancamiento:** Deuda/EBITDA={debt_ebitda:.1f}x CONTROLADO. Balance solido.")

    # FCF Yield commentary
    if fcf_yield > 0:
        if fcf_yield > 8:
            st.success(f"**FCF Yield:** {fcf_yield:.1f}% MUY ATRACTIVO. Genera mucho cash libre.")
        elif fcf_yield > 4:
            st.info(f"**FCF Yield:** {fcf_yield:.1f}% BUENO. Cash flow saludable.")
        elif fcf_yield > 0:
            st.warning(f"**FCF Yield:** {fcf_yield:.1f}% BAJO. Poca generacion de cash libre.")

    # Quality Rating (expanded)
    q_score = 0
    q_max = 0
    q_factors = []
    if roe_val:
        q_max += 1
        if roe_val > 15:
            q_score += 1
            q_factors.append(f"ROE alto ({roe_val:.1f}%)")
    if d2e_val is not None:
        q_max += 1
        if d2e_val < 100:
            q_score += 1
            q_factors.append(f"Deuda controlada ({d2e_val:.0f}%)")
    if pm:
        q_max += 1
        if pm > 10:
            q_score += 1
            q_factors.append(f"Buenos margenes ({pm:.1f}%)")
    if fcf_yield > 0:
        q_max += 1
        if fcf_yield > 4:
            q_score += 1
            q_factors.append(f"FCF Yield alto ({fcf_yield:.1f}%)")
    if cr > 0:
        q_max += 1
        if cr > 1.2:
            q_score += 1
            q_factors.append(f"Liquidez OK ({cr:.2f})")

    rating = "A" if q_score >= 4 else ("B" if q_score >= 3 else ("C" if q_score >= 2 else "D"))
    func = st.success if rating in ("A",) else (st.info if rating == "B" else (st.warning if rating == "C" else st.error))
    func(f"**Quality Rating: {rating}** ({q_score}/{q_max}) | {' | '.join(q_factors) if q_factors else 'Sin factores positivos destacados'}")


def _show_intelligence_tab(ticker: str, data: dict):
    """Intelligence tab: Congress + News + Analysts."""

    # Congress Activity (lazy-loaded)
    st.markdown("### 🏛 Actividad del Congreso")
    _load_congress = st.checkbox("Load Congress Trades", value=False, key=f"intel_congress_{ticker}",
                                  help="Click to load congress trading data")
    if not _load_congress:
        st.info("Click the checkbox above to load congress trading data for this ticker.")
        trades = pd.DataFrame()
    else:
        with st.spinner("Loading congress trades..."):
            trades = get_congress_trades_for_ticker(ticker, days=365)

    if not trades.empty:
        total = len(trades)
        buys = len(trades[trades['transaction_type'] == 'buy']) if 'transaction_type' in trades.columns else 0
        sells = len(trades[trades['transaction_type'] == 'sell']) if 'transaction_type' in trades.columns else 0
        pols = trades['politician'].nunique() if 'politician' in trades.columns else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Trades", str(total))
        with c2: st.metric("Compras", str(buys))
        with c3: st.metric("Ventas", str(sells))
        with c4: st.metric("Politicos", str(pols))

        # INSIDER ALERT: Committee-relevant trades
        if 'committee_relevant' in trades.columns:
            insider_trades = trades[trades['committee_relevant'] == True]
            if not insider_trades.empty:
                st.markdown(f"""
                <div style="background:rgba(248,81,73,0.1); border:1px solid rgba(248,81,73,0.3);
                            border-left:4px solid #f85149; padding:14px; border-radius:8px; margin:12px 0;">
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                        <span style="font-size:1.2rem;">🚨</span>
                        <span style="font-size:0.85rem; font-weight:700; color:#f85149; text-transform:uppercase; letter-spacing:0.5px;">
                            Privileged Info Alert — {len(insider_trades)} trade{'s' if len(insider_trades) > 1 else ''}
                        </span>
                    </div>
                    <div style="font-size:0.8rem; color:#e6edf3; line-height:1.6;">
                        Politicians trading <b style="color:#58a6ff;">{ticker}</b> while serving on committees overseeing this sector.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                for _, irow in insider_trades.head(5).iterrows():
                    pol_name = _esc(str(irow.get('politician', '')))
                    party = irow.get('party', '')
                    p_color = "#3B82F6" if party == 'D' else ("#EF4444" if party == 'R' else "#94a3b8")
                    tx = irow.get('transaction_type', '')
                    tx_color = "#3fb950" if 'buy' in str(tx).lower() else "#f85149"
                    tx_label = "BOUGHT" if 'buy' in str(tx).lower() else "SOLD"
                    reason = _esc(str(irow.get('relevance_reason', 'Committee sector overlap')))
                    amount = _esc(str(irow.get('amount_range', '')))
                    date_val = irow.get('traded_date', '')
                    date_str = str(date_val)[:10] if date_val else ''

                    st.markdown(f"""
                    <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:12px; margin:6px 0;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-weight:600; color:#e6edf3;">{pol_name}</span>
                                <span style="color:{p_color}; font-weight:600; margin-left:6px;">({party})</span>
                                <span style="color:{tx_color}; font-weight:700; margin-left:10px;">{tx_label}</span>
                                <span style="color:#8b949e; margin-left:6px;">{amount}</span>
                            </div>
                            <span style="color:#6e7681; font-size:0.75rem;">{date_str}</span>
                        </div>
                        <div style="font-size:0.75rem; color:#d29922; margin-top:6px;">
                            ⚠ {reason}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("")

        display_cols = ['politician', 'party', 'transaction_type', 'traded_date', 'amount_range']
        available = [c for c in display_cols if c in trades.columns]
        disp = trades[available].head(10).copy()
        if 'traded_date' in disp.columns:
            disp['traded_date'] = pd.to_datetime(disp['traded_date']).dt.strftime('%Y-%m-%d')

        # Build styled HTML table
        intel_rows = ""
        for _, row in disp.iterrows():
            pol = row.get('politician', '')
            party = row.get('party', '')
            p_color = "#3B82F6" if party == 'D' else ("#EF4444" if party == 'R' else "#94a3b8")
            tx = row.get('transaction_type', '')
            tx_color = "#10B981" if 'buy' in str(tx).lower() else "#EF4444"
            tx_label = "COMPRA" if 'buy' in str(tx).lower() else "VENTA"
            date = row.get('traded_date', '')
            amount = row.get('amount_range', '')
            # Highlight committee-relevant trades
            is_insider = False
            if 'committee_relevant' in trades.columns:
                orig_row = trades[(trades['politician'] == pol) & (trades['traded_date'].astype(str).str[:10] == str(date))]
                is_insider = not orig_row.empty and orig_row.iloc[0].get('committee_relevant', False)
            insider_badge = ' <span style="background:rgba(248,81,73,0.2);color:#f85149;padding:1px 5px;border-radius:4px;font-size:0.6rem;font-weight:600;">INSIDER</span>' if is_insider else ''
            intel_rows += f'''<tr>
                <td>{pol}{insider_badge}</td>
                <td><span style="color:{p_color};font-weight:600;">{party}</span></td>
                <td><span style="color:{tx_color};font-weight:600;">{tx_label}</span></td>
                <td>{date}</td><td>{amount}</td>
            </tr>'''

        intel_html = f'''<div style="border-radius:12px; overflow:hidden;">
        <table class="styled-table">
            <thead><tr><th>Politico</th><th>Partido</th><th>Tipo</th><th>Fecha</th><th>Monto</th></tr></thead>
            <tbody>{intel_rows}</tbody>
        </table></div>'''
        st.markdown(intel_html, unsafe_allow_html=True)

        if buys > sells:
            st.success(f"**Sesgo Congresistas: ALCISTA** ({buys}/{total} compras, {pols} politicos)")
        elif sells > buys:
            st.warning(f"**Sesgo Congresistas: BAJISTA** ({sells}/{total} ventas)")
        else:
            st.info("**Sesgo Congresistas: NEUTRAL**")
    else:
        st.info(f"Sin trades de congresistas para {ticker} en el ultimo ano")

    st.markdown("---")

    # Analyst Ratings
    st.markdown("### Ratings de Analistas")
    target_price = data.get('target_price')
    recommendation = data.get('recommendation', 'N/A')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Precio Actual", f"${data['price']:.2f}")
    with c2:
        if target_price:
            upside = ((target_price - data['price']) / data['price']) * 100 if data['price'] > 0 else 0
            st.metric("Target Medio", f"${target_price:.2f}", f"{upside:+.1f}%")
        else:
            st.metric("Target Medio", "N/A")
    with c3:
        if recommendation:
            rec = str(recommendation).upper()
            if 'BUY' in rec: st.success(f"Consenso: {recommendation}")
            elif 'HOLD' in rec: st.warning(f"Consenso: {recommendation}")
            else: st.error(f"Consenso: {recommendation}")

    st.markdown("---")

    # News
    st.markdown("### Noticias Recientes")
    news_list = data.get('news', [])
    if news_list:
        for news_item in news_list[:5]:
            try:
                title = news_item.get('title', news_item.get('content', {}).get('title', 'Sin titulo'))
                publisher = news_item.get('publisher', news_item.get('content', {}).get('provider', {}).get('displayName', ''))
                link = news_item.get('link', news_item.get('content', {}).get('clickThroughUrl', {}).get('url', '#'))
                title_lower = title.lower()
                if any(w in title_lower for w in ['down', 'fall', 'drop', 'loss', 'crash', 'warning']):
                    border_color = "#EF4444"
                elif any(w in title_lower for w in ['up', 'rise', 'gain', 'rally', 'surge', 'beat']):
                    border_color = "#10B981"
                else:
                    border_color = "#6366f1"

                st.markdown(f"""
                <div style="background:#16213e; padding:10px 14px; border-radius:6px; margin-bottom:6px; border-left:3px solid {border_color};">
                    <a href="{link}" target="_blank" style="color:#e0e0e0; text-decoration:none;">{title}</a>
                    <div style="font-size:0.7rem; color:#888; margin-top:3px;">{publisher}</div>
                </div>
                """, unsafe_allow_html=True)
            except Exception:
                continue
    else:
        st.info("Sin noticias recientes")


# =============================================================================
# PAGE 3: SIGNALS (Congress + Polymarket)
# =============================================================================
def show_signals():
    """Merged Congress Trades + Polymarket Smart Money."""
    st.markdown('<p class="main-header">🔍 Signals & Intelligence</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Congress insider trades + Polymarket smart money</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🏛 Congress Insider Trades", "🎲 Polymarket Smart Money"])

    with tab1:
        _show_congress_tab()

    with tab2:
        _show_polymarket_tab()


def _show_congress_tab():
    """Full congress trades view."""
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pol_filter = st.text_input("Buscar politico", "")
    with col2:
        chamber_filter = st.selectbox("Camara", ["All", "House", "Senate"])
    with col3:
        party_filter = st.selectbox("Partido", ["All", "Democrat", "Republican"])
    with col4:
        tx_filter = st.selectbox("Tipo", ["All", "Buy", "Sell"])

    col1, col2, col3 = st.columns(3)
    with col1:
        days_opts = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "1 ano": 365}
        days_filter = st.selectbox("Periodo", list(days_opts.keys()), index=2)
        days_val = days_opts[days_filter]
    with col2:
        issuer_filter = st.text_input("Buscar ticker", "")
    with col3:
        if st.button("Actualizar"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    all_trades = get_congress_trades(days=days_val)

    if not all_trades.empty:
        filtered = filter_congress_trades(all_trades, politician=pol_filter, chamber=chamber_filter,
                                          party=party_filter, transaction_type=tx_filter, ticker=issuer_filter, days=days_val)

        total = len(filtered)
        buys = len(filtered[filtered['transaction_type'] == 'buy']) if 'transaction_type' in filtered.columns else 0
        sells = len(filtered[filtered['transaction_type'] == 'sell']) if 'transaction_type' in filtered.columns else 0
        politicians = filtered['politician'].nunique() if 'politician' in filtered.columns else 0
        tickers = filtered['ticker'].nunique() if 'ticker' in filtered.columns else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Total", f"{total:,}")
        with c2: st.metric("Compras", f"{buys:,}")
        with c3: st.metric("Ventas", f"{sells:,}")
        with c4: st.metric("Politicos", str(politicians))
        with c5: st.metric("Tickers", str(tickers))

        st.markdown("---")

        if not filtered.empty:
            # Insider signals
            if 'committee_relevant' in filtered.columns:
                insider_trades = filtered[filtered['committee_relevant'] == True]
                if not insider_trades.empty:
                    st.markdown("### ⚠ INSIDER SIGNALS")
                    st.markdown("""
                    <div style="background:#2d1f1f; padding:8px; border-radius:5px; border-left:4px solid #ff6b6b; margin-bottom:10px;">
                    <b>Trades de politicos en sectores de sus comites.</b>
                    </div>
                    """, unsafe_allow_html=True)
                    ins_cols = ['politician', 'ticker', 'company', 'transaction_type', 'traded_date', 'amount_range', 'relevance_reason']
                    ins_avail = [c for c in ins_cols if c in insider_trades.columns]
                    ins_disp = insider_trades[ins_avail].head(10).copy()
                    if 'traded_date' in ins_disp.columns:
                        ins_disp['traded_date'] = pd.to_datetime(ins_disp['traded_date']).dt.strftime('%Y-%m-%d')
                    ins_rows = ""
                    for _, r in ins_disp.iterrows():
                        tx = r.get('transaction_type', '')
                        tx_c = "#10B981" if 'buy' in str(tx).lower() else "#EF4444"
                        ins_rows += f'''<tr>
                            <td>{r.get('politician','')}</td>
                            <td><b style="color:#60a5fa;">{r.get('ticker','')}</b></td>
                            <td style="color:#94a3b8;font-size:0.75rem;">{str(r.get('company',''))[:25]}</td>
                            <td><span style="color:{tx_c};font-weight:600;">{"COMPRA" if "buy" in str(tx).lower() else "VENTA"}</span></td>
                            <td>{r.get('traded_date','')}</td>
                            <td>{r.get('amount_range','')}</td>
                        </tr>'''
                    st.markdown(f'''<table class="styled-table"><thead><tr>
                        <th>Politico</th><th>Ticker</th><th>Empresa</th><th>Tipo</th><th>Fecha</th><th>Monto</th>
                    </tr></thead><tbody>{ins_rows}</tbody></table>''', unsafe_allow_html=True)
                    st.markdown("---")

            # All trades table - styled HTML
            st.subheader(f"Todos los Trades ({len(filtered)})")
            display_cols = ['politician', 'party', 'chamber', 'ticker', 'company', 'transaction_type',
                            'traded_date', 'price_change', 'excess_return', 'amount_range']
            available = [c for c in display_cols if c in filtered.columns]
            disp = filtered[available].head(50).copy()
            if 'traded_date' in disp.columns:
                disp['traded_date'] = pd.to_datetime(disp['traded_date']).dt.strftime('%Y-%m-%d')

            # Build styled HTML table
            congress_rows = ""
            for _, row in disp.iterrows():
                pol = row.get('politician', '')
                party = row.get('party', '')
                party_color = "#3B82F6" if party == 'D' else ("#EF4444" if party == 'R' else "#94a3b8")
                party_label = f'<span style="color:{party_color};font-weight:600;">{party}</span>'
                chamber = row.get('chamber', '')
                tk = row.get('ticker', '')
                company = row.get('company', '')[:20] if row.get('company') else ''
                tx = row.get('transaction_type', '')
                tx_color = "#10B981" if 'buy' in str(tx).lower() else "#EF4444"
                tx_label = f'<span style="color:{tx_color};font-weight:600;">{"COMPRA" if "buy" in str(tx).lower() else "VENTA"}</span>'
                date = row.get('traded_date', '')
                perf = row.get('price_change', None)
                if pd.notna(perf) and perf is not None:
                    try:
                        perf = float(perf)
                        if perf > 5: perf_html = f'<span style="color:#10B981;font-weight:600;">+{perf:.1f}%</span>'
                        elif perf > 0: perf_html = f'<span style="color:#3B82F6;">+{perf:.1f}%</span>'
                        elif perf > -5: perf_html = f'<span style="color:#F59E0B;">{perf:.1f}%</span>'
                        else: perf_html = f'<span style="color:#EF4444;">{perf:.1f}%</span>'
                    except (ValueError, TypeError):
                        perf_html = ''
                else:
                    perf_html = ''
                amount = row.get('amount_range', '')

                congress_rows += f'''<tr>
                    <td>{pol}</td><td>{party_label}</td><td>{chamber}</td>
                    <td><b style="color:#60a5fa;">{tk}</b></td><td style="color:#94a3b8;font-size:0.75rem;">{company}</td>
                    <td>{tx_label}</td><td>{date}</td><td>{perf_html}</td><td>{amount}</td>
                </tr>'''

            congress_html = f'''<div style="max-height:500px; overflow-y:auto; border-radius:12px;">
            <table class="styled-table">
                <thead><tr>
                    <th>Politico</th><th>Partido</th><th>Camara</th><th>Ticker</th><th>Empresa</th>
                    <th>Tipo</th><th>Fecha</th><th>Perf</th><th>Monto</th>
                </tr></thead>
                <tbody>{congress_rows}</tbody>
            </table></div>'''
            st.markdown(congress_html, unsafe_allow_html=True)

        # Rankings
        st.markdown("---")
        c1, c2 = st.columns(2)
        top = get_top_traded_tickers(days=days_val, top_n=10)
        with c1:
            st.markdown(f"### Mas Comprados ({days_filter})")
            if not top['buys'].empty:
                buy_rows = ""
                for _, r in top['buys'].iterrows():
                    buy_rows += f'<tr><td><b style="color:#10B981;">{r["Ticker"]}</b></td><td>{r.get("Políticos", "")}</td><td style="color:#10B981;font-weight:600;">{r.get("Compras", "")}</td></tr>'
                st.markdown(f'''<table class="styled-table"><thead><tr><th>Ticker</th><th>Politicos</th><th>Compras</th></tr></thead><tbody>{buy_rows}</tbody></table>''', unsafe_allow_html=True)
        with c2:
            st.markdown(f"### Mas Vendidos ({days_filter})")
            if not top['sells'].empty:
                sell_rows = ""
                for _, r in top['sells'].iterrows():
                    sell_rows += f'<tr><td><b style="color:#EF4444;">{r["Ticker"]}</b></td><td>{r.get("Políticos", "")}</td><td style="color:#EF4444;font-weight:600;">{r.get("Ventas", "")}</td></tr>'
                st.markdown(f'''<table class="styled-table"><thead><tr><th>Ticker</th><th>Politicos</th><th>Ventas</th></tr></thead><tbody>{sell_rows}</tbody></table>''', unsafe_allow_html=True)
    else:
        st.info("Sin trades de congresistas disponibles")


def _show_polymarket_tab():
    """Polymarket smart money detection with insider bet analysis."""
    try:
        import importlib.util
        polymarket_path = ROOT_DIR / 'integrations' / 'polymarket_client.py'
        if not polymarket_path.exists():
            st.info("Polymarket no disponible")
            return
        spec = importlib.util.spec_from_file_location("polymarket_client", polymarket_path)
        polymarket_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(polymarket_module)
        client = polymarket_module.PolymarketClient()
    except Exception as e:
        st.error(f"Error cargando Polymarket: {e}")
        return

    if st.button("Actualizar Datos", key="poly_refresh"):
        st.cache_data.clear()
        st.rerun()

    # =========================================================================
    # SECTION 1: SUSPICIOUS BETS (Insider Detection)
    # =========================================================================
    st.markdown("---")
    st.markdown("""
    <div style="background:linear-gradient(135deg, rgba(239,68,68,0.12), rgba(249,115,22,0.08));
                border:1px solid rgba(239,68,68,0.3); border-radius:12px; padding:16px; margin-bottom:16px;">
        <div style="font-size:1.1rem; font-weight:700; color:#f87171; margin-bottom:4px;">
            🕵 Deteccion de Info Privilegiada
        </div>
        <div style="font-size:0.8rem; color:#94a3b8;">
            Identifica apuestas con patrones sospechosos: volumen concentrado en 24h,
            odds extremas, mercados con fechas especificas y actividad whale.
            Ejemplo: alguien aposto $400k a que Maduro seria detenido un dia concreto.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Analizando apuestas sospechosas..."):
        try:
            suspicious = client.detect_suspicious_bets()
            if suspicious:
                # Metrics
                c1, c2, c3, c4 = st.columns(4)
                high_sus = len([s for s in suspicious if s['suspicion_score'] >= 70])
                med_sus = len([s for s in suspicious if 50 <= s['suspicion_score'] < 70])
                total_vol = sum(s['volume_24h'] for s in suspicious)
                with c1: st.metric("Muy Sospechosas", high_sus)
                with c2: st.metric("Sospechosas", med_sus)
                with c3: st.metric("Total Detectadas", len(suspicious))
                with c4: st.metric("Vol Agregado 24h", f"${total_vol/1000:.0f}k")

                for i, bet in enumerate(suspicious):
                    sus_score = bet['suspicion_score']
                    if sus_score >= 70:
                        border_color = '#EF4444'
                        level_label = 'MUY SOSPECHOSA'
                        level_emoji = '🔴'
                    elif sus_score >= 50:
                        border_color = '#f97316'
                        level_label = 'SOSPECHOSA'
                        level_emoji = '🟠'
                    else:
                        border_color = '#F59E0B'
                        level_label = 'VIGILAR'
                        level_emoji = '🟡'

                    # Odds bar
                    odds = bet.get('odds', {})
                    odds_html = ""
                    for outcome, pct in odds.items():
                        bar_color = '#10B981' if pct > 60 else ('#F59E0B' if pct > 40 else '#94a3b8')
                        odds_html += f'<span style="color:{bar_color};font-weight:600;margin-right:12px;">{_esc(outcome)}: {pct:.0f}%</span>'

                    tickers = bet.get('relevant_tickers', [])
                    tickers_html = f'<span style="color:#60a5fa;font-size:0.8rem;">Tickers: {", ".join(tickers[:4])}</span>' if tickers else ''

                    reasons_html = _esc(" | ".join(bet.get('reasons', [])[:3]))
                    question_safe = _esc(bet['question'])

                    vol_24h_str = f"&#36;{bet['volume_24h']:,.0f}"
                    vol_total_str = f"&#36;{bet['volume_total']:,.0f}"
                    liq_str = f"&#36;{bet['liquidity']:,.0f}"

                    st.markdown(f"""
                    <div style="background:#161b22;
                                border:1px solid {border_color}; border-left:4px solid {border_color};
                                border-radius:10px; padding:14px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <span style="font-weight:700; font-size:0.9rem; color:#e2e8f0;">{level_emoji} {question_safe}</span>
                            <span style="background:{border_color}; color:white; padding:2px 10px; border-radius:12px; font-size:0.7rem; font-weight:600;">
                                {level_label} ({sus_score}/100)
                            </span>
                        </div>
                        <div style="display:flex; gap:20px; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
                            <span style="font-size:0.85rem; color:#e2e8f0;">
                                Vol 24h: <b style="color:{border_color};">{vol_24h_str}</b>
                            </span>
                            <span style="font-size:0.85rem; color:#94a3b8;">
                                Vol Total: {vol_total_str}
                            </span>
                            <span style="font-size:0.85rem; color:#94a3b8;">
                                Liquidez: {liq_str}
                            </span>
                            {tickers_html}
                        </div>
                        <div style="margin-bottom:4px;">{odds_html}</div>
                        <div style="font-size:0.75rem; color:#f97316;">{reasons_html}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No se detectaron apuestas sospechosas actualmente")
        except Exception as e:
            st.error(f"Error detectando apuestas sospechosas: {e}")

    # =========================================================================
    # SECTION 2: SMART MONEY ALERTS (Volume-based)
    # =========================================================================
    st.markdown("---")
    st.markdown("### Smart Money Alerts")
    st.caption("Mercados relevantes con volumen 24h significativo")

    with st.spinner("Buscando Smart Money..."):
        try:
            alerts = client.detect_smart_money_alerts()
            if alerts:
                # Build table
                alert_rows = ""
                for alert in alerts[:15]:
                    level = alert['alert_level']
                    level_color = '#EF4444' if level == 'HIGH' else ('#F59E0B' if level == 'MEDIUM' else '#94a3b8')
                    level_emoji = '🔴' if level == 'HIGH' else ('🟡' if level == 'MEDIUM' else '🔵')
                    tickers = ', '.join(alert.get('relevant_tickers', [])[:3])
                    odds_str = ', '.join([f'{k}:{v:.0f}%' for k, v in alert.get('current_odds', {}).items()])
                    market_name = _esc(alert['market'][:80])
                    vol_str = _esc(str(alert['volume_24h']))
                    alert_rows += f'''<tr>
                        <td><span style="color:{level_color};font-weight:600;">{level_emoji} {level}</span></td>
                        <td style="max-width:300px;">{market_name}</td>
                        <td style="color:{level_color};font-weight:600;">{vol_str}</td>
                        <td style="font-size:0.75rem;">{odds_str}</td>
                        <td style="color:#60a5fa;font-size:0.8rem;">{tickers}</td>
                    </tr>'''
                st.markdown(f'''<div style="border-radius:12px; overflow:hidden; max-height:400px; overflow-y:auto;">
                <table class="styled-table">
                    <thead><tr><th>Nivel</th><th>Mercado</th><th>Vol 24h</th><th>Odds</th><th>Tickers</th></tr></thead>
                    <tbody>{alert_rows}</tbody>
                </table></div>''', unsafe_allow_html=True)
            else:
                st.info("Sin alertas de smart money actualmente")
        except Exception as e:
            st.error(f"Error: {e}")

    # =========================================================================
    # SECTION 3: RELEVANT MARKETS
    # =========================================================================
    st.markdown("---")
    st.markdown("### Mercados Relevantes para Inversion")
    with st.spinner("Cargando mercados..."):
        try:
            markets = client.get_relevant_markets(limit=20)
            if markets:
                market_rows = ""
                for market in markets[:15]:
                    question = _esc(market.get('question', '')[:90])
                    try:
                        volume = float(market.get('volume', 0) or 0)
                        vol_24h = float(market.get('volume24hr', 0) or 0)
                    except (ValueError, TypeError):
                        volume = 0.0
                        vol_24h = 0.0
                    odds = client._get_current_odds(market)
                    odds_str = ', '.join([f'{k}:{v:.0f}%' for k, v in odds.items()]) if odds else 'N/A'
                    tickers = market.get('impact_analysis', {}).get('relevant_tickers', []) if isinstance(market.get('impact_analysis'), dict) else []
                    sector = market.get('impact_analysis', {}).get('sector', '') if isinstance(market.get('impact_analysis'), dict) else ''
                    tickers_str = ', '.join(tickers[:3])

                    market_rows += f'''<tr>
                        <td style="max-width:280px;">{question}</td>
                        <td style="font-size:0.75rem;">{odds_str}</td>
                        <td>&#36;{volume/1000:.0f}k</td>
                        <td>&#36;{vol_24h/1000:.0f}k</td>
                        <td style="color:#60a5fa;">{tickers_str}</td>
                        <td style="color:#94a3b8;font-size:0.75rem;">{sector}</td>
                    </tr>'''
                st.markdown(f'''<div style="border-radius:12px; overflow:hidden; max-height:500px; overflow-y:auto;">
                <table class="styled-table">
                    <thead><tr><th>Mercado</th><th>Odds</th><th>Vol Total</th><th>Vol 24h</th><th>Tickers</th><th>Sector</th></tr></thead>
                    <tbody>{market_rows}</tbody>
                </table></div>''', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error: {e}")


if __name__ == "__main__":
    main()

