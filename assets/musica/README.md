# Música de fondo — Librería Comercial (~50 Pistas)

## ⚠️ Licencia y Uso Comercial

Todas las pistas de la librería (`assets/musica/`) utilizan la **Pixabay Content License / Open Music License**:
- **Uso Comercial Gratuito**: Permitido para redes sociales (TikTok, Instagram Reels, YouTube Shorts, anuncios).
- **Sin atribución obligatoria**.
- **Sin reclamos de Content ID**: Selección de pistas limpias para evitar silenciamientos o copyright strikes.

El listado completo con enlaces, duración, etiquetas de ánimo (`mood`) y caso de uso recomendado se encuentra en:
- `assets/musica/pistas.json` (metadatos consumidos dinámicamente por el editor visual).
- `assets/musica/LIBRERIA-RECOMENDADA.md` (guía humana categorizada en 8 estilos).

## 8 Categorías de Ánimo (Moods)

1. **Comercial / Enérgica**: Lanzamientos, ofertas relámpago, productos estrella.
2. **Lo-Fi / Relajada**: Demos de uso continuo, reviews tranquilos, comparativas.
3. **Corporate / Funky / Pop**: Unboxing dinámicos, consejos de compra, noticias.
4. **Inspiring / Uplifting**: Historias de clientes, reseñas de cámaras y fotografía.
5. **Tech / Futurista / Cyber**: Celulares gamer, sintetizadores, flagships, pruebas de rendimiento.
6. **Hip-Hop / Urban / Groove**: Contenido joven, tendencias rápidas, clips picados.
7. **Acústica / Orgánica / Folk**: Reviews sinceros, opiniones honestas, empaque ecológico.
8. **Cinemática / Dramática / Suspenso**: Ganchos de curiosidad ("El error que cometes al comprar...").

## Regla de Mezcla

Todas las pistas se mezclan en el pipeline mediante `f5_audio.py` con **ducking automático** (`sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300`). La voz del presentador siempre atenúa la música para garantizar Inteligibilidad 100%.
