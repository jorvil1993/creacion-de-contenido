"""Pruebas del editor de silencios (Bloque B): ver y deshacer el corte.

Por que existe. Restaurar un silencio ALARGA el video cortado y corre todo lo
que viene detras: palabras, subtitulos, SFX, overlays, animaciones y la curva
de encuadre. Es la clase de fallo que no da error — el render sale, se sube, y
la unica pista es que "los sonidos ya no pegan". La prueba central de este
archivo (seccion 2) corta un clip de verdad con ffmpeg, restaura un tramo, y
comprueba que una palabra concreta y un SFX concreto siguen cayendo sobre el
MISMO instante del habla que antes.

Uso:  python editor/test_silencios.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import config
import f2_cortar
import f15_silencios

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


def _clip_con_silencios(destino: Path, tramos: list, segs: float):
    """Clip de prueba con silencio real en los tramos pedidos."""
    filtros = "+".join(f"between(t,{a},{b})" for a, b in tramos) or "0"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", f"testsrc=size=320x568:rate=30:d={segs}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={segs}:sample_rate=48000",
           "-af", f"volume=0:enable='{filtros}'",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", str(destino)]
    subprocess.run(cmd, check=True, capture_output=True)
    return destino


# ===========================================================================
# 1. Aritmetica del remapeo
# ===========================================================================

def pruebas_mapeo():
    seccion("1. Ida y vuelta entre la grabacion y el video cortado")

    intervalos = [{"inicio": 0.0, "fin": 2.0},
                  {"inicio": 5.0, "fin": 8.0},
                  {"inicio": 10.0, "fin": 12.5}]

    # --- la inversa es EXACTA -----------------------------------------------
    # Si no lo fuera, cada re-corte arrastraria unas milesimas y los ajustes se
    # irian corriendo solos a base de tocar silencios.
    peor, t = 0.0, 0.0
    fin = sum(iv["fin"] - iv["inicio"] for iv in intervalos)
    while t <= fin:
        vuelta = f2_cortar.mapear_a_nueva_linea(
            f2_cortar.mapear_a_original(t, intervalos), intervalos)
        peor = max(peor, abs(vuelta - t))
        t += 0.01
    chk("nueva -> original -> nueva devuelve el mismo instante",
        peor < 1e-6, f"peor error en todo el rango: {peor*1000:.4f} ms")

    # --- puntos conocidos a mano -------------------------------------------
    chk("el principio del segundo tramo conservado cae donde toca",
        abs(f2_cortar.mapear_a_original(2.0, intervalos) - 2.0) < 1e-6
        and abs(f2_cortar.mapear_a_original(2.5, intervalos) - 5.5) < 1e-6,
        "2.5s del cortado = 5.5s del original (2s del primer tramo + 0.5 del segundo)")

    chk("mas alla del final se acota al ultimo instante conservado",
        abs(f2_cortar.mapear_a_original(99.0, intervalos) - 12.5) < 1e-6)

    chk("una lista de intervalos vacia no revienta",
        f2_cortar.mapear_a_original(3.0, []) == 0.0)

    # --- composicion: restaurar un tramo ------------------------------------
    nuevos = [{"inicio": 0.0, "fin": 8.0}, {"inicio": 10.0, "fin": 12.5}]
    chk("restaurar el hueco 2-5 corre 3s todo lo que venia detras",
        abs(f15_silencios.remapear_tiempo(2.5, intervalos, nuevos) - 5.5) < 1e-6,
        "2.5s -> 5.5s: el ajuste sigue sobre el mismo fotograma de la grabacion")

    chk("lo anterior al tramo restaurado NO se mueve",
        abs(f15_silencios.remapear_tiempo(1.0, intervalos, nuevos) - 1.0) < 1e-6)


# ===========================================================================
# 2. LA PRUEBA CENTRAL: cortar de verdad y comprobar que nada se desfasa
# ===========================================================================

def pruebas_sin_desfase():
    seccion("2. Restaurar un tramo NO desfasa las palabras ni los SFX")

    tmp = Path(tempfile.mkdtemp())
    dur = 20.0
    # Dos silencios largos de verdad en el audio, en 3-7s y 12-15s.
    clip = _clip_con_silencios(tmp / "grab.mp4", [(3.0, 7.0), (12.0, 15.0)], dur)

    # Transcripcion sintetica: una palabra por segundo hablado, mas los dos
    # silencios que el detector va a encontrar.
    palabras = [{"texto": f"p{int(t)}", "inicio": float(t), "fin": t + 0.5, "confianza": 0.9}
                for t in list(range(0, 3)) + list(range(7, 12)) + list(range(15, 20))]
    datos_t = {
        "fuente": str(clip), "idioma": "es", "modelo": "test",
        "palabras": palabras,
        "segmentos": [{"inicio": 0.0, "fin": 2.5, "texto": "p0 p1 p2"},
                      {"inicio": 7.0, "fin": 11.5, "texto": "p7 p8 p9 p10 p11"},
                      {"inicio": 15.0, "fin": 19.5, "texto": "p15 p16 p17 p18 p19"}],
        "silencios": [{"inicio": 3.0, "fin": 7.0, "duracion": 4.0},
                      {"inicio": 12.0, "fin": 15.0, "duracion": 3.0}],
        "texto_completo": " ".join(p["texto"] for p in palabras),
    }
    f_trans = tmp / "01_transcripcion.json"
    f_trans.write_text(json.dumps(datos_t, ensure_ascii=False), encoding="utf-8")

    def cortar(dir_dest: Path, ajustes: Path = None):
        dir_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(f_trans, dir_dest / "01_transcripcion.json")
        cmd = [sys.executable, str(AQUI / "f2_cortar.py"), str(dir_dest / "01_transcripcion.json"),
               str(clip), "--salida", str(dir_dest / "02_cortado.mp4")]
        if ajustes:
            cmd += ["--silencios", str(ajustes)]
        # `errors="replace"`: f2_cortar imprime acentos y la consola de Windows
        # los emite en cp1252. Sin esto el hilo lector de subprocess revienta
        # con UnicodeDecodeError y el fallo se lee como si hubiera fallado el
        # corte, que es otra cosa completamente distinta.
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-2000:])
            raise RuntimeError("f2_cortar fallo")
        return json.loads((dir_dest / "02_cortado.json").read_text(encoding="utf-8"))

    d1 = tmp / "corrida"
    antes = cortar(d1)
    chk("el corte automatico se lleva los dos silencios",
        len(antes["cortes_aplicados"]) == 2,
        f"{len(antes['cortes_aplicados'])} cortes: "
        + ", ".join(f"{c['inicio']:.1f}-{c['fin']:.1f}" for c in antes["cortes_aplicados"]))

    cat = f15_silencios.catalogo(d1)
    chk("el catalogo enumera los dos tramos, con id estable",
        len(cat["tramos"]) == 2 and all(t["id"].startswith("silencio-") for t in cat["tramos"]),
        ", ".join(t["id"] for t in cat["tramos"]))

    # --- ajustes en la linea de tiempo VIEJA --------------------------------
    # Un SFX sobre la palabra p8 y un B-roll sobre p16: dos puntos a cada lado
    # del tramo que se va a restaurar.
    pal_antes = {p["texto"]: p for p in antes["palabras"]}
    t_sfx = pal_antes["p8"]["inicio"]
    t_broll_ini = pal_antes["p16"]["inicio"]
    (d1 / "ajustes.sfx.json").write_text(
        json.dumps([{"t": t_sfx, "archivo": "pop.mp3", "volumen": 0.8, "razon": "prueba"}]),
        encoding="utf-8")
    (d1 / "ajustes.broll.json").write_text(
        json.dumps({"broll": [{"ini": t_broll_ini, "fin": t_broll_ini + 1.5,
                               "x": 0, "y": 0, "tipo": "broll", "asset": "x"}]}),
        encoding="utf-8")

    # --- restaurar el PRIMER silencio ---------------------------------------
    id_primero = cat["tramos"][0]["id"]
    f_aj = d1 / "ajustes.silencios.json"
    f_aj.write_text(json.dumps({"cortes": {id_primero: {"activo": False}}}), encoding="utf-8")

    iv_viejos = antes["intervalos_conservados_original"]
    despues = cortar(d1, f_aj)
    iv_nuevos = despues["intervalos_conservados_original"]

    chk("restaurar un tramo alarga el video",
        despues["duracion_resultante_s"] > antes["duracion_resultante_s"],
        f"{antes['duracion_resultante_s']}s -> {despues['duracion_resultante_s']}s")

    chk("el tramo restaurado ya no se corta",
        len(despues["cortes_aplicados"]) == 1)

    res = f15_silencios.remapear_ajustes(d1, iv_viejos, iv_nuevos)

    # === LO QUE DE VERDAD IMPORTA ==========================================
    # La palabra p8 esta en otro segundo del video nuevo. El SFX tiene que
    # haberse movido EXACTAMENTE lo mismo. Si se remapeara mal, seguiria en su
    # sitio de antes: un numero perfectamente creible, sobre otra palabra.
    pal_despues = {p["texto"]: p for p in despues["palabras"]}
    sfx_nuevo = json.loads((d1 / "ajustes.sfx.json").read_text(encoding="utf-8"))[0]["t"]
    chk("el SFX sigue cayendo sobre la MISMA palabra tras restaurar",
        abs(sfx_nuevo - pal_despues["p8"]["inicio"]) < 0.05,
        f"p8 paso de {t_sfx:.2f}s a {pal_despues['p8']['inicio']:.2f}s; "
        f"el SFX paso de {t_sfx:.2f}s a {sfx_nuevo:.2f}s")

    chk("el SFX se movio (la prueba no pasa por no haber hecho nada)",
        abs(sfx_nuevo - t_sfx) > 0.5,
        f"se corrio {sfx_nuevo - t_sfx:.2f}s, que es lo que dura el tramo restaurado")

    broll = json.loads((d1 / "ajustes.broll.json").read_text(encoding="utf-8"))["broll"][0]
    chk("el B-roll sigue sobre su palabra y conserva su duracion",
        abs(broll["ini"] - pal_despues["p16"]["inicio"]) < 0.05
        and abs((broll["fin"] - broll["ini"]) - 1.5) < 0.02,
        f"[{broll['ini']:.2f}-{broll['fin']:.2f}] dur {broll['fin']-broll['ini']:.2f}s")

    # --- la copia de seguridad ---------------------------------------------
    chk("el remapeo deja un .previo antes de pisar cada ajuste",
        (d1 / "ajustes.sfx.json.previo").exists()
        and json.loads((d1 / "ajustes.sfx.json.previo").read_text(encoding="utf-8"))[0]["t"] == t_sfx,
        "sin respaldo, un remapeo mal calculado no se podria deshacer")

    chk("remapear informa de que archivos toco",
        set(res["cambiados"]) >= {"ajustes.sfx.json", "ajustes.broll.json"},
        f"cambiados: {res['cambiados']}")

    # --- volver a cortarlo: el catalogo no pierde el tramo restaurado -------
    # Si el catalogo saliera de `cortes_aplicados`, el tramo que se acaba de
    # restaurar habria desaparecido de la lista y no habria forma de volver a
    # cortarlo: el bloque solo funcionaria una vez.
    cat2 = f15_silencios.catalogo(d1)
    chk("el tramo restaurado SIGUE en el catalogo, marcado como restaurado",
        len(cat2["tramos"]) == 2
        and any(t["id"] == id_primero and not t["activo"] for t in cat2["tramos"]),
        "el catalogo se recalcula de la transcripcion, no de los cortes aplicados")

    f_aj.write_text(json.dumps({"cortes": {}}), encoding="utf-8")
    otra_vez = cortar(d1, f_aj)
    chk("se puede volver a cortar lo que se habia restaurado",
        len(otra_vez["cortes_aplicados"]) == 2
        and abs(otra_vez["duracion_resultante_s"] - antes["duracion_resultante_s"]) < 0.1,
        f"vuelve a {otra_vez['duracion_resultante_s']}s "
        f"(el corte original daba {antes['duracion_resultante_s']}s)")

    shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 3. Avisos: lo que no se puede remapear con certeza
# ===========================================================================

def pruebas_avisos():
    seccion("3. Lo ambiguo se avisa, no se adivina")

    tmp = Path(tempfile.mkdtemp())
    viejos = [{"inicio": 0.0, "fin": 2.0}, {"inicio": 5.0, "fin": 10.0}]
    nuevos = [{"inicio": 0.0, "fin": 10.0}]          # se restaura el hueco 2-5

    # Un evento que ABARCA la costura: de 1.5s a 2.5s en la linea vieja, o sea
    # de 1.5s a 5.5s del original. Al restaurar el hueco pasaria a durar 4s.
    (tmp / "ajustes.broll.json").write_text(
        json.dumps({"broll": [{"ini": 1.5, "fin": 2.5, "tipo": "broll", "asset": "x"}]}),
        encoding="utf-8")
    res = f15_silencios.remapear_ajustes(tmp, viejos, nuevos)

    ev = json.loads((tmp / "ajustes.broll.json").read_text(encoding="utf-8"))["broll"][0]
    chk("un evento que cruza el tramo restaurado CONSERVA su duracion",
        abs((ev["fin"] - ev["ini"]) - 1.0) < 1e-6,
        f"[{ev['ini']}-{ev['fin']}]: estirarlo lo habria dejado en 4s, un plano fijo")

    chk("y ademas se AVISA de ese caso",
        any(a["tipo"] == "cruza-tramo" for a in res["avisos"]),
        "; ".join(a["detalle"] for a in res["avisos"]) or "(ningun aviso)")

    # Un evento que NO cruza nada no debe generar ruido.
    (tmp / "ajustes.sfx.json").write_text(
        json.dumps([{"t": 6.0, "archivo": "pop.mp3", "volumen": 0.8, "razon": "x"}]),
        encoding="utf-8")
    res2 = f15_silencios.remapear_ajustes(tmp, viejos, nuevos)
    chk("un ajuste que no cruza nada no genera avisos",
        not any(a["archivo"] == "ajustes.sfx.json" for a in res2["avisos"]),
        "avisar de todo seria igual de inutil que no avisar de nada")

    # Un evento que se pasa del final del video nuevo.
    cortos = [{"inicio": 0.0, "fin": 3.0}]
    (tmp / "ajustes.hookcta.json").write_text(
        json.dumps({"hook_cta": [{"tipo": "cta", "ini": 8.0, "fin": 9.5}]}), encoding="utf-8")
    res3 = f15_silencios.remapear_ajustes(tmp, viejos, cortos)
    chk("un ajuste que queda mas alla del final se acorta Y se avisa",
        any(a["tipo"] == "fuera-de-rango" for a in res3["avisos"]),
        "; ".join(a["detalle"] for a in res3["avisos"] if a["tipo"] == "fuera-de-rango"))

    # La musica NO se remapea: su inicio_s es un offset dentro de la pista.
    chk("ajustes.musica.json queda FUERA de la tabla de remapeo",
        "ajustes.musica.json" not in f15_silencios.CAMPOS_TIEMPO,
        "su inicio_s es un desplazamiento dentro de la cancion, no un segundo del video")

    # Los avisos sobreviven al cierre del editor.
    f15_silencios.guardar_avisos(tmp, res["avisos"])
    chk("los avisos se guardan en disco para que el editor los enseñe",
        len(f15_silencios.leer_avisos(tmp)) == len(res["avisos"]),
        "el remapeo ocurre durante el render, con el editor cerrado")

    shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 4. Seleccion, topes y estado guardado
# ===========================================================================

def pruebas_seleccion():
    seccion("4. Que tramos se cortan: seleccion, topes y persistencia")

    tmp = Path(tempfile.mkdtemp())
    cortes = [
        {"inicio": 1.0, "fin": 3.0, "razon": "silencio de 2.30s",
         "limite_inicio": 0.85, "limite_fin": 3.15},
        {"inicio": 8.0, "fin": 8.3, "razon": "muletilla 'eh'"},
    ]
    f = tmp / "aj.json"

    f.write_text(json.dumps({"cortes": {}}), encoding="utf-8")
    aplicar, fuera = f15_silencios.aplicar_seleccion(cortes, f)
    chk("sin nada elegido se cortan todos, como siempre",
        len(aplicar) == 2 and not fuera)

    chk("un archivo que no existe tampoco cambia nada",
        len(f15_silencios.aplicar_seleccion(cortes, tmp / "no-existe.json")[0]) == 2)

    f.write_text(json.dumps({"cortes": {"silencio-0.850": {"activo": False}}}), encoding="utf-8")
    aplicar, fuera = f15_silencios.aplicar_seleccion(cortes, f)
    chk("desactivar un tramo lo saca de la lista de cortes",
        len(aplicar) == 1 and len(fuera) == 1 and fuera[0]["inicio"] == 1.0)

    # --- el tope: no se puede cortar MAS de lo detectado --------------------
    # Este editor existe para devolver metraje, no para quitarlo: dejar que el
    # tirador pase del silencio seria empezar a llevarse habla.
    f.write_text(json.dumps({"cortes": {"silencio-0.850": {"inicio": 0.0, "fin": 99.0}}}),
                 encoding="utf-8")
    aplicar, _ = f15_silencios.aplicar_seleccion(cortes, f)
    chk("los tiradores no pueden pasarse del silencio detectado",
        abs(aplicar[0]["inicio"] - 0.85) < 1e-6 and abs(aplicar[0]["fin"] - 3.15) < 1e-6,
        f"pedido 0.0-99.0, aplicado {aplicar[0]['inicio']}-{aplicar[0]['fin']}")

    f.write_text(json.dumps({"cortes": {"silencio-0.850": {"inicio": 1.5, "fin": 2.5}}}),
                 encoding="utf-8")
    aplicar, _ = f15_silencios.aplicar_seleccion(cortes, f)
    chk("estrechar un corte deja mas aire a los lados",
        abs(aplicar[0]["inicio"] - 1.5) < 1e-6 and abs(aplicar[0]["fin"] - 2.5) < 1e-6)

    f.write_text(json.dumps({"cortes": {"silencio-0.850": {"inicio": 2.0, "fin": 2.0}}}),
                 encoding="utf-8")
    aplicar, fuera = f15_silencios.aplicar_seleccion(cortes, f)
    chk("encoger un corte hasta cero equivale a restaurarlo",
        len(aplicar) == 1 and len(fuera) == 1)

    f.write_text("{ esto no es json", encoding="utf-8")
    chk("un archivo de ajustes corrupto no rompe el corte",
        len(f15_silencios.aplicar_seleccion(cortes, f)[0]) == 2,
        "mejor cortar como siempre que dejar el pipeline sin poder correr")

    # --- EL BOM DE WINDOWS --------------------------------------------------
    # Bug real encontrado en la prueba de punta a punta: PowerShell `Out-File
    # -Encoding utf8` (y el Bloc de notas) escriben BOM, `utf-8` a secas
    # revienta al leerlo, y el archivo se tomaba por vacio. El re-corte se
    # saltaba EN SILENCIO: el video salia con la duracion de siempre y lo
    # elegido en el editor desaparecia sin un solo mensaje.
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        {"cortes": {"silencio-0.850": {"activo": False}}}).encode("utf-8"))
    aplicar, fuera = f15_silencios.aplicar_seleccion(cortes, f)
    chk("un JSON con BOM de Windows se lee igual que uno sin BOM",
        len(aplicar) == 1 and len(fuera) == 1,
        "con utf-8 a secas el archivo se leia vacio y el re-corte se saltaba en silencio")

    shutil.copy(f, tmp / "ajustes.silencios.json")
    chk("hay_cambios tambien tolera el BOM",
        f15_silencios.hay_cambios(tmp),
        "es la condicion que decide si se vuelve a cortar: si miente, no se corta nada")

    # --- hay_cambios ---------------------------------------------------------
    (tmp / "ajustes.silencios.json").write_text(json.dumps({"cortes": {}}), encoding="utf-8")
    chk("un estado vacio NO cuenta como cambio",
        not f15_silencios.hay_cambios(tmp),
        "si contara, cada render normal volveria a cortar la grabacion entera para nada")

    (tmp / "ajustes.silencios.json").write_text(
        json.dumps({"cortes": {"silencio-0.850": {"activo": False}}}), encoding="utf-8")
    chk("un tramo desactivado SI cuenta como cambio", f15_silencios.hay_cambios(tmp))

    # --- identificadores ----------------------------------------------------
    chk("el id de un corte no depende de los limites ajustados a mano",
        f15_silencios.id_de_corte({"inicio": 9.9, "limite_inicio": 1.0,
                                   "razon": "silencio de 2.30s"}) == "silencio-1.000",
        "si dependiera, mover un tirador desharia la eleccion guardada")

    # --- EL ID CUELGA DEL SILENCIO, NO DEL CORTE ---------------------------
    # Bug real encontrado en la prueba de punta a punta. El corte del silencio
    # inicial depende de `hooksegs` del panel: con 0 va de 0.15 a 7.75, con 3
    # va de 0.00 a 4.90. Colgando el id del corte, cambiar ese campo dejaba la
    # eleccion guardada apuntando a un tramo inexistente y el silencio
    # restaurado volvia a cortarse EN SILENCIO.
    sin_hook = {"inicio": 0.15, "fin": 7.754, "razon": "silencio de 7.90s",
                "limite_inicio": 0.0, "limite_fin": 7.904}
    con_hook = {"inicio": 0.0, "fin": 4.904,
                "razon": "silencio inicial de 7.90s (se conservan 3.00s de hook fisico)",
                "limite_inicio": 0.0, "limite_fin": 7.904}
    chk("el mismo silencio da el MISMO id con y sin hook fisico",
        f15_silencios.id_de_corte(sin_hook) == f15_silencios.id_de_corte(con_hook)
        == "silencio-0.000",
        f"sin hooksegs: {f15_silencios.id_de_corte(sin_hook)} · "
        f"con hooksegs=3: {f15_silencios.id_de_corte(con_hook)}")

    chk("una muletilla, que no tiene silencio de origen, sigue teniendo id",
        f15_silencios.id_de_corte({"inicio": 30.077, "fin": 30.34,
                                   "razon": "muletilla 'nada'"}) == "muletilla-30.077")

    chk("cada clase de corte tiene su propio tipo",
        (f15_silencios.tipo_de_corte("muletilla 'eh'") == "muletilla"
         and f15_silencios.tipo_de_corte("toma repetida (similitud 0.9)") == "toma-repetida"
         and f15_silencios.tipo_de_corte("conector aislado 'y'") == "conector"))

    shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 5. Cableado: pipeline, servidor e interfaz
# ===========================================================================

def pruebas_cableado():
    seccion("5. Cableado con el pipeline y el editor")

    fuente_editor = (AQUI / "editor.py").read_text(encoding="utf-8")
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    fuente_f10 = (AQUI / "f10_editor_visual.py").read_text(encoding="utf-8")
    fuente_f15 = (AQUI / "f15_silencios.py").read_text(encoding="utf-8")
    fuente_js = (AQUI / "web" / "silencios.js").read_text(encoding="utf-8")
    fuente_f2 = (AQUI / "f2_cortar.py").read_text(encoding="utf-8")

    chk("editor.py acepta --silencios", "--silencios" in fuente_editor)
    chk("f2_cortar.py acepta --silencios", '"--silencios"' in fuente_f2)

    # --- EL PLAN DE RETENCION SE REHACE ------------------------------------
    # 03_retencion.plan.json indexa el track del rostro y la curva de zoom por
    # segundo del video CORTADO. Reusarlo tras mover un corte es el fallo
    # silencioso de este bloque: el video sale, con el zoom medio segundo tarde.
    chk("un re-corte obliga a rehacer el analisis de retencion",
        "if not args.reaplicar or recorte_rehecho:" in fuente_editor,
        "el plan de encuadre esta indexado por segundo del video cortado")

    chk("editor.py remapea los ajustes despues de re-cortar",
        "remapear_ajustes" in fuente_editor and "guardar_avisos" in fuente_editor)

    # El re-corte va DENTRO de la rama --reaplicar y esa rama no puede
    # transcribir: WhisperX large-v3 es la parte cara del pipeline y no depende
    # de donde esten los cortes. Se mira la rama entera, no el orden del texto.
    rama_reaplicar = fuente_editor.split("if args.reaplicar:")[1].split("\n    else:")[0]
    chk("re-cortar reusa la transcripcion en vez de volver a transcribir",
        "FASE 1b-bis" in rama_reaplicar
        and "f2_cortar.py" in rama_reaplicar
        and "f1_transcribir" not in rama_reaplicar
        and "str(transcripcion)" in rama_reaplicar,
        "WhisperX es la parte cara y no depende de donde esten los cortes")

    chk("si falta la grabacion original se avisa y no se re-corta",
        "no se puede rehacer el corte" in fuente_editor,
        "el metraje restaurado no esta en 02_cortado.mp4: sin la fuente no hay de donde sacarlo")

    # --- versiones con nombre ----------------------------------------------
    import f11_servidor as srv
    chk("ajustes.silencios.json viaja con las versiones con nombre",
        "ajustes.silencios.json" in srv.ARCHIVOS_AJUSTES,
        "sin esto, restaurar una version vieja devolveria sus PiP con el corte de ahora")

    chk("el servidor sirve /silencios.js y guarda por /guardar-silencios",
        '"/silencios.js"' in fuente_srv and '"/guardar-silencios"' in fuente_srv)

    chk("el render propaga --silencios solo si hay algo que cambiar",
        'cmd += ["--silencios"' in fuente_srv and "hay_cambios(DIR_TRABAJO)" in fuente_srv,
        "sin el if, cada render normal recortaria la grabacion entera otra vez")

    chk("/datos expone el catalogo de silencios",
        '"silencios": f15_silencios.datos_silencios(dir_trabajo)' in fuente_f10)

    # --- la interfaz --------------------------------------------------------
    chk("el editor tiene su panel, su pista y su boton de reset",
        all(x in fuente_srv for x in ("panelSilencios", "pistaSilencios",
                                      "btnResetSilencios", "silLista")))

    chk("PAGINA carga /silencios.js y cargar() lo arranca",
        '<script src="/silencios.js"></script>' in fuente_srv
        and "if (window.__silencios) window.__silencios.init(DATA);" in fuente_srv)

    chk("el JS pinta los avisos del remapeo",
        "avisos_remapeo" in fuente_js and "silAvisosRemapeo" in fuente_srv,
        "un ajuste movido sin avisar es justo lo que este bloque no puede hacer")

    chk("el JS avisa de las elecciones que quedaron huerfanas",
        "huerfanos" in fuente_js,
        "si cambia hooksegs, la eleccion deja de encajar y hay que decirlo")

    chk("el JS desactiva la restauracion si falta la grabacion original",
        "fuente_existe" in fuente_js and "chk.disabled" in fuente_js)

    chk("los topes de los tiradores salen de /datos, no del JS",
        "limite_inicio" in fuente_js and "limite_inicio" not in fuente_js.split("CSS = ")[0],
        "mismo patron que los picos de SFX y la zona segura")

    # --- coherencia de nombres entre Python y JS ---------------------------
    # Un campo renombrado en Python y no en el JS deja el panel en blanco sin
    # ningun error: los tests son de Python y no verian nada.
    faltan = [c for c in ("duracion_original_s", "pendiente_de_render", "tramos",
                          "fuente_existe", "resumen", "ajustable")
              if c not in fuente_js]
    chk("el JS usa los mismos nombres de campo que datos_silencios()",
        not faltan, f"faltan en el JS: {faltan}" if faltan else "los 6 campos coinciden")

    # --- aguja mapeada sobre la barra de la grabacion ----------------------
    # La barra esta en coordenadas de la GRABACION y el reproductor en las del
    # video cortado. La aguja convierte de una a otra, asi que al llegar a un
    # corte brinca por encima de la franja roja: eso es "ver lo que se quito".
    chk("datos_silencios() expone los intervalos que sobrevivieron en el video",
        "intervalos_conservados" in fuente_f15 and "intervalos_conservados" in fuente_js,
        "son los del 02_cortado.mp4 que se esta viendo, no los que pide el panel: "
        "al destildar un tramo el catalogo cambia pero el archivo sigue igual "
        "hasta re-renderizar, y la aguja tiene que seguir al archivo")
    chk("el JS convierte del video a la grabacion con la misma aritmetica que f2_cortar",
        "function aOriginal" in fuente_js and "offset + largo + 1e-9" in fuente_js,
        "mismo bucle que f2_cortar.mapear_a_original, con los intervalos de /datos")
    # Sin comentarios: el que explica esta misma decision nombra .playhead.
    js_codigo = re.sub(r"/\*.*?\*/", "", fuente_js, flags=re.S)
    js_codigo = re.sub(r"^\s*//.*$", "", js_codigo, flags=re.M)
    chk("la aguja tiene clase propia, no .playhead",
        "sil-aguja" in fuente_js and "playhead" not in js_codigo,
        "actualizarUI() mueve las .playhead por porcentaje de la duracion del video "
        "CORTADO; esta barra es mas larga y quedaria clavada en el sitio equivocado")
    chk("el loop del editor mueve la aguja en cada frame",
        "if (window.__silencios) window.__silencios.cursor(video.currentTime);" in fuente_srv
        and "cursor: cursor" in fuente_js)
    chk("la aguja sobrevive al repintado de la pista",
        "ultimaPosOriginal" in fuente_js,
        "pintarPista() corre al tocar cualquier casilla; sin recordar la posicion "
        "la aguja se iria al 0 en mitad de la reproduccion")
    chk("clic en la barra lleva el video al punto que corresponde",
        "enganchadoClic" in fuente_js)

    # La ida y vuelta tiene que cerrar: llevar una costura al original y volver.
    intervalos = [{"inicio": 0.0, "fin": 2.0}, {"inicio": 5.0, "fin": 9.0}]
    peor = 0.0
    t = 0.0
    while t <= 6.0:
        ida = f2_cortar.mapear_a_original(t, intervalos)
        vuelta = f2_cortar.mapear_a_nueva_linea(ida, intervalos)
        peor = max(peor, abs(vuelta - t))
        t += 0.01
    chk("video -> grabacion -> video cierra exacto en todo el rango",
        peor < 1e-6, f"peor error {peor * 1000:.4f} ms")


def main():
    print("PRUEBAS DEL EDITOR DE SILENCIOS (Bloque B)")
    pruebas_mapeo()
    pruebas_sin_desfase()
    pruebas_avisos()
    pruebas_seleccion()
    pruebas_cableado()

    fallan = [n for n, ok in _resultados if not ok]
    print(f"\n{'=' * 60}")
    if fallan:
        print(f"{len(fallan)} de {len(_resultados)} pruebas FALLAN:")
        for n in fallan:
            print(f"  - {n}")
        return 1
    print(f"LAS {len(_resultados)} PRUEBAS PASAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
