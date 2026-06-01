"""
Multi-Horizon Scoring System
=============================
Sistema de scoring independiente para cada horizonte temporal.

Un stock puede tener:
- Score 90 en corto plazo (momentum fuerte, setup técnico)
- Score 40 en largo plazo (valoración cara, deuda alta)

Cada horizonte tiene sus propios factores y pesos.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import numpy as np
from datetime import datetime


class Horizon(Enum):
    SHORT_TERM = "short"    # 1-4 semanas
    MEDIUM_TERM = "medium"  # 1-6 meses
    LONG_TERM = "long"      # 6+ meses


class Signal(Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"


@dataclass
class HorizonScore:
    """Score para un horizonte específico"""
    horizon: Horizon
    total_score: float
    signal: Signal
    components: Dict[str, float]
    explanation: str
    confidence: float  # 0-100, qué tan confiable es el score


@dataclass
class MultiHorizonResult:
    """Resultado completo del análisis multi-horizonte"""
    ticker: str
    short_term: HorizonScore
    medium_term: HorizonScore
    long_term: HorizonScore
    combined_recommendation: str
    timestamp: datetime


# =============================================================================
# CONFIGURACIÓN DE PESOS POR HORIZONTE
# =============================================================================

# Backtest-calibrated weights (2-year walk-forward, 25 US stocks)
# V2: Blend contrarian with quality gates. Pure contrarian creates all-buy in pullbacks.
# Strategy: Quality fundamentals GATE the contrarian signal. Bad quality + oversold = value trap.

SHORT_TERM_WEIGHTS = {
    # IC-calibrated v3: quality_gate had +0.09 IC, fama_low_vol -0.10
    # (negative — low-vol underperformed high-vol). vix_regime near zero.
    # Keep tech signals, boost quality, drop fama_low_vol weight.

    # ============= HORIZON-SPECIFIC SIGNALS (NEW v6) =============
    # Options & catalyst-driven — drive CP differentiation vs MP/LP.
    # When the individual ticker is enriched via get_enriched_scores these
    # carry real per-ticker values; in the batch path they default to 50.
    'iv_percentile_realized': 0.04,   # low IV = cheap optionality
    'skew_score': 0.04,               # contrarian skew signal
    'pc_ratio_score': 0.03,           # P/C OI extremes
    'gex_regime_score': 0.03,         # gamma regime (volatility amplification)
    'squeeze_potential_score': 0.03,  # SI + DTC + call OI confluence
    'catalyst_proximity_score': 0.05, # earnings/event proximity with cheap IV
    'credit_risk_score': 0.03,        # systemic credit (HYG/LQD spread)

    # Technical signals (29%)
    'rsi': 0.05,
    'macd': 0.04,
    'bollinger_position': 0.04,
    'konkorde': 0.03,
    'konkorde_divergence': 0.02,
    'trendline_breakout': 0.05,
    'rsi_crossover': 0.03,
    'volume_profile': 0.03,

    # Mean-reversion (8%)
    'mean_reversion': 0.05,
    'iv_percentile': 0.02,
    'vix_regime': 0.01,

    # Momentum (8%)
    'momentum_1w': 0.02,
    'momentum_1m': 0.03,
    'relative_strength': 0.03,

    # MACRO OVERLAY (12%) — reduced (shared signals contribute too)
    'macro_overlay': 0.04,
    'macro_sector_impact': 0.04,
    'macro_regime_boost': 0.04,

    # Sector + Speculative (12%)
    'sector_rotation_score': 0.04,  # NEW: sector momentum tilt
    'congress_score': 0.03,
    'news_sentiment': 0.02,
    'quality_gate': 0.03,

    # Factor Model (6%)
    'fama_momentum': 0.04,
    'fama_low_vol': 0.02,
}  # Total: 1.00

MEDIUM_TERM_WEIGHTS = {
    # IC-calibrated v4: balance across regimes. Train/OOS analysis showed
    # quality factors (roe, quality_gate, fama_quality) had +0.13-0.22 IC
    # in 2023-2024 but flipped to ~0 in 2025-2026. Momentum_6m and macro
    # overlay are the ONLY factors with robust positive IC in BOTH regimes.
    # Reweight toward robust factors; keep moderate quality exposure.

    # ============= MP-SPECIFIC SIGNALS (NEW v6) =============
    # Fundamental momentum + flow — drives MP differentiation. These are
    # 3-12 month horizon signals (revisions, insider clusters, ROIC trend,
    # earnings streaks) that don't apply to CP or LP.
    'analyst_revisions_score': 0.06,   # 90d revisions velocity
    'insider_cluster_score': 0.05,     # >3 insiders buying
    'earnings_streak_score': 0.04,     # consecutive positive surprises
    'roic_trend_score': 0.03,          # multi-year ROIC trajectory
    'sector_rotation_score': 0.04,     # sector momentum alignment
    'credit_risk_score': 0.02,         # systemic credit context

    # Momentum (24%) — most robust across regimes
    'momentum_6m': 0.09,
    'momentum_3m': 0.07,
    'fama_momentum': 0.05,
    'analyst_revisions': 0.02,
    'earnings_momentum': 0.01,

    # MACRO OVERLAY (15%) — slight reduction
    'macro_overlay': 0.05,
    'macro_sector_impact': 0.05,
    'macro_regime_boost': 0.05,

    # Quality (18%) — strong in train, neutral in OOS. Keep moderate.
    'roe': 0.04,
    'roic': 0.04,
    'fama_quality': 0.04,
    'quality_gate': 0.03,
    'fcf_quality_mt': 0.03,

    # Contrarian (6%)
    'mean_reversion': 0.03,
    'sector_rs': 0.02,
    'short_interest': 0.01,

    # Technical (8%)
    'trend_strength': 0.04,
    'support_resistance': 0.04,

    # Speculative + structural (5%)
    'congress_score': 0.02,
    'institutional_flow': 0.02,
    'debt_trend': 0.01,
}  # Total: 1.00

LONG_TERM_WEIGHTS = {
    # IC-calibrated v4 (regime-robust): train/OOS analysis revealed that
    # quality factors (which scored +0.15-0.22 IC in 2023-2024) FLIPPED to
    # neutral/slightly-negative in 2025-2026. Only momentum_6m and the
    # macro overlay maintained positive IC across both regimes.
    # Build LT around robust factors; keep quality as moderate weight.

    # ============= LP-SPECIFIC SIGNALS (NEW v6) =============
    # Structural / multi-year — drives LP differentiation. ROIC trend
    # (improving vs declining), debt maturity risk, market breadth.
    'roic_trend_score': 0.06,           # 5-year ROIC trajectory
    'debt_maturity_risk_score': 0.04,   # refinancing pressure proxy
    'market_breadth_score': 0.03,       # % of sectors > 50sma
    'sector_rotation_score': 0.04,      # sector tailwind alignment

    # Momentum (20%) — robust positive across regimes
    'momentum_6m': 0.08,
    'fama_momentum': 0.08,
    'sector_rs': 0.04,

    # Quality (28%) — strong train, neutral OOS — keep meaningful but smaller
    'roe': 0.08,
    'roic': 0.06,
    'fama_quality': 0.05,
    'fcf_quality': 0.05,
    'moat_score': 0.04,

    # Stability (15%)
    'debt_ebitda': 0.04,
    'interest_coverage': 0.04,
    'dividend_stability': 0.03,
    'margin_stability': 0.02,
    'earnings_stability': 0.02,

    # MACRO OVERLAY (10%) — slight reduction (per-ticker structural takes priority)
    'macro_overlay': 0.03,
    'macro_sector_impact': 0.04,
    'macro_regime_boost': 0.03,

    # Speculative (6%)
    'congress_long_term': 0.03,
    'insider_activity': 0.02,
    'vix_regime': 0.01,

    # Value anchor (4%) — small; pe_percentile alone had -0.12 IC.
    'pe_percentile': 0.01,
    'fcf_yield': 0.02,
    'peg_ratio': 0.01,
}  # Total: 1.00


# Regime-adaptive weight shifts for strong macro environments
REGIME_WEIGHT_SHIFTS = {
    'strong_macro': {
        'macro_sector_impact': +0.06,
        'macro_regime_boost': +0.04,
        'news_sentiment': -0.03,
        'congress_score': -0.03,
        'options_flow': -0.02,
        'skew_score': -0.02,
    },
    'crisis': {
        'vix_regime': +0.04,
        'macro_overlay': +0.04,
        'quality_gate': +0.04,
        'momentum_1w': -0.03,
        'congress_score': -0.04,
        'options_flow': -0.03,
        'fama_momentum': -0.02,
    },
}


# =============================================================================
# PROFESSIONAL MACRO REGIME OVERRIDES
# =============================================================================
# Triggered by `detect_macro_regime()` in providers.py using real-time market
# signals (10Y/2Y yields, real rate, TIPS/IEF spread, HYG/LQD credit, DXY,
# liquidity composite — NOT M2). Each regime ships full weight overrides per
# horizon that supersede the base weights when the regime is active.
#
# Theory of regime-aware allocation:
#   EASY (loose liquidity, falling rates): GROWTH + MOMENTUM win. Bond proxies
#     and high-duration equities outperform. Bias scoring toward momentum and
#     speculative signals. De-emphasize defensive quality.
#   TIGHTENING (rising rates, draining liquidity): QUALITY + LOW-DEBT win.
#     Rising discount rate compresses valuations of high-duration growth.
#     Bias toward profitability, balance sheet, free cash flow.
#   STAGFLATION (high real rates + rising inflation): VALUE + REAL ASSETS win.
#     Cheap-multiple defensive earners with pricing power beat growth.
#   RISK_OFF (VIX>25 + credit stressed): MEAN-REVERSION + QUALITY win.
#     Drawdowns set up contrarian buys in quality names. Avoid momentum.
#   NEUTRAL: Use base weights.

# Each override returns a DICT OF MULTIPLIERS applied to each weight in the base.
# A multiplier of 1.5 means "boost this factor by 50%". Final weights are
# renormalized to sum to 1.0 after multiplication.

REGIME_FACTOR_MULTIPLIERS = {
    'easy': {
        # Growth + momentum thrive on cheap money
        'short_term': {
            'momentum_1w': 1.4, 'momentum_1m': 1.4, 'relative_strength': 1.3,
            'fama_momentum': 1.6, 'macro_overlay': 1.3, 'macro_sector_impact': 1.3,
            'macro_regime_boost': 1.3, 'congress_score': 1.2,
            # Reduce defensive
            'quality_gate': 0.7, 'fama_low_vol': 0.5, 'vix_regime': 0.5,
            'iv_percentile': 0.7, 'skew_score': 0.6,
        },
        'medium_term': {
            'momentum_3m': 1.6, 'momentum_6m': 1.6, 'fama_momentum': 1.5,
            'earnings_momentum': 1.3, 'analyst_revisions': 1.2,
            'macro_overlay': 1.3, 'macro_sector_impact': 1.3, 'macro_regime_boost': 1.3,
            # Reduce defensive
            'quality_gate': 0.7, 'mean_reversion': 0.6, 'short_interest': 0.5,
            'vix_regime': 0.5,
        },
        'long_term': {
            'momentum_6m': 1.6, 'fama_momentum': 1.5, 'sector_rs': 1.3,
            'roic': 1.2, 'fama_quality': 1.2, 'macro_overlay': 1.3,
            'macro_sector_impact': 1.3, 'macro_regime_boost': 1.3,
            # Reduce value (still cheap, but growth dominates)
            'pe_percentile': 0.5, 'fcf_yield': 0.7, 'peg_ratio': 0.6,
            'vix_regime': 0.5, 'dividend_stability': 0.7,
        },
    },
    'tightening': {
        # Quality + low debt protect; rates compress growth multiples
        'short_term': {
            'quality_gate': 1.8, 'iv_percentile': 1.3, 'skew_score': 1.3,
            'vix_regime': 1.5, 'mean_reversion': 1.3,
            # Reduce momentum + speculative
            'momentum_1w': 0.6, 'momentum_1m': 0.7, 'fama_momentum': 0.7,
            'congress_score': 0.8, 'options_flow': 0.7, 'news_sentiment': 0.8,
            'macro_sector_impact': 0.8,
        },
        'medium_term': {
            'roe': 1.5, 'roic': 1.5, 'quality_gate': 1.8, 'fcf_quality_mt': 1.4,
            'fama_quality': 1.4, 'debt_trend': 1.4, 'vix_regime': 1.3,
            # Reduce momentum (rate-sensitive growth gets punished)
            'momentum_3m': 0.7, 'momentum_6m': 0.7, 'fama_momentum': 0.6,
            'analyst_revisions': 0.8,
        },
        'long_term': {
            'roe': 1.5, 'roic': 1.5, 'fama_quality': 1.4, 'fcf_quality': 1.4,
            'debt_ebitda': 1.5, 'interest_coverage': 1.5, 'moat_score': 1.3,
            # Reduce momentum + high-multiple growth
            'momentum_6m': 0.6, 'fama_momentum': 0.6, 'sector_rs': 0.8,
            'pe_percentile': 0.6,  # high P/E hurts more here
        },
    },
    'stagflation': {
        # Value + dividends + real assets; growth multiples crushed.
        # Multipliers conservative (1.3-1.7) — backtest showed the strict
        # version (2.0-2.5) overreacted in periods where high rates coexisted
        # with growth dominance (Mag 7 era).
        'short_term': {
            'mean_reversion': 1.3, 'vix_regime': 1.2, 'iv_percentile': 1.2,
            'quality_gate': 1.3,
            'momentum_1w': 0.7, 'momentum_1m': 0.7, 'fama_momentum': 0.6,
            'macro_overlay': 1.3, 'macro_sector_impact': 1.3,
        },
        'medium_term': {
            'fcf_quality_mt': 1.4, 'quality_gate': 1.3, 'roe': 1.2,
            'macro_overlay': 1.3, 'macro_sector_impact': 1.3,
            'momentum_3m': 0.7, 'momentum_6m': 0.7, 'fama_momentum': 0.6,
            'analyst_revisions': 0.8,
        },
        'long_term': {
            # In stagflation, value works but the rotation is uneven.
            'pe_percentile': 1.7, 'fcf_yield': 1.6, 'peg_ratio': 1.4,
            'dividend_stability': 1.5, 'fcf_quality': 1.3, 'roic': 1.2,
            'debt_ebitda': 1.3, 'interest_coverage': 1.3,
            'momentum_6m': 0.7, 'fama_momentum': 0.7, 'sector_rs': 0.8,
        },
    },
    'risk_off': {
        # Quality + mean reversion + defensive; avoid momentum chasers
        'short_term': {
            'quality_gate': 2.0, 'mean_reversion': 1.8, 'vix_regime': 1.5,
            'iv_percentile': 1.5, 'fama_low_vol': 1.8,
            'momentum_1w': 0.4, 'momentum_1m': 0.5, 'fama_momentum': 0.5,
            'congress_score': 0.6, 'options_flow': 0.6, 'news_sentiment': 0.6,
            'macro_overlay': 1.5, 'macro_regime_boost': 1.3,
        },
        'medium_term': {
            'quality_gate': 2.0, 'roe': 1.5, 'fcf_quality_mt': 1.6,
            'mean_reversion': 1.6, 'vix_regime': 1.5, 'debt_trend': 1.4,
            'macro_overlay': 1.5,
            'momentum_3m': 0.5, 'momentum_6m': 0.5, 'fama_momentum': 0.5,
            'earnings_momentum': 0.7, 'analyst_revisions': 0.7,
        },
        'long_term': {
            'roe': 1.5, 'fcf_quality': 1.5, 'debt_ebitda': 1.8,
            'interest_coverage': 1.8, 'dividend_stability': 1.5,
            'moat_score': 1.4, 'quality_gate': 1.5, 'fama_quality': 1.3,
            'momentum_6m': 0.4, 'fama_momentum': 0.4, 'sector_rs': 0.6,
        },
    },
    # 'neutral' uses base weights unchanged
}


def apply_regime_overrides(base_weights: Dict[str, float], regime: str,
                           horizon: str) -> Dict[str, float]:
    """Apply regime-aware multipliers to base weights and renormalize to 1.0.

    Args:
        base_weights: one of SHORT_TERM_WEIGHTS / MEDIUM_TERM_WEIGHTS / LONG_TERM_WEIGHTS
        regime: 'easy' | 'tightening' | 'stagflation' | 'risk_off' | 'neutral'
        horizon: 'short_term' | 'medium_term' | 'long_term'

    Returns base_weights unchanged for unknown regimes. Otherwise returns a
    new dict with multipliers applied and weights renormalized so the sum is 1.0.
    """
    if regime not in REGIME_FACTOR_MULTIPLIERS:
        return base_weights
    mults = REGIME_FACTOR_MULTIPLIERS[regime].get(horizon, {})
    if not mults:
        return base_weights
    adjusted = {k: v * mults.get(k, 1.0) for k, v in base_weights.items()}
    total = sum(adjusted.values())
    if total <= 0:
        return base_weights
    return {k: v / total for k, v in adjusted.items()}


def _detect_macro_regime(data: Dict[str, Any]) -> str:
    """
    Detect current macro regime from scoring_data.
    Returns: 'strong_macro' | 'crisis' | 'low_vol_grind' | 'normal'
    """
    oil_chg = abs(data.get('macro_oil_chg', 0))
    spy_chg = data.get('macro_spy_chg', 0)
    vix = data.get('macro_vix', 20)
    hyg_chg = abs(data.get('macro_hyg_chg', 0))

    if vix >= 32 and spy_chg <= -2:
        return 'crisis'
    if oil_chg >= 3 or abs(spy_chg) >= 2 or vix >= 28 or hyg_chg >= 1:
        return 'strong_macro'
    if vix < 14 and -0.5 <= spy_chg <= 1.0:
        return 'low_vol_grind'
    return 'normal'


def _weighted_score(components: Dict[str, float], weights: Dict[str, float], amplifier: float = 1.0) -> float:
    """Compute a weighted score with effective-weight normalization.

    Standard weighted sum dilutes the score toward 50 when many factors are
    at their neutral default (50): every "missing" factor contributes
    ``50 * weight``, pulling the result back. That caps real scores around
    60-65 even for excellent stocks.

    Instead, we treat factors at exactly 50 as "no signal" and renormalize
    over the remaining weight. The final amplifier expands the deviation
    from 50 to give the score meaningful range (typically 1.2-1.5).
    """
    sig_weighted_sum = 0.0
    sig_weight = 0.0
    non_sig_weight = 0.0
    for factor, weight in weights.items():
        if factor not in components:
            continue
        val = components[factor]
        # Treat values within ±0.5 of 50 as "no signal" (most defaults sit at 50.0)
        if abs(val - 50) < 0.5:
            non_sig_weight += weight
            continue
        sig_weighted_sum += val * weight
        sig_weight += weight

    if sig_weight <= 0:
        return 50.0

    raw_avg = sig_weighted_sum / sig_weight  # weighted average of signaling factors
    # Anchor: signaling coverage. When most factors signal, trust the avg.
    # When few signal, blend slightly toward neutral to avoid overreacting to
    # a single extreme factor.
    total_weight = sig_weight + non_sig_weight
    coverage = sig_weight / total_weight if total_weight > 0 else 1.0
    # coverage 1.0 -> full trust in avg
    # coverage 0.5 -> mix 0.7 avg + 0.3 neutral
    # coverage 0.2 -> mix 0.5 avg + 0.5 neutral (extreme caution)
    trust = 0.5 + coverage * 0.5  # 0.5 to 1.0
    blended = raw_avg * trust + 50 * (1 - trust)
    # Amplify deviation from neutral
    amplified = 50 + (blended - 50) * amplifier
    return max(5, min(95, amplified))


class MultiHorizonScorer:
    """
    Calcula scores independientes para cada horizonte temporal.
    """

    def __init__(self):
        self.weights = {
            Horizon.SHORT_TERM: SHORT_TERM_WEIGHTS,
            Horizon.MEDIUM_TERM: MEDIUM_TERM_WEIGHTS,
            Horizon.LONG_TERM: LONG_TERM_WEIGHTS,
        }

    def calculate_percentile(self, value: float, all_values: List[float], higher_is_better: bool = True) -> float:
        """
        Calcula el percentil de un valor dentro de una lista.

        Args:
            value: Valor a evaluar
            all_values: Lista de todos los valores para comparar
            higher_is_better: Si True, mayor valor = mejor percentil

        Returns:
            Percentil (0-100)
        """
        if not all_values or value is None:
            return 50.0

        sorted_values = sorted([v for v in all_values if v is not None])
        if not sorted_values:
            return 50.0

        # Posición del valor
        position = sum(1 for v in sorted_values if v < value)
        percentile = (position / len(sorted_values)) * 100

        if not higher_is_better:
            percentile = 100 - percentile

        return min(max(percentile, 0), 100)

    def _get_signal(self, score: float, horizon: str = 'short_term') -> Signal:
        """
        Convierte score en señal con umbrales por horizonte.

        Short-term uses wider bands (more volatile signals).
        Long-term uses tighter bands centered on fundamentals.
        """
        # Thresholds calibrated for the effective-weight normalization scheme.
        # With missing factors no longer diluting toward 50, top stocks reach
        # the 75-90 range and the distribution is wider.
        if horizon == 'short_term':
            if score >= 72:
                return Signal.STRONG_BUY
            elif score >= 60:
                return Signal.BUY
            elif score >= 52:
                return Signal.ACCUMULATE
            elif score >= 42:
                return Signal.HOLD
            elif score >= 32:
                return Signal.REDUCE
            else:
                return Signal.SELL
        elif horizon == 'medium_term':
            if score >= 70:
                return Signal.STRONG_BUY
            elif score >= 58:
                return Signal.BUY
            elif score >= 50:
                return Signal.ACCUMULATE
            elif score >= 41:
                return Signal.HOLD
            elif score >= 31:
                return Signal.REDUCE
            else:
                return Signal.SELL
        else:  # long_term
            if score >= 68:
                return Signal.STRONG_BUY
            elif score >= 56:
                return Signal.BUY
            elif score >= 48:
                return Signal.ACCUMULATE
            elif score >= 40:
                return Signal.HOLD
            elif score >= 30:
                return Signal.REDUCE
            else:
                return Signal.SELL

    def calculate_short_term_score(
        self,
        data: Dict[str, Any],
        market_data: Optional[Dict] = None
    ) -> HorizonScore:
        """
        Calcula score de corto plazo.

        Factores principales:
        - RSI, MACD, Bollinger Bands
        - Volume Profile, VWAP
        - Momentum 1W/1M
        - Congress trades recientes
        - News sentiment
        """
        components = {}
        weights = self.weights[Horizon.SHORT_TERM]

        # === FACTORES TÉCNICOS ===

        # RSI (30-70 es neutral, extremos son señales)
        # Ajustado para ser más generoso con posiciones de compra
        rsi = data.get('rsi_14', 50)
        if rsi < 25:
            rsi_score = 90  # Muy sobrevendido = gran oportunidad
        elif rsi < 35:
            rsi_score = 80  # Sobreventa = oportunidad
        elif rsi < 45:
            rsi_score = 65  # Bajo pero no extremo = favorable
        elif rsi > 75:
            rsi_score = 20  # Muy sobrecomprado = precaución máxima
        elif rsi > 65:
            rsi_score = 35  # Sobrecompra moderada
        elif rsi > 55:
            rsi_score = 55  # Neutral-alto
        else:
            rsi_score = 55  # Rango neutral (45-55)
        components['rsi'] = min(max(rsi_score, 0), 100)

        # MACD - ajustado para ser más generoso en señales alcistas
        macd_signal = data.get('macd_signal', 'neutral')
        if macd_signal == 'bullish_cross':
            components['macd'] = 90  # Cruce alcista = señal muy fuerte
        elif macd_signal == 'bullish':
            components['macd'] = 75  # MACD positivo = buena señal
        elif macd_signal == 'bearish_cross':
            components['macd'] = 15
        elif macd_signal == 'bearish':
            components['macd'] = 30
        else:
            components['macd'] = 55  # Neutral ligeramente positivo

        # Volume Profile Position
        vp_position = data.get('volume_profile_position', 'neutral')
        if vp_position == 'at_support':
            components['volume_profile'] = 80
        elif vp_position == 'near_support':
            components['volume_profile'] = 70
        elif vp_position == 'at_resistance':
            components['volume_profile'] = 25
        elif vp_position == 'near_resistance':
            components['volume_profile'] = 35
        else:
            components['volume_profile'] = 50

        # VWAP Position
        price = data.get('price', 0)
        vwap = data.get('vwap', price)
        if price and vwap:
            vwap_diff = ((price - vwap) / vwap) * 100 if vwap else 0
            if vwap_diff > 2:
                components['vwap_position'] = 35  # Muy por encima de VWAP
            elif vwap_diff > 0:
                components['vwap_position'] = 50  # Por encima
            elif vwap_diff > -2:
                components['vwap_position'] = 65  # Por debajo (oportunidad)
            else:
                components['vwap_position'] = 75  # Muy por debajo
        else:
            components['vwap_position'] = 50

        # Bollinger Position
        bb_position = data.get('bollinger_position', 50)  # 0=lower, 50=middle, 100=upper
        if bb_position < 20:
            components['bollinger_position'] = 80  # En banda inferior
        elif bb_position > 80:
            components['bollinger_position'] = 25  # En banda superior
        else:
            components['bollinger_position'] = 50 + (50 - bb_position) * 0.3

        # Short-term trend
        trend_1w = data.get('trend_1w', 0)  # % cambio última semana
        if trend_1w > 5:
            components['short_term_trend'] = 75
        elif trend_1w > 2:
            components['short_term_trend'] = 65
        elif trend_1w > -2:
            components['short_term_trend'] = 50
        elif trend_1w > -5:
            components['short_term_trend'] = 40
        else:
            components['short_term_trend'] = 30

        # Konkorde (Institutional vs Retail flow)
        konkorde_score = data.get('konkorde_score', 50)
        konkorde_signal = data.get('konkorde_signal', 'neutral')

        # Adjust score based on signal type
        if konkorde_signal == 'strong_bullish':
            components['konkorde'] = min(95, konkorde_score + 10)  # Both buying - very bullish
        elif konkorde_signal == 'accumulation':
            components['konkorde'] = min(90, konkorde_score + 5)   # Smart money buying - bullish
        elif konkorde_signal == 'distribution':
            components['konkorde'] = max(10, konkorde_score - 5)   # Smart money selling - bearish
        elif konkorde_signal == 'strong_bearish':
            components['konkorde'] = max(5, konkorde_score - 10)   # Both selling - very bearish
        else:
            components['konkorde'] = konkorde_score

        # RSI Crossover (oversold recovery signal)
        rsi_cross_score = data.get('rsi_crossover_score', 50)
        bullish_crossover = data.get('rsi_bullish_crossover', False)
        if bullish_crossover:
            components['rsi_crossover'] = min(90, rsi_cross_score + 5)
        else:
            components['rsi_crossover'] = rsi_cross_score

        # Konkorde Divergence (institutional accumulation while price flat)
        div_score = data.get('konkorde_divergence_score', 50)
        bullish_div = data.get('konkorde_bullish_divergence', False)
        if bullish_div:
            components['konkorde_divergence'] = min(90, div_score + 5)
        else:
            components['konkorde_divergence'] = div_score

        # Trendline Breakout (bearish trendline proximity/break)
        tl_score = data.get('trendline_score', 50)
        tl_imminent = data.get('trendline_breakout_imminent', False)
        tl_confirmed = data.get('trendline_breakout_confirmed', False)
        if tl_confirmed:
            components['trendline_breakout'] = min(95, tl_score + 5)
        elif tl_imminent:
            components['trendline_breakout'] = min(90, tl_score)
        else:
            components['trendline_breakout'] = tl_score

        # === MOMENTUM (blended: slight contrarian bias, not pure inversion) ===

        # Momentum 1 week — blended: slight contrarian (60% contrarian, 40% trend)
        mom_1w = data.get('momentum_1w', 0)
        mom_1w_trend = max(10, min(90, 50 + mom_1w * 2))
        mom_1w_contra = max(10, min(90, 50 - mom_1w * 2))
        components['momentum_1w'] = mom_1w_contra * 0.6 + mom_1w_trend * 0.4

        # Momentum 1 month — blended
        mom_1m = data.get('momentum_1m', 0)
        mom_1m_trend = max(10, min(90, 50 + mom_1m * 1.2))
        mom_1m_contra = max(10, min(90, 50 - mom_1m * 1.2))
        components['momentum_1m'] = mom_1m_contra * 0.6 + mom_1m_trend * 0.4

        # Relative Strength vs SPY — blended
        rs = data.get('relative_strength_1m', 0)
        if rs > 5:
            components['relative_strength'] = 55   # Slight positive (trend)
        elif rs > 0:
            components['relative_strength'] = 60   # Neutral positive
        elif rs > -5:
            components['relative_strength'] = 55   # Slight laggard (contrarian)
        else:
            components['relative_strength'] = 65   # Deep laggard (contrarian buy)

        # === MEAN REVERSION SIGNAL ===
        rsi_val = data.get('rsi_14', 50)
        if rsi_val < 30 and mom_1m < -5:
            components['mean_reversion'] = 92  # Strong oversold bounce setup
        elif rsi_val < 40 and mom_1m < -3:
            components['mean_reversion'] = 78
        elif rsi_val > 70 and mom_1m > 10:
            components['mean_reversion'] = 15  # Overbought risk
        elif rsi_val > 65 and mom_1m > 5:
            components['mean_reversion'] = 25
        else:
            components['mean_reversion'] = 50

        # === FACTORES ESPECULATIVOS ===

        # Congress Score (de Capitol Trades)
        congress = data.get('congress_score', 50)
        components['congress_score'] = congress

        # News Sentiment (-100 a +100 -> 0 a 100)
        sentiment = data.get('news_sentiment', 0)
        components['news_sentiment'] = 50 + (sentiment / 2)

        # Options Flow
        options = data.get('options_flow', 'neutral')
        if options == 'very_bullish':
            components['options_flow'] = 85
        elif options == 'bullish':
            components['options_flow'] = 70
        elif options == 'bearish':
            components['options_flow'] = 30
        elif options == 'very_bearish':
            components['options_flow'] = 15
        else:
            components['options_flow'] = 50

        # === PROFESSIONAL VARIABLES ===

        # IV Percentile: low IV = cheap options = bullish entry
        iv_pct = data.get('iv_percentile', 50)
        components['iv_percentile'] = max(5, min(95, 100 - iv_pct))  # Invert: low IV = high score

        # VIX Regime modifier
        components['vix_regime'] = data.get('vix_regime', 50)

        # Skew Score: from 25Δ risk reversal
        skew = data.get('skew_score', 50)
        components['skew_score'] = skew

        # Quality Gate: ROE + margin composite. High quality = safe to buy dip
        roe_val = data.get('roe', 15)
        margin_val = data.get('profit_margin', 10)
        if roe_val > 20 and margin_val > 15:
            components['quality_gate'] = 85
        elif roe_val > 12 and margin_val > 8:
            components['quality_gate'] = 65
        elif roe_val > 5:
            components['quality_gate'] = 45
        elif roe_val <= 0 or margin_val < 0:
            components['quality_gate'] = 15
        else:
            components['quality_gate'] = 30

        # === MACRO OVERLAY (22%) ===
        # Composite macro risk: VIX + MOVE + Oil + Credit + Gold + SPY
        macro_composite = data.get('macro_composite', 50)
        components['macro_overlay'] = macro_composite

        # Sector-specific macro adjustment (-40 to +40) → 0-100 score
        macro_sector_adj = data.get('macro_sector_adj', 0)
        components['macro_sector_impact'] = max(5, min(95, 50 + macro_sector_adj * 2.25))

        # Direct sector rotation score (0-100)
        components['macro_regime_boost'] = data.get('macro_regime_boost', 50)

        # === NEW v6 — HORIZON-SPECIFIC SHORT-TERM SIGNALS ===
        # These drive CP differentiation vs MP/LP. All default to 50 (neutral)
        # in the batch path; enriched per-ticker via get_enriched_scores.
        # Invert IV percentile so low realized vol = high score (cheap optionality).
        iv_pct_real = data.get('iv_percentile_realized', 50)
        components['iv_percentile_realized'] = max(5, min(95, 100 - iv_pct_real))
        components['pc_ratio_score'] = data.get('pc_ratio_score', 50)
        components['gex_regime_score'] = data.get('gex_regime_score', 50)
        components['squeeze_potential_score'] = data.get('squeeze_potential_score', 50)
        components['catalyst_proximity_score'] = data.get('catalyst_proximity_score', 50)
        components['credit_risk_score'] = data.get('credit_risk_score', 50)
        components['sector_rotation_score'] = data.get('sector_rotation_score', 50)

        # === FACTOR MODEL (8%) ===
        components['fama_momentum'] = data.get('fama_momentum', 50)
        components['fama_low_vol'] = data.get('fama_low_vol', 50)

        # === REGIME-ADAPTIVE WEIGHTS ===
        # First: legacy crisis/strong_macro shift (additive deltas)
        regime = _detect_macro_regime(data)
        if regime in REGIME_WEIGHT_SHIFTS:
            active_weights = dict(weights)
            for k, delta in REGIME_WEIGHT_SHIFTS[regime].items():
                if k in active_weights:
                    active_weights[k] = max(0, active_weights[k] + delta)
        else:
            active_weights = dict(weights)

        # Second: professional macro regime (easy/tightening/stagflation/risk_off)
        # detected via 10Y/2Y/real-rate/credit/DXY/liquidity (NOT M2).
        # Passed in via scoring_data['macro_regime'] by the data layer.
        pro_regime = data.get('macro_regime', 'neutral')
        active_weights = apply_regime_overrides(active_weights, pro_regime, 'short_term')

        # Score with effective-weight normalization + conviction amplifier
        total = _weighted_score(components, active_weights, amplifier=1.5)

        # Calcular confianza basada en disponibilidad de datos
        available = sum(1 for f in weights.keys() if f in components and components[f] != 50)
        confidence = (available / len(weights)) * 100

        # Generar explicación
        explanation = self._generate_short_term_explanation(components, total)

        return HorizonScore(
            horizon=Horizon.SHORT_TERM,
            total_score=round(total, 1),
            signal=self._get_signal(total, 'short_term'),
            components=components,
            explanation=explanation,
            confidence=round(confidence, 1)
        )

    def calculate_medium_term_score(
        self,
        data: Dict[str, Any],
        market_data: Optional[Dict] = None
    ) -> HorizonScore:
        """
        Calcula score de medio plazo (1-6 meses).

        Factores principales:
        - Momentum 3M/6M
        - Analyst revisions
        - Quality metrics (ROE, ROIC)
        - Trend strength
        - Sector rotation
        """
        components = {}
        weights = self.weights[Horizon.MEDIUM_TERM]

        # === MOMENTUM (blended: 50% contrarian + 50% trend for differentiation) ===

        # Momentum 3 months — blended
        mom_3m = data.get('momentum_3m', 0)
        m3_trend = max(10, min(90, 50 + mom_3m * 0.6))
        m3_contra = max(10, min(90, 50 - mom_3m * 0.6))
        components['momentum_3m'] = m3_contra * 0.5 + m3_trend * 0.5

        # Momentum 6 months — blended, more trend-following
        mom_6m = data.get('momentum_6m', 0)
        m6_trend = max(10, min(90, 50 + mom_6m * 0.4))
        m6_contra = max(10, min(90, 50 - mom_6m * 0.4))
        components['momentum_6m'] = m6_contra * 0.4 + m6_trend * 0.6

        # Analyst Revisions
        revisions = data.get('analyst_revisions', 0)  # % cambio en estimaciones
        if revisions > 5:
            components['analyst_revisions'] = 85
        elif revisions > 2:
            components['analyst_revisions'] = 70
        elif revisions > -2:
            components['analyst_revisions'] = 50
        elif revisions > -5:
            components['analyst_revisions'] = 35
        else:
            components['analyst_revisions'] = 20

        # Earnings Momentum
        earnings_surprise = data.get('earnings_surprise', 0)
        if earnings_surprise > 10:
            components['earnings_momentum'] = 85
        elif earnings_surprise > 5:
            components['earnings_momentum'] = 70
        elif earnings_surprise > -5:
            components['earnings_momentum'] = 50
        else:
            components['earnings_momentum'] = 30

        # === QUALITY ===

        # ROE
        roe = data.get('roe', 0)
        if roe > 25:
            components['roe'] = 90
        elif roe > 15:
            components['roe'] = 70
        elif roe > 10:
            components['roe'] = 55
        elif roe > 0:
            components['roe'] = 40
        else:
            components['roe'] = 20

        # ROIC
        roic = data.get('roic', 0)
        if roic > 20:
            components['roic'] = 90
        elif roic > 12:
            components['roic'] = 70
        elif roic > 8:
            components['roic'] = 55
        elif roic > 0:
            components['roic'] = 40
        else:
            components['roic'] = 20

        # Margin Trend (mejorando o empeorando)
        margin_trend = data.get('margin_trend', 0)  # % cambio YoY
        if margin_trend > 2:
            components['margin_trend'] = 80
        elif margin_trend > 0:
            components['margin_trend'] = 65
        elif margin_trend > -2:
            components['margin_trend'] = 45
        else:
            components['margin_trend'] = 30

        # Debt Trend
        debt_trend = data.get('debt_trend', 0)  # % cambio en Debt/EBITDA
        if debt_trend < -10:
            components['debt_trend'] = 85  # Deuda bajando
        elif debt_trend < 0:
            components['debt_trend'] = 65
        elif debt_trend < 10:
            components['debt_trend'] = 45
        else:
            components['debt_trend'] = 25  # Deuda subiendo

        # === TÉCNICO ===

        # Trend Strength (ADX)
        adx = data.get('adx', 25)
        trend_direction = data.get('trend_direction', 'neutral')
        if adx > 40 and trend_direction == 'up':
            components['trend_strength'] = 85
        elif adx > 25 and trend_direction == 'up':
            components['trend_strength'] = 70
        elif adx > 25 and trend_direction == 'down':
            components['trend_strength'] = 30
        elif adx > 40 and trend_direction == 'down':
            components['trend_strength'] = 15
        else:
            components['trend_strength'] = 50

        # Support/Resistance position
        sr_position = data.get('sr_position', 'middle')
        if sr_position == 'at_support':
            components['support_resistance'] = 75
        elif sr_position == 'at_resistance':
            components['support_resistance'] = 30
        else:
            components['support_resistance'] = 50

        # Sector Rotation
        sector_strength = data.get('sector_strength', 50)
        components['sector_rotation'] = sector_strength

        # === PROFESSIONAL VARIABLES ===

        # === MEAN REVERSION & PROFESSIONAL ===

        # Mean reversion (oversold + quality = strong MT buy)
        rsi_val = data.get('rsi_14', 50)
        mom_3m_raw = data.get('momentum_3m', 0)
        if rsi_val < 35 and mom_3m_raw < -10:
            components['mean_reversion'] = 88  # Deep pullback
        elif rsi_val < 45 and mom_3m_raw < -5:
            components['mean_reversion'] = 72
        elif rsi_val > 70 and mom_3m_raw > 15:
            components['mean_reversion'] = 20  # Overextended
        else:
            components['mean_reversion'] = 50

        # Sector RS — blended (slight contrarian)
        sr = data.get('sector_rs', 50)
        components['sector_rs'] = max(10, min(90, (100 - sr) * 0.4 + sr * 0.6))

        # Short Interest: high SI = squeeze potential
        si = data.get('short_interest', 0)
        if si > 20:
            components['short_interest'] = 75
        elif si > 10:
            components['short_interest'] = 60
        elif si > 5:
            components['short_interest'] = 50
        else:
            components['short_interest'] = 45

        # FCF Quality for medium term
        components['fcf_quality_mt'] = data.get('fcf_quality', 50)

        # VIX Regime
        components['vix_regime'] = data.get('vix_regime', 50)

        # Quality Gate for MT
        roe_val = data.get('roe', 15)
        margin_val = data.get('profit_margin', 10)
        if roe_val > 20 and margin_val > 15:
            components['quality_gate'] = 85
        elif roe_val > 12 and margin_val > 8:
            components['quality_gate'] = 65
        elif roe_val > 5:
            components['quality_gate'] = 45
        elif roe_val <= 0 or margin_val < 0:
            components['quality_gate'] = 15
        else:
            components['quality_gate'] = 30

        # === MACRO OVERLAY (18%) ===
        components['macro_overlay'] = data.get('macro_composite', 50)
        macro_sector_adj = data.get('macro_sector_adj', 0)
        components['macro_sector_impact'] = max(5, min(95, 50 + macro_sector_adj * 2.25))
        components['macro_regime_boost'] = data.get('macro_regime_boost', 50)

        # === FACTOR MODEL (6%) ===
        components['fama_value'] = data.get('fama_value', 50)
        components['fama_quality'] = data.get('fama_quality', 50)

        # === ESPECULATIVO ===

        components['congress_score'] = data.get('congress_score', 50)
        components['institutional_flow'] = data.get('institutional_flow', 50)

        # === NEW v6 — HORIZON-SPECIFIC MEDIUM-TERM SIGNALS ===
        # Drives MP differentiation. Fundamental momentum signals operate on
        # 3-12 month time scales. Default to 50 in batch; enriched per-ticker
        # via get_enriched_scores.
        components['analyst_revisions_score'] = data.get('analyst_revisions_score', 50)
        components['insider_cluster_score'] = data.get('insider_cluster_score', 50)
        components['earnings_streak_score'] = data.get('earnings_streak_score', 50)
        components['roic_trend_score'] = data.get('roic_trend_score', 50)
        components['sector_rotation_score'] = data.get('sector_rotation_score', 50)
        components['credit_risk_score'] = data.get('credit_risk_score', 50)

        # Apply professional macro regime overrides
        pro_regime = data.get('macro_regime', 'neutral')
        active_weights = apply_regime_overrides(weights, pro_regime, 'medium_term')

        # Score with effective-weight normalization + moderate amplifier
        total = _weighted_score(components, active_weights, amplifier=1.3)

        # Calcular confianza
        available = sum(1 for f in weights.keys() if f in components and components[f] != 50)
        confidence = (available / len(weights)) * 100

        explanation = self._generate_medium_term_explanation(components, total)

        return HorizonScore(
            horizon=Horizon.MEDIUM_TERM,
            total_score=round(total, 1),
            signal=self._get_signal(total, 'medium_term'),
            components=components,
            explanation=explanation,
            confidence=round(confidence, 1)
        )

    def calculate_long_term_score(
        self,
        data: Dict[str, Any],
        market_data: Optional[Dict] = None
    ) -> HorizonScore:
        """
        Calcula score de largo plazo (6+ meses).

        Factores principales:
        - Valoración (P/E, P/B, EV/EBITDA, FCF Yield)
        - Calidad (ROE, ROIC, Margins, Moat)
        - Estabilidad (Debt/EBITDA, Coverage, Dividends)
        """
        components = {}
        weights = self.weights[Horizon.LONG_TERM]

        # === VALUE ===

        # P/E Percentile (lower is better for value)
        pe = data.get('pe_ratio', 0)
        sector_pe_median = data.get('sector_pe_median', 20)
        if pe and pe > 0:
            pe_rel = pe / sector_pe_median if sector_pe_median else 1
            if pe_rel < 0.7:
                components['pe_percentile'] = 90  # Muy barato vs sector
            elif pe_rel < 0.9:
                components['pe_percentile'] = 75
            elif pe_rel < 1.1:
                components['pe_percentile'] = 55
            elif pe_rel < 1.3:
                components['pe_percentile'] = 40
            else:
                components['pe_percentile'] = 25  # Caro vs sector
        else:
            components['pe_percentile'] = 50

        # P/B Percentile
        pb = data.get('pb_ratio', 0)
        if pb:
            if pb < 1.5:
                components['pb_percentile'] = 80
            elif pb < 3:
                components['pb_percentile'] = 60
            elif pb < 5:
                components['pb_percentile'] = 40
            else:
                components['pb_percentile'] = 25
        else:
            components['pb_percentile'] = 50

        # EV/EBITDA
        ev_ebitda = data.get('ev_ebitda', 0)
        if ev_ebitda:
            if ev_ebitda < 8:
                components['ev_ebitda_percentile'] = 85
            elif ev_ebitda < 12:
                components['ev_ebitda_percentile'] = 70
            elif ev_ebitda < 16:
                components['ev_ebitda_percentile'] = 50
            elif ev_ebitda < 20:
                components['ev_ebitda_percentile'] = 35
            else:
                components['ev_ebitda_percentile'] = 20
        else:
            components['ev_ebitda_percentile'] = 50

        # FCF Yield
        fcf_yield = data.get('fcf_yield', 0)
        if fcf_yield > 8:
            components['fcf_yield'] = 90
        elif fcf_yield > 5:
            components['fcf_yield'] = 75
        elif fcf_yield > 3:
            components['fcf_yield'] = 55
        elif fcf_yield > 0:
            components['fcf_yield'] = 40
        else:
            components['fcf_yield'] = 20

        # PEG Ratio
        peg = data.get('peg_ratio', 0)
        if peg and peg > 0:
            if peg < 0.8:
                components['peg_ratio'] = 90
            elif peg < 1.2:
                components['peg_ratio'] = 70
            elif peg < 2:
                components['peg_ratio'] = 50
            else:
                components['peg_ratio'] = 30
        else:
            components['peg_ratio'] = 50

        # === QUALITY ===

        # ROE
        roe = data.get('roe', 0)
        if roe > 25:
            components['roe'] = 90
        elif roe > 18:
            components['roe'] = 75
        elif roe > 12:
            components['roe'] = 60
        elif roe > 5:
            components['roe'] = 40
        else:
            components['roe'] = 20

        # ROIC
        roic = data.get('roic', 0)
        if roic > 20:
            components['roic'] = 90
        elif roic > 15:
            components['roic'] = 75
        elif roic > 10:
            components['roic'] = 60
        elif roic > 5:
            components['roic'] = 40
        else:
            components['roic'] = 20

        # Margin Stability (std dev of margins over 5 years)
        margin_stability = data.get('margin_stability', 50)  # 0-100
        components['margin_stability'] = margin_stability

        # Moat Score (competitive advantage)
        moat = data.get('moat_score', 50)  # 0-100
        components['moat_score'] = moat

        # === STABILITY ===

        # Debt/EBITDA
        debt_ebitda = data.get('debt_ebitda', 0)
        if debt_ebitda < 0:
            components['debt_ebitda'] = 95  # Net cash
        elif debt_ebitda < 1.5:
            components['debt_ebitda'] = 85
        elif debt_ebitda < 2.5:
            components['debt_ebitda'] = 70
        elif debt_ebitda < 4:
            components['debt_ebitda'] = 50
        elif debt_ebitda < 6:
            components['debt_ebitda'] = 30
        else:
            components['debt_ebitda'] = 15

        # Interest Coverage
        coverage = data.get('interest_coverage', 0)
        if coverage > 20:
            components['interest_coverage'] = 90
        elif coverage > 10:
            components['interest_coverage'] = 75
        elif coverage > 5:
            components['interest_coverage'] = 60
        elif coverage > 2:
            components['interest_coverage'] = 40
        else:
            components['interest_coverage'] = 20

        # Dividend Stability
        div_growth_years = data.get('dividend_growth_years', 0)
        if div_growth_years >= 25:
            components['dividend_stability'] = 95  # Aristocrat
        elif div_growth_years >= 10:
            components['dividend_stability'] = 80
        elif div_growth_years >= 5:
            components['dividend_stability'] = 65
        elif div_growth_years > 0:
            components['dividend_stability'] = 45
        else:
            components['dividend_stability'] = 30

        # Earnings Stability
        earnings_stability = data.get('earnings_stability', 50)  # 0-100
        components['earnings_stability'] = earnings_stability

        # === PROFESSIONAL VARIABLES ===

        # FCF Quality: FCF / Net Income ratio
        components['fcf_quality'] = data.get('fcf_quality', 50)

        # VIX Regime context for long-term
        components['vix_regime'] = data.get('vix_regime', 50)

        # Mean reversion for LT (light weight)
        mom_6m_raw = data.get('momentum_6m', 0)
        if mom_6m_raw < -20:
            components['mean_reversion'] = 80  # Deep value opportunity
        elif mom_6m_raw < -10:
            components['mean_reversion'] = 65
        elif mom_6m_raw > 30:
            components['mean_reversion'] = 30  # Extended
        else:
            components['mean_reversion'] = 50

        # Sector RS — blended for LT
        sr = data.get('sector_rs', 50)
        components['sector_rs'] = max(10, min(90, (100 - sr) * 0.3 + sr * 0.7))

        # Short Interest
        si = data.get('short_interest', 0)
        if si > 20:
            components['short_interest'] = 70
        elif si > 10:
            components['short_interest'] = 55
        else:
            components['short_interest'] = 45

        # Quality Gate for LT
        roe_val = data.get('roe', 15)
        margin_val = data.get('profit_margin', 10)
        if roe_val > 20 and margin_val > 15:
            components['quality_gate'] = 85
        elif roe_val > 10:
            components['quality_gate'] = 60
        elif roe_val <= 0:
            components['quality_gate'] = 15
        else:
            components['quality_gate'] = 35

        # === MACRO OVERLAY (12%) ===
        components['macro_overlay'] = data.get('macro_composite', 50)
        macro_sector_adj = data.get('macro_sector_adj', 0)
        components['macro_sector_impact'] = max(5, min(95, 50 + macro_sector_adj * 2.25))
        components['macro_regime_boost'] = data.get('macro_regime_boost', 50)

        # === FACTOR MODEL (8%) ===
        components['fama_value'] = data.get('fama_value', 50)
        components['fama_quality'] = data.get('fama_quality', 50)

        # === ESPECULATIVO ===

        # Congress long-term (más peso a trades grandes)
        components['congress_long_term'] = data.get('congress_score', 50)

        # Insider Activity
        insider = data.get('insider_activity', 'neutral')
        if insider == 'heavy_buying':
            components['insider_activity'] = 85
        elif insider == 'buying':
            components['insider_activity'] = 70
        elif insider == 'selling':
            components['insider_activity'] = 35
        elif insider == 'heavy_selling':
            components['insider_activity'] = 20
        else:
            components['insider_activity'] = 50

        # === NEW v6 — HORIZON-SPECIFIC LONG-TERM SIGNALS ===
        # Structural / multi-year — drives LP differentiation. Default to 50
        # in batch; enriched per-ticker via get_enriched_scores.
        components['roic_trend_score'] = data.get('roic_trend_score', 50)
        components['debt_maturity_risk_score'] = data.get('debt_maturity_risk_score', 50)
        components['market_breadth_score'] = data.get('market_breadth_score', 50)
        components['sector_rotation_score'] = data.get('sector_rotation_score', 50)

        # Apply professional macro regime overrides
        pro_regime = data.get('macro_regime', 'neutral')
        active_weights = apply_regime_overrides(weights, pro_regime, 'long_term')

        # Score with effective-weight normalization + mild amplifier for long-term
        total = _weighted_score(components, active_weights, amplifier=1.2)

        # Calcular confianza
        available = sum(1 for f in weights.keys() if f in components and components[f] != 50)
        confidence = (available / len(weights)) * 100

        explanation = self._generate_long_term_explanation(components, total)

        return HorizonScore(
            horizon=Horizon.LONG_TERM,
            total_score=round(total, 1),
            signal=self._get_signal(total, 'long_term'),
            components=components,
            explanation=explanation,
            confidence=round(confidence, 1)
        )

    def _momentum_to_score(self, momentum: float, scale: float = 1.0) -> float:
        """
        Convierte % de momentum en score 0-100.

        Ajustado para ser más agresivo y generar scores más altos
        cuando hay momentum positivo fuerte, como en el Excel original.

        Ejemplos:
        - momentum -20% -> score ~15
        - momentum -10% -> score ~30
        - momentum 0%   -> score 50
        - momentum +10% -> score ~70
        - momentum +20% -> score ~85
        - momentum +30% -> score ~95
        """
        # More aggressive scaling: +/- 20% momentum = significant deviation from 50
        base = 50 + (momentum * scale * 2.0)
        return min(max(base, 5), 95)  # Cap at 5-95 to avoid extremes

    def _generate_short_term_explanation(self, components: Dict, score: float) -> str:
        """Genera explicación del score de corto plazo"""
        parts = []

        rsi = components.get('rsi', 50)
        if rsi > 70:
            parts.append("RSI en sobrecompra")
        elif rsi < 35:
            parts.append("RSI en sobreventa (oportunidad)")

        macd = components.get('macd', 50)
        if macd > 70:
            parts.append("MACD alcista")
        elif macd < 30:
            parts.append("MACD bajista")

        vp = components.get('volume_profile', 50)
        if vp > 70:
            parts.append("en soporte de Volume Profile")
        elif vp < 30:
            parts.append("en resistencia de Volume Profile")

        congress = components.get('congress_score', 50)
        if congress > 70:
            parts.append("compras de congresistas recientes")
        elif congress < 30:
            parts.append("ventas de congresistas recientes")

        konkorde = components.get('konkorde', 50)
        if konkorde > 75:
            parts.append("Konkorde: institucionales comprando")
        elif konkorde > 65:
            parts.append("Konkorde: acumulación institucional")
        elif konkorde < 35:
            parts.append("Konkorde: distribución institucional")
        elif konkorde < 25:
            parts.append("Konkorde: institucionales vendiendo")

        rsi_cross = components.get('rsi_crossover', 50)
        if rsi_cross > 75:
            parts.append("RSI cruzando desde sobreventa (señal alcista)")
        elif rsi_cross < 25:
            parts.append("RSI cruzando desde sobrecompra (señal bajista)")

        tl = components.get('trendline_breakout', 50)
        if tl > 80:
            parts.append("rompimiento de tendencia bajista confirmado")
        elif tl > 65:
            parts.append("precio cercano a romper tendencia bajista")

        konk_div = components.get('konkorde_divergence', 50)
        if konk_div > 70:
            parts.append("divergencia Konkorde: acumulación institucional oculta")
        elif konk_div < 30:
            parts.append("divergencia Konkorde: distribución institucional oculta")

        # Macro Overlay
        macro = components.get('macro_overlay', 50)
        macro_sect = components.get('macro_sector_impact', 50)
        if macro < 25:
            parts.append("MACRO: estrés extremo (VIX/oil/credit)")
        elif macro < 40:
            parts.append("MACRO: entorno de riesgo elevado")
        elif macro > 70:
            parts.append("MACRO: entorno favorable")
        if macro_sect < 25:
            parts.append("sector muy afectado por macro")
        elif macro_sect > 75:
            parts.append("sector beneficiado por entorno macro")

        if not parts:
            return "Señales técnicas mixtas"

        return "; ".join(parts)

    def _generate_medium_term_explanation(self, components: Dict, score: float) -> str:
        """Genera explicación del score de medio plazo"""
        parts = []

        mom = components.get('momentum_3m', 50)
        if mom > 70:
            parts.append("momentum fuerte a 3M")
        elif mom < 30:
            parts.append("momentum débil a 3M")

        revisions = components.get('analyst_revisions', 50)
        if revisions > 70:
            parts.append("revisiones de analistas al alza")
        elif revisions < 30:
            parts.append("revisiones a la baja")

        roe = components.get('roe', 50)
        if roe > 70:
            parts.append("ROE alto")

        trend = components.get('trend_strength', 50)
        if trend > 70:
            parts.append("tendencia alcista fuerte")
        elif trend < 30:
            parts.append("tendencia bajista")

        # Macro
        macro = components.get('macro_overlay', 50)
        if macro < 30:
            parts.append("MACRO: estrés alto — riesgo sistémico")
        elif macro < 45:
            parts.append("MACRO: cautela — entorno deteriorándose")
        elif macro > 70:
            parts.append("MACRO: entorno favorable")

        if not parts:
            return "Indicadores de medio plazo mixtos"

        return "; ".join(parts)

    def _generate_long_term_explanation(self, components: Dict, score: float) -> str:
        """Genera explicación del score de largo plazo"""
        parts = []

        # Value
        pe = components.get('pe_percentile', 50)
        ev = components.get('ev_ebitda_percentile', 50)
        fcf = components.get('fcf_yield', 50)

        if pe > 70 and ev > 70:
            parts.append("valoración atractiva")
        elif pe < 30 and ev < 30:
            parts.append("valoración cara")

        if fcf > 70:
            parts.append("FCF yield alto")

        # Quality
        roe = components.get('roe', 50)
        roic = components.get('roic', 50)
        if roe > 70 and roic > 70:
            parts.append("excelente rentabilidad")

        moat = components.get('moat_score', 50)
        if moat > 70:
            parts.append("ventaja competitiva sólida")

        # Stability
        debt = components.get('debt_ebitda', 50)
        if debt > 80:
            parts.append("bajo endeudamiento")
        elif debt < 30:
            parts.append("alto endeudamiento")

        div = components.get('dividend_stability', 50)
        if div > 80:
            parts.append("historial de dividendos estable")

        # Macro for LT (less weight but still mentioned)
        macro = components.get('macro_overlay', 50)
        if macro < 30:
            parts.append("MACRO: estrés sistémico — vigilar")
        elif macro > 70:
            parts.append("MACRO: estabilidad macro favorable")

        if not parts:
            return "Fundamentales mixtos para largo plazo"

        return "; ".join(parts)

    def calculate_all_horizons(
        self,
        data: Dict[str, Any],
        market_data: Optional[Dict] = None
    ) -> MultiHorizonResult:
        """
        Calcula scores para los tres horizontes.

        Args:
            data: Datos del stock (técnicos + fundamentales)
            market_data: Datos de mercado opcionales

        Returns:
            MultiHorizonResult con los tres scores
        """
        short = self.calculate_short_term_score(data, market_data)
        medium = self.calculate_medium_term_score(data, market_data)
        long = self.calculate_long_term_score(data, market_data)

        # Generar recomendación combinada
        recommendation = self._generate_combined_recommendation(short, medium, long)

        return MultiHorizonResult(
            ticker=data.get('ticker', ''),
            short_term=short,
            medium_term=medium,
            long_term=long,
            combined_recommendation=recommendation,
            timestamp=datetime.now()
        )

    def _generate_combined_recommendation(
        self,
        short: HorizonScore,
        medium: HorizonScore,
        long: HorizonScore
    ) -> str:
        """Genera recomendación combinada basada en los tres horizontes"""

        recommendations = []

        # Caso: Todos los horizontes alineados bullish
        if short.total_score >= 65 and medium.total_score >= 65 and long.total_score >= 65:
            recommendations.append("OPORTUNIDAD COMPLETA: Positivo en todos los horizontes")
            recommendations.append("Estrategia: Posición completa ahora, mantener largo plazo")

        # Caso: Corto plazo bueno, largo plazo malo
        elif short.total_score >= 65 and long.total_score < 45:
            recommendations.append("TRADE DE CORTO PLAZO: Setup técnico bueno pero fundamentales débiles")
            recommendations.append("Estrategia: Entrada táctica con stop ajustado, no mantener")

        # Caso: Largo plazo bueno, corto plazo malo
        elif long.total_score >= 65 and short.total_score < 45:
            recommendations.append("ACUMULACIÓN GRADUAL: Buenos fundamentales pero técnicos débiles")
            recommendations.append("Estrategia: Esperar mejor entrada técnica o ir acumulando lento")

        # Caso: Medio plazo destacado
        elif medium.total_score >= 70:
            recommendations.append(f"SWING TRADE: Medio plazo favorable ({medium.signal.value})")
            recommendations.append("Estrategia: Posición con horizonte 1-3 meses")

        # Caso: Todos los horizontes bajistas
        elif short.total_score < 40 and medium.total_score < 40 and long.total_score < 40:
            recommendations.append("EVITAR: Negativo en todos los horizontes")
            recommendations.append("Estrategia: No comprar, considerar short si hay posición")

        else:
            recommendations.append("SEÑALES MIXTAS: Horizontes no alineados")
            recommendations.append(f"CP: {short.signal.value} ({short.total_score:.0f}) | "
                                 f"MP: {medium.signal.value} ({medium.total_score:.0f}) | "
                                 f"LP: {long.signal.value} ({long.total_score:.0f})")

        return "\n".join(recommendations)


# Singleton
_scorer_instance = None

def get_scorer() -> MultiHorizonScorer:
    """Obtiene instancia del scorer"""
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = MultiHorizonScorer()
    return _scorer_instance


if __name__ == '__main__':
    # Test
    scorer = MultiHorizonScorer()

    # Datos de ejemplo para PG (Procter & Gamble)
    test_data = {
        'ticker': 'PG',
        'price': 151.00,

        # Técnicos
        'rsi_14': 42,
        'macd_signal': 'bullish',
        'volume_profile_position': 'at_support',
        'vwap': 150.50,
        'bollinger_position': 25,
        'trend_1w': 2.5,

        # Momentum
        'momentum_1w': 2.5,
        'momentum_1m': 5.2,
        'momentum_3m': 8.5,
        'momentum_6m': 12.0,
        'relative_strength_1m': 3.2,
        'analyst_revisions': 2.5,
        'earnings_surprise': 8.0,

        # Quality
        'roe': 31.58,
        'roic': 21.22,
        'margin_trend': 1.5,
        'debt_trend': -5,

        # Value
        'pe_ratio': 22.22,
        'sector_pe_median': 25.0,
        'pb_ratio': 6.67,
        'ev_ebitda': 15.93,
        'fcf_yield': 4.2,
        'peg_ratio': 1.8,

        # Stability
        'debt_ebitda': 1.8,
        'interest_coverage': 32.5,
        'dividend_growth_years': 67,  # Dividend King!
        'earnings_stability': 85,
        'margin_stability': 80,
        'moat_score': 85,

        # Speculative
        'congress_score': 72,
        'news_sentiment': 15,
        'insider_activity': 'neutral',
    }

    result = scorer.calculate_all_horizons(test_data)

    print("=" * 60)
    print(f"MULTI-HORIZON SCORING: {result.ticker}")
    print("=" * 60)

    print(f"\n[SHORT] CORTO PLAZO ({result.short_term.signal.value})")
    print(f"   Score: {result.short_term.total_score}/100")
    print(f"   Confianza: {result.short_term.confidence}%")
    print(f"   {result.short_term.explanation}")

    print(f"\n[MEDIUM] MEDIO PLAZO ({result.medium_term.signal.value})")
    print(f"   Score: {result.medium_term.total_score}/100")
    print(f"   Confianza: {result.medium_term.confidence}%")
    print(f"   {result.medium_term.explanation}")

    print(f"\n[LONG] LARGO PLAZO ({result.long_term.signal.value})")
    print(f"   Score: {result.long_term.total_score}/100")
    print(f"   Confianza: {result.long_term.confidence}%")
    print(f"   {result.long_term.explanation}")

    print(f"\n{'='*60}")
    print("RECOMENDACION COMBINADA:")
    print(result.combined_recommendation)
