"""
Congress Trades Unified Client
===============================
Combina múltiples fuentes de datos de trades de congresistas:
1. Capitol Trades (scraping)
2. Finnhub API (gratis, 60 calls/min)
3. House Stock Watcher API (gratis)
4. Senate Stock Watcher API (gratis)

Los datos se contrastan entre fuentes para mayor fiabilidad.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import sqlite3
from pathlib import Path
import time
import json
import re
from collections import defaultdict
from bs4 import BeautifulSoup


# =============================================================================
# COMMITTEE -> SECTOR RELEVANCE MAPPING
# =============================================================================
# Trades are flagged as "committee relevant" when a politician trades
# in stocks related to committees they serve on - potential insider signal

POLITICIAN_COMMITTEES = {
    # Healthcare / Health & Human Services
    'kevin hern': ['healthcare', 'pharma', 'insurance'],
    'virginia foxx': ['healthcare', 'education'],
    'cathy mcmorris rodgers': ['healthcare', 'tech'],
    'michael burgess': ['healthcare', 'pharma'],
    'greg murphy': ['healthcare', 'pharma'],

    # Finance / Banking
    'patrick mchenry': ['finance', 'banking', 'crypto'],
    'maxine waters': ['finance', 'banking', 'housing'],
    'french hill': ['finance', 'banking'],
    'bill huizenga': ['finance', 'banking'],

    # Defense / Armed Services
    'tommy tuberville': ['defense', 'aerospace'],
    'roger wicker': ['defense', 'aerospace'],
    'jack reed': ['defense', 'aerospace'],
    'mike rogers': ['defense', 'aerospace'],
    'adam smith': ['defense', 'aerospace'],
    'gilbert cisneros': ['defense', 'aerospace', 'tech'],  # Armed Services + Veterans
    'gilbert ray cisneros': ['defense', 'aerospace', 'tech'],

    # Energy / Natural Resources
    'joe manchin': ['energy', 'oil', 'coal', 'utilities'],
    'john barrasso': ['energy', 'oil', 'utilities'],
    'cathy mcmorris rodgers': ['energy', 'utilities'],

    # Technology / Commerce
    'nancy pelosi': ['tech', 'semiconductors'],  # Spouse runs tech investment firm
    'mark warner': ['tech', 'telecom'],
    'maria cantwell': ['tech', 'telecom', 'commerce'],
    'dan crenshaw': ['tech', 'defense'],
    'josh gottheimer': ['finance', 'tech'],  # Financial Services Committee
    'michael mccaul': ['tech', 'defense', 'semiconductors'],  # China/Tech focus
    'pat fallon': ['defense', 'aerospace'],  # Armed Services

    # Agriculture
    'glenn thompson': ['agriculture', 'food'],
    'david scott': ['agriculture', 'food'],

    # Transportation
    'sam graves': ['transportation', 'airlines', 'logistics'],
    'rick larsen': ['transportation', 'airlines'],

    # Oversight / Government Affairs (broad market impact)
    'marjorie taylor greene': ['defense', 'energy'],  # Oversight Committee
}

SECTOR_TICKERS = {
    'healthcare': ['UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'GILD', 'BMY', 'CVS', 'CI', 'HUM', 'ANTM'],
    'pharma': ['PFE', 'MRK', 'ABBV', 'LLY', 'GILD', 'BMY', 'AMGN', 'BIIB', 'REGN', 'VRTX', 'MRNA', 'BNTX'],
    'insurance': ['UNH', 'CVS', 'CI', 'HUM', 'ANTM', 'ELV', 'CNC', 'MOH'],
    'finance': ['JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'USB', 'PNC', 'SCHW', 'BLK', 'BX', 'KKR'],
    'banking': ['JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'USB', 'PNC', 'TFC', 'FITB', 'RF', 'CFG'],
    'crypto': ['COIN', 'MSTR', 'RIOT', 'MARA', 'HOOD', 'SQ', 'PYPL'],
    'defense': ['LMT', 'RTX', 'NOC', 'GD', 'BA', 'HII', 'LHX', 'LDOS', 'SAIC'],
    'aerospace': ['BA', 'LMT', 'RTX', 'NOC', 'GD', 'HII', 'TDG', 'HWM', 'SPR'],
    'tech': ['AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'CRM', 'ORCL', 'IBM', 'ADBE', 'NOW'],
    'semiconductors': ['NVDA', 'AMD', 'INTC', 'AVGO', 'QCOM', 'TXN', 'MU', 'ASML', 'TSM', 'AMAT', 'LRCX'],
    'energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD', 'MPC', 'VLO', 'PSX', 'OXY'],
    'oil': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD', 'MPC', 'VLO', 'PSX', 'OXY', 'HAL'],
    'utilities': ['NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'XEL', 'ED', 'WEC', 'ES'],
    'telecom': ['VZ', 'T', 'TMUS', 'CMCSA', 'CHTR'],
    'transportation': ['UPS', 'FDX', 'UNP', 'CSX', 'NSC', 'DAL', 'UAL', 'LUV', 'AAL'],
    'airlines': ['DAL', 'UAL', 'LUV', 'AAL', 'JBLU', 'ALK', 'SAVE'],
    'agriculture': ['ADM', 'BG', 'DE', 'CTVA', 'FMC', 'NTR', 'MOS', 'CF'],
    'food': ['PEP', 'KO', 'MDLZ', 'GIS', 'K', 'CPB', 'SJM', 'CAG', 'HSY', 'TSN', 'HRL'],
    'housing': ['HD', 'LOW', 'DHI', 'LEN', 'NVR', 'PHM', 'TOL', 'KBH'],
    'education': ['CHGG', 'UDMY', 'TWOU', 'LRN', 'STRA'],
    'logistics': ['UPS', 'FDX', 'EXPD', 'XPO', 'CHRW', 'JBHT'],
    'commerce': ['AMZN', 'WMT', 'COST', 'TGT', 'HD', 'LOW', 'EBAY', 'ETSY'],
}


def check_committee_relevance(politician: str, ticker: str) -> dict:
    """
    Check if a trade is committee-relevant (politician trading in their oversight area).

    Returns:
        dict with 'relevant' (bool), 'committees' (list), 'reason' (str)
    """
    politician_lower = politician.lower().strip()

    # Find politician's committees/sectors
    relevant_sectors = []
    for name, sectors in POLITICIAN_COMMITTEES.items():
        if name in politician_lower or politician_lower in name:
            relevant_sectors = sectors
            break

    if not relevant_sectors:
        return {'relevant': False, 'sectors': [], 'reason': ''}

    # Check if ticker is in any of the politician's relevant sectors
    ticker_upper = ticker.upper()
    matched_sectors = []

    for sector in relevant_sectors:
        if sector in SECTOR_TICKERS:
            if ticker_upper in SECTOR_TICKERS[sector]:
                matched_sectors.append(sector)

    if matched_sectors:
        return {
            'relevant': True,
            'sectors': matched_sectors,
            'reason': f"Committee oversight: {', '.join(matched_sectors)}"
        }

    return {'relevant': False, 'sectors': [], 'reason': ''}


class DataSource(Enum):
    CAPITOL_TRADES = "capitol_trades"
    FINNHUB = "finnhub"
    HOUSE_WATCHER = "house_watcher"
    SENATE_WATCHER = "senate_watcher"
    QUIVER_QUANT = "quiver_quant"


class TransactionType(Enum):
    BUY = "buy"
    SELL = "sell"
    EXCHANGE = "exchange"


@dataclass
class UnifiedTrade:
    """Trade unificado de múltiples fuentes"""
    politician: str
    party: str  # D, R, I
    chamber: str  # House, Senate
    state: str
    ticker: str
    company: str
    transaction_type: TransactionType
    traded_date: datetime
    disclosed_date: Optional[datetime] = None
    amount_range: str = ""
    price: Optional[float] = None

    # Performance metrics (from QuiverQuant)
    price_change: Optional[float] = None  # % change since trade
    excess_return: Optional[float] = None  # % excess return vs SPY
    spy_change: Optional[float] = None  # SPY % change in same period

    # Metadatos de fuentes
    sources: List[DataSource] = field(default_factory=list)
    confidence: float = 0.0  # 0-100, basado en cuántas fuentes confirman
    raw_data: Dict = field(default_factory=dict)

    # Committee relevance - trades in politician's oversight area
    committee_relevant: bool = False
    committee_sectors: List[str] = field(default_factory=list)
    relevance_reason: str = ""

    def to_dict(self) -> Dict:
        return {
            'politician': self.politician,
            'party': self.party,
            'chamber': self.chamber,
            'state': self.state,
            'ticker': self.ticker,
            'company': self.company,
            'transaction_type': self.transaction_type.value,
            'traded_date': self.traded_date.isoformat() if self.traded_date else None,
            'disclosed_date': self.disclosed_date.isoformat() if self.disclosed_date else None,
            'amount_range': self.amount_range,
            'price': self.price,
            'price_change': self.price_change,
            'excess_return': self.excess_return,
            'spy_change': self.spy_change,
            'sources': [s.value for s in self.sources],
            'confidence': self.confidence,
            'committee_relevant': self.committee_relevant,
            'committee_sectors': self.committee_sectors,
            'relevance_reason': self.relevance_reason,
        }


class CongressUnifiedClient:
    """
    Cliente unificado para datos de Congress Trades.
    Combina y contrasta múltiples fuentes.

    Fuentes principales:
    - QuiverQuant API (funciona bien, datos actualizados)
    - Finnhub API (requiere key gratuita)
    - GitHub mirrors (datos históricos)
    - S3 buckets originales (pueden estar bloqueados)
    """

    # APIs primarias
    FINNHUB_BASE = "https://finnhub.io/api/v1"

    # House Stock Watcher - múltiples URLs para intentar
    HOUSE_WATCHER_URLS = [
        "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
        "https://raw.githubusercontent.com/timothycarambat/house-stock-watcher-data/master/data/all_transactions.json",
    ]

    # Senate Stock Watcher - múltiples URLs para intentar
    SENATE_WATCHER_URLS = [
        "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
        "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json",
    ]

    # Aliases para compatibilidad
    HOUSE_WATCHER_API = HOUSE_WATCHER_URLS[0]
    SENATE_WATCHER_API = SENATE_WATCHER_URLS[0]

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.google.com/',
    }

    # Normalización de nombres de políticos
    NAME_ALIASES = {
        'nancy pelosi': ['pelosi, nancy', 'pelosi nancy', 'nancy patricia pelosi'],
        'tommy tuberville': ['tuberville, tommy', 'thomas tuberville'],
        'dan crenshaw': ['crenshaw, dan', 'daniel crenshaw'],
        'kevin hern': ['hern, kevin', 'kevin ray hern'],
        'gilbert cisneros': ['cisneros, gilbert', 'gilbert ray cisneros', 'gilbert ray cisneros jr', 'gilbert ray cisneros, jr', 'cisneros gilbert'],
        'josh gottheimer': ['gottheimer, josh', 'joshua gottheimer'],
        'michael mccaul': ['mccaul, michael', 'mike mccaul', 'michael t mccaul'],
        'pat fallon': ['fallon, pat', 'patrick fallon'],
        'marjorie taylor greene': ['greene, marjorie', 'mtg', 'marjorie greene'],
    }

    def __init__(self, finnhub_api_key: Optional[str] = None, db_path: Optional[str] = None):
        """
        Args:
            finnhub_api_key: API key de Finnhub (gratis en finnhub.io)
            db_path: Ruta a SQLite para cache
        """
        self.finnhub_key = finnhub_api_key

        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / 'data' / 'congress_unified.db'
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _init_database(self):
        """Crea tablas para cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                politician TEXT NOT NULL,
                party TEXT,
                chamber TEXT,
                state TEXT,
                ticker TEXT,
                company TEXT,
                transaction_type TEXT,
                traded_date TEXT,
                disclosed_date TEXT,
                amount_range TEXT,
                price REAL,
                price_change REAL,
                excess_return REAL,
                spy_change REAL,
                sources TEXT,
                confidence REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(politician, ticker, traded_date, transaction_type)
            )
        ''')

        # Add new columns to existing tables (SQLite doesn't error if column exists)
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN price_change REAL')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN excess_return REAL')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN spy_change REAL')
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                fetch_time TEXT,
                records_count INTEGER,
                success INTEGER
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker ON trades(ticker)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_traded_date ON trades(traded_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_politician ON trades(politician)')

        conn.commit()
        conn.close()

    def _normalize_name(self, name: str) -> str:
        """Normaliza nombre de político para comparación"""
        name_lower = name.lower().strip()

        # Buscar en aliases
        for canonical, aliases in self.NAME_ALIASES.items():
            if name_lower == canonical or name_lower in aliases:
                return canonical

        # Normalización básica: "Last, First" -> "first last"
        if ',' in name_lower:
            parts = name_lower.split(',')
            if len(parts) == 2:
                return f"{parts[1].strip()} {parts[0].strip()}"

        return name_lower

    def _parse_amount(self, amount_str: str) -> Tuple[float, float]:
        """Parsea rango de cantidad como (min, max)"""
        amount_str = amount_str.replace('$', '').replace(',', '').strip().upper()

        ranges = {
            '$1,001 - $15,000': (1001, 15000),
            '$15,001 - $50,000': (15001, 50000),
            '$50,001 - $100,000': (50001, 100000),
            '$100,001 - $250,000': (100001, 250000),
            '$250,001 - $500,000': (250001, 500000),
            '$500,001 - $1,000,000': (500001, 1000000),
            '$1,000,001 - $5,000,000': (1000001, 5000000),
            'Over $5,000,000': (5000001, float('inf')),
        }

        for pattern, (min_val, max_val) in ranges.items():
            if pattern.replace('$', '').replace(',', '').upper() in amount_str:
                return (min_val, max_val)

        # Intentar extraer números
        import re
        numbers = re.findall(r'[\d,]+', amount_str)
        if len(numbers) >= 2:
            try:
                return (float(numbers[0].replace(',', '')), float(numbers[1].replace(',', '')))
            except:
                pass

        return (0, 0)

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parsea múltiples formatos de fecha"""
        if not date_str:
            return None

        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%b %d, %Y',
            '%d %b %Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    # =========================================================================
    # FUENTE 1: House Stock Watcher
    # =========================================================================

    def fetch_house_watcher(self, days: int = 90) -> List[Dict]:
        """
        Obtiene trades del House Stock Watcher.
        API gratuita, datos de la Cámara de Representantes.

        Este API devuelve TODOS los trades históricos en un solo archivo JSON.
        El archivo completo puede tener 10,000+ trades de varios años.

        Intenta múltiples URLs (S3 original + GitHub mirror).
        """
        print("  [House Watcher] Fetching data...")
        trades = []

        # Minimal headers for S3
        s3_headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        }

        # Try multiple URLs
        response = None
        for url in self.HOUSE_WATCHER_URLS:
            try:
                print(f"    Trying: {url[:50]}...")
                response = requests.get(url, headers=s3_headers, timeout=60)
                if response.status_code == 200:
                    print(f"    Success from: {url[:50]}")
                    break
                else:
                    print(f"    Got {response.status_code}, trying next...")
            except requests.exceptions.RequestException as e:
                print(f"    Error: {str(e)[:50]}, trying next...")
                continue

        if not response or response.status_code != 200:
            print(f"  [House Watcher] All URLs failed")
            self._log_fetch(DataSource.HOUSE_WATCHER, 0, False)
            return trades

        try:
            data = response.json()
            cutoff = datetime.now() - timedelta(days=days)

            # Stats para debugging
            total_in_file = len(data)
            skipped_no_date = 0
            skipped_old = 0
            skipped_no_ticker = 0

            for item in data:
                traded_date = self._parse_date(item.get('transaction_date', ''))

                if not traded_date:
                    skipped_no_date += 1
                    continue

                if traded_date < cutoff:
                    skipped_old += 1
                    continue

                ticker = item.get('ticker', '').upper()
                if not ticker or ticker in ['--', 'N/A', '', 'UNKNOWN']:
                    skipped_no_ticker += 1
                    continue

                tx_type = item.get('type', '').lower()
                if 'purchase' in tx_type:
                    transaction_type = 'buy'
                elif 'sale' in tx_type:
                    transaction_type = 'sell'
                else:
                    transaction_type = 'exchange'

                trades.append({
                    'politician': item.get('representative', ''),
                    'party': item.get('party', ''),
                    'chamber': 'House',
                    'state': item.get('state', ''),
                    'ticker': ticker,
                    'company': item.get('asset_description', ''),
                    'transaction_type': transaction_type,
                    'traded_date': traded_date.isoformat() if traded_date else None,
                    'disclosed_date': item.get('disclosure_date', ''),
                    'amount_range': item.get('amount', ''),
                    'source': DataSource.HOUSE_WATCHER.value,
                })

            print(f"  [House Watcher] File has {total_in_file} total, got {len(trades)} in last {days} days")
            print(f"    (Skipped: {skipped_old} old, {skipped_no_ticker} no ticker, {skipped_no_date} no date)")
            self._log_fetch(DataSource.HOUSE_WATCHER, len(trades), True)

        except Exception as e:
            print(f"  [House Watcher] Parse error: {e}")
            self._log_fetch(DataSource.HOUSE_WATCHER, 0, False)

        return trades

    # =========================================================================
    # FUENTE 2: Senate Stock Watcher
    # =========================================================================

    def fetch_senate_watcher(self, days: int = 90) -> List[Dict]:
        """
        Obtiene trades del Senate Stock Watcher.
        API gratuita, datos del Senado.

        Este API devuelve TODOS los trades históricos en un solo archivo JSON.
        El archivo completo puede tener miles de trades de varios años.

        Intenta múltiples URLs (S3 original + GitHub mirror).
        """
        print("  [Senate Watcher] Fetching data...")
        trades = []

        # Minimal headers for S3
        s3_headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        }

        # Try multiple URLs
        response = None
        for url in self.SENATE_WATCHER_URLS:
            try:
                print(f"    Trying: {url[:50]}...")
                response = requests.get(url, headers=s3_headers, timeout=60)
                if response.status_code == 200:
                    print(f"    Success from: {url[:50]}")
                    break
                else:
                    print(f"    Got {response.status_code}, trying next...")
            except requests.exceptions.RequestException as e:
                print(f"    Error: {str(e)[:50]}, trying next...")
                continue

        if not response or response.status_code != 200:
            print(f"  [Senate Watcher] All URLs failed")
            self._log_fetch(DataSource.SENATE_WATCHER, 0, False)
            return trades

        try:
            data = response.json()
            cutoff = datetime.now() - timedelta(days=days)

            # Stats para debugging
            total_in_file = len(data)
            skipped_no_date = 0
            skipped_old = 0
            skipped_no_ticker = 0

            for item in data:
                traded_date = self._parse_date(item.get('transaction_date', ''))

                if not traded_date:
                    skipped_no_date += 1
                    continue

                if traded_date < cutoff:
                    skipped_old += 1
                    continue

                ticker = item.get('ticker', '').upper()
                if not ticker or ticker in ['--', 'N/A', '', 'UNKNOWN']:
                    skipped_no_ticker += 1
                    continue

                tx_type = item.get('type', '').lower()
                if 'purchase' in tx_type:
                    transaction_type = 'buy'
                elif 'sale' in tx_type:
                    transaction_type = 'sell'
                else:
                    transaction_type = 'exchange'

                trades.append({
                    'politician': item.get('senator', ''),
                    'party': item.get('party', ''),
                    'chamber': 'Senate',
                    'state': item.get('state', ''),
                    'ticker': ticker,
                    'company': item.get('asset_description', ''),
                    'transaction_type': transaction_type,
                    'traded_date': traded_date.isoformat() if traded_date else None,
                    'disclosed_date': item.get('disclosure_date', ''),
                    'amount_range': item.get('amount', ''),
                    'source': DataSource.SENATE_WATCHER.value,
                })

            print(f"  [Senate Watcher] File has {total_in_file} total, got {len(trades)} in last {days} days")
            print(f"    (Skipped: {skipped_old} old, {skipped_no_ticker} no ticker, {skipped_no_date} no date)")
            self._log_fetch(DataSource.SENATE_WATCHER, len(trades), True)

        except Exception as e:
            print(f"  [Senate Watcher] Error: {e}")
            self._log_fetch(DataSource.SENATE_WATCHER, 0, False)

        return trades

    # =========================================================================
    # FUENTE 3: Finnhub
    # =========================================================================

    def fetch_finnhub(self, days: int = 90, symbols: Optional[List[str]] = None) -> List[Dict]:
        """
        Obtiene trades de Finnhub API.
        Requiere API key GRATIS de finnhub.io (60 calls/min).

        Para obtener tu API key gratis:
        1. Ve a https://finnhub.io/register
        2. Crea cuenta gratuita
        3. Copia tu API key del dashboard

        Args:
            days: Numero de dias hacia atras
            symbols: Lista de tickers a consultar (si None, usa lista por defecto)
        """
        if not self.finnhub_key:
            print("  [Finnhub] No API key configured")
            print("  [Finnhub] Get FREE key at: https://finnhub.io/register")
            return []

        print("  [Finnhub] Fetching congressional trading data...")
        trades = []

        # Lista de tickers importantes para consultar
        if symbols is None:
            symbols = [
                'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA',
                'AVGO', 'AMD', 'INTC', 'CRM', 'ORCL', 'IBM',
                'JPM', 'BAC', 'GS', 'MS', 'V', 'MA',
                'UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY',
                'XOM', 'CVX', 'COP',
                'PG', 'KO', 'PEP', 'WMT', 'COST', 'HD',
            ]

        cutoff = datetime.now() - timedelta(days=days)

        for symbol in symbols:
            try:
                # Finnhub congressional trading endpoint by symbol
                url = f"{self.FINNHUB_BASE}/stock/congressional-trading"
                params = {
                    'symbol': symbol,
                    'token': self.finnhub_key,
                }

                response = self.session.get(url, params=params, timeout=15)

                if response.status_code == 401:
                    print(f"  [Finnhub] Invalid API key")
                    return trades
                elif response.status_code == 429:
                    print(f"  [Finnhub] Rate limit - waiting...")
                    time.sleep(2)
                    continue
                elif response.status_code != 200:
                    continue

                data = response.json()

                # Finnhub devuelve {symbol: "X", data: [...]}
                for item in data.get('data', []):
                    traded_date = self._parse_date(item.get('transactionDate', ''))

                    if traded_date and traded_date >= cutoff:
                        tx_type = item.get('transactionType', '').lower()
                        if 'purchase' in tx_type or 'buy' in tx_type:
                            transaction_type = 'buy'
                        elif 'sale' in tx_type or 'sell' in tx_type:
                            transaction_type = 'sell'
                        else:
                            transaction_type = 'exchange'

                        name = item.get('name', item.get('representative', ''))

                        trades.append({
                            'politician': name,
                            'party': '',
                            'chamber': item.get('position', ''),  # Representative/Senator
                            'state': '',
                            'ticker': symbol,
                            'company': item.get('assetDescription', ''),
                            'transaction_type': transaction_type,
                            'traded_date': traded_date.isoformat() if traded_date else None,
                            'disclosed_date': item.get('filingDate', ''),
                            'amount_range': f"${item.get('amountFrom', 0):,} - ${item.get('amountTo', 0):,}",
                            'source': DataSource.FINNHUB.value,
                        })

                # Rate limiting - Finnhub free tier allows 60/min
                time.sleep(0.5)

            except Exception as e:
                print(f"  [Finnhub] Error for {symbol}: {e}")
                continue

        print(f"  [Finnhub] Got {len(trades)} trades from {len(symbols)} symbols")
        self._log_fetch(DataSource.FINNHUB, len(trades), len(trades) > 0)

        return trades

    # =========================================================================
    # FUENTE 4: Capitol Trades (scraping)
    # =========================================================================

    def fetch_capitol_trades(self, days: int = 90, max_pages: int = 5) -> List[Dict]:
        """
        Scraping REAL de Capitol Trades.
        Obtiene datos actualizados de capitoltrades.com
        """
        print("  [Capitol Trades] Scraping real data...")
        trades = []
        cutoff = datetime.now() - timedelta(days=days)

        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.capitoltrades.com/trades?page={page}"
                response = self.session.get(url, timeout=30)

                if response.status_code != 200:
                    print(f"  [Capitol Trades] Page {page}: Status {response.status_code}")
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find('table')

                if not table:
                    print(f"  [Capitol Trades] Page {page}: No table found")
                    break

                rows = table.find_all('tr')[1:]  # Skip header

                if not rows:
                    break

                page_trades = 0
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) < 8:
                        continue

                    try:
                        # Column 0: Politician info
                        pol_cell = cells[0]
                        pol_text = pol_cell.get_text(separator='|', strip=True)
                        pol_parts = pol_text.split('|')
                        politician = pol_parts[0] if pol_parts else ''

                        # Extract party from class or text
                        party = ''
                        if 'Republican' in pol_text:
                            party = 'R'
                        elif 'Democrat' in pol_text:
                            party = 'D'

                        # Extract chamber
                        chamber = 'House' if 'House' in pol_text else ('Senate' if 'Senate' in pol_text else '')

                        # Extract state (2-letter code at end)
                        import re
                        state_match = re.search(r'\b([A-Z]{2})\b', pol_text)
                        state = state_match.group(1) if state_match else ''

                        # Column 1: Issuer (ticker) - format: "Company Name | TICKER:US"
                        issuer_cell = cells[1]
                        issuer_text = issuer_cell.get_text(separator='|', strip=True)
                        company = issuer_text.split('|')[0].strip() if '|' in issuer_text else issuer_text

                        # Skip municipal bonds, state bonds, etc. (not tradeable stocks)
                        skip_keywords = ['STATE OF', 'CITY OF', 'COUNTY OF', 'MUNICIPAL',
                                        'DEVELOPMENT AUTH', 'REVENUE BOND', 'TREASURY', 'T-BILL']
                        if any(kw in company.upper() for kw in skip_keywords):
                            continue

                        # Look for TICKER:XX pattern (e.g., GOOGL:US, AB:US)
                        ticker_match = re.search(r'([A-Z]{1,5}):([A-Z]{2})\b', issuer_text)
                        if ticker_match:
                            ticker = ticker_match.group(1)
                        else:
                            # No valid ticker pattern found - skip this entry
                            # Municipal bonds and other non-stocks don't have TICKER:XX format
                            continue

                        # Column 2: Published date (when disclosed)
                        pub_text = cells[2].get_text(strip=True)
                        # Handle "Today", "Yesterday" etc.
                        if 'today' in pub_text.lower():
                            pub_date = datetime.now()
                        elif 'yesterday' in pub_text.lower():
                            pub_date = datetime.now() - timedelta(days=1)
                        else:
                            pub_date = self._parse_capitol_date(pub_text)

                        # Column 3: Traded date (when trade happened)
                        trade_text = cells[3].get_text(strip=True)
                        trade_date = self._parse_capitol_date(trade_text)

                        # Include if EITHER trade OR publication is recent
                        # (Congress members often disclose old trades late)
                        trade_is_recent = trade_date and trade_date >= cutoff
                        pub_is_recent = pub_date and pub_date >= cutoff
                        if not (trade_is_recent or pub_is_recent):
                            continue

                        # Column 5: Owner
                        owner = cells[5].get_text(strip=True)

                        # Column 6: Type (Buy/Sell)
                        type_text = cells[6].get_text(strip=True).upper()
                        if 'BUY' in type_text or 'PURCHASE' in type_text:
                            tx_type = 'buy'
                        elif 'SELL' in type_text or 'SALE' in type_text:
                            tx_type = 'sell'
                        else:
                            tx_type = 'exchange'

                        # Column 7: Size
                        size = cells[7].get_text(strip=True)

                        # Column 8: Price (if exists)
                        price = None
                        if len(cells) > 8:
                            price_text = cells[8].get_text(strip=True)
                            try:
                                price = float(price_text.replace('$', '').replace(',', ''))
                            except:
                                pass

                        if ticker:  # Only add if we have a ticker
                            trades.append({
                                'politician': politician,
                                'party': party,
                                'chamber': chamber,
                                'state': state,
                                'ticker': ticker,
                                'company': company[:50],
                                'transaction_type': tx_type,
                                'traded_date': trade_date.isoformat() if trade_date else None,
                                'disclosed_date': pub_date.isoformat() if pub_date else None,
                                'amount_range': size,
                                'price': price,
                                'owner': owner,
                                'source': DataSource.CAPITOL_TRADES.value,
                            })
                            page_trades += 1

                    except Exception as e:
                        continue

                print(f"  [Capitol Trades] Page {page}: {page_trades} trades")

                if page_trades == 0:
                    break

                # Rate limiting
                time.sleep(1)

            except Exception as e:
                print(f"  [Capitol Trades] Error on page {page}: {e}")
                break

        print(f"  [Capitol Trades] Total: {len(trades)} trades scraped")
        self._log_fetch(DataSource.CAPITOL_TRADES, len(trades), len(trades) > 0)

        return trades

    def _parse_capitol_date(self, date_str: str) -> Optional[datetime]:
        """Parsea fechas de Capitol Trades como '23 Jan2026'"""
        if not date_str:
            return None

        # Clean up the date string
        import re
        date_str = re.sub(r'(\d{1,2}\s*[A-Za-z]+)(\d{4})', r'\1 \2', date_str)

        formats = [
            '%d %b %Y',
            '%d %B %Y',
            '%b %d %Y',
            '%Y-%m-%d',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue

        return None

    def fetch_capitol_trades_mock(self, days: int = 90) -> List[Dict]:
        """
        Datos de respaldo si el scraping falla.
        """
        print("  [Capitol Trades] Using backup mock data...")

        # Datos basados en el screenshot del usuario
        mock_data = [
            {
                'politician': 'Kevin Hern',
                'party': 'R',
                'chamber': 'House',
                'state': 'OK',
                'ticker': 'UNH',
                'company': 'UnitedHealth Group Inc',
                'transaction_type': 'sell',
                'traded_date': '2025-12-23',
                'disclosed_date': '2026-01-23',
                'amount_range': '$250K-$500K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'David Taylor',
                'party': 'R',
                'chamber': 'House',
                'state': 'OH',
                'ticker': 'AVGO',
                'company': 'Broadcom Inc',
                'transaction_type': 'sell',
                'traded_date': '2026-01-08',
                'disclosed_date': '2026-01-22',
                'amount_range': '$1K-$15K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'David Taylor',
                'party': 'R',
                'chamber': 'House',
                'state': 'OH',
                'ticker': 'IBM',
                'company': 'International Business Machines',
                'transaction_type': 'buy',
                'traded_date': '2026-01-08',
                'disclosed_date': '2026-01-22',
                'amount_range': '$15K-$50K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'David Taylor',
                'party': 'R',
                'chamber': 'House',
                'state': 'OH',
                'ticker': 'MSFT',
                'company': 'Microsoft Corp',
                'transaction_type': 'buy',
                'traded_date': '2026-01-08',
                'disclosed_date': '2026-01-22',
                'amount_range': '$1K-$15K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'David Taylor',
                'party': 'R',
                'chamber': 'House',
                'state': 'OH',
                'ticker': 'LRCX',
                'company': 'Lam Research Corp',
                'transaction_type': 'sell',
                'traded_date': '2026-01-08',
                'disclosed_date': '2026-01-22',
                'amount_range': '$15K-$50K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'David Taylor',
                'party': 'R',
                'chamber': 'House',
                'state': 'OH',
                'ticker': 'PG',
                'company': 'Procter & Gamble Co',
                'transaction_type': 'buy',
                'traded_date': '2026-01-09',
                'disclosed_date': '2026-01-22',
                'amount_range': '$1K-$15K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'Nancy Pelosi',
                'party': 'D',
                'chamber': 'House',
                'state': 'CA',
                'ticker': 'NVDA',
                'company': 'NVIDIA Corp',
                'transaction_type': 'buy',
                'traded_date': '2026-01-10',
                'disclosed_date': '2026-01-18',
                'amount_range': '$250K-$500K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'Tommy Tuberville',
                'party': 'R',
                'chamber': 'Senate',
                'state': 'AL',
                'ticker': 'GOOGL',
                'company': 'Alphabet Inc',
                'transaction_type': 'buy',
                'traded_date': '2026-01-05',
                'disclosed_date': '2026-01-17',
                'amount_range': '$50K-$100K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'Dan Crenshaw',
                'party': 'R',
                'chamber': 'House',
                'state': 'TX',
                'ticker': 'META',
                'company': 'Meta Platforms Inc',
                'transaction_type': 'buy',
                'traded_date': '2026-01-03',
                'disclosed_date': '2026-01-15',
                'amount_range': '$15K-$50K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
            {
                'politician': 'Richard Blumenthal',
                'party': 'D',
                'chamber': 'Senate',
                'state': 'CT',
                'ticker': 'AAPL',
                'company': 'Apple Inc',
                'transaction_type': 'sell',
                'traded_date': '2025-12-20',
                'disclosed_date': '2026-01-10',
                'amount_range': '$100K-$250K',
                'source': DataSource.CAPITOL_TRADES.value,
            },
        ]

        print(f"  [Capitol Trades] Got {len(mock_data)} trades (mock)")
        return mock_data

    # =========================================================================
    # UNIFICACIÓN Y CONTRASTE DE DATOS
    # =========================================================================

    def _create_trade_key(self, trade: Dict) -> str:
        """Crea una clave única para identificar un trade"""
        politician = self._normalize_name(trade.get('politician', ''))
        ticker = trade.get('ticker', '').upper()
        traded_date = trade.get('traded_date', '')[:10] if trade.get('traded_date') else ''
        tx_type = trade.get('transaction_type', '')

        return f"{politician}|{ticker}|{traded_date}|{tx_type}"

    def unify_trades(self, all_trades: List[Dict]) -> List[UnifiedTrade]:
        """
        Unifica trades de múltiples fuentes.
        Calcula confianza basada en cuántas fuentes confirman el mismo trade.
        """
        # Agrupar por clave de trade
        trade_groups = defaultdict(list)

        for trade in all_trades:
            key = self._create_trade_key(trade)
            trade_groups[key].append(trade)

        unified = []

        for key, group in trade_groups.items():
            # Tomar datos del primer trade como base
            base = group[0]

            # Recopilar fuentes
            sources = set()
            for t in group:
                source_str = t.get('source', '')
                try:
                    sources.add(DataSource(source_str))
                except:
                    pass

            # Calcular confianza (más fuentes = más confianza)
            # 1 fuente = 50%, 2 fuentes = 75%, 3+ fuentes = 90%+
            num_sources = len(sources)
            if num_sources >= 3:
                confidence = 90 + min(num_sources - 3, 2) * 5  # Max 100
            elif num_sources == 2:
                confidence = 75
            else:
                confidence = 50

            # Enriquecer datos combinando fuentes
            # Ej: si una fuente tiene el estado y otra no, usar el que lo tiene
            politician = base.get('politician', '')
            party = ''
            chamber = ''
            state = ''
            company = ''
            amount = ''

            # Performance metrics (primarily from QuiverQuant)
            price_change = None
            excess_return = None
            spy_change = None

            for t in group:
                if not party and t.get('party'):
                    party = t.get('party')
                if not chamber and t.get('chamber'):
                    chamber = t.get('chamber')
                if not state and t.get('state'):
                    state = t.get('state')
                if not company and t.get('company'):
                    company = t.get('company')
                if not amount and t.get('amount_range'):
                    amount = t.get('amount_range')
                # Get performance metrics from any source that has them
                if price_change is None and t.get('price_change') is not None:
                    price_change = t.get('price_change')
                if excess_return is None and t.get('excess_return') is not None:
                    excess_return = t.get('excess_return')
                if spy_change is None and t.get('spy_change') is not None:
                    spy_change = t.get('spy_change')

            traded_date = self._parse_date(base.get('traded_date', ''))
            disclosed_date = self._parse_date(base.get('disclosed_date', ''))

            tx_type_str = base.get('transaction_type', 'exchange')
            try:
                tx_type = TransactionType(tx_type_str)
            except:
                tx_type = TransactionType.EXCHANGE

            ticker = base.get('ticker', '').upper()

            # Check committee relevance
            relevance = check_committee_relevance(politician, ticker)

            unified_trade = UnifiedTrade(
                politician=politician,
                party=party,
                chamber=chamber,
                state=state,
                ticker=ticker,
                company=company,
                transaction_type=tx_type,
                traded_date=traded_date,
                disclosed_date=disclosed_date,
                amount_range=amount,
                price_change=price_change,
                excess_return=excess_return,
                spy_change=spy_change,
                sources=list(sources),
                confidence=confidence,
                raw_data={'group_size': len(group)},
                committee_relevant=relevance['relevant'],
                committee_sectors=relevance['sectors'],
                relevance_reason=relevance['reason'],
            )

            unified.append(unified_trade)

        # Ordenar por fecha más reciente
        unified.sort(key=lambda x: x.traded_date or datetime.min, reverse=True)

        return unified

    # =========================================================================
    # FUENTE 5: QuiverQuant (multiple methods)
    # =========================================================================

    def fetch_quiver_quant(self, days: int = 90) -> List[Dict]:
        """
        Fetch from QuiverQuant using multiple approaches:
        1. Try their GitHub raw data files
        2. Try embedded JSON in page
        3. Fall back to table scraping
        """
        print("  [QuiverQuant] Fetching congress trades...")
        trades = []
        cutoff = datetime.now() - timedelta(days=days)

        # Method 1: Try GitHub raw data (QuiverQuant publishes data)
        github_trades = self._fetch_quiver_github(cutoff)
        if github_trades:
            trades.extend(github_trades)
            print(f"  [QuiverQuant] Got {len(github_trades)} trades from GitHub")
            self._log_fetch(DataSource.QUIVER_QUANT, len(trades), True)
            return trades

        # Method 2: Try API endpoint (may require key but worth trying)
        api_trades = self._fetch_quiver_api(cutoff)
        if api_trades:
            trades.extend(api_trades)
            print(f"  [QuiverQuant] Got {len(api_trades)} trades from API")
            self._log_fetch(DataSource.QUIVER_QUANT, len(trades), True)
            return trades

        # Method 3: Scrape page for embedded data
        try:
            url = "https://www.quiverquant.com/congresstrading/"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for JSON data in script tags
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        text = script.string
                        # Look for data patterns
                        patterns = [
                            ('"Representative":', 'Representative'),
                            ('"politician":', 'politician'),
                            ('"Ticker":', 'Ticker'),
                        ]
                        for pattern, key in patterns:
                            if pattern in text:
                                try:
                                    start = text.find('[{')
                                    end = text.rfind('}]') + 2
                                    if start > 0 and end > start:
                                        json_str = text[start:end]
                                        data = json.loads(json_str)
                                        for item in data:
                                            trade = self._parse_quiver_item(item, cutoff)
                                            if trade:
                                                trades.append(trade)
                                        if trades:
                                            break
                                except json.JSONDecodeError:
                                    continue

                if trades:
                    print(f"  [QuiverQuant] Extracted {len(trades)} trades from embedded data")
                else:
                    print("  [QuiverQuant] No embedded data found (JS-rendered page)")

        except Exception as e:
            print(f"  [QuiverQuant] Scrape error: {e}")

        self._log_fetch(DataSource.QUIVER_QUANT, len(trades), len(trades) > 0)
        return trades

    def _fetch_quiver_github(self, cutoff: datetime) -> List[Dict]:
        """Try to fetch from QuiverQuant's GitHub data files"""
        trades = []

        # QuiverQuant sometimes publishes data to GitHub
        github_urls = [
            "https://raw.githubusercontent.com/QuiverQuantitative/Congress-Trading/main/congress_trading.csv",
            "https://raw.githubusercontent.com/QuiverQuantitative/Congress-Trading/master/congress_trading.csv",
        ]

        for url in github_urls:
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    import csv
                    from io import StringIO

                    reader = csv.DictReader(StringIO(response.text))
                    for row in reader:
                        traded_date = self._parse_date(
                            row.get('TransactionDate', row.get('transaction_date', ''))
                        )
                        if traded_date and traded_date >= cutoff:
                            tx_type = row.get('Transaction', row.get('Type', '')).lower()
                            if 'purchase' in tx_type or 'buy' in tx_type:
                                transaction_type = 'buy'
                            elif 'sale' in tx_type or 'sell' in tx_type:
                                transaction_type = 'sell'
                            else:
                                transaction_type = 'exchange'

                            trades.append({
                                'politician': row.get('Representative', row.get('Name', '')),
                                'party': row.get('Party', ''),
                                'chamber': row.get('House', 'House'),
                                'state': row.get('State', ''),
                                'ticker': row.get('Ticker', ''),
                                'company': row.get('Description', row.get('Company', '')),
                                'transaction_type': transaction_type,
                                'traded_date': traded_date.isoformat() if traded_date else None,
                                'amount_range': row.get('Range', row.get('Amount', '')),
                                'source': DataSource.QUIVER_QUANT.value,
                            })
                    if trades:
                        return trades
            except Exception as e:
                continue

        return trades

    def _fetch_quiver_api(self, cutoff: datetime) -> List[Dict]:
        """Try QuiverQuant's API endpoint with retry logic"""
        trades = []

        # Try multiple times with different headers (API can be flaky)
        for attempt in range(3):
            try:
                url = "https://api.quiverquant.com/beta/live/congresstrading"

                # Different header combinations for retry attempts
                if attempt == 0:
                    headers = {**self.HEADERS, 'Accept': 'application/json'}
                elif attempt == 1:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                        'Referer': 'https://www.quiverquant.com/congresstrading/',
                    }
                else:
                    # Fresh session for last attempt
                    fresh_session = requests.Session()
                    fresh_session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json, text/html, */*',
                    })
                    response = fresh_session.get(url, timeout=20)
                    if response.status_code == 200:
                        data = response.json()
                        for item in data:
                            trade = self._parse_quiver_item(item, cutoff)
                            if trade:
                                trades.append(trade)
                        if trades:
                            return trades
                    continue

                response = self.session.get(url, headers=headers, timeout=20)

                if response.status_code == 200:
                    data = response.json()
                    for item in data:
                        trade = self._parse_quiver_item(item, cutoff)
                        if trade:
                            trades.append(trade)
                    if trades:
                        return trades
                elif response.status_code == 401:
                    # Try again with different headers
                    time.sleep(0.5)
                    continue

            except Exception as e:
                if attempt < 2:
                    time.sleep(0.5)
                    continue

        return trades

    def _parse_quiver_item(self, item: dict, cutoff: datetime) -> Optional[Dict]:
        """Parse a single QuiverQuant data item"""
        try:
            traded_date = self._parse_date(
                item.get('TransactionDate', item.get('transaction_date', ''))
            )

            if not traded_date or traded_date < cutoff:
                return None

            tx_type = item.get('Transaction', item.get('transaction_type', item.get('Type', ''))).lower()
            if 'purchase' in tx_type or 'buy' in tx_type:
                transaction_type = 'buy'
            elif 'sale' in tx_type or 'sell' in tx_type:
                transaction_type = 'sell'
            else:
                transaction_type = 'exchange'

            ticker = item.get('Ticker', item.get('ticker', ''))
            if not ticker:
                return None

            # Parse disclosed/filed date (ReportDate in QuiverQuant)
            disclosed_date = self._parse_date(
                item.get('ReportDate', item.get('report_date', item.get('filed_date', '')))
            )

            # Parse performance metrics
            price_change = None
            excess_return = None
            spy_change = None

            try:
                if 'PriceChange' in item and item['PriceChange'] is not None:
                    price_change = float(item['PriceChange'])
                if 'ExcessReturn' in item and item['ExcessReturn'] is not None:
                    excess_return = float(item['ExcessReturn'])
                if 'SPYChange' in item and item['SPYChange'] is not None:
                    spy_change = float(item['SPYChange'])
            except (ValueError, TypeError):
                pass

            return {
                'politician': item.get('Representative', item.get('politician', item.get('Name', ''))),
                'party': item.get('Party', ''),
                'chamber': item.get('House', 'House'),
                'state': item.get('State', ''),
                'ticker': ticker.upper(),
                'company': item.get('Description', item.get('Company', '')),
                'transaction_type': transaction_type,
                'traded_date': traded_date.isoformat() if traded_date else None,
                'disclosed_date': disclosed_date.isoformat() if disclosed_date else None,
                'amount_range': item.get('Range', item.get('Amount', '')),
                'price_change': price_change,
                'excess_return': excess_return,
                'spy_change': spy_change,
                'source': DataSource.QUIVER_QUANT.value,
            }
        except Exception:
            return None

    # =========================================================================
    # FUENTE 6: EFDS Official Data (backup - datos oficiales del gobierno)
    # =========================================================================

    def fetch_efds_official(self, days: int = 90) -> List[Dict]:
        """
        Intenta obtener datos del Electronic Financial Disclosure System oficial.

        Fuentes oficiales:
        - House: https://disclosures-clerk.house.gov/
        - Senate: https://efdsearch.senate.gov/

        Nota: Estas fuentes tienen datos completos pero pueden requerir
        scraping más complejo. Los datos de House/Senate Stock Watcher
        ya se basan en estas fuentes oficiales.
        """
        print("  [EFDS Official] Checking additional sources...")
        trades = []
        cutoff = datetime.now() - timedelta(days=days)

        # Intentar obtener datos de ProPublica Congress API (gratis, pública)
        try:
            propublica_trades = self._fetch_propublica(cutoff)
            trades.extend(propublica_trades)
        except Exception as e:
            print(f"    ProPublica: Not available ({e})")

        # Intentar OpenSecrets data (transparencia gubernamental)
        try:
            opensecrets_trades = self._fetch_opensecrets(cutoff)
            trades.extend(opensecrets_trades)
        except Exception as e:
            print(f"    OpenSecrets: Not available ({e})")

        if trades:
            print(f"  [EFDS Official] Got {len(trades)} additional trades")

        return trades

    def _fetch_propublica(self, cutoff: datetime) -> List[Dict]:
        """Intenta obtener datos de la API de ProPublica (Congress API)"""
        # ProPublica Congress API es gratuita pero se enfoca en votes/bills
        # No tiene financial disclosures directamente
        return []

    def _fetch_opensecrets(self, cutoff: datetime) -> List[Dict]:
        """Intenta obtener datos de OpenSecrets"""
        # OpenSecrets tiene datos pero requiere API key
        # Por ahora retornamos vacío
        return []

    # =========================================================================
    # FUENTE 7: Congressional Stock Trades API (alternativo)
    # =========================================================================

    def fetch_congress_gov_api(self, days: int = 90) -> List[Dict]:
        """
        Otra fuente alternativa basada en datos públicos del Congreso.
        Usa el mismo formato que House/Senate Watcher.
        """
        print("  [Congress.gov] Checking for additional data...")
        trades = []

        # Alternative S3 buckets que pueden tener datos más actualizados
        alternative_urls = [
            # Backup URLs que pueden tener datos frescos
            "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
            "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
            # GitHub mirrors
            "https://raw.githubusercontent.com/adampasternack/house-stock-watcher-data/main/data/all_transactions.json",
        ]

        # Ya procesados por House/Senate Watcher, solo intentar mirrors
        for url in alternative_urls[2:]:
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    cutoff = datetime.now() - timedelta(days=days)

                    for item in data:
                        traded_date = self._parse_date(item.get('transaction_date', ''))
                        if traded_date and traded_date >= cutoff:
                            ticker = item.get('ticker', '').upper()
                            if not ticker or ticker in ['--', 'N/A', '']:
                                continue

                            tx_type = item.get('type', '').lower()
                            if 'purchase' in tx_type:
                                transaction_type = 'buy'
                            elif 'sale' in tx_type:
                                transaction_type = 'sell'
                            else:
                                transaction_type = 'exchange'

                            trades.append({
                                'politician': item.get('representative', item.get('senator', '')),
                                'party': item.get('party', ''),
                                'chamber': 'House' if 'representative' in item else 'Senate',
                                'state': item.get('state', ''),
                                'ticker': ticker,
                                'company': item.get('asset_description', ''),
                                'transaction_type': transaction_type,
                                'traded_date': traded_date.isoformat() if traded_date else None,
                                'disclosed_date': item.get('disclosure_date', ''),
                                'amount_range': item.get('amount', ''),
                                'source': 'congress_gov',
                            })

                    if trades:
                        print(f"  [Congress.gov] Got {len(trades)} trades from mirror")
                        return trades

            except Exception as e:
                continue

        return trades

    # =========================================================================
    # FUENTE 8: GitHub Repos con datos estructurados
    # =========================================================================

    def fetch_github_repos(self, days: int = 90) -> List[Dict]:
        """
        Obtiene datos de repositorios GitHub que mantienen datos de congress trades.

        Fuentes:
        - JBellissimo/congressional-transparency-scorecard (datos estructurados)
        - jniranjan371/stock-trades-api (CSV con trades)
        - master0fsavvies/Congressional-Stock-Trade-Extractor (datos históricos)
        """
        print("  [GitHub Repos] Fetching from community repos...")
        trades = []
        cutoff = datetime.now() - timedelta(days=days)

        # Repo 1: JBellissimo (datos bien estructurados, políticos de alto perfil)
        github_sources = [
            {
                'name': 'JBellissimo',
                'url': 'https://raw.githubusercontent.com/JBellissimo/congressional-transparency-scorecard/master/data/raw/stock_trades.csv',
                'columns': {
                    'politician': 'member_name',
                    'party': 'party',
                    'chamber': 'chamber',
                    'state': 'state',
                    'ticker': 'ticker',
                    'company': 'asset_description',
                    'transaction_type': 'transaction_type',
                    'traded_date': 'transaction_date',
                    'disclosed_date': 'disclosure_date',
                    'amount_range': 'amount_raw',
                }
            },
            {
                'name': 'jniranjan371',
                'url': 'https://raw.githubusercontent.com/jniranjan371/stock-trades-api/main/all_transactions.csv',
                'columns': {
                    'politician': 'owner',  # This repo uses 'owner' for politician
                    'party': 'party',
                    'chamber': '',
                    'state': 'state',
                    'ticker': 'ticker',
                    'company': 'asset_description',
                    'transaction_type': 'type',
                    'traded_date': 'transaction_date',
                    'disclosed_date': '',
                    'amount_range': 'amount',
                }
            },
        ]

        for source in github_sources:
            try:
                print(f"    Trying {source['name']}...")
                response = self.session.get(source['url'], timeout=30)

                if response.status_code == 200:
                    import csv
                    from io import StringIO

                    reader = csv.DictReader(StringIO(response.text))
                    source_trades = 0

                    for row in reader:
                        # Get mapped columns
                        cols = source['columns']

                        # Parse date
                        date_str = row.get(cols['traded_date'], '')
                        traded_date = self._parse_date(date_str)

                        if not traded_date or traded_date < cutoff:
                            continue

                        # Get ticker
                        ticker = row.get(cols['ticker'], '').upper().strip()
                        if not ticker or ticker in ['--', 'N/A', '', 'UNKNOWN']:
                            continue

                        # Clean ticker (remove exchange suffix like :US)
                        if ':' in ticker:
                            ticker = ticker.split(':')[0]

                        # Transaction type
                        tx_type = row.get(cols['transaction_type'], '').lower()
                        if 'purchase' in tx_type or 'buy' in tx_type or tx_type == 'p':
                            transaction_type = 'buy'
                        elif 'sale' in tx_type or 'sell' in tx_type or tx_type == 's':
                            transaction_type = 'sell'
                        else:
                            transaction_type = 'exchange'

                        # Build trade
                        trade = {
                            'politician': row.get(cols['politician'], ''),
                            'party': row.get(cols['party'], ''),
                            'chamber': row.get(cols['chamber'], '') if cols['chamber'] else 'House',
                            'state': row.get(cols['state'], ''),
                            'ticker': ticker,
                            'company': row.get(cols['company'], ''),
                            'transaction_type': transaction_type,
                            'traded_date': traded_date.isoformat() if traded_date else None,
                            'disclosed_date': row.get(cols['disclosed_date'], '') if cols['disclosed_date'] else '',
                            'amount_range': row.get(cols['amount_range'], ''),
                            'source': f'github_{source["name"].lower()}',
                        }

                        trades.append(trade)
                        source_trades += 1

                    print(f"    {source['name']}: Got {source_trades} trades")
                else:
                    print(f"    {source['name']}: {response.status_code}")

            except Exception as e:
                print(f"    {source['name']}: Error - {str(e)[:50]}")

        print(f"  [GitHub Repos] Total: {len(trades)} trades")
        return trades

    def fetch_all_sources(self, days: int = 90) -> List[UnifiedTrade]:
        """
        Obtiene datos de todas las fuentes y los unifica.

        Fuentes principales (gratuitas y completas):
        1. House Stock Watcher - Todos los trades de la Cámara de Representantes
        2. Senate Stock Watcher - Todos los trades del Senado
        3. Finnhub API - Datos adicionales con API key gratuita
        4. QuiverQuant - Scraping como respaldo
        5. GitHub Repos - Datos de la comunidad

        NOTA: Capitol Trades removido por limitaciones de scraping.
        """
        print("\n" + "=" * 50)
        print("CONGRESS TRADES - Fetching from all sources")
        print("=" * 50)

        all_trades = []

        # 1. House Stock Watcher (PRINCIPAL - datos completos de la Cámara)
        # Este API tiene TODOS los trades históricos en un solo JSON
        house_trades = self.fetch_house_watcher(days)
        all_trades.extend(house_trades)

        # 2. Senate Stock Watcher (PRINCIPAL - datos completos del Senado)
        # Este API tiene TODOS los trades históricos en un solo JSON
        senate_trades = self.fetch_senate_watcher(days)
        all_trades.extend(senate_trades)

        # 3. Finnhub (si hay API key configurada)
        finnhub_trades = self.fetch_finnhub(days)
        all_trades.extend(finnhub_trades)

        # 4. QuiverQuant (scraping como respaldo)
        try:
            quiver_trades = self.fetch_quiver_quant(days)
            all_trades.extend(quiver_trades)
        except Exception as e:
            print(f"  [QuiverQuant] Failed: {e}")

        # 5. EFDS Official Data (si está disponible)
        try:
            efds_trades = self.fetch_efds_official(days)
            all_trades.extend(efds_trades)
        except Exception as e:
            print(f"  [EFDS] Not available: {e}")

        # 6. GitHub Repos (datos de la comunidad)
        try:
            github_trades = self.fetch_github_repos(days)
            all_trades.extend(github_trades)
        except Exception as e:
            print(f"  [GitHub Repos] Failed: {e}")

        print(f"\nTotal raw trades: {len(all_trades)}")

        # Unificar y contrastar
        unified = self.unify_trades(all_trades)

        print(f"Unified trades: {len(unified)}")

        # Estadísticas de confianza
        high_conf = sum(1 for t in unified if t.confidence >= 75)
        print(f"High confidence (2+ sources): {high_conf} ({high_conf/len(unified)*100:.0f}%)" if unified else "")

        # Guardar en DB
        self._save_to_db(unified)

        return unified

    def _save_to_db(self, trades: List[UnifiedTrade]):
        """Guarda trades unificados en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for trade in trades:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO trades
                    (politician, party, chamber, state, ticker, company, transaction_type,
                     traded_date, disclosed_date, amount_range, price, price_change,
                     excess_return, spy_change, sources, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade.politician,
                    trade.party,
                    trade.chamber,
                    trade.state,
                    trade.ticker,
                    trade.company,
                    trade.transaction_type.value,
                    trade.traded_date.isoformat() if trade.traded_date else None,
                    trade.disclosed_date.isoformat() if trade.disclosed_date else None,
                    trade.amount_range,
                    trade.price,
                    trade.price_change,
                    trade.excess_return,
                    trade.spy_change,
                    json.dumps([s.value for s in trade.sources]),
                    trade.confidence,
                ))
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        conn.close()

    def _log_fetch(self, source: DataSource, count: int, success: bool):
        """Registra el fetch en el log"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO fetch_log (source, fetch_time, records_count, success)
            VALUES (?, ?, ?, ?)
        ''', (source.value, datetime.now().isoformat(), count, 1 if success else 0))
        conn.commit()
        conn.close()

    # =========================================================================
    # QUERIES
    # =========================================================================

    def get_trades(
        self,
        days: int = 30,
        ticker: Optional[str] = None,
        politician: Optional[str] = None,
        transaction_type: Optional[str] = None,
        min_confidence: float = 0,
    ) -> List[Dict]:
        """Obtiene trades de la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        query = "SELECT * FROM trades WHERE traded_date >= ? AND confidence >= ?"
        params = [cutoff, min_confidence]

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())

        if politician:
            query += " AND politician LIKE ?"
            params.append(f"%{politician}%")

        if transaction_type:
            query += " AND transaction_type = ?"
            params.append(transaction_type.lower())

        query += " ORDER BY traded_date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_ticker_summary(self, days: int = 30, min_confidence: float = 50) -> List[Dict]:
        """Resumen por ticker con estadísticas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT
                ticker,
                COUNT(*) as total,
                SUM(CASE WHEN transaction_type = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN transaction_type = 'sell' THEN 1 ELSE 0 END) as sells,
                COUNT(DISTINCT politician) as politicians,
                AVG(confidence) as avg_confidence
            FROM trades
            WHERE traded_date >= ? AND confidence >= ? AND ticker != ''
            GROUP BY ticker
            ORDER BY total DESC
            LIMIT 50
        ''', (cutoff, min_confidence))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            ticker, total, buys, sells, politicians, avg_conf = row

            # Calcular señal
            if buys > sells * 1.5 and politicians >= 2:
                signal = 'STRONG_BUY'
            elif buys > sells:
                signal = 'BULLISH'
            elif sells > buys * 1.5 and politicians >= 2:
                signal = 'STRONG_SELL'
            elif sells > buys:
                signal = 'BEARISH'
            else:
                signal = 'NEUTRAL'

            results.append({
                'ticker': ticker,
                'total': total,
                'buys': buys,
                'sells': sells,
                'politicians': politicians,
                'avg_confidence': round(avg_conf, 1),
                'buy_ratio': round(buys / total, 2) if total > 0 else 0,
                'signal': signal,
            })

        return results

    def get_politician_summary(self, days: int = 90) -> List[Dict]:
        """Resumen por político"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT
                politician,
                party,
                chamber,
                COUNT(*) as total,
                SUM(CASE WHEN transaction_type = 'buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN transaction_type = 'sell' THEN 1 ELSE 0 END) as sells
            FROM trades
            WHERE traded_date >= ?
            GROUP BY politician
            ORDER BY total DESC
            LIMIT 50
        ''', (cutoff,))

        rows = cursor.fetchall()
        conn.close()

        return [{
            'politician': r[0],
            'party': r[1],
            'chamber': r[2],
            'total': r[3],
            'buys': r[4],
            'sells': r[5],
            'buy_ratio': round(r[4] / r[3], 2) if r[3] > 0 else 0,
        } for r in rows]


# Singleton
_client_instance = None

def get_congress_client(finnhub_key: Optional[str] = None) -> CongressUnifiedClient:
    """Obtiene instancia del cliente"""
    global _client_instance
    if _client_instance is None:
        _client_instance = CongressUnifiedClient(finnhub_api_key=finnhub_key)
    return _client_instance


if __name__ == '__main__':
    # Test
    client = CongressUnifiedClient()

    # Fetch de todas las fuentes
    trades = client.fetch_all_sources(days=90)

    print("\n" + "=" * 50)
    print("TRADES MAS RECIENTES (Top 10)")
    print("=" * 50)

    for t in trades[:10]:
        conf_str = f"[{t.confidence:.0f}%]" if t.confidence >= 75 else f"[{t.confidence:.0f}%?]"
        sources_str = ",".join([s.value[:3] for s in t.sources])
        print(f"{conf_str} {t.politician[:20]:20} | {t.ticker:5} | {t.transaction_type.value:4} | {str(t.traded_date)[:10]} | {sources_str}")

    print("\n" + "=" * 50)
    print("RESUMEN POR TICKER (Top 10)")
    print("=" * 50)

    summary = client.get_ticker_summary(days=90)
    for s in summary[:10]:
        print(f"{s['ticker']:5} | {s['total']:3} trades | {s['buys']:2}B/{s['sells']:2}S | {s['politicians']} pols | {s['signal']}")
