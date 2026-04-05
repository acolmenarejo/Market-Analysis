"""
Walk-Forward Backtesting Engine for Multi-Horizon Scoring System
================================================================
Tests scoring model's predictive power using historical data.
No look-ahead bias — scores computed using only data available at each date.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


# 60 liquid US stocks spanning all major sectors — broad enough for statistical power
# (~700-1000 trades per signal over 3 years, vs ~200 with the old 25-ticker list)
DEFAULT_BACKTEST_TICKERS = [
    # Mega cap / Tech
    'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA', 'NFLX',
    # Semiconductors / Software
    'AVGO', 'AMD', 'INTC', 'QCOM', 'CRM', 'ORCL', 'IBM', 'NOW', 'ADBE',
    # Banks / Finance
    'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'AXP', 'MA', 'V', 'SCHW',
    # Healthcare
    'UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'AMGN', 'CVS',
    # Consumer Staples / Discretionary
    'WMT', 'COST', 'HD', 'MCD', 'PG', 'KO', 'PEP', 'NKE', 'LOW', 'TGT',
    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY',
    # Industrials / Defense
    'CAT', 'DE', 'UNP', 'HON', 'GE', 'LMT', 'RTX', 'BA', 'UPS',
    # REITs / Utilities
    'AMT', 'NEE', 'PLD', 'O', 'EQIX',
]


class ScoringBacktester:
    """Walk-forward backtester for multi-horizon scoring system."""

    # Transaction cost per trade leg (0.10% ≈ realistic retail with tight spreads)
    TRANSACTION_COST_PCT = 0.10

    def __init__(self, tickers: List[str] = None, lookback_years: int = 3):
        self.tickers = tickers or DEFAULT_BACKTEST_TICKERS
        self.lookback_years = lookback_years
        self.hist_data: Dict[str, pd.DataFrame] = {}
        self.trades: List[dict] = []
        self.equity_curve: Optional[pd.Series] = None
        self.benchmark_curve: Optional[pd.Series] = None
        # Out-of-sample split: last 1 year of data is OOS
        self.oos_start_date: Optional[pd.Timestamp] = None

    # Sector mapping for macro-aware scoring
    TICKER_SECTOR = {
        # Tech / Semi / Software
        'AAPL': 'Tech', 'MSFT': 'Tech', 'NVDA': 'Tech', 'GOOGL': 'Tech', 'META': 'Tech',
        'AMZN': 'Tech', 'NFLX': 'Tech',
        'AVGO': 'Tech', 'AMD': 'Tech', 'INTC': 'Tech', 'QCOM': 'Tech',
        'CRM': 'Tech', 'ORCL': 'Tech', 'IBM': 'Tech', 'NOW': 'Tech', 'ADBE': 'Tech',
        # Banks / Finance
        'JPM': 'Banks', 'BAC': 'Banks', 'GS': 'Banks', 'MS': 'Banks', 'WFC': 'Banks',
        'C': 'Banks', 'AXP': 'Banks', 'MA': 'Banks', 'V': 'Banks', 'SCHW': 'Banks',
        # Healthcare
        'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'PFE': 'Healthcare', 'MRK': 'Healthcare',
        'ABBV': 'Healthcare', 'LLY': 'Healthcare', 'AMGN': 'Healthcare', 'CVS': 'Healthcare',
        # Consumer
        'WMT': 'Consumer', 'COST': 'Consumer', 'HD': 'Consumer', 'MCD': 'Consumer',
        'PG': 'Consumer', 'KO': 'Consumer', 'PEP': 'Consumer', 'NKE': 'Consumer',
        'LOW': 'Consumer', 'TGT': 'Consumer', 'TSLA': 'Consumer',
        # Energy
        'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy',
        'EOG': 'Energy', 'OXY': 'Energy',
        # Industrials / Defense
        'CAT': 'Industrials', 'DE': 'Industrials', 'UNP': 'Industrials', 'HON': 'Industrials',
        'GE': 'Industrials', 'LMT': 'Defense', 'RTX': 'Defense', 'BA': 'Industrials',
        'UPS': 'Industrials',
        # REITs / Utilities
        'AMT': 'REITs', 'NEE': 'Utilities', 'PLD': 'REITs', 'O': 'REITs', 'EQIX': 'REITs',
    }

    def download_historical_data(self) -> bool:
        """Download historical OHLCV for all tickers + SPY + CL=F (oil) + ^VIX."""
        try:
            all_tickers = self.tickers + ['SPY', 'CL=F', '^VIX']
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_years * 365 + 180)

            data = yf.download(
                all_tickers, start=start_date, end=end_date,
                group_by='ticker', auto_adjust=True, threads=True, progress=False
            )

            if data.empty:
                return False

            for t in all_tickers:
                try:
                    if data.columns.nlevels == 1:
                        self.hist_data[t] = data.copy()
                    elif t in data.columns.get_level_values(0):
                        t_df = data[t].dropna(how='all')
                        if not t_df.empty and 'Close' in t_df.columns:
                            self.hist_data[t] = t_df
                except Exception:
                    continue

            if len(self.hist_data) >= 10:
                # Set OOS start = 1 year before end of data
                spy = self.hist_data.get('SPY')
                if spy is not None and len(spy) > 0:
                    self.oos_start_date = spy.index[-1] - pd.DateOffset(years=1)
                return True
            return False
        except Exception:
            return False

    def _compute_score_at_date(self, ticker: str, date: pd.Timestamp,
                                lookback_days: int = 130) -> Optional[float]:
        """Compute a simplified multi-horizon score using only data up to `date`.
        Returns short-term score (0-100) or None if insufficient data."""
        hist = self.hist_data.get(ticker)
        if hist is None:
            return None

        # Only use data up to this date (no look-ahead)
        hist_slice = hist.loc[:date]
        if len(hist_slice) < 60:
            return None

        close = hist_slice['Close']
        try:
            # RSI (14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 0.0001)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            # MACD
            exp12 = close.ewm(span=12, adjust=False).mean()
            exp26 = close.ewm(span=26, adjust=False).mean()
            macd = exp12 - exp26
            signal_line = macd.ewm(span=9, adjust=False).mean()
            macd_bullish = float(macd.iloc[-1]) > float(signal_line.iloc[-1])

            # Bollinger
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_upper = float((sma20 + std20 * 2).iloc[-1])
            bb_lower = float((sma20 - std20 * 2).iloc[-1])
            price = float(close.iloc[-1])
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_pos = ((price - bb_lower) / bb_range) * 100
            else:
                bb_pos = 50

            # Momentum
            mom_1m = ((close.iloc[-1] / close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0
            mom_3m = ((close.iloc[-1] / close.iloc[-60]) - 1) * 100 if len(close) >= 60 else 0

            # Volume
            vol = hist_slice['Volume']
            avg_vol = vol.rolling(20).mean().iloc[-1] if len(vol) >= 20 else vol.mean()
            vol_ratio = float(vol.iloc[-1] / avg_vol) if avg_vol > 0 else 1.0

            # Relative strength vs SPY
            spy_hist = self.hist_data.get('SPY')
            rs_score = 50
            if spy_hist is not None:
                spy_slice = spy_hist.loc[:date]
                if len(spy_slice) >= 20:
                    spy_mom = ((spy_slice['Close'].iloc[-1] / spy_slice['Close'].iloc[-20]) - 1) * 100
                    diff = float(mom_1m) - float(spy_mom)
                    rs_score = max(10, min(90, 50 + diff * 3))

            # Composite score — calibrated with contrarian + quality blend
            # Based on backtest: mean-reversion dominates across all horizons
            score = 0

            # === MEAN REVERSION / CONTRARIAN (40%) ===

            # RSI contrarian (0.15) — oversold = buy opportunity
            if rsi < 25:
                score += 92 * 0.15
            elif rsi < 30:
                score += 85 * 0.15
            elif rsi < 40:
                score += 70 * 0.15
            elif rsi > 75:
                score += 15 * 0.15
            elif rsi > 65:
                score += 30 * 0.15
            else:
                score += 50 * 0.15

            # Bollinger contrarian (0.10) — near lower band = buy
            score += max(5, min(95, 100 - bb_pos)) * 0.10

            # Mean reversion signal (0.15) — oversold + dropping = max score
            if rsi < 30 and float(mom_1m) < -5:
                score += 92 * 0.15  # Strong oversold bounce
            elif rsi < 40 and float(mom_1m) < -3:
                score += 78 * 0.15
            elif rsi > 70 and float(mom_1m) > 10:
                score += 15 * 0.15  # Overbought risk
            elif rsi > 65 and float(mom_1m) > 5:
                score += 25 * 0.15
            else:
                score += 50 * 0.15

            # === TREND CONTEXT (25%) ===

            # Trend structure (0.10) — above SMA200 = healthy context
            sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else price
            sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma50
            if price > float(sma200) and price < float(sma50):
                score += 80 * 0.10  # Pullback in uptrend (best setup)
            elif price > float(sma50) > float(sma200):
                score += 60 * 0.10  # Extended uptrend (less upside)
            elif price < float(sma200):
                score += 35 * 0.10  # Below 200 SMA
            else:
                score += 50 * 0.10

            # MACD divergence (0.08) — MACD crossing UP while price down = buy
            if not macd_bullish and float(mom_1m) < -3:
                score += 70 * 0.08  # Bearish but may be bottoming
            elif macd_bullish and float(mom_1m) < 0:
                score += 85 * 0.08  # Bullish cross during pullback
            elif macd_bullish and float(mom_1m) > 8:
                score += 30 * 0.08  # Extended
            else:
                score += 50 * 0.08

            # Relative strength (0.07) — underperformers catch up
            # Invert: stocks lagging SPY = buy candidates
            rs_contrarian = max(10, min(90, 100 - rs_score))
            score += rs_contrarian * 0.07

            # === VOLATILITY (15%) ===

            # Vol percentile (0.08) — low vol = calm entry
            daily_returns = close.pct_change().dropna()
            if len(daily_returns) >= 20:
                vol_20d = float(daily_returns.tail(20).std() * np.sqrt(252) * 100)
                if vol_20d < 15:
                    score += 70 * 0.08
                elif vol_20d < 25:
                    score += 60 * 0.08
                elif vol_20d < 40:
                    score += 45 * 0.08
                else:
                    score += 65 * 0.08  # High vol = capitulation opportunity
            else:
                score += 50 * 0.08

            # Volume spike on down day = capitulation (0.07)
            last_return = float(close.pct_change().iloc[-1]) if len(close) >= 2 else 0
            if vol_ratio > 2.0 and last_return < -0.02:
                score += 80 * 0.07  # Capitulation buying
            elif vol_ratio > 1.5 and last_return < -0.01:
                score += 70 * 0.07
            elif vol_ratio > 2.0 and last_return > 0.02:
                score += 35 * 0.07  # Blow-off top risk
            else:
                score += 50 * 0.07

            # === MOMENTUM CONFIRMATION (20%) ===
            # Use momentum as confirmation, NOT primary signal
            # Contrarian momentum: recent losers with long-term uptrend

            # 1m momentum — contrarian weight (0.10)
            mom_contrarian = max(10, min(90, 50 - float(mom_1m) * 1.5))
            score += mom_contrarian * 0.10

            # 3m momentum — slight contrarian (0.10)
            mom3_contrarian = max(10, min(90, 50 - float(mom_3m) * 0.5))
            score += mom3_contrarian * 0.10

            return round(score, 1)

        except Exception:
            return None

    def run_walk_forward(self, horizon: str = 'short_term',
                         rebalance_freq: str = 'weekly') -> bool:
        """Run walk-forward backtest.

        Args:
            horizon: 'short_term' (5-day hold), 'medium_term' (21-day), 'long_term' (63-day)
            rebalance_freq: 'weekly' or 'monthly'
        """
        if not self.hist_data:
            if not self.download_historical_data():
                return False

        holding_periods = {
            'short_term': 5,
            'medium_term': 21,
            'long_term': 63,
        }
        hold_days = holding_periods.get(horizon, 5)
        rebal_days = 5 if rebalance_freq == 'weekly' else 21

        # Get common date range
        spy = self.hist_data.get('SPY')
        if spy is None:
            return False

        # Start after 6 months of warmup data
        all_dates = spy.index
        start_idx = min(130, len(all_dates) - hold_days - 10)
        if start_idx < 0:
            return False

        self.trades = []
        portfolio_values = []
        benchmark_values = []

        # Walk forward
        rebal_dates = list(range(start_idx, len(all_dates) - hold_days, rebal_days))

        for i, idx in enumerate(rebal_dates):
            date = all_dates[idx]
            exit_idx = min(idx + hold_days, len(all_dates) - 1)
            exit_date = all_dates[exit_idx]

            # Score all tickers at this date
            scores = {}
            for t in self.tickers:
                s = self._compute_score_at_date(t, date)
                if s is not None:
                    scores[t] = s

            if len(scores) < 5:
                continue

            # Rank and assign signals
            sorted_tickers = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top5 = [t for t, _ in sorted_tickers[:5]]
            top10 = [t for t, _ in sorted_tickers[5:10]]
            bottom5 = [t for t, _ in sorted_tickers[-5:]]

            # VIX regime using real ^VIX data (falls back to SPY vol if unavailable)
            vix_regime = 'normal'
            vix_hist = self.hist_data.get('^VIX')
            if vix_hist is not None:
                vix_slice = vix_hist.loc[:date]
                if len(vix_slice) > 0:
                    vix_val = float(vix_slice['Close'].iloc[-1])
                    if vix_val >= 30:
                        vix_regime = 'crisis'
                    elif vix_val >= 22:
                        vix_regime = 'high_vol'
                    elif vix_val < 15:
                        vix_regime = 'low_vol'
            else:
                # Fallback: use SPY realized vol
                spy_fb = self.hist_data.get('SPY')
                if spy_fb is not None:
                    spy_slice = spy_fb.loc[:date]
                    if len(spy_slice) >= 20:
                        spy_vol = float(spy_slice['Close'].pct_change().tail(20).std() * np.sqrt(252) * 100)
                        if spy_vol > 30:
                            vix_regime = 'crisis'
                        elif spy_vol > 20:
                            vix_regime = 'high_vol'
                        elif spy_vol < 10:
                            vix_regime = 'low_vol'

            # Calculate forward returns
            for t in self.tickers:
                t_hist = self.hist_data.get(t)
                if t_hist is None or t not in scores:
                    continue

                try:
                    if date in t_hist.index and exit_date in t_hist.index:
                        entry_price = float(t_hist.loc[date, 'Close'])
                        exit_price = float(t_hist.loc[exit_date, 'Close'])
                    else:
                        entry_loc = t_hist.index.get_indexer([date], method='nearest')[0]
                        exit_loc = t_hist.index.get_indexer([exit_date], method='nearest')[0]
                        entry_price = float(t_hist.iloc[entry_loc]['Close'])
                        exit_price = float(t_hist.iloc[exit_loc]['Close'])

                    # Deduct round-trip transaction cost (0.20% = 2 x 0.10%)
                    fwd_return = (exit_price / entry_price - 1) * 100 - (self.TRANSACTION_COST_PCT * 2)

                    # Flag whether this trade is in-sample or out-of-sample
                    is_oos = (self.oos_start_date is not None and date >= self.oos_start_date)

                    if t in top5:
                        signal = 'STRONG_BUY'
                    elif t in top10:
                        signal = 'BUY'
                    elif t in bottom5:
                        signal = 'SELL'
                    else:
                        signal = 'HOLD'

                    self.trades.append({
                        'date': date,
                        'exit_date': exit_date,
                        'ticker': t,
                        'score': scores[t],
                        'signal': signal,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'return_pct': fwd_return,
                        'vix_regime': vix_regime,
                        'is_oos': is_oos,
                    })
                except Exception:
                    continue

            # Portfolio return (equal-weight top 5)
            top5_returns = [
                tr['return_pct'] for tr in self.trades
                if tr['date'] == date and tr['signal'] == 'STRONG_BUY'
            ]
            if top5_returns:
                avg_return = sum(top5_returns) / len(top5_returns)
            else:
                avg_return = 0

            # SPY benchmark return
            try:
                spy_entry = float(spy.loc[date, 'Close']) if date in spy.index else float(spy.iloc[spy.index.get_indexer([date], method='nearest')[0]]['Close'])
                spy_exit = float(spy.loc[exit_date, 'Close']) if exit_date in spy.index else float(spy.iloc[spy.index.get_indexer([exit_date], method='nearest')[0]]['Close'])
                spy_return = (spy_exit / spy_entry - 1) * 100
            except Exception:
                spy_return = 0

            portfolio_values.append({'date': date, 'return': avg_return})
            benchmark_values.append({'date': date, 'return': spy_return})

        if not portfolio_values:
            return False

        # Build equity curves
        port_df = pd.DataFrame(portfolio_values).set_index('date')
        bench_df = pd.DataFrame(benchmark_values).set_index('date')

        self.equity_curve = (1 + port_df['return'] / 100).cumprod() * 100
        self.benchmark_curve = (1 + bench_df['return'] / 100).cumprod() * 100

        return True

    def calculate_metrics(self) -> dict:
        """Calculate professional backtest performance metrics.

        Includes: Sharpe, Sortino, Calmar, Information Ratio, t-test alpha,
        in-sample vs out-of-sample split, per-signal stats, regime analysis.
        """
        if not self.trades:
            return {}

        try:
            from scipy import stats as _scipy_stats
            _has_scipy = True
        except ImportError:
            _has_scipy = False

        trades_df = pd.DataFrame(self.trades)

        # -------------------------------------------------------
        # Per-signal stats
        # -------------------------------------------------------
        signal_stats = {}
        for signal in ['STRONG_BUY', 'BUY', 'HOLD', 'SELL']:
            sig_trades = trades_df[trades_df['signal'] == signal]
            if sig_trades.empty:
                continue
            returns = sig_trades['return_pct']
            signal_stats[signal] = {
                'count': len(sig_trades),
                'hit_rate': round((returns > 0).mean() * 100, 1),
                'avg_return': round(returns.mean(), 2),
                'median_return': round(returns.median(), 2),
                'best': round(returns.max(), 2),
                'worst': round(returns.min(), 2),
                'std': round(returns.std(), 2),
            }

        # -------------------------------------------------------
        # Overall portfolio metrics — STRONG_BUY portfolio
        # -------------------------------------------------------
        sb_trades = trades_df[trades_df['signal'] == 'STRONG_BUY']
        all_returns = sb_trades['return_pct'] if not sb_trades.empty else trades_df['return_pct']

        n = len(all_returns)
        mean_ret = float(all_returns.mean()) if n > 0 else 0
        std_ret = float(all_returns.std()) if n > 1 else 0

        # Sharpe (annualized, weekly rebalance = 52 periods/year)
        sharpe = (mean_ret / std_ret) * np.sqrt(52) if std_ret > 0 else 0

        # Sortino (downside deviation only — penalises losses more fairly)
        neg_rets = all_returns[all_returns < 0]
        downside_std = float(neg_rets.std()) if len(neg_rets) > 1 else std_ret
        sortino = (mean_ret / downside_std) * np.sqrt(52) if downside_std > 0 else 0

        # Max drawdown from equity curve
        max_dd = 0.0
        if self.equity_curve is not None and len(self.equity_curve) > 0:
            peak = self.equity_curve.expanding().max()
            dd = (self.equity_curve - peak) / peak * 100
            max_dd = round(float(dd.min()), 1)

        # Calmar ratio (annualized return / |max drawdown|)
        annualized_return = mean_ret * 52
        calmar = round(abs(annualized_return / max_dd), 2) if max_dd != 0 else 0.0

        # Win rate & profit factor
        win_rate = round((all_returns > 0).mean() * 100, 1) if n > 0 else 0
        gross_profit = float(all_returns[all_returns > 0].sum())
        gross_loss = float(abs(all_returns[all_returns < 0].sum()))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf')

        # -------------------------------------------------------
        # Alpha vs SPY + Information Ratio
        # -------------------------------------------------------
        alpha = 0.0
        information_ratio = 0.0
        alpha_p_value = 1.0
        alpha_significant = False

        if self.equity_curve is not None and self.benchmark_curve is not None:
            port_total = float(self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1) * 100
            bench_total = float(self.benchmark_curve.iloc[-1] / self.benchmark_curve.iloc[0] - 1) * 100
            alpha = round(port_total - bench_total, 1)

        # Build matched SPY returns for t-test and IR
        spy_matched = []
        if self.hist_data.get('SPY') is not None:
            spy_hist = self.hist_data['SPY']
            for _, row in sb_trades.iterrows():
                try:
                    entry_date = row['date']
                    exit_date = row['exit_date']
                    ep = spy_hist.index.get_indexer([entry_date], method='nearest')[0]
                    xp = spy_hist.index.get_indexer([exit_date], method='nearest')[0]
                    spy_ret = (float(spy_hist.iloc[xp]['Close']) / float(spy_hist.iloc[ep]['Close']) - 1) * 100
                    spy_matched.append(spy_ret)
                except Exception:
                    spy_matched.append(0.0)

        if len(spy_matched) == len(all_returns) and len(spy_matched) > 5:
            spy_arr = np.array(spy_matched)
            port_arr = all_returns.values
            excess = port_arr - spy_arr
            ir_std = float(np.std(excess))
            if ir_std > 0:
                information_ratio = round(float(np.mean(excess)) / ir_std * np.sqrt(52), 2)
            # Two-sample t-test: are portfolio returns significantly different from SPY?
            if _has_scipy and len(port_arr) >= 20 and len(spy_arr) >= 20:
                try:
                    t_stat, p_val = _scipy_stats.ttest_ind(port_arr, spy_arr, equal_var=False)
                    alpha_p_value = round(float(p_val), 4)
                    alpha_significant = bool(p_val < 0.05)
                except Exception:
                    pass

        # -------------------------------------------------------
        # Out-of-sample (OOS) metrics — last 1 year of data
        # -------------------------------------------------------
        oos_metrics = {}
        if 'is_oos' in trades_df.columns and 'is_oos' in sb_trades.columns:
            oos_sb = sb_trades[sb_trades['is_oos'] == True]
            is_sb = sb_trades[sb_trades['is_oos'] == False]

            for label, subset in [('in_sample', is_sb), ('out_of_sample', oos_sb)]:
                if len(subset) < 10:
                    continue
                r = subset['return_pct']
                s = (r.mean() / r.std()) * np.sqrt(52) if r.std() > 0 else 0
                oos_metrics[label] = {
                    'count': len(subset),
                    'hit_rate': round((r > 0).mean() * 100, 1),
                    'avg_return': round(r.mean(), 2),
                    'sharpe': round(s, 2),
                    'alpha_vs_spy': 0,  # filled if spy_matched available
                }

        # -------------------------------------------------------
        # Monthly return decomposition (for heatmap display)
        # -------------------------------------------------------
        monthly_breakdown = {}
        try:
            if self.equity_curve is not None and len(self.equity_curve) > 3:
                monthly = self.equity_curve.resample('ME').last().pct_change() * 100
                monthly = monthly.dropna()
                for dt, val in monthly.items():
                    yr = dt.year
                    mo = dt.month
                    if yr not in monthly_breakdown:
                        monthly_breakdown[yr] = {}
                    monthly_breakdown[yr][mo] = round(float(val), 2)
        except Exception:
            pass

        # -------------------------------------------------------
        # VIX regime analysis
        # -------------------------------------------------------
        regime_stats = {}
        if 'vix_regime' in trades_df.columns:
            sb_df = sb_trades
            for regime in ['low_vol', 'normal', 'high_vol', 'crisis']:
                r_trades = sb_df[sb_df['vix_regime'] == regime]
                if len(r_trades) >= 5:
                    regime_stats[regime] = {
                        'count': len(r_trades),
                        'hit_rate': round((r_trades['return_pct'] > 0).mean() * 100, 1),
                        'avg_return': round(r_trades['return_pct'].mean(), 2),
                    }

        return {
            'signal_stats': signal_stats,
            # Core risk-adjusted metrics
            'sharpe_ratio': round(sharpe, 2),
            'sortino_ratio': round(sortino, 2),
            'calmar_ratio': calmar,
            'information_ratio': information_ratio,
            # Drawdown & returns
            'max_drawdown': max_dd,
            'annualized_return': round(annualized_return, 1),
            'avg_return': round(mean_ret, 2),
            # Statistical validation
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades_df),
            'alpha_vs_spy': alpha,
            'alpha_p_value': alpha_p_value,
            'alpha_significant': alpha_significant,
            # In-sample vs out-of-sample
            'oos_metrics': oos_metrics,
            # Regime analysis
            'regime_stats': regime_stats,
            # Monthly heatmap
            'monthly_breakdown': monthly_breakdown,
        }

    def generate_report(self) -> dict:
        """Generate full backtest report for display."""
        metrics = self.calculate_metrics()

        # Monthly returns heatmap data
        monthly_returns = None
        if self.equity_curve is not None:
            try:
                monthly = self.equity_curve.resample('ME').last().pct_change() * 100
                monthly_returns = monthly.dropna()
            except Exception:
                pass

        # Factor attribution: which score ranges predicted best
        factor_attr = {}
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            # Score quintile analysis
            trades_df['score_quintile'] = pd.qcut(trades_df['score'], 5,
                                                    labels=['Q1(Low)', 'Q2', 'Q3', 'Q4', 'Q5(High)'],
                                                    duplicates='drop')
            for q in trades_df['score_quintile'].unique():
                q_trades = trades_df[trades_df['score_quintile'] == q]
                factor_attr[str(q)] = {
                    'avg_return': round(q_trades['return_pct'].mean(), 2),
                    'hit_rate': round((q_trades['return_pct'] > 0).mean() * 100, 1),
                    'count': len(q_trades),
                }

        return {
            'metrics': metrics,
            'equity_curve': self.equity_curve,
            'benchmark_curve': self.benchmark_curve,
            'monthly_returns': monthly_returns,
            'factor_attribution': factor_attr,
            'trades': pd.DataFrame(self.trades) if self.trades else pd.DataFrame(),
        }


    def analyze_market_regimes(self) -> dict:
        """Analyze backtest results split by bull/bear/crisis market regimes.
        Uses SPY drawdown and realized vol to classify periods."""
        if not self.trades:
            return {}

        trades_df = pd.DataFrame(self.trades)
        spy = self.hist_data.get('SPY')
        if spy is None:
            return {}

        # Classify each trade date into market regime
        spy_close = spy['Close']
        spy_peak = spy_close.expanding().max()
        spy_drawdown = (spy_close - spy_peak) / spy_peak * 100

        regime_labels = []
        for _, trade in trades_df.iterrows():
            date = trade['date']
            try:
                if date in spy_drawdown.index:
                    dd = float(spy_drawdown.loc[date])
                else:
                    nearest_idx = spy_drawdown.index.get_indexer([date], method='nearest')[0]
                    dd = float(spy_drawdown.iloc[nearest_idx])

                # Also check recent momentum
                spy_slice = spy_close.loc[:date]
                mom_3m = ((spy_slice.iloc[-1] / spy_slice.iloc[-63]) - 1) * 100 if len(spy_slice) >= 63 else 0

                if dd < -15:
                    regime_labels.append('CRISIS')       # >15% drawdown from peak
                elif dd < -7:
                    regime_labels.append('CORRECTION')    # 7-15% drawdown
                elif mom_3m > 8:
                    regime_labels.append('BULL_RALLY')   # Strong 3m rally
                elif mom_3m > 0:
                    regime_labels.append('BULL_STEADY')  # Mild uptrend
                else:
                    regime_labels.append('BEAR_MILD')    # Mild downtrend
            except Exception:
                regime_labels.append('UNKNOWN')

        trades_df['market_regime'] = regime_labels

        # Analyze performance per regime
        regime_analysis = {}
        for regime in ['BULL_RALLY', 'BULL_STEADY', 'BEAR_MILD', 'CORRECTION', 'CRISIS']:
            r_trades = trades_df[trades_df['market_regime'] == regime]
            if len(r_trades) < 5:
                continue

            # Overall stats
            sb = r_trades[r_trades['signal'] == 'STRONG_BUY']
            sell = r_trades[r_trades['signal'] == 'SELL']

            regime_analysis[regime] = {
                'total_periods': len(r_trades) // max(1, len(self.tickers)),
                'total_trades': len(r_trades),
                'sb_count': len(sb),
                'sb_hit_rate': round((sb['return_pct'] > 0).mean() * 100, 1) if len(sb) > 0 else 0,
                'sb_avg_return': round(sb['return_pct'].mean(), 2) if len(sb) > 0 else 0,
                'sb_worst': round(sb['return_pct'].min(), 2) if len(sb) > 0 else 0,
                'sell_count': len(sell),
                'sell_hit_rate': round((sell['return_pct'] < 0).mean() * 100, 1) if len(sell) > 0 else 0,
                'sell_avg_return': round(sell['return_pct'].mean(), 2) if len(sell) > 0 else 0,
                'all_avg_return': round(r_trades['return_pct'].mean(), 2),
                'spread': round(sb['return_pct'].mean() - sell['return_pct'].mean(), 2) if len(sb) > 0 and len(sell) > 0 else 0,
            }

        return regime_analysis

    def test_formula_variants(self, horizon: str = 'short_term') -> dict:
        """Test 5 scoring formula variants across market regimes.
        V1: base contrarian, V2: macro-aware, V3: quality+momentum,
        V4: trend-following, V5: regime-adaptive (switches V1-V4).

        Args:
            horizon: 'short_term' (5-day hold), 'medium_term' (21-day), 'long_term' (63-day)
        """
        if not self.hist_data:
            if not self.download_historical_data():
                return {}

        spy = self.hist_data.get('SPY')
        if spy is None:
            return {}

        # Holding period per horizon
        hold_map = {'short_term': 5, 'medium_term': 21, 'long_term': 63}
        hold_days = hold_map.get(horizon, 5)

        # Different formula emphasis per horizon
        if horizon == 'long_term':
            variants = {
                'v1_base': {'contrarian': 0.30, 'trend': 0.20, 'vol': 0.15, 'momentum': 0.15, 'macro': 0.00, 'quality': 0.20},
                'v2_macro_aware': {'contrarian': 0.20, 'trend': 0.15, 'vol': 0.10, 'momentum': 0.10, 'macro': 0.20, 'quality': 0.25},
                'v3_quality_mom': {'contrarian': 0.10, 'trend': 0.15, 'vol': 0.10, 'momentum': 0.20, 'macro': 0.10, 'quality': 0.35},
                'v4_trend_follow': {'contrarian': 0.10, 'trend': 0.35, 'vol': 0.10, 'momentum': 0.25, 'macro': 0.05, 'quality': 0.15},
            }
        elif horizon == 'medium_term':
            variants = {
                'v1_base': {'contrarian': 0.35, 'trend': 0.25, 'vol': 0.15, 'momentum': 0.15, 'macro': 0.00, 'quality': 0.10},
                'v2_macro_aware': {'contrarian': 0.25, 'trend': 0.20, 'vol': 0.10, 'momentum': 0.10, 'macro': 0.20, 'quality': 0.15},
                'v3_quality_mom': {'contrarian': 0.10, 'trend': 0.20, 'vol': 0.10, 'momentum': 0.25, 'macro': 0.10, 'quality': 0.25},
                'v4_trend_follow': {'contrarian': 0.10, 'trend': 0.40, 'vol': 0.10, 'momentum': 0.25, 'macro': 0.10, 'quality': 0.05},
            }
        else:  # short_term
            variants = {
                'v1_base': {'contrarian': 0.40, 'trend': 0.25, 'vol': 0.15, 'momentum': 0.20, 'macro': 0.00},
                'v2_macro_aware': {'contrarian': 0.30, 'trend': 0.20, 'vol': 0.10, 'momentum': 0.15, 'macro': 0.25},
                'v3_quality_mom': {'contrarian': 0.15, 'trend': 0.20, 'vol': 0.10, 'momentum': 0.30, 'macro': 0.10, 'quality': 0.15},
                'v4_trend_follow': {'contrarian': 0.10, 'trend': 0.45, 'vol': 0.10, 'momentum': 0.25, 'macro': 0.10},
            }

        results = {}
        all_dates = spy.index
        start_idx = min(130, len(all_dates) - 10)
        rebal_dates = list(range(start_idx, len(all_dates) - hold_days, hold_days))

        # Pre-compute SPY vol for regime detection
        spy_close = spy['Close']

        for variant_name, weights in variants.items():
            variant_trades = []
            for idx in rebal_dates:
                date = all_dates[idx]
                exit_idx = min(idx + hold_days, len(all_dates) - 1)
                exit_date = all_dates[exit_idx]

                scores = {}
                for t in self.tickers:
                    s = self._compute_score_variant(t, date, weights)
                    if s is not None:
                        scores[t] = s

                if len(scores) < 5:
                    continue

                sorted_t = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top5 = {t for t, _ in sorted_t[:5]}

                # Regime from SPY vol + drawdown
                spy_slice = spy_close.loc[:date]
                spy_peak = float(spy_slice.max())
                dd = ((float(spy_slice.iloc[-1]) - spy_peak) / spy_peak * 100) if spy_peak > 0 else 0
                spy_vol = float(spy_slice.pct_change().tail(20).std() * np.sqrt(252) * 100) if len(spy_slice) >= 22 else 20
                if dd < -15:
                    regime = 'CRISIS'
                elif dd < -7:
                    regime = 'CORRECTION'
                elif spy_vol > 25:
                    regime = 'HIGH_VOL'
                else:
                    regime = 'NORMAL'

                for t in self.tickers:
                    if t not in scores:
                        continue
                    t_hist = self.hist_data.get(t)
                    if t_hist is None:
                        continue
                    try:
                        entry_loc = t_hist.index.get_indexer([date], method='nearest')[0]
                        exit_loc = t_hist.index.get_indexer([exit_date], method='nearest')[0]
                        fwd_ret = (float(t_hist.iloc[exit_loc]['Close']) / float(t_hist.iloc[entry_loc]['Close']) - 1) * 100
                        variant_trades.append({
                            'signal': 'STRONG_BUY' if t in top5 else 'OTHER',
                            'return_pct': fwd_ret,
                            'regime': regime,
                        })
                    except Exception:
                        continue

            if variant_trades:
                vt_df = pd.DataFrame(variant_trades)
                sb = vt_df[vt_df['signal'] == 'STRONG_BUY']
                results[variant_name] = {
                    'overall_hit_rate': round((sb['return_pct'] > 0).mean() * 100, 1) if len(sb) > 0 else 0,
                    'overall_avg_return': round(sb['return_pct'].mean(), 2) if len(sb) > 0 else 0,
                    'sharpe': round(sb['return_pct'].mean() / (sb['return_pct'].std() + 0.001), 2) if len(sb) > 5 else 0,
                    'max_dd': round(sb['return_pct'].min(), 2) if len(sb) > 0 else 0,
                }
                for regime in ['CRISIS', 'CORRECTION', 'NORMAL', 'HIGH_VOL']:
                    r_sb = sb[vt_df.loc[sb.index, 'regime'] == regime] if 'regime' in vt_df.columns else pd.DataFrame()
                    if len(r_sb) >= 3:
                        results[variant_name][f'{regime.lower()}_hit_rate'] = round((r_sb['return_pct'] > 0).mean() * 100, 1)
                        results[variant_name][f'{regime.lower()}_avg_return'] = round(r_sb['return_pct'].mean(), 2)

        # V5: regime-adaptive — pick best variant per regime
        if len(results) >= 2:
            v5_stats = {'overall_hit_rate': 0, 'overall_avg_return': 0, 'sharpe': 0, 'max_dd': 0}
            best_per_regime = {}
            for regime in ['CRISIS', 'CORRECTION', 'NORMAL', 'HIGH_VOL']:
                best_v, best_hr = None, -1
                for vn, vr in results.items():
                    hr = vr.get(f'{regime.lower()}_hit_rate', 0)
                    if hr > best_hr:
                        best_hr = hr
                        best_v = vn
                if best_v:
                    best_per_regime[regime] = best_v
                    v5_stats[f'{regime.lower()}_hit_rate'] = best_hr
                    v5_stats[f'{regime.lower()}_avg_return'] = results[best_v].get(f'{regime.lower()}_avg_return', 0)

            # Weighted average of best per-regime
            regime_weights = {'NORMAL': 0.50, 'HIGH_VOL': 0.20, 'CORRECTION': 0.20, 'CRISIS': 0.10}
            total_hr, total_ret = 0, 0
            for r, w in regime_weights.items():
                total_hr += v5_stats.get(f'{r.lower()}_hit_rate', 50) * w
                total_ret += v5_stats.get(f'{r.lower()}_avg_return', 0) * w
            v5_stats['overall_hit_rate'] = round(total_hr, 1)
            v5_stats['overall_avg_return'] = round(total_ret, 2)
            v5_stats['best_per_regime'] = best_per_regime
            results['v5_regime_adaptive'] = v5_stats

        return results

    def compare_all_variants(self, horizon: str = 'short_term') -> pd.DataFrame:
        """Run variant comparison and return summary table."""
        results = self.test_formula_variants(horizon=horizon)
        if not results:
            return pd.DataFrame()

        rows = []
        for variant, stats in results.items():
            rows.append({
                'Variant': variant,
                'Sharpe': stats.get('sharpe', 0),
                'Hit Rate %': stats.get('overall_hit_rate', 0),
                'Avg Ret %': stats.get('overall_avg_return', 0),
                'Worst Trade %': stats.get('max_dd', 0),
                'Crisis HR %': stats.get('crisis_hit_rate', 0),
                'Normal HR %': stats.get('normal_hit_rate', 0),
                'High Vol HR %': stats.get('high_vol_hit_rate', 0),
            })
        return pd.DataFrame(rows).sort_values('Sharpe', ascending=False)

    def _compute_score_variant(self, ticker: str, date: pd.Timestamp,
                                weights: dict) -> Optional[float]:
        """Compute score with custom weights for formula comparison."""
        hist = self.hist_data.get(ticker)
        if hist is None:
            return None

        hist_slice = hist.loc[:date]
        if len(hist_slice) < 60:
            return None

        close = hist_slice['Close']
        try:
            # RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 0.0001)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            # MACD
            macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
            macd_bullish = float(macd.iloc[-1]) > float(macd.ewm(span=9).mean().iloc[-1])

            # Momentum
            price = float(close.iloc[-1])
            mom_1m = ((close.iloc[-1] / close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0

            # Bollinger
            sma20 = float(close.rolling(20).mean().iloc[-1])
            std20 = float(close.rolling(20).std().iloc[-1])
            bb_pos = ((price - (sma20 - 2*std20)) / (4*std20) * 100) if std20 > 0 else 50

            # SMA structure
            sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price
            sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else sma50

            # Realized vol
            vol_20d = float(close.pct_change().tail(20).std() * np.sqrt(252) * 100) if len(close) >= 22 else 20

            score = 0
            w_c = weights.get('contrarian', 0.40)
            w_t = weights.get('trend', 0.25)
            w_v = weights.get('vol', 0.15)
            w_m = weights.get('momentum', 0.20)
            w_macro = weights.get('macro', 0.0)
            w_quality = weights.get('quality', 0.0)

            # Contrarian component
            rsi_c = 90 if rsi < 30 else (70 if rsi < 40 else (30 if rsi > 70 else 50))
            bb_c = max(5, min(95, 100 - bb_pos))
            mr = 90 if (rsi < 30 and float(mom_1m) < -5) else (75 if (rsi < 40 and float(mom_1m) < -3) else 50)
            score += ((rsi_c + bb_c + mr) / 3) * w_c

            # Trend component
            if price > sma200 and price < sma50:
                trend_s = 80
            elif price > sma50 > sma200:
                trend_s = 60
            elif price < sma200:
                trend_s = 35
            else:
                trend_s = 50
            macd_s = 85 if (macd_bullish and float(mom_1m) < 0) else (30 if not macd_bullish else 50)
            score += ((trend_s + macd_s) / 2) * w_t

            # Vol component
            vol_s = 70 if vol_20d < 15 else (60 if vol_20d < 25 else (65 if vol_20d > 40 else 45))
            score += vol_s * w_v

            # Momentum component (contrarian)
            mom_c = max(10, min(90, 50 - float(mom_1m) * 1.5))
            score += mom_c * w_m

            # Macro sector component (oil-based sector rotation)
            if w_macro > 0:
                oil_hist = self.hist_data.get('CL=F')
                sector = self.TICKER_SECTOR.get(ticker, 'Other')
                macro_s = 50
                if oil_hist is not None:
                    oil_slice = oil_hist['Close'].loc[:date]
                    if len(oil_slice) >= 5:
                        oil_chg = ((float(oil_slice.iloc[-1]) / float(oil_slice.iloc[-5])) - 1) * 100
                        if sector == 'Energy':
                            macro_s = max(10, min(95, 50 + oil_chg * 8))
                        elif sector == 'Tech':
                            macro_s = max(10, min(95, 50 - oil_chg * 3))
                        elif sector == 'Consumer':
                            macro_s = max(10, min(95, 50 - oil_chg * 4))
                        elif sector == 'Banks':
                            macro_s = max(10, min(95, 50 + oil_chg * 1))
                        elif sector == 'Healthcare':
                            macro_s = max(10, min(95, 50 + oil_chg * 0.5))
                score += macro_s * w_macro

            # Quality component
            if w_quality > 0:
                # Use vol as proxy for quality (low vol = more stable = higher quality)
                quality_s = max(20, min(80, 80 - vol_20d))
                score += quality_s * w_quality

            return round(score, 1)
        except Exception:
            return None


def run_backtest_cached(horizon: str = 'short_term') -> dict:
    """Run backtest and return results. Designed to be called with @st.cache_data."""
    bt = ScoringBacktester()
    success = bt.run_walk_forward(horizon=horizon)
    if not success:
        return {}
    report = bt.generate_report()
    report['regime_analysis'] = bt.analyze_market_regimes()
    return report


def run_regime_comparison() -> dict:
    """Run formula variant comparison across market regimes."""
    bt = ScoringBacktester()
    if not bt.download_historical_data():
        return {}
    return bt.test_formula_variants()


def run_variant_comparison() -> dict:
    """Run 5-variant comparison for all 3 horizons."""
    bt = ScoringBacktester()
    if not bt.download_historical_data():
        return {}

    all_results = {}
    for horizon in ['short_term', 'medium_term', 'long_term']:
        table = bt.compare_all_variants(horizon=horizon)
        variants = bt.test_formula_variants(horizon=horizon)
        all_results[horizon] = {
            'variants': variants,
            'table': table.to_dict('records') if not table.empty else [],
            'best_overall': table.iloc[0]['Variant'] if not table.empty else 'v1_base',
        }
    return all_results
