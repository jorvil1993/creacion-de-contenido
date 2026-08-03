# Plan — pipeline de artes (flyers para redes)

Hermano del pipeline de video. Convierte un producto + un ángulo de venta en un
arte cuadrado publicable, con el copy del post ya escrito. Todo local.

Decidido con José el 2026-08-01. **Lo que está acá ya se preguntó — no repreguntar.**

## Lo que se decidió

| Tema | Decisión |
|---|---|
| Dónde vive el panel | `PANEL-ARTES.html` — archivo aparte, no una pestaña de `PANEL-PRODUCCION.html` |
| Formato | **1080×1080 por defecto**, con toggle a 1080×1920 por fila. Nunca renderiza los dos a la vez |
| Fondo/producto | Se elige **por fila** desde el panel: foto real, foto editada con IA, o generado |
| IA de imagen | ComfyUI local. **Qwen-Image-Edit-2511** para editar fotos reales; Flux queda para generar desde cero |
| Fotos de Amazon | Banco local en `contexto/fotos amazon/`. La IA las reencuadra/recompone; no se publican tal cual |
| Prompt de IA | El panel muestra el prompt + un botón que **abre la carpeta** con la imagen a subir |
| Texto roto en pantallas | Se deja como está (decisión de José) |
| Palancas de venta | Prueba social · garantía y envío · urgencia **solo por fecha**, nunca por stock inventado |
| Copy | **3 variantes** por arte (emocional / racional / oferta), cada una con su botón de copiar |

## Datos reales del negocio (NO inventar cifras nuevas)

Fuente: `deviceshop/DOCUMENTOS MD DE LA EMPRESA/`. Todo lo de abajo está documentado.

- **6 años** vendiendo (confirmado por José, 2026-08-01).
- **Garantía: 1 mes.** No decir "garantía" a secas — decir el plazo.
- Nuevo, **en caja sellada**, **stock propio importado → entrega inmediata** (sin esperar importación).
  Es el diferenciador central.
- 100% virtual, sin tienda física. Base en **Santa Cruz**, envíos a todo el país.
- Pago: **QR contra entrega** en Santa Cruz; **contra-entrega** en La Paz y Cochabamba.
- WhatsApp **692-14437** — todo camino termina ahí. CTA siempre "escribinos", nunca "comprá ya".
- Ventas históricas por ciudad: Santa Cruz ≈1.875 · La Paz ≈1.489 · Cochabamba ≈587.
  ⚠️ Sumarlas para un "+3.900 clientes" **necesita que José lo confirme** antes de publicarse.

### Qué funciona (datos de Meta Ads, no corazonadas)

- Mejor anuncio histórico: *"Buscas un excelente regalo a un precio muy económico?"* —
  **CTR 6,89%**, costo por conversación **$0,10**.
- Patrón ganador: **pregunta directa + ángulo regalo + CTA a conversar**.
- Audiencia que responde: **mujeres 45–54, después 35–44 y 55–64**, Santa Cruz y Cochabamba.
  Más madura que el estereotipo juvenil de e-readers.
- **Diciembre es el mes rey** (regalo navideño), después enero y marzo.
- Producto caballo de batalla: **Kindle Paperwhite**.
- Objeción #1: *"con mi tablet leo igual"*.
- La Paz vende mucho pero engancha poco en ads → oportunidad de creatividad propia.

## Identidad visual (medida del píxel de los 36 artes reales)

- Turquesa `#00C7CA` · navy `#011A2E` · blanco `#FFFFFF`.
  ⚠️ `voz-de-marca.md` dice `#0A2A3E`/`#4FD1D9` — **manda el valor medido**, ese doc fue a ojo.
- Fuentes: Poppins y Montserrat (`assets/fuentes/`), títulos en mayúsculas.
- Logo navy vectorial: `contexto/LOGOS IVAN/.../deviceshop color.png` (2000×848) y el `.ai`.
  Mejor fuente que el blanco de `assets/logo/`.
- **Fijo en 36/36 artes:** logo en píldora turquesa abajo-izquierda + CTA WhatsApp abajo-derecha.
  Eso no se toca nunca.

### Los 9 arquetipos de layout que José ya usa

1. Hook + producto en escena (el más común)
2. Specs laterales en panel turquesa con íconos
3. Comparativa 2 columnas (split vertical)
4. Comparativa 3 productos en fila
5. Callouts flotantes de vidrio esmerilado sobre el producto
6. Infografía vertical de specs
7. Estacional (Navidad · Día del Padre · Mes del Niño · vuelta a clases · Año Nuevo)
8. Sello de oferta (medallón dorado)
9. Metáfora conceptual (balanza kindle-vs-libros, báscula 0.15kg, libros volando)

## Por qué Qwen-Image-Edit y no otro

Verificado contra ComfyUI oficial y la tarjeta del modelo en Hugging Face (2026-08-01),
no contra blogs:

- **Apache 2.0** → uso comercial libre. FLUX.1 Kontext, su rival directo, es **no comercial**:
  descartado porque DeviceShop vende.
- **FP8 ≈16 GB VRAM** → entra justo en la RTX 5070 Ti de José (16 GB).
- Preserva la identidad del objeto al cambiarle el entorno — que es exactamente el encargo:
  "agarrá este Kindle real y ponelo en otra escena".
- Edita texto dentro de la imagen → sirve para quitar el *"20% faster"* en inglés que traen
  las fotos de Amazon.
- Acepta hasta 3 imágenes de referencia (producto + escena + estilo).

Flux no se tira: genera fondos y escenas desde cero. Está documentado que **no sabe cómo es
un Kindle real** (`assets/generado/kindle-paperwhite/README.md`), así que el producto siempre
sale de foto real.

## Recorte de fondo

`rembg` + `onnxruntime` ya están instalados en `C:\ai-video\venv312` (vinieron con el pipeline
de video). Recortan el producto de cualquier foto de Amazon para recomponerlo en otro entorno.

## Hallazgos de la auditoría de los 36 artes

Cosas a no repetir en los artes nuevos:

1. **Texto inventado dentro de las pantallas.** "Sstaban tomando el aperitivo", "la chira de
   servicio", "el ragaio dhe su yerno Lorenso". Ampliado se lee como error.
   Ver `contexto/EJEMPLO-texto-pantalla.png`. José decidió no priorizarlo.
2. **"KINDLE KINDLE SCRIBE 16GB"** — palabra duplicada, publicado.
3. **Cero precio y cero prueba social en los 36**, teniendo 6 años y miles de ventas.
