"""Iconos de contorno para la lista de fichas tecnicas.

A diferencia de los sellos (a5_sellos), aca el icono mide ~90 px de lado y el
trazo SI funciona: es el estilo que Jose ya usa en su arte del Paperwhite 32GB.
La regla del trazo macizo aplica solo a los sellos, que son mucho mas chicos.

Todos comparten viewBox 0 0 32 32 y heredan color por `currentColor`, para que
el mismo icono sirva sobre fondo claro (navy) y oscuro (turquesa).
"""
from __future__ import annotations

_A = ('<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" '
      'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">')

ICONOS = {
    # Pantalla sin reflejos: un panel con rayos, no un sol suelto.
    "pantalla": _A + (
        '<rect x="7" y="4" width="18" height="24" rx="2.5"/>'
        '<circle cx="16" cy="16" r="4"/>'
        '<path d="M16 8.5v1.6M16 21.9v1.6M10.7 16h1.6M19.7 16h1.6"/>'
        '<path d="M12.2 12.2l1.1 1.1M18.7 18.7l1.1 1.1M19.8 12.2l-1.1 1.1M13.3 18.7l-1.1 1.1"/>'
    ) + "</svg>",

    "agua": _A + (
        '<path d="M16 3.5c5 6 8.5 9.8 8.5 14a8.5 8.5 0 0 1-17 0c0-4.2 3.5-8 8.5-14z"/>'
        '<path d="M11.5 18.5a4.5 4.5 0 0 0 4.5 4.5"/>'
    ) + "</svg>",

    "bateria": _A + (
        '<rect x="3" y="10" width="22" height="12" rx="2.5"/>'
        '<path d="M28 14v4"/>'
        '<rect x="6" y="13" width="4" height="6" rx="1" fill="currentColor" stroke="none"/>'
        '<rect x="11.5" y="13" width="4" height="6" rx="1" fill="currentColor" stroke="none"/>'
        '<rect x="17" y="13" width="4" height="6" rx="1" fill="currentColor" stroke="none"/>'
    ) + "</svg>",

    # Almacenamiento: pila de discos. El icono del arte viejo (una hoja con
    # lineas) se leia como "documento", no como "capacidad".
    "memoria": _A + (
        '<ellipse cx="16" cy="8" rx="10" ry="4"/>'
        '<path d="M6 8v8c0 2.2 4.5 4 10 4s10-1.8 10-4V8"/>'
        '<path d="M6 16v8c0 2.2 4.5 4 10 4s10-1.8 10-4v-8"/>'
    ) + "</svg>",

    "luz": _A + (
        '<path d="M20.5 4.5A9.5 9.5 0 1 0 27 18a7.6 7.6 0 0 1-6.5-13.5z"/>'
        '<path d="M8 6.5V9M4 11h2.5M11.4 8.4 9.6 6.6"/>'
    ) + "</svg>",

    "lapiz": _A + (
        '<path d="M21.5 4.5l6 6L12 26l-7.5 1.5L6 20z"/>'
        '<path d="M18.5 7.5l6 6"/>'
    ) + "</svg>",

    "color": _A + (
        '<path d="M16 27a11 11 0 1 1 11-11c0 3-2.5 3.5-4.5 3.5h-2a2.8 2.8 0 0 0-2 4.8A2.6 2.6 0 0 1 16 27z"/>'
        '<circle cx="10.5" cy="14" r="1.6" fill="currentColor" stroke="none"/>'
        '<circle cx="16" cy="9.5" r="1.6" fill="currentColor" stroke="none"/>'
        '<circle cx="21.5" cy="13" r="1.6" fill="currentColor" stroke="none"/>'
    ) + "</svg>",

    "peso": _A + (
        '<path d="M16 5v22"/>'
        '<path d="M6 11h20"/>'
        '<path d="M11 11 7 20h8z"/>'
        '<path d="M21 11l-4 9h8z"/>'
        '<path d="M12 27h8"/>'
    ) + "</svg>",

    "libros": _A + (
        '<path d="M16 9.5S13 6.5 5 6.5v16c8 0 11 3 11 3s3-3 11-3v-16c-8 0-11 3-11 3z"/>'
        '<path d="M16 9.5v16"/>'
    ) + "</svg>",
}


def html(clave: str) -> str:
    return ICONOS.get(clave, "")
