# Tira de capas apiladas — bitácora

Bitácora propia de la rama `mejoras-tira` (worktree `C:\ai-video\wt-tira`), en
paralelo a `PLAN-MEJORAS.md`, que es de otra sesión y no se toca desde aquí.
Cubre los dos bloques que quedaron pendientes al final de `PLAN-MEJORAS.md`:
**A — tira de capas apiladas** y **C — zoom e imán**. El bloque B (ver y
deshacer el corte de silencios) lo lleva otra sesión.

Un commit por bloque, como se pidió. El reparto es por **funcionalidad del
editor**, no por archivo: en A la tira se lee y se navega; en C aparecen el
zoom, el desplazamiento y el arrastre magnético. `f14_tira.py` entra entero en
A —incluidas las constantes de zoom y las listas de imán, que hasta C son datos
inertes— porque partir un módulo de 250 líneas en dos commits hace el diff más
difícil de leer, no más fácil.

---

## BLOQUE A — Tira de capas apiladas

**Estado: hecho.**

### La decisión que pedía el encargo: ¿sustituye a las cinco pistas o convive?

**Convive.** Las pistas de siempre (`#pista`, `#pistaSfx`, `#pistaPipTimeline`,
`#pistaHookCta`, `#pistaAnimTimeline`, `#pistaEnc`) siguen exactamente como
estaban. La tira se suma arriba y no quita nada.

No es solo por el tamaño del merge. Al leer las cinco pistas para replicarlas
aparecieron **topes y efectos secundarios que solo viven ahí dentro** y que
sustituirlas obligaría a reimplementar uno por uno:

- Los tiradores de `pintarPipTimeline()` frenan en `duracionMaximaClip(ev)` —
  el tope del bloque 4, que impide pedir más metraje del que tiene el tramo
  recortado del clip. El tirador IZQUIERDO también, porque adelantar el inicio
  alarga el hueco tanto como atrasar el fin.
- `pintarSfx()` reordena `edicionSfx` en cada repintado y `pintarEncuadre()`
  hace lo propio con `encCerrados`.
- El arrastre de SFX dispara `escucharSfx(e.archivo, e.volumen)` para que se
  oiga al soltarlo, con la cuenta de ganancia del bloque 1.
- `pintarAnimTimeline()` a propósito NO rehace la rejilla de tarjetas en cada
  frame, porque reiniciaría los `<video>` de todas y el arrastre iría a
  tirones.
- El panel de encuadre le pide la curva al servidor (`recalcularCurva()`) en
  vez de calcularla en JS, para no acabar enseñando algo distinto del render.

Reescribir todo eso dentro de la tira multiplicaría por seis las formas de que
el editor y el render dejen de coincidir, que es justo lo que este editor
existe para evitar. **La tira es la vista de conjunto y la navegación; la
edición fina sigue siendo de cada sección.** La única excepción es el arrastre
del bloque C, que se explica más abajo y está deliberadamente limitado a mover
bloques enteros, nunca a redimensionarlos.

### Qué se puede hacer ahora

Arriba del todo, encima de la línea de tiempo de palabras, hay una tira con
seis carriles sobre **una sola escala de tiempo**:

| Carril | Qué muestra | Se arrastra |
|---|---|---|
| Voz | cada palabra de `02_cortado.json` | no |
| Subtítulos | los bloques de 2-4 palabras que el ASS dibuja juntos | no |
| B-Roll / PiP | los insertos, violeta los de video | sí |
| Animaciones | las plantillas Hyperframes | sí |
| SFX | un rombo por efecto | sí |
| Música | la pista de fondo, o «sin música de fondo» | no |

Un único cursor rojo atraviesa los seis y sigue al `<video>`; un clic en
cualquier carril lleva la aguja ahí. Los beats del guion salen marcados en
ámbar sobre la regla.

En este bloque la tira es **de lectura y navegación**: mover cosas desde ahí
llega con el bloque C. La columna «se arrastra» de la tabla describe lo que
`f14_tira.CARRILES` ya marca como editable, que es lo que el bloque C usará.

### Qué encontré

- **El editor ya tenía media solución para las agujas**: `actualizarUI()` mueve
  todas las que lleven `class="playhead"` a la vez, por porcentaje de la
  duración total. Es un buen patrón y el comentario del código dice que una
  pista nueva la trae andando sin tocar nada. **La tira no puede usarlo**: con
  zoom su escala ya no es «porcentaje de la duración», así que el cursor tiene
  clase propia (`.tira-cursor`) y se mueve desde `window.__tira.cursor()` —
  ya en este bloque, para no tener que rehacerlo al llegar el zoom. Hay una
  prueba que falla si alguien le pone la clase compartida.
- **Los beats del guion no se guardan en ningún JSON.** El encargo hablaba de
  `10_guion-alineado.json`, pero lo que `f13_guion.py` escribe es
  `10_guion-alineado.md`, un reporte legible. Los beats hay que reconstruirlos
  de los cinco `guion.*.json` (SFX, B-Roll, animaciones, eventos, encuadre).
  Eso deja fuera los beats de tipo `YO`, que alinean contra el audio pero no
  producen ningún artefacto — y son cortes editoriales igual de válidos para el
  imán. Por eso `f14_tira.beats_guion()` **también parsea el `.md`**: su
  formato lo genera código con un f-string fijo, no una persona.
- Al mezclar las dos fuentes aparece el mismo beat dos veces con distinta
  precisión: `guion.broll.json` dice `6.704` y el reporte `6.70`. El primer
  deduplicado se quedaba con el del reporte solo por ser 4 milésimas menor, y
  tiraba el dato exacto. Ahora se agrupa por cercanía (20 ms) y **gana el más
  preciso**, no el más temprano.
- El **agrupado de subtítulos ya estaba replicado en JS**
  (`agruparEnBloquesSub`, del bloque 5) con constantes verificadas contra
  Python. Aun así el carril lo calcula **en Python llamando a
  `f3_subtitulos.agrupar_en_bloques()`** — la función del render, no una copia.
  Una tercera implementación de la misma regla era una tercera forma de que se
  desviaran.

### Qué decidí y por qué

- **Todo el JS y el CSS en archivos propios** (`editor/web/tira.js`,
  `editor/web/tira.css`), servidos por un endpoint nuevo, en vez de dentro de
  `PAGINA`. Misma razón que dio la sesión de la pantalla de preparación:
  `f11_servidor.py` son 160 KB de servidor + HTML + JS en un archivo, y un
  conflicto de merge dentro del texto del JavaScript produce **Python válido
  con JS roto** — los tests son de Python, pasan en verde, y el editor se rompe
  solo en el navegador.
- En `f11_servidor.py`, exactamente las cinco anclas del encargo y nada más:
  el endpoint estático, el `<link>`, el `<script src>`, el `<div id="tiraCapas">`
  y una línea en `cargar()` y otra en `loop()`. **18 líneas en total**, ninguna
  función existente modificada. Hay una prueba que comprueba que no se coló
  cuerpo de la tira dentro de `f11_servidor.py`.
- `f10_editor_visual.py` recibe **una línea dentro del dict que devuelve
  `recolectar()`** (`"tira": f14_tira.datos_tira(dir_trabajo)`) más el `import`
  al tope del módulo — el mismo sitio al que el bloque 1 subió el de
  `f5_audio`.
- **La tira lee el estado, no lo copia.** `DATA`, `edicionPip`, `edicionSfx`,
  `edicionAnimaciones`, `edicionMusicaPista`… son `let` del `<script>` inline
  anterior, y un segundo script clásico comparte ese ámbito. Cada acceso va
  envuelto en un `try`: si alguna desaparece, la tira se apaga en vez de tirar
  la página. Duplicar el estado habría creado la posibilidad de que la tira y
  el panel de abajo dijeran cosas distintas del mismo B-Roll.
- **Arranque perezoso.** `cargar()` es `async`: su última línea (el
  `window.__tira.init(DATA)` del ancla 4) puede correr **antes** de que
  `tira.js` haya llegado del servidor, y entonces `window.__tira` todavía no
  existe. `loop()` sí corre siempre después, así que `cursor()` enciende la
  tira si `init` no llegó a tiempo. Da igual el orden de carga.
- **Sincronización por huella, no por engancharse a las otras funciones.**
  Cuando se agrega un SFX o se cambia la pista de música desde su panel, la
  tira tiene que enterarse. Modificar `pintarSfx()` para que avise está fuera
  del contrato, así que la tira compara una huella barata del estado dos veces
  y media por segundo desde `cursor()` y se repinta sola si algo cambió.
- Nada hardcodeado en el JS: los seis carriles (y, para el bloque C, los
  límites de zoom y la tolerancia del imán) salen de `f14_tira.py` por
  `/datos`, el patrón de los bloques 1, 2 y 3. **No se tocó `config.py`** — no
  está en la lista de archivos permitidos, así que las constantes de la tira
  viven en su propio módulo.
- `datos_tira()` no puede tumbar `recolectar()`: una corrida sin guion, sin
  transcripción o con un JSON corrupto devuelve la estructura completa y vacía.
  Sin tira se sigue editando en las secciones de siempre.

### Verificación hecha

- `python editor/test_regresion.py` (202 pruebas) y `python editor/test_align.py`
  en verde **antes de tocar nada** y al terminar. No se tocó `test_regresion.py`.
- `python editor/test_tira.py` — 35 pruebas nuevas en un archivo propio. Las
  que de verdad importan: que los bloques de subtítulo sean **los mismos
  cortes** que `f3_subtitulos.agrupar_en_bloques()` (no solo el mismo conteo,
  que un agrupado propio podría clavar por casualidad); que los índices sean la
  posición global de cada palabra, que es la clave con la que `generar_ass()`
  aplica las correcciones —desalinearlos corregiría la palabra equivocada—; que
  el deduplicado de beats se quede con el dato preciso; que las cinco anclas
  sigan en su sitio (un merge que se lleve una deja el editor funcionando
  igual, solo que sin tira, y no da error en ningún lado); y que no se haya
  colado cuerpo de la tira dentro de `f11_servidor.py`.
- `node --check` sobre `editor/web/tira.js` y sobre el `<script>` completo
  extraído de `f11_servidor.py`: sin errores. Los tests son de Python y **no
  ven un JavaScript roto**.
- **Abrí el editor de verdad** (Edge headless + CDP: `Page.navigate`,
  `Runtime.evaluate`, `Page.captureScreenshot`), en el puerto 8801, contra
  `_prueba-tira`:
  - Los seis carriles se pintan con el número exacto de elementos que hay en
    el estado: 76 palabras, 21 bloques de subtítulo, 5 insertos, 1 animación,
    11 SFX, 1 bloque de música. Las etiquetas salen en orden.
  - **Alineación medida en pantalla**, que es lo único que prueba que los seis
    carriles comparten escala: se leyó la posición real de cada elemento con
    `getBoundingClientRect()` y se convirtió de vuelta a segundos. Los 11 SFX
    y los 5 insertos caen en su tiempo con un error máximo de **0.4
    milésimas de segundo**. (El primer intento midió el borde izquierdo del
    rombo de SFX y dio 0.28s de desvío: el rombo va rotado 45°, así que su
    caja envolvente es más ancha que el cuadrado y su borde no significa nada.
    Era un fallo de la medición, no del código; se pasó a medir el centro.)
  - Cursor: se movió `video.currentTime` a 12.0s y el cursor quedó en 48.3228%
    de 24.833s — exacto.
  - Clic real (evento `MouseEvent` despachado sobre el elemento) al 25% del
    carril de música: la aguja saltó a 6.19s de los 6.21s esperados.
  - Captura del panel entero y de la tira recortada: layout intacto, nada roto
    por el CSS nuevo, consola del navegador **vacía** (sin errores ni avisos).
- La verificación **nunca** tocó una corrida real: se trabajó sobre
  `C:\ai-video\salida\_prueba-tira`, copia de `Guion-7` hecha a propósito, y se
  comprobó que el `Guion-7` real no cambió de mtime. El puerto 8801 se
  comprobó libre con `Get-NetTCPConnection` antes de levantar nada, y no había
  ningún `python.exe` de una sesión anterior.

### Archivos tocados

- `editor/f14_tira.py` [NUEVO]
- `editor/web/tira.js` [NUEVO]
- `editor/web/tira.css` [NUEVO]
- `editor/test_tira.py` [NUEVO]
- `editor/PLAN-TIRA.md` [NUEVO]
- `editor/f10_editor_visual.py` — una línea en el dict de `recolectar()` + el import
- `editor/f11_servidor.py` — solo las cinco anclas del encargo (18 líneas)

### Lo que NO pude verificar

- **Reproducción del video.** Edge headless no trae el decodificador H.264, así
  que el recuadro sale negro y `video.play()` no avanza. El cursor se verificó
  moviendo `currentTime` a mano y comprobando su posición en pantalla. Falta
  que José le dé a reproducir y compruebe con los ojos que el cursor va suave y
  que los seis carriles se corresponden con lo que se oye y se ve.

---

## BLOQUE C — Zoom, desplazamiento e imán

**Estado: hecho.**

### Qué se puede hacer ahora

- **Zoom** de 1x a 40x: `Ctrl` + rueda sobre la tira, o los botones `−` / `+` /
  `Todo`. Acercar **mantiene quieto el instante que está bajo el cursor**, así
  que ampliar sobre el segundo 20 no salta al principio del video. Aparece
  desplazamiento horizontal, y la regla se afina sola (de marcas cada 2s a
  marcas cada décima) según lo que quepa.
- **Arrastre magnético** en los tres carriles de en medio (B-Roll/PiP,
  animaciones y SFX). Al soltar cerca de un borde de palabra o de un beat del
  guion, el marcador se pega exacto y una guía de color dice a cuál: verde para
  bordes de palabra, ámbar para beats. La barra escribe «pegado a un borde de
  palabra» / «pegado a un beat del guion».
- **El imán se suelta** con la casilla, o con `Alt` mientras se arrastra —
  sin tener que destildar nada para un solo movimiento.

### Qué decidí y por qué

- **La tolerancia del imán se mide en PÍXELES, no en segundos**
  (`IMAN_TOLERANCIA_PX = 8`, convertida a segundos con el zoom actual). Es la
  decisión que hace que el imán no estorbe: a 1x agarra dentro de 0.22s, que es
  lo que se quiere cuando se ve el video entero; a 20x agarra dentro de 0.011s,
  o sea que cuando ya se ve el fotograma la ayuda se aparta sola en vez de
  seguir pegando todo a medio segundo. Medido en el navegador, no deducido.
- **A igual distancia gana el beat**, no el borde de palabra: un beat es una
  decisión editorial explícita del guion y un borde de palabra es solo dónde
  calló Whisper. Mismo criterio que la prioridad de SFX del bloque 3 de
  `PLAN-MEJORAS.md`.
- **Se mueve el bloque ENTERO, nunca sus bordes.** Estirar un B-Roll ya se hace
  en su pista de siempre, que conoce `duracionMaximaClip(ev)` y frena en el
  tramo recortado del clip (bloque 4). Moviéndolo entero la duración no cambia,
  así que **ese tope no se puede violar desde la tira** — no hay que replicarlo
  ni hay una segunda forma de romperlo. Hay una prueba que falla si aparece un
  tirador de redimensionado en la tira.
- **Las animaciones se mueven llamando a `moverAnimacion()`**, la función que ya
  existe: hace el clamp con la duración real del clip y marca
  `animacionesModificado`. Replicar su lógica habría permitido que el mismo
  gesto diera resultados distintos según se hiciera en la tira o en la pista.
- **Sin Ctrl, la rueda no hace zoom.** Se comprueba en una prueba: si la tira
  se tragara la rueda a secas, bajar por el editor con el ratón encima sería
  imposible.
- El imán se pega al valor EXACTO del punto (3 decimales). Las pistas viejas
  redondean a 2 (`tiempoDesdeEvento`); son caminos distintos y los dos válidos,
  pero conviene saberlo: mover el mismo SFX en la tira y en su pista puede
  dejar `2.783` o `2.78`. La diferencia es de un tercio de fotograma.

### El hallazgo que conviene recordar

**Cuatro de los seis beats de `Guion-7` caen EXACTAMENTE sobre un borde de
palabra** (distancia 0.0000s), porque `f13_guion.py` alinea los beats contra
palabras de la transcripción: el tiempo de un beat *es* un borde de palabra.
Los que no coinciden son los derivados — el fin de un tramo, el inicio de un
plano cerrado. O sea que en la práctica la regla de «a igual distancia gana el
beat» casi nunca se activa, y las dos familias del imán se solapan mucho más de
lo que parece.

Esto se descubrió porque la primera prueba del imán a beats **falló**: pedí
imantar a 0.03s del beat 6.4s y se pegó a 6.404s, un borde de palabra que
estaba a 4 milésimas del beat. El código hacía lo correcto (el más cercano
gana); la prueba había elegido un beat que no servía para distinguir nada. Se
reescribió para buscar un beat aislado de verdad (10.816s, a 0.11s del borde
más cercano).

### Verificación hecha

- `python editor/test_regresion.py` (202) y `python editor/test_align.py`: en
  verde. `python editor/test_tira.py`: **52 pruebas** (17 nuevas en la sección
  5). Cubren que el zoom y la tolerancia se lean de `/datos`, que la tolerancia
  se convierta de píxeles a segundos, que la rueda solo actúe con Ctrl, que se
  muevan bloques enteros y no bordes, que las animaciones usen
  `moverAnimacion()`, que mover marque el flag de «editado a mano» —sin él el
  cambio se ve en pantalla y el re-render lo tira— y que al soltar se refresquen
  las siete funciones de las secciones de siempre.
- `node --check` sobre `tira.js` y sobre el `<script>` extraído: sin errores.
- **En el navegador de verdad** (Edge headless + CDP), contra una copia limpia
  de `_prueba-tira` recreada justo antes:
  - Zoom por botones: 4 clics dan 1.25⁴, el lienzo pasa de 891px visibles a
    2174px reales, aparece desplazamiento y la regla pasa de 13 a 25 marcas.
  - `Ctrl`+rueda ×5 → 3.05x, y el instante bajo el cursor se movió de 18.6248s
    a 18.6290s: **4 milésimas**, con el lienzo desplazado 1371px para
    conservarlo. La misma rueda sin Ctrl no cambió el zoom.
  - Arrastre real de un SFX (eventos `pointerdown`/`pointermove`/`pointerup`
    despachados sobre el elemento): soltado en 8.425s → **pegado a 8.465s
    exacto**, guía verde encendida, aviso escrito, `sfxModificado` en true, y
    **el marcador de la pista de SFX de siempre se movió al mismo sitio**
    (34.0877% = 8.465s) — la tira y la pista vieja no se desincronizan.
  - El mismo gesto con `Alt`: se quedó en 8.425s y no se encendió ninguna guía.
  - Imán a un beat aislado (10.816s): se pegó y lo identificó como beat.
  - Tolerancia: a 1x (0.2231s) un desvío de 0.15s se imanta; a 20x (0.0112s) el
    mismo desvío ya no.
  - Casilla: destildar apaga el imán, volver a tildarla lo enciende.
  - Arrastre de un B-Roll: se movió 3s exactos **sin cambiar su duración**
    (1.85s antes y después), y empujado más allá del final se frenó en 24.833s.
  - Consola del navegador **vacía** en las dos tandas.
  - Captura a 3.1x: se leen los nombres completos de los clips y el texto de
    los subtítulos, que a 1x no cabían.
- **El otro camino del pipeline también**: una corrida **sin `--guion` y sin
  render** (`es_renderizado: false`, sin ningún `guion.*.json` ni
  `10_guion-alineado.md`) levantada aparte en el puerto 8802. La tira se
  enciende igual, pinta los seis carriles, calcula los 21 bloques de subtítulo,
  **no dibuja ninguna marca de beat** —porque no hay— y el imán sigue
  funcionando con los 147 bordes de palabra. Era el caso con más probabilidad
  de reventar y es el que sale cuando se corre el pipeline sin número de guion.

### Archivos tocados

- `editor/web/tira.js`, `editor/web/tira.css` — zoom, imán y arrastre
- `editor/test_tira.py` — sección 5

### Lo que NO pude verificar

- **Arrastre con un ratón de verdad.** En headless no hay puntero: se despachan
  eventos `pointerdown`/`pointermove`/`pointerup`, que ejercitan exactamente el
  mismo código pero no pasan por el sistema de ventanas. Falta que José agarre
  un B-Roll y lo mueva: que el cursor cambie a la manita, que el bloque siga al
  ratón sin tirones y que la guía del imán se vea encenderse al acercarse.
- **La rueda física con Ctrl.** Se probó con un `WheelEvent` sintético. En
  algunos ratones y trackpads Windows manda `deltaY` en pasos distintos; si el
  zoom se sintiera brusco o al revés, el número a tocar es
  `f14_tira.ZOOM_FACTOR` (1.25), no el JS.
- **Reproducción del video**, igual que en el bloque A: Edge headless no trae
  el decodificador H.264. En particular falta comprobar que el **desplazamiento
  automático** (con zoom > 1, la tira sigue al cursor cuando se sale de la
  vista) no marea al reproducir.

---

## Notas operativas de esta sesión

- El worktree `C:\ai-video\wt-tira` necesita enlaces a las carpetas pesadas que
  no están en git. Se hicieron con *junctions* de Windows (no hacen falta
  permisos de administrador):
  `assets` (la carpeta entera, borrando antes la que había creado el checkout),
  `entrada` y `salida`. Git ve el contenido a través del junction; los `M` que
  aparecen en `git status` sobre `assets/` son solo ruido de fin de línea
  (`git diff` sale vacío).
- **El worktree se deja en pie a propósito.** Queda la verificación manual
  (arrastre con ratón, reproducción del video) y desde ahí se puede abrir el
  editor sin tocar el repo principal, donde otra sesión sigue trabajando:

  ```
  C:\ai-video\venv312\Scripts\python.exe editor/f11_servidor.py "C:\ai-video\salida\Guion-7" --puerto 8801
  ```

  Cuando José integre `mejoras-tira` en `mejoras-editor`:
  `git worktree remove C:\ai-video\wt-tira` (los junctions se van con él).
- Los únicos archivos tocados son los siete de la lista de cada bloque.
  `git diff --name-only mejoras-editor..mejoras-tira` lo confirma: no se tocó
  `test_regresion.py`, ni `PLAN-MEJORAS.md`, ni ninguno de los archivos del
  bloque de silencios (`f2_cortar.py`, `editor.py`, `f15_silencios.py`,
  `editor/web/silencios.js`, `PLAN-SILENCIOS.md`, `test_silencios.py`).
- **Percance a evitar**: para limpiar el servidor de verificación se hizo un
  `Stop-Process` filtrando por nombre `python.exe`, y cayeron **seis** procesos
  cuando solo uno era el servidor de esta sesión. Hay otra sesión de Claude
  trabajando en paralelo sobre este mismo repo. Lo correcto es guardar el PID
  al lanzar (`Start-Process -PassThru`) y matar solo ese, o filtrar por
  `CommandLine`. Se comprobó después que ninguna corrida real cambió de mtime.
- Toda la verificación se hizo contra `C:\ai-video\salida\_prueba-tira`, copia
  descartable de `Guion-7`, recreada entre tandas para partir siempre de un
  estado conocido (el autoguardado del editor escribe `ajustes.*.json` en
  cuanto se mueve algo). El `Guion-7` real no se tocó en ningún momento y se
  comprobó su mtime al empezar y al terminar. La copia se borra al cerrar.
