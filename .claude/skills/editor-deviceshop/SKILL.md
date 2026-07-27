---
name: editor-deviceshop
description: "Convierte una grabación cruda de José (o de su esposa) hablando a cámara en un video vertical de 30-40s optimizado para retención en TikTok/Reels/Shorts, con el estilo de marca de DeviceShop Bolivia. Todo local y gratis. Usar cuando el usuario pida 'edita este video', 'convierte esta grabación', 'hazme un TikTok de [producto]', 'video para DeviceShop', o mencione /editor-deviceshop."
---

# /editor-deviceshop

Pipeline completo y **funcionando de punta a punta**: se le pasa una grabación
cruda y devuelve un MP4 vertical publicable. Todo corre local en la máquina de
José, sin APIs de pago.

Fuente de verdad completa: `contexto/PLAN-EDITOR-VIDEO.md`. Si algo aquí lo
contradice, gana el plan.

---

## Comando

```bash
C:\ai-video\venv312\Scripts\python.exe editor\editor.py "contexto\VIDEOV2.mp4"
```

Correr desde la raíz del proyecto
(`C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido`) y **con el Python
del venv312**, no con el `python` del sistema: el del sistema no tiene torch con
CUDA y la transcripción se caería a CPU.

### Opciones

| Opción | Para qué |
|---|---|
| `--nombre NOMBRE` | Nombre de la corrida. También es la **semilla** de las variantes de animación: mismo nombre = mismo video, siempre |
| `--hook "TEXTO"` | Hook curado en vez del automático. 40 opciones en `contexto/banco-hooks.md`. **Recomendado**: el automático usa la primera frase completa del video, que suele pasar de 7 palabras |
| `--presentador jose\|esposa` | Perfil de quien habla. Cambia muletillas, umbral de silencio y calibración de punch-ins |
| `--sin-generar` | No levantar ComfyUI cuando falte una imagen. La 1ª generación cuesta ~40s de arranque; después va por caché |
| `--video-ambiente` | Los insertos de ambiente salen como **clip de video** (LTX 2.3) en vez de foto fija. **Apagado por defecto**: cada clip son minutos de GPU y conviene tener >18 GB de RAM libres. Ver `contexto/GUIA-VIDEO-LOCAL.md` |
| `--sfx-manual JSON` | Efectos de sonido elegidos a mano (los exporta el editor visual) |
| `--posiciones-manual JSON` | Posiciones de los insertos elegidas a mano (idem) |
| `--sin-musica` | Sin cama musical |
| `--sin-editor-visual` | No generar el HTML del editor al terminar |

### Qué produce

```
C:\ai-video\salida\<nombre>\            (trabajo — FUERA de OneDrive)
  01_transcripcion.json    05_overlays.eventos.json   08_hoja-sonido.md
  02_cortado.mp4/.json     06_video.mp4               09_editor-visual.html
  03_retencion.plan.json   07_FINAL.mp4  <- el bueno
  04_subtitulos.ass
salida\<nombre>.mp4                     (copia final, esta sí en OneDrive)
```

**Regla dura:** los intermedios NUNCA van a OneDrive (sección 3 del plan). Ya
está resuelto en `config.DIR_SALIDA` — no cambiarlo.

### Cuánto tarda (medido el 2026-07-26, RTX 5070 Ti)

| Escenario | Tiempo |
|---|---|
| Todo en caché (Hyperframes + imágenes generadas) | **~35 s** |
| Primera vez con animaciones nuevas | +10-25 s por composición |
| Primera vez con imágenes generadas | +40 s de arranque de ComfyUI, +10-25 s por imagen |

Todo lo caro se cachea por contenido: la segunda corrida del mismo video es
prácticamente inmediata.

---

## Dos presentadores

El sistema soporta a José y a su esposa (`config.PRESENTADORES`). El perfil
cambia lo que **de verdad** depende de la persona:

| | José | Esposa |
|---|---|---|
| Estado | ✅ calibrado con `VIDEOV2.mp4` | ⚠️ **sin calibrar** — valores de partida |
| Muletillas | lista base | base + `ay`, `o sea pues`, `ya` |
| Umbral de silencio | 600 ms | 700 ms (habla más pausada) |
| Percentil de punch-ins | 90 | 88 |

Cuando la esposa grabe su primer video: correr con `--presentador esposa`,
**revisar el corte antes de publicar** (el pipeline avisa por consola de que el
perfil no está calibrado) y ajustar los números en `config.PRESENTADORES`
viendo el resultado real, nunca en teoría.

---

## Qué hace el pipeline, fase por fase

1. **Transcripción** — WhisperX `large-v3` en GPU, timestamps por palabra.
2. **Corte** — silencios >600 ms, muletillas y tomas repetidas. Nunca corta la
   primera ni la última palabra de una frase.
3. **Subtítulos** — `.ass` karaoke: blanco con contorno negro, Poppins Bold,
   2-4 palabras por bloque, al 77% de altura, capitalización tipo oración.
4. **Retención** — face tracking (MediaPipe), punch-ins por energía, zoom
   progresivo, motor de la regla de 5s y **diseño de loop**.
5. **Overlays** — hook, ficha técnica, comparativa, animaciones, insertos, CTA.
6. **Generación en GPU** — Flux.1-schnell cuando el catálogo no tiene imagen;
   LTX 2.3 para clips de ambiente si se pide `--video-ambiente`.
7. **Audio** — música con ducking sidechain + SFX atados a eventos visuales +
   `loudnorm` a −14 LUFS.

Las fases 3b, 5 y 2 se componen en **una sola codificación NVENC** (ver
`contexto/AUDITORIA-OPTIMIZACION.md`): el video se comprime 2 veces en total, no 4.

---

## De dónde sale cada imagen o video (orden de prioridad)

Cuando el guion nombra un concepto (`config.PALABRAS_A_TAGS`):

0. **Clip de video manual** — `assets/generado/video/manual/<etiqueta>.mp4`. Si
   existe, se muestra como **B-roll a pantalla completa** (1080×1920, fade
   suave, voz de José continua, subtítulos visibles encima). Gana sobre TODO.
   El pipeline no genera nada más ni busca fotos para ese concepto.
1. **Foto real del catálogo** — `contexto/catalogo-assets.json`, 262 assets
   etiquetados. Gana siempre para el producto: Flux no sabe cómo es un Kindle
   real, produce un e-reader genérico creíble.
2. **Imagen puesta a mano** — `assets/generado/manual/<etiqueta>.png`. Si a José
   no le gustó lo que generó Flux, aquí deja la suya. Ver
   `contexto/prompts-externos.md`, que se escribe solo con el prompt exacto y la
   ruta donde dejar el archivo.
3. **Clip generado con LTX 2.3** — solo con `--video-ambiente`, y solo para
   conceptos de ambiente. Sale como tarjeta ProRes 4444 con alfa, con el mismo
   marco que un PiP de foto. Si falla, cae solo al paso 4.
4. **Generada con Flux** — solo conceptos de ambiente que ninguna foto cubre:
   sol, cama, café, noche, viaje, libros, biblioteca, estudio.

La semilla del generador sale del hash del prompt, así que **el mismo prompt da
siempre la misma imagen** y queda cacheada en `assets/generado/auto/`.

---

## Reglas duras de retención (detalle en la sección 4 del plan)

- Duración **30-40 s**, nunca 60.
- Primeros 3 s: hook de **≤7 palabras**.
- Cambio visual cada 2-3 s; ningún bloque de 5 s sin corte, zoom, texto o SFX.
- Punch-in en énfasis: la técnica #1 en talking-head vertical (+68% engagement).
- **Loop**: el cierre empata con el arranque. Implementado en dos capas — el
  encuadre vuelve al del primer frame en los últimos 1.2 s, y la tarjeta de CTA
  repite el hook. Medido: el último frame pasó de 12.2 a 20.8 dB de PSNR contra
  el primero.
- El audio de quien presenta es siempre el dominante; la música nunca lo tapa.

## Ficha de estilo (detalle en la sección 5 del plan)

- **Subtítulos:** blanco, bold, contorno negro, tipo oración, 77% de altura.
  **Nunca** de color de marca — la legibilidad manda sobre la identidad.
- **Paleta:** Navy `#0A2A3E` (superficies) · Cian `#4FD1D9` (acentos: palabra
  activa del karaoke, bordes de inserto, íconos) · Blanco (texto).
  Proporción objetivo ~80% metraje real / ~20% superficies de marca.
- **Todos los overlays van en la franja superior (10-35% del alto)**
  (`config.OVERLAY_BANDA_SUPERIOR_PCT`). En un talking-head sentado la cabeza
  ocupa la franja media: cualquier cosa a media altura tapa la cara o el
  producto. Es una decisión ya tomada; cualquier plantilla nueva debe respetarla.
- **CTA sin caja:** contorno negro en vez de recuadro opaco, mismo criterio que
  los subtítulos.

---

## Ajustar un video sin reeditar a mano

Cada corrida deja `09_editor-visual.html` en la carpeta de trabajo. Se abre con
doble clic (es autocontenido, con los sonidos y los fotogramas embebidos) y
permite:

- arrastrar los efectos de sonido sobre la línea de tiempo, con la transcripción
  a la vista, y escucharlos antes de elegir;
- mover los insertos sobre el fotograma real donde aparecen;
- exportar `ajustes.sfx.json` y `ajustes.pos.json`.

Después:

```bash
python editor\editor.py "contexto\VIDEO.mp4" --sfx-manual ajustes.sfx.json --posiciones-manual ajustes.pos.json
```

También existe `08_hoja-sonido.md` para revisar por chat ("el pop de 14.9 s
muévelo a 15.4").

---

## Assets y datos

| Qué | Dónde |
|---|---|
| Catálogo de 262 fotos etiquetadas | `contexto/catalogo-assets.json` (+ `.md` legible) |
| Fichas de producto, objeciones, palabras clave | `contexto/catalogo-productos.md` |
| Banco de 40 hooks por ángulo | `contexto/banco-hooks.md` |
| Fotos de producto sin fondo | `assets/productos/` (generadas con `quitar_fondos.py`) |
| Logo transparente alta resolución | `assets/logo/` |
| Fuentes (Poppins, Montserrat) | `assets/fuentes/` |
| SFX CC0 · música | `assets/sfx/` · `assets/musica/` |
| Plantillas de motion graphics | `plantillas/compositions/` (9 composiciones) |
| Imágenes generadas | `assets/generado/auto/` · manuales en `assets/generado/manual/` |

**No reorganizar `contexto/fotos y videos/`** — esa biblioteca la usa la página
web. Derivar a `assets/productos/`, nunca mover el original.

No copiar aquí el catálogo ni los hooks: viven en esos archivos y se actualizan
ahí. Este skill solo los referencia.

---

## CTA / contacto

- WhatsApp: **69214437** (`config.WHATSAPP_NUMERO`)
- TikTok: **@deviceshopbo** (`config.TIKTOK_HANDLE`)

---

## Trampas conocidas — leer antes de "mejorar" algo

| No hacer | Por qué |
|---|---|
| Subir `NVENC_PRESET` de `p5`, ni añadir `rc-lookahead`/`temporal-aq`/`spatial-aq` | Con los frames entrando por tubería se **pierden los últimos 3 frames** del video, justo donde va el CTA. Medido contando frames. La única vía segura para más calidad es bajar el CQ |
| Renderizar Hyperframes con `--format webm` | El alfa de VP9 no sobrevive con este ffmpeg (verificado a nivel de píxel). Usar **`--format mov`** (ProRes 4444) |
| Rutas `../` en el HTML de las plantillas | Hyperframes resuelve cada composición contra la raíz del proyecto: hay que usar `assets/...` y `compositions/_shared.css`. **Excepción:** dentro de un `.css`, `url()` sí se resuelve relativo al propio CSS, y ahí `../assets/fuentes/...` es lo correcto |
| Lanzar ComfyUI con `stdout=subprocess.PIPE` | Imprime mucho al arrancar; si nadie lee el pipe se llena el buffer y el proceso se **cuelga**. Redirigir a un archivo |
| `pip install` en `venv-comfy` sin `-c C:\ai-video\constraints-comfy.txt` | `diffusers`/`accelerate` pueden pisar `torch 2.11.0+cu128` con un build sin CUDA y dejar **sin GPU a Flux y a LTX a la vez**. Comprobar después: `'sm_120' in torch.cuda.get_arch_list()` |
| Pedirle a Flux o a LTX que dibujen el **producto** | Ningún modelo generativo sabe cómo es un Kindle real. Para el producto, foto real. LTX sí sirve partiendo de una foto real (imagen-a-video): ahí el aparato sigue siendo el tuyo |
| Dar por colgada una descarga porque `Get-ChildItem` no ve crecer el archivo | En Windows el listado del shell devuelve el tamaño cacheado de un archivo abierto. Medir con `os.stat` de Python. Costó matar una descarga sana |
| Hardcodear constantes fuera de `config.py` | Todo parámetro nuevo va ahí |
| Dar por bueno un cambio porque "corrió sin error" | Extraer frames y mirarlos. En este proyecto varias veces el código corrió perfecto y el video estaba mal |

---

## Estado por fase

| Fase | Estado |
|---|---|
| 0 — Entorno | ✅ Python 3.12 + torch cu128 + ffmpeg NVENC + WhisperX, verificado en GPU |
| 1 — Transcripción y corte | ✅ Calibrado con grabación real |
| 2 — Subtítulos | ✅ Estilo agencia, Poppins real |
| 3 — Retención | ✅ Face tracking MediaPipe, punch-ins, zoom, regla de 5s, **loop implementado** |
| 4 — Audio | ✅ SFX por evento visual, ducking, −14 LUFS |
| 5 — Overlays | ✅ 9 composiciones de Hyperframes conectadas + insertos por palabra clave |
| 6 — Generación GPU | ✅ ComfyUI bajo demanda con caché y respaldo manual |
| 6b — Video generado | ✅ LTX 2.3 22B Q4 instalado e integrado, apagado por defecto (`--video-ambiente`). Ver `contexto/GUIA-VIDEO-LOCAL.md` |
| 7 — Este skill | ✅ |

**Pendiente real:** calibrar el perfil de la esposa con su primera grabación.
