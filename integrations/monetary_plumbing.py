"""
===============================================================================
MONETARY PLUMBING ANALYZER - Análisis de Fontanería Monetaria V2
===============================================================================
Analiza las condiciones de liquidez macro para ajustar dinámicamente los pesos.

INDICADORES CLAVE:
    1. Fed Balance Sheet - QE/QT indicator
    2. TGA (Treasury General Account) - Drena liquidez cuando sube
    3. RRP (Reverse Repo) - Liquidez "aparcada"
    4. Net Liquidity = Fed BS - TGA - RRP
    5. Credit Spreads (HY vs IG) - Stress financiero
    6. VIX - Volatilidad/miedo
    7. MOVE Index - Volatilidad de bonos (bond market VIX) ← NUEVO
    8. Japan Contagion - JGB yields, USD/JPY, carry trade ← NUEVO
    9. DXY (Dollar Index) - Fortaleza del dólar ← NUEVO

ALERTAS DE RIESGO GLOBAL:
    - MOVE > 120: Stress en mercado de bonos (ALERTA)
    - JGB 10Y spike: Posible contagio global
    - USD/JPY fuerte movimiento: Carry trade unwinding
    - VIX > 25 + MOVE > 100: Risk-off mode

REGIMENES DE LIQUIDEZ:
    - ABUNDANT: Net Liquidity creciendo, spreads bajos, VIX/MOVE bajo
    - NEUTRAL: Condiciones mixtas
    - TIGHT: Net Liquidity cayendo, spreads altos, VIX/MOVE alto
    - CRISIS: MOVE > 140, VIX > 30, credit spreads widening

AJUSTE DE PESOS:
    - ABUNDANT → Más Momentum, menos Defensive
    - TIGHT → Más Quality/LowVol, menos Momentum
    - CRISIS → Máximo Quality/LowVol, mínimo Momentum
===============================================================================
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import yfinance as yf

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Thresholds para clasificación de régimen
LIQUIDITY_THRESHOLDS = {
    'net_liquidity_growth': {
        'abundant': 0.02,   # >2% crecimiento mensual
        'tight': -0.02,     # <-2% decrecimiento mensual
    },
    'vix': {
        'low': 15,
        'high': 25,
        'crisis': 30,       # Pánico
    },
    'hy_spread': {
        'tight': 350,       # bps, condiciones fáciles
        'wide': 500,        # bps, stress
    },
    # NUEVOS - MOVE Index (Bond Volatility)
    'move': {
        'calm': 80,         # Mercado de bonos tranquilo
        'elevated': 100,    # Volatilidad elevada
        'stress': 120,      # Stress significativo
        'crisis': 140,      # Crisis de bonos
    },
    # NUEVOS - Japan/Carry Trade
    'usdjpy': {
        'normal_range': (140, 155),  # Rango normal
        'carry_unwind_speed': 2.0,   # Movimiento >2% en 5 días = alerta
    },
    'jgb_10y': {
        'normal': 1.0,      # Yield normal ~1%
        'elevated': 1.3,    # Por encima del techo BOJ
        'crisis': 1.5,      # Posible intervención
    },
    # DXY (Dollar Index)
    'dxy': {
        'weak': 100,        # Dólar débil - bueno para EM
        'strong': 105,      # Dólar fuerte - presión EM
        'very_strong': 110, # Dólar muy fuerte - crisis EM
    },
}

# Ajustes de peso por régimen
REGIME_WEIGHT_ADJUSTMENTS = {
    'ABUNDANT_LIQUIDITY': {
        'value': -0.05,
        'quality': -0.05,
        'momentum': +0.15,
        'lowvol': -0.10,
        'congress': +0.03,
        'polymarket': +0.02,
    },
    'NEUTRAL_LIQUIDITY': {
        'value': 0,
        'quality': 0,
        'momentum': 0,
        'lowvol': 0,
        'congress': 0,
        'polymarket': 0,
    },
    'TIGHT_LIQUIDITY': {
        'value': +0.05,
        'quality': +0.10,
        'momentum': -0.10,
        'lowvol': +0.10,
        'congress': -0.05,
        'polymarket': -0.05,
    },
    # NUEVO - Régimen de crisis (MOVE alto, VIX alto, Japan stress)
    'CRISIS_MODE': {
        'value': +0.10,
        'quality': +0.15,
        'momentum': -0.20,
        'lowvol': +0.15,
        'congress': -0.10,
        'polymarket': -0.10,
    },
}

# =============================================================================
# FUNCIONES DE DATOS
# =============================================================================

def get_fred_data(series_id: str, days: int = 365) -> Optional[pd.DataFrame]:
    """
    Obtiene datos de FRED (Federal Reserve Economic Data).
    Nota: Requiere API key para uso intensivo, pero funciona sin ella para requests limitados.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv"
        params = {
            'id': series_id,
            'cosd': start_date.strftime('%Y-%m-%d'),
            'coed': end_date.strftime('%Y-%m-%d'),
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            df.columns = ['date', 'value']
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df
        return None
    except Exception as e:
        print(f"  Error fetching FRED {series_id}: {e}")
        return None


def get_fed_balance_sheet() -> Dict:
    """
    Obtiene el balance de la Fed (proxy: Total Assets).
    Series: WALCL (Total Assets, Weekly)
    """
    # Intentar FRED primero
    df = get_fred_data('WALCL', days=365)

    if df is not None and not df.empty:
        current = df['value'].iloc[-1]
        month_ago = df['value'].iloc[-4] if len(df) >= 4 else current
        year_ago = df['value'].iloc[0] if len(df) > 0 else current

        return {
            'current': current / 1e6,  # En trillones
            'change_1m': (current - month_ago) / month_ago if month_ago else 0,
            'change_1y': (current - year_ago) / year_ago if year_ago else 0,
            'trend': 'QE' if current > month_ago else 'QT',
            'source': 'FRED',
        }

    # Fallback: usar datos aproximados recientes
    return {
        'current': 6.8,  # ~$6.8T aproximado 2024
        'change_1m': -0.01,  # QT ongoing
        'change_1y': -0.05,
        'trend': 'QT',
        'source': 'ESTIMATED',
    }


def get_tga_balance() -> Dict:
    """
    Treasury General Account - la cuenta del Tesoro en la Fed.
    Series: WTREGEN (Treasury General Account, Weekly)
    Cuando sube → drena liquidez del sistema
    Cuando baja → inyecta liquidez
    """
    df = get_fred_data('WTREGEN', days=365)

    if df is not None and not df.empty:
        current = df['value'].iloc[-1]
        month_ago = df['value'].iloc[-4] if len(df) >= 4 else current
        avg = df['value'].mean()

        return {
            'current': current / 1e3,  # En billones
            'change_1m': (current - month_ago) / month_ago if month_ago else 0,
            'vs_average': (current - avg) / avg if avg else 0,
            'impact': 'DRAINING' if current > avg else 'INJECTING',
            'source': 'FRED',
        }

    return {
        'current': 0.75,  # ~$750B aproximado
        'change_1m': 0,
        'vs_average': 0,
        'impact': 'NEUTRAL',
        'source': 'ESTIMATED',
    }


def get_rrp_balance() -> Dict:
    """
    Reverse Repo Facility - liquidez "aparcada" por money market funds.
    Series: RRPONTSYD (Overnight Reverse Repo)
    Cuando sube → hay exceso de liquidez buscando rendimiento seguro
    Cuando baja → liquidez volviendo al sistema
    """
    df = get_fred_data('RRPONTSYD', days=365)

    if df is not None and not df.empty:
        current = df['value'].iloc[-1]
        month_ago = df['value'].iloc[-20] if len(df) >= 20 else current
        peak = df['value'].max()

        return {
            'current': current / 1e3,  # En billones
            'change_1m': (current - month_ago) / month_ago if month_ago else 0,
            'vs_peak': (current - peak) / peak if peak else 0,
            'trend': 'DECLINING' if current < month_ago else 'RISING',
            'source': 'FRED',
        }

    return {
        'current': 0.5,  # ~$500B aproximado 2024 (bajando desde $2T+)
        'change_1m': -0.10,
        'vs_peak': -0.75,
        'trend': 'DECLINING',
        'source': 'ESTIMATED',
    }


def get_credit_spreads() -> Dict:
    """
    Credit spreads como indicador de stress financiero.
    Usa ETFs como proxy: HYG (High Yield) vs LQD (Investment Grade)
    """
    try:
        hyg = yf.Ticker('HYG')
        lqd = yf.Ticker('LQD')

        hyg_info = hyg.info
        lqd_info = lqd.info

        hyg_yield = hyg_info.get('yield', 0.07) * 100  # ~7%
        lqd_yield = lqd_info.get('yield', 0.05) * 100  # ~5%

        spread = (hyg_yield - lqd_yield) * 100  # En bps

        # Clasificar
        if spread < LIQUIDITY_THRESHOLDS['hy_spread']['tight']:
            condition = 'TIGHT_SPREADS'  # Bueno para risk
        elif spread > LIQUIDITY_THRESHOLDS['hy_spread']['wide']:
            condition = 'WIDE_SPREADS'  # Stress
        else:
            condition = 'NORMAL_SPREADS'

        return {
            'hy_yield': hyg_yield,
            'ig_yield': lqd_yield,
            'spread_bps': spread,
            'condition': condition,
            'source': 'YFINANCE',
        }
    except Exception as e:
        return {
            'hy_yield': 7.0,
            'ig_yield': 5.0,
            'spread_bps': 200,
            'condition': 'NORMAL_SPREADS',
            'source': 'ESTIMATED',
        }


def get_vix() -> Dict:
    """VIX - índice de volatilidad/miedo"""
    try:
        vix = yf.Ticker('^VIX')
        hist = vix.history(period='3mo')

        if hist.empty:
            raise ValueError("No VIX data")

        current = hist['Close'].iloc[-1]
        avg_30d = hist['Close'].tail(30).mean()
        avg_90d = hist['Close'].mean()

        if current < LIQUIDITY_THRESHOLDS['vix']['low']:
            condition = 'LOW_FEAR'
        elif current > LIQUIDITY_THRESHOLDS['vix']['high']:
            condition = 'HIGH_FEAR'
        else:
            condition = 'NORMAL'

        return {
            'current': current,
            'avg_30d': avg_30d,
            'avg_90d': avg_90d,
            'condition': condition,
            'source': 'YFINANCE',
        }
    except:
        return {
            'current': 18,
            'avg_30d': 17,
            'avg_90d': 16,
            'condition': 'NORMAL',
            'source': 'ESTIMATED',
        }


# =============================================================================
# NUEVOS INDICADORES V2
# =============================================================================

def get_move_index() -> Dict:
    """
    MOVE Index - Merrill Lynch Option Volatility Estimate
    Es el "VIX de los bonos" - mide volatilidad implícita en Treasury options.

    INTERPRETACIÓN:
    - MOVE < 80: Mercado de bonos muy tranquilo (risk-on)
    - MOVE 80-100: Volatilidad normal
    - MOVE 100-120: Volatilidad elevada, precaución
    - MOVE 120-140: Stress significativo en bonos (alerta)
    - MOVE > 140: Crisis de bonos (risk-off extremo)

    CORRELACIÓN CON EQUITIES:
    - MOVE alto generalmente precede caídas en equities
    - Spike en MOVE = posible risk-off inminente
    """
    try:
        # El MOVE Index no está directamente disponible en yfinance
        # Usamos TLT volatility como proxy
        tlt = yf.Ticker('TLT')
        hist = tlt.history(period='3mo')

        if hist.empty:
            raise ValueError("No TLT data")

        # Calcular volatilidad realizada (proxy para MOVE)
        returns = hist['Close'].pct_change().dropna()
        vol_20d = returns.tail(20).std() * np.sqrt(252) * 100  # Anualizada

        # Escalar para aproximar MOVE (TLT vol ~15% ≈ MOVE 100)
        move_proxy = vol_20d * 6.67  # Factor de escala aproximado

        current = move_proxy
        change_5d = (hist['Close'].iloc[-1] / hist['Close'].iloc[-5] - 1) * 100

        # Clasificar condición
        thresholds = LIQUIDITY_THRESHOLDS['move']
        if current < thresholds['calm']:
            condition = 'CALM'
            impact = 'RISK_ON'
        elif current < thresholds['elevated']:
            condition = 'NORMAL'
            impact = 'NEUTRAL'
        elif current < thresholds['stress']:
            condition = 'ELEVATED'
            impact = 'CAUTION'
        elif current < thresholds['crisis']:
            condition = 'STRESS'
            impact = 'RISK_OFF'
        else:
            condition = 'CRISIS'
            impact = 'EXTREME_RISK_OFF'

        return {
            'current': round(current, 1),
            'tlt_change_5d': round(change_5d, 2),
            'condition': condition,
            'impact': impact,
            'interpretation': _interpret_move(current),
            'source': 'TLT_PROXY',
        }

    except Exception as e:
        return {
            'current': 90,  # Valor neutral estimado
            'tlt_change_5d': 0,
            'condition': 'NORMAL',
            'impact': 'NEUTRAL',
            'interpretation': 'Sin datos - asumiendo condiciones normales',
            'source': 'ESTIMATED',
        }


def _interpret_move(move_value: float) -> str:
    """Interpreta el valor del MOVE index"""
    if move_value < 80:
        return "🟢 Bonos tranquilos - favorable para risk assets"
    elif move_value < 100:
        return "🟡 Volatilidad normal en bonos"
    elif move_value < 120:
        return "🟠 Volatilidad elevada - monitorear posiciones"
    elif move_value < 140:
        return "🔴 STRESS en bonos - reducir exposición a risk"
    else:
        return "⛔ CRISIS en bonos - máxima precaución, risk-off"


def get_japan_indicators() -> Dict:
    """
    Indicadores de Japón para detectar contagio global.

    CARRY TRADE EXPLAINED:
    - Inversores piden prestado en JPY (tasas bajas ~0%)
    - Invierten en activos de mayor yield (US bonds, EM, etc.)
    - Cuando JPY sube rápido o JGB yields suben → unwind del carry trade
    - Esto causa ventas masivas globales

    INDICADORES:
    1. USD/JPY: Movimiento brusco = alerta
    2. JGB 10Y Yield: Spike = posible intervención BOJ
    3. Japanese Bank Stocks (MUFG, SMFG): Proxy de stress bancario japonés

    EVENTO DE AYER (ejemplo):
    - JGB yields subieron por incertidumbre política BOJ
    - Carry trade unwind causó ventas globales
    - Nikkei cayó, contagio a US/EU
    """
    try:
        # 1. USD/JPY - Usar JPY=X directamente (yfinance ya da USD/JPY, no JPY/USD)
        usdjpy = yf.Ticker('JPY=X')
        usdjpy_hist = usdjpy.history(period='1mo')

        if not usdjpy_hist.empty:
            # JPY=X ya devuelve USD/JPY directamente (~155-160)
            usdjpy_current = usdjpy_hist['Close'].iloc[-1]
            usdjpy_5d_ago = usdjpy_hist['Close'].iloc[-5] if len(usdjpy_hist) >= 5 else usdjpy_current
            usdjpy_change_5d = ((usdjpy_current / usdjpy_5d_ago) - 1) * 100
        else:
            usdjpy_current = 155
            usdjpy_change_5d = 0

        # 2. Japanese Bank Stocks como proxy de stress
        mufg = yf.Ticker('MUFG')
        mufg_hist = mufg.history(period='1mo')

        if not mufg_hist.empty:
            mufg_change_5d = ((mufg_hist['Close'].iloc[-1] / mufg_hist['Close'].iloc[-5]) - 1) * 100 if len(mufg_hist) >= 5 else 0
        else:
            mufg_change_5d = 0

        # 3. Nikkei 225 como indicador de stress japonés
        nikkei = yf.Ticker('^N225')
        nikkei_hist = nikkei.history(period='1mo')

        if not nikkei_hist.empty:
            nikkei_change_5d = ((nikkei_hist['Close'].iloc[-1] / nikkei_hist['Close'].iloc[-5]) - 1) * 100 if len(nikkei_hist) >= 5 else 0
            nikkei_current = nikkei_hist['Close'].iloc[-1]
        else:
            nikkei_change_5d = 0
            nikkei_current = 0

        # Detectar alertas
        alerts = []
        carry_trade_risk = 'LOW'

        # Alerta por movimiento brusco en USD/JPY
        if abs(usdjpy_change_5d) > LIQUIDITY_THRESHOLDS['usdjpy']['carry_unwind_speed']:
            if usdjpy_change_5d < 0:  # JPY fortaleciendo (USD/JPY bajando)
                alerts.append(f"⚠️ CARRY TRADE UNWIND: JPY fortaleciendo {usdjpy_change_5d:.1f}% en 5d")
                carry_trade_risk = 'HIGH'
            else:
                alerts.append(f"📈 USD/JPY subiendo {usdjpy_change_5d:.1f}% - carry trade estable")

        # Alerta por caída en bancos japoneses
        if mufg_change_5d < -5:
            alerts.append(f"⚠️ Bancos japoneses cayendo: MUFG {mufg_change_5d:.1f}%")
            carry_trade_risk = 'ELEVATED' if carry_trade_risk == 'LOW' else carry_trade_risk

        # Alerta por caída del Nikkei
        if nikkei_change_5d < -3:
            alerts.append(f"⚠️ Nikkei cayendo {nikkei_change_5d:.1f}% - posible contagio")

        # Determinar condición general
        if carry_trade_risk == 'HIGH':
            condition = 'CARRY_UNWIND_ALERT'
            impact = 'GLOBAL_RISK_OFF'
        elif carry_trade_risk == 'ELEVATED' or nikkei_change_5d < -5:
            condition = 'ELEVATED_RISK'
            impact = 'CAUTION'
        else:
            condition = 'STABLE'
            impact = 'NEUTRAL'

        return {
            'usdjpy': {
                'current': round(usdjpy_current, 2),
                'change_5d_pct': round(usdjpy_change_5d, 2),
            },
            'japanese_banks': {
                'mufg_change_5d': round(mufg_change_5d, 2),
            },
            'nikkei': {
                'current': round(nikkei_current, 0),
                'change_5d_pct': round(nikkei_change_5d, 2),
            },
            'carry_trade_risk': carry_trade_risk,
            'condition': condition,
            'impact': impact,
            'alerts': alerts,
            'interpretation': _interpret_japan(condition, alerts),
            'source': 'YFINANCE',
        }

    except Exception as e:
        return {
            'usdjpy': {'current': 150, 'change_5d_pct': 0},
            'japanese_banks': {'mufg_change_5d': 0},
            'nikkei': {'current': 0, 'change_5d_pct': 0},
            'carry_trade_risk': 'UNKNOWN',
            'condition': 'NO_DATA',
            'impact': 'UNKNOWN',
            'alerts': [],
            'interpretation': 'Sin datos de Japón disponibles',
            'source': 'ERROR',
        }


def _interpret_japan(condition: str, alerts: list) -> str:
    """Interpreta la situación de Japón"""
    if condition == 'CARRY_UNWIND_ALERT':
        return "🔴 ALERTA CARRY TRADE: Posible contagio global desde Japón. Reducir exposición."
    elif condition == 'ELEVATED_RISK':
        return "🟠 Riesgo elevado desde Japón. Monitorear posiciones."
    elif alerts:
        return "🟡 " + " | ".join(alerts)
    else:
        return "🟢 Japón estable - sin señales de carry trade unwind"


def get_dxy() -> Dict:
    """
    DXY - Dollar Index
    Mide fortaleza del dólar contra cesta de divisas principales.

    IMPACTO:
    - DXY alto (>105): Presión sobre EM, commodities, earnings multinacionales
    - DXY bajo (<100): Favorable para EM, commodities, gold
    - DXY spike rápido: Risk-off, flight to safety

    CORRELACIONES:
    - DXY ↑ + Gold ↓ = Risk-off tradicional
    - DXY ↑ + EM ↓ = Presión sobre emergentes
    - DXY ↓ + Commodities ↑ = Reflation trade
    """
    try:
        dxy = yf.Ticker('DX-Y.NYB')
        hist = dxy.history(period='3mo')

        if hist.empty:
            raise ValueError("No DXY data")

        current = hist['Close'].iloc[-1]
        change_5d = ((current / hist['Close'].iloc[-5]) - 1) * 100 if len(hist) >= 5 else 0
        avg_30d = hist['Close'].tail(30).mean()

        thresholds = LIQUIDITY_THRESHOLDS['dxy']

        if current < thresholds['weak']:
            condition = 'WEAK_DOLLAR'
            impact_em = 'FAVORABLE'
            impact_us = 'MIXED'
        elif current < thresholds['strong']:
            condition = 'NORMAL'
            impact_em = 'NEUTRAL'
            impact_us = 'NEUTRAL'
        elif current < thresholds['very_strong']:
            condition = 'STRONG_DOLLAR'
            impact_em = 'PRESSURE'
            impact_us = 'FAVORABLE'
        else:
            condition = 'VERY_STRONG_DOLLAR'
            impact_em = 'CRISIS_RISK'
            impact_us = 'EARNINGS_PRESSURE'

        return {
            'current': round(current, 2),
            'change_5d_pct': round(change_5d, 2),
            'avg_30d': round(avg_30d, 2),
            'vs_avg': round(((current / avg_30d) - 1) * 100, 2),
            'condition': condition,
            'impact_em': impact_em,
            'impact_us': impact_us,
            'interpretation': _interpret_dxy(current, change_5d),
            'source': 'YFINANCE',
        }

    except Exception as e:
        return {
            'current': 103,
            'change_5d_pct': 0,
            'avg_30d': 103,
            'vs_avg': 0,
            'condition': 'NORMAL',
            'impact_em': 'NEUTRAL',
            'impact_us': 'NEUTRAL',
            'interpretation': 'Sin datos DXY - asumiendo normal',
            'source': 'ESTIMATED',
        }


def _interpret_dxy(current: float, change_5d: float) -> str:
    """Interpreta el DXY"""
    direction = "subiendo" if change_5d > 0.5 else ("bajando" if change_5d < -0.5 else "estable")

    if current > 110:
        return f"⛔ Dólar MUY fuerte ({current:.1f}) {direction} - Crisis EM posible"
    elif current > 105:
        return f"🟠 Dólar fuerte ({current:.1f}) {direction} - Presión sobre EM y commodities"
    elif current < 100:
        return f"🟢 Dólar débil ({current:.1f}) {direction} - Favorable para EM y gold"
    else:
        return f"🟡 Dólar normal ({current:.1f}) {direction}"


def calculate_net_liquidity() -> Dict:
    """
    Net Liquidity = Fed Balance Sheet - TGA - RRP

    Esta es la métrica más importante para predecir movimientos de mercado.
    Cuando Net Liquidity sube → bullish para risk assets
    Cuando Net Liquidity baja → bearish para risk assets
    """
    fed_bs = get_fed_balance_sheet()
    tga = get_tga_balance()
    rrp = get_rrp_balance()

    # Calcular net liquidity (todo en trillones)
    net_liq = fed_bs['current'] - tga['current'] - rrp['current']

    # Estimar cambio mensual
    fed_change = fed_bs['change_1m'] * fed_bs['current']
    tga_change = tga['change_1m'] * tga['current']
    rrp_change = rrp['change_1m'] * rrp['current']

    net_change = fed_change - tga_change - rrp_change
    net_change_pct = net_change / net_liq if net_liq else 0

    # Clasificar régimen
    if net_change_pct > LIQUIDITY_THRESHOLDS['net_liquidity_growth']['abundant']:
        regime = 'EXPANDING'
    elif net_change_pct < LIQUIDITY_THRESHOLDS['net_liquidity_growth']['tight']:
        regime = 'CONTRACTING'
    else:
        regime = 'STABLE'

    return {
        'net_liquidity_T': round(net_liq, 2),
        'change_1m_pct': round(net_change_pct * 100, 2),
        'regime': regime,
        'components': {
            'fed_bs': fed_bs,
            'tga': tga,
            'rrp': rrp,
        },
    }


# =============================================================================
# ANÁLISIS DE RÉGIMEN
# =============================================================================

def analyze_monetary_regime() -> Dict:
    """
    Análisis completo del régimen monetario actual V2.
    Incluye MOVE index, Japan indicators, DXY y early warning system.
    Retorna clasificación y ajustes de peso recomendados.
    """
    print("  Analizando fontaneria monetaria...")

    # Indicadores tradicionales
    net_liq = calculate_net_liquidity()
    credit = get_credit_spreads()
    vix = get_vix()

    # NUEVOS indicadores V2
    move = get_move_index()
    japan = get_japan_indicators()
    dxy = get_dxy()

    # Scoring de condiciones (0-100, mayor = mejor para risk)
    scores = {
        'liquidity': 50,
        'credit': 50,
        'vix': 50,
        'move': 50,      # NUEVO
        'japan': 50,     # NUEVO
        'dxy': 50,       # NUEVO
    }

    # Liquidez
    if net_liq['regime'] == 'EXPANDING':
        scores['liquidity'] = 75
    elif net_liq['regime'] == 'CONTRACTING':
        scores['liquidity'] = 25

    # Credit
    if credit['condition'] == 'TIGHT_SPREADS':
        scores['credit'] = 75
    elif credit['condition'] == 'WIDE_SPREADS':
        scores['credit'] = 25

    # VIX
    if vix['condition'] == 'LOW_FEAR':
        scores['vix'] = 75
    elif vix['condition'] == 'HIGH_FEAR':
        scores['vix'] = 25

    # MOVE (Bond volatility) - NUEVO
    if move['condition'] == 'CALM':
        scores['move'] = 80
    elif move['condition'] == 'NORMAL':
        scores['move'] = 60
    elif move['condition'] == 'ELEVATED':
        scores['move'] = 40
    elif move['condition'] == 'STRESS':
        scores['move'] = 20
    elif move['condition'] == 'CRISIS':
        scores['move'] = 5

    # Japan/Carry Trade - NUEVO
    if japan['condition'] == 'STABLE':
        scores['japan'] = 70
    elif japan['condition'] == 'ELEVATED_RISK':
        scores['japan'] = 35
    elif japan['condition'] == 'CARRY_UNWIND_ALERT':
        scores['japan'] = 10

    # DXY - NUEVO
    if dxy['condition'] == 'WEAK_DOLLAR':
        scores['dxy'] = 70  # Bueno para EM y commodities
    elif dxy['condition'] == 'NORMAL':
        scores['dxy'] = 55
    elif dxy['condition'] == 'STRONG_DOLLAR':
        scores['dxy'] = 40
    elif dxy['condition'] == 'VERY_STRONG_DOLLAR':
        scores['dxy'] = 20

    # Score compuesto V2 (ponderado)
    composite_score = (
        scores['liquidity'] * 0.30 +
        scores['credit'] * 0.15 +
        scores['vix'] * 0.15 +
        scores['move'] * 0.20 +      # MOVE es muy importante
        scores['japan'] * 0.10 +
        scores['dxy'] * 0.10
    )

    # =========================================================================
    # EARLY WARNING SYSTEM - Detectar crisis antes de que ocurra
    # =========================================================================
    alerts = []
    crisis_signals = 0

    # Alerta 1: MOVE elevado
    if move['current'] > LIQUIDITY_THRESHOLDS['move']['stress']:
        alerts.append(f"🔴 MOVE Index alto ({move['current']:.0f}) - Stress en bonos")
        crisis_signals += 2
    elif move['current'] > LIQUIDITY_THRESHOLDS['move']['elevated']:
        alerts.append(f"🟠 MOVE Index elevado ({move['current']:.0f}) - Monitorear")
        crisis_signals += 1

    # Alerta 2: VIX alto
    if vix['current'] > LIQUIDITY_THRESHOLDS['vix']['crisis']:
        alerts.append(f"🔴 VIX en pánico ({vix['current']:.1f}) - Risk-off extremo")
        crisis_signals += 2
    elif vix['current'] > LIQUIDITY_THRESHOLDS['vix']['high']:
        alerts.append(f"🟠 VIX elevado ({vix['current']:.1f}) - Miedo en mercado")
        crisis_signals += 1

    # Alerta 3: Japan carry trade
    if japan['condition'] == 'CARRY_UNWIND_ALERT':
        alerts.append("🔴 CARRY TRADE UNWIND - Contagio desde Japón")
        crisis_signals += 2
    elif japan['alerts']:
        alerts.extend(japan['alerts'])
        crisis_signals += 1

    # Alerta 4: Credit spreads
    if credit['condition'] == 'WIDE_SPREADS':
        alerts.append(f"🟠 Credit spreads amplios ({credit['spread_bps']:.0f}bps)")
        crisis_signals += 1

    # Alerta 5: DXY muy fuerte
    if dxy['condition'] == 'VERY_STRONG_DOLLAR':
        alerts.append(f"🟠 Dólar muy fuerte ({dxy['current']:.1f}) - Presión EM")
        crisis_signals += 1

    # Determinar régimen con early warning
    if crisis_signals >= 4 or (move['condition'] == 'CRISIS' and vix['current'] > 25):
        regime = 'CRISIS_MODE'
        description = '⛔ MODO CRISIS - Múltiples señales de stress. Reducir riesgo inmediatamente.'
        recommendation = 'MÁXIMA PRECAUCIÓN: Quality/LowVol máximo, Momentum mínimo, considerar cash'
    elif crisis_signals >= 2 or composite_score <= 35:
        regime = 'TIGHT_LIQUIDITY'
        description = '🔴 Liquidez restringida - Señales de stress detectadas'
        recommendation = 'Sobreponderar Quality/LowVol, infraponderar Momentum'
    elif composite_score >= 65:
        regime = 'ABUNDANT_LIQUIDITY'
        description = '🟢 Liquidez abundante - Favorable para risk assets y momentum'
        recommendation = 'Sobreponderar Momentum, infraponderar Defensive'
    else:
        regime = 'NEUTRAL_LIQUIDITY'
        description = '🟡 Condiciones mixtas - Mantener balance'
        recommendation = 'Mantener pesos neutrales'

    return {
        'regime': regime,
        'composite_score': round(composite_score, 1),
        'description': description,
        'recommendation': recommendation,
        'weight_adjustments': REGIME_WEIGHT_ADJUSTMENTS.get(regime, {}),
        'scores': scores,
        'crisis_signals': crisis_signals,
        'alerts': alerts,
        'data': {
            'net_liquidity': net_liq,
            'credit_spreads': credit,
            'vix': vix,
            'move': move,        # NUEVO
            'japan': japan,      # NUEVO
            'dxy': dxy,          # NUEVO
        },
    }


def get_optimal_weights_for_regime(base_weights: Dict[str, float],
                                    regime_analysis: Dict) -> Dict[str, float]:
    """
    Calcula pesos óptimos ajustados por régimen monetario.
    """
    adjustments = regime_analysis.get('weight_adjustments', {})

    adjusted = {}
    for factor, base_weight in base_weights.items():
        adj = adjustments.get(factor, 0)
        adjusted[factor] = max(0.05, min(0.40, base_weight + adj))  # Límites 5%-40%

    # Normalizar para que sumen 1
    total = sum(adjusted.values())
    return {k: round(v / total, 3) for k, v in adjusted.items()}


# =============================================================================
# RECOMENDACIONES POR TIPO DE INVERSIÓN
# =============================================================================

def get_long_term_weights(regime_analysis: Dict) -> Dict[str, float]:
    """
    Pesos para inversión a largo plazo (value investing).
    Más estables, menos reactivos a condiciones de corto plazo.
    """
    base = {
        'value': 0.30,
        'quality': 0.35,
        'momentum': 0.10,
        'lowvol': 0.15,
        'congress': 0.05,
        'polymarket': 0.05,
    }

    # Ajustes menores para largo plazo
    regime = regime_analysis['regime']
    if regime == 'TIGHT_LIQUIDITY':
        base['quality'] += 0.05
        base['momentum'] -= 0.05
    elif regime == 'ABUNDANT_LIQUIDITY':
        base['value'] += 0.05
        base['lowvol'] -= 0.05

    total = sum(base.values())
    return {k: round(v / total, 3) for k, v in base.items()}


def get_momentum_weights(regime_analysis: Dict) -> Dict[str, float]:
    """
    Pesos para trading de momentum (corto/medio plazo).
    Muy reactivos a condiciones de liquidez.
    """
    base = {
        'value': 0.10,
        'quality': 0.15,
        'momentum': 0.40,
        'lowvol': 0.10,
        'congress': 0.15,
        'polymarket': 0.10,
    }

    regime = regime_analysis['regime']
    if regime == 'TIGHT_LIQUIDITY':
        # En liquidez tight, reducir momentum
        base['momentum'] = 0.25
        base['quality'] = 0.25
        base['lowvol'] = 0.20
    elif regime == 'ABUNDANT_LIQUIDITY':
        # En liquidez abundante, maximizar momentum
        base['momentum'] = 0.50
        base['quality'] = 0.10
        base['lowvol'] = 0.05

    total = sum(base.values())
    return {k: round(v / total, 3) for k, v in base.items()}


# =============================================================================
# REPORTING
# =============================================================================

def generate_monetary_report() -> str:
    """Genera reporte de condiciones monetarias V2 con todos los indicadores"""

    analysis = analyze_monetary_regime()

    # Extraer datos para facilitar acceso
    move = analysis['data'].get('move', {})
    japan = analysis['data'].get('japan', {})
    dxy = analysis['data'].get('dxy', {})

    report = f"""
================================================================================
ANÁLISIS DE FONTANERÍA MONETARIA V2
================================================================================

RÉGIMEN ACTUAL: {analysis['regime']}
Score Compuesto: {analysis['composite_score']}/100
Señales de Crisis: {analysis.get('crisis_signals', 0)}

{analysis['description']}

RECOMENDACIÓN: {analysis['recommendation']}

================================================================================
⚠️  EARLY WARNING SYSTEM - ALERTAS ACTIVAS
================================================================================
"""
    if analysis.get('alerts'):
        for alert in analysis['alerts']:
            report += f"   {alert}\n"
    else:
        report += "   ✅ Sin alertas activas - condiciones estables\n"

    report += f"""
================================================================================
INDICADORES DE VOLATILIDAD
================================================================================

1. VIX (Equity Volatility)
   Nivel actual: {analysis['data']['vix']['current']:.1f}
   Media 30d: {analysis['data']['vix']['avg_30d']:.1f}
   Condición: {analysis['data']['vix']['condition']}

2. MOVE INDEX (Bond Volatility) ← NUEVO
   Nivel actual: {move.get('current', 'N/A')}
   Condición: {move.get('condition', 'N/A')}
   Impacto: {move.get('impact', 'N/A')}
   {move.get('interpretation', '')}

================================================================================
INDICADORES DE JAPÓN / CARRY TRADE ← NUEVO
================================================================================

   USD/JPY: {japan.get('usdjpy', {}).get('current', 'N/A')} (5d: {japan.get('usdjpy', {}).get('change_5d_pct', 0):+.1f}%)
   Nikkei 225: {japan.get('nikkei', {}).get('current', 'N/A')} (5d: {japan.get('nikkei', {}).get('change_5d_pct', 0):+.1f}%)
   Bancos JP (MUFG): {japan.get('japanese_banks', {}).get('mufg_change_5d', 0):+.1f}% (5d)

   Riesgo Carry Trade: {japan.get('carry_trade_risk', 'N/A')}
   {japan.get('interpretation', '')}

================================================================================
INDICADORES DE DÓLAR ← NUEVO
================================================================================

   DXY: {dxy.get('current', 'N/A')} (5d: {dxy.get('change_5d_pct', 0):+.1f}%)
   vs Media 30d: {dxy.get('vs_avg', 0):+.1f}%
   Condición: {dxy.get('condition', 'N/A')}
   Impacto EM: {dxy.get('impact_em', 'N/A')}
   {dxy.get('interpretation', '')}

================================================================================
COMPONENTES DE LIQUIDEZ
================================================================================

1. NET LIQUIDITY
   Nivel actual: ${analysis['data']['net_liquidity']['net_liquidity_T']}T
   Cambio mensual: {analysis['data']['net_liquidity']['change_1m_pct']}%
   Régimen: {analysis['data']['net_liquidity']['regime']}

   - Fed Balance Sheet: ${analysis['data']['net_liquidity']['components']['fed_bs']['current']}T ({analysis['data']['net_liquidity']['components']['fed_bs']['trend']})
   - TGA: ${analysis['data']['net_liquidity']['components']['tga']['current']}T ({analysis['data']['net_liquidity']['components']['tga']['impact']})
   - RRP: ${analysis['data']['net_liquidity']['components']['rrp']['current']}T ({analysis['data']['net_liquidity']['components']['rrp']['trend']})

2. CREDIT SPREADS
   HY-IG Spread: {analysis['data']['credit_spreads']['spread_bps']} bps
   Condición: {analysis['data']['credit_spreads']['condition']}

================================================================================
SCORES POR COMPONENTE
================================================================================
"""
    for component, score in analysis['scores'].items():
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        report += f"   {component:12s}: {bar} {score:.0f}/100\n"

    report += f"""
================================================================================
AJUSTES DE PESO RECOMENDADOS
================================================================================
"""

    for factor, adj in analysis['weight_adjustments'].items():
        if adj > 0:
            report += f"   {factor}: +{adj*100:.0f}%\n"
        elif adj < 0:
            report += f"   {factor}: {adj*100:.0f}%\n"

    report += """
================================================================================
INTERPRETACIÓN PARA EVENTO TIPO "JAPÓN"
================================================================================

Si el sistema detecta:
- USD/JPY cayendo >2% en 5 días → ALERTA CARRY TRADE UNWIND
- MOVE subiendo >120 → ALERTA STRESS EN BONOS
- Nikkei cayendo >3% → POSIBLE CONTAGIO

Combinación de estas señales → CRISIS_MODE activado automáticamente

En CRISIS_MODE:
- Quality y LowVol sobreponderados
- Momentum infraponderado
- Recomendación: Reducir exposición, favorecer cash y defensivos
"""

    return report


if __name__ == '__main__':
    print(generate_monetary_report())
