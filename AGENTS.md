# Creación de contenido — pipeline de video

Responde siempre en español.

Convierte una grabación de José hablando a cámara en un video vertical de 30-40s
para TikTok/Reels/Shorts, con la marca de DeviceShop Bolivia. Todo local, sin
servicios de pago.

## Si te piden editar, generar o retocar un video

**Leé primero `editor/COMO-USAR.md`.** Traduce el encargo en lenguaje natural
(«hacé el guion 7», «cambiá la música», «probá cómo queda») al comando y las
banderas que tocan. No inventes banderas: si el pedido no encaja en ninguno de
los casos, preguntá.

Lo más habitual:

```bash
C:\ai-video\venv312\Scripts\python.exe editor/editor.py "entrada/video.mp4" --guion 7
```

Dos cosas que se olvidan y salen caras:

- **`--guion N`** es el número de fila de `PANEL-PRODUCCION.html`. De ahí salen
  el hook, los SFX, las animaciones, los B-rolls, los acercamientos y la música.
  Sin él, el pipeline improvisa desde la transcripción.
- **`--sin-abrir-editor`** en cualquier corrida que no vaya a mirar una persona
  en ese momento. El editor es un servidor y ocupa la terminal hasta Ctrl+C.

Si el que va a hacer el video es José y no un agente, hay dos caminos sin
terminal:

- `editor/Preparar grabación.bat` — elige los clips, los recorta, los ordena y
  arranca el pipeline. Deja un `<video>.preparado.json` al lado de la grabación,
  y **cualquier corrida posterior sobre ese material aplica esos recortes sola**
  — o sea que si un archivo de entrada tiene uno, no hace falta (ni conviene)
  pasar `--desde/--hasta` encima.
- `editor/Panel de producción.bat` — abre el panel de guiones *conectado*: elegir
  la grabación, cambiar cada fila de la línea de tiempo y correr el pipeline
  desde ahí, con el log en vivo.

## Qué hay dónde

- `PANEL-PRODUCCION.html` — los guiones, uno por fila. La fuente de la verdad
  de qué se dice, qué se ve y qué suena. **Un solo archivo con dos modos**: en la
  PC, con `panel_servidor.py` detrás, trae los selectores y el botón de correr;
  publicado en `jorvil1993.github.io/creacion-de-contenido/` (rama `master`,
  carpeta raíz) eso se esconde solo y queda la página de lectura. Al escribir
  sobre él, respetá los CRLF y ubicá las filas por posición (guion, fila) y no
  por su texto: hay campos con comillas escapadas en el fuente.
- `editor/` — el pipeline (`editor.py` orquesta, `f0`…`f13` son las fases), la
  pantalla de preparación (`f0_preparar.py` + `f0_servidor_preparar.py`), el
  editor visual (`f11_servidor.py`) y el panel conectado
  (`panel_servidor.py`). Las transiciones entre cortes viven en
  `f2b_transiciones.py` (se hornean en `f2_cortar`) y las animaciones de entrada
  y salida de los PiP en `f4b_pip_anim.py` (se aplican en el render de
  `f4_retencion`). Ambas se controlan desde el panel «Transiciones y
  animaciones» del editor. Ver `editor/COMO-USAR.md`.
- `contexto/` — catálogo de assets, voz de marca, banco de hooks.
- `assets/` — fotos, música, SFX, plantillas de animación y los clips de Google
  Flow en `assets/generado/video/manual/`.
- `entrada/` — grabaciones crudas. `salida/` — los videos publicables.
- Los intermedios viven **fuera de OneDrive**, en `C:\ai-video\salida\<nombre>\`.

## Antes de dar por bueno un cambio en el pipeline

```bash
python editor/test_regresion.py
python editor/test_align.py
```

La primera caza la clase de fallo que no da error: el video sale igual, pero sin
los B-rolls o con los sonidos cambiados. Si tocás algo del recorrido
editor → render, añadí ahí la prueba.
