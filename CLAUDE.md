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

## Qué hay dónde

- `PANEL-PRODUCCION.html` — los guiones, uno por fila. La fuente de la verdad
  de qué se dice, qué se ve y qué suena.
- `editor/` — el pipeline (`editor.py` orquesta, `f1`…`f13` son las fases) y el
  editor visual (`f11_servidor.py`).
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
