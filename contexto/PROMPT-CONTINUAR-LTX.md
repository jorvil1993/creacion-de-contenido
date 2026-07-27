# Traspaso — Instalar LTX 2.3 e integrarlo al pipeline

> Escrito el 2026-07-26 al final de la sesión que cerró las Fases 3 y 4 del
> editor visual v2. **No se descargó ni instaló nada todavía**: todo lo de
> abajo es investigación verificada, no trabajo a medias. El estado del repo
> está limpio y commiteado.

---

## 0. Estado exacto al momento del traspaso

- **Nada instalado, nada descargado.** Cero riesgo de dejar algo a medias.
- Commits de la sesión anterior, ya en `master`: `8dde936` (Fase 3),
  `46a0953` (Fase 4), `642c507` (bitácora).
- Único archivo sin commitear: `editor/f11_servidor.py`, que es de **otra
  sesión en paralelo**. NO tocarlo.
- Las 6 fases del `PLAN-EDITOR-VISUAL-V2.md` están construidas. Esto es
  trabajo nuevo, no continuación de una fase.

## 1. Qué pidió José

Generar video local en su GPU para **B-roll de ambiente y PiP**, integrado al
pipeline. Decisiones que ya tomó — **no volver a preguntárselas**:

1. **Modelo: LTX 2.3 22B en Q4.** Se le presentaron los tamaños reales y las
   alternativas más livianas (LTX-2 19B en nvfp4) y aun así eligió el 22B.
   Está avisado de que hay que liberar RAM y de que cada clip son minutos.
2. **Alcance: integrar en el pipeline.** No solo instalar: los conceptos de
   ambiente (`#sol`, `#cama`, `#noche`, `#cafe`, `#viaje`) deben poder pasar
   de foto fija generada con Flux a clip de 2-3 s, **con flag para apagarlo**.
3. **Descarga en segundo plano**, trabajando en paralelo mientras baja.

## 2. Lo que YA está montado en la máquina (verificado, no asumido)

| Pieza | Estado |
|---|---|
| ComfyUI **0.28.0** en `C:\ai-video\comfyui` | ✅ |
| Su venv propio: `C:\ai-video\venv-comfy` | ✅ **distinto** de `venv312` |
| `torch 2.11.0+cu128`, `get_arch_list()` incluye **sm_120** | ✅ Blackwell real |
| `custom_nodes/ComfyUI-LTXVideo` (commit `aceeae9`, 29-jun-2026) | ✅ ya instalado |
| `custom_nodes/ComfyUI-GGUF` | ✅ ya instalado |
| `comfy/ldm/lightricks` (soporte nativo en el core) | ✅ |
| Modelos actuales | `unet/flux1-schnell-Q5_K_S.gguf` (7.9 GB), `clip/t5xxl_fp8` (4.7 GB), `clip/clip_l`, `vae/ae.safetensors` |
| Disco libre en `C:` | 209 GB |

**Falta solo:** los pesos de LTX 2.3 y 5 librerías Python.

## 3. Hardware medido — es lo que manda aquí

```
GPU : RTX 5070 Ti · 16 GB GDDR7 (13.9 GB libres) · Blackwell sm_120
RAM : 32 GB DDR4-3600 (2×16) · SOLO 13.1 GB LIBRES en el momento de medir
```

**El cuello de botella es la RAM, no la GPU.** Un 22B en 16 GB de VRAM corre
con *block swap*: ComfyUI deja unas capas en VRAM y transmite el resto desde
la RAM del sistema. Los ~16-18 GB del modelo tienen que vivir en RAM. Con
13 GB libres se va al archivo de paginación y deja de ser utilizable.

**Antes de la primera generación hay que liberar RAM** (cerrar navegador,
Antigravity, etc.) y apuntar a ≥20 GB libres.

## 4. Los archivos exactos a descargar

Tamaños verificados con la API de Hugging Face el 2026-07-26.

| Qué | Repo | Archivo | GB |
|---|---|---|---|
| Difusor | `unsloth/LTX-2.3-GGUF` | `distilled-1.1/ltx-2.3-22b-distilled-1.1-UD-Q4_K_M.gguf` | 16.39 |
| Encoder de texto | `GitMylo/LTX-2-comfy_gemma_fp8_e4m3fn` | `gemma_3_12B_it_fp8_e4m3fn.safetensors` | 13.21 |
| VAE de video | `Kijai/LTX2.3_comfy` | `vae/LTX23_video_vae_bf16.safetensors` | 1.45 |
| Proyección de texto | `Kijai/LTX2.3_comfy` | `text_encoders/ltx-2.3_text_projection_bf16.safetensors` | 2.31 |

**Total ≈ 33 GB.** Destinos en `C:\ai-video\comfyui\models\`:
`unet/` (o `diffusion_models/`) para el GGUF, `text_encoders/` para Gemma y la
proyección, `vae/` para el VAE.

Notas:
- Las quants **UD** de unsloth (Unsloth Dynamic) conservan mejor calidad al
  mismo tamaño que una Q4_K_M normal.
- Si la RAM no aguanta, el escalón de abajo es `Q3_K_M` (14.70 GB) en
  `QuantStack/LTX-2.3-GGUF`.
- **Evitar** los repos `*10Eros*`: son finetunes NSFW, no sirven aquí.
- `huggingface_hub 1.24.0` ya está en `venv-comfy`, así que `hf download`
  funciona directo (resumible).

## 5. ⚠️ EL RIESGO REAL — leer antes de tocar pip

Faltan en `venv-comfy`: **`diffusers`, `timm`, `accelerate`, `protobuf`,
`ninja`** (lo pide `ComfyUI-LTXVideo/requirements.txt`).

**`venv-comfy` NO tiene archivo de constraints.** El `C:\ai-video\constraints.txt`
que existe protege solo a `venv312`.

`diffusers` y `accelerate` declaran dependencia de torch. Un
`pip install -r requirements.txt` a secas puede "corregir" el
`torch 2.11.0+cu128` por un build CPU-only y **matar la GPU para Flux y para
LTX a la vez**. Es la trampa #3 del plan, que ya pasó una vez en este
proyecto.

**Procedimiento obligatorio:**

1. Congelar primero `C:\ai-video\constraints-comfy.txt` con las versiones de
   hoy, ya verificadas:
   ```
   torch==2.11.0+cu128
   torchvision==0.26.0+cu128
   torchaudio==2.11.0+cu128
   numpy==2.4.4
   transformers==5.14.1
   safetensors==0.8.0
   huggingface_hub==1.24.0
   ```
2. Instalar **siempre** con `-c C:\ai-video\constraints-comfy.txt`.
3. Verificar inmediatamente después:
   ```
   C:\ai-video\venv-comfy\Scripts\python.exe -c "import torch; print(torch.__version__, 'sm_120' in torch.cuda.get_arch_list())"
   ```
   Tiene que decir `2.11.0+cu128 True`. Si no, revertir antes de seguir.

## 6. Disciplina de VRAM — lo que José pidió explícitamente ("para que no reviente")

- **Nunca Flux y LTX en la misma pasada.** ComfyUI descarga por LRU, pero el
  pico durante el intercambio es donde revienta. El paso de imágenes termina y
  libera **antes** de que arranque el de video.
- **El encoder Gemma se carga, codifica el prompt y se descarga**, antes de
  cargar el difusor. Nunca los dos en VRAM. Es el error clásico: los números
  que circulan en los blogs son solo del difusor.
- **Previews apagados** (`--preview-method none`) y `--reserve-vram` para
  dejarle aire al escritorio (ya consume ~2 GB).
- **Una sola instancia de ComfyUI.** Hoy `f9_generar.ServidorCompartido` la
  levanta y `f11_servidor.py` puede disparar un re-render en paralelo. Hay que
  garantizar que no coincidan.
- **Clips de 2-3 s a 1080×1920**, nunca 4K. `width`/`height` divisibles por
  32; nº de frames divisible por 8, más 1.
- **Descartar el audio que genera LTX.** Produce audio sincronizado en la
  misma pasada, y la cadena de audio del pipeline está calibrada a −14 LUFS
  con ducking y SFX por evento visual. Ese audio solo estorba.

## 7. Cómo integrarlo (el alcance que eligió José)

`editor/f9_generar.py` ya resuelve el patrón difícil y hay que **reutilizarlo,
no duplicarlo**:

- `ServidorCompartido` arranca ComfyUI con `stdout`/`stderr` **a un archivo**,
  nunca a un pipe sin lector (trampa #5 — ComfyUI imprime ~150 tipos de nodo
  al arrancar y llena el buffer del SO).
- `workflow_api()` construye el workflow en formato API programáticamente.
- Caché por hash del prompt + parámetros.

Lo natural es un `editor/f12_video_gen.py` con la misma forma, más constantes
`LTX_*` en `config.py` y un flag para apagarlo. Los conceptos de ambiente ya
están mapeados en `config.PALABRAS_A_TAGS` y `config.PROMPTS_POR_TAG`.

**Ojo con el compositor:** `f4_retencion.py` espera **alfa** (ProRes 4444).
LTX no genera alfa. Para un PiP con esquinas redondeadas hay que enmascararlo
con ffmpeg, igual que ya describe la §6 del `PLAN-EDITOR-VISUAL-V2.md`.

**Aviso de criterio, ya conversado con José:** está documentado que ningún
modelo generativo sabe cómo es un Kindle real (pasó con Flux). Para el
**producto** siempre gana la foto real. LTX se usa para **ambiente sin
producto**, y para **imagen-a-video** partiendo de los recortes reales
(`assets/productos/*/frontal.png`) — ese es el caso de más valor.

## 8. Prohibiciones duras que siguen vigentes

- `NVENC_PRESET` se queda en `p5`. Nada de `rc-lookahead`, `temporal-aq` ni
  `spatial-aq`.
- Todo `pip install` en `venv312` lleva `-c C:\ai-video\constraints.txt`
  (y en `venv-comfy`, el constraints nuevo de la §5).
- Nada pesado a OneDrive. Los modelos van a `C:\ai-video\`.
- No lanzar procesos con `stdout=PIPE` sin leer el pipe.
- No tocar la tarea de "eliminar la recompresión del paso de corte".
- **No tocar `editor/f11_servidor.py` ni `editor/f10_editor_visual.py`** si la
  otra sesión sigue activa — comprobar marcas de tiempo con
  `ls -la --time-style=+%H:%M editor/*.py` antes de nada.

## 9. Estándar de verificación de este proyecto

- No declarar nada cerrado porque "terminó sin error".
- Al medir calidad de video, **contar los frames primero**
  (`ffprobe -count_frames`).
- **Comprobar la herramienta de medición antes de diagnosticar un bug.** Ya
  pasó tres veces. En particular: `-ss` **antes** de `-i` sobre un MOV
  compuesto devuelve un cuadro liso; hay que seleccionar por número de frame
  (`select='eq(n,35)'`).
- Verificación visual = extraer fotogramas con ffmpeg y **mirarlos**.
- Al terminar, anotar en `contexto/BITACORA-INTEGRACION.md` (al final, sin
  editar lo ya escrito): qué se construyó con rutas y funciones, qué se midió,
  qué quedó pendiente y el punto exacto de retome.

## 10. Orden sugerido de trabajo

1. Congelar `constraints-comfy.txt` (§5.1). **Primero esto.**
2. Lanzar la descarga de los 4 archivos en segundo plano (§4).
3. Mientras baja: instalar las 5 librerías con constraints y verificar sm_120.
4. Mientras baja: escribir `f12_video_gen.py` y las constantes en `config.py`.
5. Primer clip de prueba con la RAM liberada. Contar frames, extraer
   fotogramas y mirarlos.
6. Verificar que **Flux sigue funcionando** (`editor.py --reaplicar` y
   comprobar que el inserto de `#libros` se genera igual).
7. Integrar al disparo automático, con flag para apagarlo.
8. Documentar en `contexto/GUIA-VIDEO-LOCAL.md`, en
   `.claude/skills/editor-deviceshop/SKILL.md` y en la bitácora.

---

**El intérprete del pipeline es `C:\ai-video\venv312\Scripts\python.exe`.
El de ComfyUI es `C:\ai-video\venv-comfy\Scripts\python.exe`. No confundirlos.**
