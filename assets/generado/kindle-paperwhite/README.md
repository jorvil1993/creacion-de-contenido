# Librería generada — Kindle Paperwhite (Fase 6)

Generadas con **Flux.1-schnell** cuantizado GGUF `Q5_K_S` vía ComfyUI, siguiendo el workflow
`assets/comfyui-workflows/flux-schnell-gguf-deviceshop.json`. Ver ese archivo (y su nota interna)
para cargar el mismo setup en la interfaz web de ComfyUI y generar más.

Formato: 1080×1920 (vertical, igual que el video final), 4 pasos, cfg 1 — configuración estándar
de schnell (no necesita más pasos, es un modelo destilado para pocos steps).

## Archivos

| Archivo | Categoría | Uso previsto |
|---|---|---|
| `fondo_navy_cian_01.png` | Fondo | Fondo abstracto para tarjetas de texto/specs, degradado navy→cian |
| `fondo_navy_cian_02.png` | Fondo | Fondo con vetas de luz cian, alternativa con más textura |
| `hero_kindle_paperwhite_01.png` | Hero shot | Toma de estudio del e-reader en ángulo, luz de borde |
| `hero_kindle_paperwhite_02.png` | Hero shot | Toma flotante con gotas de agua (sugiere resistencia al agua) |
| `estilo_vida_lectura_sofa.png` | Estilo de vida | Manos sosteniendo el e-reader en un sofá, luz cálida de tarde |
| `estilo_vida_lectura_noche.png` | Estilo de vida | E-reader en un velador, luz cálida nocturna |

## Nota importante sobre los hero shots

Flux generó un dispositivo genérico verosímil (no reproduce el diseño ni el logo real de Kindle
— nunca lo tuvo como referencia, así que no hay riesgo de marca ajena, pero tampoco es un
Kindle exacto). Sirven bien como **fondo/textura genérica de "e-reader"** para B-roll y como
base para componer sobre ellos, pero **no reemplazan una foto real del Kindle Paperwhite**. El
inserto PiP de producto (`plantillas/compositions/pip-producto.html`) sigue esperando fotos/clips
reales del producto vía la variable `imagen` — eso está pendiente de que José filme el material
(ver `contexto/BITACORA-B.md`).

Las escenas de estilo de vida sí quedaron muy utilizables tal cual — el modelo evitó mostrar
rostros (se pidió explícitamente) y el resultado es coherente con el estilo natural/cálido que
pide la sección 5.1 del plan.

## Decisión de modelo

Se usó **FLUX.1-schnell** (Apache 2.0, sin necesidad de cuenta/gate en HuggingFace) en vez de
FLUX.1-dev. El plan no especificaba cuál, y dev requiere aceptar una licencia con cuenta de
HuggingFace — rompía el criterio "sin registro" que guio el resto de las decisiones de esta
sesión. Está documentado con más detalle en `contexto/BITACORA-B.md`.

## Cómo generar más

El script usado fue un one-off (no quedó guardado en el repo porque abre y cierra el servidor de
ComfyUI directamente contra la API HTTP — es lógica de orquestación, no una plantilla). Para
generar más imágenes a mano:

1. `C:\ai-video\venv-comfy\Scripts\python.exe C:\ai-video\comfyui\main.py --listen 127.0.0.1 --port 8188`
2. Abrir `http://127.0.0.1:8188` en el navegador y arrastrar
   `assets/comfyui-workflows/flux-schnell-gguf-deviceshop.json` a la ventana.
3. Cambiar el texto en el nodo "CLIPTextEncodeFlux" y presionar Run.

Recordatorio del plan: esta fase es la de mayor esfuerzo y menor urgencia — si el presupuesto
visual del video se cubre con insertos PiP + Hyperframes, no hace falta generar más por ahora.
