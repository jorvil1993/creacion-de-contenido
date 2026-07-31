# Bloque B — Ver y deshacer el corte de silencios

Bitácora de la sesión que construyó el editor de silencios, en la rama
`mejoras-silencios` (worktree aparte: `C:\ai-video\wt-silencios`). Mismo formato
que las entradas de `PLAN-MEJORAS.md`, en archivo propio para no chocar con la
sesión que trabaja en paralelo sobre la tira de capas.

---

## Qué se pidió

`f2_cortar.py` recorta silencios, muletillas y tomas repetidas sin dejar rastro
visible: José ve el video ya cortado y no sabe qué se fue ni puede recuperarlo.
Había que poder ver en la línea de tiempo qué tramos se recortaron y por qué, y
restaurar o ajustar cualquiera de ellos.

---

## La decisión de fondo: se re-corta desde la grabación original

El encargo planteaba dos caminos —(a) regenerar el corte, (b) remapear en
sitio— y pedía verificar cuál era el correcto antes de escribir código.

**(b) es imposible, y se puede medir.** El metraje de un tramo recortado no
está en `02_cortado.mp4`: ffmpeg lo descartó al concatenar los intervalos
conservados. Sobre `Guion-7`:

| | duración |
|---|---|
| grabación original (`contexto/Guion-7.mp4`) | 39.914s |
| `02_cortado.mp4` | 24.834s |
| suma de `intervalos_conservados_original` | 24.814s |

Los 7.6s del silencio inicial no están en ninguna parte de ese archivo. Ningún
ajuste de coordenadas los puede traer de vuelta. **Restaurar es volver a cortar
la grabación original con otra lista de cortes, y no hay atajo.**

(De paso, esos 20 ms entre 24.834 y 24.814 son el cuadre al fotograma de
ffmpeg: la aritmética de intervalos y el archivo real no coinciden al
milisegundo. Por eso el umbral de aviso del remapeo es 50 ms y no 1 ms.)

**Pero (a) no obliga a re-correr el pipeline entero sin `--reaplicar`,** que es
como estaba planteado. Lo caro es WhisperX (`large-v3`), y la transcripción **no
depende de dónde estén los cortes**: `01_transcripcion.json` cubre la grabación
entera —palabras, segmentos, silencios y la ruta de la fuente— y sigue siendo
válida palabra por palabra después de mover cualquier corte. Así que el bloque
introduce un tercer modo, entre `--reaplicar` y la corrida completa:

    --reaplicar --silencios ajustes.silencios.json

que reutiliza la transcripción, **rehace el corte** (ffmpeg, segundos) y
**rehace el análisis de retención**, y sigue con el resto como siempre.

### Por qué el análisis de retención también se rehace

`03_retencion.plan.json` guarda el track del rostro y la curva de acercamientos
**indexados por segundo del video cortado**. Tras mover un corte apuntan al
fotograma equivocado. Reusarlo era el fallo silencioso de este bloque: el video
sale, se sube, y lo único raro es que el zoom se cierra medio segundo tarde.
La condición pasó de `if not args.reaplicar:` a
`if not args.reaplicar or recorte_rehecho:`, y hay una prueba que lo comprueba
sobre el texto fuente.

---

## Cómo sobreviven los ajustes ya hechos

Los `ajustes.*.json` guardan segundos de la línea de tiempo **cortada**, que es
justo la que cambia. Se remapean componiendo dos funciones:

    tiempo_viejo --mapear_a_original(intervalos_viejos)--> grabación original
                 --mapear_a_nueva_linea(intervalos_nuevos)--> tiempo_nuevo

La grabación original es el único sistema de coordenadas que no se mueve.
`mapear_a_original` es nueva (`f2_cortar.py`, al lado de su gemela) y es la
inversa exacta: **verificado sobre `Guion-7` con paso de 10 ms, error máximo
0.000 ms**, y otra vez sobre intervalos sintéticos en `test_silencios.py`.

### Los eventos con duración conservan su duración, no su instante final

Un B-roll de 1.85s sigue durando 1.85s aunque en medio se restaure un silencio
de 7.6s. Estirarlo hasta el nuevo final convertiría un inserto en un plano fijo
de nueve segundos. Comprobado con datos reales de `Guion-7`: al restaurar el
silencio inicial, los 4 B-roll y el PiP conservan su duración exacta porque no
cruzaban el tramo; **el hook sí lo cruzaba y se habría estirado de 3.20s a
10.80s**.

### La regla no negociable: lo ambiguo se avisa

Cuando el fin remapeado directo y el fin con duración preservada difieren en más
de 50 ms, el evento abarcaba metraje que antes no existía. Se conserva la
duración **y se emite un aviso**. Lo mismo si un ajuste queda más allá del final
del video nuevo: se acorta y se avisa.

Los avisos se escriben en `ajustes.silencios.avisos.json` porque **el remapeo
ocurre durante el render, con el editor cerrado**: sin dejarlos en disco, el
único rastro de que un evento cambió de duración sería una línea en una consola
que ya se cerró. El editor los pinta en amarillo al volver a abrirse.

Y si falta la grabación original, no se re-corta: se avisa por consola, se
renderiza con el corte actual, y en el editor las casillas salen deshabilitadas
con la explicación. Antes que renderizar algo silenciosamente distinto de lo
que se pidió.

---

## El catálogo se recalcula, no se lee de lo aplicado

`f15_silencios.catalogo()` vuelve a llamar a los detectores de `f2_cortar` sobre
`01_transcripcion.json` en vez de leer `cortes_aplicados` de `02_cortado.json`.
Es la diferencia entre que el bloque funcione una vez o siempre: al restaurar un
tramo, ese corte desaparece de `cortes_aplicados`, así que un catálogo sacado de
ahí lo perdería de la lista y no habría forma de volver a cortarlo. La
transcripción, en cambio, no cambia nunca. Hay una prueba dedicada a esto
(«se puede volver a cortar lo que se había restaurado»).

Para que el recálculo dé exactamente los mismos tramos que se aplicaron,
`f2_cortar` ahora guarda `corte_parametros` (conservar_inicio/fin, presentador,
duración original, archivo fuente). Las corridas anteriores no lo tienen y caen
a los valores por defecto — comprobado contra `Guion-7`: el catálogo recalculado
coincide tramo a tramo con sus 7 `cortes_aplicados`.

**Identificador estable**: `silencio-14.578`, construido con el inicio
*detectado automáticamente* y en coordenadas del original. Si dependiera de los
límites ajustados a mano, mover un tirador desharía la elección guardada.

---

## Lo que se puede hacer ahora

Panel nuevo **«Silencios recortados»**, justo antes de Encuadre:

- Una barra con la **grabación entera** (no el video que se está viendo: los
  tramos cortados no existen en esa línea de tiempo), con cada tramo en rojo.
- Una fila por tramo: tipo, segundos, razón legible («silencio de 7.90s»,
  «muletilla 'nada'»). Destildar la casilla lo devuelve al video.
- **Tiradores** en los silencios para cortar menos y dejar más aire. No pueden
  pasarse del silencio detectado: cortar más sería empezar a llevarse habla, y
  este bloque existe para lo contrario. Las muletillas y las tomas repetidas no
  llevan tiradores — se cortan o no, cortar media no significa nada.
- El resumen dice cuánto va a durar el video resultante, y avisa de que hay
  cambios sin aplicar hasta que se vuelva a renderizar.

Se guarda en `ajustes.silencios.json`, que viaja con las **versiones con
nombre** (`ARCHIVOS_AJUSTES`): sin eso, cargar una versión vieja habría
devuelto sus PiP y sus SFX con el corte de ahora — el híbrido que el bloque de
versiones existe para evitar.

Solo se guarda lo que se **aparta** del automático. Un tramo ausente del archivo
es un tramo que se corta como siempre, así que el archivo sigue siendo válido
cuando el catálogo cambia (otro guion, otro `hooksegs`).

---

## Verificación hecha

**Suites del proyecto**: `test_regresion.py` (202) y `test_align.py` en verde
antes de tocar nada y al terminar. `test_align.py` importa especialmente aquí:
es el que caza el desfase de alineación.

**`test_silencios.py`, 55 pruebas nuevas.** La central corta un clip de verdad
con ffmpeg (lavfi con silencios reales), restaura un tramo y comprueba que un
SFX colocado sobre la palabra `p8` **sigue sobre `p8`** después: pasó de 4.30s a
8.00s, exactamente lo mismo que la palabra. Con una segunda comprobación de que
el SFX de verdad se movió, para que la prueba no pueda pasar por no haber hecho
nada. También: la inversa exacta, el B-roll que conserva duración y palabra, los
topes de los tiradores, el catálogo que no pierde el tramo restaurado, el
respaldo `.previo`, los avisos, y que un `ajustes.silencios.json` corrupto no
rompe el corte.

**Sintaxis**: `compile()` sobre los 5 módulos de Python (no `ast.parse` — ver
abajo) y `node --check` sobre `editor/web/silencios.js` y sobre el `<script>`
completo extraído de `f11_servidor.py`.

**El editor abierto de verdad**, Chrome headless + CDP, contra la copia
descartable `_prueba-silencios` (nunca `Guion-7`), confirmando por `/datos` que
el `nombre` servido era el de la copia antes de sacar ninguna conclusión:

- Panel cargado: 7 filas y 7 barras, resumen «grabación 39.9s → video 24.8s».
  La primera barra ocupa el 19.05% del ancho = 7.6s de 39.9s, exacto.
- Tiradores por barra: `2,2,2,2,0,2,2` — el cero es la muletilla, que no es
  ajustable. Salió bien a la primera.
- **Clic real** en la casilla del silencio inicial: el resumen pasó a
  «se cortan 6 (7.5s) · 1 devuelto(s) al video (+7.6s) · video 32.4s», apareció
  el aviso de pendiente de render, la barra quedó punteada y sin tiradores, y
  `ajustes.silencios.json` apareció en disco con el contenido correcto. Los
  32.4s calculados coinciden con los 32.42s que dio el re-corte real de ffmpeg.
- **Arrastre real** (eventos de ratón de CDP, no simulados desde JS): el corte
  pasó de 1.92s a 1.03s y el resumen se actualizó solo. Arrastrando 400px hacia
  fuera se frenó exactamente en 16.649s, que es el `limite_fin` del silencio.
- **Avisos**: tras un re-corte de verdad, los 2 avisos aparecen en amarillo con
  su texto completo, y `DATA.hook_cta_guardado` confirma que el hook conservó su
  duración de 3.20s en vez de estirarse a 10.80s.

**De punta a punta**, y es la prueba que más valió la pena:
`editor.py --reaplicar --guion 7 --preview --silencios ...` sobre la copia,
con el silencio inicial marcado para restaurar. **Destapó dos fallos que
ninguna de las 50 pruebas anteriores veía, y los dos eran silenciosos.**

Con los dos arreglados, la corrida entera hace lo que tiene que hacer:

```
Editor de silencios: 1 tramo(s) NO se cortan (restaurados a mano)
Duración original: 39.9s -> resultante: 32.4s
FASE 1b-bis: Re-corte con los silencios restaurados
  remapeado: ajustes.eventos.json / broll / hookcta / sfx / sesion
  AVISO [hookcta] hook: se conserva su duración de 3.20s en vez de estirarlo hasta 10.80s
  AVISO [hookcta] cta: termina en 32.43s, más allá del final del video; se acorta
Face tracking: 823 frames   (antes 742: el plan de retención SE REHIZO)
```

`07_PREVIEW.mp4` mide 32.33s contra los 32.42s de `02_cortado.mp4` — la
diferencia es el cuadre del render, no un desfase. Los SFX remapeados caen
sobre las mismas palabras que antes, y `ajustes.sfx.json.previo` conserva los
tiempos de partida.

### Fallo 1: un BOM dejaba el bloque entero sin efecto

`ajustes.silencios.json` escrito con BOM (lo pone `Out-File -Encoding utf8` de
PowerShell, y el Bloc de notas) reventaba en `json.loads` con `utf-8` a secas.
La excepción estaba capturada y devolvía `{"cortes": {}}`, así que
`hay_cambios()` decía False, el re-corte **no se ejecutaba, y el render salía
con la duración de siempre sin un solo mensaje**. Exactamente la clase de fallo
que este proyecto persigue.

Arreglado en dos sentidos: todas las lecturas pasan por `_leer_json()`, que usa
`utf-8-sig` (se come el BOM si está, idéntico a `utf-8` si no); y un archivo de
selección ilegible **ya no se traga en silencio** — se avisa por `stderr`
diciendo que lo elegido en el editor no se ha aplicado. Con prueba de regresión
que escribe el BOM a mano.

### Fallo 2: el identificador de un tramo cambiaba con `hooksegs`

El id colgaba del inicio del CORTE. Pero el corte del silencio inicial depende
de `hooksegs` del panel: con 0 va de 0.15s a 7.75s (`silencio-0.150`), con 3 va
de 0.00s a 4.90s (`silencio-0.000`). Al pasar `--guion 7`, la elección guardada
apuntaba a un tramo que ya no existía y **el silencio restaurado volvía a
cortarse, en silencio**. Se vio porque el video salió de 27.5s en vez de 32.4s.

Ahora el id cuelga del SILENCIO de origen (`limite_inicio`), que sale de la
transcripción y no depende de ningún parámetro: el mismo silencio da
`silencio-0.000` con y sin hook físico. Y como los parámetros pueden cambiar de
todos modos (otro presentador, una re-transcripción), `datos_silencios()` expone
`huerfanos`: las elecciones guardadas que ya no encajan con ningún tramo, que el
editor pinta en amarillo en vez de dejarlas desaparecer.

---

## Lo que se aprendió por el camino

- **`ast.parse` no basta para comprobar Python.** El endpoint nuevo usaba
  `DIR_TRABAJO` unas líneas antes del `global DIR_TRABAJO` que `do_POST` declara
  más abajo. `ast.parse` lo daba por bueno; el módulo reventaba al importarse
  con `SyntaxError: name 'DIR_TRABAJO' is used prior to global declaration`. Se
  resolvió con una función de módulo (`_datos_silencios_actuales()`) en vez de
  tocar la función existente. **Usar `compile()`, no `ast.parse()`.**
- **`encoding="utf-8"` no salva de la codificación de Windows.** El subproceso
  de `f2_cortar` imprime acentos en cp1252 y el hilo lector de `subprocess`
  moría con `UnicodeDecodeError` — leído como si hubiera fallado el corte, que
  es otra cosa. Hace falta `errors="replace"` además del encoding.
- **`config.perfil()` solo entiende la clave, no el nombre.** `PERFIL["nombre"]`
  es `"José"`, y guardarlo en `corte_parametros` hacía reventar el catálogo con
  `Presentador desconocido: 'José'`. Se guarda `args.presentador`, y el catálogo
  cae al perfil por defecto si la clave no se reconoce.
- **`Input.dispatchMouseEvent` usa coordenadas del viewport.** El panel está a
  y=3812 y el viewport medía 2305: el primer arrastre no hizo nada y no dio
  ningún error. Hay que `scrollIntoView` antes. Es del arnés de pruebas, no del
  código, pero cuesta media hora descubrirlo.
- **Las 55 pruebas unitarias no habrían encontrado ninguno de los dos fallos
  serios.** El del BOM necesitaba un archivo escrito por otra herramienta; el
  del identificador necesitaba `--guion 7`, que es lo que introduce `hooksegs`.
  Los dos aparecieron a los dos minutos de correr el pipeline de verdad. En un
  bloque que toca la línea de tiempo, la corrida completa no es la comprobación
  final: es donde están los fallos que las pruebas no ven.

---

## Archivos tocados

Nuevos, todos propios de este bloque:

- `editor/f15_silencios.py` — catálogo, selección, remapeo y avisos.
- `editor/web/silencios.js` — toda la interfaz del panel.
- `editor/test_silencios.py` — 50 pruebas.
- `editor/PLAN-SILENCIOS.md` — esta bitácora.

Existentes:

- `editor/f2_cortar.py` — `mapear_a_original`, `detectar_todos_los_cortes`,
  `--silencios`, `limite_inicio`/`limite_fin` en los cortes de silencio y
  `corte_parametros` en el JSON de salida.
- `editor/editor.py` — bandera `--silencios`, el re-corte dentro de
  `--reaplicar`, el remapeo, y el análisis de retención rehecho.
- `editor/f11_servidor.py` — 6 anclas: `ARCHIVOS_AJUSTES`, `GET /silencios.js`,
  `POST /guardar-silencios`, `_guardar_silencios` + `_datos_silencios_actuales`,
  la `<section>` del panel, el `<script src>`, la línea en `cargar()`, y la
  propagación de `--silencios` en `/render`.
- `editor/f10_editor_visual.py` — una línea en `recolectar()` y su import.

---

## Lo que NO se pudo verificar

- **Que el video restaurado se vea y se oiga bien.** Chrome headless no trae el
  decodificador y no hay forma de reproducir audio en este entorno. La
  aritmética está comprobada y el archivo se genera con la duración correcta,
  pero falta que José abra una corrida con un silencio restaurado y confirme con
  los ojos que el tramo devuelto es el que esperaba y que el corte no dejó un
  salto raro en la imagen.
- **El arrastre con un ratón físico.** Se verificó con eventos de ratón reales
  de CDP, que Chrome convierte en `pointerdown`/`move`/`up` igual que un ratón,
  pero no es lo mismo que la mano de una persona.
- **Los presets con el perfil de la esposa.** El catálogo se recalcula con el
  perfil guardado, y el de la esposa sigue sin calibrar con grabación real
  (pendiente ya conocido del proyecto).

---

## Siguiente paso

Este bloque está cerrado. Para quien integre:

- La rama es `mejoras-silencios` y **no se fusionó**: José integra al final.
- Fusionar **después** de `mejoras-tira`, que es dueña del endpoint estático.
  Los choques esperables son dos líneas adyacentes al final de `cargar()` y dos
  `<script>` al final de `PAGINA`; en los dos casos la resolución es quedarse
  con las dos partes.
- **Después de fusionar, correr `node --check` sobre el `<script>` de
  `f11_servidor.py` antes que cualquier test de Python.** Es lo único que
  detecta el JS roto por un merge.
- Si el panel de silencios acaba dentro de la tira de capas del bloque A, el
  dato ya está listo: `DATA.silencios.tramos` trae cada tramo en coordenadas de
  la grabación original y `t_en_video` con la costura en el video actual.
