"""
Lanzador de la pantalla de preparación (Fase 0) y, detrás, del pipeline.

El recorrido completo de hacer un video sin escribir nada:

    doble clic en «Preparar grabación.bat»
      -> se abre la pantalla en el navegador
      -> elegir clips, recortar, ordenar, elegir guion
      -> «Empezar»
      -> la pantalla se apaga y ESTE script llama a editor.py en la MISMA
         terminal, así el progreso se ve donde se hizo doble clic
      -> al terminar se abre solo el editor visual, como en cualquier corrida

Uso:
    python preparar.py                  # la pantalla
    python preparar.py --sin-abrir      # sin abrir el navegador (para probar)
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f0_servidor_preparar

AQUI = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description="Pantalla de preparación + pipeline")
    ap.add_argument("--puerto", type=int, default=8790)
    ap.add_argument("--sin-abrir", action="store_true",
                    help="No abrir el navegador solo (la URL se imprime igual)")
    ap.add_argument("--solo-preparar", action="store_true",
                    help="Guardar la preparación y NO lanzar el pipeline. Deja el "
                         "comando impreso para lanzarlo a mano o desde un agente")
    args = ap.parse_args()

    try:
        orden = f0_servidor_preparar.main(args.puerto, not args.sin_abrir)
    except Exception:
        import traceback
        traceback.print_exc()
        input("Presioná Enter para cerrar...")
        sys.exit(1)

    if not orden:
        print("No se pidió arrancar nada.")
        return 0

    # Al pipeline se le pasa el PRIMER clip nada más: el resto (los demás clips,
    # el orden y los recortes) viaja en el .preparado.json que la pantalla acaba
    # de dejar al lado del archivo. Así el mismo comando, copiado y pegado más
    # tarde, reproduce exactamente esta preparación.
    cmd = [sys.executable, "editor.py", orden["clips"][0]]
    if orden.get("guion"):
        cmd += ["--guion", str(orden["guion"])]
    if orden.get("nombre"):
        cmd += ["--nombre", orden["nombre"]]

    legible = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd[1:])
    print(f"\n{'=' * 70}\nArrancando el pipeline\n{'=' * 70}")
    print(f"  python {legible}")
    print(f"  (preparación: {orden['preparado']})\n")

    if args.solo_preparar:
        print("--solo-preparar: no se lanza nada.")
        return 0

    return subprocess.run(cmd, cwd=str(AQUI)).returncode


if __name__ == "__main__":
    sys.exit(main())
