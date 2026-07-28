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

Ninguno pendiente de este bloque. Sigue el BLOQUE 2 (zona segura de TikTok
sobre el reproductor).

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

**Cómo se integra:** la rama `mejoras-preparacion` sale de `36475b1` y toca
archivos nuevos + `editor.py`, `config.py`, `test_regresion.py`, `COMO-USAR.md`
y `CLAUDE.md`. El único solape real con la otra sesión es `test_regresion.py`
(las dos añaden secciones al final): el conflicto, si sale, es Python visible y
los tests lo cazan. Merge normal a `mejoras-editor` cuando la otra sesión cierre.
El worktree `C:\ai-video\wt-preparacion` se puede borrar después con
`git worktree remove` (antes hay que quitar los enlaces `entrada/`, `salida/` y
`assets/` que se crearon ahí para tener un entorno fiel).
