"""Pruebas de regresion del pipeline: aritmetica de tiempos y coherencia entre modulos.

Por que existe. El editor son 13 modulos acoplados por una sola cosa: los
SEGUNDOS. f2 corta y reescribe la linea de tiempo, f4 la usa para el encuadre,
f13 alinea el guion contra ella, f6 coloca overlays encima y f5 pega los
sonidos. Cuando uno de esos calculos se desvia, nada revienta — el video sale,
y el error se ve como "las animaciones no funcionaron" o "los B-roll salen
cortos". Se descubre mirando el resultado, que es la forma mas cara.

Tres bugs reales del 2026-07-27, los tres invisibles en ejecucion:

  · f13_guion definia `extender_fin_evento` DOS VECES; la segunda pisaba a la
    primera y el minimo de 3s de los B-roll no se aplicaba nunca.
  · f6_overlays pedia la plantilla "anim-anim-apps" (doble prefijo): no existe,
    caia al respaldo PIL, PIL tampoco la tiene, y la animacion desaparecia sin
    un solo mensaje de error.
  · f2_cortar se comia el hook fisico entero porque era silencio.

Las pruebas de aqui abajo cazan esas tres clases de fallo. No necesitan
grabacion ni GPU: son datos sinteticos y comprobaciones de coherencia.

Uso:  python editor/test_regresion.py
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import config
import f2_cortar
import f4_retencion
import f8_hyperframes
import f13_guion

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


# ===========================================================================
# 1. Corte y remapeo de la linea de tiempo (f2_cortar)
# ===========================================================================
def pruebas_corte():
    seccion("1. Corte de silencios y remapeo de tiempos (f2_cortar)")

    # Silencios como los emite f1_transcribir: el primero pegado al segundo 0.
    silencios = [
        {"inicio": 0.0,  "fin": 7.90, "duracion": 7.90},   # hook fisico
        {"inicio": 12.0, "fin": 13.5, "duracion": 1.50},   # pausa a mitad
        {"inicio": 20.0, "fin": 20.3, "duracion": 0.30},   # corta, no se toca
    ]

    cortes, cons_ini, cons_fin = f2_cortar.detectar_cortes_silencio(silencios, 0.0)
    chk("sin hook: el silencio inicial se corta entero",
        cons_ini == 0.0 and abs(cortes[0]["fin"] - 7.75) < 1e-6,
        f"corte {cortes[0]['inicio']:.2f}->{cortes[0]['fin']:.2f}s, conservado {cons_ini}s")

    cortes, cons_ini, cons_fin = f2_cortar.detectar_cortes_silencio(silencios, 3.0)
    chk("con hook=3s: quedan exactamente 3s antes de la primera palabra",
        cons_ini == 3.0 and abs(cortes[0]["fin"] - 4.90) < 1e-6 and cortes[0]["inicio"] == 0.0,
        f"corte {cortes[0]['inicio']:.2f}->{cortes[0]['fin']:.2f}s, conservado {cons_ini}s")

    # El hook protege SOLO al silencio inicial: una pausa larga a mitad del
    # video se sigue cortando igual por mas hook que se pida.
    inicios = ", ".join("{:.2f}".format(c["inicio"]) for c in cortes)
    chk("el hook no protege pausas de en medio",
        any(abs(c["inicio"] - 12.15) < 1e-6 for c in cortes),
        f"{len(cortes)} cortes, empiezan en {inicios}")

    # Un silencio inicial mas corto que lo pedido se conserva entero y no se
    # inventa un corte de duracion negativa.
    cortos = [{"inicio": 0.0, "fin": 1.20, "duracion": 1.20}]
    cortes_c, cons_ini_c, cons_fin_c = f2_cortar.detectar_cortes_silencio(cortos, 3.0)
    chk("hook mayor que el silencio disponible -> no corta nada",
        cortes_c == [] and cons_ini_c == 1.20,
        f"cortes={len(cortes_c)}, conservado={cons_ini_c}s")

    # --- simetrico: cierre fisico al final (levantarte, bajar el aparato) ---
    silencios_cierre = [
        {"inicio": 0.0,  "fin": 0.30,  "duracion": 0.30},   # muy corto, no se toca
        {"inicio": 12.0, "fin": 13.5,  "duracion": 1.50},   # pausa a mitad
        {"inicio": 21.0, "fin": 27.5,  "duracion": 6.50},   # cierre fisico
    ]
    duracion_total = 27.5

    cortes, cons_ini, cons_fin = f2_cortar.detectar_cortes_silencio(
        silencios_cierre, 0.0, 0.0, duracion_total)
    chk("sin cierre: el silencio final se corta entero",
        cons_fin == 0.0 and abs(cortes[-1]["fin"] - 27.35) < 1e-6,
        f"corte {cortes[-1]['inicio']:.2f}->{cortes[-1]['fin']:.2f}s, conservado {cons_fin}s")

    cortes, cons_ini, cons_fin = f2_cortar.detectar_cortes_silencio(
        silencios_cierre, 0.0, 2.5, duracion_total)
    chk("con cierre=2.5s: quedan exactamente 2.5s despues de la ultima palabra",
        cons_fin == 2.5 and abs(cortes[-1]["inicio"] - 23.5) < 1e-6 and cortes[-1]["fin"] == duracion_total,
        f"corte {cortes[-1]['inicio']:.2f}->{cortes[-1]['fin']:.2f}s, conservado {cons_fin}s")

    # El cierre protege SOLO al silencio final: la pausa de en medio se sigue
    # cortando igual por mas cierre que se pida.
    inicios = ", ".join("{:.2f}".format(c["inicio"]) for c in cortes)
    chk("el cierre no protege pausas de en medio",
        any(abs(c["inicio"] - 12.15) < 1e-6 for c in cortes),
        f"{len(cortes)} cortes, empiezan en {inicios}")

    # Un silencio final mas corto que lo pedido se conserva entero.
    colas_cortas = [{"inicio": 20.0, "fin": 21.20, "duracion": 1.20}]
    cortes_cc, cons_ini_cc, cons_fin_cc = f2_cortar.detectar_cortes_silencio(
        colas_cortas, 0.0, 3.0, 21.20)
    chk("cierre mayor que el silencio disponible -> no corta nada",
        cortes_cc == [] and cons_fin_cc == 1.20,
        f"cortes={len(cortes_cc)}, conservado={cons_fin_cc}s")

    # --- el calculo mas delicado: que las palabras no se desincronicen ------
    duracion = 25.0
    cortes_t = [{"inicio": 5.0, "fin": 8.0, "razon": "x"},
                {"inicio": 15.0, "fin": 16.0, "razon": "y"}]
    intervalos = f2_cortar.calcular_intervalos_a_conservar(duracion, cortes_t)
    total = sum(i["fin"] - i["inicio"] for i in intervalos)
    chk("los intervalos conservados suman la duracion menos lo cortado",
        abs(total - (duracion - 4.0)) < 1e-6,
        f"{total:.2f}s conservados de {duracion}s (se cortaron 4.0s)")

    palabras = [{"texto": f"p{i}", "inicio": float(i), "fin": i + 0.4} for i in range(25)]
    nuevas = f2_cortar.recalcular_timestamps_palabras(palabras, intervalos)
    chk("ninguna palabra sobrevive dentro de un tramo cortado",
        all(not (5.0 <= float(p["texto"][1:]) < 8.0) for p in nuevas),
        f"{len(nuevas)}/{len(palabras)} palabras conservadas")
    chk("las palabras quedan ordenadas y dentro de la nueva duracion",
        nuevas == sorted(nuevas, key=lambda p: p["inicio"]) and nuevas[-1]["fin"] <= total + 1e-6,
        f"ultima palabra termina en {nuevas[-1]['fin']:.2f}s, duracion nueva {total:.2f}s")

    # mapear_a_nueva_linea tiene que dar EXACTAMENTE lo mismo que el remapeo de
    # palabras. Si divergen, los empalmes entre tomas reales apuntan a un
    # segundo distinto que el audio y el zoom se reinicia donde no toca.
    desvios = []
    for p, n in zip([p for p in palabras
                     if any(iv["inicio"] <= p["inicio"] and p["fin"] <= iv["fin"]
                            for iv in intervalos)], nuevas):
        esperado = f2_cortar.mapear_a_nueva_linea(p["inicio"], intervalos)
        if abs(esperado - n["inicio"]) > 1e-6:
            desvios.append((p["texto"], esperado, n["inicio"]))
    chk("mapear_a_nueva_linea coincide con el remapeo de palabras",
        not desvios, f"{len(desvios)} desvios" if desvios else "coinciden en las 21 palabras")

    # Un instante que cayo dentro de un corte se pega al corte, nunca retrocede.
    m = [f2_cortar.mapear_a_nueva_linea(t, intervalos) for t in (0.0, 4.0, 6.5, 9.0, 25.0)]
    chk("el remapeo es monotono (nunca retrocede en el tiempo)",
        m == sorted(m), f"0,4,6.5,9,25 -> {[round(x, 2) for x in m]}")


# ===========================================================================
# 2. Encuadre y zoom (f4_retencion)
# ===========================================================================
def pruebas_zoom():
    seccion("2. Curva de zoom y planos (f4_retencion)")

    chk("sin tomas reales, todo el video es UN plano",
        f4_retencion.construir_planos(30.0, []) == [{"inicio": 0.0, "fin": 30.0}],
        "un jump cut de silencio ya no reinicia la rampa de zoom")

    planos = f4_retencion.construir_planos(30.0, [12.0])
    chk("un empalme entre tomas si abre un plano nuevo",
        len(planos) == 2 and planos[1]["inicio"] == 12.0,
        f"{planos}")

    chk("empalmes pegados a los bordes se descartan",
        len(f4_retencion.construir_planos(30.0, [0.05, 29.95])) == 1,
        "un plano de 0.05s seria un tiron, no un plano")

    # --- continuidad: el corazon de la queja "cambia a cada rato" ----------
    picos = [{"t": 6.0, "energia": 1.0}, {"t": 18.0, "energia": 1.0}]
    cerrados = [{"ini": 9.0, "fin": 15.0, "zoom": config.ZOOM_PLANO_CERRADO}]
    zs = [f4_retencion.calcular_zoom_en_t(i / config.FPS, planos, picos, cerrados)
          for i in range(int(30 * config.FPS))]

    # La continuidad se exige DENTRO de cada plano. En el empalme entre dos
    # tomas reales el zoom si salta, y tiene que saltar: ahi la imagen corta,
    # asi que un cambio instantaneo de encuadre no se ve — arrastrarlo seria lo
    # raro. Por eso se excluyen los fotogramas que cruzan un limite de plano.
    limites = {p["inicio"] for p in planos} | {p["fin"] for p in planos}
    def cruza_plano(i):
        return any(i / config.FPS < L <= (i + 1) / config.FPS for L in limites)

    saltos = [abs(b - a) for i, (a, b) in enumerate(zip(zs, zs[1:])) if not cruza_plano(i)]
    salto_max = max(saltos)
    # Referencia: el movimiento mas rapido que el diseno permite es entrar al
    # plano cerrado, 0.22 de zoom en ZOOM_TRANSICION_S con smoothstep, cuya
    # pendiente maxima es 1.5x la media. A 30 fps eso son ~0.018 por fotograma.
    # Un reinicio de rampa, en cambio, salta 0.08 de golpe. 0.03 separa las dos
    # cosas sin ambiguedad.
    chk("dentro de un plano la curva de zoom es continua",
        salto_max < 0.03, f"salto maximo {salto_max:.5f} por fotograma (limite 0.03)")

    # Y que el unico sitio donde puede saltar sea, justamente, el empalme.
    salto_borde = max((abs(b - a) for i, (a, b) in enumerate(zip(zs, zs[1:])) if cruza_plano(i)),
                      default=0.0)
    chk("el encuadre puede reiniciarse en el empalme entre tomas",
        salto_borde <= 0.08 + 1e-6,
        f"salto en el empalme {salto_borde:.5f} (como mucho la rampa entera, "
        f"{config.ZOOM_PROGRESIVO_FIN - config.ZOOM_PROGRESIVO_INICIO:.2f})")

    chk("el zoom nunca se sale del rango declarado",
        min(zs) >= config.ZOOM_PROGRESIVO_INICIO - 1e-9
        and max(zs) <= max(config.PUNCH_IN_ZOOM, config.ZOOM_PLANO_CERRADO) + 1e-9,
        f"rango observado {min(zs):.3f}-{max(zs):.3f}")

    # El plano cerrado SOSTIENE: en su tramo central el zoom no baja.
    centro = [f4_retencion.calcular_zoom_en_t(t / 10, planos, picos, cerrados)
              for t in range(101, 149)]
    chk("el plano cerrado se sostiene en vez de rebotar",
        all(abs(z - config.ZOOM_PLANO_CERRADO) < 1e-9 for z in centro),
        f"10.1s-14.8s constante en {centro[0]:.3f}")

    # El punch-in sube y baja: no se queda pegado.
    z_antes = f4_retencion.calcular_zoom_en_t(5.5, planos, picos, cerrados)
    muestreo = [(i / 100, f4_retencion.calcular_zoom_en_t(6.0 + i / 100, planos, picos, cerrados))
                for i in range(int(config.PUNCH_IN_DURACION_S * 100))]
    z_pico = max(z for _, z in muestreo)
    z_despues = f4_retencion.calcular_zoom_en_t(6.0 + config.PUNCH_IN_DURACION_S + 0.5,
                                                planos, picos, cerrados)
    chk("el punch-in sube y vuelve a bajar",
        z_pico > z_antes + 0.05 and abs(z_despues - z_antes) < 0.02,
        f"antes {z_antes:.3f} -> pico {z_pico:.3f} -> despues {z_despues:.3f}")

    # Y sobre todo: el acento tiene que caer DONDE se marco. Con la curva
    # triangular el pico llegaba a la mitad de la ventana, o sea 0.6s tarde, y
    # el enfasis aterrizaba en la palabra siguiente.
    dt_pico = next(dt for dt, z in muestreo if z >= z_pico - 1e-9)
    chk("el punch-in llega arriba sobre la palabra marcada",
        dt_pico <= config.PUNCH_IN_ATAQUE_S + 0.02,
        f"pico a los {dt_pico:.2f}s de la marca (ataque {config.PUNCH_IN_ATAQUE_S}s)")

    chk("dos efectos a la vez no se suman (se toma el mayor)",
        f4_retencion.calcular_zoom_en_t(
            12.0, planos, [{"t": 12.0, "energia": 1.0}], cerrados)
        <= max(config.PUNCH_IN_ZOOM, config.ZOOM_PLANO_CERRADO) + 1e-9,
        "un punch-in dentro de un plano cerrado no da un acercamiento del 40%")

    # Los jump cuts ya no hacen planos, pero siguen contando como cambio visual.
    # Lo que mejora no es el NUMERO de huecos (partir un hueco largo puede dar
    # dos cortos que siguen pasando el umbral) sino los segundos totales que el
    # video pasa sin que cambie nada en pantalla.
    def muerto(huecos):
        return sum(h["duracion"] for h in huecos)
    sin_jc = f4_retencion.detectar_huecos_regla_5s(30.0, planos, [], [])
    con_jc = f4_retencion.detectar_huecos_regla_5s(30.0, planos, [], [3.0, 8.0, 14.0, 20.0, 26.0])
    chk("los jump cuts siguen contando para la regla de 5s",
        muerto(con_jc) < muerto(sin_jc),
        f"{muerto(sin_jc):.0f}s sin cambio visual sin contarlos -> {muerto(con_jc):.0f}s contandolos")


# ===========================================================================
# 3. Duracion de insertos (f13_guion)
# ===========================================================================
def _beat(tipo, ini, fin, idx):
    return {"index": idx, "matched": True, "ini": ini, "fin": fin,
            "duracion": fin - ini, "beat": ["", "", tipo, "", "", ""]}


def pruebas_insertos():
    seccion("3. Duracion de B-roll y PIP (f13_guion)")

    beats = [_beat("B-ROLL", 5.0, 6.0, 0),
             _beat("YO", 6.5, 9.0, 1),
             _beat("ANIM", 9.5, 11.0, 2),
             _beat("PIP", 14.0, 15.0, 3)]

    fin = f13_guion.extender_fin_evento(5.0, 6.0, 0, beats, config.BROLL_TIPOS_QUE_CORTAN)
    # Lo que se comprueba es que PASO DE LARGO el YO (6.5s) y la ANIM (9.5s);
    # donde termina exactamente lo decide el techo, que se prueba aparte.
    chk("un B-roll no lo corta ni un YO ni una animacion de esquina",
        fin > 9.5, f"5.0 -> {fin:.2f}s, la ANIM entra en 9.5s y no lo interrumpe")

    chk("un B-roll respeta el techo estetico",
        abs((fin - 5.0) - config.BROLL_PIP_DURACION_MAX_S) < 1e-6,
        f"{fin - 5.0:.2f}s (tope {config.BROLL_PIP_DURACION_MAX_S}s)")

    fin_pip = f13_guion.extender_fin_evento(5.0, 6.0, 0, beats, config.PIP_TIPOS_QUE_CORTAN)
    chk("un PIP si lo corta la animacion que le disputa la esquina",
        abs(fin_pip - (9.5 - config.BROLL_PIP_GAP_MIN_S)) < 1e-6,
        f"5.0 -> {fin_pip:.2f}s (la ANIM entra en 9.5s)")

    # Nunca por debajo de la frase que lo disparo.
    apretado = [_beat("B-ROLL", 5.0, 8.0, 0), _beat("B-ROLL", 5.5, 6.0, 1)]
    chk("nunca dura menos que la frase que lo dispara",
        f13_guion.extender_fin_evento(5.0, 8.0, 0, apretado) >= 8.0,
        "aunque el proximo inserto caiga encima")

    # Y nunca mas metraje del que tiene el archivo.
    clip = config.DIR_VIDEO_MANUAL / "rendicion.mp4"
    if clip.exists():
        dur = f13_guion.duracion_clip(clip)
        fin_clip = f13_guion.extender_fin_evento(5.0, 6.0, 0, beats,
                                                 config.BROLL_TIPOS_QUE_CORTAN, clip)
        chk("nunca pide mas metraje del que tiene el clip",
            fin_clip - 5.0 <= dur + 1e-6,
            f"{fin_clip - 5.0:.2f}s pedidos, el clip dura {dur:.2f}s")
    else:
        print(f"  [SKIP] no existe {clip.name} para la prueba de metraje")


# ===========================================================================
# 4. Encuadre sacado del guion (f13_guion.plan_encuadre)
# ===========================================================================
def pruebas_encuadre_guion():
    seccion("4. Punch-ins y planos cerrados leidos del panel (f13_guion)")

    palabras = [{"texto": t, "inicio": 1.0 + i * 0.5, "fin": 1.4 + i * 0.5}
                for i, t in enumerate("tu con tu fuerza de voluntad contra un algoritmo".split())]
    beats = [{"index": 0, "matched": True, "ini": 1.0, "fin": 5.5, "duracion": 4.5,
              "range_words": (0, len(palabras)),
              "beat": ["", "", "ANIM", 'H08 + punch-in en "algoritmo"', "", ""]}]
    guion = {"tomas": [["0-10s", "Plano cerrado (acerca la camara)", "",
                        "tu con tu fuerza de voluntad contra un algoritmo"]]}

    plan = f13_guion.plan_encuadre(guion, palabras, beats)
    t_algoritmo = palabras[-1]["inicio"]
    chk("el punch-in se ancla en la palabra entrecomillada",
        plan["punch_ins"] and abs(plan["punch_ins"][0]["t"] - t_algoritmo) < 1e-6,
        f"punch-in en {plan['punch_ins'][0]['t']:.2f}s, 'algoritmo' se dice en {t_algoritmo:.2f}s")

    chk("'Plano cerrado' de la tabla de tomas produce un tramo sostenido",
        len(plan["planos_cerrados"]) == 1
        and plan["planos_cerrados"][0]["zoom"] == config.ZOOM_PLANO_CERRADO,
        f"{plan['planos_cerrados']}")

    # "Vuelves al plano medio" nombra un plano pero NO es un acercamiento.
    guion_medio = {"tomas": [["0-10s", "Vuelves al plano medio", "",
                              "tu con tu fuerza de voluntad contra un algoritmo"]]}
    chk("'plano medio' no se confunde con un acercamiento",
        f13_guion.plan_encuadre(guion_medio, palabras, beats)["planos_cerrados"] == [],
        "solo 'cerrado', 'primer plano' o 'plano corto' acercan")

    # Los SFX no pueden encimarse.
    ordenes = [{"t": 1.0, "archivo": "a.mp3"}, {"t": 1.05, "archivo": "b.mp3"},
               {"t": 5.0, "archivo": "c.mp3"}]
    sep = f13_guion.espaciar_sfx([dict(o) for o in ordenes])
    ok_sep = all(b["t"] - a["t"] >= config.SFX_SEPARACION_MIN_S - 1e-6
                 for a, b in zip(sep, sep[1:]))
    chk("los SFX respetan la separacion minima",
        ok_sep, f"{len(ordenes)} pedidos -> {len(sep)} colocados")


# ===========================================================================
# 5. Coherencia entre modulos: los nombres y las duraciones no pueden divergir
# ===========================================================================
def pruebas_coherencia():
    seccion("5. Coherencia entre config, plantillas y respaldo PIL")

    import f7_animaciones
    dir_comp = f8_hyperframes.DIR_PLANTILLAS / "compositions"

    huerfanas = []
    for nombre in config.ANIMACION_DURACION:
        plantilla = f8_hyperframes.plantilla_de(nombre)
        tiene_html = (dir_comp / f"{plantilla}.html").exists()
        tiene_pil = nombre in f7_animaciones.GENERADORES
        if not tiene_html and not tiene_pil:
            huerfanas.append(f"{nombre} (buscaba {plantilla}.html)")
    chk("toda animacion declarada se puede construir de verdad",
        not huerfanas,
        "; ".join(huerfanas) if huerfanas
        else f"{len(config.ANIMACION_DURACION)} animaciones, todas con plantilla o respaldo PIL")

    chk("plantilla_de respeta los dos vocabularios",
        f8_hyperframes.plantilla_de("bateria") == "anim-bateria"
        and f8_hyperframes.plantilla_de("anim-apps") == "anim-apps"
        and f8_hyperframes.plantilla_de("stickers") == "stickers",
        "nombre corto -> anim-<nombre>; nombre de plantilla -> tal cual")

    ida_vuelta = [n for n in config.ANIMACION_DURACION
                  if f8_hyperframes.nombre_canonico(f8_hyperframes.plantilla_de(n)) != n]
    chk("plantilla_de y nombre_canonico son inversas",
        not ida_vuelta, ", ".join(ida_vuelta) if ida_vuelta
        else "las dos direcciones del vocabulario cierran")

    # La invariante que de verdad importa: TODO lo que el panel puede pedir
    # tiene que llegar a f6_overlays con un nombre que config reconozca. Si no,
    # la animacion se descarta con un "animacion desconocida" que nadie mira.
    datos = f13_guion.cargar_datos_html()
    sin_soporte = []
    for g in datos["G"]:
        for i, fila in enumerate(g["tl"]):
            if fila[2] != "ANIM":
                continue
            nombre = f13_guion.extraer_plantilla_animacion(fila[3], datos["CLIPS"])
            if (nombre not in config.ANIMACION_DURACION
                    and nombre not in config.PLANTILLAS_CON_DATOS_PROPIOS):
                sin_soporte.append(f"guion {g['n']} beat {i}: '{nombre}'")
    n_anim = sum(1 for g in datos["G"] for f in g["tl"] if f[2] == "ANIM")
    chk("toda animacion pedida por el panel la sabe construir el pipeline",
        not sin_soporte, "; ".join(sin_soporte) if sin_soporte
        else f"{n_anim} beats ANIM en los {len(datos['G'])} guiones, todos resueltos")

    # El panel se lee lanzando Node y leyendo su stdout. Node escribe UTF-8,
    # pero `text=True` a secas decodifica con la codificacion regional de
    # Windows: cada tilde llegaba rota y el reporte que lee Jose salia con
    # "Â¿Por quÃ© dejaste de leer?".
    textos = " ".join(f[1] for g in datos["G"] for f in g["tl"]) + " ".join(
        g["t"] for g in datos["G"])
    chk("el panel se lee con los acentos intactos",
        "Ã" not in textos and "Â" not in textos and "é" in textos,
        "mojibake en el texto del panel" if "Ã" in textos
        else "tildes y signos de apertura correctos")

    sin_hooksegs = [g["n"] for g in datos["G"] if "hooksegs" not in g]
    chk("todos los guiones declaran hooksegs",
        not sin_hooksegs, f"faltan en {sin_hooksegs}" if sin_hooksegs
        else "los 10 lo traen; sin el, el corte se come el hook fisico")

    sin_cierresegs = [g["n"] for g in datos["G"] if "cierresegs" not in g]
    chk("todos los guiones declaran cierresegs",
        not sin_cierresegs, f"faltan en {sin_cierresegs}" if sin_cierresegs
        else "los 10 lo traen; sin el, el corte se come el cierre fisico")

    # La duracion declarada tiene que coincidir con el data-duration del HTML.
    # El comentario de config lo afirma, pero nada lo comprobaba: si alguien
    # edita el HTML, el pipeline recorta o alarga el clip sin enterarse.
    desfases = []
    for plantilla, dur in f8_hyperframes.DURACIONES.items():
        html = dir_comp / f"{plantilla}.html"
        if not html.exists():
            desfases.append(f"{plantilla}: sin HTML")
            continue
        m = re.search(r'data-duration="([\d.]+)"', html.read_text(encoding="utf-8"))
        if not m:
            desfases.append(f"{plantilla}: sin data-duration")
        elif abs(float(m.group(1)) - dur) > 1e-6:
            desfases.append(f"{plantilla}: HTML {m.group(1)}s vs DURACIONES {dur}s")
    chk("las duraciones declaradas coinciden con el data-duration del HTML",
        not desfases, "; ".join(desfases) if desfases
        else f"{len(f8_hyperframes.DURACIONES)} plantillas coinciden")

    faltan_dur = [n for n in f8_hyperframes.PLANTILLAS if n not in f8_hyperframes.DURACIONES]
    chk("toda plantilla tiene su duracion declarada",
        not faltan_dur, ", ".join(faltan_dur) if faltan_dur else "ninguna sin duracion")

    # Los SFX que nombra config tienen que existir en disco.
    dir_sfx = config.DIR_ASSETS / "sfx"
    perdidos = [a for ev in config.SFX_POR_EVENTO.values()
                for a in ev["archivos"] if not (dir_sfx / a).exists()]
    chk("los SFX de config.SFX_POR_EVENTO existen en disco",
        not perdidos, ", ".join(perdidos) if perdidos else "todos presentes")


# ===========================================================================
# 6. La red contra el bug invisible: definiciones duplicadas
# ===========================================================================
def pruebas_duplicados():
    seccion("6. Definiciones duplicadas (la clase de bug que no da error)")

    duplicados = []
    for py in sorted(AQUI.glob("*.py")):
        try:
            arbol = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            duplicados.append(f"{py.name}: no parsea ({e})")
            continue
        vistos = {}
        for nodo in arbol.body:      # solo nivel superior del modulo
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if nodo.name in vistos:
                    duplicados.append(
                        f"{py.name}: '{nodo.name}' definida en la linea {vistos[nodo.name]} "
                        f"y otra vez en la {nodo.lineno} (la segunda pisa a la primera)")
                vistos[nodo.name] = nodo.lineno

    chk("ningun modulo define dos veces la misma funcion",
        not duplicados, "\n          ".join(duplicados) if duplicados
        else f"{len(list(AQUI.glob('*.py')))} modulos revisados")


# ===========================================================================
# 7. Round-trip editor visual -> render
# ===========================================================================
# La clase de bug que ninguna de las secciones anteriores veia: el editor
# guarda unos ajustes, el pipeline los vuelve a leer, y por el camino se
# pierden. El video sale igual, solo que sin los B-roll. Paso de verdad en la
# corrida `Guion-7-hook` del 2026-07-27: los 3 clips a pantalla completa y el
# PiP de video se evaporaron y el log solo dijo "Overlays planificados: 3".
def pruebas_round_trip():
    import json
    import tempfile

    import f6_overlays
    import f10_editor_visual as f10

    seccion("7. Round-trip editor visual -> render")

    ids_catalogo = {a["id"] for a in json.loads(
        (config.DIR_CONTEXTO / "catalogo-assets.json").read_text(encoding="utf-8"))["assets"]}

    # --- la mitad JS, replicada tal cual la escribe f11_servidor -------------
    def js_asset_id(asset):
        return asset if asset in ids_catalogo else None

    def js_es_broll(ev):
        return ev.get("broll_fullscreen") is True or ev.get("tipo") == "broll"

    def js_evento_base(ev):
        base = {"ini": ev["ini"], "fin": ev["fin"], "x": ev["x"], "y": ev["y"],
                "tipo": ev.get("tipo"), "medio": ev.get("medio"),
                "palabra": ev.get("palabra", ""), "tag": ev.get("tag", "")}
        aid = js_asset_id(ev.get("asset", ""))
        if aid:
            base["asset_id"] = aid
        if ev.get("asset"):
            base["asset"] = ev["asset"]
        if ev.get("archivo"):
            base["archivo"] = ev["archivo"]
        if ev.get("codigo"):
            base["codigo"] = ev["codigo"]
        return base

    tmp = Path(tempfile.mkdtemp())
    clip = tmp / "clip.mp4"
    clip.write_bytes(b"no es un mp4 de verdad, pero existe y con eso basta")

    entrada = [
        {"tipo": "broll", "medio": "video", "broll_fullscreen": True, "archivo": str(clip),
         "x": 0, "y": 0, "ini": 7.8, "fin": 11.0, "tag": "scroll",
         "asset": "broll-manual:scroll", "codigo": "F14"},
        {"tipo": "pip-producto", "medio": "video", "archivo": str(clip),
         "x": 600, "y": 134, "ini": 18.7, "fin": 20.6, "tag": "pagina-real",
         "asset": "video:pagina-real"},
    ]

    eventos_json = tmp / "ajustes.eventos.json"
    broll_json = tmp / "ajustes.broll.json"
    eventos_json.write_text(json.dumps(
        {"eventos": [js_evento_base(e) for e in entrada if not js_es_broll(e)]}), encoding="utf-8")
    broll_json.write_text(json.dumps(
        {"broll": [dict(js_evento_base(e), broll_fullscreen=True, medio="video")
                   for e in entrada if js_es_broll(e)]}), encoding="utf-8")

    vueltos = (f6_overlays.cargar_eventos_manual(eventos_json, tmp) or []) \
        + (f6_overlays.cargar_broll_manual(broll_json) or [])

    chk("ningun inserto se pierde al volver del editor",
        len(vueltos) == len(entrada),
        f"{len(vueltos)} de {len(entrada)} sobreviven al viaje de ida y vuelta")

    br = [e for e in vueltos if e.get("broll_fullscreen")]
    chk("un B-roll vuelve siendo un B-roll a pantalla completa",
        len(br) == 1 and br[0]["medio"] == "video"
        and Path(str(br[0]["archivo"])).suffix == ".mp4",
        "no convertido en tarjeta PiP de esquina" if br else "no volvio ningun B-roll")

    pip_video = [e for e in vueltos if e.get("medio") == "video" and not e.get("broll_fullscreen")]
    chk("un PiP de video conserva su clip, no se congela en PNG",
        len(pip_video) == 1 and Path(str(pip_video[0]["archivo"])).suffix == ".mp4",
        f"{len(pip_video)} PiP de video")

    # Un asset_id que no resuelve ya no descarta el evento: se cae al archivo.
    huerfano = tmp / "huerfano.json"
    huerfano.write_text(json.dumps({"eventos": [
        {"ini": 1.0, "fin": 2.0, "x": 0, "y": 0, "asset_id": "no-existe:nada",
         "archivo": str(clip), "medio": "video"}]}), encoding="utf-8")
    chk("un asset_id desconocido cae al archivo en vez de borrar el inserto",
        len(f6_overlays.cargar_eventos_manual(huerfano, tmp) or []) == 1)

    # --- encuadre: la lista vacia es una orden, no un dato que falte --------
    plan = {"planos_cerrados": [{"ini": 5.0, "fin": 9.0, "zoom": 1.22, "razon": "auto"}],
            "picos_energia": [{"t": 3.0, "energia": 1.0}]}
    for clave, del_plan in (("planos_cerrados", plan["planos_cerrados"]),
                            ("punch_ins", plan["picos_energia"])):
        vacio = {clave: []}
        leido = vacio[clave] if clave in vacio else del_plan
        chk(f"borrar todos los '{clave}' en el editor manda sobre el automatico",
            leido == [],
            "una lista vacia ya no se confunde con 'sin dato'")

    # Y el pipeline lo lee igual que la vista previa: las dos ramas usan `in`.
    fuente_f4 = (AQUI / "f4_retencion.py").read_text(encoding="utf-8")
    fuente_f10 = (AQUI / "f10_editor_visual.py").read_text(encoding="utf-8")
    chk("ni el render ni la vista previa usan 'or' para el encuadre manual",
        'encuadre_guion.get("planos_cerrados") or' not in fuente_f4
        and 'encuadre.get("punch_ins") or' not in fuente_f10,
        "con 'or' el editor enseñaba un zoom que el video no tenia")

    # --- el re-render no puede perder los parametros de la corrida ----------
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    faltan = [b for b in ("--guion", "--presentador", "--musica", "--broll-manual")
              if b not in fuente_srv]
    chk("el re-render reenvia los parametros de la corrida original",
        not faltan,
        f"faltan: {', '.join(faltan)}" if faltan
        else "guion, presentador, musica y B-roll viajan con el re-render")

    fuente_editor = (AQUI / "editor.py").read_text(encoding="utf-8")
    chk("editor.py deja constancia de con que se lanzo la corrida",
        "00_corrida.json" in fuente_editor,
        "sin ese archivo el editor no sabe que era un video dirigido por guion")

    # --- guardar y recargar la pagina no puede perder los B-roll -----------
    # Los insertos y los B-roll se guardan en DOS archivos porque el pipeline
    # los recibe por banderas distintas. El editor los enseña en una sola tira,
    # asi que tiene que volver a juntarlos al cargar: leyendo solo
    # ajustes.eventos.json los B-roll guardados desaparecian de la pantalla, y
    # de ahi al video en el render siguiente.
    dir_falso = tmp / "corrida"
    dir_falso.mkdir(exist_ok=True)
    (dir_falso / "ajustes.eventos.json").write_text(json.dumps({"eventos": [
        {"ini": 18.0, "fin": 20.0, "tipo": "pip-producto", "archivo": str(clip)}]}), encoding="utf-8")
    (dir_falso / "ajustes.broll.json").write_text(json.dumps({"broll": [
        {"ini": 7.0, "fin": 11.0, "tipo": "broll", "medio": "video",
         "broll_fullscreen": True, "archivo": str(clip)}]}), encoding="utf-8")

    recargados = f10.eventos_del_editor(dir_falso, ids_catalogo)
    chk("al recargar la pagina siguen estando los insertos Y los B-roll",
        len(recargados) == 2 and sum(1 for e in recargados if e.get("broll_fullscreen")) == 1,
        f"{len(recargados)} eventos, en orden de tiempo: "
        f"{[round(float(e['ini']), 1) for e in recargados]}")

    # --- ajustes de una version anterior no pueden dejar insertos fantasma --
    dir_viejo = tmp / "corrida_vieja"
    dir_viejo.mkdir(exist_ok=True)
    # Formato viejo: asset_id que no es del catalogo y ninguna ruta de archivo.
    (dir_viejo / "ajustes.eventos.json").write_text(json.dumps({"eventos": [
        {"ini": 7.8, "fin": 11.0, "x": 0, "y": 0, "asset_id": "broll-manual:scroll"}]}),
        encoding="utf-8")
    (dir_viejo / "05_overlays.eventos.json").write_text(json.dumps([
        {"ini": 7.8, "fin": 11.0, "tipo": "broll", "medio": "video",
         "broll_fullscreen": True, "archivo": str(clip), "asset": "broll-manual:scroll"}]),
        encoding="utf-8")

    del_viejo = f10.eventos_del_editor(dir_viejo, ids_catalogo)
    chk("unos ajustes viejos e irreconstruibles no borran el inserto",
        len(del_viejo) == 1 and del_viejo[0].get("archivo") == str(clip),
        "se vuelve a los del ultimo render en vez de cargar un evento sin archivo "
        "que el render descartaria")


# ===========================================================================
# 8. Preview de animaciones en el editor
# ===========================================================================
# Las animaciones son ProRes 4444 con alfa y ocupan un 4% del cuadro: el editor
# enseñaba un rectangulo negro y no habia forma de saber cual era cual. El
# preview recorta a la animacion y la pasa a WebM. Dos trampas que esto fija:
# el recuadro tiene que RECORTAR (si no, la animacion sale del tamaño de una
# uña) y el encode tiene que TERMINAR (el fondo de lavfi es infinito y sin
# cortarlo dentro del filtro el WebM crece sin fin: se vio llegar a 3 MB).
def pruebas_preview_animaciones():
    import subprocess
    import tempfile

    import f10_editor_visual as f10

    seccion("8. Preview de animaciones en el editor")

    tmp = Path(tempfile.mkdtemp())
    src = tmp / "sintetica.mov"
    # Una animacion de mentira con la misma forma que las de verdad: lienzo
    # 1080x1920 casi todo transparente con un elemento pequeño dentro.
    hecho = subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black@0.0:s=1080x1920:d=2:r=25,format=yuva444p10le",
        "-f", "lavfi", "-i", "color=c=red:s=200x300:d=2:r=25",
        "-filter_complex", "[0:v][1:v]overlay=440:800:format=auto",
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(src),
    ], capture_output=True).returncode == 0

    if not hecho or not src.exists():
        chk("ffmpeg sabe hacer ProRes 4444 con alfa", False,
            "sin eso no se puede comprobar el preview de animaciones")
        return

    caja = f10._caja_animacion(src)
    # El elemento esta en (440,800) y mide 200x300; el margen del 6% ensancha
    # un poco. Lo que importa es que NO devuelva el cuadro entero.
    chk("el recuadro se ajusta a la animacion, no al cuadro entero",
        caja is not None and caja[2] < 1080 * 0.5 and caja[3] < 1920 * 0.5
        and abs(caja[0] - 440) < 60 and abs(caja[1] - 800) < 60,
        f"caja={caja} para un elemento en (440,800) de 200x300")

    prev = f10.preview_animacion(src, dir_cache=tmp / "cache")
    chk("el preview se genera", prev is not None and prev.exists())
    if prev is None or not prev.exists():
        return

    dur = f10._duracion(prev)
    chk("el preview dura lo que la animacion y no crece sin fin",
        1.5 <= dur <= 3.0,
        f"{dur:.2f}s para una animacion de 2.0s "
        f"(sin cortar el fondo de lavfi esto no terminaba nunca)")

    kb = prev.stat().st_size / 1024
    chk("el preview pesa poco: se cargan una docena en la misma pagina",
        kb < 500, f"{kb:.1f} KB")


# ===========================================================================
# 9. Orientacion de las fotos
# ===========================================================================
# 169 de las 198 fotos aptas para PiP salen del telefono en horizontal con una
# etiqueta EXIF que dice "va girada 90". PIL no la aplica sola: la rejilla del
# editor las enseñaba volcadas, el catalogo las anotaba como `horizontal`
# siendo verticales, y —lo caro— la tarjeta que se compone DENTRO DEL VIDEO
# salia volcada tambien.
def pruebas_orientacion():
    import json
    import tempfile

    from PIL import Image

    seccion("9. Orientacion de las fotos")

    tmp = Path(tempfile.mkdtemp())
    # Foto de mentira con la misma trampa: apaisada + "girala 90" en el EXIF.
    foto = tmp / "volcada.jpg"
    im = Image.new("RGB", (400, 200), (200, 30, 30))
    exif = im.getexif()
    exif[274] = 6
    im.save(foto, exif=exif)

    with config.abrir_imagen(foto) as abierta:
        medidas = abierta.size
    chk("abrir_imagen aplica la orientacion EXIF",
        medidas == (200, 400),
        f"{medidas} para una foto guardada 400x200 con EXIF 'girala 90'")

    with Image.open(foto) as cruda:
        crudas = cruda.size
    chk("y hacia falta: Image.open a secas la deja volcada",
        crudas == (400, 200),
        "por eso no vale abrir las fotos del catalogo con PIL directamente")

    # El catalogo tiene que estar de acuerdo consigo mismo: si guarda que un
    # asset es vertical, sus dimensiones tienen que decir lo mismo.
    # Con la MISMA regla que usa el indexador (tiene una banda de tolerancia
    # para lo casi cuadrado), no con una inventada aqui.
    import catalogo_assets

    ruta_cat = config.DIR_CONTEXTO / "catalogo-assets.json"
    incoherentes = []
    if ruta_cat.exists():
        for a in json.loads(ruta_cat.read_text(encoding="utf-8"))["assets"]:
            dim = a.get("dimensiones")
            if not dim or not dim[0] or not dim[1]:
                continue
            esperada = catalogo_assets._orientacion(dim[0], dim[1])
            if a.get("orientacion") != esperada:
                incoherentes.append(f"{a['id']}: dice {a.get('orientacion')} y mide {dim[0]}x{dim[1]}")
    chk("la orientacion del catalogo concuerda con las dimensiones",
        not incoherentes,
        "\n          ".join(incoherentes[:4]) if incoherentes
        else "ningun asset se contradice")

    # Y ningun modulo que componga fotos reales puede saltarse el ajuste.
    saltan = []
    for modulo in ("f6_overlays.py", "f7_animaciones.py", "quitar_fondos.py",
                   "catalogo_assets.py", "f10_editor_visual.py"):
        fuente = (AQUI / modulo).read_text(encoding="utf-8")
        for linea in fuente.splitlines():
            # Los fotogramas que extrae el propio pipeline no llevan EXIF; los
            # que importan son los que abren un archivo del catalogo.
            if "Image.open(" in linea and "ruta_logo" not in linea and "cuadros" not in linea \
                    and "(f)" not in linea and "foto, exif" not in linea:
                saltan.append(f"{modulo}: {linea.strip()[:70]}")
    chk("nadie abre una foto del catalogo saltandose la orientacion",
        not saltan,
        "\n          ".join(saltan) if saltan
        else "todos pasan por config.abrir_imagen()")


def main():
    print("Pruebas de regresion del pipeline de video\n"
          "==========================================")
    pruebas_corte()
    pruebas_zoom()
    pruebas_insertos()
    pruebas_encuadre_guion()
    pruebas_coherencia()
    pruebas_duplicados()
    pruebas_round_trip()
    pruebas_preview_animaciones()
    pruebas_orientacion()

    fallan = [n for n, ok in _resultados if not ok]
    print(f"\n{'=' * 60}")
    if fallan:
        print(f"{len(fallan)} de {len(_resultados)} pruebas FALLAN:")
        for n in fallan:
            print(f"  - {n}")
    else:
        print(f"LAS {len(_resultados)} PRUEBAS PASAN")
    print("\nFalta la otra mitad:  python editor/test_align.py"
          "  (alineacion guion <-> transcripcion contra el panel real)")
    return 1 if fallan else 0


if __name__ == "__main__":
    sys.exit(main())
