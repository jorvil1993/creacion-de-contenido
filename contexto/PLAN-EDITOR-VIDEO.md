# EDITOR DE VIDEO VIRAL — DeviceShop Bolivia

**Documento maestro de especificación y ejecución.**
Redactado por Opus 5 · Para ejecución fase por fase.
Fecha: 2026-07-26

---

## 0. INSTRUCCIONES PARA EL AGENTE EJECUTOR

Lee esta sección antes de tocar nada.

1. **Este documento es la fuente de verdad.** Las decisiones de la sección 8 ya están cerradas — no las vuelvas a discutir con el usuario ni propongas alternativas salvo que algo falle técnicamente.
2. **Ejecuta una fase a la vez.** Cada fase tiene un criterio de aceptación explícito. No avances a la siguiente hasta que el usuario confirme que el resultado le gusta.
3. **Verifica, no asumas.** Antes de usar cualquier parámetro de librería, confirma que existe en la versión instalada. Las versiones de este documento fueron verificadas el 2026-07-26 y pueden haber cambiado.
4. **Todo corre local y gratis.** Si una solución requiere API key de pago, no es la solución. La única excepción autorizada sería que el usuario lo pida explícitamente.
5. **El usuario no es programador.** Explica en español, sin jerga innecesaria. Los errores tradúcelos a lenguaje claro y propón la solución, no le pases el stack trace crudo.
6. **Calibra con material real.** Las listas de muletillas, umbrales de silencio y tiempos de zoom son puntos de partida. Se ajustan viendo el resultado en video real de José, no en teoría.

---

## 1. OBJETIVO

Construir un sistema **100% local y gratuito** que convierta una grabación cruda de José hablando a cámara (60–90 segundos, con errores, pausas y muletillas) en un **video vertical de 30–40 segundos optimizado para retención** en TikTok, Reels y Shorts.

Al final, todo se empaqueta en un **skill reutilizable** para que cada video nuevo sea un solo comando.

**Métrica de éxito del sistema:** que un video producido por el pipeline alcance >70% de tasa de completación.

---

## 2. CONTEXTO DEL NEGOCIO

| Dato | Valor |
|---|---|
| Empresa | DeviceShop Bolivia |
| Productos | Kindle (Basic, Paperwhite, Colorsoft, Scribe), Kobo |
| Presentador | José (principal). Su esposa se sumará después — el sistema debe soportar 2 presentadores distintos |
| Idioma | Español boliviano |
| Redes | TikTok `@deviceshopbo` (confirmado en el video de referencia) |
| Canal de venta | WhatsApp · pago por QR contra entrega · envíos nacionales |

| Micrófono | **DJI Mic Mini** (inalámbrico de solapa) — audio limpio y cercano |
| Paleta | Navy `#0A2A3E` · Cian `#4FD1D9` · Blanco — ver sección 5.3 |
| Primer video de prueba | **Kindle Paperwhite** |

| WhatsApp | **69214437** — confirmado por José el 2026-07-26. Es el real |
| Logos | `contexto/LOGOS IVAN/` — incluye `Deviceshop Bo Logo.ai` (vectorial), `deviceshop blanco.png`, `deviceshop color.png` |

---

## 3. ESTADO VERIFICADO DEL ENTORNO

Verificado el 2026-07-26 en la máquina de José.

| Componente | Estado | Detalle |
|---|---|---|
| GPU | ✅ | NVIDIA RTX 5070 Ti · 16303 MiB · driver 610.47 · arquitectura Blackwell (sm_120) |
| Node.js | ✅ | v24.18.0 (Hyperframes requiere 22+) |
| npm | ✅ | 11.16.0 |
| Git | ✅ | Instalado |
| Python | ⚠️ | **Solo 3.14.6** — PyTorch no lo soporta. Hay que instalar 3.12 en paralelo |
| ffmpeg | ⚠️ | Solo el binario embebido de `imageio-ffmpeg` v7.1. Falta instalación real en PATH |
| Directorio de trabajo | ✅ | `C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido` |

### ⚠️ RIESGO CRÍTICO: OneDrive

El directorio del proyecto está **dentro de OneDrive**. Los modelos de IA pesan 30–40 GB y **no deben sincronizarse a la nube** — saturaría la cuenta y ralentizaría todo.

**Regla obligatoria:** todos los modelos, entornos virtuales y caches van **fuera de OneDrive**, en:

```
C:\ai-video\
├── venv312\          ← entorno Python 3.12
├── models\           ← WhisperX, Flux, WAN
└── comfyui\
```

El proyecto en OneDrive guarda **solo** código, configuración, guiones y videos finales.

---

## 4. REGLAS DURAS DE RETENCIÓN (investigación de mercado)

Estas reglas salen de investigar qué hacen los videos cortos con millones de vistas en 2026. **Son requisitos del sistema, no sugerencias estéticas.**

### 4.1 Duración
- **Target: 30–40 segundos.** Nunca 60.
- Justificación: el algoritmo exige **>70% de completación** para viralizar (era 50% en 2024). Un video de 30s visto al 80% supera a uno de 60s visto al 40%.

### 4.2 Los primeros 3 segundos
- Retención >70% a los 3 segundos = **5x más probable de viralizar**.
- El texto del hook: **máximo 7 palabras**, legible en <1.5s.
- El hook pesa más que el número de seguidores.

### 4.3 Cadencia visual
- **Cambio visual cada 2–3 segundos.**
- **Regla de los 5 segundos:** ningún bloque de 5s sin corte, zoom, texto nuevo o SFX. Si existe, el sistema debe rellenarlo.
- Un video de 35s necesita **~14 momentos visuales distintos** (ver sección 6.1, presupuesto visual).

### 4.4 Técnicas de mayor impacto
Ordenadas por efectividad medida:
1. **Zoom súbito / punch-in** — +68% engagement. Es *la* técnica #1 en talking-head vertical.
2. **Zoom progresivo lento** hacia el presentador durante todo el plano.
3. **Texto animado** — refuerza mensaje y aumenta compartidos.
4. **Jump cuts** — eliminan aire muerto, suben la densidad de información.

### 4.5 Señales del algoritmo
- **Rewatch / loop es el cheat code.** >15–20% de rewatch = señal fuerte. El cierre del video debe empatar visual y narrativamente con el inicio.
- **Compartidos por DM pesan ~3x más que los likes.** El contenido debe dar ganas de reenviarlo.
- **Audio original tiene boost** sobre sonidos de tendencia. Usar la voz de José como audio principal, no trends.

### 4.6 Estructura narrativa
```
0–3s    HOOK          Gancho + texto ≤7 palabras
3–5s    PROMESA       Qué va a obtener el espectador
5–28s   CONTENIDO     Demostración, beneficios, prueba
28–35s  CTA + LOOP    Llamado a la acción que empata con el hook
```

---

## 5. FICHA DE ESTILO

### 5.1 Lo que se toma del video de la agencia
Extraído por análisis frame a frame de `contexto/tiktok video deviceshop.mp4`.

**Subtítulos** (replicar exacto):
- Color: **blanco**
- Tipografía: sans-serif redondeada, **bold**
- Contorno: **negro**, sutil
- Posición: **tercio inferior, ~77% de la altura** (por encima de la UI de TikTok)
- Segmentación: **2 a 4 palabras** por bloque
- Capitalización: **tipo oración, NO mayúsculas** ← detalle importante, es su firma visual

**Insertos de producto (PiP):**
- Rectángulo con **esquinas redondeadas** y **borde blanco**
- Contenido: close-up de la pantalla del producto
- Posición: centro-inferior, sobre la toma principal

**Stickers:**
- Emojis animados (destellos ✨, envío 🚚, bandera 🇧🇴)
- Badge circular del logo en el cierre

**Audio:**
- Música de fondo **continua** (cero silencios reales en los 60s)
- Mezcla normalizada, limitada a 0.0 dB

**Look general:** natural y limpio. **Cero gráficos corporativos pesados.**

### 5.2 Lo que NO se copia de la agencia
Su video está bien producido pero **no está construido para retener**:

| Problema | Medido |
|---|---|
| Duración excesiva | 60s exactos |
| Casi sin cortes | **1 solo corte duro en todo el video** |
| Bloques muertos | ~55 segundos continuos sin cambio |
| Sin punch-ins | Ninguno |
| Sin diseño de loop | El final no empata con el inicio |

**Diagnóstico:** apostaron todo a la presentadora. Nosotros apostamos a la **edición**. José no es presentador profesional y no necesita serlo — la edición automática hace el trabajo pesado.

### 5.3 Paleta de marca y cómo usarla

**Colores confirmados por José:**

| Rol | Hex | Uso |
|---|---|---|
| Navy / Petróleo | `#0A2A3E` | Fondos de tarjetas, badges, banda de CTA |
| Cian / Turquesa | `#4FD1D9` | Acentos, palabra resaltada, bordes, íconos |
| Blanco | `#FFFFFF` | Texto principal sobre fondos oscuros |

**⚠️ REGLA CRÍTICA — no pintar el video con la marca.**

En formato corto, la legibilidad le gana a la identidad. Casi todos los creadores virales usan la misma fórmula de subtítulos por una razón: funciona sobre cualquier fondo.

- **Subtítulos: SIEMPRE blanco con contorno negro.** Nunca cian, nunca navy. El cian sobre un fondo claro (como el sofá crema del video de la agencia) se vuelve ilegible, y la legibilidad de los subtítulos es lo que sostiene la retención.
- **El cian se usa solo como acento:** la palabra que se está pronunciando en el efecto karaoke, bordes de insertos PiP, íconos, líneas divisorias.
- **El navy se usa solo en superficies:** fondo de tarjetas de specs, comparativas, banda de CTA final.
- **Proporción objetivo:** ~80% imagen real de José y el producto, ~20% superficies de marca. Si el video se ve "corporativo", nos pasamos.

Esto respeta la identidad de DeviceShop sin sacrificar retención.

---

## 6. ARQUITECTURA

### 6.1 El presupuesto visual (concepto central)

Video de 35s ÷ cambio cada 2.5s = **~14 beats visuales**.

De una sola toma de José se sacan 5–6 (plano abierto, medio, punch-in, variaciones). **Faltan 8–9 por video.**

| Fuente del beat | Viabilidad |
|---|---|
| Grabar B-roll manualmente | ❌ Horas de rodaje por video |
| Stock genérico | ❌ No muestra el producto real |
| **Insertos PiP de producto** | ✅ Grabar una vez por producto, reutilizable |
| **Motion graphics (Hyperframes)** | ✅ Gratis, ilimitado |
| **Generación en GPU (Flux/WAN)** | ✅ Gratis, ilimitado, específico |

**Por eso la capa de generación no es un lujo: es lo que hace matemáticamente posible la cadencia de 2–3s.** A 3 videos/semana serían ~27 elementos visuales semanales — insostenible de grabar, trivial de generar.

### 6.2 Pipeline

```
GRABACIÓN CRUDA (60–90s, con errores)
         │
    ┌────▼─────────────────────────────────┐
    │ 1. TRANSCRIPCIÓN    WhisperX GPU     │  palabras + tiempos + VAD
    ├──────────────────────────────────────┤
    │ 2. CORTE            silencios         │  → queda ~35s
    │                     muletillas        │
    │                     tomas repetidas   │
    ├──────────────────────────────────────┤
    │ 3. RETENCIÓN        punch-ins         │  regla de 5s
    │                     zoom progresivo   │
    │                     face tracking     │
    ├──────────────────────────────────────┤
    │ 4. AUDIO            música + ducking  │  normalizado 0 dB
    │                     SFX en cortes     │
    ├──────────────────────────────────────┤
    │ 5. OVERLAYS         subtítulos        │  estilo agencia
    │                     insertos PiP      │
    │                     stickers + CTA    │
    ├──────────────────────────────────────┤
    │ 6. GENERACIÓN GPU   Flux (imágenes)   │  rellena beats faltantes
    │                     WAN (video)       │
    └────┬─────────────────────────────────┘
         │
    VIDEO FINAL 30–40s · 1080x1920
```

### 6.3 Estructura de archivos objetivo

```
creacion-de-contenido/
├── contexto/
│   ├── PLAN-EDITOR-VIDEO.md        ← este documento
│   ├── ficha-estilo.json           ← parámetros visuales
│   └── tiktok video deviceshop.mp4 ← referencia de la agencia
├── editor/
│   ├── config.py                   ← toda la configuración en un solo lugar
│   ├── f1_transcribir.py
│   ├── f2_cortar.py
│   ├── f3_retencion.py
│   ├── f4_audio.py
│   ├── f5_overlays.py
│   ├── f6_generar.py
│   └── editor.py                   ← orquestador
├── assets/
│   ├── sfx/                        ← pack CC0
│   ├── musica/
│   ├── productos/                  ← fotos y clips PiP por producto
│   ├── logo/
│   └── fuentes/
├── entrada/                        ← grabaciones crudas
├── salida/                         ← videos terminados
└── .claude/skills/editor-deviceshop/
    └── SKILL.md                    ← entregable final
```

---

## 7. FASES DE EJECUCIÓN

> Cada fase termina con un **criterio de aceptación**. No avanzar sin confirmación del usuario.

---

### FASE 0 — Preparación del entorno

**Objetivo:** dejar la máquina lista, con GPU funcionando.

**Pasos:**

0. **Driver NVIDIA: mantener "Game Ready", solo actualizarlo.**
   **Decisión evaluada y cerrada:** se consideró cambiar a Studio y se descartó. CUDA y NVENC rinden idéntico en ambos drivers, y la certificación Studio cubre Adobe/Blender/DaVinci/Autodesk — **no** PyTorch ni ComfyUI, que es lo que usa este proyecto. El beneficio sería nulo y José juega ocasionalmente. **No proponer el cambio de nuevo.**
   Acción única: actualizar a la versión más reciente disponible.

1. **Instalar Python 3.12** (convive con el 3.14 existente, no lo reemplaza).
   ```
   winget install Python.Python.3.12
   ```

2. **Instalar ffmpeg real en PATH.**
   ```
   winget install Gyan.FFmpeg
   ```
   Verificar con `ffmpeg -version` en una terminal nueva.

3. **Crear el entorno virtual FUERA de OneDrive:**
   ```
   py -3.12 -m venv C:\ai-video\venv312
   ```

4. **Instalar PyTorch con soporte Blackwell (sm_120).**
   Las RTX 50 requieren build con **CUDA 12.8 o superior**. Los builds cu124 y anteriores **no funcionan**.
   ```
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
   ```
   **Verificar obligatoriamente:**
   ```python
   import torch
   print(torch.cuda.is_available())            # debe ser True
   print(torch.cuda.get_device_name(0))        # RTX 5070 Ti
   print(torch.cuda.get_device_capability(0))  # debe ser (12, 0)
   ```
   Si `sm_120` no aparece soportado, usar el índice nightly:
   `--pre --index-url https://download.pytorch.org/whl/nightly/cu128`

5. **Instalar WhisperX** y descargar `large-v3` (~3 GB) apuntando el cache a `C:\ai-video\models`.

6. **Configurar variables de entorno** para que HuggingFace y Torch no escriban en OneDrive:
   `HF_HOME`, `TORCH_HOME` → `C:\ai-video\models`

**Criterio de aceptación:**
- `torch.cuda.is_available()` devuelve `True` y detecta capability `(12, 0)`
- `ffmpeg -version` responde en PATH
- WhisperX transcribe un audio de prueba usando GPU (verificar que tarde segundos, no minutos)

**Riesgos:** si PyTorch estable aún no trae sm_120, usar nightly. Si nightly tampoco, ese es el único punto donde el proyecto se bloquea — reportarlo de inmediato.

---

### FASE 1 — Transcripción y corte limpio

**Objetivo:** de grabación cruda a video limpio, sin silencios ni muletillas.

**Entregable:** `editor/f1_transcribir.py` + `editor/f2_cortar.py`

**Especificación técnica:**

*Transcripción:*
- Modelo `large-v3`, `language="es"`, `compute_type="float16"`
- Alineación forzada wav2vec2 en español → timestamps por palabra (±50 ms)
- VAD integrado → segmentos de silencio
- Salida: JSON con `words[]` = `{texto, inicio, fin, confianza}` + `silencios[]`

*Detección de cortes:*
1. **Silencios:** huecos > 600 ms → recortar dejando **150 ms de margen** a cada lado (nunca cortar al ras, suena antinatural).
2. **Muletillas:** lista calibrable para español boliviano.
   Punto de partida: `eh`, `ehh`, `este`, `mmm`, `o sea`, `digamos`, `viste`, `no ve`, `ya pues`, `nada`, `tipo`.
   ⚠️ Cuidado con `bueno`, `entonces`, `pues` — a veces son conectores legítimos. Evaluar por contexto (duración, pausa alrededor, posición en la frase), no por coincidencia literal.
3. **Tomas repetidas:** detectar cuando José repite una frase similar (comparación difusa entre ventanas de texto cercanas) y **quedarse con la última** — que suele ser la buena.

*Corte de video:*
- Nunca cortar la primera ni la última palabra de una frase.
- Concatenar segmentos con ffmpeg, recalculando los timestamps de las palabras sobre la línea de tiempo resultante. **Este recálculo es la parte más delicada de todo el sistema** — si se desincroniza, los subtítulos y overlays quedan corridos. Verificar con cuidado.

**Criterio de aceptación:** José ve el video cortado y confirma que suena fluido, no le cortaron palabras, y las muletillas desaparecieron sin sonar robótico.

---

### FASE 2 — Subtítulos

**Objetivo:** subtítulos con el estilo exacto de la agencia.

**Entregable:** generador de `.ass` + quemado con ffmpeg.

**Especificación:**
- Formato **ASS** (permite karaoke palabra por palabra con la etiqueta `\k`)
- Estilo según sección 5.1: blanco, bold, contorno negro, tipo oración
- Segmentación: **2–4 palabras** por bloque
- Posición: **77% de la altura** (1478 px en un lienzo de 1920)
- **Zonas seguras:** margen inferior 15% y superior 10% libres de texto — ahí va la UI de TikTok
- Palabra activa **resaltada** mientras se pronuncia (efecto karaoke)

**Criterio de aceptación:** subtítulos perfectamente sincronizados, legibles en un celular, y sin invadir la UI de TikTok. Comparar lado a lado con el video de la agencia.

---

### FASE 3 — Capa de retención

**Objetivo:** eliminar la planitud. Es la fase que más impacta el resultado.

**Entregable:** `editor/f3_retencion.py`

**Especificación:**

1. **Face tracking (MediaPipe):** detectar el rostro de José en cada frame, con suavizado exponencial (alpha 0.1–0.2) para que la cámara virtual no tiemble.

2. **Punch-ins por énfasis:** analizar la energía del audio (RMS) y detectar picos donde José enfatiza. En esos puntos, zoom rápido (~1.15x) centrado en el rostro.

3. **Zoom progresivo:** deriva lenta y continua durante cada plano largo (1.0 → 1.08 a lo largo del plano). Casi imperceptible, pero mide en retención.

4. **Motor de la regla de 5s:** recorrer la línea de tiempo final y detectar cualquier bloque ≥5s sin cambio visual. Marcar esos huecos como **beats a rellenar** en la Fase 5.

5. **Diseño de loop:** el último frame debe encadenar visualmente con el primero (mismo encuadre o movimiento continuo).

**Criterio de aceptación:** José ve el video y siente que "tiene ritmo". Verificar con el motor de la regla de 5s que no queda ningún bloque muerto.

---

### FASE 4 — Audio

**Objetivo:** que suene profesional.

**Entregable:** `editor/f4_audio.py` + `assets/sfx/` + `assets/musica/`

**Especificación:**
- **Descargar pack SFX CC0 una sola vez** (Freesound, VideoEditingSFX). Necesarios: whoosh, pop, impacto, transición, notificación.
- **SFX automático:** whoosh en punch-ins, pop en aparición de texto/overlay, impacto en el hook.
- **Música de fondo continua** con **ducking automático**: baja ~12 dB cuando José habla, sube en los silencios. (Compresión sidechain en ffmpeg.)
- **Normalización final:** `loudnorm` apuntando a los niveles de TikTok, con pico limitado a 0.0 dB (igual que la agencia).
- La voz de José siempre es el audio dominante — es el "audio original" que el algoritmo premia.

**Criterio de aceptación:** el audio se escucha parejo, la música no tapa la voz, los SFX refuerzan sin cansar. Probar con audífonos y con el parlante del celular.

---

### FASE 5 — Overlays y producción visual

**Objetivo:** rellenar los beats visuales. Aquí entra Hyperframes.

**Entregable:** `editor/f5_overlays.py` + plantillas HTML

**Especificación:**

1. **Instalar Hyperframes** (Apache 2.0, sin API key, render local):
   ```
   npx hyperframes init
   ```
   Requiere Node 22+ (ya tienes v24) y ffmpeg. Renderiza HTML+CSS+GSAP → MP4 determinista.

2. **Plantillas reutilizables a construir:**
   - Inserto PiP de producto (esquinas redondeadas, borde blanco) — estilo agencia
   - Tarjeta de specs animada
   - Comparativa lado a lado (modelo A vs B)
   - Banner de hook (texto ≤7 palabras, primeros 3s)
   - Tarjeta de cierre con CTA a WhatsApp + logo
   - Stickers animados (destellos, envío, bandera)

3. **Sincronización:** los overlays se disparan por **palabras clave del guion**. Cuando José dice "batería", entra el overlay de batería. Esto se resuelve buscando términos del catálogo en la transcripción.

4. **Rellenar los huecos** marcados por el motor de la regla de 5s.

**Criterio de aceptación:** ningún bloque de 5s sin cambio. Los overlays entran sincronizados con lo que José dice. El look sigue siendo natural, no saturado.

---

### FASE 6 — Generación en GPU

**Objetivo:** material visual ilimitado sin grabar.

**Entregable:** `editor/f6_generar.py` + workflows de ComfyUI

**Especificación:**
- **ComfyUI** instalado en `C:\ai-video\comfyui` (fuera de OneDrive)
- **Flux** con cuantización **GGUF Q5** (~9 GB, deja headroom en tus 16 GB) → imágenes hero, fondos, escenas de estilo de vida
- **WAN 2.2** con **Q5_K_M** → B-roll animado, 720p cómodo en 16 GB
- **Mejora de fotos de producto:** quitar fondo (rembg/SAM) + recomponer sobre fondo generado + upscale. Convierte una foto de celular en algo tipo render de estudio.

**Nota de prioridad:** esta fase es la de mayor esfuerzo y menor urgencia. **Solo abordarla cuando las fases 1–5 estén funcionando**. Si el presupuesto visual se cubre con insertos PiP + Hyperframes, esta fase puede posponerse indefinidamente.

**Criterio de aceptación:** generar una imagen de producto usable en menos de 60 segundos, sin errores de memoria.

---

### FASE 7 — Empaquetado como skill

**Objetivo:** que cada video futuro sea un solo comando.

**Entregable:** `.claude/skills/editor-deviceshop/SKILL.md`

**Contenido del skill:**
- Todo el estilo visual y las reglas de retención de este documento
- Catálogo de productos DeviceShop con sus specs y beneficios
- Banco de hooks probados por ángulo (dolor, curiosidad, regalo, comparativa, urgencia)
- CTA y datos de contacto
- Invocación del pipeline completo
- Instrucciones para soportar 2 presentadores (José y su esposa)

**Criterio de aceptación:** José pasa un video crudo, ejecuta un comando, y obtiene un video publicable sin intervención manual.

---

## 8. DECISIONES CERRADAS

No re-litigar. Ya se evaluaron y se descartaron alternativas.

| Decisión | Elegido | Por qué |
|---|---|---|
| Motor de transcripción | **WhisperX local** | Gratis, sin API key, timestamps ±50 ms, VAD incluido. Se evaluó AssemblyAI: excelente pero de pago y sin ventaja con GPU propia |
| Diarización | **No** | José graba solo. Evitarla ahorra el token de HuggingFace |
| Modelo | **large-v3** | Con RTX 5070 Ti no hay razón para uno menor |
| Idioma | **`es` fijo** | Español boliviano, sin mezcla de idiomas |
| Motion graphics | **Hyperframes** | Apache 2.0, sin API key, render local, diseñado para agentes |
| Formato | **9:16 vertical, 1080x1920** | TikTok/Reels/Shorts |
| Duración | **30–40s** | Exigencia de completación >70% |
| Presentador | **José** (esposa después) | El sistema debe soportar ambos |
| Ubicación de modelos | **Fuera de OneDrive** | 30–40 GB no deben sincronizarse |
| Python | **3.12** (nuevo, junto al 3.14) | PyTorch no soporta 3.14 |
| Costo | **$0 estricto** | Sin APIs de pago |

---

## 9. PREGUNTAS — ESTADO

### ✅ Resueltas

1. **Paleta de marca** → confirmada. Navy `#0A2A3E` + Cian `#4FD1D9`. Ver sección 5.3 para cómo usarla (regla importante: **no** pintar el video con ellas).
2. **Micrófono** → José tiene **DJI Mic Mini** (inalámbrico de solapa). Excelente para el pipeline: audio limpio y cercano = transcripción mucho más precisa y menos falsos positivos en la detección de muletillas.
   *Buenas prácticas a recordarle:* transmisor a un palmo del pecho, sin ropa rozando la cápsula, grabar en la máxima calidad que permita la app de cámara, y verificar niveles antes de cada sesión.
3. **Primer video de prueba** → **Kindle Paperwhite**.

4. **WhatsApp** → **69214437**, confirmado por José. Este es el número real y va en el CTA de todos los videos.
5. **Logos** → en `contexto/LOGOS IVAN/`:
   - `Deviceshop Bo Logo.ai` — vectorial, fuente de verdad
   - `deviceshop blanco.png` — para fondos oscuros
   - `deviceshop color.png` — para fondos claros
   - El resto son portadas de Facebook y fotos de perfil (no usar en video)
   *Tarea en Fase 5:* extraer del `.ai` un PNG con transparencia en alta resolución para el badge de cierre.

### ⏳ Pendiente

6. **Fuente tipográfica.** Si no hay una de marca, usar **Poppins Bold** o **Montserrat Bold** (gratuitas, muy parecidas a la que usa la agencia). *No bloquea nada — se puede decidir sobre la marcha en la Fase 2.*

---

## 10. FUENTES DE LA INVESTIGACIÓN

**Transcripción local:**
- [WhisperX (GitHub)](https://github.com/m-bain/whisperx)
- [WhisperX: word-level timestamps & diarization](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/whisperx-diarization-word-level-timestamps)

**Motion graphics:**
- [Hyperframes (GitHub, Apache 2.0)](https://github.com/heygen-com/hyperframes)
- [Guía Hyperframes + Claude](https://github.com/heygen-com/hyperframes/blob/main/docs/guides/claude-design-hyperframes.md)

**Retención y algoritmo:**
- [TikTok Algorithm 2026: cómo funciona el ranking del FYP](https://likes.io/blog/tiktok-algorithm-2026)
- [TikTok Algorithm 2026: ganar con rewatches](https://www.darkroomagency.com/observatory/how-tiktok%E2%80%99s-algorithm-works-in-2026-and-15-tactics-to-go-viral)
- [Playbook de edición vertical para watch time 2026](https://www.strategia-x.com/blog/2026-07-01-vertical-video-retention-editing-playbook/)
- [Pattern interrupts para retención](https://joyspace.ai/pattern-interrupt-reset-attention-span)
- [20 técnicas de edición 2026](https://clippie.ai/blog/video-editing-techniques-creators-2026)

**Generación local en GPU:**
- [Flux 2 en RTX 5070 Ti 16GB](https://apatero.com/blog/flux-2-rtx-5070-ti-16gb-performance-guide-2025)
- [WAN 2.2 en ComfyUI](https://www.thundercompute.com/blog/wan-2-2-comfyui-ai-video-model)

**PyTorch en Blackwell:**
- [Soporte sm_120 en PyTorch (issue oficial)](https://github.com/pytorch/pytorch/issues/164342)

---

*Fin del documento maestro.*
