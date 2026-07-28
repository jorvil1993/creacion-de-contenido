# Mejoras pendientes — feedback de José sobre el primer video real

Origen: revisión de `salida/v2_final/07_FINAL.mp4` (primer video procesado
de punta a punta con grabación real, 2026-07-26).

**No implementar mientras la sesión de auditoría (Fable) esté trabajando en
`editor/`.** Todo esto toca Fase 4 (audio) y Fase 5 (overlays).

Ordenado por impacto en retención, no por dificultad.

---

## 1. ✅ RESUELTO — El hook aparecía cortado a media frase

*(Arreglado el 2026-07-26. Se deja el diagnóstico como referencia.)*

**Qué se hizo:**
- La recolección ya no corta por conteo de palabras: junta hasta el signo de cierre (`?` `!` `.`). Tope de seguridad en `config.HOOK_MAX_PALABRAS` (14); solo si se agota sin cerrar la frase se retrocede a la última coma.
- Se quitó el límite del "primer plano" para el hook. En el video **ya editado** esas palabras se oyen seguidas y los subtítulos las muestran así, de modo que el banner puede hacerlo igual. Ese límite era lo que dejaba el hook en *"¿Quieres leer más este año"* y le quitaba el *"pero te da pereza"* que le da sentido.
- **`render_hook_banner` ahora mide el texto de verdad** con la fuente y envuelve dinámicamente: antes partía la lista de palabras por la mitad y asumía 2 líneas con altura fija. Ahora la tarjeta crece según el contenido y, si hicieran falta más de 3 líneas, baja el tamaño de letra (58→52→46→40) antes que recortar.
- **Nuevo `--hook "texto"`** en `editor.py` y `f6_overlays.py` para usar los hooks curados de `banco-hooks.md`. Gana siempre sobre el automático.

**Resultado verificado:** el hook pasó de `"¿Quieres leer más este año, pero te"` a `"¿Quieres leer más este año, pero te da pereza cargar libros pesados?"`, renderizado en 3 líneas sin desbordar.

**Nota honesta:** la frase completa del video son 12 palabras, bastante más que las ≤7 que recomienda la investigación para leerse en 1.5s. El automático ya no produce errores, pero **para máxima retención conviene usar `--hook`** con uno del banco. Comparación renderizada: el hook curado entra en 2 líneas con letra grande; el automático necesita 3 líneas más chicas.

---

## 1-bis. (diagnóstico original)

**Qué pasa:** en el segundo 1 el banner dice *"¿Quieres leer más este año, pero te"* y ahí se corta. La frase real seguía ("...pero te da pereza").

**Por qué:** `f6_overlays.py` usa como texto de hook **las primeras ~7 palabras de la transcripción**, cortando por conteo de palabras. Es un placeholder que la sesión A dejó documentado a propósito — nunca fue el diseño final.

**Impacto:** máximo. Los primeros 3 segundos deciden la retención de todo el video (sección 4.2 del plan), y un hook cortado a media frase se lee como error.

**Cómo arreglarlo:**
- Existe `contexto/banco-hooks.md` con **40 hooks reales** ya escritos por la sesión B, verificados a ≤7 palabras y en tipo oración. Hay que conectarlo.
- Regla de corte: **nunca cortar por conteo de palabras**. Cerrar en el signo de puntuación o en el final de la frase transcrita.
- Si la frase completa supera las 7 palabras del límite del plan, mejor elegir un hook del banco que truncar la del video.
- Ideal: permitir que José elija el hook al invocar el pipeline (`--hook "..."`), con el banco como sugerencia.

---

## 2. ✅ RESUELTO — Los efectos de sonido se disparaban sin criterio editorial

*(Arreglado el 2026-07-26. Se deja el diagnóstico como referencia.)*

**Qué se hizo:** `construir_eventos_sfx()` ya no recorre los picos de energía RMS. Ahora recolecta **eventos visuales** y les asigna sonido:

| Evento visual | Sonido | Volumen |
|---|---|---|
| Hook (t=0) | `impacto_dramatico` | 0.85 |
| Corte entre planos | `transicion_corte` / `transicion_swipe` (rotando) | 0.45 |
| Punch-in fuerte | 4 whooshes rotando | 0.30 |
| Aparece PiP de producto | `pop` | 0.75 |
| Aparece sticker | `notificacion_chime` | 0.60 |
| Tarjeta de CTA | `notificacion_success` | 0.80 |

Además:
- **Solo los N picos más fuertes** llevan sonido (`SFX_MAX_PUNCH_INS = 6`); los demás hacen el zoom en silencio.
- **Separación mínima** entre dos SFX (`SFX_SEPARACION_MIN_S = 1.2`), resuelta por prioridad: un overlay le gana a un punch-in.
- **Volumen por tipo**, no uno global. La transición es casi subliminal; la aparición de producto sí destaca.
- `f5_audio.py` recibe los eventos de overlay vía `--overlays` (los conecta `editor.py`).

**Medición con datos reales (VIDEOV2, 37s):**

| | Antes | Ahora |
|---|---|---|
| Sonidos | 18 | 13 |
| Archivos distintos | 2 | **8** |
| Separación mínima | **0.25s** | 1.51s |
| Separación promedio | 1.98s | 3.08s |

Cada sonido cae ahora sobre algo que se ve: el pop entra a los 14.87s justo cuando aparece el Kindle, la notificación a los 30.67s con la tarjeta de CTA.

---

## 2-bis. (diagnóstico original)

**Qué pasa:** suena siempre el mismo efecto, repartido por todo el video sin relación con lo que ocurre en pantalla.

**Diagnóstico de José, que es el correcto:**

> *"normalmente yo lo veo que lo usan cuando corresponde, o sea con un buen timing; ahorita está uso sin discreción, uso libre donde quiera"*

El problema **no es la cantidad** (17 SFX en 37s puede estar bien). El problema es **cuándo suenan**.

**Por qué pasa:** hoy el SFX se dispara en cada **pico de energía RMS del audio**, es decir, cada vez que José levanta la voz. Eso es un criterio *mecánico*, no editorial: correlaciona con el volumen de su habla, no con que esté pasando algo en pantalla. Un editor humano pone el sonido **cuando algo ocurre visualmente**.

Además `config.SFX_PUNCH_IN` apunta a un solo archivo (`whoosh_deep_1.mp3`), así que encima siempre es el mismo sonido. Hay **13 en `assets/sfx/`** y se usa 1.

**Cómo arreglarlo — el cambio conceptual primero:**

**Desacoplar el SFX del pico de audio y atarlo al evento visual.** Que el sonido acompañe algo que se ve:

| Evento visual | Sonido |
|---|---|
| Aparece un overlay / PiP de producto | pop o destello |
| Corte entre planos (jump cut) | whoosh, rotando entre los 4 |
| Hook al inicio | impacto |
| Aparece la tarjeta de CTA | notificación |
| Animación contextual (ver punto 6) | el que corresponda a la animación |

**Y solo entonces las mejoras de forma:**
- Rotar los whooshes para que no suene dos veces el mismo seguido.
- Volumen diferenciado: el de transición casi subliminal, el de aparición de producto sí destacado. Hoy `SFX_VOLUMEN` es un valor único para todos.
- Silencio también es una herramienta: si en un tramo no pasa nada visual, que no suene nada.

**Criterio de aceptación:** ver el video sin audio y poder predecir dónde debería sonar un efecto. Si el SFX no coincide con algo que se ve, sobra.

---

## 3. 🟡 PARCIAL — El inserto tapaba la cara

*(Posición resuelta el 2026-07-26. Falta quitar el fondo de las fotos.)*

**Resuelto (3b, posición):** `_posicion_inserto()` usa el `track_rostro` que
`f4_retencion` ya calculaba y se descartaba. El inserto se coloca al lado
contrario del rostro y por encima de la banda de subtítulos. Se redujo de
520×680 a 400×520. **Además se arregló un bug latente:** `render_pip_producto`
guardaba el PNG del ancho completo del lienzo con la tarjeta centrada dentro,
así que cualquier desplazamiento horizontal se duplicaba y la tarjeta se salía
del cuadro; ahora con `centrar_en_lienzo=False` guarda solo la tarjeta.

**Pendiente (3a):** quitar el fondo con `rembg` y guardar PNG transparentes en
`assets/productos/`. Hoy los insertos usan las fotos tal cual, con su fondo.

---

## 3-bis. (diagnóstico original)

**Qué pasa:** en el segundo 18 el PiP del Paperwhite entra justo sobre su rostro. Además la foto tiene **fondo blanco recortado en rectángulo**, que se ve pegado.

**Cómo arreglarlo — dos cosas separadas:**

**a) Quitar el fondo de las fotos de producto**
- `rembg` (Python, local, gratis, sin cuenta) quita fondos con buena calidad en productos.
- Guardar los PNG con transparencia en `assets/productos/`.
- Sin fondo, el producto se integra en vez de verse como una calcomanía.

**b) Posicionar el overlay esquivando el rostro**
- **El pipeline ya sabe dónde está la cara en cada momento.** `f4_retencion.py` guarda `track_rostro` en el `.plan.json` con las coordenadas normalizadas del rostro cuadro a cuadro.
- Usar ese dato para colocar el producto en la zona libre: si el rostro está en el tercio superior, el producto va abajo; si está centrado, va a un costado.
- Es la solución elegante: no hay que inventar una posición fija, el dato ya está calculado y sin usar.
- Respetar siempre las zonas seguras (15% inferior, 10% superior) y no invadir la banda de subtítulos al 77%.

---

## 4. 🟠 La tarjeta de CTA final se ve fea

**Qué pasa:** el recuadro navy sólido con el WhatsApp se siente pesado y pegado sobre el video.

**Cómo arreglarlo:**
- **Quitar el fondo sólido.** Dejar el ícono de WhatsApp + el número flotando sobre el video, con contorno o sombra suave para que se lea sobre cualquier fondo (mismo principio que los subtítulos: legibilidad sin caja).
- Conseguir un **ícono de WhatsApp** en PNG con transparencia o SVG.
- Mantener la jerarquía: ícono + número grande, handle de TikTok más chico.
- Si igual hace falta algo de fondo para legibilidad, usar una pastilla redondeada semitransparente, nunca un rectángulo opaco.

---

## 5. 🟡 Faltan imágenes contextuales según lo que se dice

**Qué pide José:** que el sistema **analice el texto** y cuando él diga "sol", "tina", etc., aparezca una fotito cuadrada ilustrando eso — como hacía la agencia en su video.

**Por qué importa:** es lo que llena el presupuesto visual (sección 6.1 del plan: ~14 beats visuales en 35s). Hoy solo hay hook, un PiP y el CTA. Estas imágenes cubrirían los huecos y evitarían la planitud.

**Cómo arreglarlo:**
- Ya existe el mecanismo de sincronización por palabra clave en `f6_overlays.py` (`PALABRAS_CLAVE_STICKER` en `config.py`), pero con una tabla genérica y sin imágenes.
- `contexto/catalogo-productos.md` ya trae una lista de **"palabras clave para overlays"** por producto, escrita justamente para esto por la sesión B.
- **Fuente de las imágenes — dos caminos, se pueden combinar:**
  - **Generación local con Flux**, ya instalado en `C:\ai-video\comfyui` con el workflow listo en `assets/comfyui-workflows/`. La sesión B ya generó 6 imágenes en menos de 2 minutos. Ventaja: gratis, ilimitado, estilo consistente.
  - **Banco de imágenes libres** para conceptos genéricos (sol, agua, cama, café).
- **Cachear por palabra clave** en `assets/generado/` para no regenerar lo mismo en cada video.
- Formato: cuadradas con esquinas redondeadas, como el estilo de la agencia. Mismo criterio de posición que el punto 3 (esquivar el rostro).
- **Ojo con la limitación ya documentada:** la sesión B anotó que Flux genera un e-reader *genérico creíble*, no un Kindle real. Para el producto en sí hay que usar fotos reales; Flux sirve para conceptos y ambientes.

---

## 6. 🟡 Animaciones contextuales con sonido

**Qué pide José:** por ejemplo, al decir *"te lo enviamos a todo Bolivia"*, que aparezca una **motito cruzando de izquierda a derecha** con sonido suave de moto por detrás.

**Cómo arreglarlo:**
- `plantillas/` ya tiene un proyecto **Hyperframes** completo con GSAP, que es exactamente la herramienta para esto (animaciones seekables, render determinista a MP4 con alfa).
- La sesión B dejó una recomendación importante en su bitácora: **usar `--format mov` (ProRes 4444) y no `webm`**, porque el canal alfa de VP9 no se decodificaba bien con el ffmpeg del pipeline. Verificado por ella a nivel de píxel.
- Definir un catálogo de animaciones disparadas por frase, no solo por palabra suelta:

| Frase gatillo | Animación | Sonido |
|---|---|---|
| envíos / a todo Bolivia | moto cruzando | motor suave |
| garantía / sellado | sello estampándose | golpe seco |
| batería / semanas | batería llenándose | zumbido corto |
| oferta / descuento | destello + precio | brillo |

- El sonido debe ir **por debajo de la voz**, con el mismo ducking que la música. Nunca competir con lo que José dice.
- **Pendiente de integración mayor:** `f6_overlays.py` hoy renderiza con Pillow (imágenes estáticas) y no invoca Hyperframes. La sesión A lo dejó anotado como integración pendiente porque `plantillas/` era territorio de B. Este punto es el que justifica hacer esa conexión.

---

## 7. 🟠 Biblioteca de fotos reales sin aprovechar

José tiene **263 archivos (~900 MB)** en `contexto/fotos y videos/`, usados para su página web. El pipeline no los conoce: hoy el PiP usa una foto de stock genérica.

### Lo que hay

| Carpeta | Contenido |
|---|---|
| `fotos-dispósitivos/` | **15 modelos** separados por versión y capacidad: kindle basic, paperwhite 16/32gb, colorsoft 16/32gb, scribe 32/64gb, scribe colorsoft, kobo clara colour, kobo libra colour, kobo stylus, paperwhite kids, y una carpeta "varios modelos en la misma foto" |
| `fotos-fundas/` | **~103 fotos**, estructura producto → color, con `LEEME.md` que documenta el criterio |
| `fotos-accesorios/` | brazo para agarrar, cargador 9W, pasa páginas |
| `pagina amazon/` · `pagina kobo/` | capturas de las páginas de producto |
| `videos/` | **26 videos, 419 MB** — 22 de la web + 2 de producto en caja |
| `RESEÑAS/` | 2 archivos |

### Regla importante: no reorganizar el original

Esa biblioteca **está en uso por la página web** y su estructura ya es buena (`fotos-fundas/` incluso tiene su propia documentación). Reorganizarla rompería la web.

**Lo correcto es derivar, no mover:** generar una biblioteca *nueva* optimizada para video en `assets/productos/`, dejando el original intacto como fuente.

### Qué hacer

1. **Seleccionar, no procesar todo.** El pipeline no necesita 263 fotos: necesita **2 o 3 tomas buenas por modelo** (frontal, en ángulo, en mano). Procesar las 263 sería desperdicio.
2. **Quitar el fondo** con `rembg` (local, gratis) y guardar PNG con transparencia en `assets/productos/<modelo>/`.
3. **Nombres normalizados**: sin acentos ni espacios. Hoy hay `fotos-dispósitivos` (con acento y con la "ó" mal puesta) y `kinlde paperwhite 32gb` (typo). Los acentos y espacios en rutas ya causaron un bug con ffmpeg antes — la biblioteca derivada debe usar `kindle-paperwhite-32gb`, etc.
4. **Mapear modelo → carpeta** para que la sincronización por palabra clave sepa qué foto sacar cuando José nombre un producto. El `catalogo-productos.md` de la sesión B ya tiene las palabras clave por producto; falta unir ambos lados.
5. **Los 26 videos son B-roll sin explotar.** Vale la pena revisar qué son (¿producto en uso? ¿unboxing?) y catalogarlos: un clip real del Paperwhite pasando página vale más que cualquier imagen generada. Esto puede reducir bastante la necesidad del punto 5 (generación con Flux).

### Detalles menores a limpiar en la derivada

- Hay dos carpetas casi iguales: `fotos fundas` (con espacio, 6 archivos) y `fotos-fundas` (con guion, 111). Revisar si la primera es un residuo.
- `fotos-fundas/funda-kindle-paperwhite-colorsoft-outlet/` tiene una nota explícita en el LEEME: esas fotos deben mostrar las manchas de cerca porque es producto outlet y la honestidad visual es el argumento de venta. **No usarlas como hero shot** en video sin ese contexto.

---

## ESTADO AL CIERRE DE LA SESIÓN DE INTEGRACIÓN (2026-07-26)

Detalle completo, con mediciones: `contexto/BITACORA-INTEGRACION.md`.

| # | Punto | Estado |
|---|---|---|
| 1 | Hook cortado a media frase | ✅ resuelto — y migrado a Hyperframes, con ajuste automático del tamaño de letra |
| 2 | SFX sin criterio editorial | ✅ resuelto (volúmenes normalizados; José confirmó que ya se oyen) |
| 3a | Quitar fondo del PiP con rembg | ✅ resuelto — `quitar_fondos.py`, 28 fotos en `assets/productos/`; el pipeline prefiere la versión recortada |
| 3b | PiP tapaba la cara | ✅ resuelto — va arriba, en la franja vacía |
| 4 | CTA con recuadro feo | ✅ resuelto — sin caja, contorno negro, ícono de WhatsApp; ahora en Hyperframes y con el eco del loop |
| 5 | Imágenes contextuales por palabra | ✅ resuelto — catálogo de 262 assets + **generación con Flux como respaldo** para conceptos de ambiente |
| 6 | Animaciones | ✅ reimplementadas en Hyperframes con GSAP + variación determinista por video |
| 7 | Biblioteca de fotos sin usar | ✅ indexada y etiquetada |
| 8 | Editor visual de sonidos y posiciones | ✅ resuelto — `f10_editor_visual.py` genera un HTML autocontenido por corrida |

### Los 8 puntos de la sesión de integración

| # | Punto | Estado |
|---|---|---|
| 1 | ComfyUI en tiempo real | ✅ `editor/f9_generar.py` — servidor bajo demanda, caché por hash del prompt, semilla determinista, respaldo del catálogo. + `contexto/prompts-externos.md` |
| 2 | Hyperframes completo | ✅ las 9 plantillas conectadas; ficha técnica subida a la franja superior; comparativa y stickers enchufados; hook y CTA migrados. **Bug encontrado: ninguna cargaba Poppins** |
| 3 | Animaciones con variación | ✅ reimplementadas en GSAP + semilla derivada del nombre del video (PIL queda de respaldo, también con variación) |
| 4 | Editor visual | ✅ sonidos arrastrables + posiciones de PiP sobre el fotograma real; exporta el JSON que ya consumía el pipeline |
| 5 | Diseño de loop | ✅ encuadre que vuelve al primer frame (PSNR 12.2 → **20.8 dB**) + eco del hook en el CTA |
| 6 | Empaquetar como skill | ✅ SKILL.md completo, con `--presentador jose\|esposa` propagado a las fases que dependen de la persona |
| 7a | Moto en un video real | ✅ verificada sobre metraje real (disparada a mano: este guion no dice "envíos"/"Bolivia") |
| 7b | Datos de nltk fuera de AppData | ✅ copiados a `C:\ai-video\nltk_data`, `NLTK_DATA` fijado en `config.py` |
| 7c | 1.72 GB de intermedios en OneDrive | ⏳ **bloqueado por permisos** — comando listo en la bitácora de integración |

**Lo que falta, en orden:**
1. **Mover los 1.72 GB** de `salida/` fuera de OneDrive (comando listo, hay que
   correrlo a mano: el sistema de permisos bloquea el borrado en la nube).
2. **Calibrar el perfil de la esposa** con su primera grabación real — hoy son
   valores de partida y el pipeline lo avisa por consola.
3. **La comparativa no se ha visto en un video real**: hace falta un guion que
   nombre dos modelos (p. ej. Paperwhite vs Colorsoft).
4. **Eliminar la recompresión del paso de corte** — sigue siendo la mejora de
   calidad #1 pendiente (sección 4-bis de `AUDITORIA-OPTIMIZACION.md`).

---

## 8. 🟠 Editor visual de sonidos Y POSICIONES (artifact / HTML) — PARA SONNET

> **Ampliación pedida por José:** que el mismo editor sirva para decidir
> **dónde va cada PiP**, no solo los sonidos. Hoy la posición se calcula sola
> (arriba, al lado contrario del rostro) y funciona, pero él quiere poder
> moverla a mano cuando el encuadre lo pida.

Idea de José (2026-07-26): la hoja de sonido en markdown funciona, pero
**colocar efectos por timestamp sería mucho más fácil en una interfaz visual**.

**Qué construir:** un artifact HTML con la línea de tiempo del video:
- La transcripción en horizontal con su escala de tiempo
- Marcadores de los SFX ya colocados, arrastrables
- Un selector con el vocabulario de sonidos disponible (`assets/sfx/`)
- Reproducción del sonido al seleccionarlo, para elegir de oído
- Al terminar, que emita el JSON con el formato de `--sfx-manual`

**Encaja con lo que ya existe:** `f5_audio.py --sfx-manual archivo.json` ya
acepta una lista escrita a mano y reemplaza la automática. La interfaz solo
tiene que producir ese JSON. Y `--hoja-sonido` ya genera todos los datos que
necesita (tiempos, transcripción, vocabulario, volúmenes).

**Ojo con el alcance:** los artifacts no pueden cargar archivos externos, así
que el audio y la forma de onda habría que embeberlos o trabajar solo con la
línea de tiempo y la transcripción (sin previsualizar el video). La versión
mínima útil es: transcripción + marcadores arrastrables + selector de sonido
+ exportar JSON.

---

## Nota de secuencia

Los puntos **1 y 2** son los de mayor impacto por esfuerzo: el material ya
existe (banco de hooks escrito, 13 SFX descargados) y solo falta conectarlo.
Conviene hacerlos primero y volver a revisar el video antes de meterse con
los puntos 5 y 6, que son desarrollo nuevo.

El punto **3b** (usar el face tracking para posicionar overlays) es
probablemente el cambio más elegante de toda la lista: el dato ya se calcula
en cada corrida y hoy se descarta.


---

## 📌 BLOQUES DE LA TIRA VISUAL (PENDIENTES PARA PRÓXIMA ETAPA)

1. **Tira de capas apiladas en la interfaz (`f11_servidor.py`)**:
   - Visualización multi-pista (Voz, Subtítulos, B-Roll/Overlays, Animaciones GSAP, SFX/Música).
2. **Ver y deshacer el corte de silencios**:
   - Inspeccionar los tramos recortados por `f2_cortar.py` y restaurar o ajustar silencios desde la línea de tiempo.
3. **Arrastrar en la tira con imán (snapping) y zoom**:
   - Control de escala de tiempo con zoom y ajuste magnético de marcas hacia bordes de palabras o beats de guion.
