# Bitácora — Sesión B

Trabajo en paralelo con la sesión A (pipeline en `editor/`). Territorio de esta sesión:
`assets/`, `plantillas/`, `C:\ai-video\venv-comfy\`, `contexto/catalogo-productos.md`,
`contexto/banco-hooks.md`, `contexto/BITACORA-B.md`. No se tocó `editor/`, `salida/`,
`C:\ai-video\venv312\` ni `contexto/BITACORA-A.md`.

Fecha: 2026-07-26.

---

## 1. Logo (`assets/logo/`)

`contexto/LOGOS IVAN/.../Deviceshop Bo Logo.ai` es en realidad un PDF válido (Illustrator
guarda con compatibilidad PDF por defecto), así que no hizo falta Illustrator ni Inkscape.

**Decisión:** instalé `pymupdf` (pip, sin admin) y rendericé directo desde el `.ai` a PNG con
canal alfa, recortado al bounding box real del contenido vectorial, a 4x/8x de zoom.

**Resultado:** dos archivos.
- `deviceshop-logo-blanco-transparente.png` (4342×1916) — lockup completo (ícono + texto).
- `deviceshop-icono-blanco-transparente.png` (2771×3831) — solo el ícono, pensado para el
  badge circular de cierre.

Solo existe la capa blanca en el `.ai` (el OCG del archivo trae un único layer, "ON"), así que
no hay versión a color extraída de ahí — para eso ya existen `deviceshop color.png` /
`deviceshop blanco.png` como rasters planos en la misma carpeta, sin canal alfa. Si en algún
momento se necesita el lockup a color con transparencia, hay que pedir el `.ai` de esa versión
o vectorizar desde el PNG plano.

## 2. Fuentes (`assets/fuentes/`)

Poppins (Regular, Bold, ExtraBold) se descargó directo del repo `google/fonts` en GitHub — son
estáticas, sin problema.

**Problema:** Montserrat en ese repo es un *variable font* (`Montserrat[wght].ttf`), no trae
pesos estáticos sueltos. **Decisión:** instalé `fonttools` y generé instancias estáticas Bold
(700) y ExtraBold (800) con `varLib.instancer` (`updateFontNames=True` para que la tabla `name`
quede correcta — sin eso, ambos pesos se llamaban "Montserrat Thin" por dentro, aunque el
peso visual era el correcto). Se conserva también `Montserrat-Variable.ttf` por si sirve.

Incluí las licencias (`OFL-Poppins.txt`, `OFL-Montserrat.txt`) junto a las fuentes.

## 3. SFX (`assets/sfx/`)

Fuente: [videoeditingsfx.com](https://videoeditingsfx.com/sfx/) — CC0, MP3 directo, sin
registro. Coincide con lo que sugería el plan. 13 archivos (whoosh ×4, pop, impacto ×3,
transición ×2, notificación ×3) organizados por la categoría de la sección 4.4 del plan.
Verifiqué cada uno por cabecera MP3/ID3 después de descargar (ninguno era una página de error).

## 4. Música de fondo (`assets/musica/`)

**Esto se desvió del plan** — se pedían pistas CC0 y documenté por qué no se pudo cumplir al
pie de la letra:

1. `freepd.com` (la fuente CC0 obvia para esto) **cerró permanentemente en 2025**.
2. Kenney.nl (CC0 verificado, la usé para SFX) solo tiene "jingles" de 2-8s estilo videojuego,
   no sirven como cama musical de 25-40s.

**Decisión:** usé [Pixabay Music](https://pixabay.com/music/) (licencia propia de Pixabay, no
CC0 literal, pero gratis, sin registro para bajar el archivo, uso comercial permitido, sin
Content ID). 4 pistas, ninguna épica ni cansadora, duraciones entre 25s y 2:33 — todo
documentado con el detalle de la desviación en `assets/musica/README.md`.

## 5. Catálogo de productos (`contexto/catalogo-productos.md`)

Specs verificadas por búsqueda web (Kindle Basic 11ª gen 2022, Paperwhite 12ª gen 2024,
Colorsoft Signature Edition, Scribe 2ª gen 2024, Kobo Clara BW / Libra Colour) — no inventé
números. **No incluí precios en bolivianos**: eso depende del costo de importación y margen de
José, no es algo que se pueda investigar en la web. Cada ficha tiene specs, beneficios en
lenguaje de venta, objeciones comunes con respuesta, y una lista de "palabras clave para
overlays" pensada para que la Fase 5 (sincronización por palabra clave, sección 7 del plan)
tenga algo concreto de donde partir.

Kobo quedó como nota abierta: el plan solo dice "Kobo" sin modelo — cubrí Clara BW y Libra
Colour (los más relevantes hoy) y dejé marcado que hay que confirmar con José cuál(es) se
importan realmente.

## 6. Banco de hooks (`contexto/banco-hooks.md`)

40 hooks (8 por ángulo × 5 ángulos: dolor, curiosidad, regalo, comparativa, urgencia), todos
verificados a mano a ≤7 palabras, capitalización tipo oración (nunca mayúsculas, por la regla
de la sección 5.1). Español boliviano neutro — evité jerga tan local que no se entienda fuera
de una región específica, priorizando que el hook se lea rápido y claro.

## 7. Plantillas Hyperframes (`plantillas/`)

`npx hyperframes init` no tiene modo no interactivo por defecto — hubo que pasar
`--example blank --resolution portrait --non-interactive` explícito.

Construí las 6 plantillas de la sección 5 del plan, todas con `data-composition-variables`
(sistema nativo de Hyperframes) para que cada video pase su propio texto/datos sin tocar el
HTML: `banner-hook.html`, `pip-producto.html`, `tarjeta-specs.html`, `comparativa.html`,
`stickers.html`, `tarjeta-cta.html` (WhatsApp 69214437 ya como default). Paleta exacta de la
sección 5.3, subtítulos fuera del alcance de estas plantillas (esos los quema `f3_subtitulos.py`
de la sesión A).

**Bug real que encontré y arreglé verificando el render (no solo el lint):** las 6 plantillas
enlazaban `_shared.css` con ruta relativa simple (`href="_shared.css"`). El linter de
Hyperframes no lo marcó como error, pero al renderizar de verdad la hoja de estilos no cargaba
— cero variables CSS resueltas, texto en negro por defecto, tarjetas sin fondo. Lo encontré
comparando un frame renderizado contra lo esperado (extraje frames con ffmpeg y los inspeccioné
pixel por pixel). La causa: Hyperframes resuelve cada composición contra la raíz del proyecto,
no contra la carpeta `compositions/`, así que hacía falta `href="compositions/_shared.css"`
(ruta "root-relative", igual que ya exigía el linter para imágenes con `../`). Después de
arreglarlo, re-rendericé y confirmé visualmente que la tarjeta de CTA sale exactamente como se
diseñó (navy, cian, blanco, logo, WhatsApp).

También verifiqué el canal alfa: `--format webm` reportó `needsAlpha:true` pero al decodificar
con ffmpeg el alfa volvía siempre en 255 (opaco) — no logré confirmar que el alfa de VP9 llegue
intacto con el ffmpeg que usé para probar. `--format mov` (ProRes 4444) sí dio alfa correcto
verificado a nivel de píxel (0,0,0,0 fuera de la tarjeta, color+255 adentro). **Recomendación
para la sesión A:** usar `--format mov` para componer las plantillas sobre el video principal,
no `webm`, salvo que se confirme que el ffmpeg del pipeline decodifica bien el alfa VP9.

Para tener con qué renderizar y verificar (no había `ffmpeg`/`ffprobe` en PATH todavía), usé el
binario embebido de `imageio-ffmpeg` más un build standalone de Gyan.dev descargado al
scratchpad — solo para probar, no toqué el PATH del sistema ni instalé nada persistente (eso le
corresponde a la Fase 0, y no quise pisarle esa tarea a la sesión A ni arriesgar un choque con
un `winget install` que ella pudiera estar corriendo en paralelo).

Documenté todo esto en `plantillas/README.md` para que la sesión A no repita la investigación.

## 8. ComfyUI + Flux (`C:\ai-video\comfyui`, `C:\ai-video\venv-comfy`)

**Cambio de plan a mitad de sesión:** la instrucción original decía instalar y descargar nada
más, probando una sola generación al final. El usuario luego pidió explícitamente continuar a
la Fase 6 completa (generar librería inicial: fondos, hero shots, escenas de estilo de vida
para Kindle Paperwhite) y a la Fase 7 (borrador del skill). Sigo esa instrucción más reciente.

**Decisiones sobre qué modelo Flux usar:**
- El plan pedía "Flux GGUF Q5" sin especificar dev vs. schnell. `black-forest-labs/FLUX.1-dev`
  (y sus derivados) están detrás de un gate de HuggingFace (`gated: auto`) — piden cuenta y
  aceptar términos, aunque sea gratis. Eso choca con el espíritu "sin registro" que se pidió
  para el resto de los assets.
- **Decisión:** usé **FLUX.1-schnell** (Apache 2.0, totalmente abierto, sin cuenta, sin gate) en
  vez de dev. Cuantización `Q5_K_S` de `city96/FLUX.1-schnell-gguf` (no existe `Q5_K_M` para
  schnell, solo K_S — es la variante K-quant más cercana). ~8.26 GB, coincide con el
  presupuesto "~9 GB" del plan.
- Descargué también lo que hace falta para que el UNet GGUF realmente funcione (el plan no lo
  menciona explícito pero es necesario): `clip_l.safetensors` + `t5xxl_fp8_e4m3fn.safetensors`
  (texto) de `comfyanonymous/flux_text_encoders`, y `ae.safetensors` (VAE) de
  `Comfy-Org/Lumina_Image_2.0_Repackaged` (un re-empaquetado sin gate del VAE oficial de Flux).
  Los tres repos confirmé que están sin gate (`gated: False`) antes de usarlos.
- Custom node `city96/ComfyUI-GGUF` para el nodo `UnetLoaderGGUF` (ComfyUI nativo no lee `.gguf`).

**Entorno:** `C:\ai-video\venv-comfy` con Python 3.12 (ya estaba instalado — no lo instalé yo,
asumo que fue la sesión A o el propio José vía el instalador de Microsoft Store que se le abrió
a mitad de la noche). PyTorch cu128 — verificado: `torch.cuda.is_available() == True`,
`RTX 5070 Ti`, capability `(12, 0)` (Blackwell/sm_120, igual que exige el plan para venv312).

**Resultado final:** todo instalado y descargado sin bloqueos. Verificado: `flux1-schnell-Q5_K_S.gguf`
(8.26 GB), `clip_l.safetensors` (246 MB), `t5xxl_fp8_e4m3fn.safetensors` (4.89 GB),
`ae.safetensors` (335 MB) — los 4 archivos con el tamaño exacto que había confirmado por HEAD
request antes de descargar, así que no quedaron truncados.

**Falló y cómo lo resolví (van dos incidentes, no uno):**
1. El `git clone` de ComfyUI abortó el script con `NativeCommandError` — es el gotcha de
   PowerShell 5.1 con `2>&1` sobre binarios nativos (git escribe su progreso normal a stderr).
   El clone en sí había funcionado. Solución: saqué `2>&1` de las llamadas a `git`/`curl.exe`.
2. Al arrancar el servidor de ComfyUI para la Fase 6 (ver abajo) desde un script Python con
   `subprocess.Popen(..., stdout=subprocess.PIPE)`, el proceso se quedó colgado sin abrir el
   puerto — ComfyUI imprime bastante al arrancar (banner, registro de ~150 tipos de nodo) y
   nadie estaba leyendo ese pipe, así que se llenó el buffer y el proceso hijo se bloqueó en el
   primer `write()`. Lo detecté porque el CPU del proceso dejó de crecer y no había nada
   escuchando en el puerto 8188. Solución: redirigir stdout/stderr del subproceso a un archivo
   de log en vez de a un pipe sin consumidor.

## 9. Fase 6 — Librería inicial de imágenes

**Workflow:** `assets/comfyui-workflows/flux-schnell-gguf-deviceshop.json` — es el template
oficial `flux_schnell_full_text_to_image.json` que trae el propio ComfyUI (paquete
`comfyui-workflow-templates`), adaptado para cargar el UNet vía el nodo `UnetLoaderGGUF` del
custom node en vez del `UNETLoader` de safetensors normal. Verifiqué los nombres exactos de
parámetros de cada nodo (`DualCLIPLoader`, `CLIPTextEncodeFlux`, `EmptySD3LatentImage`,
`UnetLoaderGGUF`) leyendo el código fuente instalado, no de memoria — evita el típico error de
JSON de workflow con un nombre de campo desactualizado.

**Generación:** 6 imágenes para Kindle Paperwhite (2 fondos navy/cian, 2 hero shots de producto,
2 escenas de estilo de vida), 1080×1920, 4 pasos/cfg 1 (config estándar de schnell). Las seis
salieron bien al primer intento — no hizo falta usar el reintento por GPU ocupada que pidió el
usuario, la sesión A no estaba usando la GPU en ese momento. Un ciclo completo (arrancar server +
las 6 generaciones) tardó menos de 2 minutos una vez cargado el modelo.

**Calidad, revisada a ojo (no solo "se generó sin error"):** las escenas de estilo de vida
salieron genuinamente usables — ambiente cálido y natural, coherente con la sección 5.1 del plan,
sin rostros visibles (se pidió explícito en el prompt). Los hero shots de producto son un
e-reader **genérico creíble**, no una réplica del Kindle Paperwhite real (Flux nunca tuvo una
foto de referencia) — sirven como fondo/textura, no reemplazan una foto real del producto.
Documentado en `assets/generado/kindle-paperwhite/README.md`, con la limitación marcada para que
nadie los use pensando que son el Kindle real.

Cerré el proceso de ComfyUI al terminar (`proc.terminate()`) y confirmé que no quedó ningún
proceso Python residente ocupando VRAM antes de dar por cerrada esta fase.

## 10. Fase 7 — Skill

Redacté el borrador en `.claude/skills/editor-deviceshop/SKILL.md`. Marcado explícitamente
como borrador: incluye estilo, paleta, referencias al catálogo y al banco de hooks (sin
duplicar contenido — solo apunta a los archivos fuente), el CTA con el WhatsApp real
(69214437), y una tabla de estado por fase. Dejé como TODO explícito: el comando de invocación
real (depende de que `editor/editor.py` exista — a la fecha de este borrador solo están
`config.py`, `f1_transcribir.py`, `f2_cortar.py`, `f3_subtitulos.py`) y el soporte para el
segundo presentador (la esposa de José) porque ninguna fase construida hasta ahora tiene
parámetro de presentador.

## Pendientes para José / para la sesión B en la próxima vuelta

1. Confirmar qué modelo(s) de Kobo importa realmente DeviceShop (el catálogo cubre Clara BW y
   Libra Colour como los más probables, a falta de confirmación).
2. Fotos/clips reales de producto para `assets/productos/` — las plantillas (PiP) están listas
   para recibirlos vía la variable `imagen`, pero hoy muestran un placeholder.
3. Si se prefiere la calidad de Flux "dev" sobre "schnell", hace falta que José cree una cuenta
   gratuita de HuggingFace y acepte la licencia — está fuera del criterio "sin registro" que
   guio el resto de las decisiones de esta sesión, así que no lo hice sin confirmar.
4. Revisar `assets/musica/README.md` — la desviación de CC0 a licencia Pixabay para la música
   de fondo es la única donde no se cumplió el requisito original al pie de la letra.
