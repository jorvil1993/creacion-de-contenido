# Cómo se llama a este pipeline

Referencia para un agente que reciba el encargo en lenguaje natural («editame
el video de ayer», «hacé el guion 7», «cambiá la música y volvé a sacarlo»).
Traducí el pedido a uno de los casos de abajo. Si ninguno encaja, preguntá
antes de inventar banderas.

Todo se corre desde la raíz del proyecto con el Python del entorno:

```
C:\ai-video\venv312\Scripts\python.exe editor/editor.py ...
```

Las salidas intermedias van a `C:\ai-video\salida\<nombre>\` (fuera de OneDrive,
a propósito). Solo el video final se copia a `salida/` del proyecto.

---

## Si lo va a hacer José: la pantalla de preparación

Doble clic en **`editor/Preparar grabación.bat`** (o `python editor/preparar.py`).
Abre una pantalla en el navegador que hace todo lo de abajo sin escribir nada:

1. Lista los videos de `entrada/` y deja elegir uno o varios.
2. Por cada clip, recorta el principio y el final con dos manijas. **Propone los
   puntos solo**, buscando el primer y el último sonido real (`silencedetect` de
   ffmpeg, no transcribe: tarda décimas de segundo). Lo normal es mirar y aceptar.
   **Espacio** reproduce el clip activo, y se detiene en el punto de corte.
3. Ordena los clips y muestra el total de segundos que va a quedar.
4. Elige el número de guion.
5. **«Ver cómo quedan unidas»** — previa en baja resolución del montaje completo.
   Usa la misma función de unión que el pipeline, así que lo que se ve ahí es lo
   que va a entrar al render, no una aproximación.
6. **«Empezar»** — la pantalla se apaga y arranca el pipeline en la misma
   terminal. Al terminar se abre el editor visual como en cualquier corrida.

Lo elegido se guarda en `<video>.preparado.json`, al lado del archivo de entrada.
A partir de ahí, **cualquier corrida sobre ese material aplica esos recortes
sola** — incluida la de un agente, que no tiene que saber nada de esto. Para
ignorarlos, borrá ese archivo o pasá `--desde/--hasta`.

El recorte se aplica **antes de transcribir**. Esa es la razón de que sea barato:
el resto del pipeline mira un solo archivo ya recortado y ninguna coordenada de
tiempo de aguas abajo (palabras, SFX, overlays, encuadre, `ajustes.*.json`) se
entera de que hubo un recorte.

La pantalla **no reencuadra**: no hay zoom ahí. El encuadre fino va en el panel
de Encuadre del editor visual, que es donde se combina bien con la curva de
acercamientos del pipeline.

---

## El panel de producción conectado

Doble clic en **`editor/Panel de producción.bat`** (o
`python editor/panel_servidor.py`). Sirve `PANEL-PRODUCCION.html` en
`http://127.0.0.1:8899/` y le enciende tres cosas que sin servidor no puede hacer:

- **Elegir la grabación cruda.** Salen solas las de `entrada/`; el botón
  «Buscar en el disco» abre el selector de archivos de Windows, porque una página
  web no puede saber la ruta absoluta de un archivo y el pipeline la necesita.
- **Correr el pipeline** con el guion que se está mirando, y ver el log en vivo.
  Corre con `--sin-abrir-editor` a propósito: el editor visual es un servidor que
  no termina nunca, así que se abre después con su botón, ya como proceso aparte.
- **Cambiar cada fila de la línea de tiempo** entre `YO`, `B-ROLL`, `PIP` y `ANIM`,
  con qué clip y cómo entra (tapa el cuadro / detrás de mí / arriba a la
  derecha / arriba a la izquierda). Se guarda en `PANEL-PRODUCCION.html`, que es
  de donde lee el pipeline.

**El mismo archivo se publica en GitHub Pages**
(`jorvil1993.github.io/creacion-de-contenido/PANEL-PRODUCCION.html`) para leerlo
desde el celular. Allá no hay servidor, así que todo lo anterior **se esconde
solo** y queda la página de lectura: guiones, tomas, teleprompter, prompts y la
línea de tiempo. No hay dos copias del panel — la diferencia la decide un `fetch`
a `/api/estado` al cargar la página.

Sin servidor pero en la PC (el panel abierto como `file://`), los selectores
siguen guardando con el selector de archivos de Chrome/Edge. Ese camino escribe
el archivo con **el mismo algoritmo** que el servidor, y `test_regresion`
compara las dos implementaciones para que no se separen.

---

## El caso normal: una grabación → un video publicable

```bash
python editor/editor.py "entrada/mi_video.mp4" --guion 7
```

`--guion N` es el número de la fila de `PANEL-PRODUCCION.html`. De ahí salen el
hook, los SFX, las animaciones, los B-rolls, los acercamientos y la música.
**Sin `--guion` el pipeline improvisa**: saca todo de la transcripción y del
catálogo. Para un video de verdad, pasalo casi siempre.

Al terminar **se abre solo el editor visual** en el navegador con ese video
cargado. Se cierra con Ctrl+C.

### Si querés el B-roll DETRÁS tuyo en vez de taparte

Cada B-roll entra de una de dos formas:

- **tapa el cuadro** (lo de siempre): el clip ocupa la pantalla entera y vos
  desaparecés esos segundos.
- **detrás de mí**: el clip ocupa el 70% de arriba, el borde de abajo se
  desvanece, y vos quedás recortado **por delante** — se te ve la cara y las
  manos pasan por encima del clip. Es el efecto "pantalla verde" de TikTok.

Se elige en dos sitios, y los dos escriben lo mismo:

- **En el panel**, en la columna «Qué se ve» de cada fila hay un selector con las
  siete formas de entrar (`YO`, B-ROLL ×2, PIP ×2, ANIM ×2) y otro para el clip.
  Guarda en `PANEL-PRODUCCION.html`. También se puede escribir a mano: lo que el
  pipeline busca en ese texto es la frase **«detrás de mí»**.
- **En el editor visual**, en la tarjeta de cada B-roll, el mismo selector de
  siempre ahora tiene tres opciones en vez de dos.

### Si querés que una fila sea PIP en vez de B-roll (o al revés)

Mismo selector del panel. Cambia dos cosas a la vez: la columna «En pantalla»
(que es lo que decide el tipo) y la frase dentro de «Qué se ve» (que es lo que
decide la posición). Un mismo `.mp4` sirve para las dos: a pantalla completa es
B-roll, y recortado a 400×520 con marco es PIP — **lo decide esta tabla**.

Poner una fila en `YO` no borra con qué clip estaba: apaga el inserto y deja el
texto, para poder volver a encenderla sin reescribir nada.

Qué cuesta: el recorte lo hace un modelo en la GPU (~17 fps), y solo corre en
los segundos que dura el B-roll. Un clip de 3s son unos 5 segundos de proceso.
La primera vez se descarga el modelo (~100 MB) a `C:\ai-video\models\rvm\`.

Si la GPU o el modelo no están, el video **sale igual**: ese B-roll vuelve a
pantalla completa y queda un AVISO en el log.

```bash
python editor/f17_matte.py --estado    # ver si el modelo está y qué GPU hay
```

### Si grabó en dos planos reales

Pasá los archivos en orden. El pipeline los une y marca los empalmes como los
únicos cambios de plano del video.

```bash
python editor/editor.py "entrada/plano-abierto.mp4" "entrada/plano-cerrado.mp4" --guion 7
```

Son **tomas seguidas** (la parte 1 en plano abierto, la parte 2 en cerrado), no
dos ángulos de la misma frase: para cortar entre ángulos haría falta el mismo
audio en los dos clips y no lo hay.

### Si sobran segundos al principio o al final

`--desde` y `--hasta` recortan sin abrir ninguna pantalla, para una corrida de
agente. Solo valen con **un** archivo de entrada.

```bash
python editor/editor.py "entrada/mi_video.mp4" --guion 7 --desde 7.5 --hasta 44
```

Importa más de lo que parece: la transcripción corre sobre el archivo entero, y
las palabras sueltas de antes de empezar disparan insertos equivocados (los PiP
se eligen por palabra dicha, `config.PALABRAS_A_TAGS`).

**Ojo con `hooksegs`.** Si el guion pide hook físico, f2_cortar conserva esos
segundos de silencio antes de la primera palabra —el gesto de entrar al cuadro—
así que el recorte tiene que dejarle ese aire por delante. La pantalla de
preparación avisa sola; por línea de comandos hay que acordarse.

### Si habla la esposa de José y no él

```bash
python editor/editor.py "entrada/video.mp4" --guion 7 --presentador esposa
```

Cambia las muletillas que se recortan, el umbral de silencio y la calibración
de los acercamientos.

---

## Volver sobre un video que ya se hizo

`--reaplicar` reutiliza la transcripción, el corte y el análisis de retención de
una corrida anterior con el mismo `--nombre`. Es la diferencia entre segundos y
un minuto largo.

```bash
python editor/editor.py "entrada/mi_video.mp4" --nombre Guion-7 --reaplicar --guion 7
```

**Trampa conocida:** `hooksegs` y `cierresegs` (los segundos de hook físico que
se conservan al principio y al final) se aplican **al cortar**, y `--reaplicar`
no vuelve a cortar. Si se cambiaron esos valores en el panel, hay que correr
**sin** `--reaplicar`.

---

## Solo abrir el editor de un video ya hecho

```bash
python editor/abrir_editor.py Guion-7        # por nombre de corrida
python editor/abrir_editor.py               # la más reciente
```

O doble clic en `editor/Abrir Editor DeviceShop.bat`.

Dentro del editor hay un desplegable para saltar entre corridas sin cerrarlo, y
dos botones al final:

- **Previsualizar** — misma composición exacta a media resolución. No toca el
  archivo final ni publica nada. Para comprobar un ajuste.
- **Renderizar final** — el bueno, y lo copia a OneDrive listo para subir.

Todo lo que se ajusta **se guarda solo** cada par de segundos, así que cerrar la
pestaña no cuesta el trabajo: al volver a abrir la corrida está todo donde se
dejó, incluido el segundo del reproductor.

Para probar dos montajes del mismo video hay **versiones con nombre**: se guarda
una copia de todos los ajustes **y del plan sobre el que se hicieron**, así que
cargar una devuelve la edición exactamente como estaba, aunque entre medias se
haya renderizado otra cosa. Viven en `_versiones/<nombre>/` dentro de la carpeta
de la corrida. Cargar una reemplaza lo que haya en ese momento, no lo mezcla.

Lo único que una versión no puede rescatar es un **re-corte**: si se vuelve a
correr sin `--reaplicar`, la línea de tiempo cambia entera y los segundos de una
versión anterior apuntan a otro sitio. El editor lo detecta y avisa al cargarla.

**Espacio** reproduce y pausa desde cualquier parte del editor.

---

## Corridas desatendidas (un agente, una tanda nocturna)

El editor es un servidor: si se abre, **ocupa la terminal hasta Ctrl+C**. En
cualquier cosa que no vaya a mirar una persona en ese momento:

```bash
python editor/editor.py "entrada/video.mp4" --guion 7 --sin-abrir-editor
```

---

## Banderas por lo que pida el encargo

| Si el pedido dice… | Bandera |
|---|---|
| «que no se abra el editor», o es automatizado | `--sin-abrir-editor` |
| «probá cómo queda», «una prueba rápida» | `--preview` |
| «sin música» | `--sin-musica` |
| «con la pista X» | `--musica X.mp3` (de `assets/musica/`) |
| «este hook en vez del otro» | `--hook "texto"` |
| «que no invente imágenes con IA» | `--sin-generar` |
| «los insertos de ambiente en video» | `--video-ambiente` (minutos de GPU) |
| «reutilizá lo ya transcrito» | `--reaplicar` |
| «otro nombre de salida» | `--nombre X` |
| «cortale los primeros/últimos segundos» | `--desde N` / `--hasta N` |
| «poné una transición entre cortes» | `--transicion glitch` (ver lista abajo) |
| «más fuerte / más suave la transición» | `--intensidad-transicion 1.4` (0.5–1.5) |

Lo que se ajusta a mano en el editor viaja en archivos `ajustes.*.json` dentro
de la carpeta de la corrida, y el editor los reenvía solo al re-renderizar. No
hace falta pasarlos a mano.

---

## Transiciones entre cortes y animación de los PiP

Dos cosas distintas, y se controlan igual de fácil: **desde el panel
«Transiciones y animaciones» del editor visual** (lo normal) o con banderas.

### Transición entre cortes

Es lo que se dibuja en cada **salto de plano** (los empalmes que dejan el corte
de silencios y la unión de tomas). Todo es nativo de ffmpeg, no cambia la
duración del video y **no toca el audio**. Diez opciones:

| Nombre | Qué hace |
|---|---|
| `flash-blanco` | destello blanco de 2–3 frames (el «hit» clásico) |
| `flash-negro` | igual pero a negro, más dramático |
| `flash-marca` | destello en el cian de DeviceShop |
| `desenfoque` | golpe de desenfoque (whip) en el corte |
| `glitch` | desplazamiento RGB + ruido, estética digital |
| `zoom-punch` | empujón de zoom rápido que aterriza en el nuevo plano |
| `shake` | sacudida de cámara corta |
| `barrido` | una barra de luz cruza el cuadro tapando el corte |
| `zoom-desenfoque` | zoom-punch + desenfoque (el más usado en cortes de venta) |
| `destello-glitch` | flash de marca + glitch (para revelaciones) |

**Se ponen donde vos quieras, con una aguja.** En el panel «Transiciones y
animaciones» del editor hay una **tira de tiempo con una aguja** que sigue al
reproductor. El flujo es: llevás la aguja al segundo donde pausaste / cambiaste
el zoom (clic en la tira o movés el reproductor) y tocás **«＋ En el segundo
actual»**. Aparece una marca en ese punto y una fila debajo para elegirle el
tipo y la intensidad o quitarla. Podés poner las que quieras, en cualquier
lado. Los puntos tenues de la tira son los cortes que el pipeline detectó solo
(sugerencias): usalos o ignoralos.

Esto es lo que sirve para un **video ya unido** —grabado pausando, con zoom y
siguiendo— donde el salto visual no cae en ningún corte automático: marcás el
segundo exacto del salto y le ponés la transición encima.

**Para verlas en el video hay que renderizar** (el guardado solo las anota; no
se ven en el reproductor hasta el render). Desde el editor, el botón
**«Previsualizar»** alcanza: la transición se hornea en el corte, y aunque el
editor renderiza en modo rápido (`--reaplicar`), ahora **detecta que cambiaste
las transiciones y vuelve a cortar solo para hornearlas** (por eso ese render
tarda un poco más que uno normal — vuelve a pasar ffmpeg sobre la grabación,
pero no re-transcribe). Si no tocaste las transiciones, no re-corta.

La bandera `--transicion` sigue existiendo como atajo para ponerle la misma a
todos los cortes detectados desde la terminal.

Para ver las diez sobre un clip de prueba:

```bash
python editor/f2b_transiciones.py --demo   # deja los .mp4 en salida/transiciones/
```

### Animación de entrada y salida de los PiP

Cómo **entran y salen** las tarjetas de producto y las animaciones de esquina.
Antes solo hacían un fundido; ahora hay diez formas, elegibles por separado para
la entrada y para la salida. Esto **sí se ve con el render normal** (se aplica en
la pasada final, así que itera rápido con `--reaplicar`).

| Nombre | Cómo entra/sale |
|---|---|
| `fundido` | solo opacidad (lo de siempre, es el default) |
| `desliza-izquierda` / `desliza-derecha` | entra deslizando de ese lado |
| `desliza-arriba` / `desliza-abajo` | entra deslizando por arriba/abajo |
| `diagonal` | desde la esquina inferior |
| `resorte-arriba` | cae desde arriba con rebote |
| `resorte-lateral` | entra de lado con rebote |
| `latigazo` | entrada rápida con sobrepaso grande |
| `subir-fundido` | sube un poco y aparece |

**Se configura por PiP.** Cada tarjeta de la sección «Colección de PiP y
B-Rolls» tiene sus propios controles (entra / sale / fuerza), así que un PiP
puede entrar deslizando desde la izquierda y otro caer con rebote. En el panel
«Transiciones y animaciones» hay además un **valor por defecto** que se aplica a
los PiP que no toques uno por uno. Para **quitar** la animación de un PiP, poné
`fundido`; para hacerla más agresiva, subí la fuerza. Los B-roll a pantalla
completa y «detrás de mí» no llevan estas animaciones (son fondo).

Ambos ajustes quedan guardados en `ajustes.transiciones.json` (por empalme),
`ajustes.pip_anim.json` (el valor por defecto) y dentro de cada evento en
`ajustes.eventos.json` (el de cada PiP), en la carpeta de la corrida, y el
editor los reenvía solo al re-renderizar.

---

## Antes de dar por bueno un cambio

```bash
python editor/test_regresion.py    # aritmética de tiempos, vocabularios, editor→render
python editor/test_align.py        # alineación guion ↔ transcripción contra el panel real
```

La primera es la que caza la clase de fallo que no da error: el video sale, pero
sin los B-rolls o con los sonidos cambiados.
