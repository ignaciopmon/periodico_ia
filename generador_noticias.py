import feedparser
import google.generativeai as genai
import datetime
import os
import json
import time
import re
import shutil
import glob
import trafilatura
from difflib import SequenceMatcher
from duckduckgo_search import DDGS
from google.api_core import exceptions

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# --- CASCADA DE MODELOS ---
MODELOS_PRIORIDAD = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
]

generation_config = {
    "temperature": 0.3,
    "response_mime_type": "application/json",
}

FUENTES = {
    "Nacional": [
        "https://www.elmundo.es/rss/espana.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana",
    ],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Tecnología": ["https://www.xataka.com/index.xml"],
    "Internacional": ["https://www.elmundo.es/rss/internacional.xml"],
}

# --- UTILIDADES ---


def limpiar_nombre_archivo(titulo):
    """Convierte un titular en un nombre de archivo seguro (slug)"""
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", titulo.lower())
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    return f"{slug[:50]}.html"


def generar_con_fallback(prompt):
    for modelo_nombre in MODELOS_PRIORIDAD:
        try:
            modelo = genai.GenerativeModel(
                modelo_nombre, generation_config=generation_config
            )
            return modelo.generate_content(prompt)
        except exceptions.ResourceExhausted:
            print(f"   ⚠️ Cuota excedida en {modelo_nombre}. Cambiando...")
            time.sleep(1)
            continue
        except Exception as e:
            if "429" in str(e):
                continue
            print(f"   ❌ Error en {modelo_nombre}: {e}")
            continue
    return None


def buscar_info_extra(query):
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region="es-es", max_results=2)
            if results:
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except:
        pass
    return ""


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


def similitud_titulares(t1, t2):
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


# --- GENERACIÓN DE CONTENIDO ---


def redactar_articulo_completo(item, contenido_real):
    print(f"✍️  Redactando a fondo: {item['titulo']}...")

    prompt = f"""
    Eres el Periodista Estrella de 'El Diario IA'. Escribe una CRÓNICA COMPLETA y detallada basada en:
    
    FUENTE ORIGINAL:
    {contenido_real[:9000]}
    
    INSTRUCCIONES:
    1. TITULAR: Periodístico y serio.
    2. BAJADA: Un resumen de 2 líneas.
    3. CUERPO: Escribe un artículo largo (mínimo 6 párrafos HTML <p>). 
       - Usa subtítulos <h3> para separar secciones.
       - Usa <strong> para datos clave.
       - NO pongas enlaces externos.
       - NO inventes datos.
    4. CATEGORÍA: {item['seccion']}
    
    Responde SOLO JSON:
    {{
        "titular": "...",
        "bajada": "...",
        "cuerpo_html": "<p>...</p><h3>...</h3><p>...</p>...", 
        "etiqueta": "...",
        "autor": "IA Staff"
    }}
    """

    response = generar_con_fallback(prompt)
    if response:
        try:
            return json.loads(response.text)
        except:
            return None
    return None


# --- MAQUETACIÓN HTML ---

CSS_GLOBAL = """
@import url('https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;1,400&family=Playfair+Display:wght@400;700;900&display=swap');
:root { --black: #121212; --dark-gray: #333; --border: #e2e2e2; --accent: #c0392b; --bg: #f9f9f9; }
body { font-family: 'Merriweather', serif; background-color: var(--bg); color: var(--black); margin: 0; padding: 20px; line-height: 1.8; }
a { text-decoration: none; color: inherit; }
a:hover { color: var(--accent); }

/* HEADER */
header { text-align: center; border-bottom: 4px double var(--black); padding-bottom: 20px; margin-bottom: 40px; max-width: 1100px; margin-left: auto; margin-right: auto; }
.brand { font-family: 'Playfair Display', serif; font-size: 4rem; font-weight: 900; letter-spacing: -2px; margin: 0; text-transform: uppercase; line-height: 1; }
.meta-bar { border-top: 1px solid var(--black); border-bottom: 1px solid var(--black); padding: 8px 0; margin-top: 15px; display: flex; justify-content: space-between; font-family: sans-serif; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; }

/* NAV HEMEROTECA */
.hemeroteca-nav { text-align: center; margin-bottom: 20px; font-family: sans-serif; font-size: 0.9rem; }
.hemeroteca-nav select { padding: 5px; font-size: 1rem; }

/* ARTÍCULOS PORTADA */
.container { max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: repeat(12, 1fr); gap: 30px; }
.hero { grid-column: span 12; display: grid; grid-template-columns: 1.5fr 1fr; gap: 30px; border-bottom: 3px solid var(--black); padding-bottom: 40px; margin-bottom: 40px; }
.hero img { width: 100%; height: 400px; object-fit: cover; }
.secondary { grid-column: span 4; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
.secondary img { width: 100%; height: 200px; object-fit: cover; margin-bottom: 10px; }
.text-only { grid-column: span 3; border-right: 1px solid var(--border); padding-right: 20px; }
.text-only:nth-child(4n) { border: none; }

h2 { font-family: 'Playfair Display', serif; margin: 10px 0; font-weight: 700; line-height: 1.2; }
.tag { font-family: sans-serif; font-size: 0.75rem; font-weight: bold; color: var(--accent); text-transform: uppercase; display: block; margin-bottom: 5px; }
.bajada { font-size: 1rem; color: #555; font-style: italic; margin-bottom: 15px; }
.read-more { font-family: sans-serif; font-size: 0.8rem; font-weight: bold; text-decoration: underline; color: var(--black); }

/* PÁGINA DE ARTÍCULO INDIVIDUAL */
.article-page { max-width: 800px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 0 20px rgba(0,0,0,0.05); }
.article-header { text-align: center; margin-bottom: 30px; }
.article-header h1 { font-family: 'Playfair Display', serif; font-size: 3rem; margin-bottom: 10px; line-height: 1.1; }
.article-img { width: 100%; height: auto; margin-bottom: 30px; }
.article-body { font-size: 1.1rem; color: #222; text-align: justify; }
.article-body h3 { font-family: sans-serif; margin-top: 30px; font-size: 1.2rem; text-transform: uppercase; }
.back-btn { display: inline-block; margin-bottom: 20px; font-family: sans-serif; font-weight: bold; }

@media (max-width: 900px) {
    .hero { grid-template-columns: 1fr; } 
    .hero img { order: -1; }
    .secondary, .text-only { grid-column: span 6; border: none; margin-bottom: 20px; }
}
@media (max-width: 600px) {
    .secondary, .text-only { grid-column: span 12; }
    .brand { font-size: 2.5rem; }
}
"""


def escribir_pagina_articulo(articulo, ruta_archivo, imagen_url, fecha_str):
    """Crea el HTML de la noticia individual"""
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{articulo['titular']} - Diario IA</title>
        <style>{CSS_GLOBAL}</style>
    </head>
    <body>
        <a href="index.html" class="back-btn">← Volver a la Portada</a>
        
        <article class="article-page">
            <header class="article-header">
                <span class="tag">{articulo['etiqueta']}</span>
                <h1>{articulo['titular']}</h1>
                <p class="bajada">{articulo['bajada']}</p>
                <div class="meta-bar">Por {articulo['autor']} • {fecha_str}</div>
            </header>
            
            <img src="{imagen_url}" class="article-img" onerror="this.style.display='none'">
            
            <div class="article-body">
                {articulo['cuerpo_html']}
            </div>
        </article>
        
        <footer style="text-align:center; margin-top:40px; font-size:0.8rem; color:#888;">
            Noticia generada por IA. Contenido ficticio basado en hechos reales.
        </footer>
    </body>
    </html>
    """
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(html)


def generar_portada_dia(noticias, carpeta_dia, fecha_legible, links_hemeroteca):
    """Genera el index.html de ese día específico"""

    # Selector de hemeroteca
    options_html = f"<option value='index.html' selected>{fecha_legible}</option>"
    for fecha_link, ruta in links_hemeroteca:
        # Calcular ruta relativa para salir de la carpeta actual si fuera necesario
        # Pero como la portada del dia está en /YYYY-MM-DD/, salir es ../
        relativa = f"../{ruta}/index.html"
        options_html += f"<option value='{relativa}'>{fecha_link}</option>"

    hemeroteca_html = f"""
    <div class="hemeroteca-nav">
        <label>📅 Hemeroteca:</label>
        <select onchange="location = this.value;">
            {options_html}
        </select>
    </div>
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Diario IA - {fecha_legible}</title>
        <style>{CSS_GLOBAL}</style>
    </head>
    <body>
        <header>
            <h1 class="brand">El Diario IA</h1>
            <div class="meta-bar">
                <span>📅 {fecha_legible}</span>
                <span>Edición Diaria</span>
                <span>Gemini Powered</span>
            </div>
        </header>
        
        {hemeroteca_html}
        
        <div class="container">
    """

    for i, n in enumerate(noticias):
        # El enlace ahora es LOCAL (nombre del archivo generado)
        link_local = n["archivo_local"]

        # Extraemos solo el primer párrafo para la portada
        match = re.search(r"<p>(.*?)</p>", n["cuerpo_html"])
        primer_parrafo = match.group(1) if match else n["bajada"]
        if len(primer_parrafo) > 200:
            primer_parrafo = primer_parrafo[:200] + "..."

        if i == 0:
            html += f"""
            <article class="hero">
                <div class="hero-content" style="display:flex; flex-direction:column; justify-content:center;">
                    <span class="tag">{n['etiqueta']}</span>
                    <h2><a href="{link_local}">{n['titular']}</a></h2>
                    <div class="bajada">{n['bajada']}</div>
                    <p>{primer_parrafo}</p>
                    <a href="{link_local}" class="read-more">Leer noticia completa →</a>
                </div>
                <img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/800x600'">
            </article>
            """
        elif i < 5:
            html += f"""
            <article class="secondary">
                <a href="{link_local}"><img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/400x300'"></a>
                <span class="tag">{n['etiqueta']}</span>
                <h2><a href="{link_local}">{n['titular']}</a></h2>
                <div class="bajada" style="font-size:0.9rem">{n['bajada']}</div>
                <a href="{link_local}" class="read-more">Leer más</a>
            </article>
            """
        else:
            html += f"""
            <article class="text-only">
                <span class="tag">{n['etiqueta']}</span>
                <h2><a href="{link_local}">{n['titular']}</a></h2>
                <p style="font-size:0.8rem">{primer_parrafo}</p>
            </article>
            """

    html += """
        </div>
        <footer style="text-align:center; padding: 40px; border-top: 4px double black; margin-top: 40px;">
            <p>© 2026 El Diario IA. Generado automáticamente.</p>
        </footer>
    </body></html>
    """

    with open(os.path.join(carpeta_dia, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main():
    # 1. Preparar Carpetas
    fecha_obj = datetime.datetime.now()
    fecha_carpeta = fecha_obj.strftime("%Y-%m-%d")
    fecha_legible = fecha_obj.strftime("%d de %B de %Y")

    os.makedirs(fecha_carpeta, exist_ok=True)

    # 2. Obtener Noticias
    raw_noticias = []
    titulares_vistos = []

    print("📡 Escaneando RSS...")
    for categoria, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:  # Top 3 de cada fuente
                    # Anti-duplicados
                    if any(
                        similitud_titulares(entry.title, t) > 0.65
                        for t in titulares_vistos
                    ):
                        continue
                    titulares_vistos.append(entry.title)

                    imagen = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=800&auto=format&fit=crop"
                    if "media_content" in entry and entry.media_content:
                        imagen = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for l in entry.links:
                            if l["type"].startswith("image"):
                                imagen = l["href"]
                                break

                    raw_noticias.append(
                        {
                            "titulo": entry.title,
                            "link": entry.link,
                            "seccion": categoria,
                            "imagen": imagen,
                        }
                    )
            except:
                continue

    # 3. Procesar y Generar Páginas Individuales
    print(f"📰 Procesando {len(raw_noticias)} noticias candidatas...")
    noticias_procesadas = []

    import random

    seleccion = raw_noticias[:9]  # Máximo 9 para la portada

    for item in seleccion:
        texto = extraer_contenido(item["link"])
        if not texto:
            texto = buscar_info_extra(f"{item['titulo']} noticias resumen")
        if not texto or len(texto) < 200:
            continue

        # Generar contenido completo
        articulo = redactar_articulo_completo(item, texto)

        if articulo:
            # Crear archivo individual
            nombre_archivo = limpiar_nombre_archivo(articulo["titular"])
            ruta_completa_archivo = os.path.join(fecha_carpeta, nombre_archivo)

            escribir_pagina_articulo(
                articulo, ruta_completa_archivo, item["imagen"], fecha_legible
            )

            # Guardamos datos para la portada
            articulo["imagen"] = item["imagen"]
            articulo["archivo_local"] = (
                nombre_archivo  # Enlace relativo dentro de la carpeta
            )
            noticias_procesadas.append(articulo)
            print(f"   ✅ Generada página: {nombre_archivo}")

        time.sleep(2)

    # 4. Generar Hemeroteca (Lista de carpetas anteriores)
    carpetas = [
        d
        for d in os.listdir(".")
        if os.path.isdir(d) and re.match(r"\d{4}-\d{2}-\d{2}", d)
    ]
    carpetas.sort(reverse=True)  # Las más nuevas primero
    links_hemeroteca = [
        (c, c) for c in carpetas if c != fecha_carpeta
    ]  # Tuplas (Texto, Ruta)

    # 5. Generar Portada del Día (index.html dentro de la carpeta)
    if noticias_procesadas:
        generar_portada_dia(
            noticias_procesadas, fecha_carpeta, fecha_legible, links_hemeroteca
        )

        # 6. Actualizar el ROOT index.html (Redirección o Copia)
        # Hacemos una copia de la portada de hoy a la raíz para que sea la "home"
        shutil.copy(os.path.join(fecha_carpeta, "index.html"), "index.html")

        # IMPORTANTE: Los enlaces en el index.html raíz deben apuntar a la carpeta del día
        # Así que leemos el HTML y arreglamos los links relativos
        with open("index.html", "r", encoding="utf-8") as f:
            contenido_root = f.read()

        # Reemplazamos href="noticia.html" por href="2026-02-11/noticia.html"
        def arreglar_links(match):
            link = match.group(1)
            if link.endswith(".html") and not link.startswith("http"):
                return f'href="{fecha_carpeta}/{link}"'
            return match.group(0)

        contenido_root = re.sub(r'href="([^"]+)"', arreglar_links, contenido_root)

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(contenido_root)

        print(f"🚀 Edición del día {fecha_carpeta} publicada y portada actualizada.")
    else:
        print("⚠️ No se pudieron generar noticias hoy.")


if __name__ == "__main__":
    main()
