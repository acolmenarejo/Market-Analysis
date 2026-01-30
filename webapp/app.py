"""
Market Analysis Web App - Main Entry Point
==========================================
App web para análisis de mercado con:
- Trades de congresistas (Capitol Trades)
- Scoring multi-horizonte (corto/medio/largo)
- Análisis técnico avanzado (Wyckoff, Volume Profile, VWAP)
- Ratios financieros completos

Ejecutar con: streamlit run webapp/app.py
"""

import streamlit as st
import pandas as pd
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
)

# Import config
from webapp.config import TICKER_UNIVERSE, HIGH_PROFILE_POLITICIANS


# Page config
st.set_page_config(
    page_title="Market Analysis Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A5F;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-top: 0;
    }
    .buy-signal { background-color: #10B981; color: white; padding: 5px 10px; border-radius: 5px; }
    .sell-signal { background-color: #EF4444; color: white; padding: 5px 10px; border-radius: 5px; }
    .hold-signal { background-color: #F59E0B; color: white; padding: 5px 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)


def main():
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/stocks.png", width=80)
        st.title("Market Analysis Pro")
        st.markdown("---")

        page = st.radio(
            "Navegación",
            [
                "🏠 Dashboard",
                "🏛️ Congress Trades",
                "📊 Stock Analysis",
                "🎯 Multi-Horizon Scoring",
                "💧 Monetary Plumbing",
                "⚙️ Settings"
            ]
        )

        st.markdown("---")
        st.markdown("### Filtros Globales")

        timeframe = st.selectbox(
            "Horizonte",
            ["Corto Plazo (1-4 sem)", "Medio Plazo (1-6 mes)", "Largo Plazo (6+ mes)"]
        )

        min_score = st.slider("Score mínimo", 0, 100, 50)

        st.markdown("---")
        st.caption("v2.1 - Datos Dinámicos")

    # Main content
    if "Dashboard" in page:
        show_dashboard()
    elif "Congress Trades" in page:
        show_congress_trades()
    elif "Stock Analysis" in page:
        show_stock_analysis()
    elif "Multi-Horizon" in page:
        show_multi_horizon_scoring()
    elif "Monetary" in page:
        show_monetary_plumbing()
    elif "Settings" in page:
        show_settings()


def show_dashboard():
    """Dashboard principal con datos dinámicos"""
    st.markdown('<p class="main-header">📈 Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Resumen ejecutivo del mercado - Datos en tiempo real</p>', unsafe_allow_html=True)

    # Cargar datos
    with st.spinner("Cargando datos del mercado..."):
        vix_data = get_vix()
        congress_stats = get_congress_stats(days=7)
        monetary = get_monetary_data()

    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        net_liq = monetary.get('net_liquidity', {})
        liq_value = net_liq.get('current', 5800) if isinstance(net_liq, dict) else 5800
        liq_change = net_liq.get('change_1m', 0) if isinstance(net_liq, dict) else 0
        st.metric("Liquidez Neta", f"${liq_value/1000:.1f}T", f"{liq_change:+.1f}%")

    with col2:
        st.metric("VIX", f"{vix_data['current']:.1f}", f"{vix_data['change']:+.1f}", delta_color="inverse")

    with col3:
        st.metric("Congress Trades (7d)", str(congress_stats['total_trades']),
                  f"+{congress_stats['buys']} buys")

    with col4:
        regime = monetary.get('regime', {})
        regime_name = regime.get('name', 'N/A') if isinstance(regime, dict) else 'N/A'
        st.metric("Régimen", regime_name, "Risk-On" if regime_name == "ABUNDANT" else "Risk-Off")

    st.markdown("---")

    # Top Picks
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚀 Top Picks Corto Plazo")
        st.info("Stocks con mejor score técnico + momentum")

        with st.spinner("Calculando scores corto plazo..."):
            # Tickers de tech/momentum para corto plazo
            short_term_tickers = ['NVDA', 'AVGO', 'MSFT', 'META', 'GOOGL', 'AMD', 'CRM']
            scores_df = get_multi_horizon_scores(short_term_tickers)

            if not scores_df.empty:
                scores_df = scores_df.sort_values('Score CP', ascending=False).head(5)
                st.dataframe(
                    scores_df[['Ticker', 'Score CP', 'Señal CP']].rename(columns={
                        'Score CP': 'Score',
                        'Señal CP': 'Señal'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("No se pudieron cargar los scores")

    with col2:
        st.subheader("🏛️ Top Picks Largo Plazo")
        st.info("Stocks infravalorados con alta calidad")

        with st.spinner("Calculando scores largo plazo..."):
            # Tickers defensivos/value para largo plazo
            long_term_tickers = ['GILD', 'BMY', 'PFE', 'JNJ', 'PG', 'KO', 'UNH']
            scores_df = get_multi_horizon_scores(long_term_tickers)

            if not scores_df.empty:
                scores_df = scores_df.sort_values('Score LP', ascending=False).head(5)
                st.dataframe(
                    scores_df[['Ticker', 'Score LP', 'Señal LP']].rename(columns={
                        'Score LP': 'Score',
                        'Señal LP': 'Señal'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("No se pudieron cargar los scores")

    st.markdown("---")

    # Congress Trades recientes
    st.subheader("🏛️ Congress Trades Más Recientes")

    with st.spinner("Cargando trades de congresistas..."):
        trades_df = get_congress_trades(days=30)

        if not trades_df.empty:
            # Mostrar las 10 más recientes (ordenados por disclosed_date = fecha de filing)
            if 'disclosed_date' in trades_df.columns:
                trades_df_sorted = trades_df.sort_values('disclosed_date', ascending=False)
            else:
                trades_df_sorted = trades_df

            display_cols = ['politician', 'ticker', 'transaction_type', 'disclosed_date',
                           'traded_date', 'price_change', 'amount_range']
            available_cols = [c for c in display_cols if c in trades_df_sorted.columns]

            recent = trades_df_sorted.head(10)[available_cols].copy()

            # Formatear fechas
            if 'traded_date' in recent.columns:
                recent['traded_date'] = pd.to_datetime(recent['traded_date']).dt.strftime('%Y-%m-%d')
            if 'disclosed_date' in recent.columns:
                recent['disclosed_date'] = pd.to_datetime(recent['disclosed_date']).dt.strftime('%Y-%m-%d')

            # Formatear performance
            if 'price_change' in recent.columns:
                def fmt_perf(val):
                    if pd.isna(val) or val is None:
                        return ''
                    if val > 5:
                        return f'🟢 +{val:.1f}%'
                    elif val > 0:
                        return f'🔵 +{val:.1f}%'
                    elif val > -5:
                        return f'🟡 {val:.1f}%'
                    else:
                        return f'🔴 {val:.1f}%'
                recent['price_change'] = recent['price_change'].apply(fmt_perf)

            col_renames = {
                'politician': 'Político',
                'ticker': 'Ticker',
                'transaction_type': 'Tipo',
                'disclosed_date': 'Filed',
                'traded_date': 'Traded',
                'price_change': 'Perf',
                'amount_range': 'Monto'
            }
            recent = recent.rename(columns={k: v for k, v in col_renames.items() if k in recent.columns})
            st.dataframe(recent, use_container_width=True, hide_index=True)
        else:
            st.warning("No se encontraron trades recientes")

    # =========================================================================
    # ALL STOCKS TABLE WITH SCORES
    # =========================================================================
    st.markdown("---")
    st.subheader("📊 Todos los Stocks - Scores Multi-Horizonte")
    st.info("Tabla completa con scores para todos los tickers del universo. Los scores van de 0-100.")

    # Horizon selector
    col1, col2 = st.columns([1, 3])
    with col1:
        horizon_view = st.selectbox(
            "Ordenar por horizonte",
            ["Corto Plazo", "Medio Plazo", "Largo Plazo"],
            key="dashboard_horizon"
        )

    # Load all tickers scores using cached batch function
    with st.spinner("Calculando scores para todos los tickers..."):
        all_tickers = tuple(TICKER_UNIVERSE)  # Convert to tuple for caching
        all_scores_df = get_all_scores_batch(all_tickers)

    if not all_scores_df.empty:
        # Sort by selected horizon
        if "Corto" in horizon_view:
            sort_col = 'Score CP'
            signal_col = 'Señal CP'
        elif "Medio" in horizon_view:
            sort_col = 'Score MP'
            signal_col = 'Señal MP'
        else:
            sort_col = 'Score LP'
            signal_col = 'Señal LP'

        # Sort and prepare display
        sorted_df = all_scores_df.sort_values(sort_col, ascending=False).copy()

        # Add action column based on signal
        def get_action(signal):
            signal_upper = str(signal).upper()
            if 'STRONG_BUY' in signal_upper:
                return '🚀 COMPRAR FUERTE'
            elif 'BUY' in signal_upper:
                return '✅ COMPRAR'
            elif 'ACCUMULATE' in signal_upper:
                return '📈 ACUMULAR'
            elif 'HOLD' in signal_upper:
                return '⏸️ MANTENER'
            elif 'REDUCE' in signal_upper:
                return '📉 REDUCIR'
            elif 'SELL' in signal_upper:
                return '🔴 VENDER'
            else:
                return '⏸️ ESPERAR'

        sorted_df['Acción'] = sorted_df[signal_col].apply(get_action)

        # Display columns based on horizon view
        if "Corto" in horizon_view:
            display_cols = ['Ticker', 'Empresa', 'Sector', 'Precio', 'Score CP', 'Señal CP', 'Acción']
        elif "Medio" in horizon_view:
            display_cols = ['Ticker', 'Empresa', 'Sector', 'Precio', 'Score MP', 'Señal MP', 'Acción']
        else:
            display_cols = ['Ticker', 'Empresa', 'Sector', 'Precio', 'Score LP', 'Señal LP', 'Acción']

        # Add all three scores columns for comparison
        display_cols_full = ['Ticker', 'Empresa', 'Sector', 'Precio',
                            'Score CP', 'Señal CP', 'Score MP', 'Señal MP', 'Score LP', 'Señal LP', 'Acción']

        available_cols = [c for c in display_cols_full if c in sorted_df.columns]

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        strong_buys = len(sorted_df[sorted_df[signal_col].str.contains('STRONG_BUY', case=False, na=False)])
        buys = len(sorted_df[sorted_df[signal_col].str.contains('BUY', case=False, na=False)])
        sells = len(sorted_df[sorted_df[signal_col].str.contains('SELL', case=False, na=False)])
        avg_score = sorted_df[sort_col].mean()

        with col1:
            st.metric("Strong Buys", f"{strong_buys}")
        with col2:
            st.metric("Total Buys", f"{buys}")
        with col3:
            st.metric("Sells", f"{sells}")
        with col4:
            st.metric("Score Medio", f"{avg_score:.1f}")

        # Show the table
        st.dataframe(
            sorted_df[available_cols],
            use_container_width=True,
            hide_index=True,
            height=500
        )

        # Export button
        csv = sorted_df[available_cols].to_csv(index=False)
        st.download_button(
            label="📥 Exportar a CSV",
            data=csv,
            file_name=f"stocks_scores_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("No se pudieron cargar los scores. Intenta refrescar la página.")


def show_congress_trades():
    """Vista de Congress Trades con datos dinámicos"""
    st.markdown('<p class="main-header">🏛️ Congress Trades</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Trades de congresistas de EEUU - Datos en tiempo real</p>', unsafe_allow_html=True)

    # Filtros PRIMERO (para que las métricas reflejen los filtros)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        politician_filter = st.text_input("🔍 Buscar político", "")
    with col2:
        chamber_filter = st.selectbox("Congress Chamber", ["All", "House", "Senate"])
    with col3:
        party_filter = st.selectbox("Partido", ["All", "Democrat", "Republican"])
    with col4:
        transaction_type = st.selectbox("Tipo", ["All", "Buy", "Sell"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        days_options = {"7 días": 7, "30 días": 30, "90 días": 90, "1 año": 365}
        days_filter = st.selectbox("Período", list(days_options.keys()), index=2)  # Default 90 días
        days_value = days_options[days_filter]
    with col2:
        issuer_filter = st.text_input("🔍 Buscar ticker/empresa", "")
    with col3:
        pass
    with col4:
        if st.button("🔄 Actualizar datos"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # Cargar todos los trades y aplicar filtros
    with st.spinner("Cargando trades..."):
        all_trades = get_congress_trades(days=days_value)

        if not all_trades.empty:
            filtered = filter_congress_trades(
                all_trades,
                politician=politician_filter,
                chamber=chamber_filter,
                party=party_filter,
                transaction_type=transaction_type,
                ticker=issuer_filter,
                days=days_value
            )

            # Métricas basadas en datos FILTRADOS
            total = len(filtered)
            buys = len(filtered[filtered['transaction_type'] == 'buy']) if 'transaction_type' in filtered.columns else 0
            sells = len(filtered[filtered['transaction_type'] == 'sell']) if 'transaction_type' in filtered.columns else 0
            politicians = filtered['politician'].nunique() if 'politician' in filtered.columns else 0
            tickers = filtered['ticker'].nunique() if 'ticker' in filtered.columns else 0
        else:
            filtered = pd.DataFrame()
            total = buys = sells = politicians = tickers = 0

    # Métricas (ahora reflejan los filtros aplicados)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Trades", f"{total:,}")
    with col2:
        st.metric("Compras", f"{buys:,}")
    with col3:
        st.metric("Ventas", f"{sells:,}")
    with col4:
        st.metric("Políticos", str(politicians))
    with col5:
        st.metric("Tickers", str(tickers))

    st.markdown("---")

    # Mostrar tabla de trades (ya tenemos filtered del bloque anterior)
    if not filtered.empty:
        # Destacar trades con relevancia de comité (INSIDER SIGNAL)
        if 'committee_relevant' in filtered.columns:
            insider_trades = filtered[filtered['committee_relevant'] == True]
            if not insider_trades.empty:
                st.markdown("### ⚠️ INSIDER SIGNALS - Trades en Área de Influencia")
                st.markdown("""
                <div style="background-color: #2d1f1f; padding: 10px; border-radius: 5px; border-left: 4px solid #ff6b6b; margin-bottom: 15px;">
                <b>Estos trades son de políticos operando en sectores relacionados con sus comités.</b>
                Por ejemplo: Kevin Hern (Ways & Means/Healthcare) vendiendo UNH.
                </div>
                """, unsafe_allow_html=True)

                insider_display = insider_trades[['politician', 'ticker', 'company', 'transaction_type',
                                                   'traded_date', 'amount_range', 'relevance_reason']].head(10).copy()
                if 'traded_date' in insider_display.columns:
                    insider_display['traded_date'] = pd.to_datetime(insider_display['traded_date']).dt.strftime('%Y-%m-%d')

                insider_display = insider_display.rename(columns={
                    'politician': 'Político',
                    'ticker': 'Ticker',
                    'company': 'Empresa',
                    'transaction_type': 'Tipo',
                    'traded_date': 'Fecha',
                    'amount_range': 'Monto',
                    'relevance_reason': 'Razón'
                })
                st.dataframe(insider_display, use_container_width=True, hide_index=True)
                st.markdown("---")

        st.subheader(f"Todos los Trades ({len(filtered)} resultados)")

        # Preparar para mostrar - sin límite, mostrar todos
        display_cols = ['politician', 'party', 'chamber', 'ticker', 'company',
                       'transaction_type', 'disclosed_date', 'traded_date', 'price_change',
                       'excess_return', 'amount_range', 'committee_relevant', 'source']
        available_cols = [c for c in display_cols if c in filtered.columns]

        display_df = filtered[available_cols].copy()  # Mostrar TODOS los trades

        # Formatear fechas
        if 'traded_date' in display_df.columns:
            display_df['traded_date'] = pd.to_datetime(display_df['traded_date']).dt.strftime('%Y-%m-%d')
        if 'disclosed_date' in display_df.columns:
            display_df['disclosed_date'] = pd.to_datetime(display_df['disclosed_date']).dt.strftime('%Y-%m-%d')

        # Formatear performance con colores usando emoji indicators
        if 'price_change' in display_df.columns:
            def format_perf(val):
                if pd.isna(val) or val is None:
                    return ''
                if val > 5:
                    return f'🟢 +{val:.1f}%'
                elif val > 0:
                    return f'🔵 +{val:.1f}%'
                elif val > -5:
                    return f'🟡 {val:.1f}%'
                else:
                    return f'🔴 {val:.1f}%'
            display_df['price_change'] = display_df['price_change'].apply(format_perf)

        if 'excess_return' in display_df.columns:
            def format_excess(val):
                if pd.isna(val) or val is None:
                    return ''
                if val > 0:
                    return f'↑ +{val:.1f}%'
                else:
                    return f'↓ {val:.1f}%'
            display_df['excess_return'] = display_df['excess_return'].apply(format_excess)

        # Añadir indicador de insider signal
        if 'committee_relevant' in display_df.columns:
            display_df['committee_relevant'] = display_df['committee_relevant'].apply(
                lambda x: '⚠️ INSIDER' if x else ''
            )

        # Renombrar columnas
        col_names = {
            'politician': 'Político',
            'party': 'Partido',
            'chamber': 'Cámara',
            'ticker': 'Ticker',
            'company': 'Empresa',
            'transaction_type': 'Tipo',
            'disclosed_date': 'Filed',
            'traded_date': 'Traded',
            'price_change': 'Perf',
            'excess_return': 'vs SPY',
            'amount_range': 'Monto',
            'committee_relevant': 'Señal',
            'source': 'Fuente'
        }
        display_df = display_df.rename(columns=col_names)

        st.dataframe(display_df, use_container_width=True, height=600, hide_index=True)
    else:
        st.info("No se encontraron trades con los filtros seleccionados")

    st.markdown("---")

    # Ranking de tickers
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Tickers Más Comprados")
        top_traded = get_top_traded_tickers(days=30, top_n=10)
        if not top_traded['buys'].empty:
            st.dataframe(top_traded['buys'], use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de compras")

    with col2:
        st.subheader("📉 Tickers Más Vendidos")
        if not top_traded['sells'].empty:
            st.dataframe(top_traded['sells'], use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de ventas")


def show_stock_analysis():
    """Análisis detallado de un stock con datos reales"""
    st.markdown('<p class="main-header">📊 Stock Analysis</p>', unsafe_allow_html=True)

    # Selector de ticker
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        ticker = st.text_input("Ticker", "NVDA", key="analysis_ticker").upper()
    with col2:
        analyze = st.button("🔍 Analizar", type="primary")
    with col3:
        st.write("")

    if ticker:
        st.markdown("---")

        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Técnico",
            "📊 Fundamental",
            "🎯 Multi-Horizon Score",
            "🏛️ Congress Activity",
            "📝 Thesis Completa"
        ])

        with tab1:
            show_technical_analysis(ticker)

        with tab2:
            show_fundamental_analysis(ticker)

        with tab3:
            show_multi_horizon_detail(ticker)

        with tab4:
            show_congress_activity(ticker)

        with tab5:
            show_investment_thesis(ticker)


def show_technical_analysis(ticker: str):
    """Análisis técnico con datos reales"""
    from webapp.data.providers import calculate_konkorde

    with st.spinner(f"Cargando datos de {ticker}..."):
        data = get_stock_data(ticker)

    if 'error' in data:
        st.error(f"Error cargando datos: {data['error']}")
        return

    # Header with real-time price
    price = data.get('price', 0)
    change_pct = data.get('change_pct', 0)
    company_name = data.get('company_name', ticker)

    price_color = "green" if change_pct >= 0 else "red"
    change_symbol = "+" if change_pct >= 0 else ""

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 15px;">
        <h2 style="margin: 0;">{ticker}</h2>
        <span style="font-size: 24px; font-weight: bold;">${price:.2f}</span>
        <span style="color: {price_color}; font-size: 18px;">{change_symbol}{change_pct:.2f}%</span>
        <span style="color: #888; font-size: 14px;">{company_name}</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📈 Gráfico con Konkorde 2.0")
        # Gráfico con plotly (más confiable que TradingView widget)
        hist = data.get('history')
        if hist is not None and not hist.empty:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Calculate Konkorde indicator
            konkorde = calculate_konkorde(hist)

            # Crear figura con 3 subplots (precio + Konkorde + volumen)
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                               vertical_spacing=0.02,
                               row_heights=[0.5, 0.25, 0.25],
                               subplot_titles=('', 'Konkorde 2.0', 'Volumen'))

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name='Precio'
            ), row=1, col=1)

            # Bollinger Bands
            close = hist['Close']
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            bb_upper = sma20 + (std20 * 2)
            bb_lower = sma20 - (std20 * 2)

            fig.add_trace(go.Scatter(x=hist.index, y=sma20, name='SMA20',
                                     line=dict(color='orange', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=bb_upper, name='BB Upper',
                                     line=dict(color='gray', width=1, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=bb_lower, name='BB Lower',
                                     line=dict(color='gray', width=1, dash='dash')), row=1, col=1)

            # Konkorde indicator (row 2)
            if not konkorde['azul'].empty:
                # Fill areas for green and blue
                fig.add_trace(go.Scatter(
                    x=hist.index, y=konkorde['verde'],
                    fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.3)',
                    line=dict(color='green', width=1),
                    name='Manos Débiles (Retail)'
                ), row=2, col=1)

                fig.add_trace(go.Scatter(
                    x=hist.index, y=konkorde['azul'],
                    fill='tozeroy', fillcolor='rgba(0, 100, 255, 0.3)',
                    line=dict(color='blue', width=1),
                    name='Manos Fuertes (Institucional)'
                ), row=2, col=1)

                fig.add_trace(go.Scatter(
                    x=hist.index, y=konkorde['marron'],
                    line=dict(color='brown', width=2),
                    name='Tendencia'
                ), row=2, col=1)

                fig.add_trace(go.Scatter(
                    x=hist.index, y=konkorde['media'],
                    line=dict(color='white', width=1, dash='dash'),
                    name='Media'
                ), row=2, col=1)

                # Zero line for Konkorde
                fig.add_hline(y=0, line_dash="dot", line_color="gray", row=2, col=1)

            # Volumen (row 3)
            colors = ['red' if close.iloc[i] < close.iloc[i-1] else 'green'
                      for i in range(1, len(close))]
            colors.insert(0, 'green')
            fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name='Volumen',
                                marker_color=colors), row=3, col=1)

            fig.update_layout(
                template='plotly_dark',
                height=600,
                showlegend=False,
                xaxis_rangeslider_visible=False,
                margin=dict(l=0, r=0, t=20, b=0)
            )

            # Update y-axis labels
            fig.update_yaxes(title_text="Precio", row=1, col=1)
            fig.update_yaxes(title_text="Konkorde", row=2, col=1)
            fig.update_yaxes(title_text="Vol", row=3, col=1)

            st.plotly_chart(fig, use_container_width=True)

            # Konkorde interpretation
            if not konkorde['azul'].empty:
                latest_azul = konkorde['azul'].iloc[-1]
                latest_verde = konkorde['verde'].iloc[-1]

                if latest_azul > 0 and latest_verde > 0:
                    st.success("**Konkorde:** Institucionales Y retail comprando - Tendencia alcista fuerte")
                elif latest_azul > 0 and latest_verde < 0:
                    st.info("**Konkorde:** Institucionales acumulando, retail vendiendo - Posible suelo")
                elif latest_azul < 0 and latest_verde > 0:
                    st.warning("**Konkorde:** Institucionales distribuyendo, retail comprando - Precaución")
                elif latest_azul < 0 and latest_verde < 0:
                    st.error("**Konkorde:** Ambos vendiendo - Tendencia bajista")
        else:
            st.warning("No se pudo cargar el historial de precios")

    with col2:
        st.markdown("### 🎯 Indicadores Clave")

        # RSI
        rsi = data['rsi']
        rsi_color = "🟢" if rsi < 30 else ("🔴" if rsi > 70 else "🟡")
        rsi_signal = "Sobreventa" if rsi < 30 else ("Sobrecompra" if rsi > 70 else "Neutral")
        st.metric("RSI (14)", f"{rsi:.1f} {rsi_color}", rsi_signal)

        # MACD
        macd_emoji = "🟢" if data['macd_bullish'] else "🔴"
        st.metric("MACD", f"{data['macd_signal']} {macd_emoji}")

        # VWAP
        price = data['price']
        vwap = data['vwap']
        above_vwap = price > vwap if vwap > 0 else False
        st.metric("VWAP", f"${vwap:.2f}", "Por encima" if above_vwap else "Por debajo")

        # Volume
        vol_ratio = data['volume_ratio']
        vol_signal = "Alto" if vol_ratio > 1.5 else ("Bajo" if vol_ratio < 0.7 else "Normal")
        st.metric("Vol vs Media", f"{vol_ratio:.1f}x", vol_signal)

        st.markdown("---")

        # Momentum
        st.markdown("### 📊 Momentum")
        st.metric("1 Mes", f"{data['momentum_1m']:+.1f}%")
        st.metric("3 Meses", f"{data['momentum_3m']:+.1f}%")

    # Resumen técnico
    st.markdown("---")

    # Determinar sesgo
    bullish_signals = 0
    bearish_signals = 0

    if data['rsi'] < 40:
        bullish_signals += 1
    elif data['rsi'] > 60:
        bearish_signals += 1

    if data['macd_bullish']:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if data['momentum_1m'] > 0:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if bullish_signals > bearish_signals:
        st.success(f"""
        **Sesgo Técnico: ALCISTA** ({bullish_signals}/3 señales positivas)

        - RSI: {data['rsi']:.1f} - {rsi_signal}
        - MACD: {data['macd_signal']}
        - Momentum 1M: {data['momentum_1m']:+.1f}%
        """)
    elif bearish_signals > bullish_signals:
        st.error(f"""
        **Sesgo Técnico: BAJISTA** ({bearish_signals}/3 señales negativas)

        - RSI: {data['rsi']:.1f} - {rsi_signal}
        - MACD: {data['macd_signal']}
        - Momentum 1M: {data['momentum_1m']:+.1f}%
        """)
    else:
        st.warning(f"""
        **Sesgo Técnico: NEUTRAL**

        - RSI: {data['rsi']:.1f} - {rsi_signal}
        - MACD: {data['macd_signal']}
        - Momentum 1M: {data['momentum_1m']:+.1f}%
        """)


def show_fundamental_analysis(ticker: str):
    """Análisis fundamental con datos reales y comentarios inteligentes"""
    st.subheader(f"Análisis Fundamental - {ticker}")

    with st.spinner(f"Cargando datos fundamentales de {ticker}..."):
        data = get_stock_data(ticker)

    if 'error' in data:
        st.error(f"Error cargando datos: {data['error']}")
        return

    # =========================================================================
    # FUNCIONES DE COMENTARIO INTELIGENTE
    # =========================================================================
    def comment_pe(pe, forward_pe, sector):
        """Comentario inteligente para P/E"""
        if not pe:
            return "Sin datos de P/E"

        # Benchmarks por sector (aproximados)
        sector_benchmarks = {
            'Technology': 30, 'Healthcare': 22, 'Financial Services': 14,
            'Consumer Cyclical': 20, 'Consumer Defensive': 22, 'Energy': 12,
            'Industrials': 18, 'Basic Materials': 15, 'Utilities': 16,
            'Real Estate': 35, 'Communication Services': 18
        }
        benchmark = sector_benchmarks.get(sector, 20)  # Default S&P500 avg

        if pe < 0:
            return "P/E negativo indica pérdidas. La empresa no es rentable actualmente."
        elif pe < benchmark * 0.6:
            comment = f"P/E de {pe:.1f} está MUY BAJO vs sector ({benchmark}). "
            if forward_pe and forward_pe > pe:
                comment += "Forward P/E mayor sugiere expectativa de menores ganancias futuras."
            else:
                comment += "Posible oportunidad value o el mercado anticipa problemas."
            return comment
        elif pe < benchmark * 0.85:
            return f"P/E de {pe:.1f} está por DEBAJO del sector ({benchmark}). Valoración atractiva si los fundamentales son sólidos."
        elif pe < benchmark * 1.15:
            return f"P/E de {pe:.1f} está en línea con el sector ({benchmark}). Valoración justa."
        elif pe < benchmark * 1.5:
            return f"P/E de {pe:.1f} está por ENCIMA del sector ({benchmark}). El mercado espera alto crecimiento."
        else:
            return f"P/E de {pe:.1f} es MUY ALTO vs sector ({benchmark}). Valoración cara, requiere crecimiento excepcional para justificarse."

    def comment_pb(pb, roe):
        """Comentario inteligente para P/B"""
        if not pb:
            return "Sin datos de P/B"

        if pb < 1:
            if roe and roe > 0:
                return f"P/B de {pb:.2f} por debajo de valor contable. Si el ROE es positivo ({roe:.1f}%), puede ser oportunidad."
            return f"P/B de {pb:.2f} indica que cotiza por debajo de su valor en libros. Puede ser oportunidad o trampa de valor."
        elif pb < 3:
            return f"P/B de {pb:.2f} es razonable. El mercado valora algo de intangibles sobre los activos."
        elif pb < 6:
            return f"P/B de {pb:.2f} es elevado pero común en empresas de calidad con altos intangibles (marca, IP, moat)."
        else:
            return f"P/B de {pb:.2f} es MUY ALTO. Típico de empresas tech asset-light. Valora más sus intangibles que activos físicos."

    def comment_roe(roe, debt_equity):
        """Comentario inteligente para ROE"""
        if not roe:
            return "Sin datos de ROE"

        if roe < 0:
            return "ROE negativo indica pérdidas. La empresa destruye valor para accionistas."
        elif roe < 8:
            return f"ROE de {roe:.1f}% es BAJO. No supera el costo de capital típico (8-10%). Destruye valor económico."
        elif roe < 15:
            return f"ROE de {roe:.1f}% es ACEPTABLE. Genera retorno moderado sobre el equity."
        elif roe < 25:
            if debt_equity and debt_equity > 150:
                return f"ROE de {roe:.1f}% es BUENO, pero cuidado: alto apalancamiento ({debt_equity:.0f}%) infla artificialmente el ROE."
            return f"ROE de {roe:.1f}% es MUY BUENO. Empresa eficiente generando valor para accionistas."
        else:
            if debt_equity and debt_equity > 150:
                return f"ROE de {roe:.1f}% es excepcional pero puede estar inflado por alto apalancamiento ({debt_equity:.0f}%)."
            return f"ROE de {roe:.1f}% es EXCEPCIONAL. Indica ventajas competitivas fuertes o modelo de negocio muy eficiente."

    def comment_margins(gross, operating, net):
        """Comentario inteligente para márgenes"""
        comments = []

        if gross:
            if gross > 60:
                comments.append(f"Margen bruto de {gross:.1f}% es EXCELENTE - indica fuerte poder de pricing o ventaja de costos.")
            elif gross > 40:
                comments.append(f"Margen bruto de {gross:.1f}% es BUENO - empresa con márgenes saludables.")
            elif gross > 20:
                comments.append(f"Margen bruto de {gross:.1f}% es MODERADO - típico de industrias competitivas.")
            else:
                comments.append(f"Margen bruto de {gross:.1f}% es BAJO - negocio de bajo margen, depende de volumen.")

        if operating and gross:
            op_efficiency = (operating / gross) * 100 if gross > 0 else 0
            if op_efficiency > 50:
                comments.append(f"Buena eficiencia operativa (retiene {op_efficiency:.0f}% del margen bruto).")
            else:
                comments.append(f"Altos gastos operativos consumen {100-op_efficiency:.0f}% del margen bruto.")

        if net:
            if net > 20:
                comments.append(f"Margen neto de {net:.1f}% es EXCELENTE - muy rentable después de todos los gastos.")
            elif net > 10:
                comments.append(f"Margen neto de {net:.1f}% es BUENO - rentabilidad sólida.")
            elif net > 5:
                comments.append(f"Margen neto de {net:.1f}% es ACEPTABLE pero ajustado.")
            elif net > 0:
                comments.append(f"Margen neto de {net:.1f}% es BAJO - poco espacio para error.")
            else:
                comments.append("Margen neto negativo - la empresa opera con pérdidas.")

        return " ".join(comments) if comments else "Sin datos de márgenes"

    def comment_debt(debt_equity, current_ratio, quick_ratio):
        """Comentario inteligente para deuda y liquidez"""
        comments = []

        if debt_equity is not None:
            if debt_equity < 0:
                comments.append("Debt/Equity negativo indica patrimonio negativo - situación financiera delicada.")
            elif debt_equity == 0:
                comments.append("Sin deuda financiera - empresa muy conservadora o no necesita apalancamiento.")
            elif debt_equity < 50:
                comments.append(f"D/E de {debt_equity:.0f}% es MUY BAJO - balance muy sólido con poca deuda.")
            elif debt_equity < 100:
                comments.append(f"D/E de {debt_equity:.0f}% es CONSERVADOR - buen equilibrio deuda/capital.")
            elif debt_equity < 150:
                comments.append(f"D/E de {debt_equity:.0f}% es MODERADO - apalancamiento aceptable si genera buenos retornos.")
            elif debt_equity < 200:
                comments.append(f"D/E de {debt_equity:.0f}% es ALTO - empresa apalancada, mayor riesgo financiero.")
            else:
                comments.append(f"D/E de {debt_equity:.0f}% es MUY ALTO - alto riesgo de estrés financiero si suben las tasas.")

        if current_ratio:
            if current_ratio < 1:
                comments.append(f"Current ratio de {current_ratio:.2f} indica posibles problemas de liquidez a corto plazo.")
            elif current_ratio < 1.5:
                comments.append(f"Current ratio de {current_ratio:.2f} es ajustado pero manejable.")
            elif current_ratio < 3:
                comments.append(f"Current ratio de {current_ratio:.2f} muestra buena liquidez.")
            else:
                comments.append(f"Current ratio de {current_ratio:.2f} indica exceso de liquidez - podría usar mejor el capital.")

        return " ".join(comments) if comments else "Sin datos de deuda"

    # =========================================================================
    # TABLAS DE DATOS
    # =========================================================================
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📊 Valoración")
        valuation_data = {
            "Ratio": ["P/E", "Fwd P/E", "P/S", "P/B", "EV/EBITDA"],
            "Valor": [
                f"{data['pe_ratio']:.1f}" if data['pe_ratio'] else "N/A",
                f"{data['forward_pe']:.1f}" if data['forward_pe'] else "N/A",
                f"{data['ps_ratio']:.2f}" if data['ps_ratio'] else "N/A",
                f"{data['pb_ratio']:.2f}" if data['pb_ratio'] else "N/A",
                f"{data['ev_ebitda']:.1f}" if data['ev_ebitda'] else "N/A",
            ]
        }
        st.dataframe(pd.DataFrame(valuation_data), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### 📈 Rentabilidad")
        profitability_data = {
            "Ratio": ["ROE %", "ROA %", "Margen Bruto %", "Margen Op. %", "Margen Neto %"],
            "Valor": [
                f"{data['roe']:.1f}" if data['roe'] else "N/A",
                f"{data['roa']:.1f}" if data['roa'] else "N/A",
                f"{data['gross_margin']:.1f}" if data['gross_margin'] else "N/A",
                f"{data['operating_margin']:.1f}" if data['operating_margin'] else "N/A",
                f"{data['profit_margin']:.1f}" if data['profit_margin'] else "N/A",
            ]
        }
        st.dataframe(pd.DataFrame(profitability_data), use_container_width=True, hide_index=True)

    with col3:
        st.markdown("### 💰 Liquidez/Deuda")
        debt_data = {
            "Ratio": ["Quick Ratio", "Current Ratio", "Debt/Equity", "Div Yield %"],
            "Valor": [
                f"{data['quick_ratio']:.2f}" if data['quick_ratio'] else "N/A",
                f"{data['current_ratio']:.2f}" if data['current_ratio'] else "N/A",
                f"{data['debt_to_equity']:.0f}" if data['debt_to_equity'] else "N/A",
                f"{data['dividend_yield']:.2f}" if data['dividend_yield'] else "N/A",
            ]
        }
        st.dataframe(pd.DataFrame(debt_data), use_container_width=True, hide_index=True)

    # =========================================================================
    # COMENTARIOS INTELIGENTES
    # =========================================================================
    st.markdown("---")
    st.markdown("### 💡 Análisis de Ratios")

    # P/E y P/B
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Valoración (P/E):**")
        pe_comment = comment_pe(data['pe_ratio'], data['forward_pe'], data['sector'])
        if "BAJO" in pe_comment or "atractiva" in pe_comment.lower():
            st.success(pe_comment)
        elif "ALTO" in pe_comment or "cara" in pe_comment.lower():
            st.warning(pe_comment)
        else:
            st.info(pe_comment)

    with col2:
        st.markdown("**Valoración (P/B):**")
        pb_comment = comment_pb(data['pb_ratio'], data['roe'])
        if "oportunidad" in pb_comment.lower():
            st.success(pb_comment)
        elif "MUY ALTO" in pb_comment:
            st.warning(pb_comment)
        else:
            st.info(pb_comment)

    # ROE
    st.markdown("**Rentabilidad (ROE):**")
    roe_comment = comment_roe(data['roe'], data['debt_to_equity'])
    if "EXCEPCIONAL" in roe_comment or "MUY BUENO" in roe_comment:
        st.success(roe_comment)
    elif "BAJO" in roe_comment or "negativo" in roe_comment.lower():
        st.error(roe_comment)
    elif "cuidado" in roe_comment.lower():
        st.warning(roe_comment)
    else:
        st.info(roe_comment)

    # Márgenes
    st.markdown("**Márgenes:**")
    margin_comment = comment_margins(data['gross_margin'], data['operating_margin'], data['profit_margin'])
    if "EXCELENTE" in margin_comment:
        st.success(margin_comment)
    elif "BAJO" in margin_comment or "pérdidas" in margin_comment.lower():
        st.error(margin_comment)
    else:
        st.info(margin_comment)

    # Deuda
    st.markdown("**Solidez Financiera:**")
    debt_comment = comment_debt(data['debt_to_equity'], data['current_ratio'], data['quick_ratio'])
    if "MUY BAJO" in debt_comment or "muy sólido" in debt_comment.lower():
        st.success(debt_comment)
    elif "MUY ALTO" in debt_comment or "problemas" in debt_comment.lower():
        st.error(debt_comment)
    elif "ALTO" in debt_comment:
        st.warning(debt_comment)
    else:
        st.info(debt_comment)

    # =========================================================================
    # RESUMEN FUNDAMENTAL
    # =========================================================================
    st.markdown("---")

    # Quality score calculation
    quality_score = 0
    max_score = 0
    quality_factors = []

    # ROE check
    if data['roe']:
        max_score += 1
        if data['roe'] > 15:
            quality_score += 1
            quality_factors.append(f"ROE alto ({data['roe']:.1f}%)")
        else:
            quality_factors.append(f"ROE bajo ({data['roe']:.1f}%)")

    # Debt check
    if data['debt_to_equity'] is not None:
        max_score += 1
        if data['debt_to_equity'] < 100:
            quality_score += 1
            quality_factors.append(f"Deuda controlada ({data['debt_to_equity']:.0f}%)")
        else:
            quality_factors.append(f"Deuda elevada ({data['debt_to_equity']:.0f}%)")

    # Margin check
    if data['profit_margin']:
        max_score += 1
        if data['profit_margin'] > 10:
            quality_score += 1
            quality_factors.append(f"Buenos márgenes ({data['profit_margin']:.1f}%)")
        else:
            quality_factors.append(f"Márgenes ajustados ({data['profit_margin']:.1f}%)")

    rating = "A" if quality_score >= 3 else ("B" if quality_score >= 2 else "C")
    rating_color = "success" if rating == "A" else ("warning" if rating == "B" else "error")

    # Display summary
    summary_func = st.success if rating == "A" else (st.warning if rating == "B" else st.error)
    summary_func(f"""
    **Resumen Fundamental - {data['company_name']}**

    - **Sector:** {data['sector']} | **Industria:** {data['industry']}
    - **Market Cap:** ${data['market_cap']/1e9:.1f}B
    - **Quality Rating: {rating}** ({quality_score}/{max_score} criterios positivos)

    Factores: {' | '.join(quality_factors)}
    """)


def show_multi_horizon_detail(ticker: str):
    """Scoring multi-horizonte para un ticker específico"""
    st.subheader(f"Multi-Horizon Scoring - {ticker}")

    with st.spinner(f"Calculando scores para {ticker}..."):
        scores_df = get_multi_horizon_scores([ticker])

    if scores_df.empty:
        st.warning("No se pudo calcular el score para este ticker")
        return

    row = scores_df.iloc[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🚀 Corto Plazo (1-4 sem)")
        score_cp = row.get('Score CP', 0)
        signal_cp = row.get('Señal CP', 'N/A')
        st.metric("Score", f"{score_cp}/100", signal_cp)
        st.progress(score_cp / 100)

    with col2:
        st.markdown("### ⏳ Medio Plazo (1-6 mes)")
        score_mp = row.get('Score MP', 0)
        signal_mp = row.get('Señal MP', 'N/A')
        st.metric("Score", f"{score_mp}/100", signal_mp)
        st.progress(score_mp / 100)

    with col3:
        st.markdown("### 🏛️ Largo Plazo (6+ mes)")
        score_lp = row.get('Score LP', 0)
        signal_lp = row.get('Señal LP', 'N/A')
        st.metric("Score", f"{score_lp}/100", signal_lp)
        st.progress(score_lp / 100)

    st.markdown("---")

    # Cargar datos fundamentales para contexto
    data = get_stock_data(ticker)

    st.markdown("### 📊 Factores del Score")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Técnicos:**")
        st.write(f"- RSI: {data['rsi']:.1f}")
        st.write(f"- MACD: {data['macd_signal']}")
        st.write(f"- Momentum 1M: {data['momentum_1m']:+.1f}%")
        st.write(f"- Momentum 3M: {data['momentum_3m']:+.1f}%")

    with col2:
        st.markdown("**Fundamentales:**")
        st.write(f"- P/E: {data['pe_ratio']:.1f}" if data['pe_ratio'] else "- P/E: N/A")
        st.write(f"- ROE: {data['roe']:.1f}%" if data['roe'] else "- ROE: N/A")
        st.write(f"- Debt/Equity: {data['debt_to_equity']:.0f}" if data['debt_to_equity'] else "- Debt/Equity: N/A")


def show_congress_activity(ticker: str):
    """Actividad de congresistas para un ticker específico"""
    st.subheader(f"Congress Activity - {ticker}")

    with st.spinner(f"Buscando trades de {ticker}..."):
        trades = get_congress_trades_for_ticker(ticker, days=365)

    if trades.empty:
        st.info(f"No se encontraron trades de congresistas para {ticker} en el último año")
        return

    # Estadísticas
    total = len(trades)
    buys = len(trades[trades['transaction_type'] == 'buy']) if 'transaction_type' in trades.columns else 0
    sells = len(trades[trades['transaction_type'] == 'sell']) if 'transaction_type' in trades.columns else 0
    unique_pols = trades['politician'].nunique() if 'politician' in trades.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades", str(total))
    with col2:
        st.metric("Compras", str(buys), f"{buys/total*100:.0f}%" if total > 0 else "")
    with col3:
        st.metric("Ventas", str(sells))
    with col4:
        st.metric("Políticos", str(unique_pols))

    st.markdown("---")

    # Timeline
    st.markdown("### 📅 Timeline de Trades")

    display_cols = ['politician', 'party', 'transaction_type', 'traded_date', 'amount_range', 'source']
    available_cols = [c for c in display_cols if c in trades.columns]

    display_df = trades[available_cols].head(20).copy()

    if 'traded_date' in display_df.columns:
        display_df['traded_date'] = pd.to_datetime(display_df['traded_date']).dt.strftime('%Y-%m-%d')

    col_names = {
        'politician': 'Político',
        'party': 'Partido',
        'transaction_type': 'Tipo',
        'traded_date': 'Fecha',
        'amount_range': 'Monto',
        'source': 'Fuente'
    }
    display_df = display_df.rename(columns=col_names)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Interpretación
    if buys > sells:
        st.success(f"""
        **Interpretación:**
        - {buys} de {total} trades son COMPRAS ({buys/total*100:.0f}% bullish)
        - {unique_pols} políticos diferentes han operado este ticker
        - Sesgo de congresistas: **ALCISTA**
        """)
    elif sells > buys:
        st.warning(f"""
        **Interpretación:**
        - {sells} de {total} trades son VENTAS ({sells/total*100:.0f}% bearish)
        - {unique_pols} políticos diferentes han operado este ticker
        - Sesgo de congresistas: **BAJISTA**
        """)
    else:
        st.info(f"""
        **Interpretación:**
        - Balance equilibrado entre compras y ventas
        - {unique_pols} políticos diferentes han operado este ticker
        - Sesgo de congresistas: **NEUTRAL**
        """)


def show_investment_thesis(ticker: str):
    """Thesis de inversión completa"""
    st.subheader(f"Investment Thesis - {ticker}")

    with st.spinner("Generando thesis..."):
        data = get_stock_data(ticker)
        trades = get_congress_trades_for_ticker(ticker, days=365)
        scores = get_multi_horizon_scores([ticker])

    if 'error' in data:
        st.error("No se pudo generar la thesis")
        return

    # Determinar sesgo técnico
    tech_bias = "ALCISTA" if data['macd_bullish'] and data['rsi'] < 70 else (
        "BAJISTA" if not data['macd_bullish'] and data['rsi'] > 30 else "NEUTRAL"
    )

    # Congress bias
    if not trades.empty and 'transaction_type' in trades.columns:
        buys = len(trades[trades['transaction_type'] == 'buy'])
        sells = len(trades[trades['transaction_type'] == 'sell'])
        congress_bias = "ALCISTA" if buys > sells else ("BAJISTA" if sells > buys else "NEUTRAL")
    else:
        congress_bias = "SIN DATOS"

    # Scores
    if not scores.empty:
        row = scores.iloc[0]
        score_cp = row.get('Score CP', 'N/A')
        score_mp = row.get('Score MP', 'N/A')
        score_lp = row.get('Score LP', 'N/A')
    else:
        score_cp = score_mp = score_lp = 'N/A'

    st.markdown(f"""
    ## {data['company_name']} ({ticker})

    **Sector:** {data['sector']} | **Precio:** ${data['price']:.2f}

    ---

    ### 📊 Resumen de Scores

    | Horizonte | Score | Señal |
    |-----------|-------|-------|
    | Corto Plazo (1-4 sem) | {score_cp} | {scores.iloc[0].get('Señal CP', 'N/A') if not scores.empty else 'N/A'} |
    | Medio Plazo (1-6 mes) | {score_mp} | {scores.iloc[0].get('Señal MP', 'N/A') if not scores.empty else 'N/A'} |
    | Largo Plazo (6+ mes) | {score_lp} | {scores.iloc[0].get('Señal LP', 'N/A') if not scores.empty else 'N/A'} |

    ---

    ### 📈 Análisis Técnico

    **Sesgo: {tech_bias}**

    - RSI (14): {data['rsi']:.1f}
    - MACD: {data['macd_signal']}
    - Momentum 1M: {data['momentum_1m']:+.1f}%
    - Momentum 3M: {data['momentum_3m']:+.1f}%
    - Volumen vs Media: {data['volume_ratio']:.1f}x

    ---

    ### 💰 Análisis Fundamental

    **Valoración:**
    - P/E: {f"{data['pe_ratio']:.1f}" if data['pe_ratio'] else 'N/A'}
    - P/B: {f"{data['pb_ratio']:.2f}" if data['pb_ratio'] else 'N/A'}
    - EV/EBITDA: {f"{data['ev_ebitda']:.1f}" if data['ev_ebitda'] else 'N/A'}

    **Rentabilidad:**
    - ROE: {f"{data['roe']:.1f}" if data['roe'] else 'N/A'}%
    - ROA: {f"{data['roa']:.1f}" if data['roa'] else 'N/A'}%
    - Margen Neto: {f"{data['profit_margin']:.1f}" if data['profit_margin'] else 'N/A'}%

    **Solidez:**
    - Debt/Equity: {f"{data['debt_to_equity']:.0f}" if data['debt_to_equity'] else 'N/A'}
    - Current Ratio: {f"{data['current_ratio']:.2f}" if data['current_ratio'] else 'N/A'}

    ---

    ### 🏛️ Actividad del Congreso

    **Sesgo: {congress_bias}**

    - Trades totales (1 año): {len(trades)}
    - Compras: {len(trades[trades['transaction_type'] == 'buy']) if not trades.empty and 'transaction_type' in trades.columns else 0}
    - Ventas: {len(trades[trades['transaction_type'] == 'sell']) if not trades.empty and 'transaction_type' in trades.columns else 0}

    ---

    ### 🎯 Conclusión

    Basado en el análisis multi-horizonte, {ticker} presenta:

    - **Corto plazo:** Score {score_cp}/100
    - **Técnicos:** {tech_bias}
    - **Congreso:** {congress_bias}

    """)


def show_multi_horizon_scoring():
    """Vista de scoring multi-horizonte para todos los stocks"""
    st.markdown('<p class="main-header">🎯 Multi-Horizon Scoring</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Scores calculados en tiempo real</p>', unsafe_allow_html=True)

    with st.expander("ℹ️ Cómo funciona el sistema de scoring"):
        st.markdown("""
        ### Sistema de Scoring Multi-Horizonte

        | Horizonte | Factores Principales |
        |-----------|---------------------|
        | **Corto Plazo** (1-4 sem) | RSI, MACD, Momentum, News |
        | **Medio Plazo** (1-6 mes) | Momentum 3M, Analyst Rev, Sector |
        | **Largo Plazo** (6+ mes) | Value, Quality, Deuda, Moat |
        """)

    st.markdown("---")

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        horizon = st.selectbox("Ordenar por horizonte", ["Corto Plazo", "Medio Plazo", "Largo Plazo"])
    with col2:
        min_score_filter = st.slider("Score mínimo", 0, 100, 50)
    with col3:
        ticker_selection = st.multiselect(
            "Tickers a analizar",
            TICKER_UNIVERSE,
            default=TICKER_UNIVERSE[:15]
        )

    if st.button("🔄 Calcular Scores", type="primary"):
        with st.spinner("Calculando scores... (esto puede tardar)"):
            scores_df = get_multi_horizon_scores(ticker_selection)

            if not scores_df.empty:
                # Filtrar por score mínimo
                sort_col = 'Score CP' if 'Corto' in horizon else ('Score MP' if 'Medio' in horizon else 'Score LP')
                scores_df = scores_df[scores_df[sort_col] >= min_score_filter]
                scores_df = scores_df.sort_values(sort_col, ascending=False)

                st.dataframe(scores_df, use_container_width=True, height=500, hide_index=True)

                # Highlights
                st.markdown("---")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("### 🚀 Top Corto Plazo")
                    top_cp = scores_df.nlargest(3, 'Score CP')[['Ticker', 'Score CP', 'Señal CP']]
                    for _, row in top_cp.iterrows():
                        st.write(f"**{row['Ticker']}**: {row['Score CP']} ({row['Señal CP']})")

                with col2:
                    st.markdown("### ⏳ Top Medio Plazo")
                    top_mp = scores_df.nlargest(3, 'Score MP')[['Ticker', 'Score MP', 'Señal MP']]
                    for _, row in top_mp.iterrows():
                        st.write(f"**{row['Ticker']}**: {row['Score MP']} ({row['Señal MP']})")

                with col3:
                    st.markdown("### 🏛️ Top Largo Plazo")
                    top_lp = scores_df.nlargest(3, 'Score LP')[['Ticker', 'Score LP', 'Señal LP']]
                    for _, row in top_lp.iterrows():
                        st.write(f"**{row['Ticker']}**: {row['Score LP']} ({row['Señal LP']})")
            else:
                st.warning("No se pudieron calcular los scores")
    else:
        st.info("Haz clic en 'Calcular Scores' para ver los resultados")


def show_monetary_plumbing():
    """Vista de monetary plumbing con datos reales"""
    st.markdown('<p class="main-header">💧 Monetary Plumbing</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Análisis de liquidez y condiciones monetarias</p>', unsafe_allow_html=True)

    with st.spinner("Cargando datos monetarios..."):
        data = get_monetary_data()

    # Extraer valores de forma segura
    net_liq = data.get('net_liquidity', {})
    vol = data.get('volatility', {})
    credit = data.get('credit', {})
    japan = data.get('japan', {})
    regime = data.get('regime', {})

    # Métricas principales
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        liq_current = net_liq.get('current', 5800) if isinstance(net_liq, dict) else 5800
        liq_change = net_liq.get('change_1m', 0) if isinstance(net_liq, dict) else 0
        st.metric("Net Liquidity", f"${liq_current/1000:.1f}T", f"{liq_change:+.1f}%")

    with col2:
        vix = vol.get('vix', 0) if isinstance(vol, dict) else 0
        st.metric("VIX", f"{vix:.1f}", delta_color="inverse")

    with col3:
        move = vol.get('move', 0) if isinstance(vol, dict) else 0
        st.metric("MOVE Index", f"{move:.0f}", delta_color="inverse")

    with col4:
        spread = credit.get('ig_spread', 0) if isinstance(credit, dict) else 0
        st.metric("Credit Spreads", f"{spread:.0f} bps", delta_color="inverse")

    with col5:
        usdjpy_data = japan.get('usdjpy', {}) if isinstance(japan, dict) else {}
        usdjpy = usdjpy_data.get('current', 155) if isinstance(usdjpy_data, dict) else 155
        st.metric("USD/JPY", f"{usdjpy:.1f}")

    st.markdown("---")

    # Régimen actual
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### 🎯 Régimen Actual")
        regime_name = regime.get('name', 'N/A') if isinstance(regime, dict) else 'N/A'
        regime_score = regime.get('score', 50) if isinstance(regime, dict) else 50

        if regime_name == 'ABUNDANT':
            st.success(f"**{regime_name}**")
        elif regime_name == 'SCARCE':
            st.error(f"**{regime_name}**")
        else:
            st.warning(f"**{regime_name}**")

        st.metric("Score Compuesto", f"{regime_score}/100")
        st.progress(regime_score / 100)

    with col2:
        st.markdown("### 📈 Implicaciones para el Scoring")

        if regime_name == 'ABUNDANT':
            st.markdown("""
            **En régimen ABUNDANT LIQUIDITY:**
            - ✅ Momentum sobreponderado (+10%)
            - ✅ Growth/Tech favorecido
            - ⚠️ Quality subponderado (-5%)
            - ⚠️ LowVol subponderado (-5%)
            """)
        elif regime_name == 'SCARCE':
            st.markdown("""
            **En régimen SCARCE LIQUIDITY:**
            - ⚠️ Momentum infraponderado (-10%)
            - ⚠️ Growth/Tech desfavorecido
            - ✅ Quality sobreponderado (+10%)
            - ✅ Defensivos favorecidos
            """)
        else:
            st.markdown("""
            **En régimen NEUTRAL:**
            - Balance entre growth y value
            - Sin ajustes significativos
            """)

    if 'error' in data:
        st.warning(f"Nota: Algunos datos pueden ser estimados. Error: {data['error']}")


def show_settings():
    """Configuración de la app"""
    st.markdown('<p class="main-header">⚙️ Settings</p>', unsafe_allow_html=True)

    st.markdown("### 🔧 Configuración de Datos")

    col1, col2 = st.columns(2)

    with col1:
        finnhub_key = st.text_input("Finnhub API Key", type="password",
                                     help="Obtener en finnhub.io (gratis)")

        if finnhub_key:
            st.success("API key configurada")

    with col2:
        st.number_input("Días de histórico Congress", value=90, min_value=30, max_value=365)

    st.markdown("---")

    st.markdown("### 🔄 Cache")

    if st.button("🗑️ Limpiar Cache", type="secondary"):
        st.cache_data.clear()
        st.success("Cache limpiado. Los datos se recargarán en la próxima consulta.")

    st.markdown("---")

    st.markdown("### 📊 Tickers Configurados")

    st.write(f"**Universo de tickers:** {len(TICKER_UNIVERSE)} stocks")
    st.code(", ".join(TICKER_UNIVERSE))

    st.markdown("### 👤 Políticos de Alto Perfil")
    st.write(", ".join(HIGH_PROFILE_POLITICIANS))


if __name__ == "__main__":
    main()
