"""
Lanzador rápido del editor visual v2: abre la corrida más reciente sin tener
que acordarse de la carpeta ni escribir el comando completo.

Uso:
    python abrir_editor.py                  # la corrida más reciente
    python abrir_editor.py <nombre-o-ruta>  # una corrida concreta
"""
import sys
from pathlib import Path

import config


def _corrida_mas_reciente() -> Path | None:
    if not config.DIR_SALIDA.is_dir():
        return None
    candidatas = [d for d in config.DIR_SALIDA.iterdir()
                  if d.is_dir() and (d / "02_cortado.mp4").exists()]
    if not candidatas:
        return None
    return max(candidatas, key=lambda d: d.stat().st_mtime)


def main():
    # Sin argumentos (el caso del acceso directo, doble clic): elige la
    # corrida más reciente sola. Con argumentos, se los pasa tal cual a
    # f11_servidor.py — ya sabe resolver la ruta y sus propias banderas
    # (--puerto, --sin-abrir).
    args = sys.argv[1:]
    if not args:
        ruta = _corrida_mas_reciente()
        if ruta is None:
            print(f"No hay ninguna corrida en {config.DIR_SALIDA}", file=sys.stderr)
            input("Presioná Enter para cerrar...")
            sys.exit(1)
        print(f"Abriendo la corrida más reciente: {ruta.name}")
        args = [str(ruta)]

    import f11_servidor
    sys.argv = ["f11_servidor.py", *args]
    try:
        f11_servidor.main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        input("Presioná Enter para cerrar...")
        sys.exit(1)


if __name__ == "__main__":
    main()
