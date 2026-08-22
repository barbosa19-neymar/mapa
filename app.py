import streamlit as st
import folium
import requests
import html
import os
import sqlite3
import pandas as pd
from datetime import datetime
from streamlit_folium import st_folium
import plotly.express as px
from xml.sax.saxutils import escape as xml_escape


# ==========================================================
# CONFIGURAÇÃO
# ==========================================================

st.set_page_config(
    page_title="Mapa de Nossa Senhora do Socorro",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Centro aproximado do município
DEFAULT_LAT = -10.855
DEFAULT_LON = -37.125

# Usado apenas como fallback caso a consulta por área falhe
RAIO_METROS = 12000

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DB = "mapa_socorro.db"


# ==========================================================
# ESTILO
# ==========================================================

st.markdown(
    """
    <style>
    .main {
        background-color: #f5f7fa;
    }

    .card {
        background: white;
        padding: 20px;
        border-radius: 16px;
        margin-bottom: 15px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.08);
    }

    .badge {
        background: #173b57;
        color: white;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 13px;
    }

    .history-box {
        background: linear-gradient(135deg, #173b57, #256d8f);
        color: white;
        padding: 25px;
        border-radius: 16px;
        margin-bottom: 20px;
    }

    .source-box {
        background: #eef4f8;
        padding: 15px;
        border-radius: 12px;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# BANCO DE DADOS
# ==========================================================

def conectar():
    return sqlite3.connect(DB)


def criar_banco():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT,
            endereco TEXT,
            telefone TEXT,
            horario TEXT,
            site TEXT,
            imagem TEXT,
            latitude REAL,
            longitude REAL,
            avaliacao REAL DEFAULT 0,
            fonte TEXT DEFAULT 'Cadastro manual',
            criado_em TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pesquisas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termo TEXT,
            data TEXT
        )
        """
    )

    # Migração simples para bancos antigos do projeto
    colunas = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(locais)").fetchall()
    }

    if "fonte" not in colunas:
        cursor.execute(
            "ALTER TABLE locais ADD COLUMN fonte TEXT DEFAULT 'Cadastro manual'"
        )

    conn.commit()
    conn.close()


criar_banco()


# ==========================================================
# CATEGORIAS DO MAPA
# ==========================================================

CATEGORIAS = [
    "Comércio",
    "Alimentação",
    "Mercado",
    "Saúde",
    "Educação",
    "Religião",
    "Cultura",
    "Turismo e lazer",
    "Esporte",
    "Serviço",
    "Hotel",
    "Transporte",
    "Órgão público",
    "Outro",
]


def classificar_categoria(tags):
    shop = tags.get("shop", "")
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    healthcare = tags.get("healthcare", "")
    office = tags.get("office", "")
    craft = tags.get("craft", "")
    railway = tags.get("railway", "")
    public_transport = tags.get("public_transport", "")
    building = tags.get("building", "")

    if healthcare:
        return "Saúde"

    if amenity in {
        "hospital",
        "clinic",
        "doctors",
        "dentist",
        "pharmacy",
        "veterinary",
        "nursing_home",
    }:
        return "Saúde"

    if amenity in {"school", "kindergarten", "college", "university"}:
        return "Educação"

    if tags.get("education"):
        return "Educação"

    if amenity in {"place_of_worship", "monastery", "grave_yard"}:
        return "Religião"

    if building in {"church", "chapel", "mosque", "synagogue", "temple"}:
        return "Religião"

    if amenity in {"restaurant", "cafe", "fast_food", "food_court", "ice_cream"}:
        return "Alimentação"

    if shop in {"supermarket", "convenience", "greengrocer", "bakery"}:
        return "Mercado"

    if shop:
        return "Comércio"

    if tourism in {"hotel", "guest_house", "hostel", "motel"}:
        return "Hotel"

    if tourism in {"museum", "gallery", "attraction", "arts_centre"}:
        return "Cultura"

    if leisure in {
        "park",
        "sports_centre",
        "stadium",
        "pitch",
        "playground",
        "fitness_centre",
        "swimming_pool",
    }:
        return "Turismo e lazer"

    if amenity in {
        "library",
        "theatre",
        "cinema",
        "community_centre",
        "social_centre",
    }:
        return "Cultura"

    if amenity in {"bus_station", "bus_stop", "taxi"} or public_transport or railway:
        return "Transporte"

    if office or craft:
        return "Serviço"

    if amenity in {
        "townhall",
        "police",
        "fire_station",
        "post_office",
        "courthouse",
        "government",
    }:
        return "Órgão público"

    return "Outro"


def montar_endereco(tags):
    partes = []

    for chave in [
        "addr:street",
        "addr:housenumber",
        "addr:suburb",
        "addr:neighbourhood",
        "addr:city",
    ]:
        valor = tags.get(chave)
        if valor:
            partes.append(valor)

    return ", ".join(partes)


def gerar_descricao_osm(nome, categoria, tags):
    tipo = (
        tags.get("shop")
        or tags.get("amenity")
        or tags.get("tourism")
        or tags.get("healthcare")
        or tags.get("leisure")
        or tags.get("office")
        or tags.get("craft")
        or ""
    )

    if tipo:
        return f"{nome} foi localizado no OpenStreetMap e classificado no projeto como {categoria} ({tipo})."

    return f"{nome} é um local classificado no projeto como {categoria}."


# ==========================================================
# OPENSTREETMAP / OVERPASS
# ==========================================================

def buscar_locais_osm():
    # Primeiro tenta consultar a área administrativa do município.
    query_area = """
    [out:json][timeout:120];
    area["name"="Nossa Senhora do Socorro"]["boundary"="administrative"]["admin_level"="6"]->.socorro;

    (
      nwr(area.socorro)["name"]["shop"];
      nwr(area.socorro)["name"]["amenity"];
      nwr(area.socorro)["name"]["healthcare"];
      nwr(area.socorro)["name"]["tourism"];
      nwr(area.socorro)["name"]["leisure"];
      nwr(area.socorro)["name"]["office"];
      nwr(area.socorro)["name"]["craft"];
      nwr(area.socorro)["name"]["public_transport"];
      nwr(area.socorro)["name"]["railway"];
    );

    out center tags;
    """

    # Fallback por raio caso a área administrativa não seja encontrada.
    query_raio = f"""
    [out:json][timeout:120];

    (
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["shop"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["amenity"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["healthcare"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["tourism"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["leisure"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["office"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["craft"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["public_transport"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["railway"];
    );

    out center tags;
    """

    try:
        resposta = requests.post(
            OVERPASS_URL,
            data=query_area,
            timeout=150,
            headers={"User-Agent": "MapaSocorro/1.0"},
        )

        resposta.raise_for_status()
        dados = resposta.json()

        # Se a consulta por área não retornou elementos, usa o fallback.
        if not dados.get("elements"):
            resposta = requests.post(
                OVERPASS_URL,
                data=query_raio,
                timeout=150,
                headers={"User-Agent": "MapaSocorro/1.0"},
            )
            resposta.raise_for_status()
            dados = resposta.json()

        locais = []

        for item in dados.get("elements", []):
            tags = item.get("tags", {})
            nome = tags.get("name")

            if not nome:
                continue

            latitude = item.get("lat")
            longitude = item.get("lon")

            if latitude is None:
                center = item.get("center", {})
                latitude = center.get("lat")
                longitude = center.get("lon")

            if latitude is None or longitude is None:
                continue

            categoria = classificar_categoria(tags)

            locais.append(
                {
                    "nome": nome,
                    "categoria": categoria,
                    "descricao": gerar_descricao_osm(nome, categoria, tags),
                    "endereco": montar_endereco(tags),
                    "telefone": tags.get("phone", ""),
                    "horario": tags.get("opening_hours", ""),
                    "site": tags.get("website", ""),
                    "imagem": tags.get("image", ""),
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "avaliacao": 0,
                    "fonte": "OpenStreetMap",
                }
            )

        # Remove duplicados
        unicos = {}
        for local in locais:
            chave = (
                local["nome"].lower().strip(),
                round(local["latitude"], 5),
                round(local["longitude"], 5),
            )
            unicos[chave] = local

        return list(unicos.values())

    except Exception as e:
        st.error(f"Não foi possível carregar os pontos do OpenStreetMap: {e}")
        return []


# ==========================================================
# BANCO
# ==========================================================

def carregar_locais_banco():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            nome, categoria, descricao, endereco, telefone,
            horario, site, imagem, latitude, longitude,
            avaliacao, fonte
        FROM locais
        """
    )

    linhas = cursor.fetchall()
    conn.close()

    locais = []

    for linha in linhas:
        locais.append(
            {
                "nome": linha[0],
                "categoria": linha[1],
                "descricao": linha[2] or "",
                "endereco": linha[3] or "",
                "telefone": linha[4] or "",
                "horario": linha[5] or "",
                "site": linha[6] or "",
                "imagem": linha[7] or "",
                "latitude": linha[8],
                "longitude": linha[9],
                "avaliacao": linha[10] or 0,
                "fonte": linha[11] or "Cadastro manual",
            }
        )

    return locais


@st.cache_data(ttl=600)
def carregar_pontos():
    return buscar_locais_osm() + carregar_locais_banco()


locais = carregar_pontos()


# ==========================================================
# EXPORTAÇÃO PARA GOOGLE MY MAPS
# ==========================================================

def criar_dataframe_exportacao(pontos):
    linhas = []

    for local in pontos:
        if local.get("latitude") is None or local.get("longitude") is None:
            continue

        linhas.append(
            {
                "Nome": local.get("nome", ""),
                "Categoria": local.get("categoria", ""),
                "Descrição": local.get("descricao", ""),
                "Endereço": local.get("endereco", ""),
                "Telefone": local.get("telefone", ""),
                "Horário": local.get("horario", ""),
                "Site": local.get("site", ""),
                "Latitude": local.get("latitude"),
                "Longitude": local.get("longitude"),
                "Fonte": local.get("fonte", ""),
            }
        )

    return pd.DataFrame(linhas)


def criar_kml(pontos):
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        "<name>Mapa de Nossa Senhora do Socorro - SE</name>",
    ]

    for local in pontos:
        lat = local.get("latitude")
        lon = local.get("longitude")

        if lat is None or lon is None:
            continue

        nome = xml_escape(str(local.get("nome", "")))
        categoria = xml_escape(str(local.get("categoria", "")))
        descricao = xml_escape(
            f"Categoria: {local.get('categoria', '')}\n"
            f"Endereço: {local.get('endereco', '')}\n"
            f"Telefone: {local.get('telefone', '')}\n"
            f"Horário: {local.get('horario', '')}\n"
            f"Fonte: {local.get('fonte', '')}"
        )

        partes.extend(
            [
                "<Placemark>",
                f"<name>{nome}</name>",
                f"<description>{descricao}</description>",
                f"<ExtendedData><Data name=\"Categoria\"><value>{categoria}</value></Data></ExtendedData>",
                "<Point>",
                f"<coordinates>{lon},{lat},0</coordinates>",
                "</Point>",
                "</Placemark>",
            ]
        )

    partes.extend(["</Document>", "</kml>"])
    return "\n".join(partes)


def perguntar_ia(local, pergunta):
    chave = obter_chave_openrouter()

    if not chave:
        return (
            "⚠️ A SergIA ainda não está configurada.\n\n"
            "Coloque sua OPENROUTER_API_KEY nos Secrets do Streamlit."
        )

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=chave,
            base_url="https://openrouter.ai/api/v1"
        )

        contexto = f"""
Nome: {local.get('nome', '')}
Categoria: {local.get('categoria', '')}
Descrição: {local.get('descricao', '')}
Endereço: {local.get('endereco', '')}
Telefone: {local.get('telefone', '')}
Horário: {local.get('horario', '')}
Site: {local.get('site', '')}
Fonte: {local.get('fonte', '')}
Latitude: {local.get('latitude', '')}
Longitude: {local.get('longitude', '')}
"""

        instrucoes = """
Você é a SergIA, assistente cultural e informativa de Nossa Senhora do Socorro-SE.

Responda em português do Brasil.

Regras:
1. Não invente fatos.
2. Diferencie dados do OpenStreetMap, cadastro manual e informações históricas.
3. Quando não houver informação suficiente, diga isso claramente.
4. Não trate um cadastro do mapa como prova de que um estabelecimento está funcionando atualmente.
5. Ao falar de um estabelecimento, use primeiro os dados fornecidos pelo mapa.
6. Seja clara, curta e amigável.
7. O projeto abrange todo o município de Nossa Senhora do Socorro, Sergipe.
"""

        prompt = f"""
DADOS DO LOCAL:
{contexto}

PERGUNTA:
{pergunta}
"""

        resposta = client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {"role": "system", "content": instrucoes},
                {"role": "user", "content": prompt}
            ]
        )

        return resposta.choices[0].message.content

    except Exception as e:
        return f"❌ Erro ao consultar a SergIA:\n\n{e}"


# ==========================================================
# CABEÇALHO
# ==========================================================

st.markdown("# 🗺️ Mapa de Nossa Senhora do Socorro")

st.markdown(
    """
    Explore **comércios, alimentação, saúde, educação, religião,
    cultura, lazer, transporte e serviços** de Nossa Senhora do Socorro-SE.
    """
)

st.info("📍 Nossa Senhora do Socorro — Sergipe")


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title("🎛️ Explorar")

categorias_disponiveis = sorted(
    set(local["categoria"] for local in locais)
)

categorias_selecionadas = st.sidebar.multiselect(
    "Categorias",
    categorias_disponiveis,
    default=categorias_disponiveis,
)

st.sidebar.markdown("---")

mostrar_mapa = st.sidebar.checkbox("🗺️ Mostrar mapa", True)

if st.sidebar.button("🔄 Atualizar pontos"):
    carregar_pontos.clear()
    st.rerun()

st.sidebar.markdown("---")

st.sidebar.info(
    """
    📍 Dados de locais:
    OpenStreetMap + cadastros do projeto

    🗺️ Exportação:
    CSV/KML para Google My Maps

    🤖 IA:
    SergIA
    """
)


# ==========================================================
# PESQUISA
# ==========================================================

st.subheader("🔎 Pesquisar")

with st.form("pesquisa_form"):
    pesquisa = st.text_input(
        "Pesquisar",
        placeholder="Ex: restaurante, escola, farmácia, igreja...",
        label_visibility="collapsed",
    )
    pesquisar = st.form_submit_button("🔍 Buscar")

termo = pesquisa.lower().strip()

resultados = []

for local in locais:
    if (
        categorias_selecionadas
        and local["categoria"] not in categorias_selecionadas
    ):
        continue

    texto = " ".join(
        [
            str(local.get("nome", "")),
            str(local.get("categoria", "")),
            str(local.get("descricao", "")),
            str(local.get("endereco", "")),
        ]
    ).lower()

    if not termo or termo in texto:
        resultados.append(local)

if pesquisar and termo:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pesquisas (termo, data) VALUES (?, ?)",
        (termo, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


# ==========================================================
# MÉTRICAS
# ==========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📍 Pontos", len(resultados))

with col2:
    st.metric(
        "🛍️ Comércio",
        len([x for x in resultados if x["categoria"] == "Comércio"]),
    )

with col3:
    st.metric(
        "🏥 Saúde",
        len([x for x in resultados if x["categoria"] == "Saúde"]),
    )

with col4:
    st.metric(
        "🏫 Educação",
        len([x for x in resultados if x["categoria"] == "Educação"]),
    )


# ==========================================================
# MAPA
# ==========================================================

if mostrar_mapa:
    st.subheader("📍 Mapa")

    mapa = folium.Map(
        location=[DEFAULT_LAT, DEFAULT_LON],
        zoom_start=13,
        control_scale=True,
        tiles="OpenStreetMap",
    )

    cores = {
        "Comércio": "blue",
        "Alimentação": "red",
        "Mercado": "green",
        "Saúde": "pink",
        "Educação": "darkblue",
        "Religião": "purple",
        "Cultura": "purple",
        "Turismo e lazer": "cadetblue",
        "Esporte": "green",
        "Serviço": "orange",
        "Hotel": "darkred",
        "Transporte": "black",
        "Órgão público": "darkgreen",
        "Outro": "gray",
    }

    icones = {
        "Comércio": "shopping-cart",
        "Alimentação": "cutlery",
        "Mercado": "shopping-cart",
        "Saúde": "plus-sign",
        "Educação": "education",
        "Religião": "home",
        "Cultura": "info-sign",
        "Turismo e lazer": "tree-conifer",
        "Esporte": "flag",
        "Serviço": "wrench",
        "Hotel": "bed",
        "Transporte": "road",
        "Órgão público": "briefcase",
        "Outro": "map-marker",
    }

    pontos_bounds = []

    for local in resultados:
        if local.get("latitude") is None or local.get("longitude") is None:
            continue

        nome = html.escape(str(local.get("nome", "")))
        categoria = html.escape(str(local.get("categoria", "")))
        descricao = html.escape(str(local.get("descricao", "")))
        endereco = html.escape(
            str(local.get("endereco") or "Endereço não informado")
        )
        horario = html.escape(
            str(local.get("horario") or "Horário não informado")
        )
        telefone = html.escape(
            str(local.get("telefone") or "Telefone não informado")
        )
        fonte = html.escape(str(local.get("fonte", "")))

        site = str(local.get("site") or "")
        site_html = ""

        if site:
            site_seguro = html.escape(site, quote=True)
            site_html = (
                f'<p>🌐 <a href="{site_seguro}" target="_blank">'
                "Visitar site</a></p>"
            )

        popup = f"""
        <div style="width:290px;font-family:Arial;">
            <h3 style="color:#173b57;">{nome}</h3>
            <p><b>🏷️ {categoria}</b></p>
            <p>{descricao}</p>
            <p>📍 {endereco}</p>
            <p>🕐 {horario}</p>
            <p>📞 {telefone}</p>
            {site_html}
            <hr>
            <small>Fonte: {fonte}</small>
        </div>
        """

        folium.Marker(
            location=[local["latitude"], local["longitude"]],
            tooltip=local["nome"],
            popup=folium.Popup(popup, max_width=350),
            icon=folium.Icon(
                color=cores.get(local["categoria"], "blue"),
                icon=icones.get(local["categoria"], "map-marker"),
            ),
        ).add_to(mapa)

        pontos_bounds.append(
            [local["latitude"], local["longitude"]]
        )

    if pontos_bounds:
        mapa.fit_bounds(pontos_bounds)

    legenda = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        width: 235px;
        background-color: white;
        border: 2px solid #999;
        z-index: 9999;
        font-size: 13px;
        padding: 12px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    ">
        <b>🗺️ Legenda</b><br><br>
        🔵 Comércio<br>
        🔴 Alimentação<br>
        🟢 Mercado<br>
        🩷 Saúde<br>
        🔷 Educação<br>
        🟣 Religião/Cultura<br>
        🟠 Serviços<br>
        ⚫ Transporte
    </div>
    """

    mapa.get_root().html.add_child(folium.Element(legenda))

    st_folium(
        mapa,
        width=None,
        height=650,
        returned_objects=[],
    )


# ==========================================================
# EXPORTAR PARA GOOGLE MY MAPS
# ==========================================================

st.markdown("---")
st.subheader("📥 Exportar para Google My Maps")

st.write(
    "Baixe os pontos do mapa e importe o arquivo em uma camada do Google My Maps."
)

df_exportacao = criar_dataframe_exportacao(resultados)

col_csv, col_kml = st.columns(2)

with col_csv:
    csv_bytes = df_exportacao.to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")

    st.download_button(
        "📄 Baixar CSV para My Maps",
        data=csv_bytes,
        file_name="mapa_nossa_senhora_do_socorro.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col_kml:
    kml_texto = criar_kml(resultados)

    st.download_button(
        "🌎 Baixar KML para My Maps",
        data=kml_texto.encode("utf-8"),
        file_name="mapa_nossa_senhora_do_socorro.kml",
        mime="application/vnd.google-earth.kml+xml",
        use_container_width=True,
    )

st.caption(
    "No Google My Maps: crie um mapa → Adicionar camada → Importar → "
    "selecione o CSV ou KML."
)


# ==========================================================
# LISTA DE LOCAIS
# ==========================================================

st.markdown("---")
st.subheader("📚 Locais encontrados")

if resultados:
    for indice, local in enumerate(resultados):
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)

            col1, col2 = st.columns([1, 3])

            with col1:
                imagem = local.get("imagem", "")

                if imagem:
                    st.image(
                        imagem,
                        use_container_width=True,
                    )
                else:
                    st.markdown(
                        """
                        <div style="
                            height:140px;
                            background:#eaf0f6;
                            border-radius:15px;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:45px;
                        ">📍</div>
                        """,
                        unsafe_allow_html=True,
                    )

            with col2:
                st.markdown(
                    f"""
                    <h2>{html.escape(str(local["nome"]))}</h2>
                    <span class="badge">
                        {html.escape(str(local["categoria"]))}
                    </span>
                    <p>{html.escape(str(local["descricao"]))}</p>
                    <p>📍 {html.escape(str(local.get("endereco") or "Endereço não informado"))}</p>
                    <p>🕐 {html.escape(str(local.get("horario") or "Horário não informado"))}</p>
                    <p>📞 {html.escape(str(local.get("telefone") or "Telefone não informado"))}</p>
                    <small>Fonte: {html.escape(str(local.get("fonte", "")))}</small>
                    """,
                    unsafe_allow_html=True,
                )

                if local.get("site"):
                    site = html.escape(
                        str(local["site"]),
                        quote=True,
                    )
                    st.markdown(
                        f'[🌐 Visitar site]({site})'
                    )

                if st.button(
                    "🤖 Conhecer este local com SergIA",
                    key=f"ia_{indice}",
                ):
                    with st.spinner("🤖 SergIA está preparando informações..."):
                        resposta = perguntar_ia(
                            local,
                            "Explique o que é este local e quais informações do mapa podem ser úteis para o visitante. Não invente.",
                        )
                    st.info(resposta)

            st.markdown("</div>", unsafe_allow_html=True)

else:
    st.warning("Nenhum ponto encontrado com os filtros atuais.")


# ==========================================================
# GRÁFICO
# ==========================================================

st.markdown("---")
st.subheader("📊 Dados do mapa")

contagem = {}

for local in resultados:
    categoria = local["categoria"]
    contagem[categoria] = contagem.get(categoria, 0) + 1

if contagem:
    dados = {
        "Categoria": list(contagem.keys()),
        "Quantidade": list(contagem.values()),
    }

    grafico = px.bar(
        dados,
        x="Categoria",
        y="Quantidade",
        color="Categoria",
        title="Locais por categoria",
    )

    grafico.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )

    st.plotly_chart(
        grafico,
        use_container_width=True,
    )


# ==========================================================
# CADASTRO MANUAL
# ==========================================================

st.markdown("---")
st.subheader("➕ Adicionar local")

with st.expander("Cadastrar um novo local"):
    with st.form("novo_local"):
        nome = st.text_input("Nome do local")

        categoria = st.selectbox(
            "Categoria",
            CATEGORIAS,
        )

        descricao = st.text_area("Descrição")
        endereco = st.text_input("Endereço")
        telefone = st.text_input("Telefone")
        horario = st.text_input("Horário de funcionamento")
        site = st.text_input("Site")
        imagem = st.text_input("URL da imagem")

        col1, col2 = st.columns(2)

        with col1:
            latitude = st.number_input(
                "Latitude",
                value=DEFAULT_LAT,
                format="%.6f",
            )

        with col2:
            longitude = st.number_input(
                "Longitude",
                value=DEFAULT_LON,
                format="%.6f",
            )

        avaliacao = st.slider(
            "Avaliação",
            0.0,
            5.0,
            0.0,
            0.1,
        )

        salvar = st.form_submit_button(
            "💾 Salvar local",
            type="primary",
        )

        if salvar:
            if not nome.strip():
                st.error("Digite o nome do local.")
            else:
                conn = conectar()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO locais (
                        nome, categoria, descricao, endereco,
                        telefone, horario, site, imagem,
                        latitude, longitude, avaliacao,
                        fonte, criado_em
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        nome.strip(),
                        categoria,
                        descricao,
                        endereco,
                        telefone,
                        horario,
                        site,
                        imagem,
                        latitude,
                        longitude,
                        avaliacao,
                        "Cadastro manual",
                        datetime.now().isoformat(),
                    ),
                )

                conn.commit()
                conn.close()

                carregar_pontos.clear()

                st.success("✅ Local cadastrado!")
                st.rerun()


# ==========================================================
# SERGIA
# ==========================================================

st.markdown("---")
st.subheader("🤖 SergIA — Assistente de Nossa Senhora do Socorro")

st.write(
    "Pergunte sobre um local do mapa ou sobre informações gerais "
    "relacionadas ao município."
)

if resultados:
    local_nomes = [local["nome"] for local in resultados]

    local_escolhido = st.selectbox(
        "Escolha um local",
        local_nomes,
    )

    local_ia = next(
        local
        for local in resultados
        if local["nome"] == local_escolhido
    )
else:
    local_ia = {
        "nome": "Nossa Senhora do Socorro",
        "categoria": "Município",
        "descricao": "Município de Sergipe.",
        "endereco": "Nossa Senhora do Socorro-SE",
        "telefone": "",
        "horario": "",
        "site": "",
        "latitude": DEFAULT_LAT,
        "longitude": DEFAULT_LON,
        "fonte": "Projeto",
    }

pergunta = st.text_area(
    "O que você quer saber?",
    placeholder="Ex: Quais tipos de locais aparecem no mapa?",
)

if st.button(
    "🤖 Perguntar à SergIA",
    type="primary",
):
    if not pergunta.strip():
        st.warning("Digite uma pergunta.")
    else:
        with st.spinner("🤖 SergIA está preparando a resposta..."):
            resposta = perguntar_ia(
                local_ia,
                pergunta,
            )

        st.markdown(
            """
            <div class="history-box">
                <h3>🤖 SergIA</h3>
                Assistente cultural e informativa
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(resposta)


# ==========================================================
# FONTES
# ==========================================================

st.markdown("---")
st.subheader("📚 Fontes")

st.markdown(
    """
    <div class="source-box">
    <b>Dados do mapa:</b><br>
    • OpenStreetMap / Overpass API<br>
    • Locais cadastrados manualmente no projeto<br><br>

    <b>Ferramentas:</b><br>
    • Python<br>
    • Streamlit<br>
    • Folium<br>
    • SQLite<br>
    • Plotly<br>
    • Google My Maps para visualização/importação dos arquivos exportados
    </div>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# RODAPÉ
# ==========================================================

st.markdown("---")
st.caption(
    "🗺️ Mapa de Nossa Senhora do Socorro • Sergipe • "
    "Python + Streamlit + OpenStreetMap + SQLite + OpenAI"
)
