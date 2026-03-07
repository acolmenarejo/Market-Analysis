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


# Default liquid US stocks for backtesting
DEFAULT_BACKTEST_TICKERS = [
    'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA',
    'JPM', 'BAC', 'GS', 'UNH', 'JNJ', 'PFE', 'XOM', 'CVX',
    'V', 'MA', 'HD', 'WMT', 'CRM', 'ORCL', 'AMD', 'AVGO',
    'LLY', 'COST',
]


class ScoringBacktester:
    """Walk-forward backtester for multi-horizon scoring system."""

    def __init__(self, tickers: List[str] = None, lookback_years: int = 2):
        self.tickers = tickers or DEFAULT_BACKTEST_TICKERS
        self.lookback_years = lookback_years
        self.hist_data: Dict[str, pd.DataFrame] = {}
        self.trades: List[dict] = []
        self.equity_curve: Optional[pd.Series] = None
        self.benchmark_curve: Optional[pd.Series] = None

    def download_historical_data(self) -> bool:
        """Download historical OHLCV for all tickers + SPY benchmark."""
        try:
            all_tickers = self.tickers + ['SPY']
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

            return len(self.hist_data) >= 10
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

            # Get VIX regime at this date
            vix_hist = self.hist_data.get('SPY')  # Use SPY vol as proxy
            vix_regime = 'normal'
            if vix_hist is not None:
                spy_slice = vix_hist.loc[:date]
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

                    fwd_return = (exit_price / entry_price - 1) * 100

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
        """Calculate backtest performance metrics."""
        if not self.trades:
            return {}

        trades_df = pd.DataFrame(self.trades)

        # By signal
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

        # Overall portfolio metrics (STRONG_BUY portfolio)
        sb_trades = trades_df[trades_df['signal'] == 'STRONG_BUY']
        all_returns = sb_trades['return_pct'] if not sb_trades.empty else trades_df['return_pct']

        # Sharpe ratio (annualized, assuming weekly rebalance)
        if len(all_returns) > 1:
            sharpe = (all_returns.mean() / all_returns.std()) * np.sqrt(52) if all_returns.std() > 0 else 0
        else:
            sharpe = 0

        # Max drawdown from equity curve
        max_dd = 0
        if self.equity_curve is not None and len(self.equity_curve) > 0:
            peak = self.equity_curve.expanding().max()
            dd = (self.equity_curve - peak) / peak * 100
            max_dd = round(float(dd.min()), 1)

        # Win rate
        win_rate = round((all_returns > 0).mean() * 100, 1) if len(all_returns) > 0 else 0

        # Profit factor
        gross_profit = all_returns[all_returns > 0].sum()
        gross_loss = abs(all_returns[all_returns < 0].sum())
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf')

        # Alpha vs SPY
        alpha = 0
        if self.equity_curve is not None and self.benchmark_curve is not None:
            port_total = float(self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1) * 100
            bench_total = float(self.benchmark_curve.iloc[-1] / self.benchmark_curve.iloc[0] - 1) * 100
            alpha = round(port_total - bench_total, 1)

        # Macro regime analysis
        regime_stats = {}
        if 'vix_regime' in trades_df.columns:
            sb_df = trades_df[trades_df['signal'] == 'STRONG_BUY']
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
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades_df),
            'alpha_vs_spy': alpha,
            'avg_return': round(all_returns.mean(), 2),
            'regime_stats': regime_stats,
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


def run_backtest_cached(horizon: str = 'short_term') -> dict:
    """Run backtest and return results. Designed to be called with @st.cache_data."""
    bt = ScoringBacktester()
    success = bt.run_walk_forward(horizon=horizon)
    if not success:
        return {}
    return bt.generate_report()
