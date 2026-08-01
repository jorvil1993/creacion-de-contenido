
/* ═══════════ CATÁLOGO DE CLIPS ═══════════ */
const CLIPS={
 F01:['noche','Cara en la oscuridad iluminada por el celular','6 guiones'],
 F02:['ojos','Primer plano de ojos cansados frotándose','6 guiones'],
 F03:['insomnio','Dando vueltas en la cama, reloj de madrugada','3 guiones'],
 F04:['sol','Sol fuerte, reflejo cegador en la pantalla','2 guiones'],
 F05:['cama','Cama acogedora con luz cálida','2 guiones'],
 F06:['cafe','Café humeando mientras se espera','1 guion'],
 F07:['viaje','Maleta abierta, ropa doblada','1 guion'],
 F08:['libros','Pila pesada de libros de tapa dura','8 guiones'],
 F09:['biblioteca','Estanterías infinitas, luz dorada','7 guiones'],
 F11:['agua','Gotas de agua salpicando en cámara lenta','1 guion'],
 F12:['tina','Bañera con espuma y vapor','1 guion'],
 F13:['regalo','Caja de regalo con moño de satén','4 guiones'],
 F14:['scroll','Pulgar deslizando sin fin en la oscuridad','10 guiones'],
 F15:['tiempo','Arena cayendo en un reloj de arena','3 guiones'],
 F16:['abandonado','Libro olvidado con separador y polvo','5 guiones'],
 F17:['notificaciones','Enjambre de burbujas de notificación','3 guiones'],
 F18:['ninos-pantalla','Niño a oscuras frente a una tablet','3 guiones'],
 F19:['ninos-leyendo','Niño leyendo feliz junto a la ventana','3 guiones'],
 F20:['mama','Mujer de 50s leyendo en un sillón','1 guion'],
 F21:['pareja','Uno duerme, el otro lee en la oscuridad','1 guion'],
 F22:['mochila','Mochila escolar reventada de libros','1 guion'],
 F23:['bateria','Celular muriéndose, cable fuera de alcance','3 guiones'],
 F24:['entrega','Moto de delivery en la ciudad','3 guiones'],
 F25:['caja','Caja de cartón abriéndose','2 guiones'],
 F28:['piscina','Borde de piscina en verano','2 guiones'],
 F29:['lampara','Lámpara que se enciende en la oscuridad','1 guion'],
 F30:['vitrina','Alguien indeciso en un pasillo de tienda','4 guiones'],
 F31:['kindle-primer-plano','Primer plano del aparato leyendo sin distracciones','1 guion'],
 F32:['lluvia','Lluvia en la ventana, luz cálida adentro','2 guiones'],
 F33:['rendicion','Se rinde: suelta el libro y agarra el celular','1 guion'],
 F34:['kindle-real','[REAL, con permiso — MySmartPrice] Encendido: logo Kindle y árbol','sin usar aún'],
 P01:['P01','Paperwhite en la cama de noche · pantalla B/N','10 guiones'],
 P02:['pagina-real','[REAL, con permiso — MySmartPrice] Paperwhite 16GB en la mano · pantalla B/N','14 guiones'],
 P03:['P03','Paperwhite a pleno sol · pantalla B/N','2 guiones'],
 P04:['P04','Paperwhite jade (verde matcha) a oscuras · B/N','3 guiones'],
 P05:['P05','Kindle Basic liviano en una mano · B/N','6 guiones'],
 P06:['P06','Paperwhite raspberry como regalo · B/N','5 guiones'],
 P07:['P07','Paperwhite Kids en manos de niño · B/N','3 guiones'],
 P08:['P08','Kindle Colorsoft · pantalla A COLOR','1 guion'],
 P09:['P09','Kobo Libra Colour con botones · A COLOR','2 guiones'],
 P10:['P10','Kobo Clara Colour compacta · A COLOR','1 guion'],
 P11:['P11','Tus cajas selladas reales (stock)','4 guiones'],
 H01:['tarjeta-specs','Hyperframe: Ficha técnica animada con 3 características clave del producto','1 guion'],
 H02:['comparativa','Hyperframe: Comparativa animada lado a lado entre 2 modelos','1 guion'],
 H03:['anim-sol','Hyperframe: Animación de legibilidad a pleno sol sin reflejos','1 guion'],
 H04:['anim-bateria','Hyperframe: Animación de batería de larga duración (semanas)','1 guion'],
 H05:['anim-splash','Hyperframe: Animación de salpicadura de agua al mojar el equipo','1 guion'],
 H06:['anim-moto','Hyperframe: Animación de envío rápido a domicilio en Bolivia','1 guion'],
 H07:['stickers','Hyperframe: Stickers gráficos (Destello cian / Bandera Bolivia)','1 guion'],
 H08:['anim-apps','Hyperframe: Animación de marcas/apps que distraen (TikTok, WhatsApp, Facebook)','1 guion']
};
function c(id){return CLIPS[id]?`<span class="clip" data-clip="${id}" onclick="event.stopPropagation();irAPrompt('${id}')">${id}</span>`:id;}
// mapa inverso: nombre de archivo -> código que se usa en los guiones (scroll -> F14)
const COD={}; for(const k in CLIPS) if(CLIPS[k][0]!==k) COD[CLIPS[k][0]]=k;
// resumen en español, una frase, de qué le pedimos a la IA en cada prompt
const RESUMEN={
 scroll:'Pulgar deslizando sin parar en un celular a oscuras, brillo azulado en la piel, cámara acercándose, sin marca ni texto en pantalla.',
 ojos:'Primer plano de ojos cansados de noche que se frotan, luz azul tenue, dormitorio oscuro de fondo, rostro no identificable.',
 noche:'Alguien acostado en un dormitorio a oscuras, cara iluminada solo por el brillo frío del celular sostenido arriba.',
 libros:'Pila alta de libros de tapa dura en una mesa, luz cálida lateral, una mano levanta el de arriba para sentir el peso.',
 biblioteca:'Recorrido vertical por estanterías interminables, luz dorada desde ventanas altas, polvo en el aire, lomos sin título.',
 abandonado:'Libro cerrado y olvidado en una mesita de noche, separador a un tercio, capa de polvo, cámara acercándose despacio.',
 notificaciones:'Enjambre abstracto de burbujas de notificación multiplicándose en la oscuridad, luz azul fría, cámara alejándose.',
 insomnio:'Alguien dando vueltas sin poder dormir, luego un reloj digital brillando débil en la mesita, tonos fríos de noche.',
 regalo:'Caja de regalo con moño de satén, luz dorada cálida, manos desatando el moño con expectativa, caja en blanco.',
 caja:'Caja de cartón lisa, manos cortando la cinta y levantando la solapa para mostrar la espuma protectora adentro.',
 vitrina:'Una persona de espaldas, hombros caídos, dudando frente a estantes de productos genéricos, sin poder decidirse.',
 tiempo:'Arena fina cayendo por el cuello de un reloj de arena, contraluz dorado, cámara casi quieta, tono melancólico.',
 bateria:'Celular con la pantalla casi negra apagándose del todo, cable de carga fuera de alcance, luz tenue de noche.',
 entrega:'Moto de delivery zigzagueando en tráfico soleado de una ciudad latina, luz dorada de tarde, cara del repartidor no visible.',
 'ninos-pantalla':'Un niño en un dormitorio oscuro, cara iluminada solo por el brillo frío de una tablet, ambiente inquietante.',
 'ninos-leyendo':'Un niño acurrucado junto a una ventana, absorto leyendo un libro de papel, luz cálida de tarde, pequeña sonrisa.',
 sol:'Sol fuerte de mediodía, una mano inclina una superficie oscura que refleja el cielo y la silueta de la persona.',
 cama:'Cama deshecha e invitante en un dormitorio cálido y tenue, lámpara de noche dando un charco de luz, nadie en cuadro.',
 agua:'Cámara súper lenta de gotas de agua salpicando sobre una superficie oscura junto a una piscina, sol brillante.',
 tina:'Bañera con espuma y vapor subiendo, luz de velas y una toalla doblada al borde, ambiente de spa, nadie en cuadro.',
 piscina:'Borde de piscina en verano, agua turquesa ondeando y reflejando luz sobre una reposera, sombras de palmeras.',
 mama:'Mujer de unos cincuenta leyendo tranquila en un sillón con luz cálida de tarde, sostiene un e-reader liso sin marca.',
 pareja:'Dormitorio de noche con dos personas en la cama: una duerme, la otra sigue despierta leyendo con cuidado de no molestar.',
 mochila:'Mochila escolar sobreestufada de libros en el piso, una mano chica hace fuerza para levantarla, luz de mañana.',
 cafe:'Taza de café humeando junto a una ventana, silla vacía enfrente, calle desenfocada afuera, espera tranquila.',
 viaje:'Maleta abierta sobre una cama siendo empacada, manos acomodando ropa doblada, luz cálida de mañana.',
 silencio:'Arranca ya casi vacío: quedan cuatro o cinco burbujas apagándose y un brillo cálido al centro. En los primeros 2 segundos se apagan las últimas y queda la calma. Revisa los primeros 3 segundos: si ahí la pantalla está llena de burbujas, el clip no sirve.',
 lluvia:'Lluvia cayendo por una ventana al atardecer, luces desenfocadas afuera, luz cálida de lámpara adentro, ambiente de lectura.',
 lampara:'Lámpara de noche que se enciende de golpe en un dormitorio a oscuras, luz cálida cayendo sobre las sábanas.',
 rendicion:'Alguien sostiene un libro tratando de seguir leyendo, afloja el agarre y termina soltándolo para agarrar el celular que brilla al lado.',
 'kindle-real':'[Metraje REAL, no generado — de un unboxing de MySmartPrice, con permiso] El Kindle se enciende: aparece el logo y el árbol de la pantalla de inicio.',
 'pagina-real':'[Metraje REAL, no generado — de un unboxing de MySmartPrice, con permiso] El Paperwhite 16GB sostenido en una mano, pantalla legible con una página real de novela. Sustituye al P02 generado por IA.',
 P01:'Animar la foto: el dispositivo en una cama a oscuras, iluminado por su propio brillo, una mano entra y toca la pantalla.',
 P03:'Animar la foto: el dispositivo a pleno sol de mediodía, sombras de hojas moviéndose encima, pantalla legible pese al sol.',
 P04:'Animar la foto: el dispositivo casi a oscuras, su brillo ámbar es la única luz, una mano lo desplaza levemente.',
 P05:'Animar la foto: el dispositivo sostenido en una sola mano, inclinándose para mostrar lo fino y liviano que es.',
 P06:'Animar la foto: el dispositivo junto a un moño de satén y luces festivas, manos lo deslizan hacia cámara como regalo.',
 P07:'Animar la foto: el dispositivo en manos de un niño, dormitorio cálido y luminoso de fondo, solo manos, sin caras.',
 P08:'Animar la foto: el dispositivo con luz cálida direccional recorriéndolo, haciendo que su color a todo color brille.',
 P09:'Animar la foto: el dispositivo en una mano, pulgar sobre los botones físicos de pasar página, luz en el borde.',
 P10:'Animar la foto: el dispositivo junto a un café en una mesa de madera, una mano lo levanta para mostrar lo compacto que es.',
 P11:'Animar la foto: las cajas selladas reales, luz cálida recorriéndolas para mostrar el cartón, se mantiene igual todo el packaging.'
};
// dónde se usa un clip: guion, momento, tipo de plano y qué se está diciendo
function usosDe(archivo){
 const cod=COD[archivo]||archivo, out=[];
 G.forEach(g=>g.tl.forEach((r,ri)=>{
  if((r[3].match(/\b[FPH]\d\d\b/g)||[]).includes(cod))
   out.push({n:g.n,ri,t:g.t,mom:r[0],tipo:r[2],dice:r[1],ve:r[3]});
 }));
 return out;
}
// abre un guion concreto desde cualquier lado.
// con ri (indice de fila) salta directo a esa fila de la linea de tiempo y la marca
function irAGuion(n,ri){
 irA('guiones');
 setTimeout(()=>{
  const el=document.getElementById('g-'+n); if(!el)return;
  el.classList.add('abierto');
  document.querySelectorAll('tr.tlmarca').forEach(t=>t.classList.remove('tlmarca'));
  const fila=ri==null?null:document.getElementById('tl-'+n+'-'+ri);
  if(fila){fila.classList.add('tlmarca');
   fila.scrollIntoView({behavior:'smooth',block:'center'});}
  else el.scrollIntoView({behavior:'smooth',block:'start'});
 },70);
}
// tooltip flotante: position:fixed, así ningún contenedor con overflow lo recorta
document.addEventListener('mouseover',e=>{
 const el=e.target.closest?.('.clip'); if(!el)return;
 const d=CLIPS[el.dataset.clip]; if(!d)return;
 const t=document.getElementById('tipflot');
 const esProd=el.dataset.clip[0]==='P';
 const us=usosDe(d[0]);
 t.innerHTML=`<b>${el.dataset.clip} · ${esProd?'producto':'ambiente'}</b>${d[1]}
   <span class="arch">${d[0]}.mp4</span><i>${us.length
     ? 'Se usa '+us.length+(us.length>1?' veces':' vez')+' en los 10 guiones: '
       +[...new Set(us.map(u=>'G'+u.n))].join(', ')
     : 'No se usa en los 10 guiones de producción'}</i>`;
 t.style.display='block';
 const r=el.getBoundingClientRect(), tr=t.getBoundingClientRect();
 let x=r.left+r.width/2-tr.width/2, y=r.top-tr.height-9;
 if(y<8) y=r.bottom+9;                                   // si no entra arriba, va abajo
 x=Math.max(8,Math.min(x,innerWidth-tr.width-8));         // nunca se sale de los costados
 t.style.left=x+'px'; t.style.top=y+'px';
});
document.addEventListener('mouseout',e=>{
 if(e.target.closest?.('.clip'))document.getElementById('tipflot').style.display='none';
});

/* ═══════════ LOS 10 GUIONES ═══════════ */
const G=[
{n:7,t:'¿Te diste cuenta de que ya no podés estar 5 minutos sin el celular?',rum:90,bloque:'Atención',hook:'fisico',hooksegs:3.0,cierresegs:0,
 hooktxt:'Entras de pie al plano caminando hacia cámara',
 utileria:['Kindle Paperwhite — lo levantas en la toma 4','Celular en mano — scrolleando en la toma 2'],
 set:['Ventana a 45° a tu izquierda','2 m de separación de la pared','De pie frente a cámara','Cámara ya grabando antes de que entres al plano'],
 tele:'¿Te diste cuenta de que ya no podés estar cinco minutos sin hacer nada? Sin sacar el celular. Sin buscar dopamina barata. || Ya casi nadie puede. Y no es casualidad. || Estás compitiendo contra una aplicación diseñada por mil ingenieros para que no puedas soltarla. El video que se reproduce solo. La notificación. El siguiente. Todo está diseñado para ganarte. || No es falta de disciplina. Es una pelea injusta: vos, con tu pobre fuerza de voluntad, contra un algoritmo. Y así, no la vas a ganar. || La única forma de ganarla es salirte del juego. || Volver a tener un espacio donde nada te interrumpa. Donde abrís un libro y el mundo se apaga: sin notificaciones, sin pantallas que te quemen la vista, sin tentaciones a un toque. || Un espacio donde tu atención vuelve a ser tuya. || Mandáselo a alguien que no suelta el celular ni en la mesa.',
 tomas:[
  ['0–6s','Plano medio · de pie · HOOK','Cámara ya grabando. Entras de pie al cuadro caminando hacia cámara. Miras fijo a cámara y dices el hook.','¿Te diste cuenta de que ya no podés estar cinco minutos sin hacer nada? Sin sacar el celular. Sin buscar dopamina barata.'],
  ['6–20s','Plano medio · de perfil con celular','Pones tu cuerpo de perfil scrolleando el celular concentrado. Dices "Ya casi nadie puede...", luego te giras o miras a cámara marcando "mil ingenieros" con la mano.','Ya casi nadie puede. Y no es casualidad. Estás compitiendo contra una aplicación diseñada por mil ingenieros para que no puedas soltarla. El video que se reproduce solo. La notificación. El siguiente. Todo está diseñado para ganarte.'],
  ['20–32s','Plano cerrado (acercá la cámara)','Cambio de distancia real de pie. Tono más confidencial e íntimo.','No es falta de disciplina. Es una pelea injusta: vos, con tu pobre fuerza de voluntad, contra un algoritmo. Y así, no la vas a ganar. La única forma de ganarla es salirte del juego.'],
  ['32–47s','Plano medio · con producto','Levantas el Kindle al cuadro a la altura del pecho de pie y lo sostienes suavemente mientras hablas.','Volver a tener un espacio donde nada te interrumpa. Donde abrís un libro y el mundo se apaga: sin notificaciones, sin pantallas que te quemen la vista, sin tentaciones a un toque. Un espacio donde tu atención vuelve a ser tuya.'],
  ['47–52s','Plano medio · CIERRE','Bajas el aparato de pie y miras fijo a cámara sosteniendo el gesto.','Mandáselo a alguien que no suelta el celular ni en la mesa.']],
 tl:[
  ['0–3s','¿Te diste cuenta de que ya no podés estar cinco minutos sin hacer nada?','YO','Entras de pie al plano caminando a cámara. Banner de hook arriba','whoosh_rapido al entrar + impacto_grave','—'],
  ['3–6s','Sin sacar el celular. Sin buscar dopamina barata.','B-ROLL','F14 a pantalla completa: persona haciendo scroll infinito en el celular','pop + ui_blip_1','entra 02-lofi a −20 dB'],
  ['6–9s','Ya casi nadie puede. Y no es casualidad.','YO','De perfil scrolleando el celular mientras dices la frase','transicion_corte','—'],
  ['9–15s','Estás compitiendo contra una aplicación diseñada por mil ingenieros para que no puedas soltarla.','ANIM','H08 arriba a la derecha: íconos de TikTok, WhatsApp, Instagram','pop + ui_blip_2','—'],
  ['15–20s','El video que se reproduce solo. La notificación. El siguiente. Todo está diseñado para ganarte.','B-ROLL','F15 a pantalla completa: pantalla brillante / luz de teléfono en la oscuridad','whoosh_swoosh_2','—'],
  ['20–28s','No es falta de disciplina. Es una pelea injusta: vos, con tu pobre fuerza de voluntad, contra un algoritmo. Y así, no la vas a ganar.','B-ROLL','F33 a pantalla completa: se rinde y suelta el libro por el celular','subdrop_1 + impacto_hit','baja a −24 dB'],
  ['28–32s','La única forma de ganarla es salirte del juego.','YO','Vuelves al plano medio mirando fijo a cámara','reverso_1','—'],
  ['32–38s','Volver a tener un espacio donde nada te interrumpa. Donde abrís un libro y el mundo se apaga:','ANIM','H07 destello mientras levantas el Kindle al cuadro','whoosh_simple','sube a −20 dB'],
  ['38–43s','sin notificaciones, sin pantallas que te quemen la vista, sin tentaciones a un toque.','B-ROLL','F31 a pantalla completa: textura de pantalla e-ink como papel real','ui_apagar','—'],
  ['43–47s','Un espacio donde tu atención vuelve a ser tuya.','PIP','P02 arriba a la derecha: lectura placentera en ambiente cálido','camara_click_2','—'],
  ['47–52s','Mandáselo a alguien que no suelta el celular ni en la mesa.','ANIM','tarjeta-cta con el hook repetido y botón de compartir','tada_cierre','fade out']]},

{n:1,t:'El celular te está robando el sueño',rum:89,bloque:'Sueño y vista',hook:'fisico',hooksegs:2.0,cierresegs:0,
 hooktxt:'Arrancas mirando el celular en la cara y lo bajas de golpe',
 utileria:['Tu celular — tomas 1 y 2','Kindle Paperwhite — tomas 4 y 5'],
 set:['De noche, o con la persiana baja','Lámpara cálida detrás tuyo','La cama o un sillón oscuro de fondo'],
 tele:'Por eso no puedes dormir de noche. || Te acuestas cansado, agarras el celular un ratito… y a la hora sigues despierto con los ojos ardiendo. || No es que tengas insomnio. Es que esa pantalla te está tirando luz directo a los ojos, y tu cerebro cree que es de día. || Hay pantallas que no emiten luz: la reflejan, como el papel. Por eso los que leen en estas se duermen leyendo, en vez de desvelarse. || Si quieres que te explique cuál te conviene, escríbeme. Y deja de dormir con el celular en la cara.',
 tomas:[
  ['0–3s','Primer plano · HOOK','Empiezas con el celular pegado a la cara, iluminándote en la oscuridad. Lo bajas de golpe y miras a cámara. El hook lo dices ya con el celular abajo.','Por eso no puedes dormir de noche.'],
  ['3–12s','Plano medio','Sostienes el celular apagado en la mano, gesticulando con él.','Te acuestas cansado, agarras el celular un ratito… y a la hora sigues despierto con los ojos ardiendo.'],
  ['12–20s','Plano cerrado','Señalas tus propios ojos al decir "directo a los ojos".','No es que tengas insomnio. Es que esa pantalla te está tirando luz directo a los ojos, y tu cerebro cree que es de día.'],
  ['20–30s','Plano medio · con producto','Dejas el celular fuera de cuadro y levantas el Kindle en su lugar. El cambio de objeto es el argumento.','Hay pantallas que no emiten luz: la reflejan, como el papel. Por eso los que leen en estas se duermen leyendo, en vez de desvelarse.'],
  ['30–36s','Plano medio · CIERRE','Vuelves a la postura inicial, pero con el Kindle en vez del celular.','Si quieres que te explique cuál te conviene, escríbeme. Y deja de dormir con el celular en la cara.']],
 tl:[
  ['0–3s','Por eso no puedes dormir de noche.','B-ROLL','F01 a pantalla completa + banner de hook','impacto_latido bajo','—'],
  ['3–6s','Te acuestas cansado, agarras el celular un ratito…','ANIM','H08 arriba a la derecha: las apps que te desvelan','transicion_corte','entra 02-lofi a −22 dB'],
  ['6–9s','…y a la hora sigues despierto','PIP','F03 arriba a la derecha','ui_blip_2','—'],
  ['9–11s','con los ojos ardiendo.','B-ROLL','F02 a pantalla completa','pop','—'],
  ['11–14s','No es que tengas insomnio.','YO','Punch-in en "insomnio"','impacto_hit_2','baja a −24 dB'],
  ['14–17s','Es que esa pantalla te está tirando luz','YO','Señalas tus propios ojos','—','—'],
  ['17–20s','directo a los ojos,','PIP','F29 arriba a la izquierda: la luz que golpea','ui_blip_1','—'],
  ['20–23s','y tu cerebro cree que es de día.','B-ROLL','F04 a pantalla completa: sol de mediodía','whoosh_deep_1','—'],
  ['23–26s','Hay pantallas que no emiten luz: la reflejan, como el papel.','ANIM','H03 anim-sol: la luz le pega y la página sigue legible','whoosh_simple al cambiar de objeto','sube a −19 dB'],
  ['26–29s','Por eso los que leen en estas se duermen leyendo,','PIP','P01 arriba a la derecha','camara_enfoque_1','—'],
  ['29–32s','en vez de desvelarse.','B-ROLL','F05 a pantalla completa','reverso_whoosh','—'],
  ['32–35s','Si quieres que te explique cuál te conviene, escríbeme.','YO','Vuelves a la postura inicial, con el Kindle','—','—'],
  ['35–38s','Y deja de dormir con el celular en la cara.','ANIM','tarjeta-cta + WhatsApp','tada_cierre','fade out']]},

{n:18,t:'Tu hijo no lee por esta razón',rum:88,bloque:'Hijos',hook:'talking',hooksegs:0,cierresegs:0,
 hooktxt:'Directo a cámara, sin preámbulo. La frase sola es el gancho',
 utileria:['Kindle Kids o Paperwhite — toma 4'],
 set:['Living o comedor, no dormitorio','Luz natural de día','Arrancas con las manos vacías'],
 tele:'Tu hijo no lee por esta razón. || No es que sea flojo, ni que los chicos de ahora no lean. Es que el libro compite contra algo diseñado para ser irresistible. || Tú de chico competías contra la tele. Y la tele se acababa. Esto no se acaba nunca. || Lo que funciona no es quitarle la pantalla. Es darle una pantalla que solo tenga libros adentro. || Mándale esto a la mamá o al papá que dice que su hijo no lee.',
 tomas:[
  ['0–3s','Plano medio corto · HOOK','Ya sentado, mirada fija a cámara, arrancas sin moverte. Pausá medio segundo después de "razón".','Tu hijo no lee por esta razón.'],
  ['3–14s','Mismo plano','Niegas con la cabeza en "no es que sea flojo".','No es que sea flojo, ni que los chicos de ahora no lean. Es que el libro compite contra algo diseñado para ser irresistible.'],
  ['14–25s','Plano cerrado','Marca el contraste con las manos: una para "la tele", otra para "esto".','Tú de chico competías contra la tele. Y la tele se acababa. Esto no se acaba nunca.'],
  ['25–35s','Plano medio · con producto','Levantas el Kindle Kids. Gesto de entregárselo a alguien.','Lo que funciona no es quitarle la pantalla. Es darle una pantalla que solo tenga libros adentro.'],
  ['35–40s','Plano medio · CIERRE','Vuelves a la postura del arranque.','Mándale esto a la mamá o al papá que dice que su hijo no lee.']],
 tl:[
  ['0–3s','Tu hijo no lee por esta razón.','YO','Tú solo + banner de hook','impacto_hit_2 al terminar la frase','—'],
  ['3–6s','No es que sea flojo,','PIP','F18 arriba a la derecha','pop','entra 02-lofi a −21 dB'],
  ['6–9s','ni que los chicos de ahora no lean.','ANIM','H07 destello mientras niegas con la cabeza','—','—'],
  ['9–12s','Es que el libro compite contra algo','B-ROLL','F14 a pantalla completa','whoosh_swoosh_3','—'],
  ['12–14s','diseñado para ser irresistible.','YO','Punch-in en "irresistible"','impacto_hit','—'],
  ['14–17s','Tú de chico competías contra la tele.','YO','Marcas con una mano','transicion_corte','baja a −23 dB'],
  ['17–19s','Y la tele se acababa.','PIP','F15 arriba a la izquierda','ui_apagar','—'],
  ['19–22s','Esto no se acaba nunca.','ANIM','H08 arriba a la derecha: las apps no se acaban nunca','riser_1','—'],
  ['22–25s','Lo que funciona no es quitarle la pantalla.','YO','Plano cerrado','reverso_2','—'],
  ['25–28s','Es darle una pantalla','B-ROLL','F19 a pantalla completa','riser_reveal suave','sube a −19 dB'],
  ['28–31s','que solo tenga libros adentro.','PIP','P07 arriba a la izquierda','camara_click_1','—'],
  ['31–34s','Mándale esto a la mamá o al papá','YO','Vuelves a la postura del arranque','—','—'],
  ['34–37s','que dice que su hijo no lee.','ANIM','tarjeta-cta','tada_cierre','fade out']]},

{n:13,t:'El error al regalar libros a quien ama leer',rum:86,bloque:'Regalo',hook:'objeto',hooksegs:1.5,cierresegs:0,
 hooktxt:'Arrancas sosteniendo un libro envuelto para regalo',
 utileria:['Un libro envuelto o con moño — toma 1','Kindle con moño — tomas 4 y 5'],
 set:['Mesa despejada','Luz cálida lateral'],
 tele:'Error al regalar libros a un lector. || Le regalas un libro… y resulta que ya lo leyó. O no era su género. O ya lo tenía. || El que lee mucho es el más difícil de acertar, justamente porque lee mucho. || Por eso lo que nunca falla no es un libro. Es lo que le deja elegir cualquiera, cuando quiera. || Mándale esto a quien te va a regalar algo.',
 tomas:[
  ['0–3s','Plano medio · HOOK','Sostienes el libro envuelto frente al pecho. Al decir el hook lo bajas un poco, como decepcionado.','Error al regalar libros a un lector.'],
  ['3–14s','Mismo plano','Enumerá con los dedos: ya lo leyó, no era su género, ya lo tenía.','Le regalas un libro… y resulta que ya lo leyó. O no era su género. O ya lo tenía.'],
  ['14–25s','Plano cerrado','Dejas el libro en la mesa, fuera de cuadro. Manos vacías.','El que lee mucho es el más difícil de acertar, justamente porque lee mucho.'],
  ['25–35s','Plano medio · con producto','Levantas el Kindle con moño, en el mismo lugar donde estaba el libro.','Por eso lo que nunca falla no es un libro. Es lo que le deja elegir cualquiera, cuando quiera.'],
  ['35–40s','Plano medio · CIERRE','Sostienes el Kindle como sostenías el libro al inicio.','Mándale esto a quien te va a regalar algo.']],
 tl:[
  ['0–3s','Error al regalar libros a un lector.','YO','Sostienes el libro envuelto + banner de hook','whoosh_simple_2','—'],
  ['3–5s','Le regalas un libro…','YO','Bajas el libro, cara de decepción','—','entra 04-corporate a −20 dB'],
  ['5–8s','y resulta que ya lo leyó.','PIP','F08 arriba a la derecha','ui_blip_1','—'],
  ['8–10s','O no era su género.','YO','Segundo dedo','ui_blip_2','—'],
  ['10–12s','O ya lo tenía.','PIP','F09 arriba a la izquierda: su estantería llena','ui_blip_3','—'],
  ['12–15s','El que lee mucho es el más difícil de acertar,','B-ROLL','F30 a pantalla completa','transicion_swipe','—'],
  ['15–18s','justamente porque lee mucho.','YO','Plano cerrado, manos vacías','—','baja a −23 dB'],
  ['18–21s','Por eso lo que nunca falla no es un libro.','YO','Dejas el libro fuera de cuadro','whoosh_rapido','—'],
  ['21–24s','Es lo que le deja elegir cualquiera,','YO','Levantas el Kindle con moño','riser_reveal','sube a −19 dB'],
  ['24–26s','cuando quiera.','ANIM','H06 anim-moto: llega a tu puerta','camara_flash_pop_3','—'],
  ['26–29s','Mándale esto a quien','ANIM','H07 bandera mientras sostienes el Kindle','—','—'],
  ['29–32s','te va a regalar algo.','ANIM','tarjeta-cta','tada_cierre','fade out']]},

{n:28,t:'Lo metí al agua a propósito',rum:86,bloque:'Comparación',hook:'accion',hooksegs:2.0,cierresegs:0,
 hooktxt:'Muestras el aparato y lo hundes en el agua mientras hablas',
 utileria:['Kindle resistente al agua — Paperwhite o superior, NUNCA el Basic','Fuente, balde transparente o lavaplatos lleno','Toalla a mano — toma 3'],
 set:['Luz fuerte para que se vean las gotas','La toma del agua grabala 3 veces: es LA toma del video'],
 tele:'Lo metí al agua. A propósito. || Todos hemos tenido el susto: el celular al borde de la tina, de la piscina, del lavaplatos. || Este se puede mojar. Se cae a la piscina, lo sacas, lo secas y sigue. || Por eso se lee en la tina, en la playa, bajo la lluvia. Sin cuidarlo como un huevo. || Etiqueta a quien lee en la tina.',
 tomas:[
  ['0–3s','Primer plano del agua · HOOK','La mano entra al cuadro con el aparato y lo hunde. Graba esto primero y repetilo 3 veces: es LA toma del video.','Lo metí al agua. A propósito.'],
  ['3–13s','Plano medio · tú','Ya seco, mirando a cámara, con el aparato en la mano goteando.','Todos hemos tenido el susto: el celular al borde de la tina, de la piscina, del lavaplatos.'],
  ['13–24s','Primer plano · sacada','Sacas el aparato del agua y lo secas con la toalla. Que se vea la pantalla funcionando mojada.','Este se puede mojar. Se cae a la piscina, lo sacas, lo secas y sigue.'],
  ['24–34s','Plano medio · tú','Relajado, sosteniendo el aparato ya seco.','Por eso se lee en la tina, en la playa, bajo la lluvia. Sin cuidarlo como un huevo.'],
  ['34–40s','Primer plano · CIERRE','Repites el gesto de hundirlo, igual que el segundo 0. Cierra el loop perfecto.','Etiqueta a quien lee en la tina.']],
 tl:[
  ['0–3s','Lo metí al agua. A propósito.','YO','Tu toma real del agua + banner de hook','impacto_vidrio + agua natural del clip','—'],
  ['3–5s','Todos hemos tenido el susto:','YO','Plano medio, aparato goteando','transicion_corte','entra 01-comercial a −20 dB'],
  ['5–8s','el celular al borde de la tina,','PIP','F12 arriba a la derecha','pop','—'],
  ['8–10s','de la piscina, del lavaplatos.','ANIM','H05 anim-splash a pantalla completa','whoosh_rapido_2','—'],
  ['10–13s','Este se puede mojar.','YO','Plano medio, sostienes el aparato','—','—'],
  ['13–16s','Se cae a la piscina,','YO','Tu toma real de la sacada del agua','whoosh_aspero','sube a −18 dB'],
  ['16–18s','lo sacas, lo secas','PIP','F11 arriba a la izquierda','ui_sparkle','—'],
  ['18–20s','y sigue.','YO','Punch-in sobre la pantalla encendida mojada','impacto_hit_5','—'],
  ['20–23s','Por eso se lee en la tina, en la playa,','YO','Plano medio, secas el aparato con la toalla','transicion_swipe','—'],
  ['23–26s','bajo la lluvia.','ANIM','H05 anim-splash, otra variante','whoosh_swish_2','—'],
  ['26–29s','Sin cuidarlo como un huevo.','YO','Plano medio, aparato seco','—','baja a −21 dB'],
  ['29–32s','Etiqueta a quien lee en la tina.','ANIM','tarjeta-cta + repetición del hook','tada_cierre','fade out']]},

{n:19,t:'Esta pantalla sí se la doy',rum:84,bloque:'Hijos',hook:'objeto',hooksegs:1.5,cierresegs:0,
 hooktxt:'Sostienes el Kindle Kids y lo giras hacia cámara',
 utileria:['Kindle Kids o Paperwhite — tomas 1, 3 y 5','Un celular para el contraste — toma 2'],
 set:['Living con luz de día','Sofá o mesa de comedor'],
 tele:'Esta pantalla sí se la doy. || Le quito el celular a las ocho y empieza la pelea de todas las noches. Ya la conoces. || Pero cuando le doy esto no hay pelea. Porque no siente que le estoy quitando algo: le estoy dando otra cosa. || No tiene juegos, no tiene YouTube, no tiene internet para otra cosa. Y no le tira luz a los ojos antes de dormir. || Si peleas por las pantallas en tu casa, escríbeme.',
 tomas:[
  ['0–3s','Plano medio · HOOK','Sostienes el Kindle con las dos manos y lo giras hacia cámara al decir "esta".','Esta pantalla sí se la doy.'],
  ['3–14s','Mismo plano','Dejas el Kindle y levantas el celular. Cara de cansancio al hablar de la pelea.','Le quito el celular a las ocho y empieza la pelea de todas las noches. Ya la conoces.'],
  ['14–25s','Plano cerrado','Sueltas el celular fuera de cuadro y vuelves a agarrar el Kindle.','Pero cuando le doy esto no hay pelea. Porque no siente que le estoy quitando algo: le estoy dando otra cosa.'],
  ['25–35s','Plano medio','Enumerá con los dedos lo que NO tiene.','No tiene juegos, no tiene YouTube, no tiene internet para otra cosa. Y no le tira luz a los ojos antes de dormir.'],
  ['35–40s','Plano medio · CIERRE','Vuelves a girar el aparato hacia cámara como en el segundo 0.','Si peleas por las pantallas en tu casa, escríbeme.']],
 tl:[
  ['0–3s','Esta pantalla sí se la doy.','YO','Giras el aparato hacia cámara + banner de hook','camara_enfoque_2','—'],
  ['3–6s','Le quito el celular a las ocho','YO','Dejas el Kindle, levantas el celular','transicion_corte','entra 02-lofi a −21 dB'],
  ['6–9s','y empieza la pelea de todas las noches.','ANIM','H08 arriba a la derecha: las apps por las que pelean','ui_error suave','—'],
  ['9–11s','Ya la conoces.','YO','Punch-in, cara de cansancio','—','—'],
  ['11–14s','Pero cuando le doy esto no hay pelea.','YO','Sueltas el celular y vuelves al Kindle','whoosh_simple','—'],
  ['14–17s','Porque no siente que le estoy quitando algo:','YO','Plano cerrado, gesto de dar con las dos manos','whoosh_deep_2','baja a −23 dB'],
  ['17–20s','le estoy dando otra cosa.','B-ROLL','F19 a pantalla completa','riser_reveal','sube a −19 dB'],
  ['20–22s','No tiene juegos,','YO','Primer dedo','ui_blip_1','—'],
  ['22–24s','no tiene YouTube,','ANIM','H08 arriba a la izquierda, otra variante: eso es lo que NO tiene','ui_blip_2','—'],
  ['24–26s','no tiene internet para otra cosa.','PIP','P07 arriba a la izquierda','ui_blip_3','—'],
  ['26–29s','Y no le tira luz a los ojos antes de dormir.','B-ROLL','F05 a pantalla completa','reverso_whoosh','—'],
  ['29–32s','Si peleas por las pantallas en tu casa, escríbeme.','ANIM','tarjeta-cta','tada_cierre','fade out']]},

{n:14,t:'Ese regalo va a quedar guardado',rum:83,bloque:'Regalo',hook:'fisico',hooksegs:2.5,cierresegs:0,
 hooktxt:'Abres un cajón lleno de regalos sin usar y lo cierras',
 utileria:['Un cajón o caja con cosas sin usar — toma 1','Perfume, taza y un adorno — toma 2','Kindle con moño — tomas 4 y 5'],
 set:['Mesa o cómoda','Luz cálida lateral'],
 tele:'Ese regalo va a quedar guardado. || El perfume que no usa. La taza número doce. El adorno que va al cajón. || Regalar bien no es gastar más. Es acertar en algo que use todos los días. || Si la persona lee, o tú quieres que lea, esto lo va a agarrar todas las noches. No una vez. || Escríbeme y te ayudo a elegir según la persona.',
 tomas:[
  ['0–3s','Plano medio · HOOK','Abres el cajón, miras adentro, lo cierras y miras a cámara. El hook lo dices al cerrarlo.','Ese regalo va a quedar guardado.'],
  ['3–13s','Primer plano de los objetos','Vas mostrando uno por uno: perfume, taza, adorno. Los dejas caer suave en la mesa.','El perfume que no usa. La taza número doce. El adorno que va al cajón.'],
  ['13–24s','Plano medio · tú','Manos vacías, hablando directo.','Regalar bien no es gastar más. Es acertar en algo que use todos los días.'],
  ['24–34s','Plano medio · con producto','Levantas el Kindle con moño y lo dejas donde estaban los otros objetos.','Si la persona lee, o tú quieres que lea, esto lo va a agarrar todas las noches. No una vez.'],
  ['34–40s','Plano medio · CIERRE','Vuelves a la postura del cajón cerrado.','Escríbeme y te ayudo a elegir según la persona.']],
 tl:[
  ['0–3s','Ese regalo va a quedar guardado.','YO','Abres el cajón y lo cierras + banner de hook','ui_atras al cerrar el cajón','—'],
  ['3–5s','El perfume que no usa.','YO','Tu toma del perfume','impacto_hit_3','entra 04-corporate a −20 dB'],
  ['5–7s','La taza número doce.','YO','Tu toma de la taza','impacto_hit_3','—'],
  ['7–9s','El adorno que va al cajón.','B-ROLL','F30 a pantalla completa','transicion_swipe','—'],
  ['9–12s','Regalar bien no es gastar más.','YO','Plano medio, manos vacías','—','baja a −23 dB'],
  ['12–15s','Es acertar en algo que use todos los días.','PIP','F13 arriba a la derecha','pop','—'],
  ['15–18s','Si la persona lee,','YO','Levantas el Kindle con moño','riser_reveal','sube a −19 dB'],
  ['18–20s','o tú quieres que lea,','PIP','P06 arriba a la izquierda','camara_flash_pop_5','—'],
  ['20–23s','esto lo va a agarrar todas las noches.','ANIM','H04 anim-bateria: dura semanas, no una noche','whoosh_swish_3','—'],
  ['23–25s','No una vez.','YO','Punch-in','impacto_hit','—'],
  ['25–28s','Escríbeme y te ayudo','ANIM','H06 anim-moto: te llega a la puerta','—','—'],
  ['28–31s','a elegir según la persona.','ANIM','tarjeta-cta','tada_cierre','fade out']]},

{n:8,t:'¿Cuántos libros dejaste a medias?',rum:82,bloque:'Atención',hook:'objeto',hooksegs:1.5,cierresegs:0,
 hooktxt:'Levantas un libro con el separador clavado en la página 30',
 utileria:['Un libro con separador clavado a un tercio — tomas 1, 2 y 5','Kindle — toma 4'],
 set:['Mesa de luz o repisa','Luz suave de tarde'],
 tele:'¿Cuántos libros dejaste a medias? || Todos tenemos ese libro con el separador clavado en la página treinta desde hace dos años. || Y cada vez que lo ves, te sientes un poco mal. Pero no lo abres, porque abrirlo cuesta más que abrir el celular. || Lo que cambia el juego es que agarrar la lectura cueste menos que agarrar el celular. Ahí sí se termina. || Comenta en qué página quedó el tuyo.',
 tomas:[
  ['0–3s','Plano medio · HOOK','Levantas el libro y lo abres justo donde está el separador. Miras a cámara.','¿Cuántos libros dejaste a medias?'],
  ['3–13s','Primer plano del libro','Pasas el dedo por el separador. Que se vea el grosor de lo que falta.','Todos tenemos ese libro con el separador clavado en la página treinta desde hace dos años.'],
  ['13–24s','Plano medio · tú','Cierras el libro y lo dejas. Tono comprensivo, no acusador.','Y cada vez que lo ves, te sientes un poco mal. Pero no lo abres, porque abrirlo cuesta más que abrir el celular.'],
  ['24–34s','Plano medio · con producto','Levantas el Kindle con una sola mano, mostrando lo fácil que es.','Lo que cambia el juego es que agarrar la lectura cueste menos que agarrar el celular. Ahí sí se termina.'],
  ['34–38s','Plano medio · CIERRE','Vuelves a levantar el libro, como en el segundo 0.','Comenta en qué página quedó el tuyo.']],
 tl:[
  ['0–3s','¿Cuántos libros dejaste a medias?','YO','Levantas el libro y lo abres en el separador + banner de hook','impacto_hit_4','—'],
  ['3–6s','Todos tenemos ese libro','YO','Tu primer plano del separador','—','entra 02-lofi a −21 dB'],
  ['6–9s','con el separador clavado en la página treinta','PIP','F16 arriba a la derecha','pop','—'],
  ['9–11s','desde hace dos años.','B-ROLL','F15 a pantalla completa','reverso_3','—'],
  ['11–14s','Y cada vez que lo ves, te sientes un poco mal.','YO','Plano medio, cierras el libro','transicion_corte','baja a −23 dB'],
  ['14–17s','Pero no lo abres,','YO','Dejas el libro fuera de cuadro','—','—'],
  ['17–20s','porque abrirlo cuesta más que abrir el celular.','B-ROLL','F14 a pantalla completa','whoosh_grave_3','—'],
  ['20–23s','Lo que cambia el juego','YO','Levantas el Kindle con una sola mano','whoosh_simple','sube a −19 dB'],
  ['23–26s','es que agarrar la lectura cueste menos','PIP','P01 arriba a la izquierda','camara_click_4','—'],
  ['26–28s','que agarrar el celular.','ANIM','H08 arriba a la derecha + punch-in en \"celular\"','impacto_hit_2','—'],
  ['28–30s','Ahí sí se termina.','ANIM','H07 destello sobre el aparato','riser_reveal','—'],
  ['30–33s','Comenta en qué página quedó el tuyo.','ANIM','tarjeta-cta + "comenta 👇"','tada_cierre','fade out']]},

{n:27,t:'Los saqué al sol. Mira.',rum:82,bloque:'Comparación',hook:'accion',hooksegs:2.0,cierresegs:0,
 hooktxt:'Exterior, sol fuerte: muestras celular y e-reader lado a lado',
 utileria:['Tu celular con el brillo al máximo','Kindle','Trípode o alguien que sostenga la cámara'],
 set:['Al mediodía, sol directo, sin sombra','La comparación grabala 3 veces: es LA toma del video'],
 tele:'Los saqué al sol. Mira. || Mismo sol, misma hora. En uno ves tu cara. En el otro ves la página. || Y no es el brillo: sube el celular al máximo y sigue igual. || Uno tira luz hacia ti. El otro deja que el sol le pegue, como a una hoja. || Escríbeme si lees afuera.',
 tomas:[
  ['0–3s','Primer plano de los dos · HOOK','Los dos aparatos juntos bajo el sol, encuadre cerrado. Que se vea tu reflejo en el celular. Esta toma es el video entero: grabala 3 veces.','Los saqué al sol. Mira.'],
  ['3–14s','Primer plano · comparación','Mueves los dos aparatos para que el sol les pegue igual. Sin cortes.','Mismo sol, misma hora. En uno ves tu cara. En el otro ves la página.'],
  ['14–25s','Primer plano del celular','Subes el brillo del celular a la vista de la cámara. Sigue sin verse.','Y no es el brillo: sube el celular al máximo y sigue igual.'],
  ['25–35s','Plano medio · tú','Te incluyes en cuadro, con el sol de fondo, sosteniendo el Kindle.','Uno tira luz hacia ti. El otro deja que el sol le pegue, como a una hoja.'],
  ['35–40s','Primer plano · CIERRE','Vuelves al encuadre de los dos aparatos del segundo 0.','Escríbeme si lees afuera.']],
 tl:[
  ['0–3s','Los saqué al sol. Mira.','YO','Tu comparación real, los dos aparatos + banner de hook','camara_dslr','—'],
  ['3–6s','Mismo sol, misma hora.','YO','Tu toma de la comparación','—','entra 01-comercial a −20 dB'],
  ['6–8s','En uno ves tu cara.','YO','Punch-in sobre el reflejo del celular','impacto_vidrio','—'],
  ['8–11s','En el otro ves la página.','ANIM','H03 anim-sol arriba a la derecha','ui_sparkle','—'],
  ['11–14s','Y no es el brillo:','YO','Tu toma del brillo al máximo','ui_boton','—'],
  ['14–16s','sube el celular al máximo','YO','Punch-in sobre el dedo en el deslizador','ui_click','—'],
  ['16–18s','y sigue igual.','ANIM','H03 anim-sol, otra variante','riser_sweep_1','sube a −18 dB'],
  ['18–21s','Uno tira luz hacia ti.','YO','Plano medio con el sol de fondo','transicion_corte_2','—'],
  ['21–24s','El otro deja que el sol le pegue,','PIP','P03 arriba a la izquierda','camara_flash','—'],
  ['24–26s','como a una hoja.','YO','Primer plano: sostienes el aparato plano, como una hoja','whoosh_metal','—'],
  ['26–29s','Escríbeme si lees afuera.','ANIM','tarjeta-cta','tada_cierre','fade out']]},

{n:32,t:'Vendo estos y no te vendo el caro',rum:81,bloque:'Rompe-creencias',hook:'talking',hooksegs:0,cierresegs:0,
 hooktxt:'Directo a cámara. La frase contradice lo que se espera de un vendedor',
 utileria:['Dos modelos sobre la mesa: uno de gama alta y uno medio — toma 3'],
 set:['Fondo limpio, tu setup habitual','Luz a 45°','Arrancas con las manos vacías'],
 tele:'Vendo estos y no te vendo el caro. || Me escriben pidiendo el más caro y les digo que no. Que con ese no van a leer más. || Si vas a leer novelas en la cama, el de arriba no te da nada que el de abajo no te dé. Estás pagando por lo que no vas a usar. || Prefiero que compres el que te sirve y vuelvas, a venderte uno caro y que se te quede guardado. || Dime qué lees y te digo cuál NO comprar.',
 tomas:[
  ['0–3s','Plano medio · HOOK','Mirada fija, sin gestos. La frase sola hace el trabajo. Pausá después de "caro".','Vendo estos y no te vendo el caro.'],
  ['3–14s','Mismo plano','Niegas con la cabeza en "les digo que no".','Me escriben pidiendo el más caro y les digo que no. Que con ese no van a leer más.'],
  ['14–26s','Plano medio · con los dos','Levantas los dos aparatos, uno en cada mano, y los comparas a la vista.','Si vas a leer novelas en la cama, el de arriba no te da nada que el de abajo no te dé. Estás pagando por lo que no vas a usar.'],
  ['26–36s','Plano cerrado','Dejas el caro fuera de cuadro. Te quedas con el que sí recomiendas.','Prefiero que compres el que te sirve y vuelvas, a venderte uno caro y que se te quede guardado.'],
  ['36–40s','Plano medio · CIERRE','Vuelves a la postura del arranque, manos vacías.','Dime qué lees y te digo cuál NO comprar.']],
 tl:[
  ['0–3s','Vendo estos y no te vendo el caro.','YO','Tú solo + banner de hook','impacto_bang_cine','—'],
  ['3–6s','Me escriben pidiendo el más caro','YO','Niegas con la cabeza','—','entra 03-corporate a −21 dB'],
  ['6–8s','y les digo que no.','ANIM','H07 destello mientras niegas','pop','—'],
  ['8–11s','Que con ese no van a leer más.','YO','Punch-in','impacto_hit_3','—'],
  ['11–14s','Si vas a leer novelas en la cama,','B-ROLL','F05 a pantalla completa','whoosh_deep_1','—'],
  ['14–17s','el de arriba no te da nada','YO','Levantas los dos aparatos, uno en cada mano','whoosh_swish_1','—'],
  ['17–20s','que el de abajo no te dé.','ANIM','H02 comparativa — la arma el pipeline solo con las specs del catálogo','riser_cortado','sube a −19 dB'],
  ['20–23s','Estás pagando por lo que no vas a usar.','YO','Punch-in sobre el aparato caro','impacto_grave_2','—'],
  ['23–26s','Prefiero que compres el que te sirve y vuelvas,','YO','Dejas el caro fuera de cuadro','transicion_corte','—'],
  ['26–29s','a venderte uno caro','PIP','P02 arriba a la izquierda','camara_click_5','—'],
  ['29–31s','y que se te quede guardado.','ANIM','H07 bandera: mejor que vuelvas','reverso_4','—'],
  ['31–34s','Dime qué lees y te digo cuál NO comprar.','ANIM','tarjeta-cta','tada_cierre','fade out']]}
];

const HOOKLBL={fisico:['h-fisico','⚡ Hook físico'],objeto:['h-objeto','📦 Hook con objeto'],
 accion:['h-accion h-objeto','💧 Hook de acción'],talking:['h-talking','🎤 Hook directo']};
const PILL={YO:'pillYO','PIP':'pillPIP','B-ROLL':'pillBR','ANIM':'pillAN'};
// deriva de la linea de tiempo que clips de Flow usa el guion — nunca se desincroniza
function clipsDe(g){const s=new Set();
 g.tl.forEach(r=>(r[3].match(/\b[FP]\d\d\b/g)||[]).forEach(m=>s.add(m)));
 return [...s].sort();}

/* ══════════ PERSISTENCIA DE PROMPTS Y EDICIÓN DE GUIONES ══════════ */
function esClipHecho(clipName){
  return localStorage.getItem('deviceshop_clip_hecho_' + clipName) === '1';
}

function toggleClipHecho(clipName, checked){
  if(checked){
    localStorage.setItem('deviceshop_clip_hecho_' + clipName, '1');
  } else {
    localStorage.removeItem('deviceshop_clip_hecho_' + clipName);
  }
  document.querySelectorAll(`.chk-clip-${clipName}`).forEach(chk=>{
    chk.checked = checked;
    const card = chk.closest('.pr');
    if(card) card.classList.toggle('hecho', checked);
  });
}

let guionSeleccionado = null; // null = ver resumen de todos, N = ver página completa del guion N
const estadoEditoresGuion = {};

function seleccionarGuion(n, ri){
  guionSeleccionado = n;
  renderGuiones();
  if(n !== null){
    if(ri != null){
      setTimeout(()=>{
        const fila = document.getElementById('tl-' + n + '-' + ri);
        if(fila){
          document.querySelectorAll('tr.tlmarca').forEach(t=>t.classList.remove('tlmarca'));
          fila.classList.add('tlmarca');
          fila.scrollIntoView({behavior:'smooth', block:'center'});
        }
      }, 50);
    } else {
      window.scrollTo({top: 0, behavior: 'smooth'});
    }
  } else {
    window.scrollTo({top: 0, behavior: 'smooth'});
  }
}

function irAGuion(n, ri){
  irA('guiones');
  seleccionarGuion(n, ri);
}

function renderTabsGuiones(){
  let html = `<div class="guion-tabs">
    <button class="guion-tab-btn ${guionSeleccionado === null ? 'on' : ''}" onclick="seleccionarGuion(null)">📋 Ver todos los guiones (10)</button>`;
  G.forEach(g => {
    html += `<button class="guion-tab-btn ${guionSeleccionado === g.n ? 'on' : ''}" onclick="seleccionarGuion(${g.n})">🎬 Guion ${g.n}</button>`;
  });
  html += `</div>`;
  return html;
}

function renderPromptsParaGuion(g){
  const clips = clipsDe(g);
  return clips.map(id => {
    const info = CLIPS[id];
    if(!info) return '';
    const archivo = info[0];
    const p = P.find(x => x[0] === archivo);
    if(!p){
      return `<div class="pr ${esClipHecho(archivo) ? 'hecho' : ''}" id="pr-g-${g.n}-${archivo}">
        <div class="prcab">
          <label class="chk-hecho-lbl">
            <input type="checkbox" class="chk-clip-${archivo}" ${esClipHecho(archivo) ? 'checked' : ''} onchange="toggleClipHecho('${archivo}', this.checked)">
            ☑ Ya tengo el video
          </label>
          <div class="prinfo" style="margin-left:10px;"><b>${info[1]}</b><span><span class="codref">${id}</span> · <span class="archivo">${archivo}.mp4</span></span></div>
          <span class="modelo mF">Metraje Real</span>
          <button class="archivo" onclick="event.stopPropagation();cp(this,'${archivo}.mp4')" title="Copiar nombre de archivo">💾 ${archivo}.mp4</button>
        </div>
        ${RESUMEN[archivo] ? `<div class="resumen-es">🇪🇸 <b>En español:</b> ${RESUMEN[archivo]}</div>` : ''}
      </div>`;
    }
    const i = P.indexOf(p);
    const esProd = p.length > 6, foto = esProd ? p[5] : null, txt = esProd ? p[6] : p[5];
    return `<div class="pr ${esClipHecho(archivo) ? 'hecho' : ''}" id="pr-g-${g.n}-${archivo}">
      <div class="prcab">
        <label class="chk-hecho-lbl">
          <input type="checkbox" class="chk-clip-${archivo}" ${esClipHecho(archivo) ? 'checked' : ''} onchange="toggleClipHecho('${archivo}', this.checked)">
          ☑ Ya tengo el video
        </label>
        <div class="orden" style="margin-left:8px;">${i + 1}</div>
        <div class="prinfo"><b>${p[4].replace(/\s*·\s*(\d+\s*)?guion(es)?[\s\d,y]*$/i, '')}</b><span>${p[3]} · tanda ${p[2]} · en este guion es <span class="codref">${id}</span></span></div>
        <span class="modelo ${esProd ? 'mQ' : 'mF'}">${esProd ? 'Veo 3.1 Quality' : 'Veo 3.1 Fast'}</span>
        <button class="archivo" onclick="event.stopPropagation();cp(this,'${archivo}.mp4')" title="Copiar nombre de archivo">💾 ${archivo}.mp4</button>
      </div>
      ${foto ? `<div class="foto">📎 <b>Frames to Video</b> — sube esta foto: <code>assets/productos/${foto}</code> <button class="btn sec" onclick="cp(this,'assets\\productos\\${foto.replace(/\//g, '\\')}')">Copiar ruta</button></div>` : ''}
      ${RESUMEN[archivo] ? `<div class="resumen-es">🇪🇸 <b>En español:</b> ${RESUMEN[archivo]}</div>` : ''}
      <pre class="p" id="txt-g-${g.n}-${archivo}">${txt.replace(/</g, '&lt;')}</pre>
      <div class="pracc">
        <button class="btn" onclick="cp(this,document.getElementById('txt-g-${g.n}-${archivo}').textContent)">📋 Copiar prompt</button>
        <button class="btn sec" onclick="cp(this,'${archivo}.mp4')">Copiar nombre de archivo</button>
      </div>
    </div>`;
  }).join('');
}

function formatearTeleParaEditor(tele){
  return (tele || '').split(' || ').join('\n\n// pausá //\n\n');
}

function toggleEditorGuion(n){
  estadoEditoresGuion[n] = !estadoEditoresGuion[n];
  const caja = document.getElementById('editor-guion-caja-' + n);
  if(caja){
    caja.style.display = estadoEditoresGuion[n] ? 'block' : 'none';
  }
}

function actualizarTextosGuion(g, nuevoTeleRaw){
  let parrafos = nuevoTeleRaw
    .replace(/\/\/\s*pausá\s*\/\//gi, ' || ')
    .split(/\s*\|\|\s*|\n\s*\n+/)
    .map(p => p.trim())
    .filter(Boolean);

  if (parrafos.length === 0) return;

  const nuevoTele = parrafos.join(' || ');
  g.tele = nuevoTele;

  // Actualizar g.tomas
  if (g.tomas && g.tomas.length > 0) {
    if (parrafos.length === g.tomas.length) {
      for (let k = 0; k < g.tomas.length; k++) {
        g.tomas[k][3] = parrafos[k];
      }
    } else {
      const parrafosPorToma = Math.ceil(parrafos.length / g.tomas.length);
      for (let k = 0; k < g.tomas.length; k++) {
        const sub = parrafos.slice(k * parrafosPorToma, (k + 1) * parrafosPorToma);
        if (sub.length > 0) {
          g.tomas[k][3] = sub.join(' ');
        }
      }
    }
  }

  // Actualizar g.tl (Línea de tiempo)
  const frases = nuevoTele
    .replace(/ \|\| /g, ' ')
    .split(/(?<=[.?!])\s+/)
    .map(s => s.trim())
    .filter(Boolean);

  if (frases.length > 0 && g.tl && g.tl.length > 0) {
    if (frases.length === g.tl.length) {
      for (let r = 0; r < g.tl.length; r++) {
        g.tl[r][1] = frases[r];
      }
    } else {
      const frasesPorFila = Math.max(1, Math.round(frases.length / g.tl.length));
      for (let r = 0; r < g.tl.length; r++) {
        const start = r * frasesPorFila;
        if (start < frases.length) {
          const sub = (r === g.tl.length - 1) ? frases.slice(start) : frases.slice(start, start + frasesPorFila);
          g.tl[r][1] = sub.join(' ');
        }
      }
    }
  }
}

async function guardarEdicionGuion(n){
  const input = document.getElementById('editor-guion-input-' + n);
  const estado = document.getElementById('editor-guion-estado-' + n);
  if(!input) return;

  const rawText = input.value.trim();
  if(!rawText){
    if(estado){ estado.textContent = 'El texto no puede estar vacío'; estado.className = 'hookseg-estado mal'; }
    return;
  }

  if(estado){ estado.textContent = 'Guardando…'; estado.className = 'hookseg-estado'; }

  let parrafos = rawText
    .replace(/\/\/\s*pausá\s*\/\//gi, ' || ')
    .split(/\s*\|\|\s*|\n\s*\n+/)
    .map(p => p.trim())
    .filter(Boolean);

  if(parrafos.length === 0){
    if(estado){ estado.textContent = 'Sin párrafos válidos'; estado.className = 'hookseg-estado mal'; }
    return;
  }

  const nuevoTele = parrafos.join(' || ');
  const g = G.find(x => x.n === n);
  if(!g) return;

  actualizarTextosGuion(g, nuevoTele);

  let guardadoEnDisco = false;

  try {
    const resp = await fetch('/guardar-guion-tele', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ guion: n, tele: nuevoTele })
    });
    if(resp.ok){
      const resJson = await resp.json();
      if(resJson.ok) guardadoEnDisco = true;
    }
  } catch(e) {}

  if(!guardadoEnDisco){
    try {
      const handle = await conseguirManejoArchivo();
      if(handle){
        const file = await handle.getFile();
        const textoFile = await file.text();
        const teleEscaped = nuevoTele.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const re = new RegExp(`(\\{n:${n},[^\\n]*?tele:')([\\s\\S]*?)(')`);
        if(re.test(textoFile)){
          const nuevoHtml = textoFile.replace(re, (_, pre) => pre + teleEscaped + "'");
          const writable = await handle.createWritable();
          await writable.write(nuevoHtml);
          await writable.close();
          guardadoEnDisco = true;
        }
      }
    } catch(e) {}
  }

  renderGuiones();

  const modal = document.getElementById('telemodal');
  if(modal && modal.classList.contains('on')){
    teleCargarGuion(n);
  }

  setTimeout(()=>{
    const nuevoEstado = document.getElementById('editor-guion-estado-' + n);
    if(nuevoEstado){
      nuevoEstado.textContent = guardadoEnDisco ? '✓ Guardado y actualizado en toda la página' : '✓ Actualizado en pantalla';
      nuevoEstado.className = 'hookseg-estado ok';
      setTimeout(()=>{
        nuevoEstado.textContent = '';
        nuevoEstado.className = 'hookseg-estado';
      }, 3000);
    }
  }, 50);
}

function renderGuiones(){
  const cont = document.getElementById('guiones');
  let html = renderTabsGuiones();

  if(guionSeleccionado === null){
    // Vista general de todos los guiones
    html += G.map((g, i) => {
      const hk = HOOKLBL[g.hook];
      return `<div class="guion" id="g-${g.n}">
       <div class="gcab" onclick="seleccionarGuion(${g.n})">
         <div class="gnum">${g.n}</div>
         <div class="gtit"><b>${g.t}</b><span>${g.bloque} · ${g.tomas.length} tomas · ${g.hooktxt}</span></div>
         <span class="tipohook ${hk[0]}">${hk[1]}</span>
         <span class="rum">RUM ${g.rum}%</span>
       </div>
       <div class="gbody" style="display:block;">
         <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
           <button class="btn ok" style="padding:9px 18px; font-size:14px; font-weight:800;" onclick="seleccionarGuion(${g.n})">📖 Abrir Página del Guion ${g.n}</button>
           <button class="btn ok" style="background:#0e2a38; border-color:var(--cian); color:var(--cian); font-weight:700; padding:8px 14px;" onclick="abrirTeleprompter(${g.n})">📺 Teleprompter</button>
         </div>
         <h4>🎒 Utilería</h4>
         <div class="setup">${g.utileria.map(s=>`<span class="chip util">${s}</span>`).join('')}</div>
         <h4>💡 Set y luz</h4>
         <div class="setup">${g.set.map(s=>`<span class="chip">${s}</span>`).join('')}</div>
       </div></div>`;
    }).join('');
  } else {
    // Página completa del guion seleccionado
    const g = G.find(x => x.n === guionSeleccionado);
    if(g){
      const i = G.indexOf(g);
      const hk = HOOKLBL[g.hook];
      const ar = clipsDe(g).map(id => CLIPS[id][0]).filter(a => P.some(p => p[0] === a));

      html += `<div class="guion-pagina-unica" id="g-pag-${g.n}">
        <div class="guion-header-barra">
          <button class="btn sec" onclick="seleccionarGuion(null)">← Ver todos los guiones</button>
          <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
             <div class="gnum" style="min-width:38px; height:38px; font-size:16px;">${g.n}</div>
             <h3 style="margin:0; font-size:19px; color:var(--blanco);">${g.t}</h3>
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
             <span class="tipohook ${hk[0]}">${hk[1]}</span>
             <span class="rum">RUM ${g.rum}%</span>
          </div>
        </div>

        <div class="guion abierto" style="border:1px solid var(--linea); border-radius:11px; margin:0;">
          <div class="gbody" style="display:block; padding:18px;">
            <h4>🎒 Utilería · esto tienes que tenerlo de verdad</h4>
            <div class="setup">${g.utileria.map(s=>`<span class="chip util">${s}</span>`).join('')}</div>

            <h4>💡 Set y luz</h4>
            <div class="setup">${g.set.map(s=>`<span class="chip">${s}</span>`).join('')}</div>

            <h4>🚫 Esto NO lo grabas · sale de Google Flow</h4>
            <div class="setup">${clipsDe(g).map(id=>`<span class="chip noGrabar" onclick="irAPrompt('${id}')"
               title="Ir al prompt de este clip">${c(id)}
               <span class="archchip">${CLIPS[id][0]}.mp4</span>
               <span class="descchip">${CLIPS[id][1]}</span>
               <span class="flecha">→</span></span>`).join('')}</div>
            <p class="notaflow">No consigas nada de esto para grabar: son clips generados que el pipeline inserta encima de tu video.</p>

            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:14px;">
              <button class="btn ok" style="background:#0e2a38; border-color:var(--cian); color:var(--cian); font-weight:700; padding:10px 18px; font-size:14px;" onclick="abrirTeleprompter(${g.n})">
                📺 Abrir Teleprompter Tablet (Guion ${g.n})
              </button>
              ${ar.length > 0 ? `<button class="btn sec" style="padding:10px 16px;" onclick="verGuion(${g.n})">
                ⚡ Ver ${ar.length} prompts en Flow
              </button>` : ''}
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:22px; margin-bottom:8px;">
              <h4 style="margin:0;">Teleprompter</h4>
              <button class="btn ok" style="padding:6px 14px; font-size:13px; font-weight:700;" onclick="event.stopPropagation(); toggleEditorGuion(${g.n})">
                ✏️ Editar Texto del Guion
              </button>
            </div>

            <div class="tele" id="tele-box-${g.n}">
              <button class="copiar" onclick="cp(this,G[${i}].tele.replace(/ \|\| /g,'\n\n'))">Copiar</button>
              ${g.tele.split(' || ').map(p => p).join('<br><span class="pausa">// pausá //</span><br>')}
            </div>

            <div id="editor-guion-caja-${g.n}" class="caja-editor-guion" style="display:${estadoEditoresGuion[g.n] ? 'block' : 'none'}; margin:12px 0 20px; background:#071a26; border:1.5px solid var(--cian); border-radius:10px; padding:16px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <b style="color:var(--cian); font-size:14px;">✏️ Editar Frases y Párrafos del Guion ${g.n}</b>
                <span style="font-size:12.5px; color:var(--txt2);">Al guardar, se actualizarán las tomas, la línea de tiempo y el teleprompter automáticamente.</span>
              </div>
              <textarea id="editor-guion-input-${g.n}" rows="9" style="width:100%; box-sizing:border-box; background:#040e16; color:#fff; border:1px solid var(--linea); border-radius:8px; padding:12px; font-size:15px; font-family:inherit; line-height:1.6; resize:vertical;">${formatearTeleParaEditor(g.tele)}</textarea>
              <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:12px;">
                <button class="btn ok" style="padding:9px 20px; font-weight:800; font-size:14px;" onclick="guardarEdicionGuion(${g.n})">
                  💾 Guardar y actualizar en toda la página
                </button>
                <button class="btn sec" style="padding:9px 16px;" onclick="toggleEditorGuion(${g.n})">
                  ❌ Cancelar
                </button>
                <span class="hookseg-estado" id="editor-guion-estado-${g.n}"></span>
              </div>
            </div>

            <h4>Tomas · graba en este orden</h4>
            ${g.tomas.map(t=>`<div class="tnum">${t[0]}</div><div class="tdesc"><b>${t[1]}</b><p>${t[2]}</p><p class="dice">"${t[3]}"</p></div>`).join('')}

            <h4>Línea de tiempo · esto es 100% automático</h4>
            <p class="notaflow" style="margin:0 0 8px">Nada de esta tabla lo haces tú: son las decisiones que ejecuta el pipeline sobre tu grabación. La columna "En pantalla" dice de dónde sale la imagen — <b>YO</b> es tu video crudo.</p>
            <div class="tablawrap">
            <table><tr><th>Momento</th><th style="min-width:210px">Qué estoy diciendo</th><th>En pantalla</th><th>Qué se ve</th><th>Sonido</th><th>Música</th></tr>
            ${g.tl.map((r,ri)=>`<tr id="tl-${g.n}-${ri}"><td>${r[0]}</td>
               <td class="digo">"${r[1]}"</td>
               <td><span class="${PILL[r[2]]}">${r[2]}</span></td>
               <td>${r[3].replace(/(F\d\d|P\d\d|H\d\d)/g,m=>c(m))}</td>
               <td class="sfx">${r[4]}</td><td class="sfx">${r[5]}</td></tr>`).join('')}
            </table></div>

            <!-- CONFIGURACIÓN DE SILENCIOS FÍSICOS (HOOK Y CIERRE UNO DEBAJO DE OTRO) -->
            <div class="caja-config-fisico">
              <h4>⏱️ Configuración de Silencios Físicos (Hook y Cierre)</h4>
              
              <div class="bloque-fisico">
                <h5>⚡ Hook físico · lo único que el corte NO se lleva</h5>
                <p class="notaflow" style="margin:0 0 8px">El pipeline corta todos los silencios. Se conserva el silencio justo antes de tu primera palabra ("${g.hooktxt.toLowerCase()}"). Ajusta los segundos aquí abajo y guarda:</p>
                <div class="hooksegs-editor" onclick="event.stopPropagation()">
                  <label class="notaflow" style="margin:0; font-weight:700;" for="hooksegs-${g.n}">Segundos de hook a conservar:</label>
                  <input type="number" id="hooksegs-${g.n}" min="0" max="8" step="0.5" value="${g.hooksegs}">
                  <button class="btn sec" onclick="guardarSegundosGuion(${g.n},'hooksegs')">💾 Guardar en el archivo</button>
                  <span class="hookseg-estado" id="hooksegs-estado-${g.n}"></span>
                </div>
              </div>

              <div class="bloque-fisico" style="margin-top:14px;">
                <h5>🏁 Cierre físico · lo único que el corte NO se lleva (al final)</h5>
                <p class="notaflow" style="margin:0 0 8px">El gesto de salida al finalizar la última palabra. Ajusta los segundos a conservar después de hablar y guarda:</p>
                <div class="hooksegs-editor" onclick="event.stopPropagation()">
                  <label class="notaflow" style="margin:0; font-weight:700;" for="cierresegs-${g.n}">Segundos de cierre a conservar:</label>
                  <input type="number" id="cierresegs-${g.n}" min="0" max="8" step="0.5" value="${g.cierresegs}">
                  <button class="btn sec" onclick="guardarSegundosGuion(${g.n},'cierresegs')">💾 Guardar en el archivo</button>
                  <span class="hookseg-estado" id="cierresegs-estado-${g.n}"></span>
                </div>
              </div>
            </div>

            <!-- PROMPTS DE ESTE GUION CON CHECKBOX Y PERSISTENCIA -->
            <div class="caja-prompts-guion" style="margin-top:30px; padding-top:20px; border-top:2px solid var(--cian);">
              <h4 style="font-size:16px;">🎨 Prompts de Google Flow para este Guion (${clipsDe(g).length} clips)</h4>
              <p class="notaflow" style="margin-bottom:14px;">Genera estos clips en Google Flow y guárdalos en <code>assets/generado/video/manual/</code>. Marca el checkbox para llevar el control.</p>
              <div class="prompts-guion-lista">
                ${renderPromptsParaGuion(g)}
              </div>
            </div>

          </div></div></div>`;
    }
  }

  cont.innerHTML = html;
}

/* ═══════════ PROMPTS ═══════════ */
// La pantalla e-ink es MATE. Sin esto Veo la renderiza como LCD quemado y la
// convierte en la fuente de luz de la escena (fallo real y repetido en P02).
const EINK_SUP=`The screen is a matte, non-reflective, paper-like electronic ink surface, not a glossy backlit tablet display: its page background is a soft light warm tone, never pure white and never blown out. Any light on it is a low, soft, perfectly even warm frontlight that leaves the text crisp, dark and readable at all times: no bright white glare, no harsh backlight bloom, no halo, no glowing hotspot, no specular highlight and no mirror reflections on it.`;
// Un solo lado tiene pantalla. Orbitar el aparato hacía que Veo le inventara una
// segunda pantalla en el dorso (fallo real en P02). Se afirma primero, se prohíbe después.
const UNA_CARA=`The device has exactly one screen and it is on the front face only: its back is a plain matte solid panel with no screen, no glass and no display of any kind. Only that front face is ever visible: the device never turns around, never flips and never shows its back, and the camera never travels behind it.`;
const BLIND_BN=`Its screen is a black and white electronic ink display showing a page of a Spanish-language novel: several justified paragraphs of small dark grey Spanish body text on a light warm grey background, with clean margins, exactly like printed prose, with no colour whatsoever on the screen. That page is a flat image rendered on the glass, never physical paper: the screen stays perfectly rigid and flat at all times, and nothing ever lifts, peels, curls, flies or emerges from it. No loose sheets, no paper, no book pages turning. The content on the screen is completely static and frozen: it never changes, never scrolls, and there is no page-turn animation, no sliding, no fading, no dissolve and no transition of any kind, because a real e-ink screen does not animate smoothly. It is a solid flat slab, not a book, and it never bends, folds or opens. ${EINK_SUP}`;
const BLIND_COL=`Its screen is a colour electronic ink display, with the soft muted pastel tones typical of colour e-ink rather than the vivid saturation of an LCD, showing a page of a Spanish-language illustrated book: a colour illustration above several justified paragraphs of small dark Spanish body text, with clean margins, exactly like a printed page. That page is a flat image rendered on the glass, never physical paper: the screen stays perfectly rigid and flat at all times, and nothing ever lifts, peels, curls, flies or emerges from it. No loose sheets, no paper, no book pages turning. The content on the screen is completely static and frozen: it never changes, never scrolls, and there is no page-turn animation, no sliding, no fading, no dissolve and no transition of any kind, because a real e-ink screen does not animate smoothly. It is a solid flat slab, not a book, and it never bends, folds or opens. ${EINK_SUP}`;
const MARCO=`Keep the device exactly as shown: do not alter its shape, proportions, colour or body. Its frame stays completely smooth, blank and unmarked, with no brand name, no logo, no lettering and no engraving anywhere on it. ${UNA_CARA}`;
const CIERRE=`No added text outside the screen, no logos, no watermark. No dialogue, no voiceover,`;

const P=[
/* --- CUENTA A · tanda 1 --- */
['scroll','A','1','Ambiente','El pulgar infinito · 10 guiones',
`Vertical 9:16. Extreme close-up of a thumb endlessly scrolling on a smartphone screen in a dark room, the screen's blue-white glow flickering across the skin, the motion repetitive and hypnotic, slight slow motion. Shot on a 50mm lens, shallow depth of field, moody low-key lighting, natural editorial photography. Camera slowly pushes in. The phone body is completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving anywhere on it. The screen is a flat rigid glass surface showing only an indistinct blur of coloured light, and it stays perfectly flat at all times: nothing ever lifts, peels, curls, flies or emerges from it. No paper, no sheets, no physical pages. No readable text, no icons, no interface, no watermark. No dialogue, no voiceover, ambient room tone only.`],
['ojos','A','1','Ambiente','Vista cansada · 6 guiones',
`Vertical 9:16. Intimate close-up of tired eyes at night, a person slowly rubbing them with the heel of the hand, blinking heavily, faint blue screen light on the face. Warm dark bedroom in the background, out of focus. Shot on an 85mm lens, shallow depth of field, natural editorial photography, soft realistic skin. Subtle handheld camera. Face partially in shadow, not a recognizable person. No text, no lettering, no logos, no watermark. No dialogue, no voiceover, quiet room tone only.`],
['noche','A','1','Ambiente','Cara iluminada por el celular · 6 guiones',
`Vertical 9:16. A person lying in bed in a completely dark bedroom, face lit only by the harsh blue-white glow of a phone held above them, the light carving hard shadows. Slow, still, uncomfortable mood. Shot on a 35mm lens, shallow depth of field, cinematic low-key lighting, natural editorial photography. Camera very slowly drifts closer. The phone body is completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving. The screen is a flat rigid glass surface showing only formless glowing light, and it stays perfectly flat at all times: nothing ever lifts, peels, curls, flies or emerges from it. No paper, no sheets, no physical pages. No readable text, no interface, no watermark. No dialogue, no voiceover, only faint night ambience.`],
['libros','A','1','Ambiente','La pila pesada · 8 guiones',
`Vertical 9:16. A tall heavy stack of thick hardcover paper books on a wooden table, dramatic warm side light raking across the spines and dust in the air, one hand entering frame to lift the top book and feel its weight. Shot on a 50mm lens, shallow depth of field, natural editorial photography, soft warm daylight from a window. Slow dolly around the stack. Real physical paper books only, no electronic devices anywhere in frame. Covers are plain with no readable titles, no text, no logos, no watermark. No dialogue, no voiceover, subtle paper sounds only.`],
['biblioteca','A','1','Ambiente','Estanterías infinitas · 7 guiones',
`Vertical 9:16. Slow upward tilt along towering library shelves packed with books, warm golden light falling from high windows, dust floating in the beams, the shelves seeming to continue endlessly. Shot on a wide 24mm lens, deep warm tones, natural editorial photography, cinematic. Smooth vertical camera movement. Spines are plain with no readable titles, no text, no lettering, no logos, no watermark, no people, no electronic devices. No dialogue, no voiceover, quiet library ambience only.`],
['abandonado','A','1','Ambiente','El libro de la página 30 · 5 guiones',
`Vertical 9:16. A closed paper book lying forgotten on a bedside table with a bookmark stuck a third of the way in, a thin layer of dust on the cover, soft grey afternoon light from a nearby window, everything still and slightly melancholic. Shot on an 85mm macro lens, very shallow depth of field, natural editorial photography. Camera creeps slowly toward the bookmark. The book stays completely closed and still. Plain cover with no readable title, no text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, silent room tone only.`],
['notificaciones','A','1','Ambiente','El bombardeo · 4 guiones',
`Vertical 9:16. Abstract visualization of relentless digital interruption: dozens of soft glowing rounded rectangles crowding the frame like a swarm, blurred and out of focus, cool blue and white light, overwhelming and claustrophobic. The frame is already packed with them in the very first frame: the swarm starts at its densest and never builds up from an empty or nearly empty screen, and more keep pouring in from the edges the whole time. Cinematic, elegant, minimal, shallow depth of field. Camera slowly pulls back as more of them pour in. The shapes are completely blank: no text, no icons, no symbols, no letters, no numbers, no logos, no watermark. No dialogue, no voiceover, subtle rising hum only.`],
['insomnio','A','1','Ambiente','Las 3:47 de la mañana · 3 guiones',
`Vertical 9:16. A person turning restlessly under the covers in a dark bedroom, unable to sleep, then a digital alarm clock on the nightstand glowing faintly in the dark. Cold blue night tones, deep shadows. Shot on a 35mm lens, shallow depth of field, cinematic natural editorial photography. Slow handheld drift toward the clock. The clock display is blurred and unreadable: no text, no numbers, no lettering, no logos, no watermark. No dialogue, no voiceover, only faint night ambience.`],
/* --- CUENTA A · tanda 2 --- */
['regalo','A','2','Ambiente','La caja con moño · 4 guiones',
`Vertical 9:16. A small elegant gift box with a satin ribbon resting on a table, warm golden light, hands entering frame to slowly untie the bow with anticipation. Soft festive bokeh in the far background. Shot on a 50mm lens, shallow depth of field, natural editorial photography, warm inviting mood. Slow push in. The box stays closed. Completely plain box with no text, no labels, no lettering, no logos, no watermark, no brand names. No dialogue, no voiceover, gentle paper and ribbon sounds only.`],
['caja','A','2','Ambiente','El desempaque · 2 guiones',
`Vertical 9:16. Close-up of a clean plain cardboard box on a table, its tape already cut and hands already lifting the flap open in the very first frame, revealing soft protective foam inside, warm daylight from a side window, satisfying unboxing mood. The box is already being opened when the clip starts: the video never opens on a closed untouched box and never waits for the tape to be cut. Shot on a 50mm lens, shallow depth of field, natural editorial photography. Slow overhead push in. Nothing is taken out of the box. The cardboard is completely blank with no printing, no text, no lettering, no labels, no logos, no watermark. No dialogue, no voiceover, cardboard and tape sounds only.`],
['vitrina','A','2','Ambiente','No saber qué regalar · 4 guiones',
`Vertical 9:16. A person standing in a bright store aisle seen from behind, shoulders slumped, hesitating with empty hands in front of shelves of generic products, clearly unable to decide. Soft diffused retail lighting, slightly desaturated. Shot on a 35mm lens, shallow depth of field, natural editorial photography, candid documentary feel. Subtle handheld camera. Face not visible. Products blurred and completely plain: no packaging text, no signage, no lettering, no logos, no watermark. No dialogue, no voiceover, faint store ambience only.`],
['tiempo','A','2','Ambiente','El tiempo que se va · 3 guiones',
`Vertical 9:16. Extreme close-up of fine sand streaming through the narrow waist of an hourglass, backlit by warm golden light, individual grains catching the light, dark background. Slow motion, hypnotic and slightly melancholic. Shot on a 100mm macro lens, very shallow depth of field, cinematic natural editorial photography. Camera almost still, barely drifting. No text, no numbers, no lettering, no logos, no watermark. No dialogue, no voiceover, soft ambient tone only.`],
['bateria','A','2','Ambiente','El 1% · 3 guiones',
`Vertical 9:16. Close-up of a smartphone lying on a bedside table, its screen already almost black in the very first frame, showing only a faint dying glow, a tangled charging cable just out of reach beside it. The phone is already dying when the clip starts: the video never opens on a bright screen. Dim warm bedroom light, night mood. Shot on an 85mm lens, very shallow depth of field, natural editorial photography. Slow push in as the last of the glow fades. The phone body is completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving. The screen is a flat rigid glass surface, blurred and unreadable, and it stays perfectly flat at all times: nothing ever lifts, peels, curls, flies or emerges from it. No paper, no sheets, no physical pages, no icons, no text, no watermark. No dialogue, no voiceover, silence with faint room tone.`],
['entrega','A','2','Ambiente','La moto en la ciudad · 3 guiones',
`Vertical 9:16. A delivery motorcycle weaving through warm sunlit city traffic in a Latin American city, tropical trees and low buildings, dust and golden late afternoon light, a small plain package secured on the back. Energetic, fast, real. Shot on a 35mm lens, handheld tracking shot following the bike, natural editorial photography, documentary feel. Rider's face not visible. No visible brands, no text, no signage, no lettering, no logos, no watermark. No dialogue, no voiceover, street and engine ambience only.`],
['ninos-pantalla','A','2','Ambiente','El niño a las 11 de la noche · 3 guiones',
`Vertical 9:16. A child in a dark bedroom at night, face lit only by the cold blue glow of a tablet held close, eyes wide and unblinking, room completely dark around them. Still, quiet, unsettling. Shot on a 50mm lens, shallow depth of field, cinematic low-key lighting, natural editorial photography. Camera slowly pushes in. Face partly in shadow and not clearly identifiable. The tablet body is completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving. Its screen is a flat rigid glass surface showing only formless glowing light, and it stays perfectly flat at all times: nothing ever lifts, peels, curls, flies or emerges from it. No paper, no sheets, no physical pages, no readable text, no icons, no watermark. No dialogue, no voiceover, silent night ambience.`],
['ninos-leyendo','A','2','Ambiente','El niño que sí lee · 3 guiones',
`Vertical 9:16. A child curled up in an armchair by a window on a bright afternoon, absorbed in reading a paper book, warm natural daylight and soft shadows, cozy living room, a small smile. Shot on a 50mm lens, shallow depth of field, natural editorial photography, warm and hopeful mood. Gentle slow dolly in. A real physical paper book only, no electronic devices anywhere in frame. Face soft and not clearly identifiable. No readable text, no lettering, no logos, no watermark. No dialogue, no voiceover, quiet room tone and page turns only.`],
['sol','A','2','Ambiente','El sol que ciega la pantalla · 2 guiones',
`Vertical 9:16. Harsh midday sun over an outdoor table, a hand tilting a glossy dark reflective rectangular slab that mirrors the bright sky and the silhouette of the person holding it, lens flare, intense summer light, tropical greenery blurred behind. Shot on a 50mm lens, shallow depth of field, natural editorial photography, high contrast. Slight handheld movement as the reflection shifts. The slab is completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving. It is flat and rigid and stays perfectly flat at all times: nothing ever lifts, peels, curls, flies or emerges from it. No paper, no sheets, no physical pages, no interface, no text, no watermark. No dialogue, no voiceover, outdoor summer ambience only.`],
['cama','A','2','Ambiente','La cama acogedora · 2 guiones',
`Vertical 9:16. An inviting unmade bed with soft rumpled linen sheets in a warm dim bedroom, a small bedside lamp casting a pool of golden light, evening calm, nobody in frame. Shot on a 35mm lens, shallow depth of field, natural editorial photography, cozy and restful mood. Very slow dolly toward the pillow. No text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, quiet evening room tone only.`],
/* --- CUENTA B · tanda 3 --- */
['agua','B','3','Ambiente','Las gotas · guion 28',
`Vertical 9:16. Extreme slow motion close-up of clear water droplets splashing and beading on a dark matte waterproof surface, bright poolside sunlight, crisp refreshing summer mood, droplets catching the light. Shot on a 100mm macro lens, very shallow depth of field, natural editorial photography. Camera almost static. The surface is completely smooth, blank and unmarked: no brand name, no logo, no lettering, no engraving. No paper, no sheets, no text, no logos, no watermark. No dialogue, no voiceover, water sounds only.`],
['tina','B','3','Ambiente','La bañera · guion 28',
`Vertical 9:16. A warm bathtub filled with foam and steam rising, soft candlelight and a folded towel on the edge, relaxing spa atmosphere, warm amber tones, nobody in frame. Shot on a 35mm lens, shallow depth of field, natural editorial photography, calm and intimate. Slow drift along the edge of the tub. No text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, gentle water ambience only.`],
['piscina','B','3','Ambiente','El verano · guiones 4 y 28',
`Vertical 9:16. Poolside on a bright summer day, turquoise water rippling and reflecting sunlight onto a lounge chair and towel, tropical palm shadows moving across the deck, nobody in frame. Shot on a 35mm lens, shallow depth of field, natural editorial photography, vivid warm summer mood. Slow lateral dolly. No text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, water and distant summer ambience only.`],
['mama','B','3','Ambiente','La lectora en el sillón · guion 15',
`Vertical 9:16. A woman in her fifties sitting in a comfortable armchair by a window, reading peacefully in warm afternoon light, relaxed shoulders, faint smile, plants and a soft home interior blurred behind her. Shot on an 85mm lens, shallow depth of field, natural editorial photography, warm and tender mood. Slow gentle push in. She holds a plain flat rectangular e-reader, completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving on its frame. ${BLIND_BN} Face soft and not clearly identifiable, no logos, no watermark. No dialogue, no voiceover, quiet home ambience only.`],
['pareja','B','3','Ambiente','Uno duerme, el otro lee · guion 6',
`Vertical 9:16. A dark bedroom at night, two people in bed: one asleep facing away, the other propped up awake beside them, careful not to disturb. Only a small warm pool of light on the awake person's side, the rest in deep shadow. Shot on a 35mm lens, shallow depth of field, cinematic low-key lighting, natural editorial photography, intimate and quiet. Camera nearly still. The awake person holds a plain flat rectangular e-reader, completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving on its frame. ${BLIND_BN} Faces not clearly identifiable, no logos, no watermark. No dialogue, no voiceover, soft breathing and night ambience only.`],
['mochila','B','3','Ambiente','El peso del colegio · guion 21',
`Vertical 9:16. A child's overstuffed school backpack sitting on the floor, visibly heavy and bulging with books, a small hand grabbing the strap and struggling to lift it, warm morning light from a hallway window. Shot on a 50mm lens, shallow depth of field, natural editorial photography, candid documentary feel. Low angle, camera static. No visible brands, no text, no lettering, no logos, no watermark. No dialogue, no voiceover, fabric and zipper sounds only.`],
['cafe','B','3','Ambiente','La espera · guion 23',
`Vertical 9:16. A cup of coffee steaming on a small café table by a window, warm morning light, an empty chair opposite, the street softly blurred outside, calm waiting mood. Shot on a 50mm lens, shallow depth of field, natural editorial photography. Slow push in on the rising steam. Plain cup with no branding, no text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, quiet café ambience only.`],
['viaje','B','3','Ambiente','La maleta · guion 25',
`Vertical 9:16. An open suitcase on a bed being packed, hands placing folded clothes inside, warm morning light from a window, travel anticipation mood, plain unbranded luggage. Shot on a 35mm lens, shallow depth of field, natural editorial photography. Slow overhead push in. No text, no tags, no labels, no lettering, no logos, no watermark. No dialogue, no voiceover, fabric and zipper sounds only.`],
['silencio','B','3','Ambiente','El silencio digital · 3 guiones',
`Vertical 9:16. Abstract visualization of digital silence, already calm and almost empty in the very first frame. The video opens on dark quiet space with only four or five soft glowing rounded rectangles left, drifting slowly and dimly, and one small warm amber glow already resting in the centre. Within the first second they start going out: one dims, shrinks and blinks out into the darkness, then another, then another, so that by the second second only one faint shape is still lit. From there the frame stays as calm empty darkness with the single warm amber glow breathing gently in the centre for the rest of the clip. This is the quiet after the noise, never the noise itself: the frame is never crowded and never full, and the shapes only ever disappear. Nothing new ever appears, no shape is ever added, and none of them ever return, multiply or refill the frame. Cinematic, elegant, minimal, shallow depth of field, warm amber calm over deep black. Camera almost still, a very slow push in. The shapes are completely blank: no text, no icons, no symbols, no letters, no numbers, no logos, no watermark. No dialogue, no voiceover, a faint hum already fading into silence.`],
['lluvia','B','3','Ambiente','Lluvia en la ventana · 2 guiones',
`Vertical 9:16. Heavy rain running down a window pane at dusk, the world outside blurred into soft bokeh lights, warm lamp light from inside reflecting on the wet glass, cozy and calm reading mood. Shot on an 85mm lens, very shallow depth of field, natural editorial photography. Camera almost static, drifting slowly along the glass. No text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, gentle rain ambience only.`],
['lampara','B','3','Ambiente','La luz que despierta al otro · guion 6',
`Vertical 9:16. A bedside lamp already switched on in a dark bedroom in the very first frame, its harsh warm light spilling across rumpled sheets and a wall while the rest of the room stays in deep shadow. The intrusive glow is there immediately and at full strength from the first frame, and it stays on for the whole clip: the video never opens in darkness, never fades up from black and never shows the lamp being switched on. The light only flickers and settles very slightly. The contrast between the harshly lit sheets and the black room is the subject. Shot on a 35mm lens, shallow depth of field, cinematic natural editorial photography, high contrast. Camera static, a very slow push in, nobody in frame. No text, no lettering, no logos, no watermark, no electronic devices. No dialogue, no voiceover, quiet room tone only.`],
['rendicion','B','3','Ambiente','Se rinde: suelta el libro por el celular · guion 7',
`Vertical 9:16. Close-up on a person's hands giving up on a paperback, the book already slipping in the very first frame. The video opens with the fingers gone loose and the half-closed book sliding out of the hand, while just beside them a smartphone lies face-up with its screen glowing and flickering insistently. Within the first second the book drops away onto the table and the same hand is already drifting over to the phone; by the second second the hand has reached it and is picking it up, and it stays there with the phone for the rest of the clip. The video never opens on someone reading calmly and it never waits: the hand is already losing the book when the clip starts. Shot on a 50mm lens, shallow depth of field, natural editorial photography, warm room light contrasted with a cool blue glow from the screen. Slow quiet camera push in, the hands doing all the movement. Face and body kept out of frame or in soft shadow, not a recognizable person. The book has a plain cover with no readable title, no text, no lettering, no logos, no watermark. The phone body is completely smooth, blank and unmarked: bare material with no brand name, no logo, no lettering and no engraving anywhere on it. Its screen is a flat rigid glass surface showing only a soft indistinct blur of coloured light, and it stays perfectly flat at all times: nothing ever lifts, peels, curls, flies or emerges from it. No dialogue, no voiceover, quiet room tone with a faint phone vibration only.`],
/* --- CUENTA B · producto --- */
['P01','B','4','Producto·B/N','Lectura en cama de noche · 10 guiones','kindle-paperwhite/frontal-negro.jpg',
`Animate this image. The device rests on a bed in a dark bedroom, lit only by its own soft warm screen glow. A hand enters frame and taps the glass surface once with a fingertip. Very subtle camera push in, shallow depth of field, cinematic low-key lighting, natural editorial photography. ${MARCO} ${BLIND_BN} ${CIERRE} quiet night room tone only.`],
['P03','B','4','Producto·B/N','A pleno sol · 2 guiones','kindle-paperwhite/frontal-negro.jpg',
`Animate this image. The device sits on an outdoor table under harsh bright midday sun, tropical greenery blurred behind, sunlight moving across its surface as leaf shadows drift over it. Slight handheld camera movement, lens flare, high contrast, natural editorial photography. ${MARCO} Its screen is a black and white electronic ink display showing a page of a Spanish-language novel: several justified paragraphs of small dark grey Spanish body text on a light warm grey background, with clean margins, exactly like printed prose, with no colour whatsoever on the screen, perfectly readable in direct sunlight with no glare washing it out. That page is a flat image rendered on the glass, never physical paper: the screen stays perfectly rigid and flat at all times, and nothing ever lifts, peels, curls, flies or emerges from it. No loose sheets, no paper, no book pages turning. The content on the screen is completely static and frozen: it never changes, never scrolls, and there is no page-turn animation, no sliding, no fading, no dissolve and no transition of any kind, because a real e-ink screen does not animate smoothly. It is a solid flat slab, not a book, and it never bends, folds or opens. ${EINK_SUP} ${CIERRE} outdoor summer ambience only.`],
['P04','B','4','Producto·B/N','Verde matcha a oscuras · 3 guiones','kindle-paperwhite/frontal-jade.jpg',
`Animate this image. The device lies in near-total darkness, its warm amber screen glow the only light source, gently illuminating the surface beneath it. A hand enters frame and shifts it slightly. Camera almost static, very shallow depth of field, cinematic low-key lighting, natural editorial photography. ${MARCO} Its screen is a black and white electronic ink display showing a page of a Spanish-language novel: several justified paragraphs of small dark grey Spanish body text on a warm amber-lit background, with clean margins, exactly like printed prose, with no colour whatsoever on the screen. That page is a flat image rendered on the glass, never physical paper: the screen stays perfectly rigid and flat at all times, and nothing ever lifts, peels, curls, flies or emerges from it. No loose sheets, no paper, no book pages turning. The content on the screen is completely static and frozen: it never changes, never scrolls, and there is no page-turn animation, no sliding, no fading, no dissolve and no transition of any kind, because a real e-ink screen does not animate smoothly. It is a solid flat slab, not a book, and it never bends, folds or opens. ${EINK_SUP} ${CIERRE} silent night ambience.`],
['P05','B','4','Producto·B/N','Liviano, una sola mano · 6 guiones','kindle-basic/frontal.png',
`Animate this image. The device is held up in a single hand, its screen facing the camera the whole time, tilting only very slightly at the edge so the thin profile catches the warm window light from the side, softly blurred home interior behind. It is never turned over or rotated to show its back. Smooth slow push in, no orbit and no arc around the device, shallow depth of field, natural editorial photography. ${MARCO} ${BLIND_BN} ${CIERRE} subtle room tone only.`],
['P06','B','4','Producto·B/N','Como regalo · 5 guiones','kindle-paperwhite/frontal-raspberry.jpg',
`Animate this image. The device rests on a table beside a satin ribbon and soft festive bokeh lights, warm golden hour light, hands entering frame to slide it gently toward the camera as a gift. Slow push in, shallow depth of field, natural editorial photography, warm celebratory mood. ${MARCO} ${BLIND_BN} ${CIERRE} soft ribbon sounds only.`],
['P07','B','4','Producto·B/N','Niños · 3 guiones','paperwhite-kids/frontal.png',
`Animate this image. The device is held by small child-sized hands in a bright cozy bedroom, warm afternoon daylight, a soft blanket and stuffed toy blurred in the background. Gentle handheld camera, shallow depth of field, natural editorial photography, warm and hopeful mood. Hands only, no faces. ${MARCO} Its screen is a black and white electronic ink display showing a page of a Spanish-language children's story: several short justified paragraphs of dark grey Spanish body text on a light warm grey background, with clean margins, exactly like printed prose, with no colour whatsoever on the screen. That page is a flat image rendered on the glass, never physical paper: the screen stays perfectly rigid and flat at all times, and nothing ever lifts, peels, curls, flies or emerges from it. No loose sheets, no paper, no book pages turning. The content on the screen is completely static and frozen: it never changes, never scrolls, and there is no page-turn animation, no sliding, no fading, no dissolve and no transition of any kind, because a real e-ink screen does not animate smoothly. It is a solid flat slab, not a book, and it never bends, folds or opens. ${EINK_SUP} ${CIERRE} quiet room tone only.`],
['P08','B','4','Producto·COLOR','Kindle Colorsoft · 1 guion','colorsoft-32gb/frontal.png',
`Animate this image. The device rests face up on a clean light surface as warm directional light slowly sweeps across it, making the colours of its body and its page deepen and come alive. The light does all the movement: the device itself stays still, flat and face up, and is never lifted, rotated or turned over. Very slow straight push in from above, no orbit and no arc around the device, shallow depth of field, natural editorial photography, crisp and vivid. ${MARCO} ${BLIND_COL} ${CIERRE} subtle ambient tone only.`],
['P09','B','4','Producto·COLOR','Kobo Libra con botones · 2 guiones','kobo-libra-colour-32-gb/frontal.png',
`Animate this image. The device is held in one hand against a softly blurred warm interior background, the thumb resting on the physical page-turn buttons along its raised side grip, the screen facing the camera the whole time and angled just enough that the raised grip and its buttons stay clearly visible along the side. The hand holds it steady, never rotating it or turning it over. Very slow straight push in, no orbit and no arc around the device, shallow depth of field, natural editorial photography, clean minimal composition. Keep the device exactly as shown: do not alter its shape, proportions, colour, body or its asymmetric grip with physical buttons. Its frame stays completely smooth, blank and unmarked, with no brand name, no logo, no lettering and no engraving anywhere on it. ${UNA_CARA} Its screen is a colour electronic ink display, with the soft muted pastel tones typical of colour e-ink rather than the vivid saturation of an LCD, showing a page of a Spanish-language novel with a few passages highlighted in soft yellow and pink: justified paragraphs of small dark Spanish body text on a light warm background, with clean margins, exactly like printed prose. That page is a flat image rendered on the glass, never physical paper: the screen stays perfectly rigid and flat at all times, and nothing ever lifts, peels, curls, flies or emerges from it. No loose sheets, no paper, no book pages turning. The content on the screen is completely static and frozen: it never changes, never scrolls, and there is no page-turn animation, no sliding, no fading, no dissolve and no transition of any kind, because a real e-ink screen does not animate smoothly. It is a solid flat slab, not a book, and it never bends, folds or opens. ${EINK_SUP} ${CIERRE} subtle room tone and a soft button click only.`],
['P10','B','4','Producto·COLOR','Kobo Clara compacta · 1 guion','kobo-clara-colour-16gb/frontal.png',
`Animate this image. The device rests on a light wooden table beside a cup of coffee, warm morning window light moving gently across it, a hand entering frame to pick it up and hold it comfortably in one palm to show how compact it is, keeping the screen facing the camera at all times and never turning it over. Slow push in, no orbit and no arc around the device, shallow depth of field, natural editorial photography, warm and inviting. ${MARCO} ${BLIND_COL} ${CIERRE} quiet morning room tone only.`],
['P11','B','4','Producto·CAJAS','Cajas selladas, stock real · 4 guiones','varios-modelos-en-la-misma-foto/frontal.png',
`Animate this image. The sealed retail boxes stand together on a dark surface under warm directional light that slowly sweeps across them, revealing the texture of the cardboard, with a subtle slow camera orbit around the group. Shallow depth of field, natural editorial photography, premium product mood. Keep every box exactly as shown: do not alter their shape, proportions, colours, or any of the printing, artwork and brand markings already on them — preserve all existing packaging graphics exactly as they appear. The boxes stay closed and sealed at all times; nothing is opened, unwrapped or taken out. Do not add any new text, lettering, labels, stickers or logos that are not already in the image. No watermark. No dialogue, no voiceover, subtle room tone only.`]
];

let filtro='todos';
// cambia de pestaña por código
function irA(sec){
 document.querySelectorAll('nav button').forEach(x=>
   x.classList.toggle('on',x.dataset.s===sec));
 document.querySelectorAll('section').forEach(s=>
   s.classList.toggle('on',s.id==='s-'+sec));
}
// clic en un chip de clip -> va al prompt y lo resalta
function irAPrompt(clipId){
 const arch=CLIPS[clipId][0];
 filtro='todos'; irA('prompts'); renderPrompts();
 setTimeout(()=>{const el=document.getElementById('pr-'+arch);
  if(el){el.scrollIntoView({behavior:'smooth',block:'center'});
   el.classList.add('destacado'); setTimeout(()=>el.classList.remove('destacado'),2400);}
  else{
   // metraje real: no tiene tarjeta de prompt porque no se genera con IA
   const t=document.getElementById('toast');
   t.textContent=`${clipId} es metraje real (${arch}.mp4) — no se genera, no tiene prompt`;
   t.classList.add('on');
   setTimeout(()=>{t.classList.remove('on');t.textContent='Copiado';},2600);
  }
 },70);
}
// "generar el material de este guion"
function verGuion(n){ filtro='G'+n; irA('prompts'); renderPrompts(); window.scrollTo(0,0); }

function renderPrompts(){
 const f=document.getElementById('filtros');
 const opts=[['todos','Todos'],['A','Cuenta A'],['B','Cuenta B'],
             ['Producto','Solo producto']];
 f.innerHTML=opts.map(o=>`<button data-f="${o[0]}" class="${o[0]==filtro?'on':''}">${o[1]}</button>`).join('')
  +`<select id="selg" title="Filtrar por guion"><option value="">— por guion —</option>`
  +G.map(g=>`<option value="G${g.n}" ${filtro==='G'+g.n?'selected':''}>Guion ${g.n} · ${g.t.slice(0,30)}</option>`).join('')
  +`</select>`;
 f.querySelectorAll('button').forEach(b=>b.onclick=()=>{filtro=b.dataset.f;renderPrompts();});
 const sel=f.querySelector?.('#selg');
 if(sel)sel.onchange=e=>{if(e.target.value){filtro=e.target.value;renderPrompts();}};

 let ordenGuion=null;
 if(/^G\d+$/.test(filtro)){
  const g=G.find(x=>x.n===+filtro.slice(1));
  ordenGuion=clipsDe(g).map(id=>CLIPS[id][0]);
 }
 let lista=P.map((p,i)=>({p,i})).filter(({p})=>{
   if(ordenGuion)return ordenGuion.includes(p[0]);
   if(filtro=='todos')return 1;
   if(filtro=='Producto')return p[3].startsWith('Producto');
   return p[1]==filtro;});
 if(ordenGuion)lista.sort((a,b)=>ordenGuion.indexOf(a.p[0])-ordenGuion.indexOf(b.p[0]));

 document.getElementById('avisog').innerHTML = ordenGuion
  ? `<div class="avisoguion">🎬 <b>Material del guion ${filtro.slice(1)}</b> —
      ${G.find(x=>x.n===+filtro.slice(1)).t}. Son <b>${lista.length} clips</b>.
      <button class="btn sec" onclick="filtro='todos';renderPrompts()">Ver todos</button></div>`
  : '';

 document.getElementById('prompts').innerHTML=lista.map(({p,i},k)=>{
   const esProd=p.length>6, foto=esProd?p[5]:null, txt=esProd?p[6]:p[5];
   return `<div class="pr ${esClipHecho(p[0]) ? 'hecho' : ''}" id="pr-${p[0]}">
    <div class="prcab">
      <label class="chk-hecho-lbl">
        <input type="checkbox" class="chk-clip-${p[0]}" ${esClipHecho(p[0]) ? 'checked' : ''} onchange="toggleClipHecho('${p[0]}', this.checked)">
        ☑ Ya tengo el video
      </label>
      <div class="orden" style="margin-left:8px;">${i+1}</div>
     <div class="prinfo"><b>${p[4].replace(/\s*·\s*(\d+\s*)?guion(es)?[\s\d,y]*$/i,'')}</b><span>${p[3]} · tanda ${p[2]}${
       COD[p[0]]?' · en los guiones aparece como <span class="codref">'+COD[p[0]]+'</span>':''}</span></div>
     <span class="modelo ${esProd?'mQ':'mF'}">${esProd?'Veo 3.1 Quality':'Veo 3.1 Fast'}</span>
     <button class="archivo" onclick="event.stopPropagation();cp(this,'${p[0]}.mp4')" title="Copiar nombre de archivo">💾 ${p[0]}.mp4</button>
   </div>
   ${foto?`<div class="foto">📎 <b>Frames to Video</b> — sube esta foto:
     <code>assets/productos/${foto}</code>
     <button class="btn sec" onclick="cp(this,'assets\\\\productos\\\\${foto.replace(/\//g,'\\\\')}')">Copiar ruta</button></div>`:''}
   ${(()=>{const us=usosDe(p[0]);
     if(!us.length)return `<div class="sinuso">💤 <b>No se usa en los 10 guiones de producción.</b></div>`;
     return `<div class="usos"><div class="usoscab">📍 Dónde se usa · verifica que el clip funcione en estos momentos</div>
      ${us.map(u=>`<div class="uso" onclick="irAGuion(${u.n},${u.ri})"
        title="Ir al guion ${u.n}, al momento ${u.mom}">
        <span class="ug">G${u.n}</span>
        <span class="um">${u.mom}</span>
        <span class="${PILL[u.tipo]}">${u.tipo}</span>
        <span class="ud">"${u.dice}"</span>
        <span class="uv">${u.ve.replace(/\b[FP]\d\d\b/g,'').replace(/^\s*a pantalla completa/,'pantalla completa').trim()||'—'}</span>
      </div>`).join('')}</div>`})()}
   ${RESUMEN[p[0]]?`<div class="resumen-es">🇪🇸 <b>En español:</b> ${RESUMEN[p[0]]}</div>`:''}
   <pre class="p" id="txt-${p[0]}">${txt.replace(/</g,'&lt;')}</pre>
   <div class="pracc">
     <button class="btn" onclick="cp(this,document.getElementById('txt-${p[0]}').textContent)">📋 Copiar prompt</button>
     <button class="btn sec" onclick="cp(this,'${p[0]}.mp4')">Copiar nombre de archivo</button>
   </div>
  </div>`}).join('');
}

/* ═══════════ TELEPROMPTER TABLET LOGIC ═══════════ */
let teleScrollTimer = null;
let teleScrollSpeed = 3;
let teleFontSize = 38;
let telePlaying = false;
let teleWakeLock = null;

async function requestWakeLock(){
 try{ if('wakeLock' in navigator) teleWakeLock = await navigator.wakeLock.request('screen'); }catch(e){}
}
function releaseWakeLock(){
 if(teleWakeLock){ teleWakeLock.release().catch(()=>{}); teleWakeLock = null; }
}

function abrirTeleprompter(gNum){
 const modal = document.getElementById('telemodal');
 const sel = document.getElementById('tele-sel');
 sel.innerHTML = G.map(g=>`<option value="${g.n}" ${g.n===gNum?'selected':''}>Guion ${g.n}: ${g.t}</option>`).join('');
 teleCargarGuion(gNum);
 modal.classList.add('on');
 document.body.style.overflow = 'hidden';
 requestWakeLock();
}

function teleCargarGuion(gNum){
 teleStop();
 const g = G.find(x=>x.n===gNum);
 if(!g) return;
 const content = document.getElementById('tele-content');
 let html = `<div style="font-size:0.55em;color:var(--cian);margin-bottom:30px;font-weight:800;letter-spacing:1.5px">🎬 GUION ${g.n} · ${g.t.toUpperCase()}</div>`;
 html += g.tomas.map((t, idx)=>`
   <div class="tele-frase">
     <span class="tele-cue">TOMA ${idx+1} (${t[0]}) — ${t[1]}</span>
     <div>${t[3]}</div>
     <span class="tele-pausa">⏸ PAUSA // CAMBIO DE PLANO</span>
   </div>
 `).join('');
 content.innerHTML = html;
 teleReset();
}

function teleTogglePlay(){
 if(telePlaying) teleStop();
 else teleStart();
}

function teleStart(){
 telePlaying = true;
 const btn = document.getElementById('tele-play');
 btn.textContent = '❚❚ Pausar';
 btn.style.background = 'var(--warn)';
 btn.style.color = '#000';
 if(teleScrollTimer) clearInterval(teleScrollTimer);
 teleScrollTimer = setInterval(()=>{
   const body = document.getElementById('tele-body');
   body.scrollTop += teleScrollSpeed;
   if(body.scrollTop + body.clientHeight >= body.scrollHeight - 10){
     teleStop();
   }
 }, 30);
}

function teleStop(){
 telePlaying = false;
 const btn = document.getElementById('tele-play');
 btn.textContent = '▶ Iniciar';
 btn.style.background = 'var(--cian)';
 btn.style.color = 'var(--navy)';
 if(teleScrollTimer){ clearInterval(teleScrollTimer); teleScrollTimer = null; }
}

function teleSpeed(delta){
 teleScrollSpeed = Math.max(1, Math.min(15, teleScrollSpeed + delta));
 document.getElementById('tele-speed-lbl').textContent = teleScrollSpeed + 'x';
}

function teleFont(delta){
 teleFontSize = Math.max(20, Math.min(72, teleFontSize + delta));
 document.getElementById('tele-font-lbl').textContent = teleFontSize + 'px';
 document.getElementById('tele-content').style.fontSize = teleFontSize + 'px';
}

function teleToggleEspejo(){
 document.getElementById('tele-content').classList.toggle('espejo');
}

function teleReset(){
 const body = document.getElementById('tele-body');
 body.scrollTop = 0;
}

function teleCerrar(){
 teleStop();
 releaseWakeLock();
 document.getElementById('telemodal').classList.remove('on');
 document.body.style.overflow = '';
}

/* ═══════════ LOTES ═══════════ */
function renderLotes(){
 let h='';
 for(let i=0;i<P.length;i+=4){
  const g=P.slice(i,i+4), nro=Math.floor(i/4)+1;
  h+=`<div class="lote"><h3>Tanda ${nro} · cuenta ${g[0][1]}</h3>
   <p style="margin:2px 0 0;font-size:13px;color:var(--txt2)">
     4 pestañas abiertas, un prompt en cada una. Cuesta ${g.length*20} créditos.</p>
   <div class="loteitems">${g.map((p,j)=>`<div class="loteit">
     <b>${j+1}. ${p[4].split('·')[0].trim()}</b>
     <span class="archivo">${p[0]}.mp4</span><br>
     <button class="btn sec" style="margin-top:7px" onclick="cpIdx(this,${i+j})">📋 Copiar</button>
   </div>`).join('')}</div>
   <button class="btn" onclick="cpTanda(this,${i})">📋 Copiar los ${g.length} numerados</button>
  </div>`;
 }
 h+=`<div class="lote" style="border-color:var(--warn)">
  <h3 style="color:var(--warn)">4 variantes del mismo prompt</h3>
  <p style="font-size:13.5px;color:var(--txt2)">
   En Flow puedes pedir varios resultados de una sola petición. Cada uno se cobra
   aparte: <b>4 variantes = 80 créditos</b> en Fast. Guardalas como
   <code>nombre.mp4</code>, <code>nombre-2.mp4</code>, <code>nombre-3.mp4</code>,
   <code>nombre-4.mp4</code> y quédate con las 2 mejores.</p>
  <p style="font-size:13.5px;color:var(--txt2)">Vale la pena solo en estos, que salen en 8-10 guiones:
   <b>scroll · libros · biblioteca · ojos · noche · P01 · P02</b></p>
 </div>`;
 document.getElementById('lotes').innerHTML=h;
}
/* ═══════════ EDITAR hooksegs / cierresegs Y GUARDAR EN EL ARCHIVO ═══════════ */
// showOpenFilePicker escribe directo en disco (Chrome/Edge, incluso abierto
// como file://). No hay forma de que el navegador sepa solo "este mismo
// archivo que ya tengo abierto" — José tiene que elegirlo una vez con el
// selector nativo; después el handle queda en memoria para el resto de la
// sesión y no se vuelve a pedir.
let panelFileHandle=null;

async function conseguirManejoArchivo(){
  if(panelFileHandle) return panelFileHandle;
  if(!window.showOpenFilePicker){
    alert('Este navegador no puede guardar directo en el archivo (hace falta Chrome o Edge). '
      +'Cambia el número a mano en PANEL-PRODUCCION.html y vuelve a correr el pipeline.');
    return null;
  }
  try{
    const [h]=await window.showOpenFilePicker({
      types:[{description:'Panel de producción',accept:{'text/html':['.html']}}]
    });
    if(h.name!=='PANEL-PRODUCCION.html'
       && !confirm(`Elegiste "${h.name}", pero se esperaba "PANEL-PRODUCCION.html". ¿Es el archivo correcto?`)){
      return null;
    }
    const permiso=await h.queryPermission({mode:'readwrite'});
    if(permiso!=='granted' && await h.requestPermission({mode:'readwrite'})!=='granted'){
      alert('Sin permiso de escritura no puedo guardar.');
      return null;
    }
    panelFileHandle=h;
    return h;
  }catch(e){
    if(e.name!=='AbortError') alert('No se pudo abrir el archivo: '+e.message);
    return null;
  }
}

// `campo` es 'hooksegs' o 'cierresegs' — mismo mecanismo para el silencio
// que se conserva al principio (hook) y al final (cierre) del video.
async function guardarSegundosGuion(n,campo){
  const input=document.getElementById(`${campo}-${n}`);
  const estado=document.getElementById(`${campo}-estado-${n}`);
  const val=parseFloat(input.value);
  if(isNaN(val)||val<0){
    estado.textContent='Valor inválido';estado.className='hookseg-estado mal';return;
  }
  estado.textContent='Guardando…';estado.className='hookseg-estado';
  const handle=await conseguirManejoArchivo();
  if(!handle){estado.textContent='';estado.className='hookseg-estado';return;}
  try{
    const file=await handle.getFile();
    const texto=await file.text();
    // hooksegs y cierresegs siempre van en la misma línea que "{n:N," (ver los
    // G del archivo), así que basta con no cruzar el salto de línea para no
    // tocar otro guion.
    const re=new RegExp(`(\\{n:${n},[^\\n]*?${campo}:)([0-9.]+)`);
    if(!re.test(texto)){
      estado.textContent=`No encontré "${campo}" del guion ${n} en ese archivo — ¿es PANEL-PRODUCCION.html?`;
      estado.className='hookseg-estado mal';return;
    }
    const nuevo=texto.replace(re,(_,pre)=>pre+val);
    const writable=await handle.createWritable();
    await writable.write(nuevo);
    await writable.close();
    const g=G.find(x=>x.n===n);
    if(g) g[campo]=val;
    estado.textContent='✓ Guardado';estado.className='hookseg-estado ok';
    setTimeout(()=>{
      if(estado.textContent==='✓ Guardado'){estado.textContent='';estado.className='hookseg-estado';}
    },2500);
  }catch(e){
    estado.textContent='Error al guardar: '+e.message;estado.className='hookseg-estado mal';
  }
}

function cpIdx(b,i){const p=P[i];cp(b,p.length>6?p[6]:p[5]);}
function cpTanda(b,i){const g=P.slice(i,i+4);
 cp(b,g.map((p,j)=>`━━━ ${j+1}. GUARDAR COMO: ${p[0]}.mp4 ━━━\n${p.length>6?'[Frames to Video · foto: assets/productos/'+p[5]+']\n':''}${p.length>6?p[6]:p[5]}`).join('\n\n\n'));}

/* ═══════════ UTILIDADES ═══════════ */
function cp(btn,txt){
 navigator.clipboard.writeText(txt).then(()=>{
  const o=btn.textContent;btn.textContent='✓ Copiado';btn.classList.add('ok');
  setTimeout(()=>{btn.textContent=o;btn.classList.remove('ok')},1400);
  const t=document.getElementById('toast');t.classList.add('on');
  setTimeout(()=>t.classList.remove('on'),1400);
 }).catch(()=>alert('No se pudo copiar. Selecciona el texto a mano.'));
}
document.querySelectorAll('nav button').forEach(b=>{
 if(b.dataset.s){
   b.onclick=()=>{ irA(b.dataset.s); window.scrollTo(0,0); };
 }
});
renderGuiones();renderPrompts();renderLotes();
