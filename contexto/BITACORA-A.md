# Bitácora — Sesión A (Editor de Video)

Trabajo autónomo nocturno. Sesión en paralelo con B (materiales/assets) — no se tocó nada de su territorio (`assets/`, `plantillas/`, `contexto/catalogo-*`, `contexto/banco-hooks.md`, `contexto/BITACORA-B.md`, `C:\ai-video\venv-comfy\`).

---

## Fase 0 — Entorno

**Hecho:**
- Python 3.12.10 instalado vía winget (`Python.Python.3.12`), convive con el 3.14 existente.
- ffmpeg 8.1.2 (Gyan.FFmpeg) instalado y en PATH, build "full" con soporte NVENC/CUVID/libx264/libx265.
- Entorno virtual creado en `C:\ai-video\venv312` (fuera de OneDrive, como exige la regla del documento maestro).
- PyTorch 2.11.0+cu128 instalado (`--index-url https://download.pytorch.org/whl/cu128`).
- **Verificado:** `torch.cuda.is_available() == True`, `torch.cuda.get_device_capability(0) == (12, 0)`, GPU detectada como `NVIDIA GeForce RTX 5070 Ti`. Blackwell (sm_120) soportado sin necesitar el build nightly — el estable cu128 ya lo trae.
- `HF_HOME` y `TORCH_HOME` configurados a nivel de usuario (`setx`-equivalente) apuntando a `C:\ai-video\models`, para que ningún modelo se sincronice a OneDrive.
- Creados `editor/`, `salida/`, `entrada/` dentro del proyecto.

**Decisión — Driver NVIDIA:** el documento pedía "actualizar a la versión más reciente disponible" del driver Game Ready. Verifiqué el driver actual: `610.47` (CUDA UMD 13.3), que ya es reciente y CUDA/PyTorch funcionan correctamente con él (confirmado arriba). Actualizar el driver requiere la app GeForce Experience/NVIDIA App con interfaz gráfica y posible reinicio — no es algo que se pueda automatizar de forma segura ni silenciosa por línea de comandos, y el propio documento aclara que el beneficio real es nulo para este proyecto (CUDA/NVENC rinden igual). **Decisión:** no tocar el driver; ya funciona. Si José quiere actualizarlo por gusto, puede hacerlo manualmente desde la app NVIDIA cuando quiera — no es bloqueante.

**Incidente — WhisperX pisó el PyTorch con CUDA:** al instalar `whisperx opencv-python mediapipe scipy numpy` sin fijar `--index-url`, pip resolvió `torch`/`torchaudio` como dependencias de whisperx desde el índice normal de PyPI (build **CPU-only**), reemplazando el 2.11.0+cu128 que ya funcionaba. Lo detecté porque `torch.cuda.is_available()` pasó de `True` a `False` (error: "Torch not compiled with CUDA enabled"). Un primer intento de reinstalar con `--index-url cu128` no lo arregló porque pip vio "torch ya satisfecho" (no distingue el sufijo `+cu128` de un build CPU al resolver sin restricción de versión) — hubo que forzar con `--force-reinstall --no-cache-dir`. **Lección para la próxima sesión/skill:** siempre instalar/reinstalar librerías que dependan de torch (whisperx, etc.) primero, y recién al final reinstalar `torch/torchvision/torchaudio` con `--index-url cu128 --force-reinstall` para que quede fijo; o usar un `constraints.txt` que fije la versión exacta `torch==2.11.0+cu128`.

**Fuentes reales encontradas en `assets/fuentes/` (entregadas por sesión B):** `Poppins-Bold.ttf`, `Poppins-ExtraBold.ttf`, `Montserrat-Bold.ttf` + licencias OFL. Esto resuelve la pregunta pendiente 6 de la sección 9 del plan — ver nota en Fase 2 más abajo.

---

## Desviación menor respecto a la sección 6.3 del plan

La lista de archivos de la sección 6.3 no incluye un archivo específico para los subtítulos (Fase 2) — solo aparecen `f1_transcribir.py`, `f2_cortar.py`, `f3_retencion.py`, `f4_audio.py`, `f5_overlays.py`, `f6_generar.py`, pero la Fase 2 (subtítulos) sí tiene su propia sección de especificación en el punto 7. Es un vacío en la numeración del documento.

**Decisión:** renombré para que el número de archivo coincida con el número de fase, así queda más claro para mantenimiento futuro:

| Archivo | Fase |
|---|---|
| `f1_transcribir.py` | 1a — transcripción |
| `f2_cortar.py` | 1b — corte |
| `f3_subtitulos.py` | 2 — subtítulos |
| `f4_retencion.py` | 3 — retención |
| `f5_audio.py` | 4 — audio |
| `f6_overlays.py` | 5 — overlays |
| `editor.py` | orquestador |

Cuando se implemente generación GPU (Fase 6, pospuesta según la propia sección 7 del plan), seguirá como `f7_generar.py`.

---

## Cambio de plan a mitad de sesión

José escribió mientras dormía (no fue una pregunta mía, fue él proactivamente) pidiendo continuar con Fases 4 y 5 (audio y overlays) después de la 3, con código completo probado contra el video de la agencia, y **sin calibrar umbrales** (silencio/muletillas/punch-in quedan en sus valores por defecto, a calibrar mañana con grabación real). Se ejecutó tal cual.

---

## QA visual de Fases 1-3 (antes de seguir con 4-5)

Extraje frames del video de prueba procesado (`salida/prueba/`) en varios timestamps para revisar el resultado real, no solo confiar en que el código corrió sin error. Encontré y corregí dos bugs reales:

1. **Capitalización incorrecta en subtítulos.** El generador forzaba mayúscula en la primera palabra de CADA bloque visual (2-4 palabras), no solo al inicio de cada oración — resultado: "**A** los libros digitales" en vez de "a los libros digitales" (mitad de oración). WhisperX ya transcribe con capitalización de oración correcta por sí solo; la función solo necesitaba tocar la primerísima palabra del video, nada más. Corregido en `f3_subtitulos.py` (`_limpiar_para_oracion`). Verificado con un frame antes/después.

2. **"Doble subtítulo" — no era un bug.** Al quemar mis subtítulos sobre el video de referencia aparecían dos líneas de texto superpuestas. Antes de asumir que era un bug del pipeline, comparé contra el video ORIGINAL sin procesar en el mismo segundo: la agencia ya tiene sus propios subtítulos quemados de fábrica en ese clip (es su video final publicado, no material crudo). Con la grabación real de José —sin subtítulos previos— esto no pasará. Lección: **siempre comparar contra la fuente antes de diagnosticar un bug en el pipeline.**

3. **Ruta con ':' y espacios rompe el filtro `ass=` de ffmpeg.** `ffmpeg -vf "ass=C:\Users\...\CLAUDE CODE\...\subs.ass"` falla (`Unable to parse "original_size"...`) porque el parser de filtros de ffmpeg usa `:` como separador de opciones y no escapa bien rutas de Windows con espacios. Solución: correr ffmpeg con `cwd` en la carpeta de trabajo y pasar nombres de archivo relativos (sin `:` ni espacios en el string). Igual patrón aplicado después para `fontsdir`.

Con esos dos fixes, el video de prueba (`salida/prueba/05_final.mp4` en ese momento) se veía correcto: subtítulo blanco/negro con la palabra activa en cian, capitalización de oración real, posición ~77% de altura, formato 1080×1920 vertical.

---

## Fase 1 — Transcripción y corte

**`editor/f1_transcribir.py`:**
- WhisperX `large-v3`, `language="es"`, `compute_type="float16"` en GPU (fallback a `int8`/CPU si CUDA no está disponible, con advertencia).
- Alineación forzada wav2vec2 → timestamps por palabra.
- Guarda `palabras[]` (texto, inicio, fin, confianza), `segmentos[]` (frases con sus límites, usadas por f2 para no cortar la primera/última palabra de una frase y para detectar tomas repetidas), y `silencios[]` derivados de los huecos entre palabras.

**`editor/f2_cortar.py`:**
- **Silencios:** huecos > 600ms se recortan dejando 150ms de margen a cada lado (si el silencio es más corto que 2×margen, no se toca — evitaría cortes al ras).
- **Muletillas:** lista de `config.MULETILLAS` calibrable. Los conectores ambiguos (`bueno`, `entonces`, `pues`) solo se cortan si están aislados (pausa >300ms antes y después) — implementa la advertencia del documento de "evaluar por contexto, no por coincidencia literal", con una heurística simple de pausas. **Esto es un punto de partida — se calibra viendo resultado real, tal como pide la sección 0.6 del plan.**
- **Tomas repetidas:** similitud difusa (`difflib.SequenceMatcher`) entre frases dentro de una ventana de 20s; si supera 0.75 de similitud, se conserva la última y se marca la anterior para corte.
- **Regla dura:** nunca se corta la primera ni la última palabra de una frase (verificado comparando el timestamp de la palabra contra los límites de segmento).
- **Corte de video:** `ffmpeg filter_complex` con `trim`/`atrim` + `concat` (sin reencode intermedio a disco, un solo paso).
- **Recalculo de timestamps** (la parte que el documento marca como más delicada): cada intervalo conservado tiene un offset acumulado en la nueva línea de tiempo; toda palabra que cae *completamente* dentro de un intervalo conservado se remapea con `nuevo_t = offset + (t_original - inicio_intervalo)`. Las palabras que quedaron parcial o totalmente fuera (es decir, que fueron cortadas) se descartan del JSON de salida. No se probé aún contra el video real — pendiente de ejecución (ver sección "Pendiente" abajo).

---

## Fase 2 — Subtítulos

**`editor/f3_subtitulos.py`:**
- Genera `.ass` con estilo karaoke (`\c` para resaltar la palabra activa).
- Blanco (`&H00FFFFFF`) con contorno negro, cian de marca (`#4FD1D9`) solo como resaltado de la palabra que se pronuncia — respeta la regla 5.3 de no pintar el video con la marca.
- Bloques de 2-4 palabras, cerrando bloque también si hay una pausa >350ms o signo de puntuación final, para que el corte de bloque caiga en un punto natural del habla.
- Posición al 77% de la altura vía `MarginV` en el estilo ASS (calculado desde `config.SUB_POSICION_ALTURA_PCT`).
- Capitalización tipo oración (no mayúsculas) vía `_limpiar_para_oracion`.
- **Fuente — pregunta pendiente de la sección 9 del plan, parcialmente resuelta.** Sesión B entregó `Poppins-Bold.ttf` y `Montserrat-Bold.ttf` reales en `assets/fuentes/` (con licencia OFL). Intenté dos formas de que ffmpeg las use sin necesitar instalación de administrador:
  1. `fontsdir=assets/fuentes` en el filtro `ass=` — no funcionó.
  2. Instalar la fuente **por usuario** (sin admin): copiar el `.ttf` a `%LOCALAPPDATA%\Microsoft\Windows\Fonts\` + registrar en `HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts` + `AddFontResourceW` + broadcast `WM_FONTCHANGE` — exactamente lo que hace el "Instalar solo para mí" de Explorer. El registro quedó correcto (verificado leyendo la llave), pero un proceso `ffmpeg` nuevo tampoco la detectó.
  
  **Causa:** el log de ffmpeg lo dice explícito: `Using font provider directwrite... fontselect: (Poppins Bold, 700, 0) -> Arial-BoldMT`. El build de ffmpeg en esta máquina usa **DirectWrite** como proveedor de fuentes de libass en Windows, y DirectWrite no está recogiendo la fuente por las vías que probé (aunque el binario sí trae `--enable-fontconfig` compilado, en Windows por defecto prioriza DirectWrite). Investigar cómo forzar el proveedor `fontconfig` en libass en Windows, o simplemente instalar la fuente "para todos los usuarios" (eso sí requiere admin, y el plan prohíbe pedir esos permisos) queda **pendiente para José o una próxima sesión** — instrucciones en Windows: clic derecho sobre el `.ttf` → Instalar.

  **Esto NO es un bloqueante:** el filtro cae a `Arial-BoldMT`, que en negrita/blanco/contorno negro cumple igual el requisito de estilo (legible, redondeada, bold) aunque no sea la tipografía de marca exacta. Confirmado que el resto del estilo (color, contorno, posición, capitalización) es correcto — solo la tipografía literal queda pendiente. **Corrección a esta bitácora:** en una revisión anterior anoté "verificado visualmente que usa Poppins" — fue un error mío, comparé frames con contenido de texto distinto y saqué una conclusión visual que no estaba realmente confirmada. Quede como lección: verificar con el log de ffmpeg (`fontselect`), no solo "a ojo".

---

## Fase 3 — Retención

**`editor/f4_retencion.py`:**
- **Face tracking:** MediaPipe Face Detection (`model_selection=1`, short+long range) con fallback a Haar Cascade de OpenCV si mediapipe no estuviera disponible. Suavizado EMA con `alpha=0.15` (dentro del rango 0.1-0.2 que pide el documento).
- **Punch-ins:** RMS de audio en ventanas de 50ms, picos sobre percentil 90 con espaciado mínimo de 1.5s entre picos, para evitar que se agrupen. Duración del punch-in configurable (`PUNCH_IN_DURACION_S`), curva triangular de zoom hasta `1.15x`.
- **Zoom progresivo:** interpolación lineal `1.00 → 1.08` a lo largo de cada plano (tramo continuo entre jump-cuts de la Fase 1).
- **Motor de regla de 5s:** combina límites de plano + picos de energía como "eventos de cambio visual"; cualquier tramo ≥5s sin evento se marca como hueco y se guarda en un `.plan.json` para que la Fase 5 (aún no implementada) lo rellene con overlays.
- **Loop:** por ahora solo genera una nota de texto comparando el primer y el último plano — el diseño real del loop (que el último frame encadene visualmente con el primero) es una decisión creativa que corresponde a la Fase 5, cuando existan los overlays con los que armar ese cierre.
- **Render:** recorte dinámico centrado en el rostro (interpolando el track) + reescalado a 1080×1920, frame por frame con OpenCV, luego se reincorpora el audio original sin recodificar.

**Nota honesta sobre esta fase:** es la más compleja y la más probable de necesitar ajuste manual viendo el resultado real (tal como advierte la sección 0.6 del plan). El render frame-a-frame con OpenCV es funcional pero no está optimizado para velocidad.

**Incidente — MediaPipe sin API `solutions`:** la versión instalada (`mediapipe 0.10.35`, la que resuelve pip para Python 3.12 en Windows) **no incluye** el módulo legacy `mp.solutions.face_detection` que pedía el plan — solo trae la nueva Tasks API (`mediapipe.tasks`), que requiere descargar un modelo `.task` aparte. Documentado y corregido: el código ahora detecta con `hasattr(mp, "solutions")` y cae a Haar Cascade de OpenCV automáticamente (ya estaba previsto como fallback, solo faltaba que el chequeo cubriera este caso además del `ImportError`).

**Incidente — opencv-python 5.0.0 sin datos de Haar Cascade:** al caer al fallback, `cv2.data.haarcascades` apuntaba a una carpeta vacía — la versión 5.0.0 de `opencv-python` no empaqueta los XML de cascada. **Alternativa 1 probada y funcional:** fijar `opencv-python==4.10.0.84`, que sí trae los XML. Con eso el fallback funciona.

**Efecto secundario:** downgradear opencv-python reinstaló `numpy` a 2.5.1 (antes 2.4.4) y pip avisó de conflicto de versión entre `torch 2.11.0+cu128` y lo que `whisperx 3.8.6` declara necesitar (`torch~=2.8.0`). Es solo una advertencia de resolución de dependencias — **whisperx ya había transcrito correctamente con torch 2.11 antes de este cambio**, así que en la práctica no rompió nada, pero queda anotado por si algo falla más adelante y hay que revisar compatibilidad de versiones con más cuidado.

**Pendiente para calidad de producción:** MediaPipe da mejor tracking de rostro que Haar Cascade (más robusto a ángulos, iluminación, oclusión parcial). Cuando haya tiempo, vale la pena migrar a la Tasks API de MediaPipe (`mediapipe.tasks.python.vision.FaceDetector` + modelo `blaze_face_short_range.tflite`, descargable gratis) en vez de quedarse con Haar Cascade permanentemente — Haar es un sustituto aceptable para salir del paso, no la solución final.

---

## Fase 4 — Audio

**`editor/f5_audio.py`:**

Sesión B ya había entregado los assets reales cuando llegué a esta fase — no tuve que descargar nada (y no lo habría hecho sin preguntar primero: bajar archivos de sitios externos con criterio de curación/licencia no es un `pip install` reproducible, es un juicio de valor que le corresponde a B o a José). Usé directamente:
- `assets/musica/03-corporate-funky.mp3` como pista default (B ya anotó en su README que "casi calza directo" con 30-40s — buen punto de partida, cambiable en `config.MUSICA_ARCHIVO_DEFAULT` sin tocar código).
- `assets/sfx/whoosh_deep_1.mp3` en cada punch-in, `impacto_dramatico.mp3` en el hook (t=0) — nombres tomados literalmente del README de B, que ya los mapeaba a la sección 4.4 del plan.

**Mezcla (ffmpeg `filter_complex`):** voz (`0:a`) + música con loop/trim a la duración exacta del video + `sidechaincompress` (la música se agacha cuando José habla — ducking real, no un volumen fijo) + un input por cada evento SFX con `adelay` + `amix` (`normalize=0` para no atenuar automáticamente la voz) + `loudnorm` final a `-14 LUFS` / pico `0.0 dB` (sección 4.5: la voz de José manda, es el "audio original" que premia el algoritmo).

**Probado contra el video de referencia:** 31 eventos SFX (30 punch-in + 1 hook), archivo de salida válido, 60s, estéreo. **Advertencia esperada, no bug:** 30 punch-ins en 60s es un SFX cada ~2s — bastante denso/saturado para el gusto. Es así **a propósito**: José pidió explícitamente no calibrar el umbral de detección de picos de energía esta noche (se calibra mañana con grabación real). La narración profesional del video de la agencia tiene más énfasis vocal por segundo que el habla casual de José, así que el resultado con grabación real debería ser naturalmente menos denso — pero si sigue sonando saturado, el primer lugar donde tocar es `config.py`: subir el percentil del umbral en `f4_retencion.detectar_picos_energia` (hoy percentil 90) o el espaciado mínimo entre picos (hoy 1.5s).

---

## Fase 5 — Overlays

**`editor/f6_overlays.py`:**

**Decisión importante de alcance — descubrí que `plantillas/` ya no está vacía.** Al revisar el estado de `assets/` (solo lectura, para no pisar nada) encontré que sesión B ya tiene ahí un proyecto Hyperframes completo scaffoldeado (`package.json`, `hyperframes.json`, `compositions/`, `index.html`) — es decir, B ya está construyendo las plantillas de motion graphics que pedía la sección 7 Fase 5 del plan. Como `plantillas/` está explícitamente prohibida para mí, y no conozco la API/nombres de composición de lo que B está armando (además de que sigue "en preparación"), **no dupliqué ese trabajo ni intenté invocarlo**. En vez de eso, construí un renderizador de overlays liviano con Pillow + `ffmpeg overlay` (sin depender de Node/Hyperframes), autocontenido dentro de `editor/`. Cuando el proyecto de B en `plantillas/` esté listo, lo natural es que `f6_overlays.py` lo invoque en vez de (o adicionalmente a) los renders de Pillow — lo dejo anotado como integración pendiente de Fase 7, no algo que intenté resolver yo solo esta noche por respeto a su territorio.

**Lo que sí se generó con datos 100% reales esta noche:**
- **Banner de hook** (0-3.2s): tarjeta navy, borde cian, texto blanco Poppins ExtraBold. El texto del hook en sí es un placeholder honesto: las primeras ~7 palabras de la transcripción, NO un hook curado — el banco de hooks reales (`contexto/banco-hooks.md`) es de sesión B y no lo leí (mismo criterio de no invadir). Reemplazar esto por hooks reales es trabajo de Fase 7.
- **Tarjeta de cierre CTA** (últimos 6.5s): logo real (`assets/logo/deviceshop-icono-blanco-transparente.png`), número de WhatsApp real (69214437, viene del propio documento del plan, no de un archivo de B), handle de TikTok real. Coincide en tiempo casi exacto con el cierre del video de la agencia (que también hace su CTA en los últimos segundos) — buena señal de que la heurística "últimos ~6.5s = CTA" es razonable.
- **Sincronización por palabra clave:** tabla `PALABRAS_CLAVE_STICKER` en `config.py`, marcada explícitamente como placeholder genérico (envío, whatsapp, garantía, oferta...) — NO es el catálogo real de B. En el video de prueba, las palabras clave que sí aparecen ("envíos", "Bolivia") caen dentro de la ventana del CTA y correctamente NO generan un sticker duplicado ahí (verificado revisando los timestamps).
- **Relleno de huecos (regla de 5s):** mecanismo listo (`planificar_overlays` lee `huecos_regla_5s` del plan de f4_retencion), pero en el video de prueba no hubo huecos que rellenar (Fase 3 ya lo reportó "OK, ningún hueco"), así que no se ejercitó en este test — lógica cubierta por code review propio pero no por un caso real todavía.

**Lo que NO se generó (a propósito, no es un olvido):** inserto PiP de producto, tarjeta de specs, comparativa lado a lado. Los tres necesitan fotos/datos reales de producto (`assets/productos/`, que todavía no existe) o el catálogo (`contexto/catalogo-*`, de B). La función `render_tarjeta_generica()` ya está escrita y lista para recibir esos datos — no hacía falta inventar contenido de marketing falso solo para "completar" la fase.

**Bug real encontrado y corregido:** los overlays no aparecían en el video compuesto pese a que los PNG se veían perfectos por separado. Causa: pasé cada imagen a ffmpeg con un solo `-i archivo.png` (sin `-loop 1 -t duración`), así que ffmpeg la trata como UN frame en el instante 0. El filtro `fade` (que hace la aparición/desaparición suave) calculó la opacidad una sola vez en t=0 — justo el arranque de la rampa de entrada, o sea prácticamente transparente — y esa imagen (ya transparente) es la que `overlay` repite para el resto del video al llegar a EOF. Con `-loop 1 -framerate 30 -t {duración}` la imagen se convierte en un stream real que avanza en el tiempo, y el fade funciona como corresponde. Verificado con capturas antes/después.

---

## QA visual del pipeline completo (Fases 1-5)

Con el orquestador `editor.py` corregido (orden: retención → audio → **overlays** → **subtítulos al final**, para que el texto siempre quede en la capa más alta y ningún overlay lo tape), corrí el pipeline completo de punta a punta contra el video de prueba, un solo comando desde el crudo hasta `07_FINAL.mp4`. Frames revisados a los 1s, 20s y 57s confirman: hook banner con estilo de marca correcto, tarjeta CTA con logo/WhatsApp reales, subtítulo con capitalización correcta y estilo bold/blanco/contorno negro en la posición correcta (tipografía real Poppins aún pendiente, ver nota en Fase 2 — cae a Arial Bold), sin overlays tapándose entre sí. Verifiqué el log completo de ffmpeg de esta corrida (no solo los frames) para confirmar que las 5 fases se ejecutaron en orden y sin errores.

---

## Estado final de la noche

**Hecho y probado de punta a punta** (un solo comando, `python editor/editor.py "video.mp4"`, corre las 5 fases sin intervención manual): transcripción, corte inteligente, subtítulos, retención (zoom/face-tracking/punch-ins), audio (música con ducking + SFX + loudnorm), overlays (hook + CTA con datos reales). Resultado en `salida/prueba_completa/07_FINAL.mp4`, revisado con capturas en varios timestamps, no solo "corrió sin error".

## Pendiente / próximos pasos

**Para calibrar mañana con grabación real de José (a propósito no tocado esta noche):**
- [ ] `MULETILLAS`, `SILENCIO_UMBRAL_MS`, `TOMA_REPETIDA_SIMILITUD_MIN` (Fase 1).
- [ ] Umbral de picos de energía / punch-ins — hoy percentil 90 genera ~1 SFX cada 2s, probablemente denso de más para habla casual (Fase 3/4).
- [ ] `PUNCH_IN_ZOOM`, `ZOOM_PROGRESIVO_FIN`, `FACE_TRACK_SUAVIZADO_ALPHA` — verificar que no tiemble ni maree con movimiento real de José (Fase 3).
- [ ] Volúmenes `MUSICA_VOLUMEN`/`SFX_VOLUMEN` — probar con audífonos y parlante de celular como pide el criterio de aceptación de Fase 4.

**Bugs conocidos / limitaciones técnicas sin resolver:**
- [ ] **Tipografía Poppins no se aplica en el quemado de subtítulos** (cae a Arial Bold vía DirectWrite) — dos intentos fallidos, ver detalle en sección Fase 2. Vía de arreglo más simple: José instala el `.ttf` con clic derecho → Instalar (2 minutos, no necesita admin para "solo para mí").
- [ ] Face tracking usa Haar Cascade (fallback) en vez de MediaPipe — funciona pero es menos robusto a ángulos/iluminación. Migrar a la Tasks API de MediaPipe cuando haya tiempo (ver nota en Fase 3).
- [ ] Diseño de loop (que el último frame encadene con el primero) — hoy solo se genera una nota de texto, no hay lógica real todavía. Es una decisión de edición que probablemente se resuelva mejor a mano/creativamente que con una regla automática.

**Bloqueado por assets que no existen todavía (no es trabajo mío pendiente, es esperar a sesión B / próxima grabación):**
- [ ] `assets/productos/` (fotos reales de producto) → inserto PiP, tarjeta de specs, comparativa lado a lado. El mecanismo de render ya existe (`render_tarjeta_generica` en `f6_overlays.py`), falta contenido real.
- [ ] Catálogo de productos y banco de hooks reales (`contexto/catalogo-*`, `contexto/banco-hooks.md`, de sesión B) → hoy el hook banner usa las primeras palabras de la transcripción como placeholder, y la sincronización por palabra clave usa una tabla genérica en `config.py`.
- [ ] Integración con el proyecto Hyperframes que sesión B ya empezó en `plantillas/` — mi renderizador de overlays (Pillow) es un sustituto funcional, no lo reemplaza necesariamente.

**No iniciado (fuera de alcance de lo pedido esta noche):**
- [ ] Fase 6 — Generación GPU (Flux/WAN/ComfyUI). El propio plan dice que es de baja prioridad y puede posponerse indefinidamente si PiP + overlays alcanzan.
- [ ] Fase 7 — Empaquetado como skill reutilizable.

*(Bitácora completa al cierre de esta sesión. Cualquier pregunta sobre una decisión, buscar la fase correspondiente arriba — todas están documentadas con el motivo.)*

---

# Anexo — Optimización de rendimiento (2026-07-26, sesión de planificación)

Sesión distinta a la A. José reportó **CPU al 95% con la GPU al 3%** mientras corría el pipeline. Diagnóstico y arreglo.

## Causa raíz

Todo el video se codificaba por software aunque el ffmpeg instalado sí trae NVENC (verificado: `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`, y `cuda` entre los hwaccels).

**Cuatro codificaciones por CPU en cadena**, una de ellas doble:
1. `f2_cortar.py` → `libx264`
2. `f4_retencion.py` → `cv2.VideoWriter` con fourcc `mp4v` (MPEG-4 Part 2, solo software) **y después** re-codificaba ese temporal con `libx264` — dos pasadas y un archivo pesado de disco por el medio
3. `f6_overlays.py` → `libx264`
4. `editor.py` (quemado de subtítulos) → sin `-c:v`, o sea el default de ffmpeg, que también es `libx264`

## Cambios aplicados

**`config.py`** — nueva sección centralizada de codificación:
- `hay_nvenc()` detecta NVENC una sola vez y cachea el resultado.
- `args_video(final=False)` devuelve los argumentos de ffmpeg, con **fallback automático a `libx264`** si NVENC no existiera (el pipeline sigue corriendo en cualquier máquina).
- Dos niveles de calidad porque el pipeline recomprime 4 veces y la pérdida se acumula: `NVENC_CQ_INTERMEDIO = 21` para los pasos intermedios, `NVENC_CQ_FINAL = 26` para el archivo que se publica.
- `AUDIO_SAMPLE_RATE = 48000`.

**`f4_retencion.py`** — el arreglo grande:
- Eliminado `cv2.VideoWriter`/`mp4v` y la re-codificación posterior. Ahora los frames procesados van **crudos por tubería a ffmpeg** (`-f rawvideo -pix_fmt bgr24 -i pipe:0`), que codifica con NVENC y muxea el audio en **una sola pasada**. Se fue una codificación entera y el temporal de disco.
- `stdout`/`stderr` del subproceso van a un **archivo de log, no a un pipe** — un pipe sin lector se llena y bloquea a ffmpeg (es el mismo incidente que documentó la sesión B con ComfyUI en su punto 8).
- Manejo de `BrokenPipeError` y verificación de `returncode` con volcado del log si falla.
- **Face tracking:** se analiza a 5 fps sobre video de 30 fps, pero antes se hacía `read()` de todos los frames y se descartaban. Ahora los frames que no se analizan se saltan con `grab()`, que avanza el decodificador sin construir el array de numpy ni convertir color.

**`f5_audio.py`** — bug real encontrado verificando el archivo de salida (no en el código):
- El final salía con **audio a 96 kHz**. Causa: el filtro `loudnorm` de ffmpeg trabaja internamente a 192 kHz y, sin `-ar` explícito en la salida, el archivo queda a 96 kHz — el doble de peso sin ganancia.
- Además las tres etapas (voz, música, SFX) hacían `aformat=sample_rates=44100`, o sea que la voz del DJI Mic Mini (48 kHz) se bajaba a 44.1 y volvía a subir. Toda la cadena unificada a `config.AUDIO_SAMPLE_RATE`.

**`editor.py`** — el quemado de subtítulos ahora usa `args_video(final=True)`. Actualizado el comentario sobre las fuentes: José instaló Poppins en Windows el 2026-07-26 y **ya se aplica correctamente** (DirectWrite la encuentra por familia); queda resuelto el pendiente de la Fase 2.

## Mediciones

Benchmark aislado, 15s a 1080x1920:

| Codificador | Tiempo | Peso |
|---|---|---|
| `libx264 -preset medium -crf 18` | 15.1s | 22.5 MB |
| `h264_nvenc -preset p5 -cq 19` | 3.8s | 56.1 MB |
| `h264_nvenc -preset p5 -cq 26` | 3.7s | 23.6 MB |

**4x más rápido**, y a CQ 26 el peso queda igual que x264. El tiempo **no cambia** con el CQ, por eso subir la calidad de los intermedios sale gratis.

Pipeline completo sobre la grabación real de José (`VIDEOV2.mp4`, 44s): **1.22 minutos** de punta a punta.

## Grabación

José regrabó con la configuración correcta tras investigar el tema. `VIDEOV2.mp4` viene en **H.264 8 bits, bt709 (SDR), 30 fps** — antes era HEVC 10 bits con HDR (HLG/bt2020) a 60 fps. Esto **elimina la necesidad del paso de normalización** que se había considerado: sin conversión de tono, sin riesgo de que OpenCV ignore el metadato de rotación, y la mitad de frames que procesar.

## Resultado verificado

`salida/v2_final/07_FINAL.mp4` — 37.17s (dentro del objetivo 30-40s), 1080x1920, H.264, audio 48 kHz, 28.5 MB. Revisado con frames a 1s, 18s y 34s: banner de hook, inserto PiP del Paperwhite sincronizado con "resistente al agua", tarjeta de CTA con logo y WhatsApp, subtítulos karaoke en Poppins con resaltado cian.

Con la voz real de José se detectaron **17 punch-ins** contra los 30 del video de la agencia — se confirma lo que anticipaba la sesión A en su Fase 4: el habla casual tiene menos densidad de énfasis que una narración profesional con guion. La densidad de SFX ya no está saturada.
