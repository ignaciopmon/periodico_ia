import feedparser
import google.generativeai as genai
import datetime
import os
import json
import time
from duckduckgo_search import DDGS

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- FUENTES BASE ---
FUENTES = {
    "Nacional": ["https://www.elmundo.es/rss/espana.xml"],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Tecnología": ["https://www.xataka.com/index.xml"],
    "Internacional": ["https://www.elmundo.es/rss/internacional.xml"],
}

IMAGENES_DEFAULT = {
    "Nacional": "https://images.unsplash.com/photo-1541872703-74c5963631df?auto=format&fit=crop&w=800&q=80",
    "Economía": "https://images.unsplash.com/photo-1611974765270-ca1258634369?auto=format&fit=crop&w=800&q=80",
    "Tecnología": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
    "Internacional": "https://images.unsplash.com/photo-1529101091760-61df6be5d18b?auto=format&fit=crop&w=800&q=80",
}


def investigar_tema(query):
    """Busca en internet información real sobre el tema"""
    print(f"🕵️  Investigando a fondo: '{query}'...")
    info_extraida = []
    try:
        with DDGS() as ddgs:
            # Buscamos 5 resultados en español de España
            results = ddgs.text(query, region="es-es", max_results=5)
            for r in results:
                info_extraida.append(f"- {r['title']}: {r['body']}")
    except Exception as e:
        print(f"⚠️ Error en la investigación: {e}")
        return "No se pudo obtener información externa. Usar conocimiento general."

    return "\n".join(info_extraida)


def obtener_noticias_crudas():
    noticias = []
    for categoria, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    # Cogemos solo la PRIMERA noticia de cada fuente para asegurar calidad
                    entry = feed.entries[0]
                    imagen = None
                    if "media_content" in entry:
                        imagen = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for link in entry.links:
                            if link["type"].startswith("image"):
                                imagen = link["href"]
                                break

                    if not imagen:
                        imagen = IMAGENES_DEFAULT[categoria]

                    noticias.append(
                        {
                            "titulo": entry.title,
                            "resumen_rss": entry.summary,
                            "seccion": categoria,
                            "imagen": imagen,
                        }
                    )
                    break  # Solo una por categoría
            except:
                continue
    return noticias


def redactar_articulo_investigado(noticia_cruda):
    # 1. INVESTIGACIÓN ACTIVA
    contexto_real = investigar_tema(noticia_cruda["titulo"])

    print(f"✍️  Escribiendo noticia con datos reales...")

    prompt = f"""
    Eres un periodista senior de investigación. Tienes que escribir una noticia RIGUROSA.
    
    TITULAR ORIGINAL (RSS): "{noticia_cruda['titulo']}"
    
    HEMOS INVESTIGADO EN INTERNET Y ENCONTRADO ESTOS DATOS REALES (ÚSALOS):
    {contexto_real}
    
    INSTRUCCIONES OBLIGATORIAS:
    1. VERACIDAD: No inventes nada. Usa los datos de la investigación (porcentajes, nombres, declaraciones).
    2. CONTEXTO POLÍTICO/SOCIAL: Si hablas de partidos políticos (VOX, PSOE, PP), trátalos como lo que son. VOX no es emergente, es un partido consolidado. El PSOE es el partido de gobierno (o lo que indiquen los datos). Sé preciso con la ideología y situación actual.
    3. ESTILO: Periodístico, neutro, párrafos bien estructurados.
    4. EXTENSIÓN: Mínimo 400 palabras.
    
    Devuelve SOLO este JSON:
    {{
        "titular": "Un titular nuevo, periodístico y atractivo (no clickbait)",
        "cuerpo": "El cuerpo completo de la noticia en formato texto plano (usa saltos de línea normales)...",
        "categoria": "{noticia_cruda['seccion']}"
    }}
    """

    try:
        response = model.generate_content(prompt)
        texto_limpio = response.text.replace("```json", "").replace("```", "")
        # A veces la IA devuelve texto antes del json, buscamos las llaves
        start = texto_limpio.find("{")
        end = texto_limpio.rfind("}") + 1
        if start != -1 and end != -1:
            texto_limpio = texto_limpio[start:end]

        datos = json.loads(texto_limpio)
        datos["imagen"] = noticia_cruda["imagen"]
        return datos
    except Exception as e:
        print(f"❌ Error redactando: {e}")
        return None


def generar_html(articulos):
    fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
        body { font-family: 'Georgia', serif; background: #f4f4f4; margin: 0; color: #333; }
        .container { max-width: 900px; margin: 20px auto; background: white; padding: 40px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 20px; margin-bottom: 40px; }
        h1 { font-family: 'Arial Black', sans-serif; font-size: 3em; text-transform: uppercase; margin: 0; letter-spacing: -2px; }
        .meta { color: #666; font-style: italic; font-size: 0.9em; margin-top: 5px; }
        article { margin-bottom: 60px; border-bottom: 1px solid #eee; padding-bottom: 40px; }
        article:last-child { border: none; }
        .kicker { font-family: 'Arial', sans-serif; font-weight: bold; color: #c00; text-transform: uppercase; font-size: 0.8em; display: block; margin-bottom: 10px; }
        h2 { font-size: 2.2em; line-height: 1.1; margin: 0 0 20px 0; color: #111; }
        img { width: 100%; height: auto; max-height: 450px; object-fit: cover; margin-bottom: 25px; filter: contrast(1.1); }
        .body-text { font-size: 1.15em; line-height: 1.6; color: #222; text-align: justify; }
        .body-text p { margin-bottom: 1em; }
    """

    html = f"""<!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>El Diario Autónomo - Edición Investigada</title>
    <style>{css}</style></head>
    <body>
    <div class="container">
        <header>
            <h1>El Diario Autónomo</h1>
            <div class="meta">Edición generada con investigación en tiempo real | {fecha}</div>
        </header>
    """

    for art in articulos:
        # Formateamos el cuerpo para que tenga párrafos HTML
        cuerpo_html = "".join(
            [f"<p>{p.strip()}</p>" for p in art["cuerpo"].split("\n") if p.strip()]
        )

        html += f"""
        <article>
            <span class="kicker">{art['categoria']}</span>
            <h2>{art['titular']}</h2>
            <img src="{art['imagen']}" onerror="this.src='https://via.placeholder.com/800x400?text=Imagen+No+Disponible'">
            <div class="body-text">{cuerpo_html}</div>
        </article>
        """

    html += "</div></body></html>"
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    raw_news = obtener_noticias_crudas()
    noticias_finales = []

    for raw in raw_news:
        noticia = redactar_articulo_investigado(raw)
        if noticia:
            noticias_finales.append(noticia)
            time.sleep(2)  # Respeto a la API

    if noticias_finales:
        generar_html(noticias_finales)
        print("✅ Edición publicada correctamente.")
    else:
        print("❌ No se generaron noticias.")


if __name__ == "__main__":
    main()
