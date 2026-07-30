/* Editor de silencios — ver y deshacer lo que recortó f2_cortar.py (Bloque B).
 *
 * Vive en su propio archivo, servido por GET /silencios.js, en vez de dentro
 * del <script> de PAGINA: f11_servidor.py ya son 3500 líneas de Python con
 * HTML y JavaScript entretejidos, y un conflicto de merge dentro del texto de
 * un <script> produce Python válido con JS roto — los tests, que son de
 * Python, pasarían igual en verde.
 *
 * LA ESCALA DE ESTA PISTA ES LA GRABACIÓN ORIGINAL, no el video que se está
 * viendo. Es la diferencia que hace que el bloque funcione: los tramos
 * cortados no existen en la línea de tiempo del video, así que dibujarlos
 * sobre ella obligaría a inventar una posición. Sobre la grabación entera cada
 * tramo cae donde de verdad está.
 *
 * Se apoya en `DATA` (del script inline, mismo scope global) y no modifica
 * ninguna de sus funciones.
 */
(function () {
  "use strict";

  const CSS = `
  #panelSilencios .sil-fila { display:flex; align-items:center; gap:10px; padding:6px 8px;
    border-bottom:1px solid var(--linea); font-size:13px; }
  #panelSilencios .sil-fila:last-child { border-bottom:0; }
  #panelSilencios .sil-fila.restaurado { opacity:.62; }
  #panelSilencios .sil-fila label { display:flex; align-items:center; gap:7px; cursor:pointer;
    min-width:200px; }
  #panelSilencios .sil-dur { font-variant-numeric:tabular-nums; color:var(--fg-2);
    min-width:118px; }
  #panelSilencios .sil-razon { color:var(--fg-2); flex:1; overflow:hidden;
    text-overflow:ellipsis; white-space:nowrap; }
  #panelSilencios .sil-tipo { font-size:11px; padding:1px 7px; border-radius:99px;
    background:var(--acento-suave); color:var(--acento); white-space:nowrap; }
  #panelSilencios .sil-tipo.muletilla { background:rgba(230,180,40,.18); color:#e6b428; }
  #panelSilencios .sil-tipo.toma-repetida { background:rgba(217,79,140,.18); color:#d94f8c; }
  #panelSilencios .sil-corte { position:absolute; top:6px; height:34px; border-radius:5px;
    background:rgba(224,70,70,.42); border:1px solid #e04646; box-sizing:border-box; }
  #panelSilencios .sil-corte.restaurado { background:rgba(120,120,120,.20);
    border-style:dashed; border-color:var(--fg-2); }
  #panelSilencios .sil-corte.sel { box-shadow:0 0 0 2px var(--acento); }
  #panelSilencios .sil-corte .enc-tirador { cursor:ew-resize; }
  #panelSilencios .sil-aviso { font-size:12px; padding:6px 9px; border-radius:6px;
    background:rgba(230,180,40,.14); border:1px solid rgba(230,180,40,.4);
    color:#e6b428; margin-bottom:5px; }
  #panelSilencios .sil-vacio { color:var(--fg-2); font-size:13px; padding:8px 0; }
  `;

  let cat = null;             // el catálogo que llegó del servidor
  let estados = {};           // id -> {activo, inicio, fin} (solo lo que difiere)
  let seleccionado = null;

  const $ = (id) => document.getElementById(id);

  function inyectarCss() {
    if (document.getElementById("silenciosCss")) return;
    const s = document.createElement("style");
    s.id = "silenciosCss";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function estadoDe(id) {
    if (!estados[id]) estados[id] = {};
    return estados[id];
  }

  function tramoPorId(id) {
    return (cat.tramos || []).find((t) => t.id === id) || null;
  }

  /* --- guardado ---------------------------------------------------------- */

  async function guardar() {
    const limpio = {};
    for (const [id, e] of Object.entries(estados)) {
      const entrada = {};
      if (e.activo === false) entrada.activo = false;
      if (e.inicio !== undefined && e.inicio !== null) entrada.inicio = e.inicio;
      if (e.fin !== undefined && e.fin !== null) entrada.fin = e.fin;
      if (Object.keys(entrada).length) limpio[id] = entrada;
    }
    try {
      const r = await fetch("/guardar-silencios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cortes: limpio }),
      });
      const res = await r.json();
      // El servidor devuelve el catálogo recalculado: los segundos que el video
      // va a durar los cuenta Python, no el navegador, para que la cuenta que
      // se lee en pantalla sea la misma que va a aplicar el render.
      if (res && res.silencios) {
        cat = res.silencios;
        pintar();
      }
    } catch (e) {
      console.error("no se pudo guardar los silencios", e);
    }
  }

  /* --- pintado ----------------------------------------------------------- */

  function pintarResumen() {
    const r = cat.resumen || {};
    const dur = cat.duracion_original_s || 0;
    const restante = Math.max(0, dur - (r.segundos_cortados || 0));
    $("silResumen").textContent =
      `${r.total} tramo(s) · se cortan ${r.cortados} (${(r.segundos_cortados || 0).toFixed(1)}s)` +
      (r.restaurados ? ` · ${r.restaurados} devuelto(s) al video (+${(r.segundos_restaurados || 0).toFixed(1)}s)` : "") +
      ` · grabación ${dur.toFixed(1)}s → video ${restante.toFixed(1)}s`;

    const pend = $("silPendiente");
    if (cat.pendiente_de_render) {
      pend.textContent = "⚠ hay cambios sin aplicar: hay que volver a renderizar para verlos "
        + "(se rehace el corte, no la transcripción)";
      pend.style.color = "#e6b428";
    } else {
      pend.textContent = "el video en pantalla ya refleja estos cortes";
      pend.style.color = "";
    }
  }

  function pintarAvisoFuente() {
    const el = $("silAvisoFuente");
    if (cat.fuente_existe) { el.style.display = "none"; return; }
    el.style.display = "";
    el.textContent = "No se encuentra la grabación original (" + (cat.fuente || "?")
      + "). Sin ella no se puede devolver ningún tramo al video: el metraje cortado "
      + "no está en el archivo ya montado. Los tramos se ven, pero no se pueden restaurar.";
  }

  function pintarAvisosRemapeo() {
    const cont = $("silAvisosRemapeo");
    const avisos = cat.avisos_remapeo || [];
    const huerfanos = cat.huerfanos || [];
    if (!avisos.length && !huerfanos.length) {
      cont.style.display = "none"; cont.innerHTML = ""; return;
    }
    cont.style.display = "";
    cont.innerHTML = "";

    if (huerfanos.length) {
      // El corte cambió de parámetros (otro `hooksegs`, otro presentador) y
      // estas elecciones ya no encajan con ningún tramo. Callarlo seria dejar
      // que un silencio devuelto al video volviera a desaparecer sin motivo.
      const d = document.createElement("div");
      d.className = "sil-aviso";
      d.textContent = `${huerfanos.length} elección(es) guardada(s) ya no corresponden a `
        + `ningún tramo de esta corrida (${huerfanos.join(", ")}). Cambiaron los `
        + `parámetros del corte, así que esos tramos han vuelto al comportamiento `
        + `automático. Volvé a elegirlos si los querías.`;
      cont.appendChild(d);
    }
    if (!avisos.length) return;

    const cab = document.createElement("p");
    cab.className = "hint";
    cab.style.marginBottom = "5px";
    cab.textContent = `Del último re-corte quedaron ${avisos.length} ajuste(s) que no se `
      + `pudieron trasladar con certeza. Están puestos donde mejor encajaban; revisalos:`;
    cont.appendChild(cab);
    for (const a of avisos) {
      const d = document.createElement("div");
      d.className = "sil-aviso";
      const que = a.etiqueta ? `${a.etiqueta} — ` : "";
      d.textContent = `${a.archivo.replace("ajustes.", "").replace(".json", "")}: ${que}${a.detalle}`;
      cont.appendChild(d);
    }
  }

  function pintarPista() {
    const franjas = $("franjasSilencios");
    franjas.innerHTML = "";
    const dur = cat.duracion_original_s || 0;
    if (!dur) return;

    for (const t of cat.tramos) {
      const d = document.createElement("div");
      d.className = "sil-corte" + (t.activo ? "" : " restaurado")
        + (seleccionado === t.id ? " sel" : "");
      d.style.left = (100 * t.inicio / dur) + "%";
      d.style.width = Math.max(0.35, 100 * (t.fin - t.inicio) / dur) + "%";
      d.title = `${t.razon}\n${t.inicio.toFixed(2)}s a ${t.fin.toFixed(2)}s de la grabación`
        + `\n${t.activo ? "se corta" : "se devuelve al video"}`;
      d.dataset.id = t.id;
      if (t.ajustable && t.activo && cat.fuente_existe) {
        for (const lado of ["izq", "der"]) {
          const tir = document.createElement("div");
          tir.className = "enc-tirador " + lado;
          tir.dataset.lado = lado;
          tir.dataset.id = t.id;
          d.appendChild(tir);
        }
      }
      franjas.appendChild(d);
    }
  }

  function pintarLista() {
    const cont = $("silLista");
    cont.innerHTML = "";
    if (!cat.tramos.length) {
      cont.innerHTML = '<p class="sil-vacio">El corte automático no quitó nada de esta '
        + "grabación: no hay silencios largos, muletillas ni tomas repetidas que deshacer.</p>";
      return;
    }
    for (const t of cat.tramos) {
      const fila = document.createElement("div");
      fila.className = "sil-fila" + (t.activo ? "" : " restaurado");

      const lab = document.createElement("label");
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.checked = t.activo;
      chk.disabled = !cat.fuente_existe;
      chk.addEventListener("change", () => {
        const e = estadoDe(t.id);
        if (chk.checked) delete e.activo; else e.activo = false;
        guardar();
      });
      lab.appendChild(chk);
      const tipo = document.createElement("span");
      tipo.className = "sil-tipo " + t.tipo;
      tipo.textContent = t.tipo;
      lab.appendChild(tipo);
      fila.appendChild(lab);

      const dur = document.createElement("span");
      dur.className = "sil-dur";
      dur.textContent = `${t.inicio.toFixed(2)}–${t.fin.toFixed(2)}s (${t.duracion.toFixed(2)}s)`;
      fila.appendChild(dur);

      const razon = document.createElement("span");
      razon.className = "sil-razon";
      razon.textContent = t.razon + (t.activo ? "" : "  ·  se devuelve al video");
      fila.appendChild(razon);

      fila.addEventListener("click", (ev) => {
        if (ev.target.tagName === "INPUT") return;
        seleccionado = seleccionado === t.id ? null : t.id;
        pintar();
      });
      cont.appendChild(fila);
    }
  }

  function pintar() {
    if (!cat || !cat.disponible) return;
    pintarResumen();
    pintarAvisoFuente();
    pintarAvisosRemapeo();
    pintarPista();
    pintarLista();
  }

  /* --- tiradores --------------------------------------------------------- */

  function arrastrar(ev) {
    const tir = ev.target.closest(".enc-tirador");
    if (!tir) return;
    ev.preventDefault();
    ev.stopPropagation();
    const id = tir.dataset.id;
    const lado = tir.dataset.lado;
    const t = tramoPorId(id);
    if (!t) return;
    const pista = $("pistaSilencios");
    const dur = cat.duracion_original_s || 0;
    seleccionado = id;

    function mover(e) {
      const caja = pista.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (e.clientX - caja.left) / caja.width));
      let seg = frac * dur;
      const est = estadoDe(id);
      if (lado === "izq") {
        // No se puede cortar MÁS de lo que el detector propuso: el tope
        // izquierdo es el principio del silencio, no el del video. Cortar más
        // sería empezar a llevarse habla, y este bloque existe para lo
        // contrario. El otro tope es el borde derecho del propio tramo.
        seg = Math.max(t.limite_inicio, Math.min(seg, t.fin - 0.05));
        est.inicio = Math.round(seg * 1000) / 1000;
        t.inicio = est.inicio;
      } else {
        seg = Math.min(t.limite_fin, Math.max(seg, t.inicio + 0.05));
        est.fin = Math.round(seg * 1000) / 1000;
        t.fin = est.fin;
      }
      t.duracion = Math.round((t.fin - t.inicio) * 1000) / 1000;
      pintarPista();
      pintarLista();
    }
    function soltar() {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
      guardar();
    }
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
  }

  /* --- arranque ---------------------------------------------------------- */

  function init(data) {
    inyectarCss();
    const panel = $("panelSilencios");
    if (!panel) return;
    cat = (data && data.silencios) || null;

    if (!cat || !cat.disponible) {
      // Sin 01_transcripcion.json no hay catálogo posible. Se dice, en vez de
      // dejar un panel vacío que parezca un fallo de carga.
      panel.style.display = "";
      $("silResumen").textContent = "";
      $("silLista").innerHTML = '<p class="sil-vacio">No se puede leer el corte de esta '
        + "corrida (" + ((cat && cat.motivo) || "faltan los archivos de la fase 1")
        + "). Se necesita una corrida completa para poder deshacer sus cortes.</p>";
      return;
    }

    estados = {};
    for (const t of cat.tramos) {
      const e = {};
      if (!t.activo) e.activo = false;
      if (Math.abs(t.inicio - t.inicio_detectado) > 1e-6) e.inicio = t.inicio;
      if (Math.abs(t.fin - t.fin_detectado) > 1e-6) e.fin = t.fin;
      if (Object.keys(e).length) estados[t.id] = e;
    }

    const pista = $("pistaSilencios");
    if (!pista.dataset.enganchado) {
      pista.dataset.enganchado = "1";
      pista.addEventListener("pointerdown", arrastrar);
    }
    const btn = $("btnResetSilencios");
    if (btn && !btn.dataset.enganchado) {
      btn.dataset.enganchado = "1";
      btn.addEventListener("click", () => {
        estados = {};
        seleccionado = null;
        guardar();
      });
    }
    pintar();
  }

  window.__silencios = { init: init };

  // cargar() puede haber terminado antes de que este archivo llegue: su
  // llamada a __silencios.init() se habría perdido y el panel quedaría vacío
  // sin ningún error visible.
  if (typeof DATA !== "undefined" && DATA) init(DATA);
})();
