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

# --- FUENTES (Solo medios serios para evitar ruido) ---
FUENTES = {
    "Política": ["https://www.elmundo.es/rss/espana.xml"],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Tecnología": ["https://www.xataka.com/index.xml"],
    "Global": ["https://www.elmundo.es/rss/internacional.xml"],
}


def investigar_tema(titular, seccion, resumen_original):
    """
    Busca información cruzando datos para evitar alucinaciones.
    Añade palabras clave forzadas para que no busque anime o videojuegos.
    """
    # 1. Construimos una búsqueda "a prueba de tontos"
    # Si la sección es Política, forzamos que busque cosas de gobierno/elecciones
    contexto_extra = "noticia españa actualidad"
    if seccion == "Política":
        contexto_extra += " partido político elecciones gobierno"
    elif seccion == "Economía":
        contexto_extra += " mercado financiero bolsa empresas"

    query = f"{titular} {contexto_extra}"
    print(f"🕵️  Investigando: '{query}'...")

    info_extraida = []
    try:
        # Usamos region='es-es' para que NO busque cosas en inglés/Japón (Vox Akuma fuera)
        with DDGS() as ddgs:
            results = ddgs.text(query, region="es-es", timelimit="d", max_results=4)
            for r in results:
                info_extraida.append(
                    f"- Título: {r['title']}\n- Fragmento: {r['body']}"
                )
    except Exception as e:
        print(f"⚠️ Error en búsqueda: {e}")
        return None

    return "\n".join(info_extraida)


def obtener_noticias_crudas():
    noticias = []
    print("📡 Escaneando RSS...")
    for categoria, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    # Cogemos la primera noticia válida
                    entry = feed.entries[0]

                    imagen = None
                    # Búsqueda agresiva de imagen
                    if "media_content" in entry:
                        imagen = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for link in entry.links:
                            if link["type"].startswith("image"):
                                imagen = link["href"]
                                break
                    if "enclosures" in entry and not imagen:
                        for enc in entry.enclosures:
                            if enc.type.startswith("image"):
                                imagen = enc.href
                                break

                    noticias.append(
                        {
                            "titulo": entry.title,
                            "resumen_rss": entry.summary,
                            "seccion": categoria,
                            "imagen": imagen,
                            "link": entry.link,
                        }
                    )
                    break
            except Exception as e:
                print(f"Error en fuente {url}: {e}")
                continue
    return noticias


def redactar_articulo_investigado(noticia_cruda):
    # 1. INVESTIGACIÓN
    datos_internet = investigar_tema(
        noticia_cruda["titulo"], noticia_cruda["seccion"], noticia_cruda["resumen_rss"]
    )

    if not datos_internet:
        print("⚠️ No se hallaron datos externos, usando solo RSS para no inventar.")
        datos_internet = "No hay datos externos confiables. Cíñete al resumen original."

    print(f"✍️  Escribiendo noticia: {noticia_cruda['titulo']}")

    # 2. EL PROMPT "ANTI-ALUCINACIÓN"
    prompt = f"""
    Actúa como un redactor jefe de un periódico serio español (tipo El País o El Mundo).
    
    TEMA PRINCIPAL (VERDAD ABSOLUTA): "{noticia_cruda['titulo']}"
    RESUMEN ORIGINAL: "{noticia_cruda['resumen_rss']}"
    
    DATOS ENCONTRADOS EN INTERNET:
    {datos_internet}
    
    ⚠️ PROTOCOLO DE SEGURIDAD (IMPORTANTE):
    1. FILTRO DE CONTEXTO: Tu sección es "{noticia_cruda['seccion']}". Si los datos de internet hablan de youtubers, anime, videojuegos o algo que NO encaja con la sección, IGNÓRALOS COMPLETAMENTE y usa solo el resumen original.
    2. VOX es un partido político español. NO es un youtuber (Vox Akuma).
    3. Si hablas de política, sé serio. Usa terminología correcta (escaños, parlamento, líderes).
    4. NO inventes cargos ni resultados que no estén en los datos.
    
    OBJETIVO: Escribe una noticia de 400 palabras.
    ESTRUCTURA: Titular impactante pero serio, Entradilla, Cuerpo desarrollado.
    
    Devuelve SOLO este JSON:
    {{
        "titular": "...",
        "cuerpo": "...",
        "categoria": "{noticia_cruda['seccion']}"
    }}
    """

    try:
        # Temperature baja = menos creatividad = menos locuras
        generation_config = genai.types.GenerationConfig(temperature=0.2)
        response = model.generate_content(prompt, generation_config=generation_config)

        texto_limpio = response.text.replace("```json", "").replace("```", "")
        start = texto_limpio.find("{")
        end = texto_limpio.rfind("}") + 1
        datos = json.loads(texto_limpio[start:end])

        # Recuperamos la imagen original del RSS (que suele ser la correcta)
        # Si no hay, ponemos placeholder
        if noticia_cruda["imagen"]:
            datos["imagen"] = noticia_cruda["imagen"]
        else:
            datos["imagen"] = (
                "https://via.placeholder.com/800x400?text=Noticia+en+Desarrollo"
            )

        return datos
    except Exception as e:
        print(f"❌ Error redactando: {e}")
        return None


def generar_html(articulos):
    fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans:wght@400;600&display=swap');
        body { font-family: 'Merriweather', serif; background: #fdfdfd; color: #111; margin: 0; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-left: 1px solid #eee; border-right: 1px solid #eee; }
        header { text-align: center; border-bottom: 4px double #000; padding-bottom: 30px; margin-bottom: 40px; }
        h1 { font-family: 'Merriweather', serif; font-size: 3.5rem; text-transform: uppercase; margin: 0; letter-spacing: -1px; }
        .meta { color: #555; font-family: 'Open Sans', sans-serif; font-size: 0.9rem; margin-top: 10px; text-transform: uppercase; letter-spacing: 1px; }
        
        article { margin-bottom: 80px; }
        .cat-label { font-family: 'Open Sans', sans-serif; font-weight: 700; font-size: 0.75rem; color: #c00; text-transform: uppercase; letter-spacing: 1px; display: block; margin-bottom: 10px; border-bottom: 1px solid #c00; display: inline-block; }
        h2 { font-size: 2.4rem; line-height: 1.1; margin: 0 0 20px 0; font-weight: 700; }
        
        .img-wrapper { width: 100%; height: 450px; background: #f0f0f0; margin-bottom: 25px; overflow: hidden; }
        img { width: 100%; height: 100%; object-fit: cover; filter: sepia(10%) contrast(1.05); }
        
        .cuerpo { font-family: 'Merriweather', serif; font-size: 1.1rem; line-height: 1.8; color: #2c2c2c; }
        .cuerpo p { margin-bottom: 20px; text-align: justify; }
        .cuerpo p:first-of-type::first-letter { float: left; font-size: 3.5rem; line-height: 0.8; padding-right: 10px; padding-top: 5px; font-weight: bold; }
    """

    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>El Diario Autónomo</title><style>{css}</style></head><body>
    <div class="container">
        <header>
            <h1>El Diario Autónomo</h1>
            <div class="meta">Edición Verificada • {fecha}</div>
        </header>
    """

    for art in articulos:
        # Convertir saltos de línea en párrafos HTML
        texto_html = "".join(
            [f"<p>{p}</p>" for p in art["cuerpo"].split("\n") if len(p) > 10]
        )

        html += f"""
        <article>
            <span class="cat-label">{art['categoria']}</span>
            <h2>{art['titular']}</h2>
            <div class="img-wrapper">
                <img src="{art['imagen']}" onerror="this.src='https://via.placeholder.com/800x400?text=Imagen+No+Disponible'">
            </div>
            <div class="cuerpo">{texto_html}</div>
        </article>
        <hr style="border:0; border-top:1px solid #eee; margin: 50px 0;">
        """

    html += "</div></body></html>"
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    raw_news = obtener_noticias_crudas()
    news_finales = []

    for item in raw_news:
        try:
            articulo = redactar_articulo_investigado(item)
            if articulo:
                news_finales.append(articulo)
                time.sleep(3)  # Pausa de seguridad
        except Exception as e:
            print(f"Fallo en bloque principal: {e}")

    if news_finales:
        generar_html(news_finales)
        print("✅ ¡Publicado correctamente!")
    else:
        print("❌ No se pudo generar ninguna noticia.")


if __name__ == "__main__":
    main()
