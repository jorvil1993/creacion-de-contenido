# Prompt de implementación — Pipeline dirigido por guion (`--guion N`)

> Prompt listo para pegarle a una IA con acceso al repo. Pide **verificación
> antes de escribir código**. Todos los números de línea y afirmaciones de este
> documento fueron comprobados leyendo el código el 2026-07-27; aun así,
> **verificalos de nuevo** antes de tocar nada: la documentación de este proyecto
> ya afirmó una vez que algo existía sin comprobarlo.

---

## Qué se quiere lograr

Hoy el pipeline decide **solo** qué mostrar y cuándo, leyendo palabras clave de
la transcripción. Funciona, pero no sabe nada del guion que José escribió.

Lo que se busca es invertir la relación: José graba siguiendo el **guion 7** del
panel de producción, deja el archivo en `contexto/Guion-7.mp4`, y corre:

```bash
python editor/editor.py "contexto/Guion-7.mp4" --guion 7
```

El pipeline entonces **ejecuta el guion tal cual está escrito en el panel**:
el B-roll que dice el guion, en el momento que dice el guion, con el sonido que
dice el guion. Y sigue haciendo por su cuenta todo lo que ya hace bien
(transcribir, cortar muletillas y silencios, subtítulos karaoke, punch-ins por
energía, face tracking, loop, render único NVENC).

**La fuente de verdad es `PANEL-PRODUCCION.html`**, en la raíz del proyecto.
Ahí, dentro del `<script>`, vive `const G=[...]` con los 10 guiones de
producción. Cada guion tiene un campo `tl` (línea de tiempo) con filas de la
forma:

```js
['3–5s','Es que compites contra una app…','B-ROLL','F16 a pantalla completa','pop','entra 02-lofi a −20 dB']
//  0=momento   1=lo que dice           2=tipo    3=qué se ve            4=sonido  5=música
```

Los tipos de la columna 2 son: `YO` (solo la grabación cruda), `PIP` (recuadro
chico arriba), `B-ROLL` (pantalla completa) y `ANIM` (tarjeta de marca).

---

## Lo que YA existe y funciona — usarlo, no reinventarlo

El pipeline **ya acepta órdenes explícitas** que reemplazan por completo sus
decisiones automáticas. Esto es la mitad del trabajo ya hecho:

| Flag de `editor.py` | Qué reemplaza | Formato de cada entrada |
|---|---|---|
| `--sfx-manual JSON` | **todos** los SFX automáticos | `{"t": 3.2, "archivo": "pop.mp3", "volumen": 0.8, "razon": "manual"}` |
| `--animaciones-manual JSON` | el disparo de animaciones por palabra | `{"nombre": "tarjeta-cta", "ini": 29.4}` (opcionales: `dur`, `variante`) |
| `--eventos-manual JSON` | qué inserto PIP se muestra y dónde | `{"ini": 3.0, "fin": 5.0, "x": 640, "y": 190, "asset_id": "..."}` |
| `--posiciones-manual JSON` | solo mueve los insertos que eligió el automático | `{"tipo": "...", "ini": 3.0, "x": .., "y": ..}` |
| `--hook "TEXTO"` | el banner de hook de los primeros segundos | string |
| `--reaplicar` | reusa transcripción + corte + plan de retención | — |

Referencias verificadas:
- `editor/editor.py:46-91` — definición de los flags.
- `editor/editor.py:116-129` — `--reaplicar` reusa `01_transcripcion.json`,
  `02_cortado.mp4/.json` y `03_retencion.plan.json`. **Clave para iterar**: sin
  esto cada prueba re-transcribe y re-corta.
- `editor/f5_audio.py:531-540` — `--sfx-manual` sustituye la lista automática
  entera y después llama a `reanclar_sfx()`.
- `editor/f6_overlays.py:1516-1561` — `cargar_animaciones_manual()`. Una lista
  vacía es una orden válida ("este video no lleva animaciones").
- `editor/f6_overlays.py:1164-1170` — con `--eventos-manual` NO se corre el
  disparo automático de insertos ni se toca ComfyUI/Flux.

**Verificación ya hecha (no repetirla):** los **67 nombres de sonido distintos**
que citan las líneas de tiempo del HTML **existen todos** como archivo real en
`assets/sfx/` (`tada_cierre.mp3`, `ui_apagar.mp3`, `riser_reveal.mp3`,
`reverso_3.mp3`, `whoosh_grave_3.mp3`, etc.). No hace falta inventar un mapa de
nombres: el nombre del HTML + `.mp3` es el archivo.

**Punch-ins:** salen de `picos_energia` dentro de `03_retencion.plan.json`, que
`f4_retencion.py:501` lee de disco cuando corre con `--solo-render`. Es decir,
son controlables reescribiendo ese JSON — **pero no hace falta tocarlos**: la
detección por energía RMS ya funciona bien y las filas `YO · Punch-in` del guion
son indicaciones para José al grabar, no órdenes para el pipeline.

---

## Los 6 huecos reales (verificados en el código)

### Hueco 1 — 🔴 Los clips que José ya descargó son invisibles para el pipeline

`editor/f9_generar.py:496-513`, `version_manual_video(tag)` busca
`assets/generado/video/manual/<slug del tag>.mp4`. Pero el **único** sitio que
la llama es `editor/f6_overlays.py:896`, dentro de un bucle donde `tag` sale
siempre de `config.PALABRAS_A_TAGS.get(...)` (línea 893).

`config.PALABRAS_A_TAGS` tiene **29 etiquetas**:
`#agua #bateria #biblioteca #botones #broll #cafe #caja #cama #carga #color
#colorsoft #compacto #comparativa #escribir #estudio #funda #kobo #libros
#ninos #noche #pantalla #paperwhite #protector #regalo #scribe #sol #stylus
#tina #viaje`

Cruzando eso contra los 29 conceptos del banco de clips del HTML: **solo 12
coinciden** (`noche, sol, cama, cafe, viaje, libros, biblioteca, agua, tina,
regalo, bateria, caja`). Los otros 17 **no existen como etiqueta y por lo tanto
nunca se pueden disparar**, entre ellos:

`ojos (F02) · insomnio (F03) · scroll (F14) · tiempo (F15) · abandonado (F16) ·
notificaciones (F17) · ninos-pantalla (F18) · ninos-leyendo (F19) · mama (F20) ·
pareja (F21) · mochila (F22) · entrega (F24) · piscina (F28) · lampara (F29) ·
vitrina (F30) · silencio (F31) · lluvia (F32)`

Ahora mismo en `assets/generado/video/manual/` hay dos archivos:
`abandonado.mp4` y `scroll.mp4` — **los dos están en la lista de los que nunca
se disparan.** El B-roll implementado no se puede probar con lo que hay bajado.

**Consecuencia de diseño:** el mapa `F16 → abandonado.mp4` tiene que salir del
**HTML** (que ya lo define en `const CLIPS={...}`), no de `PALABRAS_A_TAGS`. Con
eso los 29 conceptos funcionan en vez de 12, y de paso desaparece la
ambigüedad de "decir *piscina* devolvía una foto de producto porque el catálogo
tiene 30 fotos etiquetadas `#agua`".

### Hueco 2 — No hay forma manual de pedir un B-roll

El bloque de B-roll (`editor/f6_overlays.py:884-935`) corre **siempre en modo
automático**: recorre las palabras, busca etiqueta, busca archivo. No consulta
ningún JSON y no se puede desactivar.

Y aunque se intentara colar un B-roll por `--eventos-manual`, no funcionaría:
`cargar_eventos_manual()` (`editor/f6_overlays.py:1506-1512`) construye cada
evento **sin copiar las claves `medio` ni `broll_fullscreen`**. Sin `medio`,
`componer_overlays()` (línea 1354-1363) mete el archivo con
`-loop 1 -framerate ... -t`, que es el patrón para **imágenes fijas** — un mp4
por ahí se rompe o se congela.

Las tres ramas de composición a respetar están en
`editor/f6_overlays.py:1369-1392`:
- `ev["broll_fullscreen"]` → escala a 1080×1920 con `crop`, fade de
  `config.BROLL_FADE_S`.
- `ev["medio"] == "video"` → PiP en video, con `setpts` para el offset.
- resto → imagen fija.

### Hueco 3 — No existe el traductor de guion a tiempos reales

**Los segundos de la columna "momento" del HTML (`0–3s`, `3–5s`, …) están
siempre mal y hay que ignorarlos por completo.** No son un dato: son una
estimación que se escribió a ojo al redactar el guion, calculada sobre un ritmo
supuesto de ~3 palabras por segundo. José nunca va a hablar en esos
milisegundos, y encima el pipeline le **corta** silencios y muletillas
(`f2_cortar.py`), así que todo se corre de sitio otra vez después del corte.

Regla para quien implemente esto:

- **La columna de segundos NO se lee. Nunca.** Ni como valor, ni como pista, ni
  como respaldo cuando la alineación falla, ni para "verificar" que el resultado
  es razonable. Si el alineador dice que la frase está en 4.2s y el HTML dice
  `3–5s`, el dato bueno es 4.2s y el del HTML no existe.
- **Lo que SÍ es confiable del HTML es el ORDEN y el TEXTO.** José dice las
  frases en el orden en que están escritas. Esa es la única garantía temporal
  que da el guion, y alcanza (ver la monotonía obligatoria en la sección B).

Hace falta entonces una alineación **por texto**: *dónde, en la transcripción
real ya cortada, empieza la frase que el guion pone en este beat*. El tiempo
sale de la transcripción; del guion sale qué buscar y en qué orden.

### Hueco 4 — El HTML no es legible por máquina

Los guiones viven dentro de `<script>` como `const G=[...]`, array de objetos JS
con strings en comillas simples. Hay que extraerlos.

### Hueco 5 — La columna MÚSICA no tiene implementación (DECIDIDO: no se implementa)

`editor/f5_audio.py:447-450` usa **una sola pista** con
`volume=config.MUSICA_VOLUMEN` y ducking automático por
`sidechaincompress`. No hay automatización de volumen por tramo.

**Decisión ya tomada por José: NO implementarla.** El ducking automático ya baja
la música cuando él habla. La columna "MÚSICA" del HTML queda como **referencia
visual para humanos**; el pipeline la ignora. Lo único que se respeta de esa
columna es la elección de pista si el guion nombra una (p. ej. `02-lofi` →
`assets/musica/02-lofi-brillante.mp3`), vía el parámetro `--musica` que
`f5_audio.py:511` ya acepta. **Ojo:** ese parámetro existe en `f5_audio.py` pero
**no está expuesto en `editor.py`** — verificar y, si hace falta, exponerlo.

### Hueco 6 — El PIP en video existe y funciona; falta el cable

**Corregido tras probarlo de verdad.** La primera versión de este documento decía
que había que construir el PIP en video. Es falso: `render_pip_video()`
(`editor/f12_video_gen.py:539`) **ya hace exactamente eso** y **ya funciona con
clips de Google Flow**, no solo con salida de LTX.

Prueba ejecutada el 2026-07-27 con
`assets/generado/video/manual/abandonado.mp4` (720×1280, 8 s, de Flow):

```
render_pip_video(clip, destino)  ->  tarjeta 420x540, yuva444p12le, 192 frames
```

Recorta al centro con `scale=...:force_original_aspect_ratio=increase` + `crop`
—el mismo encuadre que la versión de foto— y le pone el marco blanco con filo
cian reutilizando las constantes de `f6_overlays`. El resultado se compuso sobre
un frame real y se ve correcto.

**Lo que falta es solo el cable:** hoy `render_pip_video()` únicamente se alcanza
desde `tarjeta_para_tag()` (línea 626), que primero **genera** el clip con LTX.
Nadie la llama con un archivo que ya existe en disco. Hace falta una vía que le
pase la ruta del clip manual y meta el resultado como evento con
`medio: "video"`.

Queda pendiente de verdad la otra mitad: `editor/f6_overlays.py:530` sólo sabe
usar un asset del catálogo `if asset["medio"] == "imagen"`, así que un asset de
video del catálogo se ignora (33 entradas con `"medio": "video"` en
`contexto/catalogo-assets.json`). Para el flujo `--guion` eso no bloquea nada
—el clip se resuelve por código F##/P##, no por catálogo—, pero conviene saberlo.

Importa comercialmente: para productos que necesitan demostrarse, el video
convierte 20-40% mejor que la foto fija.

**Dos datos de la prueba que hay que tener en cuenta al implementar:**

- La tarjeta ProRes 4444 pesa **52,6 MB por 8 s**. Un guion con 4-5 PIP de video
  deja ~250 MB de intermedios por corrida. No es un problema, pero no debe
  sorprender ni acumularse entre corridas.
- El clip de Flow dura 8 s y el beat del guion suele durar 2-3 s: **se ve solo el
  arranque del clip**. Correcto y esperado — no "arreglarlo" haciendo que el clip
  se acelere o se recorte por el medio.

---

## Qué hay que construir

### A) Extractor del guion — `PANEL-PRODUCCION.html` → JSON

Un parser (sugerido: función dentro del módulo nuevo, o
`editor/f13_guion.py::cargar_guiones()`) que lee el HTML de la raíz del proyecto,
extrae `const G=[...]` y `const CLIPS={...}`, y devuelve estructura Python.

- **No** mover los guiones fuera del HTML: José edita ahí y esa es la fuente de
  verdad. El extractor se adapta al HTML, no al revés.
- Cuidado con el Unicode: los momentos usan guion largo (`3–5s`, U+2013), hay
  comillas tipográficas y `−` (menos, U+2212) en la columna de música. Leer
  **siempre** con `encoding="utf-8"` explícito — la consola de Windows es cp1252
  y va a explotar si se imprime sin cuidado (ya pasó durante el análisis).
- Devolver, por guion: `n`, `t` (título), `hook`, y `tl` como lista de dicts con
  claves nombradas (`momento`, `dice`, `tipo`, `ve`, `sonido`, `musica`), más el
  mapa `CLIPS` (`F16 → ('abandonado', descripción, uso)`).

### B) Alineador guion ↔ transcripción real — el corazón del asunto

Entrada: la lista `tl` del guion + `palabras` de `02_cortado.json` (cada una con
`inicio`/`fin` **ya en la línea de tiempo del video cortado** — verificado en
`editor/f2_cortar.py:162-167`, que remapea los tiempos al cortar).

Algoritmo sugerido:

1. Normalizar ambos textos: minúsculas, sin tildes, sin puntuación, sin `…`.
2. Para cada beat del guion, en orden, buscar su frase dentro de la
   transcripción usando `difflib.SequenceMatcher` sobre **listas de palabras**
   (no sobre caracteres: es más robusto a que José cambie una palabra).
3. **Monotonía obligatoria:** la búsqueda del beat *n+1* empieza después del
   índice donde terminó el beat *n*. Sin esto, una frase repetida ("no es que
   no te guste leer" aparece en el hook y en el CTA por el loop) se engancha en
   el sitio equivocado.
4. `ini` = `inicio` de la primera palabra emparejada; `fin` = `fin` de la
   última. El beat siguiente puede acortar el `fin` del anterior si se solapan.
5. Umbral de confianza (sugerido: ratio ≥ 0.6). Por debajo → beat no encontrado.

**Comportamiento con beats no encontrados — DECIDIDO por José:
avisar y seguir.** Se salta ese beat (no se emite su inserto ni su sonido), se
imprime un aviso claro con la frase del guion que no se encontró y con lo que sí
dijo por esa zona, y **la corrida termina bien**. Nunca abortar: José prefiere
tener el video con un inserto de menos que no tener video.

Emitir al final un reporte legible (sugerido:
`salida/<nombre>/10_guion-alineado.md`) con una tabla: beat del guion → tiempo
real encontrado → confianza → qué se emitió. Es lo que José va a mirar para
saber si el guion "entró" bien.

### C) Generador de las 4 órdenes

Con los beats ya fechados, emitir dentro de `salida/<nombre>/`:

1. **`guion.sfx.json`** — un evento por cada beat con columna de sonido no
   vacía: `{"t": <ini del beat>, "archivo": "<nombre>.mp3", "volumen": 0.8,
   "razon": "guion"}`. Ojo: algunas celdas traen prosa ("whoosh_rapido al entrar
   + impacto_grave al sentarte") — extraer **todos** los tokens que sean nombre
   de archivo existente en `assets/sfx/`, e ignorar el resto. Si la celda es
   `—`, no emitir nada. Respetar `config.SFX_SEPARACION_MIN_S`.

2. **`guion.animaciones.json`** — un evento por cada fila `ANIM`:
   `{"nombre": "tarjeta-cta", "ini": <ini del beat>}`. Las plantillas válidas
   están en `plantillas/compositions/` (`tarjeta-cta.html`, `comparativa.html`,
   `anim-sol.html`, `anim-bateria.html`, `anim-moto.html`, `anim-splash.html`,
   `tarjeta-specs.html`, `stickers.html`, `banner-hook.html`,
   `pip-producto.html`). El texto del HTML dice cosas como "tarjeta-cta con el
   hook repetido" → quedarse con el nombre de plantilla.

3. **`guion.eventos.json`** — un evento por cada fila `PIP`. El código
   (`F16`/`P02`) sale de la columna "qué se ve". La posición: si el HTML dice
   "arriba a la derecha" / "arriba a la izquierda", respetarlo; si no, dejar que
   la calcule `_posicion_inserto()` esquivando el rostro.

4. **`guion.broll.json`** (nuevo) — un evento por cada fila `B-ROLL`:
   `{"ini", "fin", "archivo": "<ruta a assets/generado/video/manual/X.mp4>",
   "codigo": "F16"}`.

**Si el archivo de un código no está bajado**, no inventar nada: avisar
("F17 → notificaciones.mp4 no existe, beat 12–14s omitido") y seguir. José baja
los clips a mano y va a tener el banco incompleto durante semanas.

### D) Cablear el B-roll manual (hueco 2)

- Flag nuevo en `editor.py` y en `f6_overlays.py`: `--broll-manual JSON`.
- Cuando viene, **desactivar por completo** el bloque automático de
  `f6_overlays.py:884-935` y usar la lista del JSON.
- Preservar el efecto secundario que ese bloque ya tiene y que importa:
  cada tag con B-roll entra en `tags_reservados` y en `ventanas_ocupadas`, para
  que el mismo concepto no salga **además** como PiP y para que no se pisen
  eventos. Con la lista manual hay que hacer lo mismo.
- Arreglar `cargar_eventos_manual()` para que copie `medio` y
  `broll_fullscreen` cuando vengan en el JSON (hoy los descarta, línea
  1506-1512).
- Respetar `config.BROLL_DURACION_MIN_S` y `config.BROLL_FADE_S`.

### E) Resolver F-code → archivo desde el HTML (hueco 1)

El mapa `CLIPS` del HTML ya dice `F16:['abandonado', ...]`. Usarlo para resolver
la ruta `assets/generado/video/manual/abandonado.mp4`.

**No romper lo que ya existe:** `version_manual_video(tag)` sigue sirviendo para
el modo automático (sin `--guion`). Lo nuevo es una vía paralela por código, no
un reemplazo.

### F) PIP en video — cablear lo que ya existe (hueco 6)

Cuando el guion diga `PIP` y el código resuelva a un `.mp4` de
`assets/generado/video/manual/`, pasarlo por
`f12_video_gen.render_pip_video(clip, destino)` —que ya está probado con
material de Flow— y emitir el evento con `medio: "video"`, `x`, `y` y el
`ancho`/`alto` que devuelve la función. La rama `medio=="video"` de
`componer_overlays()` (línea 1380-1386) lo compone tal cual: **no** lleva
`scale` ni `crop` porque la tarjeta ya viene al tamaño exacto. No agregar
escalado ahí.

**Decisiones ya tomadas por José sobre esto:**

- **Una sola carpeta.** `assets/generado/video/manual/`, sin separar en
  `pip/` y `broll/`. El mismo archivo sirve para las dos cosas.
- **El modo lo decide el GUION, no el archivo.** El mismo `F16` es `PIP` en el
  guion 7 y `B-ROLL` en el 32, desde un único `abandonado.mp4`: para B-roll se
  escala a pantalla completa, para PIP se pasa por `render_pip_video()`. Que un
  concepto aparezca de las dos formas en guiones distintos es **correcto y
  buscado**, no una inconsistencia que haya que "arreglar".
- **La caja del PIP se queda en 400×520** (`config.INSERTO_ANCHO`/`INSERTO_ALTO`).
  Se evaluó agrandarla a 9:16 (357×634) para no recortar nada; José prefirió el
  formato más cuadrado actual. **No cambiar esos valores.**

Nota: los P0X se guardan con su código como nombre (`P02.mp4`), a diferencia de
los F0X que usan el nombre de concepto (`abandonado.mp4`). Está así documentado
en el panel y es intencional.

### G) Enganchar todo: `--guion N` en `editor.py`

`--guion N` debe: extraer el guion N del HTML → correr transcripción y corte
(fases 1a/1b, o reusarlas con `--reaplicar`) → alinear → emitir los 4 JSON →
pasárselos a las fases que ya los aceptan, junto con `--hook` sacado del propio
guion.

**Orden importante:** la alineación necesita `02_cortado.json`, que solo existe
**después** del corte. Así que `--guion` no puede armar los JSON antes de
arrancar; tiene que hacerlo entre la fase 1b y la fase 5a.

Y que siga funcionando todo lo de hoy: sin `--guion`, el comportamiento actual
no cambia en absoluto.

---

## Verificar antes de escribir una sola línea

- [ ] Confirmar que `f6_overlays.componer_overlays()` es de verdad la que
      compone en la corrida normal (rastrear desde `editor.py:152-175`), y no
      la ruta de `f4_retencion.py`. El documento
      `contexto/PROMPT-BROLL-PANTALLA-COMPLETA-Y-PRIORIDAD-MANUAL.md` dejó esa
      duda abierta; ahora `editor.py` pasa `--overlays` a `f4_retencion.py`
      con `--solo-render`, así que **hay dos sitios que tocan overlays** —
      entender cuál hace qué antes de meter mano.
- [ ] Probar el alineador con una grabación real antes de construir lo demás:
      si la alineación no es fiable, todo lo que sigue no sirve. Es el riesgo
      número uno del proyecto.
- [ ] Confirmar con un clip real que `-itsoffset` + `setpts` da el timing
      correcto para un mp4 de Flow (sin canal alfa), no solo para los `.mov`
      ProRes 4444 de Hyperframes.
- [ ] Revisar la tabla de "Trampas conocidas" en
      `.claude/skills/editor-deviceshop/SKILL.md` antes de tocar NVENC o rutas.
      En particular: **no** subir `NVENC_PRESET` de `p5` (pierde los últimos 3
      frames, justo donde va el CTA) y **una sola codificación NVENC por
      corrida**.

## Qué NO hacer

- **No usar los segundos del HTML para nada.** Están mal por diseño (son una
  estimación escrita a ojo) y el corte de muletillas los desplaza todavía más.
  Ni como pista, ni como respaldo, ni como validación. El tiempo sale **siempre**
  de la transcripción alineada. Del guion se usa el texto y el orden.
- **No implementar la automatización de música por tramo.** Decisión tomada.
- **No abortar la corrida** cuando un beat no alinea o un clip no está bajado:
  avisar y seguir. Decisión tomada.
- **No** tocar el comportamiento por defecto: sin `--guion`, todo igual que hoy.
- **No** generar video automáticamente. `config.LTX_HABILITADO` sigue en `False`
  y `--video-ambiente` sigue siendo opt-in. Esto es sobre **consumir** clips que
  José ya generó en Flow.
- **No** mover ni reorganizar `contexto/fotos y videos/` (la usa la página web).
- **No** sacar los guiones del HTML a otro archivo "porque sería más limpio":
  José trabaja sobre ese HTML, es su panel de producción.
- **No** separar la carpeta de clips en `pip/` y `broll/`, ni tocar
  `INSERTO_ANCHO`/`INSERTO_ALTO`. Decisiones tomadas.
- **No** "corregir" que un mismo F## salga como PIP en un guion y B-ROLL en
  otro. Es intencional y el pipeline lo soporta desde un solo archivo.
- **No** asumir que algo existe porque suena lógico —ni que algo falta porque
  no se encontró a la primera. Este documento cometió los dos errores: el hueco
  1 dio por hecho un disparo que no funciona, y el hueco 6 dio por ausente un
  `render_pip_video()` que ya estaba escrito y funcionando. **Probar antes de
  afirmar, en las dos direcciones.**

## Al terminar

Dejar un documento de traspaso con el formato de
`contexto/PROMPT-ARREGLAR-BROLL-LTX.md`: qué quedó funcionando **y cómo se
verificó**, qué quedó pendiente. Y actualizar:

- `.claude/skills/editor-deviceshop/SKILL.md` — el flujo `--guion N` pasa a ser
  la forma normal de trabajar; la tabla de "de dónde sale cada imagen" necesita
  la capa del guion arriba de todo.
- `PANEL-PRODUCCION.html` — el aviso "✅ Integrado en el pipeline" describe el
  disparo por etiqueta; cuando exista `--guion` hay que explicar el flujo nuevo
  y, sobre todo, **corregir la afirmación de que los nombres de concepto
  coinciden con `PALABRAS_A_TAGS`**: solo 12 de 29 coinciden.
