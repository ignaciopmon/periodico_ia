import feedparser
import google.generativeai as genai
import datetime
import os
import json
import time
import re
from duckduckgo_search import DDGS

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# CAMBIO CLAVE: Usamos Gemma 3 27B que tiene 14.400 peticiones/día según tu captura
MODEL_NAME = "gemma-3-27b-it"
model = genai.GenerativeModel(MODEL_NAME)

FUENTES = {
    "Política": [
        "https://www.elmundo.es/rss/espana.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana",
    ],
    "Economía": ["https://www.eleconomista.es/rss/rss-economia.php"],
    "Global": ["https://www.elmundo.es/rss/internacional.xml"],
    "Tecnología": ["https://www.xataka.com/index.xml"],
}


def limpiar_json(texto):
    """Limpia la respuesta de Gemma para sacar el JSON"""
    try:
        # Gemma a veces es muy charlatana, buscamos el primer { y el último }
        start = texto.find("{")
        end = texto.rfind("}") + 1
        if start != -1 and end != -1:
            json_str = texto[start:end]
            return json.loads(json_str)
        return None
    except:
        return None


def buscar_en_internet(query):
    """Función de búsqueda pura"""
    print(f"   🔎 Buscando: '{query}'...")
    try:
        with DDGS() as ddgs:
            # Buscamos definiciones y contexto
            results = ddgs.text(query, region="es-es", max_results=2)
            if results:
                return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        print(f"   ⚠️ Error búsqueda: {e}")
    return ""


def fase_1_analisis(noticia_cruda):
    """
    La IA decide QUÉ necesita saber antes de escribir.
    Aquí es donde arreglamos lo del 'Primer Ministro'.
    """
    print(f"🧠 Analizando qué investigar sobre: {noticia_cruda['titulo']}...")

    prompt = f"""
    Eres un jefe de redacción inteligente. Tienes este teletipo:
    "{noticia_cruda['titulo']} - {noticia_cruda['resumen_rss']}"
    
    Tu tarea NO es escribir la noticia aún. Tu tarea es decirme qué buscar en Google para no meter la pata.
    Si sale una persona (ej: 'Ishiba', 'Abascal'), pide buscar quién es y su cargo actual.
    
    Devuelve un JSON con una lista de 2 búsquedas exactas. Ejemplo:
    {{
        "busquedas": [
            "Quién es Shigeru Ishiba cargo actual",
            "Contexto dimisión Ishiba Japón"
        ]
    }}
    """

    try:
        response = model.generate_content(prompt)
        data = limpiar_json(response.text)
        if data and "busquedas" in data:
            return data["busquedas"]
        return [f"{noticia_cruda['titulo']} contexto"]  # Fallback
    except:
        return [f"{noticia_cruda['titulo']} noticia españa"]


def fase_3_redaccion(noticia_cruda, investigacion):
    """Escribe la noticia usando los datos recolectados"""
    print(f"✍️  Redactando noticia completa...")

    prompt = f"""
    Actúa como periodista experto. Escribe una noticia basada en estos datos.
    
    TITULAR ORIGINAL: "{noticia_cruda['titulo']}"
    
    INVESTIGACIÓN RECIENTE (USAR ESTOS DATOS PARA CONTEXTO Y CARGOS):
    {investigacion}
    
    INSTRUCCIONES:
    1. IDENTIDAD: Si la investigación dice que alguien es "Primer Ministro" o "CEO", ÚSALO. No digas "el político", di "El Primer Ministro...".
    2. CONTEXTO: Usa los datos buscados para explicar por qué es importante.
    3. ESTILO: Serio, informativo, sin opiniones personales (salvo que sea categoría Opinión).
    4. EXTENSIÓN: Unas 300-400 palabras.
    
    Devuelve SOLO este JSON:
    {{
        "titular": "Titular periodístico mejorado",
        "cuerpo": "Cuerpo de la noticia con saltos de línea...",
        "categoria": "{noticia_cruda['seccion']}"
    }}
    """

    try:
        response = model.generate_content(prompt)
        return limpiar_json(response.text)
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
                    # Cogemos hasta 3 noticias por fuente para aprovechar el volumen de Gemma
                    for entry in feed.entries[:2]:
                        imagen = None
                        if "media_content" in entry:
                            imagen = entry.media_content[0]["url"]
                        elif "links" in entry:
                            for link in entry.links:
                                if link["type"].startswith("image"):
                                    imagen = link["href"]
                                    break

                        if not imagen:
                            imagen = "https://via.placeholder.com/800x400?text=Noticia+Global"

                        noticias.append(
                            {
                                "titulo": entry.title,
                                "resumen_rss": entry.summary,
                                "seccion": categoria,
                                "imagen": imagen,
                            }
                        )
            except:
                continue
    return noticias


def generar_html(articulos):
    # (El mismo HTML bonito de antes, resumido para no ocupar espacio, pero funcional)
    css = """body{font-family:'Georgia',serif;background:#f4f4f4;max-width:900px;margin:20px auto;padding:20px;background:white;}
             h1{text-align:center;text-transform:uppercase;border-bottom:2px solid black;}
             article{border-bottom:1px solid #ddd;padding:30px 0;} img{width:100%;height:400px;object-fit:cover;}
             h2{font-size:2em;margin:10px 0;} .tag{color:red;font-weight:bold;text-transform:uppercase;}
             p{line-height:1.6;font-size:1.1em;color:#333;}"""

    html = (
        f"<html><head><style>{css}</style></head><body><h1>Diario Inteligente IA</h1>"
    )
    html += f"<p style='text-align:center'>Actualizado: {datetime.datetime.now().strftime('%H:%M')}</p>"

    for art in articulos:
        # Formateo de párrafos
        cuerpo = "".join(
            [
                f"<p>{linea}</p>"
                for linea in art["cuerpo"].split("\n")
                if len(linea) > 20
            ]
        )
        html += f"""
        <article>
            <span class="tag">{art['categoria']}</span>
            <h2>{art['titular']}</h2>
            <img src="{art['imagen']}" onerror="this.src='https://via.placeholder.com/800x400?text=Imagen+No+Disponible'">
            {cuerpo}
        </article>
        """
    html += "</body></html>"
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    raw_news = obtener_noticias()
    # Para no saturar en pruebas, cogemos 4 aleatorias, pero Gemma aguanta muchas más
    import random

    if len(raw_news) > 8:
        raw_news = random.sample(raw_news, 8)

    finales = []

    for item in raw_news:
        try:
            # 1. ¿Qué necesito saber?
            dudas = fase_1_analisis(item)

            # 2. Investigar esas dudas
            contexto_acumulado = ""
            for duda in dudas:
                info = buscar_en_internet(duda)
                contexto_acumulado += f"\nINFO SOBRE '{duda}':\n{info}\n"

            # 3. Escribir con sabiduría
            if contexto_acumulado:
                noticia = fase_3_redaccion(item, contexto_acumulado)
                if noticia:
                    noticia["imagen"] = item["imagen"]
                    finales.append(noticia)
                    print(f"✅ Noticia generada: {noticia['titular'][:30]}...")

            # Gemma tiene mucho limite diario (RPD) pero cuidado con el RPM (minuto)
            # Esperamos 4 segundos entre noticias para ir seguros
            time.sleep(4)

        except Exception as e:
            print(f"Error en noticia: {e}")

    if finales:
        generar_html(finales)
        print("🎉 ¡Periódico publicado!")


if __name__ == "__main__":
    main()
