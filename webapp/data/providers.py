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


def detect_trendline_breakout(hist, lookback: int = 60, min_touches: int = 3) -> Dict[str, Any]:
    """
    Detect bearish trendline and proximity to breakout.
    Fits linear regression on descending swing highs.
    Returns trendline_score: 50=neutral, 70-85=imminent, 85+=confirmed breakout.
    """
    import numpy as np
    if hist is None or len(hist) < max(lookback, 30):
        return {'has_bearish_trendline': False, 'trendline_score': 50,
                'breakout_imminent': False, 'breakout_confirmed': False}

    n = min(lookback, len(hist))
    high = hist['High'].values[-n:]
    close = hist['Close'].values[-n:]

    # Find swing highs: 5-bar local maxima
    swing_highs = []
    for i in range(2, len(high) - 2):
        if high[i] == max(high[i-2:i+3]):
            swing_highs.append((i, high[i]))

    if len(swing_highs) < min_touches:
        return {'has_bearish_trendline': False, 'trendline_score': 50,
                'breakout_imminent': False, 'breakout_confirmed': False}

    # Use most recent swing highs for regression
    recent = swing_highs[-min(6, len(swing_highs)):]
    x = np.array([sh[0] for sh in recent])
    y = np.array([sh[1] for sh in recent])
    slope, intercept = np.polyfit(x, y, 1)

    if slope >= 0:
        return {'has_bearish_trendline': False, 'trendline_score': 50,
                'breakout_imminent': False, 'breakout_confirmed': False}

    # Extrapolate trendline to current bar
    current_bar = len(close) - 1
    trendline_val = slope * current_bar + intercept
    current_price = close[-1]
    dist_pct = ((current_price - trendline_val) / trendline_val) * 100

    breakout_confirmed = dist_pct > 0.5
    breakout_imminent = -2.0 < dist_pct <= 0.5

    if breakout_confirmed:
        score = 85 + min(dist_pct * 5, 10)
    elif breakout_imminent:
        score = 70 + (2 + dist_pct) * 7.5
    elif dist_pct > -5:
        score = 55 + (5 + dist_pct) * 3
    else:
        score = 40

    return {
        'has_bearish_trendline': True,
        'trendline_slope': slope,
        'distance_to_trendline_pct': dist_pct,
        'breakout_confirmed': breakout_confirmed,
        'breakout_imminent': breakout_imminent,
        'trendline_score': min(max(score, 5), 95),
        'trendline_value_today': trendline_val,
    }


def detect_rsi_crossover(rsi_series, threshold: int = 30, lookback: int = 5) -> Dict[str, Any]:
    """
    Detect RSI crossing above oversold (bullish) or below overbought (bearish).
    Returns rsi_crossover_score: 85 for fresh bullish cross, 20 for bearish.
    """
    if rsi_series is None or len(rsi_series) < lookback + 1:
        return {'bullish_crossover': False, 'bearish_crossover': False, 'rsi_crossover_score': 50}

    recent = rsi_series.iloc[-(lookback + 1):]
    bullish_cross = False
    bearish_cross = False
    bars_since = lookback

    for i in range(1, len(recent)):
        if recent.iloc[i - 1] < threshold and recent.iloc[i] >= threshold:
            bullish_cross = True
            bars_since = len(recent) - 1 - i
        if recent.iloc[i - 1] > (100 - threshold) and recent.iloc[i] <= (100 - threshold):
            bearish_cross = True
            bars_since = len(recent) - 1 - i

    if bullish_cross:
        score = 85 - (bars_since * 5)
    elif bearish_cross:
        score = 20 + (bars_since * 5)
    else:
        score = 50

    return {
        'bullish_crossover': bullish_cross,
        'bearish_crossover': bearish_cross,
        'bars_since_crossover': bars_since,
        'rsi_crossover_score': min(max(score, 5), 95),
    }


def detect_konkorde_divergence(hist, konkorde: Dict[str, Any], lookback: int = 10) -> Dict[str, Any]:
    """
    Detect divergence: azul (institutional) rising while price flat/down = stealth accumulation.
    Returns divergence_score: 75+ for bullish divergence.
    """
    import numpy as np
    if not konkorde or konkorde['azul'].empty or len(konkorde['azul']) < lookback:
        return {'bullish_divergence': False, 'bearish_divergence': False, 'divergence_score': 50}

    azul = konkorde['azul'].values[-lookback:]
    close = hist['Close'].values[-lookback:]
    x = np.arange(lookback)

    azul_slope = np.polyfit(x, azul, 1)[0]
    price_pct = (close[-1] / close[0] - 1) * 100

    bullish_div = azul_slope > 0.5 and price_pct < 2
    bearish_div = azul_slope < -0.5 and price_pct > -2

    if bullish_div:
        score = 75 + min(azul_slope * 5, 20)
    elif bearish_div:
        score = 25 - min(abs(azul_slope) * 5, 20)
    else:
        score = 50

    return {
        'bullish_divergence': bullish_div,
        'bearish_divergence': bearish_div,
        'divergence_score': min(max(score, 5), 95),
        'azul_trend': azul_slope,
        'price_trend': price_pct,
    }


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

    close = hist['Close'].fillna(method='ffill')
    high = hist['High'].fillna(method='ffill')
    low = hist['Low'].fillna(method='ffill')
    volume = hist['Volume'].fillna(0)

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


def _yf_retry(fn, retries=3, base_delay=2):
    """Execute a yfinance call with exponential backoff on rate limit."""
    import time
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e).lower()
            if 'too many requests' in err_str or 'rate limit' in err_str or '429' in err_str:
                if attempt < retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
            raise
    return None


@st.cache_data(ttl=300, show_spinner=False)  # 5 minutos - aumentado para mejor performance
def get_stock_data(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    """Obtiene datos completos de un stock"""
    try:
        stock = yf.Ticker(ticker)

        # Datos de precio (with retry on rate limit)
        hist = _yf_retry(lambda: stock.history(period=period))
        if hist is None:
            hist = pd.DataFrame()
        info = _yf_retry(lambda: stock.info)
        if info is None:
            info = {}

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
            'description': info.get('longBusinessSummary', ''),
            'website': info.get('website', ''),
            'employees': info.get('fullTimeEmployees', 0),
            'country': info.get('country', 'N/A'),
            'city': info.get('city', ''),
            'news': stock.news if hasattr(stock, 'news') else [],

            # Calendar & Events (para sección de noticias)
            'ex_dividend_date': info.get('exDividendDate'),
            'dividend_rate': info.get('dividendRate', 0),
            'earnings_date': info.get('earningsDate', [None])[0] if info.get('earningsDate') else None,

            # Institutional & Analyst
            'institutional_ownership': info.get('heldPercentInstitutions', 0) * 100 if info.get('heldPercentInstitutions') else 0,
            'insider_ownership': info.get('heldPercentInsiders', 0) * 100 if info.get('heldPercentInsiders') else 0,
            'target_price': info.get('targetMeanPrice', 0),
            'target_high': info.get('targetHighPrice', 0),
            'target_low': info.get('targetLowPrice', 0),
            'recommendation': info.get('recommendationKey', ''),
            'num_analysts': info.get('numberOfAnalystOpinions', 0),

            # Additional financials
            'revenue': info.get('totalRevenue', 0),
            'revenue_growth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
            'earnings_growth': info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0,
            'free_cash_flow': info.get('freeCashflow', 0),
            'beta': info.get('beta', 1),
            '52w_high': info.get('fiftyTwoWeekHigh', 0),
            '52w_low': info.get('fiftyTwoWeekLow', 0),

            # Extended financials for valuation models
            'total_debt': info.get('totalDebt', 0),
            'total_cash': info.get('totalCash', 0),
            'ebitda': info.get('ebitda', 0),
            'book_value': info.get('bookValue', 0),
            'trailing_eps': info.get('trailingEps', 0),
            'forward_eps': info.get('forwardEps', 0),
            'revenue_per_share': info.get('revenuePerShare', 0),
            'earnings_quarterly_growth': info.get('earningsQuarterlyGrowth', 0) * 100 if info.get('earningsQuarterlyGrowth') else 0,
            'peg_ratio': info.get('pegRatio', 0),
            'ev_revenue': info.get('enterpriseToRevenue', 0),
            'shares_outstanding': info.get('sharesOutstanding', 0),
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

                if not stock_data or not isinstance(stock_data, dict):
                    failed_tickers.append((ticker, 'No data returned'))
                    continue

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

                # Calculate Konkorde signal for scoring
                konkorde_score = 50  # Default neutral
                konkorde_signal = 'neutral'
                hist = stock_data.get('history')
                if hist is not None and not hist.empty and len(hist) >= 20:
                    try:
                        konkorde = calculate_konkorde(hist)
                        if not konkorde['azul'].empty:
                            latest_azul = konkorde['azul'].iloc[-1]
                            latest_verde = konkorde['verde'].iloc[-1]

                            # Determine Konkorde signal
                            if latest_azul > 0 and latest_verde > 0:
                                konkorde_signal = 'strong_bullish'  # Both buying
                                konkorde_score = 80 + min(latest_azul, 20)
                            elif latest_azul > 0 and latest_verde < 0:
                                konkorde_signal = 'accumulation'  # Smart money buying, retail selling
                                konkorde_score = 70 + min(latest_azul, 15)
                            elif latest_azul < 0 and latest_verde > 0:
                                konkorde_signal = 'distribution'  # Smart money selling, retail buying
                                konkorde_score = 30 - min(abs(latest_azul), 15)
                            elif latest_azul < 0 and latest_verde < 0:
                                konkorde_signal = 'strong_bearish'  # Both selling
                                konkorde_score = 20 - min(abs(latest_azul), 15)
                            else:
                                konkorde_signal = 'neutral'
                                konkorde_score = 50

                            # Clamp score to valid range
                            konkorde_score = max(5, min(95, konkorde_score))
                    except Exception:
                        pass  # Keep defaults if Konkorde calculation fails

                # Trendline breakout detection
                trendline_data = {'trendline_score': 50, 'breakout_imminent': False, 'breakout_confirmed': False}
                if hist is not None and not hist.empty and len(hist) >= 30:
                    try:
                        trendline_data = detect_trendline_breakout(hist)
                    except Exception:
                        pass

                # RSI crossover detection
                rsi_crossover_data = {'rsi_crossover_score': 50, 'bullish_crossover': False}
                if hist is not None and not hist.empty and len(hist) >= 20:
                    try:
                        delta = hist['Close'].diff()
                        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / (loss + 0.0001)
                        rsi_series = 100 - (100 / (1 + rs))
                        rsi_crossover_data = detect_rsi_crossover(rsi_series)
                    except Exception:
                        pass

                # Konkorde divergence (institutional accumulation while price flat)
                konkorde_div_data = {'divergence_score': 50, 'bullish_divergence': False}
                if hist is not None and not hist.empty and len(hist) >= 20:
                    try:
                        if 'konkorde' in dir() and konkorde and not konkorde['azul'].empty:
                            konkorde_div_data = detect_konkorde_divergence(hist, konkorde)
                    except Exception:
                        pass

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

                    # Konkorde signal (institutional vs retail flow)
                    'konkorde_score': konkorde_score,
                    'konkorde_signal': konkorde_signal,

                    # Trendline breakout
                    'trendline_score': trendline_data.get('trendline_score', 50),
                    'trendline_breakout_imminent': trendline_data.get('breakout_imminent', False),
                    'trendline_breakout_confirmed': trendline_data.get('breakout_confirmed', False),

                    # RSI crossover
                    'rsi_crossover_score': rsi_crossover_data.get('rsi_crossover_score', 50),
                    'rsi_bullish_crossover': rsi_crossover_data.get('bullish_crossover', False),

                    # Konkorde divergence
                    'konkorde_divergence_score': konkorde_div_data.get('divergence_score', 50),
                    'konkorde_bullish_divergence': konkorde_div_data.get('bullish_divergence', False),
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


@st.cache_data(ttl=3600, show_spinner=False)  # 1 hora - datos macro cambian lentamente
def get_economic_indicators() -> Dict[str, Dict]:
    """
    Obtiene indicadores económicos clave (empleo, inflación, GDP, etc.)
    Intenta usar FRED API primero, fallback a yfinance y datos hardcoded.
    """
    import os
    indicators = {}

    # Try FRED API first
    fred_api_key = os.environ.get('FRED_API_KEY', '')
    fred_data = {}

    if fred_api_key:
        try:
            from fredapi import Fred
            fred = Fred(api_key=fred_api_key)

            # Fetch key series
            series_map = {
                'UNRATE': 'unemployment',
                'CPIAUCSL': 'cpi',
                'PCEPI': 'pce',
                'GDPC1': 'gdp',
                'DFF': 'fed_funds',
                'T10Y2Y': 'yield_curve',
                'ICSA': 'jobless_claims',
                'PAYEMS': 'nonfarm_payrolls',
                'UMCSENT': 'consumer_sentiment',
            }

            for fred_id, key in series_map.items():
                try:
                    series = fred.get_series(fred_id, observation_start='2023-01-01')
                    if not series.empty:
                        current_val = series.iloc[-1]
                        prev_val = series.iloc[-2] if len(series) > 1 else current_val
                        fred_data[key] = {
                            'value': current_val,
                            'change': current_val - prev_val,
                            'source': 'FRED'
                        }
                except:
                    pass
        except:
            pass

    # Unemployment Rate
    if 'unemployment' in fred_data:
        indicators['unemployment'] = fred_data['unemployment']
    else:
        indicators['unemployment'] = {'value': 4.1, 'change': 0.1, 'source': 'Estimate'}

    # CPI (Inflation)
    if 'cpi' in fred_data:
        # Calculate YoY % change
        indicators['cpi_yoy'] = {
            'value': fred_data['cpi']['change'],
            'change': 0,
            'source': 'FRED'
        }
    else:
        indicators['cpi_yoy'] = {'value': 2.9, 'change': -0.2, 'source': 'Estimate'}

    # PCE (Fed's preferred inflation measure)
    if 'pce' in fred_data:
        indicators['pce_yoy'] = {
            'value': fred_data['pce']['change'],
            'change': 0,
            'source': 'FRED'
        }
    else:
        indicators['pce_yoy'] = {'value': 2.6, 'change': -0.1, 'source': 'Estimate'}

    # GDP Growth (quarterly annualized)
    if 'gdp' in fred_data:
        indicators['gdp_growth'] = fred_data['gdp']
    else:
        indicators['gdp_growth'] = {'value': 2.8, 'change': 0.3, 'source': 'Estimate'}

    # Fed Funds Rate
    if 'fed_funds' in fred_data:
        indicators['fed_funds'] = fred_data['fed_funds']
    else:
        indicators['fed_funds'] = {'value': 4.5, 'change': -0.25, 'source': 'Estimate'}

    # 10Y-2Y Yield Curve
    if 'yield_curve' in fred_data:
        indicators['yield_curve'] = fred_data['yield_curve']
    else:
        # Try yfinance for treasuries
        try:
            t10y = yf.Ticker('^TNX')
            t2y = yf.Ticker('^IRX')
            h10 = t10y.history(period='5d')
            h2 = t2y.history(period='5d')
            if not h10.empty and not h2.empty:
                spread = h10['Close'].iloc[-1] - h2['Close'].iloc[-1]
                indicators['yield_curve'] = {'value': spread, 'change': 0, 'source': 'yfinance'}
            else:
                indicators['yield_curve'] = {'value': 0.35, 'change': 0.05, 'source': 'Estimate'}
        except:
            indicators['yield_curve'] = {'value': 0.35, 'change': 0.05, 'source': 'Estimate'}

    # Initial Jobless Claims (weekly)
    if 'jobless_claims' in fred_data:
        indicators['jobless_claims'] = fred_data['jobless_claims']
    else:
        indicators['jobless_claims'] = {'value': 215000, 'change': -5000, 'source': 'Estimate'}

    # Nonfarm Payrolls (monthly change in thousands)
    if 'nonfarm_payrolls' in fred_data:
        # Calculate monthly change
        indicators['nonfarm_payrolls'] = {
            'value': fred_data['nonfarm_payrolls']['change'],
            'change': 0,
            'source': 'FRED'
        }
    else:
        indicators['nonfarm_payrolls'] = {'value': 256000, 'change': 50000, 'source': 'Estimate'}

    # Consumer Sentiment (Univ. of Michigan)
    if 'consumer_sentiment' in fred_data:
        indicators['consumer_sentiment'] = fred_data['consumer_sentiment']
    else:
        indicators['consumer_sentiment'] = {'value': 66.4, 'change': -1.2, 'source': 'Estimate'}

    # Oil Price (WTI via yfinance)
    try:
        oil = yf.Ticker('CL=F')
        oil_hist = oil.history(period='5d')
        if not oil_hist.empty:
            current = oil_hist['Close'].iloc[-1]
            prev = oil_hist['Close'].iloc[-2] if len(oil_hist) > 1 else current
            indicators['oil_wti'] = {
                'value': current,
                'change': current - prev,
                'source': 'yfinance'
            }
        else:
            indicators['oil_wti'] = {'value': 72.5, 'change': 1.2, 'source': 'Estimate'}
    except:
        indicators['oil_wti'] = {'value': 72.5, 'change': 1.2, 'source': 'Estimate'}

    # Dollar Index (DXY via yfinance)
    try:
        dxy = yf.Ticker('DX-Y.NYB')
        dxy_hist = dxy.history(period='5d')
        if not dxy_hist.empty:
            current = dxy_hist['Close'].iloc[-1]
            prev = dxy_hist['Close'].iloc[-2] if len(dxy_hist) > 1 else current
            indicators['dollar_index'] = {
                'value': current,
                'change': current - prev,
                'source': 'yfinance'
            }
        else:
            indicators['dollar_index'] = {'value': 106.2, 'change': 0.3, 'source': 'Estimate'}
    except:
        indicators['dollar_index'] = {'value': 106.2, 'change': 0.3, 'source': 'Estimate'}

    return indicators


@st.cache_data(ttl=300, show_spinner=False)
def get_all_ticker_changes() -> Dict[str, Dict]:
    """Batch download daily changes for all tickers in TICKER_UNIVERSE for heatmap."""
    from webapp.config import TICKER_UNIVERSE
    tickers = list(TICKER_UNIVERSE)
    results = {}
    try:
        data = yf.download(tickers, period='2d', group_by='ticker', progress=False, threads=True)
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    hist = data
                else:
                    hist = data[ticker] if ticker in data.columns.get_level_values(0) else None
                if hist is None or hist.empty:
                    continue
                closes = hist['Close'].dropna()
                if len(closes) < 2:
                    continue
                current = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                change = ((current / prev) - 1) * 100
                results[ticker] = {'price': current, 'change': change}
            except Exception:
                continue
    except Exception:
        pass
    return results


@st.cache_data(ttl=300, show_spinner=False)
def get_sector_momentum() -> Dict[str, Dict]:
    """Calculate momentum (1W, 1M, 3M) for sector ETFs."""
    SECTOR_ETFS = {
        'Technology': 'XLK', 'Healthcare': 'XLV', 'Financials': 'XLF',
        'Energy': 'XLE', 'Consumer Disc.': 'XLY', 'Consumer Staples': 'XLP',
        'Industrials': 'XLI', 'Materials': 'XLB', 'Utilities': 'XLU',
        'Real Estate': 'XLRE', 'Communication': 'XLC', 'Semiconductors': 'SMH',
    }
    results = {}
    try:
        tickers = list(SECTOR_ETFS.values())
        data = yf.download(tickers, period='4mo', group_by='ticker', progress=False, threads=True)
        for sector_name, etf in SECTOR_ETFS.items():
            try:
                if len(tickers) == 1:
                    hist = data
                else:
                    hist = data[etf] if etf in data.columns.get_level_values(0) else None
                if hist is None or hist.empty:
                    continue
                closes = hist['Close'].dropna()
                if len(closes) < 5:
                    continue
                current = float(closes.iloc[-1])
                mom_1w = ((current / float(closes.iloc[-5])) - 1) * 100 if len(closes) >= 5 else 0
                mom_1m = ((current / float(closes.iloc[-20])) - 1) * 100 if len(closes) >= 20 else mom_1w
                mom_3m = ((current / float(closes.iloc[-60])) - 1) * 100 if len(closes) >= 60 else mom_1m
                results[sector_name] = {
                    'etf': etf, 'price': current,
                    'mom_1w': round(mom_1w, 2),
                    'mom_1m': round(mom_1m, 2),
                    'mom_3m': round(mom_3m, 2),
                }
            except Exception:
                continue
    except Exception:
        pass
    return results


@st.cache_data(ttl=180, show_spinner=False)
def get_global_futures() -> Dict[str, Dict]:
    """
    Fetch global futures, indices, commodities, rates, FX, and crypto.
    Returns dict with price, change, prev_close for each instrument.
    Includes both futures (ES=F) and spot indices (^GSPC) for dashboard grid.
    """
    import time

    INSTRUMENTS = {
        # US Futures
        'ES=F':      {'name': 'S&P 500 Fut',   'region': 'US',     'type': 'equity'},
        'NQ=F':      {'name': 'Nasdaq Fut',     'region': 'US',     'type': 'equity'},
        'YM=F':      {'name': 'Dow Fut',        'region': 'US',     'type': 'equity'},
        'RTY=F':     {'name': 'Russell Fut',    'region': 'US',     'type': 'equity'},
        # US Spot Indices (for grid)
        '^GSPC':     {'name': 'S&P 500',        'region': 'US',     'type': 'index'},
        '^IXIC':     {'name': 'Nasdaq',         'region': 'US',     'type': 'index'},
        '^DJI':      {'name': 'Dow',            'region': 'US',     'type': 'index'},
        '^RUT':      {'name': 'Russell 2000',   'region': 'US',     'type': 'index'},
        # Europe
        '^STOXX50E': {'name': 'Euro Stoxx 50',  'region': 'Europe', 'type': 'equity'},
        '^FTSE':     {'name': 'FTSE 100',       'region': 'Europe', 'type': 'equity'},
        '^GDAXI':    {'name': 'DAX',            'region': 'Europe', 'type': 'equity'},
        '^IBEX':     {'name': 'IBEX 35',        'region': 'Europe', 'type': 'equity'},
        # Asia
        '^N225':     {'name': 'Nikkei 225',     'region': 'Asia',   'type': 'equity'},
        '^HSI':      {'name': 'Hang Seng',      'region': 'Asia',   'type': 'equity'},
        '000001.SS': {'name': 'Shanghai',       'region': 'Asia',   'type': 'equity'},
        # Commodities
        'GC=F':      {'name': 'Gold',           'region': 'Global', 'type': 'commodity'},
        'SI=F':      {'name': 'Silver',         'region': 'Global', 'type': 'commodity'},
        'CL=F':      {'name': 'Crude Oil WTI',  'region': 'Global', 'type': 'commodity'},
        'BZ=F':      {'name': 'Brent Oil',      'region': 'Global', 'type': 'commodity'},
        'NG=F':      {'name': 'Natural Gas',    'region': 'Global', 'type': 'commodity'},
        'HG=F':      {'name': 'Copper',         'region': 'Global', 'type': 'commodity'},
        # Rates & FX
        '^TNX':      {'name': '10Y Yield',      'region': 'US',     'type': 'rate'},
        '^TYX':      {'name': '30Y Yield',      'region': 'US',     'type': 'rate'},
        '^FVX':      {'name': '5Y Yield',       'region': 'US',     'type': 'rate'},
        '^IRX':      {'name': '3M T-Bill',      'region': 'US',     'type': 'rate'},
        'DX-Y.NYB':  {'name': 'DXY',            'region': 'Global', 'type': 'fx'},
        'EURUSD=X':  {'name': 'EUR/USD',        'region': 'Global', 'type': 'fx'},
        'GBPUSD=X':  {'name': 'GBP/USD',        'region': 'Global', 'type': 'fx'},
        'JPY=X':     {'name': 'USD/JPY',        'region': 'Global', 'type': 'fx'},
        # Bonds (futures)
        'ZB=F':      {'name': '30Y Bond Fut',   'region': 'US',     'type': 'bond'},
        'ZN=F':      {'name': '10Y Note Fut',   'region': 'US',     'type': 'bond'},
        # Crypto
        'BTC-USD':   {'name': 'Bitcoin',        'region': 'Global', 'type': 'crypto'},
        'ETH-USD':   {'name': 'Ethereum',       'region': 'Global', 'type': 'crypto'},
        'SOL-USD':   {'name': 'Solana',         'region': 'Global', 'type': 'crypto'},
        # Volatility
        '^VIX':      {'name': 'VIX',            'region': 'US',     'type': 'volatility'},
    }

    tickers = list(INSTRUMENTS.keys())
    results = {}

    # Download in two batches to reduce rate limit risk
    batch_size = 25
    for batch_start in range(0, len(tickers), batch_size):
        batch = tickers[batch_start:batch_start + batch_size]
        try:
            data = yf.download(batch, period='5d', group_by='ticker', progress=False, threads=True)
            for ticker in batch:
                try:
                    if len(batch) == 1:
                        hist = data
                    else:
                        hist = data[ticker] if ticker in data.columns.get_level_values(0) else None
                    if hist is None or hist.empty:
                        continue
                    closes = hist['Close'].dropna()
                    if len(closes) < 2:
                        continue
                    current = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2])
                    change_pct = ((current / prev) - 1) * 100
                    change_abs = current - prev
                    meta = INSTRUMENTS[ticker]
                    results[ticker] = {
                        'name': meta['name'],
                        'region': meta['region'],
                        'type': meta['type'],
                        'price': current,
                        'prev_close': prev,
                        'change_pct': change_pct,
                        'change_abs': change_abs,
                        'change': change_pct,  # alias for dashboard grid
                    }
                except Exception:
                    continue
        except Exception:
            pass
        if batch_start + batch_size < len(tickers):
            time.sleep(0.5)  # Small delay between batches

    return results


@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings_calendar(tickers: tuple) -> List[Dict]:
    """
    Get upcoming earnings dates for tickers in the universe.
    Returns list of dicts: {ticker, company, date, eps_estimate, revenue_estimate}.
    """
    from datetime import date
    results = []
    today = date.today()
    cutoff = today + timedelta(days=30)

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar
            if cal is None or (isinstance(cal, pd.DataFrame) and cal.empty):
                continue
            # yfinance returns calendar as dict or DataFrame depending on version
            if isinstance(cal, pd.DataFrame):
                if 'Earnings Date' in cal.columns:
                    earn_date = cal['Earnings Date'].iloc[0]
                elif 'Earnings Date' in cal.index:
                    earn_date = cal.loc['Earnings Date'].iloc[0]
                else:
                    continue
                eps_est = cal.loc['EPS Estimate'].iloc[0] if 'EPS Estimate' in cal.index else None
                rev_est = cal.loc['Revenue Estimate'].iloc[0] if 'Revenue Estimate' in cal.index else None
            elif isinstance(cal, dict):
                earn_dates = cal.get('Earnings Date', [])
                if not earn_dates:
                    continue
                earn_date = earn_dates[0] if isinstance(earn_dates, list) else earn_dates
                eps_est = cal.get('EPS Estimate')
                rev_est = cal.get('Revenue Estimate')
            else:
                continue

            # Normalize date
            if hasattr(earn_date, 'date'):
                earn_date_d = earn_date.date()
            elif isinstance(earn_date, str):
                earn_date_d = datetime.strptime(earn_date[:10], '%Y-%m-%d').date()
            else:
                earn_date_d = earn_date

            # Only include upcoming (next 30 days)
            if today <= earn_date_d <= cutoff:
                info = stock.info or {}
                results.append({
                    'ticker': ticker,
                    'company': info.get('shortName', ticker),
                    'date': str(earn_date_d),
                    'eps_estimate': float(eps_est) if eps_est is not None else None,
                    'revenue_estimate': float(rev_est) if rev_est is not None else None,
                    'market_cap': info.get('marketCap', 0),
                })
        except Exception:
            continue

    # Sort by date
    results.sort(key=lambda x: x['date'])
    return results


@st.cache_data(ttl=1800, show_spinner=False)
def get_market_news() -> List[Dict]:
    """
    Get top market news from yfinance (Yahoo Finance RSS).
    Returns list of dicts: {title, link, publisher, date, tickers}.
    """
    results = []
    try:
        # Use SPY as proxy to get general market news
        for symbol in ['SPY', 'QQQ', '^GSPC']:
            try:
                stock = yf.Ticker(symbol)
                news = stock.news
                if news:
                    for item in news[:10]:
                        title = item.get('title', item.get('content', {}).get('title', ''))
                        if not title:
                            continue
                        # Deduplicate by title
                        if any(r['title'] == title for r in results):
                            continue
                        # Handle different yfinance news formats
                        publisher = item.get('publisher', item.get('content', {}).get('provider', {}).get('displayName', ''))
                        link = item.get('link', item.get('content', {}).get('canonicalUrl', {}).get('url', ''))
                        pub_date = item.get('providerPublishTime', '')
                        if isinstance(pub_date, (int, float)):
                            pub_date = datetime.fromtimestamp(pub_date).strftime('%Y-%m-%d %H:%M')
                        elif not pub_date:
                            pub_date = item.get('content', {}).get('pubDate', '')
                        related = item.get('relatedTickers', [])
                        if not related:
                            related = [t.get('symbol', '') for t in item.get('content', {}).get('finance', {}).get('stockTickers', [])]
                        results.append({
                            'title': title,
                            'link': link,
                            'publisher': publisher,
                            'date': str(pub_date)[:16],
                            'tickers': related[:5],
                        })
            except Exception:
                continue
    except Exception:
        pass

    # Deduplicate and limit
    return results[:15]


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


# =============================================================================
# RISK EXPOSURE ENGINE PROVIDERS
# =============================================================================

@st.cache_data(ttl=600, show_spinner=False)  # 10 minutos
def get_risk_exposure_score(manual_inputs: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Run the Risk Exposure Engine and return full results.
    Cached for 10 minutes to avoid re-running on every page load.
    """
    try:
        import importlib.util
        engine_path = ROOT_DIR / 'risk_exposure_engine.py'

        if not engine_path.exists():
            return _get_fallback_risk_data()

        spec = importlib.util.spec_from_file_location("risk_exposure_engine", engine_path)
        engine_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine_module)

        RiskExposureEngine = engine_module.RiskExposureEngine

        import os
        engine = RiskExposureEngine(
            data_dir=str(ROOT_DIR),
            fred_api_key=os.environ.get('FRED_API_KEY', ''),
        )

        if manual_inputs is None:
            manual_inputs = _get_default_manual_inputs()

        results = engine.run(manual_inputs=manual_inputs)
        return results

    except Exception as e:
        print(f"Risk Engine error: {e}")
        return _get_fallback_risk_data()


def _get_default_manual_inputs() -> Dict:
    """Default manual inputs for the risk engine when no file is provided."""
    import json
    manual_inputs_path = ROOT_DIR / 'manual_inputs.json'
    if manual_inputs_path.exists():
        try:
            with open(manual_inputs_path, 'r') as f:
                data = json.load(f)
            inputs = {}
            if 'valuations' in data:
                inputs['pe_forward'] = data['valuations'].get('pe_forward')
                inputs['cape_ratio'] = data['valuations'].get('cape_ratio')
                inputs['buffett_indicator'] = data['valuations'].get('buffett_indicator')
            if 'positioning' in data:
                inputs['put_call_ratio'] = data['positioning'].get('put_call_ratio')
                inputs['margin_debt_yoy'] = data['positioning'].get('margin_debt_yoy')
                inputs['reddit_sentiment'] = data['positioning'].get('reddit_sentiment')
            if 'cme_margin_changes' in data:
                inputs['cme_margin_changes'] = data['cme_margin_changes']
            if 'etf_anomalies' in data:
                inputs['etf_inflows'] = data['etf_anomalies']
            return inputs
        except Exception:
            pass
    # Hardcoded defaults
    return {
        'pe_forward': 22.2,
        'cape_ratio': 38.5,
        'buffett_indicator': 195,
        'put_call_ratio': 0.55,
        'margin_debt_yoy': 22,
        'reddit_sentiment': 82,
        'cme_margin_changes': [],
    }


def _get_fallback_risk_data() -> Dict[str, Any]:
    """Fallback risk data when engine is unavailable."""
    return {
        'final_score': 45,
        'regime': {
            'level': 'CAUTELA',
            'color': 'ORANGE',
            'emoji': '🟠',
            'action': 'REDUCIR especulativas. Cash 20-30%.',
            'description': 'Datos no disponibles. Score estimado.',
        },
        'allocation': {
            'equity': 45, 'bonds': 20, 'cash': 20,
            'gold_physical': 10, 'commodities': 5, 'crypto': 0,
            'notes': 'Datos estimados - actualizar con datos reales.',
        },
        'module_scores': {
            'liquidity_stress': 50,
            'market_technicals': 50,
            'valuation_excess': 50,
            'volatility_regime': 50,
            'positioning_crowding': 50,
            'macro_deterioration': 50,
        },
        'signals': ['Risk engine no disponible - usando estimaciones'],
        'alerts': [],
        'pattern_matches': [],
        'crash_probabilities': {
            'correction_5pct': {'probability': 35, 'label': 'Correccion >5%', 'reasoning': 'Sin datos'},
            'correction_10pct': {'probability': 20, 'label': 'Correccion >10%', 'reasoning': 'Sin datos'},
            'crash_20pct': {'probability': 8, 'label': 'Crash >20%', 'reasoning': 'Sin datos'},
            'rally_5pct': {'probability': 45, 'label': 'Rally >5%', 'reasoning': 'Sin datos'},
        },
        'module_explanations': {},
        'asset_scores': {},
        'error': True,
    }


def get_score_explanation(ticker: str, skip_congress: bool = False, include_options: bool = False) -> Dict[str, Any]:
    """
    Generate a comprehensive explanation of WHY a stock got its score.
    Analyzes: technicals, momentum, valuation, liquidity, debt, margins,
    congress trades, and polymarket signals.
    Set skip_congress=True to skip slow congress/polymarket API calls.
    Set include_options=True to include options/gamma analysis (adds ~10s).
    """
    stock_data = get_stock_data(ticker)
    if 'error' in stock_data:
        return {'error': stock_data['error']}

    scores_df = get_multi_horizon_scores([ticker])
    if scores_df.empty:
        return {'error': 'No scores available'}

    row = scores_df.iloc[0]

    # Extract all relevant data
    rsi = stock_data.get('rsi', 50)
    momentum_1m = stock_data.get('momentum_1m', 0) or 0
    momentum_3m = stock_data.get('momentum_3m', 0) or 0
    pe = stock_data.get('pe_ratio', 0) or 0
    forward_pe = stock_data.get('forward_pe', 0) or 0
    ps = stock_data.get('ps_ratio', 0) or 0
    pb = stock_data.get('pb_ratio', 0) or 0
    ev_ebitda = stock_data.get('ev_ebitda', 0) or 0
    peg = stock_data.get('peg_ratio', 0) or 0
    roe = stock_data.get('roe', 0) or 0
    roa = stock_data.get('roa', 0) or 0
    volume_ratio = stock_data.get('volume_ratio', 1) or 1
    macd_bullish = stock_data.get('macd_bullish', False)
    debt_equity = stock_data.get('debt_to_equity', 0) or 0
    profit_margin = stock_data.get('profit_margin', 0) or 0
    gross_margin = stock_data.get('gross_margin', 0) or 0
    operating_margin = stock_data.get('operating_margin', 0) or 0
    current_ratio = stock_data.get('current_ratio', 0) or 0
    quick_ratio = stock_data.get('quick_ratio', 0) or 0
    total_debt = stock_data.get('total_debt', 0) or 0
    total_cash = stock_data.get('total_cash', 0) or 0
    ebitda = stock_data.get('ebitda', 0) or 0
    fcf = stock_data.get('free_cash_flow', 0) or 0
    market_cap = stock_data.get('market_cap', 0) or 0
    rev_growth = stock_data.get('revenue_growth', 0) or 0
    earn_growth = stock_data.get('earnings_growth', 0) or 0
    beta = stock_data.get('beta', 1) or 1
    sector = stock_data.get('sector', '')
    price = stock_data.get('price', 0) or 0
    w52h = stock_data.get('52w_high', 0) or 0
    dividend_yield = stock_data.get('dividend_yield', 0) or 0
    target_price = stock_data.get('target_price', 0) or 0

    # Derived metrics
    w52l = stock_data.get('52w_low', 0) or 0
    book_value = stock_data.get('book_value', 0) or 0
    trailing_eps = stock_data.get('trailing_eps', 0) or 0
    forward_eps = stock_data.get('forward_eps', 0) or 0
    debt_ebitda = total_debt / ebitda if ebitda > 0 else 0
    net_debt = total_debt - total_cash
    fcf_yield = (fcf / market_cap * 100) if market_cap > 0 and fcf else 0
    pct_from_high = ((price - w52h) / w52h * 100) if w52h > 0 else 0
    pct_from_low = ((price - w52l) / w52l * 100) if w52l > 0 else 0
    analyst_upside = ((target_price - price) / price * 100) if price > 0 and target_price > 0 else 0

    # Price vs intrinsic value estimates
    graham_value = 0
    if trailing_eps > 0 and book_value > 0:
        graham_value = (22.5 * trailing_eps * book_value) ** 0.5
    dcf_upside = 0
    if forward_eps > 0 and price > 0:
        # Simple DCF: fair value = forward_eps * (8.5 + 2*growth_rate)
        growth = max(earn_growth, rev_growth) if earn_growth > 0 or rev_growth > 0 else 5
        dcf_fair = forward_eps * (8.5 + 2 * min(growth, 25))
        dcf_upside = ((dcf_fair - price) / price * 100) if dcf_fair > 0 else 0

    # Sector P/E benchmarks
    benchmarks = {'Technology': 30, 'Healthcare': 22, 'Financial Services': 14,
                  'Consumer Cyclical': 20, 'Energy': 12, 'Industrials': 18,
                  'Consumer Defensive': 22, 'Communication Services': 20, 'Utilities': 16,
                  'Real Estate': 30, 'Basic Materials': 15}
    sector_pe = benchmarks.get(sector, 20)

    # =========================================================================
    # Congress trades analysis (skipped if skip_congress=True)
    # =========================================================================
    congress_signal = 'neutral'
    congress_detail = ''
    if not skip_congress:
        try:
            trades = get_congress_trades_for_ticker(ticker, days=180)
            if not trades.empty:
                buys = len(trades[trades['transaction_type'] == 'buy']) if 'transaction_type' in trades.columns else 0
                sells = len(trades[trades['transaction_type'] == 'sell']) if 'transaction_type' in trades.columns else 0
                pols = trades['politician'].nunique() if 'politician' in trades.columns else 0
                if buys > sells and buys > 0:
                    congress_signal = 'bullish'
                    congress_detail = f'{buys} compras vs {sells} ventas por {pols} congresistas (6M)'
                elif sells > buys and sells > 0:
                    congress_signal = 'bearish'
                    congress_detail = f'{sells} ventas vs {buys} compras por {pols} congresistas (6M)'
                else:
                    congress_detail = f'{buys} compras, {sells} ventas por {pols} congresistas (6M)'
        except Exception:
            pass

    # =========================================================================
    # Polymarket signals analysis (skipped if skip_congress=True)
    # =========================================================================
    poly_signal = 'neutral'
    poly_detail = ''
    if not skip_congress:
        try:
            import importlib.util
            polymarket_path = ROOT_DIR / 'integrations' / 'polymarket_client.py'
            if polymarket_path.exists():
                spec = importlib.util.spec_from_file_location("polymarket_client", polymarket_path)
                pm = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(pm)
                client = pm.PolymarketClient()
                pm_signal = client.get_signal_for_ticker(ticker)
                if pm_signal.get('signal') != 'NO_DATA':
                    poly_signal = pm_signal.get('signal', 'NEUTRAL').lower()
                    n_markets = len(pm_signal.get('relevant_markets', []))
                    poly_detail = f"Score={pm_signal.get('score',50):.0f}, {n_markets} mercados, confianza={pm_signal.get('confidence','LOW')}"
        except Exception:
            pass

    # =========================================================================
    # Market liquidity / macro context (from risk engine + VIX)
    # =========================================================================
    vix_val = 0
    risk_score = 50
    risk_regime = 'CAUTELA'
    credit_stress = False
    try:
        vix_data = get_vix()
        vix_val = vix_data.get('current', 0) or 0
    except Exception:
        pass
    try:
        risk_data = get_risk_exposure_score()
        risk_score = risk_data.get('final_score', 50)
        risk_regime = risk_data.get('regime', {}).get('level', 'CAUTELA')
        # Check credit stress from module scores
        liq_stress = risk_data.get('module_scores', {}).get('liquidity_stress', 50)
        credit_stress = liq_stress >= 50
    except Exception:
        pass

    # =========================================================================
    # OPTIONS & GAMMA ANALYSIS (only if include_options=True)
    # =========================================================================
    gamma_regime = None  # 'positive' or 'negative'
    gamma_regime_strength = 0  # how strong the net gamma is
    pc_ratio_oi = 0
    pc_ratio_sentiment = 'neutral'
    call_wall_strike = 0
    put_wall_strike = 0
    gamma_wall_strike = 0
    hvl_strike = price
    expected_move = 0
    max_pain = price
    price_vs_call_wall_pct = 0
    price_vs_put_wall_pct = 0
    price_vs_max_pain_pct = 0
    skew_val = 0
    atm_iv_val = 0
    total_options_oi = 0

    if include_options:
     try:
        opt_stock = yf.Ticker(ticker)
        opt_expirations = opt_stock.options
        if opt_expirations:
            # Use nearest 2 expirations for a better signal
            import numpy as np
            from datetime import datetime as _dt

            all_call_gex = {}
            all_put_gex = {}
            _first_calls = None
            _first_puts = None

            for exp_idx, exp_str in enumerate(opt_expirations[:2]):
                try:
                    chain = opt_stock.option_chain(exp_str)
                    c_df = chain.calls.copy()
                    p_df = chain.puts.copy()
                    for _df in [c_df, p_df]:
                        if 'openInterest' in _df.columns:
                            _df['openInterest'] = _df['openInterest'].fillna(0).astype(float)
                        else:
                            _df['openInterest'] = 0.0

                    if exp_idx == 0:
                        _first_calls = c_df
                        _first_puts = p_df

                    exp_dt = _dt.strptime(exp_str, '%Y-%m-%d')
                    dte_i = max((exp_dt - _dt.now()).days, 1)
                    dte_w = 1.0 / (dte_i ** 0.5)

                    # IV for gaussian width
                    atm_range = (price * 0.95, price * 1.05)
                    atm_c = c_df[(c_df['strike'] >= atm_range[0]) & (c_df['strike'] <= atm_range[1])]
                    atm_p = p_df[(p_df['strike'] >= atm_range[0]) & (p_df['strike'] <= atm_range[1])]
                    c_iv = float(atm_c['impliedVolatility'].mean()) if not atm_c.empty else 0.3
                    p_iv = float(atm_p['impliedVolatility'].mean()) if not atm_p.empty else 0.3
                    avg_iv_dec = max((c_iv + p_iv) / 2, 0.15)
                    sigma_pct = max(avg_iv_dec * (dte_i / 365) ** 0.5, 0.02)

                    strike_range = (price * 0.85, price * 1.15)
                    cf = c_df[(c_df['strike'] >= strike_range[0]) & (c_df['strike'] <= strike_range[1])]
                    pf = p_df[(p_df['strike'] >= strike_range[0]) & (p_df['strike'] <= strike_range[1])]

                    for _, r in cf.iterrows():
                        s = r['strike']
                        oi = float(r.get('openInterest', 0) or 0)
                        if oi > 0:
                            m = (s - price) / price
                            gp = np.exp(-0.5 * (m / sigma_pct) ** 2)
                            gex = oi * gp * 100 * dte_w
                            all_call_gex[s] = all_call_gex.get(s, 0) + gex
                    for _, r in pf.iterrows():
                        s = r['strike']
                        oi = float(r.get('openInterest', 0) or 0)
                        if oi > 0:
                            m = (s - price) / price
                            gp = np.exp(-0.5 * (m / sigma_pct) ** 2)
                            gex = oi * gp * 100 * dte_w
                            all_put_gex[s] = all_put_gex.get(s, 0) + gex
                except Exception:
                    continue

            if _first_calls is not None and _first_puts is not None:
                total_call_oi = int(_first_calls['openInterest'].sum())
                total_put_oi = int(_first_puts['openInterest'].sum())
                total_options_oi = total_call_oi + total_put_oi
                pc_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0

                if pc_ratio_oi > 1.3:
                    pc_ratio_sentiment = 'very_bearish'
                elif pc_ratio_oi > 1.0:
                    pc_ratio_sentiment = 'bearish'
                elif pc_ratio_oi < 0.6:
                    pc_ratio_sentiment = 'very_bullish'
                elif pc_ratio_oi < 0.8:
                    pc_ratio_sentiment = 'bullish'

                # IV metrics
                atm_range = (price * 0.95, price * 1.05)
                atm_c = _first_calls[(_first_calls['strike'] >= atm_range[0]) & (_first_calls['strike'] <= atm_range[1])]
                atm_p = _first_puts[(_first_puts['strike'] >= atm_range[0]) & (_first_puts['strike'] <= atm_range[1])]
                c_iv_pct = float(atm_c['impliedVolatility'].mean() * 100) if not atm_c.empty else 0
                p_iv_pct = float(atm_p['impliedVolatility'].mean() * 100) if not atm_p.empty else 0
                atm_iv_val = (c_iv_pct + p_iv_pct) / 2 if c_iv_pct > 0 and p_iv_pct > 0 else max(c_iv_pct, p_iv_pct)

                # Skew
                otm_p = _first_puts[_first_puts['strike'] < price * 0.95]
                otm_c = _first_calls[_first_calls['strike'] > price * 1.05]
                p_iv_avg = float(otm_p['impliedVolatility'].mean() * 100) if not otm_p.empty else 0
                c_iv_avg = float(otm_c['impliedVolatility'].mean() * 100) if not otm_c.empty else 0
                skew_val = p_iv_avg - c_iv_avg

                # Expected move from ATM straddle
                atm_idx = (_first_calls['strike'] - price).abs().idxmin() if not _first_calls.empty else None
                if atm_idx is not None:
                    atm_c_px = float(_first_calls.loc[atm_idx, 'lastPrice']) if 'lastPrice' in _first_calls.columns else 0
                    atm_s_val = float(_first_calls.loc[atm_idx, 'strike'])
                    atm_p_row = _first_puts[_first_puts['strike'] == atm_s_val]
                    atm_p_px = float(atm_p_row['lastPrice'].iloc[0]) if not atm_p_row.empty else 0
                    straddle = atm_c_px + atm_p_px
                    expected_move = (straddle / price * 100) if price > 0 else 0

            # Compute gamma levels
            if all_call_gex or all_put_gex:
                all_strikes = sorted(set(list(all_call_gex.keys()) + list(all_put_gex.keys())))
                net_gex = {}
                for s in all_strikes:
                    net_gex[s] = all_call_gex.get(s, 0) - all_put_gex.get(s, 0)

                total_net = sum(net_gex.values())
                gamma_regime = 'positive' if total_net > 0 else 'negative'
                # Strength: ratio of dominant gamma to total
                pos_gex = sum(v for v in net_gex.values() if v > 0)
                neg_gex = abs(sum(v for v in net_gex.values() if v < 0))
                if pos_gex + neg_gex > 0:
                    gamma_regime_strength = abs(pos_gex - neg_gex) / (pos_gex + neg_gex) * 100

                # Call wall (highest call gex ABOVE price = resistance)
                if all_call_gex:
                    calls_above = {s: g for s, g in all_call_gex.items() if s >= price}
                    if calls_above:
                        call_wall_strike = max(calls_above, key=calls_above.get)
                    else:
                        call_wall_strike = max(all_call_gex, key=all_call_gex.get)
                    price_vs_call_wall_pct = ((call_wall_strike - price) / price) * 100

                # Put wall (highest put gex BELOW price = support)
                if all_put_gex:
                    puts_below = {s: g for s, g in all_put_gex.items() if s <= price}
                    if puts_below:
                        put_wall_strike = max(puts_below, key=puts_below.get)
                    else:
                        put_wall_strike = max(all_put_gex, key=all_put_gex.get)
                    price_vs_put_wall_pct = ((price - put_wall_strike) / price) * 100

                # Gamma wall (highest absolute net)
                gamma_wall_strike = max(net_gex, key=lambda s: abs(net_gex[s]))

                # HVL (zero-cross nearest to spot)
                sorted_strikes = sorted(net_gex.keys())
                min_dist = float('inf')
                for i in range(len(sorted_strikes) - 1):
                    g1 = net_gex[sorted_strikes[i]]
                    g2 = net_gex[sorted_strikes[i + 1]]
                    if g1 * g2 < 0:
                        cross = sorted_strikes[i] + (sorted_strikes[i + 1] - sorted_strikes[i]) * abs(g1) / (abs(g1) + abs(g2))
                        d = abs(cross - price)
                        if d < min_dist:
                            min_dist = d
                            hvl_strike = cross

                # Max pain
                if _first_calls is not None and _first_puts is not None:
                    all_opt_strikes = sorted(set(_first_calls['strike'].tolist() + _first_puts['strike'].tolist()))
                    min_pain = float('inf')
                    for s in all_opt_strikes:
                        cp = _first_calls[_first_calls['strike'] < s]
                        pp = _first_puts[_first_puts['strike'] > s]
                        pain = 0
                        if len(cp) > 0:
                            pain += (cp['openInterest'] * (s - cp['strike'])).sum()
                        if len(pp) > 0:
                            pain += (pp['openInterest'] * (pp['strike'] - s)).sum()
                        if pain < min_pain:
                            min_pain = pain
                            max_pain = s
                    price_vs_max_pain_pct = ((price - max_pain) / price) * 100
     except Exception:
        pass

    # =========================================================================
    # BUILD FACTOR ANALYSIS - SHORT TERM
    # =========================================================================
    st_factors = []

    # RSI
    if rsi < 30:
        st_factors.append(('RSI en sobreventa', +12, f'RSI={rsi:.0f} indica posible rebote', 'bullish'))
    elif rsi < 40:
        st_factors.append(('RSI bajo', +6, f'RSI={rsi:.0f} favorable', 'bullish'))
    elif rsi > 75:
        st_factors.append(('RSI sobrecompra extrema', -12, f'RSI={rsi:.0f} zona peligrosa', 'bearish'))
    elif rsi > 65:
        st_factors.append(('RSI elevado', -5, f'RSI={rsi:.0f} cercano a sobrecompra', 'bearish'))

    # MACD
    if macd_bullish and momentum_1m > 3:
        st_factors.append(('MACD cruce alcista', +8, 'Cruce alcista con momentum', 'bullish'))
    elif macd_bullish:
        st_factors.append(('MACD alcista', +4, 'Tendencia positiva', 'bullish'))
    elif not macd_bullish and momentum_1m < -3:
        st_factors.append(('MACD cruce bajista', -8, 'Cruce bajista con momentum negativo', 'bearish'))
    elif not macd_bullish:
        st_factors.append(('MACD bajista', -4, 'Tendencia negativa', 'bearish'))

    # Momentum 1M
    if momentum_1m > 10:
        st_factors.append(('Momentum 1M fuerte', +10, f'+{momentum_1m:.1f}% en 1 mes', 'bullish'))
    elif momentum_1m > 3:
        st_factors.append(('Momentum 1M positivo', +5, f'+{momentum_1m:.1f}% en 1 mes', 'bullish'))
    elif momentum_1m < -10:
        st_factors.append(('Momentum 1M negativo fuerte', -10, f'{momentum_1m:.1f}% en 1 mes', 'bearish'))
    elif momentum_1m < -3:
        st_factors.append(('Momentum 1M negativo', -5, f'{momentum_1m:.1f}% en 1 mes', 'bearish'))

    # Volume
    if volume_ratio > 2.5:
        st_factors.append(('Volumen muy alto', +7, f'{volume_ratio:.1f}x vs media - fuerte interes institucional', 'bullish'))
    elif volume_ratio > 1.5:
        st_factors.append(('Volumen alto', +4, f'{volume_ratio:.1f}x vs media - interes institucional', 'bullish'))
    elif volume_ratio < 0.5:
        st_factors.append(('Volumen bajo', -4, f'{volume_ratio:.1f}x vs media - poco interes', 'bearish'))

    # Congress short-term
    if congress_signal == 'bullish':
        st_factors.append(('Congresistas comprando', +8, congress_detail, 'bullish'))
    elif congress_signal == 'bearish':
        st_factors.append(('Congresistas vendiendo', -8, congress_detail, 'bearish'))

    # Polymarket short-term
    if poly_signal == 'bullish':
        st_factors.append(('Polymarket alcista', +5, poly_detail, 'bullish'))
    elif poly_signal == 'bearish':
        st_factors.append(('Polymarket bajista', -5, poly_detail, 'bearish'))

    # % from 52W high/low - price positioning
    if pct_from_high < -30:
        st_factors.append(('Lejos de maximos', +4, f'{pct_from_high:.0f}% desde 52W high - posible rebote', 'bullish'))
    elif pct_from_high > -3:
        st_factors.append(('Cerca de maximos', -3, f'{pct_from_high:.0f}% desde 52W high - resistencia', 'bearish'))

    if pct_from_low < 10 and pct_from_low > 0:
        st_factors.append(('Cerca de minimos 52W', +6, f'Solo +{pct_from_low:.0f}% sobre 52W low - soporte fuerte', 'bullish'))

    # Market liquidity / friction - short term
    if vix_val > 0:
        if vix_val > 30:
            st_factors.append(('Mercado en panico (VIX)', -8, f'VIX={vix_val:.0f} - alta friccion, spreads amplios', 'bearish'))
        elif vix_val > 22:
            st_factors.append(('Volatilidad elevada', -4, f'VIX={vix_val:.0f} - liquidez reducida', 'bearish'))
        elif vix_val < 14:
            st_factors.append(('Mercado tranquilo', +3, f'VIX={vix_val:.0f} - baja friccion, liquidez abundante', 'bullish'))

    if beta > 0 and vix_val > 25:
        st_factors.append(('Beta x VIX alto', -3, f'Beta={beta:.1f} con VIX={vix_val:.0f} - riesgo amplificado', 'bearish'))

    # Options/Gamma - Short term (only if sufficient OI)
    if total_options_oi >= 100 and gamma_regime is not None:
        # Gamma regime
        if gamma_regime == 'positive' and gamma_regime_strength > 30:
            st_factors.append(('Gamma positiva (dealers frenan)', +6,
                f'Net GEX positivo ({gamma_regime_strength:.0f}% dominancia) - dealers venden rallies y compran dips, volatilidad contenida', 'bullish'))
        elif gamma_regime == 'positive':
            st_factors.append(('Gamma ligeramente positiva', +3,
                f'Net GEX positivo ({gamma_regime_strength:.0f}%) - sesgo a estabilidad', 'bullish'))
        elif gamma_regime == 'negative' and gamma_regime_strength > 30:
            st_factors.append(('Gamma negativa (dealers amplifican)', -7,
                f'Net GEX negativo ({gamma_regime_strength:.0f}% dominancia) - dealers amplifican movimientos, riesgo de whipsaw', 'bearish'))
        elif gamma_regime == 'negative':
            st_factors.append(('Gamma ligeramente negativa', -3,
                f'Net GEX negativo ({gamma_regime_strength:.0f}%) - sesgo a mayor volatilidad', 'bearish'))

        # Proximity to call wall (resistance)
        if call_wall_strike > 0 and price_vs_call_wall_pct < 1.5 and price_vs_call_wall_pct > 0:
            st_factors.append(('Cerca de Call Resistance', -4,
                f'Precio a {price_vs_call_wall_pct:.1f}% del Call Wall (${call_wall_strike:.0f}) - techo gamma', 'bearish'))
        elif call_wall_strike > 0 and price_vs_call_wall_pct < 0:
            st_factors.append(('Sobre Call Resistance', +5,
                f'Precio sobre Call Wall (${call_wall_strike:.0f}) - breakout gamma puede acelerar al alza', 'bullish'))

        # Proximity to put wall (support)
        if put_wall_strike > 0 and price_vs_put_wall_pct < 1.5 and price_vs_put_wall_pct > 0:
            st_factors.append(('Cerca de Put Support', +4,
                f'Precio a {price_vs_put_wall_pct:.1f}% del Put Wall (${put_wall_strike:.0f}) - suelo gamma', 'bullish'))
        elif put_wall_strike > 0 and price_vs_put_wall_pct < 0:
            st_factors.append(('Bajo Put Support', -5,
                f'Precio bajo Put Wall (${put_wall_strike:.0f}) - breakdown gamma puede acelerar a la baja', 'bearish'))

        # Expected move
        if expected_move > 5:
            st_factors.append(('Expected Move alto (opciones)', -4,
                f'Straddle implica ±{expected_move:.1f}% - mercado espera gran movimiento', 'bearish'))
        elif expected_move > 3:
            st_factors.append(('Expected Move moderado', -2,
                f'Straddle implica ±{expected_move:.1f}%', 'bearish'))

        # ATM IV
        if atm_iv_val > 60:
            st_factors.append(('IV muy alta', -5,
                f'ATM IV={atm_iv_val:.0f}% - prima de opciones cara, miedo elevado', 'bearish'))
        elif atm_iv_val > 40:
            st_factors.append(('IV elevada', -3,
                f'ATM IV={atm_iv_val:.0f}% - opciones caras, incertidumbre', 'bearish'))
        elif atm_iv_val < 18 and atm_iv_val > 0:
            st_factors.append(('IV baja (complacencia)', +2,
                f'ATM IV={atm_iv_val:.0f}% - opciones baratas, baja incertidumbre', 'bullish'))

        # Put/Call ratio
        if pc_ratio_sentiment == 'very_bearish':
            st_factors.append(('P/C Ratio extremo (contrarian bullish)', +5,
                f'Put/Call OI={pc_ratio_oi:.2f} - exceso de proteccion put, posible suelo', 'bullish'))
        elif pc_ratio_sentiment == 'very_bullish':
            st_factors.append(('P/C Ratio bajo (complacencia)', -4,
                f'Put/Call OI={pc_ratio_oi:.2f} - poca cobertura, vulnerabilidad a baja', 'bearish'))

    # =========================================================================
    # BUILD FACTOR ANALYSIS - MEDIUM TERM (1-6 months)
    # =========================================================================
    mt_factors = []

    # Momentum 3M
    if momentum_3m > 20:
        mt_factors.append(('Momentum 3M muy fuerte', +12, f'+{momentum_3m:.1f}% en 3 meses', 'bullish'))
    elif momentum_3m > 8:
        mt_factors.append(('Momentum 3M positivo', +6, f'+{momentum_3m:.1f}% en 3 meses', 'bullish'))
    elif momentum_3m < -20:
        mt_factors.append(('Momentum 3M negativo fuerte', -12, f'{momentum_3m:.1f}% en 3 meses', 'bearish'))
    elif momentum_3m < -8:
        mt_factors.append(('Momentum 3M negativo', -6, f'{momentum_3m:.1f}% en 3 meses', 'bearish'))

    # Fundamental quality
    if roe > 25:
        mt_factors.append(('ROE excepcional', +8, f'ROE={roe:.1f}% - ventaja competitiva', 'bullish'))
    elif roe > 15:
        mt_factors.append(('Calidad fundamental', +5, f'ROE={roe:.1f}% - buena rentabilidad', 'bullish'))
    elif roe < 5 and roe > 0:
        mt_factors.append(('ROE bajo', -4, f'ROE={roe:.1f}% - poca rentabilidad', 'bearish'))
    elif roe < 0:
        mt_factors.append(('ROE negativo', -8, f'ROE={roe:.1f}% - destruye valor', 'bearish'))

    # Forward P/E trend
    if forward_pe > 0 and pe > 0:
        if forward_pe < pe * 0.85:
            mt_factors.append(('Forward P/E mejorando', +6, f'Forward={forward_pe:.1f} vs Actual={pe:.1f} (-{(1-forward_pe/pe)*100:.0f}%)', 'bullish'))
        elif forward_pe > pe * 1.1:
            mt_factors.append(('Forward P/E deteriorando', -5, f'Forward={forward_pe:.1f} vs Actual={pe:.1f} (+{(forward_pe/pe-1)*100:.0f}%)', 'bearish'))

    # Earnings/Revenue growth
    if earn_growth > 20:
        mt_factors.append(('Crecimiento BPA fuerte', +7, f'Earnings growth={earn_growth:.0f}%', 'bullish'))
    elif earn_growth > 5:
        mt_factors.append(('Crecimiento BPA positivo', +3, f'Earnings growth={earn_growth:.0f}%', 'bullish'))
    elif earn_growth < -10:
        mt_factors.append(('BPA en caida', -7, f'Earnings growth={earn_growth:.0f}%', 'bearish'))

    if rev_growth > 15:
        mt_factors.append(('Revenue acelerando', +5, f'Revenue growth={rev_growth:.0f}%', 'bullish'))
    elif rev_growth < -5:
        mt_factors.append(('Revenue contrayendo', -5, f'Revenue growth={rev_growth:.0f}%', 'bearish'))

    # Liquidity mid-term risk
    if current_ratio > 0 and current_ratio < 1.0:
        mt_factors.append(('Riesgo liquidez', -6, f'Current ratio={current_ratio:.2f} - insuficiente', 'bearish'))
    elif current_ratio >= 2.0:
        mt_factors.append(('Liquidez solida', +3, f'Current ratio={current_ratio:.2f}', 'bullish'))

    # Debt mid-term risk
    if debt_ebitda > 4:
        mt_factors.append(('Deuda/EBITDA peligroso', -7, f'Debt/EBITDA={debt_ebitda:.1f}x - refinanciacion', 'bearish'))
    elif debt_ebitda > 2.5:
        mt_factors.append(('Deuda/EBITDA elevado', -4, f'Debt/EBITDA={debt_ebitda:.1f}x', 'bearish'))
    elif 0 < debt_ebitda < 1.5:
        mt_factors.append(('Deuda controlada', +4, f'Debt/EBITDA={debt_ebitda:.1f}x', 'bullish'))

    # Analyst target
    if analyst_upside > 20:
        mt_factors.append(('Target analistas alto', +6, f'Upside={analyst_upside:.0f}% (target ${target_price:.0f})', 'bullish'))
    elif analyst_upside < -10:
        mt_factors.append(('Target analistas bajo', -5, f'Downside={analyst_upside:.0f}% (target ${target_price:.0f})', 'bearish'))

    # DCF-based price vs value
    if dcf_upside > 30:
        mt_factors.append(('Precio < valor intrinseco (DCF)', +7, f'Upside DCF={dcf_upside:.0f}% - infravalorado', 'bullish'))
    elif dcf_upside > 10:
        mt_factors.append(('Precio razonable (DCF)', +3, f'Upside DCF={dcf_upside:.0f}%', 'bullish'))
    elif dcf_upside < -20:
        mt_factors.append(('Precio > valor intrinseco (DCF)', -6, f'Downside DCF={dcf_upside:.0f}% - sobrevalorado', 'bearish'))

    # Congress medium-term
    if congress_signal == 'bullish':
        mt_factors.append(('Congresistas comprando', +6, congress_detail, 'bullish'))
    elif congress_signal == 'bearish':
        mt_factors.append(('Congresistas vendiendo', -6, congress_detail, 'bearish'))

    # Market regime / liquidity mid-term
    if risk_score >= 60:
        mt_factors.append(('Regimen macro desfavorable', -6, f'Risk Score={risk_score}/100 ({risk_regime}) - condiciones adversas', 'bearish'))
    elif risk_score >= 40:
        mt_factors.append(('Regimen macro mixto', -2, f'Risk Score={risk_score}/100 ({risk_regime}) - cautela', 'bearish'))
    elif risk_score < 25:
        mt_factors.append(('Regimen macro favorable', +5, f'Risk Score={risk_score}/100 ({risk_regime}) - condiciones optimas', 'bullish'))

    if credit_stress:
        mt_factors.append(('Estres crediticio', -5, 'Spreads de credito ampliandose - friccion alta', 'bearish'))

    # P/S ratio (useful for growth stocks)
    if ps > 0:
        if ps > 15:
            mt_factors.append(('P/S muy elevado', -5, f'P/S={ps:.1f} - valoracion agresiva', 'bearish'))
        elif ps < 2:
            mt_factors.append(('P/S atractivo', +4, f'P/S={ps:.1f} - valoracion conservadora', 'bullish'))

    # Options/Gamma - Medium term
    if total_options_oi >= 100:
        # Max pain as gravity (medium-term mean reversion)
        if price_vs_max_pain_pct > 5:
            mt_factors.append(('Precio > Max Pain (gravedad bajista)', -4,
                f'Precio {price_vs_max_pain_pct:.1f}% sobre Max Pain (${max_pain:.0f}) - gravedad hacia abajo al vencimiento', 'bearish'))
        elif price_vs_max_pain_pct < -5:
            mt_factors.append(('Precio < Max Pain (gravedad alcista)', +4,
                f'Precio {abs(price_vs_max_pain_pct):.1f}% bajo Max Pain (${max_pain:.0f}) - gravedad hacia arriba al vencimiento', 'bullish'))

        # Skew as medium-term fear gauge
        if skew_val > 15:
            mt_factors.append(('Skew extremo (miedo a caida)', -5,
                f'IV Skew={skew_val:+.0f}pp - puts OTM muy caras vs calls, mercado teme caida', 'bearish'))
        elif skew_val > 8:
            mt_factors.append(('Skew elevado', -3,
                f'IV Skew={skew_val:+.0f}pp - demanda de proteccion por encima de lo normal', 'bearish'))
        elif skew_val < -5:
            mt_factors.append(('Skew invertido (especulacion alcista)', +3,
                f'IV Skew={skew_val:+.0f}pp - calls OTM mas caras que puts, sesgo alcista', 'bullish'))

        # P/C ratio medium-term
        if pc_ratio_sentiment == 'bearish':
            mt_factors.append(('Put/Call ratio elevado', +3,
                f'P/C={pc_ratio_oi:.2f} - mucha cobertura acumulada, posible suelo tecnico', 'bullish'))

    # =========================================================================
    # BUILD FACTOR ANALYSIS - LONG TERM (6+ months)
    # =========================================================================
    lt_factors = []

    # Valuation - P/E vs sector
    if pe > 0:
        if pe > sector_pe * 1.5:
            lt_factors.append(('P/E muy elevado vs sector', -10, f'P/E={pe:.1f} vs sector={sector_pe} ({pe/sector_pe:.1f}x)', 'bearish'))
        elif pe > sector_pe * 1.2:
            lt_factors.append(('P/E elevado vs sector', -5, f'P/E={pe:.1f} vs sector={sector_pe}', 'bearish'))
        elif pe < sector_pe * 0.7:
            lt_factors.append(('P/E atractivo vs sector', +8, f'P/E={pe:.1f} vs sector={sector_pe} - value', 'bullish'))
        elif pe < sector_pe * 0.9:
            lt_factors.append(('P/E razonable', +4, f'P/E={pe:.1f} vs sector={sector_pe}', 'bullish'))

    # PEG ratio
    if peg > 0:
        if peg < 0.8:
            lt_factors.append(('PEG muy atractivo', +7, f'PEG={peg:.2f} - crecimiento barato', 'bullish'))
        elif peg < 1.2:
            lt_factors.append(('PEG razonable', +3, f'PEG={peg:.2f}', 'bullish'))
        elif peg > 2.5:
            lt_factors.append(('PEG caro', -6, f'PEG={peg:.2f} - crecimiento sobrevaluado', 'bearish'))

    # Graham Number vs price
    if graham_value > 0 and price > 0:
        graham_upside = ((graham_value - price) / price * 100)
        if graham_upside > 30:
            lt_factors.append(('Precio < Graham Number', +8, f'Graham=${graham_value:.0f} vs precio=${price:.0f} (upside {graham_upside:.0f}%)', 'bullish'))
        elif graham_upside > 10:
            lt_factors.append(('Precio cercano a Graham', +4, f'Graham=${graham_value:.0f} vs precio=${price:.0f}', 'bullish'))
        elif graham_upside < -30:
            lt_factors.append(('Precio >> Graham Number', -6, f'Graham=${graham_value:.0f} vs precio=${price:.0f} (downside {graham_upside:.0f}%)', 'bearish'))

    # EV/EBITDA
    if ev_ebitda > 0:
        if ev_ebitda > 25:
            lt_factors.append(('EV/EBITDA elevado', -5, f'EV/EBITDA={ev_ebitda:.1f}', 'bearish'))
        elif ev_ebitda < 10:
            lt_factors.append(('EV/EBITDA atractivo', +5, f'EV/EBITDA={ev_ebitda:.1f}', 'bullish'))

    # FCF Yield
    if fcf_yield > 8:
        lt_factors.append(('FCF Yield excelente', +8, f'FCF Yield={fcf_yield:.1f}% - cash machine', 'bullish'))
    elif fcf_yield > 4:
        lt_factors.append(('FCF Yield bueno', +4, f'FCF Yield={fcf_yield:.1f}%', 'bullish'))
    elif fcf_yield < 1 and fcf_yield > 0:
        lt_factors.append(('FCF Yield bajo', -3, f'FCF Yield={fcf_yield:.1f}%', 'bearish'))
    elif fcf_yield < 0:
        lt_factors.append(('FCF negativo', -7, f'FCF Yield={fcf_yield:.1f}% - quema caja', 'bearish'))

    # ROE long-term
    if roe > 25:
        lt_factors.append(('ROE excepcional', +10, f'ROE={roe:.1f}% - moat potencial', 'bullish'))
    elif roe > 15:
        lt_factors.append(('ROE bueno', +5, f'ROE={roe:.1f}%', 'bullish'))
    elif roe < 5 and roe > 0:
        lt_factors.append(('ROE bajo', -5, f'ROE={roe:.1f}%', 'bearish'))
    elif roe < 0:
        lt_factors.append(('ROE negativo', -10, f'ROE={roe:.1f}%', 'bearish'))

    # Debt long-term
    if debt_equity > 200:
        lt_factors.append(('Deuda muy alta', -8, f'D/E={debt_equity:.0f}% - riesgo solvencia', 'bearish'))
    elif debt_equity > 100:
        lt_factors.append(('Deuda elevada', -4, f'D/E={debt_equity:.0f}%', 'bearish'))
    elif debt_equity < 30 and debt_equity >= 0:
        lt_factors.append(('Balance muy solido', +6, f'D/E={debt_equity:.0f}% - fortaleza financiera', 'bullish'))
    elif debt_equity < 70:
        lt_factors.append(('Deuda controlada', +3, f'D/E={debt_equity:.0f}%', 'bullish'))

    # Liquidity long-term
    if current_ratio > 0 and current_ratio < 0.8:
        lt_factors.append(('Riesgo liquidez serio', -7, f'Current ratio={current_ratio:.2f}', 'bearish'))
    if quick_ratio > 0 and quick_ratio < 0.5:
        lt_factors.append(('Quick ratio muy bajo', -5, f'Quick ratio={quick_ratio:.2f}', 'bearish'))

    # Margins long-term
    if profit_margin > 25:
        lt_factors.append(('Margenes excepcionales', +7, f'Margen neto={profit_margin:.1f}% - pricing power', 'bullish'))
    elif profit_margin > 12:
        lt_factors.append(('Margenes buenos', +4, f'Margen neto={profit_margin:.1f}%', 'bullish'))
    elif 0 < profit_margin < 5:
        lt_factors.append(('Margenes ajustados', -4, f'Margen neto={profit_margin:.1f}%', 'bearish'))
    elif profit_margin < 0:
        lt_factors.append(('Perdidas operativas', -8, f'Margen neto={profit_margin:.1f}%', 'bearish'))

    # Gross margin (moat indicator)
    if gross_margin > 60:
        lt_factors.append(('Margen bruto alto (moat)', +5, f'Margen bruto={gross_margin:.0f}%', 'bullish'))
    elif gross_margin < 25 and gross_margin > 0:
        lt_factors.append(('Margen bruto bajo', -3, f'Margen bruto={gross_margin:.0f}% - commoditizado', 'bearish'))

    # Dividend
    if dividend_yield > 3:
        lt_factors.append(('Dividendo atractivo', +4, f'Yield={dividend_yield:.1f}%', 'bullish'))

    # Beta risk
    if beta > 1.5:
        lt_factors.append(('Beta alto (volatil)', -3, f'Beta={beta:.2f} - alta volatilidad', 'bearish'))

    # Debt/EBITDA long-term
    if debt_ebitda > 5:
        lt_factors.append(('Leverage extremo', -8, f'Debt/EBITDA={debt_ebitda:.1f}x', 'bearish'))
    elif net_debt < 0 and ebitda > 0:
        lt_factors.append(('Caja neta positiva', +6, 'Mas caja que deuda - flexibilidad total', 'bullish'))

    # Price positioning in 52W range
    if w52h > 0 and w52l > 0 and w52h != w52l:
        range_52w = w52h - w52l
        pct_in_range = ((price - w52l) / range_52w * 100) if range_52w > 0 else 50
        if pct_in_range < 20:
            lt_factors.append(('Precio en zona baja 52W', +5, f'En percentil {pct_in_range:.0f}% del rango 52W (${w52l:.0f}-${w52h:.0f})', 'bullish'))
        elif pct_in_range > 90:
            lt_factors.append(('Precio en maximos 52W', -4, f'En percentil {pct_in_range:.0f}% del rango 52W', 'bearish'))

    # Polymarket long-term
    if poly_signal == 'bullish':
        lt_factors.append(('Polymarket favorable', +3, poly_detail, 'bullish'))
    elif poly_signal == 'bearish':
        lt_factors.append(('Polymarket desfavorable', -3, poly_detail, 'bearish'))

    # Options - Long term (structural only)
    if total_options_oi >= 100 and atm_iv_val > 0:
        # Very high IV long-term = opportunities for mean reversion
        if atm_iv_val > 50:
            lt_factors.append(('IV historicamente alta', +3,
                f'ATM IV={atm_iv_val:.0f}% - IV tiende a revertir a la media, oportunidad venta de prima', 'bullish'))
        # Very high P/C ratio = structural hedge demand = potential squeeze
        if pc_ratio_oi > 1.5:
            lt_factors.append(('Posicionamiento extremo en puts', +4,
                f'P/C={pc_ratio_oi:.2f} - nivel extremo de cobertura, squeeze potencial largo plazo', 'bullish'))

    # =========================================================================
    # SEPARATE AND RANK FACTORS
    # =========================================================================
    def separate_factors(factors):
        bullish = sorted([f for f in factors if f[3] == 'bullish'], key=lambda x: x[1], reverse=True)
        bearish = sorted([f for f in factors if f[3] == 'bearish'], key=lambda x: x[1])
        return bullish[:7], bearish[:7]

    st_bull, st_bear = separate_factors(st_factors)
    mt_bull, mt_bear = separate_factors(mt_factors)
    lt_bull, lt_bear = separate_factors(lt_factors)

    score_cp = row.get('Score CP', 50)
    score_mp = row.get('Score MP', 50)
    score_lp = row.get('Score LP', 50)

    # Generate summary
    best_horizon = 'corto plazo' if score_cp >= score_mp and score_cp >= score_lp else (
        'medio plazo' if score_mp >= score_lp else 'largo plazo')

    all_bull = st_bull + mt_bull + lt_bull
    all_bear = st_bear + mt_bear + lt_bear
    top_bull = all_bull[0][0] if all_bull else 'factores mixtos'
    top_bear = all_bear[0][0] if all_bear else 'sin riesgos destacados'

    # Compose rich summary with price context
    parts = [f"{ticker} mejor oportunidad en {best_horizon} (CP={score_cp:.0f}, MP={score_mp:.0f}, LP={score_lp:.0f})."]
    # Price context
    if analyst_upside > 0:
        parts.append(f"Precio actual ${price:.2f} ({pct_from_high:.0f}% desde max 52W, target analistas ${target_price:.0f} = {analyst_upside:+.0f}%).")
    else:
        parts.append(f"Precio actual ${price:.2f} ({pct_from_high:.0f}% desde max 52W).")
    if graham_value > 0:
        gv_pct = ((graham_value - price) / price * 100) if price > 0 else 0
        parts.append(f"Graham Number: ${graham_value:.0f} ({gv_pct:+.0f}% vs precio).")
    parts.append(f"Principal catalizador: {top_bull}. Principal riesgo: {top_bear}.")
    # Macro/liquidity context
    if vix_val > 0:
        parts.append(f"Macro: VIX={vix_val:.0f}, Risk Score={risk_score}/100 ({risk_regime}).")
    if congress_detail:
        parts.append(f"Congress: {congress_detail}.")
    if poly_detail:
        parts.append(f"Polymarket: {poly_detail}.")
    # Options context
    if gamma_regime and total_options_oi >= 100:
        regime_txt = 'positiva (estabiliza)' if gamma_regime == 'positive' else 'negativa (amplifica)'
        parts.append(f"Gamma {regime_txt}, Call Wall ${call_wall_strike:.0f}, Put Wall ${put_wall_strike:.0f}, Max Pain ${max_pain:.0f}, P/C={pc_ratio_oi:.2f}.")

    summary = " ".join(parts)

    return {
        'ticker': ticker,
        'company_name': stock_data.get('company_name', ticker),
        'short_term': {
            'score': score_cp,
            'signal': row.get('Señal CP', 'N/A'),
            'bullish_factors': [(f[0], f[1], f[2]) for f in st_bull],
            'bearish_factors': [(f[0], abs(f[1]), f[2]) for f in st_bear],
        },
        'medium_term': {
            'score': score_mp,
            'signal': row.get('Señal MP', 'N/A'),
            'bullish_factors': [(f[0], f[1], f[2]) for f in mt_bull],
            'bearish_factors': [(f[0], abs(f[1]), f[2]) for f in mt_bear],
        },
        'long_term': {
            'score': score_lp,
            'signal': row.get('Señal LP', 'N/A'),
            'bullish_factors': [(f[0], f[1], f[2]) for f in lt_bull],
            'bearish_factors': [(f[0], abs(f[1]), f[2]) for f in lt_bear],
        },
        'summary': summary,
    }


# =============================================================================
# OPTIONS ANALYTICS - ADVANCED SKEW ANALYSIS
# =============================================================================

import numpy as np
import json
from scipy.stats import norm

def black_scholes_delta(S: float, K: float, T: float, r: float, sigma: float,
                        option_type: str = 'call') -> float:
    """
    Calculate option delta using Black-Scholes formula.

    Parameters:
    -----------
    S : float - Current stock price
    K : float - Strike price
    T : float - Time to expiration (in years)
    r : float - Risk-free rate (annual)
    sigma : float - Implied volatility (decimal, e.g., 0.20 for 20%)
    option_type : str - 'call' or 'put'

    Returns:
    --------
    float : Delta value
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    if option_type == 'call':
        delta = norm.cdf(d1)
    else:  # put
        delta = -norm.cdf(-d1)

    return delta


def find_25delta_strikes(calls_df: pd.DataFrame, puts_df: pd.DataFrame,
                         current_price: float, dte: int, risk_free_rate: float = 0.05):
    """
    Find the strikes closest to 25-delta for calls and puts.

    Parameters:
    -----------
    calls_df : pd.DataFrame - Calls option chain with columns: strike, impliedVolatility
    puts_df : pd.DataFrame - Puts option chain with columns: strike, impliedVolatility
    current_price : float - Current stock price
    dte : int - Days to expiration
    risk_free_rate : float - Annual risk-free rate (default 5%)

    Returns:
    --------
    dict : {
        'call_25d': {'strike': float, 'iv': float, 'delta': float},
        'put_25d': {'strike': float, 'iv': float, 'delta': float}
    }
    """
    T = max(dte / 365.0, 1/365)  # At least 1 day

    # Find 25-delta call (target delta = 0.25)
    best_call = None
    min_call_diff = float('inf')

    for _, row in calls_df.iterrows():
        K = float(row['strike'])
        sigma = float(row.get('impliedVolatility', 0))

        if sigma <= 0 or K <= 0:
            continue

        delta = black_scholes_delta(current_price, K, T, risk_free_rate, sigma, 'call')
        diff = abs(delta - 0.25)

        if diff < min_call_diff:
            min_call_diff = diff
            best_call = {'strike': K, 'iv': sigma, 'delta': delta}

    # Find 25-delta put (target delta = -0.25)
    best_put = None
    min_put_diff = float('inf')

    for _, row in puts_df.iterrows():
        K = float(row['strike'])
        sigma = float(row.get('impliedVolatility', 0))

        if sigma <= 0 or K <= 0:
            continue

        delta = black_scholes_delta(current_price, K, T, risk_free_rate, sigma, 'put')
        diff = abs(abs(delta) - 0.25)

        if diff < min_put_diff:
            min_put_diff = diff
            best_put = {'strike': K, 'iv': sigma, 'delta': delta}

    return {
        'call_25d': best_call,
        'put_25d': best_put
    }


def calculate_25d_risk_reversal(calls_df: pd.DataFrame, puts_df: pd.DataFrame,
                                  current_price: float, dte: int) -> dict:
    """
    Calculate 25-Delta Risk Reversal (industry standard SKEW measure).

    RR_25D = IV(25Δ Put) - IV(25Δ Call)

    Returns:
    --------
    dict : {
        'rr_25d': float (in percentage points),
        'call_25d_strike': float,
        'put_25d_strike': float,
        'call_25d_iv': float,
        'put_25d_iv': float,
        'interpretation': str
    }
    """
    strikes = find_25delta_strikes(calls_df, puts_df, current_price, dte)

    if not strikes['call_25d'] or not strikes['put_25d']:
        return {
            'rr_25d': 0,
            'call_25d_strike': 0,
            'put_25d_strike': 0,
            'call_25d_iv': 0,
            'put_25d_iv': 0,
            'interpretation': 'Insufficient data'
        }

    call_iv = strikes['call_25d']['iv'] * 100  # Convert to percentage
    put_iv = strikes['put_25d']['iv'] * 100
    rr_25d = put_iv - call_iv

    # Interpretation
    if rr_25d > 15:
        interpretation = 'EXTREME PUT BIAS - Heavy institutional hedging'
    elif rr_25d > 10:
        interpretation = 'STRONG PUT BIAS - Elevated protection demand'
    elif rr_25d > 5:
        interpretation = 'MODERATE PUT BIAS - Normal for indices'
    elif rr_25d > 0:
        interpretation = 'SLIGHT PUT BIAS - Balanced market'
    elif rr_25d > -5:
        interpretation = 'SLIGHT CALL BIAS - Bullish speculation'
    else:
        interpretation = 'STRONG CALL BIAS - Euphoric positioning'

    return {
        'rr_25d': round(rr_25d, 2),
        'call_25d_strike': round(strikes['call_25d']['strike'], 2),
        'put_25d_strike': round(strikes['put_25d']['strike'], 2),
        'call_25d_iv': round(call_iv, 1),
        'put_25d_iv': round(put_iv, 1),
        'interpretation': interpretation
    }


def track_skew_history(ticker: str, skew_value: float, price: float):
    """
    Track SKEW history for a ticker (last 90 days).
    Stores in a simple JSON file for percentile calculations.

    Parameters:
    -----------
    ticker : str - Ticker symbol
    skew_value : float - Current SKEW value (25D RR)
    price : float - Current price
    """
    history_file = ROOT_DIR / 'data' / f'skew_history_{ticker}.json'

    try:
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = json.load(f)
        else:
            history = []
    except Exception:
        history = []

    # Add new entry
    history.append({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'skew': skew_value,
        'price': price
    })

    # Keep only last 90 days
    cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    history = [h for h in history if h['date'] >= cutoff_date]

    # Save
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        # Silent fail if can't write (read-only filesystem, etc.)
        pass


def get_skew_percentile(ticker: str, current_skew: float) -> dict:
    """
    Calculate percentile of current SKEW vs last 90 days.

    Returns:
    --------
    dict : {
        'percentile': float (0-100),
        'avg_30d': float,
        'min_90d': float,
        'max_90d': float,
        'current': float,
        'status': str ('EXTREME' / 'ELEVATED' / 'NORMAL' / 'LOW')
    }
    """
    history_file = ROOT_DIR / 'data' / f'skew_history_{ticker}.json'

    try:
        if not history_file.exists():
            return {
                'percentile': 50.0,
                'avg_30d': current_skew,
                'min_90d': current_skew,
                'max_90d': current_skew,
                'current': current_skew,
                'status': 'INSUFFICIENT DATA'
            }

        with open(history_file, 'r') as f:
            history = json.load(f)

        if len(history) < 10:
            return {
                'percentile': 50.0,
                'avg_30d': current_skew,
                'min_90d': current_skew,
                'max_90d': current_skew,
                'current': current_skew,
                'status': 'BUILDING HISTORY'
            }

        skew_values = [h['skew'] for h in history]

        # Calculate percentile using rank method (avoids 0% for lowest value)
        from scipy.stats import percentileofscore
        percentile = percentileofscore(skew_values, current_skew, kind='rank')

        # Calculate stats
        recent_30d = [h['skew'] for h in history[-30:]] if len(history) >= 30 else skew_values
        avg_30d = np.mean(recent_30d)
        min_90d = np.min(skew_values)
        max_90d = np.max(skew_values)

        # Status
        if percentile >= 90:
            status = 'EXTREME'
        elif percentile >= 75:
            status = 'ELEVATED'
        elif percentile >= 25:
            status = 'NORMAL'
        else:
            status = 'LOW'

        return {
            'percentile': round(percentile, 1),
            'avg_30d': round(avg_30d, 2),
            'min_90d': round(min_90d, 2),
            'max_90d': round(max_90d, 2),
            'current': round(current_skew, 2),
            'status': status
        }

    except Exception:
        return {
            'percentile': 50.0,
            'avg_30d': current_skew,
            'min_90d': current_skew,
            'max_90d': current_skew,
            'current': current_skew,
            'status': 'ERROR'
        }


# =============================================================================
# OPTIONS STRATEGY RECOMMENDER
# =============================================================================

def recommend_options_strategy(price: float, skew: float, gamma_regime: str,
                                 avg_iv: float, pc_ratio: float, dte: int,
                                 trend: str = 'neutral',
                                 calls_df=None, puts_df=None,
                                 net_gex_value: float = 0,
                                 call_wall: float = 0, put_wall: float = 0) -> dict:
    """
    Professional options strategy recommender.
    Uses composite bias (P/C + SKEW + GEX), real chain data for strikes,
    liquidity scoring, risk/reward, and expected move analysis.
    """
    import pandas as pd
    import numpy as np

    has_chain = calls_df is not None and not calls_df.empty and puts_df is not None and not puts_df.empty

    # =========================================================================
    # 1. CHAIN ANALYTICS — volume, liquidity, unusual activity
    # =========================================================================
    unusual_calls = []
    unusual_puts = []
    total_call_premium = 0
    total_put_premium = 0

    if has_chain:
        for side, df, out in [('call', calls_df, unusual_calls), ('put', puts_df, unusual_puts)]:
            for _, r in df.iterrows():
                vol = float(r.get('volume', 0) or 0)
                oi = float(r.get('openInterest', 0) or 0)
                bid = float(r.get('bid', 0) or 0)
                ask = float(r.get('ask', 0) or 0)
                mid = (bid + ask) / 2 if (bid + ask) > 0 else 0
                iv = float(r.get('impliedVolatility', 0) or 0)
                strike = float(r['strike'])
                # Volume/OI ratio > 2 = unusual activity
                vol_oi = vol / oi if oi > 50 else 0
                # Premium flow = volume * mid * 100
                prem = vol * mid * 100
                if side == 'call':
                    total_call_premium += prem
                else:
                    total_put_premium += prem
                if vol_oi > 2 and vol > 100:
                    out.append({'strike': strike, 'vol': int(vol), 'oi': int(oi),
                                'vol_oi': vol_oi, 'iv': iv * 100, 'premium': prem, 'mid': mid})

        unusual_calls.sort(key=lambda x: x['premium'], reverse=True)
        unusual_puts.sort(key=lambda x: x['premium'], reverse=True)

    # =========================================================================
    # 2. COMPOSITE BIAS SCORE (weighted)
    # =========================================================================
    bias_score = 0
    bias_reasons = []

    # P/C ratio by OI
    if pc_ratio < 0.7:
        bias_score += 2; bias_reasons.append(f'P/C {pc_ratio:.2f} (strong call demand)')
    elif pc_ratio < 0.9:
        bias_score += 1; bias_reasons.append(f'P/C {pc_ratio:.2f} (mild call bias)')
    elif pc_ratio > 1.3:
        bias_score -= 2; bias_reasons.append(f'P/C {pc_ratio:.2f} (strong put demand)')
    elif pc_ratio > 1.1:
        bias_score -= 1; bias_reasons.append(f'P/C {pc_ratio:.2f} (mild put bias)')

    # Skew signal
    if skew > 12:
        bias_score -= 2; bias_reasons.append(f'SKEW {skew:+.1f}pp (heavy put hedging)')
    elif skew > 8:
        bias_score -= 1; bias_reasons.append(f'SKEW {skew:+.1f}pp (elevated put demand)')
    elif skew < 3:
        bias_score += 1; bias_reasons.append(f'SKEW {skew:+.1f}pp (complacent/bullish)')

    # GEX regime
    if gamma_regime == 'POSITIVE GAMMA':
        bias_score += 1; bias_reasons.append('Positive GEX (dealers dampen moves, bullish pin)')
    elif gamma_regime == 'NEGATIVE GAMMA':
        bias_score -= 1; bias_reasons.append('Negative GEX (dealers amplify moves, volatile)')

    # Premium flow imbalance
    if total_call_premium > 0 and total_put_premium > 0:
        flow_ratio = total_call_premium / (total_call_premium + total_put_premium)
        if flow_ratio > 0.65:
            bias_score += 1; bias_reasons.append(f'Call premium flow {flow_ratio:.0%} (aggressive call buying)')
        elif flow_ratio < 0.35:
            bias_score -= 1; bias_reasons.append(f'Put premium flow {1-flow_ratio:.0%} (aggressive put buying)')

    # GEX walls: price position relative to support/resistance
    if call_wall > 0 and put_wall > 0 and call_wall != put_wall:
        pos_in_range = (price - put_wall) / (call_wall - put_wall) if call_wall > put_wall else 0.5
        if pos_in_range > 0.8:
            bias_reasons.append(f'Price near call wall ${call_wall:.0f} (resistance)')
        elif pos_in_range < 0.2:
            bias_reasons.append(f'Price near put wall ${put_wall:.0f} (support)')

    # Determine trend from composite
    if bias_score >= 2:
        trend = 'bullish'
    elif bias_score <= -2:
        trend = 'bearish'
    else:
        trend = 'neutral'

    # =========================================================================
    # 3. EXPECTED MOVE from ATM straddle
    # =========================================================================
    expected_move_pct = 0
    expected_move_abs = 0
    if has_chain:
        atm_call = calls_df.iloc[(calls_df['strike'] - price).abs().argsort()[:1]]
        atm_put = puts_df.iloc[(puts_df['strike'] - price).abs().argsort()[:1]]
        atm_c_mid = float((atm_call['bid'].iloc[0] + atm_call['ask'].iloc[0]) / 2) if not atm_call.empty else 0
        atm_p_mid = float((atm_put['bid'].iloc[0] + atm_put['ask'].iloc[0]) / 2) if not atm_put.empty else 0
        straddle = atm_c_mid + atm_p_mid
        expected_move_abs = straddle * 0.85  # ~1 SD
        expected_move_pct = (expected_move_abs / price * 100) if price > 0 else 0

    # =========================================================================
    # 4. STRIKE SELECTION — using chain + GEX walls + liquidity
    # =========================================================================
    def _find_strike(df, target_price, direction='above', min_oi=10):
        """Find best liquid strike near target. direction='above' or 'below'."""
        if df is None or df.empty:
            return target_price, None, 0

        if direction == 'above':
            candidates = df[df['strike'] >= target_price].copy()
        else:
            candidates = df[df['strike'] <= target_price].copy()

        if 'openInterest' in candidates.columns:
            liquid = candidates[candidates['openInterest'] >= min_oi]
            if not liquid.empty:
                candidates = liquid

        if candidates.empty:
            return round(target_price, 2), None, 0

        candidates = candidates.copy()
        candidates['dist'] = (candidates['strike'] - target_price).abs()
        best = candidates.loc[candidates['dist'].idxmin()]
        strike = float(best['strike'])

        # Liquidity score: bid-ask spread / mid
        bid = float(best.get('bid', 0) or 0)
        ask = float(best.get('ask', 0) or 0)
        mid = (bid + ask) / 2
        spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 999
        liq_score = max(0, min(100, 100 - spread_pct * 10))  # 0-100

        return strike, best, liq_score

    def _strike_detail(row):
        """Build detail dict from chain row."""
        if row is None:
            return {}
        bid = float(row.get('bid', 0) or 0)
        ask = float(row.get('ask', 0) or 0)
        mid = (bid + ask) / 2
        return {
            'iv': float(row.get('impliedVolatility', 0) or 0) * 100,
            'oi': int(row.get('openInterest', 0) or 0),
            'volume': int(row.get('volume', 0) or 0),
            'bid': bid, 'ask': ask, 'mid': mid,
            'spread_pct': ((ask - bid) / mid * 100) if mid > 0 else 0,
            'text': f"IV:{float(row.get('impliedVolatility', 0) or 0)*100:.0f}% OI:{int(row.get('openInterest', 0) or 0):,} Vol:{int(row.get('volume', 0) or 0):,} Bid/Ask:{bid:.2f}/{ask:.2f}"
        }

    # Use GEX walls to inform strike targets
    otm_call_target = price * 1.02
    otm_put_target = price * 0.98
    if call_wall > price and call_wall < price * 1.10:
        otm_call_target = call_wall  # Sell at resistance
    if put_wall < price and put_wall > price * 0.90:
        otm_put_target = put_wall  # Sell at support

    # Market conditions
    skew_high = skew > 10
    iv_high = avg_iv > 30
    iv_low = avg_iv < 20

    # =========================================================================
    # 5. STRATEGY SELECTION + RISK/REWARD
    # =========================================================================
    if trend == 'bullish':
        if iv_high and skew_high:
            # Spread to cap vega risk
            buy_k, buy_r, buy_liq = _find_strike(calls_df, price * 1.01, 'above')
            sell_target = call_wall if call_wall > buy_k else price * 1.06
            sell_k, sell_r, sell_liq = _find_strike(calls_df, sell_target, 'above')
            if sell_k <= buy_k:
                sell_k, sell_r, sell_liq = _find_strike(calls_df, buy_k * 1.04, 'above')
            buy_d = _strike_detail(buy_r)
            sell_d = _strike_detail(sell_r)
            max_loss = buy_d.get('mid', 0) - sell_d.get('mid', 0) if buy_d and sell_d else 0
            max_profit = (sell_k - buy_k) - max_loss if sell_k > buy_k else 0
            rr = (max_profit / max_loss) if max_loss > 0 else 0
            strategy = {
                'name': 'BULL CALL SPREAD',
                'market_bias': 'bullish',
                'description': f'Buy ${buy_k:.0f}C / Sell ${sell_k:.0f}C — debit spread near call wall',
                'strikes': {'buy_call': buy_k, 'sell_call': sell_k},
                'strike_details': {k: v.get('text', '') for k, v in [('buy_call', buy_d), ('sell_call', sell_d)]},
                'greeks_impact': 'Pos Delta, Reduced Vega (spread), Reduced Theta decay',
                'max_profit': max_profit * 100, 'max_loss': max_loss * 100,
                'risk_reward': f'{rr:.1f}:1',
                'pros': [f'IV high ({avg_iv:.0f}%) — spread offsets vega risk', f'R/R ratio: {rr:.1f}:1', 'Defined max loss'],
                'cons': [f'Profit capped at ${sell_k:.0f}', 'Needs move above ${0:.0f} to profit'.format(buy_k)],
                'risk_level': 'low',
                'liquidity': min(buy_liq, sell_liq),
            }
        elif iv_low:
            buy_k, buy_r, buy_liq = _find_strike(calls_df, price * 1.01, 'above')
            buy_d = _strike_detail(buy_r)
            cost = buy_d.get('mid', 0)
            be = buy_k + cost
            strategy = {
                'name': 'LONG CALL',
                'market_bias': 'bullish',
                'description': f'Buy ${buy_k:.0f}C — IV cheap ({avg_iv:.0f}%), long vega benefits from expansion',
                'strikes': {'buy_call': buy_k},
                'strike_details': {'buy_call': buy_d.get('text', '')},
                'greeks_impact': 'Pos Delta (~0.50), Long Vega, Neg Theta',
                'max_profit': 'Unlimited', 'max_loss': cost * 100,
                'breakeven': be,
                'risk_reward': f'Unlimited / ${cost*100:.0f}',
                'pros': [f'IV at {avg_iv:.0f}% — cheap entry', 'Unlimited upside', f'Breakeven: ${be:.2f}'],
                'cons': [f'Loses ${cost*100:.0f}/contract if expires OTM', f'Theta decay: ~${cost/dte*100:.0f}/day'],
                'risk_level': 'medium-high',
                'liquidity': buy_liq,
            }
        else:
            sell_k, sell_r, sell_liq = _find_strike(calls_df, otm_call_target, 'above')
            sell_d = _strike_detail(sell_r)
            credit = sell_d.get('mid', 0)
            strategy = {
                'name': 'COVERED CALL',
                'market_bias': 'mild bullish',
                'description': f'Sell ${sell_k:.0f}C — collect premium, cap upside at GEX resistance',
                'strikes': {'sell_call': sell_k},
                'strike_details': {'sell_call': sell_d.get('text', '')},
                'greeks_impact': 'Pos Theta, Short Vega, Short Gamma',
                'max_profit': credit * 100, 'max_loss': 'Stock downside',
                'risk_reward': f'${credit*100:.0f} credit / stock risk',
                'pros': ['Theta income', f'Premium: ${credit*100:.0f}/contract', 'Call wall caps upside anyway'],
                'cons': ['Caps profit above strike', 'Full downside if stock drops'],
                'risk_level': 'medium',
                'liquidity': sell_liq,
            }

    elif trend == 'bearish':
        if skew_high:
            buy_k, buy_r, buy_liq = _find_strike(puts_df, price * 0.99, 'below')
            sell_target = put_wall if put_wall < buy_k else price * 0.94
            sell_k, sell_r, sell_liq = _find_strike(puts_df, sell_target, 'below')
            if sell_k >= buy_k:
                sell_k, sell_r, sell_liq = _find_strike(puts_df, buy_k * 0.94, 'below')
            buy_d = _strike_detail(buy_r)
            sell_d = _strike_detail(sell_r)
            max_loss = buy_d.get('mid', 0) - sell_d.get('mid', 0) if buy_d and sell_d else 0
            max_profit = (buy_k - sell_k) - max_loss if buy_k > sell_k else 0
            rr = (max_profit / max_loss) if max_loss > 0 else 0
            strategy = {
                'name': 'BEAR PUT SPREAD',
                'market_bias': 'bearish',
                'description': f'Buy ${buy_k:.0f}P / Sell ${sell_k:.0f}P — spread to offset expensive puts',
                'strikes': {'buy_put': buy_k, 'sell_put': sell_k},
                'strike_details': {k: v.get('text', '') for k, v in [('buy_put', buy_d), ('sell_put', sell_d)]},
                'greeks_impact': 'Neg Delta, Reduced Vega, Reduced Theta',
                'max_profit': max_profit * 100, 'max_loss': max_loss * 100,
                'risk_reward': f'{rr:.1f}:1',
                'pros': [f'Spread offsets SKEW premium ({skew:.1f}pp)', f'R/R: {rr:.1f}:1', 'Defined risk'],
                'cons': [f'Profit capped at ${sell_k:.0f}', f'Puts expensive (SKEW {skew:.1f}pp)'],
                'risk_level': 'medium',
                'liquidity': min(buy_liq, sell_liq),
                'warning': f'SKEW {skew:.1f}pp — puts overpriced. Spread reduces cost vs naked put.'
            }
        else:
            buy_k, buy_r, buy_liq = _find_strike(puts_df, price * 0.98, 'below')
            buy_d = _strike_detail(buy_r)
            cost = buy_d.get('mid', 0)
            be = buy_k - cost
            strategy = {
                'name': 'LONG PUT',
                'market_bias': 'bearish',
                'description': f'Buy ${buy_k:.0f}P — direct bearish bet, reasonable IV',
                'strikes': {'buy_put': buy_k},
                'strike_details': {'buy_put': buy_d.get('text', '')},
                'greeks_impact': 'Neg Delta (~-0.45), Long Vega, Neg Theta',
                'max_profit': (buy_k - cost) * 100, 'max_loss': cost * 100,
                'breakeven': be,
                'risk_reward': f'${(buy_k - cost)*100:.0f} / ${cost*100:.0f}',
                'pros': ['High profit if price crashes', f'Breakeven: ${be:.2f}', 'Simple directional trade'],
                'cons': [f'Loses ${cost*100:.0f}/contract if expires OTM', f'Theta: ~${cost/dte*100:.0f}/day'],
                'risk_level': 'medium-high',
                'liquidity': buy_liq,
            }

    else:  # NEUTRAL
        if iv_high:
            sc_k, sc_r, sc_liq = _find_strike(calls_df, otm_call_target, 'above')
            bc_k, bc_r, bc_liq = _find_strike(calls_df, sc_k * 1.04, 'above')
            sp_k, sp_r, sp_liq = _find_strike(puts_df, otm_put_target, 'below')
            bp_k, bp_r, bp_liq = _find_strike(puts_df, sp_k * 0.96, 'below')
            sc_d, bc_d, sp_d, bp_d = _strike_detail(sc_r), _strike_detail(bc_r), _strike_detail(sp_r), _strike_detail(bp_r)
            credit = sc_d.get('mid', 0) + sp_d.get('mid', 0) - bc_d.get('mid', 0) - bp_d.get('mid', 0)
            wing_width = max(bc_k - sc_k, sp_k - bp_k)
            max_loss = (wing_width - credit) if wing_width > credit else wing_width
            rr = (credit / max_loss) if max_loss > 0 else 0
            strategy = {
                'name': 'IRON CONDOR',
                'market_bias': 'neutral / range-bound',
                'description': f'Sell ${sp_k:.0f}P/${sc_k:.0f}C — collect premium within GEX range',
                'strikes': {'sell_put': sp_k, 'buy_put': bp_k, 'sell_call': sc_k, 'buy_call': bc_k},
                'strike_details': {
                    'sell_call': sc_d.get('text', ''), 'buy_call': bc_d.get('text', ''),
                    'sell_put': sp_d.get('text', ''), 'buy_put': bp_d.get('text', ''),
                },
                'greeks_impact': 'Short Vega, Pos Theta, Near-zero Delta',
                'max_profit': credit * 100, 'max_loss': max_loss * 100,
                'risk_reward': f'{rr:.2f}:1 (credit/risk)',
                'pros': [f'IV high ({avg_iv:.0f}%) = rich premium', f'Credit: ${credit*100:.0f}/contract', 'Theta income daily'],
                'cons': ['Loses on breakout past wings', f'Max loss: ${max_loss*100:.0f}/contract'],
                'risk_level': 'medium',
                'liquidity': min(sc_liq, sp_liq),
            }
        else:
            sell_k, sell_r, sell_liq = _find_strike(puts_df, price * 0.95, 'below')
            sell_d = _strike_detail(sell_r)
            credit = sell_d.get('mid', 0)
            strategy = {
                'name': 'CASH-SECURED PUT',
                'market_bias': 'neutral-mild bullish',
                'description': f'Sell ${sell_k:.0f}P — get paid to set a buy limit',
                'strikes': {'sell_put': sell_k},
                'strike_details': {'sell_put': sell_d.get('text', '')},
                'greeks_impact': 'Pos Theta, Short Vega, Short Gamma',
                'max_profit': credit * 100, 'max_loss': (sell_k - credit) * 100,
                'risk_reward': f'${credit*100:.0f} / ${(sell_k - credit)*100:.0f}',
                'pros': [f'Premium: ${credit*100:.0f}/contract', 'Theta works for you', 'Effectively a limit buy order'],
                'cons': ['Full risk below strike', f'IV {avg_iv:.0f}% = moderate premium'],
                'risk_level': 'medium',
                'liquidity': sell_liq,
            }

    # =========================================================================
    # 6. GEX CONTEXT + UNUSUAL ACTIVITY
    # =========================================================================
    gex_note = ''
    if call_wall > 0 and put_wall > 0:
        gex_note = f'GEX range: ${put_wall:.0f} support — ${call_wall:.0f} resistance. '
    if gamma_regime == 'POSITIVE GAMMA':
        gex_note += 'Positive gamma: price pinned, sell premium works well.'
    elif gamma_regime == 'NEGATIVE GAMMA':
        gex_note += 'Negative gamma: big moves likely, long options benefit.'

    strategy['gex_note'] = gex_note
    strategy['bias_score'] = bias_score
    strategy['bias_reasons'] = bias_reasons
    strategy['expected_move'] = {'pct': expected_move_pct, 'abs': expected_move_abs}

    # Unusual activity alerts
    if unusual_calls[:3] or unusual_puts[:3]:
        activity = []
        for u in unusual_calls[:2]:
            activity.append(f"CALL ${u['strike']:.0f}: Vol/OI {u['vol_oi']:.1f}x ({u['vol']:,} vol vs {u['oi']:,} OI) — ${u['premium']/1000:.0f}K premium")
        for u in unusual_puts[:2]:
            activity.append(f"PUT ${u['strike']:.0f}: Vol/OI {u['vol_oi']:.1f}x ({u['vol']:,} vol vs {u['oi']:,} OI) — ${u['premium']/1000:.0f}K premium")
        strategy['unusual_activity'] = activity

    # Context
    strategy['context'] = {
        'skew': f'{skew:+.1f}pp',
        'avg_iv': f'{avg_iv:.0f}%',
        'gamma_regime': gamma_regime,
        'pc_ratio': f'{pc_ratio:.2f}',
        'dte': dte,
        'expected_move': f'±{expected_move_pct:.1f}%' if expected_move_pct > 0 else 'N/A',
    }

    return strategy


def create_skew_historical_chart(ticker: str, price_data: pd.DataFrame = None):
    """
    Create dual-panel SKEW historical chart (MenthorQ style).

    Panel 1: Price candlesticks
    Panel 2: SKEW timeline with PUT BIAS / CALL BIAS zones

    Parameters:
    -----------
    ticker : str - Ticker symbol
    price_data : pd.DataFrame - Historical price data (optional, will fetch if not provided)

    Returns:
    --------
    plotly.graph_objects.Figure or None
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    history_file = ROOT_DIR / 'data' / f'skew_history_{ticker}.json'

    # Load SKEW history
    try:
        if not history_file.exists():
            return None

        with open(history_file, 'r') as f:
            skew_history = json.load(f)

        if len(skew_history) < 2:
            return None  # Not enough data

        # Convert to DataFrame
        skew_df = pd.DataFrame(skew_history)
        skew_df['date'] = pd.to_datetime(skew_df['date'])
        skew_df = skew_df.sort_values('date')

        # Calculate rolling stats
        skew_df['avg_30d'] = skew_df['skew'].rolling(min(30, len(skew_df)), min_periods=1).mean()
        skew_df['min_30d'] = skew_df['skew'].rolling(min(30, len(skew_df)), min_periods=1).min()
        skew_df['max_30d'] = skew_df['skew'].rolling(min(30, len(skew_df)), min_periods=1).max()

        # Fetch price data if not provided
        if price_data is None or price_data.empty:
            start_date = skew_df['date'].min()
            try:
                stock = yf.Ticker(ticker)
                price_data = stock.history(start=start_date, interval='1d')
            except Exception:
                price_data = pd.DataFrame()

        # Create dual-panel subplot
        fig = make_subplots(
            rows=2, cols=1,
            row_heights=[0.6, 0.4],
            vertical_spacing=0.05,
            subplot_titles=(f'{ticker} Price', '25Δ Risk Reversal SKEW'),
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )

        # =====================================================================
        # PANEL 1: PRICE CANDLESTICKS
        # =====================================================================
        if not price_data.empty:
            fig.add_trace(go.Candlestick(
                x=price_data.index,
                open=price_data['Open'],
                high=price_data['High'],
                low=price_data['Low'],
                close=price_data['Close'],
                name='Price',
                increasing_line_color='#3fb950',
                decreasing_line_color='#f85149',
                showlegend=False
            ), row=1, col=1)

        # =====================================================================
        # PANEL 2: SKEW TIMELINE
        # =====================================================================

        # PUT BIAS zone (SKEW > avg)
        avg_skew = skew_df['skew'].mean()
        put_bias_zone = skew_df[skew_df['skew'] > avg_skew].copy()
        if not put_bias_zone.empty:
            fig.add_trace(go.Scatter(
                x=put_bias_zone['date'],
                y=put_bias_zone['skew'],
                fill='tonexty',
                fillcolor='rgba(248, 81, 73, 0.3)',
                line=dict(width=0),
                name='PUT BIAS',
                showlegend=True,
                hoverinfo='skip'
            ), row=2, col=1)

        # CALL BIAS zone (SKEW < avg)
        call_bias_zone = skew_df[skew_df['skew'] <= avg_skew].copy()
        if not call_bias_zone.empty:
            fig.add_trace(go.Scatter(
                x=call_bias_zone['date'],
                y=call_bias_zone['skew'],
                fill='tozeroy',
                fillcolor='rgba(63, 185, 80, 0.3)',
                line=dict(width=0),
                name='CALL BIAS',
                showlegend=True,
                hoverinfo='skip'
            ), row=2, col=1)

        # Main SKEW line (25D Risk Reversal)
        fig.add_trace(go.Scatter(
            x=skew_df['date'],
            y=skew_df['skew'],
            mode='lines',
            name='25D RR SKEW',
            line=dict(color='#ffffff', width=2.5),
            hovertemplate='%{x|%Y-%m-%d}<br>SKEW: %{y:+.2f}pp<extra></extra>'
        ), row=2, col=1)

        # Avg 30D line
        fig.add_trace(go.Scatter(
            x=skew_df['date'],
            y=skew_df['avg_30d'],
            mode='lines',
            name='Avg 30D',
            line=dict(color='#d29922', width=1.5, dash='dot'),
            hovertemplate='%{x|%Y-%m-%d}<br>Avg: %{y:+.2f}pp<extra></extra>'
        ), row=2, col=1)

        # Min/Max 30D bands (optional, lighter)
        fig.add_trace(go.Scatter(
            x=skew_df['date'],
            y=skew_df['max_30d'],
            mode='lines',
            name='Max 30D',
            line=dict(color='#6e7681', width=1, dash='dash'),
            showlegend=False,
            hoverinfo='skip'
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=skew_df['date'],
            y=skew_df['min_30d'],
            mode='lines',
            name='Min 30D',
            line=dict(color='#6e7681', width=1, dash='dash'),
            showlegend=False,
            hoverinfo='skip'
        ), row=2, col=1)

        # =====================================================================
        # LAYOUT
        # =====================================================================
        fig.update_layout(
            height=600,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='rgba(13,17,23,1)',
            plot_bgcolor='rgba(13,17,23,0.5)',
            font={'color': '#e6edf3', 'size': 10},
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=9)
            )
        )

        # X-axis formatting
        fig.update_xaxes(
            gridcolor='#21262d',
            showgrid=True,
            zeroline=False,
            row=1, col=1
        )
        fig.update_xaxes(
            gridcolor='#21262d',
            showgrid=True,
            zeroline=False,
            row=2, col=1
        )

        # Y-axis formatting
        fig.update_yaxes(
            title_text="Price ($)",
            gridcolor='#21262d',
            showgrid=True,
            zeroline=False,
            row=1, col=1
        )
        fig.update_yaxes(
            title_text="SKEW (pp)",
            gridcolor='#21262d',
            showgrid=True,
            zeroline=True,
            zerolinecolor='#30363d',
            zerolinewidth=1,
            row=2, col=1
        )

        return fig

    except Exception as e:
        print(f"Error creating SKEW chart: {e}")
        return None
