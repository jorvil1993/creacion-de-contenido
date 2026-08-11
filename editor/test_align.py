"""Pruebas del alineador guion <-> transcripcion (f13_guion).

Por que se reescribio: la primera version fabricaba la transcripcion falsa
concatenando el texto de los propios beats, o sea que le preguntaba al alineador
si encontraba un texto DENTRO DE SI MISMO. Siempre daba 1.000 y no probaba nada
de lo que de verdad falla.

Estas pruebas atacan los modos de fallo reales:
  1. Jose se salta una linea            -> ese beat se omite y los DEMAS no se corren
  2. Jose improvisa / cambia palabras   -> igual se encuentra
  3. El guion repite el hook al final   -> el beat 0 cae en la PRIMERA aparicion
  4. El audio es de otro guion          -> no inventa coincidencias

Uso:  python editor/test_align.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import f13_guion


def transcribir(frases: list, t0: float = 0.4, paso: float = 0.32) -> list:
    """Convierte una lista de frases en palabras con timestamps, como WhisperX."""
    palabras, t = [], t0
    for frase in frases:
        for w in frase.split():
            limpio = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ]", "", w)
            if limpio:
                palabras.append({"texto": limpio, "inicio": round(t, 2), "fin": round(t + 0.25, 2)})
                t += paso
    return palabras


def correr(nombre, tl, palabras, esperado_fn):
    res = f13_guion.alinear_guion_con_transcripcion(tl, palabras)
    ok, detalle = esperado_fn(res)
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre}")
    if detalle:
        print(f"          {detalle}")
    return ok


# El guion contra el que se prueba el alineador. Se busca POR SU HOOK y no por
# su numero: desde que el calendario del mes manda, `PANEL-PRODUCCION.html` se
# recarga cada mes con los guiones de ese mes RENUMERADOS desde 1, o sea que el
# numero de un guion cambia sin que cambie una sola letra de su contenido. Las
# fixtures de aqui abajo (la improvisacion linea por linea, el beat omitido) son
# de ESTE guion y de ningun otro.
HOOK_FIXTURE = "Intenta estar cinco minutos sin mirar el celular. No puedes."


def guion_fixture() -> tuple:
    """El guion de las fixtures, del panel vivo o del archivo `_old`.

    Si el mes en curso no lo lleva, se lee del respaldo `PANEL-PRODUCCION_old.html`,
    que es permanente. Estas pruebas son del ALINEADOR, no del contenido del mes:
    quedarse sin probarlo porque agosto no programo ese video seria perder la red
    justo donde no hay que perderla.
    """
    raiz = Path(__file__).resolve().parent.parent
    for ruta in (None, raiz / "PANEL-PRODUCCION_old.html"):
        if ruta is not None and not ruta.exists():
            continue
        try:
            datos = f13_guion.cargar_datos_html(ruta)
        except Exception:
            continue
        for g in datos["G"]:
            if g["t"] == HOOK_FIXTURE:
                return g, ("PANEL-PRODUCCION.html" if ruta is None else ruta.name)
    raise SystemExit(
        f"No encontre el guion de las fixtures ({HOOK_FIXTURE!r}) ni en el panel "
        f"vivo ni en PANEL-PRODUCCION_old.html")


def main():
    g, de_donde = guion_fixture()
    tl = g["tl"]
    dichos = [b[1] for b in tl]
    print(f"Guion {g['n']} ({de_donde}): \"{g['t']}\" — {len(tl)} beats\n")

    todo_ok = True

    # --- 1. transcripcion limpia: control -------------------------------
    def chk1(res):
        n = sum(1 for r in res if r["matched"])
        orden = [r["ini"] for r in res if r["matched"]]
        return (n == len(tl) and orden == sorted(orden),
                f"{n}/{len(tl)} alineados, en orden creciente")
    todo_ok &= correr("transcripcion limpia -> alinea todo", tl, transcribir(dichos), chk1)

    # --- 2. beat omitido: el que falta se salta, el resto NO se corre ----
    OMITIDO = 5   # "No es falta de disciplina."
    def chk2(res):
        fallo = [r["index"] for r in res if not r["matched"]]
        # los beats posteriores deben seguir cayendo despues del beat 4
        fin_4 = next((r["fin"] for r in res if r["index"] == 4 and r["matched"]), None)
        posteriores = [r["ini"] for r in res if r["matched"] and r["index"] > OMITIDO]
        sanos = fin_4 is not None and all(i >= fin_4 - 0.01 for i in posteriores)
        return (fallo == [OMITIDO] and sanos,
                f"omitidos={fallo} (esperado [{OMITIDO}]); los {len(posteriores)} beats "
                f"siguientes {'siguen ordenados' if sanos else 'SE DESCOLOCARON'}")
    todo_ok &= correr("beat no hablado -> se omite solo ese",
                      tl, transcribir([d for i, d in enumerate(dichos) if i != OMITIDO]), chk2)

    # --- 3. improvisacion: cambia palabras, agrega muletillas ------------
    improvisado = [
        "Te diste cuenta de que ya no podes estar 5 minutos sin hacer nada",
        "Sin sacar el celular o buscar dopamina barata",
        "Ya casi nadie puede gente y no es casualidad",
        "Estas compitiendo contra una app disenada por miles de ingenieros para que no la sueltes",
        "El video que sale solo la notificacion el siguiente todo esta hecho para ganarte",
        "O sea no es falta de disciplina es una pelea re injusta tu fuerza de voluntad contra el algoritmo y no la vas a ganar",
        "La unica manera de ganarla es salirte del juego",
        "Volver a un espacio donde nada te interrumpa donde abris un libro y se apaga el mundo",
        "sin notificaciones sin pantallas que quemen la vista sin tentaciones",
        "Un espacio donde tu atencion vuelve a ser 100 por ciento tuya",
        "Mandaselo a alguien que no suelta el cel ni en la mesa",
    ]
    def chk3(res):
        n = sum(1 for r in res if r["matched"])
        peor = min((r["ratio"] for r in res if r["matched"]), default=0)
        return (n >= len(tl) - 2, f"{n}/{len(tl)} alineados pese a la improvisacion (ratio min {peor:.2f})")
    todo_ok &= correr("improvisacion -> tolera cambios de palabra",
                      tl, transcribir(improvisado), chk3)

    # --- 4. hook repetido al final (el loop): no debe engancharse lejos ---
    con_eco = dichos + ["¿Te diste cuenta de que ya no podés estar cinco minutos sin hacer nada?"]
    def chk4(res):
        b0 = next(r for r in res if r["index"] == 0)
        temprano = b0["matched"] and b0["ini"] < 2.0
        return (temprano, f"beat 0 cayo en {b0.get('ini', '?')}s "
                          f"({'la primera aparicion, correcto' if temprano else 'SE FUE AL ECO DEL FINAL'})")
    todo_ok &= correr("hook repetido al cierre -> toma la primera aparicion",
                      tl, transcribir(con_eco), chk4)

    # --- 5. audio de OTRO guion: no debe inventar coincidencias ----------
    otro = Path(r"C:\ai-video\salida\VIDEOV2_broll\02_cortado.json")
    if otro.exists():
        palabras_otro = json.loads(otro.read_text(encoding="utf-8"))["palabras"]
        def chk5(res):
            n = sum(1 for r in res if r["matched"])
            return (n <= 1, f"{n}/{len(tl)} beats enganchados en una grabacion de OTRO guion "
                            f"({'bien, no inventa' if n <= 1 else 'DEMASIADOS: umbral muy laxo'})")
        todo_ok &= correr("grabacion de otro guion -> rechaza", tl, palabras_otro, chk5)
    else:
        print("  [SKIP] no hay grabacion real en C:\\ai-video\\salida para la prueba 5")

    print(f"\n{'TODAS LAS PRUEBAS PASAN' if todo_ok else 'HAY PRUEBAS QUE FALLAN'}")
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
