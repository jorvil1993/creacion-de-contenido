# Bitácora — Sesión de integración

Fecha: 2026-07-26. Sesión de desarrollo sobre el pipeline ya operativo.
Objetivo: completar lo que faltaba e integrarlo, sin romper lo que funcionaba.

Todo lo que dice este documento se midió contra `contexto/VIDEOV2.mp4` (la
grabación real de 44s) en esta máquina. Video de referencia para revisar en el
celular: `salida/integrado_v1.mp4`.

---

## Resumen en una línea

La GPU pasó de generar **cero** imágenes por video a generarlas bajo demanda con
caché; las 6 plantillas de Hyperframes que estaban sin usar ahora están las 9
conectadas (y se descubrió que **ninguna cargaba Poppins**); el loop dejó de ser
una nota de texto y es una implementación medible; y el editor visual ya existe.
El video final conserva formato, duración y audio idénticos a la línea base:
1105 frames, 37.132 s, pico −0.1 dBFS.

---

## 1. Mediciones

### Tiempo del pipeline

| Escenario | Tiempo | Qué incluye |
|---|---|---|
| **Línea base** (antes de esta sesión) | **34.8 s** | 6 overlays |
| Primera corrida con lo nuevo | 120.2 s | + arranque de ComfyUI (10.5 s) + 2 imágenes generadas (31 s) + 5 composiciones de Hyperframes nuevas |
| **Corrida en caliente** (todo cacheado) | **54.0 s** | 8 overlays, 3 de ellos ProRes 4444 con alfa |

Los ~19 s de diferencia entre la base y la corrida en caliente **no** son
generación ni Hyperframes (ambos van por caché y cuestan cero): son el precio de
componer 8 overlays en vez de 6, tres de los cuales son clips ProRes 4444 que
ffmpeg tiene que decodificar dentro de la misma pasada. Es un intercambio
explícito: más beats visuales por segundo de proceso. El editor visual cuesta
**0.9 s** y se puede saltar con `--sin-editor-visual`.

### Calidad del archivo final — sin cambios (lo que se buscaba)

Medido sobre `salida/FINAL_integracion.mp4`, la corrida de confirmación:

| | Línea base | Ahora |
|---|---|---|
| Frames / duración | 1105 / 37.132 s | **1105 / 37.132 s** ✓ |
| Resolución | 1080×1920 | 1080×1920 |
| Sonoridad integrada | −14.1 LUFS | **−14.1 LUFS** ✓ |
| Pico real de audio | −0.1 dBFS | **−0.1 dBFS** ✓ |

Sin truncamiento del cierre: la advertencia de la auditoría sobre el preset de
NVENC se respetó, no se tocó `p5` ni se añadió lookahead.

Esa corrida se hizo además con `--hook "Miles de libros en tu bolsillo"` para
probar el camino del hook curado: el video abre con esa frase y **cierra con la
misma** en la tarjeta de CTA. También cambió el `--nombre`, y las variantes de
animación cambiaron con él (batería 1→2, splash 0→1) — que es exactamente el
comportamiento buscado de la variación determinista.

### Loop — medido, no supuesto

Se compara el **último frame contra el primero**. Para aislar el encuadre de lo
que hace José con las manos, se mide sobre una franja lateral del fondo (estante
y pared), que no depende de su pose:

| | Sin loop | Con loop |
|---|---|---|
| SSIM último vs primer frame | 0.639 | **0.775** |
| PSNR | 12.23 dB | **20.82 dB** |

Sobre el cuadro completo (que sí incluye a José moviéndose) la mejora es menor
—SSIM 0.442 → 0.481— y es el límite honesto de un loop automático: se puede
hacer coincidir la cámara, no lo que la persona está haciendo.

### Generación en GPU

| | Tiempo |
|---|---|
| Arranque de ComfyUI (frío, primera del día) | 40.2 s |
| Arranque de ComfyUI (en caliente) | 10.5 s |
| Primera imagen (carga 13 GB de modelos a la VRAM) | 23-30 s |
| Imágenes siguientes en la misma corrida | ~8 s |
| **Imagen ya cacheada** | **0.11 s** |

Verificado además que no queda ningún proceso Python residente ocupando VRAM al
terminar (`Get-Process python` → 0).

---

## 2. Qué se hizo, punto por punto

### 1 · ComfyUI en tiempo real — `editor/f9_generar.py` (nuevo)

Antes: ComfyUI instalado y Flux descargado, pero **nada en `editor/` lo
invocaba**; la única mención era una constante de ruta en `config.py`. Las 6
imágenes de `assets/generado/` se habían hecho a mano y no las usaba nadie.

Ahora:

- **Servidor bajo demanda** con `ServidorCompartido`, que arranca de forma
  perezosa: si todas las imágenes del video están en caché, ComfyUI no se
  levanta nunca y no cuesta un segundo. Un solo arranque sirve para todas las
  imágenes de la corrida, y se apaga al terminar liberando la VRAM. Si José ya
  tenía ComfyUI abierto, se reutiliza y **no** se le apaga.
- **stdout/stderr a un archivo**, nunca a un pipe — el gotcha documentado en la
  bitácora B punto 8. Está anotado en el docstring del módulo para que nadie lo
  "simplifique".
- **Workflow en formato API** construido en código a partir del JSON de
  `assets/comfyui-workflows/`, que está en formato de *interfaz* (nodes/links) y
  el endpoint `/prompt` no acepta. Los nombres de cada input se verificaron
  leyendo el código instalado (`nodes.py`, `comfy_extras/nodes_flux.py` y el
  custom node `ComfyUI-GGUF`), no de memoria.
- **Prompt derivado del guion**: concepto base de `config.PROMPTS_POR_TAG` + la
  frase que José dice alrededor de ese momento. Sin eso, dos videos que mencionan
  "agua" producirían exactamente la misma imagen.
- **Caché por hash del prompt** y **semilla derivada del mismo hash**: el render
  es reproducible, como exige el plan. Nada de `random`.
- **Se usa solo como respaldo**: primero el catálogo de 262 fotos reales, después
  la versión manual de José, y solo entonces Flux. Para el producto siempre gana
  la foto real — Flux no sabe cómo es un Kindle, hace un e-reader genérico
  creíble (limitación ya documentada por la sesión B).

Para que el respaldo se ejercite de verdad se añadieron a `PALABRAS_A_TAGS` los
conceptos de **ambiente** que el catálogo nunca va a cubrir: sol, cama, noche,
café, viaje, libros, biblioteca, estudio. Es literalmente lo que pedía el punto 5
de MEJORAS-PENDIENTES ("cuando diga 'sol', 'tina', etc., que aparezca una fotito
ilustrando eso").

**Verificado a ojo:** la imagen de `#agua` es un splash turquesa de piscina,
usable tal cual y coherente con el cian de marca. La de `#libros` es una pila de
libros gruesos, que es exactamente el "dolor" del hook.

### 1b · `contexto/prompts-externos.md`

Se escribe solo en cada corrida que genere imágenes. Trae, por concepto: el
prompt completo listo para pegar en Google Flow o Nano Banana, la semilla, el
tamaño recomendado y **la ruta exacta** donde dejar el resultado
(`assets/generado/manual/<concepto>.png`). La versión manual gana siempre sobre
Flux sin tener que borrar nada ni pasar ninguna opción.

También lista los conceptos que el guion nombró y que **nadie** pudo ilustrar (ni
catálogo ni Flux), con su ruta de destino.

### 2 · Hyperframes completo

**Bug real encontrado: las plantillas nunca cargaron Poppins.** `_shared.css`
vive en `compositions/` y pedía `url("assets/fuentes/...")`; el navegador
resuelve `url()` contra la ubicación del CSS, así que iba a
`compositions/assets/fuentes/...` → 404. Las seis plantillas venían renderizando
con la sans-serif por defecto desde el principio. Lo detectó `npm run check`
(sección *Runtime*); el lint solo no lo veía. Corregido a `../assets/fuentes/`,
que es la **excepción** a la regla de "nunca `../`" — esa regla aplica al HTML,
no al interior de un CSS. Documentado en `plantillas/README.md`.

**Bug real #2: el caché de Hyperframes no invalidaba al editar la plantilla.** La
clave solo miraba las variables, así que después de mover la tarjeta de specs a
la franja superior el render "tardó 0.0s" y salió idéntico. Ahora la clave
incluye el hash del HTML de la composición y de `_shared.css`.

Lo conectado:

| Plantilla | Antes | Ahora |
|---|---|---|
| `tarjeta-specs` | conectada, pero **centrada: tapaba la cara y el producto** | franja superior (10-35%), verificado con frames |
| `banner-hook` | sin usar (el hook era PIL) | conectada, con ajuste automático del tamaño de letra |
| `tarjeta-cta` | sin usar | conectada y **rediseñada** |
| `stickers` | sin usar | conectada |
| `comparativa` | sin usar | conectada, solo cuando el guion nombra 2 modelos |
| `pip-producto` | sin usar | sigue en PIL a propósito (ver abajo) |

**La comparativa tenía el mismo defecto que la ficha técnica.** Al renderizarla
por primera vez (nunca se había usado) salía centrada verticalmente, es decir
justo encima de la cara, y el badge "VS" tapaba la primera spec de la columna
derecha — algo que `npm run check` ya venía reportando como
`text_occluded #specB1t inside #vs` y que nadie había mirado. Corregidas ambas
cosas y verificado componiéndola sobre un frame real del video: ahora queda en la
franja superior, con la cara y el producto libres.

**Sobre migrar el hook y el CTA (evaluación pedida):** sí conviene, y se hizo.

- *Hook*: la versión PIL era una tarjeta navy opaca con borde cian. La de
  Hyperframes es texto blanco grande con sombra y una línea cian — se ve más
  limpio y respeta mejor la proporción "80% metraje / 20% marca" de la sección
  5.3. Se le añadió ajuste automático de tamaño (76→48px) porque el hook
  automático puede traer 12 palabras y con tamaño fijo se salía del cuadro.
- *CTA*: la plantilla **tal como estaba era una regresión** — una banda navy
  sólida en `bottom:270px`, es decir justo el recuadro pesado que José había
  pedido quitar (punto 4 de MEJORAS), y encima pisaba la banda de subtítulos del
  77%. Se reescribió: sin caja, contorno negro, logo, ícono de WhatsApp, número,
  handle y el eco del loop, en la franja superior.
- *PiP de producto*: **no** se migró. La plantilla recibe la imagen por variable
  y se posiciona sola en el HTML, pero el pipeline necesita colocarla esquivando
  el rostro con el track de cada momento y poder moverla desde el editor visual.
  Con PIL eso es un `x`/`y` en el evento; con Hyperframes habría que re-renderizar
  el clip por cada posición. Se queda en PIL, que además ya se ve bien.

Los renders de PIL siguen ahí como respaldo automático si Node/npx faltaran: el
pipeline avisa por consola y continúa.

### 3 · Animaciones con variación

Se hicieron **las dos cosas** que planteaba el punto:

1. **Reimplementadas como composiciones de Hyperframes con GSAP** —
   `anim-bateria`, `anim-splash`, `anim-moto`. La batería ahora cuenta las
   semanas mientras se llena, con easing real; el splash tiene ondas, gotas con
   gravedad y etiqueta; la moto tiene ruedas que giran, suspensión y la bandera
   de Bolivia. La comparación es clara: en el video base, el splash de PIL a los
   18.4 s era una manchita cian de unos 40 px — prácticamente invisible en un
   celular.
2. **Variación determinista** en ambos motores. La semilla sale del nombre del
   video (`--nombre`), no de `random`, así que el mismo video da siempre el mismo
   resultado pero dos videos distintos reciben variantes distintas: color de
   llegada y cuenta de la batería, número de gotas y apertura del splash, sentido
   y velocidad de la moto.

También reciben `lado` (izquierda/derecha/centro), que el pipeline calcula con el
face tracking para que la animación no caiga sobre la cara.

### 4 · Editor visual — `editor/f10_editor_visual.py` (nuevo)

Genera **un HTML autocontenido** por corrida (`09_editor-visual.html`, ~1.9 MB)
con los 13 MP3 y los fotogramas del video embebidos en base64, porque un artifact
no puede cargar archivos externos. Se abre con doble clic, sin servidor.

- Línea de tiempo con la transcripción y la escala de segundos.
- Marcadores de SFX arrastrables; al tocarlos suenan, para elegir de oído.
- Selector con el vocabulario completo de `assets/sfx/`.
- **Posición de los insertos**: cada PiP se arrastra sobre el fotograma real
  donde aparece, así se ve exactamente qué se está tapando.
- Exporta `ajustes.sfx.json` y `ajustes.pos.json`.

El contrato de vuelta ya existía a medias (`f5_audio.py --sfx-manual`); se
completó con `f6_overlays.py --posiciones-manual`, que empareja por
(tipo, instante) y no por índice, para que un ajuste viejo siga cayendo donde
debe aunque el guion cambie y aparezca un inserto más.

Publicado también como artifact:
<https://claude.ai/code/artifact/180747ea-3c4c-4bf5-9e3d-657af642a214>

### 5 · Diseño de loop

Antes: `f4_retencion` escribía una nota de texto diciendo que el loop quedaba
pendiente. Ahora son dos capas:

1. **Visual** — en los últimos 1.2 s el encuadre (zoom + paneo) vuelve con
   `smoothstep` al del primer frame. Medido arriba: +8.6 dB de PSNR.
2. **Narrativa** — la tarjeta de CTA cierra repitiendo el hook, recortado a ≤7
   palabras y cerrando en la primera coma. En este video: *"¿Quieres leer más
   este año?"*. Lo último que se lee es la frase con la que abrió.

### 6 · Skill (Fase 7)

`.claude/skills/editor-deviceshop/SKILL.md` reescrito: ya no es borrador. Trae el
comando real y verificado, la tabla completa de opciones, qué produce cada
corrida, cuánto tarda, el orden de prioridad de las imágenes, la ficha de estilo,
y una tabla de **trampas conocidas** para que ninguna sesión futura "mejore" el
preset de NVENC y trunque el cierre sin darse cuenta.

**Dos presentadores** (`config.PRESENTADORES` + `--presentador jose|esposa`):
ninguna fase tenía parámetro de presentador. Ahora el perfil cambia lo que de
verdad depende de la persona — muletillas, conectores ambiguos, umbral de
silencio y percentil de punch-ins — y se propaga a `f2_cortar` y `f4_retencion`.
El perfil de la esposa está marcado **sin calibrar** y el pipeline avisa por
consola: son valores de partida, se ajustan con su primera grabación real, no en
teoría.

### 7 · Deudas menores

- **La moto nunca se había visto en un video real.** Este guion no dice
  "envíos", "entrega" ni "Bolivia", así que no se dispara sola. Se verificó
  inyectando el evento en el mismo camino de composición (evento `medio: video`,
  `-itsoffset`, `overlay`) sobre el metraje real, en la ventana libre de
  27.4-30.0 s: cruza correctamente con su etiqueta y la bandera.
  Queda como **verificado sobre metraje real**, aunque disparado a mano.
- **Datos de nltk movidos.** Estaban en `%APPDATA%\nltk_data`, que en la app de
  Claude (paquete MSIX) Windows **redirige** a
  `AppData\Local\Packages\Claude_...\LocalCache\Roaming\` — una carpeta que se
  borra al actualizar la app, y sin ella whisperx deja de alinear. Copiados
  (14.5 MB) a `C:\ai-video\nltk_data` y `NLTK_DATA` fijado en `config.py` antes
  de que nadie importe nltk. Verificado: `nltk.data.find('tokenizers/punkt_tab/spanish')`
  resuelve desde la ruta nueva.
- **Los 1.72 GB de intermedios en OneDrive: NO se movieron.** El sistema de
  permisos bloqueó el `Move-Item`, igual que a la sesión de auditoría. No se
  buscó rodeo. Comando listo en la sección de pendientes.

---

## 3. Qué falló y cómo se detectó

1. **Las plantillas no cargaban Poppins** (desde siempre) — detectado corriendo
   `npm run check`, sección *Runtime*: `404 loading compositions/assets/fuentes/Poppins-*.ttf`.
   El lint no lo marcaba.
2. **El caché de Hyperframes no invalidaba al editar el HTML** — detectado
   porque la tarjeta de specs "se re-renderizó en 0.0 s" después de moverla.
   Si no se hubiera mirado el tiempo, el cambio habría pasado por bueno sin
   aplicarse.
3. **La plantilla de CTA era una regresión** — leerla antes de conectarla evitó
   volver a meter el recuadro navy que José ya había pedido quitar, y una
   colisión con la banda de subtítulos.
4. **`prompts-externos.md` listaba dos entradas de `#libros` apuntando al mismo
   archivo manual** — se leía como error. Corregido: agrupado por concepto, con
   todas las variantes de prompt bajo una sola ruta de reemplazo.
5. **Un frame extraído con `-ss` antes de `-i` sobre un MOV compuesto salió en
   blanco** y por un momento pareció que el splash no animaba. Era un error de
   *mi* comando de verificación (el overlay arrancaba después del inicio del
   color de fondo), no del render: con un mosaico de frames se vio animando
   perfectamente. Vale la misma lección que ya está en la bitácora A: comprobar
   la herramienta de medición antes de diagnosticar un bug.

---

## 4. Verificación visual

Frames extraídos del final y revisados uno a uno (no solo "terminó sin error"):

| t | Qué se comprobó |
|---|---|
| 1.0 s | Hook en Poppins ExtraBold blanco con sombra, 3 líneas ajustadas solas, línea cian |
| 5.0 s | Inserto de libros **generado con Flux**, tarjeta redondeada arriba a la derecha, esquivando el rostro |
| 8.0 s | Ficha técnica en la franja superior — **cara y producto completamente visibles** (antes los tapaba) |
| 14.0 s | Batería llenándose con contador de semanas |
| 18.4 s | Splash con ondas, gotas y etiqueta (antes: manchita de 40 px) |
| 21.0 s | Inserto del Paperwhite jade por "tina" |
| 33.0 s | CTA sin caja: logo, WhatsApp, handle y **el eco del hook** |
| 27.4-30.0 s | Moto cruzando (prueba dirigida) |

---

## 5. Qué queda pendiente

1. **Mover los 1.72 GB de intermedios fuera de OneDrive** — bloqueado por
   permisos, hay que correrlo a mano. Los finales ya están respaldados en la raíz
   de `salida/` (18 archivos):

   ```powershell
   $base = "C:\Users\devic\OneDrive\CLAUDE CODE\creacion-de-contenido\salida"
   New-Item -ItemType Directory -Force -Path "C:\ai-video\salida\_historico"
   "jose_kindle_paperwhite_v1","jose_kindle_paperwhite_v2","prueba","prueba_completa","test_nvenc","v2_final","animaciones" |
     ForEach-Object { Move-Item (Join-Path $base $_) "C:\ai-video\salida\_historico" -Force }
   ```

2. **Calibrar el perfil de la esposa** con su primera grabación real. Los valores
   de `config.PRESENTADORES["esposa"]` son un punto de partida honesto, no una
   medición.
3. **La comparativa no se ha visto en un video real** — la lógica está conectada
   y probada, pero este guion solo nombra un modelo, así que no se dispara. Igual
   que pasaba con la moto: hará falta un video que compare Paperwhite con
   Colorsoft para verla en contexto.
4. **La etiqueta `#agua` sigue trayendo una foto de producto**, no la imagen de
   agua generada: el catálogo tiene 30 assets con esa etiqueta (Kindles
   resistentes al agua) y la regla acordada es "catálogo primero, generación como
   respaldo". Funciona según lo pedido, pero si José prefiere ver agua de verdad
   cuando dice "tina", basta con sacar `#agua` de las etiquetas de esos assets o
   añadir una lista de conceptos que prefieran lo generado.
5. **Eliminar la recompresión del paso de corte** — sigue siendo la mejora de
   calidad #1 pendiente, tal como la dejó la auditoría (sección 4-bis de
   `AUDITORIA-OPTIMIZACION.md`). No se tocó: es una reestructuración con riesgo
   real y esta sesión ya tocaba muchas piezas.

---

## Archivos tocados

**Nuevos:** `editor/f9_generar.py`, `editor/f10_editor_visual.py`,
`plantillas/compositions/anim-bateria.html`, `anim-splash.html`, `anim-moto.html`,
`contexto/prompts-externos.md`, `contexto/BITACORA-INTEGRACION.md`.

**Modificados:** `editor/config.py` (NLTK, generación, presentadores, loop,
Hyperframes, conceptos de ambiente), `editor/editor.py` (opciones nuevas, editor
visual), `editor/f2_cortar.py` y `editor/f4_retencion.py` (perfil de presentador;
f4 además el loop), `editor/f6_overlays.py` (Hyperframes, generación, comparativa,
stickers, eco, posiciones manuales), `editor/f7_animaciones.py` (semilla),
`editor/f8_hyperframes.py` (plantillas nuevas, duraciones, caché por contenido),
`plantillas/compositions/_shared.css` (fuentes), `tarjeta-specs.html` (posición),
`tarjeta-cta.html` (rediseño), `banner-hook.html` (ajuste de letra),
`plantillas/README.md`, `.claude/skills/editor-deviceshop/SKILL.md`.

**Fuera del proyecto:** `C:\ai-video\nltk_data\` (copia de los datos de nltk).

---

# Sesión — Editor visual v2, Fase 0 (2026-07-26, ~14:40–15:05)

Ejecuta `contexto/PLAN-EDITOR-VISUAL-V2.md`. Cierra la Fase 0 (preparación, sin
interfaz todavía). Las Fases 1-5 quedan para la próxima sesión — ver "Punto de
retome" al final.

## 0 · Concurrencia — cómo se resolvió

Al arrancar, `editor/config.py`, `editor.py`, `f6_overlays.py`,
`f7_animaciones.py`, `f8_hyperframes.py` y un archivo nuevo
(`editor/preparar_pip_sol.py`) tenían escrituras de 14:29–14:38, posteriores a
las que registra el plan (§0, cerradas a las 13:18). Se verificó que era
**Antigravity IDE** (proceso activo confirmado con `tasklist`), no otra sesión
de Claude Code. José confirmó que ya no está trabajando y dio luz verde.

Antes de tocar nada se inicializó git en el proyecto (no existía) y se hizo un
commit de snapshot (`8cc9e8c`, solo código/docs vía `.gitignore`, sin medios —
el proyecto pesa 4.1 GB y `salida/`+`entrada/`+medios quedan fuera). Sirve como
red de recuperación si una sesión futura pisa a otra; no cambia nada del
comportamiento del pipeline.

Lo que Antigravity dejó en `editor/` **no se descartó**: ya tenía construida
buena parte de la Fase 3a (animación de sol) — `f7_animaciones.animar_sol()`
(PIL, respaldo), `anim-sol` registrado en `f8_hyperframes.py` (duración 2.4s),
las etiquetas en `config.py`, y un flag `--sol-pip-video` en `editor.py` y
`f6_overlays.py` que elige entre `assets/sol_video_pip.mov` (de
`editor/preparar_pip_sol.py`, video real recortado a tarjeta PiP) o la
animación Hyperframes. José pidió explícitamente **no cerrarlo a una sola
opción**: si hay video real, usarlo; si no, generar con Hyperframes. El
mecanismo de Antigravity ya lo resuelve así (flag apagado = Hyperframes por
defecto, verificado en el log de la Fase 0 más abajo: "animación 'sol'
(variante 0) por 'sol' en 29.0s [Hyperframes]"). Falta exponer esa elección
desde el editor (Fase 3c) — se retoma ahí, no hace falta revisitar el diseño.

## 1 · Recorte de productos faltantes

`quitar_fondos.py --por-modelo 2` (tal como lo pedía el plan) **no hacía nada
nuevo**: 0 hechas, 28 ya existían. Causa real: `seleccionar()` solo agrupaba
`tipo in ("producto", "caja")`, y de los 26 productos sin recorte, la mayoría
son **fundas y accesorios** (`tipo="funda"/"accesorio"`) — nunca iban a entrar
por ese filtro. `_puntaje()` en el mismo archivo ya tenía pesos para esos dos
tipos (20 y 15), así que quedar fuera de `seleccionar()` era una
inconsistencia dentro del propio archivo, no una decisión de diseño. Además
"funda" y "accesorio" son 2 de los 4 tipos que la Fase 2 promete poder filtrar
— no tenía sentido dejarlos sin recorte.

**Corrección aplicada:** `quitar_fondos.py` línea ~58, se amplió el filtro a
`("producto", "caja", "funda", "accesorio")`.

Con el fix: 31/41 productos cubiertos (antes 15/41). Los 10 restantes
(`kobo-clara`, `kobo-libra`, `paperwhite`, `basic`, `resenas`, `videos`,
`videos-pagina-web`) solo tienen `captura-web` o `video` en el catálogo — sin
foto no hay recorte posible, es un límite real de los datos, no del script.

**Verificado a ojo (como pide el plan):** 12 recortes revisados. Dos salieron
mal, exactamente la falla que el plan anticipaba (rembg come el borde de una
prenda oscura sobre fondo oscuro cerca de una sombra/dedo):
- `assets/productos/kobo-clara/frontal.png` — mordida grande en la esquina
  inferior izquierda.
- `assets/productos/funda-kobo-libra-colour/frontal.png` — mismo patrón.

**No se forzaron** (instrucción explícita del plan). Quedan anotados aquí para
que José decida: recortar a mano, usar `vista2.png` de cada uno en su lugar, o
volver a fotografiar con más contraste de fondo.

## 2 · `editor.py --reaplicar`

Implementado (líneas ~87-121 de `editor.py`): si está activo, valida que
`01_transcripcion.json`, `02_cortado.mp4`, `02_cortado.json` y
`03_retencion.plan.json` existan en la carpeta de trabajo (si falta alguno,
error claro y sale) y salta directo a subtítulos → overlays → render → audio,
sin invocar `f1_transcribir.py`, `f2_cortar.py` ni el análisis de
`f4_retencion.py --sin-render`.

**Verificado, no solo "corrió sin error":** copia de prueba de
`C:\ai-video\salida\FINAL_integracion\` a `...\test_reaplicar\` (para no tocar
la corrida de referencia). `07_FINAL.mp4` antes: 1105 frames, 37.132s. Después
de `--reaplicar`: **1105 frames, 37.132s** — idéntico. Confirmado con
`ffprobe -count_frames`, no solo con el log.

**El "~45s" del criterio de aceptación no cerraba tal cual estaba escrito** —
el plan lo calculó sumando solo 3 de los 5 pasos que `--reaplicar` en realidad
ejecuta (le faltaron sumar FASE 2 "subtítulos" y el paso EXTRA "editor visual
v1"). Medido con `time`:
- `--reaplicar` (default, regenera el HTML v1 autocontenido): **77.1s**.
- `--reaplicar --sin-editor-visual`: **33.8s** — dentro del objetivo.

La diferencia (~43s) es el costo de re-embeber en base64 el video completo +
13 MP3 en `09_editor-visual.html` en cada corrida — exactamente lo que la
Fase 1 (servidor) reemplaza. **Conclusión para la Fase 5:** el botón
"Re-renderizar" del editor debe llamar `--reaplicar --sin-editor-visual`, no
`--reaplicar` a secas. Con eso el criterio de aceptación de la Fase 0 se
cumple. Anotado aquí para no repetir la sorpresa en la Fase 5.

`test_reaplicar/` se dejó en `C:\ai-video\salida\` (fuera de OneDrive, no
cuesta nada dejarlo) como evidencia y por si sirve para probar la Fase 1.

## 3 · Proxy de video

`f10_editor_visual.generar_proxy(video, dir_trabajo)` (nueva función). Escala
a 540×960 con `libx264 -preset veryfast -crf 28` + `-movflags +faststart`.
Cachea por mtime contra el video de origen — si el proxy es más nuevo, no
regenera.

Medido sobre `02_cortado.mp4` (75 MB): proxy de **2.04 MB** en **7.66s**
(bajo el ~5MB estimado en el plan). Segunda llamada (cache hit): 0.000s.
Vive en `<dir_trabajo>/_editor/proxy.mp4` — ya fuera de OneDrive porque
`dir_trabajo` cuelga de `config.DIR_SALIDA` (`C:\ai-video\salida\`).

## 4 · Caché de miniaturas del catálogo

`f10_editor_visual.miniatura_catalogo(asset, dir_cache=None, ancho=200)`
(nueva función). JPEG de ~200px de ancho; para `medio="video"` extrae un
frame en t=0.5s con ffmpeg, para `medio="imagen"` usa PIL. Nombre de archivo:
`id` del asset con `\` y `/` reemplazados por `__` (los id del catálogo traen
rutas con backslash). Cachea por mtime del original, igual que el proxy.

Nueva constante `config.DIR_EDITOR_CACHE = C:\ai-video\_editor_cache` (fuera
de OneDrive; es un caché *compartido* entre corridas, a diferencia del proxy
que es por-corrida).

Generadas las 198 miniaturas aptas para PiP: **17.69s** la primera vez, **0**
fallidas. Se disparó un `PIL.Image.DecompressionBombWarning` en una foto
>100MP (propia, sin riesgo real) — se silenció con
`Image.MAX_IMAGE_PIXELS = None` dentro de la función.

Caché ya generado en `C:\ai-video\_editor_cache\thumbs\` — la Fase 1 solo
necesita servirlo por HTTP, no generarlo de nuevo.

## Duda resuelta sin parar a preguntar

Dónde vive el caché de miniaturas (por-corrida vs compartido): el plan no lo
especifica. Se decidió compartido (`C:\ai-video\_editor_cache\`, no dentro de
`dir_trabajo`) porque el catálogo es el mismo para todos los videos — cachear
por-corrida habría repetido las 198 miniaturas en cada carpeta de salida sin
motivo. Coherente con "Generar una sola vez" del plan.

## Archivos tocados esta sesión

**Nuevos:** `.gitignore`, `test_reaplicar/` (fuera de OneDrive, evidencia).

**Modificados:** `editor/editor.py` (flag y lógica `--reaplicar`),
`editor/quitar_fondos.py` (filtro de tipos en `seleccionar()`),
`editor/f10_editor_visual.py` (`generar_proxy()`, `miniatura_catalogo()`),
`editor/config.py` (`DIR_EDITOR_CACHE`).
`assets/productos/`: 31 carpetas con recortes (16 nuevas: fundas y
accesorios).

## Punto de retome (actualizado tras cerrar la Fase 2)

Fases 0, 1 y 2 cerradas y verificadas. Sigue la Fase 5 (ciclo cerrado) de mi
lado — la Fase 3 y 4 las está construyendo otra sesión en paralelo (ver aviso
de reparto más abajo). Detalle de la Fase 2 al final de este archivo.

---

# Sesión — Editor visual v2, Fase 1 (2026-07-26, ~15:05–15:20)

## Aviso: trabajo repartido con otra sesión en paralelo

José va a abrir una segunda sesión de Claude (otra cuenta) mientras esta
sigue corriendo. Para no chocar archivos, se repartió así:
- **Esta sesión:** `editor/f11_servidor.py` (servidor, Fase 1/2/5) y
  `editor/f10_editor_visual.py`.
- **La otra sesión:** Fase 3 (animaciones, incluido el sol) y Fase 4
  (sonidos) — sobre todo `f7_animaciones.py`, `f8_hyperframes.py`,
  `plantillas/compositions/anim-sol.html`, `f5_audio.py`.
- Punto de fricción conocido: ambas fases tocan `f6_overlays.py` y
  `config.py`, en zonas distintas (esta sesión: flag `--eventos-manual` para
  Fase 2; la otra: `CONCEPTOS_PREFIEREN_ANIMACION` y el veto de
  `anim_usadas`). Si la próxima sesión ve algo raro en esos dos archivos que
  no reconoce, es la otra sesión — revisar `git log`/`git diff` antes de
  asumir que es un bug propio.

## Qué se construyó

1. **`f4_retencion.encuadre_en_t()`** (nueva función, línea ~211): se
   **extrajo** el cálculo de (cx, cy, zoom) — interpolación del track de
   rostro + `calcular_zoom_en_t()` + blend de loop — del loop de
   `renderizar_con_zoom()`, que ahora la llama en vez de tener el cálculo
   inline. Misma implementación para el render real y para el preview del
   editor: no hay dos copias que puedan divergir con el tiempo.

   **Verificado que el refactor no cambió el resultado:** se re-renderizó
   `test_reaplicar` completo y se comparó contra una copia guardada antes del
   refactor con `ffmpeg -lavfi ssim`: **SSIM = 1.000000 en los 1105 frames**
   (coincidencia exacta, no aproximada).

2. **`f10_editor_visual.muestras_encuadre()`** (nueva): genera un
   `[t, cx, cy, zoom]` por frame (~1116 muestras para 37s) llamando a
   `encuadre_en_t()`. `recolectar()` ahora incluye `"encuadre"`,
   `"resolucion_origen"` (w/h reales de `02_cortado.mp4`, vía nuevo
   `_resolucion()`), `"fps"`, y los `"overlays"` ahora traen `x`, `y`,
   `medio`, `archivo` (antes solo tenían tipo/ini/fin).

3. **`editor/f11_servidor.py`** (nuevo, ~300 líneas). `http.server` de
   stdlib en `127.0.0.1` (nunca `0.0.0.0`), sube de puerto si 8765 está
   ocupado y avisa cuál usó. Rutas: `GET /` (interfaz), `GET /datos`
   (`recolectar()` en JSON), `GET /video` (proxy con **soporte de Range**
   implementado a mano — necesario para que arrastrar la línea de tiempo del
   `<video>` no tenga que descargar el archivo entero), `GET /archivo?ruta=`
   (sirve PNGs/assets con lista blanca de raíces permitidas —
   `RAIZ_AI_VIDEO` y `RAIZ_PROYECTO` — para no exponer el filesystem
   completo aunque el servidor sea solo-localhost).

   Interfaz (HTML+CSS+JS planos, sin dependencias): lienzo con proporción
   1080×1920, el `<video>` (proxy) con `transform: scale(zoom)
   translate(-x0*s, -y0*s)` recalculado en cada `requestAnimationFrame` a
   partir de la muestra de encuadre más cercana al `currentTime`; overlays
   PiP (los "movibles" de `recolectar()`, ya en base64 como en v1) dibujados
   como `<img>` con `transform: translate(x*s, y*s) scale(s)`, mostrados
   solo dentro de `[ini, fin)`; línea de tiempo con franjas de overlay +
   transcripción palabra por palabra, clic para saltar el video a ese
   segundo.

   **Deliberadamente fuera de esta fase** (le toca a la Fase 3c): los
   overlays con `medio == "video"` (animaciones Hyperframes/PIL — hook, cta,
   specs, batería, splash, sol en este video de prueba) no se dibujan en el
   lienzo todavía. Son 6 de los 9 eventos de este video; solo los 3
   `pip-producto` (imagen estática) se ven hoy.

## Cómo se verificó (sin poder tomar screenshot del navegador)

El panel del navegador de esta sesión no compuso frames (`the Browser pane
is not displayed, so the page is not compositing frames` — límite del
entorno, no del código) y el `<video>` no llegó a disparar `seeked` con la
pestaña sin composición. En vez de forzarlo o de asumir que "cargó y ya":

1. Se leyó el DOM real vía `javascript_exec`: se llamó a las mismas
   funciones JS (`muestraEn`, `aplicarEncuadre`, `actualizarOverlays`) para
   t=0.4s (punch-in real, zoom 1.15 — el máximo de todo el video),
   t=4.5s y t=20.5s (con overlay `pip-producto` visible), y se leyó
   `video.style.transform` y `img.style.transform` resultantes.
2. Se calculó el mismo `transform` **de forma independiente en Python**
   (mismo x0/y0/zoom/clip que usa `f4_retencion`) para los mismos t y el
   mismo ancho de lienzo (333px, el que reportó el DOM).
3. **Los tres momentos coincidieron carácter por carácter**
   (`scale(1.15) translate(-10.99px, -38.14px)` etc.) — la portada de la
   fórmula de recorte a CSS/JS no tiene error de signo, eje ni escala.
4. Se extrajeron los fotogramas reales de `06_video.mp4` en esos mismos 3
   instantes con ffmpeg y se miraron (no solo se leyó el log): t=0.4s
   muestra el punch-in centrado en el rostro con el hook; t=4.5s muestra el
   PiP de "libros" arriba a la derecha (x=620 de 1080 ⇒ 57%, coincide);
   t=20.5s muestra el PiP de "tina" arriba a la izquierda (x=40 ⇒ 4%,
   coincide).

Es una verificación más estricta que comparar dos capturas a ojo (la
comparación de transform es exacta, no aproximada), pero **queda pendiente
la comparación visual directa en un navegador real** cuando José lo abra a
mano — si algo se ve raro ahí que esta verificación no habría detectado
(ej. un bug de CSS que no toca `.transform` sino otra propiedad), anotarlo.

## Duda resuelta sin parar a preguntar

Los overlays `medio == "video"` (animaciones) no tienen un "primer
fotograma" pre-extraído todavía — el plan (Fase 3c) lo pide como bloque en
la timeline, no necesariamente en el lienzo. Se decidió **no** dibujarlos en
el lienzo en esta fase (dejar el hueco visible es más honesto que fingir una
posición) y documentarlo en la interfaz... **pendiente**: el aviso en pantalla
sobre esta limitación (que el plan pide explícitamente: "decirlo en la
interfaz, no dejar que José lo descubra solo") todavía no está en el HTML.
Añadir un texto visible antes de que José lo use — quedó solo en el
`<p class="hint">` genérico, falta ser específico con qué overlays faltan.

## Archivos tocados esta fase

**Nuevos:** `editor/f11_servidor.py`.

**Modificados:** `editor/f4_retencion.py` (`encuadre_en_t()` extraída y
reutilizada, sin cambio de comportamiento — SSIM 1.0 verificado),
`editor/f10_editor_visual.py` (`_resolucion()`, `muestras_encuadre()`,
`recolectar()` ampliado).

## Punto de retome

Sigue la **Fase 2** del plan (§4): endpoint `/catalogo` (198 aptos,
filtrados por producto dominante — `f6_overlays._producto_dominante` ya
existe), grid con tarjetas vía `/tarjeta` (usar `f6_overlays.render_pip_producto`,
cachear igual que `miniatura_catalogo`), flag nuevo
`f6_overlays.py --eventos-manual JSON` (reemplaza la lista completa de
eventos, distinto de `--posiciones-manual` que solo mueve) propagado en
`editor.py`, y los límites automáticos (`INSERTOS_MAX`,
`INSERTO_SEPARACION_MIN_S`) como avisos en vez de bloqueos cuando vienen del
editor. Antes de tocar `f6_overlays.py`, revisar si la otra sesión ya lo
modificó (Fase 3b también lo toca) — `git diff` primero.

---

# Sesión — Editor visual v2, Fase 2 (2026-07-26, ~15:20–15:55)

## Qué se construyó

1. **`f6_overlays.cargar_eventos_manual(ruta_json, dir_tmp, catalogo=None)`**
   (nueva): lee la lista completa de insertos armada en el editor. Cada
   entrada trae `{ini, fin, x, y, asset_id}` (busca el asset en el catálogo,
   renderiza con `render_pip_producto()` y cachea el PNG por `asset_id` en
   `_tmp_overlays/manual_<id>.png`) o `{..., archivo}` (reusa un PNG ya
   renderizado, para los eventos que José no tocó). `None` si el JSON no
   existe o es inválido → cae al disparo automático, igual que
   `aplicar_posiciones_manual`.
2. **`f6_overlays.planificar_overlays(..., eventos_manual=None)`**: si viene
   una lista, la usa tal cual **en vez de** llamar a
   `planificar_insertos_por_palabra()` — no se arranca ComfyUI/Flux si el
   editor ya decidió qué mostrar. Hook/CTA/animaciones/specs/comparativa no
   se tocan: `eventos_manual` solo reemplaza los `pip-producto`.
3. **Flag `--eventos-manual JSON`** en `f6_overlays.py` y propagado en
   `editor.py` (distinto de `--posiciones-manual`, que solo mueve).
4. **`f10_editor_visual.render_tarjeta_catalogo()`** (reusa
   `f6_overlays.render_pip_producto()`, cachea en
   `C:\ai-video\_editor_cache\tarjetas\` por mtime — la tarjeta que ve José
   en el grid es la MISMA función que compone el video real, no una
   aproximación), **`fondo_pendiente()`** y **`catalogo_pip()`** (filtra por
   `_producto_dominante()` salvo `todos=True`).
5. **Endpoints nuevos en `f11_servidor.py`:** `GET /catalogo`,
   `GET /miniatura?asset_id=`, `GET /tarjeta?asset_id=`,
   `POST /guardar` (escribe `<dir_trabajo>/ajustes.eventos.json`, atómico
   vía `.tmp` + `replace()`).
6. **Panel "Colección de PiP" en la interfaz:** lista de los insertos
   actuales con su tarjeta, botones Sustituir/Quitar, botón "+ Añadir PiP en
   el segundo actual", grid del catálogo (miniaturas vía `/miniatura`,
   badge "sin recorte" para `fondo_pendiente`, checkbox "ver todos"),
   avisos amarillos (no bloqueos) cuando se supera `INSERTOS_MAX` o se
   rompe `INSERTO_SEPARACION_MIN_S`, botón Guardar.

## Cómo se verificó

**Extremo a extremo, dos veces, con evidencia real — no solo "no tiró error":**

1. **Por línea de comandos:** armé a mano un `eventos_manual_prueba.json` con
   los tres casos del criterio de aceptación (sustituir el PiP de "libros" a
   los 4.0s por otro asset, añadir uno nuevo a los 21.0s en el hueco que deja
   "tina" al quitarse, sustituir el segundo "libros" a los 24.2s) y corrí
   `editor.py --reaplicar --eventos-manual ...`. Extraje fotogramas de
   `07_FINAL.mp4` en 4.5s/20.5s/22.0s/25.5s con ffmpeg y los miré: el
   sustituido se ve, el quitado ya no está, el añadido aparece donde debía.
   Log confirma además que el SFX `pip-producto` se reubicó solo a los
   nuevos tiempos (21.00s, 24.20s) — la regla "el sonido acompaña al evento
   visual" (Fase 4) ya funciona con eventos manuales sin tocar nada de audio.
2. **En el navegador de verdad** (no pude tomar screenshot por la misma
   limitación de la Fase 1, así que ejecuté la interacción real vía
   `javascript_exec`, clic por clic, no simulando el resultado): abrir el
   catálogo, elegir un asset (sustituye), añadir uno nuevo, quitar uno,
   guardar. El grid mostró 65 assets al filtrar por `#paperwhite` (producto
   dominante detectado) de 198 totales. El archivo guardado
   (`ajustes.eventos.json`) coincidió exactamente con lo que se veía en
   pantalla. Los avisos de separación mínima aparecieron correctamente al
   forzar dos insertos a 0.5s de distancia.

## Dudas resueltas sin parar a preguntar

1. **¿`--eventos-manual` reemplaza TODOS los eventos o solo los
   `pip-producto`?** El plan dice "la lista completa de eventos" pero el
   contexto (Fase 2 = "la colección de PiP") y los ejemplos que da
   (sustituir/añadir/quitar PiP) apuntan a que es solo los insertos de
   producto, no hook/cta/animaciones — esos son dominio de la Fase 3. Así
   se implementó. Si en la Fase 3 hace falta que las animaciones también
   sean editables por esta vía, se anotará ahí.
2. **`POST /tarjeta` del diagrama del plan (§3) se implementó como `GET
   /tarjeta?asset_id=`.** Es más simple para el frontend (un `<img src=...>`
   directo, sin fetch+blob) y el resultado es igual de cacheable — no
   cambia el comportamiento que pedía el plan (renderiza y cachea la
   tarjeta), solo el verbo HTTP.
3. **`/catalogo` sin `todos=1` y sin producto dominante detectado:** devuelve
   el catálogo completo (no hay nada por lo cual filtrar). No estaba
   especificado, es el comportamiento obvio.

## Qué quedó pendiente

- **Arrastrar la posición (x, y) del PiP en el lienzo.** El editor deja
  elegir *qué* asset y *cuándo*, pero la posición todavía se hereda del
  valor por defecto (620,134 o 40,134, alternando) o de la automática si no
  se tocó. Mover con el mouse quedó fuera de esta fase por tiempo — es una
  extensión natural sobre lo que ya existe (`ev.x`/`ev.y` en `edicionPip`),
  no un rediseño.
- El botón "Guardar" no dispara el render — hay que copiar el comando que
  muestra la interfaz y correrlo a mano. Eso es exactamente lo que arma la
  Fase 5.
- No se implementó el botón "quitar fondo" para assets con `fondo_pendiente`
  (el plan lo menciona como opcional: "ofrecer un botón que dispare
  `quitar_fondos.py`"). Queda para cuando se retome esta fase si José lo
  pide.

## Archivos tocados esta fase

**Modificados:** `editor/f6_overlays.py` (`cargar_eventos_manual()`,
`planificar_overlays(eventos_manual=...)`, flag `--eventos-manual`),
`editor/editor.py` (propagación del flag), `editor/f10_editor_visual.py`
(`render_tarjeta_catalogo()`, `fondo_pendiente()`, `catalogo_pip()`,
`movibles` ahora trae `asset`/`archivo`, `recolectar()` trae `limites`),
`editor/f11_servidor.py` (`/catalogo`, `/miniatura`, `/tarjeta`, `/guardar`,
panel completo de colección de PiP en HTML/CSS/JS).

## Punto de retome

Sigue la **Fase 5** del plan (§4): botón "Re-renderizar" → `POST /render` →
`editor.py --reaplicar --sin-editor-visual` (el `--sin-editor-visual` es
obligatorio, ver la nota de timing de la Fase 0: sin él el ciclo tarda 77s
en vez de 34s) con los JSON de ajustes ya escritos por `/guardar`. Progreso
en vivo leyendo las líneas `render: N/M frames` que imprime
`f4_retencion` (stdout ya va a un log de texto, no a un pipe — hay que
leerlo con polling o Server-Sent Events, ambos triviales con stdlib). Guardar
siempre antes de renderizar (ya existe `/guardar`). Recargar el preview al
terminar. Apertura automática al terminar `editor.py` + apertura manual con
`f11_servidor.py "<carpeta>"` (ya soportado, es como se probó todo esta
sesión). La Fase 4 (sonidos) la está cerrando la otra sesión — cuando
termine, revisar `git log` antes de tocar `f5_audio.py` o el panel de SFX de
`f11_servidor.py` si se llega a construir ahí.
