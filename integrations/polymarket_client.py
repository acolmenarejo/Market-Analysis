"""
===============================================================================
POLYMARKET CLIENT - Smart Money Detection
===============================================================================
Cliente para Polymarket que detecta apuestas de "smart money" y mercados
que pueden afectar a la bolsa.

APIs UTILIZADAS:
    - Gamma API (gratis): Mercados, precios, volumen
    - CLOB API: Orderbook y trades

FUNCIONALIDADES:
    1. Obtener mercados relevantes para inversión (política, economía, geopolítica)
    2. Detectar apuestas grandes (>$50k) - posible smart money
    3. Detectar wallets nuevas con apuestas grandes - posible info privilegiada
    4. Generar alertas de smart money

EJEMPLO DEL USUARIO:
    "Una persona apostó $400k el día exacto del secuestro de Maduro por EEUU.
    Esto es gente con info privilegiada."

USO:
    from integrations.polymarket_client import PolymarketClient

    client = PolymarketClient()
    markets = client.get_relevant_markets()
    alerts = client.detect_smart_money_alerts()
===============================================================================
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import time
import re

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.api_config import API_ENDPOINTS, RATE_LIMITS, SMART_MONEY_CONFIG


class PolymarketClient:
    """
    Cliente para Polymarket con detección de Smart Money.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or SMART_MONEY_CONFIG
        self.gamma_url = API_ENDPOINTS['polymarket_gamma']
        self.clob_url = API_ENDPOINTS['polymarket_clob']
        self._cache = {}
        self._cache_time = {}

    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Realiza request con manejo de errores y rate limiting"""
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(RATE_LIMITS['polymarket_gamma']['delay_seconds'])
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Error making request to {url}: {e}")
            return None

    def get_all_markets(self, limit: int = 100, active_only: bool = True) -> List[Dict]:
        """
        Obtiene todos los mercados de Polymarket.

        Returns:
            Lista de mercados con info básica
        """
        cache_key = f'markets_{limit}_{active_only}'

        # Check cache
        if cache_key in self._cache:
            cache_age = datetime.now() - self._cache_time.get(cache_key, datetime.min)
            if cache_age.total_seconds() < 900:  # 15 min cache
                return self._cache[cache_key]

        url = f"{self.gamma_url}/markets"
        params = {
            'limit': limit,
            'active': 'true' if active_only else 'false',
        }

        data = self._make_request(url, params)
        if not data:
            return []

        markets = data if isinstance(data, list) else data.get('data', [])

        # Cache
        self._cache[cache_key] = markets
        self._cache_time[cache_key] = datetime.now()

        return markets

    def get_market_details(self, market_id: str) -> Optional[Dict]:
        """Obtiene detalles de un mercado específico"""
        url = f"{self.gamma_url}/markets/{market_id}"
        return self._make_request(url)

    def _is_relevant_market(self, market: Dict) -> bool:
        """
        Determina si un mercado es relevante para inversión.

        Criterios:
            - Categorías: política, economía, fed, geopolítica
            - Keywords en título/descripción
        """
        title = (market.get('question', '') + ' ' +
                 market.get('description', '')).lower()

        # Check keywords
        keywords = self.config['market_keywords']
        for keyword in keywords:
            if keyword.lower() in title:
                return True

        # Check tags/categories
        tags = market.get('tags', []) or []
        categories = self.config['market_categories']
        for tag in tags:
            if any(cat in tag.lower() for cat in categories):
                return True

        return False

    def _estimate_market_impact(self, market: Dict) -> Dict:
        """
        Estima el impacto potencial de un mercado en inversiones.

        Returns:
            Dict con tickers relevantes y tipo de impacto
        """
        title = (market.get('question', '') + ' ' +
                 market.get('description', '')).lower()

        relevant_tickers = []
        impact_type = 'GENERAL'
        sector = None

        # Mapeo de keywords a tickers/sectores
        keyword_mappings = {
            # Política USA
            'trump': {'tickers': ['DJT', 'DWAC'], 'sector': 'Politics', 'impact': 'HIGH'},
            'biden': {'tickers': [], 'sector': 'Politics', 'impact': 'HIGH'},
            'election': {'tickers': ['SPY', 'QQQ'], 'sector': 'Politics', 'impact': 'HIGH'},

            # Fed / Economía
            'fed': {'tickers': ['TLT', 'IEF', 'GLD'], 'sector': 'Rates', 'impact': 'HIGH'},
            'rate cut': {'tickers': ['TLT', 'XLF', 'QQQ'], 'sector': 'Rates', 'impact': 'HIGH'},
            'rate hike': {'tickers': ['TLT', 'XLF'], 'sector': 'Rates', 'impact': 'HIGH'},
            'inflation': {'tickers': ['TIP', 'GLD', 'DBA'], 'sector': 'Macro', 'impact': 'MEDIUM'},
            'recession': {'tickers': ['SPY', 'TLT', 'GLD'], 'sector': 'Macro', 'impact': 'HIGH'},

            # Geopolítica
            'china': {'tickers': ['FXI', 'BABA', 'PDD', 'JD'], 'sector': 'Geopolitics', 'impact': 'HIGH'},
            'taiwan': {'tickers': ['TSM', 'NVDA', 'AMD'], 'sector': 'Geopolitics', 'impact': 'HIGH'},
            'russia': {'tickers': ['XLE', 'UNG', 'WEAT'], 'sector': 'Geopolitics', 'impact': 'HIGH'},
            'ukraine': {'tickers': ['XLE', 'WEAT', 'LMT'], 'sector': 'Geopolitics', 'impact': 'HIGH'},
            'iran': {'tickers': ['XLE', 'USO', 'OIH'], 'sector': 'Geopolitics', 'impact': 'MEDIUM'},
            'venezuela': {'tickers': ['XLE', 'USO', 'EWZ'], 'sector': 'Geopolitics', 'impact': 'MEDIUM'},
            'maduro': {'tickers': ['XLE', 'USO', 'EWZ', 'COPX'], 'sector': 'Geopolitics', 'impact': 'MEDIUM'},

            # Energía
            'oil': {'tickers': ['XLE', 'USO', 'CVX', 'XOM'], 'sector': 'Energy', 'impact': 'HIGH'},
            'gas': {'tickers': ['UNG', 'XLE'], 'sector': 'Energy', 'impact': 'MEDIUM'},
            'opec': {'tickers': ['XLE', 'USO', 'OIH'], 'sector': 'Energy', 'impact': 'HIGH'},

            # Tech / Regulación
            'antitrust': {'tickers': ['GOOGL', 'META', 'AAPL', 'AMZN'], 'sector': 'Tech', 'impact': 'HIGH'},
            'tech regulation': {'tickers': ['QQQ', 'GOOGL', 'META'], 'sector': 'Tech', 'impact': 'MEDIUM'},

            # Crypto
            'bitcoin': {'tickers': ['MSTR', 'COIN', 'RIOT'], 'sector': 'Crypto', 'impact': 'HIGH'},
            'crypto': {'tickers': ['MSTR', 'COIN'], 'sector': 'Crypto', 'impact': 'MEDIUM'},
            'sec crypto': {'tickers': ['COIN', 'MSTR'], 'sector': 'Crypto', 'impact': 'HIGH'},

            # Fiscal
            'debt ceiling': {'tickers': ['TLT', 'SPY'], 'sector': 'Fiscal', 'impact': 'HIGH'},
            'government shutdown': {'tickers': ['SPY'], 'sector': 'Fiscal', 'impact': 'MEDIUM'},
            'tariff': {'tickers': ['SPY', 'EEM', 'FXI'], 'sector': 'Trade', 'impact': 'HIGH'},
        }

        for keyword, mapping in keyword_mappings.items():
            if keyword in title:
                relevant_tickers.extend(mapping['tickers'])
                impact_type = mapping['impact']
                sector = mapping['sector']
                break

        # Eliminar duplicados
        relevant_tickers = list(set(relevant_tickers))

        return {
            'relevant_tickers': relevant_tickers[:5],  # Max 5
            'impact_type': impact_type,
            'sector': sector,
        }

    def get_relevant_markets(self, limit: int = 50) -> List[Dict]:
        """
        Obtiene mercados relevantes para inversión.

        Returns:
            Lista de mercados filtrados con análisis de impacto
        """
        all_markets = self.get_all_markets(limit=200)
        relevant = []

        for market in all_markets:
            if self._is_relevant_market(market):
                # Agregar análisis de impacto
                impact = self._estimate_market_impact(market)
                market['impact_analysis'] = impact
                relevant.append(market)

        # Ordenar por volumen
        relevant.sort(key=lambda x: x.get('volume', 0) or 0, reverse=True)

        return relevant[:limit]

    def get_market_volume_data(self, market_id: str) -> Optional[Dict]:
        """
        Obtiene datos de volumen para un mercado.

        Nota: La API pública tiene limitaciones en datos de volumen detallado.
        """
        market = self.get_market_details(market_id)
        if not market:
            return None

        return {
            'market_id': market_id,
            'question': market.get('question', ''),
            'volume': market.get('volume', 0),
            'volume_24h': market.get('volume24hr', 0),
            'liquidity': market.get('liquidity', 0),
            'outcomes': market.get('outcomes', []),
        }

    def detect_large_bets(self, min_volume_24h: float = None) -> List[Dict]:
        """
        Detecta mercados con actividad inusualmente alta (posible smart money).

        Criterios:
            - Volumen 24h alto
            - Mercados relevantes para inversión
        """
        threshold = min_volume_24h or self.config['large_bet_threshold']
        markets = self.get_relevant_markets(limit=100)

        large_bet_markets = []
        for market in markets:
            volume_24h = market.get('volume24hr', 0) or 0

            if volume_24h >= threshold:
                # Calcular nivel de alerta
                if volume_24h >= self.config['whale_bet_threshold']:
                    alert_level = 'HIGH'
                elif volume_24h >= threshold:
                    alert_level = 'MEDIUM'
                else:
                    alert_level = 'LOW'

                large_bet_markets.append({
                    'market_id': market.get('id', ''),
                    'question': market.get('question', ''),
                    'volume_24h': volume_24h,
                    'total_volume': market.get('volume', 0),
                    'current_odds': self._get_current_odds(market),
                    'relevant_tickers': market.get('impact_analysis', {}).get('relevant_tickers', []),
                    'sector': market.get('impact_analysis', {}).get('sector'),
                    'alert_level': alert_level,
                    'end_date': market.get('endDate', ''),
                })

        # Ordenar por volumen
        large_bet_markets.sort(key=lambda x: x['volume_24h'], reverse=True)
        return large_bet_markets

    def _get_current_odds(self, market: Dict) -> Dict:
        """Extrae odds actuales de un mercado"""
        outcomes = market.get('outcomes', [])
        odds = {}

        if isinstance(outcomes, list):
            for i, outcome in enumerate(outcomes):
                if isinstance(outcome, dict):
                    name = outcome.get('name', f'Outcome {i}')
                    price = outcome.get('price', 0)
                else:
                    name = str(outcome)
                    price = market.get(f'outcomePrices', [0])[i] if i < len(market.get('outcomePrices', [])) else 0
                odds[name] = round(float(price) * 100 if price else 0, 1)

        # Fallback: buscar en otros campos
        if not odds:
            yes_price = market.get('yesPrice') or market.get('bestAsk')
            no_price = market.get('noPrice') or market.get('bestBid')
            if yes_price:
                odds['Yes'] = round(float(yes_price) * 100, 1)
            if no_price:
                odds['No'] = round(float(no_price) * 100, 1)

        return odds

    def detect_smart_money_alerts(self) -> List[Dict]:
        """
        Genera alertas de smart money consolidadas.

        Criterios de alerta:
            1. Mercados con volumen 24h > $50k
            2. Mercados relevantes para acciones/materias primas
            3. Cambios bruscos en odds (si disponible)
        """
        large_bets = self.detect_large_bets()
        alerts = []

        for market in large_bets:
            # Generar descripción de impacto
            tickers = market.get('relevant_tickers', [])
            sector = market.get('sector', 'General')

            impact_description = f"Sector: {sector}"
            if tickers:
                impact_description += f" | Tickers afectados: {', '.join(tickers)}"

            alerts.append({
                'type': 'LARGE_VOLUME',
                'market': market['question'][:100],  # Truncar
                'volume_24h': f"${market['volume_24h']:,.0f}",
                'current_odds': market['current_odds'],
                'relevant_tickers': tickers,
                'impact_assessment': impact_description,
                'alert_level': market['alert_level'],
                'action_suggested': self._suggest_action(market),
                'timestamp': datetime.now().isoformat(),
            })

        return alerts

    def _suggest_action(self, market: Dict) -> str:
        """Sugiere acción basada en el mercado"""
        tickers = market.get('relevant_tickers', [])
        odds = market.get('current_odds', {})
        alert_level = market.get('alert_level', 'LOW')

        if alert_level == 'HIGH':
            if tickers:
                return f"REVISAR POSICIONES en {', '.join(tickers[:3])}. Alto volumen de apuestas detectado."
            return "Monitorear mercado de cerca. Posible información privilegiada."
        elif alert_level == 'MEDIUM':
            return "Observar desarrollo. Considerar ajustar exposición si se confirma tendencia."
        else:
            return "Mantener monitoreo rutinario."

    def get_signal_for_ticker(self, ticker: str) -> Dict:
        """
        Genera señal de Polymarket para un ticker específico.

        Busca mercados que afecten al ticker y evalúa el sentimiento.
        """
        markets = self.get_relevant_markets(limit=100)

        relevant_markets = []
        bullish_signals = 0
        bearish_signals = 0
        total_volume = 0

        for market in markets:
            impact = market.get('impact_analysis', {})
            affected_tickers = impact.get('relevant_tickers', [])

            if ticker.upper() in [t.upper() for t in affected_tickers]:
                relevant_markets.append({
                    'question': market.get('question', ''),
                    'volume_24h': market.get('volume24hr', 0),
                    'odds': self._get_current_odds(market),
                })
                total_volume += market.get('volume24hr', 0) or 0

                # Evaluar sentimiento basado en el mercado
                # (simplificado - en producción sería más sofisticado)
                question = market.get('question', '').lower()
                if any(word in question for word in ['positive', 'good', 'win', 'approve']):
                    bullish_signals += 1
                elif any(word in question for word in ['negative', 'bad', 'lose', 'reject']):
                    bearish_signals += 1

        # Calcular score
        if not relevant_markets:
            return {
                'ticker': ticker,
                'signal': 'NO_DATA',
                'score': 50,
                'relevant_markets': [],
                'total_volume_24h': 0,
                'confidence': 'LOW',
            }

        # Score basado en balance bullish/bearish
        total_signals = bullish_signals + bearish_signals
        if total_signals > 0:
            score = 50 + ((bullish_signals - bearish_signals) / total_signals) * 50
        else:
            score = 50

        # Ajustar por volumen (más volumen = más confianza)
        if total_volume > self.config['whale_bet_threshold']:
            confidence = 'HIGH'
        elif total_volume > self.config['large_bet_threshold']:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        # Determinar señal
        if score >= 60:
            signal = 'BULLISH'
        elif score <= 40:
            signal = 'BEARISH'
        else:
            signal = 'NEUTRAL'

        return {
            'ticker': ticker,
            'signal': signal,
            'score': round(score, 1),
            'relevant_markets': relevant_markets[:5],  # Top 5
            'total_volume_24h': total_volume,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'confidence': confidence,
        }

    def generate_excel_data(self) -> List[Dict]:
        """
        Genera datos formateados para la hoja Excel de Polymarket_Signals.
        """
        alerts = self.detect_smart_money_alerts()
        result = []

        for alert in alerts:
            result.append({
                'Market': alert['market'],
                'Volume_24h': alert['volume_24h'],
                'Current_Odds': str(alert['current_odds']),
                'Relevant_Tickers': ', '.join(alert['relevant_tickers']),
                'Impact_Assessment': alert['impact_assessment'],
                'Alert_Level': alert['alert_level'],
                'Action_Suggested': alert['action_suggested'],
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            })

        return result


def get_polymarket_signal_batch(tickers: List[str]) -> Dict[str, Dict]:
    """
    Obtiene señales de Polymarket para múltiples tickers.
    """
    client = PolymarketClient()
    results = {}

    for ticker in tickers:
        signal = client.get_signal_for_ticker(ticker)
        results[ticker] = signal

    return results


if __name__ == '__main__':
    # Test
    print("Testing Polymarket Client...")
    client = PolymarketClient()

    # Get relevant markets
    print("\nFetching relevant markets...")
    markets = client.get_relevant_markets(limit=10)
    print(f"Found {len(markets)} relevant markets")

    for i, market in enumerate(markets[:5], 1):
        print(f"\n{i}. {market.get('question', '')[:60]}...")
        print(f"   Volume: ${market.get('volume', 0):,.0f}")
        print(f"   24h: ${market.get('volume24hr', 0):,.0f}")
        impact = market.get('impact_analysis', {})
        print(f"   Tickers: {impact.get('relevant_tickers', [])}")
        print(f"   Sector: {impact.get('sector')}")

    # Detect smart money
    print("\n\nDetecting smart money alerts...")
    alerts = client.detect_smart_money_alerts()
    print(f"Found {len(alerts)} potential smart money alerts")

    for alert in alerts[:3]:
        print(f"\n  Alert Level: {alert['alert_level']}")
        print(f"  Market: {alert['market'][:60]}...")
        print(f"  Volume 24h: {alert['volume_24h']}")
        print(f"  Tickers: {alert['relevant_tickers']}")
        print(f"  Action: {alert['action_suggested']}")

    # Test signal for ticker
    test_ticker = 'NVDA'
    print(f"\n\nSignal for {test_ticker}:")
    signal = client.get_signal_for_ticker(test_ticker)
    print(f"  Signal: {signal['signal']}")
    print(f"  Score: {signal['score']}")
    print(f"  Confidence: {signal['confidence']}")
    print(f"  Relevant markets: {len(signal['relevant_markets'])}")
