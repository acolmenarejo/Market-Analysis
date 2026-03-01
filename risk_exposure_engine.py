#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RISK EXPOSURE ENGINE v1.0
================================================================================
Motor de probabilidades dinamicas para determinar nivel de exposicion al mercado.

Integra:
- Datos de liquidez (FRED API) del sistema existente
- Indicadores tecnicos de mercado (via yfinance)
- Sentimiento y posicionamiento
- Senales de fontaneria monetaria (plumbing)
- Alertas de crash historico pattern matching

Output: Score 0-100 donde:
  0-20  = FULL RISK-ON  (maxima exposicion)
  20-40 = RISK-ON       (exposicion normal)
  40-60 = CAUTELA       (reducir posiciones especulativas)
  60-80 = DEFENSIVO     (reducir a minimos, aumentar cash)
  80-100= PANICO/CASH   (liquidar, ir a cash/treasuries)

Autor: Peter's Financial Server
Fecha: Febrero 2026
================================================================================
"""

import os
import sys
import json
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURACION
# ============================================================================

FRED_API_KEY = os.environ.get('FRED_API_KEY', '')

# Pesos de cada modulo en el score final (suman 100)
MODULE_WEIGHTS = {
    'liquidity_stress':     25,   # Fontaneria monetaria (tu sistema existente)
    'market_technicals':    20,   # RSI, Bollinger, MA, breadth
    'valuation_excess':     15,   # P/E, CAPE, Buffett Indicator
    'volatility_regime':    15,   # VIX, MOVE, vol structure
    'positioning_crowding': 15,   # Put/Call, margin debt, ETF flows
    'macro_deterioration':  10,   # Yield curve, credit spreads, employment
}

# Umbrales historicos para pattern matching
CRASH_PATTERNS = {
    # ===== COMMODITY-DRIVEN =====
    '1980_silver': {
        'description': 'Hunt Brothers Silver Crash (1980)',
        'signals': ['parabolic_commodity', 'margin_hike', 'extreme_retail_positioning'],
        'category': 'commodities',
    },
    '2011_silver': {
        'description': 'Silver Correction Post-QE (2011)',
        'signals': ['parabolic_commodity', 'margin_hike_cascade', 'dollar_reversal'],
        'category': 'commodities',
    },

    # ===== EQUITY BUBBLES =====
    '1987_black_monday': {
        'description': 'Black Monday Crash (1987)',
        'signals': ['extreme_pe', 'correlation_spike', 'portfolio_insurance_unwind', 'vix_spike'],
        'category': 'equities',
    },
    '2000_dotcom': {
        'description': 'Dot-com Bubble Burst (2000)',
        'signals': ['extreme_pe', 'narrow_breadth', 'retail_mania', 'fed_tightening', 'ipo_mania'],
        'category': 'equities',
    },
    '2018_volmageddon': {
        'description': 'Volmageddon / XIV Collapse (2018)',
        'signals': ['extreme_low_vix', 'vix_spike', 'leverage_unwind', 'crowded_trade'],
        'category': 'equities',
    },
    '2022_fed_tightening': {
        'description': 'Fed Tightening / Growth Crash (2022)',
        'signals': ['fed_tightening', 'yield_curve_inversion', 'growth_tech_collapse', 'bond_equity_corr_break'],
        'category': 'equities',
    },

    # ===== CREDIT / BANKING =====
    '2008_gfc': {
        'description': 'Global Financial Crisis (2008)',
        'signals': ['credit_spread_blow', 'yield_curve_inversion', 'bank_stress', 'leverage_unwind', 'correlation_spike'],
        'category': 'credit',
    },
    '2023_svb': {
        'description': 'SVB / Regional Bank Crisis (2023)',
        'signals': ['bank_stress', 'bond_loss_unrealized', 'deposit_flight', 'fed_tightening'],
        'category': 'credit',
    },

    # ===== CURRENCY / CARRY =====
    '1997_asian_crisis': {
        'description': 'Asian Currency Crisis (1997)',
        'signals': ['dollar_reversal', 'em_stress', 'carry_trade_unwind', 'credit_spread_blow'],
        'category': 'currencies',
    },
    '2015_china_deval': {
        'description': 'China Devaluation Shock (2015)',
        'signals': ['em_stress', 'correlation_spike', 'vix_spike', 'dollar_reversal'],
        'category': 'currencies',
    },
    '2024_yen_carry': {
        'description': 'Yen Carry Trade Unwind (2024)',
        'signals': ['carry_trade_unwind', 'vix_spike', 'correlation_spike', 'em_stress'],
        'category': 'currencies',
    },

    # ===== LIQUIDITY / SYSTEMIC =====
    '2020_covid': {
        'description': 'COVID Liquidity Freeze (2020)',
        'signals': ['vix_spike', 'liquidity_freeze', 'credit_spread_blow', 'correlation_spike', 'treasury_stress'],
        'category': 'liquidity',
    },
    '2019_repo_crisis': {
        'description': 'Repo Market Crisis (2019)',
        'signals': ['liquidity_freeze', 'treasury_stress', 'bank_stress'],
        'category': 'liquidity',
    },

    # ===== CURRENT =====
    '2026_february_massacre': {
        'description': 'Feb 2026 Precious Metals + Tech Crash',
        'signals': ['parabolic_commodity', 'margin_hike', 'extreme_retail_positioning',
                    'crowded_trade', 'paper_physical_divergence', 'policy_shock'],
        'category': 'commodities',
    },
}


# ============================================================================
# MODULO 1: LIQUIDITY STRESS (integra tu sistema existente)
# ============================================================================

class LiquidityStressModule:
    """
    Analiza estres de liquidez usando proxies de mercado via yfinance.

    Proxies:
    - TLT: Long-duration treasuries (caidas = rates stress)
    - HYG: High-yield bonds (caidas = credit stress)
    - LQD: Investment-grade bonds (spread HYG-LQD = credit friction)
    - SHY: Short-duration treasuries (TLT/SHY ratio = yield curve proxy)
    - VIX: Volatilidad implícita (spikes = liquidity withdrawal)
    - GLD: Oro (subidas fuertes = flight to safety)
    """

    PROXIES = ['TLT', 'HYG', 'LQD', 'SHY', '^VIX', 'GLD']

    def __init__(self, data_dir='.'):
        self.data_dir = Path(data_dir)
        self.score = 0
        self.signals = []
        self.alerts = []

    def calculate(self, liquidity_df=None, fred_data=None):  # noqa: ARG002
        """
        Calcula score de estres de liquidez 0-100 usando proxies de mercado.
        liquidity_df/fred_data kept for API compat but proxies are fetched live.
        """
        self.score = 0
        self.signals = []
        self.alerts = []

        proxy_data = self._fetch_liquidity_proxies()
        if not proxy_data:
            self.alerts.append("WARNING: No se pudieron obtener datos de liquidez")
            return 50

        # --- Signal 1: Credit Spread (HYG vs LQD performance divergence) ---
        if 'HYG' in proxy_data and 'LQD' in proxy_data:
            hyg = proxy_data['HYG']['Close']
            lqd = proxy_data['LQD']['Close']
            if len(hyg) >= 20 and len(lqd) >= 20:
                hyg_ret_20d = ((hyg.iloc[-1] / hyg.iloc[-20]) - 1) * 100
                lqd_ret_20d = ((lqd.iloc[-1] / lqd.iloc[-20]) - 1) * 100
                spread_chg = hyg_ret_20d - lqd_ret_20d  # Negative = HY underperforming = stress

                if spread_chg < -3:
                    self.score += 25
                    self.signals.append(f"CRITICO: Credit spread ampliandose (HYG-LQD divergencia {spread_chg:.1f}% en 20d)")
                    self.alerts.append("ALERTA: Spreads de credito ampliandose - estres de liquidez")
                elif spread_chg < -1.5:
                    self.score += 15
                    self.signals.append(f"ELEVADO: Credit spread creciendo (HYG-LQD {spread_chg:.1f}% en 20d)")
                elif spread_chg < -0.5:
                    self.score += 8
                    self.signals.append(f"MODERADO: Credit spread ligero (HYG-LQD {spread_chg:.1f}% en 20d)")
                else:
                    self.signals.append(f"OK: Credit spreads estables (HYG-LQD {spread_chg:.1f}% en 20d)")

        # --- Signal 2: Treasury Stress (TLT moves) ---
        if 'TLT' in proxy_data:
            tlt = proxy_data['TLT']['Close']
            if len(tlt) >= 20:
                tlt_ret_5d = ((tlt.iloc[-1] / tlt.iloc[-5]) - 1) * 100
                tlt_vol = tlt.pct_change().tail(20).std() * (252 ** 0.5) * 100

                # Sharp TLT moves in either direction = rate stress
                if abs(tlt_ret_5d) > 3:
                    self.score += 20
                    self.signals.append(f"CRITICO: TLT movimiento brusco {tlt_ret_5d:+.1f}% en 5d (vol anualizada {tlt_vol:.0f}%)")
                    self.alerts.append("ALERTA: Volatilidad extrema en bonos del tesoro")
                elif abs(tlt_ret_5d) > 1.5:
                    self.score += 10
                    self.signals.append(f"ELEVADO: TLT {tlt_ret_5d:+.1f}% en 5d (vol {tlt_vol:.0f}%)")
                elif tlt_vol > 20:
                    self.score += 8
                    self.signals.append(f"ATENCION: Vol bonos elevada ({tlt_vol:.0f}% anualizada)")
                else:
                    self.signals.append(f"OK: Treasuries estables (TLT {tlt_ret_5d:+.1f}% 5d, vol {tlt_vol:.0f}%)")

        # --- Signal 3: Yield Curve Proxy (TLT vs SHY) ---
        if 'TLT' in proxy_data and 'SHY' in proxy_data:
            tlt = proxy_data['TLT']['Close']
            shy = proxy_data['SHY']['Close']
            if len(tlt) >= 60 and len(shy) >= 60:
                # TLT/SHY ratio: lower = flatter/inverted curve
                ratio_now = tlt.iloc[-1] / shy.iloc[-1]
                ratio_60d = tlt.iloc[-60] / shy.iloc[-60]
                ratio_chg = ((ratio_now / ratio_60d) - 1) * 100

                if ratio_chg < -5:
                    self.score += 15
                    self.signals.append(f"CRITICO: Curva aplanandose rapido (TLT/SHY {ratio_chg:+.1f}% en 60d)")
                elif ratio_chg < -2:
                    self.score += 8
                    self.signals.append(f"ATENCION: Curva aplanandose (TLT/SHY {ratio_chg:+.1f}% en 60d)")
                else:
                    self.signals.append(f"OK: Curva rendimientos estable (TLT/SHY {ratio_chg:+.1f}% en 60d)")

        # --- Signal 4: VIX (implied vol = liquidity withdrawal proxy) ---
        if '^VIX' in proxy_data:
            vix_df = proxy_data['^VIX']
            vix_close = vix_df['Close']
            if len(vix_close) >= 5:
                current_vix = vix_close.iloc[-1]
                vix_5d_chg = ((current_vix / vix_close.iloc[-5]) - 1) * 100

                if current_vix > 30 or vix_5d_chg > 40:
                    self.score += 20
                    self.signals.append(f"CRITICO: VIX={current_vix:.1f} ({vix_5d_chg:+.0f}% 5d) - liquidez retirandose")
                    self.alerts.append(f"ALERTA: VIX en {current_vix:.0f} - mercado retirando liquidez")
                elif current_vix > 22 or vix_5d_chg > 20:
                    self.score += 12
                    self.signals.append(f"ELEVADO: VIX={current_vix:.1f} ({vix_5d_chg:+.0f}% 5d)")
                elif current_vix < 13:
                    self.score += 5
                    self.signals.append(f"COMPLACENCIA: VIX={current_vix:.1f} - baja vol puede revertir")
                else:
                    self.signals.append(f"OK: VIX={current_vix:.1f} en rango normal")

        # --- Signal 5: Gold Flight-to-Safety ---
        if 'GLD' in proxy_data:
            gld = proxy_data['GLD']['Close']
            if len(gld) >= 20:
                gld_ret_5d = ((gld.iloc[-1] / gld.iloc[-5]) - 1) * 100
                gld_ret_20d = ((gld.iloc[-1] / gld.iloc[-20]) - 1) * 100

                if gld_ret_5d > 4:
                    self.score += 10
                    self.signals.append(f"ATENCION: Oro subiendo fuerte +{gld_ret_5d:.1f}% 5d (flight to safety)")
                elif gld_ret_20d > 8:
                    self.score += 8
                    self.signals.append(f"ELEVADO: Oro acumulando +{gld_ret_20d:.1f}% 20d")
                else:
                    self.signals.append(f"OK: Oro {gld_ret_5d:+.1f}% 5d, {gld_ret_20d:+.1f}% 20d")

        return min(self.score, 100)

    def _fetch_liquidity_proxies(self):
        """Descarga datos de proxies de liquidez via yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            return {}

        data = {}
        for ticker in self.PROXIES:
            try:
                df = yf.download(ticker, period='6mo', progress=False)
                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    data[ticker] = df
            except Exception:
                continue
        return data


# ============================================================================
# MODULO 2: MARKET TECHNICALS
# ============================================================================

class MarketTechnicalsModule:
    """
    Analiza indicadores tecnicos de los principales activos.
    Usa yfinance para datos de mercado.
    """

    # Activos a monitorear
    ASSETS = {
        'SPY':  'S&P 500',
        'QQQ':  'Nasdaq 100',
        'IWM':  'Russell 2000',
        'GLD':  'Gold ETF',
        'SLV':  'Silver ETF',
        'XLE':  'Energy',
        'XLF':  'Financials',
        'TLT':  'Long Treasuries',
        'HYG':  'High Yield Bonds',
        'DXY':  'Dollar Index',  # Puede necesitar ticker alternativo
    }

    def __init__(self):
        self.score = 0
        self.signals = []
        self.alerts = []
        self.asset_scores = {}

    def calculate(self, market_data=None):
        """
        Calcula score tecnico 0-100.
        market_data: dict de DataFrames {ticker: df_ohlcv} o None para descargar.
        """
        self.score = 0
        self.signals = []
        self.alerts = []

        if market_data is None:
            market_data = self._fetch_market_data()

        if not market_data:
            self.alerts.append("WARNING: No se pudieron obtener datos de mercado")
            return 50

        sub_scores = []

        for ticker, name in self.ASSETS.items():
            if ticker not in market_data or market_data[ticker] is None:
                continue

            df = market_data[ticker]
            if len(df) < 50:
                continue

            asset_risk = self._analyze_asset(df, ticker, name)
            self.asset_scores[ticker] = asset_risk
            sub_scores.append(asset_risk)

        # --- Breadth Analysis ---
        breadth_score = self._analyze_breadth(market_data)
        sub_scores.append(breadth_score)

        # --- Correlation spike (todo cae junto = peligro) ---
        corr_score = self._analyze_correlation(market_data)
        sub_scores.append(corr_score)

        if sub_scores:
            self.score = int(np.mean(sub_scores))

        return min(self.score, 100)

    def _analyze_asset(self, df, ticker, name):
        """Analiza un activo individual. Retorna risk score 0-100."""
        risk = 0
        close = df['Close']

        # RSI(14) - Sobrecompra/Sobreventa
        rsi = self._calc_rsi(close, 14)
        if rsi is not None:
            if rsi > 80:
                risk += 30
                self.signals.append(f"{name}: RSI={rsi:.0f} EXTREMO SOBRECOMPRA")
                self.alerts.append(f"ALERTA: {name} RSI > 80 (sobrecompra extrema)")
            elif rsi > 70:
                risk += 15
                self.signals.append(f"{name}: RSI={rsi:.0f} sobrecompra")
            elif rsi < 25:
                risk -= 10  # Oversold = potencial rebote
                self.signals.append(f"{name}: RSI={rsi:.0f} sobreventa extrema")

        # Distancia de MA200
        if len(close) >= 200:
            ma200 = close.rolling(200).mean().iloc[-1]
            dist_ma200 = ((close.iloc[-1] / ma200) - 1) * 100
            if dist_ma200 > 40:
                risk += 25
                self.signals.append(f"{name}: {dist_ma200:.0f}% sobre MA200 (PARABOLICO)")
            elif dist_ma200 > 25:
                risk += 15
                self.signals.append(f"{name}: {dist_ma200:.0f}% sobre MA200")
            elif dist_ma200 < -20:
                risk -= 5
                self.signals.append(f"{name}: {dist_ma200:.0f}% bajo MA200 (deprimido)")

        # Bollinger Bands - Precio fuera de bandas
        if len(close) >= 20:
            ma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            upper_bb = (ma20 + 2.5 * std20).iloc[-1]
            if close.iloc[-1] > upper_bb:
                risk += 15
                self.signals.append(f"{name}: Sobre Bollinger Band superior (2.5 std)")

        # Drawdown reciente (caida desde maximo de 52 semanas)
        if len(close) >= 252:
            high_52w = close.tail(252).max()
            drawdown = ((close.iloc[-1] / high_52w) - 1) * 100
            if drawdown < -20:
                risk += 10
                self.signals.append(f"{name}: Drawdown {drawdown:.0f}% desde 52w high")

        # Velocidad de subida (ritmo parabolico)
        if len(close) >= 60:
            return_60d = ((close.iloc[-1] / close.iloc[-60]) - 1) * 100
            if return_60d > 50:
                risk += 20
                self.signals.append(f"{name}: +{return_60d:.0f}% en 60 dias (PARABOLICO)")
                self.alerts.append(f"ALERTA: {name} rally parabolico (+{return_60d:.0f}% en 60d)")
            elif return_60d > 30:
                risk += 10
                self.signals.append(f"{name}: +{return_60d:.0f}% en 60 dias")

        return max(0, min(risk, 100))

    def _analyze_breadth(self, market_data):
        """
        Analiza amplitud de mercado.
        Si solo suben unos pocos mientras la mayoria cae = peligro.
        """
        risk = 0
        above_ma50 = 0
        total = 0

        for ticker in ['SPY', 'QQQ', 'IWM', 'XLE', 'XLF']:
            if ticker in market_data and market_data[ticker] is not None:
                df = market_data[ticker]
                if len(df) >= 50:
                    close = df['Close']
                    ma50 = close.rolling(50).mean().iloc[-1]
                    total += 1
                    if close.iloc[-1] > ma50:
                        above_ma50 += 1

        if total > 0:
            pct_above = above_ma50 / total
            if pct_above < 0.3:
                risk = 40
                self.signals.append(f"BREADTH: Solo {above_ma50}/{total} sobre MA50 (deterioro)")
            elif pct_above < 0.5:
                risk = 20
                self.signals.append(f"BREADTH: {above_ma50}/{total} sobre MA50")
            else:
                self.signals.append(f"BREADTH: {above_ma50}/{total} sobre MA50 (saludable)")

        return risk

    def _analyze_correlation(self, market_data):
        """
        Si todo cae junto (correlacion alta), el riesgo es elevado.
        """
        returns = {}
        for ticker in ['SPY', 'QQQ', 'GLD', 'SLV', 'XLE', 'TLT']:
            if ticker in market_data and market_data[ticker] is not None:
                df = market_data[ticker]
                if len(df) >= 20:
                    ret = df['Close'].pct_change().tail(20).dropna()
                    if len(ret) > 0:
                        returns[ticker] = ret

        if len(returns) >= 4:
            ret_df = pd.DataFrame(returns)
            corr_matrix = ret_df.corr()
            # Correlacion media (excluyendo diagonal)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            avg_corr = corr_matrix.where(mask).mean().mean()

            if avg_corr > 0.7:
                self.signals.append(f"CORRELACION: {avg_corr:.2f} (todo cae junto = PELIGRO)")
                self.alerts.append("ALERTA: Correlacion extrema entre activos")
                return 40
            elif avg_corr > 0.5:
                self.signals.append(f"CORRELACION: {avg_corr:.2f} (elevada)")
                return 20

        return 0

    def _calc_rsi(self, series, period=14):
        """Calcula RSI."""
        if len(series) < period + 1:
            return None
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def _fetch_market_data(self, period='1y'):
        """Descarga datos de mercado via yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            print("[!] yfinance no instalado. pip install yfinance")
            return {}

        data = {}
        tickers_list = list(self.ASSETS.keys())

        # Reemplazar DXY por UUP (Dollar ETF) ya que DXY no esta en yfinance
        if 'DXY' in tickers_list:
            tickers_list[tickers_list.index('DXY')] = 'UUP'

        for ticker in tickers_list:
            try:
                df = yf.download(ticker, period=period, progress=False)
                if df is not None and not df.empty:
                    # Flatten MultiIndex si existe
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    data[ticker if ticker != 'UUP' else 'DXY'] = df
            except Exception as e:
                print(f"[!] Error descargando {ticker}: {e}")

        return data


# ============================================================================
# MODULO 3: VALUATION EXCESS
# ============================================================================

class ValuationExcessModule:
    """
    Analiza si las valoraciones estan en territorio de burbuja.
    """

    def __init__(self):
        self.score = 0
        self.signals = []
        self.alerts = []

    def calculate(self, pe_forward=None, cape_ratio=None, buffett_indicator=None):
        """
        Calcula score de exceso de valoracion 0-100.

        Parametros (se pueden pasar manualmente o calcular):
        - pe_forward: Forward P/E del S&P 500
        - cape_ratio: Shiller CAPE ratio
        - buffett_indicator: Market Cap / GDP
        """
        self.score = 0
        self.signals = []
        self.alerts = []

        # --- Forward P/E ---
        if pe_forward is None:
            pe_forward = self._get_current_pe()

        if pe_forward:
            if pe_forward > 25:
                self.score += 35
                self.signals.append(f"CRITICO: Forward P/E = {pe_forward:.1f} (burbuja)")
                self.alerts.append(f"ALERTA: Forward P/E {pe_forward:.1f} en territorio de burbuja historica")
            elif pe_forward > 22:
                self.score += 25
                self.signals.append(f"ELEVADO: Forward P/E = {pe_forward:.1f} (media 30y = 17)")
            elif pe_forward > 19:
                self.score += 15
                self.signals.append(f"ALTO: Forward P/E = {pe_forward:.1f}")
            else:
                self.signals.append(f"NORMAL: Forward P/E = {pe_forward:.1f}")

        # --- CAPE Ratio ---
        if cape_ratio:
            if cape_ratio > 38:
                self.score += 30
                self.signals.append(f"CRITICO: CAPE = {cape_ratio:.1f} (niveles de burbuja dot-com y 2021)")
            elif cape_ratio > 30:
                self.score += 20
                self.signals.append(f"ELEVADO: CAPE = {cape_ratio:.1f}")
            elif cape_ratio > 25:
                self.score += 10

        # --- Buffett Indicator ---
        if buffett_indicator:
            if buffett_indicator > 200:
                self.score += 35
                self.signals.append(f"EXTREMO: Buffett Indicator = {buffett_indicator:.0f}%")
            elif buffett_indicator > 170:
                self.score += 20
                self.signals.append(f"ELEVADO: Buffett Indicator = {buffett_indicator:.0f}%")

        return min(self.score, 100)

    def _get_current_pe(self):
        """Intenta obtener P/E actual. Fallback a valor manual."""
        # En produccion, scrape de multpl.com o similar
        # Por ahora retorna el dato conocido de feb 2026
        return 22.2  # FactSet data feb 2026


# ============================================================================
# MODULO 4: VOLATILITY REGIME
# ============================================================================

class VolatilityRegimeModule:
    """
    Analiza el regimen de volatilidad actual usando multiples indicadores:

    1. VIX (nivel, spike, term structure)
    2. MOVE Index (vol de bonos = estres sistemico)
    3. Realized vs Implied vol (mercado subestimando riesgo?)
    4. Correlacion cross-asset (crisis de liquidez cuando todo cae)
    5. VVIX / Vol-of-Vol (incertidumbre sobre incertidumbre)
    6. Skew proxy (tail risk via put vs call vol)
    7. Gamma exposure proxy (vol intraday = market maker hedging)
    8. Put/Call volume proxy (sentimiento opciones)
    """

    # Tickers para analisis multi-dimensional de volatilidad
    VOL_TICKERS = ['^VIX', '^MOVE', '^SKEW', '^VIX3M',
                   'SPY', 'TLT', 'GLD', 'HYG', 'UVXY']

    def __init__(self):
        self.score = 0
        self.signals = []
        self.alerts = []

    def calculate(self, market_data=None):
        self.score = 0
        self.signals = []
        self.alerts = []

        vol_data = self._fetch_vol_data(market_data)

        # ===== 1. VIX LEVEL & SPIKE =====
        self._analyze_vix(vol_data)

        # ===== 2. MOVE INDEX (bond volatility) =====
        self._analyze_move(vol_data)

        # ===== 3. REALIZED VS IMPLIED VOL =====
        self._analyze_realized_vs_implied(vol_data)

        # ===== 4. CROSS-ASSET CORRELATION =====
        self._analyze_cross_asset_correlation(vol_data)

        # ===== 5. VVIX / VOL-OF-VOL =====
        self._analyze_vol_of_vol(vol_data)

        # ===== 6. SKEW (tail risk) =====
        self._analyze_skew(vol_data)

        # ===== 7. GAMMA EXPOSURE PROXY =====
        self._analyze_gamma_proxy(vol_data)

        # ===== 8. PUT/CALL PROXY =====
        self._analyze_put_call_proxy(vol_data)

        return min(self.score, 100)

    def _analyze_vix(self, vol_data):
        """VIX nivel, spike y term structure."""
        vix_df = vol_data.get('^VIX')
        if vix_df is None or vix_df.empty:
            return

        close = vix_df['Close'] if 'Close' in vix_df.columns else vix_df
        if len(close) < 5:
            return

        current_vix = float(close.iloc[-1])

        # VIX Level
        if current_vix > 35:
            self.score += 30
            self.signals.append(f"PANICO: VIX = {current_vix:.1f} (fear territory)")
            self.alerts.append(f"ALERTA ROJA: VIX > 35 indica panico de mercado")
        elif current_vix > 25:
            self.score += 18
            self.signals.append(f"ELEVADO: VIX = {current_vix:.1f}")
        elif current_vix > 20:
            self.score += 10
            self.signals.append(f"ALTO: VIX = {current_vix:.1f}")
        elif current_vix > 16:
            self.score += 5
            self.signals.append(f"MODERADO: VIX = {current_vix:.1f} (ligeramente elevado)")
        elif current_vix >= 12:
            self.score += 2
            self.signals.append(f"NORMAL: VIX = {current_vix:.1f} (rango bajo-normal)")
        else:
            self.score += 6
            self.signals.append(f"COMPLACENCIA: VIX = {current_vix:.1f} (extremo bajo = peligro)")

        # VIX Spike (cambio rapido)
        vix_5d_change = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100
        if vix_5d_change > 50:
            self.score += 20
            self.signals.append(f"SPIKE: VIX subio {vix_5d_change:.0f}% en 5 dias")
            self.alerts.append("ALERTA: Spike de VIX indica shock de mercado")
        elif vix_5d_change > 30:
            self.score += 10
            self.signals.append(f"SUBIDA: VIX +{vix_5d_change:.0f}% en 5 dias")
        elif vix_5d_change > 15:
            self.score += 5
            self.signals.append(f"INCREMENTO: VIX +{vix_5d_change:.0f}% en 5 dias")
        elif vix_5d_change < -20:
            self.signals.append(f"VIX CAYENDO: {vix_5d_change:.0f}% en 5 dias (risk-on)")

        # VIX Term Structure: VIX vs VIX3M
        vix3m_df = vol_data.get('^VIX3M')
        if vix3m_df is not None and not vix3m_df.empty:
            vix3m_close = vix3m_df['Close'] if 'Close' in vix3m_df.columns else vix3m_df
            if len(vix3m_close) > 0:
                current_vix3m = float(vix3m_close.iloc[-1])
                if current_vix3m > 0:
                    term_ratio = current_vix / current_vix3m
                    if term_ratio > 1.15:
                        self.score += 10
                        self.signals.append(f"BACKWARDATION SEVERA: VIX/VIX3M = {term_ratio:.2f} (panico a corto plazo)")
                        self.alerts.append("Term structure en backwardation severa - miedo extremo a corto plazo")
                    elif term_ratio > 1.0:
                        self.score += 5
                        self.signals.append(f"BACKWARDATION: VIX/VIX3M = {term_ratio:.2f} (estres corto plazo)")
                    elif term_ratio < 0.8:
                        self.signals.append(f"CONTANGO FUERTE: VIX/VIX3M = {term_ratio:.2f} (mercado complaciente)")
                        self.score += 3  # Complacencia = riesgo latente
                    else:
                        self.signals.append(f"TERM STRUCTURE: VIX/VIX3M = {term_ratio:.2f} (contango normal)")
        else:
            # Fallback: VIX vs 20d average
            if len(close) >= 20:
                vix_20d_avg = float(close.tail(20).mean())
                if current_vix > vix_20d_avg * 1.3:
                    self.score += 8
                    self.signals.append(f"TERM PROXY: VIX spot >> media 20d ({current_vix:.1f} vs {vix_20d_avg:.1f})")
                elif current_vix > vix_20d_avg * 1.1:
                    self.score += 3
                    self.signals.append(f"TERM PROXY: VIX spot > media 20d ({current_vix:.1f} vs {vix_20d_avg:.1f})")

    def _analyze_move(self, vol_data):
        """MOVE Index = volatilidad de bonos del Tesoro. Precede crashes equity."""
        move_df = vol_data.get('^MOVE')
        if move_df is None or move_df.empty:
            return

        close = move_df['Close'] if 'Close' in move_df.columns else move_df
        if len(close) < 5:
            return

        current_move = float(close.iloc[-1])

        # MOVE thresholds: <100 normal, 100-120 elevated, 120-150 high, >150 extreme
        if current_move > 150:
            self.score += 12
            self.signals.append(f"CRITICO: MOVE Index = {current_move:.0f} (estres extremo en bonos)")
            self.alerts.append(f"ALERTA: MOVE Index {current_move:.0f} - volatilidad de bonos en niveles de crisis")
        elif current_move > 120:
            self.score += 8
            self.signals.append(f"ELEVADO: MOVE Index = {current_move:.0f} (vol bonos alta)")
        elif current_move > 100:
            self.score += 4
            self.signals.append(f"MODERADO: MOVE Index = {current_move:.0f} (vol bonos por encima de normal)")
        else:
            self.signals.append(f"OK: MOVE Index = {current_move:.0f} (vol bonos en rango normal)")

        # MOVE spike
        if len(close) >= 5:
            move_5d_chg = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100
            if move_5d_chg > 30:
                self.score += 8
                self.signals.append(f"MOVE SPIKE: +{move_5d_chg:.0f}% en 5d - estres de rates acelerandose")
            elif move_5d_chg > 15:
                self.score += 4
                self.signals.append(f"MOVE SUBIENDO: +{move_5d_chg:.0f}% en 5d")

    def _analyze_realized_vs_implied(self, vol_data):
        """Compara vol realizada del SPY vs VIX (implied). Si realized > implied = peligro."""
        spy_df = vol_data.get('SPY')
        vix_df = vol_data.get('^VIX')
        if spy_df is None or vix_df is None:
            return

        spy_close = spy_df['Close'] if 'Close' in spy_df.columns else spy_df
        vix_close = vix_df['Close'] if 'Close' in vix_df.columns else vix_df

        if len(spy_close) < 21 or len(vix_close) < 1:
            return

        # Realized vol (20d annualized)
        returns = spy_close.pct_change().dropna()
        realized_20d = float(returns.tail(20).std() * (252 ** 0.5) * 100)
        current_vix = float(vix_close.iloc[-1])

        vol_gap = realized_20d - current_vix

        if vol_gap > 5:
            self.score += 8
            self.signals.append(f"PELIGRO: Vol realizada ({realized_20d:.1f}%) >> VIX ({current_vix:.1f}%) - mercado subestima riesgo")
            self.alerts.append("Vol realizada supera VIX significativamente - riesgo infravalorado")
        elif vol_gap > 2:
            self.score += 4
            self.signals.append(f"ATENCION: Vol realizada ({realized_20d:.1f}%) > VIX ({current_vix:.1f}%) - gap de {vol_gap:.1f}pp")
        elif vol_gap < -10:
            self.signals.append(f"VIX PREMIUM: VIX ({current_vix:.1f}%) >> vol realizada ({realized_20d:.1f}%) - mercado miedoso")
        else:
            self.signals.append(f"VOL BALANCE: Realizada={realized_20d:.1f}% vs Implicita (VIX)={current_vix:.1f}%")

        # 5d realized vol spike
        if len(returns) >= 5:
            realized_5d = float(returns.tail(5).std() * (252 ** 0.5) * 100)
            if realized_5d > realized_20d * 1.5 and realized_5d > 20:
                self.score += 5
                self.signals.append(f"VOL SPIKE RECIENTE: Vol 5d={realized_5d:.0f}% vs 20d={realized_20d:.0f}% - aceleracion")

    def _analyze_cross_asset_correlation(self, vol_data):
        """Cuando SPY, TLT, GLD, HYG caen juntos = crisis de liquidez sistémica."""
        assets = {}
        for ticker in ['SPY', 'TLT', 'GLD', 'HYG']:
            df = vol_data.get(ticker)
            if df is not None and not df.empty:
                close = df['Close'] if 'Close' in df.columns else df
                if len(close) >= 5:
                    ret_5d = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100
                    assets[ticker] = float(ret_5d)

        if len(assets) < 3:
            return

        # Count how many are negative
        negative = sum(1 for v in assets.values() if v < -1)
        all_returns = list(assets.values())
        avg_return = sum(all_returns) / len(all_returns)

        if negative >= 4:
            self.score += 12
            desc = ", ".join(f"{k}={v:+.1f}%" for k, v in assets.items())
            self.signals.append(f"CORRELACION PELIGRO: Todos los activos cayendo juntos ({desc}) - crisis de liquidez")
            self.alerts.append("ALERTA: Correlacion cross-asset extrema - todo cayendo = liquidity crisis")
        elif negative >= 3:
            self.score += 6
            desc = ", ".join(f"{k}={v:+.1f}%" for k, v in assets.items())
            self.signals.append(f"CORRELACION ELEVADA: {negative}/4 activos negativos 5d ({desc})")
        elif negative == 0 and avg_return > 1:
            self.signals.append(f"DECORRELACION OK: Activos diversificados normalmente ({avg_return:+.1f}% avg)")

        # Intraday-like: if both SPY and TLT down = nowhere to hide
        if 'SPY' in assets and 'TLT' in assets:
            if assets['SPY'] < -2 and assets['TLT'] < -1:
                self.score += 5
                self.signals.append(f"NOWHERE TO HIDE: SPY y TLT cayendo (equity {assets['SPY']:+.1f}%, bonds {assets['TLT']:+.1f}%)")

    def _analyze_vol_of_vol(self, vol_data):
        """VVIX proxy: volatilidad del VIX = incertidumbre sobre la incertidumbre."""
        vix_df = vol_data.get('^VIX')
        if vix_df is None or vix_df.empty:
            return

        close = vix_df['Close'] if 'Close' in vix_df.columns else vix_df
        if len(close) < 21:
            return

        # Calculate VIX volatility (vol of vol)
        vix_returns = close.pct_change().dropna()
        vvix_proxy = float(vix_returns.tail(20).std() * (252 ** 0.5) * 100)

        if vvix_proxy > 120:
            self.score += 8
            self.signals.append(f"VVIX EXTREMO: Vol-of-Vol = {vvix_proxy:.0f}% (incertidumbre maxima)")
        elif vvix_proxy > 90:
            self.score += 5
            self.signals.append(f"VVIX ELEVADO: Vol-of-Vol = {vvix_proxy:.0f}% (mercado inestable)")
        elif vvix_proxy > 60:
            self.score += 2
            self.signals.append(f"VVIX MODERADO: Vol-of-Vol = {vvix_proxy:.0f}%")
        else:
            self.signals.append(f"VVIX OK: Vol-of-Vol = {vvix_proxy:.0f}% (estable)")

    def _analyze_skew(self, vol_data):
        """CBOE SKEW Index = tail risk. >140 = alto riesgo de cola."""
        skew_df = vol_data.get('^SKEW')
        if skew_df is None or skew_df.empty:
            # Proxy: usar amplitud de rango SPY como proxy de skew
            self._analyze_skew_proxy(vol_data)
            return

        close = skew_df['Close'] if 'Close' in skew_df.columns else skew_df
        if len(close) < 1:
            return

        current_skew = float(close.iloc[-1])

        if current_skew > 150:
            self.score += 8
            self.signals.append(f"SKEW EXTREMO: {current_skew:.0f} - mercado priceando tail risk elevado")
            self.alerts.append(f"SKEW Index {current_skew:.0f} indica cola izquierda gorda")
        elif current_skew > 140:
            self.score += 5
            self.signals.append(f"SKEW ALTO: {current_skew:.0f} - demand de puts OTM elevada")
        elif current_skew > 130:
            self.score += 2
            self.signals.append(f"SKEW MODERADO: {current_skew:.0f} (normal-alto)")
        elif current_skew < 110:
            self.signals.append(f"SKEW BAJO: {current_skew:.0f} - poca demanda de proteccion (complacencia)")
            self.score += 3
        else:
            self.signals.append(f"SKEW OK: {current_skew:.0f} (rango normal)")

    def _analyze_skew_proxy(self, vol_data):
        """Proxy de skew usando la asimetria de retornos de SPY."""
        spy_df = vol_data.get('SPY')
        if spy_df is None or spy_df.empty:
            return

        close = spy_df['Close'] if 'Close' in spy_df.columns else spy_df
        if len(close) < 21:
            return

        returns = close.pct_change().dropna().tail(20)
        if len(returns) < 10:
            return

        # Skewness of returns: negative = left tail fatter = more crash risk
        skewness = float(returns.skew())
        if skewness < -1.0:
            self.score += 5
            self.signals.append(f"SKEW PROXY: Retornos muy negativamente sesgados (skew={skewness:.2f}) - tail risk")
        elif skewness < -0.5:
            self.score += 3
            self.signals.append(f"SKEW PROXY: Retornos sesgados negativamente (skew={skewness:.2f})")
        elif skewness > 0.5:
            self.signals.append(f"SKEW PROXY: Retornos sesgados positivamente (skew={skewness:.2f}) - risk-on")

    def _analyze_gamma_proxy(self, vol_data):
        """
        Gamma exposure proxy: vol intraday alta vs rango normal indica
        market makers rehedging agresivamente (gamma negativo).
        Usa High-Low range de SPY como proxy.
        """
        spy_df = vol_data.get('SPY')
        if spy_df is None or spy_df.empty:
            return

        if 'High' not in spy_df.columns or 'Low' not in spy_df.columns:
            return

        if len(spy_df) < 21:
            return

        # Intraday range as % of close
        spy_df = spy_df.copy()
        spy_df['range_pct'] = (spy_df['High'] - spy_df['Low']) / spy_df['Close'] * 100
        recent_range = float(spy_df['range_pct'].iloc[-1])
        avg_range_20d = float(spy_df['range_pct'].tail(20).mean())

        if avg_range_20d > 0:
            range_ratio = recent_range / avg_range_20d

            if range_ratio > 2.5 and recent_range > 2:
                self.score += 8
                self.signals.append(f"GAMMA NEGATIVO: Rango intraday {recent_range:.1f}% = {range_ratio:.1f}x vs media - MMs rehedging")
                self.alerts.append("Gamma exposure negativo - amplificacion de movimientos por market makers")
            elif range_ratio > 1.8 and recent_range > 1.5:
                self.score += 4
                self.signals.append(f"GAMMA ESTRESADO: Rango intraday {recent_range:.1f}% ({range_ratio:.1f}x vs media)")
            elif range_ratio > 1.3:
                self.score += 2
                self.signals.append(f"GAMMA MODERADO: Rango intraday elevado {recent_range:.1f}% ({range_ratio:.1f}x)")
            else:
                self.signals.append(f"GAMMA OK: Rango intraday {recent_range:.1f}% (normal)")

        # Multi-day elevated ranges = persistent gamma stress
        if len(spy_df) >= 5 and avg_range_20d > 0:
            last_5_avg = float(spy_df['range_pct'].tail(5).mean())
            if last_5_avg > avg_range_20d * 1.5 and last_5_avg > 1.5:
                self.score += 4
                self.signals.append(f"GAMMA PERSISTENTE: Rango 5d avg={last_5_avg:.1f}% vs 20d avg={avg_range_20d:.1f}% - estres sostenido")

    def _analyze_put_call_proxy(self, vol_data):
        """
        Put/Call proxy usando volumen de UVXY (leveraged VIX ETF).
        Alto volumen UVXY = institucionales comprando proteccion.
        """
        uvxy_df = vol_data.get('UVXY')
        if uvxy_df is None or uvxy_df.empty:
            return

        if 'Volume' not in uvxy_df.columns:
            return

        vol = uvxy_df['Volume']
        if len(vol) < 21:
            return

        current_vol = float(vol.iloc[-1])
        avg_vol_20d = float(vol.tail(20).mean())

        if avg_vol_20d > 0:
            vol_ratio = current_vol / avg_vol_20d

            if vol_ratio > 3:
                self.score += 6
                self.signals.append(f"PROTECCION EXTREMA: Vol UVXY {vol_ratio:.1f}x vs media - compra masiva de proteccion")
            elif vol_ratio > 2:
                self.score += 3
                self.signals.append(f"PROTECCION ALTA: Vol UVXY {vol_ratio:.1f}x vs media - demand de hedging")
            elif vol_ratio > 1.5:
                self.score += 1
                self.signals.append(f"PROTECCION MODERADA: Vol UVXY {vol_ratio:.1f}x vs media")
            elif vol_ratio < 0.5:
                self.score += 2  # Complacencia
                self.signals.append(f"SIN PROTECCION: Vol UVXY bajo ({vol_ratio:.1f}x) - nadie hedgeando = complacencia")

    def _fetch_vol_data(self, market_data=None):
        """Descarga todos los datos de volatilidad necesarios."""
        try:
            import yfinance as yf
        except ImportError:
            return {}

        data = {}

        # Use pre-fetched data if available
        if market_data:
            for key in self.VOL_TICKERS:
                if key in market_data:
                    data[key] = market_data[key]

        # Fetch missing tickers
        missing = [t for t in self.VOL_TICKERS if t not in data]
        if missing:
            for ticker in missing:
                try:
                    df = yf.download(ticker, period='6mo', progress=False)
                    if df is not None and not df.empty:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        data[ticker] = df
                except Exception:
                    continue

        return data


# ============================================================================
# MODULO 5: POSITIONING & CROWDING
# ============================================================================

class PositioningCrowdingModule:
    """
    Detecta posicionamiento extremo y trades "crowded".
    """

    def __init__(self):
        self.score = 0
        self.signals = []
        self.alerts = []

    def calculate(self, put_call_ratio=None, margin_debt_yoy=None,
                  etf_inflows=None, reddit_sentiment=None,
                  cme_margin_changes=None):
        """
        Parametros (muchos son manuales o via web scraping):
        - put_call_ratio: CBOE Put/Call ratio
        - margin_debt_yoy: Margin debt YoY change %
        - etf_inflows: dict con flujos recientes a ETFs clave
        - reddit_sentiment: score de sentimiento retail
        - cme_margin_changes: list de cambios de margenes recientes
        """
        self.score = 0
        self.signals = []
        self.alerts = []

        # --- Put/Call Ratio ---
        if put_call_ratio:
            if put_call_ratio < 0.5:
                self.score += 30
                self.signals.append(f"EXTREMO: Put/Call = {put_call_ratio:.2f} (complacencia)")
                self.alerts.append("ALERTA: Put/Call ratio indica complacencia extrema")
            elif put_call_ratio < 0.7:
                self.score += 15
                self.signals.append(f"BAJO: Put/Call = {put_call_ratio:.2f}")
            elif put_call_ratio > 1.2:
                self.score -= 10  # Alto P/C = miedo = contrarian bullish
                self.signals.append(f"MIEDO: Put/Call = {put_call_ratio:.2f} (contrarian bullish)")

        # --- Margin Debt ---
        if margin_debt_yoy:
            if margin_debt_yoy > 30:
                self.score += 25
                self.signals.append(f"EXTREMO: Margin debt +{margin_debt_yoy:.0f}% YoY")
                self.alerts.append("ALERTA: Apalancamiento retail en maximos")
            elif margin_debt_yoy > 15:
                self.score += 15
                self.signals.append(f"ELEVADO: Margin debt +{margin_debt_yoy:.0f}% YoY")

        # --- CME Margin Hikes (SENAL CRITICA) ---
        if cme_margin_changes:
            recent_hikes = [m for m in cme_margin_changes
                           if m.get('direction') == 'up'
                           and m.get('days_ago', 999) < 14]
            if len(recent_hikes) >= 2:
                self.score += 35
                self.signals.append(f"CRITICO: {len(recent_hikes)} subidas de margenes CME en 14 dias")
                self.alerts.append("ALERTA MAXIMA: Multiples subidas de margenes = 1980/2011 pattern")
            elif len(recent_hikes) >= 1:
                self.score += 20
                self.signals.append(f"ADVERTENCIA: Subida de margenes CME reciente")

        # --- ETF Volume Anomalies ---
        if etf_inflows:
            for etf, data in etf_inflows.items():
                if data.get('volume_vs_avg', 1) > 5:
                    self.score += 15
                    self.signals.append(
                        f"ANOMALIA: {etf} volumen {data['volume_vs_avg']:.0f}x vs media")

        # --- Reddit/Retail Mania Indicator ---
        if reddit_sentiment:
            if reddit_sentiment > 80:
                self.score += 20
                self.signals.append(f"MANIA: Sentimiento retail = {reddit_sentiment}/100")

        return max(0, min(self.score, 100))


# ============================================================================
# MODULO 6: MACRO DETERIORATION
# ============================================================================

class MacroDeteriorationModule:
    """
    Indicadores macro de deterioro economico.
    """

    def __init__(self):
        self.score = 0
        self.signals = []
        self.alerts = []

    def calculate(self, fred_data=None):
        self.score = 0
        self.signals = []
        self.alerts = []

        if fred_data is None:
            fred_data = self._fetch_macro_data()

        if not fred_data:
            self.signals.append("Sin datos FRED (API key no configurada o servicio no disponible)")
            self.signals.append("Score por defecto: 50/100 (neutral)")
            return 50

        # --- Yield Curve (10Y - 2Y) ---
        if 'T10Y2Y' in fred_data:
            spread = fred_data['T10Y2Y']
            if spread is not None:
                latest_spread = spread.iloc[-1] if hasattr(spread, 'iloc') else spread
                if latest_spread < -0.5:
                    self.score += 30
                    self.signals.append(f"INVERSION: Yield curve 10Y-2Y = {latest_spread:.2f}%")
                elif latest_spread < 0:
                    self.score += 20
                    self.signals.append(f"INVERTIDA: Yield curve = {latest_spread:.2f}%")
                elif latest_spread > 0 and latest_spread < 0.3:
                    self.score += 15
                    self.signals.append(f"STEEPENING: Curve desinvirtiendose = {latest_spread:.2f}%")
                    # Desinversion historicamente precede recesion

        # --- Credit Spreads (HY - IG) ---
        if 'BAMLH0A0HYM2' in fred_data:
            hy_spread = fred_data['BAMLH0A0HYM2']
            if hy_spread is not None:
                latest_hy = hy_spread.iloc[-1] if hasattr(hy_spread, 'iloc') else hy_spread
                if latest_hy > 6:
                    self.score += 30
                    self.signals.append(f"CRITICO: HY spread = {latest_hy:.2f}% (stress)")
                    self.alerts.append("ALERTA: Credit spreads en zona de estres")
                elif latest_hy > 4.5:
                    self.score += 15
                    self.signals.append(f"ELEVADO: HY spread = {latest_hy:.2f}%")

        # --- Unemployment Rate Trend ---
        if 'UNRATE' in fred_data:
            unemp = fred_data['UNRATE']
            if unemp is not None and hasattr(unemp, 'iloc') and len(unemp) >= 6:
                current = unemp.iloc[-1]
                six_months_ago = unemp.iloc[-6]
                if current - six_months_ago > 0.5:
                    self.score += 25
                    self.signals.append(
                        f"DETERIORO: Unemployment +{current - six_months_ago:.1f}pp en 6m")
                elif current > 4.5:
                    self.score += 10
                    self.signals.append(f"ELEVADO: Unemployment = {current:.1f}%")

        # --- Initial Claims Trend ---
        if 'ICSA' in fred_data:
            claims = fred_data['ICSA']
            if claims is not None and hasattr(claims, 'iloc') and len(claims) >= 4:
                recent_avg = claims.tail(4).mean()
                if recent_avg > 300000:
                    self.score += 15
                    self.signals.append(f"ALTO: Initial claims avg = {recent_avg/1000:.0f}K")

        return min(self.score, 100)

    def _fetch_macro_data(self):
        """Descarga datos macro de FRED."""
        if not FRED_API_KEY:
            return {}

        try:
            from fredapi import Fred
            fred = Fred(api_key=FRED_API_KEY)
            data = {}
            series = {
                'T10Y2Y': '10Y-2Y Spread',
                'BAMLH0A0HYM2': 'HY Spread',
                'UNRATE': 'Unemployment',
                'ICSA': 'Initial Claims',
            }
            for sid, name in series.items():
                try:
                    data[sid] = fred.get_series(sid, observation_start='2024-01-01')
                except:
                    pass
            return data
        except:
            return {}


# ============================================================================
# PATTERN MATCHING ENGINE
# ============================================================================

class CrashPatternMatcher:
    """
    Compara las senales actuales con patrones historicos de crash.
    """

    SIGNAL_MAP = {
        # Commodity signals
        'parabolic_commodity': lambda s: any('PARABOLICO' in sig for sig in s),
        'margin_hike': lambda s: any('margenes CME' in sig for sig in s),
        'margin_hike_cascade': lambda s: any('Multiples subidas' in sig for sig in s),
        'paper_physical_divergence': lambda s: False,  # Requiere datos especificos

        # Equity/valuation signals
        'extreme_pe': lambda s: any('Forward P/E' in sig and ('CRITICO' in sig or 'burbuja' in sig) for sig in s),
        'narrow_breadth': lambda s: any('BREADTH' in sig and 'deterioro' in sig.lower() for sig in s),
        'ipo_mania': lambda s: any('MANIA' in sig and 'IPO' in sig for sig in s),
        'growth_tech_collapse': lambda s: any('Nasdaq' in sig or 'QQQ' in sig for sig in s),
        'portfolio_insurance_unwind': lambda s: any('ANOMALIA' in sig or ('volumen' in sig.lower() and 'extremo' in sig.lower()) for sig in s),

        # Positioning / sentiment
        'extreme_retail_positioning': lambda s: any('MANIA' in sig or 'complacencia' in sig.lower() for sig in s),
        'retail_mania': lambda s: any('MANIA' in sig for sig in s),
        'crowded_trade': lambda s: any('ANOMALIA' in sig for sig in s),
        'leverage_unwind': lambda s: any('Margin debt' in sig and 'EXTREMO' in sig for sig in s),

        # Volatility signals
        'vix_spike': lambda s: any(('SPIKE' in sig or 'PANICO' in sig) and 'VIX' in sig for sig in s),
        'extreme_low_vix': lambda s: any('COMPLACENCIA' in sig and 'VIX' in sig for sig in s),

        # Credit / banking
        'credit_spread_blow': lambda s: any(('Credit spread' in sig or 'HY spread' in sig) and 'CRITICO' in sig for sig in s),
        'bank_stress': lambda s: any(('SRF' in sig or 'bank' in sig.lower() or 'deposito' in sig.lower()) and ('CRITICO' in sig or 'crisis' in sig.lower()) for sig in s),
        'bond_loss_unrealized': lambda s: any('TLT' in sig and 'CRITICO' in sig for sig in s),
        'deposit_flight': lambda s: any('deposito' in sig.lower() or 'deposit' in sig.lower() for sig in s),

        # Rate / monetary
        'fed_tightening': lambda s: any('hawkish' in sig.lower() or 'tightening' in sig.lower() or 'subida' in sig.lower() for sig in s),
        'yield_curve_inversion': lambda s: any('INVERSION' in sig or 'INVERTIDA' in sig or 'aplanandose' in sig.lower() for sig in s),
        'treasury_stress': lambda s: any('TLT' in sig and ('CRITICO' in sig or 'brusco' in sig.lower()) for sig in s),

        # Liquidity
        'liquidity_freeze': lambda s: any(('liquidez' in sig.lower() or 'Liquidity' in sig) and ('CRITICO' in sig or 'retirandose' in sig.lower()) for sig in s),

        # Correlation / systemic
        'correlation_spike': lambda s: any('CORRELACION' in sig and 'PELIGRO' in sig for sig in s),

        # Currency / carry
        'dollar_reversal': lambda s: any('Dollar' in sig or 'DXY' in sig for sig in s),
        'carry_trade_unwind': lambda s: any('carry' in sig.lower() or ('JPY' in sig and ('unwind' in sig.lower() or 'reversal' in sig.lower())) for sig in s),
        'em_stress': lambda s: any('emerg' in sig.lower() or 'EM' in sig for sig in s),

        # Policy
        'policy_shock': lambda s: any('Warsh' in sig.lower() or 'Fed Chair' in sig.lower() or 'policy' in sig.lower() for sig in s),
        'bond_equity_corr_break': lambda s: any('correlacion' in sig.lower() and ('bond' in sig.lower() or 'TLT' in sig) for sig in s),
    }

    def match(self, all_signals):
        """
        Compara senales actuales con patrones historicos.
        Retorna lista de matches con % de coincidencia.
        """
        results = []

        for pattern_id, pattern in CRASH_PATTERNS.items():
            matched = 0
            total = len(pattern['signals'])
            matched_signals = []

            for signal_name in pattern['signals']:
                checker = self.SIGNAL_MAP.get(signal_name, lambda s: False)
                if checker(all_signals):
                    matched += 1
                    matched_signals.append(signal_name)

            pct = (matched / total) * 100 if total > 0 else 0

            if pct >= 30:  # Solo reportar si al menos 30% match
                results.append({
                    'pattern': pattern_id,
                    'description': pattern['description'],
                    'category': pattern.get('category', 'general'),
                    'match_pct': pct,
                    'matched': matched,
                    'total': total,
                    'matched_signals': matched_signals,
                })

        results.sort(key=lambda x: x['match_pct'], reverse=True)
        return results


# ============================================================================
# MOTOR PRINCIPAL - RISK EXPOSURE ENGINE
# ============================================================================

class RiskExposureEngine:
    """
    Motor principal que orquesta todos los modulos y produce el score final.
    """

    def __init__(self, data_dir='.', fred_api_key=None):
        global FRED_API_KEY
        if fred_api_key:
            FRED_API_KEY = fred_api_key

        self.data_dir = data_dir
        self.modules = {
            'liquidity_stress': LiquidityStressModule(data_dir),
            'market_technicals': MarketTechnicalsModule(),
            'valuation_excess': ValuationExcessModule(),
            'volatility_regime': VolatilityRegimeModule(),
            'positioning_crowding': PositioningCrowdingModule(),
            'macro_deterioration': MacroDeteriorationModule(),
        }
        self.pattern_matcher = CrashPatternMatcher()
        self.results = {}

    def run(self, manual_inputs=None):
        """
        Ejecuta el analisis completo.

        manual_inputs: dict con datos manuales para complementar APIs.
        Ejemplo:
        {
            'pe_forward': 22.2,
            'cape_ratio': 38,
            'buffett_indicator': 195,
            'put_call_ratio': 0.6,
            'margin_debt_yoy': 25,
            'cme_margin_changes': [
                {'asset': 'gold', 'direction': 'up', 'from': 6, 'to': 8, 'days_ago': 3},
                {'asset': 'silver', 'direction': 'up', 'from': 11, 'to': 15, 'days_ago': 3},
            ],
            'reddit_sentiment': 85,
        }
        """
        if manual_inputs is None:
            manual_inputs = {}

        print("=" * 70)
        print("  RISK EXPOSURE ENGINE v1.0 - Analisis Diario")
        print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 70)
        print()

        module_scores = {}
        all_signals = []
        all_alerts = []

        # --- 1. Liquidity Stress ---
        print("[1/6] Analizando estres de liquidez...")
        score = self.modules['liquidity_stress'].calculate()
        module_scores['liquidity_stress'] = score
        all_signals.extend(self.modules['liquidity_stress'].signals)
        all_alerts.extend(self.modules['liquidity_stress'].alerts)

        # --- 2. Market Technicals ---
        print("[2/6] Analizando tecnicos de mercado...")
        score = self.modules['market_technicals'].calculate()
        module_scores['market_technicals'] = score
        all_signals.extend(self.modules['market_technicals'].signals)
        all_alerts.extend(self.modules['market_technicals'].alerts)

        # --- 3. Valuation Excess ---
        print("[3/6] Analizando valoraciones...")
        score = self.modules['valuation_excess'].calculate(
            pe_forward=manual_inputs.get('pe_forward'),
            cape_ratio=manual_inputs.get('cape_ratio'),
            buffett_indicator=manual_inputs.get('buffett_indicator'),
        )
        module_scores['valuation_excess'] = score
        all_signals.extend(self.modules['valuation_excess'].signals)
        all_alerts.extend(self.modules['valuation_excess'].alerts)

        # --- 4. Volatility Regime ---
        print("[4/6] Analizando regimen de volatilidad...")
        score = self.modules['volatility_regime'].calculate()
        module_scores['volatility_regime'] = score
        all_signals.extend(self.modules['volatility_regime'].signals)
        all_alerts.extend(self.modules['volatility_regime'].alerts)

        # --- 5. Positioning & Crowding ---
        print("[5/6] Analizando posicionamiento...")
        score = self.modules['positioning_crowding'].calculate(
            put_call_ratio=manual_inputs.get('put_call_ratio'),
            margin_debt_yoy=manual_inputs.get('margin_debt_yoy'),
            cme_margin_changes=manual_inputs.get('cme_margin_changes'),
            reddit_sentiment=manual_inputs.get('reddit_sentiment'),
        )
        module_scores['positioning_crowding'] = score
        all_signals.extend(self.modules['positioning_crowding'].signals)
        all_alerts.extend(self.modules['positioning_crowding'].alerts)

        # --- 6. Macro Deterioration ---
        print("[6/6] Analizando deterioro macro...")
        score = self.modules['macro_deterioration'].calculate()
        module_scores['macro_deterioration'] = score
        all_signals.extend(self.modules['macro_deterioration'].signals)
        all_alerts.extend(self.modules['macro_deterioration'].alerts)

        # --- SCORE FINAL PONDERADO ---
        final_score = 0
        for module_name, score in module_scores.items():
            weight = MODULE_WEIGHTS[module_name]
            final_score += score * (weight / 100)

        final_score = int(min(max(final_score, 0), 100))

        # --- PATTERN MATCHING ---
        print("\nBuscando patrones historicos de crash...")
        pattern_matches = self.pattern_matcher.match(all_signals)

        # Boost score si hay patrones fuertes
        if pattern_matches and pattern_matches[0]['match_pct'] >= 60:
            boost = 10
            final_score = min(final_score + boost, 100)
            all_alerts.append(
                f"PATRON HISTORICO: {pattern_matches[0]['description']} "
                f"({pattern_matches[0]['match_pct']:.0f}% match) - Score boosted +{boost}"
            )

        # --- DETERMINAR REGIMEN ---
        regime = self._determine_regime(final_score)

        # --- ALLOCATION RECOMMENDATION ---
        allocation = self._get_allocation(final_score)

        # --- COMPILAR RESULTADOS ---
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'final_score': final_score,
            'regime': regime,
            'allocation': allocation,
            'module_scores': module_scores,
            'signals': all_signals,
            'alerts': all_alerts,
            'pattern_matches': pattern_matches,
            'asset_scores': self.modules['market_technicals'].asset_scores,
        }

        # Calculate crash probabilities
        self.results['crash_probabilities'] = self.calculate_crash_probabilities()

        # Generate module explanations
        self.results['module_explanations'] = self.get_module_explanations()

        self._print_report()
        return self.results

    def calculate_crash_probabilities(self):
        """
        Calculate probability of market corrections/crashes for next 30 days.
        Based on risk score, module scores, and pattern matching.
        """
        if not self.results:
            return {}

        score = self.results['final_score']
        module_scores = self.results['module_scores']
        pattern_matches = self.results.get('pattern_matches', [])
        alerts = self.results.get('alerts', [])

        # Base probabilities from composite score (calibrated to historical)
        p_5pct = min(max(score * 0.85, 5), 90)
        p_10pct = min(max(score * 0.55, 3), 80)
        p_20pct = min(max(score * 0.30, 1), 60)
        p_rally = max(min((100 - score) * 0.80, 90), 5)

        # Adjust for module concentration (>= 3 modules above 50 = higher risk)
        high_modules = sum(1 for s in module_scores.values() if s > 50)
        if high_modules >= 4:
            p_5pct = min(p_5pct + 15, 95)
            p_10pct = min(p_10pct + 12, 85)
            p_20pct = min(p_20pct + 8, 70)
            p_rally = max(p_rally - 15, 5)
        elif high_modules >= 3:
            p_5pct = min(p_5pct + 8, 92)
            p_10pct = min(p_10pct + 6, 80)
            p_20pct = min(p_20pct + 4, 60)

        # Adjust for pattern matches
        if pattern_matches:
            top_match = pattern_matches[0]
            match_pct = top_match['match_pct']
            if match_pct >= 80:
                p_5pct = min(p_5pct + 20, 97)
                p_10pct = min(p_10pct + 15, 90)
                p_20pct = min(p_20pct + 12, 75)
                p_rally = max(p_rally - 20, 3)
            elif match_pct >= 60:
                p_5pct = min(p_5pct + 12, 95)
                p_10pct = min(p_10pct + 8, 85)
                p_20pct = min(p_20pct + 5, 65)

        # Adjust for critical alerts
        critical_alerts = sum(1 for a in alerts if 'CRITICO' in a or 'MAXIMA' in a or 'ROJA' in a)
        if critical_alerts >= 3:
            p_5pct = min(p_5pct + 10, 97)
            p_10pct = min(p_10pct + 8, 90)
            p_20pct = min(p_20pct + 5, 75)

        # Generate reasoning for each probability
        def build_reasoning():
            reasons = []
            if score >= 60:
                reasons.append(f"Risk score elevado ({score}/100)")
            if high_modules >= 3:
                reasons.append(f"{high_modules}/6 modulos en alerta")
            if pattern_matches:
                top = pattern_matches[0]
                reasons.append(f"Patron {top['description']} ({top['match_pct']:.0f}% match)")
            if critical_alerts >= 2:
                reasons.append(f"{critical_alerts} alertas criticas activas")
            if module_scores.get('positioning_crowding', 0) > 60:
                reasons.append("Posicionamiento crowded")
            if module_scores.get('volatility_regime', 0) > 50:
                reasons.append("Volatilidad elevada")
            if not reasons:
                if score < 30:
                    reasons.append("Condiciones de mercado favorables")
                else:
                    reasons.append("Condiciones mixtas, sin senales dominantes")
            return " | ".join(reasons[:3])

        return {
            'correction_5pct': {
                'probability': round(p_5pct, 1),
                'label': 'Correccion >5%',
                'reasoning': build_reasoning(),
            },
            'correction_10pct': {
                'probability': round(p_10pct, 1),
                'label': 'Correccion >10%',
                'reasoning': build_reasoning(),
            },
            'crash_20pct': {
                'probability': round(p_20pct, 1),
                'label': 'Crash >20%',
                'reasoning': build_reasoning(),
            },
            'rally_5pct': {
                'probability': round(p_rally, 1),
                'label': 'Rally >5%',
                'reasoning': build_reasoning(),
            },
        }

    def get_module_explanations(self):
        """
        Generate human-readable explanations for each module score.
        Explains WHY each module scored what it scored.
        """
        if not self.results:
            return {}

        explanations = {}
        module_names = {
            'liquidity_stress': 'Estres de Liquidez',
            'market_technicals': 'Tecnicos de Mercado',
            'valuation_excess': 'Exceso de Valoracion',
            'volatility_regime': 'Regimen de Volatilidad',
            'positioning_crowding': 'Posicionamiento y Crowding',
            'macro_deterioration': 'Deterioro Macro',
        }

        for module_key, module_obj in self.modules.items():
            score = self.results['module_scores'].get(module_key, 0)
            weight = MODULE_WEIGHTS.get(module_key, 0)
            name = module_names.get(module_key, module_key)

            # Determine severity
            if score >= 70:
                severity = 'CRITICO'
                color = 'red'
            elif score >= 50:
                severity = 'ELEVADO'
                color = 'orange'
            elif score >= 30:
                severity = 'MODERADO'
                color = 'yellow'
            else:
                severity = 'BAJO'
                color = 'green'

            exp = {
                'name': name,
                'score': score,
                'weight': weight,
                'weighted_contribution': round(score * weight / 100, 1),
                'severity': severity,
                'color': color,
                'signals': getattr(module_obj, 'signals', []),
                'alerts': getattr(module_obj, 'alerts', []),
            }

            # For market_technicals: add grouped signals by asset + asset_scores
            if module_key == 'market_technicals':
                asset_scores = getattr(module_obj, 'asset_scores', {})
                grouped = {}
                for sig in exp['signals']:
                    # Signals are formatted as "AssetName: detail"
                    parts = str(sig).split(':', 1)
                    if len(parts) == 2:
                        asset_name = parts[0].strip()
                        detail = parts[1].strip()
                        if asset_name not in grouped:
                            grouped[asset_name] = []
                        grouped[asset_name].append(detail)
                    else:
                        if 'General' not in grouped:
                            grouped['General'] = []
                        grouped['General'].append(str(sig))
                exp['grouped_signals'] = grouped
                exp['asset_scores'] = asset_scores

            explanations[module_key] = exp

        return explanations

    def _determine_regime(self, score):
        if score >= 80:
            return {
                'level': 'PANICO',
                'color': 'RED',
                'emoji': '🔴🔴🔴',
                'action': 'LIQUIDAR posiciones. IR A CASH/TREASURIES.',
                'description': 'Multiples senales de crash inminente o en curso.'
            }
        elif score >= 60:
            return {
                'level': 'DEFENSIVO',
                'color': 'RED',
                'emoji': '🔴🔴',
                'action': 'REDUCIR exposicion a minimos. Cash 40-60%.',
                'description': 'Senales fuertes de correccion. Proteger capital.'
            }
        elif score >= 40:
            return {
                'level': 'CAUTELA',
                'color': 'ORANGE',
                'emoji': '🟠',
                'action': 'REDUCIR especulativas. Cash 20-30%.',
                'description': 'Senales mixtas. Reducir apalancamiento y posiciones de riesgo.'
            }
        elif score >= 20:
            return {
                'level': 'RISK-ON',
                'color': 'GREEN',
                'emoji': '🟢',
                'action': 'Exposicion normal. Cash 10-15%.',
                'description': 'Condiciones favorables. Mantener posiciones.'
            }
        else:
            return {
                'level': 'FULL RISK-ON',
                'color': 'GREEN',
                'emoji': '🟢🟢',
                'action': 'Maxima exposicion. Cash minimo.',
                'description': 'Condiciones optimas para tomar riesgo.'
            }

    def _get_allocation(self, score):
        """
        Retorna allocation recomendada basada en score de riesgo.
        Incluye:
        - Asset allocation por clase
        - Sector equity breakdown
        - Instrumentos concretos en EUR (ETFs europeos)
        - Razonamiento para cada decision
        - Contexto de tipos de interes
        """
        # Detect rate environment from signals
        all_signals = self.results.get('signals', [])
        rate_signals = [s for s in all_signals
                        if any(w in s.lower() for w in ['tlt', 'yield', 'curva', 'rate', 'fed', 'bce', 'tipo'])]

        # Rate environment assessment
        rates_falling = any('cayendo' in s.lower() or 'risk-on' in s.lower() for s in rate_signals)
        rates_rising = any('subida' in s.lower() or 'tightening' in s.lower() or 'hawkish' in s.lower() for s in rate_signals)

        # Bond duration recommendation based on rate outlook
        if rates_falling:
            bond_strategy = 'long_duration'
            bond_rationale = 'Tipos bajando - bonos largo plazo se aprecian. Priorizar duracion larga.'
        elif rates_rising:
            bond_strategy = 'short_duration'
            bond_rationale = 'Tipos subiendo - evitar duracion. Solo corto plazo o inflation-linked.'
        else:
            bond_strategy = 'mixed_duration'
            bond_rationale = 'Tipos estables - mix de duraciones. Core en medio plazo.'

        # =====================================================================
        # ALLOCATION BY RISK REGIME
        # =====================================================================
        if score >= 80:
            alloc = {
                'equity': 10, 'bonds': 15, 'cash': 50,
                'gold_physical': 20, 'commodities': 0, 'crypto': 0, 'alternatives': 5,
            }
            equity_sectors = {
                'Utilities': 30, 'Healthcare': 30, 'Consumer Defensive': 25, 'Cash-like ETFs': 15,
            }
            bond_detail = {
                'govt_short': 60, 'govt_long': 0, 'corp_ig': 20, 'inflation_linked': 20, 'high_yield': 0,
            }
            rationale = [
                'PANICO: Prioridad absoluta = preservar capital.',
                f'Cash 50%: Depositos EUR o letras del Tesoro (ES/DE/FR) a 3-6 meses.',
                f'Oro 20%: Cobertura contra crash sistemico y devaluacion.',
                f'Bonos 15%: {bond_rationale} Solo gobierno corto plazo.',
                'Equity 10%: Solo utilities y healthcare defensivos si mantienes.',
            ]
            example_100k = [
                ('Cash / Letras Tesoro', '50,000 EUR', 'Depositos a plazo o ES0000012N35 (Letras ESP)'),
                ('Oro fisico / ETF', '20,000 EUR', 'iShares Physical Gold ETC (IGLN) o Invesco Physical Gold (SGLD)'),
                ('Bonos gobierno corto', '9,000 EUR', 'Xtrackers II EUR Govt Bond 1-3 (DBXN) o iShares EUR Govt 1-3yr (IBGS)'),
                ('Bonos inflation-linked', '3,000 EUR', 'iShares EUR Inflation Linked Govt (IBCI)'),
                ('Corp IG corto', '3,000 EUR', 'iShares EUR Corp Bond 1-5yr (IS0V)'),
                ('Equity defensivo', '10,000 EUR', 'iShares STOXX Europe 600 Healthcare (SXDPEX) + Utilities (SX6PEX)'),
                ('Alternatives', '5,000 EUR', 'Trend-following CTA o cash reserva tactica'),
            ]

        elif score >= 60:
            alloc = {
                'equity': 25, 'bonds': 25, 'cash': 25,
                'gold_physical': 15, 'commodities': 5, 'crypto': 0, 'alternatives': 5,
            }
            equity_sectors = {
                'Healthcare': 25, 'Consumer Defensive': 20, 'Utilities': 15,
                'Quality Tech': 15, 'Financials': 10, 'Industrials': 10, 'Energy': 5,
            }
            if bond_strategy == 'long_duration':
                bond_detail = {'govt_short': 20, 'govt_long': 40, 'corp_ig': 25, 'inflation_linked': 15, 'high_yield': 0}
            elif bond_strategy == 'short_duration':
                bond_detail = {'govt_short': 50, 'govt_long': 0, 'corp_ig': 30, 'inflation_linked': 20, 'high_yield': 0}
            else:
                bond_detail = {'govt_short': 30, 'govt_long': 20, 'corp_ig': 30, 'inflation_linked': 15, 'high_yield': 5}
            rationale = [
                'ALERTA: Reducir exposicion significativamente.',
                f'Cash 25%: Depositos EUR remunerados. Liquidez para oportunidades.',
                f'Bonos 25%: {bond_rationale}',
                'Equity 25%: Solo blue chips de calidad y dividendo. Evitar growth especulativo.',
                'Oro 15%: Hedge contra tail risk.',
            ]
            example_100k = [
                ('Cash / Depositos EUR', '25,000 EUR', 'Cuenta remunerada o Letras Tesoro 3-6M'),
                ('Bonos EUR core', '15,000 EUR', 'iShares Core EUR Govt Bond (IEGA) o Xtrackers EUR Govt Bond (DBXN)'),
                ('Bonos Corp IG', '7,500 EUR', 'iShares EUR Corp Bond (IEAC) o Xtrackers EUR Corp Bond (XBLC)'),
                ('Bonos inflation', '2,500 EUR', 'iShares EUR Inflation Linked (IBCI)'),
                ('Equity calidad EU', '15,000 EUR', 'iShares MSCI Europe Quality Factor (IEQU) + Stoxx 600 Healthcare'),
                ('Equity calidad US', '10,000 EUR', 'iShares MSCI USA Quality Factor (ISQU) - hedged EUR si posible'),
                ('Oro', '15,000 EUR', 'Invesco Physical Gold (SGLD) o iShares Physical Gold (IGLN)'),
                ('Commodities', '5,000 EUR', 'Invesco Bloomberg Commodity (CMOD)'),
                ('Alternatives', '5,000 EUR', 'JPM Global Macro Opps o cash tactico'),
            ]

        elif score >= 40:
            alloc = {
                'equity': 50, 'bonds': 20, 'cash': 12,
                'gold_physical': 8, 'commodities': 5, 'crypto': 0, 'alternatives': 5,
            }
            equity_sectors = {
                'Quality Tech': 25, 'Healthcare': 15, 'Financials': 15,
                'Industrials': 15, 'Consumer Discretionary': 10, 'Energy': 10, 'Consumer Defensive': 10,
            }
            if bond_strategy == 'long_duration':
                bond_detail = {'govt_short': 15, 'govt_long': 35, 'corp_ig': 30, 'inflation_linked': 10, 'high_yield': 10}
            elif bond_strategy == 'short_duration':
                bond_detail = {'govt_short': 40, 'govt_long': 5, 'corp_ig': 30, 'inflation_linked': 15, 'high_yield': 10}
            else:
                bond_detail = {'govt_short': 25, 'govt_long': 20, 'corp_ig': 30, 'inflation_linked': 10, 'high_yield': 15}
            rationale = [
                'CAUTELA: Mantener diversificacion con sesgo defensivo.',
                f'Equity 50%: Diversificar sectores, priorizar calidad sobre growth.',
                f'Bonos 20%: {bond_rationale}',
                'Cash 12%: Reserva tactica para comprar caidas.',
                'Oro 8%: Diversificacion de cartera.',
            ]
            example_100k = [
                ('Equity Europa', '20,000 EUR', 'iShares Core MSCI Europe (SMEA) o Vanguard FTSE Developed Europe (VEUR)'),
                ('Equity USA', '20,000 EUR', 'iShares Core S&P 500 EUR Hedged (IUSE) o Vanguard S&P 500 (VUSA)'),
                ('Equity Sectorial', '10,000 EUR', 'iShares Healthcare (SXDPEX) + Financials + Industrials'),
                ('Bonos EUR mix', '12,000 EUR', 'iShares Core EUR Govt Bond (IEGA) + Corp Bond (IEAC)'),
                ('Bonos HY', '4,000 EUR', 'iShares EUR High Yield Corp Bond (IHYG)'),
                ('Bonos inflation', '4,000 EUR', 'iShares EUR Inflation Linked (IBCI)'),
                ('Cash', '12,000 EUR', 'Depositos o Letras'),
                ('Oro', '8,000 EUR', 'Invesco Physical Gold (SGLD)'),
                ('Commodities', '5,000 EUR', 'Invesco Bloomberg Commodity (CMOD)'),
                ('Alternatives', '5,000 EUR', 'Amundi Multi-Strategy o cash tactico'),
            ]

        elif score >= 20:
            alloc = {
                'equity': 65, 'bonds': 15, 'cash': 5,
                'gold_physical': 5, 'commodities': 5, 'crypto': 5, 'alternatives': 0,
            }
            equity_sectors = {
                'Tech / Growth': 30, 'Financials': 15, 'Industrials': 15,
                'Healthcare': 10, 'Consumer Discretionary': 10, 'Energy': 10, 'Small Caps': 10,
            }
            if bond_strategy == 'long_duration':
                bond_detail = {'govt_short': 10, 'govt_long': 40, 'corp_ig': 25, 'inflation_linked': 5, 'high_yield': 20}
            else:
                bond_detail = {'govt_short': 25, 'govt_long': 20, 'corp_ig': 25, 'inflation_linked': 10, 'high_yield': 20}
            rationale = [
                'OPTIMISMO: Condiciones favorables para riesgo.',
                'Equity 65%: Diversificacion amplia con sesgo growth.',
                f'Bonos 15%: {bond_rationale} Incluir high yield para extra carry.',
                'Crypto 5%: Posicion tactica en BTC/ETH.',
            ]
            example_100k = [
                ('Equity World', '30,000 EUR', 'iShares Core MSCI World (IWDA) o Vanguard FTSE All-World (VWCE)'),
                ('Equity USA Growth', '20,000 EUR', 'iShares Nasdaq 100 (CNDX) o Invesco QQQ EUR'),
                ('Equity Europa', '10,000 EUR', 'iShares STOXX Europe 600 (EXSA)'),
                ('Small Caps', '5,000 EUR', 'iShares MSCI World Small Cap (WSML)'),
                ('Bonos EUR', '10,000 EUR', 'Mix: Govt Bond (IEGA) + Corp IG (IEAC) + HY (IHYG)'),
                ('Bonos inflation', '5,000 EUR', 'iShares EUR Inflation Linked (IBCI)'),
                ('Cash', '5,000 EUR', 'Cuenta remunerada'),
                ('Oro', '5,000 EUR', 'Invesco Physical Gold (SGLD)'),
                ('Commodities', '5,000 EUR', 'Invesco Bloomberg Commodity (CMOD)'),
                ('Crypto', '5,000 EUR', 'BTC + ETH via ETP (21Shares, WisdomTree)'),
            ]

        else:  # score < 20
            alloc = {
                'equity': 75, 'bonds': 8, 'cash': 2,
                'gold_physical': 3, 'commodities': 5, 'crypto': 7, 'alternatives': 0,
            }
            equity_sectors = {
                'Tech / Growth': 35, 'Consumer Discretionary': 15, 'Financials': 15,
                'Small Caps': 10, 'Industrials': 10, 'Emerging Markets': 10, 'Energy': 5,
            }
            bond_detail = {'govt_short': 20, 'govt_long': 20, 'corp_ig': 20, 'inflation_linked': 10, 'high_yield': 30}
            rationale = [
                'EUFORIA: Maxima exposicion a risk assets.',
                'Equity 75%: Full risk-on con growth y small caps.',
                'Crypto 7%: Posicion significativa aprovechando momentum.',
                'Bonos 8%: Minimo, solo para rebalanceo y decorrelacion.',
                'AVISO: Mantener stops. Este regimen no dura para siempre.',
            ]
            example_100k = [
                ('Equity World', '30,000 EUR', 'iShares Core MSCI World (IWDA) o Vanguard FTSE All-World (VWCE)'),
                ('Equity USA Growth', '25,000 EUR', 'iShares Nasdaq 100 (CNDX)'),
                ('Small Caps', '10,000 EUR', 'iShares MSCI World Small Cap (WSML)'),
                ('Emerging Markets', '10,000 EUR', 'iShares Core MSCI EM IMI (EIMI)'),
                ('Bonos HY + IG', '8,000 EUR', 'iShares EUR High Yield (IHYG) + Corp Bond (IEAC)'),
                ('Crypto', '7,000 EUR', 'BTC (21Shares ABTC) + ETH (21Shares AETH)'),
                ('Commodities', '5,000 EUR', 'Invesco Bloomberg Commodity (CMOD)'),
                ('Oro', '3,000 EUR', 'Invesco Physical Gold (SGLD)'),
                ('Cash', '2,000 EUR', 'Reserva minima'),
            ]

        return {
            **alloc,
            'equity_sectors': equity_sectors,
            'bond_detail': bond_detail,
            'bond_strategy': bond_strategy,
            'bond_rationale': bond_rationale,
            'rationale': rationale,
            'example_100k': example_100k,
            'currency': 'EUR',
            'notes': ' | '.join(rationale[:2]),
        }

    def _print_report(self):
        """Imprime el reporte en consola."""
        r = self.results

        print()
        print("=" * 70)
        print(f"  {r['regime']['emoji']} RISK EXPOSURE SCORE: {r['final_score']}/100")
        print(f"  REGIMEN: {r['regime']['level']}")
        print(f"  ACCION: {r['regime']['action']}")
        print("=" * 70)

        # Module Scores
        print("\n--- SCORES POR MODULO ---")
        for module, score in r['module_scores'].items():
            bar = '█' * (score // 5) + '░' * (20 - score // 5)
            weight = MODULE_WEIGHTS[module]
            print(f"  {module:30s} [{bar}] {score:3d}/100 (peso: {weight}%)")

        # Alerts
        if r['alerts']:
            print(f"\n--- ALERTAS ({len(r['alerts'])}) ---")
            for alert in r['alerts']:
                print(f"  !! {alert}")

        # Pattern Matches
        if r['pattern_matches']:
            print("\n--- PATRONES HISTORICOS DETECTADOS ---")
            for pm in r['pattern_matches']:
                print(f"  {pm['match_pct']:5.0f}% match: {pm['description']}")
                print(f"         Senales: {', '.join(pm['matched_signals'])}")

        # Allocation
        alloc = r['allocation']
        print("\n--- ALLOCATION RECOMENDADA ---")
        print(f"  Equity:        {alloc['equity']}%")
        print(f"  Bonds:         {alloc['bonds']}%")
        print(f"  Cash:          {alloc['cash']}%")
        print(f"  Gold (fisico): {alloc['gold_physical']}%")
        print(f"  Commodities:   {alloc['commodities']}%")
        print(f"  Crypto:        {alloc['crypto']}%")
        print(f"  Nota: {alloc['notes']}")

        # Top signals
        print(f"\n--- TOP SENALES ({len(r['signals'])} total) ---")
        for sig in r['signals'][:15]:
            print(f"  - {sig}")
        if len(r['signals']) > 15:
            print(f"  ... y {len(r['signals']) - 15} mas")

        print()

    def export_json(self, filepath=None):
        """Exporta resultados a JSON."""
        if filepath is None:
            filepath = f"risk_exposure_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

        # Serializar
        output = self.results.copy()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        print(f"Resultados exportados a: {filepath}")
        return filepath

    def export_for_pdf(self):
        """
        Retorna dict formateado para integracion con el generador de PDF.
        """
        r = self.results
        return {
            'section_title': 'RISK EXPOSURE ANALYSIS',
            'score': r['final_score'],
            'regime': r['regime'],
            'allocation': r['allocation'],
            'module_scores': r['module_scores'],
            'alerts': r['alerts'],
            'pattern_matches': r['pattern_matches'],
            'signals_summary': r['signals'][:20],
            'timestamp': r['timestamp'],
        }


# ============================================================================
# MAIN - Ejecucion standalone
# ============================================================================

def main():
    """
    Ejecuta el Risk Exposure Engine con datos reales + inputs manuales.
    """
    # Inputs manuales (actualizar diariamente o via web scraping)
    # Estos son los datos de feb 2026 como ejemplo
    manual_inputs = {
        # Valoraciones
        'pe_forward': 22.2,       # FactSet feb 2026
        'cape_ratio': 38.5,       # Shiller PE
        'buffett_indicator': 195,  # Estimado

        # Posicionamiento
        'put_call_ratio': 0.55,   # CBOE
        'margin_debt_yoy': 22,    # FINRA

        # Margin changes (CRITICO para detectar el patron de feb 2026)
        'cme_margin_changes': [
            {'asset': 'gold', 'direction': 'up', 'from': 6, 'to': 8, 'days_ago': 5},
            {'asset': 'silver', 'direction': 'up', 'from': 11, 'to': 15, 'days_ago': 5},
        ],

        # Sentimiento retail
        'reddit_sentiment': 82,    # 0-100 bullishness
    }

    # Crear e iniciar engine
    engine = RiskExposureEngine(
        data_dir='.',
        fred_api_key=os.environ.get('FRED_API_KEY', ''),
    )

    # Ejecutar analisis
    results = engine.run(manual_inputs=manual_inputs)

    # Exportar
    engine.export_json()

    return results


if __name__ == '__main__':
    main()
