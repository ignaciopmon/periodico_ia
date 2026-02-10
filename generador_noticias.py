import feedparser
import google.generativeai as genai
import datetime
import os
import json
import time
import trafilatura
from difflib import SequenceMatcher
from duckduckgo_search import DDGS
from google.api_core import exceptions

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# --- CASCADA DE MODELOS (Resistencia a fallos) ---
MODELOS_PRIORIDAD = [
    "gemini-flash-latest",  # Tu "Gemini 3 Flash" (usamos la 2.0 que es la latest actual)
    "gemini-2.5-flash",  # Tu "Gemini 2.5 Flash" (standard workhorse)
    "gemini-2.5-flash-lite",  # Tu "Gemini 2.5 Flash Lite" (versión optimizada/lite)
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

# --- HERRAMIENTAS ---


def generar_con_fallback(prompt):
    """Intenta generar contenido rotando modelos si se acaba la cuota."""
    for modelo_nombre in MODELOS_PRIORIDAD:
        try:
            modelo_actual = genai.GenerativeModel(
                modelo_nombre, generation_config=generation_config
            )
            return modelo_actual.generate_content(prompt)
        except exceptions.ResourceExhausted:
            print(f"   ⚠️ Cuota excedida en {modelo_nombre}. Cambiando modelo...")
            time.sleep(1)
            continue
        except Exception as e:
            print(f"   ❌ Error en {modelo_nombre}: {e}")
            if "429" in str(e):
                continue
            continue
    print("   ☠️ TODOS LOS MODELOS FALLARON.")
    return None


def similitud_titulares(t1, t2):
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


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


def redactar_noticia_ia(item, contenido_real):
    print(f"✍️  Reescribiendo: {item['titulo']}...")

    prompt = f"""
    Eres el Editor Jefe de 'El Diario IA'. Escribe una noticia basada en esto:
    
    FUENTE ORIGINAL:
    {contenido_real[:7000]}
    
    Instrucciones de Estilo:
    1. TITULAR: Periodístico, serio pero atractivo. Máximo 10 palabras.
    2. RESUMEN: Una frase impactante que iría debajo del titular.
    3. CUERPO: 3 párrafos HTML (<p>). Usa <strong> para resaltar datos clave.
    4. TONO: Objetivo, informativo, estilo 'The New York Times'.
    
    Responde SOLO JSON:
    {{
        "titular": "...",
        "bajada": "...",
        "cuerpo_html": "<p>...</p>...", 
        "etiqueta": "{item['seccion']}",
        "autor": "Redacción IA"
    }}
    """

    response = generar_con_fallback(prompt)
    if response:
        try:
            return json.loads(response.text)
        except:
            return None
    return None


def obtener_y_filtrar_noticias():
    raw_noticias = []
    titulares_vistos = []

    print("📡 Escaneando fuentes...")
    for categoria, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    # Filtro duplicados
                    es_repetida = False
                    for t_visto in titulares_vistos:
                        if similitud_titulares(entry.title, t_visto) > 0.65:
                            es_repetida = True
                            break
                    if es_repetida:
                        continue

                    titulares_vistos.append(entry.title)

                    # Imagen
                    imagen = "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?q=80&w=1000&auto=format&fit=crop"
                    if "media_content" in entry and entry.media_content:
                        imagen = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for link in entry.links:
                            if link["type"].startswith("image"):
                                imagen = link["href"]
                                break

                    raw_noticias.append(
                        {
                            "titulo": entry.title,
                            "link": entry.link,
                            "seccion": categoria,
                            "imagen": imagen,
                            "fecha": getattr(
                                entry, "published", str(datetime.date.today())
                            ),
                        }
                    )
            except:
                continue
    return raw_noticias


def generar_html_premium(noticias):
    fecha_hoy = datetime.datetime.now().strftime("%d de %B de %Y")

    # CSS INSPIRADO EN NEW YORK TIMES / EL PAÍS
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;1,400&family=Playfair+Display:wght@400;700;900&display=swap');
    
    :root { --black: #121212; --dark-gray: #333; --border: #e2e2e2; --accent: #c0392b; --bg: #f9f9f9; }
    
    body { font-family: 'Merriweather', serif; background-color: var(--bg); color: var(--black); margin: 0; padding: 20px; line-height: 1.6; }
    
    /* CABECERA */
    header { text-align: center; border-bottom: 4px double var(--black); padding-bottom: 20px; margin-bottom: 40px; max-width: 1100px; margin-left: auto; margin-right: auto; }
    .brand { font-family: 'Playfair Display', serif; font-size: 4.5rem; font-weight: 900; letter-spacing: -2px; margin: 0; text-transform: uppercase; line-height: 1; }
    .meta-bar { border-top: 1px solid var(--black); border-bottom: 1px solid var(--black); padding: 8px 0; margin-top: 15px; display: flex; justify-content: space-between; font-family: sans-serif; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; }
    
    /* LAYOUT */
    .container { max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: repeat(12, 1fr); gap: 30px; }
    
    /* ESTILOS DE NOTICIA */
    article { margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
    article:last-child { border: none; }
    
    .tag { font-family: sans-serif; font-size: 0.75rem; font-weight: bold; color: var(--accent); text-transform: uppercase; display: block; margin-bottom: 8px; letter-spacing: 1px; }
    
    h2 { font-family: 'Playfair Display', serif; margin: 10px 0; font-weight: 700; line-height: 1.1; }
    .bajada { font-size: 1.1rem; color: #555; margin-bottom: 15px; font-style: italic; line-height: 1.4; }
    .cuerpo { font-size: 0.95rem; color: var(--dark-gray); text-align: justify; }
    .cuerpo p { margin-bottom: 15px; }
    
    img { width: 100%; height: auto; display: block; margin-bottom: 15px; filter: grayscale(20%); transition: filter 0.3s; }
    article:hover img { filter: grayscale(0%); }
    
    .read-more { font-family: sans-serif; font-size: 0.8rem; text-decoration: none; color: var(--black); border-bottom: 1px solid var(--black); font-weight: bold; }
    
    /* TIPOS DE TARJETAS */
    
    /* NOTICIA PRINCIPAL (PORTADA) */
    .hero { grid-column: span 12; display: grid; grid-template-columns: 1.5fr 1fr; gap: 30px; border-bottom: 3px solid var(--black); margin-bottom: 40px; padding-bottom: 40px; }
    .hero img { height: 400px; object-fit: cover; width: 100%; order: 2; }
    .hero-content { order: 1; display: flex; flex-direction: column; justify-content: center; }
    .hero h2 { font-size: 3rem; margin-bottom: 15px; }
    .hero .bajada { font-size: 1.3rem; }
    
    /* NOTICIAS SECUNDARIAS */
    .secondary { grid-column: span 4; }
    .secondary h2 { font-size: 1.5rem; }
    .secondary img { height: 200px; object-fit: cover; }
    
    /* NOTICIAS TERCIARIAS (SOLO TEXTO) */
    .text-only { grid-column: span 3; border-right: 1px solid var(--border); padding-right: 20px; }
    .text-only:nth-child(4n) { border-right: none; } 
    .text-only h2 { font-size: 1.2rem; }
    .text-only img { display: none; }
    
    /* RESPONSIVE */
    @media (max-width: 900px) {
        .hero { grid-template-columns: 1fr; }
        .hero img { order: 1; height: 300px; }
        .hero-content { order: 2; }
        .secondary { grid-column: span 6; }
        .text-only { grid-column: span 6; border: none; }
    }
    @media (max-width: 600px) {
        .brand { font-size: 3rem; }
        .container { display: block; }
        .hero, .secondary, .text-only { display: block; margin-bottom: 40px; }
    }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>El Diario IA - Edición del Día</title>
        <style>{css}</style>
    </head>
    <body>
        <header>
            <h1 class="brand">El Diario IA</h1>
            <div class="meta-bar">
                <span>📅 {fecha_hoy}</span>
                <span>Edición Global</span>
                <span>Vol. 1 - N.º {datetime.datetime.now().strftime('%j')}</span>
            </div>
        </header>
        
        <div class="container">
    """

    # LÓGICA DE MAQUETACIÓN
    for i, n in enumerate(noticias):
        if i == 0:
            # PRIMERA NOTICIA: HERO (GRANDE)
            html += f"""
            <article class="hero">
                <div class="hero-content">
                    <span class="tag">{n['etiqueta']}</span>
                    <h2>{n['titular']}</h2>
                    <div class="bajada">{n['bajada']}</div>
                    <div class="cuerpo">{n['cuerpo_html']}</div>
                    <a href="{n['link']}" target="_blank" class="read-more">Leer noticia completa →</a>
                </div>
                <img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/800x600'">
            </article>
            """
        elif i < 5:
            # SIGUIENTES 4: TARJETAS VISUALES
            html += f"""
            <article class="secondary">
                <img src="{n['imagen']}" onerror="this.src='https://via.placeholder.com/400x300'">
                <span class="tag">{n['etiqueta']}</span>
                <h2>{n['titular']}</h2>
                <div class="bajada">{n['bajada']}</div>
                <a href="{n['link']}" target="_blank" class="read-more">Continuar leyendo</a>
            </article>
            """
        else:
            # EL RESTO: COLUMNAS DE TEXTO (Tipo breve)
            html += f"""
            <article class="text-only">
                <span class="tag">{n['etiqueta']}</span>
                <h2>{n['titular']}</h2>
                <div class="cuerpo" style="font-size:0.85rem">{n['cuerpo_html'][:150]}...</div>
            </article>
            """

    html += """
        </div>
        <footer style="text-align:center; padding: 50px 0; border-top: 4px double black; margin-top: 50px; font-family: sans-serif; color: #666;">
            <p>© 2026 El Diario IA. Generado automáticamente con tecnología Gemini.</p>
        </footer>
    </body></html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    candidatos = obtener_y_filtrar_noticias()
    print(f"📰 Noticias detectadas: {len(candidatos)}")

    # Seleccionamos hasta 9 noticias para llenar bien la parrilla
    seleccion = candidatos[:9]
    noticias_finales = []

    for item in seleccion:
        texto = extraer_contenido(item["link"])

        if not texto:
            texto = buscar_info_extra(f"{item['titulo']} noticias resumen")

        if not texto or len(texto) < 200:
            continue

        articulo = redactar_noticia_ia(item, texto)
        if articulo:
            articulo["imagen"] = item["imagen"]
            articulo["link"] = item["link"]
            noticias_finales.append(articulo)
            print(f"✅ Publicada: {articulo['titular']}")

        time.sleep(2)

    if noticias_finales:
        generar_html_premium(noticias_finales)
        print("🚀 Edición impresa generada (index.html)")
    else:
        print("⚠️ No hay noticias suficientes.")


if __name__ == "__main__":
    main()
