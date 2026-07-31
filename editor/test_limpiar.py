"""Pruebas de la limpieza de disco (f16_limpiar).

Por que existe. Este modulo BORRA archivos, asi que la prueba que de verdad
importa no es que libere espacio -- es que NO borre cuando no debe:

  · Si el video todavia no esta en salida/ de OneDrive, la carpeta de trabajo
    contiene el UNICO ejemplar que existe. Borrar los intermedios ahi no es
    liberar disco, es perder el video.
  · El corte crudo (02_cortado.mp4) es lo que hace que --reaplicar cueste
    segundos. No puede irse en la limpieza normal.
  · Los ajustes.*.json son la edicion a mano. Pesan 50 KB entre todos: borrarlos
    no libera nada y si borra el trabajo.

Uso:  python editor/test_limpiar.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import config
import f16_limpiar

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


def _corrida(base: Path, nombre: str) -> Path:
    """Una corrida con los pesos aproximados de una real."""
    d = base / nombre
    d.mkdir(parents=True, exist_ok=True)
    for archivo, kb in (("02_cortado.mp4", 48), ("07_FINAL.mp4", 29),
                        ("06_video.mp4", 29), ("07_PREVIEW.mp4", 9),
                        ("06_preview.mp4", 9), ("09_editor-visual.html", 7)):
        (d / archivo).write_bytes(b"x" * (kb * 1024))
    (d / "01_transcripcion.json").write_text(json.dumps({"palabras": []}), encoding="utf-8")
    (d / "ajustes.sfx.json").write_text("[]", encoding="utf-8")
    (d / "ajustes.hook.json").write_text("{}", encoding="utf-8")
    tmpg = d / "_tmp_guion"
    tmpg.mkdir(exist_ok=True)
    (tmpg / "pip_guion_1.mov").write_bytes(b"x" * (50 * 1024))
    ed = d / "_editor"
    ed.mkdir(exist_ok=True)
    (ed / "proxy_07_FINAL.mp4").write_bytes(b"x" * (2 * 1024))
    return d


def pruebas_guarda():
    seccion("1. La guarda: no borrar lo que es el unico ejemplar")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pub = tmp / "publicados"
        pub.mkdir()
        salida = tmp / "salida"
        salida.mkdir()
        orig_pub, orig_sal = config.DIR_PUBLICADOS, config.DIR_SALIDA
        config.DIR_PUBLICADOS, config.DIR_SALIDA = pub, salida
        try:
            d = _corrida(salida, "sin-publicar")
            antes = len(list(d.iterdir()))
            r = f16_limpiar.limpiar(d)
            chk("una corrida SIN publicar no se toca", not r["ok"] and r["liberado"] == 0
                and len(list(d.iterdir())) == antes,
                r["motivo"])
            chk("y el motivo explica que hay que renderizar primero",
                "OneDrive" in r["motivo"] and "renderiz" in r["motivo"].lower())
            chk("el 07_FINAL.mp4 sigue ahi", (d / "07_FINAL.mp4").exists(),
                "es el unico ejemplar que existe mientras no este publicado")

            # Con el video publicado, la misma llamada si limpia.
            (pub / "sin-publicar.mp4").write_bytes(b"x" * 1024)
            r2 = f16_limpiar.limpiar(d)
            chk("con el video ya publicado, si limpia", r2["ok"] and r2["liberado"] > 0,
                f"{r2['liberado'] / 1048576:.1f} MB liberados")

            # --forzar existe, pero es una decision explicita.
            d2 = _corrida(salida, "otra-sin-publicar")
            r3 = f16_limpiar.limpiar(d2, forzar=True)
            chk("--forzar salta la guarda (para casos raros, a conciencia)",
                r3["ok"] and r3["liberado"] > 0)
        finally:
            config.DIR_PUBLICADOS, config.DIR_SALIDA = orig_pub, orig_sal


def pruebas_que_conserva():
    seccion("2. Que se conserva")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pub = tmp / "publicados"; pub.mkdir()
        salida = tmp / "salida"; salida.mkdir()
        orig_pub, orig_sal = config.DIR_PUBLICADOS, config.DIR_SALIDA
        config.DIR_PUBLICADOS, config.DIR_SALIDA = pub, salida
        try:
            d = _corrida(salida, "Guion-7")
            (pub / "Guion-7.mp4").write_bytes(b"x" * 1024)
            r = f16_limpiar.limpiar(d)

            chk("el corte crudo se conserva: es lo que hace barato --reaplicar",
                (d / "02_cortado.mp4").exists())
            chk("el video final de trabajo se conserva",
                (d / "07_FINAL.mp4").exists(),
                "sin el, el editor cae al corte crudo y enseña el video sin "
                "subtitulos, sin B-rolls y sin encuadre")
            chk("los ajustes a mano se conservan",
                (d / "ajustes.sfx.json").exists() and (d / "ajustes.hook.json").exists(),
                "pesan 50 KB entre todos: borrarlos no libera disco y si borra el trabajo")
            chk("la transcripcion se conserva", (d / "01_transcripcion.json").exists())
            chk("el video PUBLICADO en OneDrive no se toca nunca",
                (pub / "Guion-7.mp4").exists(), "es el que se sube a las redes")

            chk("se borra el compuesto sin audio", not (d / "06_video.mp4").exists())
            chk("se borran las previsualizaciones",
                not (d / "07_PREVIEW.mp4").exists() and not (d / "06_preview.mp4").exists())
            chk("se borran los .mov de los insertos, ya quemados en el video",
                not (d / "_tmp_guion").exists())
            chk("se borra el proxy del reproductor (se regenera solo)",
                not (d / "_editor").exists())
            chk("se borra el editor v1, sustituido por el servidor",
                not (d / "09_editor-visual.html").exists())

            # ~104 KB de los 183 KB de la corrida sintetica.
            chk("libera la mayor parte del peso", r["liberado"] > 100 * 1024,
                f"{r['liberado'] / 1024:.0f} KB de {sum(f.stat().st_size for f in salida.rglob('*') if f.is_file()) / 1024 + r['liberado'] / 1024:.0f} KB")

            # --a-fondo si se lleva el final y el crudo.
            d3 = _corrida(salida, "a-fondo")
            (pub / "a-fondo.mp4").write_bytes(b"x" * 1024)
            f16_limpiar.limpiar(d3, a_fondo=True)
            chk("--a-fondo si borra el final y el corte crudo",
                not (d3 / "07_FINAL.mp4").exists() and not (d3 / "02_cortado.mp4").exists())
            chk("pero ni con --a-fondo toca los ajustes",
                (d3 / "ajustes.sfx.json").exists())
        finally:
            config.DIR_PUBLICADOS, config.DIR_SALIDA = orig_pub, orig_sal


def pruebas_publicados():
    seccion("3. Detectar el video publicado (con sus versiones)")

    with tempfile.TemporaryDirectory() as tmp:
        pub = Path(tmp)
        orig = config.DIR_PUBLICADOS
        config.DIR_PUBLICADOS = pub
        try:
            chk("sin nada publicado, no encuentra nada",
                f16_limpiar.publicados_de("Guion-7") == [])

            (pub / "Guion-7.mp4").write_bytes(b"x")
            (pub / "Guion-7_v2.mp4").write_bytes(b"x")
            (pub / "Guion-7_v3.mp4").write_bytes(b"x")
            n = len(f16_limpiar.publicados_de("Guion-7"))
            chk("encuentra el original y sus versiones _v2/_v3", n == 3,
                "editor._ruta_versionada publica asi cuando se re-renderiza")

            # Un nombre que EMPIEZA igual no es la misma corrida: limpiar
            # "Guion-7" mirando "Guion-7-hook.mp4" borraria una corrida cuyo
            # video no existe.
            (pub / "Guion-7-hook.mp4").write_bytes(b"x")
            (pub / "Guion-7-automatico.mp4").write_bytes(b"x")
            chk("NO confunde 'Guion-7-hook' con una version de 'Guion-7'",
                len(f16_limpiar.publicados_de("Guion-7")) == 3,
                "si contara los prefijos, limpiaria corridas sin publicar")
            chk("y encuentra la suya propia",
                len(f16_limpiar.publicados_de("Guion-7-hook")) == 1)
        finally:
            config.DIR_PUBLICADOS = orig


def pruebas_cableado():
    seccion("4. Cableado con el editor")

    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("existe el endpoint /limpiar", 'partes.path == "/limpiar"' in fuente_srv)
    chk("el endpoint sabe solo mirar, sin borrar",
        'datos.get("solo_ver")' in fuente_srv and "f16_limpiar.calcular" in fuente_srv,
        "el boton pregunta primero que se llevaria y lo enseña")
    chk("hay boton en el editor", 'id="btnListoPublicar"' in fuente_srv)
    chk("el boton pide confirmacion con la lista de lo que borra",
        "confirm(" in fuente_srv and "SE CONSERVAN" in fuente_srv,
        "un boton que borra 200 MB sin decir que se lleva no se puede pulsar con confianza")
    chk("si no esta publicado, el boton lo dice y no llama a borrar",
        "!plan.esta_publicado" in fuente_srv)

    # Que la limpieza no se lleve por delante nada que otro modulo lea despues.
    fuente_f10 = (AQUI / "f10_editor_visual.py").read_text(encoding="utf-8")
    chk("f10 sigue pudiendo caer a 02_cortado.mp4, que la limpieza conserva",
        '"02_cortado.mp4"' in fuente_f10
        and "02_cortado.mp4" not in f16_limpiar.ARCHIVOS_PESADOS)
    chk("ARCHIVOS_PESADOS no incluye ningun ajustes.*.json ni la transcripcion",
        not any("ajustes" in a or "transcripcion" in a for a in f16_limpiar.ARCHIVOS_PESADOS))


def pruebas_compilan():
    seccion("5. Todos los modulos COMPILAN (no solo parsean)")

    # Esta prueba nace de un fallo real de esta misma sesion. El endpoint
    # /limpiar leia DIR_TRABAJO dentro de do_POST, y mas abajo esa funcion
    # declara `global DIR_TRABAJO` (en /cambiar-proyecto). Python lo prohibe:
    #
    #     SyntaxError: name 'DIR_TRABAJO' is used prior to global declaration
    #
    # Lo caro es COMO se manifiesta: `ast.parse`, que es lo que usan varias
    # pruebas para leer el fuente, NO lo detecta -- el arbol es sintacticamente
    # valido y el error sale del analisis de ambitos, que solo hace compile().
    # Asi que las suites pasaban en verde y el servidor moria al arrancar, sin
    # mas rastro que una consola que ya se habia cerrado. La otra sesion tropezo
    # con lo mismo en el bloque de silencios y lo dejo escrito; esta prueba
    # convierte ese comentario en algo que falla solo.
    fallos = []
    for py in sorted((AQUI).glob("*.py")):
        try:
            compile(py.read_text(encoding="utf-8"), str(py), "exec")
        except SyntaxError as e:
            fallos.append(f"{py.name}:{e.lineno} {e.msg}")
    chk("los .py del editor compilan, no solo parsean",
        not fallos, "\n          ".join(fallos) if fallos
        else f"{len(list(AQUI.glob('*.py')))} modulos compilados con compile(), "
             "que si ve los errores de ambito que ast.parse deja pasar")

    # Y que la leccion quede escrita donde toca: f16_limpiar SI recibe
    # DIR_TRABAJO, pero desde una funcion de modulo (_limpiar_corrida), nunca
    # desde dentro de do_POST, que es donde esta la declaracion `global`.
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    cuerpo_post = fuente_srv.split("def do_POST(self):", 1)[-1].split("\ndef ", 1)[0]
    # Sin los comentarios: el que EXPLICA esta decision nombra f16_limpiar, y
    # contarlo como uso hacia fallar la prueba por su propia documentacion.
    codigo_post = "\n".join(l for l in cuerpo_post.splitlines()
                            if not l.strip().startswith("#"))
    chk("el endpoint no lee DIR_TRABAJO dentro de do_POST",
        "_limpiar_corrida" in fuente_srv and "f16_limpiar" not in codigo_post,
        "se pasa por una funcion de modulo, como ya hace _datos_silencios_actuales")


def main():
    print("=" * 60)
    print("  PRUEBAS DE LA LIMPIEZA DE DISCO (f16_limpiar)")
    print("=" * 60)
    pruebas_guarda()
    pruebas_que_conserva()
    pruebas_publicados()
    pruebas_cableado()
    pruebas_compilan()

    fallos = [n for n, ok in _resultados if not ok]
    print("\n" + "=" * 60)
    if fallos:
        print(f"FALLAN {len(fallos)} DE {len(_resultados)} PRUEBAS:")
        for n in fallos:
            print(f"  - {n}")
        sys.exit(1)
    print(f"LAS {len(_resultados)} PRUEBAS PASAN")


if __name__ == "__main__":
    main()
