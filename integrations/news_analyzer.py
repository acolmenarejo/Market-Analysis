"""
===============================================================================
NEWS ANALYZER MODULE
===============================================================================
Analiza noticias financieras y calcula sentimiento para trading.

FUENTES:
    - Finnhub (primaria): https://finnhub.io/
    - Alpha Vantage (backup): https://www.alphavantage.co/

FUNCIONALIDADES:
    1. Obtener noticias recientes por ticker
    2. Calcular sentimiento con VADER
    3. Detectar noticias de alto impacto (earnings, FDA, M&A)
    4. Generar score de sentimiento para scoring

DEPENDENCIAS:
    pip install finnhub-python vaderSentiment requests

USO:
    from integrations.news_analyzer import NewsAnalyzer

    analyzer = NewsAnalyzer()
    news = analyzer.get_news('NVDA', days=7)
    sentiment = analyzer.get_sentiment_score('NVDA')
===============================================================================
"""

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import time
import re

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.api_config import (
    API_ENDPOINTS, API_KEYS, RATE_LIMITS, NEWS_CONFIG,
    get_api_key, is_api_configured
)

# Intentar importar VADER, con fallback
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    print("  Warning: vaderSentiment not installed. Using basic sentiment analysis.")

# Intentar importar finnhub
try:
    import finnhub
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    print("  Warning: finnhub-python not installed. Using fallback news source.")


class NewsAnalyzer:
    """
    Analizador de noticias con sentimiento para trading.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or NEWS_CONFIG
        self._cache = {}
        self._cache_time = {}

        # Inicializar VADER si está disponible
        if VADER_AVAILABLE:
            self.vader = SentimentIntensityAnalyzer()
        else:
            self.vader = None

        # Inicializar Finnhub si está disponible y configurado
        self.finnhub_client = None
        if FINNHUB_AVAILABLE and is_api_configured('finnhub'):
            api_key = get_api_key('finnhub')
            if api_key and not api_key.startswith('YOUR_'):
                self.finnhub_client = finnhub.Client(api_key=api_key)

    def _get_finnhub_news(self, ticker: str, from_date: str, to_date: str) -> List[Dict]:
        """Obtiene noticias de Finnhub"""
        if not self.finnhub_client:
            return []

        try:
            news = self.finnhub_client.company_news(ticker, _from=from_date, to=to_date)
            time.sleep(RATE_LIMITS['finnhub_free']['delay_seconds'])
            return news or []
        except Exception as e:
            print(f"  Finnhub error for {ticker}: {e}")
            return []

    def _get_yfinance_news(self, ticker: str) -> List[Dict]:
        """Fallback: obtiene noticias de yfinance"""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            news = stock.news or []

            # Normalizar formato
            normalized = []
            for item in news:
                normalized.append({
                    'headline': item.get('title', ''),
                    'summary': item.get('summary', ''),
                    'source': item.get('publisher', ''),
                    'url': item.get('link', ''),
                    'datetime': item.get('providerPublishTime', 0),
                    'category': 'general',
                })
            return normalized
        except Exception as e:
            print(f"  yfinance news error for {ticker}: {e}")
            return []

    def get_news(self, ticker: str, days: int = None) -> List[Dict]:
        """
        Obtiene noticias para un ticker.

        Returns:
            Lista de noticias con headline, summary, source, datetime, etc.
        """
        days = days or self.config['lookback_days']
        cache_key = f'news_{ticker}_{days}'

        # Check cache
        if cache_key in self._cache:
            cache_age = datetime.now() - self._cache_time.get(cache_key, datetime.min)
            if cache_age.total_seconds() < 3600:  # 1 hour cache
                return self._cache[cache_key]

        # Fechas
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Intentar Finnhub primero
        news = self._get_finnhub_news(ticker, from_date, to_date)

        # Fallback a yfinance
        if not news:
            news = self._get_yfinance_news(ticker)

        # Cache
        self._cache[cache_key] = news
        self._cache_time[cache_key] = datetime.now()

        return news

    def _calculate_vader_sentiment(self, text: str) -> float:
        """Calcula sentimiento con VADER (-1 a +1)"""
        if not self.vader:
            return self._calculate_basic_sentiment(text)

        scores = self.vader.polarity_scores(text)
        return scores['compound']

    def _calculate_basic_sentiment(self, text: str) -> float:
        """Sentimiento básico sin VADER (fallback)"""
        text = text.lower()

        # Palabras positivas y negativas para finanzas
        positive_words = [
            'beat', 'beats', 'exceeded', 'record', 'growth', 'profit', 'gain',
            'surge', 'soar', 'jump', 'rise', 'boost', 'strong', 'upgrade',
            'buy', 'bullish', 'outperform', 'positive', 'approval', 'approved',
            'success', 'win', 'deal', 'partnership', 'expansion', 'innovation',
            'breakthrough', 'recovery', 'momentum', 'optimistic', 'confidence',
        ]

        negative_words = [
            'miss', 'missed', 'loss', 'losses', 'decline', 'drop', 'fall',
            'plunge', 'crash', 'weak', 'downgrade', 'sell', 'bearish',
            'underperform', 'negative', 'rejection', 'rejected', 'fail',
            'failed', 'lawsuit', 'investigation', 'fraud', 'scandal',
            'layoff', 'layoffs', 'cut', 'cuts', 'warning', 'risk', 'concern',
            'trouble', 'crisis', 'bankruptcy', 'default', 'delay', 'recall',
        ]

        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        return (pos_count - neg_count) / total

    def _categorize_news(self, headline: str, summary: str = '') -> str:
        """Categoriza una noticia"""
        text = (headline + ' ' + summary).lower()

        categories = self.config['categories']
        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category

        return 'OTHER'

    def _assess_impact(self, headline: str, summary: str = '', category: str = 'OTHER') -> str:
        """Evalúa el impacto potencial de una noticia"""
        text = (headline + ' ' + summary).lower()

        # High impact keywords
        high_impact_keywords = self.config['high_impact_keywords']

        high_count = sum(1 for kw in high_impact_keywords if kw in text)

        # Categorías de alto impacto
        high_impact_categories = ['EARNINGS', 'FDA', 'M&A', 'REGULATORY']

        if high_count >= 2 or category in high_impact_categories:
            return 'HIGH'
        elif high_count >= 1:
            return 'MEDIUM'
        else:
            return 'LOW'

    def analyze_news(self, ticker: str, days: int = None) -> List[Dict]:
        """
        Analiza noticias con sentimiento y categorización.

        Returns:
            Lista de noticias analizadas con sentiment, category, impact
        """
        news = self.get_news(ticker, days)
        analyzed = []

        for item in news:
            headline = item.get('headline', '')
            summary = item.get('summary', '')
            full_text = f"{headline} {summary}"

            # Calcular sentimiento
            sentiment = self._calculate_vader_sentiment(full_text)

            # Categorizar
            category = self._categorize_news(headline, summary)

            # Evaluar impacto
            impact = self._assess_impact(headline, summary, category)

            # Fecha
            ts = item.get('datetime', 0)
            if isinstance(ts, int) and ts > 0:
                date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            else:
                date = str(ts)

            analyzed.append({
                'ticker': ticker,
                'headline': headline,
                'summary': summary[:200] if summary else '',  # Truncar
                'source': item.get('source', ''),
                'url': item.get('url', ''),
                'date': date,
                'sentiment': round(sentiment, 3),
                'sentiment_label': self._sentiment_to_label(sentiment),
                'category': category,
                'impact': impact,
            })

        # Ordenar por fecha (más reciente primero)
        analyzed.sort(key=lambda x: x['date'], reverse=True)
        return analyzed

    def _sentiment_to_label(self, sentiment: float) -> str:
        """Convierte score de sentimiento a etiqueta"""
        if sentiment >= 0.5:
            return 'VERY_POSITIVE'
        elif sentiment >= 0.1:
            return 'POSITIVE'
        elif sentiment <= -0.5:
            return 'VERY_NEGATIVE'
        elif sentiment <= -0.1:
            return 'NEGATIVE'
        else:
            return 'NEUTRAL'

    def get_sentiment_score(self, ticker: str, days: int = None) -> Dict:
        """
        Genera score de sentimiento agregado para un ticker.

        Returns:
            Dict con score (0-100), signal, y estadísticas
        """
        analyzed = self.analyze_news(ticker, days)

        if not analyzed:
            return {
                'ticker': ticker,
                'signal': 'NO_DATA',
                'score': 50,
                'avg_sentiment': 0,
                'news_count': 0,
                'positive_count': 0,
                'negative_count': 0,
                'high_impact_news': [],
                'confidence': 'LOW',
            }

        # Estadísticas
        sentiments = [n['sentiment'] for n in analyzed]
        avg_sentiment = sum(sentiments) / len(sentiments)

        positive = [n for n in analyzed if n['sentiment'] > 0.1]
        negative = [n for n in analyzed if n['sentiment'] < -0.1]
        high_impact = [n for n in analyzed if n['impact'] == 'HIGH']

        # Score (0-100, 50 = neutral)
        # Mapear avg_sentiment (-1 a +1) a score (0-100)
        score = 50 + (avg_sentiment * 50)
        score = max(0, min(100, score))

        # Ajustar por volumen de noticias
        if len(analyzed) > 10:
            # Más noticias = más peso al sentimiento
            adjustment = (avg_sentiment * 10)
            score = max(0, min(100, score + adjustment))

        # Ajustar por noticias de alto impacto
        for news in high_impact:
            if news['sentiment'] > 0.3:
                score += 5
            elif news['sentiment'] < -0.3:
                score -= 5
        score = max(0, min(100, score))

        # Señal
        if score >= 60:
            signal = 'BULLISH'
        elif score <= 40:
            signal = 'BEARISH'
        else:
            signal = 'NEUTRAL'

        # Confianza
        if len(analyzed) >= 10 and len(high_impact) >= 2:
            confidence = 'HIGH'
        elif len(analyzed) >= 5:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        return {
            'ticker': ticker,
            'signal': signal,
            'score': round(score, 1),
            'avg_sentiment': round(avg_sentiment, 3),
            'news_count': len(analyzed),
            'positive_count': len(positive),
            'negative_count': len(negative),
            'high_impact_news': [
                {'headline': n['headline'][:80], 'sentiment': n['sentiment'], 'category': n['category']}
                for n in high_impact[:3]
            ],
            'confidence': confidence,
            'days_analyzed': days or self.config['lookback_days'],
        }

    def detect_market_moving_events(self, ticker: str, days: int = None) -> List[Dict]:
        """
        Detecta eventos que pueden mover el mercado.

        Returns:
            Lista de eventos de alto impacto
        """
        analyzed = self.analyze_news(ticker, days)
        events = []

        for news in analyzed:
            if news['impact'] == 'HIGH':
                events.append({
                    'ticker': ticker,
                    'event_type': news['category'],
                    'headline': news['headline'],
                    'date': news['date'],
                    'sentiment': news['sentiment'],
                    'sentiment_label': news['sentiment_label'],
                    'source': news['source'],
                    'url': news['url'],
                })

        return events

    def generate_excel_data(self, ticker: str, days: int = None) -> List[Dict]:
        """
        Genera datos formateados para la hoja Excel de News_Sentiment.
        """
        analyzed = self.analyze_news(ticker, days)
        result = []

        for news in analyzed:
            result.append({
                'Ticker': ticker,
                'Date': news['date'],
                'Headline': news['headline'][:100],  # Truncar para Excel
                'Source': news['source'],
                'Sentiment_Score': news['sentiment'],
                'Sentiment_Label': news['sentiment_label'],
                'Category': news['category'],
                'Impact': news['impact'],
                'URL': news['url'],
            })

        return result


def get_news_sentiment_batch(tickers: List[str], days: int = 7) -> Dict[str, Dict]:
    """
    Obtiene sentimiento de noticias para múltiples tickers.
    """
    analyzer = NewsAnalyzer()
    results = {}

    for ticker in tickers:
        print(f"  Analyzing news for {ticker}...", end=" ")
        sentiment = analyzer.get_sentiment_score(ticker, days)
        results[ticker] = sentiment
        print(f"OK (Score: {sentiment['score']}, {sentiment['signal']})")

    return results


if __name__ == '__main__':
    # Test
    print("Testing News Analyzer...")
    print(f"VADER available: {VADER_AVAILABLE}")
    print(f"Finnhub available: {FINNHUB_AVAILABLE}")

    analyzer = NewsAnalyzer()

    test_ticker = 'NVDA'
    print(f"\nAnalyzing news for {test_ticker}...")

    # Get news
    news = analyzer.get_news(test_ticker, days=7)
    print(f"Found {len(news)} news articles")

    # Analyze
    analyzed = analyzer.analyze_news(test_ticker, days=7)
    print(f"\nAnalyzed {len(analyzed)} articles:")
    for n in analyzed[:3]:
        print(f"  - {n['headline'][:60]}...")
        print(f"    Sentiment: {n['sentiment']} ({n['sentiment_label']})")
        print(f"    Category: {n['category']}, Impact: {n['impact']}")

    # Get sentiment score
    print(f"\nSentiment Score for {test_ticker}:")
    score = analyzer.get_sentiment_score(test_ticker)
    print(f"  Signal: {score['signal']}")
    print(f"  Score: {score['score']}")
    print(f"  Avg Sentiment: {score['avg_sentiment']}")
    print(f"  News Count: {score['news_count']}")
    print(f"  Positive: {score['positive_count']}, Negative: {score['negative_count']}")
    print(f"  Confidence: {score['confidence']}")

    # Detect events
    print(f"\nMarket Moving Events:")
    events = analyzer.detect_market_moving_events(test_ticker)
    for event in events[:3]:
        print(f"  - [{event['event_type']}] {event['headline'][:50]}...")
