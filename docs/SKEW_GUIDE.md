# 📊 GUÍA COMPLETA: SKEW - EL INDICADOR DE MIEDO INSTITUCIONAL

---

## **🎯 ¿QUÉ ES EL SKEW?**

### **Definición Simple**

El **SKEW** mide **cuánto más caro están los puts OTM comparado con los calls OTM** del mismo strike distance.

**Fórmula conceptual:**
```
SKEW = IV de Puts OTM - IV de Calls OTM
```

**Interpretación:**
- **SKEW alto (positivo)** → Puts caros → Miedo / Demanda de protección → **PUT BIAS**
- **SKEW bajo (negativo)** → Calls caros → Euforia / Especulación → **CALL BIAS**
- **SKEW normal** → ~5-10% para índices (S&P, NDX)

---

## **📐 SKEW vs CBOE SKEW INDEX**

Hay **dos formas** de medir skew:

### **1. Simple IV Skew (lo que tienes en tu app)**

```python
# webapp/app.py - líneas 3065-3070
otm_puts = puts[puts['strike'] < price * 0.95]   # Puts 5% OTM
otm_calls = calls[calls['strike'] > price * 1.05] # Calls 5% OTM
put_iv_avg = float(otm_puts['impliedVolatility'].mean() * 100)
call_iv_avg = float(otm_calls['impliedVolatility'].mean() * 100)
skew = put_iv_avg - call_iv_avg
```

**Ventaja:** Simple, fácil de calcular
**Desventaja:** No estandarizado, cambia según qué strikes elijas

---

### **2. CBOE SKEW Index (oficial)**

**Fórmula compleja:**
```
SKEW = 100 - 10 × (Expected value of 2% tail - Expected value of normal distribution)
```

- **Rango:** 100-150 típicamente
- **100** = Distribución normal (sin skew)
- **135+** = Tail risk extremo (como pre-crash)

**Interpretación CBOE SKEW:**
- **100-115:** Skew normal (put demand moderado)
- **115-130:** Skew elevado (hedging activo)
- **130-140:** Skew extremo (pánico institucional)
- **140+:** Histórico (solo en crisis)

**Ejemplos reales:**
- **Feb 2020 (pre-COVID crash):** SKEW llegó a 145
- **Oct 2008 (Lehman):** SKEW en 152
- **Diciembre 2024:** SKEW ~120-125 (normal-alto)
- **Febrero 2026 (según el chart):** SKEW en percentil 95% (muy alto)

---

## **🧠 ¿POR QUÉ EXISTE EL SKEW?**

### **Teoría: La Volatility Smile**

En un mundo **teórico** (Black-Scholes), todas las opciones del mismo vencimiento deberían tener la **misma IV**.

**Realidad:** La IV forma una **sonrisa** (smile) o **sesgo** (skew):

```
       IV
        │
   High │     ╱╲  (Smile simétrico - raro)
        │    ╱  ╲
        │   ╱    ╲
        │  ╱      ╲
        │ ╱        ╲
        └─────────────── Strike
       OTM   ATM   OTM
       Put        Call

       IV
        │
   High │  ╱
        │ ╱
        │╱   ╲    (Skew típico de índices)
        │      ╲
        │       ╲
        └─────────────── Strike
       OTM   ATM   OTM
       Put        Call
```

---

### **¿Por qué los puts OTM son más caros?**

#### **1. Crash de 1987 - El trauma del mercado**
- **Antes de Oct-1987:** La volatility smile era simétrica
- **19 de Octubre 1987:** S&P 500 cae **-20% en un día**
- **Después:** Los inversores institucionales aprendieron que los crashes son:
  - Más frecuentes de lo que predice distribución normal
  - Más severos (fat tails)
  - Inesperados

**Resultado:** Desde 1987, **siempre** hay demanda estructural de puts OTM para protección.

---

#### **2. Asimetría psicológica**

**Subidas:**
- Graduales (el mercado sube por escalera)
- Esperadas (bull markets largos)
- Menos volátiles

**Caídas:**
- Rápidas (el mercado baja por ascensor)
- Inesperadas (pánico súbito)
- Muy volátiles (VIX spikes)

**Ejemplo real - COVID Crash (Feb-Mar 2020):**
- **Subida 2019:** S&P +28% en 12 meses (gradual)
- **Caída Feb-Mar 2020:** S&P -34% en 23 días (catastrófico)

---

#### **3. Estructura del mercado**

**Quién compra puts:**
- Fondos de pensiones (protección obligatoria)
- Mutual funds (hedging regulatorio)
- Hedge funds (tail risk hedging)
- Instituciones (portfolio insurance)

**Quién compra calls:**
- Retail especulativo (menos capital)
- Market makers (delta hedging)

**Demanda estructural de puts > demanda de calls** → Skew permanente

---

## **📊 ANÁLISIS DEL CHART DE MENTHOR Q**

### **Estructura del Chart**

#### **Panel Superior: Precio + Bandas de Skew**

```
Elementos:
1. Candlestick chart de SPX (precio)
2. Línea blanca: 25D Risk Reversal SKEW
3. Línea amarilla: Average 30D SKEW
4. Línea verde: Min 30D SKEW
5. Línea roja: Max 30D SKEW
```

**25-Delta Risk Reversal:**
- Es la diferencia de IV entre un **25-delta put** y un **25-delta call**
- Delta 25 = ~20-25% OTM aproximadamente
- Es el estándar de la industria para medir skew

**Fórmula:**
```
25D RR = IV(25Δ Put) - IV(25Δ Call)
```

---

#### **Panel Inferior: SKEW a lo largo del tiempo**

```
Zonas:
- ROJA (PUT BIAS): Skew > promedio → Demanda de puts alta
- VERDE (CALL BIAS): Skew < promedio → Demanda de calls alta
- AMARILLO: Zona de transición
```

**Línea blanca:** 25D Risk Reversal actual
**Área sombreada:** Magnitud del skew (cuanto más rojo/verde, más extremo)

---

### **Interpretación del Chart (Feb 11, 2026)**

**Observaciones del hilo:**

#### **1. Skew en percentil 95.16%**

```
Significado:
- El skew actual es más alto que el 95.16% de las lecturas de los últimos 3 meses
- Solo en ~5% de los días recientes hubo más demanda de puts
- Esto es EXTREMO
```

**Cálculo de percentil:**
```python
import numpy as np

skew_history = [5.2, 6.1, 5.8, ..., 15.3]  # últimos 90 días
current_skew = 15.3

percentile = (np.sum(skew_history < current_skew) / len(skew_history)) * 100
# Result: 95.16%
```

---

#### **2. Divergencia: Precio Alto + Hedging Alto**

```
PRECIO (SPX):
- Trading cerca de all-time highs
- Candelas verdes dominantes
- Sin crash aparente

SKEW:
- En zona PUT BIAS profunda
- Instituciones comprando protección agresivamente
- Expectativa de volatilidad
```

**¿Qué significa esto?**

**Escenario A - Contrarian Bullish:**
> "Cuando todos están hedgeados, no queda nadie para vender"

- Si el mercado NO cae, todos los puts expiran sin valor
- Los hedgers tienen que "unwind" (cerrar posiciones)
- Eso genera **buying pressure** (dealers compran acciones de vuelta)
- Posible rally de relief

**Ejemplo real - Agosto 2024:**
- VIX spike a 65 (crisis de Carry Trade de Japón)
- Todo el mundo compró puts de pánico
- S&P 500 recuperó todo en 2 semanas
- Los que compraron puts perdieron 100% de la prima

---

**Escenario B - Bearish Confirmado:**
> "Los institucionales saben algo que nosotros no"

- Fondos grandes tienen info privilegiada (no ilegal, solo mejor research)
- Si compran protección masiva, es porque esperan caída
- El skew alto precede crashes reales

**Ejemplo real - Enero 2020:**
- Skew empezó a subir en Enero (pre-COVID público)
- Instituciones sabían algo (cadenas de suministro, China lockdown)
- En Febrero explotó el crash

---

#### **3. Spike de Skew el 27 de Enero**

En el chart, hay un **pico masivo** de skew ~60% en la línea blanca.

**¿Qué pasó probablemente?**

**Posibles causas:**
1. **Evento geopolítico** (guerra, ataque, crisis bancaria)
2. **Datos macro muy malos** (NFP terrible, inflación alta)
3. **Crash flash** (caída intraday que recuperó)
4. **VIX spike** (correlacionado con skew)

**Reacción del mercado:**
- Después del spike, el skew se mantiene elevado pero no vuelve a pico
- Precio se recupera (velas verdes después)
- **Interpretación:** Falsa alarma, pero dejó nerviosismo

---

## **🔥 CASOS DE ESTUDIO REALES**

### **Caso 1: Crash de COVID (Febrero-Marzo 2020)**

#### **Timeline:**

**20 de Febrero 2020:**
- SPX: 3,386 (ATH)
- VIX: 14 (complacencia)
- **SKEW: 130** (empezando a subir) ← Primera señal

**28 de Febrero 2020:**
- SPX: 2,954 (-12.8% en 1 semana)
- VIX: 40 (pánico)
- **SKEW: 145** (extremo histórico)

**23 de Marzo 2020 (Bottom):**
- SPX: 2,237 (-34% desde ATH)
- VIX: 82 (récord post-2008)
- **SKEW: 152** (solo visto en 2008)

**Lección:**
> El skew subió ANTES del crash visible. Los institucionales estaban comprando protección cuando el VIX estaba tranquilo.

**Divergencia:**
- 15-Feb: SPX en ATH, SKEW empezando a subir
- 20-Feb: SPX aún cerca de ATH, SKEW en 130
- 24-Feb: Primer -3% day, SKEW explota

**Si hubieras monitoreado skew:**
- Señal de alerta el 15-Feb (skew subiendo sin razón)
- Hedge comprado el 20-Feb (skew >130)
- Salvado del crash

---

### **Caso 2: August 2024 VIX Spike (Carry Trade Unwind)**

#### **Timeline:**

**30 de Julio 2024:**
- SPX: 5,522
- VIX: 16
- **SKEW: 118** (normal)

**5 de Agosto 2024 (Black Monday asiático):**
- Nikkei: -12.4% (peor día desde 1987)
- SPX futures: -6% premarket
- VIX: **65** (spike histórico)
- **SKEW: 140+** (todos comprando puts de pánico)

**Causa:** Bank of Japan subió tasas → Carry Trade unwind → margin calls globales

**9 de Agosto 2024:**
- SPX: 5,344 (-3.2% desde peak)
- VIX: 23 (normalizado)
- **SKEW: 125** (bajando rápido)

**23 de Agosto 2024:**
- SPX: 5,634 (nuevo ATH, +2% sobre pre-crisis)
- VIX: 15
- **SKEW: 115** (normal)

**Lección:**
> Skew extremo por pánico = contrarian signal. Si compras puts en pánico (skew 140), pierdes. El mejor trade era vender puts caros.

**¿Por qué?**
- Cuando el miedo es **máximo**, la demanda de puts está **saturada**
- No queda nadie más para vender (ya todos hedgearon)
- Los puts están **sobrevalorados** (IV inflada)
- Mejor estrategia: sell premium (cash-secured puts, spreads)

---

### **Caso 3: Taper Tantrum (Mayo 2013)**

#### **Timeline:**

**1 de Mayo 2013:**
- SPX: 1,582
- VIX: 13
- **SKEW: 115**

**22 de Mayo 2013 (Bernanke speech):**
- Fed anuncia "taper" del QE
- Bonds crash (-100bps en días)
- **SKEW salta a 135**

**24 de Junio 2013:**
- SPX: 1,573 (-5% desde peak)
- VIX: 20
- **SKEW: 138** (instituciones comprando protección)

**Resultado:**
- Mercado se recuperó en 2 meses
- Los hedges expiraron sin valor
- Fue una **corrección sana**, no un crash

**Lección:**
> Skew alto + corrección leve = oportunidad de compra. Si el mercado solo cae 5-10% con skew extremo, es probable que rebote.

---

## **📉 RELACIÓN ENTRE SKEW, VIX Y MERCADO**

### **Matriz de Escenarios**

| SPX | VIX | SKEW | Interpretación | Acción |
|-----|-----|------|----------------|--------|
| ↑ ATH | Bajo (12-15) | Bajo (110-115) | **Complacencia** | Precaución, comprar hedges baratos |
| ↑ ATH | Bajo (12-15) | **Alto (130+)** | **Divergencia preocupante** | Reducir exposición, institucionales saben algo |
| ↓ -5% | Medio (18-25) | **Alto (135+)** | **Corrección sana** | Oportunidad de compra, oversold |
| ↓ -10%+ | **Alto (30+)** | **Extremo (140+)** | **Pánico máximo** | Contrarian buy, vender puts caros |
| → Lateral | Bajo (14-17) | Normal (118-122) | **Mercado sano** | Operar normal, sell premium |

---

### **Ejemplo Numérico: SPX Hoy (11-Feb-2026)**

**Datos del chart:**
- **Precio:** ~6,900 (cerca de ATH)
- **VIX:** ~16-18 (no mostrado pero asumible por precio)
- **SKEW:** Percentil 95% → ~135-138 estimado

**Análisis:**

```
✓ SPX en highs
✓ VIX relativamente bajo
✗ SKEW en percentil 95 (muy alto)

→ DIVERGENCIA CLÁSICA
```

**Interpretación (dos visiones):**

**Bull case:**
> "Todo el mundo está hedgeado, el muro de preocupación sigue escalándose"
> - Si no pasa nada malo, los puts expiran → dealers compran acciones → rally
> - Exceso de pessimismo = fuel para subida

**Bear case:**
> "Los institucionales no compran protección cara por nada"
> - Hedge funds grandes tienen mejor info
> - Skew 95th percentile sin evento visible = red flag
> - Posible corrección 5-15% en 1-2 meses

**Trade práctico:**
1. **Si eres bullish:** Vender put spreads (aprovechar IV inflada)
2. **Si eres bearish:** Comprar call spreads (más barato que calls directos)
3. **Si estás neutral:** Wait and see, tener cash para comprar dips

---

## **🛠️ CÓMO USAR SKEW EN TU TRADING**

### **Regla 1: Skew como Indicador de Sentimiento**

**Skew NO predice dirección, predice EXPECTATIVA**

```
SKEW Alto → Mercado espera movimiento brusco a la baja
SKEW Bajo → Mercado espera rally o lateralización
```

**Uso práctico:**
- Si skew >130 y precio lateral → espera volatilidad
- Si skew <110 y precio rally → complacencia, comprar hedges

---

### **Regla 2: Skew para Timing de Opciones**

**Cuándo COMPRAR opciones:**
- Skew bajo (<115)
- Puts baratos
- VIX bajo
- **Momento ideal para hedging barato**

**Cuándo VENDER opciones:**
- Skew alto (>130)
- Puts caros
- VIX alto
- **Momento ideal para sell premium**

**Ejemplo real - tu situación hoy:**

Si SKEW está en percentil 95:
```python
# Estrategia: VENDER put spreads (bull put spread)

SPX = 6900

# Vender: 6800 put (30 días, delta -25)
# Comprar: 6750 put (30 días, delta -15)

# Crédito recibido: ~$15-20 por spread ($1,500-2,000 por contrato)
# Riesgo máximo: $50 (diferencia de strikes)
# Break-even: ~6785

# ¿Por qué funciona?
# - Los puts están INFLADOS por skew alto
# - Vendes volatilidad cara
# - Si SPX se mantiene >6800, ganas el crédito completo
```

---

### **Regla 3: Divergencias Skew-Precio**

**Divergencia Alcista (Bullish):**
```
Precio: ↓ cayendo
SKEW: ↓ bajando también
VIX: ↓ bajando

→ Corrección ordenada, no pánico
→ Oportunidad de compra
```

**Divergencia Bajista (Bearish):**
```
Precio: ↑ subiendo
SKEW: ↑ subiendo
VIX: → lateral o subiendo

→ Rally sobre hedging pesado
→ Institucionales no confían
→ Precaución
```

**Situación actual (según chart):**
```
Precio: → lateral alto
SKEW: ↑↑ extremo (95th percentile)
VIX: → (asumible ~16-18)

→ Divergencia BEARISH clásica
→ Precaución, reducir exposición o comprar hedges
```

---

## **📈 IMPLEMENTACIÓN EN TU APP**

### **Nivel 1: SKEW Básico (YA TIENES)**

```python
# webapp/app.py - líneas 3065-3070
otm_puts = puts[puts['strike'] < price * 0.95]
otm_calls = calls[calls['strike'] > price * 1.05]
put_iv_avg = float(otm_puts['impliedVolatility'].mean() * 100)
call_iv_avg = float(otm_calls['impliedVolatility'].mean() * 100)
skew = put_iv_avg - call_iv_avg
```

**Mejora sugerida:**
```python
# Usar 25-delta en vez de % fijo
# Más preciso, estándar de industria
```

---

### **Nivel 2: 25-Delta Risk Reversal (MEDIO)**

**Qué necesitas:**
1. Calcular delta de cada opción (necesitas Black-Scholes)
2. Encontrar el strike con delta más cercano a 0.25 (calls) y -0.25 (puts)
3. Comparar sus IVs

**Complejidad:** Media (requiere calcular delta manualmente)

**Código aproximado:**
```python
from scipy.stats import norm
import numpy as np

def black_scholes_delta(S, K, T, r, sigma, option_type='call'):
    """
    S: Precio actual
    K: Strike
    T: Time to expiration (años)
    r: Tasa libre de riesgo
    sigma: Implied volatility
    """
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))

    if option_type == 'call':
        delta = norm.cdf(d1)
    else:
        delta = -norm.cdf(-d1)

    return delta

# Encontrar 25-delta strikes
target_delta_call = 0.25
target_delta_put = -0.25

# Buscar en tus dataframes de opciones
best_call_25d = None
best_put_25d = None
min_call_diff = float('inf')
min_put_diff = float('inf')

for _, row in calls.iterrows():
    K = row['strike']
    sigma = row['impliedVolatility']
    T = dte / 365

    delta = black_scholes_delta(price, K, T, 0.05, sigma, 'call')
    diff = abs(delta - target_delta_call)

    if diff < min_call_diff:
        min_call_diff = diff
        best_call_25d = row

for _, row in puts.iterrows():
    K = row['strike']
    sigma = row['impliedVolatility']
    T = dte / 365

    delta = black_scholes_delta(price, K, T, 0.05, sigma, 'put')
    diff = abs(delta - target_delta_put)

    if diff < min_put_diff:
        min_put_diff = diff
        best_put_25d = row

# Risk Reversal
rr_25d = (best_put_25d['impliedVolatility'] - best_call_25d['impliedVolatility']) * 100
```

---

### **Nivel 3: SKEW Historical Chart (COMPLEJO)**

**Qué necesitas:**
1. Guardar datos diarios de skew en base de datos
2. Calcular percentiles móviles
3. Crear visualización con zonas PUT BIAS / CALL BIAS
4. Overlay con precio

**Complejidad:** Alta (requiere persistencia de datos y cálculos históricos)

**Estructura de datos:**
```python
# Nueva tabla en SQLite
CREATE TABLE skew_history (
    date DATE PRIMARY KEY,
    ticker TEXT,
    skew_25d REAL,
    avg_30d REAL,
    min_30d REAL,
    max_30d REAL,
    percentile_90d REAL,
    price REAL,
    vix REAL
);
```

**Proceso diario:**
1. Calcular 25D RR para SPX
2. Calcular stats móviles (avg 30d, min/max 30d)
3. Calcular percentil sobre últimos 90 días
4. Guardar en DB
5. Plotear con Plotly (similar al chart de MenthorQ)

---

## **🎓 QUIZ DE AUTOEVALUACIÓN**

### **Pregunta 1:**
SPX está en 7,000 (ATH). VIX = 14. SKEW = 135 (percentil 90).

**¿Qué haces?**

A) Comprar calls (rally continúa)
B) Comprar puts (crash inminente)
C) Reducir exposición y vender put spreads
D) All-in YOLO calls 0DTE

**Respuesta correcta:** **C**
- SKEW alto = puts caros = vender premium
- Divergencia precio/skew = precaución (reducir exposición)
- Si eres bullish, vender put spreads aprovecha IV inflada

---

### **Pregunta 2:**
Mercado cae -8% en 3 días. VIX salta a 35. SKEW = 142 (extremo).

**¿Qué significa?**

A) Crash catastrófico viene, vender todo
B) Pánico máximo, posible bottom near
C) Comprar más puts para protección
D) Cerrar eyes y hold

**Respuesta correcta:** **B**
- SKEW 142 = everyone hedged
- VIX 35 = peak fear
- Histórico: estos niveles marcan bottoms (Aug 2024, Mar 2020)
- Contrarian: vender puts caros o comprar dips

---

### **Pregunta 3:**
SKEW ha estado en 115 (normal) por 2 meses. De repente salta a 128 en 2 días sin caída de precio visible.

**¿Qué hacen los institucionales?**

A) Están comprando calls especulativos
B) Están comprando protección (esperan caída)
C) Están vendiendo puts
D) Nothing, es ruido

**Respuesta correcta:** **B**
- SKEW sube sin evento = alguien sabe algo
- Institucionales compran protección antes de eventos
- Ejemplo: Enero 2020 pre-COVID

---

## **📚 CHECKLIST DE CONCEPTOS APRENDIDOS**

✅ **Fundamentos:**
- [ ] Entiendo qué es el SKEW (diferencia IV puts vs calls OTM)
- [ ] Sé la diferencia entre simple IV skew y 25D Risk Reversal
- [ ] Conozco el rango normal de SKEW (110-120) y extremos (135+)

✅ **Historia:**
- [ ] Sé por qué existe el skew (Crash 1987)
- [ ] Entiendo la demanda estructural de puts (institucionales)
- [ ] Conozco casos históricos (COVID, Aug 2024, Taper Tantrum)

✅ **Interpretación:**
- [ ] Puedo interpretar divergencias precio-skew
- [ ] Entiendo skew como sentimiento, no dirección
- [ ] Sé cuándo skew alto es bearish vs contrarian bullish

✅ **Trading:**
- [ ] Sé cuándo comprar opciones (skew bajo)
- [ ] Sé cuándo vender opciones (skew alto)
- [ ] Puedo usar skew para timing de hedges

✅ **Implementación:**
- [ ] Tengo skew básico en mi app
- [ ] (Opcional) Implementé 25D Risk Reversal
- [ ] (Opcional) Tengo tracking histórico con percentiles

---

## **🔗 RECURSOS ADICIONALES**

### **Papers académicos:**
1. **"The Volatility Smile and Its Implied Tree"** - Derman & Kani (1994)
2. **"Recovering Risk Aversion from Option Prices"** - Jackwerth (2000)
3. **"What Does Individual Option Volatility Smirk Tell Us About Future Equity Returns?"** - Xing, Zhang & Zhao (2010)

### **Herramientas:**
- **CBOE SKEW Index:** https://www.cboe.com/tradable_products/vix/
- **SqueezeMetrics (DIX/GEX):** https://squeezemetrics.com
- **SpotGamma HIRO:** https://spotgamma.com

### **Cuentas de Twitter/X:**
- @MenthorQpro (tu referencia)
- @SqueezeMetrics (DIX, dark pool)
- @spotgamma (gamma levels)
- @MikeZaccardi (vol trading education)

---

## **📝 PRÓXIMOS PASOS**

1. **Lee este documento completo** (30-45 min)
2. **Revisa los casos de estudio** y busca los charts reales en TradingView
3. **Monitorea el CBOE SKEW Index** diariamente por 1 mes
4. **Compara tu skew básico en la app** con el CBOE oficial
5. **Paper trade** estrategias basadas en skew (sell put spreads en skew alto)
6. **Implementa 25D RR** en tu app (ejercicio de código)

---

## **✨ RESUMEN EJECUTIVO**

**SKEW en una frase:**
> "Mide cuánto más caros están los puts que los calls, revelando si los institucionales están comprando protección (miedo) o especulando (euforia)"

**Situación actual (Feb 11, 2026):**
- SKEW en percentil 95 = institucionales comprando protección agresivamente
- Precio en highs = divergencia preocupante
- VIX relativamente bajo = complacencia retail vs institucionales preparados

**Acción recomendada:**
1. Reducir exposición (trailing stops más tight)
2. Si tienes convicción bull: vender put spreads (aprovechar IV alta)
3. Si estás neutral: cash, esperar confirmación
4. Si estás bear: comprar call spreads (más barato que calls directos por skew)

**Monitorear:**
- Si SKEW baja rápido sin caída de precio → all clear, institucionales unwinding hedges
- Si SKEW se mantiene alto y precio empieza a caer → validación del miedo, esperar más caída

---

**FIN DEL DOCUMENTO**

*Última actualización: 14 de Febrero de 2026*
*Basado en el análisis de MenthorQ sobre SPX 1-Month SKEW*
