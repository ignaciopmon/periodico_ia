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

# --- CASCADA DE MODELOS (PRIORIDAD) ---
# El script intentará usar el primero. Si da error 429 (cuota), saltará al segundo, etc.
# AJUSTA LOS NOMBRES TÉCNICOS SI TU API TIENE OTROS
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
        "https://www.abc.es/rss/2.0/espana/"
    ],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Tecnología": ["https://www.xataka.com/index.xml"],
    "Internacional": ["https://www.elmundo.es/rss/internacional.xml"]
}

# --- HERRAMIENTAS ---

def generar_con_fallback(prompt):
    """
    Intenta generar contenido rotando modelos si se acaba la cuota.
    """
    errores_acumulados = []

    for modelo_nombre in MODELOS_PRIORIDAD:
        try:
            # Instanciamos el modelo actual del bucle
            modelo_actual = genai.GenerativeModel(modelo_nombre, generation_config=generation_config)
            
            # Intentamos generar
            response = modelo_actual.generate_content(prompt)
            
            # Si llegamos aquí, funcionó
            return response
            
        except exceptions.ResourceExhausted:
            print(f"   ⚠️ Cuota excedida en {modelo_nombre}. Cambiando al siguiente modelo...")
            time.sleep(1) # Pequeña pausa para respirar
            continue # Saltamos a la siguiente iteración del bucle (siguiente modelo)
            
        except Exception as e:
            # Si el error es otro (ej: modelo no existe, error de seguridad), lo guardamos
            print(f"   ❌ Error en {modelo_nombre}: {e}")
            errores_acumulados.append(f"{modelo_nombre}: {str(e)}")
            if "429" in str(e): # A veces el 429 no salta como ResourceExhausted sino como excepción genérica
                 print(f"   ⚠️ Detectado 429 en texto. Cambiando modelo...")
                 continue
            # Si es otro error grave, quizás queramos seguir probando o parar. 
            # Por ahora seguimos probando por si es un error específico del modelo.
            continue

    print("   ☠️ TODOS LOS MODELOS FALLARON. No se pudo generar la noticia.")
    return None

def similitud_titulares(t1, t2):
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()

def buscar_info_extra(query):
    print(f"   🔎 Buscando alternativa: '{query}'...")
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region="es-es", max_results=2)
            if results:
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        print(f"   ⚠️ Fallo en búsqueda: {e}")
    return ""

def extraer_contenido(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            texto = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if texto and len(texto) > 300: 
                return texto
    except:
        pass
    return None

def redactar_noticia_ia(item, contenido_real):
    print(f"✍️  Reescribiendo: {item['titulo']}...")

    prompt = f"""
    Actúa como Editor Jefe de un periódico digital moderno.
    
    FUENTE ORIGINAL:
    {contenido_real[:7000]}
    
    INSTRUCCIONES:
    1. Escribe un titular potente, corto y directo (máximo 12 palabras).
    2. Redacta la noticia en 3 párrafos:
       - Párrafo 1: El gancho (qué ha pasado y por qué importa).
       - Párrafo 2: Los detalles y datos duros.
       - Párrafo 3: Contexto o conclusión.
    3. Estilo: Objetivo pero ameno. Nada de "En conclusión" o "Por otro lado".
    4. Categoria: Elige la más adecuada de la fuente.
    
    Responde SOLO con este JSON:
    {{
        "titular": "...",
        "resumen": "...",
        "cuerpo_html": "<p>...</p><p>...</p>", 
        "etiqueta": "{item['seccion']}"
    }}
    """
    
    # USAMOS LA NUEVA FUNCIÓN CON FALLBACK
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
    
    print("📡 Escaneando fuentes RSS...")
    for categoria, urls in FUENTES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    
                    # Filtro anti-repetición
                    es_repetida = False
                    for t_visto in titulares_vistos:
                        if similitud_titulares(entry.title, t_visto) > 0.65:
                            es_repetida = True
                            break
                    
                    if es_repetida:
                        continue
                        
                    titulares_vistos.append(entry.title)
                    
                    imagen = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=800&auto=format&fit=crop"
                    if "media_content" in entry and entry.media_content:
                        imagen = entry.media_content[0]["url"]
                    elif "links" in entry:
                        for link in entry.links:
                            if link["type"].startswith("image"):
                                imagen = link["href"]
                                break

                    raw_noticias.append({
                        "titulo": entry.title,
                        "link": entry.link,
                        "seccion": categoria,
                        "imagen": imagen,
                        "fecha": getattr(entry, "published", str(datetime.date.today()))
                    })
            except:
                continue
    return raw_noticias

def generar_html_moderno(noticias):
    css = """
    :root { --primary: #2c3e50; --accent: #e74c3c; --bg: #f4f7f6; }
    body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: var(--bg); margin: 0; padding: 20px; color: #333; }
    header { text-align: center; margin-bottom: 40px; padding: 20px 0; border-bottom: 2px solid #ddd; }
    h1 { font-size: 3em; margin: 0; color: var(--primary); letter-spacing: -1px; }
    .date { color: #7f8c8d; font-style: italic; margin-top: 5px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 25px; max-width: 1200px; margin: 0 auto; }
    .card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); transition: transform 0.2s; display: flex; flex-direction: column; }
    .card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
    .card-img { height: 200px; width: 100%; object-fit: cover; }
    .card-content { padding: 20px; flex-grow: 1; display: flex; flex-direction: column; }
    .tag { align-self: flex-start; background: var(--primary); color: white; padding: 4px 10px; border-radius: 4px; font-size: 0.75em; text-transform: uppercase; font-weight: bold; margin-bottom: 10px; }
    .tag.Economía { background: #27ae60; }
    .tag.Tecnología { background: #8e44ad; }
    .tag.Nacional { background: #c0392b; }
    h2 { margin: 0 0 10px 0; font-size: 1.4em; line-height: 1.3; color: var(--primary); }
    .body-text { font-size: 0.95em; line-height: 1.6; color: #555; flex-grow: 1; }
    .read-more { display: block; margin-top: 15px; text-align: right; color: var(--accent); text-decoration: none; font-weight: bold; font-size: 0.9em; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resumen Inteligente IA</title>
        <style>{css}</style>
    </head>
    <body>
        <header>
            <h1>Diario Inteligente</h1>
            <div class="date">{datetime.datetime.now().strftime('%d de %B de %Y - Actualizado a las %H:%M')}</div>
        </header>
        <div class="grid">
    """

    for n in noticias:
        html += f"""
        <article class="card">
            <img src="{n['imagen']}" class="card-img" onerror="this.src='https://via.placeholder.com/400x200'">
            <div class="card-content">
                <span class="tag {n['etiqueta']}">{n['etiqueta']}</span>
                <h2>{n['titular']}</h2>
                <div class="body-text">{n['cuerpo_html']}</div>
                <a href="{n['link']}" target="_blank" class="read-more">Leer fuente original →</a>
            </div>
        </article>
        """

    html += """
        </div>
        <footer style="text-align:center; padding: 40px; color:#aaa; font-size:0.8em;">
            Generado con Inteligencia Artificial • Editado automáticamente
        </footer>
    </body></html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    candidatos = obtener_y_filtrar_noticias()
    print(f"📰 Noticias únicas encontradas: {len(candidatos)}")
    
    import random
    seleccion = candidatos[:8] 

    noticias_finales = []
    
    for item in seleccion:
        texto = extraer_contenido(item['link'])
        
        if not texto:
            texto = buscar_info_extra(f"{item['titulo']} noticias resumen")
        
        if not texto or len(texto) < 200:
            print(f"⏩ Saltando {item['titulo']} (Sin información suficiente)")
            continue

        articulo = redactar_noticia_ia(item, texto)
        if articulo:
            articulo['imagen'] = item['imagen']
            articulo['link'] = item['link']
            noticias_finales.append(articulo)
            print(f"✅ Generada ({item['seccion']}): {articulo['titular']}")
        
        # Pausa para respetar la API (incluso con fallback, es mejor esperar un poco)
        time.sleep(3)

    if noticias_finales:
        generar_html_moderno(noticias_finales)
        print("🚀 Periódico publicado con éxito.")
    else:
        print("⚠️ No se generaron noticias hoy.")

if __name__ == "__main__":
    main()
