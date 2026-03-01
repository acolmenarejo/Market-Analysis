# 🎯 SKEW Analysis Implementation Guide

## **What's New**

Tu app ahora tiene **análisis avanzado de SKEW** usando el estándar de la industria: **25-Delta Risk Reversal**.

---

## **📍 Dónde Encontrarlo**

1. Ve a cualquier ticker (ej: SPY, AAPL, NVDA)
2. Click en la pestaña **"🔗 Options & Gamma"**
3. Verás una nueva sección después de las 5 cards: **"📊 Advanced SKEW Analysis"**

---

## **🎨 Componentes de la Visualización**

### **1. Main SKEW Value**
```
+15.30pp    🔴 EXTREME
```
- **Número grande**: 25-Delta Risk Reversal actual
- **Color**:
  - 🟢 Verde = SKEW bajo (puts baratos, buena oportunidad para hedge)
  - 🟡 Amarillo = SKEW normal (5-10pp es típico)
  - 🟠 Naranja = SKEW elevado (>10pp, institucionales comprando protección)
  - 🔴 Rojo = SKEW extremo (>15pp, pánico o miedo intenso)

### **2. Percentile Bar**
```
[========================================] 95.1%
0    25    50    75    90    100
```
- Muestra dónde está el SKEW actual vs últimos **90 días**
- **>90%** = Extremo (solo 10% de los días han tenido más SKEW)
- **75-90%** = Elevado
- **25-75%** = Normal
- **<25%** = Bajo (complacencia)

### **3. Interpretation Box**
```
🔵 INTERPRETATION
EXTREME PUT BIAS - Heavy institutional hedging
```
Interpretación automática basada en el nivel de SKEW:
- **EXTREME PUT BIAS** (>15pp): Institucionales comprando protección agresivamente
- **STRONG PUT BIAS** (10-15pp): Demanda elevada de puts
- **MODERATE PUT BIAS** (5-10pp): Normal para índices
- **SLIGHT PUT BIAS** (0-5pp): Mercado balanceado
- **CALL BIAS** (<0pp): Especulación alcista (raro, euforia)

### **4. Stats Grid**
```
Current    30D Avg    90D Range
+15.30pp   +8.20pp    4.1 to 18.7
```
- **Current**: SKEW actual
- **30D Avg**: Promedio últimos 30 días (contexto reciente)
- **90D Range**: Mínimo y máximo últimos 90 días (rango histórico)

### **5. 25Δ Strikes Info**
```
25Δ Put Strike: $580.00 (IV: 25.3%)
25Δ Call Strike: $620.00 (IV: 10.1%)
```
Muestra:
- Qué strikes específicos se usaron para el cálculo
- Sus IVs respectivas
- **Diferencia de IV = SKEW**

### **6. Trading Implications**
```
💡 TRADING IMPLICATIONS
High SKEW = Expensive Puts
• Sell put spreads to capture inflated premium
• Reduce long exposure or tighten stops
• Monitor for divergence resolution
```

Recomendaciones automáticas basadas en el percentil:
- **Percentil >75%**: Puts caros → vender premium
- **Percentil 25-75%**: Normal → operar normalmente
- **Percentil <25%**: Puts baratos → comprar protección

---

## **💡 Cómo Interpretarlo - Ejemplos Reales**

### **Ejemplo 1: SPY con SKEW Extremo**
```
25-Delta Risk Reversal: +16.50pp  🔴 EXTREME
Percentile: 97.3%
```

**Qué significa:**
- Los puts están **16.5% más caros** que los calls (en términos de IV)
- Esto es más alto que el **97.3%** de los últimos 90 días
- Institucionales están comprando protección masiva

**Contexto histórico (del documento):**
- **Feb 2020 (pre-COVID)**: SKEW subió a ~15pp antes del crash
- **Agosto 2024 (VIX spike)**: SKEW llegó a 18pp en pánico, luego rebotó

**Acción recomendada:**
1. **Si eres bajista**: Ya está muy hedgeado, quizás es tarde
2. **Si eres alcista**: Vender put spreads (aprovechar puts caros)
3. **Si estás neutral**: Esperar - puede ser contrarian signal (bottom near)

---

### **Ejemplo 2: AAPL con SKEW Normal**
```
25-Delta Risk Reversal: +6.20pp  🟡 NORMAL
Percentile: 52.1%
```

**Qué significa:**
- SKEW en rango normal para acciones individuales
- No hay miedo extremo ni euforia
- Mercado balanceado

**Acción recomendada:**
- Operar normalmente sin sesgos de volatilidad
- Strategies neutras funcionan bien (iron condors, strangles)

---

### **Ejemplo 3: TSLA con SKEW Bajo**
```
25-Delta Risk Reversal: +2.10pp  🟢 LOW
Percentile: 18.5%
```

**Qué significa:**
- Puts están baratos (poca demanda de protección)
- Mercado complacente
- **Buena oportunidad para comprar hedges baratos**

**Acción recomendada:**
- Comprar puts de protección (están baratos)
- Long premium strategies (comprar opciones)
- Precaución: complacencia puede preceder correcciones

---

## **🔬 Cómo Funciona Técnicamente**

### **1. Black-Scholes Delta Calculation**
```python
# Calcula delta de cada opción usando fórmula Black-Scholes
delta = norm.cdf(d1)  # Para calls
delta = -norm.cdf(-d1)  # Para puts
```

### **2. 25-Delta Strike Finding**
```python
# Busca el strike con delta más cercano a 0.25 (calls) y -0.25 (puts)
# 25-delta = ~20-25% OTM aproximadamente
```

### **3. Risk Reversal Calculation**
```
RR_25D = IV(25Δ Put) - IV(25Δ Call)
```

### **4. Historical Tracking**
- Guarda datos en `data/skew_history_{TICKER}.json`
- Mantiene últimos **90 días**
- Se actualiza automáticamente cada vez que visitas la pestaña de opciones

### **5. Percentile Calculation**
```python
percentile = (count of days with skew < current) / total days * 100
```

---

## **📊 Tracking Histórico**

Los datos se guardan automáticamente en:
```
d:\proyectos\Market Analysis\data\skew_history_SPY.json
```

Formato:
```json
[
  {
    "date": "2026-02-14",
    "skew": 15.30,
    "price": 583.50
  },
  ...
]
```

**Notas:**
- Máximo 90 días (se auto-limpia)
- Requiere al menos 10 días para calcular percentiles confiables
- Si es la primera vez, mostrará "BUILDING HISTORY"

---

## **🎓 Relación con el Hilo de MenthorQ**

El hilo que compartiste explica exactamente lo que implementamos:

### **Del Hilo:**
> "Skew measures the difference in demand between downside protection (puts) and upside speculation (calls)"

**En tu app:**
- ✅ Calculamos esa diferencia usando **25-delta** (estándar industria)
- ✅ Mostramos en **percentage points** (pp)

### **Del Hilo:**
> "Right now, skew is in the 95th percentile over the last 3 months"

**En tu app:**
- ✅ Mostramos el **percentile bar** sobre últimos 90 días
- ✅ Coloreamos por status (EXTREME, ELEVATED, NORMAL, LOW)

### **Del Hilo:**
> "When skew spikes like this, it usually means: institutions are buying protection"

**En tu app:**
- ✅ Interpretación automática: "EXTREME PUT BIAS - Heavy institutional hedging"
- ✅ Trading implications específicas

---

## **⚙️ Requisitos Técnicos**

### **Dependencias Nuevas:**
- `scipy>=1.11.0` (para `norm.cdf` en Black-Scholes)

Instalación:
```bash
pip install scipy>=1.11.0
```

O reinstalar todo:
```bash
pip install -r requirements.txt
```

### **Funciones Nuevas (providers.py):**
1. `black_scholes_delta()` - Calcula delta usando BS
2. `find_25delta_strikes()` - Encuentra strikes 25-delta
3. `calculate_25d_risk_reversal()` - Calcula RR y devuelve dict completo
4. `track_skew_history()` - Guarda histórico en JSON
5. `get_skew_percentile()` - Calcula stats y percentiles

---

## **🐛 Troubleshooting**

### **"Unable to calculate 25Δ Risk Reversal"**
**Causa:** No hay suficientes opciones con IVs válidas

**Solución:**
- Usa tickers más líquidos (SPY, QQQ, AAPL, NVDA, TSLA)
- Selecciona expiración con más OI (30-45 días típico)

---

### **"INSUFFICIENT DATA" o "BUILDING HISTORY"**
**Causa:** Menos de 10 días de datos históricos

**Solución:**
- Espera unos días (el tracking es automático)
- El percentile se calculará cuando haya ≥10 días de datos

---

### **"Could not calculate advanced SKEW"**
**Causa:** Falta scipy o error en cálculo

**Solución:**
```bash
pip install scipy
```

---

## **📈 Next Steps (Futuro)**

Para llegar al nivel del chart de MenthorQ completo, se necesitaría:

### **Fase 2 (Complejo - Requiere Opus):**
1. **Dual-panel chart** (precio arriba, skew abajo)
2. **Bandas históricas** (Avg 30D, Min 30D, Max 30D)
3. **Zonas coloreadas** (PUT BIAS en rojo, CALL BIAS en verde)
4. **Múltiples expirations** (1M, 2M, 3M simultáneos)
5. **Base de datos permanente** (SQLite en vez de JSON)

**Esto requeriría:**
- ~2-3 horas de desarrollo
- Base de datos SQL para datos históricos robustos
- Plotly subplots complejos
- Cron job o scheduler para actualización diaria

---

## **✅ Checklist de Uso**

Usa esto para validar que entiendes el análisis:

- [ ] Sé dónde encontrar el análisis de SKEW en la app
- [ ] Entiendo qué es el 25-Delta Risk Reversal
- [ ] Puedo interpretar el percentile bar
- [ ] Sé qué significa SKEW >90th percentile (extremo, institucionales hedgeando)
- [ ] Sé qué significa SKEW <25th percentile (complacencia, hedges baratos)
- [ ] Entiendo las trading implications (vender premium cuando alto, comprar cuando bajo)
- [ ] Puedo relacionar esto con casos históricos (COVID crash, Aug 2024)
- [ ] Sé que SKEW no predice dirección, solo muestra posicionamiento

---

## **🎯 Resumen Ejecutivo**

**Antes:**
- SKEW básico (diferencia IV de puts/calls OTM a % fijo)
- Sin contexto histórico
- Sin percentiles

**Ahora:**
- ✅ **25-Delta Risk Reversal** (estándar industria)
- ✅ **Tracking histórico** (últimos 90 días)
- ✅ **Percentiles** (sabes si es extremo o normal)
- ✅ **Interpretación automática** (qué significa)
- ✅ **Trading implications** (qué hacer)
- ✅ **Visualización profesional** (estilo MenthorQ)

**Valor añadido:**
- Detectar cuando institucionales están hedgeando agresivamente
- Identificar oportunidades de vender premium (SKEW alto = puts caros)
- Saber cuándo comprar protección barata (SKEW bajo)
- Evitar comprar puts en pánico (SKEW extremo = contrarian signal)

---

**Siguiente paso:**
1. Lee el documento completo [`SKEW_GUIDE.md`](./SKEW_GUIDE.md)
2. Abre tu app y ve a SPY → Options & Gamma
3. Revisa el SKEW actual y compáralo con el mercado
4. Monitorea diariamente por 1 semana para ver cómo cambia

¡Ahora eres parte del 5% de traders que entienden SKEW profundamente! 🚀
