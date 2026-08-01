# Investigación de Viralidad Real 2026: Algoritmos, Hooks y Métricas

Documento maestro de investigación de tendencias, patrones de retención de micro-segundos, psicología de consumo y clasificación de audios/efectos de sonido para la creación del **Sistema Profesional de Guiones Virales**.

---

## 📊 1. El Estándar de Retención Algorítmica 2026 (TikTok, Reels, Shorts)

En 2026, los algoritmos de TikTok e Instagram han dejado atrás el modelo de "entretenimiento pasivo" para adoptar el modelo de **Shoppertainment & Micro-Retención**:

### Umbrales Críticos de Algoritmo:
1. **La Barrera del 1.5s (Micro-Retention)**:
   - El algoritmo mide el descarte inmediato en el primer segundo. El **70% o más de los espectadores** deben permanecer en pantalla pasados los primeros 1.5 segundos para que el video califique al primer anillo de distribución (1.000 a 5.000 impresiones).
2. **El Factor RUM (Relevancia Universal de Mercado)**:
   $$\text{RUM} = U \text{ (Universalidad)} \times I \text{ (Intensidad)} \times C \text{ (Claridad)} \times S \text{ (Shareability)} \text{ por DM} \times D \text{ (Distribución)} \times A \text{ (Alineación con Oferta)}$$
   - **Shares por DM**: Es el indicador #1 de distribución viral. Si la gente lo envía a amigos ("mira esto"), el video salta del anillo de 10k al de 100k views.
3. **Completion Rate vs. Drop-off Rate**:
   - En videos de 30 a 45 segundos, un **Completion Rate > 35%** es el requisito indispensable para superar las 100.000 reproducciones.

---

## 🎯 2. Las 5 Familias de Hooks Virales Comprobados (Data 2026)

### A. Hook de "Contraste & Resultado" (Ideal para producto/demostración)
- **Mecanismo Psicológico**: Muestra la transformación o el beneficio inmediato en el primer cuadro.
- **Ejemplo DeviceShop**: *"La razón por la que dejé de leer en el celular después de 5 años por este e-reader."*
- **Ejemplo LAM**: *"Cómo pasé de no poder concentrarme 2 minutos a rezar con paz total cada mañana."*

### B. Hook de "Anti-Sell / Desafío a la Creencia" (Alta retención)
- **Mecanismo Psicológico**: Decir lo contrario a lo que la industria espera genera un quiebre de expectativa.
- **Ejemplo DeviceShop**: *"Vendo Kindles y no te vendo el modelo más caro. Te explico por qué."*
- **Ejemplo LAM**: *"No necesitas rezar 3 horas para estar cerca de Dios. De hecho, eso te está alejando."*

### C. Hook de "Identidad y Comunidad" (Segmentación activa)
- **Mecanismo Psicológico**: Apela directamente al tipo de persona que consume el contenido.
- **Ejemplo DeviceShop**: *"Si eres de los que ama leer de noche pero odia amanecer con los ojos ardiendo, mira esto."*
- **Ejemplo LAM**: *"Esto es para cualquiera que siente que su oración se volvió una rutina sin sentido."*

### D. Hook de "Advertencia / Evitación de Error" (Miedo a perder / FOMO)
- **Mecanismo Psicológico**: La aversión a la pérdida activa el cerebro 2.5x más rápido que el beneficio.
- **Ejemplo DeviceShop**: *"No compres un e-reader sin antes ver este error que comete el 90% de la gente."*
- **Ejemplo LAM**: *"No cometas este error al intentar rezar cuando tienes la mente cansada."*

### E. Hook de "Open Loop / Curiosidad Resuelta al Final"
- **Mecanismo Psicológico**: Presenta un dilema o incógnita que solo se resuelve en los últimos 5 segundos del video, garantizando la retención completa.
- **Ejemplo DeviceShop**: *"Casi devuelvo mi Kindle el primer día, hasta que descubrí esta función oculta..."*
- **Ejemplo LAM**: *"Ojalá alguien me hubiera explicado esto sobre el silencio antes de mis 20 años..."*

---

## 🎬 3. Mapeo Físico de Filmación y Edición

Para garantizar que el guion resultante no sea una simple plantilla de texto sino una **guía de producción minuciosa**:

| Etapa | Elemento | Regla de Oro en Producción |
|---|---|---|
| **Filmación** | **Plano Inicial (0-3s)** | Arrancar SIEMPRE con movimiento irrumpiendo a cámara o gesto físico (no estático). |
| **Filmación** | **PPM (Palabras Por Minuto)** | Ritmo de 140-160 PPM con pausas marcadas (`// pausá //`) para evitar vacilaciones. |
| **Filmación** | **Props (Utilería)** | Mínimo 2 objetos de contraste visible (ej. Celular encendido vs E-reader / Biblia vs Notificación). |
| **Edición** | **Cortes de Escena (CPM)** | Cambio de plano cada 1.5s - 2.5s (25 a 35 cortes por minuto). |
| **Edición** | **Zona Segura de Texto** | Texto siempre en la franja superior (10% - 35% del alto) para evitar botones de TikTok/Reels. |
| **Edición** | **Punch-ins** | Zoom digital (+12%) en las palabras de impacto de cada párrafo. |

---

## 🎵 4. Clasificación Minuciosa de SFX y Música

El audio se clasifica por su función en la estructura de tensión del video:

```
[0-3s HOOK] ──► SFX Golpe Fuerte (impacto_grave / impacto_latido) + Inicia Música Mood
[3-15s CONFLICTO] ──► SFX Corte (transicion_corte / whoosh_deep) + Punch-ins (pop / ui_blip)
[15-30s SOLUCIÓN] ──► SFX Destello (whoosh_simple / camara_enfoque) + Música sube volumen
[30-40s CIERRE] ──► SFX Remate (tada_cierre) + Fade out de música
```

---

## 📌 5. Plan por Etapas para el Desarrollo del Sistema

- [x] **Etapa 1: Investigación de Data Real & Métricas Algorítmicas 2026** (`INVESTIGACION-VIRALIDAD-2026.md`)
- [ ] **Etapa 2: Estructuración Anatómica de las 5 Plantillas Virales en Python** (`editor/f14_viral_extractor.py` y `editor/f15_adaptador_rum.py`)
- [ ] **Etapa 3: Diseño de la Interfaz Web Profesional (`PANEL-VIRALES.html`)**
- [ ] **Etapa 4: Conexión y Pruebas con el Pipeline de Producción (`PANEL-PRODUCCION.html` & `editor.py`)**
