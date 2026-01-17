#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
MARKET ANALYZER V13 - SISTEMA SEMI-AUTOMATIZADO
═══════════════════════════════════════════════════════════════════════════════
Script de actualización automática usando yfinance (GRATIS, sin API key)

USO:
    python market_analyzer.py                    # Genera Excel con datos actualizados
    python market_analyzer.py --regime CONTRACTION  # Cambia régimen macro
    python market_analyzer.py --add AAPL GOOGL   # Añade tickers al universo

REQUISITOS:
    pip install yfinance openpyxl pandas numpy

DATOS QUE OBTIENE YFINANCE (GRATIS):
    ✅ Precio actual
    ✅ Forward P/E
    ✅ Trailing P/E
    ✅ EV/EBITDA
    ✅ Beta
    ✅ 52-week high/low
    ✅ Target price (consenso analistas)
    ✅ Analyst recommendations
    ✅ Profit margins
    ✅ ROE
    ✅ Dividend yield
    ✅ Historical prices (para calcular momentum y volatilidad)

LIMITACIONES:
    ⚠️ ROIC no disponible directamente (se aproxima con ROE)
    ⚠️ FCF Yield requiere cálculo manual
    ⚠️ Analyst revisions no disponible (se usa recommendation changes)
    ⚠️ Algunos datos pueden estar desactualizados 1-2 días

AUTOR: Claude (Anthropic) para Peter
FECHA: Enero 2026

V13 UPDATES:
    - Integración con Polymarket (smart money detection)
    - Integración con Congress Tracker (trades de congresistas)
    - Sistema de scoring mejorado con 6 factores
═══════════════════════════════════════════════════════════════════════════════
"""

import yfinance as yf
import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta
import argparse
import sys
import time

# Imports de integraciones (opcionales - funcionan sin ellas)
try:
    from integrations.congress_tracker import CongressTracker
    CONGRESS_AVAILABLE = True
except ImportError:
    CONGRESS_AVAILABLE = False

try:
    from integrations.polymarket_client import PolymarketClient
    POLYMARKET_AVAILABLE = True
except ImportError:
    POLYMARKET_AVAILABLE = False

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Universo de inversión - EDITAR AQUÍ PARA AÑADIR/QUITAR TICKERS
UNIVERSE = {
    'Semiconductores': ['NVDA', 'TSM', 'AMD', 'ASML', 'AVGO', 'QCOM', 'INTC', 'MU'],
    'IA Software': ['ORCL', 'CRM', 'SAP', 'IBM', 'NOW', 'PLTR'],
    'Defensa': ['LMT', 'NOC', 'GD', 'RTX', 'BA'],
    'Lujo': ['MC.PA', 'RACE', 'RMS.PA'],  # Europeos necesitan .PA para Paris
    'Energia': ['CVX', 'XOM', 'TTE', 'SHEL', 'COP'],
    'Defensivo': ['JNJ', 'PG', 'KO', 'PEP', 'WMT', 'COST'],
    'Oro': ['NEM', 'GOLD', 'AEM', 'GFI'],
    'Cobre': ['FCX', 'BHP', 'RIO', 'SCCO'],
    'Nuclear': ['CCJ', 'CEG', 'VST'],
    'China Tech': ['PDD', 'BABA', 'JD', 'BIDU'],
    'Streaming': ['NFLX', 'DIS', 'SPOT'],
    'Pharma': ['NVO', 'MRK', 'LLY', 'PFE'],
}

# Mapeo de países por ticker (para ajustes regionales)
COUNTRY_MAP = {
    'TSM': ('Taiwan', 'Asia'),
    'ASML': ('Netherlands', 'Europe'),
    'SAP': ('Germany', 'Europe'),
    'MC.PA': ('France', 'Europe'),
    'RMS.PA': ('France', 'Europe'),
    'RACE': ('Italy', 'Europe'),
    'TTE': ('France', 'Europe'),
    'SHEL': ('UK', 'Europe'),
    'NVO': ('Denmark', 'Europe'),
    'BHP': ('Australia', 'Asia'),
    'RIO': ('Australia', 'Asia'),
    'PDD': ('China', 'Asia'),
    'BABA': ('China', 'Asia'),
    'JD': ('China', 'Asia'),
    'BIDU': ('China', 'Asia'),
    'GOLD': ('Canada', 'Americas'),
    'AEM': ('Canada', 'Americas'),
    'CCJ': ('Canada', 'Americas'),
    'SPOT': ('Sweden', 'Europe'),
}

# Régimen macro - EDITAR SEGÚN CONDICIONES DE MERCADO
MACRO_CONFIG = {
    'regime': 'LATE_EXPANSION',  # RECOVERY, EXPANSION, LATE_EXPANSION, CONTRACTION
    'risk_appetite': 'NEUTRAL',   # RISK_ON, NEUTRAL, RISK_OFF
}

# Pesos base y ajustes
# V13: Nuevos factores congress y polymarket
BASE_WEIGHTS = {
    'value': 0.20,
    'quality': 0.25,
    'momentum': 0.15,
    'lowvol': 0.15,
    'congress': 0.10,      # Trades de congresistas
    'polymarket': 0.10,    # Smart money de Polymarket
    'news': 0.05,          # Sentimiento de noticias (reservado)
}

REGIME_ADJUSTMENTS = {
    'RECOVERY': {'value': +0.05, 'quality': -0.05, 'momentum': +0.05, 'lowvol': -0.05},
    'EXPANSION': {'value': +0.05, 'quality': 0, 'momentum': +0.05, 'lowvol': -0.10},
    'LATE_EXPANSION': {'value': -0.05, 'quality': +0.05, 'momentum': -0.05, 'lowvol': +0.05},
    'CONTRACTION': {'value': -0.05, 'quality': +0.10, 'momentum': -0.10, 'lowvol': +0.05},
}

RISK_ADJUSTMENTS = {
    'RISK_ON': {'value': 0, 'quality': -0.05, 'momentum': +0.10, 'lowvol': -0.05},
    'NEUTRAL': {'value': 0, 'quality': 0, 'momentum': 0, 'lowvol': 0},
    'RISK_OFF': {'value': 0, 'quality': +0.05, 'momentum': -0.10, 'lowvol': +0.05},
}

# =============================================================================
# ESTILOS EXCEL
# =============================================================================
thin = Side(style='thin', color='CCCCCC')
thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)

DARK_BLUE = '1F4E79'
header_fill = PatternFill(start_color=DARK_BLUE, end_color=DARK_BLUE, fill_type='solid')
subheader_fill = PatternFill(start_color='2E75B6', end_color='2E75B6', fill_type='solid')
green_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
light_green_fill = PatternFill(start_color='D9EAD3', end_color='D9EAD3', fill_type='solid')
light_blue_fill = PatternFill(start_color='DBEEF7', end_color='DBEEF7', fill_type='solid')
yellow_fill = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')
red_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')

white_font = Font(color='FFFFFF', bold=True, size=11)
title_font = Font(color=DARK_BLUE, bold=True, size=16)
green_font = Font(color='006100', bold=True)
red_font = Font(color='9C0006', bold=True)
center = Alignment(horizontal='center', vertical='center', wrap_text=True)
wrap = Alignment(wrap_text=True, vertical='top')

def set_col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

# =============================================================================
# FUNCIONES DE DATOS
# =============================================================================

def get_final_weights():
    """Calcula pesos finales según régimen macro"""
    weights = BASE_WEIGHTS.copy()
    regime_adj = REGIME_ADJUSTMENTS.get(MACRO_CONFIG['regime'], {})
    risk_adj = RISK_ADJUSTMENTS.get(MACRO_CONFIG['risk_appetite'], {})
    
    for factor in weights:
        weights[factor] += regime_adj.get(factor, 0) + risk_adj.get(factor, 0)
    
    total = sum(weights.values())
    return {k: v/total for k, v in weights.items()}


def fetch_stock_data(ticker, sector):
    """
    Obtiene datos de un ticker usando yfinance
    Retorna diccionario con métricas o None si falla
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Datos básicos
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        if not price:
            print(f"  ⚠️ {ticker}: Sin precio disponible")
            return None
        
        name = info.get('shortName', ticker)
        
        # País y región
        country_info = COUNTRY_MAP.get(ticker, ('US', 'Americas'))
        country, region = country_info
        
        # Valoración
        fwd_pe = info.get('forwardPE')
        trailing_pe = info.get('trailingPE')
        ev_ebitda = info.get('enterpriseToEbitda')
        
        # Calidad
        roe = info.get('returnOnEquity', 0)
        if roe:
            roe = roe * 100  # Convertir a porcentaje
        
        op_margin = info.get('operatingMargins', 0)
        if op_margin:
            op_margin = op_margin * 100
        
        profit_margin = info.get('profitMargins', 0)
        if profit_margin:
            profit_margin = profit_margin * 100
        
        # Aproximar ROIC con ROE (simplificación)
        roic = roe * 0.8 if roe else None  # ROIC típicamente menor que ROE
        
        # Deuda
        total_debt = info.get('totalDebt', 0) or 0
        total_cash = info.get('totalCash', 0) or 0
        ebitda = info.get('ebitda', 1) or 1
        net_debt_ebitda = (total_debt - total_cash) / ebitda if ebitda > 0 else None
        
        # FCF Yield aproximado
        free_cf = info.get('freeCashflow', 0) or 0
        market_cap = info.get('marketCap', 1) or 1
        fcf_yield = (free_cf / market_cap) * 100 if market_cap > 0 else None
        
        # Riesgo
        beta = info.get('beta')
        
        # Dividendo
        div_yield = info.get('dividendYield', 0) or 0
        if div_yield:
            div_yield = div_yield * 100
        
        # Target y rating
        target = info.get('targetMeanPrice')
        
        # Recomendación (1=Strong Buy, 5=Sell)
        rec = info.get('recommendationMean', 3)
        # Convertir a escala 1-5 donde 5 es mejor
        rating = 6 - rec if rec else 3
        
        # Momentum - obtener histórico
        try:
            hist = stock.history(period='1y')
            if len(hist) > 0:
                price_1y_ago = hist['Close'].iloc[0]
                mom_12m = ((price - price_1y_ago) / price_1y_ago) * 100
                
                # Volatilidad
                returns = hist['Close'].pct_change().dropna()
                vol_252d = returns.std() * np.sqrt(252) * 100
            else:
                mom_12m = 0
                vol_252d = 30
        except:
            mom_12m = 0
            vol_252d = 30
        
        # Analyst revisions (aproximación con recommendation trend)
        # yfinance no tiene esto directamente, usamos cambio en target
        analyst_rev = 0  # Por defecto neutral
        
        return {
            'ticker': ticker,
            'name': name[:25],  # Truncar nombre largo
            'sector': sector,
            'country': country,
            'region': region,
            'price': round(price, 2) if price else None,
            'fwd_pe': round(fwd_pe, 1) if fwd_pe else None,
            'trailing_pe': round(trailing_pe, 1) if trailing_pe else None,
            'ev_ebitda': round(ev_ebitda, 1) if ev_ebitda else None,
            'fcf_yield': round(fcf_yield, 1) if fcf_yield else None,
            'roic': round(roic, 1) if roic else None,
            'roe': round(roe, 1) if roe else None,
            'op_margin': round(op_margin, 1) if op_margin else None,
            'net_debt_ebitda': round(net_debt_ebitda, 2) if net_debt_ebitda else None,
            'beta': round(beta, 2) if beta else 1.0,
            'vol_252d': round(vol_252d, 1) if vol_252d else 30,
            'mom_12m': round(mom_12m, 1) if mom_12m else 0,
            'analyst_rev': analyst_rev,
            'target': round(target, 2) if target else None,
            'rating': round(rating, 1) if rating else 3.0,
            'dividend_yield': round(div_yield, 2) if div_yield else 0,
        }
        
    except Exception as e:
        print(f"  ❌ {ticker}: Error - {str(e)[:50]}")
        return None


def fetch_all_data():
    """Obtiene datos de todo el universo"""
    companies = []
    total_tickers = sum(len(tickers) for tickers in UNIVERSE.values())
    
    print(f"\n📊 Descargando datos de {total_tickers} tickers...")
    print("=" * 50)
    
    count = 0
    for sector, tickers in UNIVERSE.items():
        print(f"\n📁 {sector}:")
        for ticker in tickers:
            count += 1
            print(f"  [{count}/{total_tickers}] {ticker}...", end=" ")
            
            data = fetch_stock_data(ticker, sector)
            if data:
                companies.append(data)
                print(f"✅ ${data['price']}")
            else:
                print("❌")
            
            # Pausa para evitar rate limiting
            time.sleep(0.3)
    
    print(f"\n✅ Datos obtenidos: {len(companies)}/{total_tickers} tickers")
    return companies


def percentile_rank(values, reverse=False):
    """Calcula percentiles (0-100)"""
    result = []
    valid_with_idx = [(i, v) for i, v in enumerate(values) if v is not None]
    if not valid_with_idx:
        return [50.0 for _ in values]
    
    sorted_vals = sorted(valid_with_idx, key=lambda x: x[1], reverse=reverse)
    ranks = {idx: ((rank + 1) / len(sorted_vals)) * 100 
             for rank, (idx, _) in enumerate(sorted_vals)}
    
    for i, v in enumerate(values):
        result.append(ranks.get(i, 50.0) if v is not None else 50.0)
    return result


def calculate_scores(companies):
    """Calcula scores multifactor para todas las empresas (V13: 6 factores)"""
    weights = get_final_weights()

    # V13: Inicializar trackers si están disponibles
    congress_tracker = None
    polymarket_client = None
    congress_signals = {}
    polymarket_signals = {}

    if CONGRESS_AVAILABLE:
        try:
            congress_tracker = CongressTracker()
            print("  📊 Obteniendo señales de Congress...")
            for c in companies:
                ticker = c['ticker']
                signal = congress_tracker.get_signal_for_ticker(ticker, days=30)
                congress_signals[ticker] = signal.get('score', 50)
        except Exception as e:
            print(f"  ⚠️ Congress tracker error: {e}")

    if POLYMARKET_AVAILABLE:
        try:
            polymarket_client = PolymarketClient()
            print("  📊 Obteniendo señales de Polymarket...")
            for c in companies:
                ticker = c['ticker']
                signal = polymarket_client.get_signal_for_ticker(ticker)
                polymarket_signals[ticker] = signal.get('score', 50)
        except Exception as e:
            print(f"  ⚠️ Polymarket client error: {e}")

    # Extraer métricas
    fwd_pes = [c.get('fwd_pe') or c.get('trailing_pe') for c in companies]
    ev_ebitdas = [c.get('ev_ebitda') for c in companies]
    fcf_yields = [c.get('fcf_yield') for c in companies]
    roics = [c.get('roic') or c.get('roe') for c in companies]
    op_margins = [c.get('op_margin') for c in companies]
    net_debt_ebitdas = [c.get('net_debt_ebitda') for c in companies]
    betas = [c.get('beta') for c in companies]
    vols = [c.get('vol_252d') for c in companies]
    mom_12ms = [c.get('mom_12m') for c in companies]
    analyst_revs = [c.get('analyst_rev') for c in companies]

    # Calcular percentiles
    value_pe_pctl = percentile_rank(fwd_pes, reverse=True)
    value_ev_pctl = percentile_rank(ev_ebitdas, reverse=True)
    value_fcf_pctl = percentile_rank(fcf_yields, reverse=False)
    qual_roic_pctl = percentile_rank(roics, reverse=False)
    qual_margin_pctl = percentile_rank(op_margins, reverse=False)
    qual_debt_pctl = percentile_rank(net_debt_ebitdas, reverse=True)
    mom_return_pctl = percentile_rank(mom_12ms, reverse=False)
    mom_rev_pctl = percentile_rank(analyst_revs, reverse=False)
    risk_beta_pctl = percentile_rank(betas, reverse=True)
    risk_vol_pctl = percentile_rank(vols, reverse=True)

    for i, c in enumerate(companies):
        # Factor scores tradicionales
        c['value_score'] = (value_pe_pctl[i] + value_ev_pctl[i] + value_fcf_pctl[i]) / 3
        c['quality_score'] = (qual_roic_pctl[i] + qual_margin_pctl[i] + qual_debt_pctl[i]) / 3
        c['momentum_score'] = (mom_return_pctl[i] + mom_rev_pctl[i]) / 2
        c['lowvol_score'] = (risk_beta_pctl[i] + risk_vol_pctl[i]) / 2

        # V13: Nuevos factores
        ticker = c['ticker']
        c['congress_score'] = congress_signals.get(ticker, 50)
        c['polymarket_score'] = polymarket_signals.get(ticker, 50)
        c['news_score'] = 50  # Reservado para futuro uso

        # Ajuste regional
        region_adj = 0
        if c['country'] == 'China':
            region_adj = -10
        elif c['region'] == 'Europe' and c['sector'] in ['Defensa', 'Energia']:
            region_adj = +5
        c['region_adj'] = region_adj

        # Score compuesto V13 (6 factores + ajustes)
        c['composite_score'] = (
            c['value_score'] * weights.get('value', 0.20) +
            c['quality_score'] * weights.get('quality', 0.25) +
            c['momentum_score'] * weights.get('momentum', 0.15) +
            c['lowvol_score'] * weights.get('lowvol', 0.15) +
            c['congress_score'] * weights.get('congress', 0.10) +
            c['polymarket_score'] * weights.get('polymarket', 0.10) +
            region_adj
        )

        # Drivers (incluye nuevos factores)
        factor_contributions = {
            'Value': (c['value_score'] - 50) * weights.get('value', 0.20),
            'Quality': (c['quality_score'] - 50) * weights.get('quality', 0.25),
            'Momentum': (c['momentum_score'] - 50) * weights.get('momentum', 0.15),
            'LowVol': (c['lowvol_score'] - 50) * weights.get('lowvol', 0.15),
            'Congress': (c['congress_score'] - 50) * weights.get('congress', 0.10),
            'Polymarket': (c['polymarket_score'] - 50) * weights.get('polymarket', 0.10),
        }
        sorted_factors = sorted(factor_contributions.items(),
                               key=lambda x: abs(x[1]), reverse=True)

        positive = [(f, round(v, 1)) for f, v in sorted_factors if v > 0][:3]
        negative = [(f, round(v, 1)) for f, v in sorted_factors if v < 0][:3]

        c['drivers_str'] = ' + '.join([f"{f}({v:+.1f})" for f, v in positive]) if positive else "None"
        c['detractors_str'] = ' - '.join([f"{f}({abs(v):.1f})" for f, v in negative]) if negative else "None"

        # Señal
        score = c['composite_score']
        if score >= 60: c['signal'] = 'BUY'
        elif score >= 50: c['signal'] = 'ACCUMULATE'
        elif score >= 40: c['signal'] = 'HOLD'
        elif score >= 30: c['signal'] = 'REDUCE'
        else: c['signal'] = 'SELL'

        # Upside
        if c['target'] and c['price']:
            c['upside'] = ((c['target'] - c['price']) / c['price']) * 100
        else:
            c['upside'] = 0

    # Ordenar por score
    companies.sort(key=lambda x: x['composite_score'], reverse=True)
    return companies


# =============================================================================
# GENERACIÓN DE EXCEL
# =============================================================================

def create_excel(companies, output_path):
    """Genera el Excel con todas las hojas"""
    wb = Workbook()
    weights = get_final_weights()
    
    # =========================================================================
    # HOJA 1: DASHBOARD
    # =========================================================================
    ws_dash = wb.active
    ws_dash.title = 'Dashboard'
    
    ws_dash['A1'] = f'📊 MULTIFACTOR DASHBOARD - {datetime.now().strftime("%d %b %Y %H:%M")}'
    ws_dash['A1'].font = title_font
    ws_dash.merge_cells('A1:L1')
    
    ws_dash['A2'] = f'Régimen: {MACRO_CONFIG["regime"]} | Risk: {MACRO_CONFIG["risk_appetite"]} | V{weights.get("value",0.20)*100:.0f}% Q{weights.get("quality",0.25)*100:.0f}% M{weights.get("momentum",0.15)*100:.0f}% L{weights.get("lowvol",0.15)*100:.0f}% C{weights.get("congress",0.10)*100:.0f}% P{weights.get("polymarket",0.10)*100:.0f}%'
    ws_dash['A2'].font = Font(italic=True)
    
    headers = ['#', 'Ticker', 'Empresa', 'Sector', 'Precio', 'Score', 'Señal', 
               'Value', 'Quality', 'Mom', 'LowVol', 'Drivers']
    
    for col, h in enumerate(headers, 1):
        cell = ws_dash.cell(row=4, column=col, value=h)
        cell.fill = header_fill
        cell.font = white_font
        cell.alignment = center
    
    for i, c in enumerate(companies, 1):
        row = i + 4
        
        ws_dash.cell(row=row, column=1, value=i).border = thin_border
        ws_dash.cell(row=row, column=2, value=c['ticker']).border = thin_border
        ws_dash.cell(row=row, column=2).font = Font(bold=True)
        ws_dash.cell(row=row, column=3, value=c['name']).border = thin_border
        ws_dash.cell(row=row, column=4, value=c['sector']).border = thin_border
        
        cell_price = ws_dash.cell(row=row, column=5, value=c['price'])
        cell_price.border = thin_border
        cell_price.number_format = '$#,##0.00'
        
        cell_score = ws_dash.cell(row=row, column=6, value=round(c['composite_score'], 1))
        cell_score.border = thin_border
        cell_score.alignment = center
        if c['composite_score'] >= 60:
            cell_score.fill = green_fill
            cell_score.font = green_font
        elif c['composite_score'] >= 50:
            cell_score.fill = light_green_fill
        elif c['composite_score'] < 40:
            cell_score.fill = red_fill
            cell_score.font = red_font
        
        cell_signal = ws_dash.cell(row=row, column=7, value=c['signal'])
        cell_signal.border = thin_border
        cell_signal.alignment = center
        if c['signal'] == 'BUY':
            cell_signal.fill = green_fill
            cell_signal.font = green_font
        elif c['signal'] == 'ACCUMULATE':
            cell_signal.fill = light_green_fill
        elif c['signal'] == 'HOLD':
            cell_signal.fill = yellow_fill
        elif c['signal'] in ['REDUCE', 'SELL']:
            cell_signal.fill = red_fill
            cell_signal.font = red_font
        
        for j, score in enumerate([c['value_score'], c['quality_score'], 
                                   c['momentum_score'], c['lowvol_score']], 8):
            cell = ws_dash.cell(row=row, column=j, value=round(score, 0))
            cell.border = thin_border
            cell.alignment = center
        
        ws_dash.cell(row=row, column=12, value=c['drivers_str']).border = thin_border
        ws_dash.cell(row=row, column=12).font = Font(size=9, color='006100')
    
    set_col_widths(ws_dash, [4, 8, 22, 14, 10, 8, 12, 8, 8, 8, 8, 35])
    
    # =========================================================================
    # HOJA 2: RAW DATA
    # =========================================================================
    ws_raw = wb.create_sheet('Raw_Data')
    
    raw_headers = ['Ticker', 'Name', 'Sector', 'Country', 'Price', 'Fwd_PE', 
                   'EV_EBITDA', 'FCF_Yield', 'ROIC', 'Op_Margin', 'Net_Debt_EBITDA',
                   'Beta', 'Vol_252d', 'Mom_12M', 'Target', 'Rating', 'Div_Yield']
    
    for col, h in enumerate(raw_headers, 1):
        cell = ws_raw.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = white_font
    
    for i, c in enumerate(companies, 1):
        row = i + 1
        ws_raw.cell(row=row, column=1, value=c['ticker'])
        ws_raw.cell(row=row, column=2, value=c['name'])
        ws_raw.cell(row=row, column=3, value=c['sector'])
        ws_raw.cell(row=row, column=4, value=c['country'])
        ws_raw.cell(row=row, column=5, value=c['price'])
        ws_raw.cell(row=row, column=6, value=c.get('fwd_pe'))
        ws_raw.cell(row=row, column=7, value=c.get('ev_ebitda'))
        ws_raw.cell(row=row, column=8, value=c.get('fcf_yield'))
        ws_raw.cell(row=row, column=9, value=c.get('roic'))
        ws_raw.cell(row=row, column=10, value=c.get('op_margin'))
        ws_raw.cell(row=row, column=11, value=c.get('net_debt_ebitda'))
        ws_raw.cell(row=row, column=12, value=c.get('beta'))
        ws_raw.cell(row=row, column=13, value=c.get('vol_252d'))
        ws_raw.cell(row=row, column=14, value=c.get('mom_12m'))
        ws_raw.cell(row=row, column=15, value=c.get('target'))
        ws_raw.cell(row=row, column=16, value=c.get('rating'))
        ws_raw.cell(row=row, column=17, value=c.get('dividend_yield'))
    
    set_col_widths(ws_raw, [8, 22, 14, 10, 10, 10, 12, 10, 10, 12, 14, 8, 10, 10, 10, 8, 10])
    
    # =========================================================================
    # HOJA 3: ACTION LIST
    # =========================================================================
    ws_action = wb.create_sheet('Action_List')
    
    ws_action['A1'] = f'🎯 ACTION LIST - {datetime.now().strftime("%d %b %Y")}'
    ws_action['A1'].font = title_font
    ws_action.merge_cells('A1:F1')
    
    # BUY
    ws_action['A3'] = '🟢 COMPRAR (Score ≥60)'
    ws_action['A3'].font = Font(bold=True, size=12, color='006100')
    ws_action['A3'].fill = green_fill
    
    action_headers = ['Ticker', 'Empresa', 'Score', 'Precio', 'Target', 'Upside%', 'Drivers']
    for col, h in enumerate(action_headers, 1):
        cell = ws_action.cell(row=4, column=col, value=h)
        cell.fill = light_green_fill
        cell.font = Font(bold=True)
    
    row = 5
    buy_list = [c for c in companies if c['signal'] == 'BUY']
    for c in buy_list:
        ws_action.cell(row=row, column=1, value=c['ticker']).font = Font(bold=True)
        ws_action.cell(row=row, column=2, value=c['name'])
        ws_action.cell(row=row, column=3, value=round(c['composite_score'], 1))
        ws_action.cell(row=row, column=4, value=c['price'])
        ws_action.cell(row=row, column=5, value=c.get('target', ''))
        ws_action.cell(row=row, column=6, value=f"{c['upside']:.0f}%" if c['upside'] else '')
        ws_action.cell(row=row, column=7, value=c['drivers_str'])
        for col in range(1, 8):
            ws_action.cell(row=row, column=col).border = thin_border
        row += 1
    
    if not buy_list:
        ws_action.cell(row=row, column=1, value='No hay señales BUY actualmente')
        row += 1
    
    # ACCUMULATE
    row += 1
    ws_action.cell(row=row, column=1, value='🟡 ACUMULAR (Score 50-59)').font = Font(bold=True, size=12)
    ws_action.cell(row=row, column=1).fill = yellow_fill
    row += 1
    
    for col, h in enumerate(action_headers, 1):
        cell = ws_action.cell(row=row, column=col, value=h)
        cell.fill = yellow_fill
        cell.font = Font(bold=True)
    row += 1
    
    acc_list = [c for c in companies if c['signal'] == 'ACCUMULATE'][:10]
    for c in acc_list:
        ws_action.cell(row=row, column=1, value=c['ticker']).font = Font(bold=True)
        ws_action.cell(row=row, column=2, value=c['name'])
        ws_action.cell(row=row, column=3, value=round(c['composite_score'], 1))
        ws_action.cell(row=row, column=4, value=c['price'])
        ws_action.cell(row=row, column=5, value=c.get('target', ''))
        ws_action.cell(row=row, column=6, value=f"{c['upside']:.0f}%" if c['upside'] else '')
        ws_action.cell(row=row, column=7, value=c['drivers_str'])
        for col in range(1, 8):
            ws_action.cell(row=row, column=col).border = thin_border
        row += 1
    
    # AVOID
    row += 1
    ws_action.cell(row=row, column=1, value='🔴 EVITAR (Score <40)').font = Font(bold=True, size=12, color='9C0006')
    ws_action.cell(row=row, column=1).fill = red_fill
    row += 1
    
    avoid_headers = ['Ticker', 'Empresa', 'Score', 'Señal', 'Detractors']
    for col, h in enumerate(avoid_headers, 1):
        cell = ws_action.cell(row=row, column=col, value=h)
        cell.fill = red_fill
        cell.font = Font(bold=True, color='FFFFFF')
    row += 1
    
    avoid_list = [c for c in companies if c['signal'] in ['REDUCE', 'SELL']]
    for c in avoid_list:
        ws_action.cell(row=row, column=1, value=c['ticker'])
        ws_action.cell(row=row, column=2, value=c['name'])
        ws_action.cell(row=row, column=3, value=round(c['composite_score'], 1))
        ws_action.cell(row=row, column=4, value=c['signal'])
        ws_action.cell(row=row, column=5, value=c['detractors_str'])
        for col in range(1, 6):
            ws_action.cell(row=row, column=col).border = thin_border
        row += 1
    
    set_col_widths(ws_action, [10, 22, 8, 10, 10, 10, 40])
    
    # =========================================================================
    # HOJA 4: WEEKLY ROUTINE
    # =========================================================================
    ws_routine = wb.create_sheet('Weekly_Routine')
    
    ws_routine['A1'] = '📅 RUTINA SEMANAL DE INVERSIÓN'
    ws_routine['A1'].font = title_font
    ws_routine.merge_cells('A1:D1')
    
    routine_data = [
        ['', '', '', ''],
        ['DÍA', 'ACTIVIDAD', 'DURACIÓN', 'OUTPUT'],
        ['Domingo PM', '1. Ejecutar: python market_analyzer.py', '5 min', 'Excel actualizado'],
        ['Domingo PM', '2. Revisar Dashboard: ordenar por Score', '10 min', 'Top 10 candidatos'],
        ['Domingo PM', '3. Revisar Action_List: BUY y ACCUMULATE', '10 min', 'Lista de órdenes'],
        ['Domingo PM', '4. Verificar régimen macro (VIX, spreads)', '5 min', 'Confirmar pesos'],
        ['Lunes AM', '5. Ejecutar órdenes pre-market', '15 min', 'Trades colocados'],
        ['Miércoles', '6. Check noticias relevantes de posiciones', '15 min', 'Alertas si hay'],
        ['Viernes PM', '7. Revisar P&L semanal en Portfolio_Tracker', '10 min', 'Performance'],
        ['', '', '', ''],
        ['MENSUAL', 'Verificar que datos yfinance son coherentes', '30 min', 'Auditoría'],
        ['TRIMESTRAL', 'Rebalanceo: ajustar posiciones a targets', '1 hora', 'Portfolio alineado'],
        ['', '', '', ''],
        ['TRIGGERS DE ACCIÓN', '', '', ''],
        ['Score cruza 60↑', 'Añadir posición hasta 5% portfolio', 'Inmediato', ''],
        ['Score cruza 50↓', 'Parar de añadir, mantener', '1-2 días', ''],
        ['Score cruza 40↓', 'Reducir posición 50%', '1 semana', ''],
        ['Score cruza 30↓', 'Cerrar posición', 'Inmediato', ''],
        ['VIX > 25', 'Pausar compras, revisar hedges', 'Mismo día', ''],
    ]
    
    for i, row_data in enumerate(routine_data):
        for col, val in enumerate(row_data, 1):
            cell = ws_routine.cell(row=i+3, column=col, value=val)
            if i == 1:
                cell.fill = header_fill
                cell.font = white_font
            elif val and 'TRIGGERS' in val:
                cell.font = Font(bold=True, size=12, color=DARK_BLUE)
            elif val and ('Ejecutar' in val or 'cruza' in val):
                cell.fill = light_blue_fill
            cell.border = thin_border
    
    set_col_widths(ws_routine, [18, 45, 15, 25])
    
    # Guardar
    wb.save(output_path)
    return wb


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Market Analyzer - Sistema Semi-Automatizado')
    parser.add_argument('--regime', choices=['RECOVERY', 'EXPANSION', 'LATE_EXPANSION', 'CONTRACTION'],
                        help='Cambiar régimen macro')
    parser.add_argument('--risk', choices=['RISK_ON', 'NEUTRAL', 'RISK_OFF'],
                        help='Cambiar risk appetite')
    parser.add_argument('--output', default='market_analysis_auto.xlsx',
                        help='Nombre del archivo de salida')
    parser.add_argument('--add', nargs='+', help='Añadir tickers al sector Otros')
    
    args = parser.parse_args()
    
    # Actualizar configuración si se especifica
    if args.regime:
        MACRO_CONFIG['regime'] = args.regime
    if args.risk:
        MACRO_CONFIG['risk_appetite'] = args.risk
    if args.add:
        if 'Otros' not in UNIVERSE:
            UNIVERSE['Otros'] = []
        UNIVERSE['Otros'].extend(args.add)
    
    print("=" * 60)
    print("📊 MARKET ANALYZER V12 - Sistema Semi-Automatizado")
    print("=" * 60)
    print(f"⚙️  Régimen: {MACRO_CONFIG['regime']}")
    print(f"⚙️  Risk Appetite: {MACRO_CONFIG['risk_appetite']}")
    print(f"⚙️  Pesos: {get_final_weights()}")
    
    # Obtener datos
    companies = fetch_all_data()
    
    if not companies:
        print("\n❌ No se pudieron obtener datos. Verifica conexión a internet.")
        sys.exit(1)
    
    # Calcular scores
    print("\n📈 Calculando scores multifactor...")
    companies = calculate_scores(companies)
    
    # Generar Excel
    print(f"\n📝 Generando Excel: {args.output}")
    create_excel(companies, args.output)
    
    # Resumen
    signals = {'BUY': 0, 'ACCUMULATE': 0, 'HOLD': 0, 'REDUCE': 0, 'SELL': 0}
    for c in companies:
        signals[c['signal']] += 1
    
    print("\n" + "=" * 60)
    print("✅ COMPLETADO")
    print("=" * 60)
    print(f"\n📋 Distribución de señales:")
    for sig, count in signals.items():
        emoji = {'BUY': '🟢', 'ACCUMULATE': '🟡', 'HOLD': '⚪', 'REDUCE': '🟠', 'SELL': '🔴'}
        print(f"   {emoji.get(sig, '')} {sig}: {count}")
    
    print(f"\n🎯 TOP 5 PICKS:")
    for c in companies[:5]:
        print(f"   {c['ticker']:8} | Score: {c['composite_score']:.1f} | {c['signal']:10} | ${c['price']}")
    
    print(f"\n📁 Archivo guardado: {args.output}")
    print("\n💡 Próximo paso: Abre el Excel y revisa la hoja 'Action_List'")


if __name__ == '__main__':
    main()
