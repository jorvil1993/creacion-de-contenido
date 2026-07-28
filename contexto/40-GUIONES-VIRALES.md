# 40 guiones virales — DeviceShop Bolivia

> 🎬 **Para grabar, no uses este archivo: abre `PANEL-PRODUCCION.html`** (doble
> clic, en la raíz del proyecto). Ahí están los 10 de RUM más alto convertidos en
> **guiones de producción**: qué grabar toma por toma, teleprompter listo para
> copiar, y la línea de tiempo con el material, los efectos de sonido y la música
> ya decididos. Este archivo es el **banco de ideas** con los 40 ángulos.

Construidos con la fórmula **RUM = U × I × C × S × D × A** del curso
(`ESTRATEGIA-VIRAL-2026.md`) y calibrados con la data real de ventas.

**Cómo leer cada guion**

- `RUM` — puntuación 1-10 por variable y el % resultante. Todos los de este banco
  están por encima de 60%.
- `[F01]`…`[F30]` — clip de **ambiente** del banco de Google Flow (gente, objetos,
  metáforas). Se generan con texto.
- `[P01]`…`[P11]` — clip de **producto**: tu Kindle o Kobo real, animado desde una
  foto tuya. `[P02]`, por ejemplo, es el Paperwhite 16GB en la mano, con la
  pantalla en blanco y negro; `[P09]` es la Kobo Libra Colour con pantalla a color.
- **Los dos códigos son nombres de archivo**, no hay que generar nada por guion:
  el mismo `[P02]` se reutiliza en 12 guiones. La tabla completa con la foto de
  partida y el prompt de cada uno está en `PROMPTS-GOOGLE-FLOW.md`.
- `📌 PIP` — inserto en imagen sobre el hablante. `🎬 B-roll` — cubre la pantalla
  completa. `✨ Anim` — animación de marca (la hace el pipeline, no Flow).

> ⚠️ **La pantalla va según el modelo.** Blanco y negro en Kindle Basic,
> Paperwhite y Kids (`P01`-`P07`). A color solo en Kindle Colorsoft (`P08`) y
> Kobo Colour (`P09`, `P10`). Si un guion habla de color, el clip tiene que ser
> uno de esos tres.

**Reglas que cumplen los 40** (ver estrategia): hook ≤7 palabras · la palabra
"Kindle" nunca en los primeros 8s · una idea por video · cero specs · 30-40s ·
CTA a conversación · cierre que empata con el arranque.

**Grabación:** todo se graba hablando a cámara y entra al pipeline
(`editor.py`). Los clips de Flow son el material de apoyo, no el video entero.

> ⚠️ **Verificado en el código, no supuesto:** hoy el pipeline solo inserta
> **tarjetas PiP pequeñas** en la franja superior (`OVERLAY_BANDA_SUPERIOR_PCT`,
> 10-35% del alto) — el "🎬 B-roll a pantalla completa" de esta tabla **no es una
> capacidad que exista todavía**. Tampoco hay reemplazo automático para video: la
> única función de manual override real (`version_manual()` en `f9_generar.py`)
> es para imagen fija. Conectar los clips de Flow al render final es trabajo de
> código nuevo, pendiente hasta que se pida — hoy el flujo es 100% externo, como
> se pidió desde el inicio.

---

## BLOQUE A — Sueño y vista (RUM más alto del banco)

Universalidad máxima: cualquiera con un celular. Intensidad alta: salud.
**Empezar la cuenta por aquí.**

---

### 1 · El celular te está robando el sueño

**Hook:** `Por eso no puedes dormir de noche`
**RUM:** U9 · I9 · C10 · S9 · D9 · A8 → **89%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Por eso no puedes dormir de noche." | 🎬 `[F01]` cara en la oscuridad iluminada por el celular |
| 3-12s | "Te acuestas cansado, agarras el celular 'un ratito'… y a la hora sigues despierto con los ojos ardiendo." | 🎬 `[F03]` dando vueltas en la cama, reloj 3:47 |
| 12-20s | "No es que tengas insomnio. Es que esa pantalla te está tirando luz directo a los ojos, y tu cerebro cree que es de día." | 📌 `[F02]` primer plano de ojos cansados |
| 20-30s | "Hay pantallas que no emiten luz: la reflejan, como el papel. Por eso los que leen en estas se duermen leyendo, en vez de desvelarse." | 📌 `[P01]` producto en cama, luz cálida |
| 30-36s | "Si quieres que te explique cuál te conviene, escríbeme. Y deja de dormir con el celular en la cara." | ✨ CTA + loop al hook |

> 💡 **Share:** todo el mundo tiene a alguien que se duerme con el celular en la mano.

---

### 2 · Los ojos rojos de las 11 de la noche

**Hook:** `¿Te arden los ojos al leer?`
**RUM:** U9 · I8 · C10 · S8 · D8 · A8 → **79%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "¿Te arden los ojos al leer?" | 📌 `[F02]` ojos frotándose |
| 3-12s | "No es tu vista. Es que estás mirando una linterna a 20 centímetros de la cara, por horas." | 🎬 `[F01]` resplandor azulado en la oscuridad |
| 12-22s | "Un estudio comparó a gente leyendo en pantalla brillante y en tinta electrónica: los de la pantalla brillante parpadeaban más y terminaban más cansados." | ✨ Anim comparativa (plantilla del pipeline) |
| 22-32s | "La diferencia no es la letra. Es de dónde viene la luz: si te la tira a los ojos o si rebota, como en una hoja." | 📌 `[P02]` producto en la mano |
| 32-38s | "¿Quieres saber cuál descansa más la vista? Escríbeme." | ✨ CTA + loop |

---

### 3 · Lo que le pasa a tu vista sin que te des cuenta

**Hook:** `Tu vista se cansa y no lo notas`
**RUM:** U9 · I8 · C9 · S8 · D8 · A8 → **75%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Tu vista se cansa y no lo notas." | 📌 `[F02]` |
| 3-13s | "No duele. Solo te da sueño más rápido, te cuesta concentrarte y culpas al libro de aburrido." | 🎬 `[F16]` libro abandonado con separador en la página 30 |
| 13-24s | "El problema no era el libro. Era la pantalla que te obliga a forzar los ojos sin que lo sientas." | 🎬 `[F14]` pulgar deslizando sin fin |
| 24-34s | "Cuando la pantalla se ve como papel, el cansancio no aparece. Y de repente terminas el libro." | 📌 `[P01]` |
| 34-38s | "Escríbeme y te digo cuál va con tu forma de leer." | ✨ CTA + loop |

---

### 4 · Leer al sol: la prueba que nadie te muestra

**Hook:** `Mira lo que pasa a pleno sol`
**RUM:** U8 · I7 · C10 · S9 · D9 · A8 → **77%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Mira lo que pasa a pleno sol." | 🎬 `[F04]` sol fuerte, reflejo cegador |
| 3-12s | "Sacas el celular afuera y ves tu propia cara reflejada. Subes el brillo al máximo y sigue sin verse." | 📌 `[F04]` mano tapando el reflejo |
| 12-24s | "Ahora mira esto: mientras más sol le da, mejor se ve. Porque no genera luz, la aprovecha." | 📌 `[P03]` producto al sol (foto real animada) |
| 24-34s | "Por eso la gente lee en la playa, en la piscina, en el patio. Sin buscar sombra." | 🎬 `[F28]` piscina / verano |
| 34-38s | "Si lees afuera, escríbeme. Esto te cambia el verano." | ✨ CTA + loop |

> 💡 Formato **comparación lado a lado**: de los que mejor rinden en 2026.

---

### 5 · Duerme leyendo, no scrolleando

**Hook:** `Cambia esto y vas a dormir mejor`
**RUM:** U9 · I8 · C9 · S8 · D8 · A8 → **75%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Cambia esto y vas a dormir mejor." | 🎬 `[F05]` cama con luz cálida |
| 3-14s | "El problema de la última media hora del día no es que no tengas sueño. Es lo que estás mirando." | 🎬 `[F17]` enjambre de notificaciones |
| 14-25s | "Un video te lleva a otro. Un mensaje te acelera. Y cuando cierras el celular, tu cabeza sigue corriendo." | 🎬 `[F14]` |
| 25-35s | "Cambia esa media hora por algo que no te tire luz ni te notifique nada. Vas a caer dormido a las 3 páginas." | 📌 `[P01]` |
| 35-40s | "Te digo cuál sirve para leer de noche sin molestar a nadie. Escríbeme." | ✨ CTA + loop |

---

### 6 · La luz de noche que no despierta a nadie

**Hook:** `Leer de noche sin despertar a nadie`
**RUM:** U8 · I7 · C9 · S9 · D8 · A9 → **73%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Leer de noche sin despertar a nadie." | 🎬 `[F21]` pareja en cama, uno dormido |
| 3-13s | "Si tu pareja se duerme antes que tú, ya sabes el problema: prendes la lámpara y lo despiertas." | 🎬 `[F29]` lámpara de mesa encendiéndose |
| 13-24s | "Y si usas el celular, la luz te da a ti, en la cara, en la oscuridad. Lo peor de los dos mundos." | 🎬 `[F01]` |
| 24-34s | "Existe una luz cálida, tenue, que ilumina solo la hoja. Ni molesta al lado ni te encandila a ti." | 📌 `[P04]` producto con luz cálida en oscuridad |
| 34-38s | "Escríbeme y te muestro cuáles la tienen." | ✨ CTA + loop |

---

## BLOQUE B — Atención y celular

El dolor más universal de 2026. Ninguno menciona el producto antes del segundo 15.

---

### 7 · No es que no te guste leer

**Hook:** `No es que no te guste leer`
**RUM:** U10 · I8 · C10 · S10 · D9 · A8 → **90%** ⭐ *el más alto del banco*

| t | Habla | Visual |
|---|---|---|
| 0-3s | "No es que no te guste leer." | 🎬 `[F16]` libro abandonado, polvo |
| 3-14s | "Es que compites contra una app diseñada por mil ingenieros para que no puedas soltarla." | 🎬 `[F14]` scroll infinito |
| 14-24s | "No es falta de disciplina. Es una pelea injusta. Tú con tu fuerza de voluntad contra un algoritmo." | 🎬 `[F33]` se rinde: suelta el libro por el celular |
| 24-34s | "La única forma de ganarla es no pelearla: leer en algo que no tenga apps, ni notificaciones, ni nada más que la página." | 📌 `[P02]` |
| 34-40s | "Si te pasa, mándale esto a alguien que también dejó un libro a medias." | ✨ CTA + loop |

> 💡 **Share máximo:** absuelve al espectador de la culpa. Ese es el mecanismo.

---

### 8 · Cuántos libros dejaste en la página 30

**Hook:** `¿Cuántos libros dejaste a medias?`
**RUM:** U9 · I7 · C10 · S10 · D9 · A8 → **82%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "¿Cuántos libros dejaste a medias?" | 🎬 `[F16]` |
| 3-13s | "Todos tenemos ese libro con el separador clavado en la página 30 desde hace dos años." | 🎬 `[F08]` pila de libros |
| 13-24s | "Y cada vez que lo ves, te sientes un poco mal. Pero no lo abres, porque abrirlo cuesta más que abrir el celular." | 🎬 `[F14]` |
| 24-34s | "Lo que cambia el juego es que agarrar la lectura cueste menos que agarrar el celular. Ahí sí se termina." | 📌 `[P01]` |
| 34-38s | "Comenta en qué página quedó el tuyo 👇" | ✨ CTA comentarios + loop |

> 💡 CTA a **comentario**, no a WhatsApp: dispara interacción temprana (crítica en la primera hora).

---

### 9 · La hora que pierdes sin darte cuenta

**Hook:** `Pierdes una hora al día así`
**RUM:** U10 · I8 · C9 · S9 · D9 · A7 → **81%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Pierdes una hora al día así." | 🎬 `[F14]` |
| 3-14s | "Entras a ver una cosa. Sales 40 minutos después sin acordarte a qué entraste." | 🎬 `[F15]` reloj / arena cayendo |
| 14-26s | "En un año son 15 días completos. Despierto. Deslizando." | ✨ Anim número grande "15 días" |
| 26-36s | "Con esa misma hora al día se leen 30 libros al año. Es exactamente el mismo tiempo, en otra pantalla." | 🎬 `[F09]` biblioteca |
| 36-40s | "¿Qué harías tú con esos 15 días?" | ✨ CTA comentarios + loop |

---

### 10 · Un aparato con pantalla que no te notifica nada

**Hook:** `Tiene pantalla y no te notifica nada`
**RUM:** U8 · I7 · C9 · S8 · D8 · A9 → **70%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Tiene pantalla y no te notifica nada." | 📌 `[P02]` |
| 3-13s | "Suena raro en 2026, ¿no? Una pantalla que no te interrumpe nunca." | 🎬 `[F17]` |
| 13-24s | "No entra WhatsApp. No entra Instagram. No hay juegos. Literalmente no se puede hacer otra cosa que leer." | ✨ Anim íconos apagándose |
| 24-34s | "Y ese 'defecto' es justo lo que hace que termines los libros." | 📌 `[P01]` |
| 34-38s | "Escríbeme si quieres una pantalla que te deje en paz." | ✨ CTA + loop |

---

### 11 · POV: te dormiste con el celular en la cara

**Hook:** `POV: se te cayó el celular en la cara`
**RUM:** U10 · I6 · C10 · S10 · D9 · A6 → **78%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "POV: se te cayó el celular en la cara." | 🎬 `[F01]` |
| 3-12s | "Otra vez. A las dos de la mañana. Y encima te despertó." | 🎬 `[F03]` |
| 12-22s | "Todos hemos estado ahí. El celular pesa, brilla, y se te resbala justo cuando te estás durmiendo." | 📌 `[F02]` |
| 22-32s | "Lo que uso yo pesa como medio celular, no brilla, y si se me cae no me deja marca en la frente." | 📌 `[P05]` producto liviano en la mano |
| 32-38s | "Etiqueta a alguien a quien se le cayó el celular en la cara 😂" | ✨ CTA etiquetar + loop |

> 💡 **Distribución indirecta (D) pura:** se etiqueta gente que nunca compraría, y ellos traen al comprador.

---

### 12 · Deja de leer en la tablet

**Hook:** `Tu tablet no sirve para leer`
**RUM:** U8 · I7 · C9 · S8 · D8 · A9 → **70%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Tu tablet no sirve para leer." | 🎬 comparativa (plantilla) |
| 3-14s | "Sirve para ver videos, para YouTube, para todo. Pero para leer 300 páginas seguidas, no." | 🎬 `[F14]` |
| 14-25s | "Pesa, se calienta, te dura 4 horas, te llegan notificaciones y al sol no ves nada." | ✨ Anim 4 íconos (pesa/calor/batería/sol) |
| 25-35s | "Es como usar una camioneta para ir a la esquina. Funciona, pero no es lo que necesitas." | 📌 `[P02]` |
| 35-40s | "Escríbeme y te comparo sin venderte nada." | ✨ CTA + loop |

---

## BLOQUE C — Regalo (tu ganador comprobado)

Tu mejor anuncio histórico fue de regalo. Cargar estos hacia **noviembre-diciembre**,
Día de la Madre, Día del Padre y cumpleaños.

---

### 13 · El error al regalarle un libro a quien ama leer

**Hook:** `Error al regalar libros a un lector`
**RUM:** U9 · I7 · C9 · S10 · D10 · A9 → **86%** ⭐

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Error al regalar libros a un lector." | 🎬 `[F13]` caja de regalo con moño |
| 3-14s | "Le regalas un libro… y resulta que ya lo leyó. O no era su género. O ya lo tenía." | 🎬 `[F08]` |
| 14-25s | "El que lee mucho es el más difícil de acertar, justamente porque lee mucho." | 🎬 `[F30]` manos vacías en una tienda |
| 25-35s | "Por eso lo que nunca falla no es un libro: es lo que le deja elegir cualquiera, cuando quiera." | 📌 `[P06]` producto con moño |
| 35-40s | "Mándale esto a quien te va a regalar algo 😏" | ✨ CTA + loop |

> 💡 **D altísimo:** lo comparte quien NO compra (el que quiere que le regalen).

---

### 14 · El regalo que sí van a usar

**Hook:** `Ese regalo va a quedar guardado`
**RUM:** U9 · I7 · C10 · S9 · D9 · A9 → **83%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Ese regalo va a quedar guardado." | 🎬 `[F30]` |
| 3-13s | "El perfume que no usa. La taza número 12. El adorno que va al cajón." | ✨ Anim 3 objetos apareciendo y cayendo |
| 13-24s | "Regalar bien no es gastar más. Es acertar en algo que use todos los días." | 🎬 `[F13]` |
| 24-34s | "Si la persona lee, o tú quieres que lea, esto lo va a agarrar todas las noches. No una vez." | 📌 `[P06]` |
| 34-40s | "Escríbeme y te ayudo a elegir según la persona." | ✨ CTA + loop |

---

### 15 · Le regalé uno a mi mamá y ahora lee más que yo

**Hook:** `Le regalé uno a mi mamá`
**RUM:** U9 · I7 · C9 · S9 · D9 · A9 → **80%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Le regalé uno a mi mamá." | 🎬 `[F20]` mujer 50s leyendo en sillón |
| 3-14s | "Ella decía que ya no veía bien de cerca y que los libros le cansaban la vista." | 📌 `[F02]` |
| 14-25s | "Lo primero que hizo fue agrandar la letra al tamaño que ella quiso. Nadie le tuvo que explicar nada." | ✨ Anim letra creciendo |
| 25-35s | "Hoy lee más que yo. Y me manda fotos de en qué página va." | 🎬 `[F20]` |
| 35-40s | "Si tu mamá dejó de leer por la vista, escríbeme." | ✨ CTA + loop |

> 💡 Habla directo a tu **Persona 1**, la lectora regalona (mujer 35-60), que es quien más responde.

---

### 16 · Miles de libros en una sola caja

**Hook:** `Le regalas mil libros en una caja`
**RUM:** U9 · I6 · C10 · S9 · D9 · A9 → **79%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Le regalas mil libros en una caja." | 🎬 `[F25]` caja sellada abriéndose |
| 3-13s | "No es exageración. En lo que pesa menos que un cuaderno entran más libros de los que va a leer en su vida." | 🎬 `[F09]` biblioteca infinita |
| 13-24s | "Y muchos de esos libros son gratis. Clásicos, dominio público, la biblioteca entera." | ✨ Anim "gratis" |
| 24-34s | "Por eso el regalo no se acaba el día que lo abre. Empieza ahí." | 📌 `[P06]` |
| 34-40s | "Escríbeme y lo dejamos listo para regalar." | ✨ CTA + loop |

---

### 17 · Lo que pide todo el mundo en diciembre

**Hook:** `Esto se agota todos los diciembres`
**RUM:** U8 · I7 · C9 · S8 · D8 · A10 → **72%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Esto se agota todos los diciembres." | 🎬 `[F25]` |
| 3-13s | "Todos los años pasa lo mismo: en diciembre me escriben 20 personas por el mismo modelo y ya no queda." | 🎬 `[F24]` moto de entrega en la ciudad |
| 13-24s | "No es marketing, es que se importa con meses de anticipación y el que se duerme, se queda." | 🎬 `[P11]` tus cajas selladas reales |
| 24-34s | "Si ya sabes a quién le vas a regalar, no esperes a diciembre para preguntar." | 📌 `[P06]` |
| 34-38s | "Escríbeme y te aviso qué hay ahora." | ✨ CTA + loop |

> ⚠️ Solo publicar si **de verdad** hay poco stock. La urgencia falsa quema la marca.

---

## BLOQUE D — Hijos y pantallas

Intensidad emocional altísima en padres. Gran shareability entre parejas.

---

### 18 · Tu hijo no lee porque compite contra esto

**Hook:** `Tu hijo no lee por esta razón`
**RUM:** U9 · I9 · C9 · S10 · D9 · A8 → **88%** ⭐

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Tu hijo no lee por esta razón." | 🎬 `[F18]` niño frente a pantalla en la oscuridad |
| 3-14s | "No es que sea flojo ni que 'los chicos de ahora no leen'. Es que el libro compite contra algo diseñado para ser irresistible." | 🎬 `[F14]` |
| 14-25s | "Tú de chico competías contra la tele, que se acababa. Esto no se acaba nunca." | ✨ Anim scroll infinito |
| 25-35s | "Lo que funciona no es quitarle la pantalla. Es darle una pantalla que solo tenga libros adentro." | 🎬 `[F19]` niño leyendo |
| 35-40s | "Mándale esto a la mamá o papá que dice que su hijo no lee." | ✨ CTA + loop |

---

### 19 · La pantalla que sí le doy a mi hijo

**Hook:** `Esta pantalla sí se la doy`
**RUM:** U9 · I8 · C9 · S9 · D9 · A9 → **84%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Esta pantalla sí se la doy." | 🎬 `[F19]` |
| 3-14s | "Le quito el celular a las 8 y empieza la pelea de todas las noches. Ya la conoces." | 🎬 `[F18]` |
| 14-25s | "Pero cuando le doy esto no hay pelea, porque no siente que le estoy quitando algo. Le estoy dando otra cosa." | 🎬 `[F19]` |
| 25-35s | "No tiene juegos, no tiene YouTube, no tiene internet para otra cosa. Y no le tira luz a los ojos antes de dormir." | 📌 `[P07]` |
| 35-40s | "Si peleas por las pantallas en tu casa, escríbeme." | ✨ CTA + loop |

---

### 20 · Lo que ven tus hijos a las 11 de la noche

**Hook:** `Mira qué hace tu hijo a las 11`
**RUM:** U9 · I9 · C9 · S9 · D8 · A7 → **80%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Mira qué hace tu hijo a las 11." | 🎬 `[F18]` |
| 3-14s | "Cuarto oscuro, cara azul, ojos abiertos. Y mañana hay colegio a las 7." | 🎬 `[F03]` |
| 14-25s | "No es que no quiera dormir. Esa luz le está diciendo al cerebro que todavía es de día." | 📌 `[F02]` |
| 25-35s | "Cambiar esa pantalla por una que no emite luz propia es de las cosas más fáciles que puedes hacer por su sueño." | 📌 `[P07]` |
| 35-40s | "Mándale esto a alguien que tenga adolescentes." | ✨ CTA + loop |

---

### 21 · Cómo lograr que un niño pida leer

**Hook:** `Así logré que pida leer solo`
**RUM:** U8 · I8 · C9 · S9 · D8 · A8 → **75%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Así logré que pida leer solo." | 🎬 `[F19]` |
| 3-14s | "Obligarlo no funcionó nunca. Premiarlo tampoco: leía 10 minutos mirando el reloj." | 🎬 `[F22]` mochila pesada de libros |
| 14-26s | "Lo que funcionó fue dejarlo elegir. Cualquier libro, el que él quiera, sin que yo opine." | 🎬 `[F09]` |
| 26-36s | "Cuando tienes miles para elegir en un solo aparato, la elección es de él. Y ahí empieza a leer por gusto." | 📌 `[P07]` |
| 36-40s | "Escríbeme si quieres el que hicimos para niños." | ✨ CTA + loop |

---

## BLOQUE E — Hábito, tiempo y culpa

---

### 22 · Terminar un libro no depende de disciplina

**Hook:** `Terminar libros no es disciplina`
**RUM:** U9 · I7 · C9 · S9 · D9 · A7 → **77%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Terminar libros no es disciplina." | 🎬 `[F16]` |
| 3-14s | "Es fricción. Cuánto te cuesta empezar. El libro está en la otra pieza, pesa, y hay que buscar luz." | 🎬 `[F08]` |
| 14-25s | "El celular está en tu mano, prendido, y ya sabe qué mostrarte. Gana por comodidad, no por interés." | 🎬 `[F14]` |
| 25-35s | "Baja la fricción del libro al mismo nivel y el hábito aparece solo. Sin fuerza de voluntad." | 📌 `[P01]` |
| 35-40s | "Guarda esto para cuando quieras retomar." | ✨ CTA guardar + loop |

> 💡 CTA a **guardar**: los saves también empujan el alcance.

---

### 23 · Los 20 minutos muertos del día

**Hook:** `Estos 20 minutos son 12 libros`
**RUM:** U9 · I7 · C9 · S9 · D9 · A7 → **77%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Estos 20 minutos son 12 libros." | 🎬 `[F15]` |
| 3-14s | "La fila del banco. La sala de espera. Los 20 minutos antes de que llegue tu comida." | 🎬 `[F06]` café mientras espera |
| 14-25s | "Ahí sacas el celular por inercia. No porque quieras: porque está." | 🎬 `[F14]` |
| 25-35s | "Esos ratos sueltos, en un año, son 12 libros. Solo cambia lo que sacas del bolsillo." | 🎬 `[F09]` |
| 35-40s | "Escríbeme cuál entra en tu cartera o bolsillo." | ✨ CTA + loop |

---

### 24 · La biblioteca que cabe en la mano

**Hook:** `Toda tu biblioteca en una mano`
**RUM:** U8 · I6 · C10 · S8 · D8 · A9 → **69%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Toda tu biblioteca en una mano." | 🎬 `[F09]` |
| 3-14s | "Si tienes libros, ya sabes el problema: se acumulan, ocupan, se humedecen, y cuando te mudas son 8 cajas." | 🎬 `[F08]` |
| 14-25s | "Y aún así nunca encuentras el que buscas." | 🎬 `[F09]` |
| 25-35s | "Todo eso, en algo que pesa menos que un libro de bolsillo y busca cualquier frase en 2 segundos." | 📌 `[P05]` |
| 35-40s | "Escríbeme si ya no te entran más libros en casa." | ✨ CTA + loop |

---

### 25 · Viajar sin cargar libros

**Hook:** `No cargues libros en la maleta`
**RUM:** U8 · I6 · C10 · S8 · D8 · A9 → **69%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "No cargues libros en la maleta." | 🎬 `[F07]` maleta / avión |
| 3-14s | "Eliges dos, pesan dos kilos, y terminas uno y medio. O peor: te aburre y te quedaste sin nada." | 🎬 `[F08]` |
| 14-25s | "Y si el vuelo se atrasa 4 horas, adivinaste: celular hasta que se muere la batería." | 🎬 `[F23]` celular al 1% |
| 25-36s | "Con esto llevas 500 y la batería te dura todo el viaje. Semanas, no horas." | 📌 `[P05]` |
| 36-40s | "Escríbeme antes de tu próximo viaje." | ✨ CTA + loop |

---

### 26 · La batería que dura semanas

**Hook:** `Lo cargué hace 3 semanas`
**RUM:** U8 · I7 · C10 · S8 · D8 · A9 → **72%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Lo cargué hace 3 semanas." | 📌 `[P05]` |
| 3-13s | "Tu celular lo cargas dos veces al día. Tu reloj, cada dos días. Los audífonos, cada rato." | 🎬 `[F23]` |
| 13-24s | "Todo lo que tienes encima te pide cargador. Estás administrando batería todo el día." | ✨ Anim íconos de batería bajando |
| 24-34s | "Esto gasta solo cuando pasas la página. Por eso dura semanas y te olvidas de que existe el cargador." | 📌 `[P02]` |
| 34-38s | "Escríbeme y te cuento cuánto dura el que te sirve." | ✨ CTA + loop |

---

## BLOQUE F — Comparaciones visuales

Formato de altísimo rendimiento en 2026. **El video hace el trabajo, no la
explicación.** Graba la comparación real siempre que puedas.

---

### 27 · Celular vs. esto, al sol

**Hook:** `Los saqué al sol. Mira.`
**RUM:** U9 · I7 · C10 · S9 · D9 · A8 → **82%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Los saqué al sol. Mira." | 🎬 **grabación real** lado a lado |
| 3-14s | "Mismo sol, misma hora. En uno ves tu cara. En el otro ves la página." | 🎬 `[F04]` |
| 14-25s | "Y no es el brillo: sube el celular al máximo y sigue igual." | 🎬 grabación real |
| 25-35s | "Uno tira luz hacia ti. El otro deja que el sol le pegue, como a una hoja." | 📌 `[P03]` |
| 35-40s | "Escríbeme si lees afuera." | ✨ CTA + loop |

---

### 28 · Lo metí al agua

**Hook:** `Lo metí al agua. A propósito.`
**RUM:** U9 · I6 · C10 · S10 · D10 · A8 → **86%** ⭐

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Lo metí al agua. A propósito." | 🎬 `[F11]` gotas salpicando |
| 3-13s | "Todos hemos tenido el susto: el celular al borde de la tina, de la piscina, del lavaplatos." | 🎬 `[F12]` bañera con espuma |
| 13-24s | "Este se puede mojar. Se cae a la piscina, lo sacas, lo secas y sigue." | 🎬 **grabación real** con agua |
| 24-34s | "Por eso se lee en la tina, en la playa, bajo la lluvia. Sin cuidarlo como un huevo." | 🎬 `[F28]` |
| 34-40s | "Etiqueta a quien lee en la tina 🛁" | ✨ CTA etiquetar + loop |

> 💡 **S y D al tope:** el "wait for it" del agua es lo más compartible del banco.

---

### 29 · El peso, en la mano

**Hook:** `Pesa menos que tu celular`
**RUM:** U8 · I6 · C10 · S8 · D8 · A9 → **69%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Pesa menos que tu celular." | 📌 `[P05]` |
| 3-14s | "Si alguna vez leíste acostado y se te durmió la mano, sabes de qué hablo." | 🎬 `[F05]` |
| 14-25s | "Un libro de tapa dura son 600 gramos. Tu celular, 200. Esto, menos." | ✨ Anim balanza comparando |
| 25-35s | "Se sostiene con una mano toda la noche y no te cansa el brazo." | 📌 `[P05]` |
| 35-40s | "Escríbeme cuál es el más liviano." | ✨ CTA + loop |

---

### 30 · Color vs. blanco y negro: cuál te sirve

**Hook:** `¿A color o blanco y negro?`
**RUM:** U7 · I6 · C9 · S8 · D7 · A10 → **64%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "¿A color o blanco y negro?" | 🎬 comparativa (plantilla) |
| 3-14s | "Todo el mundo quiere el color. Y a la mitad de la gente no le sirve para nada." | 📌 `[P08]` Kindle a color |
| 14-26s | "Si lees novelas, texto puro, el blanco y negro se ve mejor y cuesta menos. Punto." | 📌 `[P02]` pantalla B/N |
| 26-36s | "El color vale la pena si lees cómics, revistas, manga o resaltas apuntes de colores." | 📌 `[P09]` Kobo Libra, resaltados a color |
| 36-40s | "Dime qué lees y te digo cuál. Sin venderte el más caro." | ✨ CTA + loop |

> 💡 El **color es 35% de tu ingreso**. Este guion también filtra y evita devoluciones.

---

### 31 · Antes y después de un año leyendo

**Hook:** `Un año después de dejar el celular`
**RUM:** U8 · I7 · C9 · S9 · D8 · A7 → **72%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Un año después de dejar el celular." | 🎬 `[F14]` |
| 3-14s | "Antes: 4 libros al año, si me iba bien. Y 5 horas de pantalla al día." | ✨ Anim números "4" y "5h" |
| 14-26s | "Después: 31 libros. No porque me volví disciplinado, sino porque cambié de pantalla en la mesa de noche." | ✨ Anim número "31" |
| 26-36s | "Lo único que hice fue poner lo que quería hacer más cerca que lo que quería hacer menos." | 📌 `[P01]` |
| 36-40s | "Guarda esto y prueba un mes." | ✨ CTA guardar + loop |

---

## BLOQUE G — Rompe-creencias ("soy X y por supuesto no…")

Formato citado explícitamente en el curso: rompe la expectativa social y dispara
comentarios. **Es el que más autoridad construye.**

---

### 32 · Vendo estos y no te vendo el más caro

**Hook:** `Vendo estos y no te vendo el caro`
**RUM:** U8 · I7 · C9 · S9 · D9 · A10 → **81%** ⭐

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Vendo estos y no te vendo el caro." | 📌 `[P02]` |
| 3-14s | "Me escriben pidiendo el más caro y les digo que no. Que con ese no van a leer más." | 🎬 `[F30]` |
| 14-26s | "Si vas a leer novelas en la cama, el de arriba no te da nada que el de abajo no te dé. Estás pagando por lo que no vas a usar." | ✨ Anim comparativa |
| 26-36s | "Prefiero que compres el que te sirve y vuelvas, a venderte uno caro y que se te quede guardado." | 📌 `[P01]` |
| 36-40s | "Dime qué lees y te digo cuál NO comprar." | ✨ CTA + loop |

> 💡 Invierte la expectativa del vendedor. Construye la confianza que cierra en WhatsApp.

---

### 33 · A la mitad de la gente no le recomiendo esto

**Hook:** `A mucha gente le digo que no`
**RUM:** U8 · I7 · C9 · S9 · D8 · A9 → **76%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "A mucha gente le digo que no." | 📌 `[P02]` |
| 3-14s | "Si lees dos libros al año por compromiso, no lo compres. En serio. Te va a quedar guardado." | 🎬 `[F16]` |
| 14-26s | "Esto es para el que YA lee y se pelea con el peso, la luz o la falta de tiempo. No hace magia." | 🎬 `[F08]` |
| 26-36s | "No convierte a nadie en lector. Le saca los obstáculos al que ya quiere serlo." | 📌 `[P01]` |
| 36-40s | "Si te describí, escríbeme. Si no, ahorrate la plata." | ✨ CTA + loop |

---

### 34 · Lo que nadie te dice antes de comprar

**Hook:** `Lo que nadie te dice antes de comprar`
**RUM:** U8 · I7 · C9 · S9 · D8 · A9 → **76%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Lo que nadie te dice antes de comprar." | 📌 `[P02]` |
| 3-14s | "Uno: no sirve para ver videos ni redes. Si esperas eso, te vas a decepcionar." | ✨ Anim "1" |
| 14-24s | "Dos: la pantalla no es como la del celular. Es más lenta a propósito, porque imita al papel." | ✨ Anim "2" |
| 24-34s | "Tres: no es un capricho de tecnología. Es lo contrario: es tecnología para dejar de usar tecnología." | ✨ Anim "3" |
| 34-40s | "Escríbeme y te digo si te sirve o no." | ✨ CTA + loop |

> 💡 Sustitución simbólica del curso: números arábigos grandes, no palabras.

---

### 35 · La verdad sobre los libros gratis

**Hook:** `Sí, hay miles de libros gratis`
**RUM:** U9 · I6 · C9 · S9 · D9 · A8 → **77%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Sí, hay miles de libros gratis." | 🎬 `[F09]` |
| 3-14s | "Todos los clásicos: dominio público, gratis y legales. Cervantes, Austen, Dostoievski, sin pagar nada." | ✨ Anim "gratis" |
| 14-26s | "Y los que no son gratis casi siempre cuestan menos que el libro de papel." | 🎬 `[F08]` |
| 26-36s | "O sea que el aparato se paga solo con lo que ahorras en libros. Nadie hace esa cuenta." | 📌 `[P02]` |
| 36-40s | "Escríbeme y te paso de dónde bajarlos." | ✨ CTA + loop |

> 💡 Enorme para tu kit postventa (ya regalas un Drive de libros — comunicalo).

---

## BLOQUE H — Prueba social y negocio

**Publicar cuando la cuenta ya tenga tracción.** Tienen U más bajo, pero
convierten fuerte a quien ya te sigue.

---

### 36 · Entrega en 68 minutos

**Hook:** `De "hola" a entregado: 68 minutos`
**RUM:** U7 · I6 · C9 · S8 · D7 · A10 → **63%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "De 'hola' a entregado: 68 minutos." | 🎬 `[F24]` moto de entrega |
| 3-14s | "Me escribió a las 3 de la tarde. A las 4 y 8 ya lo estaba usando en su casa." | ✨ Anim reloj 15:00 → 16:08 |
| 14-25s | "No es magia: es que el equipo ya está acá, en Santa Cruz. No lo pido a Estados Unidos cuando me compras." | 🎬 `[P11]` tus cajas selladas reales |
| 25-35s | "Pagas por QR cuando lo tienes en la mano. No antes." | 🎬 `[F24]` |
| 35-40s | "Si estás en Santa Cruz, hoy mismo lo tienes." | ✨ CTA + loop |

> 💡 Tu superpoder real según los chats. Casi no lo comunicas.

---

### 37 · Paga cuando te lo entregan

**Hook:** `Pagas cuando lo tienes en la mano`
**RUM:** U8 · I7 · C10 · S8 · D7 · A10 → **75%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Pagas cuando lo tienes en la mano." | 🎬 `[F24]` |
| 3-14s | "Sé por qué dudas en comprar por internet en Bolivia. A todos nos pasó o le pasó a un conocido." | 🎬 `[F30]` |
| 14-26s | "Por eso en La Paz y Cochabamba es contra-entrega. Llega, lo revisas, y recién ahí pagas." | 🎬 `[F25]` |
| 26-36s | "Caja sellada, nuevo, con garantía. Si no te convence cuando lo ves, no lo recibes." | 🎬 `[P11]` tus cajas selladas reales |
| 36-40s | "Escríbeme y coordinamos." | ✨ CTA + loop |

> 💡 La frase que aparece en casi TODAS tus ventas del interior.

---

### 38 · El color que se hizo viral

**Hook:** `Este color se agotó en 3 días`
**RUM:** U7 · I5 · C9 · S9 · D8 · A9 → **61%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Este color se agotó en 3 días." | 📌 `[P04]` el jade / verde matcha |
| 3-14s | "El verde matcha. No lo pide porque fuera bonito: lo pide porque me lo pidieron 10 personas la misma semana." | 📌 `[P04]` |
| 14-25s | "Y hay gente que espera semanas por un color específico. El blanco es el otro que vuela." | 📌 `[P10]` Kobo Clara |
| 25-35s | "Suena tonto, pero el color importa: es algo que vas a tener en la mano todos los días." | 📌 `[P06]` |
| 35-40s | "Dime qué color buscas y te aviso cuando llegue." | ✨ CTA + loop |

> 💡 Alimenta tu mecánica ganadora: avisar cuando llega el color cierra ventas.

---

## BLOQUE I — Dinero y valor

---

### 39 · Cuánto te cuesta realmente leer

**Hook:** `Haz esta cuenta antes de comprar`
**RUM:** U8 · I7 · C9 · S8 · D8 · A9 → **73%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "Haz esta cuenta antes de comprar." | ✨ Anim calculadora |
| 3-14s | "Un libro nuevo en Bolivia te sale entre 80 y 150 bolivianos. Si lees uno al mes, son casi 1.500 al año." | ✨ Anim cifras |
| 14-26s | "En digital, muchos son gratis y el resto cuesta la mitad o menos." | 🎬 `[F09]` |
| 26-36s | "Así que no es un gasto de 2.000. Es un gasto que se devuelve solo en un año y después te ahorra plata." | 📌 `[P02]` |
| 36-40s | "Escríbeme y sacamos la cuenta con lo que lees tú." | ✨ CTA + loop |

---

### 40 · No es caro, es que dura

**Hook:** `"Es caro" — hagamos la cuenta`
**RUM:** U8 · I7 · C9 · S8 · D8 · A9 → **73%**

| t | Habla | Visual |
|---|---|---|
| 0-3s | "'Es caro' — hagamos la cuenta." | 📌 `[P02]` |
| 3-14s | "Cambias de celular cada 2 o 3 años. Sí o sí, porque se pone lento." | 🎬 `[F23]` |
| 14-26s | "Esto no se pone lento, porque no hace nada más que mostrar letras. Hay gente leyendo con el mismo de hace 8 años." | 🎬 `[F15]` |
| 26-36s | "Dividí el precio entre 8 años y dime si es caro." | ✨ Anim división |
| 36-40s | "Escríbeme y te muestro las opciones según tu presupuesto." | ✨ CTA + loop |

---

## Resumen de puntuaciones

| Rango RUM | Guiones | Cuándo publicarlos |
|---|---|---|
| **80-90%** ⭐ | 1, 7, 8, 9, 11, 13, 14, 15, 18, 19, 20, 27, 28, 32 | Primeros. Son los que abren anillos |
| **70-79%** | 2, 3, 4, 5, 6, 10, 12, 16, 17, 21, 22, 23, 25, 26, 31, 33, 34, 35, 37, 39, 40 | Cuerpo del calendario |
| **60-69%** | 24, 29, 30, 36, 38 | Cuando ya haya audiencia propia |

**Reparto por bloque:** A-Sueño/vista 6 · B-Atención 6 · C-Regalo 5 ·
D-Hijos 4 · E-Hábito 5 · F-Comparación 5 · G-Rompe-creencias 4 ·
H-Prueba social 3 · I-Dinero 2.

A 4 videos por semana, este banco cubre **10 semanas**.
