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

Lo que se ajusta a mano en el editor viaja en archivos `ajustes.*.json` dentro
de la carpeta de la corrida, y el editor los reenvía solo al re-renderizar. No
hace falta pasarlos a mano.

---

## Antes de dar por bueno un cambio

```bash
python editor/test_regresion.py    # aritmética de tiempos, vocabularios, editor→render
python editor/test_align.py        # alineación guion ↔ transcripción contra el panel real
```

La primera es la que caza la clase de fallo que no da error: el video sale, pero
sin los B-rolls o con los sonidos cambiados.
