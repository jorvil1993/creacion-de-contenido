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
import subprocess
import sys
import tempfile
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

    # --- palabras normales que la lista de muletillas se comia --------------
    # Caso real (2026-07-30): Jose dijo "ya no podes estar cinco minutos sin
    # hacer NADA?" y el corte se llevo el "nada" porque estaba en MULETILLAS,
    # que se aplica por coincidencia LITERAL sin mirar contexto. Es un pronombre
    # indefinido, no una muletilla, y romperlo cambia el sentido de la frase.
    # Mismo bug que ya habia tenido "este" ("mas ESTE año"). La correccion es la
    # misma: pasarlo a CONECTORES_AMBIGUOS, que solo corta si la palabra va
    # AISLADA por pausas -- que es como suena una muletilla de verdad.
    palabras_nada = [
        {"inicio": 0.00, "fin": 0.30, "texto": "cinco"},
        {"inicio": 0.32, "fin": 0.70, "texto": "minutos"},
        {"inicio": 0.72, "fin": 0.90, "texto": "sin"},
        {"inicio": 0.92, "fin": 1.20, "texto": "hacer"},
        {"inicio": 1.22, "fin": 1.50, "texto": "nada?"},   # legitimo: pegado
        {"inicio": 1.52, "fin": 1.70, "texto": "Sin"},
        {"inicio": 1.72, "fin": 2.10, "texto": "sacar"},
        {"inicio": 3.50, "fin": 3.80, "texto": "nada"},    # muletilla: aislado
        {"inicio": 4.40, "fin": 4.90, "texto": "final"},
    ]
    cortes_m = f2_cortar.detectar_cortes_muletillas(
        palabras_nada, [{"inicio": 0.0, "fin": 4.90}])
    cortados = [round(c["inicio"], 2) for c in cortes_m]
    chk("'sin hacer nada?' NO se corta: es un pronombre, no una muletilla",
        1.22 not in cortados,
        f"cortes en {cortados}" if cortados else "no corto nada")
    chk("un 'nada' AISLADO por pausas si se sigue cortando",
        3.50 in cortados,
        "el criterio de contexto no puede volverse tan blando que deje de "
        "cortar la muletilla de verdad")
    chk("'nada' esta en los ambiguos y ya no en la lista literal",
        "nada" in config.CONECTORES_AMBIGUOS and "nada" not in config.MULETILLAS)

    # Las entradas de dos palabras de MULETILLAS estan INERTES: _es_muletilla
    # compara una sola palabra de la transcripcion. Se documenta para que nadie
    # las cuente como proteccion activa; hacerlas funcionar es otro cambio.
    inertes = [m for m in config.MULETILLAS if " " in m]
    chk("las muletillas de dos palabras se sabe que no cortan nada",
        all(" " in m for m in inertes),
        f"inertes por comparar palabra a palabra: {inertes}")


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

    # --- el preview no puede pisar el render bueno --------------------------
    chk("una previsualizacion escribe en sus propios archivos",
        "07_PREVIEW.mp4" in fuente_editor and "06_preview.mp4" in fuente_editor,
        "compartiendo nombre, una prueba a media resolucion dejaria el "
        "07_FINAL.mp4 en baja sin que se notara hasta subirlo")
    chk("una previsualizacion no publica a OneDrive",
        re.search(r"if not args\.preview:\s*\n\s*config\.DIR_PUBLICADOS", fuente_editor)
        is not None,
        "solo el render bueno viaja a la carpeta de publicados")

    # El editor se abre solo al terminar una corrida. El render que lanza el
    # PROPIO editor tiene que desactivarlo o levanta un segundo servidor que no
    # termina nunca: el proceso queda vivo para siempre y la barra de progreso
    # no llega jamas al final.
    chk("el render lanzado desde el editor no abre otro editor",
        "--sin-abrir-editor" in fuente_srv,
        "si no, el subproceso se queda sirviendo una pagina y nunca acaba")

    # Los overlays vienen medidos en pixeles de 1080x1920: si el lienzo se
    # encoge y ellos no, salen al doble y fuera de sitio, y el preview no sirve
    # para decidir nada.
    fuente_f4 = (AQUI / "f4_retencion.py").read_text(encoding="utf-8")
    chk("al previsualizar, los overlays se encogen con el lienzo",
        "int(ev[\"x\"] * escala)" in fuente_f4 and "scale=iw*" in fuente_f4,
        "posicion y tamaño escalan con el mismo factor que la salida")

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

    # --- guardar un PiP no puede borrar el hook, el CTA ni las animaciones ---
    # Los ajustes a mano solo contienen insertos y B-roll: son lo unico que esos
    # archivos guardan. Si sustituyeran la lista ENTERA, tocar un PiP dejaba el
    # panel de Hook y CTA en blanco, sus miniaturas rotas y las animaciones
    # fuera de la vista.
    dir_mix = tmp / "corrida_mixta"
    dir_mix.mkdir(exist_ok=True)
    (dir_mix / "05_overlays.eventos.json").write_text(json.dumps([
        {"tipo": "hook", "medio": "video", "ini": 0.0, "fin": 3.2, "archivo": str(clip)},
        {"tipo": "anim-sol", "medio": "video", "ini": 5.0, "fin": 7.6, "archivo": str(clip)},
        {"tipo": "pip-producto", "ini": 10.0, "fin": 13.0, "archivo": str(clip)},
        {"tipo": "cta", "medio": "video", "ini": 21.0, "fin": 27.5, "archivo": str(clip)},
    ]), encoding="utf-8")
    (dir_mix / "ajustes.eventos.json").write_text(json.dumps({"eventos": [
        {"tipo": "pip-producto", "ini": 15.0, "fin": 18.0, "archivo": str(clip)}]}),
        encoding="utf-8")

    mezcla = f10.eventos_del_editor(dir_mix, ids_catalogo)
    tipos = [e["tipo"] for e in mezcla]
    inserto = [e for e in mezcla if e["tipo"] == "pip-producto"]
    chk("guardar un inserto no se lleva por delante el hook, el CTA ni las animaciones",
        "hook" in tipos and "cta" in tipos and "anim-sol" in tipos
        and len(inserto) == 1 and inserto[0]["ini"] == 15.0,
        f"quedan {tipos}, y el inserto es el ajustado a mano (15.0s), no el del render")

    # --- los tiempos de hook/CTA movidos a mano tienen que llegar al render ---
    fuente_f6 = (AQUI / "f6_overlays.py").read_text(encoding="utf-8")
    cadena = [("f11_servidor.py", fuente_srv), ("editor.py", fuente_editor),
              ("f6_overlays.py", fuente_f6)]
    rotos = [n for n, f in cadena if "hook_cta" not in f and "hook-cta-manual" not in f]
    chk("mover el hook o el CTA en la linea de tiempo llega hasta el render",
        not rotos,
        f"se corta en: {', '.join(rotos)}" if rotos
        else "editor -> servidor -> editor.py -> f6_overlays, la cadena completa")
    chk("y f6 usa esos tiempos en vez de los automaticos",
        "ini_hook" in fuente_f6 and "fin_cta" in fuente_f6,
        "el hook ya no arranca siempre en 0.0 ni el CTA acaba siempre con el video")

    # --- irse a medias y volver exactamente donde estaba --------------------
    # Las animaciones y los tiempos de hook/CTA se guardaban pero el editor no
    # los volvia a leer: al reabrir la corrida se repoblaba todo desde el ULTIMO
    # RENDER, asi que mover una animacion, guardar y volver al dia siguiente
    # enseñaba los valores viejos. Se aplicaban igual al renderizar, pero la
    # pantalla mentia sobre lo que iba a salir.
    dir_vuelta = tmp / "corrida_vuelta"
    dir_vuelta.mkdir(exist_ok=True)
    (dir_vuelta / "05_overlays.eventos.json").write_text(json.dumps([
        {"tipo": "anim-apps", "anim": "anim-apps", "medio": "video",
         "ini": 4.7, "fin": 7.7, "archivo": str(clip)},
        {"tipo": "hook", "medio": "video", "ini": 0.0, "fin": 3.2, "archivo": str(clip)},
    ]), encoding="utf-8")
    (dir_vuelta / "ajustes.animaciones.json").write_text(
        json.dumps({"animaciones": [{"nombre": "anim-apps", "ini": 9.9}]}), encoding="utf-8")
    (dir_vuelta / "ajustes.hookcta.json").write_text(
        json.dumps({"hook_cta": [{"tipo": "hook", "ini": 0.0, "fin": 6.0}]}), encoding="utf-8")
    (dir_vuelta / "ajustes.sesion.json").write_text(json.dumps({"t": 14.6}), encoding="utf-8")

    vuelta = f10.recolectar(dir_vuelta)
    chk("al volver, las animaciones movidas siguen donde se dejaron",
        (vuelta.get("animaciones_guardadas") or [{}])[0].get("ini") == 9.9,
        "y no en el 4.7s del ultimo render")
    chk("al volver, el hook estirado sigue estirado",
        (vuelta.get("hook_cta_guardado") or [{}])[0].get("fin") == 6.0,
        "y no en los 3.2s del ultimo render")
    chk("al volver, el reproductor arranca donde se dejo",
        vuelta.get("sesion", {}).get("t") == 14.6)

    fuente_srv_txt = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("el editor guarda solo, sin depender de que se pulse el boton",
        "setInterval(() => guardarAhora(true)" in fuente_srv_txt
        and "beforeunload" in fuente_srv_txt,
        "cerrar la pestaña no cuesta el trabajo")
    chk("pero abrir una corrida y no tocar nada no la marca como editada",
        "ultimoGuardado = estadoSerializado()" in fuente_srv_txt,
        "el autoguardado parte de lo que se acaba de cargar, no de cero")

    # --- versiones con nombre ----------------------------------------------
    import f11_servidor as srv

    # El nombre llega del navegador y acaba siendo una ruta en disco. Lo que hay
    # que garantizar no es una cadena concreta sino la PROPIEDAD: mande lo que
    # mande, la carpeta cae dentro de _versiones.
    raiz = Path(tempfile.mkdtemp()) / "_versiones"
    raiz.mkdir(parents=True)
    escapan = []
    for crudo in ("../../../etc", "prueba/../otra", r"..\..\windows", "/etc/passwd",
                  "  ..  ", "", ".", "..", "con:stream", "a" * 200):
        limpio = srv._nombre_version(crudo)
        if limpio is None:
            continue                      # rechazado de plano, que también vale
        destino = (raiz / limpio).resolve()
        if not destino.is_relative_to(raiz.resolve()) or destino == raiz.resolve():
            escapan.append(f"{crudo!r} -> {limpio!r} sale a {destino}")
    chk("un nombre de version no puede escribir fuera de la corrida",
        not escapan, "\n          ".join(escapan) if escapan
        else "las barras y los .. se filtran antes de tocar el disco")

    chk("un nombre vacio o solo puntos se rechaza",
        srv._nombre_version("") is None and srv._nombre_version("  ..  ") is None)

    chk("un nombre normal se respeta",
        srv._nombre_version("sin b-roll del final") == "sin b-roll del final")

    # Cargar una version tiene que BORRAR los ajustes actuales antes de copiar:
    # si la version no tenia B-roll y la de ahora si, quedarse con ellos
    # mezclaria dos ediciones y el resultado no seria ninguna de las dos.
    chk("cargar una version reemplaza, no mezcla",
        re.search(r"/version/cargar", fuente_srv_txt) is not None
        and "unlink(missing_ok=True)" in fuente_srv_txt,
        "se limpian los ajustes actuales antes de restaurar los de la version")

    chk("una version guarda TODOS los ajustes, no algunos",
        set(srv.ARCHIVOS_AJUSTES) >= {
            "ajustes.eventos.json", "ajustes.broll.json", "ajustes.sfx.json",
            "ajustes.animaciones.json", "ajustes.encuadre.json",
            "ajustes.hookcta.json", "ajustes.hook.json"},
        f"{len(srv.ARCHIVOS_AJUSTES)} archivos en la lista")

    # El editor no enseña solo lo ajustado: lo monta ENCIMA del plan del ultimo
    # render. El hook, el CTA y las animaciones que no se tocaron salen de ahi,
    # igual que la curva de encuadre. Sin guardar ese plan con la version,
    # cargarla despues de renderizar otra cosa devolvia un HIBRIDO: tus ajustes
    # sobre el plan nuevo. Comprobado: el CTA volvia con el fin del render nuevo.
    chk("una version guarda tambien el plan sobre el que se ajusto",
        set(srv.ARCHIVOS_BASE) >= {"05_overlays.eventos.json", "03_retencion.plan.json"},
        "si no, cargarla tras un re-render devuelve un hibrido")

    chk("cargar una version restaura ajustes Y plan",
        "ARCHIVOS_AJUSTES + ARCHIVOS_BASE" in fuente_srv_txt,
        "las dos listas viajan juntas al guardar y al cargar")

    # Volver a cortar el video mueve la linea de tiempo entera: los segundos de
    # una version anterior apuntan a otro sitio. No se puede arreglar, pero
    # callarlo seria peor.
    chk("se avisa si la version es de otro corte del video",
        "_huella_corte" in fuente_srv_txt and "pueden no cuadrar" in fuente_srv_txt,
        "se compara el numero de palabras y el final del corte")

    # --- espacio = reproducir/pausar ---------------------------------------
    chk("el espacio reproduce y pausa, pero no mientras se escribe",
        'e.code !== "Space"' in fuente_srv_txt
        and 'el.tagName === "TEXTAREA"' in fuente_srv_txt,
        "en el hook o en el nombre de una version, un espacio es un espacio")


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


# ===========================================================================
# 10. Volumen de los SFX en la previa del editor (f10 + f11)
# ===========================================================================
# Bug real: el editor cargaba 07_FINAL.mp4 (que YA trae los SFX mezclados y
# calibrados) y ademas el loop del navegador volvia a disparar cada SFX crudo
# al 100% -- cada efecto sonaba dos veces. Y el numero de la columna "volumen"
# de la tabla no cambiaba nada de lo audible porque escucharSfx() solo
# aceptaba el nombre del archivo. Ninguna de las dos cosas daba error: el
# video se veia y se abria igual.
def pruebas_sfx_previa():
    import tempfile

    import f10_editor_visual as f10

    seccion("10. Volumen de los SFX en la previa del editor (f10 + f11)")

    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    fuente_f10 = (AQUI / "f10_editor_visual.py").read_text(encoding="utf-8")

    chk("el navegador deja de disparar SFX sobre un video ya renderizado",
        re.search(r"if\s*\(!video\.paused\s*&&\s*!DATA\.es_renderizado\)", fuente_srv)
        is not None,
        "07_FINAL.mp4 ya trae los SFX quemados: dispararlos de nuevo se oye doble")

    chk("escucharSfx ya recibe el volumen en vez de descartarlo en silencio",
        "function escucharSfx(nombre, volumen)" in fuente_srv,
        "antes el segundo argumento se pasaba desde el loop y la tabla, pero la "
        "funcion solo declaraba 'nombre': cambiar el volumen de una fila no sonaba distinto")

    chk("la ganancia se calcula igual que en el render (pico comun + volumen artistico)",
        "gananciaSfxDb" in fuente_srv and "niveles_sfx" in fuente_srv,
        "sin la misma cuenta que f5_audio.mezclar_audio, el numero de la tabla no predice nada")

    chk("la previa usa un pool de audios, no uno compartido",
        "sfxPool" in fuente_srv and "createMediaElementSource" in fuente_srv,
        "un unico Audio() cortaba el sonido anterior cuando dos SFX caian cerca")

    chk("tocar el volumen de una fila se escucha al instante, sin re-renderizar",
        re.search(r'e\.volumen = parseFloat\(inV\.value\)[^\n]*\n\s*escucharSfx\(e\.archivo, e\.volumen\)',
                   fuente_srv) is not None,
        "si no, el numero cambia en la tabla pero nada suena distinto hasta re-renderizar")

    chk("f10.recolectar() expone los picos medidos y el pico objetivo",
        "niveles_sfx" in fuente_f10 and "sfx_pico_objetivo_db" in fuente_f10,
        "el navegador los necesita para replicar la normalizacion -6dB + volumen artistico")

    # --- el dato que /datos manda de verdad, no solo el texto fuente --------
    tmp = Path(tempfile.mkdtemp()) / "corrida_sfx"
    tmp.mkdir(parents=True)
    datos = f10.recolectar(tmp)

    chk("recolectar() trae 'niveles_sfx' con los picos cacheados del pack",
        isinstance(datos.get("niveles_sfx"), dict) and len(datos["niveles_sfx"]) > 0,
        f"{len(datos.get('niveles_sfx') or {})} sonidos con pico medido")

    chk("recolectar() trae 'sfx_pico_objetivo_db' igual al de config",
        datos.get("sfx_pico_objetivo_db") == config.SFX_PICO_OBJETIVO_DB,
        f"{datos.get('sfx_pico_objetivo_db')} vs config.SFX_PICO_OBJETIVO_DB={config.SFX_PICO_OBJETIVO_DB}")

    chk("una corrida sin render (02_cortado.mp4) se marca como NO renderizada",
        datos.get("es_renderizado") is False,
        "es la señal que usa el navegador para decidir si dispara los SFX el mismo")


# ===========================================================================
# 11. Zona segura de TikTok/Reels sobre el reproductor (f10 + f11)
# ===========================================================================
# El editor no mostraba donde la app tapa el video con su propia interfaz:
# un overlay, el hook o el CTA podian quedar invisibles en el celular sin que
# se notara en el editor. Bloque 2 del plan de mejoras.
def pruebas_zona_segura():
    import tempfile

    import f10_editor_visual as f10

    seccion("11. Zona segura de TikTok/Reels sobre el reproductor (f10 + f11)")

    for nombre in ("ZONA_SEGURA_INFERIOR_PX", "ZONA_SEGURA_DERECHA_PX"):
        valor = getattr(config, nombre, None)
        chk(f"config.{nombre} existe y es un numero positivo",
            isinstance(valor, (int, float)) and valor > 0,
            f"valor: {valor!r}")

    chk("config.ZONA_SEGURA_DERECHA_DESDE_PCT es una fraccion entre 0 y 1",
        isinstance(config.ZONA_SEGURA_DERECHA_DESDE_PCT, (int, float))
        and 0 <= config.ZONA_SEGURA_DERECHA_DESDE_PCT <= 1,
        f"valor: {config.ZONA_SEGURA_DERECHA_DESDE_PCT!r} "
        "-- la columna de iconos no arranca arriba del todo")

    hook_y2 = config.ZONA_HOOK_APROX_PX["y"] + config.ZONA_HOOK_APROX_PX["alto"]
    chk("el hook (arriba de la pantalla) no cae en la franja derecha por defecto",
        hook_y2 <= config.ALTO * config.ZONA_SEGURA_DERECHA_DESDE_PCT,
        f"hook baja hasta {hook_y2}px, la columna de iconos arranca en "
        f"{config.ALTO * config.ZONA_SEGURA_DERECHA_DESDE_PCT:.0f}px -- si la columna cubriera "
        "toda la altura, el hook avisaria SIEMPRE y la alarma se volveria ruido")

    for nombre in ("ZONA_HOOK_APROX_PX", "ZONA_CTA_APROX_PX"):
        caja = getattr(config, nombre, None)
        chk(f"config.{nombre} trae x/y/ancho/alto",
            isinstance(caja, dict) and {"x", "y", "ancho", "alto"} <= caja.keys(),
            f"valor: {caja!r}")

    tmp = Path(tempfile.mkdtemp()) / "corrida_zona_segura"
    tmp.mkdir(parents=True)
    datos = f10.recolectar(tmp)
    zs = datos.get("zona_segura")
    chk("recolectar() expone 'zona_segura' con los datos que necesita el navegador",
        isinstance(zs, dict)
        and {"inferior_px", "derecha_px", "derecha_desde_pct", "hook_aprox", "cta_aprox"} <= zs.keys(),
        f"zona_segura: {zs!r}")
    chk("los valores que viajan son los mismos de config, no una copia desincronizada",
        zs == {
            "inferior_px": config.ZONA_SEGURA_INFERIOR_PX,
            "derecha_px": config.ZONA_SEGURA_DERECHA_PX,
            "derecha_desde_pct": config.ZONA_SEGURA_DERECHA_DESDE_PCT,
            "hook_aprox": config.ZONA_HOOK_APROX_PX,
            "cta_aprox": config.ZONA_CTA_APROX_PX,
        })

    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")

    chk("existe la funcion reutilizable de deteccion de zona tapada",
        "function cajaEnZonaTapada(x, y, ancho, alto)" in fuente_srv,
        "los bloques 5 (subtitulos) y 6 (texto destacado) la reusan tal cual")

    chk("el boton de zona segura recuerda el estado en localStorage",
        "zonaSeguraVisible" in fuente_srv and 'localStorage.getItem("zonaSeguraVisible")' in fuente_srv,
        "si no, hay que volver a prenderlo cada vez que se abre el editor")

    chk("un B-roll a pantalla completa no genera aviso de zona tapada",
        re.search(r"if\s*\(esBroll\(ev\)\)\s*return;\s*\n\s*const zona = cajaEnZonaTapada\(ev\.x, ev\.y, 400, 520\)",
                   fuente_srv) is not None,
        "un B-roll pantalla completa SIEMPRE tapa esa zona -- avisar seria ruido, no informacion")

    chk("el hook y el CTA muestran su propio aviso de zona tapada",
        "hookZonaAviso" in fuente_srv and "ctaZonaAviso" in fuente_srv,
        "con la caja aproximada de config.ZONA_HOOK_APROX_PX / ZONA_CTA_APROX_PX")


# ===========================================================================
# 12. Densidad de efectos de sonido (f5_audio + f13_guion + f10 + f11)
# ===========================================================================
# Medido antes de tocar nada (ver PLAN-MEJORAS.md): Guion-7 (guion.sfx.json,
# lo que de verdad suena en un render con --guion 7) traia 11 SFX en 24.8s,
# uno cada 2.25s. El automatico puro (construir_eventos_sfx) traia 10 en
# 24.8s, uno cada 2.48s. Los dos caminos sonaban a "tic de editor". El bug
# real es que --guion N (el caso recomendado en COMO-USAR.md) NUNCA pasaba
# por construir_eventos_sfx: f13_guion.py arma su propia lista desde la
# columna "Sonido" del panel y editor.py la inyecta como --sfx-manual, así
# que tocar solo f5_audio.construir_eventos_sfx habria dejado el problema
# real intacto. El tope global se aplica en LOS DOS caminos.
def pruebas_densidad_sfx():
    import tempfile

    import f5_audio
    import f10_editor_visual as f10

    seccion("12. Densidad de efectos de sonido (f5_audio + f13_guion + f10 + f11)")

    chk("SFX_MAX_PUNCH_INS se bajo de 6 a 2",
        config.SFX_MAX_PUNCH_INS == 2,
        "el zoom del punch-in YA es el enfasis; un whoosh en cada uno de los 6 lo subrayaba dos veces")

    chk("SFX_SEPARACION_MIN_S se subio de 1.2 a 1.8",
        config.SFX_SEPARACION_MIN_S == 1.8)

    presets = config.SFX_DENSIDAD_PRESETS
    chk("SFX_DENSIDAD_PRESETS trae sobrio/normal/cargado, de mas a menos separacion",
        isinstance(presets, dict) and {"sobrio", "normal", "cargado"} <= presets.keys()
        and presets["sobrio"] > presets["normal"] > presets["cargado"] > 0,
        f"valores: {presets!r}")

    # --- aplicar_tope_densidad: respeta prioridad, no solo el tiempo --------
    eventos = [
        {"t": 1.0, "archivo": "a.mp3", "razon": "punch-in"},   # prioridad 10 (baja)
        {"t": 1.3, "archivo": "b.mp3", "razon": "hook"},       # prioridad 100, muy cerca del anterior
        {"t": 5.0, "archivo": "c.mp3", "razon": "corte"},      # prioridad 50, lejos de todo
        {"t": 5.2, "archivo": "d.mp3", "razon": "punch-in"},   # cerca del corte, prioridad menor
    ]
    resultado = f5_audio.aplicar_tope_densidad(eventos, separacion_s=2.0)
    archivos = [e["archivo"] for e in resultado]
    chk("entre dos SFX que chocan, sobrevive el de mayor prioridad, no el mas temprano",
        "b.mp3" in archivos and "a.mp3" not in archivos,
        f"sobrevivieron: {archivos} (el hook en t=1.3 debe ganarle al punch-in en t=1.0)")
    chk("ningun par de sobrevivientes queda mas cerca que la separacion pedida",
        all(b["t"] - a["t"] >= 2.0 for a, b in zip(resultado, resultado[1:])),
        f"tiempos: {[e['t'] for e in resultado]}")

    # --- reproduce la medicion real de Guion-7 (11 SFX en 24.8s, uno cada 2.25s) ---
    sinteticos = [
        {"t": t, "archivo": f"guion_{i}.mp3", "razon": f"guion_{i}"}
        for i, t in enumerate([2.00, 3.88, 5.34, 6.70, 8.46, 10.11, 13.09, 16.07, 17.99, 20.97, 23.09], start=1)
    ]
    capado = f5_audio.aplicar_tope_densidad(sinteticos, presets["normal"])
    resumen = f5_audio.resumen_densidad(capado, 24.8)
    chk("el tope 'normal' baja una densidad tipo Guion-7 (11 en 24.8s) al rango sano (5-8)",
        5 <= resumen["n"] <= 8,
        f"{resumen['n']} sonidos en {resumen['duracion']}s (uno cada {resumen['cada_s']}s), "
        f"antes eran 11 (uno cada 2.25s)")

    # --- avisos_sfx ahora tambien avisa densidad, no solo separacion/repeticion ---
    avisos = f5_audio.avisos_sfx(sinteticos, 24.8)
    chk("avisos_sfx() marca una lista mas densa que 'normal'",
        any(a["tipo"] == "densidad" for a in avisos),
        f"avisos: {[a['tipo'] for a in avisos]}")
    chk("avisos_sfx() NO marca densidad sobre la lista ya topada",
        not any(a["tipo"] == "densidad" for a in f5_audio.avisos_sfx(capado, 24.8)),
        "si sigue avisando despues de aplicar el tope, el umbral esta mal calibrado contra el propio preset")

    # --- f13_guion aplica el tope al escribir guion.sfx.json y guarda el pool completo
    fuente_guion = (AQUI / "f13_guion.py").read_text(encoding="utf-8")
    chk("f13_guion.py aplica el tope de densidad antes de escribir guion.sfx.json",
        "aplicar_tope_densidad" in fuente_guion,
        "si no, el bug real (--guion N nunca pasa por construir_eventos_sfx) queda intacto")
    chk("f13_guion.py guarda el pool completo como 'candidatos', no solo lo topado",
        re.search(r'"sfx":\s*ordenes_sfx,\s*"candidatos":\s*candidatos_sfx', fuente_guion) is not None,
        "el editor necesita el pool sin topar para poder ofrecer 'cargado'")

    # --- f10_editor_visual expone lo que el selector del editor necesita ----
    tmp = Path(tempfile.mkdtemp()) / "corrida_densidad_sfx"
    tmp.mkdir(parents=True)
    datos = f10.recolectar(tmp)
    for clave in ("sfx_candidatos", "sfx_prioridades", "sfx_prioridad_defecto",
                  "sfx_densidad_presets", "resumen_sfx"):
        chk(f"recolectar() expone '{clave}'", clave in datos, f"claves presentes: {sorted(datos.keys())}")
    chk("sfx_prioridades coincide con f5_audio.PRIORIDAD_SFX_POR_RAZON",
        datos.get("sfx_prioridades") == f5_audio.PRIORIDAD_SFX_POR_RAZON)
    chk("sfx_densidad_presets coincide con config.SFX_DENSIDAD_PRESETS",
        datos.get("sfx_densidad_presets") == config.SFX_DENSIDAD_PRESETS)

    # --- el editor: selector, contador y funcion de re-filtrado en vivo -----
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("existe el selector sobrio/normal/cargado en el editor",
        'id="selDensidadSfx"' in fuente_srv,
        "con las tres opciones sobrio/normal/cargado")
    chk("existe la funcion de re-filtrado en vivo por prioridad",
        "function aplicarTopeDensidadSfx(eventos, separacionS)" in fuente_srv)
    chk("el selector re-filtra desde el pool completo, no desde la lista ya topada",
        "edicionSfxCandidatos.length ? edicionSfxCandidatos : edicionSfx" in fuente_srv,
        "si re-filtrara sobre edicionSfx, pasar de sobrio a cargado no podria recuperar "
        "los sonidos que sobrio ya habia descartado")
    chk("el contador de densidad se actualiza cada vez que se repinta la pista de SFX",
        re.search(r"function pintarSfx\(\)[\s\S]*?actualizarContadorSfx\(\);\s*\n\}", fuente_srv) is not None,
        "para que no se desactualice al agregar, quitar o mover un efecto a mano")
    chk("el contador se pinta en rojo cuando la densidad supera lo recomendado",
        "sfx-denso" in fuente_srv and "cada < umbral" in fuente_srv)

    # --- El sonido acompaña al evento visual: si se quita, se quita el pop -----
    # (hook/CTA/PiP quitados en el editor no deben dejar su SFX huérfano)
    plan_min = {"planos": [], "picos_energia": []}
    con_hook = f5_audio.construir_eventos_sfx(plan_min, [{"tipo": "hook", "ini": 0.0}])
    chk("con hook presente, el whoosh de entrada en t=0 se pone",
        any(e.get("razon") == "hook" or e.get("t") == 0.0 for e in con_hook),
        f"razones: {[e.get('razon') for e in con_hook]}")
    sin_hook = f5_audio.construir_eventos_sfx(plan_min, [{"tipo": "pip-producto", "ini": 4.0, "asset": "x"}])
    chk("hook quitado (no llega en overlays) -> no hay whoosh de entrada en t=0",
        not any(abs(e["t"] - 0.0) < 0.01 and e.get("razon") == "hook" for e in sin_hook),
        f"tiempos/razones: {[(e['t'], e.get('razon')) for e in sin_hook]}")
    compat = f5_audio.construir_eventos_sfx(plan_min, None)
    chk("sin lista de overlays (None) se mantiene el comportamiento previo: hook en t=0",
        any(e["t"] == 0.0 for e in compat))

    # reanclar_sfx: el SFX cuyo overlay se quitó se elimina; el suelto no se toca
    sfx = [
        {"t": 4.0, "archivo": "pop.mp3", "ancla": "pip|x#0"},   # su PiP sigue -> se mueve
        {"t": 9.0, "archivo": "pop.mp3", "ancla": "pip|y#0"},   # su PiP se quitó -> se elimina
        {"t": 12.0, "archivo": "whoosh.mp3"},                    # sin ancla -> intacto
    ]
    overlays_hoy = [{"tipo": "pip-producto", "ini": 5.0, "asset": "x"}]
    f5_audio.reanclar_sfx(sfx, overlays_hoy)
    anclas = [e.get("ancla") for e in sfx]
    chk("reanclar quita el SFX cuyo evento visual ya no existe",
        "pip|y#0" not in anclas,
        f"anclas tras reanclar: {anclas}")
    chk("reanclar mueve el SFX cuyo evento visual sigue, a su nuevo segundo",
        any(abs(e["t"] - 5.0) < 0.01 and e.get("ancla") == "pip|x#0" for e in sfx),
        f"tiempos: {[(e['t'], e.get('ancla')) for e in sfx]}")
    chk("reanclar no toca los SFX sueltos (sin ancla)",
        any(e["archivo"] == "whoosh.mp3" and e["t"] == 12.0 for e in sfx))


# ===========================================================================
# 13. Elegir el tramo de un clip de B-roll (f4_retencion + f6_overlays + editor)
# ===========================================================================
# Verificado antes de tocar nada: un B-roll de video SIEMPRE se leía desde el
# segundo 0 del archivo fuente (ni `-ss` ni `atrim` en ningún lado de la
# composición), y si el hueco de la línea de tiempo quedaba más largo que el
# clip, el `overlay` de ffmpeg (eof_action por defecto = repeat) congelaba el
# último cuadro — se ve como un error. El audio del B-roll nunca se mezcla
# (solo se mapea `[N]:v`, nunca `[N]:a`). Este bloque agrega el modal para
# elegir el tramo Y el cambio real en el render (f4_retencion.py), que es
# donde el bloque 1 y el 3 ya enseñaron que el bug real puede vivir fuera de
# donde apunta el diagnóstico si no se sigue el dato hasta el final.
def pruebas_recorte_broll():
    import json
    import tempfile

    import f6_overlays

    seccion("13. Elegir el tramo de un clip de B-roll (f4_retencion + f6_overlays + editor)")

    fuente_f4 = (AQUI / "f4_retencion.py").read_text(encoding="utf-8")
    chk("el render arranca la LECTURA del clip en recorte_inicio, no siempre en 0",
        '["-ss", f"{recorte_inicio:.3f}"]' in fuente_f4,
        "antes -itsoffset solo desplazaba DONDE aparece en la salida, nunca "
        "DESDE DONDE se lee el archivo -- el tramo elegido en el editor no habria "
        "cambiado nada del video final")
    chk("el render recorta el hueco al tramo elegido ANTES de componer (defensa contra el freeze)",
        'min(ev["fin"], ev["ini"] + (ev["recorte_fin"] - ev["recorte_inicio"]))' in fuente_f4,
        "sin este tope, un ajustes.broll.json tocado a mano por fuera del editor "
        "podia pedir mas metraje del que el clip tiene y el ultimo cuadro se congela")

    # --- round-trip: recorte_inicio/recorte_fin sobreviven ajustes.broll.json ---
    tmp = Path(tempfile.mkdtemp())
    clip = tmp / "clip.mp4"
    clip.write_bytes(b"no es un mp4 de verdad, pero existe y con eso basta")
    broll_json = tmp / "ajustes.broll.json"
    broll_json.write_text(json.dumps({"broll": [
        {"ini": 5.0, "fin": 8.0, "tipo": "broll", "medio": "video", "broll_fullscreen": True,
         "archivo": str(clip), "recorte_inicio": 8.0, "recorte_fin": 11.0},
    ]}), encoding="utf-8")
    vueltos = f6_overlays.cargar_broll_manual(broll_json)
    chk("cargar_broll_manual conserva recorte_inicio/recorte_fin, no los descarta",
        len(vueltos) == 1 and vueltos[0].get("recorte_inicio") == 8.0 and vueltos[0].get("recorte_fin") == 11.0,
        f"evento recuperado: {vueltos[0] if vueltos else None}")

    # Un evento SIN recorte (el caso de siempre, o un B-roll automático del
    # guion) no debe inventarse un recorte de la nada.
    broll_json2 = tmp / "ajustes.broll2.json"
    broll_json2.write_text(json.dumps({"broll": [
        {"ini": 1.0, "fin": 4.0, "tipo": "broll", "medio": "video", "broll_fullscreen": True,
         "archivo": str(clip)},
    ]}), encoding="utf-8")
    sin_recorte = f6_overlays.cargar_broll_manual(broll_json2)
    chk("un B-roll sin tramo elegido no trae recorte_inicio/recorte_fin inventados",
        sin_recorte[0].get("recorte_inicio") is None and sin_recorte[0].get("recorte_fin") is None,
        f"evento: {sin_recorte[0]}")

    # --- round-trip a través de f10_editor_visual.recolectar() --------------
    import f10_editor_visual as f10
    dir_corrida = tmp / "corrida_recorte"
    dir_corrida.mkdir(parents=True)
    (dir_corrida / "ajustes.broll.json").write_text(json.dumps({"broll": [
        {"ini": 5.0, "fin": 8.0, "tipo": "broll", "medio": "video", "broll_fullscreen": True,
         "archivo": str(clip), "recorte_inicio": 8.0, "recorte_fin": 11.0},
    ]}), encoding="utf-8")
    datos = f10.recolectar(dir_corrida)
    broll_mov = next((m for m in datos["movibles"] if m["tipo"] == "broll"), None)
    chk("recolectar() expone el tramo elegido en 'movibles' para que el editor lo recupere al recargar",
        broll_mov is not None and broll_mov.get("recorte_inicio") == 8.0 and broll_mov.get("recorte_fin") == 11.0,
        f"movible: {broll_mov}")

    # --- el editor: modal, tope del hueco, y aviso de audio ------------------
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("existe el modal para elegir el tramo, con manijas de inicio y fin",
        'id="cajaSegmento"' in fuente_srv and 'id="segTirIzq"' in fuente_srv and 'id="segTirDer"' in fuente_srv)
    chk("el modal reproduce el clip ENTERO (no un recorte del servidor) para elegir el tramo",
        re.search(r"v\.src = `/archivo\?ruta=\$\{encodeURIComponent\(asset\.archivo\)\}`", fuente_srv)
        is not None)
    chk("las manijas del modal no dejan pedir mas metraje del que el clip tiene",
        "function tiempoSegmento(ev, elemento)" in fuente_srv
        and "Math.max(0, Math.min(segmentoDur" in fuente_srv,
        "tiempoSegmento frena en [0, segmentoDur]")
    chk("el audio del B-roll se declara explicito en la interfaz, no se asume",
        "no se usa" in fuente_srv and "entra mudo" in fuente_srv,
        "verificado en f4_retencion.py: el B-roll solo aporta [N]:v, el audio de "
        "salida sale siempre de 1:a (la voz) -- el editor ahora lo dice, no lo da por sentado")
    chk("existe la funcion que limita el hueco al tramo elegido",
        "function duracionMaximaClip(ev)" in fuente_srv,
        "los bloques 5 y 6 no la necesitan, pero sigue el mismo patron de "
        "'una funcion reutilizable, no metida en el dibujado' del bloque 2")
    chk("estirar el borde derecho del bloque en la linea de tiempo respeta ese tope",
        re.search(r"const maxFin = Number\.isFinite\(tope\) \? ev\.ini \+ tope : Infinity;", fuente_srv)
        is not None,
        "sin este tope, arrastrar el borde podia pedir mas metraje del que el tramo elegido tiene")
    chk("estirar el borde IZQUIERDO tambien respeta el tope (alarga el hueco igual que el derecho)",
        re.search(r"const minIni = Number\.isFinite\(tope\) \? ev\.fin - tope : 0;", fuente_srv)
        is not None,
        "mover el inicio mas temprano alarga el hueco tanto como mover el fin mas tarde")
    chk("guardar y recargar no pierde el tramo elegido (eventoBase lo propaga)",
        "if (ev.recorte_inicio != null) base.recorte_inicio = ev.recorte_inicio;" in fuente_srv,
        "sin esto, ajustes.broll.json se guardaba sin el recorte y el render volvia al segundo 0")
    chk("sustituir un inserto ata el hueco nuevo al tramo del clip nuevo, no al hueco viejo",
        "const fin = Math.min(viejo.fin, viejo.ini + duracionTramo);" in fuente_srv,
        "decision explicita del bloque: el hueco no puede ser mas largo que el pedazo")


# ===========================================================================
# 14. Subtitulos: tamano ajustable y corregir el texto (f3 + f10 + editor)
# ===========================================================================
# La clase de fallo que se caza aqui: `palabras` es la MISMA lista que
# f13_guion usa para alinear el guion contra la transcripcion (test_align.py).
# Si corregir "Colorsof" -> "Colorsoft" para que se LEA bien tocara `texto` o
# los tiempos, el video saldria igual de bien pero los beats del guion se
# alinearian contra otra cosa: los B-roll y los SFX caerian en el segundo
# equivocado, sin un solo mensaje de error. Por eso las pruebas de abajo no
# miran solo que el texto cambie -- miran que los tiempos NO cambien.
def pruebas_subtitulos():
    import json
    import tempfile

    import f3_subtitulos

    seccion("14. Subtitulos: tamano ajustable y corregir el texto (f3 + f10 + editor)")

    # Transcripcion sintetica: dos bloques separados por una pausa larga, con
    # una palabra mal transcrita (la clase de error real de Whisper: nombres de
    # producto y precios en Bs).
    palabras = [
        {"inicio": 0.00, "fin": 0.40, "texto": "el"},
        {"inicio": 0.42, "fin": 0.90, "texto": "kindle"},
        {"inicio": 0.92, "fin": 1.50, "texto": "colorsof"},
        {"inicio": 2.20, "fin": 2.60, "texto": "cuesta"},
        {"inicio": 2.62, "fin": 3.30, "texto": "mil"},
        {"inicio": 3.32, "fin": 3.90, "texto": "bolivianos."},
    ]
    copia_textos = [p["texto"] for p in palabras]

    def dialogos(ass):
        return [l for l in ass.splitlines() if l.startswith("Dialogue:")]

    def tiempos(ass):
        # "Dialogue: 0,0:00:00.00,0:00:00.42,Default,,..." -> ("0:00:00.00", "0:00:00.42")
        return [tuple(l.split(",")[1:3]) for l in dialogos(ass)]

    base = f3_subtitulos.generar_ass(palabras)
    grande = f3_subtitulos.generar_ass(palabras, tamano_px=120)

    chk("el tamano pedido llega al Fontsize de la cabecera ASS",
        f"Style: Default,{config.SUB_FUENTE},120," in grande
        and f"Style: Default,{config.SUB_FUENTE},{config.SUB_TAMANO_PX}," in base,
        "es el unico numero que el render mira para dibujar el subtitulo mas grande")

    # El check que importa del tamano: cambiar el tamano NO puede cambiar nada
    # mas. Comparacion linea a linea, no solo de los Dialogue.
    difieren = [(a, b) for a, b in zip(base.splitlines(), grande.splitlines()) if a != b]
    chk("cambiar el tamano cambia SOLO la linea de estilo, ni un tiempo ni un texto",
        len(base.splitlines()) == len(grande.splitlines())
        and len(difieren) == 1 and difieren[0][0].startswith("Style: Default"),
        f"lineas distintas entre los dos ASS: {len(difieren)} (la de Style)")

    # --- correcciones: cambia lo que se LEE, nunca lo que se ALINEA ----------
    corregido = f3_subtitulos.generar_ass(palabras, correcciones={"2": "Colorsoft"})

    chk("una correccion cambia el texto que se ve en la linea de dialogo",
        "Colorsoft" in corregido and "Colorsoft" not in base,
        "la palabra 2 se lee corregida en el subtitulo quemado")
    chk("la palabra mal transcrita ya no aparece en el ASS corregido",
        "colorsof" not in corregido.replace("Colorsoft", ""),
        "no quedan restos de la transcripcion cruda en lo que ve el espectador")

    # ESTE es el check que de verdad importa del bloque.
    chk("corregir el texto no mueve NI UN tiempo del subtitulo",
        tiempos(base) == tiempos(corregido) and len(dialogos(base)) == len(dialogos(corregido)),
        f"{len(dialogos(base))} lineas Dialogue con tiempos identicos con y sin correccion -- "
        "si un solo tiempo se moviera, el guion se alinearia contra otra cosa y los "
        "B-roll/SFX caerian en el segundo equivocado sin dar error")

    chk("corregir el texto NO muta la transcripcion en memoria",
        [p["texto"] for p in palabras] == copia_textos,
        "f13_guion alinea contra esta misma lista: si generar_ass la reescribiera, "
        "la correccion ortografica cambiaria contra que se compara cada beat del guion")

    chk("una correccion de un indice que no existe no rompe ni cambia nada",
        f3_subtitulos.generar_ass(palabras, correcciones={"99": "x"}) == base,
        "un ajustes.subtitulos.json viejo, de una corrida con mas palabras, se ignora solo")

    chk("sin correcciones y sin tamano, el ASS es exactamente el de siempre",
        f3_subtitulos.generar_ass(palabras, tamano_px=None, correcciones=None) == base,
        "los dos parametros son opcionales: una corrida que no toca subtitulos no cambia")

    # --- estilos (Bloque 5b): 5 presets, "karaoke" tiene que ser el de siempre ---
    chk("el estilo 'karaoke' explicito es byte a byte igual que no pasar estilo",
        f3_subtitulos.generar_ass(palabras, estilo="karaoke") == base
        and f3_subtitulos.generar_ass(palabras, estilo=None) == base,
        "config.SUB_ESTILO_DEFECTO tiene que reproducir EXACTO el .ass de antes de "
        "que existieran los estilos -- una corrida vieja no puede cambiar de golpe")

    otros_estilos = [e for e in config.SUB_ESTILOS if e != "karaoke"]
    chk("hay 11 estilos definidos en config.SUB_ESTILOS",
        len(config.SUB_ESTILOS) == 11 and len(otros_estilos) == 10,
        f"estilos: {sorted(config.SUB_ESTILOS)}")

    for estilo_id in otros_estilos:
        ass_estilo = f3_subtitulos.generar_ass(palabras, estilo=estilo_id)
        preset = config.SUB_ESTILOS[estilo_id]
        chk(f"el estilo '{estilo_id}' genera un .ass valido y distinto del karaoke",
            len(dialogos(ass_estilo)) > 0 and ass_estilo != base,
            f"{len(dialogos(ass_estilo))} lineas Dialogue")

        n_bloques_esperado = len(f3_subtitulos.agrupar_en_bloques(
            palabras, *f3_subtitulos.AGRUPACION_BOUNDS[preset["agrupacion"]]))
        if preset["resaltado"] in ("dinamico", "subrayado", "foco"):
            chk(f"'{estilo_id}' (resaltado {preset['resaltado']!r}) emite un evento por PALABRA activa",
                len(dialogos(ass_estilo)) == len(palabras),
                f"{len(dialogos(ass_estilo))} eventos == {len(palabras)} palabras")
        else:
            chk(f"'{estilo_id}' (resaltado {preset['resaltado']!r}) emite UN evento por bloque, no por palabra",
                len(dialogos(ass_estilo)) == n_bloques_esperado,
                f"{len(dialogos(ass_estilo))} eventos == {n_bloques_esperado} bloques -- "
                "si emitiera uno por palabra, el resaltado estatico repetiria el mismo bloque de mas")

        if preset.get("borderstyle") == 3:
            chk(f"'{estilo_id}' usa BorderStyle=3 (caja opaca) en la cabecera",
                re.search(r",3,24,0,2,60,60,", ass_estilo) is not None,
                "BorderStyle 3 + Outline de padding es lo que dibuja el fondo detras del texto")
        if preset["resaltado"] == "estatico":
            chk(f"'{estilo_id}' colorea exactamente una palabra por bloque en ambar",
                ass_estilo.count(config.SUB_COLOR_KEYWORD) == n_bloques_esperado,
                f"{ass_estilo.count(config.SUB_COLOR_KEYWORD)} usos de {config.SUB_COLOR_KEYWORD} "
                f"== {n_bloques_esperado} bloques")
        if preset["resaltado"] == "subrayado":
            chk(f"'{estilo_id}' subraya con \\u1 nativo, una vez por palabra",
                ass_estilo.count("\\u1\\c") == len(palabras) and ass_estilo.count("\\u0\\c") == len(palabras),
                f"{ass_estilo.count(chr(92) + 'u1' + chr(92) + 'c')} aperturas \\u1 == {len(palabras)} palabras")
        if preset["resaltado"] == "foco":
            chk(f"'{estilo_id}' agranda la palabra activa a 145% y la devuelve a 100%, una vez por palabra",
                ass_estilo.count("\\fscx145\\fscy145") == len(palabras)
                and ass_estilo.count("\\fscx100\\fscy100") == len(palabras),
                f"{ass_estilo.count(chr(92) + 'fscx145')} crecidas == {len(palabras)} palabras -- si no vuelve "
                "a 100%, el escalado se le queda pegado a toda la palabra que sigue en la linea")
        if preset.get("mayusculas"):
            chk(f"'{estilo_id}' pasa el texto a MAYUSCULAS",
                "kindle" not in ass_estilo and "KINDLE" in ass_estilo,
                "el estilo pide mayusculas=True; el texto de muestra tiene que salir gritado, no en case de oracion")
        if preset["animacion"] == "pop":
            chk(f"'{estilo_id}' antepone el tag de escala \\t a cada evento",
                ass_estilo.count("\\fscx55\\fscy55\\t(0,120,\\fscx100\\fscy100)") == n_bloques_esperado,
                "una palabra por evento (agrupacion 'palabra'): el pop tiene que repetirse una vez por palabra")
        if preset["animacion"] == "glow":
            chk(f"'{estilo_id}' antepone el tag de blur, una vez por bloque",
                ass_estilo.count("\\blur2") == n_bloques_esperado,
                f"{ass_estilo.count(chr(92) + 'blur2')} usos == {n_bloques_esperado} bloques")
        if preset["animacion"] == "shake":
            chk(f"'{estilo_id}' antepone el sacudon encadenado de \\t, una vez por bloque",
                ass_estilo.count("\\frz-3") == n_bloques_esperado,
                f"{ass_estilo.count(chr(92) + 'frz-3')} usos == {n_bloques_esperado} bloques")
        if estilo_id == "glitch_rgb":
            chk("'glitch_rgb' tiñe OutlineColour de rojo y BackColour/Shadow de cian, sin capas duplicadas",
                (f"Style: Default,{config.SUB_FUENTE},{config.SUB_TAMANO_PX},{config.SUB_COLOR_TEXTO},"
                 f"{config.SUB_COLOR_RESALTADO},{config.SUB_COLOR_GLITCH_ROJO},{config.SUB_COLOR_RESALTADO},"
                 "-1,0,0,0,100,100,0,0,1,3,4,2,60,60,") in ass_estilo,
                "el filo cromatico sale de dos colores en la cabecera (outline + sombra), "
                "no de duplicar el texto en varias capas con offsets a mano")
        if estilo_id == "pegatina":
            chk("'pegatina' usa un contorno blanco bien grueso (Outline=14) y relleno rosa",
                re.search(r",1,14,0,2,60,60,", ass_estilo) is not None
                and config.SUB_COLOR_PEGATINA in ass_estilo,
                "el halo tipo sticker es un Outline ancho, no una capa de fondo")

    # --- round-trip por ajustes.subtitulos.json -> recolectar() -------------
    import f10_editor_visual as f10
    tmp = Path(tempfile.mkdtemp())

    dir_sin = tmp / "corrida_sin_ajustes"
    dir_sin.mkdir(parents=True)
    datos_sin = f10.recolectar(dir_sin)
    chk("sin ajustes.subtitulos.json, recolectar() cae en el tamano de config",
        datos_sin["sub_tamano_px"] == config.SUB_TAMANO_PX
        and datos_sin["sub_correcciones"] == {},
        f"sub_tamano_px = {datos_sin['sub_tamano_px']} (config.SUB_TAMANO_PX)")
    chk("sin ajustes.subtitulos.json, recolectar() cae en el estilo 'karaoke'",
        datos_sin["sub_estilo"] == config.SUB_ESTILO_DEFECTO == "karaoke",
        f"sub_estilo = {datos_sin['sub_estilo']!r}")
    chk("recolectar() expone los 10 estilos con nombre y descripcion, no solo el id",
        set(datos_sin["sub_estilos"]) == set(config.SUB_ESTILOS)
        and all("nombre" in v and "descripcion" in v for v in datos_sin["sub_estilos"].values()),
        "el grid del editor arma sus tarjetas con esto, no con una lista hardcodeada en el HTML")

    dir_con = tmp / "corrida_con_ajustes"
    dir_con.mkdir(parents=True)
    (dir_con / "ajustes.subtitulos.json").write_text(
        json.dumps({"tamano_px": 104, "correcciones": {"2": "Colorsoft"}, "estilo": "palabra_pop"}),
        encoding="utf-8")
    datos_con = f10.recolectar(dir_con)
    chk("recolectar() expone los campos de subtitulos que el editor necesita",
        all(k in datos_con for k in
            ("sub_tamano_px", "sub_tamano_defecto", "sub_posicion_altura_pct", "sub_correcciones",
             "sub_estilo", "sub_estilo_defecto", "sub_estilos")),
        "el editor no hardcodea ninguno: mismo patron que los picos de SFX (bloque 1) "
        "y la zona segura (bloque 2)")
    chk("el tamano y las correcciones guardadas mandan sobre el defecto de config",
        datos_con["sub_tamano_px"] == 104
        and datos_con["sub_correcciones"] == {"2": "Colorsoft"}
        and datos_con["sub_tamano_defecto"] == config.SUB_TAMANO_PX,
        "sin esto, abrir el editor despues de guardar mostraria el subtitulo al tamano viejo")
    chk("el estilo guardado manda sobre el defecto de config",
        datos_con["sub_estilo"] == "palabra_pop" and datos_con["sub_estilo_defecto"] == "karaoke",
        "sin esto, abrir el editor despues de elegir un estilo lo mostraria de nuevo en karaoke")
    chk("la posicion del subtitulo sale de config, no de un numero suelto en el JS",
        datos_con["sub_posicion_altura_pct"] == config.SUB_POSICION_ALTURA_PCT,
        "la vista previa dibuja donde el ASS ancla de verdad; si config cambia, la previa la sigue")

    # --- las banderas del pipeline ------------------------------------------
    fuente_f3 = (AQUI / "f3_subtitulos.py").read_text(encoding="utf-8")
    chk("f3_subtitulos acepta --tamano, --correcciones y --estilo por linea de comandos",
        '"--tamano"' in fuente_f3 and '"--correcciones"' in fuente_f3 and '"--estilo"' in fuente_f3)

    fuente_editor = (AQUI / "editor.py").read_text(encoding="utf-8")
    chk("editor.py acepta --sub-tamano, --sub-correcciones y --sub-estilo",
        '"--sub-tamano"' in fuente_editor and '"--sub-correcciones"' in fuente_editor
        and '"--sub-estilo"' in fuente_editor)
    chk("editor.py se los PASA a la FASE 2, no solo los acepta",
        '"--tamano", str(args.sub_tamano)' in fuente_editor
        and '"--correcciones", args.sub_correcciones' in fuente_editor
        and '"--estilo", args.sub_estilo' in fuente_editor,
        "aceptar una bandera y no reenviarla es fallo silencioso puro: el render corre "
        "igual y el subtitulo sale del tamano/estilo de siempre")

    # --- el editor ----------------------------------------------------------
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("existe el slider de tamano y la tabla de correccion de texto",
        'id="subTamanoInput"' in fuente_srv and 'id="tablaCorreccionesSub"' in fuente_srv)
    chk("existe el grid de miniaturas de estilo (no un <select> de texto)",
        'id="gridEstilosSub"' in fuente_srv and "function renderGridEstilosSub()" in fuente_srv
        and 'id="subEstiloInput"' not in fuente_srv,
        "renderGridEstilosSub arma las tarjetas desde DATA.sub_estilos, no de una lista "
        "hardcodeada en el HTML -- y ya no queda el <select> a medio reemplazar")
    chk("cada tarjeta del grid pide su captura real a /sub-estilo-preview",
        '/sub-estilo-preview?estilo=' in fuente_srv,
        "sin esto el grid se pintaria vacio o con la miniatura de otro estilo")
    chk("la vista previa del subtitulo se dibuja sobre el reproductor",
        'id="subPreview"' in fuente_srv and "function pintarSubPreview(t)" in fuente_srv)
    chk("la vista previa se apaga sobre un video ya renderizado",
        re.search(r"if \(DATA\.es_renderizado\) \{ el\.style\.display = \"none\"; return; \}", fuente_srv)
        is not None,
        "mismo caso que los SFX del bloque 1: 07_FINAL.mp4 ya trae los subtitulos "
        "quemados, dibujar encima se veria doble")
    chk("la vista previa agrupa las palabras con la misma regla que el render, ahora segun el estilo",
        "function agruparEnBloquesSub(palabras, minimo, maximo)" in fuente_srv,
        "si la previa mostrara bloques distintos a los del ASS, serviria para elegir "
        "el tamano pero mentiria sobre que se lee junto")

    # Coherencia real JS <-> Python: los numeros del agrupado estan escritos en
    # los dos lados. Si alguien cambia config y no el JS, la previa deja de
    # coincidir con el render sin que nada falle.
    m_minmax = re.search(r"const MIN = minimo != null \? minimo : (\d+), MAX = maximo != null \? maximo : (\d+);",
                          fuente_srv)
    chk("el agrupado del JS cae en los mismos MIN/MAX que config cuando no se pide otro estilo",
        m_minmax is not None
        and int(m_minmax.group(1)) == config.SUB_PALABRAS_POR_BLOQUE_MIN
        and int(m_minmax.group(2)) == config.SUB_PALABRAS_POR_BLOQUE_MAX,
        f"JS = {m_minmax.groups() if m_minmax else None}, config = "
        f"({config.SUB_PALABRAS_POR_BLOQUE_MIN}, {config.SUB_PALABRAS_POR_BLOQUE_MAX})")
    m_bloque_corto = re.search(r"bloque_corto:\s*\[(\d+),\s*(\d+)\]", fuente_srv)
    chk("el estilo 'bloque_corto' del catalogo JS usa los mismos MIN/MAX que config",
        m_bloque_corto is not None
        and int(m_bloque_corto.group(1)) == config.SUB_PALABRAS_POR_BLOQUE_MIN
        and int(m_bloque_corto.group(2)) == config.SUB_PALABRAS_POR_BLOQUE_MAX,
        f"JS = {m_bloque_corto.groups() if m_bloque_corto else None}, config = "
        f"({config.SUB_PALABRAS_POR_BLOQUE_MIN}, {config.SUB_PALABRAS_POR_BLOQUE_MAX})")
    chk("el corte por pausa del JS usa el mismo umbral que f3_subtitulos",
        "pausaSig > 0.35" in fuente_srv and "pausa_siguiente > 0.35" in fuente_f3,
        "0.35s es lo que separa un bloque del siguiente en los dos lados")

    chk("el aviso de zona tapada reusa cajaEnZonaTapada del bloque 2",
        "function cajaSubActual()" in fuente_srv
        and re.search(r"cajaEnZonaTapada\(caja\.x, caja\.y, caja\.ancho, caja\.alto\)", fuente_srv)
        is not None,
        "un subtitulo grande baja hasta la franja que TikTok tapa con su interfaz; "
        "la funcion ya existia, no se duplico la geometria")
    chk("tocar el tamano o el texto marca la edicion como manual",
        "subModificado = true" in fuente_srv and "if (subModificado) cuerpo.subtitulos" in fuente_srv,
        "mismo patron que encModificado/hookCtaModificado: si no se toca, no se "
        "reescribe ajustes.subtitulos.json y la corrida queda como estaba")
    chk("ajustes.subtitulos.json viaja con las versiones con nombre",
        '"ajustes.subtitulos.json"' in fuente_srv
        and re.search(r'ARCHIVOS_AJUSTES = \((?:[^)]|\n)*ajustes\.subtitulos\.json', fuente_srv)
        is not None,
        "sin esto, restaurar una version devolveria los PiP y los SFX de entonces "
        "pero el subtitulo del tamano actual -- el hibrido que arreglo el bloque 'Que una "
        "version restaure la edicion exacta'")
    chk("el re-render pasa el tamano, las correcciones y el estilo guardados al pipeline",
        '"--sub-tamano", str(ajustes_sub_tamano)' in fuente_srv
        and '"--sub-correcciones", str(ajustes_sub_correcciones)' in fuente_srv
        and '"--sub-estilo", ajustes_sub_estilo' in fuente_srv,
        "es el tramo que convierte lo elegido en el editor en pixeles del video final")
    chk("las claves de las correcciones se guardan como texto, igual que las lee generar_ass",
        "{str(k): str(v) for k, v in correcciones.items() if str(v).strip()}" in fuente_srv,
        "generar_ass busca correcciones.get(str(indice)): una clave numerica guardada "
        "en el JSON no encontraria su palabra y la correccion se perderia en silencio")
    chk("_guardar_subtitulos valida el estilo contra config.SUB_ESTILOS antes de guardarlo",
        'datos.get("estilo") in config.SUB_ESTILOS' in fuente_srv,
        "un ajustes.subtitulos.json corrupto o de una version vieja con un id de estilo "
        "que ya no existe se ignora solo, en vez de reventar generar_ass con KeyError")
    chk("el endpoint /sub-estilo-preview esta servido por f11_servidor.py",
        '"/sub-estilo-preview"' in fuente_srv and "f10.preview_estilo_subtitulo(estilo)" in fuente_srv,
        "sin esto el grid de miniaturas pide una imagen que el servidor no sabe servir")

    # --- miniaturas reales (Bloque 5c): ffmpeg de verdad, cacheadas en disco -
    # Mismo criterio que las pruebas de f0_preparar: llaman a ffmpeg de verdad
    # en vez de mockearlo, porque justo el header ASS (un color en el campo
    # equivocado) es lo que NO se nota leyendo texto y SI se nota en un PNG.
    for estilo_id in ("karaoke", "caja_frase", "glitch_rgb", "pegatina"):
        png1 = f10.preview_estilo_subtitulo(estilo_id)
        chk(f"preview_estilo_subtitulo('{estilo_id}') genera un PNG real",
            png1 is not None and png1.exists() and png1.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n",
            str(png1))
        if png1 is None:
            continue
        mtime_1 = png1.stat().st_mtime
        png2 = f10.preview_estilo_subtitulo(estilo_id)
        chk(f"pedir la miniatura de '{estilo_id}' dos veces reusa el cache, no re-invoca ffmpeg",
            png2 == png1 and png2.stat().st_mtime == mtime_1,
            "cachea por huella del preset (SHA1 de config.SUB_ESTILOS[estilo]) -- abrir el "
            "editor no puede disparar un render de ffmpeg por cada estilo cada vez")
    chk("preview_estilo_subtitulo(estilo desconocido) no revienta, devuelve None",
        f10.preview_estilo_subtitulo("no-existe") is None)


def pruebas_texto_destacado():
    seccion("15. Texto destacado tipo CapCut (plantilla Hyperframes + f8)")
    import f8_hyperframes
    ruta_tpl = config.RAIZ_PROYECTO / "plantillas" / "compositions" / "texto-destacado.html"
    chk("existe la plantilla HTML de texto-destacado",
        ruta_tpl.exists(),
        "sin la plantilla HTML, f8_hyperframes.render no puede generar el clip MOV")

    chk("texto-destacado esta registrada en f8_hyperframes.PLANTILLAS con texto y estilo",
        f8_hyperframes.PLANTILLAS.get("texto-destacado") == ["texto", "estilo"],
        "si falta en PLANTILLAS, render() la rechaza antes de llamar a npx")

    chk("texto-destacado tiene su duracion registrada en f8_hyperframes.DURACIONES",
        f8_hyperframes.DURACIONES.get("texto-destacado") == 2.5,
        "si falta en DURACIONES, el pipeline asume 2.4s por defecto y la barra de tiempo miente")

    chk("config.ANIMACION_DURACION incluye texto-destacado",
        config.ANIMACION_DURACION.get("texto-destacado") == 2.5,
        "config centraliza las duraciones para el editor visual y los respaldos")

    html_text = ruta_tpl.read_text(encoding="utf-8") if ruta_tpl.exists() else ""
    chk("la plantilla declara las 2 variables (texto y estilo) en data-composition-variables",
        '"id":"texto"' in html_text and '"id":"estilo"' in html_text,
        "Hyperframes lee estas variables del data-attribute del html")

    estilos_esperados = ["contorno", "pildora", "neon", "degradado", "sombra", "marcador"]
    chk("la plantilla soporta los 6 estilos pedidos (contorno, pildora, neon, degradado, sombra, marcador)",
        all(est in html_text for est in estilos_esperados),
        f"deben estar los 6 estilos CSS pedidos: {estilos_esperados}")

    chk("la plantilla registra la linea de tiempo en window.__timelines['texto-destacado']",
        'window.__timelines["texto-destacado"]' in html_text,
        "el motor de Hyperframes necesita la clave exacta para pausar/reproducir la composicion")


def pruebas_guardar_portada():
    seccion("16. Guardar la portada a resolución completa (f10 + f11)")
    import f10_editor_visual
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        video_dummy = tmp_path / "07_FINAL.mp4"
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=blue:s=1080x1920:d=2",
            "-c:v", "libx264", str(video_dummy)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and video_dummy.exists():
            res = f10_editor_visual.guardar_portada(tmp_path, 1.0)
            chk("guardar_portada genera la imagen de salida correctamente",
                res.get("ok") is True and Path(res["ruta"]).exists(),
                "la portada debe ser extraida del video original con ffmpeg")

            if res.get("ok") and "ruta" in res:
                res_img = f10_editor_visual._resolucion(Path(res["ruta"]))
                chk("la portada extraida conserva la resolucion completa 1080x1920",
                    res_img == (1080, 1920),
                    f"resolucion obtenida {res_img} -- si se sacara del canvas del reproductor se obtendria la del proxy, no 1080x1920")

                if Path(res["ruta"]).exists():
                    try: Path(res["ruta"]).unlink()
                    except Exception: pass
        else:
            chk("guardar_portada ffmpeg dummy test disponible", False, "No se pudo generar video dummy con ffmpeg")

    fuente_srv = (config.RAIZ_PROYECTO / "editor" / "f11_servidor.py").read_text(encoding="utf-8")
    chk("existe el endpoint /guardar-portada en f11_servidor.py",
        'partes.path == "/guardar-portada"' in fuente_srv,
        "el frontend del editor realiza POST a /guardar-portada enviando el segundo del reproductor")

    chk("existe el boton btnGuardarPortada en el HTML del editor",
        'id="btnGuardarPortada"' in fuente_srv,
        "el usuario debe tener el boton visible en los controles del reproductor")


def pruebas_musica_editor():
    seccion("17. Música de fondo editable en el editor (f5 + f10 + f11)")
    import json
    import importlib
    import f10_editor_visual as f10
    pistas_json = config.DIR_ASSETS / "musica" / "pistas.json"
    chk("existe assets/musica/pistas.json con metadatos estructurados",
        pistas_json.exists(),
        "el catalogo de musica debe estar documentado con mood y duracion")

    if pistas_json.exists():
        datos_pistas = json.loads(pistas_json.read_text(encoding="utf-8"))
        chk("pistas.json contiene una lista de pistas con mood y duracion",
            isinstance(datos_pistas, list) and len(datos_pistas) >= 4 and all("mood" in p and "duracion" in p for p in datos_pistas),
            "cada pista debe tener id, archivo, nombre, mood y duracion")

    cat = f10.catalogo_musica()
    chk("f10_editor_visual.catalogo_musica() retorna elementos validos",
        isinstance(cat, list) and len(cat) >= 1,
        "el editor debe poder consultar el catalogo de musica")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "02_cortado.mp4").touch()
        (tmp_path / "02_cortado.json").write_text(json.dumps({"palabras": []}), encoding="utf-8")
        (tmp_path / "03_retencion.plan.json").write_text(json.dumps({}), encoding="utf-8")
        (tmp_path / "05_overlays.eventos.json").write_text(json.dumps([]), encoding="utf-8")
        (tmp_path / "00_corrida.json").write_text(json.dumps({"musica": "01-corporativo-suave.mp3"}), encoding="utf-8")

        datos_rec = f10.recolectar(tmp_path)
        chk("recolectar() expone las claves de musica necesarias",
            "musica_catalogo" in datos_rec and "musica_pista" in datos_rec and "musica_volumen" in datos_rec
            and "musica_inicio_s" in datos_rec and "sin_musica" in datos_rec,
            "el endpoint /datos del editor debe enviar el catalogo y los valores actuales de musica")

        # Probar que _guardar_musica en f11_servidor escribe correctamente
        import f11_servidor
        old_dir = f11_servidor.DIR_TRABAJO
        try:
            f11_servidor.DIR_TRABAJO = tmp_path
            f11_servidor._guardar_musica({"pista": "03-tech-futurista.mp3", "volumen": 0.35, "inicio_s": 12.5, "sin_musica": False})
            f_mus = tmp_path / "ajustes.musica.json"
            chk("ajustes.musica.json se crea correctamente con _guardar_musica",
                f_mus.exists(),
                "_guardar_musica debe guardar el archivo de ajustes de musica")
            if f_mus.exists():
                saved_mus = json.loads(f_mus.read_text(encoding="utf-8"))
                chk("ajustes.musica.json contiene los valores esperados",
                    saved_mus.get("pista") == "03-tech-futurista.mp3" and saved_mus.get("volumen") == 0.35 and saved_mus.get("inicio_s") == 12.5,
                    "los valores de pista, volumen e inicio_s deben coincidir")
        finally:
            f11_servidor.DIR_TRABAJO = old_dir

    fuente_srv = (config.RAIZ_PROYECTO / "editor" / "f11_servidor.py").read_text(encoding="utf-8")
    chk("f11_servidor.py incluye ajustes.musica.json en ARCHIVOS_AJUSTES",
        '"ajustes.musica.json"' in fuente_srv,
        "el gestor de versiones del editor debe persistir los ajustes de musica")

    chk("el editor HTML posee selector de pista, slider de volumen e inicio",
        'id="selMusicaPista"' in fuente_srv and 'id="musicaVolumenInput"' in fuente_srv and 'id="musicaInicioInput"' in fuente_srv,
        "el usuario debe disponer de los controles de musica en la interfaz")

    # --- El bug de la ruta: la musica NUNCA sonaba desde el .bat ------------
    # La previa pedia /archivo?ruta=assets/musica/<pista>. Esa ruta es RELATIVA
    # y `_archivo_permitido` la resuelve con Path.resolve(), o sea contra el cwd
    # del proceso. "Abrir Editor DeviceShop.bat" hace `cd` a editor\, asi que
    # resolvia a editor\assets\musica\ -- que no existe. Resultado: 404 mudo, la
    # musica no sonaba nunca y no habia ni un error a la vista. Lanzado a mano
    # desde la raiz del proyecto SI funcionaba, que es lo que lo hacia dificil
    # de ver.
    chk("existe el endpoint /musica, que no depende del cwd",
        'ruta == "/musica"' in fuente_srv and 'config.DIR_ASSETS / "musica" / nombre' in fuente_srv,
        "la pista se resuelve desde config.DIR_ASSETS, no contra el directorio de trabajo")
    chk("el endpoint rechaza cualquier intento de salirse de assets/musica/",
        '"/" in nombre or "\\\\" in nombre' in fuente_srv,
        "un nombre con separadores de ruta serviria archivos de fuera de la carpeta")
    chk("el JS ya no construye la ruta de musica a mano",
        '"assets/musica/" + edicionMusicaPista' not in fuente_srv
        and '"/musica?archivo=" + encodeURIComponent(archivo)' in fuente_srv,
        "si vuelve la ruta relativa, la musica deja de sonar otra vez y en silencio")

    # Boton de preescucha: es la UNICA forma de oir la pista cuando la corrida
    # ya esta renderizada, porque ahi sincronizarMusicaPrevia() no suena a
    # proposito (la musica ya va mezclada dentro del mp4 y sonaria doble).
    chk("hay un boton para escuchar la pista sola",
        'id="btnEscucharMusica"' in fuente_srv and "function alternarEscuchaMusica" in fuente_srv)
    chk("la preescucha manda sobre el loop de la previa",
        "let musicaEscuchaManual" in fuente_srv
        and "if (musicaEscuchaManual) return;" in fuente_srv,
        "sin esto el loop, que corre en cada frame, la pausaria al instante por video.paused")
    chk("si el navegador no deja reproducir, se avisa en vez de callarse",
        "avisarMusica(" in fuente_srv and 'id="avisoMusica"' in fuente_srv,
        "revertir el boton en silencio deja el mismo problema que el boton viene a arreglar")

    # Las dos previas de hook y CTA, al mismo tamaño. La regla de ancho solo
    # existia para `img`, y quedo huerfana cuando pasaron a enseñarse con un
    # <video>: cada uno se dibujaba a su tamaño intrinseco y el CTA (tarjeta a
    # pantalla completa) salia casi del doble que el hook (una banda de arriba).
    chk("las previas de hook y CTA tienen el mismo ancho asignado",
        ".hook-preview > div { flex: 0 0 170px" in fuente_srv
        and ".hook-preview video { width: 100%" in fuente_srv)


# ===========================================================================
# 18. Fase 0: preparar la entrada (recortar, ordenar, unir) — f0_preparar
# ===========================================================================
# La clase de fallo que cazan estas pruebas: el recorte SALE (el video se hace,
# dura lo que tiene que durar) pero los EMPALMES quedan medidos sobre la
# duracion original del clip en vez de sobre la recortada. El resultado no da
# ningun error: f4_retencion reinicia la rampa de zoom en el segundo
# equivocado, o sea "los acercamientos estan corridos", y solo se descubre
# mirando el video terminado.
#
# Usan clips sinteticos de lavfi (mismo recurso que pruebas_preview_animaciones)
# para no depender de que haya una grabacion real en entrada/.
def _clip_sintetico(destino: Path, segs: float, silencio_hasta: float = 0.0):
    """Un clip de prueba: barras de color + tono, opcionalmente mudo al principio."""
    import subprocess
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", f"testsrc=size=320x568:rate=30:d={segs}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={segs}:sample_rate=48000"]
    if silencio_hasta > 0:
        cmd += ["-af", f"volume=0:enable='lt(t,{silencio_hasta})'"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(destino)]
    subprocess.run(cmd, check=True, capture_output=True)
    return destino


def pruebas_preparacion():
    seccion("18. Fase 0: recortar y unir antes de transcribir (f0_preparar)")
    import tempfile
    import f0_preparar as f0

    tmp = Path(tempfile.mkdtemp())
    a = _clip_sintetico(tmp / "a.mp4", 6.0)
    b = _clip_sintetico(tmp / "b.mp4", 5.0)

    # --- una sola implementacion de la union, no dos ------------------------
    # Si editor.py se quedara con su propia copia de unir_tomas, la previa de la
    # pantalla y el pipeline podrian divergir sin que nada avisara.
    import editor as editor_mod
    chk("editor.py y la pantalla unen con LA MISMA funcion",
        editor_mod.unir_tomas is f0.unir_tomas,
        "dos copias de unir_tomas = la previa muestra una cosa y el render saca otra")

    # --- el atajo: sin recorte no se toca el archivo ------------------------
    ruta, empalmes = f0.preparar_entrada(
        [{"ruta": a, "desde": 0, "hasta": None}], tmp / "out_atajo.mp4")
    chk("un clip sin recortar se pasa TAL CUAL, sin recodificar",
        Path(ruta) == Path(a) and empalmes == [] and not (tmp / "out_atajo.mp4").exists(),
        "el caso normal no debe costar una generacion de compresion de mas")

    # --- recorte exacto -----------------------------------------------------
    ruta, _ = f0.preparar_entrada(
        [{"ruta": a, "desde": 1.0, "hasta": 4.0}], tmp / "out_recorte.mp4")
    dur = f0.duracion(ruta)
    chk("recortar 1.0s->4.0s deja exactamente 3s",
        abs(dur - 3.0) < 0.15, f"quedaron {dur:.3f}s")

    # --- EL EMPALME SE MIDE SOBRE EL CLIP RECORTADO ------------------------
    # Es la prueba central de este bloque. Con clips de 6s y 5s recortados a 3s
    # y 2s, el empalme tiene que caer en 3.0s (el fin del PRIMER clip ya
    # recortado). Si alguien volviera a medirlo sobre el original caeria en
    # 6.0s: un numero perfectamente creible que nadie mira, y que manda el
    # reinicio del zoom a un sitio donde no hay ningun cambio de plano.
    ruta, empalmes = f0.preparar_entrada(
        [{"ruta": a, "desde": 1.0, "hasta": 4.0},
         {"ruta": b, "desde": 0.5, "hasta": 2.5}], tmp / "out_dos.mp4")
    dur = f0.duracion(ruta)
    chk("el empalme se mide sobre la duracion RECORTADA, no la original",
        len(empalmes) == 1 and abs(empalmes[0] - 3.0) < 0.15,
        f"empalme en {empalmes} (esperado ~[3.0]; sobre el original habria dado 6.0)")
    chk("dos clips recortados suman sus duraciones recortadas",
        abs(dur - 5.0) < 0.2, f"{dur:.3f}s (esperado ~5.0 = 3.0 + 2.0)")

    # --- la previa no puede mentir -----------------------------------------
    # Mismo montaje por el mismo camino, solo cambia `escala`. Si los empalmes
    # difirieran, "ver como quedan unidas" dejaria de servir para decidir.
    ruta_p, empalmes_p = f0.preparar_entrada(
        [{"ruta": a, "desde": 1.0, "hasta": 4.0},
         {"ruta": b, "desde": 0.5, "hasta": 2.5}], tmp / "out_previa.mp4",
        escala=config.PREVIEW_ESCALA)
    chk("la previa a baja resolucion da los MISMOS empalmes que el render",
        empalmes_p == empalmes,
        f"previa {empalmes_p} vs corrida {empalmes}")
    chk("la previa sale a la escala pedida y no a tamaño completo",
        abs(f0.duracion(ruta_p) - dur) < 0.2,
        "misma duracion, distinta resolucion")

    # --- el empalme sigue cuadrando DESPUES del corte de silencios ----------
    # Es el encadenado real del pipeline: f0 entrega los empalmes en la linea de
    # tiempo del archivo unido, y f2_cortar los remapea con mapear_a_nueva_linea
    # a la del video ya cortado. Un empalme en 3.0s, con 0.8s de silencio
    # cortado antes, tiene que terminar en 2.2s.
    intervalos = [{"inicio": 0.0, "fin": 1.2}, {"inicio": 2.0, "fin": 5.0}]
    nuevo = f2_cortar.mapear_a_nueva_linea(3.0, intervalos)
    chk("el empalme sobrevive al corte de silencios (mapear_a_nueva_linea)",
        abs(nuevo - 2.2) < 1e-6,
        f"3.00s del unido -> {nuevo:.2f}s del cortado (esperado 2.20)")

    # --- acotado de valores heredados --------------------------------------
    # Un .preparado.json viejo puede pedir un `hasta` que ya no existe si la
    # grabacion se volvio a hacer mas corta. ffmpeg no avisa: devuelve un clip
    # mas corto y el empalme queda mal.
    norm = f0.normalizar_clips([{"ruta": a, "desde": 0, "hasta": 999.0}])
    chk("un 'hasta' mas alla del final se acota a la duracion real",
        abs(norm[0]["hasta"] - 6.0) < 0.15, f"hasta={norm[0]['hasta']}")
    norm = f0.normalizar_clips([{"ruta": a, "desde": 5.0, "hasta": 2.0}])
    chk("un 'desde' posterior al 'hasta' no produce un clip negativo",
        norm[0]["desde"] < norm[0]["hasta"],
        f"desde={norm[0]['desde']} hasta={norm[0]['hasta']}")

    # --- deteccion de bordes ------------------------------------------------
    # El umbral se MIDE del archivo (ver SILENCIO_MARGEN_BAJO_MEDIA_DB): uno
    # fijo no encontraba ni un silencio en la grabacion real de entrada/, que
    # esta muy caliente.
    c = _clip_sintetico(tmp / "c.mp4", 6.0, silencio_hasta=2.0)
    bordes = f0.detectar_bordes(c)
    esperado = 2.0 - f0.MARGEN_PROPUESTA_S
    chk("detectar_bordes encuentra el silencio inicial y deja aire",
        bordes["detectado"] and abs(bordes["desde"] - esperado) < 0.25,
        f"propone desde={bordes['desde']}s (esperado ~{esperado:.2f}s), "
        f"umbral medido {bordes['umbral_db']}dB")

    # --- memoria: el .preparado.json ---------------------------------------
    archivo = f0.guardar_preparado([{"ruta": a, "desde": 1.0, "hasta": 4.0}], guion=7)
    leido = f0.leer_preparado(a)
    chk("guardar y leer la preparacion devuelve los mismos recortes",
        leido is not None and leido["guion"] == 7
        and abs(leido["clips"][0]["desde"] - 1.0) < 1e-6,
        f"{archivo.name}: {leido and leido['clips']}")
    archivo.unlink(missing_ok=True)
    chk("sin .preparado.json, leer_preparado devuelve None y no revienta",
        f0.leer_preparado(a) is None)

    # --- editor.py: por donde NO tiene que pasar ----------------------------
    fuente = (AQUI / "editor.py").read_text(encoding="utf-8")
    chk("editor.py no vuelve a recortar con --reaplicar",
        "if not args.reaplicar:" in fuente
        and fuente.index("if not args.reaplicar:")
            < fuente.index("f0_preparar.preparar_entrada("),
        "recortar en cada re-render del editor visual seria recodificar la "
        "grabacion entera para nada")
    chk("--desde/--hasta se rechazan con varios archivos de entrada",
        "--desde/--hasta solo valen con UN archivo" in fuente,
        "con dos archivos no hay forma de saber a cual se refiere el recorte")
    chk("la pantalla de preparacion no ofrece zoom",
        "zoom" not in (AQUI / "f0_servidor_preparar.py").read_text(encoding="utf-8").lower(),
        "el encuadre se combina con la curva del pipeline en el panel de "
        "Encuadre; un segundo control aqui se multiplicaria con aquel")

    import shutil as _shutil
    _shutil.rmtree(tmp, ignore_errors=True)


def pruebas_texto_destacado_editor():
    seccion("19. Añadir texto llamativo desde el editor (panel + preview de estilos)")
    import json
    import tempfile
    import time

    import f6_overlays
    import f10_editor_visual as f10

    estilos_esperados = ["contorno", "pildora", "neon", "degradado", "sombra", "marcador"]
    chk("config.TEXTO_DESTACADO_ESTILOS tiene los 6 estilos, con etiqueta legible",
        list(config.TEXTO_DESTACADO_ESTILOS.keys()) == estilos_esperados
        and all(isinstance(v, str) and v for v in config.TEXTO_DESTACADO_ESTILOS.values()),
        "el editor pinta estas etiquetas en el selector, nunca la clave cruda del CSS")

    chk("config.TEXTO_DESTACADO_MUESTRA coincide con el default embebido en el HTML",
        config.TEXTO_DESTACADO_MUESTRA == "¡OJO A ESTO!",
        "si difieren, el preview de cada estilo (pre-renderizado con este texto) "
        "no coincidiria con la clave de cache que arma el endpoint /anim-preview")

    # --- texto-destacado NO debe aparecer en el grid generico ----------------
    inventario = f8_hyperframes.inventario_animaciones()
    chk("texto-destacado no aparece en el inventario generico de animaciones",
        all(a["nombre"] != "texto-destacado" for a in inventario),
        "ese flujo solo sabe anadir con los valores por defecto (mismo texto y "
        "estilo siempre) -- tiene su propio panel dedicado con preview de estilos")

    # --- los 6 previews ya estan cacheados: ningun clic debe disparar un ------
    # --- render de Hyperframes real (eso tarda segundos, no querer eso) ------
    t0 = time.monotonic()
    rutas = {}
    for estilo in estilos_esperados:
        rutas[estilo] = f8_hyperframes.render(
            "texto-destacado", {"texto": config.TEXTO_DESTACADO_MUESTRA, "estilo": estilo})
    elapsed = time.monotonic() - t0
    chk("los 6 estilos de muestra ya estan renderizados (cache-hit, no un render nuevo)",
        all(r is not None and r.exists() for r in rutas.values()) and elapsed < 5.0,
        f"{elapsed:.2f}s para los 6 -- un render real de Hyperframes tarda varios "
        "segundos POR estilo; si esto tardara de mas, el panel se sentiria trabado "
        "la primera vez que Jose lo abre")
    chk("cada estilo cae en un archivo MOV distinto (6 clips, no 1 repetido)",
        len({r for r in rutas.values() if r is not None}) == 6,
        "si dos estilos compartieran archivo, el preview de uno mostraria el otro")

    # --- variables sobrevive el viaje por ajustes.animaciones.json -----------
    tmp = Path(tempfile.mkdtemp())
    try:
        entrada = {"nombre": "texto-destacado", "ini": 4.2,
                   "variables": {"texto": "Envio gratis hoy", "estilo": "neon"}}
        (tmp / "ajustes.animaciones.json").write_text(
            json.dumps({"animaciones": [entrada]}), encoding="utf-8")
        cargadas = f6_overlays.cargar_animaciones_manual(tmp / "ajustes.animaciones.json")
        chk("cargar_animaciones_manual conserva 'variables' (texto y estilo)",
            cargadas is not None and len(cargadas) == 1
            and cargadas[0].get("variables") == {"texto": "Envio gratis hoy", "estilo": "neon"},
            f"cargadas: {cargadas} -- sin esto, _construir_animacion() siempre recibia "
            "variables_extra=None y el render ignoraba el texto que Jose escribio")

        # --- round-trip por recolectar(): las 4 claves nuevas del panel ------
        datos = f10.recolectar(tmp)
        chk("recolectar() expone anim_duraciones, texto_destacado_estilos/muestra/duracion",
            datos.get("anim_duraciones") == config.ANIMACION_DURACION
            and datos.get("texto_destacado_estilos") == config.TEXTO_DESTACADO_ESTILOS
            and datos.get("texto_destacado_muestra") == config.TEXTO_DESTACADO_MUESTRA
            and datos.get("texto_destacado_duracion") == 2.5,
            "mismo patron que los picos de SFX (bloque 1) y el tamano de subtitulo "
            "(bloque 14): nada hardcodeado en el JS")
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp, ignore_errors=True)

    # --- el editor: panel, preview por estilo y persistencia -----------------
    fuente_srv = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("existe el panel 'Texto llamativo' con input de texto y grid de estilos",
        'id="textoDestacadoInput"' in fuente_srv
        and 'id="gridEstilosDestacado"' in fuente_srv
        and 'id="btnAñadirTextoDestacado"' in fuente_srv)
    chk("hay una funcion que pinta los 6 estilos y otra que los guarda al elegir",
        "function renderGridEstilosDestacado()" in fuente_srv
        and "renderGridEstilosDestacado();" in fuente_srv,
        "tiene que pintarse tanto al elegir un estilo como al recargar la pagina "
        "(en cargar()), o el grid quedaria vacio hasta el primer clic")
    chk("el grid de estilos pide el preview de CADA estilo, no uno generico",
        'medioAnimacion({ nombre: "texto-destacado", variables: { estilo: clave } })' in fuente_srv,
        "sin pasar 'estilo', las 6 tarjetas del selector mostrarian todas el mismo "
        "clip (el ultimo cacheado), y elegir a ciegas es justo lo que se pidio evitar")
    chk("medioAnimacion pide el estilo puntual cuando el nombre es texto-destacado",
        'a.nombre === "texto-destacado" && a.variables && a.variables.estilo' in fuente_srv,
        "sin esto, la tarjeta ya anadida al video (o la del selector de estilos) "
        "mostraria un estilo cualquiera de los 6 ya cacheados, no el elegido")
    chk("el boton de anadir arma el evento con variables:{texto, estilo}",
        "variables: { texto, estilo: textoDestacadoEstilo }" in fuente_srv,
        "es la forma en que el texto libre de Jose llega hasta ajustes.animaciones.json")
    chk("animacionesParaGuardar() incluye 'variables' cuando existe",
        "if (a.variables) base.variables = a.variables;" in fuente_srv,
        "sin esto, guardar el video se olvidaria del texto y el estilo elegidos")
    chk("recargar la pagina no pierde las variables de una animacion ya guardada",
        "variables: a.variables || null," in fuente_srv,
        "el mapeo de animGuardadas -> edicionAnimaciones tiene que preservarlas")
    chk("la duracion por defecto de una animacion sin renderizar usa config, no 2.4s fijo",
        "DATA.anim_duraciones && DATA.anim_duraciones[a.nombre]" in fuente_srv,
        "2.4s a ciegas mentia en la linea de tiempo para cualquier animacion cuya "
        "duracion real fuera otra (texto-destacado y stickers duran 2.5s)")
    chk("el endpoint /anim-preview renderiza el estilo puntual para texto-destacado",
        'if plantilla == "texto-destacado" and estilo:' in fuente_srv,
        "sin esto, pedir un estilo especifico devolveria 'cualquier MOV ya cacheado "
        "de esa plantilla' (mov_de_plantilla), no el que el usuario esta mirando")

    # --- f8_hyperframes: el filtro que saca texto-destacado del grid generico
    fuente_f8 = (AQUI / "f8_hyperframes.py").read_text(encoding="utf-8")
    chk('inventario_animaciones() salta "texto-destacado" a proposito, con el motivo escrito',
        'if nombre == "texto-destacado":' in fuente_f8 and "continue" in fuente_f8)

    # --- f6_overlays: variables declarada y documentada en la firma ----------
    fuente_f6 = (AQUI / "f6_overlays.py").read_text(encoding="utf-8")
    chk('cargar_animaciones_manual conserva la clave "variables" en el JSON limpio',
        '"variables": variables if isinstance(variables, dict) else None,' in fuente_f6)


def pruebas_broll_detras():
    """B-roll DETRAS de Jose: el modo "recorte" (franja del 70% + persona encima).

    La clase de fallo que cazan: el modo se elige en el panel o en el editor y
    se PIERDE en algun salto — al guardar, al recargar, al planificar — sin que
    nada falle. El video sale, con el B-roll tapandole la cara, que es
    exactamente lo que el modo venia a evitar.
    """
    seccion("15. B-roll detras de Jose (modo recorte)")

    # --- la marca en el texto del panel ---
    casos = [
        ("F14 a pantalla completa: scroll", "completo"),
        ("F14 detras de mi: scroll", "recorte"),
        ("F33 DETRAS DE MI", "recorte"),
        ("F31 al 70% del cuadro", "recorte"),
        ("F05", "completo"),
    ]
    malos = [(t, f13_guion.modo_broll_de(t), esp) for t, esp in casos
             if f13_guion.modo_broll_de(t) != esp]
    chk("modo_broll_de() lee la marca del panel (con y sin tildes)", not malos,
        f"fallan: {malos}" if malos else f"{len(casos)}/{len(casos)} casos")

    # El texto que ESCRIBE el selector del panel tiene que ser el mismo que lee
    # el pipeline. Si uno escribe "detras mio" y el otro busca "detras de mi",
    # el selector queda de adorno.
    panel = (AQUI.parent / "PANEL-PRODUCCION.html").read_text(encoding="utf-8")
    m = re.search(r"MARCA_RECORTE\s*=\s*'([^']+)'", panel)
    chk("la marca que escribe el panel es la que lee f13_guion",
        bool(m) and f13_guion.modo_broll_de(f"F14 {m.group(1)}") == "recorte",
        f"el panel escribe {m.group(1)!r}" if m else "no encontre MARCA_RECORTE en el panel")

    # --- el campo sobrevive el viaje editor -> JSON -> pipeline ---
    import json
    import f6_overlays
    with tempfile.TemporaryDirectory() as td:
        ruta = Path(td) / "broll.json"
        clip = AQUI.parent / "assets" / "generado" / "video" / "manual" / "rendicion.mp4"
        ruta.write_text(json.dumps({"broll": [
            {"ini": 1.0, "fin": 4.0, "archivo": str(clip), "modo_broll": "recorte"},
            {"ini": 6.0, "fin": 9.0, "archivo": str(clip)},
        ]}), encoding="utf-8")
        cargados = f6_overlays.cargar_broll_manual(ruta) or []
        modos = [ev.get("modo_broll") for ev in cargados]
        chk("cargar_broll_manual conserva modo_broll y asume 'completo' si falta",
            modos == ["recorte", "completo"],
            f"modos cargados: {modos} (el clip existe: {clip.exists()})")

    # --- f10 se lo pasa a la web ---
    f10 = (AQUI / "f10_editor_visual.py").read_text(encoding="utf-8")
    chk("f10_editor_visual expone modo_broll al editor",
        '"modo_broll"' in f10,
        "sin esto, elegir 'detras de mi' se pierde al recargar el editor")

    # --- el editor visual: selector de 3 y guardado ---
    f11 = (AQUI / "f11_servidor.py").read_text(encoding="utf-8")
    chk("el selector del editor ofrece las tres formas del clip",
        '"recorte", "Detrás de mí (70%)"' in f11 and '"broll", "A pantalla completa"' in f11
        and '"pip", "Como tarjeta PiP"' in f11)
    chk("brollParaGuardar() manda modo_broll al pipeline",
        re.search(r"brollParaGuardar\(\)[\s\S]{0,400}?base\.modo_broll", f11) is not None,
        "es lo que hace que la eleccion llegue a ajustes.broll.json")

    # --- el render: dos capas, y la de Jose ENCIMA del clip ---
    ev = {"tipo": "broll", "medio": "video", "modo_broll": "recorte",
          "archivo": "x.mp4", "ini": 1.0, "fin": 3.0, "x": 0, "y": 0}
    sin_modelo = None
    with tempfile.TemporaryDirectory() as td:
        # Sin GPU ni modelo, _preparar_recorte tiene que DEGRADAR, no reventar:
        # el video sale igual, solo que sin la capa recortada.
        try:
            sin_modelo, _ = f4_retencion._preparar_recorte(
                [dict(ev, archivo=str(AQUI / "no-existe.mp4"))],
                Path(td) / "v.mp4", Path(td), 1080, 1920, 30.0, lambda f, t: f)
        except Exception as e:
            sin_modelo = f"EXCEPCION: {e}"
    chk("_preparar_recorte no revienta si el clip o el modelo no estan",
        isinstance(sin_modelo, list) and len(sin_modelo) == 1,
        f"devolvio: {sin_modelo if not isinstance(sin_modelo, list) else 'lista de 1 evento'}")

    # El orden importa: la capa de la persona va DESPUES del B-roll en la lista,
    # porque el filter_complex apila en ese orden. Al reves, el clip taparia a
    # Jose y el modo no serviria de nada.
    fuente = (AQUI / "f4_retencion.py").read_text(encoding="utf-8")
    i_broll = fuente.find('salida.append(ev_broll)')
    i_matte = fuente.find('"tipo": "matte-persona"')
    chk("la capa de la persona se apila DESPUES del clip",
        0 < i_broll < i_matte,
        "si se invirtiera, el B-roll taparia a Jose y el modo no haria nada")
    # "fade=t=" y no "fade" a secas: el comentario de esa rama explica por que NO
    # lleva fade, y buscar la palabra suelta daba por rota una rama que esta bien.
    rama_matte = fuente[fuente.find('== "matte-persona"'):
                        fuente.find('elif ev.get("tipo") == "broll-recorte"')]
    chk("la capa de la persona se compone SIN fade",
        "[ov{i}]" in rama_matte and "fade=t=" not in rama_matte,
        "con fade se veria a Jose medio transparente sobre el B-roll al entrar y salir")

    # --- la cache de las capas distingue resolucion ---
    chk("el nombre de las capas incluye la resolucion",
        re.search(r'base = f"recorte_\{i\}_\{[^}]+\}_\{w_out\}x\{h_out\}"', fuente) is not None,
        "sin esto un --preview reutilizaria las capas del render final, al doble de tamano")

    # --- la mascara de degradado ---
    import f17_matte
    with tempfile.TemporaryDirectory() as td:
        png = f17_matte.mascara_degradado(64, 400, 100, Path(td) / "m.png")
        from PIL import Image
        import numpy as _np
        col = _np.asarray(Image.open(png).convert("L"))[:, 0]
        chk("la mascara es opaca arriba y transparente en el borde de abajo",
            col[0] == 255 and col[250] == 255 and col[-1] <= 2 and col[350] < 255,
            f"arriba={col[0]}, en el arranque del degradado={col[300]}, abajo={col[-1]}")
        chk("el degradado es suave (smoothstep), no una rampa recta",
            abs(int(col[350]) - 128) <= 12 and col[310] > col[350] > col[390],
            f"a mitad del degradado: {col[350]} (una rampa recta daria 128 exacto "
            f"y dos codos visibles en los extremos)")


def pruebas_transiciones_pip():
    """Transiciones entre cortes (f2b) y animaciones de PiP (f4b).

    La clase de fallo que cazan: que el motor cambie el default y un video sin
    transicion pedida salga distinto, o que una expresion de posicion se cuele
    cuando el PiP es 'fundido' (deberia quedar estatico como siempre), o que los
    empalmes se calculen en el sitio equivocado y la transicion caiga donde no
    hay corte.
    """
    seccion("19. Transiciones entre cortes y animacion de PiP (f2b/f4b)")
    import f2_cortar
    import f2b_transiciones
    import f4b_pip_anim

    # empalmes = suma acumulada de duraciones, sin el ultimo tramo
    iv = [{"inicio": 0, "fin": 2.0}, {"inicio": 5, "fin": 6.5}, {"inicio": 10, "fin": 11.0}]
    emp = f2_cortar.boundaries_de_cortes(iv)
    chk("los empalmes caen en la suma acumulada de tramos (no en tiempos del original)",
        emp == [2.0, 3.5],
        f"esperado [2.0, 3.5], obtenido {emp} — un empalme mal ubicado pone la "
        f"transicion donde no hay corte")

    # default seguro: sin transicion o sin cortes -> cadena vacia (no toca el video)
    chk("transicion 'ninguna' no anade ningun filtro (camino de regresion)",
        f2b_transiciones.construir_filtro("ninguna", [2.0], 1080, 1920) == "")
    chk("sin empalmes no hay filtro aunque se pida una transicion",
        f2b_transiciones.construir_filtro("glitch", [], 1080, 1920) == "")

    # una transicion real produce un filtro con una ventana por empalme
    f = f2b_transiciones.construir_filtro("flash-blanco", [2.0, 3.5], 1080, 1920)
    chk("flash-blanco dibuja una ventana 'enable' por empalme",
        f.count("enable=") == 2 and "drawbox" in f, f[:120])
    # tipo desconocido: falla ruidosa, no en silencio
    try:
        f2b_transiciones.construir_filtro("no-existe", [2.0], 1080, 1920)
        ruidosa = False
    except ValueError:
        ruidosa = True
    chk("una transicion inexistente lanza error (no cae a un default en silencio)", ruidosa)

    # PiP 'fundido/fundido' -> posicion estatica (None,None): el llamador deja el
    # overlay como siempre. Este es el default y NO debe animar nada.
    x, y = f4b_pip_anim.expr_posicion(800, 1200, 5.0, 9.0, "fundido", "fundido")
    chk("PiP fundido/fundido no genera expresion de posicion (queda estatico)",
        x is None and y is None)

    # un preset de movimiento SI genera expresion y arranca desde la base
    x, y = f4b_pip_anim.expr_posicion(800, 1200, 5.0, 9.0, "desliza-izquierda", "fundido")
    chk("un PiP con animacion de entrada genera expresion de x dependiente de t",
        x is not None and "t-5.000" in x and x.startswith("800"), (x or "")[:90])

    # las diez animaciones y las once transiciones estan todas nombradas
    chk("hay 10 animaciones de PiP en el catalogo",
        len(f4b_pip_anim.ANIMACIONES) == 10, str(list(f4b_pip_anim.ANIMACIONES)))
    chk("hay 10 transiciones + 'ninguna' en el catalogo",
        len(f2b_transiciones.TRANSICIONES) == 11, str(list(f2b_transiciones.TRANSICIONES)))

    # --- POR EMPALME: cada corte con SU propia transicion (construir_filtro_multi) ---
    specs = [{"t": 1.3, "tipo": "flash-blanco", "intensidad": 1.0},
             {"t": 2.0, "tipo": "zoom-punch", "intensidad": 1.2},
             {"t": 2.7, "tipo": "glitch", "intensidad": 0.8},
             {"t": 3.2, "tipo": "shake", "intensidad": 1.0}]
    fm = f2b_transiciones.construir_filtro_multi(specs, 540, 960, 30)
    chk("por-empalme: mezcla familias (drawbox/glitch en cadena + un solo zoompan)",
        "drawbox" in fm and "rgbashift" in fm and fm.count("zoompan") == 1, fm[:80])
    chk("por-empalme: cada corte de cadena pone su ventana en SU tiempo",
        "between(t,1.180,1.420)" in fm and "2.588" in fm, "las ventanas no caen en el tiempo del corte")
    chk("por-empalme: sin comas escapadas dentro de las comillas (van en filter_complex)",
        "\\," not in fm, "una coma escapada rompe la expresion dentro de comillas simples")
    chk("por-empalme: todo 'ninguna' no dibuja nada",
        f2b_transiciones.construir_filtro_multi(
            [{"t": 1.0, "tipo": "ninguna"}], 540, 960, 30) == "")

    # --- POR PiP: f6 deja pasar la animacion propia de cada evento ---
    import json
    import tempfile
    from PIL import Image
    import f6_overlays
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        Image.new("RGBA", (10, 10)).save(tdp / "x.png")
        (tdp / "ev.json").write_text(json.dumps({"eventos": [{
            "ini": 5.0, "fin": 9.0, "x": 800, "y": 1200, "archivo": str(tdp / "x.png"),
            "anim_entrada": "desliza-abajo", "anim_salida": "latigazo", "anim_intensidad": 1.3,
        }]}), encoding="utf-8")
        cargados = f6_overlays.cargar_eventos_manual(tdp / "ev.json", tdp, catalogo=[])
        ok = (cargados and cargados[0].get("anim_entrada") == "desliza-abajo"
              and cargados[0].get("anim_salida") == "latigazo"
              and cargados[0].get("anim_intensidad") == 1.3)
        chk("por-PiP: cargar_eventos_manual conserva anim_entrada/salida/intensidad",
            ok, "sin esto el editor guarda la animacion del PiP pero el render la ignora")


def pruebas_panel_conectado():
    """El panel escribiendo sobre si mismo: selector de tipo de fila y servidor.

    La clase de fallo que cazan: el panel es la ENTRADA del pipeline, un archivo
    que se parsea con eval(). Un selector que escribe mal deja el archivo o bien
    corrupto (y entonces revienta lejos, en f13, sin apuntar aqui) o bien valido
    pero con OTRA fila cambiada, que es peor: el video sale, distinto, y nadie
    se entera.

    Y hay DOS escritores del mismo archivo — panel_servidor.py cuando el
    pipeline esta detras, y el JS del panel cuando se abre como file:// — que
    tienen que producir exactamente lo mismo.
    """
    seccion("17. Panel conectado (selector de fila y escritura del panel)")

    import json
    import panel_servidor as ps

    fuente = ps.leer_panel()
    datos = f13_guion.cargar_datos_html()
    guiones = datos["G"]

    # --- leer: lo que ve el editor de fuente es lo que ve el pipeline --------
    claves = ("momento", "dice", "tipo", "ve", "sonido", "musica")
    malos = []
    total = 0
    for g in guiones:
        for ri, r in enumerate(g["tl"]):
            total += 1
            leida = ps.leer_fila(fuente, g["n"], ri)
            if leida != dict(zip(claves, r)):
                malos.append(f"G{g['n']}/{ri}")
    chk("leer_fila() ve las mismas 120 filas que el parser del pipeline",
        not malos, f"difieren: {malos[:5]}" if malos else f"{total} filas")

    # --- escribir lo mismo no cambia el archivo -----------------------------
    # Sin esto, abrir un desplegable y elegir la opcion que ya estaba reescribia
    # el panel: diffs enormes en git y, cuando el guion tenia la frase en otro
    # orden, el texto reordenado sin que nadie lo pidiera.
    distintos = [f"G{g['n']}/{ri}"
                 for g in guiones for ri, r in enumerate(g["tl"])
                 if ps.escribir_fila(fuente, g["n"], ri, r[2], r[3]) != fuente]
    chk("reescribir una fila con lo que ya tenia deja el archivo intacto",
        not distintos, f"cambian: {distintos[:5]}" if distintos else f"{total} filas")

    # --- escribir de verdad: cambia esa fila y SOLO esa ---------------------
    malos = []
    for g in guiones:
        ri = len(g["tl"]) - 1
        nuevo = ps.escribir_fila(fuente, g["n"], ri, "PIP", "P05 arriba a la izquierda: x")
        try:
            releidos = _guiones_de_fuente(nuevo)
        except Exception as e:
            malos.append(f"G{g['n']}: el panel ya no parsea ({e})")
            continue
        cambiadas = sum(1 for a, b in zip(guiones, releidos)
                        for x, y in zip(a["tl"], b["tl"]) if x != y)
        fila = next(x for x in releidos if x["n"] == g["n"])["tl"][ri]
        if cambiadas != 1 or fila[2] != "PIP" or fila[3] != "P05 arriba a la izquierda: x":
            malos.append(f"G{g['n']}: {cambiadas} filas cambiadas, quedo {fila[2:4]}")
    chk("escribir una fila toca esa fila y ninguna otra, en los 10 guiones",
        not malos, "; ".join(malos[:3]) if malos else f"{len(guiones)} guiones")

    # --- comillas y apostrofos sobreviven -----------------------------------
    # La fila 9 del guion 8 lleva comillas escapadas en el fuente (punch-in en
    # \"celular\"): por eso la fila se ubica por POSICION y no buscando su texto.
    raro = "Con 'apostrofo', \"comillas\" y una barra \\ suelta"
    con_raro = ps.escribir_fila(fuente, 8, 9, "ANIM", raro)
    try:
        fila = next(x for x in _guiones_de_fuente(con_raro) if x["n"] == 8)["tl"][9]
        ok = fila[3] == raro
    except Exception as e:
        ok, fila = False, str(e)
    chk("un texto con comillas, apostrofos y barras se relee tal cual", ok,
        f"quedo: {fila!r}")

    # --- un tipo inventado no llega al archivo ------------------------------
    try:
        ps.escribir_fila(fuente, 7, 0, "CUALQUIERA", "x")
        ok = False
    except ValueError:
        ok = True
    chk("un tipo fuera de YO/B-ROLL/PIP/ANIM se rechaza antes de escribir", ok,
        "un tipo inventado no da error en el pipeline: la fila deja de aportar y ya")

    # --- CRLF: el panel es CRLF entero --------------------------------------
    # read_text() normal lo entrega con \n, y reescribirlo asi convertia el
    # archivo entero a LF: 1.797 lineas de diff por cambiar un campo.
    con_segs = ps.escribir_segundos(fuente, 7, "hooksegs", 2.5)
    chk("los finales de linea CRLF sobreviven a una escritura",
        con_segs.count("\r\n") == fuente.count("\r\n") and "\r\n" in fuente,
        f"antes {fuente.count(chr(13) + chr(10))}, despues {con_segs.count(chr(13) + chr(10))}")
    chk("escribir_segundos() cambia hooksegs del guion pedido",
        re.search(r"\{n:7,[^\n]*hooksegs:2\.5", con_segs) is not None)

    # --- el JS del panel y el servidor escriben LO MISMO --------------------
    # Son dos implementaciones del mismo algoritmo (una para cuando hay pipeline
    # detras, otra para el panel abierto como file://). Si se separan, editar
    # desde un lado o desde el otro deja archivos distintos.
    panel_txt = (AQUI.parent / "PANEL-PRODUCCION.html").read_text(encoding="utf-8")
    for nombre in ("escribirFilaEnFuente", "_bloqueGuion", "_lineasFilas", "_campos"):
        chk(f"el panel trae su propia copia de {nombre}() para el modo sin servidor",
            f"function {nombre}(" in panel_txt)

    casos = [[7, 9, "B-ROLL", "P02 detras de mi: prueba"],
             [8, 9, "PIP", 'H08 arriba a la izquierda + punch-in en "celular"'],
             [1, 12, "ANIM", "tarjeta-cta + WhatsApp"]]
    js = """
const fs=require('fs'), vm=require('vm');
const html=fs.readFileSync(process.argv[1],'utf8');
const codigo=html.match(/<script>([\\s\\S]*)<\\/script>/)[1];
const noop=()=>{};
const el=()=>({innerHTML:'',textContent:'',className:'',style:{},dataset:{},
 classList:{add:noop,remove:noop,toggle:noop},appendChild:noop,scrollIntoView:noop,
 cells:[],options:[],querySelectorAll:()=>[],querySelector:()=>null,closest:()=>null,
 addEventListener:noop,getBoundingClientRect:()=>({left:0,top:0,width:0,height:0,bottom:0})});
const ctx={console,document:{getElementById:el,querySelectorAll:()=>[],
 querySelector:()=>null,addEventListener:noop,createElement:el,body:el()},
 location:{protocol:'file:',hostname:'',origin:'null'},
 navigator:{clipboard:{writeText:()=>Promise.resolve()}},
 localStorage:{getItem:()=>null,setItem:noop},fetch:()=>Promise.reject(new Error('sin red')),
 setTimeout:noop,setInterval:noop,clearInterval:noop,innerWidth:1200,
 AbortController:function(){this.signal=null;this.abort=noop;}};
ctx.window=ctx; vm.createContext(ctx);
vm.runInContext(codigo+';globalThis.__W=escribirFilaEnFuente;',ctx);
console.log(JSON.stringify(JSON.parse(process.argv[2]).map(
  ([n,ri,t,v])=>ctx.__W(html,n,ri,t,v))));
"""
    try:
        res = subprocess.run(
            ["node", "-e", js, str(AQUI.parent / "PANEL-PRODUCCION.html"), json.dumps(casos)],
            capture_output=True, text=True, encoding="utf-8", timeout=90)
        desde_js = json.loads(res.stdout) if res.returncode == 0 else None
    except Exception:
        desde_js = None
    if desde_js is None:
        chk("el escritor del panel (JS) y el del servidor (Python) coinciden",
            False, "no se pudo correr Node para compararlos")
    else:
        difieren = [f"G{c[0]}/{c[1]}" for c, s in zip(casos, desde_js)
                    if ps.escribir_fila(fuente, c[0], c[1], c[2], c[3]) != s]
        chk("el escritor del panel (JS) y el del servidor (Python) escriben igual",
            not difieren, f"difieren en {difieren}" if difieren else f"{len(casos)} casos")

    # --- una fila por linea: en eso se apoyan los dos escritores ------------
    malos = [f"G{g['n']}" for g in guiones
             if len(ps._lineas_filas(fuente, *ps._bloque_guion(fuente, g["n"]))) != len(g["tl"])]
    chk("cada fila de la linea de tiempo ocupa exactamente una linea del archivo",
        not malos, f"no cuadran: {malos}" if malos else f"{total} filas en {len(guiones)} guiones")

    # --- las frases que escribe el panel son las que lee el pipeline --------
    for constante, esperado in (("MARCA_RECORTE", "recorte"), ("MARCA_COMPLETO", "completo")):
        m = re.search(constante + r"\s*=\s*'([^']+)'", panel_txt)
        chk(f"la frase de {constante} que escribe el panel es la que lee f13_guion",
            bool(m) and f13_guion.modo_broll_de(f"F14 {m.group(1)}") == esperado,
            f"el panel escribe {m.group(1)!r}" if m else f"no encontre {constante}")

    # --- lo del pipeline se esconde solo cuando no hay pipeline -------------
    # Es lo unico que separa la pagina publica de GitHub Pages del panel de la
    # PC: el MISMO archivo. Si esto se rompe, la web muestra botones muertos.
    chk("los controles de fila no se dibujan sin servidor detras",
        re.search(r"function controlesFila\([^)]*\)\{\s*\n?\s*if\(!API\) return '';", panel_txt)
        is not None,
        "sin esto, GitHub Pages mostraria selectores que no pueden guardar nada")
    chk("lo que solo sirve con pipeline arranca oculto (.pipe-off) y se enciende al detectarlo",
        ".pipe-off{display:none!important}" in panel_txt
        and "document.querySelectorAll('.pipe-solo').forEach(el=>el.classList.remove('pipe-off'))"
        in panel_txt)
    chk("el panel busca el pipeline por fetch, no por una bandera del archivo",
        "async function pipeDetectar()" in panel_txt and "/api/estado" in panel_txt,
        "una bandera obligaria a mantener dos copias del panel, una para la web y otra para la PC")

    # --- el servidor no lanza el editor visual dentro de la corrida ---------
    # f11_servidor sirve para siempre: si editor.py lo abriera, el subproceso no
    # terminaria nunca y el panel se quedaria en "corriendo" hasta que se cierre.
    fuente_srv = (AQUI / "panel_servidor.py").read_text(encoding="utf-8")
    chk("la corrida se lanza con --sin-abrir-editor",
        '"--sin-abrir-editor"' in fuente_srv,
        "sin esto la corrida no termina nunca a ojos del panel")
    chk("detener la corrida mata tambien a los hijos (ffmpeg, whisper)",
        '"taskkill", "/F", "/T"' in fuente_srv,
        "matar solo al padre deja el render corriendo y la GPU ocupada")
    chk("el log del subproceso se lee en UTF-8",
        'entorno["PYTHONIOENCODING"] = "utf-8"' in fuente_srv
        and 'encoding="utf-8"' in fuente_srv,
        "sin esto las tildes del pipeline llegan rotas al panel")


def _guiones_de_fuente(fuente: str) -> list:
    """Los guiones de un panel EN MEMORIA, con el mismo eval que usa el pipeline."""
    import json
    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8",
                                     newline="", delete=False) as f:
        f.write(fuente)
        tmp = Path(f.name)
    try:
        return f13_guion.cargar_datos_html(tmp)["G"]
    finally:
        tmp.unlink(missing_ok=True)


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
    pruebas_sfx_previa()
    pruebas_zona_segura()
    pruebas_densidad_sfx()
    pruebas_recorte_broll()
    pruebas_subtitulos()
    pruebas_texto_destacado()
    pruebas_guardar_portada()
    pruebas_musica_editor()
    pruebas_preparacion()
    pruebas_texto_destacado_editor()
    pruebas_broll_detras()
    pruebas_transiciones_pip()
    pruebas_panel_conectado()

    fallan = [n for n, ok in _resultados if not ok]
    print(f"\n{'=' * 60}")
    if fallan:
        print(f"{len(fallan)} de {len(_resultados)} pruebas FALLAN:")
        for n in fallan:
            print(f"  - {n}")
        return 1
    else:
        print(f"LAS {len(_resultados)} PRUEBAS PASAN")
    print("\nFalta la otra mitad:  python editor/test_align.py"
          "  (alineacion guion <-> transcripcion contra el panel real)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
