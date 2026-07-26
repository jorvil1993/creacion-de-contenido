# Plantillas — DeviceShop (Hyperframes)

Proyecto [Hyperframes](https://hyperframes.heygen.com) con las 6 plantillas reutilizables de la
Fase 5 del plan maestro (`contexto/PLAN-EDITOR-VIDEO.md`, sección 7). Cada una es una composición
HTML+CSS+GSAP independiente, con **fondo transparente** y **variables** para inyectar texto/datos
por video sin editar el HTML.

## Cómo previsualizar

```bash
npm run dev      # servidor de preview — ábrelo en el navegador. Correr en background.
npm run check     # lint completo (0 errores antes de dar por bueno cualquier cambio)
```

`index.html` es una **galería de demostración** (no un video final): coloca las 6 plantillas en
una línea de tiempo de 29.5s sobre un fondo simulado con las guías de zona segura (10% superior /
15% inferior libres, sección 7 / Fase 2 del plan) para ver cómo quedarían superpuestas sobre la
toma real de José.

## Cómo renderizar cada plantilla para el pipeline (Fase 5)

**Importante — usar `--format mov`, no `--format webm`, para el canal alfa.**

Se probaron ambos: el mov (ProRes 4444) devuelve alfa correcto y verificado a nivel de píxel
(`0,0,0,0` fuera de la tarjeta, color+255 dentro). El webm (VP9) reportó `needsAlpha:true` en el
render pero al decodificarlo con ffmpeg el canal alfa volvía siempre en 255 (opaco) — no se pudo
confirmar que el alfa real llegue intacto con el ffmpeg usado para verificar. Si más adelante se
confirma que el ffmpeg del pipeline sí decodifica bien el alfa de VP9, webm pesa menos y es buena
alternativa — pero por defecto, usar mov:

```bash
npx hyperframes render -c compositions/pip-producto.html \
  --format mov -q high \
  --variables '{"etiqueta":"Kindle Paperwhite"}' \
  -o out/pip-producto.mov
```

El clip resultante tiene fondo transparente y se compone directo sobre el video principal con
`ffmpeg -i principal.mp4 -i overlay.mov -filter_complex overlay -t <duración>` en el momento
exacto donde se necesite (así lo resuelve `f5_overlays.py` de la sesión A).

Cada composición ocupa el **lienzo completo 1080×1920** y ya posiciona su elemento dentro de las
zonas seguras — no hace falta calcular offsets x/y al componer, solo superponer el clip completo.

## Las 10 plantillas

| Archivo | Variables | Duración |
|---|---|---|
| `compositions/banner-hook.html` | `texto` (ajusta el tamaño de letra solo) | 3.2s |
| `compositions/pip-producto.html` | `imagen` (ruta a foto/clip, opcional), `etiqueta` (opcional) | 4s |
| `compositions/tarjeta-specs.html` | `producto`, `spec1_label`/`spec1_valor` ×3 | 4.5s |
| `compositions/comparativa.html` | `modeloA`/`specA1-3`, `modeloB`/`specB1-3` | 5s |
| `compositions/stickers.html` | `tipo`: `destello` \| `envio` \| `bandera` | 2.5s |
| `compositions/tarjeta-cta.html` | `mensaje`, `whatsapp`, `handle`, `eco` | 6.5s |
| `compositions/anim-bateria.html` | `variante` (0\|1\|2), `lado`, `etiqueta` | 2.4s |
| `compositions/anim-splash.html` | `variante` (0\|1\|2), `lado`, `etiqueta` | 2.2s |
| `compositions/anim-moto.html` | `variante` (0\|1\|2), `etiqueta` | 2.6s |
| `compositions/anim-sol.html` | `variante` (0\|1\|2), `lado`, `etiqueta`, `imagen` | 2.6s |

Si se cambia un `data-duration`, hay que actualizar también
`editor/f8_hyperframes.py → DURACIONES`, que es de donde el pipeline lo lee sin
abrir el archivo.

### `anim-sol.html` — la única que recibe una foto

`imagen` es la **foto real recortada del producto del video**
(`assets/productos/<producto>/frontal.png`). No es decorativa: el mensaje de esa
animación es *"esta pantalla sigue legible con el sol directo encima"*, y eso
solo se demuestra con el aparato de verdad y su texto nítido. Está documentado
que Flux no sabe cómo es un Kindle — para el producto siempre gana la foto real.

La ruta tiene que ser **root-relativa al proyecto de plantillas**, y los
recortes viven fuera de él. De eso se encarga `f8_hyperframes.preparar_imagen()`,
que copia la foto a `assets/_pipeline/<nombre>_<hash-del-contenido>.png` y
devuelve la ruta que la composición sí resuelve. El hash es del contenido, no de
la ruta: si se vuelve a recortar la foto, cambia el nombre y el caché se
invalida solo.

**Regla de composición que no se puede romper:** toda la luz (halo, rayos,
barrido) va **detrás** del dispositivo. Si el destello pasa por encima de la
pantalla, la animación comunica lo contrario de lo que vende. Lo único que toca
al aparato es una copia difuminada y cálida de su propia silueta, debajo de la
copia nítida — el destello sigue el contorno real de cualquier foto sin poner un
píxel sobre la pantalla.

Las cuatro `anim-*` sustituyen a las animaciones dibujadas con PIL en
`editor/f7_animaciones.py` (que quedan como respaldo por si Node/npx no
estuvieran disponibles). `variante` da la **variación determinista por video**:
el pipeline la deriva del nombre del archivo de video, nunca al azar, porque el
plan exige render reproducible. `lado` (izquierda/derecha/centro) lo decide el
pipeline con el face tracking, para que la animación no caiga sobre la cara.

`eco` en la tarjeta de CTA es el **cierre del loop**: repite el hook del inicio
para que lo último que se lea sea la frase con la que abrió el video
(sección 4.5 del plan). Vacío = no se muestra.

**Todas se posicionan en la franja superior (10-35% del alto).** No es
estético: en un talking-head sentado la cabeza ocupa la franja media, y
cualquier tarjeta centrada tapa la cara o el producto que se está enseñando.
Se verificó extrayendo frames del video real. Cualquier plantilla nueva debe
respetarlo (`config.OVERLAY_BANDA_SUPERIOR_PCT`).

La duración es el `data-duration` del elemento raíz `.clip` — se puede editar directo en el HTML
si un video necesita más o menos tiempo en pantalla.

### `pip-producto.html` sin imagen todavía

Mientras no existan fotos/clips reales de producto (`assets/productos/` queda pendiente — depende
de que José filme el material), la plantilla muestra un placeholder "FOTO / CLIP DEL PRODUCTO" en
vez de romperse. Pasar la variable `imagen` con una ruta root-relativa (ej. `"assets/productos/kindle-pw-1.jpg"`) en cuanto existan.

## Decisiones tomadas (para no repreguntar)

- **Rutas en el HTML: siempre root-relativas, nunca `../`.** El renderer y el preview de Studio
  resuelven cada composición contra la raíz del proyecto (`plantillas/`), no contra la carpeta
  `compositions/`. Un `href="_shared.css"` o `src="../assets/..."` se ve bien en el editor pero
  **carga en blanco al renderizar** (así se detectó y arregló durante la verificación — todas las
  plantillas usaban `_shared.css` con ruta relativa simple y los estilos no cargaban). Usar
  siempre `assets/...` o `compositions/_shared.css`.
- **⚠️ EXCEPCIÓN: dentro de un `.css`, `url()` SÍ lleva `../`.** El navegador resuelve `url()`
  contra la ubicación del propio archivo CSS, no contra la raíz. `_shared.css` vive en
  `compositions/`, así que `url("assets/fuentes/Poppins-Bold.ttf")` pedía
  `compositions/assets/fuentes/...` → 404, y **las seis plantillas venían renderizando con la
  sans-serif por defecto en vez de Poppins** desde el principio. Corregido a
  `url("../assets/fuentes/...")` el 2026-07-26. Se detectó con `npm run check` (sección
  *Runtime*), que lo reporta como `404 loading compositions/assets/fuentes/Poppins-*.ttf`.
  Lección: `npm run check` no es opcional — el lint solo no lo veía.
- **Stickers construidos en SVG/CSS, no emoji.** El Chrome que usa el render (local o Docker) no
  siempre trae una fuente de emoji a color instalada — un emoji sin fuente sale en blanco. La
  bandera de Bolivia es un tricolor CSS, el destello un SVG, el camión de envío un SVG simple.
- **Borde del PiP: blanco (fiel al video de la agencia, sección 5.1) + resplandor cian sutil**
  como acento, en vez de reemplazar el blanco por cian. Concilia la sección 5.1 (borde blanco) con
  la 5.3 (el cian se usa en bordes de PiP) sin sacrificar legibilidad.
- **Fuentes:** Poppins (Bold/ExtraBold/Regular) y Montserrat (Bold, instanciada desde la variable
  con `fonttools` porque Google Fonts solo publica Montserrat como variable font — no había
  estático `Montserrat-Bold.ttf` para descargar directo). Copiadas a `plantillas/assets/fuentes/`
  desde `assets/fuentes/` para que el proyecto Hyperframes sea autocontenido.
