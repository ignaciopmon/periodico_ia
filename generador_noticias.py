import feedparser
import google.generativeai as genai
import datetime
import os
import json

# --- CONFIGURACIÓN ---
# Aquí pondrás tu API KEY gratuita de Google AI Studio
API_KEY = os.environ.get("GEMINI_API_KEY") 
genai.configure(api_key=API_KEY)

# Fuentes de noticias (RSS) - Puedes añadir más
FUENTES = [
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "https://www.elmundo.es/rss/portada.xml",
    "http://ep00.epimg.net/rss/tags/ultimas_noticias.xml"
]

# Configuración del modelo
model = genai.GenerativeModel("gemini-2.5-flash")

def obtener_noticias_crudas():
    print("Buscando noticias en la red...")
    noticias = []
    for fuente in FUENTES:
        feed = feedparser.parse(fuente)
        for entry in feed.entries[:3]: # Cogemos las 3 primeras de cada medio
            imagen = None
            # Intentar encontrar imagen en el RSS
            if 'media_content' in entry:
                imagen = entry.media_content[0]['url']
            elif 'links' in entry:
                for link in entry.links:
                    if link['type'].startswith('image'):
                        imagen = link['href']
            
            noticias.append({
                "titulo_original": entry.title,
                "resumen": entry.summary,
                "link_origen": entry.link,
                "imagen": imagen
            })
    return noticias

def redactar_noticia(noticia_cruda):
    print(f"Redactando: {noticia_cruda['titulo_original']}...")
    
    prompt = f"""
    Eres un periodista de IA cínico, objetivo y moderno. 
    Escribe una noticia breve basada en esta información: "{noticia_cruda['resumen']}".
    
    Reglas:
    1. Inventa un titular llamativo (máximo 10 palabras).
    2. Escribe el cuerpo de la noticia (máximo 150 palabras).
    3. Decide una categoría (Política, Tecnología, Sociedad, Opinión).
    4. Devuelve el resultado SOLO en formato JSON así:
    {{
        "titular": "...",
        "cuerpo": "...",
        "categoria": "..."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Limpiamos el texto por si la IA pone ```json al principio
        texto_limpio = response.text.replace("```json", "").replace("```", "")
        datos_generados = json.loads(texto_limpio)
        return datos_generados
    except Exception as e:
        print(f"Error redactando: {e}")
        return None

def generar_html(articulos):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>El Diario Autónomo</title>
        <style>
            body {{ font-family: 'Courier New', monospace; background: #f4f4f4; margin: 0; padding: 20px; }}
            header {{ text-align: center; border-bottom: 3px solid black; padding-bottom: 20px; margin-bottom: 30px; }}
            h1 {{ font-size: 3em; margin: 0; text-transform: uppercase; }}
            .fecha {{ color: #666; font-style: italic; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
            .card {{ background: white; padding: 20px; border: 1px solid #ddd; box-shadow: 5px 5px 0px #000; }}
            .categoria {{ background: black; color: white; padding: 3px 8px; font-size: 0.8em; text-transform: uppercase; }}
            .imagen-noticia {{ width: 100%; height: 200px; object-fit: cover; filter: grayscale(100%); margin-bottom: 10px; }}
            h2 {{ font-size: 1.5em; margin-top: 10px; }}
            .opinion {{ background: #fff0f0; border: 2px solid red; }}
        </style>
    </head>
    <body>
        <header>
            <h1>El Diario Autónomo</h1>
            <p>Escrito, editado y dirigido por Inteligencia Artificial</p>
            <p class="fecha">Última actualización: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </header>
        
        <div class="grid">
    """
    
    for art in articulos:
        clase_extra = "opinion" if art['categoria'] == "Opinión" else ""
        img_html = f'<img src="{art["imagen"]}" class="imagen-noticia">' if art["imagen"] else ''
        
        html_content += f"""
            <article class="card {clase_extra}">
                <span class="categoria">{art['categoria']}</span>
                {img_html}
                <h2>{art['titular']}</h2>
                <p>{art['cuerpo']}</p>
            </article>
        """

    html_content += """
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    raw_news = obtener_noticias_crudas()
    # Seleccionamos solo 6 noticias para no gastar cuota de API
    raw_news = raw_news[:6] 
    
    articulos_finales = []
    
    for raw in raw_news:
        redaccion = redactar_noticia(raw)
        if redaccion:
            redaccion['imagen'] = raw['imagen']
            articulos_finales.append(redaccion)
    
    generar_html(articulos_finales)
    print("¡Periódico publicado!")

if __name__ == "__main__":
    main()
