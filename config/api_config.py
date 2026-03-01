"""
===============================================================================
API CONFIGURATION - Market Analysis Enhanced
===============================================================================
Configuración centralizada de APIs y rate limits.

INSTRUCCIONES:
    1. Registrarse en las APIs gratuitas necesarias
    2. Copiar las API keys aquí (o usar variables de entorno)
    3. Las APIs marcadas como "GRATIS" no requieren key

APIs REQUERIDAS:
    - Finnhub: https://finnhub.io/ (gratis, registrarse)
    - Bitquery: https://bitquery.io/ (gratis tier disponible)

APIs OPCIONALES:
    - Alpha Vantage: https://www.alphavantage.co/ (backup noticias)
    - Quiver Quantitative: https://www.quiverquant.com/ (congress data premium)
===============================================================================
"""

import os

# =============================================================================
# API KEYS (usar variables de entorno en producción)
# =============================================================================

API_KEYS = {
    # GRATIS - No requieren key
    'yfinance': None,
    'house_stock_watcher': None,
    'senate_stock_watcher': None,
    'polymarket_gamma': None,

    # FREEMIUM - Requieren registro gratuito
    'finnhub': os.environ.get('FINNHUB_API_KEY', 'YOUR_FINNHUB_KEY'),
    'alpha_vantage': os.environ.get('ALPHA_VANTAGE_KEY', 'YOUR_ALPHA_VANTAGE_KEY'),
    'bitquery': os.environ.get('BITQUERY_API_KEY', 'YOUR_BITQUERY_KEY'),

    # PAGO (opcional)
    'quiver_quant': os.environ.get('QUIVER_API_KEY', None),
    'fmp': os.environ.get('FMP_API_KEY', None),
}

# =============================================================================
# ENDPOINTS
# =============================================================================

API_ENDPOINTS = {
    # Polymarket
    'polymarket_gamma': 'https://gamma-api.polymarket.com',
    'polymarket_clob': 'https://clob.polymarket.com',

    # Congress - Alternativas si S3 falla
    'house_stock_watcher': 'https://housestockwatcher.com/api/all_transactions',
    'senate_stock_watcher': 'https://senatestockwatcher.com/api/all_transactions',

    # Noticias
    'finnhub': 'https://finnhub.io/api/v1',
    'alpha_vantage': 'https://www.alphavantage.co/query',

    # Blockchain (para trades Polymarket)
    'bitquery': 'https://graphql.bitquery.io',
}

# =============================================================================
# RATE LIMITS
# =============================================================================

RATE_LIMITS = {
    'yfinance': {
        'calls_per_minute': 2000,
        'delay_seconds': 0.3,
    },
    'finnhub_free': {
        'calls_per_minute': 60,
        'delay_seconds': 1.1,
    },
    'alpha_vantage_free': {
        'calls_per_minute': 5,
        'delay_seconds': 12,
    },
    'bitquery_free': {
        'calls_per_day': 500,
        'delay_seconds': 2,
    },
    'house_stock_watcher': {
        'calls_per_minute': 30,
        'delay_seconds': 2,
    },
    'polymarket_gamma': {
        'calls_per_minute': 100,
        'delay_seconds': 0.6,
    },
}

# =============================================================================
# CACHE SETTINGS
# =============================================================================

from datetime import timedelta

CACHE_DURATION = {
    'stock_data': timedelta(hours=4),
    'news': timedelta(hours=1),
    'congress_trades': timedelta(hours=24),
    'polymarket_markets': timedelta(minutes=15),
    'polymarket_trades': timedelta(minutes=5),
    'technical_indicators': timedelta(hours=1),
}

# =============================================================================
# SMART MONEY DETECTION THRESHOLDS
# =============================================================================

SMART_MONEY_CONFIG = {
    # Umbral de apuesta grande (USD)
    'large_bet_threshold': 50000,

    # Umbral de apuesta muy grande (USD)
    'whale_bet_threshold': 100000,

    # Días para considerar wallet "fresca"
    'fresh_wallet_days': 7,

    # Umbral de apuesta para wallet fresca (menor, porque es sospechoso)
    'fresh_wallet_bet_threshold': 10000,

    # Categorías de mercados a monitorear
    'market_categories': [
        'politics',
        'economics',
        'fed',
        'crypto',
        'geopolitics',
        'regulatory',
    ],

    # Keywords para detectar mercados relevantes para bolsa
    'market_keywords': [
        'trump', 'biden', 'election', 'president', 'congress', 'senate',
        'fed', 'rate cut', 'rate hike', 'interest rate', 'rate', 'inflation', 'fomc',
        'china', 'russia', 'ukraine', 'iran', 'taiwan', 'north korea', 'venezuela', 'maduro',
        'war', 'strike', 'sanction', 'tariff', 'tax', 'trade war',
        'recession', 'gdp', 'unemployment', 'jobs', 'cpi', 'ppi',
        'oil', 'energy', 'opec', 'gas',
        'tech', 'antitrust', 'regulation', 'sec',
        'crypto', 'bitcoin', 'ethereum',
        'default', 'debt ceiling', 'shutdown', 'budget', 'fiscal',
        'price of', 'market crash', 'bear market', 'bull market',
    ],
}

# =============================================================================
# CONGRESS TRACKER CONFIG
# =============================================================================

CONGRESS_CONFIG = {
    # Políticos con historial notable de "timing"
    'high_performers': [
        'Nancy Pelosi',
        'Tommy Tuberville',
        'Dan Crenshaw',
        'Brian Mast',
        'Josh Gottheimer',
        'Marjorie Taylor Greene',
        'Michael McCaul',
        'Austin Scott',
    ],

    # Umbral de transacción grande (mínimo del rango)
    'large_transaction_min': 50000,

    # Días hacia atrás para buscar trades recientes
    'lookback_days': 30,

    # Sectores regulados (más relevantes para insider info)
    'regulated_sectors': [
        'tech', 'technology',
        'pharma', 'pharmaceutical', 'biotech',
        'defense', 'aerospace',
        'energy', 'oil', 'gas',
        'financial', 'banking',
        'telecom', 'communications',
    ],
}

# =============================================================================
# TECHNICAL ANALYSIS CONFIG
# =============================================================================

TECHNICAL_CONFIG = {
    # RSI
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,

    # MACD
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,

    # Bollinger Bands
    'bb_period': 20,
    'bb_std': 2,

    # Ichimoku
    'ichimoku_tenkan': 9,
    'ichimoku_kijun': 26,
    'ichimoku_senkou_b': 52,

    # ATR para stops
    'atr_period': 14,
    'atr_multiplier_stop': 2.0,
    'atr_multiplier_target': 3.0,

    # Fibonacci levels
    'fib_lookback': 50,
    'fib_levels': [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0],
}

# =============================================================================
# SCORING WEIGHTS
# =============================================================================

# Scoring para horizonte LARGO PLAZO (mensual/trimestral)
LONG_TERM_WEIGHTS = {
    'value': 0.20,
    'quality': 0.25,
    'momentum': 0.15,
    'lowvol': 0.15,
    'congress': 0.10,
    'polymarket': 0.10,
    'news_sentiment': 0.05,
}

# Scoring para horizonte CORTO PLAZO (días/semanas)
SHORT_TERM_WEIGHTS = {
    'technical': 0.35,
    'momentum': 0.25,
    'news_sentiment': 0.20,
    'congress': 0.10,
    'polymarket': 0.10,
}

# =============================================================================
# NEWS SENTIMENT CONFIG
# =============================================================================

NEWS_CONFIG = {
    # Fuente primaria
    'primary_source': 'finnhub',

    # Fuente backup
    'backup_source': 'alpha_vantage',

    # Días hacia atrás para noticias
    'lookback_days': 7,

    # Keywords de alto impacto
    'high_impact_keywords': [
        'earnings', 'revenue', 'guidance', 'forecast',
        'fda', 'approval', 'rejection', 'trial',
        'merger', 'acquisition', 'buyout', 'takeover',
        'lawsuit', 'investigation', 'sec', 'doj',
        'layoff', 'restructuring', 'bankruptcy',
        'dividend', 'buyback', 'split',
        'upgrade', 'downgrade', 'rating',
        'ceo', 'cfo', 'resign', 'appointed',
    ],

    # Categorías de noticias
    'categories': {
        'EARNINGS': ['earnings', 'revenue', 'profit', 'eps', 'guidance'],
        'FDA': ['fda', 'approval', 'trial', 'drug', 'therapy'],
        'M&A': ['merger', 'acquisition', 'buyout', 'deal', 'takeover'],
        'REGULATORY': ['sec', 'doj', 'investigation', 'lawsuit', 'fine'],
        'MANAGEMENT': ['ceo', 'cfo', 'resign', 'appointed', 'board'],
        'FINANCIAL': ['dividend', 'buyback', 'debt', 'offering'],
    },
}


def get_api_key(api_name: str) -> str | None:
    """Obtiene API key, primero de env, luego de config"""
    env_key = os.environ.get(f'{api_name.upper()}_API_KEY')
    if env_key:
        return env_key
    return API_KEYS.get(api_name)


def is_api_configured(api_name: str) -> bool:
    """Verifica si una API está configurada"""
    key = get_api_key(api_name)
    if key is None:
        return True  # APIs sin key
    return key and not key.startswith('YOUR_')
