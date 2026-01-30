"""
Data Providers - Dynamic data loading for Market Analysis Web App
=================================================================
Centraliza la obtención de datos dinámicos de todas las fuentes.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# Paths setup
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'webapp'))


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _calculate_speculative_score(momentum_1m: float, momentum_3m: float,
                                  roe: float, volume_ratio: float) -> float:
    """
    Calculate a speculative score based on available data.
    This is used as a proxy for congress trading activity.

    A stock is more speculative/attractive when:
    - Strong positive momentum (recent winners keep winning)
    - Good fundamentals (ROE > 15%)
    - High volume (institutional interest)

    Returns score 0-100, where 50 is neutral.

    UPDATED: More aggressive scoring to match original Excel patterns.
    """
    score = 50.0

    # Momentum contribution - MORE AGGRESSIVE (±30 points max)
    # Strong momentum is the key driver in the original Excel
    momentum_boost = (momentum_1m * 1.2) + (momentum_3m * 0.8)
    score += min(max(momentum_boost, -30), 30)

    # ROE contribution: good profitability is bullish (±15 points)
    if roe and roe > 0:
        if roe > 30:
            score += 15
        elif roe > 20:
            score += 10
        elif roe > 12:
            score += 5
        elif roe < 5:
            score -= 10

    # Volume contribution: high volume = institutional interest (±10 points)
    if volume_ratio > 2.5:
        score += 12
    elif volume_ratio > 1.8:
        score += 8
    elif volume_ratio > 1.3:
        score += 5
    elif volume_ratio < 0.5:
        score -= 8

    return min(max(score, 5), 95)


def calculate_konkorde(hist: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Calculate Konkorde 2.0 indicator.

    The Konkorde indicator separates institutional ("manos fuertes")
    from retail ("manos débiles") activity using volume and price analysis.

    Returns:
        - azul (blue): Institutional/Smart money activity
        - verde (green): Retail/Weak hands activity
        - marron (brown): Total trend
        - media (white): Signal line (EMA of trend)
    """
    if hist is None or len(hist) < 20:
        return {'azul': pd.Series(), 'verde': pd.Series(), 'marron': pd.Series(), 'media': pd.Series()}

    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']

    # Typical price
    tp = (high + low + close) / 3

    # Money Flow calculation (basis for institutional detection)
    mf = tp * volume

    # PVI (Positive Volume Index) - tracks activity on up-volume days
    # NVI (Negative Volume Index) - tracks activity on down-volume days
    pvi = pd.Series(index=hist.index, dtype=float)
    nvi = pd.Series(index=hist.index, dtype=float)
    pvi.iloc[0] = 1000
    nvi.iloc[0] = 1000

    for i in range(1, len(hist)):
        price_change_pct = (close.iloc[i] - close.iloc[i-1]) / close.iloc[i-1] if close.iloc[i-1] != 0 else 0

        if volume.iloc[i] > volume.iloc[i-1]:
            # Up volume day - retail is active
            pvi.iloc[i] = pvi.iloc[i-1] * (1 + price_change_pct)
            nvi.iloc[i] = nvi.iloc[i-1]
        else:
            # Down volume day - institutions accumulating
            pvi.iloc[i] = pvi.iloc[i-1]
            nvi.iloc[i] = nvi.iloc[i-1] * (1 + price_change_pct)

    # Smooth with EMAs
    pvi_ema = pvi.ewm(span=13, adjust=False).mean()
    nvi_ema = nvi.ewm(span=13, adjust=False).mean()

    # Normalize for display
    pvi_norm = ((pvi - pvi_ema) / pvi_ema) * 100
    nvi_norm = ((nvi - nvi_ema) / nvi_ema) * 100

    # Accumulation/Distribution component
    clv = ((close - low) - (high - close)) / (high - low + 0.0001)  # Close Location Value
    ad = (clv * volume).cumsum()
    ad_ema = ad.ewm(span=13, adjust=False).mean()
    ad_norm = ((ad - ad_ema) / (ad_ema.abs() + 1)) * 50

    # RSI-like component for retail detection
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 0.0001)
    rsi = 100 - (100 / (1 + rs))
    rsi_norm = (rsi - 50) / 2  # Center around 0, scale down

    # Calculate Konkorde components
    # AZUL (Blue) - Institucional/"Manos Fuertes": NVI-based + A/D
    azul = nvi_norm + ad_norm * 0.5

    # VERDE (Green) - Retail/"Manos Débiles": PVI-based + RSI
    verde = pvi_norm + rsi_norm

    # MARRON (Brown) - Tendencia total: combination
    marron = (azul + verde) / 2

    # MEDIA (White) - Signal line
    media = marron.ewm(span=9, adjust=False).mean()

    # Final smoothing
    azul = azul.ewm(span=5, adjust=False).mean()
    verde = verde.ewm(span=5, adjust=False).mean()
    marron = marron.ewm(span=5, adjust=False).mean()

    return {
        'azul': azul,
        'verde': verde,
        'marron': marron,
        'media': media
    }


# =============================================================================
# CACHING DECORATORS
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)  # 5 minutos
def get_congress_trades(days: int = 90) -> pd.DataFrame:
    """Obtiene trades de congresistas de todas las fuentes"""
    try:
        from webapp.integrations.congress_unified import CongressUnifiedClient
        from webapp.config import get_finnhub_key

        finnhub_key = get_finnhub_key()
        tracker = CongressUnifiedClient(finnhub_api_key=finnhub_key)
        unified_trades = tracker.fetch_all_sources(days=days)

        if not unified_trades:
            # Intentar con datos de respaldo si no hay trades
            return _get_fallback_congress_data()

        # Convertir objetos UnifiedTrade a diccionarios
        trades = [t.to_dict() for t in unified_trades]
        df = pd.DataFrame(trades)

        # Convertir 'sources' (lista) a 'source' (string principal)
        if 'sources' in df.columns:
            df['source'] = df['sources'].apply(lambda x: x[0] if x else 'unknown')

        # Formatear columnas
        if 'traded_date' in df.columns:
            df['traded_date'] = pd.to_datetime(df['traded_date'], errors='coerce')
            df = df.sort_values('traded_date', ascending=False)

        return df
    except Exception as e:
        print(f"Error loading congress data: {e}")
        # Retornar datos de respaldo en caso de error
        return _get_fallback_congress_data()


def _get_fallback_congress_data() -> pd.DataFrame:
    """Retorna DataFrame vacío cuando las APIs no están disponibles.

    No usamos datos fabricados para evitar confusión con trades reales.
    """
    # Retornamos DataFrame vacío con las columnas esperadas
    columns = ['politician', 'party', 'chamber', 'state', 'ticker', 'company',
               'transaction_type', 'traded_date', 'disclosed_date', 'amount_range',
               'price_change', 'excess_return', 'spy_change', 'source']
    return pd.DataFrame(columns=columns)


@st.cache_data(ttl=300, show_spinner=False)  # 5 minutos - aumentado para mejor performance
def get_stock_data(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    """Obtiene datos completos de un stock"""
    try:
        stock = yf.Ticker(ticker)

        # Datos de precio
        hist = stock.history(period=period)
        info = stock.info

        # Calcular métricas técnicas básicas
        if not hist.empty:
            close = hist['Close']

            # RSI (14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if not rsi.empty else 50

            # MACD
            exp12 = close.ewm(span=12, adjust=False).mean()
            exp26 = close.ewm(span=26, adjust=False).mean()
            macd = exp12 - exp26
            signal_line = macd.ewm(span=9, adjust=False).mean()
            macd_current = macd.iloc[-1] if not macd.empty else 0
            signal_current = signal_line.iloc[-1] if not signal_line.empty else 0
            macd_bullish = macd_current > signal_current

            # Bollinger Bands
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            bb_upper = sma20 + (std20 * 2)
            bb_lower = sma20 - (std20 * 2)
            current_price = close.iloc[-1]
            bb_position = "Middle"
            if current_price > bb_upper.iloc[-1]:
                bb_position = "Above Upper"
            elif current_price < bb_lower.iloc[-1]:
                bb_position = "Below Lower"

            # Momentum
            if len(close) >= 20:
                momentum_1m = ((close.iloc[-1] / close.iloc[-20]) - 1) * 100
            else:
                momentum_1m = 0

            if len(close) >= 60:
                momentum_3m = ((close.iloc[-1] / close.iloc[-60]) - 1) * 100
            else:
                momentum_3m = momentum_1m

            # Volume
            avg_volume = hist['Volume'].rolling(20).mean().iloc[-1] if len(hist) >= 20 else hist['Volume'].mean()
            current_volume = hist['Volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # VWAP (diario)
            typical_price = (hist['High'] + hist['Low'] + hist['Close']) / 3
            vwap = (typical_price * hist['Volume']).cumsum() / hist['Volume'].cumsum()
            current_vwap = vwap.iloc[-1] if not vwap.empty else current_price

        else:
            current_rsi = 50
            macd_bullish = False
            bb_position = "N/A"
            momentum_1m = 0
            momentum_3m = 0
            volume_ratio = 1
            current_price = 0
            current_vwap = 0

        return {
            'ticker': ticker,
            'price': info.get('currentPrice', info.get('regularMarketPrice', current_price if not hist.empty else 0)),
            'change_pct': info.get('regularMarketChangePercent', 0),
            'history': hist,
            'info': info,

            # Técnicos
            'rsi': round(current_rsi, 1),
            'macd_bullish': macd_bullish,
            'macd_signal': "Alcista" if macd_bullish else "Bajista",
            'bb_position': bb_position,
            'volume_ratio': round(volume_ratio, 2),
            'vwap': round(current_vwap, 2),
            'momentum_1m': round(momentum_1m, 1),
            'momentum_3m': round(momentum_3m, 1),

            # Fundamentales
            'pe_ratio': info.get('trailingPE', info.get('forwardPE', 0)),
            'forward_pe': info.get('forwardPE', 0),
            'ps_ratio': info.get('priceToSalesTrailing12Months', 0),
            'pb_ratio': info.get('priceToBook', 0),
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0,
            'profit_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
            'operating_margin': info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0,
            'gross_margin': info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0,
            'debt_to_equity': info.get('debtToEquity', 0),
            'current_ratio': info.get('currentRatio', 0),
            'quick_ratio': info.get('quickRatio', 0),
            'market_cap': info.get('marketCap', 0),
            'enterprise_value': info.get('enterpriseValue', 0),
            'ev_ebitda': info.get('enterpriseToEbitda', 0),
            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,

            # Meta
            'company_name': info.get('longName', info.get('shortName', ticker)),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
        }

    except Exception as e:
        return {
            'ticker': ticker,
            'error': str(e),
            'price': 0,
            'rsi': 50,
            'macd_bullish': False,
            'momentum_1m': 0,
        }


@st.cache_data(ttl=300)  # 5 minutos
def get_multi_horizon_scores(tickers: List[str]) -> pd.DataFrame:
    """Calcula scores multi-horizonte para lista de tickers"""
    try:
        from webapp.scoring.multi_horizon import MultiHorizonScorer

        scorer = MultiHorizonScorer()
        results = []

        failed_tickers = []

        for ticker in tickers:
            try:
                stock_data = get_stock_data(ticker)

                if 'error' in stock_data:
                    failed_tickers.append((ticker, stock_data.get('error', 'Unknown error')))
                    continue

                # Preparar datos para el scorer (mapear a nombres esperados)
                # Con valores por defecto seguros para evitar errores
                rsi = stock_data.get('rsi', 50) or 50
                macd_bullish = stock_data.get('macd_bullish', False)
                momentum_1m = stock_data.get('momentum_1m', 0) or 0
                momentum_3m = stock_data.get('momentum_3m', 0) or 0

                # Determinar señal MACD
                if macd_bullish and momentum_1m > 3:
                    macd_signal = 'bullish_cross'
                elif macd_bullish:
                    macd_signal = 'bullish'
                elif not macd_bullish and momentum_1m < -3:
                    macd_signal = 'bearish_cross'
                elif not macd_bullish:
                    macd_signal = 'bearish'
                else:
                    macd_signal = 'neutral'

                # Determinar posición BB (convertir string a número 0-100)
                bb_pos_str = str(stock_data.get('bb_position', 'Middle'))
                if 'Below' in bb_pos_str:
                    bb_position_num = 15  # Cerca de banda inferior
                    vp_position = 'near_support'
                elif 'Above' in bb_pos_str:
                    bb_position_num = 85  # Cerca de banda superior
                    vp_position = 'near_resistance'
                else:
                    bb_position_num = 50  # En el medio
                    vp_position = 'neutral'

                scoring_data = {
                    'ticker': ticker,
                    'price': stock_data['price'],
                    'vwap': stock_data['vwap'],

                    # Técnicos (nombres esperados por el scorer)
                    'rsi_14': rsi,
                    'macd_signal': macd_signal,
                    'volume_profile_position': vp_position,
                    'bollinger_position': bb_position_num,  # 0-100 numeric
                    'volume_ratio': stock_data['volume_ratio'],

                    # Momentum
                    'momentum_1w': momentum_1m / 4,  # Aproximación
                    'momentum_1m': momentum_1m,
                    'momentum_3m': momentum_3m,
                    'momentum_6m': momentum_3m * 1.5,  # Aproximación

                    # Fundamentales
                    'pe_ratio': stock_data['pe_ratio'] or 20,
                    'pb_ratio': stock_data['pb_ratio'] or 3,
                    'ev_ebitda': stock_data['ev_ebitda'] or 15,
                    'roe': stock_data['roe'] or 15,
                    'roic': stock_data['roe'] * 0.8 if stock_data['roe'] else 12,
                    'profit_margin': stock_data['profit_margin'] or 10,
                    'gross_margin': stock_data['gross_margin'] or 30,
                    'operating_margin': stock_data['operating_margin'] or 15,
                    'debt_to_equity': stock_data['debt_to_equity'] or 50,
                    'debt_ebitda': (stock_data['debt_to_equity'] or 50) / 30,
                    'current_ratio': stock_data['current_ratio'] or 1.5,
                    'interest_coverage': 10,  # Default
                    'dividend_yield': stock_data['dividend_yield'] or 0,
                    'dividend_growth': 3,  # Default

                    # Sector info
                    'sector': stock_data['sector'],
                    'company_name': stock_data['company_name'],
                    'sector_pe_median': 20,  # Default

                    # Especulativos - calcular dinámicamente
                    # UPDATED: More aggressive scoring to match original Excel patterns
                    # Congress score based on momentum + fundamentals as proxy
                    'congress_score': _calculate_speculative_score(
                        momentum_1m, momentum_3m,
                        stock_data.get('roe', 15),
                        stock_data.get('volume_ratio', 1.0)
                    ),
                    # News sentiment proxy: more aggressive - momentum drives sentiment
                    'news_sentiment': min(max(50 + (momentum_1m * 2.0) + (momentum_3m * 0.8), 10), 90),
                    # Options flow proxy: high volume + momentum = bullish flow
                    'options_flow': min(max(50 + ((stock_data.get('volume_ratio', 1.0) - 1) * 20) + (momentum_1m * 1.0), 10), 90),
                    'analyst_revisions': momentum_3m * 0.5,  # Proxy from momentum - more aggressive
                    'earnings_surprise': momentum_1m * 0.8,  # Proxy from recent move - more aggressive
                }

                # Calcular scores
                result = scorer.calculate_all_horizons(scoring_data)

                company_name = stock_data.get('company_name', ticker) or ticker
                sector = stock_data.get('sector', 'N/A') or 'N/A'
                price = stock_data.get('price', 0) or 0

                results.append({
                    'Ticker': ticker,
                    'Empresa': company_name[:30] if len(company_name) > 30 else company_name,
                    'Sector': sector,
                    'Precio': f"${price:.2f}" if price else 'N/A',
                    'Score CP': result.short_term.total_score,
                    'Señal CP': result.short_term.signal.value,
                    'Score MP': result.medium_term.total_score,
                    'Señal MP': result.medium_term.signal.value,
                    'Score LP': result.long_term.total_score,
                    'Señal LP': result.long_term.signal.value,
                })

            except Exception as e:
                failed_tickers.append((ticker, str(e)))
                continue

        # Mostrar advertencia si hay tickers que fallaron
        if failed_tickers:
            failed_list = ', '.join([f"{t} ({e[:30]})" for t, e in failed_tickers[:5]])
            st.warning(f"No se pudieron calcular {len(failed_tickers)} tickers: {failed_list}")

        return pd.DataFrame(results) if results else pd.DataFrame()

    except Exception as e:
        st.error(f"Error calculating scores: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600)  # 10 minutos
def get_monetary_data() -> Dict[str, Any]:
    """Obtiene datos de monetary plumbing"""
    try:
        # Import dinámico con path correcto
        import importlib.util
        monetary_path = ROOT_DIR / 'integrations' / 'monetary_plumbing.py'

        if monetary_path.exists():
            spec = importlib.util.spec_from_file_location("monetary_plumbing", monetary_path)
            monetary_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(monetary_module)

            # Usar nombres correctos de funciones
            net_liq = monetary_module.calculate_net_liquidity()
            vix_data = monetary_module.get_vix()
            move_data = monetary_module.get_move_index()
            credit = monetary_module.get_credit_spreads()
            japan = monetary_module.get_japan_indicators()
            regime = monetary_module.analyze_monetary_regime()

            return {
                'net_liquidity': net_liq,
                'volatility': {
                    'vix': vix_data.get('current', 15),
                    'move': move_data.get('current', 90),
                },
                'credit': credit,
                'japan': japan,
                'regime': {
                    'name': regime.get('regime', 'NEUTRAL'),
                    'score': regime.get('score', 50),
                },
            }
        else:
            raise FileNotFoundError(f"monetary_plumbing.py not found at {monetary_path}")

    except Exception as e:
        # Fallback data
        return {
            'net_liquidity': {'current': 5800, 'change_1m': 2.3},
            'volatility': {'vix': 14.2, 'move': 92},
            'credit': {'ig_spread': 285},
            'japan': {'usdjpy': 156.2},
            'regime': {'name': 'ABUNDANT', 'score': 68},
            'error': str(e)
        }


@st.cache_data(ttl=300)
def get_congress_trades_for_ticker(ticker: str, days: int = 365) -> pd.DataFrame:
    """Obtiene trades de congresistas para un ticker específico"""
    all_trades = get_congress_trades(days)

    if all_trades.empty:
        return pd.DataFrame()

    ticker_trades = all_trades[all_trades['ticker'].str.upper() == ticker.upper()].copy()
    return ticker_trades


@st.cache_data(ttl=300)
def get_congress_stats(days: int = 90) -> Dict[str, Any]:
    """Obtiene estadísticas agregadas de congress trades"""
    trades = get_congress_trades(days)

    if trades.empty:
        return {
            'total_trades': 0,
            'total_politicians': 0,
            'total_tickers': 0,
            'buys': 0,
            'sells': 0,
        }

    return {
        'total_trades': len(trades),
        'total_politicians': trades['politician'].nunique() if 'politician' in trades.columns else 0,
        'total_tickers': trades['ticker'].nunique() if 'ticker' in trades.columns else 0,
        'buys': len(trades[trades['transaction_type'] == 'buy']) if 'transaction_type' in trades.columns else 0,
        'sells': len(trades[trades['transaction_type'] == 'sell']) if 'transaction_type' in trades.columns else 0,
    }


@st.cache_data(ttl=300)
def get_top_traded_tickers(days: int = 30, top_n: int = 5) -> Dict[str, pd.DataFrame]:
    """Obtiene los tickers más comprados y vendidos"""
    trades = get_congress_trades(days)

    if trades.empty:
        return {'buys': pd.DataFrame(), 'sells': pd.DataFrame()}

    # Top compras
    if 'transaction_type' in trades.columns and 'ticker' in trades.columns:
        buys = trades[trades['transaction_type'] == 'buy']
        buy_counts = buys.groupby('ticker').agg({
            'politician': 'nunique',
            'ticker': 'count'
        }).rename(columns={'politician': 'Políticos', 'ticker': 'Compras'})
        buy_counts = buy_counts.sort_values('Compras', ascending=False).head(top_n).reset_index()
        buy_counts.columns = ['Ticker', 'Políticos', 'Compras']

        # Top ventas
        sells = trades[trades['transaction_type'] == 'sell']
        sell_counts = sells.groupby('ticker').agg({
            'politician': 'nunique',
            'ticker': 'count'
        }).rename(columns={'politician': 'Políticos', 'ticker': 'Ventas'})
        sell_counts = sell_counts.sort_values('Ventas', ascending=False).head(top_n).reset_index()
        sell_counts.columns = ['Ticker', 'Políticos', 'Ventas']

        return {'buys': buy_counts, 'sells': sell_counts}

    return {'buys': pd.DataFrame(), 'sells': pd.DataFrame()}


def filter_congress_trades(
    df: pd.DataFrame,
    politician: str = "",
    chamber: str = "All",
    party: str = "All",
    transaction_type: str = "All",
    ticker: str = "",
    days: int = 90
) -> pd.DataFrame:
    """Filtra trades de congresistas según criterios"""
    if df.empty:
        return df

    filtered = df.copy()

    # Filtro por político - busca por cualquier palabra
    if politician and 'politician' in filtered.columns:
        # Dividir en palabras y buscar cualquiera
        search_words = politician.strip().split()
        if search_words:
            # Buscar cualquier palabra del input
            pattern = '|'.join(search_words)
            filtered = filtered[filtered['politician'].str.contains(pattern, case=False, na=False, regex=True)]

    # Filtro por cámara
    if chamber != "All" and 'chamber' in filtered.columns:
        filtered = filtered[filtered['chamber'].str.contains(chamber, case=False, na=False)]

    # Filtro por partido
    if party != "All" and 'party' in filtered.columns:
        party_code = 'R' if 'Republican' in party else ('D' if 'Democrat' in party else party)
        filtered = filtered[filtered['party'] == party_code]

    # Filtro por tipo de transacción
    if transaction_type != "All" and 'transaction_type' in filtered.columns:
        tx_type = transaction_type.lower()
        filtered = filtered[filtered['transaction_type'] == tx_type]

    # Filtro por ticker
    if ticker and 'ticker' in filtered.columns:
        filtered = filtered[filtered['ticker'].str.contains(ticker, case=False, na=False)]

    # Filtro por días
    if 'traded_date' in filtered.columns:
        cutoff = datetime.now() - timedelta(days=days)
        filtered['traded_date'] = pd.to_datetime(filtered['traded_date'], errors='coerce')
        filtered = filtered[filtered['traded_date'] >= cutoff]

    return filtered


# =============================================================================
# MARKET OVERVIEW
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)  # 5 minutos
def get_market_indices() -> Dict[str, Dict]:
    """Obtiene datos de índices principales"""
    indices = {
        'SPY': 'S&P 500',
        'QQQ': 'Nasdaq 100',
        'IWM': 'Russell 2000',
        'DIA': 'Dow Jones',
    }

    result = {}
    for symbol, name in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d')
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = ((current / prev) - 1) * 100
                result[symbol] = {
                    'name': name,
                    'price': current,
                    'change': change,
                }
        except:
            pass

    return result


@st.cache_data(ttl=300, show_spinner=False)  # 5 minutos
def get_vix() -> Dict[str, float]:
    """Obtiene VIX actual"""
    try:
        vix = yf.Ticker('^VIX')
        hist = vix.history(period='5d')
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
            return {
                'current': current,
                'change': current - prev,
            }
    except:
        pass
    return {'current': 0, 'change': 0}


@st.cache_data(ttl=300, show_spinner=False)
def get_all_scores_batch(tickers: tuple) -> pd.DataFrame:
    """
    Batch load scores for all tickers in a single cached call.
    Uses tuple for tickers to make it hashable for caching.
    """
    return get_multi_horizon_scores(list(tickers))


def warm_cache(tickers: List[str]):
    """
    Pre-warm the cache by loading all ticker data.
    Called once at app startup to prevent slow first-load times.
    """
    # Convert to tuple for caching
    tickers_tuple = tuple(tickers)

    # Pre-load critical data in parallel-ish manner
    # (Streamlit cache will store the results)
    try:
        get_vix()
        get_market_indices()
        get_all_scores_batch(tickers_tuple)
    except Exception as e:
        print(f"Cache warm-up error (non-critical): {e}")
