# Pack de SFX — DeviceShop

**141 sonidos.** 13 del pack inicial (2026-07-26) + 128 añadidos el 2026-07-27.

## De dónde salen y con qué licencia

| Origen | Cuántos | Licencia |
|---|---|---|
| [videoeditingsfx.com](https://videoeditingsfx.com/sfx/) | 121 | **CC0** (dominio público), descarga directa sin cuenta |
| Síntesis propia (`numpy` + `scipy`) | 20 | Sin licencia que respetar: se fabricaron aquí |

Ninguno tiene riesgo de Content ID ni de copyright strike.

Los 13 originales resultaron ser byte a byte los mismos archivos de esa web
(comprobado por md5), así que la ampliación bajó los 87 restantes de su catálogo
—que tiene exactamente 100— sin duplicar ninguno.

**No hay sonidos meme** (Vine Boom, metal pipe, "emotional damage" y compañía).
Son los más virales que existen, pero casi todos vienen rasgados de películas,
series o juegos, y son justo los que disparan reclamos. Para el momento en que
un meme haría gracia, el equivalente limpio de este pack es `impacto_grave_2` o
`impacto_subdrop`.

## Qué se eligió y por qué

La selección sigue lo que las guías de edición de corto de 2026 marcan como la
paleta que de verdad se usa, en este orden:

1. **whoosh / swipe** — la categoría más usada; uno en cada corte
2. **impactos** — reveals y remates; 1 o 2 por video como máximo
3. **risers / buildups** — 2-3s antes del reveal, reventando encima de él
4. **UI / clicks / pops** — apariciones de texto y listas
5. **reverse FX** — succión antes del corte
6. **obturador de cámara** — cortes tipo foto
7. **success / cierre** — hito y CTA final

El pack inicial no tenía **nada** de las categorías 3, 5 y 6, ni clicks de UI.

## El catálogo

| Categoría | Sonidos | En rotación automática | Para qué |
|---|---|---|---|
| `whoosh_*`, `transicion_*` | 27 | 20 | transiciones y punch-ins |
| `camara_*` | 29 | 2 | cortes tipo foto, obturadores, flashes |
| `ui_*` | 23 | 11 | apariciones de texto, stickers, listas |
| `impacto_*` | 20 | 5 | hook, remates, reveals |
| `riser_*` | 18 | 0 | anticipación antes del reveal grande |
| `reverso_*` | 12 | 0 | succión hacia un corte, rebobinado |
| `notificacion_*` | 4 | 4 | confirmación, CTA |
| `glitch_*` | 4 | 0 | transición corta de estética tecnológica |
| `venta_*` (caja, monedas, tada) | 4 | 1 | reveal de precio, cierre positivo |

**43 están en rotación automática** (`config.SFX_POR_EVENTO`). Los otros 98 se
usan a mano desde la hoja de sonido, que los lista agrupados por categoría.

Los risers y los reverses están fuera de la rotación **a propósito**: son de un
solo uso por video. Puestos automáticamente en cada corte dejarían de significar
nada.

## Punto de impacto — `_alineacion.json`

El dato que hace que el pack funcione. Cada archivo trae medido **en qué segundo
de sí mismo golpea**:

| Familia | Dónde golpea | Ejemplo |
|---|---|---|
| `golpe` | en los primeros ms | `impacto_hit.mp3` → 0.06s |
| `swell` | en el medio | `whoosh_swoosh.mp3` → 0.36s |
| `build` | al final | `riser_1.mp3` → 2.38s |

El pipeline coloca cada sonido en `t - punto`, de modo que lo que cae sobre el
evento visual es el golpe y no el primer frame del archivo. Sin esto un riser
revienta dos segundos y medio tarde, que es igual que no ponerlo.

`SFX_DURACION_MAX_S` (1.6s) también se cuenta **desde el golpe**, no desde el
inicio del archivo: si no, el recorte se llevaba justo la parte que vale.

## Cómo se procesaron

Los archivos no se copiaron tal cual. Sobre la descarga cruda se midió:

- hasta **2s de silencio al inicio** en varios (`riser-2`, `vintage-flash-long`),
  que habría hecho sonar el golpe tarde;
- archivos que son **packs con varias tomas dentro**: `analog-shutter` traía 4
  disparos en 9s y `vintage-flash-long` 12 en 37s. Se partieron, y por eso salen
  128 sonidos de 87 descargas;
- **20 dB de dispersión** de nivel entre archivos.

Cada archivo quedó recortado alrededor de su golpe (máximo 3s de entrada y 2.5s
de cola), normalizado a **-1 dBFS** y con micro-fades para que no chasquee.

Los 20 sintetizados se comprobaron midiendo su trayectoria espectral: que un sub
drop de verdad baje de frecuencia, que un riser suba de brillo y de energía, que
un blip tenga su fundamental donde dice. Los sub drops no bajan de 45 Hz a
propósito — el parlante de un celular no reproduce nada por debajo de eso.

**Los 20 sintetizados no los ha escuchado nadie todavía.** Cumplen la medición,
pero el oído manda: si alguno suena barato al lado de los grabados, se borra y
no pasa nada.
