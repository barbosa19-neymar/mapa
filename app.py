import streamlit as st
import folium
import requests
import html
import os
import sqlite3
from datetime import datetime
from streamlit_folium import st_folium
import plotly.express as px


# ==========================================================
# CONFIGURAÇÃO
# ==========================================================

st.set_page_config(
    page_title="Mapa Cultural de Piabeta",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================================
# CONFIGURAÇÕES DO MAPA
# ==========================================================

DEFAULT_LAT = -10.90
DEFAULT_LON = -37.12
RAIO_METROS = 5000

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

DB = "mapa_cultural.db"


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

    .person-box {
        background: white;
        padding: 20px;
        border-radius: 16px;
        margin-bottom: 15px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.08);
        border-left: 5px solid #173b57;
    }

    .historical-box {
        background: white;
        padding: 20px;
        border-radius: 16px;
        margin-bottom: 15px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.08);
        border-left: 5px solid #7b3fb6;
    }

    .ai-box {
        background: linear-gradient(
            135deg,
            #173b57,
            #256d8f
        );

        color: white;
        padding: 20px;
        border-radius: 16px;
        margin-top: 15px;
    }

    .source-box {
        background: #eef4f8;
        padding: 15px;
        border-radius: 12px;
        font-size: 14px;
    }

    </style>
    """,
    unsafe_allow_html=True
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

    conn.commit()
    conn.close()


criar_banco()


# ==========================================================
# OPENSTREETMAP
# ==========================================================

def classificar_categoria(tags):

    if tags.get("shop"):
        return "Loja"

    amenity = tags.get("amenity", "")

    if amenity in [
        "restaurant",
        "cafe",
        "fast_food",
        "bar",
        "pub"
    ]:
        return "Restaurante"

    if amenity == "marketplace":
        return "Mercado"

    tourism = tags.get("tourism", "")

    if tourism in [
        "hotel",
        "guest_house"
    ]:
        return "Hotel"

    if tourism in [
        "museum",
        "attraction",
        "gallery"
    ]:
        return "Cultura"

    if tags.get("craft"):
        return "Serviço"

    if tags.get("office"):
        return "Serviço"

    if tags.get("leisure"):
        return "Turismo"

    return "Comércio"


def montar_endereco(tags):

    partes = []

    if tags.get("addr:street"):
        partes.append(tags.get("addr:street"))

    if tags.get("addr:housenumber"):
        partes.append(tags.get("addr:housenumber"))

    if tags.get("addr:suburb"):
        partes.append(tags.get("addr:suburb"))

    if tags.get("addr:city"):
        partes.append(tags.get("addr:city"))

    return ", ".join(partes)


def gerar_descricao_osm(nome, categoria, tags):

    if categoria == "Restaurante":

        return (
            f"{nome} é um estabelecimento "
            "de gastronomia localizado na "
            "região de Piabeta."
        )

    if categoria == "Loja":

        produto = tags.get("shop", "")

        if produto:

            return (
                f"{nome} é um comércio "
                "classificado no OpenStreetMap "
                f"como {produto}."
            )

        return (
            f"{nome} é um estabelecimento "
            "comercial localizado na região."
        )

    if categoria == "Hotel":

        return (
            f"{nome} é um estabelecimento "
            "de hospedagem."
        )

    if categoria == "Cultura":

        return (
            f"{nome} é um local relacionado "
            "à cultura ou ao turismo."
        )

    if categoria == "Mercado":

        return (
            f"{nome} é um estabelecimento "
            "de comércio de alimentos."
        )

    return (
        f"{nome} é um estabelecimento "
        "localizado na região de Piabeta."
    )


def buscar_comercios_osm():

    query = f"""
    [out:json][timeout:60];

    (
        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )
        ["name"]
        ["shop"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )
        ["name"]
        ["amenity"~"restaurant|cafe|fast_food|bar|pub|marketplace"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )
        ["name"]
        ["tourism"~"hotel|guest_house|museum|attraction|gallery"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )
        ["name"]
        ["office"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )
        ["name"]
        ["craft"];

        nwr(
            around:{RAIO_METROS},
            {DEFAULT_LAT},
            {DEFAULT_LON}
        )
        ["name"]
        ["leisure"~"sports_centre|stadium|park"];
    );

    out center tags;
    """

    try:

        resposta = requests.post(
            OVERPASS_URL,
            data=query,
            timeout=90
        )

        resposta.raise_for_status()

        dados = resposta.json()

        locais_osm = []

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

            endereco = montar_endereco(tags)

            descricao = gerar_descricao_osm(
                nome,
                categoria,
                tags
            )

            locais_osm.append(
                {
                    "nome": nome,
                    "categoria": categoria,
                    "descricao": descricao,
                    "endereco": endereco,
                    "telefone": tags.get("phone", ""),
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
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "avaliacao": 0
                }
            )

        unicos = {}

        for local in locais_osm:

            chave = (
                local["nome"].lower().strip(),
                round(local["latitude"], 5),
                round(local["longitude"], 5)
            )

            unicos[chave] = local

        return list(unicos.values())

    except Exception as e:

        st.error(
            "Não foi possível carregar os pontos "
            f"do OpenStreetMap: {e}"
        )

        return []


# ==========================================================
# LOCAIS CADASTRADOS NO BANCO
# ==========================================================

def carregar_locais_banco():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
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
            avaliacao
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
                "avaliacao": linha[10] or 0
            }
        )

    return locais


# ==========================================================
# PONTOS HISTÓRICOS
# ==========================================================

PONTOS_HISTORICOS = [

    {
        "nome": "🏖️ Prainha da Piabeta",

        "categoria": "História e Meio Ambiente",

        "descricao": (
            "A Prainha da Piabeta está localizada "
            "na região do Rio do Sal. Estudos da "
            "Universidade Federal de Sergipe registram "
            "atividades educativas e ambientais "
            "realizadas no local, incluindo ações "
            "de limpeza com estudantes."
        ),

        "endereco": (
            "Estrada Sítio do Vigário, s/n, "
            "Piabeta, Nossa Senhora do Socorro - SE"
        ),

        "latitude": -10.8845,

        "longitude": -37.1120,

        "fonte": (
            "Universidade Federal de Sergipe / "
            "dados locais"
        )
    },

    {
        "nome": "⛪ Paróquia Nossa Senhora de Montserrat",

        "categoria": "Cultura e Religião",

        "descricao": (
            "A Paróquia Nossa Senhora de Montserrat "
            "está localizada no Jardim Piabeta. "
            "A presença religiosa faz parte da vida "
            "comunitária da região. O Centro Escolápio "
            "registra que religiosas chegaram ao bairro "
            "em 2001 e que a capelinha da Comunidade "
            "Nossa Senhora de Montserrat foi inaugurada "
            "em 2003."
        ),

        "endereco": (
            "Av. Central/Rosemary Vieira de Jesus, "
            "1285, Jardim Piabeta, "
            "Nossa Senhora do Socorro - SE"
        ),

        "latitude": -10.8915,

        "longitude": -37.1195,

        "fonte": (
            "Arquidiocese de Aracaju / "
            "Centro Escolápio Nossa Senhora de Montserrat"
        )
    }

]


# ==========================================================
# FIGURAS COMUNITÁRIAS
# ==========================================================

FIGURAS_COMUNITARIAS = [

    {
        "nome": "👤 Washington de Oliveira Santos",

        "tipo": "Morador e liderança comunitária",

        "descricao": (
            "Washington de Oliveira Santos foi "
            "identificado pela imprensa sergipana "
            "como morador da Piabeta e liderança "
            "comunitária. Em 2015, informou que "
            "morava na localidade havia 28 anos. "
            "Em 2009, também aparece como líder "
            "comunitário da Piabeta em uma mobilização "
            "por segurança."
        ),

        "observacao": (
            "É apresentado como morador e liderança "
            "comunitária documentada, e não como "
            "personagem histórico oficial."
        )
    },

    {
        "nome": "👤 Paulo da Piabeta",

        "tipo": "Liderança comunitária",

        "descricao": (
            "Paulo da Piabeta foi citado em publicação "
            "sobre as demandas da comunidade como "
            "líder comunitário da Piabeta. A referência "
            "aparece em discussão pública sobre educação "
            "e a necessidade de escola pública de Ensino "
            "Médio para os jovens da região."
        ),

        "observacao": (
            "É apresentado como liderança comunitária "
            "documentada. O projeto não afirma que seja "
            "uma personalidade histórica oficial."
        )
    }

]


# ==========================================================
# CARREGAR TODOS OS PONTOS
# ==========================================================

@st.cache_data(ttl=600)
def carregar_pontos():

    locais_osm = buscar_comercios_osm()

    locais_banco = carregar_locais_banco()

    return locais_osm + locais_banco


locais_osm = carregar_pontos()


# ==========================================================
# OPENAI / SERGIA
# ==========================================================

def obter_chave_openai():

    try:

        return st.secrets["OPENAI_API_KEY"]

    except Exception:

        return os.environ.get("OPENAI_API_KEY")


def perguntar_ia(local, pergunta):

    chave = obter_chave_openai()

    if not chave:

        return (
            "⚠️ A SergIA ainda não está configurada.\n\n"
            "Coloque sua OPENAI_API_KEY nos Secrets "
            "do Streamlit."
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

Latitude: {local.get('latitude', '')}

Longitude: {local.get('longitude', '')}
"""

        contexto_piabeta = """

CONTEXTO DO PROJETO:

O projeto é sobre Piabeta,
no município de Nossa Senhora do Socorro,
estado de Sergipe.

Piabeta é uma localidade/bairro de
Nossa Senhora do Socorro, Sergipe.

A Prefeitura Municipal de Nossa Senhora
do Socorro lista Piabeta entre os principais
conjuntos habitacionais do município.

O município de Nossa Senhora do Socorro
possui história documentada desde o período
colonial.

Segundo a Prefeitura e o IBGE, o território
era habitado por povos indígenas antes da
colonização portuguesa.

A freguesia de Nossa Senhora do Perpétuo
Socorro do Tomar da Cotinguiba foi criada
em 25 de setembro de 1718.

Em 19 de fevereiro de 1835, o povoado foi
elevado à categoria de vila e foi criado
o município.

O município passou por grandes transformações
urbanas a partir da década de 1980, quando
novos empreendimentos habitacionais e
loteamentos transformaram diversas áreas.

Piabeta aparece nesse processo de crescimento
urbano e habitacional.

SOBRE A ORIGEM DO NOME "PIABETA":

Não foi encontrada, nas fontes consultadas
para este projeto, uma fonte histórica ou
linguística confiável que estabeleça de forma
definitiva a origem do nome Piabeta de
Nossa Senhora do Socorro-SE.

Existe uma explicação conhecida para
"Piabetá" relacionada a uma localidade
homônima de Magé, no Rio de Janeiro.

Essa explicação NÃO deve ser atribuída
à Piabeta de Sergipe.

Se o usuário perguntar:

"Qual é a origem do nome Piabeta?"

responda que a origem específica do nome
da localidade sergipana não foi confirmada
pelas fontes disponíveis no projeto.

Não invente uma tradução indígena.

PONTOS DO PROJETO:

1. Prainha da Piabeta

Está localizada na região do Rio do Sal.
Há registros acadêmicos da UFS sobre
atividades de educação ambiental realizadas
no local com estudantes.

2. Paróquia Nossa Senhora de Montserrat

Está localizada no Jardim Piabeta.
O Centro Escolápio registra a chegada
das religiosas ao bairro em 2001 e a
inauguração da capelinha da comunidade
em 2003.

FIGURAS COMUNITÁRIAS:

Washington de Oliveira Santos:

Morador da Piabeta e liderança comunitária
documentada em matérias jornalísticas.
Em 2015, declarou morar na localidade
havia 28 anos.

Paulo da Piabeta:

Foi citado como líder comunitário da Piabeta
em uma publicação sobre demandas da
comunidade relacionadas à educação.

Não classifique automaticamente essas
pessoas como "figuras históricas".
Prefira "morador", "liderança comunitária"
ou "figura da comunidade".
"""

        instrucoes = """

Você é a SergIA, a Assistente Cultural
de Sergipe do Mapa Cultural de Piabeta.

Sua função é explicar:

- história de Piabeta;
- cultura local;
- pontos de interesse;
- religião;
- meio ambiente;
- comércio;
- moradores e lideranças;
- história de Nossa Senhora do Socorro;
- informações culturais de Sergipe.

REGRAS:

1. Responda em português do Brasil.

2. Não invente fatos.

3. Não invente a origem do nome Piabeta.

4. Nunca confunda Piabeta-SE com
Piabetá-Magé-RJ.

5. Se houver falta de informação,
diga claramente.

6. Diferencie fatos documentados,
relatos de moradores e interpretações.

7. Não transforme uma pessoa citada
em jornal como "personagem histórico"
sem evidência.

8. Seja amigável e fácil de entender.

9. Quando falar de história, indique
quando a informação é baseada em fonte
oficial, acadêmica ou relato jornalístico.

10. Quando a pergunta for sobre um
estabelecimento do mapa, use os dados
fornecidos sobre o estabelecimento e
não invente informações adicionais.

"""

        prompt = f"""

CONTEXTO HISTÓRICO:

{contexto_piabeta}

DADOS DO LOCAL:

{contexto}

PERGUNTA DO USUÁRIO:

{pergunta}

"""

        resposta = client.responses.create(
            model="gpt-5.6",
            instructions=instrucoes,
            input=prompt
        )

        return resposta.output_text

    except Exception as e:

        return (
            "❌ Erro ao consultar a SergIA:\n\n"
            f"{e}"
        )


# ==========================================================
# CABEÇALHO
# ==========================================================

st.markdown(
    "# 🗺️ Mapa Cultural de Piabeta"
)

st.markdown(
    """
    Explore **comércio, gastronomia, cultura,
    meio ambiente e história de Piabeta**.
    """
)

st.info(
    """
    📍 Piabeta — Nossa Senhora do Socorro,
    Sergipe
    """
)


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title(
    "🎛️ Explorar"
)

if locais_osm:

    categorias = sorted(
        list(
            set(
                local["categoria"]
                for local in locais_osm
            )
        )
    )

else:

    categorias = []


categorias_selecionadas = st.sidebar.multiselect(

    "Categorias",

    categorias,

    default=categorias

)

st.sidebar.markdown("---")


mostrar_historicos = st.sidebar.checkbox(
    "🏛️ Mostrar pontos culturais",
    value=True
)


mostrar_comunidade = st.sidebar.checkbox(
    "👥 Mostrar figuras comunitárias",
    value=True
)


st.sidebar.markdown("---")


st.sidebar.info(
    """
    🗺️ Comércio e serviços:
    OpenStreetMap

    🏛️ Cultura e história:
    informações selecionadas
    para o projeto.

    🤖 IA:
    SergIA
    """
)


if st.sidebar.button(
    "🔄 Atualizar pontos"
):

    carregar_pontos.clear()

    st.rerun()


# ==========================================================
# PESQUISA
# ==========================================================

st.subheader(
    "🔎 Pesquisar"
)

with st.form("pesquisa_form"):

    pesquisa = st.text_input(

        "Pesquisar",

        placeholder=(
            "Ex: restaurante, loja, "
            "Piabeta, cultura, igreja..."
        ),

        label_visibility="collapsed"

    )

    pesquisar = st.form_submit_button(
        "🔍 Buscar"
    )


termo = pesquisa.lower().strip()


resultados = []


for local in locais_osm:

    if (
        categorias_selecionadas
        and local["categoria"]
        not in categorias_selecionadas
    ):

        continue

    texto = " ".join(
        [
            local["nome"],
            local["categoria"],
            local["descricao"],
            local["endereco"]
        ]
    ).lower()

    if not termo or termo in texto:

        resultados.append(local)


# ==========================================================
# PESQUISAR PONTOS CULTURAIS
# ==========================================================

historicos_resultados = []


for ponto in PONTOS_HISTORICOS:

    texto = " ".join(
        [
            ponto["nome"],
            ponto["categoria"],
            ponto["descricao"],
            ponto["endereco"]
        ]
    ).lower()

    if not termo or termo in texto:

        historicos_resultados.append(ponto)


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
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


# ==========================================================
# MÉTRICAS
# ==========================================================

total_pontos = (
    len(resultados)
    +
    (
        len(historicos_resultados)
        if mostrar_historicos
        else 0
    )
)


col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "📍 Pontos",
        total_pontos
    )


with col2:

    st.metric(
        "🏛️ Cultura",
        len(historicos_resultados)
        if mostrar_historicos
        else 0
    )


with col3:

    st.metric(
        "🏪 Comércio",
        len(
            [
                x for x in resultados
                if x["categoria"]
                in [
                    "Loja",
                    "Mercado",
                    "Serviço"
                ]
            ]
        )
    )


with col4:

    st.metric(
        "🍴 Gastronomia",
        len(
            [
                x for x in resultados
                if x["categoria"]
                == "Restaurante"
            ]
        )
    )


# ==========================================================
# MAPA
# ==========================================================

st.subheader(
    "📍 Mapa de Piabeta"
)


mapa = folium.Map(

    location=[
        DEFAULT_LAT,
        DEFAULT_LON
    ],

    zoom_start=14,

    control_scale=True,

    tiles="OpenStreetMap"
)


# ==========================================================
# CORES E ÍCONES
# ==========================================================

cores = {

    "Cultura": "purple",

    "História": "purple",

    "História e Meio Ambiente": "green",

    "Cultura e Religião": "purple",

    "Restaurante": "red",

    "Loja": "blue",

    "Mercado": "green",

    "Hotel": "orange",

    "Turismo": "cadetblue",

    "Serviço": "darkblue",

    "Comércio": "gray"

}


icones = {

    "Restaurante": "cutlery",

    "Loja": "shopping-cart",

    "Mercado": "shopping-cart",

    "Hotel": "home",

    "Serviço": "wrench",

    "Turismo": "tree-conifer",

    "Cultura": "info-sign",

    "Comércio": "shopping-cart"

}


# ==========================================================
# MARCADORES COMERCIAIS
# ==========================================================

for local in resultados:

    nome = html.escape(
        local["nome"]
    )

    categoria = local["categoria"]

    descricao = html.escape(
        local["descricao"]
    )

    endereco = html.escape(
        local["endereco"]
    )

    horario = html.escape(
        local["horario"]
    )

    telefone = html.escape(
        local["telefone"]
    )

    site = html.escape(
        local["site"]
    )

    imagem = local.get("imagem", "")


    imagem_html = ""

    if imagem:

        imagem_segura = html.escape(
            imagem,
            quote=True
        )

        imagem_html = f"""
        <img
            src="{imagem_segura}"
            style="
                width:100%;
                max-height:150px;
                object-fit:cover;
                border-radius:10px;
                margin-bottom:10px;
            "
        >
        """


    site_html = ""

    if site:

        site_html = f"""
        <p>
            🌐
            <a
                href="{site}"
                target="_blank"
            >
                Visitar site
            </a>
        </p>
        """


    popup = f"""

    <div style="
        width:280px;
        font-family:Arial;
    ">

        {imagem_html}

        <h3 style="
            color:#173b57;
            margin-bottom:5px;
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
            📍
            {
                endereco
                or
                "Endereço não informado"
            }
        </p>

        <p>
            🕐
            {
                horario
                or
                "Horário não informado"
            }
        </p>

        <p>
            📞
            {
                telefone
                or
                "Telefone não informado"
            }
        </p>

        {site_html}

    </div>

    """


    folium.Marker(

        location=[
            local["latitude"],
            local["longitude"]
        ],

        tooltip=local["nome"],

        popup=folium.Popup(
            popup,
            max_width=350
        ),

        icon=folium.Icon(

            color=cores.get(
                categoria,
                "blue"
            ),

            icon=icones.get(
                categoria,
                "map-marker"
            )

        )

    ).add_to(mapa)


# ==========================================================
# MARCADORES CULTURAIS
# ==========================================================

if mostrar_historicos:

    for ponto in historicos_resultados:

        nome = html.escape(
            ponto["nome"]
        )

        categoria = html.escape(
            ponto["categoria"]
        )

        descricao = html.escape(
            ponto["descricao"]
        )

        endereco = html.escape(
            ponto["endereco"]
        )

        fonte = html.escape(
            ponto["fonte"]
        )

        popup = f"""

        <div style="
            width:310px;
            font-family:Arial;
        ">

            <h3 style="
                color:#673a91;
            ">
                {nome}
            </h3>

            <p>
                <b>🏛️ {categoria}</b>
            </p>

            <p>
                {descricao}
            </p>

            <p>
                📍 {endereco}
            </p>

            <hr>

            <small>
                Fonte:
                {fonte}
            </small>

        </div>

        """


        folium.Marker(

            location=[
                ponto["latitude"],
                ponto["longitude"]
            ],

            tooltip=ponto["nome"],

            popup=folium.Popup(
                popup,
                max_width=360
            ),

            icon=folium.Icon(

                color="purple",

                icon="info-sign"

            )

        ).add_to(mapa)


# ==========================================================
# CENTRALIZAR MAPA
# ==========================================================

todos_pontos_mapa = []

for local in resultados:

    todos_pontos_mapa.append(
        [
            local["latitude"],
            local["longitude"]
        ]
    )


if mostrar_historicos:

    for ponto in historicos_resultados:

        todos_pontos_mapa.append(
            [
                ponto["latitude"],
                ponto["longitude"]
            ]
        )


if todos_pontos_mapa:

    mapa.fit_bounds(
        todos_pontos_mapa
    )


# ==========================================================
# LEGENDA
# ==========================================================

legenda = """

<div style="
    position: fixed;
    bottom: 30px;
    left: 30px;
    width: 220px;
    background-color: white;
    border: 2px solid #999;
    z-index: 9999;
    font-size: 14px;
    padding: 12px;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
">

<b>🗺️ Legenda</b>

<br><br>

🔵 Comércio

<br>

🔴 Gastronomia

<br>

🟢 Mercado

<br>

🟠 Hotel

<br>

🟣 Cultura / religião

<br>

🟢 Meio ambiente

</div>

"""


mapa.get_root().html.add_child(
    folium.Element(legenda)
)


st_folium(

    mapa,

    width=None,

    height=600,

    returned_objects=[]

)


# ==========================================================
# HISTÓRIA
# ==========================================================

st.markdown("---")

st.subheader(
    "📜 História de Piabeta"
)


st.markdown(

    """
    <div class="history-box">

        <h2>🏘️ Piabeta e Nossa Senhora do Socorro</h2>

        <p>
        <b>Piabeta</b> é uma localidade/bairro do
        município de <b>Nossa Senhora do Socorro,
        Sergipe</b>.
        </p>

        <p>
        A Prefeitura Municipal de Nossa Senhora
        do Socorro inclui Piabeta entre os principais
        conjuntos habitacionais do município.
        </p>

        <p>
        O crescimento urbano de Nossa Senhora do
        Socorro se intensificou principalmente a
        partir da década de 1980, com novos
        empreendimentos habitacionais e mudanças
        na ocupação do território.
        </p>

        <p>
        Portanto, a história de Piabeta também está
        relacionada ao processo de crescimento urbano
        e habitacional da Região Metropolitana de
        Aracaju.
        </p>

    </div>
    """,

    unsafe_allow_html=True

)


# ==========================================================
# ORIGEM DO NOME
# ==========================================================

st.subheader(
    "📖 Origem do nome Piabeta"
)


st.markdown(

    """
    <div class="card">

        <h3>🔎 O que sabemos?</h3>

        <p>
        A origem específica do nome
        <b>Piabeta</b>, em Nossa Senhora do
        Socorro-SE, ainda não foi confirmada
        por uma fonte histórica ou linguística
        suficientemente confiável nas fontes
        consultadas para este projeto.
        </p>

        <p>
        Por isso, o Mapa Cultural não apresenta
        uma tradução ou significado como se fosse
        um fato comprovado.
        </p>

        <p>
        Existe uma localidade homônima chamada
        <b>Piabetá</b> em Magé, no Rio de Janeiro,
        mas as explicações relacionadas a ela não
        devem ser automaticamente transferidas para
        Piabeta, em Sergipe.
        </p>

        <p>
        Uma futura etapa do projeto pode buscar
        documentos municipais, mapas antigos,
        registros de loteamento, jornais antigos
        e entrevistas com moradores para tentar
        descobrir a origem do nome utilizado
        pela comunidade.
        </p>

    </div>
    """,

    unsafe_allow_html=True

)


# ==========================================================
# FIGURAS COMUNITÁRIAS
# ==========================================================

st.subheader(
    "👥 Moradores e lideranças da comunidade"
)


st.warning(
    """
    As pessoas abaixo aparecem em fontes públicas
    como moradores ou lideranças comunitárias.
    O projeto não as classifica como personagens
    históricos oficiais sem documentação suficiente.
    """
)


if mostrar_comunidade:

    for figura in FIGURAS_COMUNITARIAS:

        st.markdown(

            f"""
            <div class="person-box">

                <h3>
                    {html.escape(
                        figura["nome"]
                    )}
                </h3>

                <span class="badge">
                    {html.escape(
                        figura["tipo"]
                    )}
                </span>

                <p>
                    {html.escape(
                        figura["descricao"]
                    )}
                </p>

                <small>
                    ℹ️ {html.escape(
                        figura["observacao"]
                    )}
                </small>

            </div>
            """,

            unsafe_allow_html=True

        )


# ==========================================================
# PONTOS CULTURAIS
# ==========================================================

st.markdown("---")

st.subheader(
    "🏛️ Pontos culturais de Piabeta"
)


for ponto in PONTOS_HISTORICOS:

    st.markdown(

        f"""
        <div class="historical-box">

            <h2>
                {html.escape(
                    ponto["nome"]
                )}
            </h2>

            <span class="badge">
                {html.escape(
                    ponto["categoria"]
                )}
            </span>

            <p>
                {html.escape(
                    ponto["descricao"]
                )}
            </p>

            <p>
                📍
                {
                    html.escape(
                        ponto["endereco"]
                    )
                }
            </p>

            <small>
                Fonte:
                {
                    html.escape(
                        ponto["fonte"]
                    )
                }
            </small>

        </div>
        """,

        unsafe_allow_html=True

    )


# ==========================================================
# SERGIA
# ==========================================================

st.markdown("---")

st.subheader(
    "🤖 SergIA — Assistente Cultural de Sergipe"
)


st.write(
    """
    Pergunte à **SergIA** sobre Piabeta,
    seus pontos de interesse, sua comunidade
    ou sobre Nossa Senhora do Socorro.
    """
)


locais_para_ia = (
    resultados
    + historicos_resultados
)


if locais_para_ia:

    local_nomes = [

        local["nome"]

        for local in locais_para_ia

    ]


    local_escolhido = st.selectbox(

        "Escolha um local",

        local_nomes

    )


    local_ia = next(

        local

        for local in locais_para_ia

        if local["nome"]
        == local_escolhido

    )

else:

    local_ia = {

        "nome": "Piabeta",

        "categoria": "História",

        "descricao": (
            "Piabeta, Nossa Senhora "
            "do Socorro-SE."
        ),

        "endereco":
            "Piabeta, Nossa Senhora do Socorro-SE",

        "telefone": "",

        "horario": "",

        "site": "",

        "latitude":
            DEFAULT_LAT,

        "longitude":
            DEFAULT_LON

    }


pergunta = st.text_area(

    "O que você quer saber?",

    placeholder=(
        "Ex: Qual é a história de Piabeta? "
        "Qual a origem do nome Piabeta? "
        "Quem são moradores antigos? "
        "Qual a importância da Prainha?"
    )

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
            "🤖 SergIA está preparando a resposta..."
        ):

            resposta = perguntar_ia(

                local_ia,

                pergunta

            )


        st.markdown(

            """
            <div class="ai-box">

                <h3>
                    🤖 SergIA
                </h3>

                <p>
                    Assistente Cultural de Sergipe
                </p>

            </div>
            """,

            unsafe_allow_html=True

        )


        st.markdown(
            resposta
        )


# ==========================================================
# RESULTADOS COMERCIAIS
# ==========================================================

st.markdown("---")

st.subheader(
    "📚 Locais encontrados"
)


if resultados:

    for indice, local in enumerate(
        resultados
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

                st.image(
                    imagem,
                    use_container_width=True
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
                        local["nome"]
                    )}
                </h2>

                <span class="badge">
                    {html.escape(
                        local["categoria"]
                    )}
                </span>

                <p>
                    {html.escape(
                        local["descricao"]
                    )}
                </p>

                <p>
                    📍
                    {
                        html.escape(
                            local["endereco"]
                            or
                            "Endereço não informado"
                        )
                    }
                </p>

                <p>
                    🕐
                    {
                        html.escape(
                            local["horario"]
                            or
                            "Horário não informado"
                        )
                    }
                </p>

                <p>
                    📞
                    {
                        html.escape(
                            local["telefone"]
                            or
                            "Telefone não informado"
                        )
                    }
                </p>
                """,

                unsafe_allow_html=True

            )


            if local.get("site"):

                st.markdown(
                    f"[🌐 Visitar site]({local['site']})"
                )


            if st.button(

                "🤖 Conhecer este local com SergIA",

                key=f"ia_{indice}"

            ):

                with st.spinner(
                    "🤖 SergIA está preparando informações..."
                ):

                    resposta = perguntar_ia(

                        local,

                        (
                            "Conte o que é este "
                            "local e explique sua "
                            "importância para "
                            "Piabeta, sem inventar."
                        )

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
        "Nenhum ponto comercial encontrado."
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

    categoria = local["categoria"]

    contagem[categoria] = (

        contagem.get(
            categoria,
            0
        )
        + 1

    )


if mostrar_historicos:

    contagem["Cultura / História"] = (
        len(historicos_resultados)
    )


if contagem:

    dados = {

        "Categoria":
            list(contagem.keys()),

        "Quantidade":
            list(contagem.values())

    }


    grafico = px.bar(

        dados,

        x="Categoria",

        y="Quantidade",

        color="Categoria",

        title="Locais por categoria"

    )


    grafico.update_layout(

        plot_bgcolor="white",

        paper_bgcolor="white",

        showlegend=False

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

            [

                "Cultura",

                "História",

                "Restaurante",

                "Loja",

                "Mercado",

                "Hotel",

                "Eventos",

                "Turismo",

                "Serviço"

            ]

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


        col1, col2 = st.columns(2)


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


        avaliacao = st.slider(

            "Avaliação",

            0.0,

            5.0,

            5.0,

            0.1

        )


        salvar = st.form_submit_button(

            "💾 Salvar local"

        )


        if salvar:

            if not nome:

                st.error(
                    "Digite o nome do local."
                )

            else:

                conn = conectar()

                cursor = conn.cursor()


                cursor.execute(

                    """
                    INSERT INTO locais
                    (
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
                        criado_em
                    )

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,

                    (

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

                        datetime.now().isoformat()

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
# FONTES
# ==========================================================

st.markdown("---")

st.subheader(
    "📚 Fontes e referências"
)


st.markdown(

    """
    <div class="source-box">

    <b>Fontes utilizadas na construção
    do conteúdo histórico:</b>

    <br><br>

    • Prefeitura Municipal de Nossa Senhora
    do Socorro — História do município

    <br><br>

    • IBGE — Histórico de Nossa Senhora
    do Socorro

    <br><br>

    • Universidade Federal de Sergipe —
    estudos relacionados à Prainha da Piabeta

    <br><br>

    • Arquidiocese de Aracaju —
    Paróquia Nossa Senhora de Montserrat

    <br><br>

    • Centro Escolápio Nossa Senhora
    de Montserrat — história da comunidade
    no bairro Piabeta

    <br><br>

    • Imprensa sergipana — registros de
    moradores e lideranças comunitárias

    <br><br>

    • OpenStreetMap — pontos comerciais
    e localização

    <br><br>

    • OpenAI — Assistente SergIA

    </div>
    """,

    unsafe_allow_html=True

)


# ==========================================================
# RODAPÉ
# ==========================================================

st.markdown("---")

st.caption(

    "🗺️ Mapa Cultural de Piabeta • "
    "Nossa Senhora do Socorro - SE • "
    "Python + Streamlit + OpenStreetMap + OpenAI • "
    "🤖 SergIA"

)
