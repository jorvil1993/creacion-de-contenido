# Plan de mejoras del editor — bitácora

Archivo compartido entre sesiones. Cada entrada se identifica por el TÍTULO
del bloque (el número puede variar según qué sesión lo esté numerando). No
reordenar ni tocar entradas que no sean tuyas.

---

## BLOQUE — El volumen de los SFX en la previa (es un fallo)

**Estado: hecho.**

### Qué encontré

- El editor carga `07_FINAL.mp4` cuando existe (`f11_servidor.py`, endpoint
  `/video`), que ya trae los SFX mezclados y calibrados (pico común -6dB +
  volumen artístico + loudnorm -14 LUFS).
- El loop del navegador (`loop()`, disparo de SFX en tiempo real) volvía a
  reproducir cada SFX crudo al 100% sin mirar si el video ya los traía
  quemados — de ahí el doble sonido sobre una corrida renderizada.
- `escucharSfx(nombre)` solo declaraba un parámetro: el volumen que le pasaban
  el loop y la tabla se descartaba en silencio. Por eso cambiar el número de
  la columna "volumen" no cambiaba nada audible.
- Un único `Audio()` compartido para toda la previa: dos SFX cercanos se
  cortaban entre sí.
- `/datos` no exponía los picos medidos de cada SFX (`f5_audio._niveles_sfx()`,
  cacheados en `assets/sfx/_niveles.json`), así que el navegador no tenía con
  qué replicar la cuenta del render.

### Qué cambié

- `editor/f10_editor_visual.py` (`recolectar()`): ahora expone
  `niveles_sfx` (el dict completo de picos medidos) y `sfx_pico_objetivo_db`
  (`config.SFX_PICO_OBJETIVO_DB`) en el JSON de `/datos`. Import de
  `f5_audio` subido al tope del módulo (antes se importaba a mitad de función,
  solo en una rama).
- `editor/f11_servidor.py`:
  - `escucharSfx(nombre, volumen)` ahora usa el volumen: calcula
    `ganancia_db = (sfx_pico_objetivo_db - pico) + 20*log10(volumen)` — la
    MISMA cuenta que `f5_audio.mezclar_audio` — y la aplica con un `GainNode`
    de Web Audio API (no con `<audio>.volume`, que no pasa de 1.0 y varios
    SFX del pack necesitan +30dB para llegar al pico común).
    - Pool de 8 `Audio()` + `GainNode` cada uno (`sfxPool`/`poolSfx()`),
      round-robin por índice. Se crean una sola vez (perezoso, en el primer
      `escucharSfx`) porque `AudioContext` necesita un gesto del usuario.
    - El loop de reproducción (`loop()`) ahora solo dispara SFX si
      `!DATA.es_renderizado` — sobre un render, no dispara nada: ya están
      adentro del video.
    - Los tres puntos donde se pedía "escuchar" un sonido de una fila (marcador
      de la línea de tiempo, cambiar el `<select>` de sonido, y el input de
      volumen) ahora pasan `e.volumen` y quedan disparando `escucharSfx` para
      que el cambio se oiga al instante — incluido el input de volumen, que
      antes solo guardaba el número sin reproducir nada.

### Verificación hecha

- `python editor/test_regresion.py` y `python editor/test_align.py`: en verde
  (93 pruebas + la suite de alineación). Sección nueva 10 en
  `test_regresion.py` (`pruebas_sfx_previa`): comprueba por texto fuente que
  el loop respeta `es_renderizado`, que `escucharSfx` ya declara `volumen`,
  que existe el pool y el `GainNode`, y que `f10.recolectar()` sobre una
  corrida sintética trae `niveles_sfx` (141 sonidos) y
  `sfx_pico_objetivo_db == config.SFX_PICO_OBJETIVO_DB`.
- Chequeo de sintaxis del bloque `<script>` completo de `f11_servidor.py` con
  `node --check` — sin errores.
- Levanté el servidor de verdad dos veces (`f11_servidor.py --puerto ... --sin-abrir`)
  contra una copia temporal SIN render (solo `01`..`03`, `05_overlays.eventos.json`,
  `guion.sfx.json` — sin `06_video.mp4` ni `07_FINAL.mp4`) y contra `Guion-7`
  (con `07_FINAL.mp4`), y confirmé por `/datos`:
  - Sin render: `es_renderizado: false`, `niveles_sfx` con 141 entradas, y la
    ganancia calculada a mano para los primeros eventos varía por archivo tal
    como se espera (p. ej. `pop.mp3` a volumen 0.8 da +3.7dB, `whoosh_swoosh_2.mp3`
    al mismo volumen da -6.6dB — el pico real de cada archivo pesa, no solo el
    número de la tabla).
  - Con render: `es_renderizado: true` — el loop ya no dispara nada ahí.
  - La copia temporal de verificación (`_prueba-sfx-raw`) se borró al terminar.
- **Lo que NO pude verificar con oídos propios**: no tengo forma de reproducir
  audio ni tomar captura del navegador en este entorno. Verifiqué la
  aritmética (el mismo `ganancia_db` que usa `f5_audio.py`) y que el dato
  llega correcto al navegador, pero falta que José confirme al oído que:
  (a) una corrida ya renderizada no suena doble, y (b) sobre el corte crudo
  los SFX suenan a un volumen coherente con la tabla y no todos al mismo nivel.

### Archivos tocados

- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque.

---

## BLOQUE — Zona segura de TikTok sobre el reproductor

**Estado: hecho.**

### Qué decidí y por qué

- Constantes nuevas en `config.py`: `ZONA_SEGURA_INFERIOR_PX` (340, ~18% de
  1920) y `ZONA_SEGURA_DERECHA_PX` (160, ~15% de 1080). Documentadas como
  APROXIMADAS (sacadas a ojo de capturas típicas de TikTok/Reels), con nota de
  calibrar contra una captura real más adelante.
- Al primer intento hice la franja derecha de alto completo (0 a 1920) y
  **eso estaba mal**: la probé en el navegador de verdad y el hook (que va
  arriba, `top:300px` en `banner-hook.html`) avisaba "tapado" SIEMPRE, porque
  en TikTok real la columna de íconos (like/comentar/compartir/disco) no
  arranca arriba de la pantalla, arranca a mitad más o menos. Agregué
  `ZONA_SEGURA_DERECHA_DESDE_PCT = 0.45` para que la franja derecha solo exista
  desde el 45% de la altura hacia abajo. Con eso el hook deja de avisar y el
  CTA (que sí baja hasta cerca del 47-100%) sigue avisando — que es lo
  correcto, porque su caja aproximada de verdad se mete ahí.
- Cajas aproximadas de hook y CTA (`ZONA_HOOK_APROX_PX`, `ZONA_CTA_APROX_PX`)
  leídas DIRECTO de las plantillas Hyperframes reales (`banner-hook.html`:
  top 300px, left/right 60px; `tarjeta-cta.html`: top 230px, ancho completo).
  El alto es una estimación generosa (dependen del texto real) — sirven para
  el aviso, no para posicionar nada. Como hook/cta no llevan x/y en el estado
  del editor (son composiciones a pantalla completa con posición fija en su
  plantilla, no arrastrables), no hay otra forma de chequearlos que con una
  caja fija documentada como aproximada.
- Función reutilizable `cajaEnZonaTapada(x, y, ancho, alto)` en
  `f11_servidor.py` (espacio de salida 1080x1920, no píxeles de pantalla):
  hace overlap AABB contra las dos franjas y devuelve `"inferior"`,
  `"derecha"`, `"inferior y derecha"` o `null`. Es la pieza que piden
  reusar los bloques 5 (subtítulos) y 6 (texto destacado) — NO metí el
  chequeo dentro de ninguna función de dibujado.
- Overlay visual: dos franjas semitransparentes con rayas diagonales rojas
  sobre `.lienzo`, con clase `.visible` togggleada por un botón nuevo
  ("🛡 Ver/Ocultar zona segura de TikTok") que recuerda el estado en
  `localStorage` (`zonaSeguraVisible`). `pointer-events:none` para no robarle
  el arrastre a los PiP que queden debajo.
- Aviso en los PiP: extendí `avisosPip()` (ya generaba badges tipo "muy cerca
  del siguiente") para agregar `"tapado por la interfaz de la app (…)"` en
  los PiP que NO son B-roll a pantalla completa, usando el tamaño real y fijo
  de la tarjeta (400x520, `f10_editor_visual.render_tarjeta_catalogo`). Un
  B-roll fullscreen SIEMPRE "tapa" esa zona por definición — avisar ahí sería
  ruido, no información, así que se excluye a propósito.
- Aviso en hook/CTA: dos badges (`hookZonaAviso`, `ctaZonaAviso`) que se
  calculan una sola vez al cargar (`pintarZonaSegura()`, llamada al final de
  `cargar()` después de `pintarHookCta()`), no en cada frame — su posición es
  fija, no depende del tiempo.

### Verificación hecha

- `test_regresion.py` sección 11 (`pruebas_zona_segura`): valida que las
  constantes existen y tienen el tipo/rango correcto, que `recolectar()`
  expone `zona_segura` con los 5 campos y que coinciden con `config`, que
  existe `cajaEnZonaTapada`, que el toggle usa `localStorage`, que un B-roll
  fullscreen NO genera aviso, que hook/cta tienen sus badges, y — el fix del
  falso positivo — que la caja del hook NO llega a la altura donde arranca la
  franja derecha (`hook_y2 <= ALTO * DERECHA_DESDE_PCT`).
- **Abrí el editor de verdad** (`f11_servidor.py` contra `Guion-7`, con
  captura de pantalla vía Edge headless + CDP, ya que no hay entorno gráfico
  interactivo en esta sesión):
  - Screenshot de la página completa: layout intacto, botón nuevo visible,
    nada roto por los cambios de CSS/HTML.
  - Con la zona prendida por click real (no simulado): captura del lienzo
    mostrando las dos franjas rayadas en rojo, con el tamaño correcto
    (17.7% de alto / 14.8% de ancho, exactamente 340/1920 y 160/1080).
  - `edicionPip` real de `Guion-7` trae un PiP en `x:600, y:134`: con el
    tamaño real de tarjeta (400x520) su borde derecho cae en 1000px, más allá
    del límite seguro (920px) — `cajaEnZonaTapada` lo detectó como
    `"derecha"` SOLO, y el badge `"tapado por la interfaz de la app
    (derecha)"` apareció de verdad en el panel de PiP, junto al badge de
    separación que ya existía. Caso real, no fabricado.
  - Con la franja derecha a altura completa (antes del ajuste), tanto hook
    como CTA marcaban `"derecha"` — confirmé que era un falso positivo del
    hook mirando la posición real en su plantilla, apliqué
    `ZONA_SEGURA_DERECHA_DESDE_PCT` y volví a probar en el navegador: el hook
    pasó a `display:none` (sin aviso) y el CTA se mantuvo avisando.
- `node --check` sobre el `<script>` completo extraído: sin errores de
  sintaxis, en cada iteración.
- `python editor/test_regresion.py` (105 pruebas) y `python editor/test_align.py`:
  en verde.

### Archivos tocados

- `editor/config.py`
- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque. Los bloques 5 y 6 pueden reusar
`cajaEnZonaTapada(x, y, ancho, alto)` tal cual está — recibe coordenadas en
el espacio de salida 1080x1920.

---

## BLOQUE — Bajar la densidad de efectos de sonido

**Estado: hecho.**

### Medición previa (antes de tocar nada)

Abrí dos corridas reales de `C:\ai-video\salida\`:

- **`Guion-7`** (`--guion 7`, el caso recomendado por `COMO-USAR.md` — "para
  un video de verdad, pasalo casi siempre"): `08_hoja-sonido.md` decía
  **11 efectos en 24.8s = uno cada 2.25s**.
- **`Guion-7-automatico`** (sin `--guion`, el camino que sí pasa por
  `f5_audio.construir_eventos_sfx`): **10 efectos en 24.8s = uno cada 2.48s**.

Los dos rondaban "uno cada 2.5s", el "tic de editor" que reportó José.

### El hallazgo que cambió el plan

El diagnóstico del bloque apuntaba a `f5_audio.py:223`
(`construir_eventos_sfx`, con sus prioridades hook/overlay/corte/punch-in) como
el lugar del problema. **Es real, pero es solo MEDIO problema.** Encontré que
`--guion N` — el caso normal, el que se usa "casi siempre" — **nunca pasa por
esa función**: `editor.py:296-300` llama a `f13_guion.procesar_guion()`, que
arma su propia lista de SFX leyendo la columna "Sonido" del panel
(`extraer_sfx_de_texto` + `espaciar_sfx`, sin prioridades ni tipos), la
escribe en `guion.sfx.json`, y `editor.py` la inyecta como `--sfx-manual` — el
branch de `f5_audio.py` que **se salta `construir_eventos_sfx` por completo**.

Si hubiera tocado solo `construir_eventos_sfx` y sus constantes de
`config.py`, el arreglo habría quedado bonito en el código y sin ningún efecto
en un render real con `--guion 7`. Por eso el tope global se aplica en LOS DOS
caminos, no solo en el que menciona el diagnóstico.

### Qué decidí y por qué

- `config.py`: `SFX_MAX_PUNCH_INS` 6→2, `SFX_SEPARACION_MIN_S` 1.2→1.8 (los
  dos cambios pedidos, sin más vuelta).
- `config.SFX_DENSIDAD_PRESETS = {"sobrio": 6.5, "normal": 4.5, "cargado": 2.5}`
  — segundos de separación mínima GLOBAL entre cualquier par de SFX, sin
  importar el tipo. "normal" es el que se aplica solo, calibrado contra la
  medición de arriba (11 → ver más abajo).
- `f5_audio.aplicar_tope_densidad(eventos, separacion_s)`: nueva función.
  Ordena por prioridad (`PRIORIDAD_SFX_POR_RAZON`: hook/hook_fisico=100,
  pip-producto/sticker/cta=90, corte=50, punch-in=10; cualquier otra `razon`
  — o sea los `guion_N` del panel — cae en `PRIORIDAD_SFX_DEFECTO=80, entre
  overlay y corte: es una decisión editorial explícita, no ruido) y acepta
  greedy, igual que la resolución de colisiones que ya existía en
  `construir_eventos_sfx` pero con una separación mayor y sin importar el
  tipo.
- `f5_audio.resumen_densidad(eventos, duracion)`: `{n, duracion, cada_s}`.
  `avisos_sfx()` ahora recibe `duracion` (firma cambiada; actualicé sus dos
  llamadores) y agrega un aviso `"densidad"` cuando `cada_s` < preset
  "normal". `escribir_hoja_sonido()` ahora imprime "· uno cada Xs" en el
  encabezado, usando lo mismo.
- **`f13_guion.py`** (el arreglo que de verdad importa): después de
  `espaciar_sfx()`, aplica `f5_audio.aplicar_tope_densidad(..., presets["normal"])`
  y escribe `guion.sfx.json` como `{"sfx": [...ya topado...], "candidatos": [...pool completo...]}`.
  `candidatos` existe para que el selector del editor pueda ofrecer "cargado"
  sin tener que volver a correr el guion.
- **`f5_audio.py main()`**: el branch AUTOMÁTICO (sin `--guion`, sin
  `--sfx-manual`) aplica el mismo tope tras `construir_eventos_sfx()`. El
  branch `--sfx-manual` (que es por donde entra `guion.sfx.json` en un render
  real) **NO vuelve a aplicar el tope** — ya viene topado desde `f13_guion.py`,
  y si además viene de `ajustes.sfx.json` (José editó a mano en el editor,
  quizás con el selector en "cargado") volver a toparlo ahí deshacía su
  elección. Un solo lugar de verdad por camino, nunca doble.
- **`f10_editor_visual.recolectar()`**: lee `candidatos` del JSON si existe
  (lo expone como `sfx_candidatos`); si no existe (automático puro o
  `ajustes.sfx.json` guardado a mano — ahí no hay "pool más ancho" que
  ofrecer), usa el propio `sfx`. También expone `sfx_prioridades`,
  `sfx_prioridad_defecto`, `sfx_densidad_presets` y `resumen_sfx` — todo
  sacado de `config`/`f5_audio`, nunca hardcodeado en el JS (mismo patrón que
  el bloque 1 con los picos de SFX).
- **Editor**: selector de tres posiciones (sobrio/normal/cargado) junto a la
  barra de SFX existente, y un contador `"N sonido(s) en Ds · uno cada Xs"`
  que se pinta en rojo (`.sfx-denso`) cuando queda más denso que "normal".
  `aplicarTopeDensidadSfx(eventos, separacionS)` en JS replica EXACTO el
  algoritmo de Python (prioridad primero, tiempo de desempate). El selector
  **re-filtra siempre desde `edicionSfxCandidatos`** (el pool completo
  guardado en `cargar()`), nunca desde `edicionSfx` ya filtrado — si filtrara
  sobre lo ya filtrado, pasar de "sobrio" a "cargado" no podría recuperar los
  sonidos que "sobrio" descartó. Elegir cualquier preset marca
  `sfxModificado = true` (mismo patrón que `encModificado`/`hookCtaModificado`:
  tocarlo lo vuelve manual, y hay que Guardar para que sobreviva a un
  re-render).

### Verificación hecha

- `test_regresion.py` sección 12 (`pruebas_densidad_sfx`, 17 checks): valores
  de config, que `aplicar_tope_densidad` respeta prioridad (no solo tiempo) y
  la separación pedida, que topar una densidad sintética IDÉNTICA a la medida
  en `Guion-7` (11 en 24.8s) cae al rango sano (5-8), que `avisos_sfx` marca
  y deja de marcar densidad correctamente, que `f13_guion.py` aplica el tope
  y guarda `candidatos`, que `recolectar()` expone todo lo que el selector
  necesita, y que el editor tiene el selector/contador/función de re-filtrado
  con el patrón correcto (candidatos, no la lista ya filtrada).
- **Verifiqué contra los datos reales de `Guion-7`** (sin tocar el archivo:
  leí su `guion.sfx.json`, apliqué `aplicar_tope_densidad` en un script aparte)
  — 11 eventos → 5, de uno cada 2.25s a uno cada 4.96s. Los sobrevivientes
  fueron `guion_1, guion_4, guion_7, guion_9, guion_11`: quedan
  razonablemente repartidos porque todos comparten la misma prioridad
  (80) y el desempate es por tiempo.
- **Abrí el editor de verdad** contra `Guion-7` (Edge headless + CDP, sin
  entorno gráfico interactivo disponible): estado inicial 11 sonidos, contador
  en rojo "11 sonido(s) en 25s · uno cada 2.3s"; clic real en el selector →
  "normal" bajó a 5 (mismos tiempos que calculé aparte, confirma que JS y
  Python calculan lo mismo), contador pasó a verde/normal; "sobrio" → 3;
  "cargado" → 6. Los tres presets se mueven en la dirección esperada y de
  forma monótona.
- **Percance y arreglo**: el autoguardado del editor escribió mi prueba
  ("cargado", 6 sonidos) en el `ajustes.sfx.json` REAL de `Guion-7` — no
  existía antes de esta sesión. Lo detecté al recargar la página (volvía a
  cargar 6 en vez de 11) hasta darme cuenta de que `ajustes.sfx.json` ya
  manda sobre `guion.sfx.json`. Borré el archivo para dejar la corrida de José
  como estaba. **Nota para las próximas verificaciones del plan**: probar
  contra una corrida real con el editor abierto de verdad puede escribir
  `ajustes.*.json` por el autoguardado — revisar y limpiar después, o probar
  contra una copia descartable.
- `node --check` sobre el `<script>` completo: sin errores, en cada iteración.
- `python editor/test_regresion.py` (127 pruebas) y `python editor/test_align.py`:
  en verde.

### Archivos tocados

- `editor/config.py`
- `editor/f5_audio.py`
- `editor/f13_guion.py`
- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque. Los valores de "sobrio" (6.5s) y "cargado"
(2.5s) no están calibrados contra una corrida real todavía — son el
doble/mitad de "normal" a ojo. Si en uso real se sienten mal, ajustar esos dos
números en `config.SFX_DENSIDAD_PRESETS` sin tocar el resto.

---

## BLOQUE — Modal para elegir el tramo de un clip de B-roll

**Estado: hecho.**

### Lo que investigué antes de tocar nada

- Un B-roll de video **siempre se lee desde el segundo 0** del archivo fuente:
  `f4_retencion.py` usa `-itsoffset {ini} -i archivo` para ubicarlo en la
  salida, pero `-itsoffset` NO mueve desde dónde se lee — no había ningún
  `-ss`/`atrim`/`trim=` tocando estos clips en ningún lado del render real.
- Si el hueco de la línea de tiempo queda más largo que el clip, `overlay`
  (con su `eof_action` por defecto, `repeat`) **congela el último cuadro** —
  no hace loop ni corta el video ni rompe el render.
- El **audio del B-roll nunca se mezcla**: el filtro solo referencia `[N]:v`
  de cada clip, nunca `[N]:a`; el mapeo final siempre sale de `1:a` (el video
  hablado). Esto lo hice explícito en la interfaz en vez de asumirlo (pedido
  del bloque).
- **Hallazgo de arquitectura importante**: `f6_overlays.py` tiene su PROPIO
  código de composición con B-roll (líneas ~1410-1466), pero está MUERTO en
  el pipeline real — `editor.py` solo lo llama con `--solo-planificar`
  (planifica eventos, no compone). La composición real siempre pasa por
  `f4_retencion.py --solo-render`. Solo toqué ese camino; no toqué el código
  muerto de `f6_overlays.py` (fuera de alcance, y tocar código que nunca se
  ejecuta no arregla nada).
- El catálogo del editor solo mostraba miniaturas estáticas (un frame fijo a
  los 0.5s) para los clips — nunca un `<video>` real. Sí existe un mecanismo
  de preview con `<video>` en el editor, pero es el de animaciones/hook/CTA
  (`medioAnimacion()`), no conectado al grid de B-roll.
- No existía ningún campo de offset/recorte en la estructura de un evento de
  B-roll (`ini, fin, x, y, tipo, medio, archivo, ...` — nada de
  `recorte_inicio`/`recorte_fin`).

### Qué decidí y por qué

- Dos campos nuevos, opcionales: `recorte_inicio` y `recorte_fin` — el tramo
  del ARCHIVO FUENTE que se usa (distinto de `ini`/`fin`, que es dónde cae en
  el video final). `None`/ausentes = comportamiento de siempre (desde el
  segundo 0, sin tope nuevo) — ningún B-roll viejo ni automático se ve
  afectado.
- **`f4_retencion.py`** (el único camino de render real):
  1. `-ss {recorte_inicio}` ANTES del `-i` del clip (además del `-itsoffset`
     que ya existía) — arranca la LECTURA en ese segundo del archivo. Sin
     esto, elegir un tramo en el editor no habría cambiado nada del render.
  2. Clamp defensivo: `fin = min(fin, ini + (recorte_fin - recorte_inicio))`
     aplicado a TODOS los eventos de video con recorte, antes de componer —
     por si un `ajustes.broll.json` tocado a mano por fuera del editor pide
     más metraje del que el clip tiene. Doble red de seguridad junto con el
     freno del editor.
- **`f6_overlays.cargar_broll_manual` y `cargar_eventos_manual`**: antes
  reconstruían el evento con una lista fija de claves (sin recorte); ahora
  propagan `recorte_inicio`/`recorte_fin` si vienen. Lo agregué a los dos por
  simetría, aunque hoy el modal solo genera B-roll (`cargar_broll_manual`) —
  `f4_retencion.py` aplica el offset a CUALQUIER evento de `medio: "video"`,
  así que un PiP de video con recorte también funcionaría si algún día se
  genera uno con esos campos.
- **`f10_editor_visual.recolectar()`**: el diccionario `movibles` (lo que
  repuebla `edicionPip` al recargar la página) ahora incluye
  `recorte_inicio`/`recorte_fin` — sin esto, guardar un tramo y refrescar la
  página lo habría olvidado.
- **Editor — el modal**: se abre SOLO para assets con `es_clip: true` (los de
  `assets/generado/video/manual/`, verificado que son los únicos con un
  `archivo` resuelto de forma confiable; hay 2 assets del catálogo con
  `medio: "video"` y `"pip"` en usos que hoy ya se manejan como imagen en
  `elegirAsset` — queda fuera de alcance, es un gap previo no relacionado).
  Reproduce el `<video>` COMPLETO vía `/archivo?ruta=...` (ya servible, sin
  endpoint nuevo). Dos manijas (`segTirIzq`/`segTirDer`) sobre una pista tipo
  `.enc-cerrado`, con `tiempoSegmento()` frenando siempre en `[0, duración]`
  — no se puede pedir más metraje del que el archivo tiene.
- **DECISIÓN explícita del bloque, implementada tal cual**: el hueco en la
  línea de tiempo queda ATADO al tramo — al confirmar el modal, `fin = ini +
  duración_del_tramo` (para un inserto nuevo) o `fin = min(hueco_viejo, ini +
  duración_del_tramo)` (al sustituir uno existente, nunca más largo que el
  tramo nuevo). `duracionMaximaClip(ev)` es la función reutilizable que dice
  cuánto puede durar el hueco; los dos tiradores de estirar el bloque en la
  línea de tiempo principal (`pintarPipTimeline`) la usan para frenarse — el
  IZQUIERDO también, porque adelantar el inicio alarga el hueco tanto como
  atrasar el fin.
- El aviso de audio ("el audio de este clip no se usa... entra mudo") va
  dentro del modal, verificado contra el código real de `f4_retencion.py`
  (no es una suposición).

### Verificación hecha

- `test_regresion.py` sección 13 (`pruebas_recorte_broll`, 13 checks):
  `-ss` condicional presente en `f4_retencion.py`, el clamp defensivo del
  `fin`, round-trip de `recorte_inicio`/`recorte_fin` a través de
  `cargar_broll_manual` (con y sin recorte, para no inventar uno de la nada),
  round-trip a través de `f10.recolectar()` → `movibles`, existencia del
  modal y sus manijas, el aviso de audio, la función `duracionMaximaClip`, el
  tope en los dos tiradores de la línea de tiempo, y que `eventoBase` /
  "sustituir" respeten el tramo.
- `node --check` sobre el `<script>` completo: sin errores.
- **Abrí el editor de verdad** contra `Guion-7` (Edge headless + CDP):
  - Catálogo real: 3 clips de Flow (`abandonado` 8s, `inside box` 5s,
    `kindle primer plano` 10.01s) con sus duraciones reales.
  - Clic en "abandonado" → modal abierto de verdad, `<video>` apuntando al
    archivo real, resumen inicial "0.0s a 8.0s de 8.0s".
  - Simulé arrastrar las manijas a [2s, 6s] y confirmé: el evento nuevo en
    `edicionPip` trae `recorte_inicio:2, recorte_fin:6` y **el hueco quedó en
    exactamente 4s** (`fin - ini = 4`), igual a la duración del tramo.
  - Repliqué la lógica EXACTA de los dos tiradores con valores extremos
    (pedir el borde derecho a 60s, el izquierdo a 0s): los dos se frenaron
    exactamente en el límite del tramo (`ini + 4` y `fin - 4`
    respectivamente), no más allá.
- **Mismo percance que en el bloque 3, dos veces**: el autoguardado escribió
  mi B-roll de prueba en el `ajustes.broll.json` REAL de `Guion-7`. Lo
  detecté después (`ls` mostró un 4to evento con `asset:
  "broll-manual:abandonado"`) y lo saqué a mano, restaurando los 3 eventos
  originales. **Regla que adopto de acá en adelante para lo que queda del
  plan**: para cualquier verificación en el navegador que vaya a tocar
  PiP/B-roll/SFX/hook-CTA (cualquier cosa que dispare el autoguardado), usar
  una copia descartable de la corrida (como hice en el bloque 1 con
  `_prueba-sfx-raw`), nunca la corrida real con nombre, aunque sea "solo para
  mirar".
- `python editor/test_regresion.py` (141 pruebas) y `python editor/test_align.py`:
  en verde.

### Archivos tocados

- `editor/f4_retencion.py`
- `editor/f6_overlays.py`
- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque. Sigue el BLOQUE 5 (subtítulos: tamaño
ajustable y corregir el texto). `cajaEnZonaTapada` (bloque 2) y el patrón de
exponer constantes vía `/datos` en vez de hardcodearlas en el JS (bloques 1 y
3) ya están listos para reusar ahí.
