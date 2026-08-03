import sys, re
sys.path.insert(0, '.')
import panel_servidor as ps

fuente = ps.leer_panel()
ini, fin = ps._bloque_guion(fuente, 7)
bloque = fuente[ini:fin]

m_tl = re.search(r"tl:\[\r?\n([\s\S]*?)\]\]", bloque)
if m_tl:
    lineas = m_tl.group(1).splitlines()
    print("MATCH TL OK! Lineas:", len(lineas))
    for k, l in enumerate(lineas):
        campos = ps._campos(l)
        if len(campos) >= 2:
            print(f"  Beat {k:2d}: {repr(ps._desescapar(l[campos[1][0]:campos[1][1]]))[:60]}")
else:
    print("NO MATCH TL!")
