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
    "gemini-2.0-flash-exp"
]

generation_config = {
    "temperature": 0.3, 
    "response_mime_type": "application/json",
}

# --- FUENTES (CAMBIO: DEPORTES INCLUIDO) ---
FUENTES = {
    "Nacional": [
        "https://www.elmundo.es/rss/espana.xml", 
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana"
    ],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Deportes": [
        "https://e00-marca.uecdn.es/rss/portada.xml", 
        "https://as.com/rss/tags/ultimas_noticias.xml"
    ],
    "Internacional": ["https://www.elmundo.es/rss/internacional.xml"]
}

# --- HELPERS ---

def limpiar_nombre_archivo(titulo):
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', titulo.lower())
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return f"{slug[:40]}.html"

def es_imagen_valida(url):
    """Filtra imágenes placeholder o vacías"""
    if not url: return False
    bloqueadas = ["placeholder", "logo", "pixel", "1x1", "icon"]
    return not any(x in url.lower() for x in bloqueadas)

def generar_con_fallback(prompt):
    for modelo_nombre in MODELOS_PRIORIDAD:
        try:
            modelo = genai.GenerativeModel(modelo_nombre, generation_config=generation_config)
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
            texto = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if texto and len(texto) > 300: return texto
    except: pass
    return None

def buscar_info_extra(query):
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region="es-es", max_results=2)
            if results: return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except: pass
    return ""

def similitud_titulares(t1, t2):
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()

# --- GENERACIÓN IA ---

def redactar_articulo_completo(item, contenido_real):
    print(f"✍️  Redactando: {item['titulo'][:30]}...")

    prompt = f"""
    Eres periodista de 'El Diario IA'. Escribe una noticia basada en:
    {contenido_real[:9000]}
    
    INSTRUCCIONES:
    1. Titular: Serio y periodístico (max 10 palabras).
    2. Bajada: Resumen de 1 frase.
    3. Cuerpo: Mínimo 5 párrafos HTML (<p>). Usa <h3> para subtítulos.
    4. Categoria: {item['seccion']}
    
    Responde SOLO JSON:
    {{
        "titular": "...",
        "bajada": "...",
        "cuerpo_html": "...", 
        "etiqueta": "...",
        "autor": "Redacción IA"
    }}
    """
    
    response = generar_con_fallback(prompt)
    if response:
        try: return json.loads(response.text)
        except: return None
    return None

# --- MAQUETACIÓN VISUAL (CSS GRID REAL) ---

CSS_GLOBAL = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Roboto:wght@400;700&display=swap');

:root { --black: #111; --accent: #b91c1c; --bg: #fdfbf7; --border: #d1d5db; }

body { font-family: 'Libre Baskerville', serif; background-color: var(--bg); color: var(--black); margin: 0; padding: 0; }
a { text-decoration: none; color: inherit; transition: color 0.2s; }
a:hover { color: var(--accent); }

/* HEADER */
header { 
    border-bottom: 1px solid var(--black); 
    padding: 20px 0; 
    text-align: center; 
    position: relative;
    background: white;
}
.brand { 
    font-family: 'Cinzel', serif; 
    font-size: 3.5rem; 
    text-transform: uppercase; 
    margin: 0; 
    letter-spacing: 2px;
    line-height: 1;
}
.meta-bar {
    border-top: 1px solid var(--black);
    border-bottom: 4px double var(--black);
    max-width: 1200px;
    margin: 15px auto 0;
    padding: 8px 0;
    display: flex;
    justify-content: space-between;
    font-family: 'Roboto', sans-serif;
    font-size: 0.85rem;
    text-transform: uppercase;
    font-weight: 700;
}

/* HEMEROTECA NAV */
.nav-wrapper { background: #eee; padding: 5px 0; text-align: center; border-bottom: 1px solid #ddd; }
.nav-wrapper select { padding: 5px; font-family: 'Roboto', sans-serif; }

/* LAYOUT PRINCIPAL */
.container {
    max-width: 1200px;
    margin: 40px auto;
    padding: 0 20px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 30px;
}

/* HERO (NOTICIA PRINCIPAL) */
.card-hero {
    grid-column: 1 / -1; /* Ocupa todo el ancho */
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 30px;
    border-bottom: 3px solid var(--black);
    padding-bottom: 40px;
    margin-bottom: 20px;
}
.card-hero img { width: 100%; height: 450px; object-fit: cover; }
.hero-content { display: flex; flex-direction: column; justify-content: center; }
.hero-content h2 { font-size: 2.8rem; line-height: 1.1; margin: 10px 0 20px 0; }
.hero-content .bajada { font-size: 1.2rem; color: #444; margin-bottom: 20px; font-style: italic; }

/* TARJETAS ESTÁNDAR */
.card {
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--border);
    padding-bottom: 20px;
}
.card img {
    width: 100%;
    height: 220px;
    object-fit: cover;
    margin-bottom: 15px;
    filter: brightness(0.95);
}
.card h2 { font-size: 1.4rem; margin: 10px 0; line-height: 1.2; }
.tag { 
    font-family: 'Roboto', sans-serif; 
    color: var(--accent); 
    font-weight: 700; 
    text-transform: uppercase; 
    font-size: 0.75rem; 
    letter-spacing: 1px; 
}
.extracto { font-size: 0.95rem; color: #555; line-height: 1.5; margin-bottom: 15px; }
.leer-mas { font-family: 'Roboto', sans-serif; font-weight: bold; font-size: 0.8rem; text-decoration: underline; }

/* ARTÍCULO INDIVIDUAL */
.article-container { max-width: 800px; margin: 40px auto; padding: 0 20px; }
.article-header h1 { font-size: 3rem; line-height: 1.1; margin-bottom: 20px; text-align: center; }
.article-img-full { width: 100%; height: auto; margin: 30px 0; }
.article-body { font-size: 1.15rem; line-height: 1.8; color: #222; }
.article-body p { margin-bottom: 20px; }
.back-btn { display: inline-block; margin: 20px; font-family: 'Roboto', sans-serif; font-weight: bold; }

/* RESPONSIVE */
@media (max-width: 900px) {
    .container { grid-template-columns: 1fr 1fr; }
    .card-hero { grid-template-columns: 1fr; }
    .card-hero img { order: -1; height: 300px; }
}
@media (max-width: 600px) {
    .container { grid-template-columns: 1fr; }
    .brand { font-size: 2.5rem; }
}
"""

def escribir_pagina_articulo(articulo, ruta, imagen, fecha):
    html = f"""
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{articulo['titular']}</title><style>{CSS_GLOBAL}</style></head><body>
    <a href="../index.html" class="back-btn">← VOLVER A PORTADA</a>
    <div class="article-container">
        <header class="article-header">
            <span class="tag" style="display:block; text-align:center;">{articulo['etiqueta']}</span>
            <h1>{articulo['titular']}</h1>
            <p style="text-align:center; font-style:italic; color:#666;">{articulo['bajada']}</p>
        </header>
        <img src="{imagen}" class="article-img-full">
        <div class="article-body">{articulo['cuerpo_html']}</div>
    </div>
    </body></html>
    """
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)

def generar_index(noticias, ruta_salida, fecha_display, es_root=False, hemeroteca_data=[]):
    """
    Genera el index.html.
    es_root=True -> Genera el index.html de la raíz (links apuntan a carpetas ./YYYY/...)
    es_root=False -> Genera el index.html de un día (links apuntan a archivos locales)
    """
    
    # 1. Construir menú hemeroteca
    # Lógica de rutas: Si estamos en root, carpetas son "./". Si estamos en día, son "../"
    prefijo_ruta = "" if es_root else "../"
    
    opts = f"<option value='#' selected>📅 Edición: {fecha_display}</option>"
    for fecha_iso, ruta_folder in hemeroteca_data:
        # El value debe llevar al index de esa carpeta
        link = f"{prefijo_ruta}{ruta_folder}/index.html"
        opts += f"<option value='{link}'>{fecha_iso}</option>"

    nav_html = f"""
    <div class="nav-wrapper">
        <label>Hemeroteca:</label>
        <select onchange="if(this.value != '#') location = this.value;">{opts}</select>
    </div>
    """

    # 2. Construir Grid de Noticias
    grid_html = ""
    for i, n in enumerate(noticias):
        # Enlace: Si es root, necesitamos ruta completa "carpeta/archivo.html". Si es día, solo "archivo.html"
        link_final = n['archivo_local']
        if es_root:
            link_final = f"{n['carpeta']}/{n['archivo_local']}"

        if i == 0: # HERO
            grid_html += f"""
            <article class="card-hero">
                <div class="hero-content">
                    <span class="tag">{n['etiqueta']}</span>
                    <h2><a href="{link_final}">{n['titular']}</a></h2>
                    <div class="bajada">{n['bajada']}</div>
                    <a href="{link_final}" class="leer-mas">LEER NOTICIA COMPLETA →</a>
                </div>
                <img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/800x400?text=Diario+IA'">
            </article>
            """
        else: # TARJETAS NORMALES
            grid_html += f"""
            <article class="card">
                <a href="{link_final}"><img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/400x300?text=Noticia'"></a>
                <span class="tag">{n['etiqueta']}</span>
                <h2><a href="{link_final}">{n['titular']}</a></h2>
                <div class="extracto">{n['bajada'][:100]}...</div>
                <a href="{link_final}" class="leer-mas">Leer más</a>
            </article>
            """

    html = f"""
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diario IA - {fecha_display}</title><style>{CSS_GLOBAL}</style></head><body>
    <header>
        <h1 class="brand">El Diario IA</h1>
        <div class="meta-bar">
            <span>{fecha_display}</span>
            <span>Edición Global</span>
            <span>Inteligencia Artificial</span>
        </div>
    </header>
    {nav_html}
    <div class="container">
        {grid_html}
    </div>
    <footer style="text-align:center; padding:40px; color:#777; font-size:0.8rem; border-top:1px solid #ddd; margin-top:40px;">
        &copy; 2026 El Diario IA. Generado automáticamente.
    </footer>
    </body></html>
    """
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    # Fechas
    hoy = datetime.datetime.now()
    carpeta_hoy = hoy.strftime('%Y-%m-%d')
    fecha_legible = hoy.strftime('%d de %B de %Y')
    os.makedirs(carpeta_hoy, exist_ok=True)

    # 1. Obtener candidatos RSS
    candidatos = []
    titulos_vistos = []
    
    print("📡 Escaneando fuentes...")
    for seccion, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:4]:
                    if any(similitud_titulares(entry.title, t) > 0.65 for t in titulos_vistos): continue
                    titulos_vistos.append(entry.title)
                    
                    # Extracción Imagen
                    img = None
                    if "media_content" in entry and entry.media_content: img = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for l in entry.links:
                            if l["type"].startswith("image"): img = l["href"]; break
                    
                    # Prioridad visual: Marcamos si tiene imagen real
                    tiene_img = 1 if es_imagen_valida(img) else 0
                    if not img: img = "https://via.placeholder.com/800x600?text=Sin+Imagen"

                    candidatos.append({
                        "titulo": entry.title,
                        "link": entry.link,
                        "seccion": seccion,
                        "imagen": img,
                        "tiene_img": tiene_img # Clave para ordenar
                    })
            except: continue

    # 2. ORDENAR: Priorizar noticias con imagen real para que salgan primero
    candidatos.sort(key=lambda x: x['tiene_img'], reverse=True)
    seleccion = candidatos[:10] # Top 10

    # 3. Generar contenido
    noticias_finales = []
    print(f"📰 Generando {len(seleccion)} noticias...")
    
    for item in seleccion:
        texto = extraer_contenido(item['link'])
        if not texto: texto = buscar_info_extra(f"{item['titulo']} noticia")
        if not texto or len(texto) < 200: continue

        articulo = redactar_articulo_completo(item, texto)
        if articulo:
            nombre_archivo = limpiar_nombre_archivo(articulo['titular'])
            ruta_completa = os.path.join(carpeta_hoy, nombre_archivo)
            
            escribir_pagina_articulo(articulo, ruta_completa, item['imagen'], fecha_legible)
            
            # Guardar metadatos para index
            articulo['imagen'] = item['imagen']
            articulo['archivo_local'] = nombre_archivo
            articulo['carpeta'] = carpeta_hoy
            noticias_finales.append(articulo)
            print(f"   ✅ {nombre_archivo}")
        time.sleep(1)

    # 4. Generar Índices y Hemeroteca
    if noticias_finales:
        # Detectar carpetas anteriores para hemeroteca
        carpetas = [d for d in os.listdir('.') if os.path.isdir(d) and re.match(r'\d{4}-\d{2}-\d{2}', d)]
        carpetas.sort(reverse=True)
        hemeroteca_data = [(c, c) for c in carpetas]

        # A) Index del día (dentro de la carpeta)
        generar_index(noticias_finales, os.path.join(carpeta_hoy, "index.html"), fecha_legible, es_root=False, hemeroteca_data=hemeroteca_data)
        
        # B) Index Principal (Root) -> Links ajustados
        generar_index(noticias_finales, "index.html", fecha_legible, es_root=True, hemeroteca_data=hemeroteca_data)
        
        print("🚀 Edición publicada correctamente.")
    else:
        print("⚠️ No se generaron noticias.")

if __name__ == "__main__":
    main()
