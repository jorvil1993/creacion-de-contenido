# Traspaso — Lo que está MAL en el B-roll generado con LTX 2.3

> Escrito el 2026-07-27. LTX 2.3 quedó **instalado, integrado y funcionando**:
> eso no hay que rehacerlo. Este documento es solo lo que salió mal y lo que
> quedó sin verificar. El repo está limpio y todo commiteado (13 commits).

---

## 0. Lo que SÍ funciona — no tocarlo

- LTX 2.3 22B distilled-1.1 en GGUF Q4 genera video real en la RTX 5070 Ti.
  **2.5 a 4 minutos por clip** de 3 s a 704×1280, con 13-14 GB de RAM libres.
- `editor/f12_video_gen.py` (texto-a-video e imagen-a-video), integrado en
  `f6_overlays.py` con la bandera `--video-ambiente`. **Apagado por defecto**
  (`config.LTX_HABILITADO = False`).
- El conversor a tarjeta de PiP (`render_pip_video`) produce ProRes 4444 con
  alfa, 420×540, esquinas redondeadas idénticas al PiP de foto. Verificado
  mirando frames y el canal alfa por separado.
- **Camino por defecto intacto**: sin la bandera, el plan de overlays es
  idéntico byte a byte al de antes (verificado con un control sobre
  `FINAL_integracion`: 9 eventos, 0 diferencias).
- `torch 2.11.0+cu128` con `sm_120` sobrevivió a la instalación de
  `diffusers`/`accelerate`/`timm`. Flux sigue generando (29.4 s, imagen nueva).
- `C:\ai-video\constraints-comfy.txt` existe y protege a `venv-comfy`.

Documentación de uso: `contexto/GUIA-VIDEO-LOCAL.md`.
Bitácora de la instalación: final de `contexto/BITACORA-INTEGRACION.md`.

---

## 1. EL PROBLEMA GRANDE — 12 de 14 conceptos sin verificar

`config.LTX_PROMPTS_POR_TAG` tiene **14 conceptos**. Solo **2 están mirados**:

| Concepto | Estado |
|---|---|
| `#sol` | ✅ limpio y bueno — ramas moviéndose, luz cálida, sin texto |
| `#libros` | ✅ limpio **después de arreglarlo** (ver §2) |
| `#tina` | ❌ **ROTO** — subtítulos falsos quemados (ver §2) |
| `#agua`, `#bateria`, `#biblioteca`, `#broll`, `#cafe`, `#cama`, `#estudio`, `#noche`, `#playa`, `#regalo`, `#viaje` | ⚠️ **NUNCA GENERADOS NI MIRADOS** |

**Esta es la tarea principal.** Generar los 11 restantes de a uno, mirarlos, y
arreglar el prompt del que salga mal. Cada uno cuesta ~3 minutos:

```bash
C:\ai-video\venv312\Scripts\python.exe editor/f12_video_gen.py --tag "#cafe"
```

Después extraer 3 fotogramas **seleccionando por número** y **mirarlos** —
`-ss` antes de `-i` devuelve un cuadro liso:

```bash
ffmpeg -y -i <clip> -vf "select='eq(n,36)'" -frames:v 1 frame.png
```

---

## 2. El defecto concreto: SUBTÍTULOS FALSOS QUEMADOS

`#libros` y `#tina` generaron clips con **texto tipo subtítulo quemado en la
imagen**, en párrafos ilegibles ("Tincera you perscods?", "Neicsı hea po thı
tperza"). El modelo imita el material con el que se entrenó, que viene
subtitulado.

**Lo que NO lo arregla** (probado y medido):

- Reforzar `config.LTX_PROMPT_NEGATIVO` con `subtitles, captions, closed
  captions, burned-in text, overlay text, title card, lower third, letters,
  words`. Se hizo, se volvió a generar, y **volvió a salir con texto**. El
  negativo reforzado quedó igual porque no estorba, pero no resuelve esto.

**Lo que SÍ lo arregló en `#libros`:** reencuadrar el prompt como **MACRO de
textura** en vez de una escena narrable. Antes:

```
pages of a thick hardcover book turning slowly on a table, dramatic side light
```

Después (limpio, verificado):

```
extreme macro close-up of the stacked paper edges of a thick book,
warm side light grazing the paper texture, shallow depth of field, very slow drift
```

**La hipótesis a aplicar al resto:** cuanto más se parezca el prompt a "un video
narrado sobre X", más probable es que aparezca texto. Un macro de textura no se
parece a un video narrado.

**`#tina` sigue roto.** Su clip actual
(`assets/generado/video/auto/tina_daaf3cb6db0b.mp4`) tiene los subtítulos falsos
Y además no se lee como una tina ni como agua. Hay que reescribirle el prompt y
volver a mirarlo.

⚠️ **La caché**: `_clave()` en `f12_video_gen.py` incluye el prompt positivo Y
el negativo, así que cambiar cualquiera de los dos genera un archivo nuevo. Pero
el prompt positivo se arma con `contexto_guion` (la frase alrededor de la
palabra en el video), así que el mismo concepto en dos videos distintos da dos
clips distintos. Para probar suelto, usar siempre el mismo `--guion` o ninguno.

---

## 3. `#sol` nunca llega a generarse en un video real

Verificado en la corrida `VIDEOV2_broll`, midiendo las ventanas de tiempo:

```
sol   28.96-31.76s   BLOQUEADO por cta (30.67-37.17s)
```

José dice "sol" a los 28.96 s y el CTA entra a los 30.67 s. Un inserto dura
`config.INSERTO_DURACION_S = 2.8` s y **no entra**. La animación dibujada de sol
dura 2.6 s y sí entra — el colocador de animaciones además la adelanta 0.89 s
para que quepa completa (esa lógica ya existe en `f6_overlays.py`, busca
"adelantada").

Por eso `_cede()` deja la animación en su sitio, que es lo correcto: **una
animación solo cede al video si el clip cabe donde iría**. Sin esa comprobación
ese momento quedaba sin animación Y sin clip (8 overlays en vez de 9).

**Lo que falta decidir** (es decisión de José, no técnica):

1. Aceptar que en este guion el sol lo cuenta la animación dibujada.
2. Darle a los insertos de video el mismo trato que a las animaciones: poder
   adelantarse para entrar antes del CTA. **Ojo:** eso cambia la colocación de
   TODOS los insertos, no solo los de video — hay que verificar que no rompa el
   camino por defecto con el control de §0.
3. Que José mencione el sol antes en el guion.

---

## 4. `#agua` tampoco entra, por otro motivo

Misma corrida, mismas mediciones:

```
resistente  17.69-20.49s  BLOQUEADO por anim-bateria (16.03-18.43s)
agua        18.27-21.07s  BLOQUEADO por anim-bateria (16.03-18.43s)
piscina     20.91-23.71s  BLOQUEADO por el clip de #tina (20.03-22.83s)
```

La animación de batería ocupa la franja donde se dice "resistente al agua", y
para cuando llega "piscina" ya entró el clip de `#tina` y la regla de
`INSERTO_SEPARACION_MIN_S = 4.0` s corta.

O sea: el agua **sí** está representada en el video final (por el clip de
`#tina`), pero ese clip está roto (§2). Arreglando `#tina` se arregla también
esto. Si se quisiera específicamente piscina y no tina, hay que mirar el orden
de prioridad, no el generador.

---

## 5. Sin verificar: dos movimientos de cámara peleándose

El imagen-a-video desde foto real **funciona bien** (probado con la caja del
Colorsoft 32GB: el logo de amazon, "Signature Edition", "Metallic Black" y las 9
portadas siguen siendo los de la foto). Pero el modelo **agrega un acercamiento
propio** pese al `static camera` de `config.LTX_PROMPT_ESTILO`.

`f4_retencion` ya hace punch-ins. **Nunca se probó un render real con un PiP de
imagen-a-video encima**, así que no se sabe si los dos movimientos se pelean.
Vale la pena mirarlo antes de usarlo en un video de verdad.

---

## 6. Roto pero sin consecuencia (por ahora)

`custom_nodes/ComfyUI-LTXVideo` **no importa** con ComfyUI 0.28.0:

```
cannot import name 'interleaved_freqs_cis' from 'comfy.ldm.lightricks.model'
```

No bloquea nada porque el workflow de `f12_video_gen.py` usa **solo nodos del
core más ComfyUI-GGUF** — fue una decisión de diseño deliberada y resultó
acertada. Pero deja fuera `LTXVTiledVAEDecode`, `LTXVPromptEnhancer` y los
samplers avanzados de ese repo, por si algún día hacen falta. Se arregla
actualizando el custom node, no el core.

---

## 7. Trampas ya pagadas EN ESTA TAREA — no repetirlas

1. **`Get-ChildItem`/`dir` de Windows miente con archivos abiertos.** Reporta el
   tamaño cacheado de la entrada de directorio, que para un archivo que está
   creciendo se queda congelado. Costó **matar una descarga sana** que iba por
   7.24 GB. Medir con `os.stat` de Python, tomando dos muestras separadas 20-30 s
   dentro del mismo proceso.
2. **`-loop 1` sobre un PNG en un `filter_complex` es un stream INFINITO** y pasa
   a mandar sobre el video; `-shortest` no lo frena. Escribió **39 GB** con 1h24m
   de video a partir de un clip de 10 s. La imagen va como un solo fotograma y
   `overlay` la sostiene con su `eof_action=repeat`. `render_pip_video` tiene
   además un tope duro de 15 s con `-t`.
3. **Ceder una animación al video "por etiqueta" no funciona.** "tina" y
   "directo" también disparan `splash` y `sol` sin llevar esa etiqueta, así que
   la animación seguía ocupando la franja y el clip se caía por solapamiento. Se
   declara por **nombre de animación** (`config.LTX_ANIMACIONES_CEDEN_AL_VIDEO`)
   y las etiquetas se derivan.
4. Todo lo de la §5 de `PLAN-EDITOR-VISUAL-V2.md` sigue vigente: `NVENC_PRESET`
   en `p5`, nada de `stdout=PIPE` sin lector, contar frames antes de medir
   calidad, `pip install` siempre con `-c`.

---

## 8. Cómo verificar que no se rompió nada

Control obligatorio después de cualquier cambio en `f6_overlays.py`. Tiene que
dar **9 eventos y 0 diferencias** contra el guardado:

```bash
cd editor
C:\ai-video\venv312\Scripts\python.exe f6_overlays.py \
  "C:/ai-video/salida/FINAL_integracion/02_cortado.mp4" \
  "C:/ai-video/salida/FINAL_integracion/03_retencion.plan.json" \
  "C:/ai-video/salida/FINAL_integracion/02_cortado.json" \
  --solo-planificar "C:/ai-video/salida/_prueba_tarjeta/control_nuevo.json" \
  --nombre-video FINAL_integracion
```

y comparar contra
`C:\ai-video\salida\_prueba_tarjeta\eventos_control.json`.

Corrida completa con B-roll (reutiliza transcripción y corte):

```bash
C:\ai-video\venv312\Scripts\python.exe editor/editor.py "contexto/VIDEOV2.mp4" --nombre VIDEOV2_broll --video-ambiente --sin-editor-visual --reaplicar
```

El render bueno tiene **1105 frames**. Si da otro número, algo se rompió.

---

## 9. Datos del entorno

```
Intérprete del pipeline : C:\ai-video\venv312\Scripts\python.exe
Intérprete de ComfyUI   : C:\ai-video\venv-comfy\Scripts\python.exe
ffmpeg/ffprobe          : %LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*-full_build\bin
                          (config.py ya lo agrega al PATH si falta)
GPU  : RTX 5070 Ti · 16 GB · sm_120
RAM  : 32 GB — LTX quiere >18 GB LIBRES (config.LTX_RAM_LIBRE_MINIMA_GB)
Pesos de LTX (33.7 GB)  : comfyui/models/{unet,text_encoders,vae,checkpoints}/
```

Geometría de los clips: `704×1280`, `73` frames a `24` fps (múltiplo de 32 en
ancho/alto, múltiplo de 8 más 1 en frames).

**El audio que genera LTX se descarta a propósito** — el modelo es audio-video y
el sampler recibe la pareja (video, audio) como un solo latente, pero el audio
nunca se decodifica. No "arreglar" eso.
