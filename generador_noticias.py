import feedparser
import google.generativeai as genai
import datetime
import os
import json
import random

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Usamos el modelo rápido y gratuito
model = genai.GenerativeModel("gemini-2.5-flash")

# --- FUENTES DIVERSIFICADAS ---
# Diccionario para obligar a coger temas distintos
FUENTES = {
    "Actualidad": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "Tecnología": "https://www.xataka.com/index.xml",
    "Cultura": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/cultura",
    "Economía": "https://www.eleconomista.es/rss/rss-economia.php",
}


def limpiar_json(texto_sucio):
    """Limpia el texto markdown que a veces devuelve la IA"""
    texto = texto_sucio.replace("```json", "").replace("```", "")
    start = texto.find("{")
    end = texto.rfind("}") + 1
    if start != -1 and end != -1:
        return texto[start:end]
    return texto


def obtener_noticias_crudas():
    print("📰 Buscando noticias variadas en la red...")
    noticias_seleccionadas = []

    # Recorremos cada categoría para asegurar variedad
    for categoria, url_feed in FUENTES.items():
        try:
            feed = feedparser.parse(url_feed)
            if feed.entries:
                # Cogemos la primera entrada de cada sección (la más nueva)
                # Si queremos más variedad, podríamos hacer random.choice(feed.entries[:3])
                entry = feed.entries[0]

                imagen = None
                # Intentamos pescar la imagen
                if "media_content" in entry:
                    imagen = entry.media_content[0]["url"]
                elif "links" in entry:
                    for link in entry.links:
                        if link["type"].startswith("image"):
                            imagen = link["href"]
                            break

                noticias_seleccionadas.append(
                    {
                        "titulo_original": entry.title,
                        "resumen": entry.summary[
                            :500
                        ],  # Limitamos texto para no saturar
                        "link_origen": entry.link,
                        "imagen": imagen,
                        "seccion_origen": categoria,
                    }
                )
        except Exception as e:
            print(f"⚠️ Error leyendo feed de {categoria}: {e}")

    return noticias_seleccionadas


def redactar_articulo(noticia_cruda):
    # Decidir si hacemos noticia normal o artículo de opinión (30% prob)
    tipo_articulo = "Noticia"
    estilo = "objetivo y periodístico"
    extra_prompt = ""

    if random.random() < 0.3:
        tipo_articulo = "Opinión"
        estilo = "subjetivo, crítico, con un toque de humor ácido o filosófico"
        extra_prompt = "No te limites a informar, da tu opinión de IA sobre por qué esto es importante o ridículo."

    print(f"✍️ Redactando ({tipo_articulo}): {noticia_cruda['titulo_original']}...")

    prompt = f"""
    Actúa como un redactor de periódico IA. Tienes que escribir un artículo breve basado en esto:
    Contexto: "{noticia_cruda['resumen']}"
    Sección original: {noticia_cruda['seccion_origen']}
    
    TIPO DE ARTÍCULO: {tipo_articulo}
    ESTILO: {estilo}
    {extra_prompt}
    
    Instrucciones:
    1. Titular: Máximo 10 palabras. Impactante.
    2. Cuerpo: Máximo 120 palabras.
    3. Categoría: Usa una sola palabra (ej: Política, Tech, Cine, Dinero, Reflexión).
    4. Devuelve SOLO un JSON válido con este formato:
    {{
        "titular": "...",
        "cuerpo": "...",
        "categoria": "..."
    }}
    """

    try:
        response = model.generate_content(prompt)
        texto_limpio = limpiar_json(response.text)
        datos = json.loads(texto_limpio)

        # Añadimos metadatos extra
        datos["imagen"] = noticia_cruda["imagen"]
        datos["tipo"] = tipo_articulo  # Para pintar diferente si es opinión
        return datos
    except Exception as e:
        print(f"❌ Error al generar texto con IA: {e}")
        return None


def generar_html(articulos):
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    css = """
        body { font-family: 'Georgia', serif; background: #f0f0f0; margin: 0; padding: 20px; color: #333; }
        header { text-align: center; border-bottom: 4px double #333; padding-bottom: 20px; margin-bottom: 30px; }
        h1 { font-family: 'Impact', sans-serif; font-size: 4em; margin: 0; text-transform: uppercase; letter-spacing: -2px; }
        .subtitulo { font-style: italic; color: #555; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 25px; max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; border: 1px solid #ccc; box-shadow: 3px 3px 10px rgba(0,0,0,0.1); transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
        .tag { background: #333; color: white; padding: 4px 8px; font-size: 0.7em; text-transform: uppercase; font-weight: bold; }
        .opinion-tag { background: #d9534f; } /* Rojo para opinión */
        img { width: 100%; height: 200px; object-fit: cover; margin: 10px 0; filter: sepia(20%); }
        h2 { font-size: 1.4em; margin: 10px 0; line-height: 1.2; font-family: 'Arial', sans-serif; font-weight: bold; }
        p { font-size: 0.95em; line-height: 1.5; color: #444; }
        footer { margin-top: 50px; text-align: center; font-size: 0.8em; color: #777; border-top: 1px solid #ccc; padding-top: 20px; }
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
        <header>
            <h1>EL DIARIO AUTÓNOMO</h1>
            <p class="subtitulo">Noticias curadas y escritas por Inteligencia Artificial</p>
            <p><strong>Edición:</strong> {fecha_actual}</p>
        </header>
        
        <div class="grid">
    """

    for art in articulos:
        # Lógica visual para opinión vs noticia normal
        clase_tag = "opinion-tag" if art.get("tipo") == "Opinión" else ""
        etiqueta_visual = (
            "OPINIÓN" if art.get("tipo") == "Opinión" else art["categoria"]
        )

        img_html = f'<img src="{art["imagen"]}">' if art["imagen"] else ""

        html += f"""
            <article class="card">
                <span class="tag {clase_tag}">{etiqueta_visual}</span>
                {img_html}
                <h2>{art['titular']}</h2>
                <p>{art['cuerpo']}</p>
            </article>
        """

    html += """
        </div>
        <footer>
            <p>Proyecto experimental de redacción autónoma.</p>
        </footer>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    raw_news = obtener_noticias_crudas()

    articulos_finales = []
    for raw in raw_news:
        # Pequeña pausa para no saturar si hiciera falta, pero con Flash no suele hacer falta
        articulo = redactar_articulo(raw)
        if articulo:
            articulos_finales.append(articulo)

    if articulos_finales:
        generar_html(articulos_finales)
        print("✅ ¡Edición publicada con éxito!")
    else:
        print("⚠️ No se han podido generar noticias.")


if __name__ == "__main__":
    main()
