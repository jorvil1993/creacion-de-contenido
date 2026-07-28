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
el espacio de salida 1080x1920. Sigue el BLOQUE 3 (bajar la densidad de
efectos de sonido).
