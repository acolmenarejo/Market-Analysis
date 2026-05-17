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
        # Big Tech / Mega Cap
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'NVDA', 'TSLA', 'NFLX', 'AVGO',
        # Semiconductores
        'AMD', 'INTC', 'QCOM', 'MU', 'TSM', 'AMAT', 'LRCX', 'MRVL', 'ARM', 'SMCI',
        'ON', 'KLAC', 'NXPI', 'TER', 'MPWR', 'SWKS', 'ASML', 'WOLF', 'ENTG', 'COHR',
        'CRDO', 'ALAB', 'AEHR', 'POWI', 'OLED',
        # Software / Cloud / AI
        'CRM', 'ORCL', 'IBM', 'NOW', 'ADBE', 'PLTR', 'SNOW', 'DDOG', 'ZS', 'CRWD',
        'PANW', 'NET', 'TTD', 'HUBS', 'WDAY', 'TEAM', 'ZM', 'DOCU', 'OKTA', 'SPLK',
        'FTNT', 'MNDY', 'MDB', 'BILL', 'CELH', 'IONQ', 'SOUN', 'INTU', 'CDNS', 'SNPS',
        'ANSS', 'ADSK', 'ROP', 'TYL', 'GTLB', 'S', 'CFLT', 'ESTC', 'TWLO', 'U',
        'BRZE', 'PATH', 'AI', 'BBAI', 'TEM', 'APP',
        # Fintech / Payments
        'V', 'MA', 'PYPL', 'XYZ', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'FISV', 'GPN',
        'FI', 'FIS', 'NU', 'TOST', 'MQ', 'LMND', 'OPEN',
        # Banks / Brokers
        'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'SCHW', 'BLK', 'USB', 'PNC', 'TFC', 'AXP',
        'COF', 'STT', 'BK', 'ALLY', 'KEY', 'RF', 'FITB', 'HBAN', 'CFG', 'MTB',
        'IBKR', 'TROW', 'AMP',
        # Healthcare / Biotech
        'UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'GILD', 'BMY', 'AMGN', 'REGN', 'MRNA', 'VRTX',
        'ISRG', 'DXCM', 'ILMN', 'BIIB', 'ZTS', 'CI', 'HUM', 'ELV', 'TMO', 'ABT', 'SYK', 'MDT',
        'CVS', 'DHR', 'BSX', 'EW', 'BDX', 'A', 'IDXX', 'IQV', 'RMD', 'WST',
        'NVO', 'TAK', 'BNTX', 'CRSP', 'BEAM', 'NTLA', 'VKTX', 'SRPT', 'INCY', 'NBIX',
        # Consumer Discretionary
        'PG', 'KO', 'PEP', 'WMT', 'COST', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW',
        'LULU', 'DECK', 'EL', 'CL', 'GIS', 'KHC', 'MNST', 'STZ', 'TJX', 'BKNG',
        'CMG', 'YUM', 'ORLY', 'AZO', 'ROST', 'BURL', 'DG', 'DLTR', 'KR', 'SYY',
        'F', 'GM', 'STLA', 'TM', 'HMC', 'CHWY', 'ETSY', 'W', 'PTON',
        # Energy
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY', 'PSX', 'MPC', 'VLO', 'DVN', 'FANG',
        'HES', 'KMI', 'WMB', 'ENB', 'TRP', 'OKE', 'EQT', 'CTRA', 'APA', 'MRO',
        'PXD', 'TPL', 'CHK', 'SM',
        # Defense / Aerospace
        'LMT', 'RTX', 'NOC', 'GD', 'BA', 'HII', 'LHX', 'TDG', 'AXON', 'KTOS', 'LDOS',
        'SAIC', 'BAH', 'HEI', 'HWM', 'CW',
        # Industrials
        'CAT', 'DE', 'UNP', 'UPS', 'FDX', 'HON', 'GE', 'MMM', 'EMR', 'ETN', 'ITW', 'PH',
        'CARR', 'OTIS', 'JCI', 'TT', 'DOV', 'PWR', 'NSC', 'CSX', 'WAB', 'CMI',
        'PCAR', 'GWW', 'FAST', 'EXPD', 'ODFL', 'XPO', 'CHRW',
        # Telecom / Media
        'VZ', 'T', 'TMUS', 'DIS', 'CMCSA', 'CHTR', 'WBD', 'FOX', 'PARA', 'NWSA',
        'TKO', 'LBRDA', 'LBRDK',
        # REITs / Utilities
        'AMT', 'PLD', 'NEE', 'DUK', 'SO', 'SPG', 'O', 'EQIX', 'PSA', 'CCI', 'D', 'AEP', 'SRE',
        'EXC', 'XEL', 'PCG', 'EIX', 'PEG', 'WEC', 'AWK', 'DLR', 'WELL', 'VICI',
        'EXR', 'AVB', 'MAA', 'CPT', 'EQR', 'ESS', 'ARE', 'BXP',
        # Growth / High-volume
        'UBER', 'ABNB', 'SHOP', 'SPOT', 'RBLX', 'SNAP', 'PINS', 'ROKU', 'DASH', 'LYFT',
        'RIVN', 'LCID', 'MELI', 'SE', 'GRAB', 'CPNG', 'BIDU', 'JD', 'BABA', 'PDD',
        'NIO', 'XPEV', 'LI',
        # Materials / Mining / Chemicals
        'FCX', 'NEM', 'LIN', 'APD', 'ECL', 'NUE', 'DOW', 'DD', 'PPG', 'SHW',
        'CTVA', 'CF', 'MOS', 'FMC', 'ALB', 'AA', 'X', 'CLF', 'STLD', 'RS',
        # Insurance
        'BRK-B', 'PGR', 'TRV', 'ALL', 'MET', 'CB', 'AIG', 'PRU', 'AFL', 'HIG',
        'WRB', 'AJG', 'MMC', 'AON',
        # AI / Robotics / Space / Quantum
        'RKLB', 'LUNR', 'ASTS', 'ACHR', 'JOBY', 'RGTI', 'QBTS', 'ARQQ', 'INVZ',
        # Crypto / Mining
        'MSTR', 'MARA', 'RIOT', 'CLSK', 'WULF', 'BITF', 'CIFR', 'HUT', 'BITO',
        # ETF references (for cross-validation)
        'SPY', 'QQQ', 'IWM', 'DIA',
    ],
    'Europe': [
        # UK (.L) — FTSE 100/250
        'SHEL.L', 'AZN.L', 'HSBA.L', 'ULVR.L', 'BP.L', 'GSK.L', 'RIO.L', 'BHP.L',
        'LSEG.L', 'DGE.L', 'REL.L', 'BARC.L', 'LLOY.L', 'NWG.L', 'STAN.L',
        'VOD.L', 'BT-A.L', 'NG.L', 'SSE.L', 'GLEN.L', 'AAL.L', 'ANTO.L', 'FRES.L',
        'PRU.L', 'AV.L', 'LGEN.L', 'III.L', 'ABF.L', 'RKT.L', 'IMB.L', 'BATS.L',
        'CRH.L', 'EXPN.L', 'RR.L', 'BA.L', 'CCH.L', 'NXT.L', 'JD.L', 'CPG.L',
        'SMIN.L', 'SGE.L', 'INF.L', 'WPP.L', 'AHT.L', 'BNZL.L',
        # Germany (.DE) — DAX 40 + MDAX
        'SAP.DE', 'SIE.DE', 'ALV.DE', 'DTE.DE', 'AIR.DE', 'BAS.DE', 'BAYN.DE',
        'MBG.DE', 'BMW.DE', 'MUV2.DE', 'IFX.DE', 'ADS.DE', 'PUM.DE',
        'RHM.DE', 'HEN3.DE', 'DB1.DE', 'VOW3.DE', 'POR3.DE', 'CON.DE',
        'DPW.DE', 'EOAN.DE', 'RWE.DE', 'FRE.DE', 'FME.DE', 'MRK.DE',
        'HEI.DE', 'BNR.DE', 'SHL.DE', 'ZAL.DE', 'SY1.DE', 'DBK.DE',
        'CBK.DE', 'LHA.DE', 'TKA.DE', 'EVK.DE',
        # France (.PA) — CAC 40
        'MC.PA', 'OR.PA', 'TTE.PA', 'SAN.PA', 'AI.PA', 'SU.PA', 'BNP.PA',
        'BN.PA', 'CS.PA', 'KER.PA', 'EL.PA', 'SGO.PA', 'CAP.PA', 'GLE.PA',
        'ACA.PA', 'ENGI.PA', 'VIE.PA', 'DG.PA', 'HO.PA', 'STM.PA', 'ML.PA',
        'RNO.PA', 'STLAP.PA', 'PUB.PA', 'LR.PA', 'RI.PA', 'AC.PA', 'EN.PA',
        'CA.PA', 'ORA.PA', 'VIV.PA',
        # Spain (.MC) — IBEX 35
        'ITX.MC', 'SAN.MC', 'IBE.MC', 'TEF.MC', 'BBVA.MC', 'FER.MC', 'AMS.MC',
        'REP.MC', 'CABK.MC', 'ELE.MC', 'ACS.MC', 'NTGY.MC', 'AENA.MC',
        'GRF.MC', 'ANA.MC', 'MAP.MC', 'CLNX.MC', 'MRL.MC', 'RED.MC', 'SAB.MC',
        'BKT.MC', 'IAG.MC', 'ROVI.MC', 'LOG.MC', 'COL.MC',
        # Netherlands (.AS) — AEX
        'ASML.AS', 'PHIA.AS', 'UNA.AS', 'INGA.AS', 'AD.AS', 'WKL.AS', 'PRX.AS',
        'HEIA.AS', 'ASRNL.AS', 'AKZA.AS', 'DSM.AS', 'ASM.AS', 'BESI.AS',
        'KPN.AS', 'NN.AS', 'RAND.AS', 'IMCD.AS', 'JDEP.AS', 'EXO.AS',
        # Switzerland (.SW) — SMI
        'NESN.SW', 'ROG.SW', 'NOVN.SW', 'UBSG.SW', 'ABBN.SW', 'SREN.SW',
        'ZURN.SW', 'CFR.SW', 'GIVN.SW', 'LONN.SW', 'HOLN.SW', 'SIKA.SW',
        'GEBN.SW', 'ALC.SW', 'PGHN.SW', 'KNIN.SW', 'SCMN.SW', 'SOON.SW',
        'LOGN.SW', 'STMN.SW', 'SLHN.SW',
        # Italy (.MI) — FTSE MIB
        'ENI.MI', 'ISP.MI', 'UCG.MI', 'ENEL.MI', 'RACE.MI', 'STLAM.MI',
        'STM.MI', 'G.MI', 'MB.MI', 'TIT.MI', 'PIRC.MI', 'PRY.MI',
        'MONC.MI', 'BMED.MI', 'CPR.MI', 'TRN.MI', 'BAMI.MI', 'BPE.MI',
        'IP.MI', 'TEN.MI', 'ATL.MI', 'BPSO.MI',
        # Nordic — Sweden (.ST), Denmark (.CO), Finland (.HE), Norway (.OL)
        'NOVO-B.CO', 'ERIC-B.ST', 'VOLV-B.ST', 'SAND.ST', 'NESTE.HE',
        'NOKIA.HE', 'KNEBV.HE', 'FORTUM.HE', 'UPM.HE', 'SAMPO.HE',
        'ATCO-A.ST', 'INVE-B.ST', 'HM-B.ST', 'SHB-A.ST', 'SEB-A.ST',
        'SWED-A.ST', 'TELIA.ST', 'ESSITY-B.ST', 'NDA-SE.ST', 'ASSA-B.ST',
        'MAERSK-B.CO', 'CARL-B.CO', 'DSV.CO', 'ORSTED.CO', 'COLO-B.CO',
        'DANSKE.CO', 'TRYG.CO',
        'EQNR.OL', 'DNB.OL', 'TEL.OL', 'YAR.OL', 'NHY.OL', 'AKER.OL',
        # Belgium (.BR), Portugal (.LS), Ireland
        'ABI.BR', 'KBC.BR', 'UCB.BR', 'SOLB.BR',
        'GALP.LS', 'EDP.LS', 'JMT.LS',
        'RYAAY', 'CRH', 'STX', 'ICLR', 'JHX',
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
