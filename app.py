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

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

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

    .big-number {
        font-size: 30px;
        font-weight: bold;
        color: #173b57;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# BANCO
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

            osm_id TEXT,

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

    # ------------------------------------------------------
    # MIGRAÇÃO
    # ------------------------------------------------------

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
            ADD COLUMN fonte TEXT DEFAULT 'Cadastro manual'
            """
        )

    if "osm_id" not in colunas:

        cursor.execute(
            """
            ALTER TABLE locais
            ADD COLUMN osm_id TEXT
            """
        )

    conn.commit()
    conn.close()


criar_banco()


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
    public_transport = tags.get(
        "public_transport",
        ""
    )
    building = tags.get("building", "")
    sport = tags.get("sport", "")

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
        "blood_donation",
    }:
        return "Saúde"

    # EDUCAÇÃO
    if amenity in {
        "school",
        "kindergarten",
        "college",
        "university",
        "training",
        "music_school",
        "driving_school",
    }:
        return "Educação"

    if tags.get("education"):
        return "Educação"

    # RELIGIÃO
    if amenity in {
        "place_of_worship",
        "monastery",
        "grave_yard",
        "funeral_hall",
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
        "biergarten",
    }:
        return "Alimentação"

    # MERCADO
    if shop in {
        "supermarket",
        "convenience",
        "greengrocer",
        "bakery",
        "butcher",
        "deli",
        "beverages",
        "wholesale",
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
        "chalet",
    }:
        return "Hotel"

    # CULTURA
    if tourism in {
        "museum",
        "gallery",
        "attraction",
        "arts_centre",
        "theme_park",
    }:
        return "Cultura"

    if amenity in {
        "library",
        "theatre",
        "cinema",
        "community_centre",
        "social_centre",
        "arts_centre",
    }:
        return "Cultura"

    # ESPORTE
    if sport:
        return "Esporte"

    if leisure in {
        "sports_centre",
        "stadium",
        "pitch",
        "fitness_centre",
        "swimming_pool",
        "golf_course",
        "track",
        "sports_hall",
    }:
        return "Esporte"

    # LAZER
    if leisure in {
        "park",
        "playground",
        "garden",
        "nature_reserve",
        "picnic_table",
        "dog_park",
    }:
        return "Turismo e lazer"

    # TRANSPORTE
    if amenity in {
        "bus_station",
        "bus_stop",
        "taxi",
        "fuel",
        "charging_station",
        "car_wash",
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
        "prison",
        "social_facility",
    }:
        return "Órgão público"

    if office in {
        "government",
        "administrative",
    }:
        return "Órgão público"

    # SERVIÇO
    if office or craft:
        return "Serviço"

    return "Outro"


# ==========================================================
# ENDEREÇO
# ==========================================================

def montar_endereco(tags):

    partes = []

    chaves = [
        "addr:street",
        "addr:housenumber",
        "addr:suburb",
        "addr:neighbourhood",
        "addr:district",
        "addr:city",
    ]

    for chave in chaves:

        valor = tags.get(chave)

        if valor:
            partes.append(valor)

    return ", ".join(partes)


# ==========================================================
# DESCRIÇÃO
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
# BUSCAR ÁREA DO MUNICÍPIO
# ==========================================================

def obter_query_overpass():

    return """
    [out:json][timeout:180];

    area
      ["name"="Nossa Senhora do Socorro"]
      ["boundary"="administrative"]
      ["admin_level"="6"]
      ->.socorro;

    (
        nwr(area.socorro)["name"];
    );

    out center tags;
    """


# ==========================================================
# CONSULTAR OVERPASS
# ==========================================================

def consultar_overpass():

    query = obter_query_overpass()

    ultimo_erro = ""

    for servidor in OVERPASS_SERVERS:

        try:

            resposta = requests.post(
                servidor,
                data=query,
                timeout=240,
                headers={
                    "User-Agent":
                    "MapaNossaSenhoraDoSocorro/2.0"
                },
            )

            resposta.raise_for_status()

            dados = resposta.json()

            elementos = dados.get(
                "elements",
                []
            )

            if elementos:

                return elementos

        except Exception as erro:

            ultimo_erro = str(erro)

            continue

    raise Exception(
        "Todos os servidores Overpass falharam. "
        f"Último erro: {ultimo_erro}"
    )


# ==========================================================
# TRANSFORMAR OSM
# ==========================================================

def transformar_osm(elementos):

    locais = []

    for item in elementos:

        tags = item.get(
            "tags",
            {}
        )

        nome = tags.get(
            "name"
        )

        if not nome:
            continue

        # --------------------------------------------------
        # COORDENADAS
        # --------------------------------------------------

        latitude = item.get(
            "lat"
        )

        longitude = item.get(
            "lon"
        )

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

        # --------------------------------------------------
        # CATEGORIA
        # --------------------------------------------------

        categoria = classificar_categoria(
            tags
        )

        # --------------------------------------------------
        # ID OSM
        # --------------------------------------------------

        osm_id = (
            f"{item.get('type', '')}/"
            f"{item.get('id', '')}"
        )

        # --------------------------------------------------
        # SITE
        # --------------------------------------------------

        site = (
            tags.get("website")
            or tags.get("contact:website")
            or ""
        )

        # --------------------------------------------------
        # TELEFONE
        # --------------------------------------------------

        telefone = (
            tags.get("phone")
            or tags.get("contact:phone")
            or ""
        )

        locais.append(
            {
                "nome": nome,
                "categoria": categoria,
                "descricao":
                    gerar_descricao_osm(
                        nome,
                        categoria,
                        tags,
                    ),
                "endereco":
                    montar_endereco(tags),
                "telefone":
                    telefone,
                "horario":
                    tags.get(
                        "opening_hours",
                        "",
                    ),
                "site": site,
                "imagem":
                    tags.get(
                        "image",
                        "",
                    ),
                "latitude":
                    float(latitude),
                "longitude":
                    float(longitude),
                "avaliacao": 0,
                "fonte":
                    "OpenStreetMap",
                "osm_id":
                    osm_id,
            }
        )

    return locais


# ==========================================================
# SALVAR OSM NO BANCO
# ==========================================================

def salvar_pontos_osm(locais):

    conn = conectar()
    cursor = conn.cursor()

    novos = 0
    atualizados = 0

    for local in locais:

        osm_id = local.get(
            "osm_id"
        )

        if not osm_id:
            continue

        cursor.execute(
            """
            SELECT id
            FROM locais
            WHERE osm_id = ?
            """,
            (osm_id,),
        )

        existente = cursor.fetchone()

        if existente:

            cursor.execute(
                """
                UPDATE locais

                SET
                    nome = ?,
                    categoria = ?,
                    descricao = ?,
                    endereco = ?,
                    telefone = ?,
                    horario = ?,
                    site = ?,
                    imagem = ?,
                    latitude = ?,
                    longitude = ?,
                    fonte = 'OpenStreetMap'

                WHERE osm_id = ?
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
                    osm_id,
                ),
            )

            atualizados += 1

        else:

            # ----------------------------------------------
            # SEGURANÇA CONTRA DUPLICADOS ANTIGOS
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM locais

                WHERE
                    LOWER(nome) = LOWER(?)
                    AND ABS(latitude - ?) < 0.0001
                    AND ABS(longitude - ?) < 0.0001
                """,
                (
                    local["nome"],
                    local["latitude"],
                    local["longitude"],
                ),
            )

            duplicado = cursor.fetchone()

            if duplicado:

                cursor.execute(
                    """
                    UPDATE locais

                    SET osm_id = ?

                    WHERE id = ?
                    """,
                    (
                        osm_id,
                        duplicado[0],
                    ),
                )

                atualizados += 1

            else:

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
                        osm_id,
                        criado_em

                    )

                    VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?
                    )
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
                        osm_id,
                        datetime.now().isoformat(),
                    ),
                )

                novos += 1

    conn.commit()
    conn.close()

    return novos, atualizados


# ==========================================================
# CONTAGEM DO BANCO
# ==========================================================

def quantidade_banco():

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM locais"
    )

    quantidade = cursor.fetchone()[0]

    conn.close()

    return quantidade


# ==========================================================
# CARREGAR BANCO
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
            fonte,
            osm_id

        FROM locais
        """
    )

    linhas = cursor.fetchall()

    conn.close()

    locais = []

    for linha in linhas:

        locais.append(
            {
                "id": linha[0],
                "nome": linha[1],
                "categoria": linha[2],
                "descricao": linha[3] or "",
                "endereco": linha[4] or "",
                "telefone": linha[5] or "",
                "horario": linha[6] or "",
                "site": linha[7] or "",
                "imagem": linha[8] or "",
                "latitude": linha[9],
                "longitude": linha[10],
                "avaliacao": linha[11] or 0,
                "fonte": linha[12]
                    or "Cadastro manual",
                "osm_id": linha[13] or "",
            }
        )

    return locais


# ==========================================================
# CACHE
# ==========================================================

@st.cache_data(ttl=300)
def carregar_pontos():

    return carregar_locais_banco()


# ==========================================================
# EXPORTAÇÃO CSV
# ==========================================================

def criar_dataframe_exportacao(
    pontos
):

    linhas = []

    for local in pontos:

        if (
            local.get("latitude")
            is None
            or local.get("longitude")
            is None
        ):
            continue

        linhas.append(
            {
                "Nome":
                    local.get(
                        "nome",
                        "",
                    ),

                "Categoria":
                    local.get(
                        "categoria",
                        "",
                    ),

                "Descrição":
                    local.get(
                        "descricao",
                        "",
                    ),

                "Endereço":
                    local.get(
                        "endereco",
                        "",
                    ),

                "Telefone":
                    local.get(
                        "telefone",
                        "",
                    ),

                "Horário":
                    local.get(
                        "horario",
                        "",
                    ),

                "Site":
                    local.get(
                        "site",
                        "",
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
                        "",
                    ),
            }
        )

    return pd.DataFrame(
        linhas
    )


# ==========================================================
# KML
# ==========================================================

def criar_kml(pontos):

    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',

        '<kml xmlns="http://www.opengis.net/kml/2.2">',

        "<Document>",

        "<name>"
        "Mapa de Nossa Senhora do Socorro"
        "</name>",
    ]

    for local in pontos:

        lat = local.get(
            "latitude"
        )

        lon = local.get(
            "longitude"
        )

        if lat is None or lon is None:
            continue

        nome = xml_escape(
            str(
                local.get(
                    "nome",
                    "",
                )
            )
        )

        categoria = xml_escape(
            str(
                local.get(
                    "categoria",
                    "",
                )
            )
        )

        descricao = xml_escape(
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

        partes.extend(
            [
                "<Placemark>",

                f"<name>{nome}</name>",

                f"<description>"
                f"{descricao}"
                f"</description>",

                "<ExtendedData>",

                '<Data name="Categoria">',

                f"<value>{categoria}</value>",

                "</Data>",

                "</ExtendedData>",

                "<Point>",

                f"<coordinates>"
                f"{lon},{lat},0"
                f"</coordinates>",

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
# IMPORTAR CSV
# ==========================================================

def importar_csv(
    arquivo
):

    df = pd.read_csv(
        arquivo,
        encoding="utf-8-sig",
    )

    # Aceita nomes diferentes
    mapa_colunas = {}

    for coluna in df.columns:

        limpa = (
            str(coluna)
            .strip()
            .lower()
        )

        mapa_colunas[limpa] = coluna

    def pegar(*nomes):

        for nome in nomes:

            if nome.lower() in mapa_colunas:

                return df[
                    mapa_colunas[
                        nome.lower()
                    ]
                ]

        return None

    serie_nome = pegar(
        "nome",
        "name",
    )

    if serie_nome is None:

        raise Exception(
            "O CSV precisa ter uma coluna Nome."
        )

    serie_categoria = pegar(
        "categoria",
        "category",
    )

    serie_descricao = pegar(
        "descrição",
        "descricao",
        "description",
    )

    serie_endereco = pegar(
        "endereço",
        "endereco",
        "address",
    )

    serie_telefone = pegar(
        "telefone",
        "phone",
    )

    serie_horario = pegar(
        "horário",
        "horario",
        "opening_hours",
    )

    serie_site = pegar(
        "site",
        "website",
    )

    serie_lat = pegar(
        "latitude",
        "lat",
    )

    serie_lon = pegar(
        "longitude",
        "lon",
        "lng",
    )

    if (
        serie_lat is None
        or serie_lon is None
    ):

        raise Exception(
            "O CSV precisa ter Latitude e Longitude."
        )

    conn = conectar()

    cursor = conn.cursor()

    quantidade = 0

    for i in range(
        len(df)
    ):

        nome = str(
            serie_nome.iloc[i]
        )

        if (
            not nome
            or nome == "nan"
        ):
            continue

        categoria = (
            str(
                serie_categoria.iloc[i]
            )
            if serie_categoria is not None
            else "Outro"
        )

        if categoria not in CATEGORIAS:

            categoria = "Outro"

        descricao = (
            str(
                serie_descricao.iloc[i]
            )
            if serie_descricao is not None
            else ""
        )

        endereco = (
            str(
                serie_endereco.iloc[i]
            )
            if serie_endereco is not None
            else ""
        )

        telefone = (
            str(
                serie_telefone.iloc[i]
            )
            if serie_telefone is not None
            else ""
        )

        horario = (
            str(
                serie_horario.iloc[i]
            )
            if serie_horario is not None
            else ""
        )

        site = (
            str(
                serie_site.iloc[i]
            )
            if serie_site is not None
            else ""
        )

        try:

            latitude = float(
                serie_lat.iloc[i]
            )

            longitude = float(
                serie_lon.iloc[i]
            )

        except Exception:

            continue

        # evita duplicado
        cursor.execute(
            """
            SELECT id

            FROM locais

            WHERE
                LOWER(nome)
                =
                LOWER(?)

                AND ABS(latitude - ?)
                < 0.0001

                AND ABS(longitude - ?)
                < 0.0001
            """,
            (
                nome,
                latitude,
                longitude,
            ),
        )

        if cursor.fetchone():

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
                osm_id,
                criado_em

            )

            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                nome,
                categoria,
                descricao,
                endereco,
                telefone,
                horario,
                site,
                "",
                latitude,
                longitude,
                0,
                "Importação CSV",
                "",
                datetime.now().isoformat(),
            ),
        )

        quantidade += 1

    conn.commit()
    conn.close()

    return quantidade


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
            "⚠️ A SergIA ainda não está "
            "configurada.\n\n"
            "Coloque sua "
            "`OPENAI_API_KEY` nos "
            "Secrets do Streamlit."
        )

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=chave
        )

        contexto = f"""
Nome: {local.get('nome', '')}

Categoria:
{local.get('categoria', '')}

Descrição:
{local.get('descricao', '')}

Endereço:
{local.get('endereco', '')}

Telefone:
{local.get('telefone', '')}

Horário:
{local.get('horario', '')}

Site:
{local.get('site', '')}

Fonte:
{local.get('fonte', '')}

Latitude:
{local.get('latitude', '')}

Longitude:
{local.get('longitude', '')}
"""

        instrucoes = """
Você é a SergIA, assistente cultural e
informativa de Nossa Senhora do Socorro-SE.

Responda em português do Brasil.

Não invente informações.

Diferencie informações do
OpenStreetMap, cadastro manual e
informações históricas.

Quando não houver informação suficiente,
diga claramente.

Não trate um cadastro como prova de
que um estabelecimento está funcionando
atualmente.

Seja clara, curta e amigável.

O projeto abrange todo o município de
Nossa Senhora do Socorro, Sergipe.
"""

        prompt = f"""
DADOS DO LOCAL:

{contexto}

PERGUNTA:

{pergunta}
"""

        # --------------------------------------------------
        # COMPATÍVEL COM OPENAI ATUAL
        # --------------------------------------------------

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
    Explore **comércios, alimentação,
    saúde, educação, religião, cultura,
    lazer, transporte e serviços** de
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

quantidade = quantidade_banco()

st.sidebar.metric(
    "📍 Pontos salvos",
    quantidade,
)

st.sidebar.markdown("---")


# ==========================================================
# BOTÃO PRINCIPAL DE CARREGAMENTO OSM
# ==========================================================

st.sidebar.subheader(
    "🌎 Dados do OpenStreetMap"
)

st.sidebar.write(
    "Use este botão para carregar os "
    "pontos reais disponíveis no "
    "OpenStreetMap para o município."
)

if st.sidebar.button(
    "📥 CARREGAR PONTOS DO MUNICÍPIO",
    type="primary",
    use_container_width=True,
):

    with st.spinner(
        "🌎 Consultando o município inteiro no OpenStreetMap..."
    ):

        try:

            elementos = consultar_overpass()

            pontos_osm = transformar_osm(
                elementos
            )

            novos, atualizados = (
                salvar_pontos_osm(
                    pontos_osm
                )
            )

            carregar_pontos.clear()

            st.success(
                f"✅ Consulta concluída!\n\n"
                f"Encontrados: "
                f"{len(pontos_osm)}\n\n"
                f"Novos pontos: "
                f"{novos}\n\n"
                f"Atualizados: "
                f"{atualizados}"
            )

            st.rerun()

        except Exception as erro:

            st.error(
                f"❌ Não foi possível carregar "
                f"os pontos:\n\n{erro}"
            )


if st.sidebar.button(
    "🔄 Recarregar mapa",
    use_container_width=True,
):

    carregar_pontos.clear()

    st.rerun()


st.sidebar.markdown("---")


# ==========================================================
# IMPORTAR CSV
# ==========================================================

st.sidebar.subheader(
    "📥 Importar muitos pontos"
)

arquivo_csv = st.sidebar.file_uploader(
    "CSV com Nome, Latitude e Longitude",
    type=["csv"],
)

if arquivo_csv is not None:

    if st.sidebar.button(
        "⬆️ Importar CSV",
        use_container_width=True,
    ):

        try:

            quantidade_importada = (
                importar_csv(
                    arquivo_csv
                )
            )

            carregar_pontos.clear()

            st.sidebar.success(
                f"✅ {quantidade_importada} "
                f"pontos importados."
            )

            st.rerun()

        except Exception as erro:

            st.sidebar.error(
                f"Erro: {erro}"
            )


st.sidebar.markdown("---")


mostrar_mapa = st.sidebar.checkbox(
    "🗺️ Mostrar mapa",
    True,
)


# ==========================================================
# CARREGAR PONTOS
# ==========================================================

locais = carregar_pontos()


# ==========================================================
# CATEGORIAS
# ==========================================================

categorias_disponiveis = sorted(
    set(
        local["categoria"]
        for local in locais
    )
)

categorias_selecionadas = (
    st.sidebar.multiselect(
        "Categorias",
        categorias_disponiveis,
        default=categorias_disponiveis,
    )
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


# ==========================================================
# FILTRAR
# ==========================================================

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
                    "",
                )
            ),

            str(
                local.get(
                    "categoria",
                    "",
                )
            ),

            str(
                local.get(
                    "descricao",
                    "",
                )
            ),

            str(
                local.get(
                    "endereco",
                    "",
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
# SALVAR PESQUISA
# ==========================================================

if pesquisar and termo:

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO pesquisas (
            termo,
            data
        )

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

        lat = local.get(
            "latitude"
        )

        lon = local.get(
            "longitude"
        )

        if lat is None or lon is None:
            continue

        nome = html.escape(
            str(
                local.get(
                    "nome",
                    "",
                )
            )
        )

        categoria = html.escape(
            str(
                local.get(
                    "categoria",
                    "",
                )
            )
        )

        descricao = html.escape(
            str(
                local.get(
                    "descricao",
                    "",
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
                    "",
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
                f'<p>🌐 <a href="'
                f'{site_seguro}" '
                f'target="_blank">'
                f'Visitar site</a></p>'
            )

        popup = f"""
        <div
            style="
            width:290px;
            font-family:Arial;
            "
        >

            <h3
                style="
                color:#173b57;
                "
            >
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
                lat,
                lon,
            ],

            tooltip=local[
                "nome"
            ],

            popup=folium.Popup(
                popup,
                max_width=350,
            ),

            icon=folium.Icon(
                color=cores.get(
                    local[
                        "categoria"
                    ],
                    "blue",
                ),

                icon=icones.get(
                    local[
                        "categoria"
                    ],
                    "map-marker",
                ),
            ),
        ).add_to(
            mapa
        )

        pontos_bounds.append(
            [
                lat,
                lon,
            ]
        )

    if pontos_bounds:

        mapa.fit_bounds(
            pontos_bounds
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
    "📥 Exportar para Google My Maps"
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
# IMPORTAÇÃO DE PONTOS
# ==========================================================

st.markdown("---")

st.subheader(
    "📥 Importar pontos em massa"
)

st.write(
    "Você pode importar uma planilha CSV "
    "com milhares de locais. O sistema "
    "não adicionará duplicados."
)

arquivo = st.file_uploader(
    "Escolha um CSV",
    type=["csv"],
    key="csv_principal",
)

if arquivo:

    if st.button(
        "⬆️ Importar estes pontos",
        type="primary",
    ):

        try:

            qtd = importar_csv(
                arquivo
            )

            carregar_pontos.clear()

            st.success(
                f"✅ {qtd} novos pontos "
                f"foram adicionados."
            )

            st.rerun()

        except Exception as erro:

            st.error(
                str(erro)
            )


# ==========================================================
# LISTA
# ==========================================================

st.markdown("---")

st.subheader(
    f"📚 Locais encontrados "
    f"({len(resultados)})"
)

if resultados:

    # Para não deixar a página gigantesca
    limite_lista = st.number_input(
        "Quantidade exibida na lista",
        min_value=20,
        max_value=1000,
        value=100,
        step=20,
    )

    lista_exibicao = resultados[
        :int(limite_lista)
    ]

    for indice, local in enumerate(
        lista_exibicao
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
                    "",
                )

                if imagem:

                    try:

                        st.image(
                            imagem,
                            use_container_width=True,
                        )

                    except Exception:

                        st.markdown(
                            "📍"
                        )

                else:

                    st.markdown(
                        """
                        <div
                        style="
                        height:140px;
                        background:#eaf0f6;
                        border-radius:15px;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        font-size:45px;
                        "
                        >
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
                            local["nome"]
                        )
                    )}
                    </h2>

                    <span class="badge">
                    {html.escape(
                        str(
                            local[
                                "categoria"
                            ]
                        )
                    )}
                    </span>

                    <p>
                    {html.escape(
                        str(
                            local[
                                "descricao"
                            ]
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
                            "Telefone não informado"
                        )
                    )}
                    </p>

                    <p>
                    🕐
                    {html.escape(
                        str(
                            local.get(
                                "horario"
                            )
                            or
                            "Horário não informado"
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
                            local[
                                "site"
                            ]
                        ),
                        quote=True,
                    )

                    st.markdown(
                        f"[🌐 Visitar site]"
                        f"({site})"
                    )

                if st.button(
                    "🤖 Conhecer este local com SergIA",
                    key=f"ia_local_{indice}",
                ):

                    with st.spinner(
                        "🤖 SergIA está preparando informações..."
                    ):

                        resposta = (
                            perguntar_ia(
                                local,
                                "Explique o que é este local e quais informações do mapa podem ser úteis para o visitante. Não invente.",
                            )
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
        "Nenhum ponto encontrado."
    )

    st.info(
        "Use na barra lateral o botão "
        "📥 CARREGAR PONTOS DO MUNICÍPIO."
    )


# ==========================================================
# GRÁFICO
# ==========================================================

st.markdown("---")

st.subheader(
    "📊 Dados do mapa"
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
        use_container_width=True,
    )


# ==========================================================
# CADASTRO MANUAL
# ==========================================================

st.markdown("---")

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

        categoria = (
            st.selectbox(
                "Categoria",
                CATEGORIAS,
            )
        )

        descricao = (
            st.text_area(
                "Descrição"
            )
        )

        endereco = (
            st.text_input(
                "Endereço"
            )
        )

        telefone = (
            st.text_input(
                "Telefone"
            )
        )

        horario = (
            st.text_input(
                "Horário de funcionamento"
            )
        )

        site = (
            st.text_input(
                "Site"
            )
        )

        imagem = (
            st.text_input(
                "URL da imagem"
            )
        )

        col1, col2 = (
            st.columns(2)
        )

        with col1:

            latitude = (
                st.number_input(
                    "Latitude",
                    value=DEFAULT_LAT,
                    format="%.6f",
                )
            )

        with col2:

            longitude = (
                st.number_input(
                    "Longitude",
                    value=DEFAULT_LON,
                    format="%.6f",
                )
            )

        avaliacao = (
            st.slider(
                "Avaliação",
                0.0,
                5.0,
                0.0,
                0.1,
            )
        )

        salvar = (
            st.form_submit_button(
                "💾 Salvar local",
                type="primary",
            )
        )

        if salvar:

            if not nome.strip():

                st.error(
                    "Digite o nome do local."
                )

            else:

                conn = conectar()

                cursor = conn.cursor()

                # ------------------------------------------
                # DUPLICADO
                # ------------------------------------------

                cursor.execute(
                    """
                    SELECT id
                    FROM locais

                    WHERE
                        LOWER(nome)
                        =
                        LOWER(?)

                        AND ABS(latitude - ?)
                        < 0.0001

                        AND ABS(longitude - ?)
                        < 0.0001
                    """,
                    (
                        nome.strip(),
                        latitude,
                        longitude,
                    ),
                )

                existe = (
                    cursor.fetchone()
                )

                if existe:

                    conn.close()

                    st.warning(
                        "⚠️ Esse local já "
                        "está cadastrado."
                    )

                else:

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
                            osm_id,
                            criado_em

                        )

                        VALUES (
                            ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?,
                            ?, ?, ?, ?
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
                            "",
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

st.markdown("---")

st.subheader(
    "🤖 SergIA — Assistente de "
    "Nossa Senhora do Socorro"
)

st.write(
    "Pergunte sobre um local do mapa "
    "ou sobre informações relacionadas "
    "ao município."
)


if resultados:

    local_nomes = [
        local["nome"]
        for local in resultados
    ]

    local_escolhido = (
        st.selectbox(
            "Escolha um local",
            local_nomes,
        )
    )

    local_ia = next(
        local
        for local in resultados
        if local["nome"]
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
        "Ex: Quais tipos de locais "
        "aparecem no mapa?"
    ),
)


if st.button(
    "🤖 Perguntar à SergIA",
    type="primary",
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

                <h3>
                    🤖 SergIA
                </h3>

                Assistente cultural e
                informativa

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

st.markdown("---")

st.subheader(
    "📚 Fontes"
)

st.markdown(
    """
    <div class="source-box">

    <b>Dados do mapa:</b><br>

    • OpenStreetMap / Overpass API<br>
    • Locais cadastrados manualmente<br>
    • Pontos importados por CSV<br><br>

    <b>Ferramentas:</b><br>

    • Python<br>
    • Streamlit<br>
    • Folium<br>
    • SQLite<br>
    • Plotly<br>
    • Google My Maps para importação
    e visualização dos arquivos exportados

    </div>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# RODAPÉ
# ==========================================================

st.markdown("---")

st.caption(
    "🗺️ Mapa de Nossa Senhora do Socorro • "
    "Sergipe • Python + Streamlit + "
    "OpenStreetMap + SQLite + OpenAI"
)
