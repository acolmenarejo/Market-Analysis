"""
===============================================================================
CONGRESS TRACKER MODULE
===============================================================================
Rastrea trades de congresistas (Senadores y Representantes) para detectar
posibles señales de información privilegiada.

FUENTES DE DATOS (gratuitas):
    - House Stock Watcher: https://housestockwatcher.com/
    - Senate Stock Watcher: https://senatestockwatcher.com/

POLÍTICOS CON HISTORIAL NOTABLE:
    - Nancy Pelosi (D-CA)
    - Tommy Tuberville (R-AL)
    - Dan Crenshaw (R-TX)
    - Brian Mast (R-FL)

USO:
    from integrations.congress_tracker import CongressTracker

    tracker = CongressTracker()
    trades = tracker.get_recent_trades(days=30)
    signal = tracker.get_signal_for_ticker('NVDA')
===============================================================================
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.api_config import API_ENDPOINTS, RATE_LIMITS, CONGRESS_CONFIG

# Integración con base de datos local
try:
    from integrations.signal_database import SignalDatabase
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class CongressTracker:
    """
    Rastrea y analiza trades de congresistas.
    Integrado con base de datos local para persistencia y fallback.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or CONGRESS_CONFIG
        self.house_url = API_ENDPOINTS['house_stock_watcher']
        self.senate_url = API_ENDPOINTS['senate_stock_watcher']
        self._cache = {}
        self._cache_time = {}

        # Inicializar base de datos local
        self.db = SignalDatabase() if DB_AVAILABLE else None

    def _get_headers(self) -> Dict:
        """Headers para evitar bloqueo por User-Agent"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        }

    def _fetch_house_trades(self) -> List[Dict]:
        """Obtiene trades de la Cámara de Representantes"""
        try:
            response = requests.get(self.house_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Error fetching House trades: {e}")
            return []

    def _fetch_senate_trades(self) -> List[Dict]:
        """Obtiene trades del Senado"""
        try:
            response = requests.get(self.senate_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Error fetching Senate trades: {e}")
            return []

    def _parse_amount_range(self, amount_str: str) -> tuple:
        """
        Parsea el rango de cantidad de la transacción.

        Ejemplos:
            '$1,001 - $15,000' -> (1001, 15000)
            '$50,001 - $100,000' -> (50001, 100000)
            '$1,000,001 - $5,000,000' -> (1000001, 5000000)
        """
        if not amount_str:
            return (0, 0)

        try:
            # Limpiar y separar
            parts = amount_str.replace('$', '').replace(',', '').split(' - ')
            if len(parts) == 2:
                return (int(parts[0]), int(parts[1]))
            elif len(parts) == 1:
                val = int(parts[0])
                return (val, val)
        except (ValueError, AttributeError):
            pass

        return (0, 0)

    def _normalize_trade(self, trade: Dict, chamber: str) -> Dict:
        """Normaliza un trade a formato estándar"""
        # Campos comunes
        if chamber == 'house':
            politician = trade.get('representative', '')
            party = trade.get('party', '')
            state = trade.get('state', '')
            district = trade.get('district', '')
        else:  # senate
            politician = trade.get('senator', '') or trade.get('first_name', '') + ' ' + trade.get('last_name', '')
            party = trade.get('party', '')
            state = trade.get('state', '')
            district = ''

        ticker = trade.get('ticker', '').upper()
        if ticker == '--' or ticker == 'N/A':
            ticker = ''

        # Parsear fecha
        tx_date = trade.get('transaction_date', '')
        disc_date = trade.get('disclosure_date', '')

        # Tipo de transacción
        tx_type = trade.get('type', '').upper()
        if 'PURCHASE' in tx_type or 'BUY' in tx_type:
            tx_type = 'PURCHASE'
        elif 'SALE' in tx_type or 'SELL' in tx_type:
            tx_type = 'SALE'
        elif 'EXCHANGE' in tx_type:
            tx_type = 'EXCHANGE'

        # Amount
        amount_str = trade.get('amount', '')
        amount_min, amount_max = self._parse_amount_range(amount_str)

        # Asset type
        asset_type = trade.get('asset_type', '') or trade.get('asset_description', '')
        is_option = 'option' in asset_type.lower() if asset_type else False

        return {
            'politician': politician.strip(),
            'party': party,
            'state': state,
            'district': district,
            'chamber': chamber.upper(),
            'ticker': ticker,
            'transaction_date': tx_date,
            'disclosure_date': disc_date,
            'type': tx_type,
            'amount_range': amount_str,
            'amount_min': amount_min,
            'amount_max': amount_max,
            'asset_type': asset_type,
            'is_option': is_option,
            'asset_description': trade.get('asset_description', ''),
        }

    def fetch_all_trades(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Obtiene todos los trades de House y Senate.
        Integrado con base de datos local para persistencia y fallback.

        Returns:
            DataFrame con todos los trades normalizados
        """
        cache_key = 'all_trades'

        # Check memory cache
        if use_cache and cache_key in self._cache:
            cache_age = datetime.now() - self._cache_time.get(cache_key, datetime.min)
            if cache_age.total_seconds() < 3600:  # 1 hour cache
                return self._cache[cache_key]

        print("  Fetching Congress trades...")

        # Fetch data from APIs
        house_trades = self._fetch_house_trades()
        time.sleep(RATE_LIMITS['house_stock_watcher']['delay_seconds'])
        senate_trades = self._fetch_senate_trades()

        # Normalize
        all_trades = []

        for trade in house_trades:
            normalized = self._normalize_trade(trade, 'house')
            if normalized['ticker']:  # Solo trades con ticker
                all_trades.append(normalized)

        for trade in senate_trades:
            normalized = self._normalize_trade(trade, 'senate')
            if normalized['ticker']:
                all_trades.append(normalized)

        # Si obtuvimos datos de las APIs, almacenar en DB local
        if all_trades and self.db:
            stored = self.db.store_congress_trades_bulk(all_trades)
            if stored > 0:
                print(f"  Almacenados {stored} nuevos trades en base de datos local")

        # Si NO obtuvimos datos de APIs, usar base de datos local como fallback
        if not all_trades and self.db:
            print("  APIs no disponibles, usando datos locales...")
            db_trades = self.db.get_congress_trades(days=365)
            if db_trades:
                # Normalizar nombres de columnas de DB a formato esperado
                for trade in db_trades:
                    # DB usa 'action', DataFrame espera 'type'
                    if 'action' in trade and 'type' not in trade:
                        action = trade['action'].upper() if trade['action'] else ''
                        if 'PURCHASE' in action or 'BUY' in action:
                            trade['type'] = 'PURCHASE'
                        elif 'SALE' in action or 'SELL' in action:
                            trade['type'] = 'SALE'
                        else:
                            trade['type'] = action
                    # Añadir campos que pueden faltar
                    trade.setdefault('amount_range', '')
                    trade.setdefault('is_option', False)
                    trade.setdefault('asset_type', 'Stock')
                    trade.setdefault('asset_description', '')
                    trade.setdefault('state', '')
                    trade.setdefault('district', '')
                all_trades = db_trades
                print(f"  Recuperados {len(db_trades)} trades de base de datos local")

        df = pd.DataFrame(all_trades)

        if not df.empty:
            # Convertir fechas
            if 'transaction_date' in df.columns:
                df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
            if 'disclosure_date' in df.columns:
                df['disclosure_date'] = pd.to_datetime(df['disclosure_date'], errors='coerce')

            # Ordenar por fecha más reciente
            if 'transaction_date' in df.columns:
                df = df.sort_values('transaction_date', ascending=False)

        # Memory cache
        self._cache[cache_key] = df
        self._cache_time[cache_key] = datetime.now()

        print(f"  Found {len(df)} trades total")
        return df

    def get_recent_trades(self, days: int = None, all_available: bool = False) -> pd.DataFrame:
        """
        Obtiene trades recientes dentro del período especificado.

        Args:
            days: Número de días hacia atrás para filtrar
            all_available: Si True, devuelve todos los trades sin filtro de fecha
        """
        days = days or self.config['lookback_days']

        df = self.fetch_all_trades()
        if df.empty:
            return df

        if all_available:
            return df

        cutoff_date = datetime.now() - timedelta(days=days)
        recent = df[df['transaction_date'] >= cutoff_date].copy()

        # Si no hay trades recientes, devolver todos los disponibles como fallback
        if recent.empty and not df.empty:
            return df

        return recent

    def get_trades_by_politician(self, politician_name: str,
                                  days: int = None) -> pd.DataFrame:
        """Obtiene trades de un político específico"""
        df = self.get_recent_trades(days)
        if df.empty:
            return df

        # Búsqueda flexible por nombre
        mask = df['politician'].str.contains(politician_name, case=False, na=False)
        return df[mask]

    def get_trades_by_ticker(self, ticker: str, days: int = None) -> pd.DataFrame:
        """Obtiene trades de un ticker específico"""
        df = self.get_recent_trades(days)
        if df.empty:
            return df

        mask = df['ticker'].str.upper() == ticker.upper()
        return df[mask]

    def get_high_performer_trades(self, days: int = None) -> pd.DataFrame:
        """Obtiene trades de políticos con historial de buen timing"""
        df = self.get_recent_trades(days)
        if df.empty:
            return df

        # Filtrar por high performers
        high_performers = self.config['high_performers']
        mask = df['politician'].apply(
            lambda x: any(hp.lower() in x.lower() for hp in high_performers)
        )
        return df[mask]

    def get_large_trades(self, days: int = None,
                         min_amount: int = None) -> pd.DataFrame:
        """Obtiene trades grandes"""
        min_amount = min_amount or self.config['large_transaction_min']
        df = self.get_recent_trades(days)
        if df.empty:
            return df

        mask = df['amount_min'] >= min_amount
        return df[mask]

    def calculate_politician_stats(self, politician_name: str,
                                   lookback_days: int = 365) -> Dict:
        """
        Calcula estadísticas de un político.

        TODO: Implementar track record real (requiere datos históricos de precios)
        """
        trades = self.get_trades_by_politician(politician_name, lookback_days)

        if trades.empty:
            return {
                'politician': politician_name,
                'total_trades': 0,
                'purchases': 0,
                'sales': 0,
                'top_tickers': [],
                'avg_amount': 0,
                'is_high_performer': politician_name in self.config['high_performers'],
            }

        purchases = trades[trades['type'] == 'PURCHASE']
        sales = trades[trades['type'] == 'SALE']

        # Top tickers
        ticker_counts = trades['ticker'].value_counts().head(5)

        return {
            'politician': politician_name,
            'total_trades': len(trades),
            'purchases': len(purchases),
            'sales': len(sales),
            'top_tickers': ticker_counts.to_dict(),
            'avg_amount_min': trades['amount_min'].mean(),
            'avg_amount_max': trades['amount_max'].mean(),
            'is_high_performer': any(hp.lower() in politician_name.lower()
                                     for hp in self.config['high_performers']),
            'chambers': trades['chamber'].unique().tolist(),
            'party': trades['party'].mode().iloc[0] if not trades['party'].mode().empty else 'Unknown',
        }

    def get_signal_for_ticker(self, ticker: str, days: int = None) -> Dict:
        """
        Genera señal de trading basada en actividad de congresistas para un ticker.

        Returns:
            Dict con:
                - signal: 'BULLISH', 'BEARISH', o 'NEUTRAL'
                - score: 0-100 (50 = neutral)
                - recent_purchases: número de compras recientes
                - recent_sales: número de ventas recientes
                - high_performer_activity: actividad de high performers
        """
        days = days or self.config['lookback_days']
        trades = self.get_trades_by_ticker(ticker, days)

        if trades.empty:
            return {
                'ticker': ticker,
                'signal': 'NO_DATA',
                'score': 50,
                'recent_purchases': 0,
                'recent_sales': 0,
                'high_performer_activity': [],
                'politicians_buying': [],
                'politicians_selling': [],
                'confidence': 'LOW',
            }

        purchases = trades[trades['type'] == 'PURCHASE']
        sales = trades[trades['type'] == 'SALE']

        # High performer activity
        high_performers = self.config['high_performers']
        hp_trades = trades[trades['politician'].apply(
            lambda x: any(hp.lower() in x.lower() for hp in high_performers)
        )]

        hp_purchases = hp_trades[hp_trades['type'] == 'PURCHASE']
        hp_sales = hp_trades[hp_trades['type'] == 'SALE']

        # Calcular score
        # Base: ratio compras/ventas
        total = len(purchases) + len(sales)
        if total == 0:
            base_score = 50
        else:
            purchase_ratio = len(purchases) / total
            base_score = purchase_ratio * 100

        # Ajustar por high performers (peso doble)
        hp_adjustment = 0
        if len(hp_purchases) > len(hp_sales):
            hp_adjustment = 10 * (len(hp_purchases) - len(hp_sales))
        elif len(hp_sales) > len(hp_purchases):
            hp_adjustment = -10 * (len(hp_sales) - len(hp_purchases))

        # Ajustar por tamaño de transacciones
        size_adjustment = 0
        large_purchases = purchases[purchases['amount_min'] >= self.config['large_transaction_min']]
        large_sales = sales[sales['amount_min'] >= self.config['large_transaction_min']]
        if len(large_purchases) > len(large_sales):
            size_adjustment = 5
        elif len(large_sales) > len(large_purchases):
            size_adjustment = -5

        final_score = max(0, min(100, base_score + hp_adjustment + size_adjustment))

        # Determinar señal
        if final_score >= 65:
            signal = 'BULLISH'
        elif final_score <= 35:
            signal = 'BEARISH'
        else:
            signal = 'NEUTRAL'

        # Determinar confianza
        if total >= 5 and len(hp_trades) >= 2:
            confidence = 'HIGH'
        elif total >= 3 or len(hp_trades) >= 1:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        return {
            'ticker': ticker,
            'signal': signal,
            'score': round(final_score, 1),
            'recent_purchases': len(purchases),
            'recent_sales': len(sales),
            'high_performer_purchases': len(hp_purchases),
            'high_performer_sales': len(hp_sales),
            'high_performer_activity': hp_trades['politician'].unique().tolist(),
            'politicians_buying': purchases['politician'].unique().tolist()[:5],
            'politicians_selling': sales['politician'].unique().tolist()[:5],
            'large_transactions': len(large_purchases) + len(large_sales),
            'confidence': confidence,
            'days_analyzed': days,
        }

    def get_top_traded_tickers(self, days: int = None, limit: int = 20) -> pd.DataFrame:
        """
        Obtiene los tickers más operados por congresistas.
        """
        df = self.get_recent_trades(days)
        if df.empty:
            return pd.DataFrame()

        # Contar por ticker
        ticker_stats = df.groupby('ticker').agg({
            'politician': 'nunique',
            'type': lambda x: {
                'purchases': (x == 'PURCHASE').sum(),
                'sales': (x == 'SALE').sum(),
            },
            'amount_min': 'sum',
        }).reset_index()

        # Expandir type a columnas separadas
        ticker_stats['purchases'] = ticker_stats['type'].apply(lambda x: x['purchases'])
        ticker_stats['sales'] = ticker_stats['type'].apply(lambda x: x['sales'])
        ticker_stats['total_trades'] = ticker_stats['purchases'] + ticker_stats['sales']
        ticker_stats = ticker_stats.drop('type', axis=1)

        # Ordenar por total
        ticker_stats = ticker_stats.sort_values('total_trades', ascending=False)

        return ticker_stats.head(limit)

    def generate_excel_data(self, days: int = None) -> List[Dict]:
        """
        Genera datos formateados para la hoja Excel de Congress_Trades.
        """
        df = self.get_recent_trades(days)
        if df.empty:
            return []

        # Filtrar y formatear
        result = []
        for _, row in df.iterrows():
            # Determinar si es high performer
            is_hp = any(hp.lower() in row['politician'].lower()
                        for hp in self.config['high_performers'])

            # Calcular signal strength (1-5)
            signal_strength = 1
            if is_hp:
                signal_strength += 2
            if row['amount_min'] >= self.config['large_transaction_min']:
                signal_strength += 1
            if row['is_option']:
                signal_strength += 1  # Opciones sugieren timing específico

            result.append({
                'Politician': row['politician'],
                'Party': row['party'],
                'Chamber': row['chamber'],
                'Ticker': row['ticker'],
                'Transaction_Date': row['transaction_date'].strftime('%Y-%m-%d') if pd.notna(row['transaction_date']) else '',
                'Disclosure_Date': row['disclosure_date'].strftime('%Y-%m-%d') if pd.notna(row['disclosure_date']) else '',
                'Type': row['type'],
                'Amount_Range': row['amount_range'],
                'Asset_Type': 'Option' if row['is_option'] else 'Stock',
                'Is_High_Performer': 'Yes' if is_hp else 'No',
                'Signal_Strength': min(signal_strength, 5),
            })

        return result


def get_congress_signal_batch(tickers: List[str],
                               days: int = 30) -> Dict[str, Dict]:
    """
    Obtiene señales de Congress para múltiples tickers.
    """
    tracker = CongressTracker()
    results = {}

    for ticker in tickers:
        signal = tracker.get_signal_for_ticker(ticker, days)
        results[ticker] = signal

    return results


if __name__ == '__main__':
    # Test
    print("Testing Congress Tracker...")
    tracker = CongressTracker()

    # Get recent trades
    print("\nFetching recent trades...")
    recent = tracker.get_recent_trades(days=30)
    print(f"Found {len(recent)} trades in last 30 days")

    # High performer trades
    print("\nHigh performer trades:")
    hp_trades = tracker.get_high_performer_trades(days=30)
    print(f"Found {len(hp_trades)} trades from high performers")
    if not hp_trades.empty:
        print(hp_trades[['politician', 'ticker', 'type', 'amount_range']].head(10))

    # Top traded tickers
    print("\nTop traded tickers:")
    top = tracker.get_top_traded_tickers(days=30, limit=10)
    print(top)

    # Signal for specific ticker
    test_ticker = 'NVDA'
    print(f"\nSignal for {test_ticker}:")
    signal = tracker.get_signal_for_ticker(test_ticker)
    print(f"  Signal: {signal['signal']}")
    print(f"  Score: {signal['score']}")
    print(f"  Purchases: {signal['recent_purchases']}")
    print(f"  Sales: {signal['recent_sales']}")
    print(f"  Confidence: {signal['confidence']}")
