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


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

DEFAULT_LAT = -10.855
DEFAULT_LON = -37.125

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
        display: inline-block;
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

    .sergia-box {
        background: linear-gradient(
            135deg,
            #102f45,
            #176b91
        );
        color: white;
        padding: 25px;
        border-radius: 18px;
        margin-bottom: 20px;
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

    # Migração de bancos antigos
    colunas = {
        row[1]
        for row in cursor.execute(
            "PRAGMA table_info(locais)"
        ).fetchall()
    }

    if "fonte" not in colunas:
        cursor.execute(
            """
            ALTER TABLE locais
            ADD COLUMN fonte TEXT
            DEFAULT 'Cadastro manual'
            """
        )

    if "imagem" not in colunas:
        cursor.execute(
            """
            ALTER TABLE locais
            ADD COLUMN imagem TEXT
            """
        )

    conn.commit()
    conn.close()


criar_banco()


# ==========================================================
# CLASSIFICAÇÃO OSM
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

    # ------------------------------------------------------
    # SAÚDE
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # EDUCAÇÃO
    # ------------------------------------------------------

    if amenity in {
        "school",
        "kindergarten",
        "college",
        "university",
    }:
        return "Educação"

    if tags.get("education"):
        return "Educação"

    # ------------------------------------------------------
    # RELIGIÃO
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # ALIMENTAÇÃO
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # MERCADO
    # ------------------------------------------------------

    if shop in {
        "supermarket",
        "convenience",
        "greengrocer",
        "bakery",
        "butcher",
        "market",
    }:
        return "Mercado"

    # ------------------------------------------------------
    # COMÉRCIO
    # ------------------------------------------------------

    if shop:
        return "Comércio"

    # ------------------------------------------------------
    # HOTEL
    # ------------------------------------------------------

    if tourism in {
        "hotel",
        "guest_house",
        "hostel",
        "motel",
        "camp_site",
    }:
        return "Hotel"

    # ------------------------------------------------------
    # CULTURA
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # ESPORTE
    # ------------------------------------------------------

    if leisure in {
        "sports_centre",
        "stadium",
        "pitch",
        "fitness_centre",
        "swimming_pool",
        "track",
        "sports_hall",
    }:
        return "Esporte"

    # ------------------------------------------------------
    # TURISMO E LAZER
    # ------------------------------------------------------

    if leisure in {
        "park",
        "playground",
        "nature_reserve",
        "garden",
        "marina",
    }:
        return "Turismo e lazer"

    # ------------------------------------------------------
    # TRANSPORTE
    # ------------------------------------------------------

    if amenity in {
        "bus_station",
        "bus_stop",
        "taxi",
        "fuel",
        "car_wash",
    }:
        return "Transporte"

    if public_transport:
        return "Transporte"

    if railway:
        return "Transporte"

    # ------------------------------------------------------
    # ÓRGÃO PÚBLICO
    # ------------------------------------------------------

    if amenity in {
        "townhall",
        "police",
        "fire_station",
        "post_office",
        "courthouse",
        "government",
    }:
        return "Órgão público"

    # ------------------------------------------------------
    # SERVIÇOS
    # ------------------------------------------------------

    if office or craft:
        return "Serviço"

    # ------------------------------------------------------
    # OUTRO
    # ------------------------------------------------------

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
        "addr:city",
    ]:

        valor = tags.get(chave)

        if valor:
            partes.append(valor)

    return ", ".join(partes)


# ==========================================================
# DESCRIÇÃO OSM
# ==========================================================

def gerar_descricao_osm(
    nome,
    categoria,
    tags,
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
            f"{nome} foi localizado no OpenStreetMap "
            f"e classificado no projeto como "
            f"{categoria} ({tipo})."
        )

    return (
        f"{nome} é um local classificado "
        f"no projeto como {categoria}."
    )


# ==========================================================
# CONSULTA OPENSTREETMAP
# ==========================================================

def consultar_overpass(query):

    resposta = requests.post(
        OVERPASS_URL,
        data=query,
        timeout=180,
        headers={
            "User-Agent":
            "MapaNossaSenhoraSocorro/1.0"
        },
    )

    resposta.raise_for_status()

    return resposta.json()


# ==========================================================
# BUSCAR LOCAIS NO OSM
# ==========================================================

def buscar_locais_osm():

    # ------------------------------------------------------
    # PRIMEIRA TENTATIVA:
    # ÁREA ADMINISTRATIVA
    # ------------------------------------------------------

    query_area = """
    [out:json][timeout:180];

    area
        ["name"="Nossa Senhora do Socorro"]
        ["boundary"="administrative"]
        ->.socorro;

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

    # ------------------------------------------------------
    # SEGUNDA TENTATIVA:
    # RAIO
    # ------------------------------------------------------

    query_raio = f"""
    [out:json][timeout:180];

    (
        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["shop"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["amenity"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["healthcare"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["tourism"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["leisure"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["office"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["craft"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["public_transport"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )["name"]["railway"];
    );

    out center tags;
    """

    try:

        dados = consultar_overpass(
            query_area
        )

        if not dados.get("elements"):

            dados = consultar_overpass(
                query_raio
            )

    except Exception:

        # Se o OSM falhar, não retorna erro
        # e não apaga os dados antigos.
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

        nome = tags.get(
            "name"
        )

        if not nome:
            continue

        latitude = item.get(
            "lat"
        )

        longitude = item.get(
            "lon"
        )

        # Way/relation
        if latitude is None:

            centro = item.get(
                "center",
                {}
            )

            latitude = centro.get(
                "lat"
            )

            longitude = centro.get(
                "lon"
            )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        categoria = classificar_categoria(
            tags
        )

        local = {

            "nome": nome,

            "categoria":
                categoria,

            "descricao":
                gerar_descricao_osm(
                    nome,
                    categoria,
                    tags,
                ),

            "endereco":
                montar_endereco(
                    tags
                ),

            "telefone":
                tags.get(
                    "phone",
                    ""
                ),

            "horario":
                tags.get(
                    "opening_hours",
                    ""
                ),

            "site":
                tags.get(
                    "website",
                    ""
                ),

            "imagem":
                tags.get(
                    "image",
                    ""
                ),

            "latitude":
                float(latitude),

            "longitude":
                float(longitude),

            "avaliacao":
                0,

            "fonte":
                "OpenStreetMap",
        }

        locais.append(
            local
        )

    # ------------------------------------------------------
    # REMOVER DUPLICADOS
    # ------------------------------------------------------

    unicos = {}

    for local in locais:

        chave = (

            local["nome"]
            .lower()
            .strip(),

            round(
                local["latitude"],
                5,
            ),

            round(
                local["longitude"],
                5,
            ),
        )

        unicos[chave] = local

    return list(
        unicos.values()
    )


# ==========================================================
# SALVAR PONTOS OSM NO BANCO
# ==========================================================

def salvar_locais_osm(
    locais_osm
):

    if not locais_osm:
        return

    conn = conectar()
    cursor = conn.cursor()

    for local in locais_osm:

        nome = local.get(
            "nome",
            ""
        )

        latitude = local.get(
            "latitude"
        )

        longitude = local.get(
            "longitude"
        )

        if (
            not nome
            or latitude is None
            or longitude is None
        ):
            continue

        # Verifica se já existe pelo nome
        # e localização aproximada.
        cursor.execute(
            """
            SELECT id
            FROM locais
            WHERE
                LOWER(nome) = LOWER(?)
                AND ABS(latitude - ?) < 0.0001
                AND ABS(longitude - ?) < 0.0001
            LIMIT 1
            """,
            (
                nome,
                latitude,
                longitude,
            ),
        )

        existente = cursor.fetchone()

        if existente:
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
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?
            )
            """,
            (
                local.get(
                    "nome",
                    ""
                ),

                local.get(
                    "categoria",
                    "Outro"
                ),

                local.get(
                    "descricao",
                    ""
                ),

                local.get(
                    "endereco",
                    ""
                ),

                local.get(
                    "telefone",
                    ""
                ),

                local.get(
                    "horario",
                    ""
                ),

                local.get(
                    "site",
                    ""
                ),

                local.get(
                    "imagem",
                    ""
                ),

                latitude,

                longitude,

                local.get(
                    "avaliacao",
                    0
                ),

                "OpenStreetMap",

                datetime.now()
                .isoformat(),
            ),
        )

    conn.commit()
    conn.close()


# ==========================================================
# CARREGAR LOCAIS DO BANCO
# ==========================================================

def carregar_locais_banco():

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
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
        """
    )

    linhas = cursor.fetchall()

    conn.close()

    locais = []

    for linha in linhas:

        locais.append(
            {

                "_id":
                    linha[0],

                "nome":
                    linha[1],

                "categoria":
                    linha[2],

                "descricao":
                    linha[3] or "",

                "endereco":
                    linha[4] or "",

                "telefone":
                    linha[5] or "",

                "horario":
                    linha[6] or "",

                "site":
                    linha[7] or "",

                "imagem":
                    linha[8] or "",

                "latitude":
                    linha[9],

                "longitude":
                    linha[10],

                "avaliacao":
                    linha[11] or 0,

                "fonte":
                    linha[12]
                    or "Cadastro manual",
            }
        )

    return locais


# ==========================================================
# CARREGAR TODOS OS PONTOS
# ==========================================================

@st.cache_data(ttl=600)
def carregar_pontos():

    # ------------------------------------------------------
    # Primeiro tenta atualizar o OSM.
    # Se falhar, continua usando o banco.
    # ------------------------------------------------------

    try:

        locais_osm = buscar_locais_osm()

        if locais_osm:

            salvar_locais_osm(
                locais_osm
            )

    except Exception:

        pass

    # ------------------------------------------------------
    # Agora sempre carrega do banco.
    # ------------------------------------------------------

    return carregar_locais_banco()


# ==========================================================
# SERGIA — CHAVE
# ==========================================================

def obter_chave_openrouter():

    # Streamlit Secrets
    try:

        chave = st.secrets.get(
            "OPENROUTER_API_KEY"
        )

        if chave:

            return str(
                chave
            ).strip()

    except Exception:

        pass

    # Variável de ambiente
    chave = os.getenv(
        "OPENROUTER_API_KEY"
    )

    if chave:

        return chave.strip()

    return None


# ==========================================================
# SERGIA — IA
# ==========================================================

def perguntar_ia(
    local,
    pergunta,
):

    chave = obter_chave_openrouter()

    if not chave:

        return (
            "⚠️ **A SergIA ainda não está configurada.**\n\n"
            "Adicione `OPENROUTER_API_KEY` aos "
            "Secrets do Streamlit."
        )

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=chave,
            base_url="https://openrouter.ai/api/v1",
        )

        contexto = f"""
Nome: {local.get('nome', 'Não informado')}

Categoria: {local.get('categoria', 'Não informado')}

Descrição: {local.get('descricao', 'Não informado')}

Endereço: {local.get('endereco', 'Não informado')}

Telefone: {local.get('telefone', 'Não informado')}

Horário: {local.get('horario', 'Não informado')}

Site: {local.get('site', 'Não informado')}

Fonte: {local.get('fonte', 'Não informado')}

Latitude: {local.get('latitude', 'Não informado')}

Longitude: {local.get('longitude', 'Não informado')}
"""

        instrucoes = """
Você é a SergIA, assistente virtual do
Mapa de Nossa Senhora do Socorro-SE.

Responda em português do Brasil.

REGRAS:

1. Não invente fatos.

2. Use os dados do local fornecidos pelo mapa.

3. Se uma informação não estiver disponível,
   diga claramente que não está disponível.

4. Não invente telefone, endereço, horário,
   preço ou funcionamento.

5. Um local cadastrado no mapa não significa
   necessariamente que esteja funcionando
   atualmente.

6. Diferencie dados do OpenStreetMap,
   cadastro manual e informações do projeto.

7. Seja objetiva, clara e amigável.

8. Não apresente suposições como fatos.
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

                {
                    "role": "system",
                    "content": instrucoes,
                },

                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        if not resposta.choices:

            return (
                "⚠️ A SergIA não recebeu "
                "uma resposta."
            )

        texto = (
            resposta
            .choices[0]
            .message
            .content
        )

        if not texto:

            return (
                "⚠️ A SergIA retornou "
                "uma resposta vazia."
            )

        return texto.strip()

    except ImportError:

        return (
            "❌ A biblioteca `openai` não está instalada.\n\n"
            "Adicione `openai` ao requirements.txt."
        )

    except Exception as erro:

        return (
            "❌ **Erro ao consultar a SergIA.**\n\n"
            f"`{str(erro)}`"
        )


# ==========================================================
# EXPORTAÇÃO CSV
# ==========================================================

def criar_dataframe_exportacao(
    pontos
):

    linhas = []

    for local in pontos:

        if (
            local.get("latitude") is None
            or local.get("longitude") is None
        ):
            continue

        linhas.append(
            {
                "Nome":
                    local.get(
                        "nome",
                        ""
                    ),

                "Categoria":
                    local.get(
                        "categoria",
                        ""
                    ),

                "Descrição":
                    local.get(
                        "descricao",
                        ""
                    ),

                "Endereço":
                    local.get(
                        "endereco",
                        ""
                    ),

                "Telefone":
                    local.get(
                        "telefone",
                        ""
                    ),

                "Horário":
                    local.get(
                        "horario",
                        ""
                    ),

                "Site":
                    local.get(
                        "site",
                        ""
                    ),

                "Latitude":
                    local.get(
                        "latitude"
                    ),

                "Longitude":
                    local.get(
                        "longitude"
                    ),

                "Fonte":
                    local.get(
                        "fonte",
                        ""
                    ),
            }
        )

    return pd.DataFrame(
        linhas
    )


# ==========================================================
# KML
# ==========================================================

def criar_kml(
    pontos
):

    partes = [

        '<?xml version="1.0" encoding="UTF-8"?>',

        '<kml xmlns="http://www.opengis.net/kml/2.2">',

        "<Document>",

        (
            "<name>"
            "Mapa de Nossa Senhora do Socorro - SE"
            "</name>"
        ),
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
                f"Categoria: {local.get('categoria', '')}\n"
                f"Endereço: {local.get('endereco', '')}\n"
                f"Telefone: {local.get('telefone', '')}\n"
                f"Horário: {local.get('horario', '')}\n"
                f"Fonte: {local.get('fonte', '')}"
            )
        )

        partes.extend(
            [
                "<Placemark>",

                f"<name>{nome}</name>",

                (
                    "<description>"
                    f"{descricao}"
                    "</description>"
                ),

                (
                    "<ExtendedData>"
                    f"<Data name=\"Categoria\">"
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
# CARREGAR PONTOS
# ==========================================================

locais = carregar_pontos()


# ==========================================================
# CABEÇALHO
# ==========================================================

st.markdown(
    "# 🗺️ Mapa de Nossa Senhora do Socorro"
)

st.markdown(
    """
    Explore **comércios, alimentação, saúde,
    educação, religião, cultura, lazer,
    transporte e serviços** de
    Nossa Senhora do Socorro-SE.
    """
)

st.info(
    "📍 Nossa Senhora do Socorro — Sergipe"
)


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title(
    "🎛️ Explorar"
)


# IMPORTANTE:
# Todas as categorias continuam disponíveis.
categorias_disponiveis = CATEGORIAS.copy()


categorias_selecionadas = (
    st.sidebar.multiselect(

        "Categorias",

        categorias_disponiveis,

        default=categorias_disponiveis,
    )
)


st.sidebar.markdown(
    "---"
)


mostrar_mapa = st.sidebar.checkbox(
    "🗺️ Mostrar mapa",
    True,
)


if st.sidebar.button(
    "🔄 Atualizar pontos"
):

    carregar_pontos.clear()

    st.rerun()


st.sidebar.markdown(
    "---"
)


st.sidebar.info(
    """
    📍 **Dados**

    OpenStreetMap + cadastro manual

    🤖 **IA**

    SergIA

    🗺️ **Exportação**

    CSV e KML
    """
)


# ==========================================================
# PESQUISA
# ==========================================================

st.subheader(
    "🔎 Pesquisar"
)


with st.form(
    "pesquisa_form"
):

    pesquisa = st.text_input(

        "Pesquisar",

        placeholder=(
            "Ex: restaurante, escola, "
            "farmácia, igreja..."
        ),

        label_visibility="collapsed",
    )

    pesquisar = (
        st.form_submit_button(
            "🔍 Buscar"
        )
    )


termo = (
    pesquisa
    .lower()
    .strip()
)


resultados = []


for local in locais:

    # Categoria
    if (
        categorias_selecionadas
        and local.get("categoria")
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


# ==========================================================
# REGISTRAR PESQUISA
# ==========================================================

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
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


# ==========================================================
# MÉTRICAS
# ==========================================================

col1, col2, col3, col4 = (
    st.columns(4)
)


with col1:

    st.metric(
        "📍 Pontos",
        len(resultados),
    )


with col2:

    st.metric(
        "🛍️ Comércio",
        len(
            [
                x
                for x in resultados
                if x.get("categoria")
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
                if x.get("categoria")
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
                if x.get("categoria")
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
            DEFAULT_LON,
        ],

        zoom_start=13,

        control_scale=True,

        tiles="OpenStreetMap",
    )


    cores = {

        "Comércio":
            "blue",

        "Alimentação":
            "red",

        "Mercado":
            "green",

        "Saúde":
            "pink",

        "Educação":
            "darkblue",

        "Religião":
            "purple",

        "Cultura":
            "purple",

        "Turismo e lazer":
            "cadetblue",

        "Esporte":
            "green",

        "Serviço":
            "orange",

        "Hotel":
            "darkred",

        "Transporte":
            "black",

        "Órgão público":
            "darkgreen",

        "Outro":
            "gray",
    }


    icones = {

        "Comércio":
            "shopping-cart",

        "Alimentação":
            "cutlery",

        "Mercado":
            "shopping-cart",

        "Saúde":
            "plus-sign",

        "Educação":
            "education",

        "Religião":
            "home",

        "Cultura":
            "info-sign",

        "Turismo e lazer":
            "tree-conifer",

        "Esporte":
            "flag",

        "Serviço":
            "wrench",

        "Hotel":
            "bed",

        "Transporte":
            "road",

        "Órgão público":
            "briefcase",

        "Outro":
            "map-marker",
    }


    pontos_bounds = []


    for local in resultados:

        latitude = local.get(
            "latitude"
        )

        longitude = local.get(
            "longitude"
        )

        if (
            latitude is None
            or longitude is None
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


        horario = html.escape(
            str(
                local.get(
                    "horario"
                )
                or
                "Horário não informado"
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
                quote=True,
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

            <h3 style="color:#173b57;">
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
                latitude,
                longitude,
            ],

            tooltip=local.get(
                "nome",
                "Local"
            ),

            popup=folium.Popup(
                popup,
                max_width=350,
            ),

            icon=folium.Icon(

                color=cores.get(
                    local.get(
                        "categoria",
                        "Outro"
                    ),
                    "blue",
                ),

                icon=icones.get(
                    local.get(
                        "categoria",
                        "Outro"
                    ),
                    "map-marker",
                ),
            ),
        ).add_to(mapa)


        pontos_bounds.append(
            [
                latitude,
                longitude,
            ]
        )


    if pontos_bounds:

        mapa.fit_bounds(
            pontos_bounds
        )


    # ------------------------------------------------------
    # LEGENDA
    # ------------------------------------------------------

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
        🟢 Esporte<br>
        🟠 Serviços<br>
        ⚫ Transporte<br>
        🟤 Órgão público

    </div>
    """


    mapa.get_root().html.add_child(
        folium.Element(
            legenda
        )
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

st.markdown(
    "---"
)

st.subheader(
    "📥 Exportar para Google My Maps"
)


st.write(
    "Baixe os pontos encontrados e "
    "importe o arquivo em uma camada "
    "do Google My Maps."
)


df_exportacao = (
    criar_dataframe_exportacao(
        resultados
    )
)


col_csv, col_kml = (
    st.columns(2)
)


with col_csv:

    csv_bytes = (
        df_exportacao
        .to_csv(
            index=False,
            encoding="utf-8-sig",
        )
        .encode(
            "utf-8-sig"
        )
    )


    st.download_button(

        "📄 Baixar CSV para My Maps",

        data=csv_bytes,

        file_name=(
            "mapa_nossa_senhora_"
            "do_socorro.csv"
        ),

        mime="text/csv",

        use_container_width=True,
    )


with col_kml:

    kml_texto = criar_kml(
        resultados
    )


    st.download_button(

        "🌎 Baixar KML para My Maps",

        data=kml_texto.encode(
            "utf-8"
        ),

        file_name=(
            "mapa_nossa_senhora_"
            "do_socorro.kml"
        ),

        mime=(
            "application/vnd.google-earth."
            "kml+xml"
        ),

        use_container_width=True,
    )


st.caption(
    "No Google My Maps: crie um mapa → "
    "Adicionar camada → Importar → "
    "selecione o CSV ou KML."
)


# ==========================================================
# LISTA DE LOCAIS
# ==========================================================

st.markdown(
    "---"
)

st.subheader(
    "📚 Locais encontrados"
)


if resultados:

    for indice, local in enumerate(
        resultados
    ):

        with st.container():

            st.markdown(
                '<div class="card">',
                unsafe_allow_html=True,
            )


            col1, col2 = (
                st.columns(
                    [1, 3]
                )
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
                            use_container_width=True,
                        )

                    except Exception:

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
                            unsafe_allow_html=True,
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
                        unsafe_allow_html=True,
                    )


            with col2:

                st.markdown(

                    f"""
                    <h2>
                        {html.escape(
                            str(
                                local.get(
                                    "nome",
                                    ""
                                )
                            )
                        )}
                    </h2>

                    <span class="badge">
                        {html.escape(
                            str(
                                local.get(
                                    "categoria",
                                    "Outro"
                                )
                            )
                        )}
                    </span>

                    <p>
                        {html.escape(
                            str(
                                local.get(
                                    "descricao",
                                    ""
                                )
                            )
                        )}
                    </p>

                    <p>
                        📍 {html.escape(
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
                        🕐 {html.escape(
                            str(
                                local.get(
                                    "horario"
                                )
                                or
                                "Horário não informado"
                            )
                        )}
                    </p>

                    <p>
                        📞 {html.escape(
                            str(
                                local.get(
                                    "telefone"
                                )
                                or
                                "Telefone não informado"
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

                    unsafe_allow_html=True,
                )


                if local.get(
                    "site"
                ):

                    site = html.escape(
                        str(
                            local["site"]
                        ),
                        quote=True,
                    )

                    st.markdown(
                        f"""
                        <a href="{site}"
                           target="_blank">
                           🌐 Visitar site
                        </a>
                        """,
                        unsafe_allow_html=True,
                    )


                if st.button(

                    "🤖 Conhecer este local com SergIA",

                    key=f"ia_local_{indice}",

                ):

                    with st.spinner(
                        "🤖 SergIA está preparando informações..."
                    ):

                        resposta = perguntar_ia(

                            local,

                            (
                                "Explique o que é "
                                "este local e quais "
                                "informações do mapa "
                                "podem ser úteis "
                                "para o visitante. "
                                "Não invente."
                            ),
                        )


                    st.info(
                        resposta
                    )


            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )


else:

    st.warning(
        "Nenhum ponto encontrado "
        "com os filtros atuais."
    )


# ==========================================================
# GRÁFICO
# ==========================================================

st.markdown(
    "---"
)

st.subheader(
    "📊 Dados do mapa"
)


contagem = {}


for local in resultados:

    categoria = local.get(
        "categoria",
        "Outro"
    )

    contagem[categoria] = (
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

        title=
            "Locais por categoria",
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

st.markdown(
    "---"
)

st.subheader(
    "➕ Adicionar local"
)


with st.expander(
    "Cadastrar um novo local"
):

    with st.form(
        "novo_local"
    ):

        nome = st.text_input(
            "Nome do local"
        )


        categoria = st.selectbox(
            "Categoria",
            CATEGORIAS,
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
            "Horário de funcionamento"
        )


        site = st.text_input(
            "Site"
        )


        imagem = st.text_input(
            "URL da imagem"
        )


        col1, col2 = (
            st.columns(2)
        )


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

                st.error(
                    "Digite o nome do local."
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
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?
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
                        avaliacao,
                        "Cadastro manual",
                        datetime.now().isoformat(),
                    ),
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

st.markdown(
    "---"
)

st.markdown(
    """
    <div class="sergia-box">

        <h2>🤖 SergIA</h2>

        <p>
        Assistente virtual do Mapa de
        Nossa Senhora do Socorro.
        </p>

        <p>
        Pergunte sobre qualquer local
        apresentado no mapa.
        </p>

    </div>
    """,
    unsafe_allow_html=True,
)


if resultados:

    local_nomes = [
        local.get(
            "nome",
            "Local"
        )
        for local in resultados
    ]


    local_escolhido = st.selectbox(
        "📍 Escolha um local",
        local_nomes,
        key="sergia_local",
    )


    local_ia = next(
        (
            local
            for local in resultados
            if local.get("nome")
            == local_escolhido
        ),
        resultados[0],
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
    "💬 O que você quer saber?",
    placeholder=(
        "Ex: Qual é a categoria deste local? "
        "Quais informações estão disponíveis?"
    ),
    key="sergia_pergunta",
)


if st.button(
    "🤖 Perguntar à SergIA",
    type="primary",
    key="botao_sergia",
):

    if not pergunta.strip():

        st.warning(
            "Digite uma pergunta."
        )

    else:

        with st.spinner(
            "🤖 SergIA está preparando a resposta..."
        ):

            resposta = perguntar_ia(
                local_ia,
                pergunta,
            )


        st.markdown(
            """
            <div class="history-box">

                <h3>🤖 SergIA</h3>

                Assistente cultural e
                informativa de
                Nossa Senhora do Socorro

            </div>
            """,
            unsafe_allow_html=True,
        )


        st.markdown(
            resposta
        )


# ==========================================================
# FONTES
# ==========================================================

st.markdown(
    "---"
)

st.subheader(
    "📚 Fontes"
)


st.markdown(
    """
    <div class="source-box">

    <b>Dados do mapa:</b><br>

    • OpenStreetMap / Overpass API<br>
    • Locais armazenados no SQLite<br>
    • Locais cadastrados manualmente<br><br>

    <b>Ferramentas:</b><br>

    • Python<br>
    • Streamlit<br>
    • Folium<br>
    • SQLite<br>
    • Plotly<br>
    • Google My Maps<br><br>

    <b>Inteligência artificial:</b><br>

    • SergIA através da OpenRouter

    </div>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# RODAPÉ
# ==========================================================

st.markdown(
    "---"
)

st.caption(
    "🗺️ Mapa de Nossa Senhora do Socorro "
    "• Sergipe "
    "• Python + Streamlit + OpenStreetMap "
    "+ SQLite + OpenRouter"
)
