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

SHORT_TERM_WEIGHTS = {
    # Factores técnicos (45%)
    'rsi': 0.10,
    'macd': 0.08,
    'volume_profile': 0.08,
    'vwap_position': 0.06,
    'bollinger_position': 0.05,
    'short_term_trend': 0.05,
    'konkorde': 0.08,  # NEW: Institutional vs Retail flow

    # Momentum (25%)
    'momentum_1w': 0.08,
    'momentum_1m': 0.10,
    'relative_strength': 0.07,

    # Factores especulativos (25%)
    'congress_score': 0.12,
    'news_sentiment': 0.08,
    'options_flow': 0.05,
}

MEDIUM_TERM_WEIGHTS = {
    # Momentum (40%)
    'momentum_3m': 0.15,
    'momentum_6m': 0.10,
    'analyst_revisions': 0.10,
    'earnings_momentum': 0.05,

    # Quality (30%)
    'roe': 0.08,
    'roic': 0.08,
    'margin_trend': 0.07,
    'debt_trend': 0.07,

    # Técnico (20%)
    'trend_strength': 0.08,
    'support_resistance': 0.07,
    'sector_rotation': 0.05,

    # Especulativo (10%)
    'congress_score': 0.05,
    'institutional_flow': 0.05,
}

LONG_TERM_WEIGHTS = {
    # Value (35%)
    'pe_percentile': 0.08,
    'pb_percentile': 0.05,
    'ev_ebitda_percentile': 0.08,
    'fcf_yield': 0.08,
    'peg_ratio': 0.06,

    # Quality (35%)
    'roe': 0.08,
    'roic': 0.10,
    'margin_stability': 0.08,
    'moat_score': 0.09,

    # Stability (20%)
    'debt_ebitda': 0.08,
    'interest_coverage': 0.05,
    'dividend_stability': 0.04,
    'earnings_stability': 0.03,

    # Especulativo (10%)
    'congress_long_term': 0.05,
    'insider_activity': 0.05,
}


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

    def _get_signal(self, score: float) -> Signal:
        """
        Convierte score en señal - umbrales alineados con Excel original.

        Original Excel thresholds:
        - STRONG BUY: Score >= 60 AND Upside >= 10%
        - BUY: Score >= 60 AND Upside >= 0%
        - ACCUMULATE: Score >= 50
        - HOLD: Score 40-50
        - REDUCE: Score 30-40
        - SELL: Score < 30
        """
        if score >= 60:
            return Signal.STRONG_BUY
        elif score >= 55:
            return Signal.BUY
        elif score >= 50:
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

        # === FACTORES DE MOMENTUM ===

        # Momentum 1 semana
        mom_1w = data.get('momentum_1w', 0)
        components['momentum_1w'] = self._momentum_to_score(mom_1w)

        # Momentum 1 mes
        mom_1m = data.get('momentum_1m', 0)
        components['momentum_1m'] = self._momentum_to_score(mom_1m)

        # Relative Strength vs SPY
        rs = data.get('relative_strength_1m', 0)
        if rs > 5:
            components['relative_strength'] = 80
        elif rs > 0:
            components['relative_strength'] = 65
        elif rs > -5:
            components['relative_strength'] = 45
        else:
            components['relative_strength'] = 30

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

        # Calcular score total
        total = 0
        for factor, weight in weights.items():
            if factor in components:
                total += components[factor] * weight

        # Calcular confianza basada en disponibilidad de datos
        available = sum(1 for f in weights.keys() if f in components and components[f] != 50)
        confidence = (available / len(weights)) * 100

        # Generar explicación
        explanation = self._generate_short_term_explanation(components, total)

        return HorizonScore(
            horizon=Horizon.SHORT_TERM,
            total_score=round(total, 1),
            signal=self._get_signal(total),
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

        # === MOMENTUM ===

        # Momentum 3 meses
        mom_3m = data.get('momentum_3m', 0)
        components['momentum_3m'] = self._momentum_to_score(mom_3m, scale=1.5)

        # Momentum 6 meses
        mom_6m = data.get('momentum_6m', 0)
        components['momentum_6m'] = self._momentum_to_score(mom_6m, scale=1.2)

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

        # === ESPECULATIVO ===

        components['congress_score'] = data.get('congress_score', 50)
        components['institutional_flow'] = data.get('institutional_flow', 50)

        # Calcular score total
        total = 0
        for factor, weight in weights.items():
            if factor in components:
                total += components[factor] * weight

        # Calcular confianza
        available = sum(1 for f in weights.keys() if f in components and components[f] != 50)
        confidence = (available / len(weights)) * 100

        explanation = self._generate_medium_term_explanation(components, total)

        return HorizonScore(
            horizon=Horizon.MEDIUM_TERM,
            total_score=round(total, 1),
            signal=self._get_signal(total),
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

        # Calcular score total
        total = 0
        for factor, weight in weights.items():
            if factor in components:
                total += components[factor] * weight

        # Calcular confianza
        available = sum(1 for f in weights.keys() if f in components and components[f] != 50)
        confidence = (available / len(weights)) * 100

        explanation = self._generate_long_term_explanation(components, total)

        return HorizonScore(
            horizon=Horizon.LONG_TERM,
            total_score=round(total, 1),
            signal=self._get_signal(total),
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
