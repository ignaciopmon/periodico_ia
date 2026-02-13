import feedparser
import google.generativeai as genai
import datetime
import os
import json
import time
import re
import trafilatura
from difflib import SequenceMatcher
from duckduckgo_search import DDGS
from google.api_core import exceptions

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# --- MODELOS ---

MODELOS_PRIORIDAD = [
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-pro-exp",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
]


generation_config = {
    "temperature": 0.4,  # Un poco más alto para creatividad en Opinión
    "response_mime_type": "application/json",
}

# --- FUENTES ---
FUENTES = {
    "Nacional": [
        "https://www.elmundo.es/rss/espana.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana",
    ],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Deportes": [
        "https://e00-marca.uecdn.es/rss/portada.xml",
        "https://as.com/rss/tags/ultimas_noticias.xml",
    ],
    "Internacional": ["https://www.elmundo.es/rss/internacional.xml"],
}

# --- UTILIDADES ---


def limpiar_nombre_archivo(titulo):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", titulo.lower())
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    return f"{slug[:40]}.html"


def es_imagen_valida(url):
    if not url:
        return False
    bloqueadas = ["placeholder", "logo", "pixel", "1x1", "icon"]
    return not any(x in url.lower() for x in bloqueadas)


def generar_con_fallback(prompt):
    for modelo_nombre in MODELOS_PRIORIDAD:
        try:
            modelo = genai.GenerativeModel(
                modelo_nombre, generation_config=generation_config
            )
            return modelo.generate_content(prompt)
        except exceptions.ResourceExhausted:
            time.sleep(2)
            continue
        except Exception:
            continue
    return None


def extraer_contenido(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            texto = trafilatura.extract(
                downloaded, include_comments=False, include_tables=False
            )
            if texto and len(texto) > 300:
                return texto
    except:
        pass
    return None


def buscar_info_extra(query):
    """Busca contexto para noticias normales"""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region="es-es", max_results=2)
            if results:
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except:
        pass
    return ""


def investigar_para_opinion(tema):
    """Busca análisis profundo y controversia para la sección OpinIA"""
    print(f"   🕵️‍♀️ Investigando a fondo para OpinIA: {tema}...")
    query = f"Análisis opinión controversia consecuencias {tema}"
    contexto = ""
    try:
        with DDGS() as ddgs:
            # Buscamos más resultados y más enfocados en opinión/análisis
            results = ddgs.text(query, region="es-es", max_results=4)
            if results:
                contexto = "\n".join(
                    [f"FUENTE EXT: {r['title']} - {r['body']}" for r in results]
                )
    except Exception as e:
        print(f"   ⚠️ Error investigando opinión: {e}")
    return contexto


def similitud_titulares(t1, t2):
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


# --- GENERACIÓN IA ---


def redactar_articulo_completo(item, contenido_real):
    print(f"✍️  Noticia: {item['titulo'][:30]}...")
    prompt = f"""
    Eres periodista de 'El Diario IA'. Escribe una noticia:
    DATOS: {contenido_real[:9000]}
    
    JSON: {{ "titular": "Max 10 palabras", "bajada": "Resumen 1 frase", "cuerpo_html": "Min 5 parrafos con <h3>", "etiqueta": "{item['seccion']}", "autor": "Redacción IA" }}
    """
    response = generar_con_fallback(prompt)
    if response:
        try:
            return json.loads(response.text)
        except:
            return None
    return None


def generar_columna_opinion(noticia_base, investigacion_extra):
    print(f"🧠 Escribiendo OpinIA sobre: {noticia_base['titular']}...")
    prompt = f"""
    Eres un columnista de opinión experto, crítico y sagaz. 
    Vas a escribir la columna "OpinIA" del día.
    
    TEMA PRINCIPAL: {noticia_base['titular']}
    HECHOS BÁSICOS: {noticia_base['bajada']}
    INVESTIGACIÓN PROFUNDA (ÚSALA): 
    {investigacion_extra}
    
    INSTRUCCIONES:
    1. NO es una noticia. Es una OPINIÓN. Usa primera persona del plural ("Nos preguntamos...", "Observamos...").
    2. Sé analítico. Busca las causas, las consecuencias ocultas o la hipocresía del asunto.
    3. Estilo: The New Yorker / El País Opinión. Culto pero directo.
    4. Titular: Debe ser un título de columna de opinión (metafórico o contundente).
    
    Responde SOLO JSON:
    {{
        "titular_opinion": "...",
        "cuerpo_opinion_html": "<p>...</p><p>...</p>...", 
        "firma": "La IA del Editor"
    }}
    """
    response = generar_con_fallback(prompt)
    if response:
        try:
            return json.loads(response.text)
        except:
            return None
    return None


# --- MAQUETACIÓN CSS (RESPONSIVE MEJORADO) ---

CSS_GLOBAL = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Roboto:wght@400;700&display=swap');

:root { --black: #111; --accent: #b91c1c; --bg: #fdfbf7; --border: #d1d5db; --opinia-bg: #1a1a1a; --opinia-text: #f0f0f0; }

body { font-family: 'Libre Baskerville', serif; background-color: var(--bg); color: var(--black); margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }
a { text-decoration: none; color: inherit; transition: color 0.2s; }
a:hover { color: var(--accent); }

/* HEADER */
header { border-bottom: 1px solid var(--black); padding: 20px 0; text-align: center; background: white; }
.brand { font-family: 'Cinzel', serif; font-size: 4rem; text-transform: uppercase; margin: 0; letter-spacing: -1px; line-height: 1; }
.meta-bar { border-top: 1px solid var(--black); border-bottom: 4px double var(--black); max-width: 1200px; margin: 15px auto 0; padding: 10px 0; display: flex; justify-content: space-between; font-family: 'Roboto', sans-serif; font-size: 0.8rem; text-transform: uppercase; font-weight: 700; padding-left: 20px; padding-right: 20px;}

/* NAV HEMEROTECA */
.nav-wrapper { background: #f4f4f4; padding: 10px 0; text-align: center; border-bottom: 1px solid #ddd; }
.nav-wrapper select { padding: 8px; font-family: 'Roboto', sans-serif; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; }

/* GRID LAYOUT */
.container { max-width: 1200px; margin: 40px auto; padding: 0 20px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; }

/* HERO */
.card-hero { grid-column: 1 / -1; display: grid; grid-template-columns: 1.5fr 1fr; gap: 40px; border-bottom: 3px solid var(--black); padding-bottom: 40px; margin-bottom: 20px; }
.card-hero img { width: 100%; height: 500px; object-fit: cover; border-radius: 2px; }
.hero-content { display: flex; flex-direction: column; justify-content: center; }
.hero-content h2 { font-size: 3rem; line-height: 1.05; margin: 10px 0 20px 0; letter-spacing: -0.5px; }
.hero-content .bajada { font-size: 1.25rem; color: #444; margin-bottom: 25px; line-height: 1.4; }

/* CARDS */
.card { display: flex; flex-direction: column; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
.card img { width: 100%; height: 240px; object-fit: cover; margin-bottom: 15px; filter: contrast(1.05); }
.card h2 { font-size: 1.6rem; margin: 10px 0; line-height: 1.2; font-weight: 700; }
.tag { font-family: 'Roboto', sans-serif; color: var(--accent); font-weight: 900; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 1px; display: inline-block; margin-bottom: 5px; }
.leer-mas { font-family: 'Roboto', sans-serif; font-weight: bold; font-size: 0.85rem; text-decoration: underline; margin-top: auto; padding-top: 15px; display: block; }

/* SECCIÓN OpinIA */
.opinia-section {
    background-color: var(--opinia-bg);
    color: var(--opinia-text);
    padding: 60px 40px;
    margin-top: 60px;
    border-top: 10px solid var(--accent);
}
.opinia-container { max-width: 900px; margin: 0 auto; display: grid; grid-template-columns: 1fr 2fr; gap: 50px; align-items: start; }
.opinia-brand { font-family: 'Cinzel', serif; font-size: 3rem; color: var(--accent); border-bottom: 2px solid #444; padding-bottom: 20px; margin-bottom: 20px; }
.opinia-meta { font-family: 'Roboto', sans-serif; color: #888; text-transform: uppercase; letter-spacing: 2px; font-size: 0.9rem; margin-bottom: 30px; }
.opinia-content h2 { font-family: 'Libre Baskerville', serif; font-size: 2.5rem; margin-bottom: 30px; line-height: 1.2; color: white; }
.opinia-body { font-size: 1.2rem; line-height: 1.8; color: #ddd; font-family: 'Georgia', serif; }
.opinia-body p { margin-bottom: 20px; }
.opinia-firma { text-align: right; font-style: italic; margin-top: 30px; font-weight: bold; color: var(--accent); }

/* ARTÍCULO INDIVIDUAL */
.article-container { max-width: 800px; margin: 40px auto; padding: 0 20px; }
.article-header h1 { font-size: 3.5rem; line-height: 1.1; margin-bottom: 20px; text-align: center; }
.article-img-full { width: 100%; height: auto; margin: 30px 0; max-height: 600px; object-fit: cover; }
.article-body { font-size: 1.25rem; line-height: 1.8; color: #111; }
.back-btn { display: inline-block; margin: 20px; font-family: 'Roboto', sans-serif; font-weight: bold; padding: 10px 20px; background: #eee; border-radius: 4px; }

/* MOBILE RESPONSIVE */
@media (max-width: 900px) {
    .container { grid-template-columns: repeat(2, 1fr); }
    .card-hero { grid-template-columns: 1fr; }
    .card-hero img { order: -1; height: 350px; }
    .opinia-container { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
    .brand { font-size: 2.5rem; }
    .container { grid-template-columns: 1fr; gap: 30px; }
    .meta-bar { flex-direction: column; text-align: center; gap: 5px; }
    .card h2 { font-size: 1.4rem; }
    .card-hero h2 { font-size: 2rem; }
    .opinia-section { padding: 40px 20px; }
    .opinia-content h2 { font-size: 1.8rem; }
    .article-header h1 { font-size: 2.2rem; }
    .article-body { font-size: 1.1rem; }
}
"""


def escribir_pagina_articulo(articulo, ruta, imagen):
    html = f"""
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{articulo['titular']}</title><style>{CSS_GLOBAL}</style></head><body>
    <a href="../index.html" class="back-btn">← PORTADA</a>
    <div class="article-container">
        <header class="article-header">
            <span class="tag" style="display:block; text-align:center;">{articulo['etiqueta']}</span>
            <h1>{articulo['titular']}</h1>
            <p style="text-align:center; font-style:italic; color:#555; font-size:1.2rem;">{articulo['bajada']}</p>
        </header>
        <img src="{imagen}" class="article-img-full">
        <div class="article-body">{articulo['cuerpo_html']}</div>
    </div>
    </body></html>
    """
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)


def generar_index(
    noticias,
    ruta_salida,
    fecha_display,
    opinion_data,
    es_root=False,
    hemeroteca_data=[],
):
    """Genera la portada con noticias + Sección OpinIA + Hemeroteca funcional"""

    # 1. HEMEROTECA INTELIGENTE
    prefijo_ruta = "" if es_root else "../"

    opts = f"<option value='#' selected disabled>— Navegar a otra edición —</option>"

    # Botón para ir al ROOT (Hoy/Última) si estamos en una subcarpeta
    if not es_root:
        opts += f"<option value='../index.html'>📅 VOLVER A PORTADA ACTUAL</option>"

    for fecha_iso, ruta_folder in hemeroteca_data:
        # Si estoy en root, link es "./2026-X/index.html"
        # Si estoy en carpeta, link es "../2026-X/index.html"
        link = f"{prefijo_ruta}{ruta_folder}/index.html"
        opts += f"<option value='{link}'>{fecha_iso}</option>"

    nav_html = f"""
    <div class="nav-wrapper">
        <select onchange="if(this.value != '#') location = this.value;">{opts}</select>
    </div>
    """

    # 2. GRID NOTICIAS
    grid_html = ""
    for i, n in enumerate(noticias):
        link_final = (
            n["archivo_local"]
            if not es_root
            else f"{n['carpeta']}/{n['archivo_local']}"
        )

        if i == 0:  # HERO
            grid_html += f"""
            <article class="card-hero">
                <div class="hero-content">
                    <span class="tag">{n['etiqueta']}</span>
                    <h2><a href="{link_final}">{n['titular']}</a></h2>
                    <div class="bajada">{n['bajada']}</div>
                    <a href="{link_final}" class="leer-mas">LEER ARTÍCULO COMPLETO →</a>
                </div>
                <img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/800x500'">
            </article>
            """
        else:
            grid_html += f"""
            <article class="card">
                <a href="{link_final}"><img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/400x300'"></a>
                <span class="tag">{n['etiqueta']}</span>
                <h2><a href="{link_final}">{n['titular']}</a></h2>
                <a href="{link_final}" class="leer-mas">Leer más</a>
            </article>
            """

    # 3. SECCIÓN OpinIA
    opinia_html = ""
    if opinion_data:
        opinia_html = f"""
        <section class="opinia-section">
            <div class="opinia-container">
                <div class="opinia-sidebar">
                    <div class="opinia-brand">OpinIA</div>
                    <div class="opinia-meta">
                        La Columna de la IA<br>
                        Análisis Diario<br>
                        {fecha_display}
                    </div>
                </div>
                <div class="opinia-content">
                    <h2>{opinion_data['titular_opinion']}</h2>
                    <div class="opinia-body">
                        {opinion_data['cuerpo_opinion_html']}
                    </div>
                    <div class="opinia-firma">~ {opinion_data['firma']}</div>
                </div>
            </div>
        </section>
        """

    html = f"""
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diario IA - {fecha_display}</title><style>{CSS_GLOBAL}</style></head><body>
    <header>
        <h1 class="brand">El Diario IA</h1>
        <div class="meta-bar">
            <span>{fecha_display}</span>
            <span>Edición Global</span>
            <span>Periodismo Algorítmico</span>
        </div>
    </header>
    {nav_html}
    
    <div class="container">
        {grid_html}
    </div>
    
    {opinia_html}
    
    <footer style="text-align:center; padding:50px; background:#111; color:#555; font-size:0.8rem;">
        &copy; 2026 El Diario IA. Un experimento de generación automática de noticias.
    </footer>
    </body></html>
    """
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    # SETUP
    hoy = datetime.datetime.now()
    carpeta_hoy = hoy.strftime("%Y-%m-%d")
    fecha_legible = hoy.strftime("%d de %B de %Y")
    os.makedirs(carpeta_hoy, exist_ok=True)

    # 1. RSS FETCHING
    candidatos = []
    titulos_vistos = []

    print("📡 Escaneando fuentes RSS...")
    for seccion, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:4]:
                    if any(
                        similitud_titulares(entry.title, t) > 0.65
                        for t in titulos_vistos
                    ):
                        continue
                    titulos_vistos.append(entry.title)

                    img = None
                    if "media_content" in entry and entry.media_content:
                        img = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for l in entry.links:
                            if l["type"].startswith("image"):
                                img = l["href"]
                                break

                    tiene_img = 1 if es_imagen_valida(img) else 0
                    if not img:
                        img = "https://via.placeholder.com/800x600?text=Diario+IA"

                    candidatos.append(
                        {
                            "titulo": entry.title,
                            "link": entry.link,
                            "seccion": seccion,
                            "imagen": img,
                            "tiene_img": tiene_img,
                        }
                    )
            except:
                continue

    # PRIORIZAR IMÁGENES
    candidatos.sort(key=lambda x: x["tiene_img"], reverse=True)
    seleccion = candidatos[:10]

    # 2. GENERACIÓN NOTICIAS
    noticias_finales = []
    print(f"📰 Generando {len(seleccion)} noticias...")

    for item in seleccion:
        texto = extraer_contenido(item["link"])
        if not texto:
            texto = buscar_info_extra(f"{item['titulo']} noticia")
        if not texto or len(texto) < 200:
            continue

        articulo = redactar_articulo_completo(item, texto)
        if articulo:
            nombre_archivo = limpiar_nombre_archivo(articulo["titular"])
            ruta_completa = os.path.join(carpeta_hoy, nombre_archivo)

            escribir_pagina_articulo(articulo, ruta_completa, item["imagen"])

            articulo["imagen"] = item["imagen"]
            articulo["archivo_local"] = nombre_archivo
            articulo["carpeta"] = carpeta_hoy
            noticias_finales.append(articulo)
            print(f"   ✅ {nombre_archivo}")
        time.sleep(1)

    # 3. GENERACIÓN OPINIA (Sobre la noticia principal/Hero)
    opinion_data = None
    if noticias_finales:
        tema_opinion = noticias_finales[0]  # Usamos la Hero
        print(f"🤔 Generando OpinIA sobre: {tema_opinion['titular']}...")

        # Investigar MÁS contexto externo
        investigacion = investigar_para_opinion(tema_opinion["titular"])

        # Escribir columna
        opinion_data = generar_columna_opinion(tema_opinion, investigacion)

    # 4. GENERACIÓN ÍNDICES (ROOT + DÍA)
    if noticias_finales:
        # Escanear carpetas para hemeroteca
        carpetas = [
            d
            for d in os.listdir(".")
            if os.path.isdir(d) and re.match(r"\d{4}-\d{2}-\d{2}", d)
        ]
        carpetas.sort(reverse=True)
        hemeroteca_data = [(c, c) for c in carpetas]

        # A) Index del día (dentro de la carpeta)
        generar_index(
            noticias_finales,
            os.path.join(carpeta_hoy, "index.html"),
            fecha_legible,
            opinion_data,
            es_root=False,
            hemeroteca_data=hemeroteca_data,
        )

        # B) Index Principal (Root)
        generar_index(
            noticias_finales,
            "index.html",
            fecha_legible,
            opinion_data,
            es_root=True,
            hemeroteca_data=hemeroteca_data,
        )

        print("🚀 Edición publicada con OpinIA y Responsive Design.")
    else:
        print("⚠️ No se generaron noticias.")


if __name__ == "__main__":
    main()
