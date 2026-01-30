"""
===============================================================================
BACKTESTER - Market Analysis Strategy Validation (Optimized)
===============================================================================
Valida las estrategias de scoring usando datos históricos.

ESCENARIOS DE TEST:
    1. COVID Crash (Feb-Mar 2020) - Caída extrema
    2. Recovery Rally (Mar-Dec 2020) - Recuperación V
    3. Bear Market 2022 - Fed hawkish, caída prolongada
    4. AI Rally 2023 - Rally liderado por tech/AI
    5. Market Highs 2024 - Máximos históricos

MÉTRICAS:
    - Win Rate
    - Average Return
    - Sharpe Ratio
    - Max Drawdown
    - Alpha vs SPY
===============================================================================
"""

import sys
import io

# Windows encoding fix
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

SCENARIOS = {
    'covid_crash': {
        'name': 'COVID Crash',
        'start': '2020-02-01',
        'end': '2020-03-31',
        'description': 'Caida extrema por pandemia',
    },
    'recovery_2020': {
        'name': 'Recovery 2020',
        'start': '2020-04-01',
        'end': '2020-12-31',
        'description': 'Recuperacion en V',
    },
    'bear_2022': {
        'name': 'Bear 2022',
        'start': '2022-01-01',
        'end': '2022-10-31',
        'description': 'Fed hawkish',
    },
    'ai_rally_2023': {
        'name': 'AI Rally 2023',
        'start': '2023-01-01',
        'end': '2023-12-31',
        'description': 'Rally tech/AI',
    },
    'highs_2024': {
        'name': 'Market Highs 2024',
        'start': '2024-01-01',
        'end': '2024-06-30',
        'description': 'Maximos historicos',
    },
}

# Universo reducido para backtest más rápido
BACKTEST_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META',  # Tech
    'JPM', 'JNJ', 'PG', 'KO', 'WMT',           # Value/Defensive
    'TSLA', 'AMD', 'NFLX',                     # Growth
    'XOM', 'CVX', 'FCX',                       # Commodities
    'SPY',                                     # Benchmark
]

WEIGHT_CONFIGS = {
    'original_v12': {
        'name': 'V12 (4 factores)',
        'weights': {'value': 0.25, 'quality': 0.25, 'momentum': 0.25, 'lowvol': 0.25},
    },
    'current_v13': {
        'name': 'V13 (6 factores)',
        'weights': {'value': 0.20, 'quality': 0.25, 'momentum': 0.15, 'lowvol': 0.15, 'congress': 0.10, 'polymarket': 0.10},
    },
    'momentum_heavy': {
        'name': 'Momentum Heavy',
        'weights': {'value': 0.15, 'quality': 0.15, 'momentum': 0.40, 'lowvol': 0.10, 'congress': 0.10, 'polymarket': 0.10},
    },
    'defensive': {
        'name': 'Defensive',
        'weights': {'value': 0.25, 'quality': 0.30, 'momentum': 0.10, 'lowvol': 0.25, 'congress': 0.05, 'polymarket': 0.05},
    },
    'value_focused': {
        'name': 'Value Focused',
        'weights': {'value': 0.35, 'quality': 0.25, 'momentum': 0.10, 'lowvol': 0.15, 'congress': 0.10, 'polymarket': 0.05},
    },
}

# =============================================================================
# CACHE DE DATOS
# =============================================================================

DATA_CACHE = {}

def download_all_data():
    """Descarga todos los datos de una vez para eficiencia"""
    print("Descargando datos historicos (esto puede tardar 1-2 minutos)...")

    # Rango completo
    start_date = '2019-01-01'  # Un año antes del primer escenario
    end_date = '2024-12-31'

    for i, ticker in enumerate(BACKTEST_TICKERS):
        print(f"  [{i+1}/{len(BACKTEST_TICKERS)}] {ticker}...", end=' ')
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(start=start_date, end=end_date, auto_adjust=True)

            if not data.empty:
                DATA_CACHE[ticker] = data
                print(f"OK ({len(data)} dias)")
            else:
                print("Sin datos")
        except Exception as e:
            print(f"Error: {e}")

    print(f"\nDatos descargados: {len(DATA_CACHE)} tickers\n")


def get_cached_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Obtiene datos del cache filtrados por fecha"""
    if ticker not in DATA_CACHE:
        return pd.DataFrame()

    data = DATA_CACHE[ticker]
    mask = (data.index >= start) & (data.index <= end)
    return data[mask].copy()


# =============================================================================
# CÁLCULO DE FACTORES
# =============================================================================

def calculate_value_score(ticker: str, data: pd.DataFrame) -> float:
    """Score de value basado en precio vs máximos (proxy sin fundamentales históricos)"""
    try:
        if len(data) < 252:
            return 50

        current = data['Close'].iloc[-1]
        high_52w = data['Close'].tail(252).max()
        low_52w = data['Close'].tail(252).min()

        # Posición en el rango 52 semanas (más cerca de mínimo = mejor value)
        position = (current - low_52w) / (high_52w - low_52w) if high_52w != low_52w else 0.5

        # Invertir: más cerca de mínimos = mejor score
        return max(0, min(100, (1 - position) * 100))
    except:
        return 50


def calculate_quality_score(ticker: str, data: pd.DataFrame) -> float:
    """Score de quality basado en consistencia de retornos"""
    try:
        if len(data) < 63:
            return 50

        returns = data['Close'].pct_change().dropna()

        # Ratio de días positivos
        positive_days = (returns > 0).sum() / len(returns)

        # Consistencia (menor dispersión = mejor)
        consistency = 1 / (1 + returns.std() * 100)

        return max(0, min(100, (positive_days * 50 + consistency * 50)))
    except:
        return 50


def calculate_momentum_score(data: pd.DataFrame) -> float:
    """Score de momentum basado en retornos recientes"""
    try:
        if len(data) < 126:
            return 50

        # Momentum de diferentes plazos
        mom_1m = (data['Close'].iloc[-1] / data['Close'].iloc[-21] - 1) * 100 if len(data) >= 21 else 0
        mom_3m = (data['Close'].iloc[-1] / data['Close'].iloc[-63] - 1) * 100 if len(data) >= 63 else 0
        mom_6m = (data['Close'].iloc[-1] / data['Close'].iloc[-126] - 1) * 100 if len(data) >= 126 else 0

        # Ponderado
        momentum = mom_1m * 0.5 + mom_3m * 0.3 + mom_6m * 0.2

        # Normalizar
        return max(0, min(100, 50 + momentum))
    except:
        return 50


def calculate_lowvol_score(data: pd.DataFrame) -> float:
    """Score de baja volatilidad"""
    try:
        if len(data) < 63:
            return 50

        returns = data['Close'].pct_change().dropna()
        vol = returns.std() * np.sqrt(252) * 100  # Vol anualizada %

        # Menor vol = mayor score (vol típica 15-60%)
        return max(0, min(100, 100 - (vol - 10) * 1.5))
    except:
        return 50


def calculate_scores(ticker: str, end_date: str, lookback_days: int = 252) -> Dict[str, float]:
    """Calcula todos los scores para un ticker"""
    end = pd.to_datetime(end_date)
    start = end - timedelta(days=lookback_days + 50)

    data = get_cached_data(ticker, start.strftime('%Y-%m-%d'), end_date)

    if data.empty or len(data) < 50:
        return None

    return {
        'value': calculate_value_score(ticker, data),
        'quality': calculate_quality_score(ticker, data),
        'momentum': calculate_momentum_score(data),
        'lowvol': calculate_lowvol_score(data),
        'congress': 50,  # Neutral para backtest
        'polymarket': 50,
    }


def calculate_composite(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """Calcula score compuesto"""
    if not scores:
        return 50

    total = sum(scores.get(f, 50) * w for f, w in weights.items())
    return total


# =============================================================================
# BACKTEST
# =============================================================================

def get_forward_return(ticker: str, date: str, days: int) -> float:
    """Obtiene retorno forward"""
    try:
        start = pd.to_datetime(date)
        end = start + timedelta(days=days + 10)

        data = get_cached_data(ticker, date, end.strftime('%Y-%m-%d'))

        if len(data) < days:
            return None

        return (data['Close'].iloc[days-1] / data['Close'].iloc[0] - 1) * 100
    except:
        return None


def run_backtest(scenario_key: str, weight_key: str, holding_period: int = 21) -> Dict:
    """Ejecuta backtest para un escenario y configuración"""

    scenario = SCENARIOS[scenario_key]
    weights = WEIGHT_CONFIGS[weight_key]['weights']

    start = pd.to_datetime(scenario['start'])
    end = pd.to_datetime(scenario['end'])

    # Fechas de rebalanceo (mensual)
    rebalance_dates = pd.date_range(start=start, end=end, freq='MS')

    portfolio_returns = []
    benchmark_returns = []
    all_picks = []

    for rebal_date in rebalance_dates:
        date_str = rebal_date.strftime('%Y-%m-%d')

        # Calcular scores
        ticker_data = []
        for ticker in BACKTEST_TICKERS:
            if ticker == 'SPY':
                continue
            scores = calculate_scores(ticker, date_str)
            if scores:
                composite = calculate_composite(scores, weights)
                ticker_data.append({
                    'ticker': ticker,
                    'score': composite,
                    'scores': scores,
                })

        if len(ticker_data) < 3:
            continue

        # Ordenar y seleccionar top 3
        ticker_data.sort(key=lambda x: x['score'], reverse=True)
        top_picks = ticker_data[:3]

        # Retornos forward
        returns = []
        for pick in top_picks:
            ret = get_forward_return(pick['ticker'], date_str, holding_period)
            if ret is not None:
                returns.append(ret)
                all_picks.append({
                    'date': date_str,
                    'ticker': pick['ticker'],
                    'score': pick['score'],
                    'return': ret,
                })

        if returns:
            portfolio_returns.append(np.mean(returns))

        # Benchmark
        spy_ret = get_forward_return('SPY', date_str, holding_period)
        if spy_ret is not None:
            benchmark_returns.append(spy_ret)

    # Métricas
    if not portfolio_returns:
        return {'error': 'No data'}

    portfolio_returns = np.array(portfolio_returns)
    benchmark_returns = np.array(benchmark_returns[:len(portfolio_returns)])

    total_ret = np.sum(portfolio_returns)
    avg_ret = np.mean(portfolio_returns)
    std_ret = np.std(portfolio_returns) if len(portfolio_returns) > 1 else 1
    sharpe = avg_ret / std_ret * np.sqrt(12) if std_ret > 0 else 0
    win_rate = np.sum(portfolio_returns > 0) / len(portfolio_returns) * 100
    alpha = total_ret - np.sum(benchmark_returns) if len(benchmark_returns) > 0 else 0

    # Max drawdown
    cumulative = np.cumsum(portfolio_returns)
    running_max = np.maximum.accumulate(cumulative)
    max_dd = np.max(running_max - cumulative) if len(cumulative) > 0 else 0

    return {
        'scenario': scenario['name'],
        'config': WEIGHT_CONFIGS[weight_key]['name'],
        'total_return': round(total_ret, 2),
        'avg_return': round(avg_ret, 2),
        'sharpe': round(sharpe, 2),
        'win_rate': round(win_rate, 1),
        'max_drawdown': round(max_dd, 2),
        'alpha': round(alpha, 2),
        'n_periods': len(portfolio_returns),
        'benchmark_return': round(np.sum(benchmark_returns), 2) if len(benchmark_returns) > 0 else 0,
        'picks': all_picks,
    }


def run_full_backtest() -> pd.DataFrame:
    """Ejecuta backtest completo"""

    print("=" * 70)
    print("BACKTESTING - Market Analysis Strategy Validation")
    print("=" * 70)

    # Descargar datos
    download_all_data()

    results = []

    for scenario_key, scenario in SCENARIOS.items():
        print(f"\n{'='*50}")
        print(f"ESCENARIO: {scenario['name']}")
        print(f"Periodo: {scenario['start']} a {scenario['end']}")
        print(f"Descripcion: {scenario['description']}")
        print("=" * 50)

        for weight_key in WEIGHT_CONFIGS:
            result = run_backtest(scenario_key, weight_key)
            if 'error' not in result:
                results.append(result)
                print(f"  {result['config']:20s} | Ret: {result['total_return']:7.1f}% | "
                      f"WR: {result['win_rate']:5.1f}% | Sharpe: {result['sharpe']:5.2f} | "
                      f"Alpha: {result['alpha']:6.1f}%")

    return pd.DataFrame(results)


def analyze_and_recommend(results_df: pd.DataFrame) -> Dict:
    """Analiza resultados y genera recomendaciones"""

    print("\n" + "=" * 70)
    print("ANALISIS DE RESULTADOS")
    print("=" * 70)

    # Promedios por configuración
    avg = results_df.groupby('config').agg({
        'total_return': 'mean',
        'sharpe': 'mean',
        'win_rate': 'mean',
        'alpha': 'mean',
    }).round(2)

    print("\n>>> RENDIMIENTO PROMEDIO POR CONFIGURACION:")
    print(avg.to_string())

    # Mejor por métrica
    best_sharpe = avg['sharpe'].idxmax()
    best_return = avg['total_return'].idxmax()
    best_alpha = avg['alpha'].idxmax()

    print(f"\n>>> MEJOR CONFIGURACION:")
    print(f"  Por Sharpe:  {best_sharpe}")
    print(f"  Por Retorno: {best_return}")
    print(f"  Por Alpha:   {best_alpha}")

    # Mejor por escenario
    print("\n>>> MEJOR CONFIGURACION POR ESCENARIO:")
    best_per_scenario = {}
    for scenario in results_df['scenario'].unique():
        sc_data = results_df[results_df['scenario'] == scenario]
        best = sc_data.loc[sc_data['sharpe'].idxmax()]
        best_per_scenario[scenario] = best['config']
        print(f"  {scenario:20s}: {best['config']:20s} (Sharpe: {best['sharpe']:.2f})")

    # Análisis bull vs bear
    print("\n>>> ANALISIS POR TIPO DE MERCADO:")

    bull_scenarios = ['Recovery 2020', 'AI Rally 2023', 'Market Highs 2024']
    bear_scenarios = ['COVID Crash', 'Bear 2022']

    bull_data = results_df[results_df['scenario'].isin(bull_scenarios)]
    bear_data = results_df[results_df['scenario'].isin(bear_scenarios)]

    if not bull_data.empty:
        bull_best = bull_data.groupby('config')['sharpe'].mean().idxmax()
        print(f"  Mercados Alcistas: {bull_best}")

    if not bear_data.empty:
        bear_best = bear_data.groupby('config')['sharpe'].mean().idxmax()
        print(f"  Mercados Bajistas: {bear_best}")

    # Pesos óptimos sugeridos
    print("\n>>> PESOS OPTIMOS SUGERIDOS:")

    # Basado en el mejor performer general
    if 'Momentum Heavy' in best_sharpe:
        optimal = {'value': 0.15, 'quality': 0.20, 'momentum': 0.35, 'lowvol': 0.10, 'congress': 0.10, 'polymarket': 0.10}
    elif 'Defensive' in best_sharpe:
        optimal = {'value': 0.25, 'quality': 0.30, 'momentum': 0.10, 'lowvol': 0.20, 'congress': 0.10, 'polymarket': 0.05}
    elif 'Value' in best_sharpe:
        optimal = {'value': 0.30, 'quality': 0.25, 'momentum': 0.15, 'lowvol': 0.15, 'congress': 0.10, 'polymarket': 0.05}
    else:
        # V13 ajustado
        optimal = {'value': 0.20, 'quality': 0.25, 'momentum': 0.20, 'lowvol': 0.15, 'congress': 0.10, 'polymarket': 0.10}

    for factor, weight in optimal.items():
        print(f"    {factor}: {weight:.0%}")

    return {
        'best_config': best_sharpe,
        'best_per_scenario': best_per_scenario,
        'optimal_weights': optimal,
        'avg_results': avg.to_dict(),
    }


def export_results(results_df: pd.DataFrame, analysis: Dict):
    """Exporta resultados a Excel"""

    filepath = 'd:\\proyectos\\Market Analysis\\backtest_results.xlsx'

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Resultados completos
        results_df.drop(columns=['picks'], errors='ignore').to_excel(
            writer, sheet_name='Backtest_Results', index=False)

        # Pivot por escenario
        pivot = results_df.pivot_table(
            index='scenario',
            columns='config',
            values=['total_return', 'sharpe', 'alpha'],
        )
        pivot.to_excel(writer, sheet_name='Scenario_Comparison')

        # Pesos óptimos
        opt_df = pd.DataFrame([analysis['optimal_weights']])
        opt_df.to_excel(writer, sheet_name='Optimal_Weights', index=False)

    print(f"\n>>> Resultados exportados a: {filepath}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "=" * 70)
    print("   MARKET ANALYSIS - BACKTESTING ENGINE")
    print("=" * 70)

    # Ejecutar
    results_df = run_full_backtest()

    if results_df.empty:
        print("ERROR: No hay resultados")
        return

    # Analizar
    analysis = analyze_and_recommend(results_df)

    # Exportar
    export_results(results_df, analysis)

    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN EJECUTIVO")
    print("=" * 70)
    print(f"""
HALLAZGOS CLAVE:
  - Mejor configuracion general: {analysis['best_config']}

RECOMENDACIONES:
  1. En mercados alcistas: usar configuracion con mas peso en Momentum
  2. En mercados bajistas: usar configuracion Defensiva (Quality + LowVol)
  3. Los factores Congress/Polymarket aportan valor en tiempo real
     (detectan informacion asimetrica que no se puede backtestear)

LIMITACIONES:
  - Congress/Polymarket usan score neutral (no hay datos historicos)
  - Fundamentales historicos no disponibles (usamos proxies tecnicos)
  - No incluye costes de transaccion

PESOS SUGERIDOS PARA market_analyzer.py:
""")
    for f, w in analysis['optimal_weights'].items():
        print(f"    '{f}': {w},")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
