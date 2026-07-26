# Plan — Editor visual v2 (colección de PiP, animaciones y ciclo cerrado)

> **Para quien ejecute esto (Sonnet u otra sesión).** Este documento es
> autosuficiente: contiene el estado verificado del pipeline, las decisiones ya
> tomadas por José (no volver a preguntárselas), la especificación de cada fase
> con su criterio de aceptación, y las trampas ya pagadas que no hay que volver
> a pisar. Léelo entero antes de escribir código.
>
> Fecha de redacción: 2026-07-26, ~14:20.
> Fuentes de verdad relacionadas: `contexto/PLAN-EDITOR-VIDEO.md` (plan original
> del pipeline), `contexto/BITACORA-INTEGRACION.md` (la sesión que construyó el
> editor v1), `contexto/MEJORAS-PENDIENTES.md` (feedback de José),
> `contexto/AUDITORIA-OPTIMIZACION.md` (mediciones de calidad y codificación).
> Si algo aquí contradice a esos documentos, **gana el más reciente** y hay que
> anotar la contradicción en la bitácora.

---

## 0. Aviso de concurrencia — leer primero

Este plan se escribió **mientras otra sesión modificaba `editor/`**. Marcas de
tiempo verificadas ese mismo día:

| Archivo | Última escritura |
|---|---|
| `editor/f9_generar.py` | 13:09 |
| `editor/f6_overlays.py` | 13:03 |
| `editor/editor.py` | 13:04 |
| `editor/f10_editor_visual.py` | 13:05 |
| `contexto/BITACORA-INTEGRACION.md` | 13:18 |

**Antes de tocar nada:** volver a mirar esas marcas de tiempo y leer el final de
`BITACORA-INTEGRACION.md`. Si hay escrituras posteriores a las de arriba, otra
sesión sigue trabajando — coordinar con José antes de editar los mismos
archivos. Este plan asume el estado del código a las 14:20.

---

## 1. Qué YA existe (verificado leyendo el código, no asumido)

La sesión de integración cerró los 8 puntos de `MEJORAS-PENDIENTES.md`. Lo
relevante para este plan:

### 1.1 El editor visual v1 ya existe

`editor/f10_editor_visual.py` (21 KB) genera **un HTML autocontenido por
corrida** (`09_editor-visual.html` en la carpeta de trabajo). Ya se ejecutó:
existen salidas en `C:\ai-video\salida\integrado_v1\` y `\FINAL_integracion\`.

Qué hace hoy:

- Pista de tiempo con la transcripción palabra por palabra.
- Marcadores de SFX **arrastrables**, reconstruidos con la misma función que usa
  el pipeline real (`f5_audio.construir_eventos_sfx(plan, eventos)`).
- Selector con los 13 MP3 de `assets/sfx/` **embebidos en base64** y botón de
  escuchar — elegir de oído funciona.
- Botón "+ Agregar en el centro" para crear un SFX nuevo.
- Sección de posiciones: por cada inserto movible, un **fotograma estático** del
  video (extraído con ffmpeg en `ev["ini"] + 0.2`) con el PNG del overlay encima,
  arrastrable.
- Exporta `ajustes.sfx.json` y `ajustes.pos.json`.

Qué **no** hace (y es justo lo que José pidió después):

- **No deja cambiar cuál asset se muestra.** Solo mueve el que ya eligió el
  automático. No hay colección ni selector.
- **No deja agregar un PiP nuevo** en un segundo arbitrario. Solo agrega SFX.
- **No toca las animaciones.** `recolectar()` las descarta explícitamente con
  `if ev.get("medio") == "video": continue` (f10_editor_visual.py:88).
- **No reproduce el video.** Fotogramas estáticos, sin zoom/paneo ni movimiento.
- **No re-renderiza.** Exporta JSON y muestra un comando para pegar en la
  terminal.

### 1.2 El contrato de datos, ya abierto por ambos lados

| Flag existente | Módulo | Qué acepta |
|---|---|---|
| `--sfx-manual JSON` | `f5_audio.py`, `editor.py` | reemplaza **toda** la lista de SFX |
| `--posiciones-manual JSON` | `f6_overlays.py`, `editor.py` | **mueve** overlays existentes (solo x/y) |
| `--hook TEXTO` | `f6_overlays.py`, `editor.py` | texto del banner de apertura |
| `--presentador jose\|esposa` | `editor.py` (propagado a f2/f4) | perfil por persona |
| `--sin-generar` | `f6_overlays.py`, `editor.py` | desactiva Flux |
| `--sin-editor-visual` | `editor.py` | omite generar el HTML de f10 |

**Ojo con la distinción que define este plan:** `--posiciones-manual` **mueve**,
no **sustituye**. No existe todavía una entrada que permita cambiar *qué* asset
se muestra, ni añadir o quitar eventos. Eso es lo que hay que construir.

### 1.3 La biblioteca de assets

`contexto/catalogo-assets.json` — 262 assets ya catalogados y etiquetados:

| | |
|---|---|
| Fotos / videos | 229 / 33 |
| **Marcados aptos para PiP (`"pip" in usos`)** | **198** |
| Productos distintos | 41 |
| Fondo: ambiente / blanco / transparente | 225 / 35 / 2 |
| Orientación: horizontal / cuadrada / vertical | 233 / 17 / 12 |
| Con recorte ya generado (`assets/productos/`) | 28 PNG en **15** carpetas |

Cada entrada trae `id`, `ruta`, `producto`, `color`, `tipo`, `medio`,
`orientacion`, `dimensiones`, `fondo`, `usos`, `origen`, `tags`, `revisado`.
**Todo lo que un selector necesita para filtrar ya está escrito.** No hay que
catalogar nada.

### 1.4 Las piezas que hacen barato el selector

- `f6_overlays.render_pip_producto(ruta_foto, ruta_salida, ancho, alto, centrar_en_lienzo=False)`
  → construye la tarjeta de PiP a partir de **cualquier** foto y devuelve
  `(ancho, alto)`. Cambiar de asset = llamar a esta función con otra `ruta`.
- `f6_overlays._elegir_asset(tag, catalogo, ya_usados, producto)` → es la única
  función que hoy decide cuál asset se usa. **El editor no reemplaza el sistema:
  le quita el volante a esta función.**
- `f6_overlays._version_sin_fondo(asset)` → prefiere `assets/productos/<producto>/frontal.png`
  si existe. De ahí sale la advertencia "este asset todavía tiene fondo".
- `f6_overlays._posicion_inserto(w, h, track_rostro, t)` → posición automática
  esquivando el rostro. Sigue siendo el valor por defecto cuando se añade un PiP.

### 1.5 El encuadre final es reproducible en el navegador

Esto es lo que permite un preview exacto y no aproximado:

- `02_cortado.mp4` ya es **1080×1920 @ 30 fps** (verificado con ffprobe).
- El recorte del render final (`f4_retencion.py:374-386`) es una función pura de
  `03_retencion.plan.json`: interpolación lineal de `track_rostro` (`np.interp`)
  para el centro, y `calcular_zoom_en_t(t, planos, picos)` para la escala.
- Como `w_in=1080`, `h_in=1920` y `aspecto_salida = 1080/1920`, resulta
  `w_crop = 1080/zoom` y `h_crop = 1920/zoom`: **un escalado uniforme alrededor
  de (cx, cy), recortado a los bordes**. Se replica con un `transform: scale()`
  en CSS sobre el `<video>`.

Conclusión: el navegador puede mostrar **el encuadre final exacto**, frame a
frame, encima de `02_cortado.mp4`. Lo que ve José es lo que va a renderizar.

---

## 1-bis. ¿Conservar el v1 o empezar de cero? — CONSERVAR

José preguntó explícitamente (2026-07-26) si lo ya construido diverge tanto del
plan como para justificar arrancar de nuevo. **La respuesta verificada es no.**
Lo que hizo la sesión de integración no es un diseño distinto: es la primera
mitad de este mismo diseño, entregada de forma más simple.

| Pieza de v1 | Veredicto | Por qué |
|---|---|---|
| Contrato JSON (`--sfx-manual`, `--posiciones-manual`) | **Se conserva tal cual** | Es exactamente el contrato que este plan necesita |
| `f10.recolectar()` | **Se conserva y se amplía** | Es la capa de datos, independiente de cómo se entregue la interfaz |
| Reconstrucción de SFX con `f5_audio.construir_eventos_sfx()` | **Se conserva** | Garantiza que el editor arranque con lo que de verdad suena hoy |
| Extracción de fotogramas con ffmpeg | **Se conserva** | Sirve igual para el grid del catálogo |
| Timeline, marcadores arrastrables, selector de sonido | **Se porta** | HTML/CSS/JS aprovechable casi entero; solo cambia de dónde llegan los datos |
| Animaciones en Hyperframes/GSAP (`f9`, `anim-*.html`) | **Se conserva** | Mejor que el PIL original; este plan lo asume |
| **Entrega en base64 sin servidor** | **Se reemplaza** | Único punto que no escala: 198 miniaturas + video + MP3 en un solo HTML |

**Es un cambio de transporte, no de arquitectura.** La capa de datos y el
contrato con el pipeline —que es lo caro y lo ya verificado— se quedan enteros.
Empezar de cero tiraría precisamente las piezas que ya funcionan y que costaron
más de acertar.

**Instrucción para quien ejecute:** no reescribir `f10_editor_visual.py`.
Ampliarlo donde haga falta y construir `f11_servidor.py` encima. Si en algún
punto parece más fácil rehacer que reutilizar, **es señal de que hay que
preguntar a José antes**, no de que haya que rehacer.

---

## 2. Decisiones ya tomadas por José — NO volver a preguntar

1. **Orden:** la colección de PiP va **antes** que la mejora de sonidos. Los
   sonidos ya funcionan en v1; elegir el asset correcto cambia más el video.
2. **Filtro por defecto:** el selector abre filtrado **por el producto detectado
   en el video**, con un botón "ver todos" para los 198.
3. **Recortes:** procesar **de una vez** los 26 productos que aún no tienen
   versión sin fondo (ver Fase 0).
4. **Reglas de disparo automático que él quiere garantizadas:**
   - si se dice **agua** (o tina, piscina, lluvia, resistente) → **animación de
     splash**, no una foto de producto;
   - si se dice **sol** → **animación de sol** (hoy no existe, hay que crearla);
   - si se menciona la **Kindle** → se muestra el producto;
   - y en los tres casos, poder **anularlo desde el editor**.
5. **Repetición de un concepto:** si dice "agua" dos veces, la animación sale las
   dos veces, pero **variada** — no la misma toma repetida ni una caída a foto de
   producto. Ver §3b.
6. **La animación de sol es "rayos de sol sobre una Kindle"**, no un sol
   saliendo. El mensaje es el beneficio real del e-ink: la pantalla **sigue
   legible** bajo el sol directo. Ver §3a.
7. **El editor se abre solo al terminar el pipeline, y además puede abrirse a
   mano** cuando José quiera volver sobre una corrida anterior. Ver §5.

**El principio rector, en una frase:** el automático deja de ser un veredicto y
pasa a ser un primer borrador que José corrige. Toda decisión automática debe
ser visible y sobrescribible desde el editor.

---

## 3. Arquitectura de v2

v1 es un HTML autocontenido con todo en base64 y sin servidor. **Ese enfoque no
escala a v2** y hay que decirlo con números: 198 miniaturas + el video para
reproducir (75 MB) + 13 MP3, todo en base64, daría un HTML de cientos de MB que
ningún navegador abre con comodidad.

**v2 usa un servidor local mínimo.** Y por la misma razón que ya está
documentada en `MEJORAS-PENDIENTES.md` línea 280, **un Artifact publicado no
sirve**: el CSP le impide cargar archivos externos, no puede leer
`C:\ai-video\salida\`, no puede escribir de vuelta y no puede disparar ffmpeg.

```
Claude Code ──lanza──> editor/f11_servidor.py   (http.server de stdlib, puerto 8765)
                              │
                              ├── GET  /            interfaz (HTML+CSS+JS planos)
                              ├── GET  /datos       el JSON de recolectar()
                              ├── GET  /video       02_cortado.mp4 o el proxy
                              ├── GET  /catalogo    los 198 aptos para PiP, filtrados
                              ├── GET  /miniatura   miniatura cacheada de un asset
                              ├── POST /tarjeta     renderiza la tarjeta de un asset -> PNG
                              ├── POST /guardar     escribe los JSON de ajustes
                              └── POST /render      dispara el re-render (~45 s)
                                          │
        Navegador ◄───────────────────────┘
```

**Reglas de construcción, no negociables:**

- **Sin dependencias nuevas.** `http.server` de la stdlib, JS plano, CSS plano.
  Nada de npm, ni frameworks, ni CDN (no hay red garantizada y no hay API keys).
- **Reutilizar, no duplicar.** `f11` importa `f10_editor_visual.recolectar()` y
  las funciones de `f6_overlays`. Si `recolectar()` necesita más datos, se
  **amplía** ahí, no se copia.
- **`f10` sigue existiendo** como salida sin servidor (útil para revisar sin
  levantar nada). No borrarlo ni romper su contrato.
- **El servidor solo escucha en `127.0.0.1`.** Nunca `0.0.0.0`.
- **Escritura atómica:** escribir a `.tmp` y renombrar. Si José tiene el JSON
  abierto en otra parte, no debe quedar a medias.

---

## 4. Fases

Cada fase entrega algo usable por sí sola. No pasar a la siguiente sin cumplir
el criterio de aceptación.

### Fase 0 — Preparación (sin interfaz todavía)

1. **Recortar los 26 productos faltantes.**
   `python editor/quitar_fondos.py --por-modelo 2` (el flag ya existe).
   Hoy hay 28 PNG en 15 carpetas de `assets/productos/`; el catálogo tiene 41
   productos. Verificar el resultado a ojo: `rembg` a veces come el borde de una
   pantalla oscura sobre fondo oscuro. Los que salgan mal, anotarlos — no
   forzarlos.
2. **`editor.py --reaplicar`.** Hoy `editor.py` siempre arranca en f1 y
   re-transcribe: 41 s tirados en cada iteración. `--reaplicar` debe entrar
   directo en f6 → f4 → f5 reutilizando `01_transcripcion.json`, `02_cortado.mp4`
   y `03_retencion.plan.json` de la carpeta de trabajo.
   Medido: pipeline completo 93.65 s; f4 solo-render 38.59 s; f6 4.68 s;
   f5 1.66 s. **El ciclo de reaplicar debe quedar en ~45 s.**
3. **Proxy de video para el editor.** `02_cortado.mp4` pesa 75 MB. Generar
   `_editor/proxy.mp4` a 540×960 con `-movflags +faststart` (~5 MB) para que
   arrastrar la línea de tiempo sea instantáneo. El render final **siempre** usa
   el original, nunca el proxy.
4. **Caché de miniaturas del catálogo.** 198 miniaturas de ~200 px en
   `_editor/thumbs/<id>.jpg`. Generar una sola vez e invalidar por mtime del
   archivo original. **Nunca servir los originales al navegador**: hay fotos de
   4000×3000.

**Criterio de aceptación:** `editor.py --reaplicar` sobre una corrida existente
produce un `07_FINAL.mp4` idéntico al anterior (mismo conteo de frames) en ~45 s,
sin volver a transcribir.

---

### Fase 1 — Servidor y preview con encuadre real

1. `editor/f11_servidor.py` sirviendo la interfaz y `/datos`.
2. Reproductor con el **encuadre final reproducido** (sección 1.5): un
   contenedor con proporción 1080×1920 y `overflow:hidden`, el `<video>` dentro
   con `transform: scale(zoom)` y desplazamiento según (cx, cy) interpolados del
   plan. Actualizar en `requestAnimationFrame`, no en `timeupdate` (que dispara
   ~4 veces por segundo y se ve a saltos).
3. Línea de tiempo con la transcripción alineada; clic en una palabra → salta el
   video a ese segundo.
4. Overlays dibujados encima como `<img>` posicionados en el mismo espacio de
   coordenadas 1080×1920, respetando `ini`/`fin`.

**Criterio de aceptación:** pausar en cualquier segundo y comparar la pantalla
del navegador con el fotograma correspondiente de `06_video.mp4` extraído con
ffmpeg. El encuadre y la posición de los overlays deben coincidir. **Verificarlo
con al menos 3 momentos distintos, uno de ellos dentro de un punch-in.**

---

### Fase 2 — La colección de PiP (el corazón de v2)

Es lo que José pidió literalmente: *"una colección de PiPs y me deje seleccionar
cuál quiero y en qué tiempo y luego poner otra"*.

1. **Endpoint `/catalogo`**: lee `contexto/catalogo-assets.json`, devuelve los
   que tienen `"pip" in usos` (198), con sus campos de filtrado. **Filtra por el
   producto dominante del video por defecto** (`f6_overlays._producto_dominante`
   ya lo calcula), con "ver todos" disponible.
2. **Grid de selección.** Filtros por producto, tipo (funda / producto /
   accesorio / caja), y tags. **El grid muestra la tarjeta ya renderizada, no la
   foto original** — 233 de los 262 assets son horizontales y la tarjeta es
   vertical (400×520); si José elige mirando la foto cruda, elegirá una cosa y
   saldrá otra. Renderizar la tarjeta bajo demanda vía `/tarjeta` y cachearla.
3. **Marcar los que todavía tienen fondo** (`fondo != "transparente"` y sin
   versión en `assets/productos/<producto>/`). Ofrecer un botón que dispare
   `quitar_fondos.py` para ese producto concreto.
4. **Sustituir**: elegir otro asset para un PiP existente conserva `ini`, `fin` y
   posición; solo cambia la imagen.
5. **Añadir**: crear un PiP nuevo en el segundo que marque José, con posición por
   defecto de `_posicion_inserto()` y duración `config.INSERTO_DURACION_S`.
6. **Quitar**: eliminar el evento de la lista.
7. **Los límites automáticos pasan a ser avisos.** `INSERTOS_MAX = 4`,
   `INSERTO_SEPARACION_MIN_S = 4.0` y la ventana `_libre()` **no deben bloquear**
   en modo manual: se muestran en amarillo ("estás rompiendo la separación
   mínima") y José decide.

**Flag nuevo necesario: `f6_overlays.py --eventos-manual JSON`.**
Distinto de `--posiciones-manual`. Recibe la **lista completa** de eventos y la
usa tal cual, renderizando los PNG que falten (por `asset_id`) y respetando los
que ya existan. Es la entrada que hace posible sustituir, añadir y quitar.
Propagarlo también en `editor.py`.

**Criterio de aceptación:** sustituir el PiP de un segundo concreto por otro
asset del catálogo, añadir uno nuevo en un segundo vacío, quitar un tercero,
re-renderizar, y verificar en el MP4 final que los tres cambios están.

---

### Fase 3 — Animaciones: disparo garantizado y control manual

#### 3a. La animación de sol (nueva)

Hoy **no existe**. `config.ANIMACIONES_POR_PALABRA` solo tiene `bateria`,
`splash` y `moto`. La palabra "sol" sí está en `PALABRAS_A_TAGS` (config.py:349)
pero como `#sol`, que activa **generación de imagen con Flux** (`f9_generar.py`),
no una animación.

Dato concreto: el video de prueba dice *"la pantalla se ve perfecta debajo del
sol directo"* alrededor de los 25.5–29.3 s — y en `08_hoja-sonido.md` ese es
**el único tramo sin ningún evento**. Es literalmente el hueco más plano del
video. Es el mejor caso de prueba posible.

**Decisión de José: son rayos de sol SOBRE UNA KINDLE, no un sol saliendo.**
El mensaje no es "hace sol", es "la pantalla sigue legible bajo el sol directo"
— que es el beneficio real del e-ink frente a una tablet. La animación tiene que
demostrar eso, no ilustrar el clima.

Qué construir:
- `plantillas/compositions/anim-sol.html` siguiendo el patrón de
  `anim-splash.html` / `anim-bateria.html` / `anim-moto.html` (el motor por
  defecto es Hyperframes: `config.USAR_HYPERFRAMES = True`).
- **El dispositivo de la animación es la foto real recortada del producto
  dominante del video**: `assets/productos/<producto>/frontal.png`, que ya viene
  con transparencia gracias a la Fase 0. Dos razones: es el modelo que José está
  vendiendo en ese video concreto, y está documentado que Flux **no sabe cómo es
  un Kindle real** (produce un e-reader genérico creíble). Para el producto
  siempre gana la foto real. Si el producto dominante no tuviera recorte, caer a
  `_buscar_foto_producto_default()` y, en último caso, a una silueta dibujada.
- **La pantalla NO se lava.** Los rayos barren, aparece un destello en el marco,
  y el texto de la pantalla se mantiene nítido — ese contraste *es* el argumento.
  Si al renderizarlo la pantalla se ve apagada o velada, la animación está
  comunicando lo contrario de lo que vende y hay que rehacerla.
- Respaldo en `f7_animaciones.py` con PIL, como tienen las otras tres.
- Registrar en `config.ANIMACION_ETIQUETAS["sol"]` (texto sugerido: *"se lee bajo
  el sol"*) y `config.ANIMACION_DURACION["sol"]`.
- Añadir a `ANIMACIONES_POR_PALABRA`: `sol`, `solazo`, `verano`, `afuera`,
  `playa`, `directo`.
- **Renderizar con `--format mov` (ProRes 4444).** Verificado a nivel de píxel
  por la sesión B: el alfa de VP9/webm no se decodifica bien con el ffmpeg del
  pipeline. Está en `plantillas/README.md`.

**Criterio de aceptación propio:** ver el fotograma del medio de la animación sin
contexto y poder decir *"esa pantalla se lee con sol encima"*. Si solo se ve un
sol bonito, no cumple.

#### 3b. Que la animación gane sobre la foto

`BITACORA-INTEGRACION.md` (punto 5.4) documenta el problema exacto: la etiqueta
`#agua` sigue trayendo una foto de producto porque 30 assets del catálogo la
llevan (Kindles resistentes al agua) y la regla acordada es "catálogo primero,
generación como respaldo".

José pidió lo contrario para estos conceptos. La bitácora propone la solución y
esta es la que hay que implementar:

```
config.CONCEPTOS_PREFIEREN_ANIMACION = {"#agua", "#sol", "#bateria"}
```

Para esas etiquetas, la animación gana sobre la foto del catálogo. **No tocar
las etiquetas de los 30 assets** — eso rompería otros usos del catálogo.

Nota verificada: el disparo de animaciones **ya funciona** para la primera
aparición de cada concepto (en `ev_sf.json` de la corrida `cq22` se ven
`anim-bateria` a 13.6 s y `anim-splash` a 17.7 s por la palabra "resistente").
Lo que falla es la **segunda** mención — "tina" a los 20.0 s cayó a una foto
porque `anim_usadas` permite una sola animación por tipo y por video.

**Decisión de José: la segunda mención SÍ lleva animación, pero variada.**
No la misma toma repetida (se lee como error de edición) y tampoco una caída a
foto de producto (es lo que hace hoy y es justo lo que él no quiere).

Cómo implementarlo:
- Quitar el bloqueo de `anim_usadas` como veto absoluto. Sustituirlo por
  `config.ANIMACION_MAX_POR_TIPO` (por defecto **2**), y que al venir del editor
  sea aviso, no bloqueo.
- El motor de Hyperframes **ya tiene variación determinista** por semilla
  derivada del nombre del video (lo implementó la sesión de integración).
  Extender esa semilla para que incluya el **índice de aparición**: la 1ª y la 2ª
  splash del mismo video salen distintas, pero el mismo video renderizado dos
  veces da siempre el mismo resultado. La reproducibilidad no se negocia — es lo
  que permite comparar renders.
- La variación debe ser **visible pero de la misma familia**: otro ángulo de
  entrada, otra cantidad/ritmo de gotas, otra dirección del barrido. No cambiar
  el color de marca ni el concepto.

**Criterio de aceptación:** un video que diga "agua" y luego "tina" produce dos
animaciones de splash claramente distintas entre sí, y ninguna foto de producto
en su lugar. Renderizar dos veces el mismo video da resultados idénticos.

#### 3c. Animaciones en el editor

`f10.recolectar()` las descarta (`medio == "video"`). En v2 deben aparecer en la
línea de tiempo como bloques con su primer fotograma, y poder **quitarse,
moverse en el tiempo y añadirse** eligiendo entre el inventario disponible:

| Fuente | Disponibles |
|---|---|
| `plantillas/compositions/anim-*.html` (Hyperframes + GSAP) | batería, splash, moto, **+ sol** |
| Resto de plantillas de Hyperframes | banner-hook, comparativa, pip-producto, stickers, tarjeta-cta, tarjeta-specs |
| `f7_animaciones.py` (PIL, respaldo) | las mismas, dibujadas con Pillow |

**Limitación honesta que hay que mostrar en la interfaz:** ningún navegador
reproduce ProRes 4444. En el editor las animaciones se ven como **bloque con su
primer fotograma**, no en movimiento. Para verlas animadas hay que renderizar.
Decirlo en la interfaz, no dejar que José lo descubra solo.

**Criterio de aceptación:** en el video de prueba, decir "sol" dispara la
animación de sol en el tramo 25.5–29.3 s; decir "agua"/"tina" dispara splash y
**no** una foto de producto; ambas se pueden quitar desde el editor y desaparecen
del MP4 final.

---

### Fase 4 — Sonidos (evolución de lo que ya hay en v1)

v1 ya cubre lo esencial. En v2 solo hay que:

1. Portar la pista de SFX de `f10` a la interfaz servida (mismo comportamiento,
   mismos datos).
2. Que el SFX se pueda **enganchar a un evento visual** en vez de a un tiempo
   suelto: si José mueve un PiP, su `pop` se mueve con él. Es la regla editorial
   que ya estableció el pipeline ("el sonido acompaña un evento visual",
   config.py:253-272) — mantenerla al editar, no solo al generar.
3. Aviso visual cuando dos SFX queden a menos de `config.SFX_SEPARACION_MIN_S`
   (1.2 s).

**No tocar** los volúmenes de `config.SFX_POR_EVENTO`. Están calibrados tras un
error documentado: se bajaron a 0.30–0.45, quedaron enterrados bajo la voz y
José reportó que "se quitaron todos". Nada debe bajar de ~0.55.

---

### Fase 5 — Ciclo cerrado

1. Botón **Re-renderizar** → `POST /render` → `editor.py --reaplicar` con los
   JSON de ajustes.
2. Progreso en vivo (leer las líneas `render: N/M frames` que ya imprime
   `f4_retencion`).
3. Al terminar, recargar el resultado en el mismo preview para comparar.
4. **Guardar siempre antes de renderizar.** Que un fallo de ffmpeg nunca pierda
   media hora de ajustes.

**Cómo se abre (decisión de José: las dos formas).**

- **Automático:** al terminar `editor.py`, el editor se abre solo. `editor.py` ya
  tiene `--sin-editor-visual` para desactivarlo, así que el default es
  reversible. Debe abrir el navegador en `http://127.0.0.1:8765` **después** de
  copiar el final a `salida/`, nunca antes.
- **A mano:** `python editor/f11_servidor.py "C:\ai-video\salida\<nombre>"` sobre
  cualquier corrida anterior, sin volver a procesar nada. Este es el modo que
  usará más: volver sobre un video de ayer y corregirle un PiP.
- Si el puerto 8765 está ocupado, subir al siguiente libre y **decir en consola
  cuál se usó**. Nunca fallar en silencio ni matar el proceso que estaba.

**Criterio de aceptación:** José hace tres cambios (un PiP sustituido, una
animación quitada, un sonido movido), pulsa un botón, y ve el video corregido sin
tocar la terminal. Y puede reabrir una corrida de días atrás con un solo comando.

---

## 5. Trampas ya pagadas — no volver a pisarlas

Todas están verificadas con mediciones. Repetir cualquiera de ellas es perder
horas ya perdidas por otro.

1. **`NVENC_PRESET` se queda en `p5`.** Con frames por tubería (que es como
   renderiza `f4_retencion`), `p6`/`p7`, `-rc-lookahead` y `-temporal-aq`
   **pierden los últimos 3 frames** — justo donde va la tarjeta de CTA.
   `spatial-aq` empeora la calidad medida (VMAF 98.41 vs 98.83). La única vía
   segura para más calidad es bajar `NVENC_CQ_FINAL`. Detalle en
   `AUDITORIA-OPTIMIZACION.md` sección 4-bis.
2. **Al medir calidad, contar los frames primero.** Un VMAF alto sobre un video
   al que le faltan frames no significa nada.
3. **`pip install` en `venv312` siempre con `-c C:\ai-video\constraints.txt`.**
   torch 2.11.0+cu128 es el único build con sm_120 para la RTX 5070 Ti; pip ya lo
   pisó una vez con un build CPU-only.
4. **Nada pesado a OneDrive.** Los intermedios van a `C:\ai-video\salida\<nombre>\`.
   Hay 1.72 GB pendientes de mover (comando listo en `BITACORA-INTEGRACION.md`
   sección 5.1). El `_editor/` con proxy y miniaturas también va fuera de OneDrive.
5. **No lanzar procesos con `stdout=PIPE` sin leerlo.** ComfyUI imprime ~150
   tipos de nodo al arrancar, llena el buffer del sistema operativo y el hijo se
   bloquea. Igual para ffmpeg. **stdout/stderr van a un archivo.** Documentado en
   `f9_generar.py` y en `f4_retencion.py:355`.
6. **Rutas con acentos, espacios o `:` rompen el filtro `ass=` de ffmpeg.** Por
   eso `f4_retencion` corre con `cwd` en la carpeta del `.ass` y nombres
   relativos. No "simplificar" eso.
7. **Las grabaciones del celular vienen 1920×1080 con metadato de rotación 90°.**
   ffmpeg las rota solo; **OpenCV no**. Cualquier camino nuevo que lea el crudo
   con OpenCV debe rotar a mano.
8. **Medir en PowerShell 5.1:** redirigir salida de python/ffmpeg con
   `cmd /c "... > log 2>&1"`, no con `*>` (convierte stderr benigno en error
   terminante).
9. **Comprobar la herramienta de medición antes de diagnosticar un bug.** Ya pasó
   dos veces: una con el conteo de frames y otra con el splash que "no animaba" y
   resultó ser un comando de verificación mal construido.

---

## 6. Lo que este plan NO incluye

Decirlo explícitamente para que nadie lo dé por prometido:

- **Video como PiP.** Hay 33 videos (24 de B-roll) y serían mejores que cualquier
  foto, pero solo 2 están marcados aptos para PiP y meterlos exige
  preprocesarlos a ProRes 4444 con máscara de esquinas redondeadas, porque el
  compositor (`f4_retencion.py:302`) espera alfa. Va después de v2.
- **Crear animaciones nuevas desde el editor.** El editor elige entre las que
  existen. Crear una nueva sigue siendo trabajo de código.
- **Proyectos multi-video.** Una corrida abierta a la vez.
- **Mezcla de audio real en el preview.** El navegador reproduce el audio del
  corte con los SFX encima; el ducking y el `loudnorm` a −14 LUFS solo existen
  tras pasar por `f5_audio`. Sirve para juzgar *timing*, no *mezcla*.
- **Subtítulos idénticos.** El navegador no usa libass: posición y tiempo serán
  exactos, la tipografía aproximada.
- **Eliminar la recompresión del paso de corte.** Sigue siendo la mejora de
  calidad #1 pendiente (`f2_cortar` mide VMAF 97.68, peor que el render final),
  pero es una reestructuración con riesgo real. **No hacerla dentro de este
  plan.**

---

## 7. Orden de ejecución recomendado

```
Fase 0  (preparación)         ──> sin interfaz, pero ya acelera todo
Fase 1  (servidor + preview)  ──> primer momento "esto es un editor"
Fase 2  (colección de PiP)    ──> lo que más pidió José
Fase 3  (animaciones + sol)   ──> cierra sus tres reglas de disparo
Fase 4  (sonidos)             ──> evolución de v1, menor riesgo
Fase 5  (ciclo cerrado)       ──> el botón que lo vuelve fluido
```

Al cerrar cada fase: **anotar en `contexto/BITACORA-INTEGRACION.md`** qué se
hizo, qué se midió y qué quedó pendiente. Ese registro es lo que ha evitado que
las sesiones se pisen entre sí.

---

## 8. Preguntas abiertas — ninguna

Las tres que quedaban abiertas las respondió José el 2026-07-26 y ya están
incorporadas arriba:

| Pregunta | Respuesta | Dónde quedó |
|---|---|---|
| ¿"agua" dos veces = dos animaciones? | Sí, **variadas** | §2.5 y §3b |
| ¿Cómo es la animación de sol? | **Rayos sobre una Kindle**, pantalla legible | §2.6 y §3a |
| ¿El editor se abre solo o a mano? | **Las dos** | §2.7 y §5 |

**El plan está cerrado y listo para ejecutarse.** Si aparece una duda nueva
durante la construcción, resolverla con el criterio de §2 ("el automático es un
borrador, no un veredicto") y anotarla en `BITACORA-INTEGRACION.md`. Solo parar a
preguntar si la respuesta cambiaría el diseño, no por decisiones de detalle.
