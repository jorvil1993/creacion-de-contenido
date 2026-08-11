"""Panel de artes conectado — servidor local.

Hermano de `editor/panel_servidor.py`, no una extension suya. Se dejo aparte a
proposito: aquel son 642 lineas atadas a la estructura de PANEL-PRODUCCION.html
(posiciones de guion/fila, f0_preparar), y mezclarle rutas de artes haria mas
pesados y mas fragiles a los dos. Ademas se van a usar a la vez: el panel de
artes abierto mientras se renderiza un video.

Solo libreria estandar, igual que el otro. No agrega ni una dependencia: reusa
el venv que ya tiene PIL, rembg y onnxruntime.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/panel_servidor_artes.py
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes import (  # noqa: E402
    a3_copy, a4_variacion, a6_qwen, a8_conceptos, a9_prompts, a10_comfy,
    a11_agy, a12_codex, a13_editorial,
)
from artes.a1_marca import ESCENAS, FORMATOS, Arte, render  # noqa: E402
from artes.a2_recorte import FOTOS_AMAZON, recortar  # noqa: E402

PANEL = RAIZ / "PANEL-ARTES.html"
# Todo (candidatos intermedios Y arte final) vive bajo una carpeta por sesion
# de trabajo, ej. C:\ai-video\artes\2026-08-03-1430-kindle-paperwhite\ --
# pedido explicito de Jose el 2026-08-03: antes se generaba en 3 lugares
# distintos (TRABAJO suelto, TRABAJO/subir, y salida/artes/ dentro del repo)
# y era imposible de controlar/borrar a mano. Ahora cada sesion es autocontenida:
# cuando Jose termina con una idea, borra ESA carpeta entera y listo.
TRABAJO = Path(r"C:\ai-video\artes")

# Estado de la corrida en curso. Un arte por vez: renderizar dos a la vez no
# aporta nada (el cuello es el recorte, que usa la GPU) y complica el log.
TRABAJOS: dict[str, dict] = {}


def _sesion(sid: str | None) -> Path:
    """Carpeta de la sesion de trabajo actual (candidatos + arte final juntos).

    El id lo arma el navegador una vez por producto elegido (ver ilPintar/
    agPintar/fotos() en PANEL-ARTES.html) y se reusa en cada llamada de esa
    misma ronda de trabajo -- asi todo lo generado para una idea queda bajo
    un solo lugar. Si algun llamador viejo no lo manda, cae en "sin-sesion"
    en vez de romper. Uso: `_sesion(cfg.get("sesion"))` en POST (json),
    `_sesion(q.get("sesion", [""])[0])` en GET (query string).
    """
    sid = re.sub(r"[^A-Za-z0-9_-]", "-", sid or "sin-sesion")[:80]
    carpeta = TRABAJO / sid
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _proveedor_de(conversation_id: str) -> str:
    """"agy:<id>" -> "agy", "codex:<id>" -> "codex" -- ver a11_agy.generar_con_respaldo().
    Se expone al panel para que el log diga cuando se uso el respaldo."""
    return conversation_id.split(":", 1)[0] if ":" in conversation_id else "agy"


def _proveedores_imagen() -> list[dict]:
    return [
        {"id": "agy", "nombre": "Antigravity (AGY)", "disponible": a11_agy.disponible()},
        {"id": "chatgpt", "nombre": "ChatGPT (Codex CLI)", "disponible": a12_codex.disponible()},
    ]


def _generar_imagen(proveedor: str, prompt: str, destino: Path,
                    referencias: list[Path] | None = None) -> tuple[Path, str]:
    """Generación de fondos desde la cuenta elegida en el Panel Artes."""
    proveedor = (proveedor or "agy").lower()
    if proveedor == "chatgpt":
        ruta, cid = a12_codex.generar_imagen(prompt, destino, referencias=referencias)
        return ruta, f"chatgpt:{cid}"
    if proveedor == "agy":
        ruta, cid = a11_agy.generar_imagen(prompt, destino, referencias=referencias)
        return ruta, f"agy:{cid}"
    raise ValueError("Proveedor inválido: elegí Antigravity o ChatGPT (Codex CLI).")


def _productos() -> list[dict]:
    """Productos con las fotos que hay de cada uno.

    El panel muestra las miniaturas para que Jose elija cual recortar. NO se
    adivina: se probo suponer que la `img2` era siempre el hero limpio y en el
    Kobo Libra esa foto era una infografia — el recorte salio con texto en
    ingles adentro.
    """
    por_producto: dict[str, list[str]] = {}
    for f in sorted(FOTOS_AMAZON.glob("fotos-amazon_*_img*.jpg")):
        resto = f.stem[len("fotos-amazon_"):]
        prod = resto.rsplit("_img", 1)[0]
        por_producto.setdefault(prod, []).append(f.name)
    return [
        {"clave": k, "fotos": v, "fichas": bool(a8_conceptos.FICHAS.get(k)),
         "copy": k in a3_copy.PRODUCTOS}
        for k, v in sorted(por_producto.items())
    ]


def _fotos_en(carpeta: Path) -> list[str]:
    if not carpeta.exists():
        return []
    exts = (".jpg", ".jpeg", ".png", ".webp")
    return sorted(f.name for f in carpeta.iterdir() if f.suffix.lower() in exts)


# Donde va el producto dentro del lienzo, por formato. NO es una formula: el
# bloque de texto y el pie miden lo mismo en PIXELES ABSOLUTOS en los tres
# formatos (salen de `ancho`, ver a1_marca.py), pero el producto se posiciona en
# % de `alto` -- que cambia de 1080 a 1350 a 1920. Cada terna salio de renderizar
# y mirar, no de razonar en abstracto. Si se toca una, hay que volver a renderizar
# los tres y comparar (artes/pruebas_formato.py hace justo eso).
#
#   formato  -> (alto %, centro y %, centro x %) para (limpio, resto)
_COLOCACION = {
    "cuadrado": {"limpio": (44, 57, 50), "otro": (38, 57, 79)},
    "retrato":  {"limpio": (46, 57, 50), "otro": (39, 57, 79)},
    "vertical": {"limpio": (60, 52, 50), "otro": (48, 54, 66)},
}


def _colocacion(formato: str, modo: str) -> tuple[float, float, float]:
    tabla = _COLOCACION.get(formato, _COLOCACION["cuadrado"])
    return tabla["limpio" if modo == "limpio" else "otro"]


# Campos de cfg que NO sirven para saber por que un arte rindio y solo ensucian
# la ficha (rutas de archivos temporales, ids de conversacion de agy).
_FICHA_IGNORA = {"sesion", "foto_gemini", "split_izq", "split_der",
                 "conversation_id", "prompt_armado"}


def _ficha(arte_jpg: Path, cfg: dict, copys: dict | None, **extra) -> Path:
    """Deja al lado del arte todo lo que hizo falta para producirlo.

    Reemplaza al sidecar `<nombre>.copys.json`, que guardaba SOLO los 3 copys:
    con eso era imposible saber, dos meses despues, si el que rindio fue el
    angulo regalo o el de la vista. Ahora queda registrado el concepto, el
    molde, el formato, el sello, la ciudad y la fecha.

    `resultados` nace vacio a proposito. Lo llena despues Claude Code leyendo la
    cuenta de Meta con el conector (el panel no tiene credenciales de Meta ni
    conviene que las tenga): ver `_indice_fichas()` y /api/fichas.
    """
    datos = {
        "arte": arte_jpg.name,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {k: v for k, v in cfg.items() if k not in _FICHA_IGNORA},
        "copys": copys,
        # Lo llena el conector de Meta, no el panel.
        "resultados": {"publicado": None, "impresiones": None, "clics": None,
                       "ctr": None, "conversaciones": None, "costo_conv": None},
        **extra,
    }
    ficha = arte_jpg.with_suffix(".ficha.json")
    ficha.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    # Se sigue escribiendo el sidecar viejo: /api/historial-copys lo lee y los
    # artes ya generados dependen de el.
    if copys is not None:
        arte_jpg.with_name(f"{arte_jpg.stem}.copys.json").write_text(
            json.dumps(copys, ensure_ascii=False), encoding="utf-8")
    return ficha


def _indice_fichas(limite: int = 200) -> list[dict]:
    """Todas las fichas de todas las sesiones, de la mas nueva a la mas vieja.

    Es lo que hace posible la revision automatica: Claude Code pide
    /api/fichas, cruza cada arte con lo que devuelve el conector de Meta y
    escribe los `resultados` de vuelta con /api/ficha-resultado.
    """
    fichas = sorted(TRABAJO.glob("*/*.ficha.json"),
                    key=lambda f: f.stat().st_mtime, reverse=True)
    salida = []
    for f in fichas[:limite]:
        try:
            d = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        d["sesion"] = f.parent.name
        salida.append(d)
    return salida


def _escena_qwen(tid: str, cfg: dict, concepto, origen: Path, paso) -> Path:
    """Genera (o reusa) el fondo con Qwen para el concepto elegido.

    Se cachea dentro de la carpeta de la sesion actual: repetir "Generar arte"
    en la MISMA sesion no vuelve a pagar los ~150-185s que tarda Qwen (medido
    en a10_comfy.py), pero cambiar de sesion si.
    """
    cache = _sesion(cfg.get("sesion")) / f"fondo-qwen-{concepto.clave}.png"
    if cache.exists():
        paso(f"escena IA ya generada, se reusa: {cache.name}")
        return cache

    if not a10_comfy.arrancar(avisar=paso):
        raise RuntimeError("ComfyUI no arranco — revisa C:\\ai-video\\comfy-artes.log")

    vram = a10_comfy.vram()
    if vram:
        usada, total = vram
        paso(f"VRAM: {usada} / {total} MiB")

    paso(f"generando escena con Qwen ({concepto.clave})... esto tarda 2-3 min")
    semilla = abs(hash(concepto.clave)) % (2**31)
    try:
        salida_comfy = a6_qwen.editar(origen, concepto.escena, semilla=semilla)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(salida_comfy.read_bytes())
    finally:
        # Docstring de a10_comfy.py: dejar ComfyUI prendido no ahorra tiempo
        # (el modelo no entra en 16GB igual) y le saca la GPU al pipeline de
        # video. Se apaga apenas termina, siempre.
        a10_comfy.apagar(avisar=paso)
    return cache


def _qwen_generar_ia(tid: str, cfg: dict) -> None:
    """Trabajo async para /api/qwen-generar-ia -- mismo patron que _generar()
    (TRABAJOS + paso() + polling desde /api/trabajo) en vez de una respuesta
    sincrona de 2-4 min, para que el navegador muestre progreso real en vez
    de parecer colgado.

    Dos modos (Jose pidio poder probar los dos, no asumir cual sirve):
    - preservar_producto=False (default, seguro): denoise parejo, el
      producto real se compone DESPUES con el recorte local -- nunca pasa
      por IA.
    - preservar_producto=True (experimental): usa el alfa del recorte como
      SetLatentNoiseMask para que Qwen redibuje SOLO el fondo. Confirmado
      2026-08-03 que el mecanismo de mascara funciona (fondo, mano y marco
      del producto quedan intactos) pero rembg no segmenta bien pantallas
      claras -- puede salir con la pantalla mezclada con la escena nueva.
    """
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        foto = cfg.get("foto", "")
        prompt = cfg.get("prompt", "").strip()
        preservar_producto = bool(cfg.get("preservar_producto"))
        try:
            denoise = float(cfg.get("denoise", 1.0))
        except (TypeError, ValueError):
            denoise = 1.0
        if not foto:
            raise RuntimeError("elegi una foto base primero")
        if not prompt:
            raise RuntimeError("falta el prompt")
        origen = FOTOS_AMAZON / foto
        if not origen.exists():
            raise RuntimeError(f"no existe la foto {foto}")

        sesion = _sesion(cfg.get("sesion"))
        mascara = None
        if preservar_producto:
            mascara = sesion / "recorte.png"
            if not mascara.exists():
                paso("recortando el producto para la mascara (rembg)...")
                recortar(origen, mascara)
            else:
                paso("mascara ya existente, se reusa")

        if not a10_comfy.arrancar(avisar=paso):
            raise RuntimeError("ComfyUI no arranco — revisa C:\\ai-video\\comfy-artes.log")
        paso(f"generando con Qwen (denoise={denoise}, "
             f"{'con mascara de producto' if mascara else 'sin mascara'})... esto tarda 2-4 min")
        try:
            semilla = int(time.time()) % (2**31)
            salida_comfy = a6_qwen.editar(origen, prompt, semilla=semilla,
                                            denoise=denoise, mascara=mascara)
            nombre = f"fondo-qwen-{int(time.time())}.png"
            destino = sesion / nombre
            destino.write_bytes(salida_comfy.read_bytes())
        finally:
            a10_comfy.apagar(avisar=paso)

        paso(f"LISTO: {nombre}")
        TRABAJOS[tid]["estado"] = "listo"
        TRABAJOS[tid]["archivo"] = nombre
        TRABAJOS[tid]["producto_en_imagen"] = preservar_producto
    except Exception as e:
        paso(f"ERROR: {e}")
        TRABAJOS[tid]["estado"] = "error"


def _imagen_ia(tid: str, cfg: dict) -> None:
    """Trabajo async para /api/imagen-ia (fondo solo, agy) -- mismo patron que
    _qwen_generar_ia: sin esto, la llamada sincrona a agy (hasta 240s, mas si
    es una correccion sobre una conversacion) se ve colgada en el navegador
    sin ningun aviso de progreso. Encontrado 2026-08-03 con una correccion
    real que tardo mas de lo esperado en la pestana Antigravity.
    """
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        prompt = cfg.get("prompt", "").strip()
        if not prompt:
            raise RuntimeError("falta el prompt")
        proveedor = cfg.get("proveedor", "agy")
        paso(f"generando fondo con {proveedor}... esto tarda 15-40s, mas si es una correccion")
        nombre = f"fondo-{proveedor}-{int(time.time())}.png"
        destino = _sesion(cfg.get("sesion")) / nombre
        persona_foto = a9_prompts.ruta_persona(cfg.get("persona", ""))
        _, cid = _generar_imagen(proveedor, prompt, destino,
                                  referencias=[persona_foto] if persona_foto else None)
        paso(f"LISTO: {nombre}")
        TRABAJOS[tid]["estado"] = "listo"
        TRABAJOS[tid]["archivo"] = nombre
        TRABAJOS[tid]["conversation_id"] = cid
    except Exception as e:
        paso(f"ERROR: {e}")
        TRABAJOS[tid]["estado"] = "error"


def _imagen_producto_ia(tid: str, cfg: dict) -> None:
    """Trabajo async para /api/imagen-producto-ia (fondo CON el producto, agy)
    -- mismo motivo que _imagen_ia(): la correccion sobre una conversacion
    puede tardar bastante mas que los ~15-40s de una generacion nueva, y sin
    progreso en vivo parece colgado aunque este funcionando bien.
    """
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        foto = cfg.get("foto", "")
        if not foto:
            raise RuntimeError("elegi una foto base primero")
        origen = FOTOS_AMAZON / foto
        if not origen.exists():
            raise RuntimeError(f"no existe la foto {foto}")
        proveedor = cfg.get("proveedor", "agy")
        paso(f"generando fondo con el producto ({proveedor})... esto tarda 15-40s, mas si es una correccion")
        nombre = f"fondo-{proveedor}-conproducto-{int(time.time())}.png"
        destino = _sesion(cfg.get("sesion")) / nombre
        _, cid = a9_prompts.generar_imagen_producto_ia(
            cfg.get("titular", ""), cfg.get("escena_base", ""),
            cfg.get("formato", "cuadrado"), origen, destino,
            correccion=cfg.get("correccion", ""),
            conversation_id=cfg.get("conversation_id"),
            prompt_armado=cfg.get("prompt", ""),
            persona=cfg.get("persona", ""),
            proveedor=proveedor,
        )
        paso(f"LISTO: {nombre}")
        TRABAJOS[tid]["estado"] = "listo"
        TRABAJOS[tid]["archivo"] = nombre
        TRABAJOS[tid]["conversation_id"] = cid
    except Exception as e:
        paso(f"ERROR: {e}")
        TRABAJOS[tid]["estado"] = "error"


def _generar(tid: str, cfg: dict) -> None:
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        modo = cfg["modo"]
        concepto = a8_conceptos.por_clave(cfg["concepto"])
        titular = cfg.get("titular") or concepto.titular
        # La ciudad al inicio del titular. No es decoracion: los 5 anuncios
        # historicos que abren nombrando Santa Cruz o Cochabamba estan TODOS por
        # encima del 2,9% de CTR (metricas-meta-para-pauta.md), contra 1-2% de
        # la industria. Va solo en el titular; los hashtags del copy siguen
        # siendo nacionales, que es otra decision y no se toca.
        ciudad = (cfg.get("ciudad") or "").strip()
        if ciudad:
            titular = f"{ciudad.upper()}:<br>{titular}"
        sesion = _sesion(cfg.get("sesion"))
        paso(f"concepto: {concepto.clave} · modo: {modo} · formato: {cfg['formato']} · sesion: {sesion.name}")

        if modo == "split":
            izq, der = cfg["split_izq"], cfg["split_der"]
            par = a9_prompts.SPLIT[cfg["comparativa"]]
            chip_izq = next((p.chip for p in par if p.clave.endswith("-mal")), "")
            chip_der = next((p.chip for p in par if p.clave.endswith("-bien")), "")
            paso(f"comparativa: {cfg['comparativa']} · {izq} / {der}")
            arte = Arte(
                titular=titular,
                producto=cfg["nombre"],
                escena=cfg.get("escena", "navy"),
                formato=cfg["formato"],
                sello=cfg.get("sello", ""),
                split=(sesion / izq, chip_izq, sesion / der, chip_der),
            )
        elif modo in ("chat", "comparativa"):
            # Los dos moldes de puro texto: no llevan foto ni recorte, asi que
            # se saltan rembg entero (son ~1,5s en vez de ~40s). El titular y el
            # kicker salen del guion elegido salvo que Jose los pise a mano.
            if modo == "chat":
                guion = a8_conceptos.CHATS[cfg.get("guion", "tienda")]
                extra = {"chat": guion["mensajes"]}
            else:
                guion = a8_conceptos.COMPARATIVAS_FILAS[cfg.get("guion", "tablet")]
                extra = {"filas": guion["filas"],
                         "filas_titulos": tuple(guion["titulos"])}
            paso(f"guion: {cfg.get('guion')} · sin foto (molde de solo texto)")
            arte = Arte(
                titular=(titular if cfg.get("titular")
                         else (f"{ciudad.upper()}:<br>{guion['titular']}"
                               if ciudad else guion["titular"])),
                producto=cfg["nombre"],
                escena=cfg.get("escena", "navy"),
                formato=cfg["formato"],
                sello=cfg.get("sello", ""),
                kicker=cfg.get("kicker") or guion["kicker"],
                bloque_top=float(cfg.get("bloque_top") or 23),
                **extra,
            )
        else:
            paso(f"foto: {cfg['foto']}")
            origen = FOTOS_AMAZON / cfg["foto"]

            # Si el producto ya viene compuesto en la imagen (agy la genero a
            # partir de la foto real como referencia, ver a9_prompts.
            # generar_imagen_producto_ia), NO se compone el recorte local
            # encima -- eso duplicaria el producto. Confirmado 2026-08-03: agy
            # preserva el diseno y la pantalla mucho mejor que Qwen, asi que
            # esta via se salta rembg por completo.
            producto_en_imagen = bool(cfg.get("producto_en_imagen"))
            recorte = None
            if not producto_en_imagen:
                recorte = sesion / "recorte.png"
                if not recorte.exists():
                    paso("recortando el fondo (rembg isnet-general-use)...")
                    recortar(origen, recorte)
                else:
                    paso("recorte ya existente, se reusa")

            foto_fondo = None
            if cfg.get("foto_gemini"):
                foto_gemini_path = sesion / Path(cfg["foto_gemini"]).name
                if foto_gemini_path.exists():
                    paso(f"usando fondo generado: {foto_gemini_path.name}"
                         + (" (con el producto ya compuesto)" if producto_en_imagen else ""))
                    foto_fondo = foto_gemini_path
                else:
                    paso(f"aviso: fondo {cfg['foto_gemini']} no encontrado en la sesion, se usa fondo por defecto")
            elif cfg.get("qwen_escena"):
                foto_fondo = _escena_qwen(tid, cfg, concepto, origen, paso)

            alto_p, y_p, x_p = _colocacion(cfg["formato"], modo)
            arte = Arte(
                titular=titular,
                producto=cfg["nombre"],
                escena=cfg["escena"],
                foto_fondo=foto_fondo,
                recorte=recorte,
                recorte_alto=alto_p,
                recorte_y=y_p,
                recorte_x=x_p,
                formato=cfg["formato"],
                sello=cfg.get("sello", ""),
                fichas=(a8_conceptos.FICHAS.get(cfg["producto"], [])
                        if modo == "fichas" else []),
                fichas_vidrio=bool(cfg.get("vidrio")),
                dolores=(a8_conceptos.DOLORES[:min(int(cfg.get("n_dolores", 3)),
                                                     len(a8_conceptos.DOLORES))]
                         if modo == "dolores" else []),
                # Oferta apilada. El precio lo escribe Jose en el panel y NO
                # tiene default: precios-y-margenes.md avisa que cambian seguido,
                # asi que un numero quemado en el codigo se publicaria viejo.
                kicker=cfg.get("kicker", ""),
                precio=cfg.get("precio", "") if modo == "precio" else "",
                moneda=cfg.get("moneda", "Bs"),
                incluye=a8_conceptos.INCLUYE if modo == "precio" else [],
                bloque_top=float(cfg.get("bloque_top") or 23),
            )

        nombre = f"{cfg['producto']}-{concepto.clave}-{modo}.jpg"
        paso("renderizando (Chrome headless, 2x y bajado con LANCZOS)...")
        destino = render(arte, sesion / nombre)

        # Bug corregido 2026-08-01: antes se llamaba siempre con PAPERWHITE sin
        # importar el producto elegido — publicaba el copy equivocado. Ahora,
        # si el producto todavia no tiene copy verificado (caso del accesorio
        # kobo-stylus, ver a3_copy.PRODUCTOS), se avisa en el log en vez de
        # tirar el arte ya renderizado a la basura.
        #
        # Pedido de Jose 2026-08-04: el copy automatico (este bloque, corre en
        # TODOS los modos/pestanas) usaba siempre la plantilla fija
        # (a3_copy.variantes) sin ningun dato de ESTE arte puntual -- salia
        # identico sin importar la idea. Ahora se le pasa el titular (limpio
        # de HTML) como "ocasion" a agy via generar_con_ia(), igual que ya
        # hacia el boton manual "Generar variante con IA" del panel clasico.
        # Si agy/Codex fallan los dos, cae a la plantilla fija CON la misma
        # ocasion (variantes() tambien acepta ese parametro) en vez de dejar
        # el arte sin copy.
        copys = None
        try:
            p_copy = a3_copy.por_clave(cfg["producto"])
            ocasion = re.sub(r"<br\s*/?>", " ", titular, flags=re.I)
            ocasion = re.sub(r"<[^>]+>", "", ocasion)
            ocasion = re.sub(r"\s+", " ", ocasion).strip()
            try:
                paso("generando las 3 variantes de copy con agy (segun la idea de este arte)...")
                copys, _cid = a3_copy.generar_con_ia(p_copy, ocasion=ocasion)
            except Exception as e:
                paso(f"agy/Codex no generaron el copy ({e}) — uso la plantilla fija con la misma idea")
                try:
                    copys = a3_copy.variantes(p_copy, ocasion=ocasion)
                except Exception as e2:
                    paso(f"tampoco pudo la plantilla fija ({e2}) — el arte se generó sin copy")
                    copys = None
            if copys is not None:
                (sesion / f"{destino.stem}.copys.json").write_text(
                    json.dumps(copys, ensure_ascii=False), encoding="utf-8"
                )
        except KeyError as e:
            paso(f"sin copy verificado para este producto ({e}) — el arte se generó igual")

        _ficha(destino, cfg, copys, concepto=concepto.clave, modo=modo,
               titular=titular, origen="panel-clasico")

        TRABAJOS[tid].update(estado="listo", arte=destino.name, sesion=sesion.name, copys=copys)
        paso(f"LISTO: {destino.name}")
    except Exception:
        TRABAJOS[tid]["estado"] = "error"
        log.append("ERROR:\n" + traceback.format_exc())


def _generar_editorial(tid: str, cfg: dict) -> None:
    """El segundo sistema visual (a13_editorial), ahora si conectado al panel.

    Hasta hoy `a13_editorial.py` estaba entero y funcionando pero NO lo importaba
    nadie: solo se podia correr desde codigo. Es el estilo que Jose armo con
    Claude en la web (papel claro, tipografia enorme, una idea por slide) y que
    le rindio mas que sus carruseles con fotos.

    El guion no lo escribe una IA de pago: lo escribe Claude Code en el chat y
    Jose lo pega como JSON. Cuesta cero cuota y son ~1,3s por slide. Ver la
    regla de entrega en la memoria `claude-code-integracion-artes`: dos bloques
    pegables, nunca un parrafo mezclado.
    """
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        sesion = _sesion(cfg.get("sesion"))
        formato = cfg.get("formato", "cuadrado")
        crudas = cfg.get("slides") or []
        if not crudas:
            raise ValueError("no llegó ninguna slide en el guion")
        paso(f"editorial: {len(crudas)} slides · formato: {formato}")

        # La foto real aparece UNA sola vez en el sistema editorial, como prueba
        # — no en todas las slides. Se prepara solo si alguna la pide.
        foto_lista = None
        if any(s.get("tipo") == "foto" for s in crudas) and cfg.get("foto"):
            foto_lista = sesion / "editorial-foto.jpg"
            paso(f"preparando la foto real para el molde 'foto': {cfg['foto']}")
            a13_editorial.preparar_foto(
                FOTOS_AMAZON / cfg["foto"], foto_lista, formato=formato,
                # A mano y no automatico: la deteccion de la franja en ingles de
                # Amazon falla cuando el texto va sobre la foto misma.
                recorte_top=float(cfg.get("recorte_top") or 0.0),
            )

        slides = []
        for s in crudas:
            items = s.get("items") or []
            # `grilla` y `antes` esperan pares; el JSON los trae como listas.
            if s.get("tipo") in ("grilla", "antes"):
                items = [tuple(it) if isinstance(it, list) else it for it in items]
            slides.append(a13_editorial.Slide(
                tipo=s.get("tipo", "texto"),
                kicker=s.get("kicker", ""),
                titular=s.get("titular", ""),
                bajada=s.get("bajada", ""),
                items=items,
                foto=foto_lista if s.get("tipo") == "foto" else None,
                contacto=[tuple(c) for c in (s.get("contacto") or [])],
                invertida=bool(s.get("invertida")),
            ))

        paso("renderizando (Chrome headless, ~1,3s por slide)...")
        rutas = a13_editorial.render_carrusel(
            slides, sesion, prefijo="editorial", formato=formato)
        nombres = [r.name for r in rutas]
        for r in rutas:
            _ficha(r, cfg, None, modo="editorial", origen="editorial")

        copys = None
        try:
            copys = a3_copy.variantes(a3_copy.por_clave(cfg["producto"]))
        except KeyError as e:
            paso(f"sin copy verificado para este producto ({e})")

        TRABAJOS[tid].update(estado="listo", artes=nombres, sesion=sesion.name,
                             copys=copys)
        paso(f"LISTO: {len(nombres)} slides en {sesion.name}")
    except Exception:
        TRABAJOS[tid]["estado"] = "error"
        log.append("ERROR:\n" + traceback.format_exc())


def _generar_tanda(tid: str, cfg: dict) -> None:
    """N artes del mismo producto que NO se parecen entre si.

    Por que existe (2026-08-10): el algoritmo de Meta desde octubre de 2025
    (Andromeda) lee la creatividad en vez de la audiencia, y **fusiona en una
    sola entidad los anuncios que se parecen mas del 60%**, haciendolos competir
    entre ellos en vez de ampliar alcance. O sea que subir seis veces el mismo
    molde con otro titular no sirve de nada.

    Por eso la rotacion es estructural, no cosmetica: cambia el MOLDE (limpio,
    chat, comparativa, fichas), el fondo, el sello y las palancas de confianza,
    todo desde `a4_variacion.para(i)` — que hasta hoy no tenia ningun llamador
    vivo en el repo (su unico usuario, `tanda.py`, estaba roto desde que los
    sellos cambiaron de formato).

    Es determinista: la tanda numero i siempre da lo mismo. Si una pieza gusta,
    se puede reproducir.
    """
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        n = max(2, min(int(cfg.get("n", 6)), 12))
        sesion = _sesion(cfg.get("sesion"))
        formato = cfg.get("formato", "cuadrado")
        ciudad = (cfg.get("ciudad") or "").strip()
        paso(f"tanda de {n} · producto: {cfg['producto']} · formato: {formato}"
             + (f" · ciudad: {ciudad}" if ciudad else ""))

        # Los conceptos rotan igual que todo lo demas. Se saca "libre", que es
        # el comodin de la pestana Antigravity y tiene titular vacio.
        conceptos = [c for c in a8_conceptos.CONCEPTOS if c.clave != "libre"]
        claves_chat = list(a8_conceptos.CHATS)
        claves_comp = list(a8_conceptos.COMPARATIVAS_FILAS)

        # El recorte se hace UNA vez para toda la tanda: es lo unico caro (rembg
        # sobre GPU, ~40s). Los moldes de solo texto ni lo tocan.
        recorte = None
        artes: list[str] = []

        for i in range(n):
            v = a4_variacion.para(i)
            modo = v.modo
            paso(f"[{i+1}/{n}] molde={modo} fondo={v.escena} sello={v.sello or '—'}")

            if modo == "chat":
                g = a8_conceptos.CHATS[claves_chat[i % len(claves_chat)]]
                arte = Arte(
                    titular=g["titular"], producto=cfg["nombre"],
                    escena=v.escena, formato=formato, sello=v.sello,
                    kicker=g["kicker"], chat=g["mensajes"],
                )
            elif modo == "comparativa":
                g = a8_conceptos.COMPARATIVAS_FILAS[claves_comp[i % len(claves_comp)]]
                arte = Arte(
                    titular=g["titular"], producto=cfg["nombre"],
                    escena=v.escena, formato=formato, sello=v.sello,
                    kicker=g["kicker"], filas=g["filas"],
                    filas_titulos=tuple(g["titulos"]),
                )
            else:
                if recorte is None:
                    recorte = sesion / "recorte.png"
                    if not recorte.exists():
                        paso("recortando el fondo (rembg) — una sola vez para toda la tanda")
                        recortar(FOTOS_AMAZON / cfg["foto"], recorte)
                c = conceptos[i % len(conceptos)]
                titular = c.titular
                if ciudad:
                    titular = f"{ciudad.upper()}:<br>{titular}"
                alto_p, y_p, x_p = _colocacion(formato, modo)
                arte = Arte(
                    titular=titular, producto=cfg["nombre"],
                    escena=v.escena, formato=formato, sello=v.sello,
                    recorte=recorte, recorte_alto=alto_p,
                    recorte_y=y_p if v.confianza else y_p + 3, recorte_x=x_p,
                    confianza=v.confianza,
                    fichas=(a8_conceptos.FICHAS.get(cfg["producto"], [])
                            if modo == "fichas" else []),
                )

            destino = render(arte, sesion / f"tanda-{i+1:02d}-{modo}.jpg")
            _ficha(destino, cfg, None, modo=modo, escena=v.escena,
                   sello=v.sello, indice=i, origen="tanda")
            artes.append(destino.name)

        # El copy se genera UNA vez para la tanda entera: es del producto, no de
        # cada pieza, y llamar a agy seis veces gastaria cuota sin necesidad.
        copys = None
        try:
            copys = a3_copy.variantes(a3_copy.por_clave(cfg["producto"]))
        except KeyError as e:
            paso(f"sin copy verificado para este producto ({e})")

        TRABAJOS[tid].update(estado="listo", artes=artes, sesion=sesion.name,
                             copys=copys)
        paso(f"LISTO: {len(artes)} artes en {sesion.name}")
    except Exception:
        TRABAJOS[tid]["estado"] = "error"
        log.append("ERROR:\n" + traceback.format_exc())


def _generar_carrusel(tid: str, cfg: dict) -> None:
    """Carrusel de TikTok (2026-08-04): N slides que cuentan una historia, no
    N artes sueltos. Pestaña nueva, endpoint nuevo -- no comparte codigo con
    _generar() mas que Arte/render()/a3_copy, para no arriesgar el modo de
    siempre.

    cfg["slides"] es una lista de {"titular", "prompt"?, "foto_gemini"?} en
    orden. Si cfg["generar_imagenes"] es true, cada slide se genera con la
    persona elegida como referencia y, en el modo "usar nuestras fotos",
    tambien con la foto real del producto. No se reenvia el fondo de la slide
    anterior: con Codex eso producia casi la misma foto una y otra vez en lugar
    de una historia que avance. Si es false (modo esqueleto), cada slide usa el
    archivo ya subido con /api/subir-imagen-directa.

    cfg["fuente_producto"] es el selector "¿De donde sale el e-reader?" del
    panel: "nuestras" (default) adjunta la foto real para que el modelo ponga
    ESE equipo; "ia" no adjunta nada y el modelo inventa el aparato. El que lo
    UBICA en la escena es el modelo en los dos casos -- aca NO se compone
    ningun recorte encima. Se probo el 2026-08-05 y se descarto: `Arte.recorte`
    pega en porcentajes fijos (recorte_x/recorte_y) sin saber donde quedo el
    hueco de la escena, asi que el aparato caia sobre la persona o los muebles.
    Pedido de Jose: "tenemos que pasarle nuestra foto de referencia al modelo
    agy y que el la coloque en su foto".

    Solo la ULTIMA slide lleva el CTA de WhatsApp (pie_whatsapp=True); todas
    van con el pie un poco mas chico que el arte suelto (pie_escala=0.85) --
    ver Arte en a1_marca.py.
    """
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        producto_clave = cfg["producto"]
        # Cuadrado siempre -- Jose probo vertical (9:16) en carrusel y no
        # queda bien en ninguna red social (2026-08-04).
        formato = cfg.get("formato", "cuadrado")
        slides_cfg = cfg["slides"]
        n = len(slides_cfg)
        if n < 1:
            raise RuntimeError("el carrusel no tiene slides")
        sesion = _sesion(cfg.get("sesion"))
        generar_imagenes = bool(cfg.get("generar_imagenes"))
        fuente_producto = cfg.get("fuente_producto", "nuestras")
        usar_foto_real = fuente_producto != "ia"
        proveedor = cfg.get("proveedor", "agy")
        foto_producto = None
        if cfg.get("foto"):
            candidato = FOTOS_AMAZON / cfg["foto"]
            if candidato.exists():
                foto_producto = candidato
        persona_foto = a9_prompts.ruta_persona(cfg.get("persona", ""))
        nombre_imprimir = cfg.get("nombre", "")

        paso(f"carrusel: {n} slides · producto: {producto_clave} · formato: {formato}")
        if usar_foto_real:
            if not foto_producto and generar_imagenes:
                raise RuntimeError(
                    "elegí la foto real del producto: es la referencia que se le "
                    "adjunta al modelo para que coloque NUESTRO equipo en la escena"
                )
            paso("el e-reader sale de nuestra foto, adjunta como referencia en cada slide")
        else:
            paso("el e-reader lo inventa el modelo (sin foto nuestra de referencia)")

        archivos = []
        for i, s in enumerate(slides_cfg):
            titular = s.get("titular", "")
            es_ultima = (i == n - 1)

            if generar_imagenes:
                paso(f"slide {i + 1}/{n}: generando fondo con {proveedor}...")
                # La foto del producto viaja SOLO en el modo "nuestras": es lo
                # que hace que el aparato de la escena sea el que vendemos y no
                # uno inventado. En el modo "ia" no se manda a proposito.
                referencias = [p for p in (foto_producto if usar_foto_real else None,
                                            persona_foto) if p]
                destino_fondo = sesion / f"carrusel-fondo-{i + 1}.png"
                _generar_imagen(proveedor, s.get("prompt", ""), destino_fondo,
                                 referencias=referencias or None)
                foto_fondo = destino_fondo
            else:
                nombre_subido = s.get("foto_gemini", "")
                foto_fondo = sesion / Path(nombre_subido).name if nombre_subido else None
                if not foto_fondo or not foto_fondo.exists():
                    raise RuntimeError(f"slide {i + 1}: no se encontro la imagen subida")

            arte = Arte(
                titular=titular,
                producto=nombre_imprimir,
                foto_fondo=foto_fondo,
                # Sin recorte a proposito: el aparato ya viene dentro del fondo,
                # puesto por el modelo. Ver el docstring.
                recorte=None,
                formato=formato,
                pie_whatsapp=es_ultima,
                # 0.85 y no 0.6 (2026-08-05): a 0.6 el logo no se leia -- Jose
                # lo marco mirando una slide terminada. Agrandarlo no le come
                # nada a la foto: la instruccion del guion ya reserva el 15%
                # inferior y el pie a 0.85 ocupa 12.75%. A 1.0 (el pie del arte
                # suelto) el logo pesa demasiado repetido en 6-8 slides.
                pie_escala=0.85,
            )
            nombre_archivo = f"{producto_clave}-carrusel-{i + 1}.jpg"
            paso(f"slide {i + 1}/{n}: renderizando...")
            destino = render(arte, sesion / nombre_archivo)
            archivos.append(destino.name)

        # El copy es del POST completo, no por slide -- una sola llamada, con
        # los titulares de todas las slides como contexto de la historia.
        copys = None
        try:
            p_copy = a3_copy.por_clave(producto_clave)
            resumen = " / ".join(
                re.sub(r"<[^>]+>", "", s.get("titular", "")).strip() for s in slides_cfg
            )
            try:
                paso("generando el copy del post con agy (segun la historia completa)...")
                copys, _cid = a3_copy.generar_con_ia(p_copy, ocasion=resumen)
            except Exception as e:
                paso(f"agy/Codex no generaron el copy ({e}) — uso la plantilla fija")
                try:
                    copys = a3_copy.variantes(p_copy, ocasion=resumen)
                except Exception as e2:
                    paso(f"tampoco pudo la plantilla fija ({e2}) — el carrusel se generó sin copy")
                    copys = None
            if copys is not None:
                (sesion / "carrusel.copys.json").write_text(
                    json.dumps(copys, ensure_ascii=False), encoding="utf-8"
                )
        except KeyError as e:
            paso(f"sin copy verificado para este producto ({e}) — el carrusel se generó igual")

        TRABAJOS[tid].update(estado="listo", slides=archivos, sesion=sesion.name, copys=copys)
        paso(f"LISTO: {n} slides")
    except Exception:
        TRABAJOS[tid]["estado"] = "error"
        log.append("ERROR:\n" + traceback.format_exc())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencia el log de acceso
        pass

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _bytes(self, datos: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _miniatura_archivo(self, f: Path):
        from PIL import Image
        if not f.exists():
            return self._json({"error": "no existe"}, 404)
        with Image.open(f) as im:
            im = im.convert("RGB")
            im.thumbnail((260, 260), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
        return self._bytes(buf.getvalue(), "image/jpeg")

    def _miniatura_de(self, carpeta: Path, q: dict):
        return self._miniatura_archivo(carpeta / Path(q["f"][0]).name)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path in ("/", "/PANEL-ARTES.html"):
            return self._bytes(PANEL.read_bytes(), "text/html; charset=utf-8")

        if u.path == "/api/estado":
            return self._json({
                "ok": True,
                "productos": _productos(),
                "conceptos": [
                    {"clave": c.clave, "titular": c.titular, "modo": c.modo,
                     "nota": c.nota}
                    for c in a8_conceptos.CONCEPTOS
                ],
                "escenas": list(ESCENAS),
                "formatos": list(FORMATOS),
                "confianza": a8_conceptos.CONFIANZA,
                "chats": {k: {"kicker": v["kicker"], "titular": v["titular"],
                              "n": len(v["mensajes"])}
                          for k, v in a8_conceptos.CHATS.items()},
                "comparativas_filas": {
                    k: {"kicker": v["kicker"], "titular": v["titular"],
                        "n": len(v["filas"])}
                    for k, v in a8_conceptos.COMPARATIVAS_FILAS.items()},
                "incluye": a8_conceptos.INCLUYE,
                "n_dolores_max": len(a8_conceptos.DOLORES),
                "prompts": {k: [vars(p) for p in v]
                            for k, v in a9_prompts.SPLIT.items()},
                "personas": a9_prompts.listar_personas(),
                "agy": a11_agy.disponible(),
                "codex": a12_codex.disponible(),
                "proveedores_imagen": _proveedores_imagen(),
            })

        if u.path == "/api/miniatura":
            return self._miniatura_de(FOTOS_AMAZON, q)

        if u.path == "/api/miniatura-persona":
            f = a9_prompts.ruta_persona(q.get("clave", [""])[0])
            if not f:
                return self._json({"error": "no existe"}, 404)
            return self._miniatura_archivo(f)

        if u.path == "/api/subir-miniatura":
            return self._miniatura_de(_sesion(q.get("sesion", [""])[0]), q)

        if u.path == "/api/subir-fotos":
            return self._json({"fotos": _fotos_en(_sesion(q.get("sesion", [""])[0]))})

        if u.path == "/api/abrir-subir":
            carpeta = _sesion(q.get("sesion", [""])[0])
            try:
                os.startfile(carpeta)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/abrir-foto-base":
            f = q.get("f", [""])[0]
            ruta = FOTOS_AMAZON / f if f else FOTOS_AMAZON
            target = ruta if ruta.exists() else FOTOS_AMAZON
            try:
                if target.is_file():
                    os.system(f'start "" explorer.exe /select,"{target}"')
                else:
                    os.startfile(target)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/abrir-arte-explorer":
            # Selecciona el arte final en el Explorador -- un arrastre y ya
            # esta sobre el selector de archivos de Meta Business Suite o
            # TikTok Studio, que se abren aparte en /api/abrir-arte-explorer
            # no hace publicar de verdad (eso pide token/API, ver decision
            # 2026-08-03 de ir por "preparar y abrir" en vez de integracion).
            carpeta = _sesion(q.get("sesion", [""])[0])
            target = carpeta / Path(q.get("f", [""])[0]).name
            try:
                if target.exists():
                    os.system(f'start "" explorer.exe /select,"{target}"')
                else:
                    os.startfile(carpeta)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/comfy":
            return self._json({"vivo": a10_comfy.vivo(), "vram": a10_comfy.vram()})

        if u.path == "/api/arte":
            f = _sesion(q.get("sesion", [""])[0]) / Path(q["f"][0]).name
            if not f.exists():
                return self._json({"error": "no existe"}, 404)
            return self._bytes(f.read_bytes(), "image/jpeg")

        if u.path == "/api/historial":
            # El arte final vive mezclado con los candidatos dentro de cada
            # carpeta de sesion bajo TRABAJO -- se filtra por convencion de
            # nombre: los candidatos siempre arrancan con "fondo-", el arte
            # final nunca (ver _generar/_qwen_generar_ia/api endpoints).
            # "subir" se excluye a mano: es la carpeta del esquema VIEJO
            # (antes de la reorganizacion por sesion, 2026-08-03) -- sus
            # archivos sueltos (agy-*.jpg sin el prefijo "fondo-" de antes)
            # no son arte final, y esa carpeta no se borra sola.
            candidatos = [f for f in TRABAJO.glob("*/*.jpg")
                          if not f.name.startswith("fondo-") and f.parent.name != "subir"]
            items = []
            for f in sorted(candidatos, key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
                sidecar = f.parent / f"{f.stem}.copys.json"
                items.append({
                    "arte": f.name,
                    "sesion": f.parent.name,
                    "tiene_copy": sidecar.exists(),
                })
            return self._json({"items": items})

        if u.path == "/api/historial-copys":
            carpeta = _sesion(q.get("sesion", [""])[0])
            f = carpeta / Path(q["f"][0]).name
            sidecar = carpeta / f"{f.stem}.copys.json"
            if not sidecar.exists():
                return self._json({"copys": None})
            return self._json({"copys": json.loads(sidecar.read_text(encoding="utf-8"))})

        # Las fichas de todos los artes generados, para la revision automatica:
        # Claude Code las pide, las cruza contra la cuenta de Meta con el
        # conector y devuelve los numeros por /api/ficha-resultado.
        if u.path == "/api/fichas":
            solo_sin = q.get("sin_resultados", ["0"])[0] == "1"
            fichas = _indice_fichas()
            if solo_sin:
                fichas = [f for f in fichas
                          if not (f.get("resultados") or {}).get("publicado")]
            return self._json({"fichas": fichas})

        if u.path == "/api/trabajo":
            t = TRABAJOS.get(q["id"][0])
            return self._json(t or {"estado": "desconocido"})

        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)

        if u.path == "/api/comfy/encender":
            avisos: list[str] = []
            ok = a10_comfy.arrancar(avisar=avisos.append)
            return self._json({"ok": ok, "log": avisos, "vram": a10_comfy.vram()})

        if u.path == "/api/comfy/apagar":
            avisos: list[str] = []
            a10_comfy.apagar(avisar=avisos.append)
            return self._json({"ok": True, "log": avisos})

        # Escribe los numeros de Meta dentro de la ficha de un arte. Lo llama
        # Claude Code despues de leer la cuenta con el conector; el panel no
        # habla con Meta.
        if u.path == "/api/ficha-resultado":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            carpeta = _sesion(cfg.get("sesion"))
            ficha = carpeta / (Path(cfg["arte"]).stem + ".ficha.json")
            if not ficha.exists():
                return self._json({"ok": False, "error": "no existe la ficha"}, 404)
            datos = json.loads(ficha.read_text(encoding="utf-8-sig"))
            datos.setdefault("resultados", {}).update(cfg.get("resultados", {}))
            ficha.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                             encoding="utf-8")
            return self._json({"ok": True, "resultados": datos["resultados"]})

        if u.path == "/api/prompt-ia":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            try:
                prompt, cid = a9_prompts.generar_prompt_ia(
                    cfg.get("nombre", ""), cfg.get("titular", ""),
                    cfg.get("escena_base", ""), cfg.get("formato", "cuadrado"),
                    correccion=cfg.get("correccion", ""),
                    conversation_id=cfg.get("conversation_id"),
                    persona=cfg.get("persona", ""),
                    proveedor=cfg.get("proveedor", "agy"),
                )
                return self._json({"ok": True, "prompt": prompt, "conversation_id": cid,
                                    "proveedor": _proveedor_de(cid)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/imagen-ia":
            # Trabajo async (ver _imagen_ia) -- agy puede tardar bastante mas
            # de lo esperado en una correccion, y sin polling parecia colgado.
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            tid = f"t{len(TRABAJOS) + 1}"
            TRABAJOS[tid] = {"estado": "corriendo", "log": []}
            threading.Thread(target=_imagen_ia, args=(tid, cfg), daemon=True).start()
            return self._json({"id": tid})

        if u.path == "/api/titular-ia":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            idea = cfg.get("idea", "").strip()
            # idea puede venir vacia SI es una correccion sobre una conversacion
            # ya arrancada (el contexto ya lo tiene agy) -- igual que copy-ia
            # y prompt-ia.
            es_correccion = bool(cfg.get("correccion") and cfg.get("conversation_id"))
            if not idea and not es_correccion:
                return self._json({"ok": False, "error": "escribi la idea libre primero"}, 400)
            try:
                titular, cid = a9_prompts.generar_titular_ia(
                    idea, correccion=cfg.get("correccion", ""),
                    conversation_id=cfg.get("conversation_id"),
                )
                return self._json({"ok": True, "titular": titular, "conversation_id": cid,
                                    "proveedor": _proveedor_de(cid)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        # Tanda: N artes que no se parecen entre si (ver _generar_tanda).
        if u.path == "/api/tanda":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            if not cfg.get("foto"):
                return self._json({"ok": False, "error": "elegí una foto base primero"}, 400)
            tid = f"t{len(TRABAJOS) + 1}"
            TRABAJOS[tid] = {"estado": "corriendo", "log": []}
            threading.Thread(target=_generar_tanda, args=(tid, cfg), daemon=True).start()
            return self._json({"id": tid})

        # Editorial: el guion lo escribe Claude Code y llega pegado como JSON.
        if u.path == "/api/editorial":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            if not cfg.get("slides"):
                return self._json({"ok": False, "error": "pegá el guion primero"}, 400)
            tid = f"t{len(TRABAJOS) + 1}"
            TRABAJOS[tid] = {"estado": "corriendo", "log": []}
            threading.Thread(target=_generar_editorial, args=(tid, cfg), daemon=True).start()
            return self._json({"id": tid})

        if u.path == "/api/prompt-producto-ia":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            correccion = cfg.get("correccion", "")
            es_correccion = bool(correccion and cfg.get("conversation_id"))
            if not cfg.get("escena_base") and not es_correccion:
                return self._json({"ok": False, "error": "escribi la idea libre primero"}, 400)
            try:
                prompt, cid = a9_prompts.generar_prompt_producto_ia(
                    cfg.get("titular", ""), cfg.get("escena_base", ""),
                    cfg.get("formato", "cuadrado"),
                    correccion=correccion,
                    conversation_id=cfg.get("conversation_id"),
                    persona=cfg.get("persona", ""),
                )
                return self._json({"ok": True, "prompt": prompt, "conversation_id": cid,
                                    "proveedor": _proveedor_de(cid)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/imagen-producto-ia":
            # Trabajo async (ver _imagen_producto_ia) -- mismo motivo que
            # /api/imagen-ia: una correccion puede tardar bastante mas que
            # los ~15-40s de una generacion nueva.
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            if not cfg.get("foto"):
                return self._json({"ok": False, "error": "elegi una foto base primero"}, 400)
            tid = f"t{len(TRABAJOS) + 1}"
            TRABAJOS[tid] = {"estado": "corriendo", "log": []}
            threading.Thread(target=_imagen_producto_ia, args=(tid, cfg), daemon=True).start()
            return self._json({"id": tid})

        if u.path == "/api/subir-imagen-directa":
            # Modo "Solo esqueleto": la imagen de fondo NO la genera ningun
            # proveedor, la trae Jose ya hecha (ej. bajada de Google Flow) --
            # se guarda tal cual en la sesion y de ahi la usa /api/generar
            # como foto_gemini + producto_en_imagen=true, mismo mecanismo que
            # ya usan las otras pestanas para saltear el recorte local.
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            datos = cfg.get("datos_base64", "")
            if not datos:
                return self._json({"ok": False, "error": "no llego ninguna imagen"}, 400)
            ext = Path(cfg.get("nombre", "")).suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            # Nanosegundos, no segundos: el carrusel sube varias fotos seguidas
            # y con resolucion de 1s dos subidas en el mismo segundo se
            # pisaban el nombre entre si.
            destino_nombre = f"subida-{time.time_ns()}{ext}"
            try:
                crudos = base64.b64decode(datos.split(",", 1)[-1])
                (_sesion(cfg.get("sesion")) / destino_nombre).write_bytes(crudos)
                return self._json({"ok": True, "archivo": destino_nombre})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/qwen-generar-ia":
            # Trabajo async (ver _qwen_generar_ia) -- el navegador hace
            # polling a /api/trabajo?id=... igual que "Generar arte", en vez
            # de esperar 2-4 min con una sola llamada sincrona sin feedback.
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            tid = f"t{len(TRABAJOS) + 1}"
            TRABAJOS[tid] = {"estado": "corriendo", "log": []}
            threading.Thread(target=_qwen_generar_ia, args=(tid, cfg), daemon=True).start()
            return self._json({"id": tid})

        if u.path == "/api/copy-ia":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            try:
                p = a3_copy.por_clave(cfg["producto"])
                copys, cid = a3_copy.generar_con_ia(
                    p, ocasion=cfg.get("ocasion", ""),
                    correccion=cfg.get("correccion", ""),
                    conversation_id=cfg.get("conversation_id"),
                )
                return self._json({"ok": True, "copys": copys, "conversation_id": cid,
                                    "proveedor": _proveedor_de(cid)})
            except KeyError as e:
                return self._json({"ok": False, "error": f"sin copy verificado para este producto ({e})"}, 400)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/carrusel-guion-ia":
            # Texto barato (agy o Codex) -- arma las n slides (titular corto +
            # prompt en ingles) de una historia completa en un solo llamado,
            # para revisar/corregir antes de gastar imagenes. Usado por el
            # modo "con una idea" del carrusel Y por el sub-modo "con una
            # idea" del modo esqueleto del carrusel (ese solo necesita el
            # texto, no genera imagenes).
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            try:
                slides, cid = a9_prompts.generar_guion_carrusel_ia(
                    cfg.get("nombre", ""), cfg.get("idea", ""),
                    int(cfg.get("n", 6)), cfg.get("formato", "cuadrado"),
                    correccion=cfg.get("correccion", ""),
                    conversation_id=cfg.get("conversation_id"),
                    persona=cfg.get("persona", ""),
                    # El panel manda las dos desde 2026-08-05: `proveedor` es
                    # el selector "Generar guion con" (antes se ignoraba y
                    # siempre salia por agy) y `fuente_producto` es el selector
                    # "¿De donde sale el e-reader?".
                    proveedor=cfg.get("proveedor", "agy"),
                    fuente_producto=cfg.get("fuente_producto", "nuestras"),
                )
                return self._json({"ok": True, "slides": slides, "conversation_id": cid,
                                    "proveedor": _proveedor_de(cid)})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/carrusel-generar":
            # Trabajo async (ver _generar_carrusel) -- con imagenes
            # encadenadas puede tardar varios minutos (n slides x ~15-40s
            # cada una), necesita polling igual que /api/imagen-producto-ia.
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n).decode("utf-8"))
            if not cfg.get("slides"):
                return self._json({"ok": False, "error": "el carrusel no tiene slides"}, 400)
            tid = f"t{len(TRABAJOS) + 1}"
            TRABAJOS[tid] = {"estado": "corriendo", "log": []}
            threading.Thread(target=_generar_carrusel, args=(tid, cfg), daemon=True).start()
            return self._json({"id": tid})

        if u.path != "/api/generar":
            return self.send_error(404)
        n = int(self.headers.get("Content-Length", 0))
        cfg = json.loads(self.rfile.read(n).decode("utf-8"))
        tid = f"t{len(TRABAJOS) + 1}"
        TRABAJOS[tid] = {"estado": "corriendo", "log": []}
        threading.Thread(target=_generar, args=(tid, cfg), daemon=True).start()
        return self._json({"id": tid})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8791)
    ap.add_argument("--sin-abrir", action="store_true")
    a = ap.parse_args()

    TRABAJO.mkdir(parents=True, exist_ok=True)

    s = ThreadingHTTPServer(("127.0.0.1", a.puerto), Handler)
    url = f"http://127.0.0.1:{a.puerto}/"
    print(f"Panel de artes en {url}  (Ctrl+C para salir)")
    if not a.sin_abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        print("\ncerrado")


if __name__ == "__main__":
    main()
