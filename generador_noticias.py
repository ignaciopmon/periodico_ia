import feedparser
import google.generativeai as genai
import datetime
import os
import json
import time
import trafilatura
from duckduckgo_search import DDGS

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# CAMBIO IMPORTANTE: Usamos Gemini 2.0 Flash. Es más rápido, más listo y más estable para JSON.
MODEL_NAME = "gemini-2.5-flash"

generation_config = {
    "temperature": 0.3,  # Baja temperatura para ser más factual y menos "creativo/mentiroso"
    "response_mime_type": "application/json",  # Forzamos respuesta JSON nativa
}

model = genai.GenerativeModel(MODEL_NAME, generation_config=generation_config)

FUENTES = {
    "Política": [
        "https://www.elmundo.es/rss/espana.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana",
    ],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Global": ["https://www.elmundo.es/rss/internacional.xml"],
    "Tecnología": ["https://www.xataka.com/index.xml"],
}


def limpiar_texto(texto):
    """Limpia espacios extra y saltos de línea raros"""
    if not texto:
        return ""
    return " ".join(texto.split())


def buscar_contexto_extra(query):
    """Busca dato puntual si la noticia es muy corta"""
    print(f"   🔎 Buscando contexto extra: '{query}'...")
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region="es-es", max_results=2)
            if results:
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        print(f"   ⚠️ Error búsqueda: {e}")
    return ""


def extraer_contenido_url(url):
    """Descarga el texto REAL de la noticia para no inventar"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            texto = trafilatura.extract(
                downloaded, include_comments=False, include_tables=False
            )
            if texto and len(texto) > 200:  # Si hay suficiente texto
                return texto
    except Exception as e:
        print(f"   ⚠️ Error extrayendo URL: {e}")
    return None


def redactar_noticia(item, texto_completo):
    """Escribe la noticia basándose en el TEXTO REAL"""
    print(f"✍️  Redactando noticia: {item['titulo']}...")

    # Si el texto es muy corto (menos de 500 caracteres), buscamos contexto extra
    contexto_adicional = ""
    if len(texto_completo) < 500:
        contexto_adicional = buscar_contexto_extra(f"{item['titulo']} noticias")

    prompt = f"""
    Eres un periodista serio y riguroso. Tu tarea es reescribir y resumir esta noticia para un periódico digital.
    
    INFORMACIÓN DE LA FUENTE (NO INVENTES NADA QUE NO ESTÉ AQUÍ):
    {texto_completo[:6000]} 
    
    CONTEXTO EXTRA (SOLO SI ES NECESARIO):
    {contexto_adicional}
    
    INSTRUCCIONES:
    1. Escribe un titular atractivo pero veraz.
    2. Escribe el cuerpo de la noticia en 3 o 4 párrafos bien estructurados.
    3. MANTÉN LOS HECHOS: Nombres, cargos y fechas deben ser exactos a la fuente.
    4. Estilo: Objetivo, formal y periodístico.
    
    Responde ÚNICAMENTE con este JSON:
    {{
        "titular": "...",
        "cuerpo": "...",
        "categoria": "{item['seccion']}"
    }}
    """

    try:
        response = model.generate_content(prompt)
        # Al usar response_mime_type="application/json", response.text ya es un JSON válido
        return json.loads(response.text)
    except Exception as e:
        print(f"❌ Error redactando: {e}")
        return None


def obtener_noticias():
    noticias = []
    print("📡 Leyendo RSS...")
    for categoria, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    # Procesamos solo 1 o 2 noticias por fuente para no saturar
                    for entry in feed.entries[:2]:
                        imagen = "https://via.placeholder.com/800x400?text=Noticia"

                        # Lógica mejorada para encontrar imágenes
                        if "media_content" in entry and entry.media_content:
                            imagen = entry.media_content[0]["url"]
                        elif "links" in entry:
                            for link in entry.links:
                                if link["type"].startswith("image"):
                                    imagen = link["href"]
                                    break

                        noticias.append(
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
            except Exception as e:
                print(f"Error leyendo RSS {url}: {e}")
                continue
    return noticias


def generar_html(articulos):
    css = """body{font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#f0f2f5; max-width:800px; margin:0 auto; padding:20px;}
             header{text-align:center; padding: 20px 0; border-bottom: 3px solid #1a73e8; margin-bottom: 30px;}
             h1{margin:0; color:#1a73e8; font-size: 2.5em;}
             .meta{color: #666; font-size: 0.9em; margin-top: 5px;}
             article{background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 30px; overflow: hidden;}
             .img-container{width:100%; height:300px; overflow:hidden;}
             img{width:100%; height:100%; object-fit:cover; transition: transform 0.3s;}
             article:hover img{transform: scale(1.02);}
             .content{padding: 25px;}
             .tag{background: #e8f0fe; color: #1a73e8; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em; text-transform: uppercase;}
             h2{margin: 15px 0; font-size: 1.8em; line-height: 1.2; color: #202124;}
             p{line-height:1.6; font-size:1.05em; color:#444; margin-bottom: 15px;}
             """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Diario IA</title>
        <style>{css}</style>
    </head>
    <body>
        <header>
            <h1>Diario IA</h1>
            <div class="meta">Actualizado: {datetime.datetime.now().strftime('%d/%m/%Y - %H:%M')}</div>
        </header>
    """

    for art in articulos:
        # Formateamos párrafos HTML
        texto_html = "".join(
            [f"<p>{p.strip()}</p>" for p in art["cuerpo"].split("\n") if len(p) > 20]
        )

        html += f"""
        <article>
            <div class="img-container">
                <img src="{art['imagen']}" onerror="this.src='https://via.placeholder.com/800x400?text=Imagen+No+Disponible'" alt="Imagen noticia">
            </div>
            <div class="content">
                <span class="tag">{art['categoria']}</span>
                <h2>{art['titular']}</h2>
                {texto_html}
            </div>
        </article>
        """
    html += "</body></html>"

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    raw_news = obtener_noticias()
    print(f"Recuperadas {len(raw_news)} noticias potenciales.")

    # Seleccionamos aleatorias para variedad o las primeras
    import random

    if len(raw_news) > 6:
        raw_news = random.sample(raw_news, 6)

    noticias_finales = []

    for item in raw_news:
        try:
            # 1. Extraer contenido real (FUNDAMENTAL para evitar alucinaciones)
            texto_real = extraer_contenido_url(item["link"])

            if not texto_real:
                print(f"⏩ Saltando {item['titulo']} (No se pudo leer contenido)")
                continue

            # 2. Generar noticia con Gemini
            noticia_generada = redactar_noticia(item, texto_real)

            if noticia_generada:
                noticia_generada["imagen"] = item["imagen"]
                noticias_finales.append(noticia_generada)
                print(f"✅ Publicada: {noticia_generada['titular'][:40]}...")

            # Respetamos límites de API
            time.sleep(2)

        except Exception as e:
            print(f"❌ Error procesando noticia: {e}")

    if noticias_finales:
        generar_html(noticias_finales)
        print("🎉 ¡Periódico publicado correctamente!")
    else:
        print("⚠️ No se generaron noticias.")


if __name__ == "__main__":
    main()
