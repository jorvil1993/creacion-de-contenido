"""Motor de Adaptación RUM (Relevancia Universal de Mercado)

Toma patrones y fórmulas de videos virales (outliers) y los mapea automáticamente
al nicho de producción (DeviceShop / Lectura / E-readers o Lazos de Amor Mariano),
calculando la puntuación RUM = U x I x C x S x D x A y construyendo el objeto
de guion completo compatible con PANEL-PRODUCCION.html y editor.py.
"""

import json
from pathlib import Path
from editor.f14_viral_extractor import obtener_virales, buscar_viral_por_id


PLANTILLAS_VIRALES = [
    {
        "id": "viral_01_sueno_celular",
        "titulo_viral": "El hábito nocturno que arruina tu cerebro",
        "nicho_origen": "Salud / Productividad",
        "formato": "Rompe-creencias + POV",
        "rum_base": {"U": 9, "I": 9, "C": 10, "S": 9, "D": 9, "A": 8, "pct": 89},
        "hook_original": "Por eso no puedes dormir de noche",
        "estructura": [
            {"fase": "Hook (0-3s)", "proposito": "Síntoma universal inmediato sin preámbulos"},
            {"fase": "Conflicto (3-12s)", "proposito": "Describir el sufrimiento cotidiano en detalle"},
            {"fase": "Mecanismo (12-20s)", "proposito": "Explicar por qué ocurre sin tecnicismos"},
            {"fase": "Solución (20-30s)", "proposito": "Presentar el hábito/producto alternativo"},
            {"fase": "Cierre (30-36s)", "proposito": "CTA a conversación + loop al hook"}
        ],
        "adaptaciones": {
            "deviceshop": {
                "t": "El celular te está robando el sueño",
                "bloque": "Sueño y vista",
                "hook": "fisico",
                "hooksegs": 2.0,
                "cierresegs": 0.0,
                "hooktxt": "Arrancas mirando el celular en la cara y lo bajas de golpe",
                "utileria": ["Tu celular — tomas 1 y 2", "Kindle Paperwhite — tomas 4 y 5"],
                "set": ["De noche, o con la persiana baja", "Lámpara cálida detrás tuyo", "La cama o un sillón oscuro de fondo"],
                "tele": "Por eso no puedes dormir de noche. || Te acuestas cansado, agarras el celular un ratito… y a la hora sigues despierto con los ojos ardiendo. || No es que tengas insomnio. Es que esa pantalla te está tirando luz directo a los ojos, y tu cerebro cree que es de día. || Hay pantallas que no emiten luz: la reflejan, como el papel. Por eso los que leen en estas se duermen leyendo, en vez de desvelarse. || Si quieres que te explique cuál te conviene, escríbeme. Y deja de dormir con el celular en la cara.",
                "tomas": [
                    ["0–3s", "Primer plano · HOOK", "Empiezas con el celular pegado a la cara iluminándote. Lo bajas de golpe.", "Por eso no puedes dormir de noche."],
                    ["3–12s", "Plano medio", "Sostienes el celular apagado en la mano gesticulando.", "Te acuestas cansado, agarras el celular un ratito… y a la hora sigues despierto con los ojos ardiendo."],
                    ["12–20s", "Plano cerrado", "Señalas tus propios ojos al decir 'directo a los ojos'.", "No es que tengas insomnio. Es que esa pantalla te está tirando luz directo a los ojos, y tu cerebro cree que es de día."],
                    ["20–30s", "Plano medio · con producto", "Dejas el celular fuera de cuadro y levantas el Kindle.", "Hay pantallas que no emiten luz: la reflejan, como el papel. Por eso los que leen en estas se duermen leyendo, en vez de desvelarse."],
                    ["30–36s", "Plano medio · CIERRE", "Vuelves a la postura inicial con el Kindle.", "Si quieres que te explique cuál te conviene, escríbeme. Y deja de dormir con el celular en la cara."]
                ],
                "tl": [
                    ["0–3s", "Por eso no puedes dormir de noche.", "B-ROLL", "F01 a pantalla completa + banner de hook", "impacto_latido bajo", "—"],
                    ["3–6s", "Te acuestas cansado, agarras el celular un ratito…", "ANIM", "H08 arriba a la derecha: las apps que te desvelan", "transicion_corte", "entra 02-lofi a −22 dB"],
                    ["6–9s", "…y a la hora sigues despierto", "PIP", "F03 arriba a la derecha", "ui_blip_2", "—"],
                    ["9–11s", "con los ojos ardiendo.", "B-ROLL", "F02 a pantalla completa", "pop", "—"],
                    ["11–14s", "No es que tengas insomnio.", "YO", "Punch-in en 'insomnio'", "impacto_hit_2", "baja a −24 dB"],
                    ["14–17s", "Es que esa pantalla te está tirando luz", "YO", "Señalas tus propios ojos", "—", "—"],
                    ["17–20s", "directo a los ojos,", "PIP", "F29 arriba a la izquierda: la luz que golpea", "ui_blip_1", "—"],
                    ["20–23s", "y tu cerebro cree que es de día.", "B-ROLL", "F04 a pantalla completa: sol de mediodía", "whoosh_deep_1", "—"],
                    ["23–26s", "Hay pantallas que no emiten luz: la reflejan, como el papel.", "ANIM", "H03 anim-sol: la luz le pega y la página sigue legible", "whoosh_simple al cambiar de objeto", "sube a −19 dB"],
                    ["26–29s", "Por eso los que leen en estas se duermen leyendo,", "PIP", "P01 arriba a la derecha", "camara_enfoque_1", "—"],
                    ["29–32s", "en vez de desvelarse.", "B-ROLL", "F05 a pantalla completa", "reverso_whoosh", "—"],
                    ["32–35s", "Si quieres que te explique cuál te conviene, escríbeme.", "YO", "Vuelves a la postura inicial, con el Kindle", "—", "—"],
                    ["35–38s", "Y deja de dormir con el celular en la cara.", "ANIM", "tarjeta-cta + WhatsApp", "tada_cierre", "fade out"]
                ]
            },
            "lam": {
                "t": "Por eso sientes que tu oración no funciona",
                "bloque": "Espiritualidad y Oración",
                "hook": "fisico",
                "hooksegs": 1.5,
                "cierresegs": 0.0,
                "hooktxt": "Cierras una libreta de golpe y miras fijo a cámara",
                "utileria": ["Biblia o libreta de oración", "Celular vibrando a un lado"],
                "set": ["Escritorio cálido o rincón de oración", "Luz tenue de lámpara", "Silencio visual"],
                "tele": "Por eso sientes que tu oración no funciona. || Te sientas con buena intención, intentas rezar 5 minutos… y a la primera notificación agarras el celular. || No es falta de fe ni que Dios no te escuche. Es que tu atención está dividida entre el cielo y una pantalla. || El verdadero silencio interior empieza cuando sacas las distracciones de la habitación. || Comparte este video con alguien que necesite recuperar su paz en la oración.",
                "tomas": [
                    ["0–3s", "Primer plano · HOOK", "Cierras la libreta de golpe y miras fijo a cámara.", "Por eso sientes que tu oración no funciona."],
                    ["3–12s", "Plano medio", "Muestras el celular al lado de la Biblia.", "Te sientas con buena intención, intentas rezar 5 minutos… y a la primera notificación agarras el celular."],
                    ["12–20s", "Plano cerrado", "Hablas con tono confidencial e íntimo.", "No es falta de fe ni que Dios no te escuche. Es que tu atención está dividida entre el cielo y una pantalla."],
                    ["20–30s", "Plano medio · con Biblia", "Alejas el celular y abres la Biblia con ambas manos.", "El verdadero silencio interior empieza cuando sacas las distracciones de la habitación."],
                    ["30–36s", "Plano medio · CIERRE", "Gesto cálido mirando a cámara.", "Comparte este video con alguien que necesite recuperar su paz en la oración."]
                ],
                "tl": [
                    ["0–3s", "Por eso sientes que tu oración no funciona.", "YO", "Cierras la libreta. Banner de hook arriba", "impacto_latido bajo", "—"],
                    ["3–6s", "Te sientas con buena intención, intentas rezar 5 minutos…", "B-ROLL", "Persona intentando concentrarse", "transicion_corte", "entra musica sacra suave"],
                    ["6–9s", "…y a la primera notificación agarras el celular.", "PIP", "Pantalla de celular notificando", "ui_blip_2", "—"],
                    ["9–14s", "No es falta de fe ni que Dios no te escuche.", "YO", "Punch-in a cámara", "impacto_hit_2", "—"],
                    ["14–20s", "Es que tu atención está dividida entre el cielo y una pantalla.", "B-ROLL", "Detalle de vela encendida", "whoosh_deep_1", "—"],
                    ["20–28s", "El verdadero silencio interior empieza cuando sacas las distracciones.", "YO", "Abres la Biblia con paz", "whoosh_simple", "—"],
                    ["28–35s", "Comparte este video con alguien que necesite recuperar su paz.", "ANIM", "Tarjeta de mensaje y compartir", "tada_cierre", "fade out"]
                ]
            }
        }
    },
    {
        "id": "viral_02_anti_sell_caro",
        "titulo_viral": "Soy especialista y te digo cuál NO comprar",
        "nicho_origen": "E-Commerce / Recomendaciones",
        "formato": "Soy X y no hago Y (Anti-sell)",
        "rum_base": {"U": 10, "I": 9, "C": 10, "S": 9, "D": 9, "A": 9, "pct": 90},
        "hook_original": "Vendo estos y no te vendo el caro",
        "estructura": [
            {"fase": "Hook (0-3s)", "proposito": "Declaración contraria al interés propio (genera confianza masiva)"},
            {"fase": "Objeción / Relave (3-14s)", "proposito": "Mostrar la tentación de gastar de más"},
            {"fase": "Comparativa (14-26s)", "proposito": "Demostrar que la versión accesible cumple el 90% del uso"},
            {"fase": "Cierre (26-34s)", "proposito": "Filosofía de marca + CTA directo"}
        ],
        "adaptaciones": {
            "deviceshop": {
                "t": "Vendo estos y no te vendo el caro",
                "bloque": "Recomendación honesta",
                "hook": "objeto",
                "hooksegs": 3.0,
                "cierresegs": 0.0,
                "hooktxt": "Sostienes dos modelos, uno en cada mano, y bajas el caro",
                "utileria": ["Kindle Paperwhite 16GB", "Kindle Basic"],
                "set": ["De pie frente a cámara con ambos e-readers en mano"],
                "tele": "Vendo estos y no te vendo el caro. || Me escriben pidiendo el más caro y les digo que no. Que con ese no van a leer más. || Si vas a leer novelas en la cama, el de arriba no te da nada que el de abajo no te dé. Estás pagando por lo que no vas a usar. || Prefiero que compres el que te sirve y vuelvas, a venderte uno caro y que se te quede guardado. || Dime qué lees y te digo cuál NO comprar.",
                "tomas": [
                    ["0–3s", "Plano medio · HOOK", "Sostienes los dos aparatos en mano y bajas el caro.", "Vendo estos y no te vendo el caro."],
                    ["3–14s", "Mismo plano", "Niegas con la cabeza en 'les digo que no'.", "Me escriben pidiendo el más caro y les digo que no. Que con ese no van a leer más."],
                    ["14–26s", "Plano medio · con los dos", "Levantas los dos aparatos y los comparas.", "Si vas a leer novelas en la cama, el de arriba no te da nada que el de abajo no te dé. Estás pagando por lo que no vas a usar."],
                    ["26–36s", "Plano cerrado", "Dejas el caro fuera de cuadro. Te quedas con el recomendado.", "Prefiero que compres el que te sirve y vuelvas, a venderte uno caro y que se te quede guardado."],
                    ["36–40s", "Plano medio · CIERRE", "Vuelves a la postura inicial con manos vacías.", "Dime qué lees y te digo cuál NO comprar."]
                ],
                "tl": [
                    ["0–3s", "Vendo estos y no te vendo el caro.", "YO", "Tú solo + banner de hook", "impacto_bang_cine", "—"],
                    ["3–6s", "Me escriben pidiendo el más caro", "YO", "Niegas con la cabeza", "—", "entra 03-corporate a −21 dB"],
                    ["6–8s", "y les digo que no.", "ANIM", "H07 destello mientras niegas", "pop", "—"],
                    ["8–11s", "Que con ese no van a leer más.", "YO", "Punch-in", "impacto_hit_3", "—"],
                    ["11–14s", "Si vas a leer novelas en la cama,", "B-ROLL", "F05 a pantalla completa", "whoosh_deep_1", "—"],
                    ["14–17s", "el de arriba no te da nada", "YO", "Levantas los dos aparatos", "whoosh_swish_1", "—"],
                    ["17–20s", "que el de abajo no te dé.", "ANIM", "H02 comparativa de specs", "riser_cortado", "sube a −19 dB"],
                    ["20–23s", "Estás pagando por lo que no vas a usar.", "YO", "Punch-in sobre aparato caro", "impacto_grave_2", "—"],
                    ["23–26s", "Prefiero que compres el que te sirve y vuelvas,", "YO", "Dejas el caro fuera de cuadro", "transicion_corte", "—"],
                    ["26–29s", "a venderte uno caro", "PIP", "P02 arriba a la izquierda", "camara_click_5", "—"],
                    ["29–31s", "y que se te quede guardado.", "ANIM", "H07 bandera: mejor que vuelvas", "reverso_4", "—"],
                    ["31–34s", "Dime qué lees y te digo cuál NO comprar.", "ANIM", "tarjeta-cta", "tada_cierre", "fade out"]
                ]
            },
            "lam": {
                "t": "No necesitas rezar 3 horas para estar cerca de Dios",
                "bloque": "Vida de Oración",
                "hook": "talking",
                "hooksegs": 0.0,
                "cierresegs": 0.0,
                "hooktxt": "Mirada directa sin vacilar",
                "utileria": ["Rosario o libreta pequeña"],
                "set": ["De pie frente a cámara, fondo sobrio"],
                "tele": "No necesitas rezar 3 horas para estar cerca de Dios. || Muchos creen que si no hacen devociones larguísimas su oración no vale nada. Y terminan abandonando todo. || Dios prefiere 5 minutos con tu corazón presente que 2 horas de frases repetidas por obligación sin estar ahí. || Empieza por 5 minutos constantes al despertar. || Escribe PAZ y te comparto la guía de oración diaria.",
                "tomas": [
                    ["0–3s", "Plano medio · HOOK", "Mirada fija a cámara.", "No necesitas rezar 3 horas para estar cerca de Dios."],
                    ["3–14s", "Plano cerrado", "Niegas suavemente con la cabeza.", "Muchos creen que si no hacen devociones larguísimas su oración no vale nada. Y terminan abandonando todo."],
                    ["14–25s", "Plano medio", "Marcas el contraste con las manos.", "Dios prefiere 5 minutos con tu corazón presente que 2 horas de frases repetidas por obligación sin estar ahí."],
                    ["25–35s", "Plano cerrado", "Tono de consejo cercano.", "Empieza por 5 minutos constantes al despertar."],
                    ["35–40s", "Plano medio · CIERRE", "Gesto final cálido.", "Escribe PAZ y te comparto la guía de oración diaria."]
                ],
                "tl": [
                    ["0–3s", "No necesitas rezar 3 horas para estar cerca de Dios.", "YO", "Banner de hook arriba", "impacto_latido bajo", "—"],
                    ["3–12s", "Muchos creen que si no hacen devociones larguísimas...", "B-ROLL", "Reloj corriendo rápido", "transicion_corte", "musica ambiental suave"],
                    ["12–22s", "Dios prefiere 5 minutos con tu corazón presente...", "YO", "Punch-in a cámara", "impacto_hit", "—"],
                    ["22–30s", "Empieza por 5 minutos constantes al despertar.", "B-ROLL", "Luz de mañana entrando por la ventana", "whoosh_simple", "—"],
                    ["30–35s", "Escribe PAZ y te comparto la guía.", "ANIM", "Tarjeta CTA con palabra PAZ", "tada_cierre", "fade out"]
                ]
            }
        }
    }
]


def listar_plantillas_virales():
    return PLANTILLAS_VIRALES


def adaptar_guion_viral(plantilla_id: str, nicho: str = "deviceshop") -> dict:
    """Adapta una plantilla viral al nicho especificado ('deviceshop' o 'lam')."""
    plantilla = next((p for p in PLANTILLAS_VIRALES if p["id"] == plantilla_id), None)
    if not plantilla:
        plantilla = PLANTILLAS_VIRALES[0]

    nicho_key = "lam" if nicho.lower() in ("lam", "lazos", "religioso") else "deviceshop"
    adaptacion = plantilla["adaptaciones"].get(nicho_key, plantilla["adaptaciones"]["deviceshop"])

    rum = plantilla["rum_base"]

    # Traer detalles de ingesta del viral de referencia
    info_viral = buscar_viral_por_id(plantilla_id)

    return {
        "n": 99,
        "t": adaptacion["t"],
        "rum": rum["pct"],
        "bloque": adaptacion["bloque"],
        "hook": adaptacion["hook"],
        "hooksegs": adaptacion["hooksegs"],
        "cierresegs": adaptacion["cierresegs"],
        "hooktxt": adaptacion["hooktxt"],
        "utileria": adaptacion["utileria"],
        "set": adaptacion["set"],
        "tele": adaptacion["tele"],
        "tomas": adaptacion["tomas"],
        "tl": adaptacion["tl"],
        "viral_ref": {
            "id": plantilla["id"],
            "titulo": plantilla["titulo_viral"],
            "hook_original": plantilla["hook_original"],
            "nicho_origen": plantilla["nicho_origen"],
            "rum_stats": f"U{rum['U']} · I{rum['I']} · C{rum['C']} · S{rum['S']} · D{rum['D']} · A{rum['A']} → {rum['pct']}%",
            "info_extra": info_viral
        }
    }
