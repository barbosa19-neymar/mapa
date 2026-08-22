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

DEFAULT_LAT = -10.855
DEFAULT_LON = -37.125

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

DB = "mapa_socorro.db"

RAIO_METROS = 15000


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
        padding: 18px;
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
        background: linear-gradient(
            135deg,
            #173b57,
            #256d8f
        );
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

    .counter {
        background: #173b57;
        color: white;
        padding: 15px;
        border-radius: 14px;
        text-align: center;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# CATEGORIAS
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


# ==========================================================
# BANCO
# ==========================================================

def conectar():
    return sqlite3.connect(DB)


def garantir_coluna(cursor, tabela, coluna, definicao):
    colunas = {
        row[1]
        for row in cursor.execute(
            f"PRAGMA table_info({tabela})"
        ).fetchall()
    }

    if coluna not in colunas:
        cursor.execute(
            f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}"
        )


def criar_banco():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT,
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

    garantir_coluna(
        cursor,
        "locais",
        "categoria",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "descricao",
        "descricao",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "locais",
        "endereco",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "locais",
        "telefone",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "locais",
        "horario",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "locais",
        "site",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "locais",
        "imagem",
        "TEXT"
    )

    garantir_coluna(
        cursor,
        "locais",
        "latitude",
        "REAL"
    )

    garantir_coluna(
        cursor,
        "locais",
        "longitude",
        "REAL"
    )

    garantir_coluna(
        cursor,
        "locais",
        "avaliacao",
        "REAL DEFAULT 0"
    )

    garantir_coluna(
        cursor,
        "locais",
        "fonte",
        "TEXT DEFAULT 'Cadastro manual'"
    )

    garantir_coluna(
        cursor,
        "locais",
        "criado_em",
        "TEXT"
    )

    conn.commit()
    conn.close()


criar_banco()


# ==========================================================
# CLASSIFICAÇÃO
# ==========================================================

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

    # SAÚDE
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
        "health_centre",
        "physiotherapist",
        "optometrist",
    }:
        return "Saúde"

    # EDUCAÇÃO
    if amenity in {
        "school",
        "kindergarten",
        "college",
        "university",
        "music_school",
        "language_school",
    }:
        return "Educação"

    if tags.get("education"):
        return "Educação"

    # RELIGIÃO
    if amenity in {
        "place_of_worship",
        "monastery",
        "grave_yard",
    }:
        return "Religião"

    if building in {
        "church",
        "chapel",
        "mosque",
        "synagogue",
        "temple",
    }:
        return "Religião"

    # ALIMENTAÇÃO
    if amenity in {
        "restaurant",
        "cafe",
        "fast_food",
        "food_court",
        "ice_cream",
        "bar",
        "pub",
    }:
        return "Alimentação"

    # MERCADO
    if shop in {
        "supermarket",
        "convenience",
        "greengrocer",
        "bakery",
        "butcher",
        "beverages",
    }:
        return "Mercado"

    # COMÉRCIO
    if shop:
        return "Comércio"

    # HOTEL
    if tourism in {
        "hotel",
        "guest_house",
        "hostel",
        "motel",
        "apartment",
    }:
        return "Hotel"

    # CULTURA
    if tourism in {
        "museum",
        "gallery",
        "attraction",
        "arts_centre",
    }:
        return "Cultura"

    if amenity in {
        "library",
        "theatre",
        "cinema",
        "community_centre",
        "social_centre",
    }:
        return "Cultura"

    # LAZER / ESPORTE
    if leisure in {
        "park",
        "sports_centre",
        "stadium",
        "pitch",
        "playground",
        "fitness_centre",
        "swimming_pool",
        "recreation_ground",
    }:
        return "Turismo e lazer"

    if leisure in {
        "sports_hall",
        "track",
    }:
        return "Esporte"

    # TRANSPORTE
    if amenity in {
        "bus_station",
        "bus_stop",
        "taxi",
        "fuel",
    }:
        return "Transporte"

    if public_transport:
        return "Transporte"

    if railway:
        return "Transporte"

    # ÓRGÃO PÚBLICO
    if amenity in {
        "townhall",
        "police",
        "fire_station",
        "post_office",
        "courthouse",
        "government",
    }:
        return "Órgão público"

    # SERVIÇOS
    if office or craft:
        return "Serviço"

    return "Outro"


# ==========================================================
# ENDEREÇO
# ==========================================================

def montar_endereco(tags):

    partes = []

    for chave in [
        "addr:street",
        "addr:housenumber",
        "addr:suburb",
        "addr:neighbourhood",
        "addr:district",
        "addr:city",
    ]:

        valor = tags.get(chave)

        if valor:
            partes.append(str(valor))

    return ", ".join(partes)


# ==========================================================
# DESCRIÇÃO OSM
# ==========================================================

def gerar_descricao_osm(
    nome,
    categoria,
    tags
):

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

        return (
            f"{nome} foi localizado no "
            f"OpenStreetMap e classificado "
            f"como {categoria} ({tipo})."
        )

    return (
        f"{nome} é um local classificado "
        f"como {categoria}."
    )


# ==========================================================
# NORMALIZAR LOCAL
# ==========================================================

def normalizar_local(local):

    return {
        "nome": str(local.get("nome") or ""),
        "categoria": str(
            local.get("categoria")
            or "Outro"
        ),
        "descricao": str(
            local.get("descricao") or ""
        ),
        "endereco": str(
            local.get("endereco") or ""
        ),
        "telefone": str(
            local.get("telefone") or ""
        ),
        "horario": str(
            local.get("horario") or ""
        ),
        "site": str(
            local.get("site") or ""
        ),
        "imagem": str(
            local.get("imagem") or ""
        ),
        "latitude": local.get("latitude"),
        "longitude": local.get("longitude"),
        "avaliacao": float(
            local.get("avaliacao") or 0
        ),
        "fonte": str(
            local.get("fonte")
            or "Cadastro manual"
        ),
    }


# ==========================================================
# CARREGAR BANCO EXISTENTE
# ==========================================================

def carregar_locais_banco():

    conn = conectar()

    try:

        df = pd.read_sql_query(
            """
            SELECT
                nome,
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
                fonte
            FROM locais
            WHERE nome IS NOT NULL
            """,
            conn,
        )

    except Exception:

        df = pd.DataFrame()

    conn.close()

    locais = []

    if df.empty:
        return locais

    for _, linha in df.iterrows():

        local = normalizar_local(
            linha.to_dict()
        )

        if (
            local["latitude"] is not None
            and local["longitude"] is not None
        ):
            locais.append(local)

    return locais


# ==========================================================
# OVERPASS
# ==========================================================

def consulta_overpass(query):

    ultimo_erro = None

    for url in OVERPASS_URLS:

        try:

            resposta = requests.post(
                url,
                data=query,
                timeout=180,
                headers={
                    "User-Agent":
                    "MapaNossaSenhoraSocorro/2.0"
                },
            )

            resposta.raise_for_status()

            return resposta.json()

        except Exception as erro:

            ultimo_erro = erro

    raise ultimo_erro


# ==========================================================
# BUSCAR OSM
# ==========================================================

def buscar_locais_osm():

    query = f"""
    [out:json][timeout:180];

    (
        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"];

    );

    out center tags;
    """

    try:

        dados = consulta_overpass(query)

    except Exception as erro:

        st.warning(
            "Não foi possível atualizar "
            f"os dados do OpenStreetMap: {erro}"
        )

        return []

    locais = []

    for item in dados.get(
        "elements",
        []
    ):

        tags = item.get(
            "tags",
            {}
        )

        nome = tags.get("name")

        if not nome:
            continue

        latitude = item.get("lat")
        longitude = item.get("lon")

        if latitude is None:

            center = item.get(
                "center",
                {}
            )

            latitude = center.get(
                "lat"
            )

            longitude = center.get(
                "lon"
            )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        # Só considera elementos que realmente
        # possam representar um local.
        possui_categoria = any(
            tags.get(chave)
            for chave in [
                "shop",
                "amenity",
                "healthcare",
                "tourism",
                "leisure",
                "office",
                "craft",
                "public_transport",
                "railway",
            ]
        )

        if not possui_categoria:
            continue

        categoria = classificar_categoria(
            tags
        )

        local = {
            "nome": nome,
            "categoria": categoria,
            "descricao": gerar_descricao_osm(
                nome,
                categoria,
                tags,
            ),
            "endereco": montar_endereco(
                tags
            ),
            "telefone": tags.get(
                "phone",
                ""
            ),
            "horario": tags.get(
                "opening_hours",
                ""
            ),
            "site": tags.get(
                "website",
                ""
            ),
            "imagem": tags.get(
                "image",
                ""
            ),
            "latitude": float(
                latitude
            ),
            "longitude": float(
                longitude
            ),
            "avaliacao": 0,
            "fonte": "OpenStreetMap",
        }

        locais.append(local)

    return locais


# ==========================================================
# CHAVE DE DUPLICAÇÃO
# ==========================================================

def chave_local(local):

    nome = (
        str(
            local.get(
                "nome",
                ""
            )
        )
        .lower()
        .strip()
    )

    lat = local.get(
        "latitude"
    )

    lon = local.get(
        "longitude"
    )

    if lat is not None and lon is not None:

        return (
            nome,
            round(
                float(lat),
                5
            ),
            round(
                float(lon),
                5
            ),
        )

    return (
        nome,
        "",
        "",
    )


# ==========================================================
# JUNTAR PONTOS
# ==========================================================

def juntar_locais(
    antigos,
    novos
):

    resultado = {}

    # Primeiro entram os antigos.
    # Isso garante que a base histórica
    # não seja substituída.
    for local in antigos:

        local = normalizar_local(
            local
        )

        resultado[
            chave_local(local)
        ] = local

    # Depois entram os OSM.
    for local in novos:

        local = normalizar_local(
            local
        )

        chave = chave_local(
            local
        )

        if chave not in resultado:

            resultado[chave] = local

    return list(
        resultado.values()
    )


# ==========================================================
# SALVAR NOVOS OSM NO BANCO
# ==========================================================

def salvar_osm_no_banco(locais_osm):

    if not locais_osm:
        return 0

    conn = conectar()
    cursor = conn.cursor()

    existentes = set()

    cursor.execute(
        """
        SELECT nome, latitude, longitude
        FROM locais
        """
    )

    for nome, lat, lon in cursor.fetchall():

        if (
            lat is not None
            and lon is not None
        ):

            existentes.add(
                (
                    str(nome)
                    .lower()
                    .strip(),
                    round(
                        float(lat),
                        5
                    ),
                    round(
                        float(lon),
                        5
                    ),
                )
            )

    adicionados = 0

    for local in locais_osm:

        chave = chave_local(
            local
        )

        if chave in existentes:
            continue

        cursor.execute(
            """
            INSERT INTO locais (
                nome,
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
                fonte,
                criado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                local["nome"],
                local["categoria"],
                local["descricao"],
                local["endereco"],
                local["telefone"],
                local["horario"],
                local["site"],
                local["imagem"],
                local["latitude"],
                local["longitude"],
                0,
                "OpenStreetMap",
                datetime.now().isoformat(),
            ),
        )

        existentes.add(chave)

        adicionados += 1

    conn.commit()
    conn.close()

    return adicionados


# ==========================================================
# CARREGAMENTO PRINCIPAL
# ==========================================================

@st.cache_data(ttl=900)
def carregar_pontos():

    antigos = carregar_locais_banco()

    osm = buscar_locais_osm()

    return juntar_locais(
        antigos,
        osm
    )


# ==========================================================
# INICIALIZAÇÃO
# ==========================================================

locais = carregar_pontos()


# ==========================================================
# EXPORTAÇÃO
# ==========================================================

def criar_dataframe_exportacao(
    pontos
):

    linhas = []

    for local in pontos:

        if (
            local.get("latitude")
            is None
            or
            local.get("longitude")
            is None
        ):
            continue

        linhas.append(
            {
                "Nome": local.get(
                    "nome",
                    ""
                ),
                "Categoria": local.get(
                    "categoria",
                    ""
                ),
                "Descrição": local.get(
                    "descricao",
                    ""
                ),
                "Endereço": local.get(
                    "endereco",
                    ""
                ),
                "Telefone": local.get(
                    "telefone",
                    ""
                ),
                "Horário": local.get(
                    "horario",
                    ""
                ),
                "Site": local.get(
                    "site",
                    ""
                ),
                "Latitude": local.get(
                    "latitude"
                ),
                "Longitude": local.get(
                    "longitude"
                ),
                "Fonte": local.get(
                    "fonte",
                    ""
                ),
            }
        )

    return pd.DataFrame(
        linhas
    )


def criar_kml(pontos):

    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        "<name>Mapa de Nossa Senhora do Socorro - SE</name>",
    ]

    for local in pontos:

        lat = local.get(
            "latitude"
        )

        lon = local.get(
            "longitude"
        )

        if (
            lat is None
            or lon is None
        ):
            continue

        nome = xml_escape(
            str(
                local.get(
                    "nome",
                    ""
                )
            )
        )

        categoria = xml_escape(
            str(
                local.get(
                    "categoria",
                    ""
                )
            )
        )

        descricao = xml_escape(
            (
                f"Categoria: "
                f"{local.get('categoria', '')}\n"
                f"Endereço: "
                f"{local.get('endereco', '')}\n"
                f"Telefone: "
                f"{local.get('telefone', '')}\n"
                f"Horário: "
                f"{local.get('horario', '')}\n"
                f"Fonte: "
                f"{local.get('fonte', '')}"
            )
        )

        partes.extend(
            [
                "<Placemark>",
                f"<name>{nome}</name>",
                f"<description>{descricao}</description>",
                (
                    "<ExtendedData>"
                    "<Data name=\"Categoria\">"
                    f"<value>{categoria}</value>"
                    "</Data>"
                    "</ExtendedData>"
                ),
                "<Point>",
                (
                    f"<coordinates>"
                    f"{lon},{lat},0"
                    f"</coordinates>"
                ),
                "</Point>",
                "</Placemark>",
            ]
        )

    partes.extend(
        [
            "</Document>",
            "</kml>",
        ]
    )

    return "\n".join(
        partes
    )


# ==========================================================
# SERGIA
# ==========================================================

def obter_chave_openai():

    try:

        return st.secrets[
            "OPENAI_API_KEY"
        ]

    except Exception:

        return os.environ.get(
            "OPENAI_API_KEY"
        )


def perguntar_ia(
    local,
    pergunta
):

    chave = obter_chave_openai()

    if not chave:

        return (
            "⚠️ A SergIA não está configurada.\n\n"
            "Adicione OPENAI_API_KEY "
            "nos Secrets do Streamlit."
        )

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=chave
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
Você é a SergIA, assistente do
Mapa de Nossa Senhora do Socorro-SE.

Responda em português do Brasil.

Não invente informações.

Use os dados fornecidos pelo mapa.

Diga quando uma informação não estiver disponível.

Diferencie informações do
OpenStreetMap e cadastros do projeto.

Não afirme que um estabelecimento
está funcionando atualmente apenas
porque ele aparece no mapa.

Seja clara e amigável.
"""

        prompt = f"""
DADOS DO LOCAL:

{contexto}

PERGUNTA:

{pergunta}
"""

        resposta = client.responses.create(
            model="gpt-5.6",
            instructions=instrucoes,
            input=prompt,
        )

        return resposta.output_text

    except Exception as erro:

        return (
            "❌ Erro ao consultar a SergIA:\n\n"
            f"{erro}"
        )


# ==========================================================
# CABEÇALHO
# ==========================================================

st.markdown(
    "# 🗺️ Mapa de Nossa Senhora do Socorro"
)

st.markdown(
    """
    Explore os locais de
    **Nossa Senhora do Socorro — Sergipe**.
    """
)

st.info(
    f"📍 {len(locais):,} pontos carregados"
    .replace(",", ".")
)


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title(
    "🎛️ Explorar"
)

categorias_disponiveis = sorted(
    set(
        local["categoria"]
        for local in locais
        if local["categoria"]
    )
)

categorias_selecionadas = st.sidebar.multiselect(
    "Categorias",
    categorias_disponiveis,
    default=categorias_disponiveis,
)

st.sidebar.markdown("---")

mostrar_mapa = st.sidebar.checkbox(
    "🗺️ Mostrar mapa",
    True,
)

if st.sidebar.button(
    "🔄 Atualizar pontos do OpenStreetMap"
):

    with st.spinner(
        "Buscando novos pontos..."
    ):

        novos = buscar_locais_osm()

        adicionados = salvar_osm_no_banco(
            novos
        )

    carregar_pontos.clear()

    st.success(
        f"Atualização concluída. "
        f"{adicionados} novos pontos adicionados."
    )

    st.rerun()


st.sidebar.markdown("---")

st.sidebar.metric(
    "📍 Total de pontos",
    len(locais)
)

st.sidebar.info(
    """
    Dados:

    • Base SQLite existente
    • OpenStreetMap
    • Cadastros manuais

    Sem Google Places API.
    """
)


# ==========================================================
# PESQUISA
# ==========================================================

st.subheader(
    "🔎 Pesquisar locais"
)

with st.form(
    "pesquisa_form"
):

    pesquisa = st.text_input(
        "Pesquisar",
        placeholder=(
            "Ex: farmácia, mercado, "
            "escola, restaurante..."
        ),
        label_visibility="collapsed",
    )

    pesquisar = st.form_submit_button(
        "🔍 Buscar"
    )

termo = pesquisa.lower().strip()

resultados = []

for local in locais:

    if (
        categorias_selecionadas
        and local["categoria"]
        not in categorias_selecionadas
    ):
        continue

    texto = " ".join(
        [
            str(
                local.get(
                    "nome",
                    ""
                )
            ),
            str(
                local.get(
                    "categoria",
                    ""
                )
            ),
            str(
                local.get(
                    "descricao",
                    ""
                )
            ),
            str(
                local.get(
                    "endereco",
                    ""
                )
            ),
        ]
    ).lower()

    if (
        not termo
        or termo in texto
    ):

        resultados.append(
            local
        )


if pesquisar and termo:

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO pesquisas
        (termo, data)
        VALUES (?, ?)
        """,
        (
            termo,
            datetime.now().isoformat()
        ),
    )

    conn.commit()
    conn.close()


# ==========================================================
# MÉTRICAS
# ==========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "📍 Pontos",
        len(resultados)
    )

with col2:

    st.metric(
        "🛍️ Comércio",
        len(
            [
                x
                for x in resultados
                if x["categoria"]
                == "Comércio"
            ]
        ),
    )

with col3:

    st.metric(
        "🏥 Saúde",
        len(
            [
                x
                for x in resultados
                if x["categoria"]
                == "Saúde"
            ]
        ),
    )

with col4:

    st.metric(
        "🏫 Educação",
        len(
            [
                x
                for x in resultados
                if x["categoria"]
                == "Educação"
            ]
        ),
    )


# ==========================================================
# MAPA
# ==========================================================

if mostrar_mapa:

    st.subheader(
        "📍 Mapa"
    )

    mapa = folium.Map(
        location=[
            DEFAULT_LAT,
            DEFAULT_LON
        ],
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

    # Cluster para muitos pontos
    from folium.plugins import MarkerCluster

    cluster = MarkerCluster(
        name="Locais"
    )

    cluster.add_to(
        mapa
    )

    for local in resultados:

        lat = local.get(
            "latitude"
        )

        lon = local.get(
            "longitude"
        )

        if (
            lat is None
            or lon is None
        ):
            continue

        nome = html.escape(
            str(
                local.get(
                    "nome",
                    ""
                )
            )
        )

        categoria = html.escape(
            str(
                local.get(
                    "categoria",
                    ""
                )
            )
        )

        descricao = html.escape(
            str(
                local.get(
                    "descricao",
                    ""
                )
            )
        )

        endereco = html.escape(
            str(
                local.get(
                    "endereco"
                )
                or
                "Endereço não informado"
            )
        )

        telefone = html.escape(
            str(
                local.get(
                    "telefone"
                )
                or
                "Telefone não informado"
            )
        )

        horario = html.escape(
            str(
                local.get(
                    "horario"
                )
                or
                "Horário não informado"
            )
        )

        fonte = html.escape(
            str(
                local.get(
                    "fonte",
                    ""
                )
            )
        )

        site = str(
            local.get(
                "site"
            )
            or ""
        )

        site_html = ""

        if site:

            site_seguro = html.escape(
                site,
                quote=True
            )

            site_html = (
                f'<p>🌐 '
                f'<a href="{site_seguro}" '
                f'target="_blank">'
                f'Visitar site'
                f'</a></p>'
            )

        popup = f"""
        <div style="
            width:290px;
            font-family:Arial;
        ">

            <h3 style="
                color:#173b57;
            ">
                {nome}
            </h3>

            <p>
                <b>🏷️ {categoria}</b>
            </p>

            <p>
                {descricao}
            </p>

            <p>
                📍 {endereco}
            </p>

            <p>
                🕐 {horario}
            </p>

            <p>
                📞 {telefone}
            </p>

            {site_html}

            <hr>

            <small>
                Fonte: {fonte}
            </small>

        </div>
        """

        folium.Marker(
            location=[
                float(lat),
                float(lon)
            ],
            tooltip=str(
                local.get(
                    "nome",
                    ""
                )
            ),
            popup=folium.Popup(
                popup,
                max_width=350
            ),
            icon=folium.Icon(
                color=cores.get(
                    local["categoria"],
                    "blue"
                ),
                icon=icones.get(
                    local["categoria"],
                    "map-marker"
                ),
            ),
        ).add_to(
            cluster
        )

        pontos_bounds.append(
            [
                float(lat),
                float(lon)
            ]
        )

    if pontos_bounds:

        mapa.fit_bounds(
            pontos_bounds
        )

    folium.LayerControl().add_to(
        mapa
    )

    st_folium(
        mapa,
        width=None,
        height=650,
        returned_objects=[],
    )


# ==========================================================
# EXPORTAÇÃO
# ==========================================================

st.markdown("---")

st.subheader(
    "📥 Exportar mapa"
)

df_exportacao = criar_dataframe_exportacao(
    resultados
)

col_csv, col_kml = st.columns(2)

with col_csv:

    csv_bytes = (
        df_exportacao
        .to_csv(
            index=False,
            encoding="utf-8-sig"
        )
        .encode("utf-8-sig")
    )

    st.download_button(
        "📄 Baixar CSV",
        data=csv_bytes,
        file_name=(
            "mapa_nossa_senhora_do_socorro.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )

with col_kml:

    kml_texto = criar_kml(
        resultados
    )

    st.download_button(
        "🌎 Baixar KML",
        data=kml_texto.encode(
            "utf-8"
        ),
        file_name=(
            "mapa_nossa_senhora_do_socorro.kml"
        ),
        mime=(
            "application/vnd.google-earth.kml+xml"
        ),
        use_container_width=True,
    )


# ==========================================================
# LISTA
# ==========================================================

st.markdown("---")

st.subheader(
    "📚 Locais encontrados"
)

if resultados:

    # Para não deixar 2.800 cards gigantes
    # carregarem todos de uma vez.
    limite = st.number_input(
        "Quantidade de locais exibidos na lista",
        min_value=20,
        max_value=len(resultados),
        value=min(100, len(resultados)),
        step=20,
    )

    for indice, local in enumerate(
        resultados[:limite]
    ):

        st.markdown(
            '<div class="card">',
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(
            [1, 3]
        )

        with col1:

            imagem = local.get(
                "imagem",
                ""
            )

            if imagem:

                try:

                    st.image(
                        imagem,
                        use_container_width=True
                    )

                except Exception:

                    st.markdown(
                        "📍"
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
                    ">
                        📍
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with col2:

            st.markdown(
                f"""
                <h2>
                    {html.escape(
                        str(
                            local["nome"]
                        )
                    )}
                </h2>

                <span class="badge">
                    {html.escape(
                        str(
                            local["categoria"]
                        )
                    )}
                </span>

                <p>
                    {html.escape(
                        str(
                            local["descricao"]
                        )
                    )}
                </p>

                <p>
                    📍
                    {html.escape(
                        str(
                            local.get(
                                "endereco"
                            )
                            or
                            "Endereço não informado"
                        )
                    )}
                </p>

                <p>
                    📞
                    {html.escape(
                        str(
                            local.get(
                                "telefone"
                            )
                            or
                            "Não informado"
                        )
                    )}
                </p>

                <small>
                    Fonte:
                    {html.escape(
                        str(
                            local.get(
                                "fonte",
                                ""
                            )
                        )
                    )}
                </small>
                """,
                unsafe_allow_html=True
            )

            if local.get("site"):

                site = html.escape(
                    str(
                        local["site"]
                    ),
                    quote=True
                )

                st.markdown(
                    f"[🌐 Visitar site]({site})"
                )

            if st.button(
                "🤖 Conhecer este local com SergIA",
                key=f"ia_{indice}",
            ):

                with st.spinner(
                    "SergIA pensando..."
                ):

                    resposta = perguntar_ia(
                        local,
                        (
                            "Explique o que é "
                            "este local e quais "
                            "informações do mapa "
                            "podem ser úteis "
                            "para o visitante."
                        ),
                    )

                st.info(
                    resposta
                )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

else:

    st.warning(
        "Nenhum ponto encontrado."
    )


# ==========================================================
# GRÁFICO
# ==========================================================

st.markdown("---")

st.subheader(
    "📊 Estatísticas"
)

contagem = {}

for local in resultados:

    categoria = local[
        "categoria"
    ]

    contagem[
        categoria
    ] = (
        contagem.get(
            categoria,
            0
        )
        + 1
    )

if contagem:

    dados = {
        "Categoria":
            list(
                contagem.keys()
            ),

        "Quantidade":
            list(
                contagem.values()
            ),
    }

    grafico = px.bar(
        dados,
        x="Categoria",
        y="Quantidade",
        color="Categoria",
        title=(
            "Locais por categoria"
        ),
    )

    grafico.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )

    st.plotly_chart(
        grafico,
        use_container_width=True
    )


# ==========================================================
# CADASTRO MANUAL
# ==========================================================

st.markdown("---")

st.subheader(
    "➕ Cadastrar novo local"
)

with st.expander(
    "Abrir formulário"
):

    with st.form(
        "novo_local"
    ):

        nome = st.text_input(
            "Nome do local"
        )

        categoria = st.selectbox(
            "Categoria",
            CATEGORIAS
        )

        descricao = st.text_area(
            "Descrição"
        )

        endereco = st.text_input(
            "Endereço"
        )

        telefone = st.text_input(
            "Telefone"
        )

        horario = st.text_input(
            "Horário"
        )

        site = st.text_input(
            "Site"
        )

        imagem = st.text_input(
            "URL da imagem"
        )

        col1, col2 = st.columns(
            2
        )

        with col1:

            latitude = st.number_input(
                "Latitude",
                value=DEFAULT_LAT,
                format="%.6f"
            )

        with col2:

            longitude = st.number_input(
                "Longitude",
                value=DEFAULT_LON,
                format="%.6f"
            )

        salvar = st.form_submit_button(
            "💾 Salvar local",
            type="primary"
        )

        if salvar:

            if not nome.strip():

                st.error(
                    "Digite o nome."
                )

            else:

                conn = conectar()

                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO locais (
                        nome,
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
                        fonte,
                        criado_em
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
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
                        0,
                        "Cadastro manual",
                        datetime.now().isoformat(),
                    )
                )

                conn.commit()
                conn.close()

                carregar_pontos.clear()

                st.success(
                    "✅ Local cadastrado!"
                )

                st.rerun()


# ==========================================================
# SERGIA
# ==========================================================

st.markdown("---")

st.subheader(
    "🤖 SergIA"
)

st.write(
    "Assistente de Nossa Senhora do Socorro."
)

if resultados:

    nomes = [
        x["nome"]
        for x in resultados
    ]

    local_escolhido = st.selectbox(
        "Escolha um local",
        nomes
    )

    local_ia = next(
        x
        for x in resultados
        if x["nome"]
        == local_escolhido
    )

else:

    local_ia = {
        "nome":
            "Nossa Senhora do Socorro",
        "categoria":
            "Município",
        "descricao":
            "Município de Sergipe.",
        "endereco":
            "Nossa Senhora do Socorro-SE",
        "telefone":
            "",
        "horario":
            "",
        "site":
            "",
        "latitude":
            DEFAULT_LAT,
        "longitude":
            DEFAULT_LON,
        "fonte":
            "Projeto",
    }


pergunta = st.text_area(
    "O que você quer saber?",
    placeholder=(
        "Ex: Quais locais de saúde "
        "aparecem no mapa?"
    ),
)


if st.button(
    "🤖 Perguntar à SergIA",
    type="primary"
):

    if not pergunta.strip():

        st.warning(
            "Digite uma pergunta."
        )

    else:

        with st.spinner(
            "SergIA preparando resposta..."
        ):

            resposta = perguntar_ia(
                local_ia,
                pergunta
            )

        st.markdown(
            """
            <div class="history-box">
                <h3>🤖 SergIA</h3>
                Assistente do mapa
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            resposta
        )


# ==========================================================
# FONTES
# ==========================================================

st.markdown("---")

st.subheader(
    "📚 Fontes"
)

st.markdown(
    """
    <div class="source-box">

    <b>Dados:</b><br>

    • Banco SQLite do projeto<br>
    • OpenStreetMap / Overpass API<br>
    • Cadastros manuais<br><br>

    <b>Importante:</b><br>

    O projeto não utiliza Google Places API.
    Os pontos do OpenStreetMap são dados
    disponibilizados pela comunidade do
    OpenStreetMap.

    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# RODAPÉ
# ==========================================================

st.markdown("---")

st.caption(
    "🗺️ Mapa de Nossa Senhora do Socorro • "
    "Sergipe • Python + Streamlit + "
    "OpenStreetMap + SQLite + SergIA"
)
