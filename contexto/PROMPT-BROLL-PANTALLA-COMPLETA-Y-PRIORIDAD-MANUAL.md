# Prompt de implementación — B-roll a pantalla completa + prioridad absoluta del video manual

> Prompt listo para pegarle a una IA con acceso al repo. Pide **verificación
> antes de escribir código**: la documentación de este proyecto ya afirmó una
> vez que esto existía sin comprobarlo (ver `contexto/PROMPT-ARREGLAR-BROLL-LTX.md`
> como ejemplo del formato de traspaso esperado al terminar). No repetir ese error.

---

## Contexto para quien implemente esto

DeviceShop Bolivia vende e-readers (Kindle/Kobo). José graba videos verticales
de 30-40s hablando a cámara; el pipeline en `editor/` los convierte en TikToks
editados: subtítulos, punch-ins, inserciones (PiP) sobre palabras clave del
guion, música y SFX — todo en una sola pasada de NVENC.

Aparte del pipeline, José está generando **clips de video con Google Flow**
(IA externa, fuera del repo) para ilustrar conceptos del guion — "alguien
scrolleando sin parar", "un libro abandonado con separador", etc. Hoy esos
clips se guardan a mano en `assets/generado/video/manual/<nombre>.mp4` pero
**el pipeline no los usa para nada**: es solo una carpeta de acopio.

Se necesitan dos cosas nuevas:

## 1 — B-roll a pantalla completa con el audio original de fondo

Así se editan los B-roll virales en TikTok: el video de la persona hablando
desaparece un momento y se ve otra cosa (el objeto del que habla, una
metáfora), pero **la voz de la persona sigue sonando sin cortes** y **los
subtítulos siguen en pantalla**. El espectador nunca deja de escuchar ni de
leer; solo cambia lo que ve.

Hoy el pipeline **no tiene esto**. Lo único que existe son tarjetas PiP
pequeñas (400×520px) ancladas en la franja superior (10-35% del alto),
nunca a pantalla completa. Verificado en `editor/config.py`:
`INSERTO_ANCHO = 400`, `INSERTO_ALTO = 520`, `OVERLAY_BANDA_SUPERIOR_PCT = (0.10, 0.35)`.

**Requisito:** un tipo de inserto nuevo que:
- ocupe el frame completo (1080×1920, `config.ANCHO`/`config.ALTO`) durante su
  ventana `[ini, fin]`;
- **nunca corte ni silencie el audio original** de José — el audio manda
  siempre, esto ya es una regla dura del proyecto (sección 4.5 del plan
  maestro, `contexto/PLAN-EDITOR-VIDEO.md`);
- **no tape los subtítulos** — son el pilar de retención del proyecto
  (`.ass` karaoke, siempre visibles, ver `f3_subtitulos.py`); hay que
  componerlos por encima del B-roll, no que el B-roll los tape;
- transición suave de entrada/salida (fade), igual que ya hace el resto de
  los overlays, para no romper la regla de "cambio visual cada 2-3s" sin que
  se sienta como un corte brusco de video.

### Pista real ya existente en el código — usarla, no reinventar

`editor/f4_retencion.py` (función que compone frames + audio + eventos de
overlay, alrededor de la línea 295-345) **ya tiene un caso para
`ev["medio"] == "video"`** que hace exactamente el truco de tiempo que hace
falta:

```python
if ev.get("medio") == "video":
    inputs += ["-itsoffset", f"{ev['ini']:.3f}", "-i", str(ev["archivo"])]
```

`-itsoffset` desplaza el clip para que **empiece a reproducirse en su propio
`ini`**, no en t=0 — así el clip no llega "ya adelantado" cuando se hace
visible. Ese es exactamente el mecanismo que un B-roll a pantalla completa
necesita. **Verificar si ese código es el que de verdad se ejecuta en el
camino de producción** (rastrear la llamada desde `editor.py`) y si es así,
extender ese patrón — no crear una segunda ruta de composición desde cero.

Hay **otra** función, `editor/f6_overlays.py: componer_overlays()`, que
también procesa eventos con `archivo` pero usa `-loop 1 -framerate ... -t`
para todos los inputs por igual (ese patrón es para **imágenes fijas**, no
para video real). **Confirmar cuál de las dos funciones es la que compone
los overlays en la corrida normal de `editor.py`** antes de decidir dónde
enganchar el B-roll nuevo — puede que una sea legado de un modo de uso
distinto (`--posiciones-manual` vía el editor visual). No asumir.

## 2 — Prioridad absoluta del video generado a mano sobre cualquier generación automática

**Regla de negocio, sin excepción:** si existe un clip de video puesto a mano
por José, se usa ese. El pipeline **nunca debe generar un video propio para
un concepto que ya tiene un clip manual**, y **nunca debe generar video
automáticamente si nadie lo pidió explícitamente** — esto último ya es el
comportamiento por defecto hoy (`config.LTX_HABILITADO = False`, se prende
solo con `--video-ambiente`) y **no debe romperse**.

### Dónde viven los clips manuales

`assets/generado/video/manual/<nombre>.mp4` — la carpeta no existe todavía
en el repo (créala el código si hace falta, o documentar que el usuario la
crea al primer uso). El nombre del archivo coincide con el nombre de
concepto que ya usa `config.PALABRAS_A_TAGS` para las imágenes fijas (p. ej.
`scroll.mp4`, `noche.mp4`, `libros.mp4`, `sol.mp4`) — **no** con el código de
referencia (`F14`, `F01`, etc.) que solo se usa en la documentación de
guiones para humanos.

### El precedente ya existe para IMAGEN — replicar el mismo patrón para VIDEO

`editor/f9_generar.py`, función `version_manual(tag)` (línea ~483):

```python
def version_manual(tag: str) -> Path | None:
    """Imagen puesta a mano por José para esta etiqueta (gana sobre Flux)."""
    dir_manual = config.DIR_GENERADO / "manual"
    if not dir_manual.is_dir():
        return None
    nombre = _slug(tag.lstrip("#"))
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        cand = dir_manual / f"{nombre}{ext}"
        if cand.exists():
            return cand
    return None
```

Y en `generar_para_tag()`, la prioridad es explícita: *"Prioridad: la que puso
José a mano > Flux"*.

**Implementar el equivalente para video**: una función (sugerido
`version_manual_video(tag)`) que mire en
`config.DIR_VIDEO_GENERADO / "manual"` (constante nueva; hoy solo existe
`config.DIR_VIDEO_GENERADO_AUTO = DIR_ASSETS/"generado"/"video"/"auto"`,
verificado en `config.py` líneas 762-763) con extensión `.mp4`, y que se
consulte **antes** de cualquier llamada a `f12_video_gen` (el generador LTX).

### Orden de prioridad final que debe quedar (para el inserto de un concepto)

1. **Clip de video manual** (`assets/generado/video/manual/<tag>.mp4`) → se
   usa como **B-roll a pantalla completa** (la funcionalidad del punto 1).
   Si existe, el pipeline no genera nada para ese concepto, con o sin
   `--video-ambiente`.
2. Si no hay clip manual, sigue el camino que **ya existe hoy sin tocar**:
   foto real del catálogo > imagen manual (PNG) > clip LTX (solo si
   `--video-ambiente`) > imagen generada con Flux — todo como PiP pequeño,
   no a pantalla completa.

Es decir: el B-roll a pantalla completa es una **capa nueva que se consulta
primero**, no un reemplazo del sistema de PiP existente. Un concepto sin
clip manual sigue funcionando exactamente igual que hoy.

## Verificar antes de escribir una sola línea

- [ ] Leer `editor/f6_overlays.py` completo (es el orquestador de qué
      inserto va con qué prioridad) y `editor/f9_generar.py` (prioridad de
      imagen) para entender el patrón real, no el que yo describo de oído.
- [ ] Rastrear desde `editor/editor.py` qué función compone los overlays en
      una corrida normal (`f4_retencion.py` vs `f6_overlays.componer_overlays`)
      — confirmar con un print/log o leyendo las llamadas, no asumir.
- [ ] Confirmar que `-itsoffset` de verdad resuelve el timing para un mp4
      real (no solo para los `.mov` ProRes 4444 con alfa que genera
      Hyperframes) — un clip de Flow no tiene canal alfa; hay que decidir
      si necesita composición con alfa (no, si tapa toda la pantalla no
      hace falta transparencia, solo estar arriba en el `overlay=`/mapeo de
      streams) o si conviene un filtro distinto (`concat`/`overlay` según
      corresponda al caso "pantalla completa" en vez de "PiP con alfa").
- [ ] Revisar la tabla de "Trampas conocidas" en
      `.claude/skills/editor-deviceshop/SKILL.md` antes de tocar NVENC,
      Hyperframes o rutas — en particular: no subir `NVENC_PRESET` de `p5`
      (pierde los últimos 3 frames, justo donde va el CTA) y mantener la
      disciplina de una sola codificación NVENC por corrida (no agregar un
      segundo paso de encode para el B-roll).
- [ ] Revisar cómo se manejan hoy los formatos de video que YA se insertan
      (`hook`, `cta`, `anim-*`, `comparativa`, `specs`, `pip-producto`) para
      no duplicar código: si alguno de esos ya es "video real ocupando un
      área", puede que el mecanismo sea reusable case por case.

## Qué NO hacer

- No generar video automáticamente por el solo hecho de implementar esto —
  `LTX_HABILITADO` sigue en `False` por defecto y `--video-ambiente` sigue
  siendo opt-in. Este cambio es sobre **consumir** clips ya generados por
  José, no sobre generar más.
- No mover ni reorganizar `contexto/fotos y videos/` (la usa la página web).
- No tocar el `NVENC_PRESET` ni agregar `rc-lookahead`/`temporal-aq`/`spatial-aq`.
- No asumir que un archivo o función existe porque "suena lógico que
  exista" — este mismo documento nació de corregir exactamente ese error.

## Al terminar

Dejar un documento de traspaso con el mismo formato que
`contexto/PROMPT-ARREGLAR-BROLL-LTX.md`: qué quedó funcionando y verificado
(con cómo se verificó), qué quedó pendiente, y actualizar:

- `.claude/skills/editor-deviceshop/SKILL.md` (la tabla de "de dónde sale
  cada imagen" pasa a incluir el video manual como capa 0, antes de la foto
  real del catálogo).
- `contexto/PROMPTS-GOOGLE-FLOW.md` y `PANEL-PRODUCCION.html` — ahora mismo
  ambos dicen explícitamente **"el pipeline no lee esta carpeta sola"**;
  ese texto queda desactualizado en cuanto esto se implemente y hay que
  corregirlo para que no vuelva a generar confusión.
