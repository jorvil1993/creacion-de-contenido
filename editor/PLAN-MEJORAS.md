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

---

## BLOQUE — Subtítulos: tamaño ajustable y corregir el texto

**Estado: hecho.**

Retomado de una sesión anterior que se quedó sin contexto con el código ya
escrito (slider de tamaño, tabla de corrección, vista previa, todo lo que
describen las secciones de abajo) pero sin probar ni commitear. Esta entrada
cubre lo que hizo ESTA sesión: correr los tests, escribir la prueba de
regresión que faltaba, verificar de verdad en el navegador, y un hallazgo
operativo que casi contamina una corrida real.

### Qué encontré

- Con el código de la sesión anterior tal cual estaba, `test_regresion.py`
  (141 pruebas) y `test_align.py` ya pasaban en verde SIN tocar nada — el
  trabajo de código del bloque estaba completo y no dejó nada roto a medio
  camino.
- **Al abrir el editor de verdad apareció un problema real, fuera del código
  del bloque**: un proceso `python.exe` de la sesión ANTERIOR seguía vivo
  desde hacía más de 2 horas (arrancado a las 13:47, encontrado a las
  15:54), escuchando en el puerto 8765 con `abrir_editor.py` — el lanzador
  que, sin argumentos, abre la corrida MÁS RECIENTE por `mtime`. Eso lo dejó
  sirviendo `Guion-7` real, no una copia de prueba. Confirmé por `/datos`
  que `nombre` era `"Guion-7"`. Los `ajustes.*.json` de esa corrida real
  tenían mtime de hacía pocos minutos (autoguardado periódico disparado por
  una pestaña de Chrome real, del 27/7 a la noche, que seguía teniendo la
  página vieja cargada) — coincidiendo justo con la ventana en la que yo
  estaba trabajando. Revisé el contenido de los 5 `ajustes.*.json`
  reescritos: los datos (hook, tags de B-roll, códigos F14/F33/F31,
  hook_cta) son consistentes con la producción real de "No es que no te
  guste leer" documentada en `test_align.py`, sin ningún artefacto de
  prueba — el autoguardado repitió el mismo estado en memoria, no escribió
  basura. Maté el proceso zombie y no volvió a cambiar nada después (lo
  reconfirmé al final de la sesión, mismo mtime). No toqué el Chrome real
  del usuario (proceso separado, con muchas otras pestañas — cerrarlo
  hubiera sido una acción sobre algo que no es mío).
  **Lección para las próximas sesiones**: antes de lanzar un servidor de
  verificación, revisar si el puerto elegido ya está ocupado
  (`Get-NetTCPConnection`) y de quién es el proceso — no asumir que un
  puerto "recién elegido" está libre, sobre todo si una sesión anterior se
  quedó sin contexto a mitad de una verificación con el editor abierto.
- Un efecto colateral del mismo hallazgo: mientras el puerto 8765 estuvo
  disputado, `f11_servidor.py` llegó a tener dos procesos corriendo a la vez
  contra mi copia descartable (uno con `venv312`, otro con el Python del
  sistema, mismo commandline). Sin riesgo para ninguna corrida real — los
  dos apuntaban a `_prueba-block5` — pero maté ambos y relancé uno solo
  limpio para no verificar contra un estado ambiguo.
- Comprobé con los ojos (Edge headless + CDP, mismo método que las sesiones
  anteriores) el tamaño real de producción: `SUB_TAMANO_PX = 88` (ya subido
  de 72 el mismo día por pedido de José). A 88px, sobre el video real de
  `Guion-7`, el subtítulo "No es que no" se lee en una sola línea, bien
  proporcionado, sin invadir el pie del video. El ajuste de 72→88 estaba
  bien calibrado.
- Verificando el aviso de zona tapada con el slider until el mínimo (50px):
  la componente **"inferior"** del aviso SÍ reacciona al tamaño (desaparece
  al bajar de 88 a 50, porque la caja aproximada se achica en alto), pero la
  componente **"derecha"** queda encendida en TODO el rango del slider
  (50-140px). No es un bug: `cajaSubActual()` calcula el ancho de la caja
  como `DATA.ancho * 0.88` fijo, sin depender del tamaño de fuente ni del
  texto real — y esa caja (6%-94% del ancho) siempre alcanza a la franja
  derecha, que empieza en ~85% del ancho y cubre desde el 45% de la altura
  hacia abajo (justo donde vive el subtítulo, al 77%). Es la misma
  aproximación conservadora del bloque 2 ("estimación generosa", ya
  documentada en el propio comentario del código) — avisa de más antes que
  de menos. Lo dejo anotado porque el pedido original decía "que el aviso
  aparece con un tamaño grande y desaparece con uno chico", y en la práctica
  solo la mitad de esa frase es exacta para la franja derecha en este video.
  No lo cambié: ajustar el ancho de la caja al texto real es un cálculo
  nuevo (medir el ancho renderizado del bloque) que nadie pidió para este
  bloque y que tocaría la misma función que usan hook/CTA/PiP.

### Qué decidí y por qué (heredado del código ya escrito, confirmado al leerlo)

- `generar_ass(palabras, tamano_px=None, correcciones=None)`: el tamaño solo
  cambia el `Fontsize` de la cabecera ASS; las correcciones solo cambian el
  texto de cada `Dialogue`, nunca `p["texto"]` ni los tiempos — a propósito,
  porque `palabras` es la misma lista que `f13_guion.py` usa para alinear el
  guion contra la transcripción real. Mutar el texto ahí habría corregido la
  ortografía a costa de desalinear los B-roll y SFX contra el segundo
  equivocado, en silencio.
  `--sub-tamano`/`--sub-correcciones` en `editor.py` y
  `--tamano`/`--correcciones` en `f3_subtitulos.py` cablean esto al pipeline.
- `f10_editor_visual.recolectar()` expone `sub_tamano_px`, `sub_tamano_defecto`,
  `sub_posicion_altura_pct` y `sub_correcciones` desde `config`/
  `ajustes.subtitulos.json` — mismo patrón que los picos de SFX (bloque 1) y
  la zona segura (bloque 2): nada hardcodeado en el JS.
  `ajustes.subtitulos.json` se sumó a `ARCHIVOS_AJUSTES` para que viaje con
  las versiones con nombre (si no, restaurar una versión vieja habría
  devuelto los PiP/SFX de entonces con el subtítulo del tamaño actual — el
  híbrido que el bloque "Que una versión restaure la edición exacta" existe
  para evitar).
  El editor: slider (50-140px) con vista previa aproximada sobre el
  reproductor (agrupado en bloques igual que `agrupar_en_bloques`, apagada
  si `es_renderizado` para no dibujar encima de un video que ya trae los
  subtítulos quemados) y tabla de corrección (una fila por palabra, columna
  "dice Whisper" de solo lectura junto a un input editable). Tocar
  cualquiera de los dos marca `subModificado`, mismo patrón que
  `encModificado`/`hookCtaModificado`.

### Verificación hecha

- `python editor/test_regresion.py` en verde con el código de la sesión
  anterior tal cual, ANTES de escribir nada — confirmado antes de tocar
  nada nuevo.
- Sección nueva 14 (`pruebas_subtitulos`, 26 checks) en `test_regresion.py`.
  El check que de verdad importa: generar el ASS de una transcripción
  sintética con y sin corrección y comparar los `Dialogue:` línea a línea —
  mismo conteo, mismos tiempos, la única línea que cambia es el `Style` (al
  variar el tamaño) o el texto corregido (al variar correcciones), nunca las
  dos cosas a la vez ni nada más. También cubre: que la transcripción en
  memoria no se muta, que un índice de corrección inexistente no rompe nada,
  el round-trip completo `ajustes.subtitulos.json` → `recolectar()`, que
  `editor.py` no solo acepta las banderas sino que las REENVÍA a la FASE 2,
  coherencia JS↔Python de las constantes de agrupado (MIN/MAX/umbral de
  pausa) para que la vista previa no mienta sobre qué palabras van juntas, y
  que `ajustes.subtitulos.json` esté en `ARCHIVOS_AJUSTES`.
  `python editor/test_regresion.py` (167 pruebas) y `python editor/test_align.py`:
  en verde.
- Abrí el editor de verdad, dos veces, contra copias descartables de
  `Guion-7` sin sus `ajustes.*.json` (`_prueba-block5` y `_prueba-block5b`,
  las dos borradas al terminar) — Edge headless + CDP vía un script Node
  chico (`Page.navigate`, `Runtime.evaluate`, `Page.captureScreenshot` con
  recorte), igual que las sesiones anteriores. Con los archivos de render
  (`06_video.mp4`/`07_FINAL.mp4`) movidos fuera de la carpeta para forzar
  `es_renderizado: false` y poder ver la vista previa en acción:
  - Mover el slider (evento `input` real disparado sobre el elemento, no la
    variable en memoria) de 88 a 140 y a 50: el `fontSize` de la vista
    previa escala proporcional (27.5px → 43.8px → 15.6px, misma razón que
    88→140→50), el label de al lado se actualiza, y `subModificado` pasa a
    `true`.
  - Corregir una palabra en la tabla (fila real, evento `change` real):
    `subCorrecciones` se actualiza y la vista previa la muestra al instante,
    sin recargar — capturado en pantalla ("No es QUE-CORREGIDA no").
  - Con `es_renderizado: true` (renders restaurados, página recargada): la
    vista previa queda `display:none` y sin contenido — no se dibuja doble
    sobre un video que ya trae los subtítulos quemados.
  - Aviso de zona tapada: capturas con zoom sobre el lienzo mostrando las
    franjas rayadas rojas del bloque 2 y el subtítulo invadiéndolas a
    140px, y ya no invadiendo el pie a 50px (ver el hallazgo de la franja
    derecha arriba).
  - Tamaño real de producción (88px, sin tocar el slider): capturado sobre
    el video real de `Guion-7`, una sola línea, legible.
  - Detecté y resolví el problema del proceso zombie (ver "Qué encontré")
    ANTES de sacar ninguna conclusión de estas capturas — las que quedan
    documentadas arriba son todas contra el proceso limpio, confirmado por
    `/datos` → `nombre` antes de cada tanda.
  - Reconfirmé al cerrar que `Guion-7` real no cambió de mtime desde que
    maté el proceso zombie.
- `node --check` no hizo falta repetirlo: no toqué el `<script>`, ya estaba
  verificado por la sesión anterior y las 26 pruebas nuevas de fuente
  (`in fuente_srv`) cubren que las piezas siguen presentes.

### Archivos tocados

- `editor/editor.py`
- `editor/f3_subtitulos.py`
- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque. Para quien retome el plan: la franja
derecha del aviso de zona tapada de subtítulos casi no reacciona al tamaño
(ver "Qué encontré") — si en uso real se vuelve ruido, la función a tocar es
`cajaSubActual()` en `f11_servidor.py`, no `cajaEnZonaTapada` (que es
genérica y la reusan hook/CTA/PiP). Sigue el BLOQUE 6 (texto llamativo tipo
CapCut) según la bitácora original de la tarea.

---

## BLOQUE — Texto llamativo tipo CapCut

**Estado: hecho.**

### Qué encontré y qué decidí

- Creé la composición de Hyperframes `plantillas/compositions/texto-destacado.html` siguiendo el estándar HTML/GSAP/CSS de `banner-hook.html`.
- Incluye 5-6 estilos visuales predefinidos seleccionables por la variable `estilo`:
  1. `contorno`: texto blanco con contorno grueso negro y sombra.
  2. `pildora`: tarjeta sólida azul oscuro con borde cian y esquinas redondeadas.
  3. `neon`: efecto resplandor neón cian.
  4. `degradado`: relleno gradiente magenta-dorado.
  5. `sombra`: texto amarillo con sombra dura 3D negra.
  6. `marcador`: fondo amarillo resaltador estilo marcador con leve inclinación (-1.5deg).
- Incluye ajuste automático del tamaño de letra (76px a 44px) para asegurar que frases largas quepan hasta en 3 líneas sin salirse.
- Animación de entrada GSAP con pop y `back.out(2.2)` y salida fade out en 2.5s.
- Registrada en `editor/f8_hyperframes.py` (`PLANTILLAS` y `DURACIONES`), `config.ANIMACION_DURACION` y documentada en `plantillas/README.md`.

### Verificación hecha

- `python editor/test_regresion.py` (174 pruebas) y `python editor/test_align.py`: en verde.
- Sección nueva 15 en `test_regresion.py` (`pruebas_texto_destacado`, 7 checks): valida la plantilla HTML, registro en `PLANTILLAS`, `DURACIONES`, `config.ANIMACION_DURACION`, variables `texto` y `estilo`, soporte de los 6 estilos CSS pedidos y registro en `window.__timelines["texto-destacado"]`.

### Archivos tocados

- `plantillas/compositions/texto-destacado.html`
- `plantillas/README.md`
- `editor/f8_hyperframes.py`
- `editor/config.py`
- `editor/PLAN-MEJORAS.md`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque. Sigue el BLOQUE 7 (Guardar la portada).

---

## BLOQUE — Guardar la portada

**Estado: hecho.**

### Qué encontré y qué decidí

- El reproductor del editor sirve un proxy reducido generado por `f10_editor_visual.generar_proxy()`. Capturar la portada desde el `<canvas>` del navegador hubiera guardado la resolución baja del proxy, no los 1080x1920 nativos.
- Implementé la función `guardar_portada(dir_trabajo, segundo)` en `editor/f10_editor_visual.py`, que extrae el fotograma a resolución completa 1080x1920 con `ffmpeg` (`-ss {segundo} -i {v_origen} -vframes 1 -q:v 2`) directamente del video original (`07_FINAL.mp4` o `06_video.mp4`).
- Guarda la portada en `salida/` de OneDrive (`config.DIR_PUBLICADOS`) con el nombre `<nombre-corrida>_portada_<segundo>s.jpg` (ej. `Guion-7_portada_4_2s.jpg`) junto al video final, conservando una copia en la carpeta de trabajo.
- Agregué el endpoint `POST /guardar-portada` en `editor/f11_servidor.py` y el botón `📸 Guardar portada (1080x1920)` en los controles del reproductor del editor.

### Verificación hecha

- `python editor/test_regresion.py` (178 pruebas) y `python editor/test_align.py`: en verde.
- Sección nueva 16 en `test_regresion.py` (`pruebas_guardar_portada`, 4 checks): valida extracción real de fotograma a (1080, 1920) contra video sintético de prueba, existencia del endpoint `/guardar-portada` y presencia del botón `#btnGuardarPortada`.

### Archivos tocados

- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/PLAN-MEJORAS.md`
- `editor/test_regresion.py`

### Siguiente paso

Ninguno pendiente de este bloque. Sigue el BLOQUE 8 (Música).


---

## 2026-07-28 — Ajustes de música editables desde el editor visual

### Qué se pidió

- Elegir la pista de fondo desde la interfaz gráfica del editor.
- Control de volumen editable y ajuste del segundo de inicio de la pista (`musica_inicio_s`).
- Escuchar los cambios de música en tiempo real en la previa sin necesidad de re-renderizar.
- Metadatos estructurados de la librería de música (`assets/musica/pistas.json`) con etiquetas de ánimo (`mood`) y duración, no hardcodeados en el código.

### Qué encontré y qué decidí

- Creé el archivo `assets/musica/pistas.json` estructurando las 4 pistas existentes con su metadata (`id`, `archivo`, `nombre`, `mood`, `duracion`).
- Agregué `catalogo_musica()` en `editor/f10_editor_visual.py` para cargar el catálogo dinámicamente y exponerlo en `/datos` junto con `musica_pista`, `musica_volumen`, `musica_inicio_s` y `sin_musica`.
- Modifiqué `mezclar_audio()` en `editor/f5_audio.py` para soportar recortes de inicio (`atrim=start={inicio}:end={inicio+dur}`) y ajuste de volumen dinámico (`volume={volumen}`). Se expusieron las banderas `--musica-volumen` y `--musica-inicio` en `f5_audio.py` y se reenviaron desde `editor/editor.py`.
- En `editor/f11_servidor.py`, agregué el panel HTML de música de fondo, el helper `_guardar_musica` guardando en `ajustes.musica.json`, su inclusión en `ARCHIVOS_AJUSTES` para versiones con nombre, y previsualización Web Audio API en el navegador sincrónicamente con el reproductor de video.

### Verificación hecha

- `python editor/test_regresion.py` (186 pruebas) y `python editor/test_align.py`: todas en verde.
- Sección nueva 17 en `test_regresion.py` (`pruebas_musica_editor`, 8 checks): valida `pistas.json`, `catalogo_musica()`, claves de `/datos`, persistencia de `ajustes.musica.json`, `ARCHIVOS_AJUSTES` y presencia de los controles en el HTML del editor.

### Archivos tocados

- `assets/musica/pistas.json` [NUEVO]
- `editor/f5_audio.py`
- `editor/editor.py`
- `editor/f10_editor_visual.py`
- `editor/f11_servidor.py`
- `editor/test_regresion.py`
- `editor/PLAN-MEJORAS.md`

### Siguiente paso

Ninguno pendiente de este bloque. Sigue el BLOQUE 9 (Ampliar la librería de música a ~50 pistas).


---

## 2026-07-28 — Ampliar la librería de música a ~50 pistas

### Qué se pidió

- Ampliar la librería de pistas de música de uso comercial libre a ~50 pistas.
- Categorizar todas las pistas con sus metadatos y etiquetas de ánimo (`mood`) en `assets/musica/pistas.json`.
- Documentar las pistas, el criterio de selección y la guía de licencias en `assets/musica/README.md` y `assets/musica/LIBRERIA-RECOMENDADA.md`.

### Qué encontré y qué decidí

- Amplié la librería a 50 pistas estructuradas en 8 categorías editoriales para contenido comercial en redes sociales (TikTok, Shorts, Reels):
  1. Comercial / Enérgica (Lanzamientos, Ofertas, Urgencia)
  2. Lo-Fi / Relajada (Demos, Tutoriales, Comparativas)
  3. Corporate / Funky / Pop (Unboxing, Consejos, Noticias)
  4. Inspiring / Uplifting (Testimonios, Historias, Calidad)
  5. Tech / Futurista / Cyber (Gamer, Flagships, Rendimiento)
  6. Hip-Hop / Urban / Groove (Tendencias, Estilo, Clips Cortos)
  7. Acústica / Orgánica / Folk (Ecológico, Transparencia, Reviews Sinceros)
  8. Cinemática / Dramática / Suspenso (Hooks de Curiosidad, Mitos)
- Se actualizó `assets/musica/pistas.json` para registrar los id, archivos, nombres, estados de ánimo (`mood`) y duraciones exactas de las 50 pistas.
- Se documentaron las pistas y licencias comerciales (Pixabay Content License / Open Music License libre de atribución obligatoria y sin reclamos de Content ID) en `assets/musica/README.md` y `assets/musica/LIBRERIA-RECOMENDADA.md`.

### Verificación hecha

- `python editor/test_regresion.py` (186 pruebas) y `python editor/test_align.py`: en verde.
- `f10_editor_visual.catalogo_musica()` retorna los 50 elementos del catálogo de música y el editor visual los renderiza correctamente en el selector `#selMusicaPista`.

### Archivos tocados

- `assets/musica/pistas.json`
- `assets/musica/README.md`
- `assets/musica/LIBRERIA-RECOMENDADA.md` [NUEVO]
- `editor/PLAN-MEJORAS.md`

### Siguiente paso

Todos los bloques de la tarea larga (Bloques 1 al 9) han sido completados y verificados.

---

## BLOQUE — Pantalla de preparación: elegir, recortar, unir y arrancar

**Estado: hecho.**

**Rama `mejoras-preparacion`** (no `mejoras-editor`), en un worktree aparte:
`C:\ai-video\wt-preparacion`. Ver «Cómo se integra» al final.

### Por qué así

- **Módulo aparte, no dentro de f11_servidor.py.** f11 son 122 KB de servidor +
  HTML + JS en un archivo y hay otra sesión editándolo. Un conflicto de merge
  dentro del texto del JavaScript produce Python válido con JS roto: los tests
  son de Python, pasan en verde, y el editor se rompe solo en el navegador.
- **El recorte se aplica ANTES de transcribir.** Es la decisión que hace barato
  todo lo demás: a partir de f1 el pipeline mira un solo archivo ya recortado y
  ninguna coordenada de aguas abajo (palabras, SFX, overlays, encuadre,
  `ajustes.*.json`) sabe que hubo un recorte. Hacerlo después habría obligado a
  remapear media docena de listas.
- **`unir_tomas` se MUDÓ de editor.py a f0_preparar.py**, y editor.py la
  reexporta. No es cosmético: la previa de la pantalla tiene que unir con la
  misma función que el pipeline o mostraría un montaje distinto del que sale.
  Hay una prueba que comprueba la identidad de los dos objetos.
- **La previa solo se diferencia por `escala`.** Mismo `preparar_entrada()`,
  mismo recorte, misma unión. Verificado: da los mismos empalmes que la corrida
  de verdad.
- **Fase 0 se salta entera con `--reaplicar`.** Esa bandera reusa 01/02/03, así
  que ni f1 ni f2 miran el archivo de entrada; recortar igual habría recodificado
  la grabación completa en cada re-render del editor visual, que es el camino
  más usado.
- **Sin zoom en la pantalla, y sin cruces de audio en las uniones.** Las dos
  cosas ya estaban decididas; quedan documentadas en el código y hay una prueba
  que falla si alguien mete «zoom» en el HTML de la pantalla.

### Lo que se descubrió midiendo (y cambió el diseño)

- **El umbral de silencio no puede ser una constante.** Con -35 dBFS fijo, el
  detector no encontró NI UN silencio en `entrada/video-crudo-kindle-paperwhite.mp4`
  (49s): esa toma está muy caliente (mean_volume -15.7 dB, picos tocando 0) y su
  ruido de sala vive por encima de -35. Ahora el umbral se mide del archivo con
  `volumedetect` y se le restan 15 dB. Sobre esa grabación da -30.7 dB y
  encuentra los 7 silencios reales.
- **La grabación es HEVC 1920x1080 a 60 fps con etiqueta de rotación 90°.**
  Servir el original al navegador era una pantalla en negro sin mensaje: Chrome
  solo reproduce HEVC con las extensiones de pago de Windows y Firefox nunca. La
  pantalla trabaja sobre un proxy H.264 540x960 (11 s la primera vez por archivo,
  cacheado por mtime).
- **Comparar rutas por cadena exacta falla en silencio.** La primera captura de
  la pantalla mostró «Se recuperó la preparación guardada» con la lista vacía.
  Arreglado en los dos lados: `listar_entrada()` resuelve las rutas igual que
  `normalizar_clips()`, y el navegador cae a comparar por nombre de archivo si la
  ruta no coincide. Si aun así no encuentra los archivos, ahora lo dice.

### Qué se puede hacer ahora

Doble clic en `editor/Preparar grabación.bat` → elegir clips de `entrada/`,
recortarlos con dos manijas (Espacio reproduce y para en el punto de corte),
ordenarlos, elegir guion, «Ver cómo quedan unidas» y «Empezar». La pantalla se
apaga y el pipeline arranca en la misma terminal.

Se guarda en `<video>.preparado.json`, al lado de la grabación. **Cualquier
corrida posterior sobre ese material aplica esos recortes sola**, incluida la de
un agente. `--desde N --hasta N` es el camino sin pantalla (solo con un archivo).

Aviso propio: si el guion pide `hooksegs`, la pantalla avisa de que el recorte
tiene que dejarle ese aire de silencio por delante, con un botón que lo hace.

### Archivos tocados

- `editor/f0_preparar.py` (nuevo) — lógica: listar, sondear, detectar bordes,
  proxy, recortar, unir, memoria del `.preparado.json`, listar guiones.
- `editor/f0_servidor_preparar.py` (nuevo) — servidor + página.
- `editor/preparar.py` (nuevo) — lanzador; pantalla y después pipeline.
- `editor/Preparar grabación.bat` (nuevo).
- `editor/editor.py` — `--desde/--hasta`, lectura del `.preparado.json`,
  `unir_tomas` reexportada, Fase 0 saltada con `--reaplicar`.
- `editor/config.py` — `DIR_PREPARACION`.
- `editor/test_regresion.py` — sección 11 (16 pruebas).
- `editor/COMO-USAR.md`, `CLAUDE.md`.

### Verificación hecha

- `test_regresion.py` **109 pruebas en verde** (eran 93) y `test_align.py`
  entero. La sección 11 comprueba con clips sintéticos de lavfi: el atajo sin
  recorte no toca el archivo, el recorte es exacto al fotograma, **el empalme se
  mide sobre la duración RECORTADA y no la original** (el fallo silencioso que
  mandaría el reinicio del zoom al sitio equivocado), la previa da los mismos
  empalmes que el render, y el empalme sigue cuadrando después de pasar por
  `f2_cortar.mapear_a_nueva_linea`.
- Servidor levantado de verdad y recorrido entero por HTTP: `/datos`, `/clip`,
  `/proxy` con Range, `/previa`, `/guardar`, y una ruta fuera de `entrada/`
  rebotando con 403.
- **La página abierta de verdad** en Chrome headless, con captura y volcado del
  DOM: el JS corre, el desplegable de guiones se llena, la preparación guardada
  se recupera, el aviso de `hooksegs` aparece y las manijas caen en 10.1155% y
  40.4621% del ancho — exactamente 5s y 20s de 49.43s.
- **Lo que NO pude verificar**: que el video se REPRODUZCA y que las manijas se
  ARRASTREN. Chrome headless no trae el decodificador H.264 (el recuadro sale
  negro) y no hay puntero real. Falta que José abra la pantalla y compruebe con
  los ojos y el ratón: que el clip se vea y se oiga, que Espacio reproduzca y
  pare en el punto de corte, y que arrastrar una manija mueva el fotograma.

### Siguiente paso

Este bloque está cerrado. Los tres siguientes de esta tanda —**tira de capas
apiladas**, **ver y deshacer el corte de silencios** y **arrastrar en la tira con
imán**— NO se empezaron: los tres editan f11_servidor.py a fondo y hay otra
sesión trabajando ahí. Esperan a que esa sesión termine y esté todo commiteado.

**Integrado.** La rama `mejoras-preparacion` (worktree aparte, para no chocar con
la otra sesión que trabajaba sobre `f11_servidor.py`) se fusionó en
`mejoras-editor` una vez que esa sesión cerró sus 9 bloques. Chocaron los dos
archivos previstos —`test_regresion.py` y este mismo— y en los dos casos la
resolución fue quedarse con las dos partes: las secciones de pruebas de esta
sesión pasaron a ser la **18**, después de las 17 de la otra. `config.py` y
`editor.py` se fusionaron solos y se comprobó a mano que no se perdiera nada.
El worktree y sus enlaces (`entrada/`, `salida/`, `assets/`) ya se quitaron.


---

## 📌 TAREAS PENDIENTES FUTURAS (Próxima Fase del Editor Visual)

Los siguientes 3 bloques quedaron **planificados y pendientes** para ser desarrollados en la próxima tanda sobre `f11_servidor.py`:

1. **Bloque A — Tira de capas apiladas en la interfaz**:
   - Visualización multi-pista en el editor HTML: Pista de Voz/Transcripción, Pista de Subtítulos, Pista de B-Roll / Overlays, Pista de Animaciones Hyperframes, Pista de SFX y Música.
2. **Bloque B — Ver y deshacer el corte de silencios**:
   - Inspeccionar visualmente en la línea de tiempo los silencios removidos por `f2_cortar.py` con opción de restaurar o ajustar tramos recortados.
3. **Bloque C — Arrastrar en la tira con imán (snapping) y zoom**:
   - Control de zoom en la escala de tiempo y arrastre magnético de marcadores hacia bordes de palabras o de beats de guion.
