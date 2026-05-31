"""
IC-based Backtester for MultiHorizonScorer
==========================================
Validates the real production scoring formula against forward returns.

Methodology:
 1. Sample anchor dates monthly across the lookback window (3 years).
 2. For each (date, ticker), build a `scoring_data` dict using ONLY data
    available at that date (no look-ahead) — RSI, MACD, momentum, BB, vol,
    macro (VIX/oil/credit), cross-sectional Fama ranks.
 3. Run `MultiHorizonScorer.calculate_all_horizons(scoring_data)` to get
    ST/MT/LT scores.
 4. Compute forward excess returns vs SPY over 21d/63d/126d.
 5. Metrics:
    - Spearman IC per date, then mean / IR (= mean/std)
    - Decile spread (top 20% return - bottom 20%)
    - Per-factor IC (which inputs actually predict returns)
    - Hit rate of STRONG_BUY signals
    - Long-only top-decile portfolio Sharpe / max drawdown

Fundamentals (ROE, debt/equity, margins) are intentionally STABLE proxies:
yfinance only exposes the current snapshot, so we use it for all backtest
dates. This biases the test slightly toward survivors but is unavoidable
without a paid point-in-time fundamentals feed. The factors most sensitive
to time — technicals, momentum, macro, cross-sectional ranks — are computed
correctly without look-ahead.
"""

from __future__ import annotations

import warnings
warnings.filterwarnings('ignore')

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from webapp.scoring.multi_horizon import MultiHorizonScorer, Horizon


# Universe: 60 liquid US stocks across all major sectors.
# Same set as the legacy backtester for comparability.
BACKTEST_UNIVERSE = [
    'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA', 'NFLX',
    'AVGO', 'AMD', 'INTC', 'QCOM', 'CRM', 'ORCL', 'IBM', 'NOW', 'ADBE',
    'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C', 'AXP', 'MA', 'V', 'SCHW',
    'UNH', 'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'AMGN', 'CVS',
    'WMT', 'COST', 'HD', 'MCD', 'PG', 'KO', 'PEP', 'NKE', 'LOW', 'TGT',
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY',
    'CAT', 'DE', 'UNP', 'HON', 'GE', 'LMT', 'RTX', 'BA', 'UPS',
    'AMT', 'NEE', 'PLD', 'O', 'EQIX',
]

MACRO_TICKERS = ['^VIX', '^MOVE', 'CL=F', 'GC=F', 'HYG', 'TLT', 'SPY',
                  '^TNX', '^IRX', '^FVX', 'TIP', 'IEF', 'LQD', 'DX-Y.NYB',
                  'GLD', 'USO']

# Sector mapping (lightweight — used for sector_pe_median + macro_sector_adj)
SECTOR_MAP = {
    'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology',
    'GOOGL': 'Communication Services', 'META': 'Communication Services',
    'AMZN': 'Consumer Cyclical', 'TSLA': 'Consumer Cyclical',
    'NFLX': 'Communication Services',
    'AVGO': 'Technology', 'AMD': 'Technology', 'INTC': 'Technology',
    'QCOM': 'Technology', 'CRM': 'Technology', 'ORCL': 'Technology',
    'IBM': 'Technology', 'NOW': 'Technology', 'ADBE': 'Technology',
    'JPM': 'Financial Services', 'BAC': 'Financial Services',
    'GS': 'Financial Services', 'MS': 'Financial Services',
    'WFC': 'Financial Services', 'C': 'Financial Services',
    'AXP': 'Financial Services', 'MA': 'Financial Services',
    'V': 'Financial Services', 'SCHW': 'Financial Services',
    'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'PFE': 'Healthcare',
    'MRK': 'Healthcare', 'ABBV': 'Healthcare', 'LLY': 'Healthcare',
    'AMGN': 'Healthcare', 'CVS': 'Healthcare',
    'WMT': 'Consumer Defensive', 'COST': 'Consumer Defensive',
    'HD': 'Consumer Cyclical', 'MCD': 'Consumer Cyclical',
    'PG': 'Consumer Defensive', 'KO': 'Consumer Defensive',
    'PEP': 'Consumer Defensive', 'NKE': 'Consumer Cyclical',
    'LOW': 'Consumer Cyclical', 'TGT': 'Consumer Defensive',
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy',
    'SLB': 'Energy', 'EOG': 'Energy', 'OXY': 'Energy',
    'CAT': 'Industrials', 'DE': 'Industrials', 'UNP': 'Industrials',
    'HON': 'Industrials', 'GE': 'Industrials', 'LMT': 'Industrials',
    'RTX': 'Industrials', 'BA': 'Industrials', 'UPS': 'Industrials',
    'AMT': 'Real Estate', 'NEE': 'Utilities', 'PLD': 'Real Estate',
    'O': 'Real Estate', 'EQIX': 'Real Estate',
}


@dataclass
class BacktestResult:
    """Container for backtest output."""
    horizon: str
    forward_days: int
    n_observations: int
    ic_mean: float          # Mean Spearman IC across dates
    ic_std: float           # Std of per-date IC
    ic_ir: float            # IC / std (information ratio)
    ic_t_stat: float        # t-statistic for significance
    decile_spread: float    # Top quintile return - bottom quintile (annualized)
    hit_rate_sb: float      # % of STRONG_BUY signals with positive excess return
    n_strong_buy: int
    factor_ic: Dict[str, float] = field(default_factory=dict)  # per-factor IC
    long_portfolio_return: float = 0.0  # CAGR of top-quintile long-only
    long_portfolio_sharpe: float = 0.0
    benchmark_return: float = 0.0


class ScorerBacktester:
    """Walk-forward backtest for the real MultiHorizonScorer."""

    HORIZON_DAYS = {'short_term': 21, 'medium_term': 63, 'long_term': 126}

    def __init__(self, tickers: List[str] = None, lookback_years: int = 3,
                 anchor_freq_days: int = 21):
        self.tickers = tickers or BACKTEST_UNIVERSE
        self.lookback_years = lookback_years
        self.anchor_freq_days = anchor_freq_days  # ~monthly
        self.hist: Dict[str, pd.DataFrame] = {}
        self.macro: Dict[str, pd.DataFrame] = {}
        self.fundamentals: Dict[str, dict] = {}
        self.scorer = MultiHorizonScorer()

    # ------------------------------------------------------------------
    # DATA LOADING
    # ------------------------------------------------------------------

    def load_data(self) -> bool:
        """Download all historical price + macro + current fundamentals."""
        end_date = datetime.now()
        # Need extra padding for warmup (200d SMA, 252d momentum, etc.)
        start_date = end_date - timedelta(days=self.lookback_years * 365 + 400)

        all_tickers = self.tickers + MACRO_TICKERS
        try:
            data = yf.download(
                all_tickers, start=start_date, end=end_date,
                group_by='ticker', auto_adjust=True, threads=True, progress=False
            )
        except Exception as e:
            print(f"Historical download failed: {e}")
            return False

        if data is None or data.empty:
            return False

        for t in all_tickers:
            try:
                if data.columns.nlevels == 1:
                    df = data
                else:
                    df = data[t].dropna(how='all')
                if df.empty:
                    continue
                df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna(subset=['Close'])
                if t in MACRO_TICKERS:
                    self.macro[t] = df
                else:
                    self.hist[t] = df
            except Exception:
                continue

        # Fundamentals (current snapshot — yfinance does not expose history cheaply)
        for t in self.tickers:
            try:
                info = yf.Ticker(t).info or {}
                self.fundamentals[t] = info
            except Exception:
                self.fundamentals[t] = {}

        return len(self.hist) >= 20

    # ------------------------------------------------------------------
    # SCORING DATA BUILDER (per anchor date, per ticker)
    # ------------------------------------------------------------------

    def _regime_at(self, date: pd.Timestamp) -> str:
        """Detect the professional macro regime as of `date` using ONLY data
        available at that date (no look-ahead). Mirrors logic of
        providers.detect_macro_regime() but operates on the cached macro series.

        Returns one of: 'easy' | 'tightening' | 'stagflation' | 'risk_off' | 'neutral'
        """
        def _series_at(sym):
            df = self.macro.get(sym)
            if df is None:
                return None
            sl = df.loc[:date]
            return sl['Close'] if not sl.empty else None

        def _last(s):
            return float(s.iloc[-1]) if s is not None and len(s) >= 1 else None

        def _pct_chg(s, n=20):
            if s is None or len(s) <= n:
                return 0.0
            return float((s.iloc[-1] / s.iloc[-n - 1] - 1) * 100)

        tnx = _series_at('^TNX')
        irx = _series_at('^IRX')
        tip = _series_at('TIP')
        ief = _series_at('IEF')
        hyg = _series_at('HYG')
        lqd = _series_at('LQD')
        tlt = _series_at('TLT')
        dxy = _series_at('DX-Y.NYB')
        vix = _series_at('^VIX')
        gld = _series_at('GLD')
        uso = _series_at('USO')
        spy = _series_at('SPY')

        ten_y = _last(tnx)
        two_y_proxy = _last(irx)
        curve_slope = (ten_y - two_y_proxy) if (ten_y and two_y_proxy) else None
        rates_trend_20d = _pct_chg(tnx, 20)
        real_rate_proxy = (ten_y - 2.5) if ten_y else None

        # Inflation proxy: TIP/IEF momentum + commodity outperformance
        tip_ief_chg = 0.0
        if tip is not None and ief is not None and len(tip) >= 21 and len(ief) >= 21:
            try:
                ratio_now = tip.iloc[-1] / ief.iloc[-1]
                ratio_then = tip.iloc[-21] / ief.iloc[-21]
                tip_ief_chg = (ratio_now / ratio_then - 1) * 100
            except Exception:
                pass
        gld_chg = _pct_chg(gld, 20)
        uso_chg = _pct_chg(uso, 20)
        spy_chg = _pct_chg(spy, 20)
        commodity_inflation = (gld_chg + uso_chg) / 2 - spy_chg
        inflation_proxy = (tip_ief_chg + commodity_inflation) / 2

        dxy_trend = _pct_chg(dxy, 20)

        # Credit stress
        hyg_chg_5d = _pct_chg(hyg, 5)
        lqd_chg_5d = _pct_chg(lqd, 5)
        hyg_chg_20d = _pct_chg(hyg, 20)
        credit_divergence = lqd_chg_5d - hyg_chg_5d
        cs = 50
        if hyg_chg_5d <= -2: cs -= 25
        elif hyg_chg_5d <= -1: cs -= 12
        elif hyg_chg_5d >= 1: cs += 10
        if credit_divergence > 1: cs -= 15
        elif credit_divergence < -0.5: cs += 8
        if hyg_chg_20d <= -3: cs -= 10
        credit_stress_score = max(5, min(95, cs))

        # Liquidity composite
        liq = 50
        liq -= dxy_trend * 3
        liq += _pct_chg(hyg, 20) * 2
        liq += _pct_chg(tlt, 20) * 1.5
        if curve_slope is not None:
            if curve_slope > 1.0: liq += 8
            elif curve_slope < -0.5: liq -= 12
        liq -= rates_trend_20d * 0.3
        liquidity_score = max(5, min(95, liq))

        # Regime classification
        vix_now = _last(vix) or 20
        rates_rising = rates_trend_20d > 3
        rates_falling = rates_trend_20d < -3
        high_real = (real_rate_proxy or 0) > 1.5
        rising_inflation = inflation_proxy > 2
        dollar_strong = dxy_trend > 1
        credit_calm = credit_stress_score > 60
        credit_stressed = credit_stress_score < 35
        hi_liq = liquidity_score > 60
        lo_liq = liquidity_score < 40

        if vix_now > 25 and credit_stressed:
            return 'risk_off'
        if (ten_y or 0) > 4.3 and inflation_proxy > 4 and high_real and dollar_strong:
            return 'stagflation'
        if rates_rising and (lo_liq or dollar_strong):
            return 'tightening'
        if (hi_liq or rates_falling) and credit_calm and vix_now < 20:
            return 'easy'
        return 'neutral'


    def _macro_at(self, date: pd.Timestamp) -> Dict[str, float]:
        """Compute macro overlay using only data up to `date`."""
        out = {
            'macro_composite': 50.0, 'macro_sector_adj': 0.0, 'macro_regime_boost': 50.0,
            'macro_oil_chg': 0.0, 'macro_vix': 18.0, 'macro_move': 100.0,
            'macro_hyg_chg': 0.0, 'macro_spy_chg': 0.0, 'vix_regime': 50.0,
            'macro_alerts': [],
        }

        # VIX level + 5d change
        vix_df = self.macro.get('^VIX')
        if vix_df is not None and not vix_df.empty:
            v_slice = vix_df.loc[:date]
            if len(v_slice) >= 5:
                vix_now = float(v_slice['Close'].iloc[-1])
                out['macro_vix'] = vix_now
                # VIX regime: <14=80, 14-18=65, 18-22=55, 22-28=40, 28-35=25, >35=15
                if vix_now < 14: out['vix_regime'] = 80
                elif vix_now < 18: out['vix_regime'] = 65
                elif vix_now < 22: out['vix_regime'] = 55
                elif vix_now < 28: out['vix_regime'] = 40
                elif vix_now < 35: out['vix_regime'] = 25
                else: out['vix_regime'] = 15

        # MOVE index
        move_df = self.macro.get('^MOVE')
        if move_df is not None and not move_df.empty:
            m_slice = move_df.loc[:date]
            if len(m_slice) >= 1:
                out['macro_move'] = float(m_slice['Close'].iloc[-1])

        # Oil 5d change
        oil_df = self.macro.get('CL=F')
        if oil_df is not None and not oil_df.empty:
            o_slice = oil_df.loc[:date]
            if len(o_slice) >= 6:
                out['macro_oil_chg'] = float(
                    (o_slice['Close'].iloc[-1] / o_slice['Close'].iloc[-6] - 1) * 100
                )

        # HYG 5d change
        hyg_df = self.macro.get('HYG')
        if hyg_df is not None and not hyg_df.empty:
            h_slice = hyg_df.loc[:date]
            if len(h_slice) >= 6:
                out['macro_hyg_chg'] = float(
                    (h_slice['Close'].iloc[-1] / h_slice['Close'].iloc[-6] - 1) * 100
                )

        # SPY 5d change
        spy_df = self.macro.get('SPY')
        if spy_df is not None and not spy_df.empty:
            s_slice = spy_df.loc[:date]
            if len(s_slice) >= 6:
                out['macro_spy_chg'] = float(
                    (s_slice['Close'].iloc[-1] / s_slice['Close'].iloc[-6] - 1) * 100
                )

        # Composite macro score (mimic _compute_macro_overlay heuristic)
        comp = 50
        if out['macro_vix'] > 25: comp -= 15
        elif out['macro_vix'] > 20: comp -= 8
        elif out['macro_vix'] < 14: comp += 8
        if abs(out['macro_oil_chg']) > 5: comp -= 8
        if abs(out['macro_hyg_chg']) > 1.0: comp -= 6
        if out['macro_spy_chg'] < -2: comp -= 10
        elif out['macro_spy_chg'] > 1.5: comp += 5
        if out['macro_move'] > 120: comp -= 5
        out['macro_composite'] = max(5, min(95, comp))
        out['macro_regime_boost'] = out['macro_composite']  # simplified

        return out

    def _cross_sectional_ranks(self, date: pd.Timestamp) -> Dict[str, Dict[str, float]]:
        """Compute per-date Fama-style percentile ranks across the universe."""
        mom_vals, vol_vals, value_vals, quality_vals = {}, {}, {}, {}
        for t in self.tickers:
            hist = self.hist.get(t)
            if hist is None:
                continue
            sl = hist.loc[:date]
            if len(sl) < 60:
                continue
            close = sl['Close']

            # 12-1 month momentum
            try:
                if len(close) >= 252:
                    m = float((close.iloc[-21] / close.iloc[-252]) - 1) * 100
                elif len(close) >= 126:
                    m = float((close.iloc[-21] / close.iloc[-126]) - 1) * 100
                else:
                    m = float((close.iloc[-21] / close.iloc[-60]) - 1) * 100
            except Exception:
                m = 0
            mom_vals[t] = m if not np.isnan(m) else 0

            # 60d realized vol
            try:
                rets = close.pct_change().dropna().tail(60)
                v = float(rets.std() * np.sqrt(252) * 100) if len(rets) >= 30 else 25.0
            except Exception:
                v = 25.0
            vol_vals[t] = v

            # Value: earnings yield + FCF yield (use stable fundamentals)
            info = self.fundamentals.get(t, {})
            pe = float(info.get('trailingPE', 0) or 0)
            fcf = float(info.get('freeCashflow', 0) or 0)
            mcap = float(info.get('marketCap', 0) or 0)
            ey = (1 / pe * 100) if pe > 0 else 0
            fy = (fcf / mcap * 100) if mcap > 0 else 0
            value_vals[t] = ey * 0.5 + fy * 0.5

            # Quality: ROE + gross margin
            roe = float(info.get('returnOnEquity', 0) or 0) * 100
            gm = float(info.get('grossMargins', 0) or 0) * 100
            quality_vals[t] = roe * 0.6 + gm * 0.4

        def _pct(d, higher_better=True):
            if not d or len(d) < 5:
                return {k: 50.0 for k in d}
            items = sorted(d.items(), key=lambda x: x[1])
            n = len(items)
            return {
                t: (rank / max(n - 1, 1)) * 100 if higher_better else 100 - (rank / max(n - 1, 1)) * 100
                for rank, (t, _) in enumerate(items)
            }

        mom_pct = _pct(mom_vals, True)
        vol_pct = _pct(vol_vals, False)
        val_pct = _pct(value_vals, True)
        qual_pct = _pct(quality_vals, True)

        return {
            t: {
                'fama_momentum': mom_pct.get(t, 50),
                'fama_low_vol': vol_pct.get(t, 50),
                'fama_value': val_pct.get(t, 50),
                'fama_quality': qual_pct.get(t, 50),
            }
            for t in self.tickers
        }

    def _build_scoring_data(self, ticker: str, date: pd.Timestamp,
                            macro: Dict[str, float],
                            cs_ranks: Dict[str, float],
                            sector_pe_med: float,
                            macro_regime: str = 'neutral') -> Optional[Dict]:
        """Build a scoring_data dict for one (ticker, date) — no look-ahead."""
        hist = self.hist.get(ticker)
        if hist is None:
            return None
        sl = hist.loc[:date]
        if len(sl) < 60:
            return None

        close = sl['Close']
        high = sl['High']
        low = sl['Low']
        vol = sl['Volume']
        try:
            # RSI(14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-9)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            # MACD
            e12 = close.ewm(span=12, adjust=False).mean()
            e26 = close.ewm(span=26, adjust=False).mean()
            macd_line = e12 - e26
            sig_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_bullish = bool(float(macd_line.iloc[-1]) > float(sig_line.iloc[-1]))
            # detect cross within last 3 days
            if len(macd_line) >= 4:
                prev_bull = float(macd_line.iloc[-4]) > float(sig_line.iloc[-4])
                if macd_bullish and not prev_bull:
                    macd_signal = 'bullish_cross'
                elif not macd_bullish and prev_bull:
                    macd_signal = 'bearish_cross'
                else:
                    macd_signal = 'bullish' if macd_bullish else 'bearish'
            else:
                macd_signal = 'bullish' if macd_bullish else 'bearish'

            # Bollinger position 0-100
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_lo = float((sma20 - std20 * 2).iloc[-1])
            bb_hi = float((sma20 + std20 * 2).iloc[-1])
            price = float(close.iloc[-1])
            bb_range = bb_hi - bb_lo
            bb_pos = ((price - bb_lo) / bb_range) * 100 if bb_range > 0 else 50

            # VWAP — running daily-weighted (use recent 20d slice)
            tp = (high + low + close) / 3
            recent = sl.tail(20)
            tp20 = ((recent['High'] + recent['Low'] + recent['Close']) / 3)
            vwap = float((tp20 * recent['Volume']).sum() / max(recent['Volume'].sum(), 1))

            # Momentum
            mom_1w = float((close.iloc[-1] / close.iloc[-5] - 1) * 100) if len(close) >= 5 else 0
            mom_1m = float((close.iloc[-1] / close.iloc[-20] - 1) * 100) if len(close) >= 20 else 0
            mom_3m = float((close.iloc[-1] / close.iloc[-60] - 1) * 100) if len(close) >= 60 else 0
            mom_6m = float((close.iloc[-1] / close.iloc[-126] - 1) * 100) if len(close) >= 126 else mom_3m

            # Volume ratio
            avgv = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else float(vol.mean())
            vol_ratio = float(vol.iloc[-1] / avgv) if avgv > 0 else 1.0

            # Relative strength vs SPY (1m)
            spy = self.macro.get('SPY')
            rs_1m = 0
            if spy is not None and not spy.empty:
                ss = spy.loc[:date]
                if len(ss) >= 20:
                    spy_mom = float((ss['Close'].iloc[-1] / ss['Close'].iloc[-20] - 1) * 100)
                    rs_1m = mom_1m - spy_mom

            # ADX (14)
            tr = pd.concat([
                (high - low),
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ], axis=1).max(axis=1)
            up_move = high.diff()
            down_move = -low.diff()
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            atr = tr.ewm(alpha=1/14, adjust=False).mean()
            pdi = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1/14, adjust=False).mean() / (atr + 1e-9)
            mdi = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1/14, adjust=False).mean() / (atr + 1e-9)
            dx = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-9)
            adx_val = float(dx.ewm(alpha=1/14, adjust=False).mean().iloc[-1])
            trend_dir = 'up' if float(pdi.iloc[-1]) > float(mdi.iloc[-1]) else 'down'

            # Sector
            sector = SECTOR_MAP.get(ticker, 'Other')
            info = self.fundamentals.get(ticker, {})

            return {
                'ticker': ticker,
                'price': price,
                'vwap': vwap,
                'rsi_14': rsi,
                'macd_signal': macd_signal,
                'volume_profile_position': 'neutral',
                'bollinger_position': bb_pos,
                'volume_ratio': vol_ratio,
                'momentum_1w': mom_1w,
                'momentum_1m': mom_1m,
                'momentum_3m': mom_3m,
                'momentum_6m': mom_6m,
                'relative_strength_1m': rs_1m,
                # Fundamentals (stable snapshot)
                'pe_ratio': float(info.get('trailingPE', 0) or 0),
                'pb_ratio': float(info.get('priceToBook', 0) or 0),
                'ev_ebitda': float(info.get('enterpriseToEbitda', 0) or 0),
                'roe': float(info.get('returnOnEquity', 0) or 0) * 100,
                'roic': float(info.get('returnOnAssets', 0) or 0) * 100,
                'profit_margin': float(info.get('profitMargins', 0) or 0) * 100,
                'gross_margin': float(info.get('grossMargins', 0) or 0) * 100,
                'operating_margin': float(info.get('operatingMargins', 0) or 0) * 100,
                'debt_to_equity': float(info.get('debtToEquity', 0) or 0),
                'debt_ebitda': 0,
                'current_ratio': float(info.get('currentRatio', 0) or 0),
                'interest_coverage': 10,
                'dividend_yield': 0,
                'sector': sector,
                'sector_pe_median': sector_pe_med,
                # Optional signals (skip noisy ones — set neutral)
                'congress_score': 50,
                'news_sentiment': 0,
                'options_flow': 'neutral',
                'analyst_revisions': 0,
                'earnings_surprise': 0,
                'konkorde_score': 50, 'konkorde_signal': 'neutral',
                'trendline_score': 50, 'rsi_crossover_score': 50,
                'konkorde_divergence_score': 50,
                'iv_percentile': 50, 'skew_score': 50,
                'sector_rs': 50, 'short_interest': 0, 'fcf_quality': 50,
                'margin_trend': 0, 'debt_trend': 0,
                'adx': adx_val, 'trend_direction': trend_dir,
                'sr_position': 'middle',
                'institutional_flow': 50, 'insider_activity': 'neutral',
                'fcf_yield': 0, 'peg_ratio': float(info.get('pegRatio', 0) or 0),
                'margin_stability': 50, 'moat_score': 50, 'earnings_stability': 50,
                'dividend_growth_years': 0,
                # Macro
                **macro,
                # Cross-sectional
                **cs_ranks,
                # Professional regime override
                'macro_regime': macro_regime,
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # FORWARD RETURNS
    # ------------------------------------------------------------------

    def _forward_return(self, ticker: str, date: pd.Timestamp, days: int) -> Optional[float]:
        """Total return over `days` trading days after `date`."""
        hist = self.hist.get(ticker)
        if hist is None:
            return None
        try:
            future = hist.loc[date:]
            if len(future) < days + 1:
                return None
            p_now = float(future['Close'].iloc[0])
            p_then = float(future['Close'].iloc[days])
            return (p_then / p_now - 1) * 100
        except Exception:
            return None

    def _benchmark_return(self, date: pd.Timestamp, days: int) -> Optional[float]:
        spy = self.macro.get('SPY')
        if spy is None:
            return 0
        try:
            future = spy.loc[date:]
            if len(future) < days + 1:
                return None
            return (float(future['Close'].iloc[days]) / float(future['Close'].iloc[0]) - 1) * 100
        except Exception:
            return None

    # ------------------------------------------------------------------
    # MAIN BACKTEST
    # ------------------------------------------------------------------

    def _anchor_dates(self, sample: str = 'all') -> List[pd.Timestamp]:
        """Generate monthly anchor dates spanning the lookback window.

        ``sample``: 'all' | 'train' (first 60%) | 'oos' (last 40%) — for
        held-out validation that confirms the calibration generalizes.
        """
        spy = self.macro.get('SPY')
        if spy is None or spy.empty:
            return []
        max_fwd = max(self.HORIZON_DAYS.values())
        usable = spy.index[200:-max_fwd]
        if len(usable) < self.anchor_freq_days * 5:
            return []
        all_anchors = list(usable[::self.anchor_freq_days])
        if sample == 'all':
            return all_anchors
        split = int(len(all_anchors) * 0.6)
        return all_anchors[:split] if sample == 'train' else all_anchors[split:]

    def run(self, horizon: str = 'short_term', verbose: bool = True,
            sample: str = 'all') -> BacktestResult:
        """Run the full backtest for one horizon.

        ``sample``: 'all' uses full window. 'train' uses first 60% of anchors,
        'oos' uses last 40% — pass 'oos' to validate that the calibration
        generalizes out-of-sample.
        """
        if horizon not in self.HORIZON_DAYS:
            raise ValueError(f"Unknown horizon: {horizon}")
        fwd_days = self.HORIZON_DAYS[horizon]

        anchors = self._anchor_dates(sample=sample)
        if verbose:
            print(f"\nBacktest [{horizon}, fwd={fwd_days}d] over {len(anchors)} anchor dates "
                  f"× {len(self.tickers)} tickers")

        per_date_records = []   # list of dicts {date, ticker, score, fwd_ret, fwd_excess}
        per_date_ics = []
        factor_collector = {}   # {factor_name: list of (factor_val, fwd_ret)}

        regime_log = {}
        for idx, date in enumerate(anchors):
            macro = self._macro_at(date)
            macro_regime = self._regime_at(date)
            regime_log[date] = macro_regime
            cs_ranks_all = self._cross_sectional_ranks(date)

            # Sector PE median for this date (from current snapshot, stable)
            sector_pes = {}
            for t in self.tickers:
                info = self.fundamentals.get(t, {})
                pe = float(info.get('trailingPE', 0) or 0)
                sec = SECTOR_MAP.get(t, 'Other')
                if 0 < pe < 200:
                    sector_pes.setdefault(sec, []).append(pe)
            sector_pe_medians = {s: float(np.median(pes)) for s, pes in sector_pes.items() if pes}

            scores_today = []
            for t in self.tickers:
                sd = self._build_scoring_data(
                    t, date, macro,
                    cs_ranks_all.get(t, {'fama_momentum': 50, 'fama_low_vol': 50,
                                          'fama_value': 50, 'fama_quality': 50}),
                    sector_pe_medians.get(SECTOR_MAP.get(t, 'Other'), 20),
                    macro_regime=macro_regime,
                )
                if sd is None:
                    continue
                try:
                    result = self.scorer.calculate_all_horizons(sd)
                    if horizon == 'short_term':
                        hz = result.short_term
                    elif horizon == 'medium_term':
                        hz = result.medium_term
                    else:
                        hz = result.long_term
                    fwd_ret = self._forward_return(t, date, fwd_days)
                    if fwd_ret is None:
                        continue
                    bench = self._benchmark_return(date, fwd_days) or 0
                    excess = fwd_ret - bench

                    scores_today.append({
                        'date': date, 'ticker': t,
                        'score': hz.total_score, 'signal': hz.signal.value,
                        'fwd_ret': fwd_ret, 'fwd_excess': excess,
                        'components': hz.components,
                    })
                except Exception:
                    continue

            if len(scores_today) >= 10:
                df_today = pd.DataFrame(scores_today)
                # Per-date Spearman IC: score rank vs forward excess return rank
                ic = df_today['score'].corr(df_today['fwd_excess'], method='spearman')
                if not np.isnan(ic):
                    per_date_ics.append(ic)
                per_date_records.extend(scores_today)

                # Collect per-factor values for factor IC
                for rec in scores_today:
                    for fname, fval in rec['components'].items():
                        factor_collector.setdefault(fname, []).append((fval, rec['fwd_excess']))

            if verbose and (idx + 1) % 5 == 0:
                print(f"  [{idx+1}/{len(anchors)}] {date.date()} — IC so far: "
                      f"mean={np.mean(per_date_ics):.3f}, n_dates={len(per_date_ics)}")

        # Aggregate
        ic_arr = np.array(per_date_ics)
        ic_mean = float(np.mean(ic_arr)) if len(ic_arr) > 0 else 0
        ic_std = float(np.std(ic_arr)) if len(ic_arr) > 1 else 1
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0
        ic_t_stat = ic_mean / (ic_std / np.sqrt(len(ic_arr))) if ic_std > 0 and len(ic_arr) > 0 else 0

        # Per-factor IC (Spearman across all observations)
        factor_ic = {}
        for fname, pairs in factor_collector.items():
            if len(pairs) < 50:
                continue
            df_f = pd.DataFrame(pairs, columns=['val', 'ret'])
            if df_f['val'].nunique() < 5:
                continue
            try:
                ic_f = df_f['val'].corr(df_f['ret'], method='spearman')
                if not np.isnan(ic_f):
                    factor_ic[fname] = float(ic_f)
            except Exception:
                pass

        # Decile spread: top quintile vs bottom quintile of scores
        all_df = pd.DataFrame(per_date_records)
        decile_spread = 0
        if not all_df.empty:
            all_df['rank'] = all_df.groupby('date')['score'].rank(pct=True)
            top = all_df[all_df['rank'] >= 0.8]['fwd_excess'].mean()
            bot = all_df[all_df['rank'] <= 0.2]['fwd_excess'].mean()
            decile_spread = float(top - bot) if not (np.isnan(top) or np.isnan(bot)) else 0

        # Hit rate of STRONG_BUY
        sb_df = all_df[all_df['signal'] == 'STRONG BUY'] if not all_df.empty else pd.DataFrame()
        hit_rate = 0
        if not sb_df.empty:
            hit_rate = float((sb_df['fwd_excess'] > 0).mean() * 100)

        # Long-only portfolio: top quintile each anchor, hold for fwd_days
        portfolio_ret, sharpe, bench_ret = 0, 0, 0
        if not all_df.empty:
            anchor_returns = []
            bench_returns = []
            for date, grp in all_df.groupby('date'):
                grp_sorted = grp.sort_values('score', ascending=False)
                top_n = max(int(len(grp_sorted) * 0.2), 1)
                top_picks = grp_sorted.head(top_n)
                anchor_returns.append(top_picks['fwd_ret'].mean())
                bench_returns.append(self._benchmark_return(date, fwd_days) or 0)
            anchor_returns = pd.Series(anchor_returns)
            bench_returns = pd.Series(bench_returns)
            # Annualize: periods per year ≈ 252 / anchor_freq_days, scale to fwd_days
            periods_per_yr = 252 / self.anchor_freq_days
            mean_p = anchor_returns.mean()
            std_p = anchor_returns.std() if len(anchor_returns) > 1 else 1
            # Convert period return to annualized
            portfolio_ret = mean_p * periods_per_yr  # simple, %/year
            sharpe = (mean_p / std_p) * np.sqrt(periods_per_yr) if std_p > 0 else 0
            bench_ret = bench_returns.mean() * periods_per_yr

        return BacktestResult(
            horizon=horizon,
            forward_days=fwd_days,
            n_observations=len(per_date_records),
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            ic_t_stat=ic_t_stat,
            decile_spread=decile_spread,
            hit_rate_sb=hit_rate,
            n_strong_buy=len(sb_df),
            factor_ic=factor_ic,
            long_portfolio_return=portfolio_ret,
            long_portfolio_sharpe=float(sharpe),
            benchmark_return=bench_ret,
        )


def print_result(r: BacktestResult, top_n_factors: int = 15) -> None:
    """Pretty-print a backtest result with diagnostics."""
    print("=" * 70)
    print(f"  Horizon: {r.horizon}  ({r.forward_days} trading days forward)")
    print("=" * 70)
    print(f"  Observations:      {r.n_observations:,}")
    print(f"  Mean IC (Spearman): {r.ic_mean:+.4f}")
    print(f"  IC std:             {r.ic_std:.4f}")
    print(f"  IC IR (= mean/std): {r.ic_ir:+.3f}")
    print(f"  IC t-stat:          {r.ic_t_stat:+.2f}  (>2 = significant)")
    print(f"  Decile spread:      {r.decile_spread:+.2f}%  (top quintile - bottom)")
    print(f"  STRONG_BUY signals: {r.n_strong_buy}  hit-rate: {r.hit_rate_sb:.1f}%")
    print(f"  Long top-quintile:  {r.long_portfolio_return:+.2f}%/yr  Sharpe={r.long_portfolio_sharpe:.2f}")
    print(f"  SPY benchmark:      {r.benchmark_return:+.2f}%/yr")
    print(f"  Alpha:              {r.long_portfolio_return - r.benchmark_return:+.2f}%/yr")
    print()
    print(f"  Top factors by |IC| (predictive power):")
    sorted_factors = sorted(r.factor_ic.items(), key=lambda x: abs(x[1]), reverse=True)
    for name, ic in sorted_factors[:top_n_factors]:
        flag = "+" if ic >= 0 else "-"
        print(f"    {flag} {ic:+.4f}  {name}")
    print()
    print(f"  Bottom factors (noisy / harmful):")
    for name, ic in sorted_factors[-5:]:
        print(f"    {ic:+.4f}  {name}")


if __name__ == '__main__':
    bt = ScorerBacktester(lookback_years=3)
    print("Loading data...")
    if not bt.load_data():
        print("FAILED to load data")
        raise SystemExit(1)
    print(f"Loaded {len(bt.hist)} tickers, {len(bt.macro)} macro series")
    for hz in ('short_term', 'medium_term', 'long_term'):
        r = bt.run(hz)
        print_result(r)
