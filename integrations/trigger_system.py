#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
TRIGGER SYSTEM - Descubrimiento Automático de Oportunidades
═══════════════════════════════════════════════════════════════════════════════

Este módulo detecta TRIGGERS que justifican analizar una acción:
1. Congress Trades: Pelosi, Tuberville compran algo → trigger
2. Correlaciones: Oro sube → analizar miners, etc.
3. Noticias virales: Detección de market-moving events
4. Fontanería Monetaria: Cambios en liquidez → sectores específicos

IMPORTANTE: No analizamos acciones al azar. Cada acción debe tener un TRIGGER.
═══════════════════════════════════════════════════════════════════════════════
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from urllib.parse import quote  # Para encoding correcto de URLs

# Importar base de datos local
try:
    from integrations.signal_database import SignalDatabase
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Importar congress tracker
try:
    from integrations.congress_tracker import CongressTracker
    CONGRESS_TRACKER_AVAILABLE = True
except ImportError:
    CONGRESS_TRACKER_AVAILABLE = False

# =============================================================================
# CORRELACIONES CONOCIDAS (Basadas en relaciones históricas)
# =============================================================================

CORRELATIONS = {
    # Cuando X sube, analizar Y (thresholds reducidos para mayor sensibilidad)
    'GLD': {  # Oro
        'positive': ['NEM', 'GOLD', 'AEM', 'GFI', 'FNV', 'WPM', 'AU'],
        'negative': ['JPM', 'GS', 'MS'],
        'threshold': 0.015,  # 1.5% (antes 3%)
        'rationale': 'Oro sube → miners se benefician por apalancamiento operativo',
        'source_url': 'https://finance.yahoo.com/quote/GLD'
    },
    'USO': {  # Petróleo
        'positive': ['XOM', 'CVX', 'COP', 'PBR', 'TTE', 'SHEL', 'BP', 'SU', 'EC'],
        'negative': ['AAL', 'DAL', 'UAL', 'LUV'],
        'threshold': 0.025,  # 2.5% (antes 5%)
        'rationale': 'Petróleo sube → productores ganan, consumidores pierden',
        'source_url': 'https://finance.yahoo.com/quote/USO'
    },
    'TLT': {  # Bonos largos
        'positive': ['XLU', 'VNQ', 'O', 'PLD', 'AMT', 'EQIX'],
        'negative': ['XLF', 'JPM', 'BAC', 'C', 'WFC'],
        'threshold': 0.01,  # 1% (antes 2%)
        'rationale': 'Rates bajan → REITs/Utilities atractivos, banks sufren',
        'source_url': 'https://finance.yahoo.com/quote/TLT'
    },
    'UUP': {  # Dólar
        'positive': ['WMT', 'COST', 'PG'],
        'negative': ['AAPL', 'MSFT', 'GOOGL', 'KO', 'NKE'],
        'threshold': 0.01,  # 1% (antes 1.5%)
        'rationale': 'Dólar fuerte → exportadores pierden, importadores ganan',
        'source_url': 'https://finance.yahoo.com/quote/UUP'
    },
    'COPX': {  # Cobre
        'positive': ['FCX', 'SCCO', 'BHP', 'RIO', 'TECK', 'VALE'],
        'negative': [],
        'threshold': 0.02,  # 2% (antes 4%)
        'rationale': 'Cobre sube → mineras de cobre se benefician',
        'source_url': 'https://finance.yahoo.com/quote/COPX'
    },
    'URA': {  # Uranio
        'positive': ['CCJ', 'UEC', 'UUUU', 'CEG', 'VST'],
        'negative': [],
        'threshold': 0.025,  # 2.5% (antes 5%)
        'rationale': 'Uranio sube → productores y utilities nucleares ganan',
        'source_url': 'https://finance.yahoo.com/quote/URA'
    },
    '^VIX': {  # Volatilidad
        'positive': ['GLD', 'TLT', 'JNJ', 'PG', 'KO'],
        'negative': ['ARKK', 'NVDA', 'TSLA', 'COIN', 'MSTR'],
        'threshold': 0.10,  # 10% (antes 20%)
        'rationale': 'VIX sube → flight to quality, vender high beta',
        'source_url': 'https://finance.yahoo.com/quote/%5EVIX'
    },
    'SMH': {  # Semiconductores
        'positive': ['NVDA', 'AMD', 'TSM', 'ASML', 'AVGO', 'QCOM', 'MU'],
        'negative': [],
        'threshold': 0.015,  # 1.5% (antes 3%)
        'rationale': 'Sector semiconductores en rally → analizar líderes',
        'source_url': 'https://finance.yahoo.com/quote/SMH'
    },
    'FXI': {  # China ETF
        'positive': ['BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'LI', 'XPEV', 'TCEHY'],
        'negative': [],
        'threshold': 0.02,  # 2%
        'rationale': 'China rallying → tech China se beneficia',
        'source_url': 'https://finance.yahoo.com/quote/FXI'
    },
    'XLE': {  # Energía
        'positive': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PXD'],
        'negative': [],
        'threshold': 0.015,  # 1.5%
        'rationale': 'Sector energía en rally → analizar majors',
        'source_url': 'https://finance.yahoo.com/quote/XLE'
    },
    'XLF': {  # Financieras
        'positive': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C'],
        'negative': [],
        'threshold': 0.015,  # 1.5%
        'rationale': 'Sector financiero subiendo → analizar bancos',
        'source_url': 'https://finance.yahoo.com/quote/XLF'
    },
}

# =============================================================================
# TRIGGERS POR FONTANERÍA MONETARIA
# =============================================================================

MONETARY_TRIGGERS = {
    'LIQUIDITY_SURGE': {
        # Cuando Net Liquidity sube significativamente
        'favor': ['QQQ', 'ARKK', 'NVDA', 'TSLA', 'COIN', 'MSTR'],  # Risk-on
        'avoid': ['TLT', 'GLD', 'JNJ', 'PG'],  # Defensivos menos atractivos
        'rationale': 'Liquidez abundante favorece activos de riesgo'
    },
    'LIQUIDITY_DRAIN': {
        # Cuando Net Liquidity baja (QT, TGA sube, etc.)
        'favor': ['JNJ', 'PG', 'KO', 'WMT', 'COST', 'GLD'],  # Defensivos
        'avoid': ['ARKK', 'COIN', 'MSTR', 'GME', 'AMC'],  # Especulativos
        'rationale': 'Drenaje de liquidez → huir de especulativos'
    },
    'TGA_BUILD': {
        # Treasury General Account aumentando (drena liquidez)
        'favor': ['TLT', 'GLD', 'UUP'],  # Safe assets
        'avoid': ['SPY', 'QQQ', 'IWM'],  # Índices bajo presión
        'rationale': 'TGA build drena reservas bancarias'
    },
    'RRP_DROP': {
        # Reverse Repo bajando (liquidez entrando al mercado)
        'favor': ['SPY', 'QQQ', 'IWM', 'NVDA', 'META'],
        'avoid': [],
        'rationale': 'RRP bajando = liquidez buscando retorno'
    },
}

# =============================================================================
# POLÍTICOS CON MEJOR TRACK RECORD
# =============================================================================

TOP_POLITICIANS = [
    {'name': 'Nancy Pelosi', 'track_record': 0.65, 'avg_return': 0.45},
    {'name': 'Tommy Tuberville', 'track_record': 0.58, 'avg_return': 0.32},
    {'name': 'Dan Crenshaw', 'track_record': 0.55, 'avg_return': 0.28},
    {'name': 'Josh Gottheimer', 'track_record': 0.54, 'avg_return': 0.25},
    {'name': 'Brian Mast', 'track_record': 0.52, 'avg_return': 0.22},
]


class TriggerSystem:
    """Sistema de detección de triggers para descubrir oportunidades."""

    def __init__(self):
        self.triggered_stocks = {}  # {ticker: [list of triggers]}
        self.correlation_alerts = []
        self.congress_alerts = []
        self.monetary_alerts = []

    def scan_correlations(self, lookback_days: int = 5) -> List[Dict]:
        """
        Escanea movimientos en activos correlacionados.
        Retorna lista de triggers encontrados.
        """
        triggers = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days + 5)

        print("  Escaneando correlaciones de mercado...")

        for base_ticker, config in CORRELATIONS.items():
            try:
                # Obtener datos del activo base
                data = yf.download(base_ticker, start=start_date, end=end_date,
                                   progress=False)
                if data.empty or len(data) < 2:
                    continue

                # Calcular retorno reciente
                recent_return = (data['Close'].iloc[-1] / data['Close'].iloc[-lookback_days] - 1)

                # Check threshold
                threshold = config['threshold']

                if abs(recent_return) >= threshold:
                    direction = 'UP' if recent_return > 0 else 'DOWN'
                    affected = config['positive'] if recent_return > 0 else config['negative']

                    trigger = {
                        'type': 'CORRELATION',
                        'source': base_ticker,
                        'move': f"{recent_return*100:.1f}%",
                        'direction': direction,
                        'affected_tickers': affected,
                        'rationale': config['rationale'],
                        'timestamp': datetime.now().isoformat(),
                        'strength': min(abs(recent_return) / threshold, 3.0),
                        'source_url': config.get('source_url', f'https://finance.yahoo.com/quote/{base_ticker}')
                    }
                    triggers.append(trigger)

                    # Añadir tickers afectados al registro
                    for ticker in affected:
                        if ticker not in self.triggered_stocks:
                            self.triggered_stocks[ticker] = []
                        self.triggered_stocks[ticker].append(trigger)

            except Exception as e:
                continue

        self.correlation_alerts = triggers
        return triggers

    def scan_congress_trades(self, days: int = 30) -> List[Dict]:
        """
        Escanea trades recientes de congresistas.
        Usa CongressTracker que tiene fallback a base de datos local.
        """
        triggers = []
        print("  Escaneando trades de congresistas...")

        # Usar CongressTracker que ya tiene fallback a DB local
        if CONGRESS_TRACKER_AVAILABLE:
            try:
                tracker = CongressTracker()
                df = tracker.get_recent_trades(days=days)

                if not df.empty:
                    for _, trade in df.iterrows():
                        try:
                            politician = trade.get('politician', '')
                            ticker = trade.get('ticker', '')
                            tx_type = trade.get('type', '')
                            amount_min = trade.get('amount_min', 0) or 0
                            tx_date = trade.get('transaction_date')

                            if not ticker or len(ticker) > 5:
                                continue

                            # Verificar si es político top
                            is_top_politician = any(p['name'].lower() in politician.lower()
                                                    for p in TOP_POLITICIANS)

                            # Trigger si: político top O trade grande (>$50k)
                            if is_top_politician or amount_min >= 50000:
                                # Formatear fecha
                                date_str = tx_date.strftime('%Y-%m-%d') if hasattr(tx_date, 'strftime') else str(tx_date)[:10]

                                trigger = {
                                    'type': 'CONGRESS_TRADE',
                                    'politician': politician,
                                    'ticker': ticker,
                                    'action': 'BUY' if 'PURCHASE' in str(tx_type).upper() else 'SELL',
                                    'amount': trade.get('amount_range', f'${amount_min:,.0f}+'),
                                    'amount_value': amount_min,
                                    'date': date_str,
                                    'is_top_politician': is_top_politician,
                                    'rationale': f"{politician} {'compró' if 'PURCHASE' in str(tx_type).upper() else 'vendió'} {ticker}",
                                    'strength': 2.5 if is_top_politician else 1.5,
                                    # URL por ticker (más confiable) + URL por político
                                    'source_url': f"https://housestockwatcher.com/summary_by_ticker/{ticker}",
                                    'politician_url': f"https://housestockwatcher.com/summary_by_rep/{quote(politician)}"
                                }
                                triggers.append(trigger)

                                # Registrar ticker
                                if ticker not in self.triggered_stocks:
                                    self.triggered_stocks[ticker] = []
                                self.triggered_stocks[ticker].append(trigger)

                        except Exception as e:
                            continue

            except Exception as e:
                print(f"    Warning: CongressTracker error: {e}")

        # Fallback directo a DB si CongressTracker no disponible
        elif DB_AVAILABLE:
            try:
                db = SignalDatabase()
                db_trades = db.get_congress_trades(days=days)

                for trade in db_trades:
                    politician = trade.get('politician', '')
                    ticker = trade.get('ticker', '')
                    action = trade.get('action', '')

                    is_top_politician = any(p['name'].lower() in politician.lower()
                                            for p in TOP_POLITICIANS)

                    if is_top_politician:
                        trigger = {
                            'type': 'CONGRESS_TRADE',
                            'politician': politician,
                            'ticker': ticker,
                            'action': 'BUY' if 'purchase' in action.lower() else 'SELL',
                            'date': trade.get('transaction_date', ''),
                            'is_top_politician': True,
                            'rationale': f"{politician} {'compró' if 'purchase' in action.lower() else 'vendió'} {ticker}",
                            'strength': 2.5,
                            # URL por ticker (más confiable) + URL por político
                            'source_url': f"https://housestockwatcher.com/summary_by_ticker/{ticker}",
                            'politician_url': f"https://housestockwatcher.com/summary_by_rep/{quote(politician)}"
                        }
                        triggers.append(trigger)

                        if ticker not in self.triggered_stocks:
                            self.triggered_stocks[ticker] = []
                        self.triggered_stocks[ticker].append(trigger)

            except Exception as e:
                print(f"    Warning: DB fallback error: {e}")

        self.congress_alerts = triggers
        return triggers

    def scan_monetary_regime(self, monetary_analysis: Optional[Dict] = None) -> List[Dict]:
        """
        Genera triggers basados en el régimen monetario actual.
        """
        triggers = []

        if not monetary_analysis:
            try:
                from integrations.monetary_plumbing import analyze_monetary_regime
                monetary_analysis = analyze_monetary_regime()
            except ImportError:
                return triggers

        print("  Analizando régimen monetario...")

        regime = monetary_analysis.get('liquidity_regime', 'NEUTRAL_LIQUIDITY')
        net_liq_change = monetary_analysis.get('net_liquidity_change_30d', 0)

        # Determinar tipo de trigger monetario
        if regime == 'ABUNDANT_LIQUIDITY' or net_liq_change > 100:  # $100B+
            config = MONETARY_TRIGGERS['LIQUIDITY_SURGE']
            trigger_type = 'LIQUIDITY_SURGE'
        elif regime == 'TIGHT_LIQUIDITY' or net_liq_change < -100:
            config = MONETARY_TRIGGERS['LIQUIDITY_DRAIN']
            trigger_type = 'LIQUIDITY_DRAIN'
        else:
            return triggers  # Neutral, no trigger

        trigger = {
            'type': 'MONETARY',
            'subtype': trigger_type,
            'regime': regime,
            'net_liq_change': f"${net_liq_change:.0f}B",
            'favor_tickers': config['favor'],
            'avoid_tickers': config['avoid'],
            'rationale': config['rationale'],
            'timestamp': datetime.now().isoformat(),
            'strength': 2.0
        }
        triggers.append(trigger)

        # Registrar tickers favorecidos
        for ticker in config['favor']:
            if ticker not in self.triggered_stocks:
                self.triggered_stocks[ticker] = []
            self.triggered_stocks[ticker].append(trigger)

        self.monetary_alerts = triggers
        return triggers

    def get_all_triggered_stocks(self) -> Dict[str, List[Dict]]:
        """
        Retorna todos los tickers que han sido triggered con sus razones.
        """
        return self.triggered_stocks

    def get_trigger_summary(self) -> List[Dict]:
        """
        Resumen de todos los triggers para mostrar en Excel.
        """
        summary = []

        for ticker, triggers in self.triggered_stocks.items():
            # Calcular score combinado de triggers
            total_strength = sum(t.get('strength', 1) for t in triggers)

            # Consolidar razones
            reasons = []
            for t in triggers:
                if t['type'] == 'CORRELATION':
                    reasons.append(f"{t['source']} {t['direction']} {t['move']}")
                elif t['type'] == 'CONGRESS_TRADE':
                    reasons.append(f"{t['politician'][:15]} {t['action']}")
                elif t['type'] == 'MONETARY':
                    reasons.append(f"{t['subtype']}")

            summary.append({
                'ticker': ticker,
                'trigger_count': len(triggers),
                'trigger_strength': round(total_strength, 1),
                'reasons': ' | '.join(reasons[:3]),  # Máx 3 razones
                'triggers': triggers
            })

        # Ordenar por fuerza de trigger
        summary.sort(key=lambda x: x['trigger_strength'], reverse=True)
        return summary

    def _parse_amount(self, amount_str: str) -> float:
        """Parsea el string de amount a valor numérico."""
        try:
            if not amount_str:
                return 0
            # Formato: "$1,001 - $15,000" o "$100,001 - $250,000"
            parts = amount_str.replace('$', '').replace(',', '').split(' - ')
            if len(parts) >= 2:
                return (float(parts[0]) + float(parts[1])) / 2
            return float(parts[0])
        except:
            return 0


def run_full_scan() -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """
    Ejecuta un escaneo completo de todos los triggers.
    Retorna (triggered_stocks, trigger_summary)
    """
    system = TriggerSystem()

    print("\n[TRIGGER SYSTEM] Escaneando oportunidades...")
    print("=" * 50)

    # Escanear todas las fuentes
    corr_triggers = system.scan_correlations(lookback_days=5)
    print(f"  - Correlaciones: {len(corr_triggers)} triggers encontrados")

    congress_triggers = system.scan_congress_trades(days=14)
    print(f"  - Congress trades: {len(congress_triggers)} triggers encontrados")

    monetary_triggers = system.scan_monetary_regime()
    print(f"  - Monetario: {len(monetary_triggers)} triggers encontrados")

    # Resumen
    summary = system.get_trigger_summary()
    print(f"\n  TOTAL: {len(summary)} tickers con triggers activos")
    print("=" * 50)

    return system.get_all_triggered_stocks(), summary


# =============================================================================
# ESTRATEGIAS ÓPTIMAS POR HORIZONTE TEMPORAL
# =============================================================================

STRATEGY_RECOMMENDATIONS = {
    'VERY_SHORT_TERM': {  # Días a 2 semanas
        'name': 'Especulativo/Trading',
        'description': 'Para traders activos. Alto riesgo, alta recompensa potencial.',
        'weights': {
            'momentum': 0.40,
            'technical': 0.30,  # RSI, MACD, etc.
            'congress': 0.15,
            'news_sentiment': 0.15,
        },
        'signals_to_use': ['STRONG BUY', 'BUY'],
        'position_sizing': 'Pequeñas (2-5% cartera)',
        'stop_loss': '5-8%',
        'take_profit': '10-20%',
        'holding_period': '1-14 días',
        'rebalance': 'Diario',
        'best_for': 'Congress trades recientes, momentum breakouts',
        'when_works': 'Mercados trending, alta volatilidad',
        'when_fails': 'Mercados laterales, baja liquidez',
    },
    'SHORT_TERM': {  # 2 semanas a 3 meses
        'name': 'Swing Trading',
        'description': 'Capturar movimientos de semanas. Balance riesgo/recompensa.',
        'weights': {
            'momentum': 0.35,
            'quality': 0.25,
            'value': 0.15,
            'congress': 0.15,
            'polymarket': 0.10,
        },
        'signals_to_use': ['STRONG BUY', 'BUY', 'ACCUMULATE'],
        'position_sizing': 'Medianas (5-10% cartera)',
        'stop_loss': '10-15%',
        'take_profit': '20-40%',
        'holding_period': '2-12 semanas',
        'rebalance': 'Semanal',
        'best_for': 'Correlaciones activadas, eventos catalizadores',
        'when_works': 'Rotaciones sectoriales, earnings season',
        'when_fails': 'Crisis sistémicas, bear markets',
    },
    'MEDIUM_TERM': {  # 3 meses a 1 año
        'name': 'Position Trading',
        'description': 'Capturar tendencias mayores. Menor ruido, mejor ratio.',
        'weights': {
            'quality': 0.30,
            'momentum': 0.25,
            'value': 0.20,
            'lowvol': 0.15,
            'congress': 0.10,
        },
        'signals_to_use': ['STRONG BUY', 'BUY', 'ACCUMULATE'],
        'position_sizing': 'Significativas (10-15% cartera)',
        'stop_loss': '15-20%',
        'take_profit': '40-80%',
        'holding_period': '3-12 meses',
        'rebalance': 'Mensual',
        'best_for': 'Empresas de calidad con momentum, cambios régimen monetario',
        'when_works': 'Bull markets, expansión económica',
        'when_fails': 'Recesiones, crashes',
    },
    'LONG_TERM': {  # 1-5 años
        'name': 'Inversión Value-Quality',
        'description': 'Compounding a largo plazo. Menor estrés, mejores resultados históricos.',
        'weights': {
            'quality': 0.35,
            'value': 0.35,
            'lowvol': 0.20,
            'momentum': 0.10,
        },
        'signals_to_use': ['STRONG BUY', 'BUY'],
        'position_sizing': 'Core positions (15-25% cartera)',
        'stop_loss': 'No fijo (fundamentales)',
        'take_profit': 'No fijo (hold mientras tesis válida)',
        'holding_period': '1-5+ años',
        'rebalance': 'Trimestral',
        'best_for': 'Empresas dominantes, moats, dividendos crecientes',
        'when_works': 'Siempre (a largo plazo)',
        'when_fails': 'Disrupciones tecnológicas en la empresa',
    },
}


def get_strategy_recommendation(investment_horizon: str) -> Dict:
    """
    Retorna la estrategia recomendada para el horizonte temporal dado.
    """
    horizon_map = {
        'very_short': 'VERY_SHORT_TERM',
        'short': 'SHORT_TERM',
        'medium': 'MEDIUM_TERM',
        'long': 'LONG_TERM',
    }

    key = horizon_map.get(investment_horizon.lower(), 'MEDIUM_TERM')
    return STRATEGY_RECOMMENDATIONS.get(key)


if __name__ == '__main__':
    # Test del sistema
    triggered_stocks, summary = run_full_scan()

    print("\n[TOP 10 STOCKS CON TRIGGERS]")
    for item in summary[:10]:
        print(f"  {item['ticker']:6} | Strength: {item['trigger_strength']:.1f} | {item['reasons']}")

    print("\n[ESTRATEGIAS RECOMENDADAS]")
    for horizon, strategy in STRATEGY_RECOMMENDATIONS.items():
        print(f"\n{horizon}: {strategy['name']}")
        print(f"  Mejor para: {strategy['best_for']}")
        print(f"  Holding: {strategy['holding_period']}")
