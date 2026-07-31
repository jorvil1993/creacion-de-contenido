"""Pruebas de la tira de capas apiladas (bloques A y C de PLAN-TIRA.md).

Por que existe, y por que en un archivo aparte de test_regresion.py. La tira es
casi toda JavaScript, y `test_regresion.py` es de Python: un JS roto lo deja
pasar en verde. Lo que si se puede comprobar desde aqui, y es donde de verdad
se rompen las cosas, son tres clases de fallo silencioso:

  · Que `f14_tira` calcule los bloques de subtitulo con reglas propias en vez
    de con `f3_subtitulos.agrupar_en_bloques()`. El carril diria una cosa y el
    video quemaria otra, sin que nada falle.
  · Que las anclas en `f11_servidor.py` se pierdan en un merge. El editor sigue
    funcionando exactamente igual, solo que sin tira, y no hay error en ningun
    lado.
  · Que un dato que falta en una corrida (sin guion, sin transcripcion) tumbe
    `recolectar()` entero y con el todo el editor, no solo la tira.

Las de sintaxis del JS se hacen con `node --check` (ver PLAN-TIRA.md), que si
las ve.

Uso:  python editor/test_tira.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import config
import f3_subtitulos
import f10_editor_visual as f10
import f14_tira

AQUI = Path(__file__).resolve().parent

_resultados = []


def chk(nombre: str, condicion: bool, detalle: str = ""):
    _resultados.append((nombre, bool(condicion)))
    print(f"  [{'OK ' if condicion else 'FALLA'}] {nombre}")
    if detalle:
        print(f"          {detalle}")
    return bool(condicion)


def seccion(titulo: str):
    print(f"\n{titulo}\n{'-' * len(titulo)}")


def _corrida_sintetica(dir_base: Path) -> Path:
    """Una corrida con lo justo: transcripcion + las ordenes de un guion."""
    d = dir_base / "corrida"
    d.mkdir(parents=True, exist_ok=True)
    palabras = [
        {"inicio": 0.30, "fin": 0.55, "texto": "No"},
        {"inicio": 0.58, "fin": 0.80, "texto": "es"},
        {"inicio": 0.83, "fin": 1.10, "texto": "que"},
        {"inicio": 1.13, "fin": 1.40, "texto": "no"},
        # Pausa de 0.6s: cierra bloque aunque solo lleve 4 palabras
        {"inicio": 2.00, "fin": 2.30, "texto": "te"},
        {"inicio": 2.33, "fin": 2.70, "texto": "guste"},
        {"inicio": 2.73, "fin": 3.20, "texto": "leer."},
        {"inicio": 3.50, "fin": 3.90, "texto": "Compites"},
        {"inicio": 3.93, "fin": 4.30, "texto": "con"},
        {"inicio": 4.33, "fin": 4.90, "texto": "una"},
    ]
    (d / "02_cortado.json").write_text(
        json.dumps({"palabras": palabras}, ensure_ascii=False), encoding="utf-8")
    (d / "guion.sfx.json").write_text(json.dumps({
        "sfx": [{"t": 2.782, "archivo": "pop.mp3", "volumen": 0.8, "razon": "guion_3"}],
        "candidatos": [],
    }), encoding="utf-8")
    (d / "guion.broll.json").write_text(json.dumps({
        "broll": [{"ini": 6.704, "fin": 14.929, "tag": "rendicion", "asset": "broll-manual:rendicion"}],
    }), encoding="utf-8")
    (d / "guion.animaciones.json").write_text(json.dumps({
        "animaciones": [{"nombre": "anim-apps", "ini": 2.782}],
    }), encoding="utf-8")
    (d / "guion.eventos.json").write_text(json.dumps({"eventos": []}), encoding="utf-8")
    (d / "guion.encuadre.json").write_text(json.dumps({
        "punch_ins": [], "planos_cerrados": [{"ini": 3.322, "fin": 14.929, "zoom": 1.22}],
    }), encoding="utf-8")
    (d / "10_guion-alineado.md").write_text(
        "| Beat | Tipo | Texto Guion | Estado | Inicio | Fin | Detalles |\n"
        "|---|---|---|---|---|---|---|\n"
        "| Beat 0 | `YO` | \"algo\" | **OMITIDO** | - | - | Frase no encontrada |\n"
        "| Beat 3 | `ANIM` | \"otra cosa\" | **OK** | 2.78s | 6.40s | conf 0.77 |\n"
        "| Beat 5 | `B-ROLL` | \"y otra\" | **OK** | 6.70s | 14.93s | conf 0.72 |\n",
        encoding="utf-8")
    return d


# ===========================================================================
# 1. Bloques de subtitulo: la MISMA funcion que el render
# ===========================================================================
def pruebas_bloques_subtitulo():
    seccion("1. Bloques de subtitulo (f14_tira <-> f3_subtitulos)")

    with tempfile.TemporaryDirectory() as tmp:
        d = _corrida_sintetica(Path(tmp))
        palabras = json.loads((d / "02_cortado.json").read_text(encoding="utf-8"))["palabras"]
        bloques = f14_tira.bloques_subtitulos(d)
        esperados = f3_subtitulos.agrupar_en_bloques(palabras)

        chk("mismo numero de bloques que agrupar_en_bloques",
            len(bloques) == len(esperados),
            f"tira {len(bloques)} vs f3_subtitulos {len(esperados)}")

        # El check que de verdad importa: no basta con que coincida el conteo,
        # tienen que ser LOS MISMOS cortes. Un agrupado propio que casualmente
        # diera 4 bloques distintos pasaria la prueba de arriba.
        iguales = all(
            abs(b["ini"] - round(g[0]["inicio"], 3)) < 1e-6
            and abs(b["fin"] - round(g[-1]["fin"], 3)) < 1e-6
            and b["texto"] == " ".join(p["texto"] for p in g)
            for b, g in zip(bloques, esperados)
        )
        chk("los cortes y el texto son identicos, no solo el conteo", iguales,
            " | ".join(f"{b['ini']}-{b['fin']} {b['texto']!r}" for b in bloques))

        # Los indices son la clave con la que generar_ass aplica correcciones.
        # Si se desalinean, corregir "leer" en el editor cambiaria otra palabra.
        planos = [i for b in bloques for i in b["indices"]]
        chk("los indices son la posicion GLOBAL de cada palabra, en orden y sin huecos",
            planos == list(range(len(palabras))),
            f"{planos}")
        chk("cada bloque trae sus palabras sueltas, ademas del texto unido",
            all(len(b["palabras"]) == len(b["indices"]) for b in bloques)
            and bloques[0]["palabras"] == ["No", "es", "que", "no"],
            f"primer bloque: {bloques[0]['palabras']}")

        # Coherencia de las constantes: el carril no puede prometer bloques de
        # 2-4 si config dice otra cosa.
        datos = f14_tira.datos_tira(d)
        chk("agrupado_sub expone los limites reales de config",
            datos["agrupado_sub"]["min"] == config.SUB_PALABRAS_POR_BLOQUE_MIN
            and datos["agrupado_sub"]["max"] == config.SUB_PALABRAS_POR_BLOQUE_MAX,
            f"{datos['agrupado_sub']} vs config {config.SUB_PALABRAS_POR_BLOQUE_MIN}-"
            f"{config.SUB_PALABRAS_POR_BLOQUE_MAX}")
        chk("ningun bloque pasa del maximo de palabras",
            all(len(b["indices"]) <= config.SUB_PALABRAS_POR_BLOQUE_MAX for b in bloques))


# ===========================================================================
# 2. Beats del guion e imanes (bloque C)
# ===========================================================================
def pruebas_beats():
    seccion("2. Beats del guion y puntos de iman")

    with tempfile.TemporaryDirectory() as tmp:
        d = _corrida_sintetica(Path(tmp))
        beats = f14_tira.beats_guion(d)
        tiempos = [b["t"] for b in beats]

        chk("los beats salen ordenados por tiempo", tiempos == sorted(tiempos), f"{tiempos}")

        # Deduplicado con la fuente PRECISA ganando: el reporte .md dice 6.70s y
        # guion.broll.json 6.704s del mismo beat. Quedarse con el del reporte
        # por ser 4 milesimas menor tirar+ia el dato exacto sin ninguna razon.
        chk("6.704 (json, 3 decimales) gana a 6.70 (reporte, 2 decimales)",
            6.704 in tiempos and 6.70 not in tiempos, f"{tiempos}")
        chk("2.782 (json) gana a 2.78 (reporte)",
            2.782 in tiempos and 2.78 not in tiempos)

        # Un beat que NO dejo artefacto (el fin del beat 3, que ninguna orden
        # json conoce) tiene que llegar igual desde el reporte: es un corte
        # editorial tan valido como los demas para el iman.
        chk("el fin del beat 3 (6.40s) llega desde el reporte, sin artefacto json",
            6.4 in tiempos, f"{tiempos}")
        chk("los tramos aportan su inicio Y su fin",
            3.322 in tiempos and 14.929 in tiempos, f"{tiempos}")

        imanes = f14_tira.puntos_iman(d, beats)
        chk("los bordes de palabra van ordenados y sin repetidos",
            imanes["palabras"] == sorted(set(imanes["palabras"])),
            f"{len(imanes['palabras'])} bordes")
        chk("cada palabra aporta su inicio y su fin",
            0.30 in imanes["palabras"] and 0.55 in imanes["palabras"]
            and 4.90 in imanes["palabras"])
        chk("los beats del iman son los mismos que los del carril",
            imanes["beats"] == tiempos)

    # Una corrida SIN guion (automatica) no tiene beats: el iman se queda solo
    # con los bordes de palabra en vez de reventar.
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "sin-guion"
        d.mkdir()
        (d / "02_cortado.json").write_text(
            json.dumps({"palabras": [{"inicio": 1.0, "fin": 1.5, "texto": "hola"}]}),
            encoding="utf-8")
        datos = f14_tira.datos_tira(d)
        chk("corrida sin --guion: 0 beats pero los bordes de palabra siguen",
            datos["beats"] == [] and datos["imanes"]["palabras"] == [1.0, 1.5],
            f"beats={datos['beats']} palabras={datos['imanes']['palabras']}")


# ===========================================================================
# 3. Robustez: un dato que falta no puede tumbar el editor
# ===========================================================================
def pruebas_robustez():
    seccion("3. Robustez de datos_tira")

    with tempfile.TemporaryDirectory() as tmp:
        vacia = Path(tmp) / "no-existe"
        datos = f14_tira.datos_tira(vacia)
        chk("una carpeta inexistente devuelve la estructura completa y vacia",
            datos["subtitulos"] == [] and datos["beats"] == []
            and datos["imanes"] == {"palabras": [], "beats": []}
            and len(datos["carriles"]) == 6)

        rota = Path(tmp) / "rota"
        rota.mkdir()
        (rota / "02_cortado.json").write_text("{esto no es JSON", encoding="utf-8")
        (rota / "guion.sfx.json").write_text("tampoco", encoding="utf-8")
        datos = f14_tira.datos_tira(rota)
        chk("un JSON corrupto no lanza: la tira sale vacia y el editor sigue",
            datos["subtitulos"] == [] and datos["beats"] == [])

        chk("las constantes viajan siempre, aunque no haya datos",
            datos["zoom"]["min"] == f14_tira.ZOOM_MIN
            and datos["zoom"]["max"] == f14_tira.ZOOM_MAX
            and datos["iman"]["tolerancia_px"] == f14_tira.IMAN_TOLERANCIA_PX,
            f"zoom {datos['zoom']} iman {datos['iman']}")
        chk("el zoom minimo es 1 (el video entero entra en la tira)",
            f14_tira.ZOOM_MIN == 1.0 and f14_tira.ZOOM_MAX > f14_tira.ZOOM_MIN
            and f14_tira.ZOOM_FACTOR > 1.0)

    # Los seis carriles del bloque A, en orden, y cuales se pueden arrastrar.
    ids = [c["id"] for c in f14_tira.CARRILES]
    chk("los seis carriles, en el orden de PLAN-TIRA.md",
        ids == ["voz", "subtitulos", "broll", "anim", "sfx", "musica"], f"{ids}")
    editables = [c["id"] for c in f14_tira.CARRILES if c["editable"]]
    chk("solo tres carriles se marcan editables (los que el bloque C arrastra)",
        editables == ["broll", "anim", "sfx"],
        "voz y subtitulos salen de la transcripcion; la musica cubre el video entero")


# ===========================================================================
# 4. Enganche con /datos y con la pagina del editor
# ===========================================================================
def pruebas_enganche():
    seccion("4. Enganche con el editor (f10 y f11)")

    fuente_f10 = (AQUI / "f10_editor_visual.py").read_text(encoding="utf-8")
    chk("f10.recolectar() expone el bloque `tira`",
        '"tira": f14_tira.datos_tira(dir_trabajo)' in fuente_f10)

    with tempfile.TemporaryDirectory() as tmp:
        d = _corrida_sintetica(Path(tmp))
        datos = f10.recolectar(d)
        chk("recolectar() sobre una corrida sin video devuelve la tira igual",
            "tira" in datos and len(datos["tira"]["subtitulos"]) > 0,
            f"{len(datos['tira']['subtitulos'])} bloques, {len(datos['tira']['beats'])} beats")
        # El carril de voz se dibuja con DATA.palabras, no con una copia: si un
        # dia dejaran de venir, la tira se quedaria muda sin decir por que.
        chk("las palabras que dibuja el carril de voz siguen en /datos",
            len(datos["palabras"]) == 10)

    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("el servidor sirve /tira.js y /tira.css",
        'ruta in ("/tira.js", "/tira.css")' in fuente_srv
        and 'Path(__file__).resolve().parent / "web"' in fuente_srv)
    chk("la pagina enlaza la hoja de estilo",
        '<link rel="stylesheet" href="/tira.css">' in fuente_srv)
    chk("la pagina carga tira.js como ultima linea antes de </body>",
        re.search(r'<script src="/tira\.js"></script>\s*</body>', fuente_srv) is not None)
    chk("el contenedor va justo despues de la pista de palabras",
        re.search(r'<div class="palabras" id="palabras"></div>\s*</div>\s*'
                  r'<div id="tiraCapas"></div>', fuente_srv) is not None)
    chk("cargar() inicializa la tira",
        "if (window.__tira) window.__tira.init(DATA);" in fuente_srv)
    chk("loop() mueve el cursor de la tira",
        "if (window.__tira) window.__tira.cursor(video.currentTime);" in fuente_srv)

    # El contrato de no-colision: la tira no puede haberse metido en el JS de
    # nadie. Si alguna de estas dos cosas aparece, es que se colo codigo de la
    # tira dentro de PAGINA en vez de en editor/web/tira.js.
    chk("nada del cuerpo de la tira vive dentro de f11_servidor.py",
        "tira-carril" not in fuente_srv and "tira-bloque" not in fuente_srv,
        "todo el JS y el CSS de la tira viven en editor/web/")

    js = (AQUI / "web" / "tira.js").read_text(encoding="utf-8")
    css = (AQUI / "web" / "tira.css").read_text(encoding="utf-8")
    chk("tira.js y tira.css existen y no estan vacios", len(js) > 2000 and len(css) > 500,
        f"tira.js {len(js)} chars, tira.css {len(css)} chars")
    chk("tira.js expone window.__tira con init y cursor",
        "window.__tira = API" in js and "init:" in js and "cursor:" in js)

    # El cursor de la tira NO puede usar la clase .playhead: actualizarUI() las
    # mueve todas por porcentaje de la duracion total, y con zoom la escala de
    # la tira ya no es esa. Compartir la clase clavaria el cursor donde no es.
    # Se mira el SELECTOR y la asignacion de clase, no la cadena suelta: el
    # comentario que explica esta misma decision nombra .playhead.
    css_sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    js_sin_comentarios = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js_sin_comentarios = re.sub(r"^\s*//.*$", "", js_sin_comentarios, flags=re.M)
    chk("el cursor de la tira usa clase propia, no .playhead",
        "tira-cursor" in js and "playhead" not in js_sin_comentarios
        and ".playhead" not in css_sin_comentarios)

    # Nada hardcodeado: los carriles salen de /datos, no de una lista propia en
    # el JS. Es el patron establecido (bloques 1, 2 y 3 de PLAN-MEJORAS).
    chk("el JS dibuja los carriles que manda /datos, no una lista propia",
        "T.carriles.map" in js and '"voz"' not in js.split("mapaPunto")[0])


# ===========================================================================
# 5. Zoom e iman (bloque C)
# ===========================================================================
def pruebas_zoom_iman():
    seccion("5. Zoom e iman (bloque C)")

    js = (AQUI / "web" / "tira.js").read_text(encoding="utf-8")

    chk("los limites de zoom y la tolerancia del iman se leen de /datos",
        "T.zoom.min" in js and "T.zoom.max" in js and "T.zoom.factor" in js
        and "T.iman.tolerancia_px" in js,
        "mismo patron que los picos de SFX y la zona segura: nada hardcodeado en el JS")

    # La tolerancia se mide en PANTALLA, no en segundos. Es lo que hace que al
    # acercar la ayuda se afine sola en vez de seguir pegando todo a medio
    # segundo cuando ya se ve el fotograma.
    chk("la tolerancia del iman se convierte de pixeles a segundos con el zoom",
        "tolerancia_px || 8) * segPorPx()" in js and "return w > 0 ? dur / w : 0;" in js)

    chk("el iman se puede soltar con Alt y con la casilla",
        "mv.altKey" in js and 'el("tiraIman")' in js and "imanActivo = chk.checked" in js)

    # Ctrl+rueda: sin Ctrl la rueda tiene que seguir desplazando la pagina, o
    # se vuelve imposible bajar por el editor con el raton sobre la tira.
    chk("la rueda solo hace zoom con Ctrl",
        "if (!ev.ctrlKey) return;" in js and "{ passive: false }" in js)
    chk("acercar mantiene quieto el instante bajo el cursor",
        "zoomAnclado" in js and "tAnclado" in js and "scroll.scrollLeft =" in js)

    # Mover un bloque ENTERO nunca cambia su duracion, asi que no puede
    # saltarse el tope del tramo recortado del clip (bloque 4 de PLAN-MEJORAS),
    # que es cosa de los tiradores de la pista de siempre.
    # Sin los comentarios: el que explica esta misma decision nombra
    # duracionMaximaClip para decir que NO hace falta llamarla.
    js_codigo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js_codigo = re.sub(r"^\s*//.*$", "", js_codigo, flags=re.M)
    chk("la tira mueve bloques enteros, no redimensiona",
        "obj.fin = t + largo" in js_codigo and "enc-tirador" not in js_codigo
        and "duracionMaximaClip" not in js_codigo,
        "moviendo entero la duracion no cambia, asi que el tope del tramo "
        "recortado del clip no se puede violar desde la tira")
    chk("el movimiento se frena en los bordes del video",
        "Math.min(dur - largo, propuesto)" in js)

    # Reusar moverAnimacion() en vez de replicar su clamp: si la tira y la
    # pista de animaciones movieran de dos maneras distintas, el mismo gesto
    # daria resultados distintos segun donde se hiciera.
    chk("las animaciones se mueven con moverAnimacion(), la funcion que ya existe",
        "moverAnimacion(obj, t)" in js)
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("moverAnimacion sigue existiendo en el editor y marca el flag",
        "function moverAnimacion(a, ini)" in fuente_srv
        and "animacionesModificado = true;" in fuente_srv)

    # Mover algo desde la tira tiene que marcarlo como manual: si no, el
    # cambio se ve en pantalla pero el re-render lo tira.
    chk("mover un SFX en la tira lo marca como editado a mano",
        "sfxModificado = true" in js)

    # Al soltar, las secciones de siempre tienen que enterarse: la tira NO las
    # sustituye, siguen siendo ellas las que mandan en la edicion fina.
    for fn in ("pintarSfx", "tablaSfx", "pintarAnimTimeline", "renderAnimGrid",
               "renderPipsLista", "pintarPipTimeline", "construirTimeline"):
        chk(f"al soltar se refresca {fn}()", f"{fn}();" in js.split("function refrescarPaneles")[-1])


# ===========================================================================
def main():
    print("=" * 60)
    print("  PRUEBAS DE LA TIRA DE CAPAS  (editor/PLAN-TIRA.md)")
    print("=" * 60)

    pruebas_bloques_subtitulo()
    pruebas_beats()
    pruebas_robustez()
    pruebas_enganche()
    pruebas_zoom_iman()

    fallos = [n for n, ok in _resultados if not ok]
    print("\n" + "=" * 60)
    if fallos:
        print(f"FALLAN {len(fallos)} DE {len(_resultados)} PRUEBAS:")
        for n in fallos:
            print(f"  - {n}")
        sys.exit(1)
    print(f"LAS {len(_resultados)} PRUEBAS PASAN")
    print("\nOjo: estas son de Python y NO ven un JavaScript roto.")
    print("Ademas hay que pasar:  node --check editor/web/tira.js")


if __name__ == "__main__":
    main()
