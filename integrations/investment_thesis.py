#!/usr/bin/env python3
"""
===============================================================================
INVESTMENT THESIS GENERATOR - Tesis de Inversión Ultra-Detalladas
===============================================================================

Este módulo genera tesis de inversión completas con:
1. Drivers macroeconómicos (monetary plumbing)
2. Congress trades con links a fuentes
3. Correlaciones activas
4. Momentum técnico explicado
5. Recomendación de estrategia por horizonte temporal
6. Timing de entrada, stop loss, take profit
7. Links a todas las fuentes

USO:
    from integrations.investment_thesis import InvestmentThesisGenerator

    generator = InvestmentThesisGenerator()
    thesis = generator.generate_detailed_thesis(company_data, triggers, monetary)

===============================================================================
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import quote  # Para encoding correcto de URLs


# =============================================================================
# FUENTES DE DATOS Y LINKS
# =============================================================================

DATA_SOURCES = {
    'congress_house': {
        'name': 'House Stock Watcher',
        'base_url': 'https://housestockwatcher.com',
        'politician_url': 'https://housestockwatcher.com/summary_by_rep/{politician}',
        'ticker_url': 'https://housestockwatcher.com/summary_by_ticker/{ticker}',
    },
    'congress_senate': {
        'name': 'Senate Stock Watcher',
        'base_url': 'https://senatestockwatcher.com',
        'politician_url': 'https://senatestockwatcher.com/summary_by_rep/{politician}',
        'ticker_url': 'https://senatestockwatcher.com/summary_by_ticker/{ticker}',
    },
    'yahoo_finance': {
        'name': 'Yahoo Finance',
        'base_url': 'https://finance.yahoo.com',
        'quote_url': 'https://finance.yahoo.com/quote/{ticker}',
        'chart_url': 'https://finance.yahoo.com/quote/{ticker}/chart',
        'analysis_url': 'https://finance.yahoo.com/quote/{ticker}/analysis',
    },
    'polymarket': {
        'name': 'Polymarket',
        'base_url': 'https://polymarket.com',
        'markets_url': 'https://polymarket.com/markets',
    },
    'fred': {
        'name': 'FRED (Federal Reserve)',
        'base_url': 'https://fred.stlouisfed.org',
        'series_url': 'https://fred.stlouisfed.org/series/{series}',
    },
    'finviz': {
        'name': 'Finviz',
        'quote_url': 'https://finviz.com/quote.ashx?t={ticker}',
    },
}

# =============================================================================
# INTERPRETACIÓN DE MOMENTUM
# =============================================================================

MOMENTUM_INTERPRETATION = {
    'strong_bullish': {
        'range': (75, 100),
        'meaning': 'Momentum extremadamente fuerte',
        'action': 'El precio está en tendencia alcista clara. Considerar entrada.',
        'timing': 'Comprar en pullbacks hacia medias móviles (20 o 50 días)',
        'risk': 'Riesgo de corrección si momentum se agota',
    },
    'bullish': {
        'range': (60, 75),
        'meaning': 'Momentum positivo sostenido',
        'action': 'Tendencia alcista confirmada pero no sobreextendida.',
        'timing': 'Buen momento para construir posición gradualmente',
        'risk': 'Monitorear volumen para confirmar fuerza',
    },
    'neutral_bullish': {
        'range': (50, 60),
        'meaning': 'Momentum ligeramente positivo',
        'action': 'Tendencia indecisa, posible consolidación.',
        'timing': 'Esperar confirmación antes de entrar',
        'risk': 'Puede girar a bajista fácilmente',
    },
    'neutral_bearish': {
        'range': (40, 50),
        'meaning': 'Momentum ligeramente negativo',
        'action': 'Presión vendedora emergente.',
        'timing': 'No es momento de comprar, esperar',
        'risk': 'Puede acelerarse a la baja',
    },
    'bearish': {
        'range': (25, 40),
        'meaning': 'Momentum negativo sostenido',
        'action': 'Tendencia bajista clara. Evitar o cubrir.',
        'timing': 'No comprar hasta que momentum gire',
        'risk': 'Catch a falling knife',
    },
    'strong_bearish': {
        'range': (0, 25),
        'meaning': 'Momentum extremadamente negativo',
        'action': 'Capitulación en curso. ESPERAR.',
        'timing': 'Solo para traders de rebote (alto riesgo)',
        'risk': 'Puede seguir cayendo mucho más',
    },
}

# =============================================================================
# ESTRATEGIAS POR HORIZONTE TEMPORAL
# =============================================================================

STRATEGY_BY_HORIZON = {
    'short_term': {
        'name': 'Especulativo/Trading (1-30 días)',
        'best_signals': ['STRONG BUY'],
        'key_factors': ['momentum', 'congress', 'correlations'],
        'position_size': '2-5% de cartera',
        'stop_loss': '5-8% desde entrada',
        'take_profit': '10-20%',
        'description': 'Para capturar movimientos rápidos basados en catalizadores.',
        'when_use': [
            'Congress trade reciente de político top (Pelosi, Tuberville)',
            'Correlación activa fuerte (ej: oro subiendo → mineras)',
            'Momentum score > 70 con volumen',
            'Evento catalizador próximo (earnings, FDA, etc.)',
        ],
        'when_avoid': [
            'Mercado lateral sin dirección',
            'VIX elevado (>25) sin catalizador claro',
            'Sin triggers activos',
        ],
    },
    'medium_term': {
        'name': 'Swing/Position (1-6 meses)',
        'best_signals': ['STRONG BUY', 'BUY', 'ACCUMULATE'],
        'key_factors': ['quality', 'momentum', 'value', 'congress'],
        'position_size': '5-10% de cartera',
        'stop_loss': '12-18% desde entrada',
        'take_profit': '25-50%',
        'description': 'Balance entre riesgo y recompensa. Captura tendencias mayores.',
        'when_use': [
            'Score compuesto > 60 con múltiples factores fuertes',
            'Régimen monetario favorable (abundant liquidity)',
            'Empresa de calidad con momentum positivo',
            'Congress + correlación apuntando al mismo ticker',
        ],
        'when_avoid': [
            'Régimen de liquidez restrictiva',
            'Empresa con quality score < 40',
            'Sector en rotación negativa',
        ],
    },
    'long_term': {
        'name': 'Inversión Value-Quality (1-5 años)',
        'best_signals': ['STRONG BUY', 'BUY'],
        'key_factors': ['quality', 'value', 'lowvol'],
        'position_size': '10-20% de cartera',
        'stop_loss': 'Por fundamentales (no precio)',
        'take_profit': 'Mantener mientras tesis válida',
        'description': 'Compounding a largo plazo. Ignorar ruido corto plazo.',
        'when_use': [
            'Quality score > 70 (empresa dominante)',
            'Value score > 60 (no sobrevalorada)',
            'Moat competitivo claro',
            'Dividendos crecientes o buybacks',
        ],
        'when_avoid': [
            'Disrupción tecnológica amenazando el modelo',
            'Management cuestionable',
            'Deuda excesiva (debt/EBITDA > 4)',
        ],
    },
}


class InvestmentThesisGenerator:
    """Genera tesis de inversión ultra-detalladas."""

    def __init__(self):
        self.data_sources = DATA_SOURCES
        self.strategies = STRATEGY_BY_HORIZON

    def generate_detailed_thesis(
        self,
        company: Dict,
        triggers: List[Dict] = None,
        monetary_analysis: Dict = None,
        congress_data: Dict = None
    ) -> Dict:
        """
        Genera una tesis de inversión completa y detallada.

        Returns:
            Dict con tesis estructurada incluyendo:
            - summary: Resumen ejecutivo
            - recommended_strategy: Estrategia recomendada
            - drivers: Lista de drivers con explicación y links
            - entry_timing: Cuándo entrar
            - risk_management: Stop loss, position sizing
            - sources: Links a todas las fuentes
        """
        ticker = company.get('ticker', '')
        signal = company.get('signal', 'HOLD')
        score = company.get('composite_score', 50)

        # Generar cada sección
        drivers = self._generate_drivers(company, triggers, monetary_analysis, congress_data)
        strategy = self._recommend_strategy(company, triggers)
        timing = self._generate_timing(company, triggers)
        risk_mgmt = self._generate_risk_management(company, strategy)
        sources = self._generate_sources(ticker, triggers, congress_data)

        # Construir summary
        summary = self._generate_summary(company, drivers, strategy)

        # Tesis completa para Excel (texto largo)
        thesis_text = self._format_thesis_for_excel(
            company, summary, drivers, strategy, timing, risk_mgmt, sources
        )

        return {
            'ticker': ticker,
            'signal': signal,
            'score': score,
            'summary': summary,
            'recommended_strategy': strategy,
            'drivers': drivers,
            'entry_timing': timing,
            'risk_management': risk_mgmt,
            'sources': sources,
            'thesis_text': thesis_text,
            'thesis_short': summary,  # Para columna corta
        }

    def _generate_drivers(
        self,
        company: Dict,
        triggers: List[Dict],
        monetary: Dict,
        congress: Dict
    ) -> List[Dict]:
        """Genera lista de drivers con explicación detallada."""
        drivers = []
        ticker = company.get('ticker', '')

        # 1. MOMENTUM
        momentum_score = company.get('momentum_score', 50)
        momentum_interp = self._interpret_momentum(momentum_score)
        drivers.append({
            'category': 'MOMENTUM',
            'score': momentum_score,
            'interpretation': momentum_interp['meaning'],
            'action': momentum_interp['action'],
            'timing': momentum_interp['timing'],
            'risk': momentum_interp['risk'],
            'source': DATA_SOURCES['yahoo_finance']['chart_url'].format(ticker=ticker),
        })

        # 2. CONGRESS TRADES
        congress_score = company.get('congress_score', 50)
        if congress_score != 50 or (congress and congress.get('trades', 0) > 0):
            congress_driver = self._build_congress_driver(ticker, company, congress)
            drivers.append(congress_driver)

        # 3. CORRELACIONES (desde triggers)
        if triggers:
            for trigger in triggers:
                if trigger.get('type') == 'CORRELATION' and ticker in trigger.get('affected_tickers', []):
                    drivers.append({
                        'category': 'CORRELACIÓN',
                        'source_asset': trigger.get('source', ''),
                        'move': trigger.get('move', ''),
                        'direction': trigger.get('direction', ''),
                        'interpretation': trigger.get('rationale', ''),
                        'action': f"{ticker} se beneficia del movimiento en {trigger.get('source', '')}",
                        'strength': trigger.get('strength', 1),
                        'source': trigger.get('source_url', ''),
                    })

        # 4. MONETARY/MACRO
        if monetary:
            macro_driver = self._build_macro_driver(company, monetary)
            if macro_driver:
                drivers.append(macro_driver)

        # 5. QUALITY
        quality_score = company.get('quality_score', 50)
        if quality_score >= 65 or quality_score <= 35:
            drivers.append({
                'category': 'QUALITY',
                'score': quality_score,
                'interpretation': 'Alta calidad operativa' if quality_score >= 65 else 'Baja calidad operativa',
                'details': f"ROE: {company.get('roe', 'N/A')}, Margin: {company.get('op_margin', 'N/A')}",
                'source': DATA_SOURCES['yahoo_finance']['quote_url'].format(ticker=ticker),
            })

        # 6. VALUE
        value_score = company.get('value_score', 50)
        if value_score >= 65 or value_score <= 35:
            drivers.append({
                'category': 'VALUE',
                'score': value_score,
                'interpretation': 'Valoración atractiva' if value_score >= 65 else 'Valoración cara',
                'details': f"P/E: {company.get('fwd_pe', 'N/A')}, EV/EBITDA: {company.get('ev_ebitda', 'N/A')}",
                'source': DATA_SOURCES['yahoo_finance']['analysis_url'].format(ticker=ticker),
            })

        return drivers

    def _build_congress_driver(self, ticker: str, company: Dict, congress: Dict) -> Dict:
        """Construye driver de Congress con detalles."""
        congress_score = company.get('congress_score', 50)

        if congress and congress.get('trades', 0) > 0:
            politicians_buying = congress.get('politicians_buying', [])
            politicians_selling = congress.get('politicians_selling', [])

            details = []
            if politicians_buying:
                details.append(f"COMPRANDO: {', '.join(politicians_buying[:3])}")
            if politicians_selling:
                details.append(f"VENDIENDO: {', '.join(politicians_selling[:3])}")

            return {
                'category': 'CONGRESS',
                'score': congress_score,
                'signal': congress.get('signal', 'NEUTRAL'),
                'interpretation': 'Congresistas comprando' if congress_score > 55 else
                                 ('Congresistas vendiendo' if congress_score < 45 else 'Actividad mixta'),
                'details': '; '.join(details) if details else 'Sin actividad reciente',
                'total_trades': congress.get('trades', 0),
                'confidence': congress.get('confidence', 'LOW'),
                'source': DATA_SOURCES['congress_house']['ticker_url'].format(ticker=ticker),
            }
        else:
            return {
                'category': 'CONGRESS',
                'score': 50,
                'signal': 'NO_DATA',
                'interpretation': 'Sin trades de congresistas detectados',
                'details': '',
                'source': DATA_SOURCES['congress_house']['ticker_url'].format(ticker=ticker),
            }

    def _build_macro_driver(self, company: Dict, monetary: Dict) -> Optional[Dict]:
        """Construye driver macroeconómico."""
        regime = monetary.get('liquidity_regime', 'NEUTRAL')
        net_liq_change = monetary.get('net_liquidity_change_30d', 0)
        risk_appetite = monetary.get('risk_appetite', 'NEUTRAL')

        # Determinar impacto según sector/tipo de acción
        ticker = company.get('ticker', '')
        sector = company.get('sector', '')

        # Acciones risk-on vs risk-off
        risk_on_tickers = ['NVDA', 'TSLA', 'AMD', 'ARKK', 'COIN', 'MSTR', 'NIO', 'XPEV']
        risk_off_tickers = ['JNJ', 'PG', 'KO', 'WMT', 'COST', 'GLD', 'TLT']

        is_risk_on = ticker in risk_on_tickers or sector in ['Technology', 'Crypto']
        is_risk_off = ticker in risk_off_tickers or sector in ['Consumer Defensive', 'Healthcare']

        impact = 'NEUTRAL'
        interpretation = ''

        if regime == 'ABUNDANT_LIQUIDITY':
            if is_risk_on:
                impact = 'FAVORABLE'
                interpretation = 'Liquidez abundante favorece activos de riesgo como este'
            elif is_risk_off:
                impact = 'NEUTRAL'
                interpretation = 'Liquidez abundante pero defensivos menos atractivos'
            else:
                impact = 'FAVORABLE'
                interpretation = 'Liquidez abundante generalmente positiva para renta variable'
        elif regime == 'TIGHT_LIQUIDITY':
            if is_risk_on:
                impact = 'DESFAVORABLE'
                interpretation = 'Liquidez restrictiva daña activos de riesgo'
            elif is_risk_off:
                impact = 'FAVORABLE'
                interpretation = 'Liquidez restrictiva favorece defensivos'
            else:
                impact = 'DESFAVORABLE'
                interpretation = 'Liquidez restrictiva presiona renta variable'
        else:
            impact = 'NEUTRAL'
            interpretation = 'Régimen de liquidez neutral, sin sesgo claro'

        return {
            'category': 'MACRO/MONETARY',
            'regime': regime,
            'net_liquidity_change': f"${net_liq_change:.0f}B (30d)",
            'risk_appetite': risk_appetite,
            'impact': impact,
            'interpretation': interpretation,
            'source': DATA_SOURCES['fred']['series_url'].format(series='WALCL'),
        }

    def _interpret_momentum(self, score: float) -> Dict:
        """Interpreta el momentum score."""
        for key, config in MOMENTUM_INTERPRETATION.items():
            low, high = config['range']
            if low <= score <= high:
                return config
        return MOMENTUM_INTERPRETATION['neutral_bullish']

    def _recommend_strategy(self, company: Dict, triggers: List[Dict]) -> Dict:
        """Recomienda estrategia según datos."""
        signal = company.get('signal', 'HOLD')
        score = company.get('composite_score', 50)
        momentum = company.get('momentum_score', 50)
        quality = company.get('quality_score', 50)
        congress = company.get('congress_score', 50)

        # Contar triggers
        has_congress_trigger = any(t.get('type') == 'CONGRESS_TRADE' for t in (triggers or []))
        has_correlation_trigger = any(t.get('type') == 'CORRELATION' for t in (triggers or []))

        # Determinar estrategia
        if signal in ['STRONG BUY', 'BUY'] and momentum > 65 and (has_congress_trigger or has_correlation_trigger):
            recommended = 'short_term'
            rationale = 'Triggers activos + momentum fuerte = oportunidad de trading'
        elif signal in ['STRONG BUY', 'BUY'] and quality > 60 and score > 60:
            recommended = 'medium_term'
            rationale = 'Calidad + score alto = buena posición swing'
        elif quality > 70 and company.get('value_score', 50) > 60:
            recommended = 'long_term'
            rationale = 'Alta calidad + valoración razonable = inversión largo plazo'
        elif signal in ['STRONG BUY', 'BUY', 'ACCUMULATE']:
            recommended = 'medium_term'
            rationale = 'Señal positiva, horizonte medio por defecto'
        else:
            recommended = None
            rationale = 'No hay oportunidad clara de compra'

        if recommended:
            strategy = self.strategies[recommended].copy()
            strategy['rationale'] = rationale
            return strategy
        else:
            return {
                'name': 'NO TRADE',
                'rationale': rationale,
                'description': 'Esperar mejores condiciones o setup más claro',
            }

    def _generate_timing(self, company: Dict, triggers: List[Dict]) -> Dict:
        """Genera recomendación de timing."""
        momentum = company.get('momentum_score', 50)
        signal = company.get('signal', 'HOLD')

        # Timing basado en momentum y triggers
        if signal in ['STRONG BUY'] and momentum > 70:
            entry = "INMEDIATO - Momentum fuerte, no esperar"
            condition = "Entrada a mercado o límite cercano al precio actual"
        elif signal in ['BUY'] and momentum > 60:
            entry = "PRÓXIMOS DÍAS - Buscar pullback menor"
            condition = "Esperar retroceso del 2-3% hacia media de 20 días"
        elif signal in ['ACCUMULATE']:
            entry = "GRADUAL - Construir posición en varias compras"
            condition = "Comprar 1/3 ahora, 1/3 en pullback, 1/3 en confirmación"
        else:
            entry = "ESPERAR - No hay setup claro"
            condition = "Esperar señal más fuerte o catalizador"

        # Catalizadores próximos
        catalysts = []
        if triggers:
            for t in triggers:
                if t.get('type') == 'CONGRESS_TRADE':
                    catalysts.append(f"Congress trade de {t.get('politician', 'N/A')} ({t.get('date', 'N/A')})")
                elif t.get('type') == 'CORRELATION':
                    catalysts.append(f"{t.get('source', 'N/A')} {t.get('direction', '')} {t.get('move', '')}")

        return {
            'entry_recommendation': entry,
            'entry_condition': condition,
            'catalysts': catalysts,
        }

    def _generate_risk_management(self, company: Dict, strategy: Dict) -> Dict:
        """Genera parámetros de gestión de riesgo."""
        price = company.get('price', 0)

        strategy_name = strategy.get('name', 'medium_term')

        # Stop loss según estrategia
        if 'Especulativo' in strategy_name or 'short' in strategy_name.lower():
            stop_pct = 0.06  # 6%
            target_pct = 0.15  # 15%
            position = "2-5% de cartera"
        elif 'Swing' in strategy_name or 'medium' in strategy_name.lower():
            stop_pct = 0.12  # 12%
            target_pct = 0.30  # 30%
            position = "5-10% de cartera"
        elif 'Value' in strategy_name or 'long' in strategy_name.lower():
            stop_pct = 0.20  # 20% o fundamentales
            target_pct = 0.50  # 50%+
            position = "10-20% de cartera"
        else:
            stop_pct = 0.10
            target_pct = 0.20
            position = "5% de cartera (conservador)"

        stop_price = price * (1 - stop_pct) if price else None
        target_price = price * (1 + target_pct) if price else None

        return {
            'position_size': position,
            'stop_loss_pct': f"{stop_pct*100:.0f}%",
            'stop_loss_price': f"${stop_price:.2f}" if stop_price else "N/A",
            'take_profit_pct': f"{target_pct*100:.0f}%",
            'take_profit_price': f"${target_price:.2f}" if target_price else "N/A",
            'risk_reward': f"1:{target_pct/stop_pct:.1f}",
        }

    def _generate_sources(self, ticker: str, triggers: List[Dict], congress: Dict) -> List[Dict]:
        """Genera lista de fuentes con links."""
        sources = []

        # Yahoo Finance
        sources.append({
            'name': 'Yahoo Finance - Quote',
            'url': DATA_SOURCES['yahoo_finance']['quote_url'].format(ticker=ticker),
            'description': 'Precio, fundamentales, news',
        })
        sources.append({
            'name': 'Yahoo Finance - Chart',
            'url': DATA_SOURCES['yahoo_finance']['chart_url'].format(ticker=ticker),
            'description': 'Gráfico técnico interactivo',
        })
        sources.append({
            'name': 'Yahoo Finance - Analysis',
            'url': DATA_SOURCES['yahoo_finance']['analysis_url'].format(ticker=ticker),
            'description': 'Estimaciones analistas, earnings',
        })

        # Finviz
        sources.append({
            'name': 'Finviz',
            'url': DATA_SOURCES['finviz']['quote_url'].format(ticker=ticker),
            'description': 'Screener, gráfico, métricas',
        })

        # Congress
        sources.append({
            'name': 'House Stock Watcher',
            'url': DATA_SOURCES['congress_house']['ticker_url'].format(ticker=ticker),
            'description': 'Trades de congresistas (House)',
        })
        sources.append({
            'name': 'Senate Stock Watcher',
            'url': DATA_SOURCES['congress_senate']['ticker_url'].format(ticker=ticker),
            'description': 'Trades de senadores',
        })

        # FRED para macro
        sources.append({
            'name': 'FRED - Fed Balance Sheet',
            'url': DATA_SOURCES['fred']['series_url'].format(series='WALCL'),
            'description': 'Balance Fed (liquidez)',
        })

        # Triggers sources
        if triggers:
            for t in triggers:
                if t.get('source_url'):
                    sources.append({
                        'name': f"Trigger: {t.get('type', '')} - {t.get('source', '')}",
                        'url': t.get('source_url'),
                        'description': t.get('rationale', ''),
                    })

        return sources

    def _generate_summary(self, company: Dict, drivers: List[Dict], strategy: Dict) -> str:
        """Genera resumen ejecutivo."""
        ticker = company.get('ticker', '')
        signal = company.get('signal', 'HOLD')
        score = company.get('composite_score', 50)
        price = company.get('price', 0)

        # Construir resumen
        parts = []

        # Señal principal
        signal_text = {
            'STRONG BUY': 'COMPRA FUERTE',
            'BUY': 'COMPRA',
            'ACCUMULATE': 'ACUMULAR',
            'HOLD': 'MANTENER',
            'REDUCE': 'REDUCIR',
            'SELL': 'VENDER',
        }.get(signal, signal)

        parts.append(f"{signal_text} {ticker} (Score: {score:.0f}/100)")

        # Estrategia
        if strategy.get('name') and strategy.get('name') != 'NO TRADE':
            parts.append(f"Estrategia: {strategy.get('name', 'N/A')}")

        # Top drivers
        top_drivers = []
        for d in drivers[:3]:
            cat = d.get('category', '')
            if cat == 'CONGRESS' and d.get('score', 50) != 50:
                top_drivers.append(d.get('details', 'Congress activo'))
            elif cat == 'CORRELACIÓN':
                top_drivers.append(f"{d.get('source_asset', '')} {d.get('move', '')}")
            elif cat == 'MOMENTUM' and d.get('score', 50) > 60:
                top_drivers.append(f"Momentum fuerte ({d.get('score', 0):.0f})")
            elif cat == 'MACRO/MONETARY' and d.get('impact') == 'FAVORABLE':
                top_drivers.append(f"Macro favorable: {d.get('regime', '')}")

        if top_drivers:
            parts.append(f"Drivers: {'; '.join(top_drivers)}")

        return ' | '.join(parts)

    def _format_thesis_for_excel(
        self,
        company: Dict,
        summary: str,
        drivers: List[Dict],
        strategy: Dict,
        timing: Dict,
        risk_mgmt: Dict,
        sources: List[Dict]
    ) -> str:
        """Formatea la tesis completa para la celda de Excel."""
        ticker = company.get('ticker', '')
        signal = company.get('signal', 'HOLD')
        score = company.get('composite_score', 50)

        lines = []

        # Header
        lines.append(f"=== TESIS DE INVERSIÓN: {ticker} ===")
        lines.append(f"Señal: {signal} | Score: {score:.0f}/100")
        lines.append("")

        # Estrategia recomendada
        if strategy.get('name'):
            lines.append(f"ESTRATEGIA RECOMENDADA: {strategy.get('name', 'N/A')}")
            lines.append(f"  Razón: {strategy.get('rationale', '')}")
            lines.append(f"  Holding: {strategy.get('holding_period', 'N/A') if 'holding_period' in strategy else 'Variable'}")
            lines.append("")

        # Drivers
        lines.append("DRIVERS CLAVE:")
        for d in drivers:
            cat = d.get('category', '')
            lines.append(f"  [{cat}]")
            lines.append(f"    - Score: {d.get('score', 'N/A')}")
            lines.append(f"    - {d.get('interpretation', d.get('action', 'N/A'))}")
            if d.get('details'):
                lines.append(f"    - Detalles: {d.get('details')}")
            if d.get('source'):
                lines.append(f"    - Fuente: {d.get('source')}")
        lines.append("")

        # Timing
        lines.append("TIMING:")
        lines.append(f"  Entrada: {timing.get('entry_recommendation', 'N/A')}")
        lines.append(f"  Condición: {timing.get('entry_condition', 'N/A')}")
        if timing.get('catalysts'):
            lines.append(f"  Catalizadores: {', '.join(timing.get('catalysts', []))}")
        lines.append("")

        # Risk Management
        lines.append("GESTIÓN DE RIESGO:")
        lines.append(f"  Posición: {risk_mgmt.get('position_size', 'N/A')}")
        lines.append(f"  Stop Loss: {risk_mgmt.get('stop_loss_price', 'N/A')} ({risk_mgmt.get('stop_loss_pct', 'N/A')})")
        lines.append(f"  Take Profit: {risk_mgmt.get('take_profit_price', 'N/A')} ({risk_mgmt.get('take_profit_pct', 'N/A')})")
        lines.append(f"  Riesgo/Beneficio: {risk_mgmt.get('risk_reward', 'N/A')}")
        lines.append("")

        # Sources
        lines.append("FUENTES:")
        for s in sources[:5]:  # Limitar a 5 fuentes principales
            lines.append(f"  - {s.get('name', '')}: {s.get('url', '')}")

        return '\n'.join(lines)


# =============================================================================
# FUNCIÓN DE CONVENIENCIA
# =============================================================================

def generate_thesis_batch(
    companies: List[Dict],
    triggers_by_ticker: Dict[str, List[Dict]] = None,
    monetary_analysis: Dict = None,
    congress_signals: Dict[str, Dict] = None
) -> Dict[str, Dict]:
    """
    Genera tesis para múltiples empresas.

    Returns:
        Dict {ticker: thesis_dict}
    """
    generator = InvestmentThesisGenerator()
    results = {}

    triggers_by_ticker = triggers_by_ticker or {}
    congress_signals = congress_signals or {}

    for company in companies:
        ticker = company.get('ticker', '')
        triggers = triggers_by_ticker.get(ticker, [])
        congress = congress_signals.get(ticker, {})

        thesis = generator.generate_detailed_thesis(
            company=company,
            triggers=triggers,
            monetary_analysis=monetary_analysis,
            congress_data=congress
        )
        results[ticker] = thesis

    return results


if __name__ == '__main__':
    # Test
    test_company = {
        'ticker': 'NVDA',
        'signal': 'STRONG BUY',
        'composite_score': 78,
        'price': 850,
        'momentum_score': 82,
        'quality_score': 75,
        'value_score': 45,
        'congress_score': 70,
        'lowvol_score': 40,
    }

    test_triggers = [{
        'type': 'CONGRESS_TRADE',
        'politician': 'Nancy Pelosi',
        'ticker': 'NVDA',
        'action': 'BUY',
        'date': '2024-12-15',
        'is_top_politician': True,
        'source_url': 'https://housestockwatcher.com/summary_by_rep/Nancy%20Pelosi',
    }]

    test_monetary = {
        'liquidity_regime': 'ABUNDANT_LIQUIDITY',
        'net_liquidity_change_30d': 150,
        'risk_appetite': 'RISK_ON',
    }

    test_congress = {
        'signal': 'BULLISH',
        'score': 70,
        'trades': 1,
        'politicians_buying': ['Nancy Pelosi'],
        'politicians_selling': [],
        'confidence': 'MEDIUM',
    }

    generator = InvestmentThesisGenerator()
    thesis = generator.generate_detailed_thesis(
        test_company, test_triggers, test_monetary, test_congress
    )

    print("=== SUMMARY ===")
    print(thesis['summary'])
    print("\n=== THESIS TEXT ===")
    print(thesis['thesis_text'])
