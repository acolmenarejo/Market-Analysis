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

# Universo de tickers por región
TICKER_UNIVERSE_BY_REGION = {
    'US': [
        # Big Tech
        'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'TSLA', 'NFLX',
        # Semiconductores
        'AVGO', 'AMD', 'INTC', 'QCOM', 'MU', 'TSM', 'AMAT', 'LRCX', 'MRVL', 'ARM', 'SMCI',
        'ON', 'KLAC', 'NXPI', 'TER', 'MPWR', 'SWKS',
        # Software / Cloud
        'CRM', 'ORCL', 'IBM', 'NOW', 'ADBE', 'PLTR', 'SNOW', 'DDOG', 'ZS', 'CRWD',
        'PANW', 'NET', 'TTD', 'HUBS', 'WDAY', 'TEAM', 'ZM', 'DOCU',
        'FTNT', 'MNDY', 'MDB', 'BILL', 'CELH', 'IONQ', 'SOUN',
        # Fintech
        'V', 'MA', 'PYPL', 'XYZ', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'FISV', 'GPN',
        # Banks
        'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'SCHW', 'BLK', 'USB', 'PNC', 'TFC', 'AXP',
        # Healthcare / Biotech
        'UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'GILD', 'BMY', 'AMGN', 'REGN', 'MRNA', 'VRTX',
        'ISRG', 'DXCM', 'ILMN', 'BIIB', 'ZTS', 'CI', 'HUM', 'ELV', 'TMO', 'ABT', 'SYK', 'MDT',
        # Consumer
        'PG', 'KO', 'PEP', 'WMT', 'COST', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW',
        'LULU', 'DECK', 'EL', 'CL', 'GIS', 'KHC', 'MNST', 'STZ',
        # Energy
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY', 'PSX', 'MPC', 'VLO', 'DVN', 'FANG',
        # Defense / Aerospace
        'LMT', 'RTX', 'NOC', 'GD', 'BA', 'HII', 'LHX', 'TDG',
        # Industrials
        'CAT', 'DE', 'UNP', 'UPS', 'FDX', 'HON', 'GE', 'MMM', 'EMR', 'ETN', 'ITW', 'PH',
        # Telecom / Media
        'VZ', 'T', 'TMUS', 'DIS', 'CMCSA', 'CHTR', 'WBD', 'FOX',
        # REITs / Utilities
        'AMT', 'PLD', 'NEE', 'DUK', 'SO', 'SPG', 'O', 'EQIX', 'PSA', 'CCI', 'D', 'AEP', 'SRE',
        # Growth / High-volume
        'UBER', 'ABNB', 'SHOP', 'SPOT', 'RBLX', 'SNAP', 'PINS', 'ROKU',
        'RIVN', 'LCID', 'MELI', 'SE', 'GRAB', 'DASH', 'LYFT', 'CPNG',
        # Materials / Mining
        'FCX', 'NEM', 'LIN', 'APD', 'ECL', 'NUE',
        # Insurance
        'BRK-B', 'PGR', 'TRV', 'ALL', 'MET',
        # AI / Robotics
        'PATH', 'AI', 'RKLB', 'LUNR',
    ],
    'Europe': [
        # UK (.L) — FTSE blue chips
        'SHEL.L', 'AZN.L', 'HSBA.L', 'ULVR.L', 'BP.L', 'GSK.L', 'RIO.L',
        'LSEG.L', 'DGE.L', 'REL.L', 'BARC.L', 'LLOY.L',
        'VOD.L', 'BT-A.L', 'NG.L', 'SSE.L', 'GLEN.L', 'AAL.L',
        # Germany (.DE) — DAX
        'SAP.DE', 'SIE.DE', 'ALV.DE', 'DTE.DE', 'AIR.DE', 'BAS.DE',
        'MBG.DE', 'BMW.DE', 'MUV2.DE', 'IFX.DE', 'ADS.DE',
        'RHM.DE', 'HEN3.DE', 'DB1.DE', 'VOW3.DE',
        # France (.PA) — CAC 40
        'MC.PA', 'OR.PA', 'TTE.PA', 'SAN.PA', 'AI.PA', 'SU.PA',
        'BN.PA', 'CS.PA', 'KER.PA', 'EL.PA', 'SGO.PA', 'CAP.PA',
        # Spain (.MC)
        'ITX.MC', 'SAN.MC', 'IBE.MC', 'TEF.MC', 'BBVA.MC', 'FER.MC', 'AMS.MC',
        # Netherlands (.AS)
        'ASML.AS', 'PHIA.AS', 'UNA.AS', 'INGA.AS', 'AD.AS', 'WKL.AS',
        # Switzerland (.SW)
        'NESN.SW', 'ROG.SW', 'NOVN.SW', 'UBSG.SW', 'ABBN.SW', 'SREN.SW',
        # Italy (.MI)
        'ENI.MI', 'ISP.MI', 'UCG.MI', 'ENEL.MI', 'RACE.MI',
        # Nordic
        'NOVO-B.CO', 'ERIC-B.ST', 'VOLV-B.ST', 'SAND.ST', 'NESTE.HE',
    ],
    'Asia': [
        # Japan (.T)
        '7203.T', '6758.T', '6861.T', '8306.T', '9984.T', '6902.T', '7267.T', '4063.T',
        '6501.T', '7974.T', '8035.T', '9983.T',
        # Hong Kong (.HK)
        '0700.HK', '9988.HK', '1299.HK', '0005.HK', '3690.HK', '9999.HK', '2318.HK',
        '0941.HK', '1810.HK', '2020.HK',
        # China (.SS)
        '600519.SS', '601318.SS', '600036.SS', '601012.SS',
        # Korea (.KS)
        '005930.KS', '000660.KS', '035420.KS', '373220.KS',
        # India (.NS)
        'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'ITC.NS', 'SBIN.NS', 'LT.NS', 'WIPRO.NS',
        # Australia (.AX)
        'BHP.AX', 'CBA.AX', 'CSL.AX', 'WDS.AX', 'NAB.AX', 'WBC.AX', 'FMG.AX',
        # Taiwan (.TW)
        '2330.TW', '2454.TW',
        # Singapore (.SI)
        'D05.SI', 'O39.SI', 'U11.SI',
    ],
    'LatAm': [
        # Brazil (.SA)
        'VALE3.SA', 'PETR4.SA', 'ITUB4.SA', 'BBDC4.SA', 'ABEV3.SA', 'WEGE3.SA',
        'B3SA3.SA', 'RENT3.SA', 'SUZB3.SA', 'GGBR4.SA',
        # Mexico (.MX)
        'FEMSAUBD.MX', 'WALMEX.MX', 'GFNORTEO.MX', 'CEMEXCPO.MX',
        # Argentina (US-listed ADRs)
        'YPF', 'GGAL', 'MELI',
        # Chile / Colombia (US-listed)
        'SQM', 'BSAC', 'CIB', 'EC',
    ],
}

# Backward-compatible flat list (deduplicated)
TICKER_UNIVERSE = list(dict.fromkeys(
    t for region in TICKER_UNIVERSE_BY_REGION.values() for t in region
))

# Ticker → Region mapping for filtering
REGION_MAP = {}
for _region, _tickers in TICKER_UNIVERSE_BY_REGION.items():
    for _t in _tickers:
        REGION_MAP[_t] = _region

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
