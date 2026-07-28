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
