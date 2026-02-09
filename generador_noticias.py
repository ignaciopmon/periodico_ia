import feedparser
import google.generativeai as genai
import datetime
import os
import json
import random
import time

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Usamos el modelo Flash que ya tienes comprobado
model = genai.GenerativeModel("gemini-2.5-flash")

# --- FUENTES ROBUSTAS (Con respaldo) ---
# Si la primera falla, intenta la segunda.
FUENTES = {
    "Nacional": [
        "https://www.elmundo.es/rss/espana.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana",
    ],
    "Economía": [
        "https://www.eleconomista.es/rss/rss-economia.php",
        "https://www.cincodias.com/rss/feed.html",
    ],
    "Tecnología": [
        "https://www.xataka.com/index.xml",
        "https://www.20minutos.es/rss/tecnologia/",
    ],
    "Internacional": [
        "https://www.elmundo.es/rss/internacional.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional",
    ],
}

# Imágenes de relleno por si falla la original (Stock gratuito)
IMAGENES_DEFAULT = {
    "Nacional": "https://images.unsplash.com/photo-1541872703-74c5963631df?auto=format&fit=crop&w=800&q=80",
    "Economía": "https://images.unsplash.com/photo-1611974765270-ca1258634369?auto=format&fit=crop&w=800&q=80",
    "Tecnología": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
    "Internacional": "https://images.unsplash.com/photo-1529101091760-61df6be5d18b?auto=format&fit=crop&w=800&q=80",
}


def limpiar_json(texto_sucio):
    texto = texto_sucio.replace("```json", "").replace("```", "")
    start = texto.find("{")
    end = texto.rfind("}") + 1
    if start != -1 and end != -1:
        return texto[start:end]
    return texto


def obtener_noticia_de_seccion(categoria, urls):
    print(f"🔍 Buscando en sección: {categoria}...")

    for url in urls:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                # Cogemos la primera que tenga algo de contenido
                for entry in feed.entries[:3]:
                    if len(entry.summary) > 50:  # Evitar noticias vacías
                        imagen = None
                        if "media_content" in entry:
                            imagen = entry.media_content[0]["url"]
                        elif "links" in entry:
                            for link in entry.links:
                                if link["type"].startswith("image"):
                                    imagen = link["href"]
                                    break

                        # Si no hay imagen, usamos la de defecto YA
                        if not imagen:
                            imagen = IMAGENES_DEFAULT[categoria]

                        return {
                            "titulo_original": entry.title,
                            "resumen": entry.summary,
                            "link_origen": entry.link,
                            "imagen": imagen,
                            "seccion": categoria,
                        }
        except Exception as e:
            print(f"⚠️ Falló la fuente {url}: {e}")
            continue  # Intentamos con la siguiente URL de la lista

    return None


def redactar_articulo(noticia_cruda):
    print(f"✍️ Redactando a fondo: {noticia_cruda['titulo_original']}...")

    prompt = f"""
    Eres un periodista experto en política y actualidad internacional. Vas a recibir un teletipo (texto breve) y debes convertirlo en una noticia completa.
    
    FUENTE ORIGINAL: "{noticia_cruda['resumen']}"
    SECCIÓN: {noticia_cruda['seccion']}
    
    INSTRUCCIONES CRÍTICAS DE CONTEXTO (IMPORTANTE):
    1. USAR CONOCIMIENTO INTERNO: El texto original es corto. USA TU CONOCIMIENTO PREVIO sobre cualquier tema o figuras públicas para dar el contexto correcto.
    2. NO ALUCINES: Sé preciso con la historia política de España y el mundo, con el deporte, la economía, etc. Si no sabes algo, mejor omítelo que inventarlo.
    3. DATOS REALES: Si el texto dice "17,9%", respeta el dato numérico, pero explica qué implica eso según tu conocimiento del panorama político habitual.
    
    INSTRUCCIONES DE FORMATO:
    1. Extensión: Mínimo 350 palabras.
    2. Titular: Periodístico, serio, sin clickbait barato. Máximo 12 palabras.
    3. Estilo: Formal, objetivo, prensa de calidad.
    
    Devuelve SOLO este JSON:
    {{
        "titular": "...",
        "cuerpo": "...",
        "categoria": "{noticia_cruda['seccion']}"
    }}
    """

    try:
        # response = model.generate_content(prompt)
        # Añadimos configuración para que sea menos "creativo" y más preciso
        generation_config = genai.types.GenerationConfig(
            temperature=0.3  # Bajamos la temperatura para que no invente cosas raras
        )
        response = model.generate_content(prompt, generation_config=generation_config)

        texto_limpio = limpiar_json(response.text)
        datos = json.loads(texto_limpio)

        datos["imagen"] = noticia_cruda["imagen"]
        if "categoria" not in datos:
            datos["categoria"] = noticia_cruda["seccion"]

        return datos
    except Exception as e:
        print(f"❌ Error redactando: {e}")
        return None


def generar_html(articulos):
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    css = """
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Roboto:wght@300;400&display=swap');
        body { font-family: 'Roboto', sans-serif; background: #f9f9f9; margin: 0; color: #1a1a1a; }
        .container { max-width: 1000px; margin: 0 auto; background: white; box-shadow: 0 0 20px rgba(0,0,0,0.05); min-height: 100vh; }
        header { padding: 40px 20px; text-align: center; border-bottom: 1px solid #ddd; }
        h1 { font-family: 'Playfair Display', serif; font-size: 3.5rem; margin: 0; text-transform: uppercase; letter-spacing: -1px; }
        .fecha { color: #888; margin-top: 10px; font-size: 0.9rem; border-top: 1px solid #eee; display: inline-block; padding-top: 5px; }
        
        .noticia { padding: 40px; border-bottom: 1px solid #eee; }
        .noticia:last-child { border-bottom: none; }
        .categoria-tag { color: #d93025; font-weight: bold; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 1px; margin-bottom: 10px; display: block;}
        
        .noticia h2 { font-family: 'Playfair Display', serif; font-size: 2.2rem; margin: 10px 0 20px 0; line-height: 1.1; }
        
        /* Imagen con manejo de errores */
        .img-container { width: 100%; height: 400px; overflow: hidden; background: #eee; margin-bottom: 25px; }
        .img-container img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s; }
        
        .cuerpo { font-size: 1.1rem; line-height: 1.8; color: #333; text-align: justify; }
        .cuerpo p { margin-bottom: 15px; }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>El Diario Autónomo</title>
        <style>{css}</style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>El Diario Autónomo</h1>
                <div class="fecha">{fecha_actual} | Edición IA Global</div>
            </header>
    """

    for art in articulos:
        # El evento onerror reemplaza la imagen si falla por una genérica transparente
        html += f"""
            <article class="noticia">
                <span class="categoria-tag">{art['categoria']}</span>
                <h2>{art['titular']}</h2>
                <div class="img-container">
                    <img src="{art['imagen']}" onerror="this.onerror=null;this.src='https://via.placeholder.com/800x400?text=Imagen+No+Disponible';">
                </div>
                <div class="cuerpo">{art['cuerpo'].replace(chr(10), '<br><br>')}</div>
            </article>
        """

    html += """
        </div>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    articulos_finales = []

    # Recorremos cada categoría
    for categoria, urls in FUENTES.items():
        raw = obtener_noticia_de_seccion(categoria, urls)
        if raw:
            # Pausa de 2 segundos para no agobiar a la API
            time.sleep(2)
            articulo = redactar_articulo(raw)
            if articulo:
                articulos_finales.append(articulo)
        else:
            print(f"⚠️ No se encontraron noticias para {categoria}")

    if len(articulos_finales) > 0:
        generar_html(articulos_finales)
        print("✅ ¡Edición publicada!")
    else:
        print("❌ Error fatal: No se generó ninguna noticia.")
        # Generar un HTML de error para que al menos se vea algo
        with open("index.html", "w") as f:
            f.write("<h1>Error técnico: No hay noticias disponibles.</h1>")


if __name__ == "__main__":
    main()
