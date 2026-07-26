# Prompt de ejecución — Editor visual v2

Copiar y pegar el bloque de abajo en una sesión nueva de Claude Code abierta en
`creacion-de-contenido/`. Está escrito para que la sesión trabaje de corrido sin
parar a pedir permiso en cada paso.

---

```
Vas a construir el Editor visual v2 del pipeline de video de DeviceShop.

## Antes de escribir una sola línea

1. Lee entero `contexto/PLAN-EDITOR-VISUAL-V2.md`. Es tu especificación completa:
   tiene el estado verificado del código, las decisiones ya tomadas por José, las
   6 fases con su criterio de aceptación, y las trampas ya pagadas.
2. Corre `ls -la --time-style=+%H:%M editor/*.py` y lee el final de
   `contexto/BITACORA-INTEGRACION.md`. Otras sesiones trabajan sobre `editor/` en
   paralelo: si hay escrituras posteriores a las que registra el plan (§0), léelas
   antes de tocar esos archivos.
3. No confíes en una lectura de archivo hecha hace rato. `config.py` pasó de 414
   a 600 líneas en una hora sin aviso.

## Cómo quiero que trabajes

Trabaja de corrido, en el orden de fases del §7 del plan, sin parar a pedirme
permiso entre pasos. El plan ya tiene mis decisiones tomadas (§2) — no me las
vuelvas a preguntar.

Cuando dudes en un detalle de diseño, resuélvelo tú con el criterio rector del
plan: **el automático es un primer borrador que José corrige, no un veredicto.
Toda decisión automática debe ser visible y sobrescribible desde el editor.**
Anota la duda y cómo la resolviste; no te detengas por ella.

Solo párate a preguntarme si:
- la respuesta cambiaría el diseño de una fase entera, o
- tendrías que romper una de las 9 trampas del §5, o
- descubres que algo del plan es factualmente falso.

Si algo del plan resulta equivocado, dilo claro y sigue con lo demás. No lo
ejecutes a ciegas sabiendo que está mal.

## Estándar de verificación de este proyecto

Este pipeline tiene cultura de medir, no de suponer. Respétala:

- No declares una fase cerrada porque "terminó sin error". Cumple su criterio de
  aceptación explícito y muestra la evidencia.
- Al medir calidad de video, **cuenta los frames primero**. Un VMAF alto sobre un
  video al que le faltan frames no significa nada.
- **Comprueba tu herramienta de medición antes de diagnosticar un bug.** En este
  proyecto ya pasó dos veces que el "bug" era el comando de verificación.
- Cuando verifiques algo visual, extrae fotogramas y míralos. No te fíes del log.

## Registro (esto es lo que hace que valga la pena trabajar de corrido)

Después de **cada fase**, escribe en `contexto/BITACORA-INTEGRACION.md`:
- qué construiste, con rutas y nombres de función
- qué mediste y con qué resultado
- qué quedó pendiente o dudoso
- **el punto exacto por donde seguiría la próxima sesión**

Hazlo aunque la fase haya quedado a medias. Si te quedas sin contexto o se corta
la sesión, ese registro es lo único que permite retomar sin repetir trabajo.
Escríbelo pensando en alguien que llega sin haber visto nada de esto.

## Prohibiciones duras

- No subas `NVENC_PRESET` de `p5`. No actives `rc-lookahead`, `temporal-aq` ni
  `spatial-aq`. Está medido: pierden los últimos 3 frames o empeoran la calidad.
- Todo `pip install` en `venv312` lleva `-c C:\ai-video\constraints.txt`.
- Nada pesado a OneDrive. Intermedios, proxy y miniaturas van a `C:\ai-video\`.
- No lances procesos con `stdout=PIPE` sin leer el pipe (cuelga ffmpeg y ComfyUI).
- No reescribas `f10_editor_visual.py` desde cero. Amplíalo y construye
  `f11_servidor.py` encima. Si rehacer parece más fácil que reutilizar, eso es
  señal de preguntarme, no de rehacer.
- No metas dependencias nuevas: stdlib de Python, JS y CSS planos. Sin npm, sin
  frameworks, sin CDN. No hay API keys ni red garantizada.
- No toques la tarea de "eliminar la recompresión del paso de corte". Está fuera
  de alcance por decisión explícita.

## Cuando ya no puedas seguir

Si te quedas sin contexto, te bloqueas o terminas todo:
1. Deja el repo en estado consistente (nada a medio escribir que rompa el pipeline).
2. Cierra la bitácora con el punto de retome.
3. Dame un resumen corto: qué quedó funcionando, qué falta, qué decisión necesito
   tomar yo.

Empieza por la Fase 0 y avanza sin detenerte.
```

---

## Nota de uso

- Si querés que trabaje sobre una copia aislada del repo en vez de sobre los
  archivos vivos, agregá al final: *"Trabajá en un worktree aislado."* Tiene
  sentido si sospechás que otra sesión va a estar tocando `editor/` al mismo
  tiempo.
- Si preferís que se detenga al terminar cada fase para que la revises, cambiá
  *"Trabaja de corrido, en el orden de fases"* por *"Al cerrar cada fase, párate
  y muéstrame el resultado antes de seguir"*.
