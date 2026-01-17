"""
===============================================================================
TECHNICAL INDICATORS MODULE
===============================================================================
Calcula indicadores técnicos usando pandas-ta.

Indicadores incluidos:
    BÁSICOS:
        - RSI (Relative Strength Index)
        - MACD (Moving Average Convergence Divergence)
        - Bollinger Bands

    AVANZADOS:
        - Ichimoku Cloud
        - Fibonacci Retracements
        - ATR (Average True Range) para stops

DEPENDENCIAS:
    pip install pandas-ta yfinance pandas numpy

USO:
    from integrations.technical_indicators import TechnicalAnalyzer

    analyzer = TechnicalAnalyzer()
    result = analyzer.analyze('NVDA', period='6mo')
    print(result['signal'])  # 'LONG', 'SHORT', o 'WAIT'
===============================================================================
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.api_config import TECHNICAL_CONFIG


class TechnicalAnalyzer:
    """
    Analizador técnico completo para trading de corto plazo.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or TECHNICAL_CONFIG

    def fetch_price_data(self, ticker: str, period: str = '6mo') -> Optional[pd.DataFrame]:
        """
        Obtiene datos OHLCV de yfinance.

        Args:
            ticker: Símbolo del activo
            period: Período de datos ('1mo', '3mo', '6mo', '1y')

        Returns:
            DataFrame con Open, High, Low, Close, Volume
        """
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)

            if df.empty:
                print(f"  Warning: No data for {ticker}")
                return None

            # Asegurar columnas necesarias
            required = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df.columns for col in required):
                print(f"  Warning: Missing columns for {ticker}")
                return None

            return df

        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
            return None

    def calculate_rsi(self, df: pd.DataFrame, period: int = None) -> pd.Series:
        """
        Calcula RSI (Relative Strength Index).

        RSI < 30: Oversold (posible LONG)
        RSI > 70: Overbought (posible SHORT)
        """
        period = period or self.config['rsi_period']

        try:
            import pandas_ta as ta
            return ta.rsi(df['Close'], length=period)
        except ImportError:
            # Fallback sin pandas-ta
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

    def calculate_macd(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Calcula MACD (Moving Average Convergence Divergence).

        Señales:
            - MACD cruza signal hacia arriba: BULLISH
            - MACD cruza signal hacia abajo: BEARISH
        """
        fast = self.config['macd_fast']
        slow = self.config['macd_slow']
        signal = self.config['macd_signal']

        try:
            import pandas_ta as ta
            macd_df = ta.macd(df['Close'], fast=fast, slow=slow, signal=signal)
            return {
                'macd': macd_df.iloc[:, 0],
                'signal': macd_df.iloc[:, 1],
                'histogram': macd_df.iloc[:, 2],
            }
        except ImportError:
            # Fallback sin pandas-ta
            exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
            exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
            macd = exp1 - exp2
            signal_line = macd.ewm(span=signal, adjust=False).mean()
            histogram = macd - signal_line
            return {
                'macd': macd,
                'signal': signal_line,
                'histogram': histogram,
            }

    def calculate_bollinger_bands(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Calcula Bollinger Bands.

        Señales:
            - Precio cerca de banda inferior: Posible rebote (LONG)
            - Precio cerca de banda superior: Posible corrección (SHORT)
        """
        period = self.config['bb_period']
        std = self.config['bb_std']

        try:
            import pandas_ta as ta
            bb_df = ta.bbands(df['Close'], length=period, std=std)
            return {
                'lower': bb_df.iloc[:, 0],
                'mid': bb_df.iloc[:, 1],
                'upper': bb_df.iloc[:, 2],
                'bandwidth': bb_df.iloc[:, 3] if bb_df.shape[1] > 3 else None,
                'percent_b': bb_df.iloc[:, 4] if bb_df.shape[1] > 4 else None,
            }
        except ImportError:
            # Fallback sin pandas-ta
            mid = df['Close'].rolling(window=period).mean()
            std_dev = df['Close'].rolling(window=period).std()
            upper = mid + (std * std_dev)
            lower = mid - (std * std_dev)
            return {
                'lower': lower,
                'mid': mid,
                'upper': upper,
                'bandwidth': (upper - lower) / mid,
                'percent_b': (df['Close'] - lower) / (upper - lower),
            }

    def calculate_ichimoku(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Calcula Ichimoku Cloud.

        Componentes:
            - Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
            - Kijun-sen (Base Line): (26-period high + 26-period low) / 2
            - Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen) / 2
            - Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
            - Chikou Span (Lagging Span): Close shifted back 26 periods

        Señales:
            - Precio sobre cloud: BULLISH
            - Precio bajo cloud: BEARISH
            - TK Cross (Tenkan cruza Kijun): Señal de momentum
        """
        tenkan = self.config['ichimoku_tenkan']
        kijun = self.config['ichimoku_kijun']
        senkou_b = self.config['ichimoku_senkou_b']

        try:
            import pandas_ta as ta
            ichi = ta.ichimoku(df['High'], df['Low'], df['Close'],
                              tenkan=tenkan, kijun=kijun, senkou=senkou_b)
            # ichimoku returns tuple: (dataframe, dataframe)
            ichi_df = ichi[0] if isinstance(ichi, tuple) else ichi
            return {
                'tenkan': ichi_df.iloc[:, 0] if ichi_df is not None else None,
                'kijun': ichi_df.iloc[:, 1] if ichi_df is not None else None,
                'senkou_a': ichi_df.iloc[:, 2] if ichi_df is not None else None,
                'senkou_b': ichi_df.iloc[:, 3] if ichi_df is not None else None,
                'chikou': ichi_df.iloc[:, 4] if ichi_df is not None and ichi_df.shape[1] > 4 else None,
            }
        except (ImportError, Exception):
            # Fallback sin pandas-ta
            high_tenkan = df['High'].rolling(window=tenkan).max()
            low_tenkan = df['Low'].rolling(window=tenkan).min()
            tenkan_sen = (high_tenkan + low_tenkan) / 2

            high_kijun = df['High'].rolling(window=kijun).max()
            low_kijun = df['Low'].rolling(window=kijun).min()
            kijun_sen = (high_kijun + low_kijun) / 2

            senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)

            high_senkou = df['High'].rolling(window=senkou_b).max()
            low_senkou = df['Low'].rolling(window=senkou_b).min()
            senkou_span_b = ((high_senkou + low_senkou) / 2).shift(kijun)

            chikou_span = df['Close'].shift(-kijun)

            return {
                'tenkan': tenkan_sen,
                'kijun': kijun_sen,
                'senkou_a': senkou_span_a,
                'senkou_b': senkou_span_b,
                'chikou': chikou_span,
            }

    def calculate_atr(self, df: pd.DataFrame, period: int = None) -> pd.Series:
        """
        Calcula ATR (Average True Range) para sizing de stops.
        """
        period = period or self.config['atr_period']

        try:
            import pandas_ta as ta
            return ta.atr(df['High'], df['Low'], df['Close'], length=period)
        except ImportError:
            # Fallback sin pandas-ta
            high_low = df['High'] - df['Low']
            high_close = abs(df['High'] - df['Close'].shift())
            low_close = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            return tr.rolling(window=period).mean()

    def calculate_fibonacci_levels(self, df: pd.DataFrame,
                                   lookback: int = None) -> Dict[str, float]:
        """
        Calcula niveles de Fibonacci basados en swing high/low reciente.

        Niveles estándar: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
        """
        lookback = lookback or self.config['fib_lookback']
        recent = df.tail(lookback)

        high = recent['High'].max()
        low = recent['Low'].min()
        diff = high - low

        levels = {}
        for level in self.config['fib_levels']:
            level_name = f'fib_{int(level * 100)}'
            levels[level_name] = high - (diff * level)

        levels['swing_high'] = high
        levels['swing_low'] = low
        levels['current_price'] = df['Close'].iloc[-1]

        # Determinar nivel actual
        price = levels['current_price']
        for i, level in enumerate(sorted(self.config['fib_levels'])):
            level_price = high - (diff * level)
            if price >= level_price:
                levels['current_level'] = level
                break

        return levels

    def generate_rsi_signal(self, rsi_value: float) -> Dict[str, Any]:
        """Genera señal basada en RSI"""
        oversold = self.config['rsi_oversold']
        overbought = self.config['rsi_overbought']

        if rsi_value < oversold:
            return {'signal': 'OVERSOLD', 'direction': 'LONG', 'strength': (oversold - rsi_value) / oversold}
        elif rsi_value > overbought:
            return {'signal': 'OVERBOUGHT', 'direction': 'SHORT', 'strength': (rsi_value - overbought) / (100 - overbought)}
        else:
            return {'signal': 'NEUTRAL', 'direction': 'WAIT', 'strength': 0}

    def generate_macd_signal(self, macd: Dict[str, pd.Series]) -> Dict[str, Any]:
        """Genera señal basada en MACD crossover"""
        macd_line = macd['macd'].iloc[-1]
        signal_line = macd['signal'].iloc[-1]
        histogram = macd['histogram'].iloc[-1]

        # Crossover detection
        prev_histogram = macd['histogram'].iloc[-2] if len(macd['histogram']) > 1 else 0

        if histogram > 0 and prev_histogram <= 0:
            return {'signal': 'BULLISH_CROSS', 'direction': 'LONG', 'strength': abs(histogram)}
        elif histogram < 0 and prev_histogram >= 0:
            return {'signal': 'BEARISH_CROSS', 'direction': 'SHORT', 'strength': abs(histogram)}
        elif histogram > 0:
            return {'signal': 'BULLISH', 'direction': 'LONG', 'strength': histogram}
        elif histogram < 0:
            return {'signal': 'BEARISH', 'direction': 'SHORT', 'strength': abs(histogram)}
        else:
            return {'signal': 'NEUTRAL', 'direction': 'WAIT', 'strength': 0}

    def generate_bb_signal(self, bb: Dict[str, pd.Series],
                           current_price: float) -> Dict[str, Any]:
        """Genera señal basada en Bollinger Bands"""
        lower = bb['lower'].iloc[-1]
        upper = bb['upper'].iloc[-1]
        mid = bb['mid'].iloc[-1]

        percent_b = (current_price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        if percent_b < 0.05:  # Cerca de banda inferior
            return {'signal': 'OVERSOLD', 'direction': 'LONG', 'strength': 1 - percent_b, 'percent_b': percent_b}
        elif percent_b > 0.95:  # Cerca de banda superior
            return {'signal': 'OVERBOUGHT', 'direction': 'SHORT', 'strength': percent_b, 'percent_b': percent_b}
        elif percent_b < 0.2:
            return {'signal': 'NEAR_LOWER', 'direction': 'LONG', 'strength': 0.5, 'percent_b': percent_b}
        elif percent_b > 0.8:
            return {'signal': 'NEAR_UPPER', 'direction': 'SHORT', 'strength': 0.5, 'percent_b': percent_b}
        else:
            return {'signal': 'NEUTRAL', 'direction': 'WAIT', 'strength': 0, 'percent_b': percent_b}

    def generate_ichimoku_signal(self, ichimoku: Dict[str, pd.Series],
                                  current_price: float) -> Dict[str, Any]:
        """Genera señal basada en Ichimoku Cloud"""
        if ichimoku['senkou_a'] is None or ichimoku['senkou_b'] is None:
            return {'signal': 'NO_DATA', 'direction': 'WAIT', 'strength': 0}

        senkou_a = ichimoku['senkou_a'].iloc[-1]
        senkou_b = ichimoku['senkou_b'].iloc[-1]
        tenkan = ichimoku['tenkan'].iloc[-1] if ichimoku['tenkan'] is not None else None
        kijun = ichimoku['kijun'].iloc[-1] if ichimoku['kijun'] is not None else None

        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)

        # Posición respecto a la nube
        if current_price > cloud_top:
            cloud_signal = 'ABOVE_CLOUD'
            direction = 'LONG'
            strength = (current_price - cloud_top) / cloud_top * 100
        elif current_price < cloud_bottom:
            cloud_signal = 'BELOW_CLOUD'
            direction = 'SHORT'
            strength = (cloud_bottom - current_price) / cloud_bottom * 100
        else:
            cloud_signal = 'IN_CLOUD'
            direction = 'WAIT'
            strength = 0

        # TK Cross
        tk_cross = None
        if tenkan is not None and kijun is not None:
            if tenkan > kijun:
                tk_cross = 'BULLISH'
            elif tenkan < kijun:
                tk_cross = 'BEARISH'
            else:
                tk_cross = 'NEUTRAL'

        return {
            'signal': cloud_signal,
            'direction': direction,
            'strength': min(strength, 100),
            'tk_cross': tk_cross,
            'cloud_top': cloud_top,
            'cloud_bottom': cloud_bottom,
        }

    def calculate_entry_exit(self, df: pd.DataFrame,
                             direction: str,
                             atr: pd.Series) -> Dict[str, float]:
        """
        Calcula precios de entrada, stop loss y targets basados en ATR.
        """
        current_price = df['Close'].iloc[-1]
        atr_value = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else current_price * 0.02

        stop_multiplier = self.config['atr_multiplier_stop']
        target_multiplier = self.config['atr_multiplier_target']

        if direction == 'LONG':
            entry = current_price
            stop_loss = current_price - (atr_value * stop_multiplier)
            target_1 = current_price + (atr_value * target_multiplier)
            target_2 = current_price + (atr_value * target_multiplier * 1.5)
        elif direction == 'SHORT':
            entry = current_price
            stop_loss = current_price + (atr_value * stop_multiplier)
            target_1 = current_price - (atr_value * target_multiplier)
            target_2 = current_price - (atr_value * target_multiplier * 1.5)
        else:
            entry = current_price
            stop_loss = current_price
            target_1 = current_price
            target_2 = current_price

        risk = abs(entry - stop_loss)
        reward = abs(target_1 - entry)
        risk_reward = reward / risk if risk > 0 else 0

        return {
            'entry': round(entry, 2),
            'stop_loss': round(stop_loss, 2),
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'risk_reward': round(risk_reward, 2),
            'atr': round(atr_value, 2),
        }

    def analyze(self, ticker: str, period: str = '6mo') -> Optional[Dict[str, Any]]:
        """
        Análisis técnico completo de un ticker.

        Returns:
            Dict con todos los indicadores, señales y recomendaciones
        """
        df = self.fetch_price_data(ticker, period)
        if df is None or len(df) < 50:
            return None

        current_price = df['Close'].iloc[-1]

        # Calcular indicadores
        rsi = self.calculate_rsi(df)
        macd = self.calculate_macd(df)
        bb = self.calculate_bollinger_bands(df)
        ichimoku = self.calculate_ichimoku(df)
        atr = self.calculate_atr(df)
        fib = self.calculate_fibonacci_levels(df)

        # Generar señales individuales
        rsi_signal = self.generate_rsi_signal(rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50)
        macd_signal = self.generate_macd_signal(macd)
        bb_signal = self.generate_bb_signal(bb, current_price)
        ichimoku_signal = self.generate_ichimoku_signal(ichimoku, current_price)

        # Calcular score técnico compuesto (0-100)
        signals = [rsi_signal, macd_signal, bb_signal, ichimoku_signal]
        direction_scores = {'LONG': 0, 'SHORT': 0, 'WAIT': 0}

        for sig in signals:
            direction = sig['direction']
            strength = sig.get('strength', 0)
            if direction in direction_scores:
                direction_scores[direction] += 1 + min(strength, 1)

        # Determinar dirección dominante
        max_direction = max(direction_scores, key=direction_scores.get)
        total_signals = sum(direction_scores.values())

        if direction_scores[max_direction] / total_signals >= 0.6:
            overall_direction = max_direction
        else:
            overall_direction = 'WAIT'

        # Score técnico (0-100, 50 = neutral)
        long_score = direction_scores['LONG'] / total_signals * 100 if total_signals > 0 else 50
        short_score = direction_scores['SHORT'] / total_signals * 100 if total_signals > 0 else 50
        tech_score = 50 + (long_score - short_score) / 2

        # Calcular entry/exit
        entry_exit = self.calculate_entry_exit(df, overall_direction, atr)

        # Determinar señal general
        if tech_score >= 70:
            overall_signal = 'STRONG_BUY'
        elif tech_score >= 60:
            overall_signal = 'BUY'
        elif tech_score <= 30:
            overall_signal = 'STRONG_SELL'
        elif tech_score <= 40:
            overall_signal = 'SELL'
        else:
            overall_signal = 'NEUTRAL'

        # Determinar confianza
        consensus = direction_scores[max_direction] / total_signals if total_signals > 0 else 0
        if consensus >= 0.75:
            confidence = 'HIGH'
        elif consensus >= 0.5:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        return {
            'ticker': ticker,
            'price': round(current_price, 2),
            'timestamp': datetime.now().isoformat(),

            # Indicadores
            'rsi_14': round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else None,
            'macd': round(macd['macd'].iloc[-1], 3) if not pd.isna(macd['macd'].iloc[-1]) else None,
            'macd_signal': round(macd['signal'].iloc[-1], 3) if not pd.isna(macd['signal'].iloc[-1]) else None,
            'macd_histogram': round(macd['histogram'].iloc[-1], 3) if not pd.isna(macd['histogram'].iloc[-1]) else None,
            'bb_upper': round(bb['upper'].iloc[-1], 2) if not pd.isna(bb['upper'].iloc[-1]) else None,
            'bb_lower': round(bb['lower'].iloc[-1], 2) if not pd.isna(bb['lower'].iloc[-1]) else None,
            'bb_percent': round(bb_signal['percent_b'] * 100, 1),
            'ichimoku_signal': ichimoku_signal['signal'],
            'tk_cross': ichimoku_signal.get('tk_cross'),
            'atr_14': round(atr.iloc[-1], 2) if not pd.isna(atr.iloc[-1]) else None,

            # Fibonacci
            'fib_levels': fib,

            # Señales individuales
            'rsi_signal': rsi_signal['signal'],
            'macd_signal_type': macd_signal['signal'],
            'bb_signal': bb_signal['signal'],

            # Score y dirección
            'tech_score': round(tech_score, 1),
            'direction': overall_direction,
            'overall_signal': overall_signal,
            'confidence': confidence,

            # Entry/Exit
            'entry': entry_exit['entry'],
            'stop_loss': entry_exit['stop_loss'],
            'target_1': entry_exit['target_1'],
            'target_2': entry_exit['target_2'],
            'risk_reward': entry_exit['risk_reward'],
        }


def analyze_batch(tickers: List[str], period: str = '6mo') -> List[Dict]:
    """
    Analiza múltiples tickers en batch.
    """
    analyzer = TechnicalAnalyzer()
    results = []

    for ticker in tickers:
        print(f"  Analyzing {ticker}...", end=" ")
        result = analyzer.analyze(ticker, period)
        if result:
            results.append(result)
            print(f"OK (Score: {result['tech_score']}, {result['direction']})")
        else:
            print("SKIP")

    return results


if __name__ == '__main__':
    # Test
    print("Testing Technical Analyzer...")
    analyzer = TechnicalAnalyzer()

    test_ticker = 'NVDA'
    result = analyzer.analyze(test_ticker)

    if result:
        print(f"\n{test_ticker} Analysis:")
        print(f"  Price: ${result['price']}")
        print(f"  RSI: {result['rsi_14']} ({result['rsi_signal']})")
        print(f"  MACD: {result['macd_signal_type']}")
        print(f"  Bollinger: {result['bb_signal']} (B%: {result['bb_percent']})")
        print(f"  Ichimoku: {result['ichimoku_signal']}")
        print(f"\n  Tech Score: {result['tech_score']}")
        print(f"  Direction: {result['direction']}")
        print(f"  Signal: {result['overall_signal']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"\n  Entry: ${result['entry']}")
        print(f"  Stop Loss: ${result['stop_loss']}")
        print(f"  Target 1: ${result['target_1']}")
        print(f"  Risk/Reward: {result['risk_reward']}")
    else:
        print(f"Failed to analyze {test_ticker}")
