#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
SIGNAL DATABASE - Almacenamiento Local de Señales para Backtesting
═══════════════════════════════════════════════════════════════════════════════

Base de datos SQLite local que almacena:
1. Congress trades (cada vez que conseguimos datos)
2. Polymarket signals
3. Scores calculados por nuestro sistema
4. Triggers detectados

Esto nos permite:
- Construir nuestro propio histórico con el tiempo
- Backtestear estrategias con datos reales
- No depender de APIs externas

USO:
    from integrations.signal_database import SignalDatabase
    db = SignalDatabase()
    db.store_congress_trade(...)
    db.store_score(...)
    historical = db.get_historical_scores('NVDA', days=90)

═══════════════════════════════════════════════════════════════════════════════
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os


class SignalDatabase:
    """Base de datos local para almacenar señales y construir histórico."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Usar directorio del proyecto
            base_dir = Path(__file__).parent.parent
            db_path = base_dir / 'data' / 'signals.db'

        # Crear directorio si no existe
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_path)
        self._init_database()

    def _init_database(self):
        """Inicializa las tablas de la base de datos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de Congress trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS congress_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                politician TEXT NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                amount_min REAL,
                amount_max REAL,
                transaction_date DATE,
                disclosure_date DATE,
                chamber TEXT,
                party TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(politician, ticker, transaction_date, action)
            )
        ''')

        # Tabla de Polymarket signals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS polymarket_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                question TEXT,
                ticker TEXT,
                signal_type TEXT,
                probability REAL,
                volume_24h REAL,
                large_bet_amount REAL,
                wallet_age_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabla de scores calculados (nuestro histórico)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculated_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                price REAL,
                target_price REAL,
                upside REAL,
                composite_score REAL,
                value_score REAL,
                quality_score REAL,
                momentum_score REAL,
                lowvol_score REAL,
                congress_score REAL,
                polymarket_score REAL,
                signal TEXT,
                investment_thesis TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            )
        ''')

        # Tabla de triggers detectados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_type TEXT NOT NULL,
                source TEXT,
                ticker TEXT,
                direction TEXT,
                strength REAL,
                rationale TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabla de precios históricos (para validación)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                volume INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            )
        ''')

        # Índices para búsquedas rápidas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_congress_ticker ON congress_trades(ticker)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_congress_date ON congress_trades(transaction_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scores_ticker ON calculated_scores(ticker)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scores_date ON calculated_scores(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prices_ticker ON price_history(ticker)')

        conn.commit()
        conn.close()

    # =========================================================================
    # CONGRESS TRADES
    # =========================================================================

    def store_congress_trade(self, politician: str, ticker: str, action: str,
                              amount_min: float = None, amount_max: float = None,
                              transaction_date: str = None, disclosure_date: str = None,
                              chamber: str = None, party: str = None) -> bool:
        """Almacena un trade de congresista."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO congress_trades
                (politician, ticker, action, amount_min, amount_max,
                 transaction_date, disclosure_date, chamber, party)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (politician, ticker.upper(), action, amount_min, amount_max,
                  transaction_date, disclosure_date, chamber, party))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing congress trade: {e}")
            return False

    def store_congress_trades_bulk(self, trades: List[Dict]) -> int:
        """Almacena múltiples trades de congresistas."""
        stored = 0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for trade in trades:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO congress_trades
                    (politician, ticker, action, amount_min, amount_max,
                     transaction_date, disclosure_date, chamber, party)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade.get('representative', trade.get('politician', '')),
                    trade.get('ticker', '').upper(),
                    trade.get('type', trade.get('action', '')),
                    trade.get('amount_min'),
                    trade.get('amount_max'),
                    trade.get('transaction_date'),
                    trade.get('disclosure_date'),
                    trade.get('chamber', 'house'),
                    trade.get('party', '')
                ))
                if cursor.rowcount > 0:
                    stored += 1
            except Exception as e:
                continue

        conn.commit()
        conn.close()
        return stored

    def get_congress_trades(self, ticker: str = None, politician: str = None,
                            days: int = 365, all_available: bool = False) -> List[Dict]:
        """
        Obtiene trades de congresistas.

        Args:
            ticker: Filtrar por ticker
            politician: Filtrar por nombre de político
            days: Número de días hacia atrás (default 365)
            all_available: Si True, ignora el filtro de fecha y devuelve todos los datos
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if all_available:
            # Sin filtro de fecha - devuelve todos los datos disponibles
            query = 'SELECT * FROM congress_trades WHERE 1=1'
            params = []
        else:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query = '''
                SELECT * FROM congress_trades
                WHERE transaction_date >= ?
            '''
            params = [cutoff_date]

        if ticker:
            query += ' AND ticker = ?'
            params.append(ticker.upper())

        if politician:
            query += ' AND politician LIKE ?'
            params.append(f'%{politician}%')

        query += ' ORDER BY transaction_date DESC'

        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Si no hay resultados con filtro de fecha, intentar sin filtro (fallback)
        if not results and not all_available:
            return self.get_congress_trades(ticker=ticker, politician=politician,
                                           days=days, all_available=True)

        return results

    def get_recent_congress_trades(self, days: int = 90) -> List[Dict]:
        """
        Obtiene TODOS los trades recientes de congresistas (sin filtrar por ticker).
        Wrapper conveniente para la UI del Excel.
        """
        return self.get_congress_trades(ticker=None, politician=None, days=days)

    def get_congress_signal(self, ticker: str, days: int = 60) -> Dict:
        """Calcula señal de Congress para un ticker basada en histórico."""
        trades = self.get_congress_trades(ticker=ticker, days=days)

        if not trades:
            return {'score': 50, 'trades': 0, 'signal': 'NEUTRAL'}

        buys = sum(1 for t in trades if 'purchase' in t['action'].lower())
        sells = sum(1 for t in trades if 'sale' in t['action'].lower())

        total = buys + sells
        if total == 0:
            return {'score': 50, 'trades': 0, 'signal': 'NEUTRAL'}

        # Score basado en ratio compras/ventas
        buy_ratio = buys / total
        score = 50 + (buy_ratio - 0.5) * 60  # Rango 20-80

        signal = 'BULLISH' if score > 60 else ('BEARISH' if score < 40 else 'NEUTRAL')

        return {
            'score': round(score, 1),
            'trades': total,
            'buys': buys,
            'sells': sells,
            'signal': signal
        }

    # =========================================================================
    # CALCULATED SCORES (NUESTRO HISTÓRICO)
    # =========================================================================

    def store_score(self, ticker: str, date: str, data: Dict) -> bool:
        """Almacena score calculado."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO calculated_scores
                (ticker, date, price, target_price, upside, composite_score,
                 value_score, quality_score, momentum_score, lowvol_score,
                 congress_score, polymarket_score, signal, investment_thesis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker.upper(),
                date,
                data.get('price'),
                data.get('target'),
                data.get('upside'),
                data.get('composite_score'),
                data.get('value_score'),
                data.get('quality_score'),
                data.get('momentum_score'),
                data.get('lowvol_score'),
                data.get('congress_score'),
                data.get('polymarket_score'),
                data.get('signal'),
                data.get('investment_thesis')
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing score: {e}")
            return False

    def store_scores_bulk(self, companies: List[Dict], date: str = None) -> int:
        """Almacena múltiples scores (típicamente de una ejecución del analyzer)."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        stored = 0
        for company in companies:
            if self.store_score(company.get('ticker', ''), date, company):
                stored += 1
        return stored

    def get_historical_scores(self, ticker: str, days: int = 90) -> List[Dict]:
        """Obtiene histórico de scores para un ticker."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT * FROM calculated_scores
            WHERE ticker = ? AND date >= ?
            ORDER BY date DESC
        ''', (ticker.upper(), cutoff_date))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    # =========================================================================
    # TRIGGERS
    # =========================================================================

    def store_trigger(self, trigger_type: str, source: str, ticker: str,
                      direction: str, strength: float, rationale: str) -> bool:
        """Almacena un trigger detectado."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO triggers
                (trigger_type, source, ticker, direction, strength, rationale)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (trigger_type, source, ticker.upper() if ticker else None,
                  direction, strength, rationale))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing trigger: {e}")
            return False

    # =========================================================================
    # PRICE HISTORY
    # =========================================================================

    def store_price(self, ticker: str, date: str, open_p: float, high_p: float,
                    low_p: float, close_p: float, volume: int) -> bool:
        """Almacena precio histórico."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO price_history
                (ticker, date, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ticker.upper(), date, open_p, high_p, low_p, close_p, volume))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            return False

    def get_price_history(self, ticker: str, days: int = 365) -> List[Dict]:
        """Obtiene histórico de precios."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT * FROM price_history
            WHERE ticker = ? AND date >= ?
            ORDER BY date DESC
        ''', (ticker.upper(), cutoff_date))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    # =========================================================================
    # ESTADÍSTICAS Y REPORTES
    # =========================================================================

    def get_database_stats(self) -> Dict:
        """Retorna estadísticas de la base de datos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Contar registros en cada tabla
        tables = ['congress_trades', 'polymarket_signals', 'calculated_scores',
                  'triggers', 'price_history']

        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = cursor.fetchone()[0]

        # Rango de fechas de scores
        cursor.execute('SELECT MIN(date), MAX(date) FROM calculated_scores')
        row = cursor.fetchone()
        stats['scores_date_range'] = {'min': row[0], 'max': row[1]}

        # Rango de fechas de congress
        cursor.execute('SELECT MIN(transaction_date), MAX(transaction_date) FROM congress_trades')
        row = cursor.fetchone()
        stats['congress_date_range'] = {'min': row[0], 'max': row[1]}

        # Tickers únicos en scores
        cursor.execute('SELECT COUNT(DISTINCT ticker) FROM calculated_scores')
        stats['unique_tickers_scored'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def get_signal_performance(self, ticker: str, days: int = 90) -> Dict:
        """
        Calcula el rendimiento de las señales históricas para un ticker.
        Útil para validar si las señales funcionaron.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Obtener scores históricos con precios
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT s.date, s.signal, s.composite_score, s.price,
                   p.close_price as future_price
            FROM calculated_scores s
            LEFT JOIN price_history p ON s.ticker = p.ticker
                AND p.date = date(s.date, '+30 days')
            WHERE s.ticker = ? AND s.date >= ?
            ORDER BY s.date
        ''', (ticker.upper(), cutoff_date))

        results = cursor.fetchall()
        conn.close()

        if not results:
            return {'error': 'No hay datos suficientes'}

        # Calcular rendimiento por tipo de señal
        performance = {'BUY': [], 'SELL': [], 'HOLD': []}

        for row in results:
            if row['price'] and row['future_price']:
                return_pct = (row['future_price'] - row['price']) / row['price'] * 100
                signal_type = 'BUY' if 'BUY' in (row['signal'] or '') else \
                              ('SELL' if row['signal'] in ['SELL', 'REDUCE'] else 'HOLD')
                performance[signal_type].append(return_pct)

        summary = {}
        for signal, returns in performance.items():
            if returns:
                summary[signal] = {
                    'count': len(returns),
                    'avg_return': round(sum(returns) / len(returns), 2),
                    'win_rate': round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1)
                }

        return summary


def import_congress_from_api(db: SignalDatabase, api_response: List[Dict]) -> int:
    """
    Importa trades de Congress desde respuesta de API.
    Formato esperado: lista de dicts con campos de House/Senate Stock Watcher.
    """
    return db.store_congress_trades_bulk(api_response)


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN Y TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Test de la base de datos
    print("Inicializando base de datos...")
    db = SignalDatabase()

    print("\nEstadísticas actuales:")
    stats = db.get_database_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test de almacenamiento
    print("\nTest de almacenamiento de trade...")
    db.store_congress_trade(
        politician='Nancy Pelosi',
        ticker='NVDA',
        action='purchase',
        amount_min=100000,
        amount_max=250000,
        transaction_date='2024-01-15',
        chamber='house',
        party='D'
    )

    print("Test de almacenamiento de score...")
    db.store_score('NVDA', datetime.now().strftime('%Y-%m-%d'), {
        'price': 500.0,
        'target': 600.0,
        'upside': 20.0,
        'composite_score': 72.5,
        'value_score': 45.0,
        'quality_score': 80.0,
        'momentum_score': 85.0,
        'lowvol_score': 65.0,
        'congress_score': 75.0,
        'polymarket_score': 50.0,
        'signal': 'BUY',
        'investment_thesis': 'COMPRA: Score alto con momentum fuerte'
    })

    print("\nEstadísticas después de test:")
    stats = db.get_database_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\nSeñal de Congress para NVDA:")
    signal = db.get_congress_signal('NVDA')
    print(f"  {signal}")

    print(f"\nBase de datos ubicada en: {db.db_path}")
