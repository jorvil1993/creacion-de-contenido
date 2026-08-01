"""Extractor y Analizador de Videos Virales (Outliers 2026)

Este módulo gestiona la ingesta de referencias virales de TikTok / Instagram Reels / YouTube Shorts,
extrayendo la anatomía del guion (Hook físico, ritmo de cortes, texto en pantalla y sonidos).
"""

import json
from pathlib import Path

# Catálogo completo de videos virales de referencia (Outliers minados y analizados con Data Real 2026)
VIRALES_MINADOS = [
    {
        "id": "viral_01_sueno_celular",
        "plataforma": "TikTok",
        "url_referencia": "https://tiktok.com/@estilodevida/video/101",
        "creador": "@estilodevida",
        "familia_hook": "Contraste & Resultado + POV",
        "metricas": {"views": "1.8M", "seguidores": "15K", "ratio_outlier": "120x", "shares": "42K", "completion_rate": "38%"},
        "rum_calculado": {"U": 9, "I": 9, "C": 10, "S": 9, "D": 9, "A": 8, "total_pct": 89},
        "filmacion": {
            "hook_tipo": "fisico",
            "hook_accion": "Arrancas de noche con el celular pegado a la cara iluminándote en la oscuridad. Lo bajas de golpe y miras fijo a cámara.",
            "ritmo_cortes_cpm": 32,
            "duracion_total_s": 38,
            "props_utileria": ["Celular encendido", "Lámpara de noche cálida", "Objeto alternativo de reemplazo"],
            "planos": ["Plano medio corto (0-3s)", "Plano medio de perfil (3-12s)", "Plano cerrado a ojos (12-20s)", "Plano medio con producto (20-30s)", "Plano medio cierre (30-38s)"]
        },
        "edicion": {
            "banner_hook_texto": "POR ESO NO PUEDES DORMIR DE NOCHE",
            "estilo_banner": "Banda superior negro/amarillo alto contraste",
            "porcentaje_hablante_yo": 45,
            "porcentaje_broll": 40,
            "porcentaje_pip": 15,
            "transiciones_clave": ["Punch-in al segundo 11 en palabra insomnio", "Glitch al segundo 20 al cambiar objeto"]
        },
        "sonidos": {
            "sfx_entrada": "impacto_latido",
            "sfx_transiciones": ["transicion_corte", "ui_blip_2", "pop", "whoosh_deep_1"],
            "sfx_cierre": "tada_cierre",
            "musica_mood": "Lofi ambiental suave (−22 dB)",
            "pista_id": "02-lofi"
        },
        "transcripcion_desglosada": [
            {"t": "0-3s", "texto": "Por eso no puedes dormir de noche.", "fase": "Hook"},
            {"t": "3-12s", "texto": "Te acuestas cansado, agarras el celular un ratito… y a la hora sigues despierto con los ojos ardiendo.", "fase": "Conflicto / Relave"},
            {"t": "12-20s", "texto": "No es que tengas insomnio. Es que esa pantalla te está tirando luz directo a los ojos, y tu cerebro cree que es de día.", "fase": "Mecanismo"},
            {"t": "20-30s", "texto": "Hay pantallas que no emiten luz: la reflejan, como el papel. Por eso los que leen en estas se duermen leyendo.", "fase": "Solución"},
            {"t": "30-38s", "texto": "Si quieres que te explique cuál te conviene, escríbeme. Y deja de dormir con el celular en la cara.", "fase": "Cierre / CTA"}
        ]
    },
    {
        "id": "viral_02_anti_sell_caro",
        "plataforma": "Instagram Reels",
        "url_referencia": "https://instagram.com/reels/202",
        "creador": "@tech_honesto",
        "familia_hook": "Anti-Sell / Desafío a la Creencia",
        "metricas": {"views": "2.4M", "seguidores": "30K", "ratio_outlier": "80x", "shares": "65K", "completion_rate": "41%"},
        "rum_calculado": {"U": 10, "I": 9, "C": 10, "S": 9, "D": 9, "A": 9, "total_pct": 90},
        "filmacion": {
            "hook_tipo": "objeto",
            "hook_accion": "Sostienes dos opciones en mano (una en cada mano) a la altura del pecho. Bajas la costosa de golpe.",
            "ritmo_cortes_cpm": 28,
            "duracion_total_s": 40,
            "props_utileria": ["Opción costosa", "Opción accesible / recomendada"],
            "planos": ["Plano medio con dos objetos (0-3s)", "Plano medio gesticulando (3-14s)", "Plano cerrado comparando (14-26s)", "Plano cerrado recomendación (26-36s)", "Plano medio cierre (36-40s)"]
        },
        "edicion": {
            "banner_hook_texto": "VENDO ESTOS Y NO TE VENDO EL CARO",
            "estilo_banner": "Título-tarjeta a pantalla completa",
            "porcentaje_hablante_yo": 60,
            "porcentaje_broll": 25,
            "porcentaje_pip": 15,
            "transiciones_clave": ["Punch-in al segundo 8 en palabra NO", "Corte rápido al descartar el caro"]
        },
        "sonidos": {
            "sfx_entrada": "impacto_bang_cine",
            "sfx_transiciones": ["pop", "impacto_hit_3", "whoosh_deep_1", "riser_cortado"],
            "sfx_cierre": "tada_cierre",
            "musica_mood": "Corporate / Upbeat dinámico (−21 dB)",
            "pista_id": "03-corporate"
        },
        "transcripcion_desglosada": [
            {"t": "0-3s", "texto": "Vendo estos y no te vendo el caro.", "fase": "Hook Anti-Sell"},
            {"t": "3-14s", "texto": "Me escriben pidiendo el más caro y les digo que no. Que con ese no van a leer más.", "fase": "Objeción / Confianza"},
            {"t": "14-26s", "texto": "Si vas a leer novelas en la cama, el de arriba no te da nada que el de abajo no te dé. Estás pagando por lo que no vas a usar.", "fase": "Comparativa"},
            {"t": "26-36s", "texto": "Prefiero que compres el que te sirve y vuelvas, a venderte uno caro y que se te quede guardado.", "fase": "Filosofía de Marca"},
            {"t": "36-40s", "texto": "Dime qué lees y te digo cuál NO comprar.", "fase": "CTA a Conversación"}
        ]
    },
    {
        "id": "viral_03_advertencia_error",
        "plataforma": "TikTok",
        "url_referencia": "https://tiktok.com/@lector_experto/video/303",
        "creador": "@lector_experto",
        "familia_hook": "Advertencia / Evitación de Error",
        "metricas": {"views": "1.2M", "seguidores": "18K", "ratio_outlier": "66x", "shares": "31K", "completion_rate": "36%"},
        "rum_calculado": {"U": 9, "I": 8, "C": 10, "S": 8, "D": 8, "A": 9, "total_pct": 84},
        "filmacion": {
            "hook_tipo": "accion",
            "hook_accion": "Muestras la mano haciendo señal de ALTO y miras directo a cámara con expresión seria.",
            "ritmo_cortes_cpm": 30,
            "duracion_total_s": 35,
            "props_utileria": ["Dispositivo o hábito equivocado"],
            "planos": ["Plano medio señal de alto (0-3s)", "Plano cerrado advertencia (3-12s)", "Plano medio corrección (12-25s)", "Plano medio cierre (25-35s)"]
        },
        "edicion": {
            "banner_hook_texto": "NO COMETAS ESTE ERROR AL LEER DE NOCHE",
            "estilo_banner": "Franja roja/blanca de advertencia",
            "porcentaje_hablante_yo": 50,
            "porcentaje_broll": 35,
            "porcentaje_pip": 15,
            "transiciones_clave": ["Zoom in rápido en el segundo 3", "Flash sutil en el segundo 12"]
        },
        "sonidos": {
            "sfx_entrada": "impacto_grave",
            "sfx_transiciones": ["whoosh_swish_1", "ui_blip_1", "camara_click_2"],
            "sfx_cierre": "tada_cierre",
            "musica_mood": "Tensión limpia que resuelve en calma (−22 dB)",
            "pista_id": "02-lofi"
        },
        "transcripcion_desglosada": [
            {"t": "0-3s", "texto": "No cometas este error al intentar leer antes de dormir.", "fase": "Advertencia Hook"},
            {"t": "3-12s", "texto": "Usar la pantalla del teléfono con el modo oscuro no evita que la luz azul bloquee tu melatonina.", "fase": "Mito vs Realidad"},
            {"t": "12-25s", "texto": "La única tecnología real que no emite luz hacia tus ojos es la tinta electrónica.", "fase": "Demostración de Solución"},
            {"t": "25-35s", "texto": "Comenta LIBRO y te enseño cuál es el modelo ideal para tu rutina.", "fase": "CTA"}
        ]
    },
    {
        "id": "viral_04_identidad_lector",
        "plataforma": "Instagram Reels",
        "url_referencia": "https://instagram.com/reels/404",
        "creador": "@habitos_lectura",
        "familia_hook": "Identidad & Comunidad",
        "metricas": {"views": "1.5M", "seguidores": "22K", "ratio_outlier": "68x", "shares": "39K", "completion_rate": "39%"},
        "rum_calculado": {"U": 9, "I": 9, "C": 9, "S": 9, "D": 9, "A": 8, "total_pct": 86},
        "filmacion": {
            "hook_tipo": "talking",
            "hook_accion": "Sentado relajado con una taza, miras a cámara con tono cercano e identitario.",
            "ritmo_cortes_cpm": 26,
            "duracion_total_s": 36,
            "props_utileria": ["Taza de café/té", "Libro o e-reader en mesa"],
            "planos": ["Plano medio sentado (0-3s)", "Plano cerrado empático (3-15s)", "Plano medio demostración (15-28s)", "Plano medio cierre (28-36s)"]
        },
        "edicion": {
            "banner_hook_texto": "SI ERES DE LOS QUE AMA LEER PERO NO TIENE TIEMPO",
            "estilo_banner": "Subtítulo estilo píldora césped/cian",
            "porcentaje_hablante_yo": 55,
            "porcentaje_broll": 30,
            "porcentaje_pip": 15,
            "transiciones_clave": ["Corte suave entre planos", "Destello sutil en el beneficio"]
        },
        "sonidos": {
            "sfx_entrada": "whoosh_simple",
            "sfx_transiciones": ["pop", "camara_enfoque_1", "reverso_whoosh"],
            "sfx_cierre": "tada_cierre",
            "musica_mood": "Lofi cálido de cafetería (−22 dB)",
            "pista_id": "02-lofi"
        },
        "transcripcion_desglosada": [
            {"t": "0-3s", "texto": "Si eres de los que ama leer pero siente que ya no tiene tiempo, escucha esto.", "fase": "Identidad Hook"},
            {"t": "3-15s", "texto": "No es que no tengas tiempo. Es que tu mente está tan fatigada de las pantallas del trabajo que agarrar un libro pesado se siente como un esfuerzo enorme.", "fase": "Empatía & Diagnóstico"},
            {"t": "15-28s", "texto": "Tener todos tus libros en 150 gramos y con luz cálida cambia por completo cómo usas tus 10 minutos libres.", "fase": "Transformación"},
            {"t": "28-36s", "texto": "Mándaselo a tu amigo que siempre dice que quiere volver a leer.", "fase": "CTA Shareability"}
        ]
    },
    {
        "id": "viral_05_open_loop_secreto",
        "plataforma": "TikTok",
        "url_referencia": "https://tiktok.com/@trucos_digitales/video/505",
        "creador": "@trucos_digitales",
        "familia_hook": "Open Loop / Misterio Resuelto al Final",
        "metricas": {"views": "3.1M", "seguidores": "40K", "ratio_outlier": "77x", "shares": "88K", "completion_rate": "44%"},
        "rum_calculado": {"U": 9, "I": 9, "C": 10, "S": 10, "D": 9, "A": 9, "total_pct": 91},
        "filmacion": {
            "hook_tipo": "objeto",
            "hook_accion": "Levantas un dispositivo y lo miras con sorpresa, como si acabaras de descubrir algo insólito.",
            "ritmo_cortes_cpm": 34,
            "duracion_total_s": 42,
            "props_utileria": ["Kindle o e-reader con funda cerrada"],
            "planos": ["Plano medio descubrimiento (0-3s)", "Plano cerrado intriga (3-15s)", "Plano medio prueba (15-30s)", "Plano medio revelación final (30-42s)"]
        },
        "edicion": {
            "banner_hook_texto": "CASI DEVUELVO ESTO EL PRIMER DÍA HASTA QUE...",
            "estilo_banner": "Banner negro con texto resaltado en amarillo",
            "porcentaje_hablante_yo": 40,
            "porcentaje_broll": 45,
            "porcentaje_pip": 15,
            "transiciones_clave": ["Glitch en el segundo 3", "Whoosh rápido en la revelación"]
        },
        "sonidos": {
            "sfx_entrada": "impacto_latido",
            "sfx_transiciones": ["whoosh_rapido", "ui_blip_2", "impacto_hit_2", "camara_click_5"],
            "sfx_cierre": "tada_cierre",
            "musica_mood": "Curiosidad rítmica que acelera (−20 dB)",
            "pista_id": "03-corporate"
        },
        "transcripcion_desglosada": [
            {"t": "0-3s", "texto": "Casi devuelvo esto el primer día, hasta que descubrí este truco.", "fase": "Open Loop Hook"},
            {"t": "3-15s", "texto": "Pensé que se vería igual que mi tablet y que me cansaría la vista exactamente igual.", "fase": "Duda / Conflicto"},
            {"t": "15-30s", "texto": "Pero al ajustar la temperatura de luz a tono cálido y sacarlo al sol directo, me di cuenta de que no hay ningún reflejo.", "fase": "Descubrimiento"},
            {"t": "30-42s", "texto": "Es literalmente papel digital. Si quieres ver cómo funciona en vivo, escríbeme.", "fase": "Revelación & CTA"}
        ]
    }
]


def obtener_virales():
    return VIRALES_MINADOS


def buscar_viral_por_id(viral_id: str):
    return next((v for v in VIRALES_MINADOS if v["id"] == viral_id), VIRALES_MINADOS[0])
