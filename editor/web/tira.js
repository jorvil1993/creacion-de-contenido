/* Tira de capas apiladas del editor visual — bloques A y C.
 *
 * Módulo aparte, cargado con <script src="/tira.js"> como última línea del
 * <body>. Vive en su propio archivo y no en el <script> inline de
 * f11_servidor.py por la misma razón que la pantalla de preparación: ese
 * archivo son 160 KB de servidor + HTML + JS mezclados, y un conflicto de
 * merge dentro del texto del JavaScript produce Python válido con JS roto —
 * los tests son de Python, pasan en verde, y el editor se rompe solo en el
 * navegador.
 *
 * Todo el estado que dibuja (DATA, edicionPip, edicionSfx, edicionAnimaciones,
 * edicionMusicaPista…) son variables `let` del <script> inline anterior. Un
 * segundo script clásico comparte ese ámbito, así que se leen por nombre; cada
 * acceso va envuelto para que la desaparición de cualquiera de ellas apague la
 * tira en vez de tirar la página entera.
 */
(function () {
  "use strict";

  var iniciado = false;
  var T = null;              // DATA.tira
  var dur = 0;
  var zoom = 1;
  var imanActivo = true;
  var imanElegido = false;   // true en cuanto se toca la casilla: cambiar de
                             // corrida no puede volver a encender el imán que
                             // se acaba de apagar a mano
  var arrastre = null;       // {tipo, obj} mientras se arrastra algo
  var huella = "";
  var ultimaHuella = 0;
  var ultimoCursor = -1;

  // -- acceso defensivo al estado del editor -------------------------------
  function leer(fn, porDefecto) {
    try {
      var v = fn();
      return (v === undefined || v === null) ? porDefecto : v;
    } catch (e) {
      return porDefecto;
    }
  }
  function datos() { return leer(function () { return DATA; }, null); }
  function pips() { return leer(function () { return edicionPip; }, []); }
  function sfx() { return leer(function () { return edicionSfx; }, []); }
  function anims() { return leer(function () { return edicionAnimaciones; }, []); }
  function elVideo() { return leer(function () { return video; }, null); }
  function llamar(nombre, fn) { try { fn(); } catch (e) { console.warn("tira: " + nombre, e); } }

  // -- escala de tiempo ----------------------------------------------------
  function el(id) { return document.getElementById(id); }
  function anchoLienzoPx() {
    var l = el("tiraLienzo");
    return l ? l.getBoundingClientRect().width : 0;
  }
  function segPorPx() {
    var w = anchoLienzoPx();
    return w > 0 ? dur / w : 0;
  }
  function pct(t) { return dur > 0 ? (t / dur) * 100 : 0; }

  /** Tiempo bajo un evento de puntero, en el espacio del lienzo (con zoom). */
  function tiempoEn(ev) {
    var l = el("tiraLienzo");
    if (!l || dur <= 0) return 0;
    var r = l.getBoundingClientRect();
    var t = ((ev.clientX - r.left) / r.width) * dur;
    return Math.max(0, Math.min(dur, t));
  }

  // -- imán (bloque C) -----------------------------------------------------
  /* Devuelve {t, tipo, referencia}: el instante al que se pega el marcador y a
   * qué se pegó. La tolerancia se mide EN PANTALLA y se convierte a segundos
   * con el zoom actual, así que ampliar afina la ayuda sola en vez de seguir
   * imantando a medio segundo cuando ya se ve el fotograma. */
  function imantar(t, sinIman) {
    var libre = { t: Math.round(t * 1000) / 1000, tipo: null, referencia: null };
    if (sinIman || !imanActivo || !T) return libre;
    var tol = (T.iman.tolerancia_px || 8) * segPorPx();
    if (!(tol > 0)) return libre;

    var mejor = null;
    function mirar(lista, tipo) {
      if (!lista) return;
      for (var i = 0; i < lista.length; i++) {
        var d = Math.abs(lista[i] - t);
        if (d > tol) continue;
        // A igual distancia gana el beat: es una decisión editorial explícita
        // del guion, mientras que un borde de palabra es solo dónde calló
        // Whisper. Mismo criterio que la prioridad de los SFX del panel.
        if (!mejor || d < mejor.d - 1e-9 || (Math.abs(d - mejor.d) <= 1e-9 && tipo === "beat")) {
          mejor = { d: d, t: lista[i], tipo: tipo };
        }
      }
    }
    mirar(T.imanes && T.imanes.palabras, "palabra");
    mirar(T.imanes && T.imanes.beats, "beat");
    if (!mejor) return libre;
    return { t: mejor.t, tipo: mejor.tipo, referencia: mejor.t };
  }

  function mostrarGuia(res) {
    var g = el("tiraGuia");
    if (!g) return;
    if (!res || !res.tipo) { g.className = "tira-guia"; return; }
    g.className = "tira-guia visible " + res.tipo;
    g.style.left = pct(res.t) + "%";
  }

  function avisar(txt) {
    var a = el("tiraAviso");
    if (a) a.textContent = txt || "";
  }

  // -- construcción de la tira --------------------------------------------
  function construirArmazon() {
    var cont = el("tiraCapas");
    if (!cont) return false;
    var etiquetas = T.carriles.map(function (c) {
      return '<div class="et' + (c.editable ? " editable" : "") + '" data-carril="' + c.id + '">' +
        '<span class="punto" data-punto="' + c.id + '"></span>' + c.etiqueta + "</div>";
    }).join("");
    var carriles = T.carriles.map(function (c) {
      return '<div class="tira-carril" data-carril="' + c.id + '"></div>';
    }).join("");

    cont.innerHTML =
      '<div class="tira-panel">' +
      '<h2>Tira de capas</h2>' +
      '<div class="tira-barra">' +
        '<div class="grupo">' +
          '<button type="button" id="tiraZoomMenos" title="Alejar">−</button>' +
          '<span class="zoom-valor" id="tiraZoomValor">1.0x</span>' +
          '<button type="button" id="tiraZoomMas" title="Acercar">+</button>' +
          '<button type="button" id="tiraZoomTodo" title="Ver el video entero">Todo</button>' +
        '</div>' +
        '<div class="grupo">' +
          '<label title="Pega los marcadores a los bordes de palabra y a los beats del guion">' +
            '<input type="checkbox" id="tiraIman"> Imán</label>' +
          '<span class="tira-aviso" id="tiraAviso"></span>' +
        '</div>' +
      '</div>' +
      '<div class="tira-cuerpo">' +
        '<div class="tira-etiquetas">' +
          '<div class="hueco"></div>' + etiquetas +
        '</div>' +
        '<div class="tira-scroll" id="tiraScroll">' +
          '<div class="tira-lienzo" id="tiraLienzo">' +
            '<div class="tira-regla" id="tiraRegla"></div>' +
            carriles +
            '<div class="tira-guia" id="tiraGuia"></div>' +
            '<div class="tira-cursor" id="tiraCursor"></div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<p class="tira-leyenda">Clic en cualquier carril para llevar la aguja ahí. ' +
      '<span class="clave">Ctrl + rueda</span> acerca y aleja; los tres carriles de en medio ' +
      '(B-Roll/PiP, animaciones y SFX) se arrastran. Con el imán puesto se pegan a los bordes ' +
      'de palabra y a los beats del guion — <span class="clave">Alt</span> mientras arrastrás ' +
      'lo suelta sin tener que destildar la casilla.</p>' +
      '</div>';

    // Los puntos de color de las etiquetas los pinta el CSS por clase; aquí
    // solo se les cuelga la clase del bloque que representan.
    var mapaPunto = { voz: "voz", subtitulos: "subtitulo", broll: "broll", anim: "anim", sfx: "", musica: "musica" };
    Array.prototype.forEach.call(cont.querySelectorAll("[data-punto]"), function (p) {
      var clase = mapaPunto[p.getAttribute("data-punto")];
      p.className = "punto tira-bloque " + (clase || "");
      if (p.getAttribute("data-punto") === "sfx") p.style.background = "var(--acento)";
    });

    var chk = el("tiraIman");
    if (chk) {
      chk.checked = imanActivo;
      chk.addEventListener("change", function () {
        imanActivo = chk.checked;
        imanElegido = true;
      });
    }
    el("tiraZoomMas").addEventListener("click", function () { zoomCentrado(T.zoom.factor); });
    el("tiraZoomMenos").addEventListener("click", function () { zoomCentrado(1 / T.zoom.factor); });
    el("tiraZoomTodo").addEventListener("click", function () { fijarZoom(1); el("tiraScroll").scrollLeft = 0; });

    var scroll = el("tiraScroll");
    scroll.addEventListener("wheel", function (ev) {
      if (!ev.ctrlKey) return;   // sin Ctrl la rueda sigue desplazando la página
      ev.preventDefault();
      var r = scroll.getBoundingClientRect();
      zoomAnclado(ev.deltaY < 0 ? T.zoom.factor : 1 / T.zoom.factor, ev.clientX - r.left);
    }, { passive: false });

    // Clic en la regla o en un carril: llevar la aguja ahí. Se pone en el
    // lienzo entero y se descarta si el clic vino de un bloque arrastrable,
    // igual que hacen las pistas viejas con .enc-cerrado / .marca-sfx.
    el("tiraLienzo").addEventListener("click", function (ev) {
      if (ev.target.closest(".tira-bloque.arrastrable") || ev.target.closest(".tira-marca-sfx")) return;
      var v = elVideo();
      if (v) v.currentTime = tiempoEn(ev);
    });
    return true;
  }

  function fijarZoom(z) {
    zoom = Math.max(T.zoom.min, Math.min(T.zoom.max, z));
    var l = el("tiraLienzo");
    if (l) l.style.width = (zoom * 100) + "%";
    var v = el("tiraZoomValor");
    if (v) v.textContent = zoom.toFixed(1) + "x";
    pintarRegla();
  }

  /** Acerca manteniendo quieto el instante que está bajo `xVista` (px desde el
   *  borde izquierdo de la ventana de scroll). Sin esto, acercar sobre el
   *  segundo 20 saltaba al principio del video y había que volver a buscarlo. */
  function zoomAnclado(factor, xVista) {
    var scroll = el("tiraScroll");
    if (!scroll || dur <= 0) return;
    var anchoAntes = anchoLienzoPx();
    if (!(anchoAntes > 0)) return;
    var tAnclado = ((scroll.scrollLeft + xVista) / anchoAntes) * dur;
    fijarZoom(zoom * factor);
    var anchoDespues = anchoLienzoPx();
    scroll.scrollLeft = (tAnclado / dur) * anchoDespues - xVista;
  }

  function zoomCentrado(factor) {
    var scroll = el("tiraScroll");
    if (scroll) zoomAnclado(factor, scroll.clientWidth / 2);
  }

  /** Marcas de la regla: se elige el paso más chico de la escala que deje al
   *  menos 60px entre marcas, para que al acercar aparezcan décimas solas. */
  function pintarRegla() {
    var regla = el("tiraRegla");
    if (!regla || dur <= 0) return;
    var ancho = anchoLienzoPx();
    if (!(ancho > 0)) return;
    var pasos = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60];
    var paso = pasos[pasos.length - 1];
    for (var i = 0; i < pasos.length; i++) {
      if ((pasos[i] / dur) * ancho >= 60) { paso = pasos[i]; break; }
    }
    var html = "";
    for (var t = 0; t <= dur + 1e-6; t += paso) {
      var etiqueta = paso < 1 ? t.toFixed(1) : Math.round(t);
      html += '<div class="marca" style="left:' + pct(t) + '%"><span>' + etiqueta + 's</span></div>';
    }
    (T.beats || []).forEach(function (b) {
      html += '<div class="tira-beat" style="left:' + pct(b.t) + '%" title="' + escapar(b.etiqueta) + '"></div>';
    });
    regla.innerHTML = html;
  }

  function escapar(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function carril(id) { return document.querySelector('.tira-carril[data-carril="' + id + '"]'); }

  function bloque(clase, ini, fin, texto, titulo) {
    var d = document.createElement("div");
    d.className = "tira-bloque " + clase;
    d.style.left = pct(ini) + "%";
    d.style.width = Math.max(0.15, pct(fin - ini)) + "%";
    d.textContent = texto;
    d.title = titulo || texto;
    return d;
  }

  // -- carriles ------------------------------------------------------------
  function pintarVoz() {
    var c = carril("voz");
    var D = datos();
    if (!c || !D) return;
    c.innerHTML = "";
    (D.palabras || []).forEach(function (p) {
      c.appendChild(bloque("voz", p.t, p.fin, p.texto,
        p.texto + " · " + p.t.toFixed(2) + "s - " + p.fin.toFixed(2) + "s"));
    });
  }

  function pintarSubtitulos() {
    var c = carril("subtitulos");
    var D = datos();
    if (!c || !D) return;
    c.innerHTML = "";
    // El texto se muestra ya corregido: `sub_correcciones` se indexa por la
    // posición GLOBAL de la palabra, la misma clave que trae cada bloque desde
    // f14_tira.bloques_subtitulos() y la que usa f3_subtitulos.generar_ass().
    var corr = leer(function () { return subCorrecciones; }, D.sub_correcciones || {});
    (T.subtitulos || []).forEach(function (b) {
      var sueltas = b.palabras || [];
      var texto = b.indices.map(function (idx, j) {
        var c2 = corr[idx];
        return (c2 != null && c2 !== "") ? c2 : (sueltas[j] || "");
      }).join(" ").trim() || b.texto;
      c.appendChild(bloque("subtitulo", b.ini, b.fin, texto,
        texto + " · " + b.ini.toFixed(2) + "s - " + b.fin.toFixed(2) + "s"));
    });
  }

  function pintarBroll() {
    var c = carril("broll");
    if (!c) return;
    c.innerHTML = "";
    pips().forEach(function (ev) {
      var esVideo = ev.medio === "video" || ev.tipo === "broll";
      var nombre = ev.asset_id || (ev.archivo ? ev.archivo.split(/[\\/]/).pop() : "") || ev.tipo;
      var d = bloque(esVideo ? "broll" : "pip", ev.ini, ev.fin,
        (esVideo ? "B-Roll: " : "PiP: ") + nombre,
        nombre + " · " + ev.ini.toFixed(2) + "s - " + ev.fin.toFixed(2) + "s");
      d.classList.add("arrastrable");
      hacerArrastrable(d, "pip", ev);
      c.appendChild(d);
    });
  }

  function pintarAnims() {
    var c = carril("anim");
    if (!c) return;
    c.innerHTML = "";
    anims().forEach(function (a) {
      var d = bloque("anim", a.ini, a.fin, a.nombre,
        a.nombre + " · " + a.ini.toFixed(2) + "s - " + a.fin.toFixed(2) + "s");
      d.classList.add("arrastrable");
      hacerArrastrable(d, "anim", a);
      c.appendChild(d);
    });
  }

  function pintarSfxCarril() {
    var c = carril("sfx");
    if (!c) return;
    c.innerHTML = "";
    sfx().forEach(function (e) {
      var m = document.createElement("div");
      m.className = "tira-marca-sfx";
      m.style.left = pct(e.t) + "%";
      m.title = e.archivo + " · " + e.t.toFixed(2) + "s · " + e.razon;
      hacerArrastrable(m, "sfx", e);
      c.appendChild(m);
    });
  }

  function pintarMusica() {
    var c = carril("musica");
    var D = datos();
    if (!c || !D) return;
    c.innerHTML = "";
    // Los valores en vivo del panel de música mandan sobre los de /datos: si
    // se acaba de cambiar la pista, el carril tiene que decir la nueva.
    var apagada = leer(function () { return edicionSinMusica; }, D.sin_musica);
    var pista = leer(function () { return edicionMusicaPista; }, D.musica_pista) || "";
    var inicio = leer(function () { return edicionMusicaInicio; }, D.musica_inicio_s) || 0;
    var nombre = pista;
    (D.musica_catalogo || []).forEach(function (p) {
      if (p.archivo === pista) nombre = p.nombre || p.archivo;
    });
    var texto = apagada ? "sin música de fondo" : ("♪ " + nombre);
    var d = bloque("musica" + (apagada ? " apagada" : ""), 0, dur, texto,
      apagada ? "El render sale sin música de fondo"
              : (nombre + " · desde el segundo " + Number(inicio).toFixed(1) + " de la pista"));
    c.appendChild(d);
  }

  function pintarTodo() {
    if (!iniciado) return;
    pintarRegla();
    pintarVoz();
    pintarSubtitulos();
    pintarBroll();
    pintarAnims();
    pintarSfxCarril();
    pintarMusica();
    huella = huellaEstado();
  }

  // -- arrastre con imán (bloque C) ---------------------------------------
  /* Se mueve el bloque ENTERO, nunca sus bordes: estirar un B-Roll ya se hace
   * en su pista de siempre, que conoce `duracionMaximaClip(ev)` y frena en el
   * tramo elegido del clip. Moviéndolo entero la duración no cambia, así que
   * ese tope no se puede violar desde aquí. */
  function hacerArrastrable(elem, tipo, obj) {
    elem.addEventListener("pointerdown", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      try { elem.setPointerCapture(ev.pointerId); } catch (e) { /* seguimos sin captura */ }
      elem.classList.add("arrastrando");
      arrastre = { tipo: tipo, obj: obj };

      var t0 = tiempoEn(ev);
      var ini0 = (tipo === "sfx") ? obj.t : obj.ini;
      var largo = (tipo === "sfx") ? 0 : (obj.fin - obj.ini);

      var mover = function (mv) {
        var propuesto = ini0 + (tiempoEn(mv) - t0);
        propuesto = Math.max(0, Math.min(dur - largo, propuesto));
        var res = imantar(propuesto, mv.altKey);
        var t = Math.max(0, Math.min(dur - largo, res.t));
        aplicarMovimiento(tipo, obj, t, largo);
        elem.style.left = pct(tipo === "sfx" ? obj.t : obj.ini) + "%";
        mostrarGuia(res.tipo ? res : null);
        avisar(res.tipo === "palabra" ? "pegado a un borde de palabra"
             : res.tipo === "beat" ? "pegado a un beat del guion"
             : (mv.altKey ? "imán suelto (Alt)" : ""));
      };
      var soltar = function () {
        window.removeEventListener("pointermove", mover);
        window.removeEventListener("pointerup", soltar);
        elem.classList.remove("arrastrando");
        arrastre = null;
        mostrarGuia(null);
        avisar("");
        refrescarPaneles(tipo);
        pintarTodo();
      };
      window.addEventListener("pointermove", mover);
      window.addEventListener("pointerup", soltar);
    });
  }

  function aplicarMovimiento(tipo, obj, t, largo) {
    if (tipo === "sfx") {
      obj.t = t;
      try { sfxModificado = true; } catch (e) { /* sin flag no se guarda, pero no rompe */ }
    } else if (tipo === "anim") {
      // moverAnimacion() ya existe en el editor: hace el clamp con la duración
      // real del clip y marca animacionesModificado. Reusarla evita que la tira
      // y la pista de animaciones muevan las cosas de dos maneras distintas.
      var usada = false;
      try { moverAnimacion(obj, t); usada = true; } catch (e) { /* cae al camino manual */ }
      if (!usada) { obj.ini = t; obj.fin = t + largo; }
    } else {
      obj.ini = t;
      obj.fin = t + largo;
    }
  }

  /* Al soltar se avisa a las secciones de siempre. La tira NO sustituye a las
   * cinco pistas viejas (ver PLAN-TIRA.md): son ellas las que siguen mandando
   * en la edición fina, así que tienen que enterarse de lo que se movió aquí. */
  function refrescarPaneles(tipo) {
    if (tipo === "sfx") {
      llamar("pintarSfx", function () { pintarSfx(); });
      llamar("tablaSfx", function () { tablaSfx(); });
    } else if (tipo === "anim") {
      llamar("pintarAnimTimeline", function () { pintarAnimTimeline(); });
      llamar("renderAnimGrid", function () { renderAnimGrid(); });
    } else {
      llamar("renderPipsLista", function () { renderPipsLista(); });
      llamar("pintarPipTimeline", function () { pintarPipTimeline(); });
      llamar("construirTimeline", function () { construirTimeline(); });
    }
  }

  // -- sincronización con el resto del editor ------------------------------
  /* La tira no puede engancharse a los repintados de las otras secciones sin
   * modificar sus funciones, que es justo lo que este módulo no hace. En vez de
   * eso compara una huella barata del estado un par de veces por segundo: si
   * algo cambió en otro panel (se agregó un SFX, se cambió la pista de música,
   * se movió un B-Roll con su tirador), la tira se repinta sola. */
  function huellaEstado() {
    var partes = [];
    sfx().forEach(function (e) { partes.push("s" + e.t + e.archivo); });
    pips().forEach(function (e) { partes.push("p" + e.ini + "-" + e.fin + (e.asset_id || e.tipo)); });
    anims().forEach(function (a) { partes.push("a" + a.ini + a.nombre); });
    partes.push("m" + leer(function () { return edicionMusicaPista; }, "") +
                leer(function () { return edicionSinMusica; }, "") +
                leer(function () { return edicionMusicaInicio; }, ""));
    return partes.join("|");
  }

  // -- API pública ---------------------------------------------------------
  var API = {
    init: function (D) {
      D = D || datos();
      if (!D || !D.tira) return;
      T = D.tira;
      dur = D.duracion || 0;
      if (!T.carriles || !T.carriles.length || dur <= 0) return;
      if (!imanElegido) imanActivo = !(T.iman && T.iman.activo_defecto === false);
      if (!construirArmazon()) return;
      iniciado = true;
      zoom = 1;
      fijarZoom(1);
      pintarTodo();
      ultimoCursor = -1;
    },

    cursor: function (t) {
      // Arranque perezoso: cargar() es async y su última línea puede correr
      // antes de que este archivo llegue del servidor. loop() sí corre siempre
      // después, así que la tira se enciende aquí si todavía no lo hizo.
      if (!iniciado) {
        var D = datos();
        if (D && D.tira) API.init(D);
        if (!iniciado) return;
      }
      if (typeof t !== "number" || !isFinite(t)) return;

      if (t !== ultimoCursor) {
        ultimoCursor = t;
        var c = el("tiraCursor");
        if (c) c.style.left = pct(t) + "%";
        // Con zoom, el cursor se va de la vista enseguida. Se sigue solo
        // mientras el video corre: durante un arrastre o al mirar otro tramo
        // parado, mover el scroll bajo el ratón sería pelearse con el usuario.
        var v = elVideo();
        if (zoom > 1 && v && !v.paused && !arrastre) {
          var scroll = el("tiraScroll");
          if (scroll) {
            var x = (t / dur) * anchoLienzoPx();
            var margen = scroll.clientWidth * 0.15;
            if (x < scroll.scrollLeft + margen || x > scroll.scrollLeft + scroll.clientWidth - margen) {
              scroll.scrollLeft = x - scroll.clientWidth / 2;
            }
          }
        }
      }

      var ahora = Date.now();
      if (ahora - ultimaHuella > 400) {
        ultimaHuella = ahora;
        var h = huellaEstado();
        if (h !== huella) pintarTodo();
      }
    },

    // Para las pruebas y para la consola: estado interno sin tener que
    // adivinarlo desde el DOM.
    _estado: function () {
      return { iniciado: iniciado, zoom: zoom, iman: imanActivo, dur: dur, carriles: T ? T.carriles.length : 0 };
    },
    _imantar: imantar,
    _pintarTodo: pintarTodo,
    _fijarZoom: fijarZoom,
    _tiempoEn: tiempoEn,
  };

  window.__tira = API;
})();
