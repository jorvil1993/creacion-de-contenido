# Para mañana ☀️

Trabajo de la noche del **2026-07-27**, en la rama `mejoras-pipeline-nocturno`
(cuatro commits, `master` sin tocar).

```bash
git log --oneline master..mejoras-pipeline-nocturno
```

Los mensajes de commit traen el detalle técnico de cada cosa. Esto de aquí es
cómo se **usa**.

---

## 1. El hook físico ya no se borra

El corte de silencios se llevaba los segundos en los que entras al cuadro y te
sientas, porque ahí no hablas. Ahora cada guion del panel declara cuántos
segundos de silencio conservar justo antes de tu primera palabra:

```js
{n:7, t:'No es que no te guste leer', hook:'fisico', hooksegs:3.0, ...}
```

**Para calibrarlo:** cambia el número en `PANEL-PRODUCCION.html`, en la línea
del guion, y vuelve a correr. El panel te lo enseña dentro de cada guion, en el
bloque "⏱️ Hook físico". Se cuenta **hacia atrás** desde tu primera palabra: lo
de antes (la silla vacía, acomodarte) se sigue cortando. Con `0` se comporta
como antes.

Valores puestos según el gesto de cada hook: sentarse de golpe 3.0s, bajar el
celular 2.0s, girar el aparato hacia cámara 1.5s, y 0 en los dos guiones que
arrancan hablando a cámara.

> Ojo: `hooksegs` lo aplica el corte, que **no** se re-ejecuta con
> `--reaplicar`. Si cambias el valor, corre sin esa bandera. El pipeline te lo
> avisa.

## 2. Grabar en dos planos reales

La columna "Tomas" del guion 7 pide un plano cerrado con *cambio de distancia
real, no zoom digital*. Ya se puede:

```bash
python editor.py toma-abierta.mp4 toma-cerrada.mp4 --guion 7
```

Las une, y marca los empalmes como los **únicos** cambios de plano del video —
que es donde el encuadre se reinicia. Un corte de silencio ya no reinicia nada.

Si prefieres seguir grabando de una sola toma, no cambia nada: pasa un solo
archivo y el pipeline hace el acercamiento digital donde el guion dice "Plano
cerrado".

## 3. Retocar el encuadre a mano

En el editor visual hay un panel nuevo, **Encuadre**:

- Las barras cian son los **planos cerrados**: arrastra el cuerpo para moverlas
  y los bordes para estirarlas.
- Las marcas amarillas son los **punch-ins**: arrástralas.
- La curva de abajo es el zoom real del render, con un cursor que sigue al
  video. No es un dibujo aproximado: la calcula el servidor con la misma
  función que usa el render.
- "Volver al automático" deshace tus cambios y regresa a lo que dice el guion.

Guardar y re-renderizar ya lo tienen en cuenta.

## 4. Los 10 guiones tienen animaciones

Antes solo el 7. Los otros nueve tenían un único beat ANIM al final pidiendo la
tarjeta de CTA, que el pipeline ya pone solo — o sea, cero animaciones. Ahora
cada guion tiene 3 o 4 Hyperframes repartidos.

Se colocaron a propósito en los beats cuyo clip de Google Flow **todavía no
existe**, así tapan un hueco en vez de competir con algo.

## 5. Antes de publicar cualquier cambio

```bash
python editor/test_regresion.py
```

```bash
python editor/test_align.py
```

39 + 5 pruebas sobre la aritmética de tiempos, que es donde el pipeline falla
en silencio: el video sale igual y el error solo se ve mirando el resultado.

---

## Lo que sigue pendiente

- **Los clips de Google Flow.** Es el cuello de botella real. Ocho de los diez
  guiones referencian clips F/P que no existen en `assets/generado/video/manual/`
  (`F01:noche`, `F15:tiempo`, `F30:vitrina`, `P06`, `P07`…). Sin ellos esos
  beats salen OMITIDOS. Los que sí existen: `scroll`, `rendicion`,
  `kindle-primer-plano`, `pagina-real`, `abandonado`, `kindle-real`,
  `inside-box`, `unboxing-paperwhite`.

- **El guion 7 grabado tiene el hook viejo.** En el audio dices *"No es que no
  te guste leer"* pero el panel ya dice *"¿Por qué dejaste de leer?"*. Ese beat
  nunca alinea. Si vuelves a grabar, arranca con la frase del panel.

- **El CTA se come los últimos 6.5s.** En un video de 27s eso es un cuarto del
  total, y ya obligó a descartar el B-roll del beat 9 (le quedaban 0.32s). Vale
  la pena revisar si el cierre necesita tanto.

- **Tres archivos tuyos sin commitear** de antes de esta sesión:
  `contexto/40-GUIONES-VIRALES.md`, `contexto/PROMPTS-GOOGLE-FLOW.md` y
  `editor/f12_video_gen.py`. Los dejé como estaban.

## Para verlo

`salida/Guion-7-hook.mp4` — el guion 7 con todo lo de arriba aplicado.

---

*El plan completo sigue en `contexto/PLAN-EDITOR-VIDEO.md`.*
