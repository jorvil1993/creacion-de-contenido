# Traspaso — Modo "Pipeline Dirigido por Guion" (`--guion N`)

> Escrito el 2026-07-27. El modo dirigido por guion quedó **implementado, verificado y funcionando de punta a punta**.
> Permite a José ejecutar cualquier guion de `PANEL-PRODUCCION.html` (ej. `--guion 7`) como fuente de verdad.
> El comportamiento por defecto del pipeline (sin `--guion`) **no cambia en absoluto**.

---

## 0. Lo que SÍ funciona — no tocarlo

- **Extractor de Guiones HTML (`editor/f13_guion.py`)**:
  - Lee `PANEL-PRODUCCION.html` (fuente de verdad), extrae `const G=[...]` (los 10 guiones) y `const CLIPS={...}` (los 40 códigos de assets visuales).
  - Incluye fallback automático entre Node.js y parser de respaldo en Python.

- **Alineador Guion ↔ Transcripción (`f13_guion.py:alinear_guion_con_transcripcion`)**:
  - **Los tiempos del HTML (`3–5s`) se ignoran por completo.**
  - Realiza una alineación monótona palabra a palabra usando `difflib.SequenceMatcher` sobre `02_cortado.json`.
  - Mantiene estricta monotonía: el beat $n+1$ se busca siempre después del final del beat $n$.
  - Si una frase no es pronunciada o falta un beat, se emite un aviso en consola y **la corrida continúa sin fallar** (resiliencia comprobada).

- **Generador de las 4 Órdenes y Reporte Markdown**:
  - Genera `10_guion-alineado.md` en el directorio de trabajo con la tabla de coincidencia, tiempos reales y nivel de confianza.
  - `guion.sfx.json`: Extrae los SFX de la columna de sonido mapeando directamente a `assets/sfx/<nombre>.mp3`.
  - `guion.animaciones.json`: Emite eventos de plantillas `ANIM` mapeando a `plantillas/compositions/`.
  - `guion.eventos.json`: Emite eventos `PIP`. Si el asset es un video manual (`.mp4`), se renderiza previamente a tarjeta con marco vía `f12_video_gen.render_pip_video()` con `"medio": "video"`.
  - `guion.broll.json`: Emite eventos `B-ROLL` a pantalla completa (1080×1920) con `"broll_fullscreen": True`.

- **Integración en `f6_overlays.py` y `editor.py`**:
  - `f6_overlays.py` acepta `--broll-manual JSON` y `cargar_eventos_manual()` preserva `"medio"` y `"broll_fullscreen"`.
  - `editor.py` acepta `--guion N`, `--musica NOMBRE` y `--broll-manual JSON`. Inyecta automáticamente los JSONs alineados entre la Fase 1b y 5a.

---

## 1. Verificación Realizada

1. **Sintaxis y Módulos**:
   - `python -c "import sys; sys.path.append('editor'); import config, f9_generar, f6_overlays, f4_retencion, f12_video_gen, f13_guion, editor; print('OK')"`
   - Resultado: **Exit Code 0** (Sintaxis y módulos OK).

2. **Alineador y Resiliencia**:
   - Probado con transcripción simulada de 11/12 beats de Guion 7 (omitiendo intencionalmente el beat 5).
   - Resultado: 11 beats alineados con confianza 1.00; beat 5 reportado como omitido sin romper los beats 6–11.

3. **Ejecución Completa End-to-End**:
   - Ejecutado: `python editor/editor.py "contexto/VIDEOV2.mp4" --nombre guion7_test_run --guion 7 --reaplicar`
   - Resultado:
     - Generado `salida/guion7_test_run/10_guion-alineado.md`
     - Generados `guion.sfx.json`, `guion.animaciones.json`, `guion.eventos.json`, `guion.broll.json`
     - Finalizado en `salida/guion7_test_run/07_FINAL.mp4` y copiado a OneDrive `salida/guion7_test_run.mp4`.

---

## 2. Cómo Usarlo en Producción

José graba siguiendo el guion N (por ejemplo Guion 7):

```bash
C:\ai-video\venv312\Scripts\python.exe editor\editor.py "contexto\Guion-7.mp4" --guion 7
```

Si quiere iterar rápidamente sobre los overlays o sonidos ajustados:

```bash
C:\ai-video\venv312\Scripts\python.exe editor\editor.py "contexto\Guion-7.mp4" --guion 7 --nombre Guion-7 --reaplicar
```

---

## 3. Pendientes Visuales (Material de Producción)

- **Bajar clips faltantes**: Actualmente existen `abandonado.mp4` y `scroll.mp4` en `assets/generado/video/manual/`. A medida que José baje los 27 clips restantes (ej. `F01 -> noche.mp4`, `F02 -> ojos.mp4`, `P02 -> P02.mp4`), el pipeline los consumirá automáticamente. Si no están bajados, el pipeline simplemente los omite con un aviso y continúa.
