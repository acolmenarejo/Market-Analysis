"""
Configuration for Market Analysis Web App
==========================================

Para obtener API keys gratuitas:

1. FINNHUB (Congress Trading):
   - Ve a: https://finnhub.io/register
   - Crea cuenta gratuita
   - Copia tu API key del dashboard
   - Limite: 60 calls/min (suficiente)

2. Otras APIs opcionales (no necesarias para empezar):
   - Alpha Vantage: https://www.alphavantage.co/support/#api-key
   - Polygon.io: https://polygon.io/dashboard/signup
"""

import os
from pathlib import Path

# =============================================================================
# API KEYS
# =============================================================================

# Finnhub - GRATIS, necesaria para Congress Trading
# Obtener en: https://finnhub.io/register
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', '')

# Si prefieres hardcodear tu key (menos seguro pero más fácil):
# FINNHUB_API_KEY = 'tu_api_key_aqui'

# =============================================================================
# PATHS
# =============================================================================

# Directorio raíz del proyecto
ROOT_DIR = Path(__file__).parent.parent

# Base de datos
DATA_DIR = ROOT_DIR / 'data'
DB_PATH = DATA_DIR / 'congress_unified.db'

# =============================================================================
# SETTINGS
# =============================================================================

# Días de histórico a mantener
DEFAULT_HISTORY_DAYS = 90

# Universo de tickers a analizar (expandido)
TICKER_UNIVERSE = [
    # Big Tech
    'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'TSLA', 'NFLX',
    # Semiconductores
    'AVGO', 'AMD', 'INTC', 'QCOM', 'MU', 'ASML', 'TSM', 'AMAT', 'LRCX', 'MRVL',
    # Software
    'CRM', 'ORCL', 'IBM', 'NOW', 'ADBE', 'PLTR', 'SNOW', 'DDOG', 'ZS', 'CRWD',
    # Fintech
    'V', 'MA', 'PYPL', 'SQ', 'COIN', 'HOOD',
    # Banks
    'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'SCHW', 'BLK',
    # Healthcare
    'UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'GILD', 'BMY', 'AMGN', 'REGN', 'MRNA', 'VRTX',
    # Consumer
    'PG', 'KO', 'PEP', 'WMT', 'COST', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW',
    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY',
    # Defense
    'LMT', 'RTX', 'NOC', 'GD', 'BA', 'HII',
    # Industrials
    'CAT', 'DE', 'UNP', 'UPS', 'FDX', 'HON',
    # Telecom/Media
    'VZ', 'T', 'TMUS', 'DIS', 'CMCSA', 'CHTR',
    # REITs / Utilities
    'AMT', 'PLD', 'NEE', 'DUK', 'SO',
    # Other high-volume
    'UBER', 'ABNB', 'SHOP', 'SQ', 'SPOT',
]

# Políticos de alto rendimiento a trackear
HIGH_PROFILE_POLITICIANS = [
    'Nancy Pelosi',
    'Tommy Tuberville',
    'Dan Crenshaw',
    'Brian Mast',
    'Kevin Hern',
    'Richard Blumenthal',
    'Gilbert Cisneros',
    'Josh Gottheimer',
    'Michael McCaul',
    'Pat Fallon',
    'Marjorie Taylor Greene',
]

# =============================================================================
# SCORING WEIGHTS
# =============================================================================

# Pesos por defecto para cada horizonte
SCORING_WEIGHTS = {
    'short_term': {
        'technical': 0.50,
        'momentum': 0.25,
        'speculative': 0.25,
    },
    'medium_term': {
        'momentum': 0.40,
        'quality': 0.30,
        'technical': 0.20,
        'speculative': 0.10,
    },
    'long_term': {
        'value': 0.35,
        'quality': 0.35,
        'stability': 0.20,
        'speculative': 0.10,
    }
}

# =============================================================================
# FUNCIONES HELPER
# =============================================================================

def get_finnhub_key() -> str:
    """Obtiene la API key de Finnhub"""
    key = FINNHUB_API_KEY

    # Try Streamlit secrets (for Streamlit Community Cloud)
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get('FINNHUB_API_KEY', '')
        except Exception:
            pass

    if not key:
        # Intentar leer de archivo .env si existe
        env_file = ROOT_DIR / '.env'
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith('FINNHUB_API_KEY='):
                        key = line.split('=', 1)[1].strip().strip('"\'')
                        break

    return key


def is_configured() -> bool:
    """Verifica si las APIs están configuradas"""
    return bool(get_finnhub_key())


if __name__ == '__main__':
    print("Market Analysis Configuration")
    print("=" * 40)
    print(f"Root dir: {ROOT_DIR}")
    print(f"Data dir: {DATA_DIR}")
    print(f"Finnhub configured: {bool(get_finnhub_key())}")
    print(f"Tickers in universe: {len(TICKER_UNIVERSE)}")

    if not get_finnhub_key():
        print("\n" + "=" * 40)
        print("ACCION REQUERIDA:")
        print("=" * 40)
        print("1. Ve a https://finnhub.io/register")
        print("2. Crea una cuenta gratuita")
        print("3. Copia tu API key")
        print("4. Opciones para configurar:")
        print("   a) Variable de entorno: set FINNHUB_API_KEY=tu_key")
        print("   b) Archivo .env: FINNHUB_API_KEY=tu_key")
        print("   c) Editar webapp/config.py directamente")
