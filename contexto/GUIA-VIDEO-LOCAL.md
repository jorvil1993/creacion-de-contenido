# Guía — Video generado en tu GPU (LTX 2.3)

Cómo usar la generación de video local, qué esperar de ella y qué NO pedirle.
Escrito el 2026-07-26, cuando se instaló.

---

## 1. Lo primero: esto está apagado

No se enciende solo. Un video normal sigue funcionando exactamente igual que
antes, con fotos fijas. Para encenderlo hay que pedirlo:

```bash
C:\ai-video\venv312\Scripts\python.exe editor/editor.py "entrada/mi-video.mp4" --video-ambiente
```

Está apagado a propósito por dos razones honestas:

- **Cada clip son minutos, no segundos.** El modelo pesa 16.4 GB y tu tarjeta
  tiene 16 GB de VRAM, así que no entra entero: ComfyUI deja unas capas en la
  tarjeta y transmite el resto desde la RAM. Funciona, pero no es gratis.
- **Necesita RAM libre de verdad.** Ver §3.

Si algún día querés que sea el comportamiento normal, cambiá
`LTX_HABILITADO = True` en `editor/config.py`. La bandera
`--sin-video-ambiente` sigue sirviendo para apagarlo en una corrida suelta.

## 2. Qué hace exactamente

Cuando el guion nombra un concepto de ambiente (sol, cama, noche, café,
viaje...) y **el catálogo de fotos reales no tiene nada para ese concepto**, en
vez de generar una foto fija con Flux genera un **clip de ~3 segundos** con
movimiento y lo mete como PiP, con las mismas esquinas redondeadas y el mismo
borde blanco con filo cian que los PiP de foto. Visualmente es el mismo
inserto; la diferencia es que se mueve.

El orden de preferencia completo, de mayor a menor:

1. Foto real del catálogo
2. Imagen puesta a mano en `assets/generado/manual/`
3. **Clip de LTX** (solo si está encendido)
4. Imagen fija de Flux

Si LTX falla, o el concepto no tiene prompt de movimiento definido, **cae solo
al paso 4**. Nunca se pierde un inserto por culpa de esto.

## 3. La regla de la RAM — la única que importa de verdad

Antes de generar, cerrá el navegador y lo que tengas abierto. El objetivo es
**más de 18 GB de RAM libres** de los 32 que tenés.

El motivo no es capricho: el modelo que no entra en la VRAM vive en la RAM del
sistema. Si no hay RAM, Windows lo manda al archivo de paginación (al disco), y
ahí un clip de minutos pasa a decenas de minutos. El pipeline te avisa antes de
empezar si hay poca, pero no te frena — la decisión es tuya.

Para ver cómo estás parado:

```bash
C:\ai-video\venv312\Scripts\python.exe editor/f12_video_gen.py --estado
```

## 4. Para qué SÍ sirve y para qué NO

**NO le pidas que dibuje un Kindle.** Está verificado desde la sesión B con
Flux y sigue valiendo: ningún modelo generativo sabe cómo es un Kindle de
verdad. Te va a dar un lector de libros genérico creíble, y eso en un video que
vende Kindles es peor que nada. **Para el producto, foto real, siempre.**

Sirve para dos cosas:

**a) Ambiente sin producto.** Los conceptos que ninguna foto tuya cubre: la luz
del sol moviéndose en una terraza, el vapor de un café, las olas en la playa.
Están en `config.LTX_PROMPTS_POR_TAG`, escritos en términos de **movimiento** —
no son los mismos prompts que los de Flux, porque pedirle "terraza soleada" a
un modelo de video te da una postal quieta.

**b) Imagen-a-video partiendo de tus fotos reales.** Este es el caso que más
vale la pena y el que conviene probar primero:

```bash
C:\ai-video\venv312\Scripts\python.exe editor/f12_video_gen.py --imagen "assets/productos/kindle-paperwhite/frontal.png"
```

Acá el Kindle **sigue siendo tu Kindle**, el de la foto. El modelo solo le
mueve la luz por encima. No inventa el aparato porque no se lo pedimos: el
prompt describe cómo se mueve la luz, no qué es el objeto.

## 5. Probar un clip suelto, sin tocar un video

```bash
C:\ai-video\venv312\Scripts\python.exe editor/f12_video_gen.py --tag "#sol"
```

Queda cacheado en `assets/generado/video/auto/`. El mismo prompt da siempre el
mismo clip (la semilla sale del hash del prompt), así que volver a pedirlo es
gratis.

Si un clip no te convence, podés reemplazarlo a mano igual que con las
imágenes: dejá tu versión en `assets/generado/video/manual/<concepto>.mp4` y
esa gana siempre.

## 6. El audio de LTX se tira a la basura

LTX 2.3 genera audio sincronizado en la misma pasada. **No se usa.** Tu cadena
de audio está calibrada a −14 LUFS con ducking y efectos por evento visual; ese
audio solo estorbaría. El clip sale mudo a propósito.

(Detalle técnico por si alguna vez hace falta: el latente de audio igual se
genera, porque el modelo es audio-video y el sampler recibe la pareja
video+audio como un solo latente. Lo que no se hace nunca es decodificarlo.)

## 7. Qué se instaló y dónde

Nada de esto está en OneDrive. Todo vive en `C:\ai-video\`.

| Pieza | Dónde | Peso |
|---|---|---|
| Transformer 22B destilado, GGUF Q4 | `comfyui/models/unet/` | 16.39 GB |
| Encoder de texto Gemma-3 12B fp8 | `comfyui/models/text_encoders/` | 13.21 GB |
| Proyección de texto | `comfyui/models/text_encoders/` | 2.31 GB |
| VAE de video | `comfyui/models/vae/` | 1.45 GB |
| VAE de audio | `comfyui/models/checkpoints/` | 0.36 GB |

**El VAE de audio va en `checkpoints/`, no en `vae/`.** No es un error: el nodo
que lo carga (`LTXVAudioVAELoader`) lista esa carpeta.

Para volver a bajarlos (es resumible, y se salta lo que ya está):

```bash
C:\ai-video\venv-comfy\Scripts\python.exe editor/descargar_ltx.py
```

## 8. La trampa de pip, que ya está desactivada

`venv-comfy` (el de ComfyUI) ahora tiene su propio archivo de restricciones en
`C:\ai-video\constraints-comfy.txt`. **Todo `pip install` ahí va con `-c`:**

```bash
C:\ai-video\venv-comfy\Scripts\python.exe -m pip install -c C:\ai-video\constraints-comfy.txt <paquete>
```

Sin eso, `diffusers` o `accelerate` pueden reemplazarte el `torch 2.11.0+cu128`
por una versión sin CUDA y dejarte sin GPU para Flux **y** para LTX a la vez.
Ya pasó una vez en el otro venv. Después de cualquier instalación, comprobá:

```bash
C:\ai-video\venv-comfy\Scripts\python.exe -c "import torch; print(torch.__version__, 'sm_120' in torch.cuda.get_arch_list())"
```

Tiene que decir `2.11.0+cu128 True`.

## 9. Si algo sale mal

**"faltan pesos de LTX"** — no terminó la descarga. Corré `descargar_ltx.py`
otra vez; retoma donde iba.

**El clip tarda muchísimo** — mirá la RAM libre (§3). Es casi siempre eso.

**ComfyUI se queda sin memoria** — no corras Flux y LTX en la misma pasada a
mano. El pipeline ya se encarga: le pide a ComfyUI que descargue todo antes y
después de cada clip, y los dos comparten una sola instancia de ComfyUI.

**Querés ver por qué falló** — el log del servidor está en
`C:\ai-video\comfyui-servidor.log`.
