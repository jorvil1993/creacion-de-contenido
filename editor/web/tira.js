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

  // -- escala de tiempo ----------------------------------------------------
  function el(id) { return document.getElementById(id); }
  function anchoLienzoPx() {
    var l = el("tiraLienzo");
    return l ? l.getBoundingClientRect().width : 0;
  }
  function pct(t) { return dur > 0 ? (t / dur) * 100 : 0; }

  /** Tiempo bajo un evento de puntero, en el espacio del lienzo. */
  function tiempoEn(ev) {
    var l = el("tiraLienzo");
    if (!l || dur <= 0) return 0;
    var r = l.getBoundingClientRect();
    var t = ((ev.clientX - r.left) / r.width) * dur;
    return Math.max(0, Math.min(dur, t));
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
      '<div class="tira-cuerpo">' +
        '<div class="tira-etiquetas">' +
          '<div class="hueco"></div>' + etiquetas +
        '</div>' +
        '<div class="tira-scroll" id="tiraScroll">' +
          '<div class="tira-lienzo" id="tiraLienzo">' +
            '<div class="tira-regla" id="tiraRegla"></div>' +
            carriles +
            '<div class="tira-cursor" id="tiraCursor"></div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<p class="tira-leyenda">Clic en cualquier carril para llevar la aguja ahí. ' +
      'Los seis carriles comparten una sola escala de tiempo: lo que está encima de ' +
      'lo mismo, suena y se ve a la vez.</p>' +
      '</div>';

    // Los puntos de color de las etiquetas los pinta el CSS por clase; aquí
    // solo se les cuelga la clase del bloque que representan.
    var mapaPunto = { voz: "voz", subtitulos: "subtitulo", broll: "broll", anim: "anim", sfx: "", musica: "musica" };
    Array.prototype.forEach.call(cont.querySelectorAll("[data-punto]"), function (p) {
      var clase = mapaPunto[p.getAttribute("data-punto")];
      p.className = "punto tira-bloque " + (clase || "");
      if (p.getAttribute("data-punto") === "sfx") p.style.background = "var(--acento)";
    });

    // Clic en la regla o en un carril: llevar la aguja ahí.
    el("tiraLienzo").addEventListener("click", function (ev) {
      var v = elVideo();
      if (v) v.currentTime = tiempoEn(ev);
    });
    return true;
  }

  /** Marcas de la regla: se elige el paso más chico de la escala que deje al
   *  menos 60px entre marcas. */
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
      c.appendChild(bloque(esVideo ? "broll" : "pip", ev.ini, ev.fin,
        (esVideo ? "B-Roll: " : "PiP: ") + nombre,
        nombre + " · " + ev.ini.toFixed(2) + "s - " + ev.fin.toFixed(2) + "s"));
    });
  }

  function pintarAnims() {
    var c = carril("anim");
    if (!c) return;
    c.innerHTML = "";
    anims().forEach(function (a) {
      c.appendChild(bloque("anim", a.ini, a.fin, a.nombre,
        a.nombre + " · " + a.ini.toFixed(2) + "s - " + a.fin.toFixed(2) + "s"));
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
      if (!construirArmazon()) return;
      iniciado = true;
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
      return { iniciado: iniciado, dur: dur, carriles: T ? T.carriles.length : 0 };
    },
    _pintarTodo: pintarTodo,
    _tiempoEn: tiempoEn,
  };

  window.__tira = API;
})();
