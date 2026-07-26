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

## Punto de retome

Fase 0 cerrada y verificada con evidencia (frames idénticos, timings medidos,
recortes revisados a ojo). **Sigue la Fase 1** del plan (§4): crear
`editor/f11_servidor.py` con `http.server` en `127.0.0.1:8765`, sirviendo la
interfaz y `/datos` (ampliar `recolectar()` de `f10_editor_visual.py`, no
duplicarlo), con el preview de encuadre real sobre `_editor/proxy.mp4` (ya
generado por esta sesión) replicando el crop de `f4_retencion.py:374-386` con
`transform: scale()` en CSS. El criterio de aceptación de la Fase 1 exige
comparar contra fotogramas reales extraídos con ffmpeg en 3 momentos, uno
dentro de un punch-in — no basta con que cargue en el navegador.
