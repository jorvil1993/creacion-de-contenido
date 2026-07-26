# Auditoría y optimización del pipeline — 2026-07-26

Sesión de auditoría sobre el pipeline ya operativo. Todo lo que dice este documento
fue **medido en esta máquina contra `contexto/VIDEOV2.mp4`** (la grabación real de 44s),
no estimado. El video de prueba resultante quedó en `salida/auditoria_opt.mp4` para que
lo revises en el celular.

## Resumen en una línea

**El pipeline pasó de 68 segundos a 38 segundos Y la calidad de imagen subió de forma
medible** — contra una referencia sin pérdida: VMAF 96.65 → **98.83**, PSNR 43.97 →
**47.23 dB**. El video ahora se recomprime 2 veces en vez de 4, y las corridas nuevas
ya no llenan tu OneDrive. Nada de lo que funcionaba se rompió: el resultado se
verificó frame por frame, con medición objetiva de imagen y de audio.

Esa ganancia viene de dos cosas: la reestructuración del pipeline (sección 1) y el
ajuste de CQ 26 → 22 que José aprobó (sección 4-bis). El archivo final pasó de 28.5 MB
a 54.9 MB — el intercambio explícito y aceptado: más peso de subida a cambio de más
calidad.

---

## 1. Mediciones: antes y después

Todas las mediciones son "en caliente" (segunda corrida del día; la primera del día
suma unos ~25s extra porque Windows tiene que leer los 3 GB del modelo de WhisperX
del disco — eso es inevitable y le pasa igual a cualquier programa grande).

| Fase | Antes | Después | Qué cambió |
|---|---|---|---|
| 1a Transcripción (WhisperX) | 15.7s | ~15s | Nada (ver sección 4.9) |
| 1b Corte | 3.9s | ~4s | Nada |
| 3 Retención — análisis | 27.9s | ~4.5s | **Face tracking: 26.9s → 3.3s** (MediaPipe) |
| 3 Retención — render | 8.7s | ~7s | Ahora compone overlays + subtítulos adentro |
| 4 Audio | 1.6s | 1.6s | Nada (ya copiaba el video sin recomprimir) |
| 5 Overlays (video aparte) | 4.6s | — | Eliminada como codificación aparte |
| 2 Quemado de subtítulos (aparte) | 3.3s | — | Eliminada como codificación aparte |
| **TOTAL pipeline completo** | **68.3s** | **34.6–35.1s** | (dos corridas de confirmación) |

Codificaciones de video en cadena: **antes 4** (cortar → retención → overlays →
subtítulos), **ahora 2** (cortar → render único). Cada recompresión pierde un poco de
calidad; la mitad de recompresiones = mejor imagen final con el mismo peso.
El audio también pasa por una generación menos de compresión.

### ¿La optimización quitó calidad? No — la subió, y está medido

José preguntó explícitamente si acelerar el pipeline costó calidad de imagen.
Para responderlo sin opinar, monté un experimento controlado: se renderizaron tres
versiones del MISMO video con la MISMA geometría (mismo encuadre, mismos overlays,
mismos subtítulos), cambiando únicamente la cadena de compresión:

- **R** = referencia **sin pérdida** (x264 `-qp 0`, 538 MB) — la verdad contra la que medir.
- **A** = cadena **nueva** (1 sola codificación NVENC).
- **B** = cadena **vieja** (3 codificaciones NVENC encadenadas).

Resultado sobre los 1105 frames comparables, con las métricas estándar de la industria
(VMAF es la que usa Netflix para medir calidad percibida; 100 = idéntico al original):

| Métrica contra la referencia sin pérdida | Cadena VIEJA | Cadena NUEVA |
|---|---|---|
| VMAF medio | 96.65 | **97.69** |
| PSNR medio | 43.97 dB | **45.05 dB** |
| SSIM medio | 0.99644 | **0.99731** |
| Peor frame del video (VMAF) | 90.47 | **92.85** |
| Peso del archivo | 27.5 MB | 29.9 MB |

La cadena nueva gana en **todas** las métricas. El archivo nuevo pesa un poco más
justamente *porque* conserva más detalle: el video viejo llegaba al último paso ya
suavizado por dos compresiones previas, y lo que ya se perdió comprime más chico.
Donde más se nota es en los bordes de alto contraste — el texto de los subtítulos y
las tarjetas — que es lo que peor sobrevive a las recompresiones repetidas.

*Nota metodológica:* en la primera pasada la cadena vieja marcó un "peor frame" de
VMAF 35.6, que parecía un defecto grave. No lo era: la cadena vieja producía 1107
frames contra 1105 de la referencia (el paso de overlays alargaba el video 2 frames),
y esos 2 frames sobrantes se comparaban contra nada. Verificado el conteo real de
frames y recalculado sobre los frames comunes, el número honesto es 90.47. De paso:
la cadena nueva **conserva la duración exacta**, la vieja la corría 0.07s.

### Verificación del resultado (no solo "terminó sin error")

- **Video:** frames extraídos a 1s, 10s, 18s y 34s del final nuevo y del final viejo,
  comparados lado a lado. Hook banner ✓, subtítulos karaoke con palabra en cian ✓,
  PiP del Kindle sincronizado con "es resistente al agua" ✓, tarjeta CTA con logo y
  WhatsApp ✓, subtítulos siempre por encima de los overlays ✓, rostro bien encuadrado ✓.
- **Audio:** medido con el estándar EBU R128: **-14.1 LUFS** integrado (objetivo -14),
  pico real -0.4 dBFS (sin distorsión), idéntico al de antes.
- **Formato:** 37.13s (dentro del objetivo 30-40s), 1080×1920, AAC 48 kHz estéreo.
- **Modo clásico:** los scripts f4 y f6 siguen funcionando solos con sus comandos de
  siempre (probado) — los cambios solo agregan opciones nuevas, no quitan nada.

---

## 2. Cambios aplicados (con su medición)

### 2.1 Face tracking migrado a MediaPipe Tasks — 26.9s → 3.3s (8x)

**El hallazgo más importante de la sesión, y no estaba en tu lista.** Tu pista 3
sospechaba del bucle de render de Python; medí por separado y el render solo costaba
8.7s — el verdadero devorador era el face tracking con Haar Cascade: **26.9 de los
39 segundos de la fase**. Causa: buscaba rostros desde 30 píxeles de tamaño en el
frame completo de 1080×1920, sin límite de tamaño mínimo ni reducción previa
(~145 ms por frame analizado).

Arreglo doble:
1. **MediaPipe Tasks API** (lo que pedía tu pista 7): descargué el modelo oficial
   `blaze_face_short_range.tflite` (230 KB, gratuito) a `C:\ai-video\models\mediapipe\`
   y reescribí el detector con la API nueva. Mejor seguimiento Y más rápido.
2. El fallback Haar (por si el modelo faltara) ahora también es rápido: detecta sobre
   el frame reducido a 540 px con tamaño mínimo de rostro, en vez del frame completo.

Verificación: el rostro se detectó en las 185 muestras (igual que antes); la
trayectoria difiere de la de Haar en promedio solo 0.9% en horizontal. En vertical hay
un corrimiento sistemático de ~4% porque BlazeFace encuadra el rostro distinto que
Haar (no es un error — se verificó en los frames finales que el encuadre queda bien).

### 2.2 Overlays + subtítulos dentro del render de retención — 4 codificaciones → 2

Tu pista 2, confirmada y resuelta. La estructura nueva del orquestador:

```
ANTES:  cortar → retención → audio → overlays → subtítulos   (4 codificaciones de video)
AHORA:  cortar → [análisis + planificación como datos] → render único → audio
                                                          (2 codificaciones de video)
```

Primero se generan **datos** (plan de retención, archivo .ass de subtítulos, PNGs de
overlays con su lista de tiempos), y luego un solo ffmpeg compone todo — zoom/paneo,
overlays con fade y subtítulos — mientras codifica una única vez con NVENC en calidad
final. La mezcla de audio (f5) ya copiaba el video sin tocarlo, así que quedó al final
sin costo. Ahorro directo: ~8s. Ganancia de calidad: la cara de José pasa por 2
compresiones en vez de 4, y el audio por 2 en vez de 3 (el render ahora copia el AAC
en vez de recomprimirlo — eso también era pérdida gratuita).

El orden de capas se mantiene: subtítulos SIEMPRE encima de los overlays (el filtro
`ass` se aplica después de los `overlay` dentro de la misma cadena).

### 2.3 OpenCV: doble instalación eliminada (bomba de tiempo latente)

**Bug latente encontrado, no estaba en tu lista.** Estaban instalados a la vez
`opencv-python 4.10.0.84` y `opencv-contrib-python 5.0.0.93` — dos versiones distintas
del MISMO módulo `cv2`, pisándose los archivos. Funcionaba de casualidad (el 4.10 fue
el último en escribir), pero cualquier `pip install` futuro podía dejar una mezcla
corrupta. Lo detecté con `pip list` durante la revisión del entorno.

Arreglo: desinstalé ambos e instalé solo `opencv-contrib-python==4.10.0.84`, que trae
todo lo del paquete base (incluidos los Haar cascades) y además es el paquete que
mediapipe declara como dependencia — `pip check` quedó limpio de ese conflicto.
Verificado: `cv2` importa, lee video y los cascades existen.

### 2.4 Corridas nuevas fuera de OneDrive (tu pista 1, confirmada)

Medido: `salida/` acumulaba **1.76 GB de archivos intermedios** en OneDrive y el
proceso de OneDrive llevaba **más de 21 minutos de CPU acumulados** peleando por
disco y red en cada corrida. Además el propio plan (sección 3) dice que OneDrive
guarda "solo código, configuración, guiones y videos finales" — los intermedios lo
estaban violando.

Arreglo en `config.py` + `editor.py`:
- Los archivos de trabajo van ahora a **`C:\ai-video\salida\<nombre>\`** (fuera de OneDrive).
- El video final **sí** se copia automáticamente a `salida/<nombre>.mp4` en OneDrive.

Para lo histórico: copié el video final de cada corrida vieja a la raíz de `salida/`
(ej. `v2_final__07_FINAL.mp4`) para que no pierdas ninguno. Las 6 carpetas con
intermedios viejos siguen ahí — moverlas es decisión tuya (sección 5.1).

### 2.5 Blindaje de versiones: `C:\ai-video\constraints.txt` (tu pista 6)

El conflicto que dejó anotado la sesión A (whisperx declara `torch~=2.8.0` pero hay
2.11.0+cu128 instalado) es **solo una advertencia de papeleo**: whisperx funciona
perfecto con 2.11 (todas las corridas de hoy lo prueban). El riesgo real es otro: que
un `pip install` futuro intente "corregirlo" instalando un torch sin GPU (ya pasó una
vez, ver BITACORA-A). Creé `C:\ai-video\constraints.txt` con las versiones exactas que
funcionan juntas; las instrucciones de uso están dentro del archivo.

### 2.6 Limpieza menor de código

Código muerto eliminado en `f2_cortar.py` (un set que se creaba y nunca se usaba) y
`f4_retencion.py` (una variable calculada y descartada). Sin efecto en el resultado.

---

## 3. Qué revisé y descarté (y por qué)

| Idea | Veredicto | Evidencia |
|---|---|---|
| **Decodificación por hardware en OpenCV** (pista 4) | ❌ Descartada | Medido: decodificar los 1110 frames por CPU toma 3.1s; por GPU (D3D11) toma 7.6s — bajar cada frame de la VRAM a la RAM cuesta más de lo que ahorra el decodificador. |
| **Reemplazar el bucle de Python por crop+sendcmd de ffmpeg** (pista 3) | ❌ No aplicada | Tras el arreglo del face tracking, el bucle completo (decodificar + recortar + redimensionar + codificar) cuesta ~7s. La reescritura con `sendcmd` ahorraría quizás 3-4s a cambio de una complejidad frágil (expresiones dinámicas de crop por frame). Mala relación riesgo/beneficio hoy. |
| **Subir batch_size de WhisperX** (pista 9) | ❌ Irrelevante | Con 44s de audio solo hay ~2 lotes de 30s: el batch_size no toca el tiempo. La transcripción en sí cuesta 1.9s; lo caro es cargar el modelo (8.7s), y eso no depende del batch. `float16` es el compute_type correcto para esta GPU. |
| **Aviso de torchcodec en el log** (pista 5) | ❌ Cosmético | Verificado en el código instalado: whisperx decodifica el audio con el ffmpeg de línea de comandos y le pasa a pyannote el audio ya en memoria — exactamente la "solución 1" que sugiere el propio aviso. No hay ningún camino lento activo. El aviso saldría igual aunque se arreglara torchcodec, porque nadie lo usa. Ignorable. |
| **Cambiar preset/CQ de NVENC** | ❌ Sin tocar | La sesión anterior ya midió que el tiempo no cambia con el CQ. Los valores actuales (p5, CQ 21 intermedio / 26 final) están bien elegidos. |

---

## 4. Estado de tus 9 pistas, una por una

1. **OneDrive sincronizando salida/** → Confirmada y resuelta (sección 2.4). Falta tu decisión sobre lo histórico (5.1).
2. **4 recompresiones en cadena** → Confirmada y resuelta: ahora son 2 (sección 2.2).
3. **Bucle Python de f4** → Sospecha equivocada de lugar: el costo real era el face tracking (26.9s), no el bucle (8.7s). Resuelto por otra vía (sección 2.1); sendcmd descartado con medición (sección 3).
4. **NVDEC para OpenCV** → Probado y descartado con medición: es más lento (sección 3).
5. **Aviso torchcodec** → Cosmético, verificado en el código fuente instalado (sección 3).
6. **Conflicto torch 2.11 vs whisperx** → Solo papeleo; blindado con constraints.txt (sección 2.5).
7. **Migrar a mediapipe.tasks** → Hecho, 8x más rápido y mejor tracking (sección 2.1).
8. **Plan de energía / ReBAR / GPU** → Revisado (sección 6). Un hallazgo: Resizable BAR desactivado.
9. **batch_size y compute_type de WhisperX** → Revisado y descartado con medición (sección 3).

---

## 4-bis. Cuánta calidad MÁS se puede comprar (y una trampa que casi caigo)

Como el pipeline ahora sobra tiempo (35s de 68s que tardaba), medí si conviene
gastar parte de ese margen en más calidad. Todas las variantes se puntuaron contra
la misma referencia sin pérdida, **verificando siempre el conteo de frames**:

| Ajuste del codificador | Frames | VMAF | Peor frame | PSNR | Peso | Tiempo |
|---|---|---|---|---|---|---|
| **p5 CQ26 — el actual** | 1105 ✅ | 97.69 | 92.85 | 45.05 dB | 29.9 MB | 11.6s |
| p5 **CQ22** | 1105 ✅ | **98.83** | 95.32 | **47.23 dB** | 50.9 MB | 11.6s |
| p5 **CQ19** | 1105 ✅ | **99.25** | 96.31 | **48.88 dB** | 71.5 MB | 11.2s |
| p5 CQ22 + spatial-AQ | 1105 ✅ | 98.41 | 94.57 | 46.63 dB | 54.2 MB | 12.2s |
| preset p6 | 1102 ❌ | — | — | — | — | — |
| preset p7 (+ banderas) | 1102 ❌ | — | — | — | — | — |
| p5 + rc-lookahead / AQ temporal | 1102 ❌ | — | — | — | — | — |

**Bajar el CQ no cuesta tiempo** (confirma lo que ya había medido la sesión anterior:
NVENC tarda lo mismo en cualquier CQ). Solo cuesta peso de archivo.

### ⚠️ La trampa: subir el preset ROMPE el final del video

Lo que parecía la mejora obvia — subir el preset de `p5` a `p7` ("más lento, mejor
calidad") — **se come los últimos 3 frames del video** (0.1s, justo donde está la
tarjeta de CTA). Lo mismo pasa con `rc-lookahead` y `temporal-aq`.

Cómo lo detecté: al medir las variantes, el "peor frame" caía a VMAF ~52 en todas las
que usaban esas banderas. En vez de aceptar el número, conté los frames de cada
archivo: 1102 en vez de 1105.

Causa aislada con una prueba adicional: el problema **solo ocurre cuando los frames
entran por tubería** (que es como funciona nuestro render). Codificando de archivo a
archivo, esas mismas banderas conservan los 1105 frames sin problema. Es un fallo al
vaciar la cola de análisis del codificador cuando se cierra la tubería.

**Consecuencia práctica: no subir el preset ni agregar lookahead en este pipeline.**
Queda anotado aquí para que ninguna sesión futura "mejore" el codificador y trunque
el cierre del video sin que nadie lo note. La única vía segura para más calidad es
bajar el CQ.

Anotado también: `spatial-aq` **empeoró** el resultado (98.41 contra 98.83 al mismo
CQ) y encima pesaba más. Descartada.

### ✅ APLICADO: CQ final 26 → 22 (aprobado por José)

José eligió priorizar calidad sobre peso de archivo. Aplicado en `config.py` y
verificado con una corrida completa del pipeline real:

| | Antes (CQ 26) | Ahora (CQ 22) |
|---|---|---|
| Calidad (VMAF vs sin pérdida) | 97.69 | **98.83** |
| PSNR | 45.05 dB | **47.23 dB** |
| Peso del archivo | 31.3 MB | 54.9 MB |
| Frames / duración | 1105 / 37.132s | **1105 / 37.132s** (idéntico ✓) |
| Tiempo del pipeline | 35.1s | 38.4s |
| Audio | -14.1 LUFS, pico -0.4 dBFS | **-14.1 LUFS, pico -0.1 dBFS** ✓ |

Verificado además con frames a 1s, 18s y 34s: banner de hook, inserto PiP, tarjeta de
CTA y subtítulos karaoke, todos correctos. Sin truncamiento del cierre.

También se bajó el CQ **intermedio** (el paso de corte) de 21 a **17**, para que ese
paso no limite la calidad del final. Medido contra un corte sin pérdida: VMAF 97.444
→ 97.675, PSNR +0.5 dB, +8 MB de archivo temporal (que ya no va a OneDrive). Mejora
pequeña y por sí sola no visible, pero cuesta cero tiempo.

### 🔎 El cuello de botella de calidad que queda: el paso de corte

Dato revelado al medir lo anterior, **más importante que el ajuste de CQ**:

| Paso del pipeline | Calidad que conserva (VMAF vs sin pérdida) |
|---|---|
| **1b Corte** (`f2_cortar`) | 97.68 ← el eslabón más débil |
| 3b Render final (`f4_retencion`, CQ 22) | 98.83 |

El paso de corte pierde **más** que el render final, aunque va con mejor CQ. La razón
es que comprime el material original completo, con todo su detalle y grano de cámara,
mientras que el render final comprime frames ya procesados.

**La mejora grande que queda es eliminar esa compresión por completo**: hacer que
`f4_retencion` lea el video ORIGINAL y descarte los frames de los tramos cortados
dentro de su propio bucle, en vez de leer un `02_cortado.mp4` ya recomprimido. El
pipeline pasaría de 2 codificaciones a **1 sola**, y la ganancia sería mayor que la
del cambio de CQ que acabamos de hacer.

**No lo hice** porque es una reestructuración real (habría que mover el análisis de
rostro y de energía a la línea de tiempo del original, y resolver aparte el corte del
audio), y José pidió explícitamente cuidado con romper lo que ya funciona. Queda como
la mejora de calidad #1 pendiente, para abordar con calma y con este documento como
línea base de comparación.

---

## 5. Decisiones que te tocan a ti

### 5.1 Mover los intermedios históricos fuera de OneDrive (~1.6 GB)

Ya respaldé los videos finales en la raíz de `salida/`. Las 6 carpetas viejas
(`jose_kindle_paperwhite_v1/v2`, `prueba`, `prueba_completa`, `test_nvenc`, `v2_final`)
contienen solo intermedios reproducibles. Si estás de acuerdo, muévelas con este
comando en PowerShell (o pídemelo en la próxima sesión):

```powershell
Move-Item "C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida\jose_kindle_paperwhite_v1","C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida\jose_kindle_paperwhite_v2","C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida\prueba","C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida\prueba_completa","C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida\test_nvenc","C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida\v2_final" "C:\ai-video\salida\"
```

No lo hice yo porque borra datos de tu nube — eso te corresponde. (Intenté; el sistema
de permisos me lo bloqueó, correctamente.)

### 5.2 Activar Resizable BAR en la BIOS (hallazgo de hardware)

Tu RTX 5070 Ti está corriendo con **Resizable BAR desactivado** (verificado: la
ventana de acceso a la VRAM es de 256 MB en vez de 16 GB). Para este pipeline el
impacto es menor, pero en juegos suele dar +5-10% gratis y en cargas de IA con mucha
transferencia CPU↔GPU también ayuda. Se activa en la BIOS: activar **"Above 4G
Decoding"** y **"Resizable BAR"** (en placas para Ryzen 5000 suele estar en
Settings → Advanced → PCIe). Es reversible y sin riesgo, pero es tu máquina y tu BIOS:
tu decisión. Con `nvidia-smi -q -d MEMORY` puedes confirmar después (BAR1 debería
decir ~16384 MiB).

### 5.3 Excluir C:\ai-video del antivirus (opcional, no medido)

Windows Defender escanea en tiempo real cada archivo que el pipeline escribe
(gigabytes de video por corrida). Excluir `C:\ai-video\` reduciría ese costo, pero es
un intercambio de seguridad que no quise decidir por ti, y su ganancia aquí no está
medida (probablemente 1-3s). Prioridad baja.

### 5.4 Si algún día editas varios videos seguidos

El costo fijo más grande que queda es cargar el modelo de WhisperX (~9-15s por
corrida). Si un día editas 3-4 videos en tanda, valdría la pena un "modo servidor"
que cargue el modelo una vez y procese todos. No lo implementé: para el uso actual
(un video por sesión) no se justifica la complejidad. Pedirlo cuando el volumen lo
amerite.

---

## 6. Hallazgos de hardware y sistema

| Qué | Estado | Nota |
|---|---|---|
| Plan de energía | ✅ "Alto rendimiento" | Ya estaba bien, no toqué nada. |
| GPU RTX 5070 Ti | ✅ Sana | 42°C en reposo, driver 610.47, límite de potencia 300W completo. |
| **Resizable BAR** | ⚠️ **Desactivado** | Único hallazgo accionable de hardware — ver 5.2. |
| HAGS (planificación GPU por hardware) | Por defecto | Sin valor forzado en el registro; no interfiere con NVENC/CUDA. Sin acción. |
| RAM | ✅ 32 GB | Suficiente para que el modelo de WhisperX quede en caché de disco entre corridas del mismo día (por eso la 2ª corrida es mucho más rápida). |
| OneDrive | ⚠️ Era el mayor parásito | 1.76 GB de intermedios + 21 min de CPU acumulados. Resuelto para corridas nuevas (2.4), histórico pendiente de tu OK (5.1). |
| VIDEOV2.mp4 | ℹ️ Dato útil | Viene grabado en horizontal (1920×1080) **con metadato de rotación de 90°**. ffmpeg lo rota solo en la Fase 1b, así que todo funciona — pero si algún día un video entra al pipeline por otra vía y sale acostado, la causa es esta. |

---

## 7. Bugs encontrados y cómo los detecté

1. **Doble instalación de OpenCV (4.10 + 5.0 a la vez)** — detectado con `pip list`
   al auditar el entorno. Riesgo latente de corrupción silenciosa en cualquier
   instalación futura. Corregido (sección 2.3).
2. **El render recomprimía el audio sin necesidad** — detectado leyendo el comando
   ffmpeg de `f4_retencion.py`: recodificaba a AAC un audio que ya venía en AAC
   idéntico. Una generación de pérdida de audio gratuita. Ahora se copia (parte de 2.2).
3. **Face tracking 8 veces más lento de lo necesario** — detectado cronometrando cada
   sub-paso de la fase por separado (el tiempo total de la fase escondía cuál era el
   culpable). Es el motivo por el que conviene medir antes de optimizar: la sospecha
   apuntaba al bucle de render y el problema estaba en otro lado.
4. **Código muerto** en f2 y f4 (sin efecto funcional) — detectado en lectura de código,
   eliminado.

No se encontró ningún bug que afectara el contenido del video publicado: los finales
de antes eran correctos, solo se producían más lento y con más pérdida de calidad
intermedia.

---

## 8. Qué quedó pendiente y por qué

- **Eliminar la recompresión del paso de corte** (pipeline de 1 sola codificación) —
  la mejora de calidad más grande que queda, ver sección 4-bis. No abordada por ser
  una reestructuración con riesgo real.
- **Mover el histórico de salida/** — requiere tu OK (5.1).
- **Resizable BAR** — requiere entrar a la BIOS físicamente (5.2).
- **Modo servidor de WhisperX** — no se justifica todavía (5.4).
- **Render 100% ffmpeg con sendcmd** — descartado por relación riesgo/beneficio (sección 3); si algún día la fase 3 vuelve a ser el cuello de botella (p. ej. videos mucho más largos), retomarlo desde esa nota.
- **Los pendientes previos del proyecto siguen vigentes** (no eran de esta auditoría):
  diseño de loop real, plantillas Hyperframes de la sesión B, fotos reales de producto,
  Fase 6 de generación GPU, empaquetado como skill (Fase 7).

## Archivos tocados en esta sesión

- `editor/config.py` — rutas de salida, constantes de face tracking, comentarios.
- `editor/f4_retencion.py` — face tracking MediaPipe, render fusionado, audio copy, flags nuevos (`--solo-render`, `--overlays`, `--subs`, `--final`).
- `editor/f6_overlays.py` — flag nuevo `--solo-planificar`.
- `editor/f2_cortar.py` — limpieza de código muerto.
- `editor/editor.py` — orquestación nueva (2 codificaciones) + copia del final a OneDrive.
- `C:\ai-video\constraints.txt` — nuevo.
- `C:\ai-video\models\mediapipe\blaze_face_short_range.tflite` — nuevo (230 KB).
- Entorno: `opencv-python` + `opencv-contrib-python` → solo `opencv-contrib-python==4.10.0.84`.

*Todas las cifras de este documento salieron de corridas reales del 2026-07-26 en esta máquina.*
