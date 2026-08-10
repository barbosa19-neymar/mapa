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
    page_title="Mapa Cultural",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# CONFIGURAÇÕES DO MAPA
# ==========================================================

# Região inicial do seu projeto
DEFAULT_LAT = -10.855
DEFAULT_LON = -37.125

PONTOS_HISTORICOS = [
    {
        "nome": "Shopping Prêmio",
        "categoria": "História",
        "descricao": "Importante ponto de referência de Nossa Senhora do Socorro. Foi anunciado em 2008 e concluído em 2011, sendo apresentado como o primeiro shopping center do município.",
        "endereco": "Nossa Senhora do Socorro - SE",
        "latitude": -10.846,
        "longitude": -37.126
    },

    {
        "nome": "Centro Histórico de Nossa Senhora do Socorro",
        "categoria": "História",
        "descricao": "Região ligada à formação histórica de Nossa Senhora do Socorro. A ocupação da região remonta ao período colonial e o núcleo foi elevado à categoria de vila em 1835.",
        "endereco": "Centro, Nossa Senhora do Socorro - SE",
        "latitude": -10.855,
        "longitude": -37.126
    }
]
# Raio de busca dos pontos comerciais
RAIO_METROS = 8000

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

DB = "mapa_cultural.db"

# ==========================================================
# ESTILO
# ==========================================================

st.markdown("""
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

.ai-box {
    background: linear-gradient(135deg, #173b57, #256d8f);
    color: white;
    padding: 20px;
    border-radius: 16px;
    margin-top: 15px;
}

</style>
""", unsafe_allow_html=True)

# ==========================================================
# BANCO
# ==========================================================

def conectar():
    return sqlite3.connect(DB)


def criar_banco():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
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
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pesquisas (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            termo TEXT,

            data TEXT
        )
    """)

    conn.commit()
    conn.close()


criar_banco()

# ==========================================================
# OPENSTREETMAP
# ==========================================================

def buscar_comercios_osm():

    query = f"""
    [out:json][timeout:60];

    (
        nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})
            ["name"]
            ["shop"];

        nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})
            ["name"]
            ["amenity"~"restaurant|cafe|fast_food|bar|pub|marketplace"];

        nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})
            ["name"]
            ["tourism"~"hotel|guest_house|museum|attraction|gallery"];

        nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})
            ["name"]
            ["office"];

        nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})
            ["name"]
            ["craft"];

        nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})
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

            # Ways e relations possuem center
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

            locais_osm.append({

                "nome": nome,

                "categoria": categoria,

                "descricao": descricao,

                "endereco": endereco,

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

                "latitude": float(latitude),

                "longitude": float(longitude),

                "avaliacao": 0

            })

        # Remove duplicados
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
            f"Não foi possível carregar os pontos comerciais: {e}"
        )

        return []


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
        partes.append(
            tags.get("addr:street")
        )

    if tags.get("addr:housenumber"):
        partes.append(
            tags.get("addr:housenumber")
        )

    if tags.get("addr:suburb"):
        partes.append(
            tags.get("addr:suburb")
        )

    if tags.get("addr:city"):
        partes.append(
            tags.get("addr:city")
        )

    return ", ".join(partes)


def gerar_descricao_osm(
    nome,
    categoria,
    tags
):

    if categoria == "Restaurante":
        return f"{nome} é um estabelecimento de gastronomia."

    if categoria == "Loja":
        produto = tags.get("shop", "")

        if produto:
            return (
                f"{nome} é um comércio "
                f"classificado no OpenStreetMap "
                f"como {produto}."
            )

        return f"{nome} é um estabelecimento comercial."

    if categoria == "Hotel":
        return f"{nome} é um estabelecimento de hospedagem."

    if categoria == "Cultura":
        return (
            f"{nome} é um local relacionado "
            f"à cultura ou ao turismo."
        )

    if categoria == "Mercado":
        return f"{nome} é um estabelecimento de comércio de alimentos."

    return f"{nome} é um estabelecimento localizado na região."


# ==========================================================
# CARREGAR PONTOS
# ==========================================================

@st.cache_data(ttl=600)
def carregar_pontos():

    return buscar_comercios_osm()


locais_osm = carregar_pontos()

# ==========================================================
# IA OPENAI
# ==========================================================

def obter_chave_openai():

    try:

        return st.secrets["OPENAI_API_KEY"]

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
            "⚠️ A IA ainda não está configurada. "
            "Adicione OPENAI_API_KEY nos secrets "
            "do Streamlit."
        )

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=chave
        )

        contexto = f"""
Nome: {local['nome']}
Categoria: {local['categoria']}
Descrição: {local['descricao']}
Endereço: {local['endereco']}
Telefone: {local['telefone']}
Horário: {local['horario']}
Site: {local['site']}
Latitude: {local['latitude']}
Longitude: {local['longitude']}
"""

        instrucoes = """
Você é a IA oficial do projeto Mapa Cultural.

Sua função é explicar informações sobre
locais comerciais, culturais, turísticos e
históricos.

IMPORTANTE:

- Não invente fatos históricos.
- Se não houver informação suficiente,
  diga claramente que não há dados históricos
  disponíveis.
- Diferencie fatos conhecidos de contexto geral.
- Responda em português do Brasil.
- Seja amigável e fácil de entender.
- Quando o usuário perguntar sobre a história
  de um estabelecimento, explique o que é possível
  saber com os dados disponíveis.
- Você pode explicar a importância cultural,
  comercial ou turística de um local.
"""

        prompt = f"""
DADOS DO LOCAL:

{contexto}

PERGUNTA DO USUÁRIO:

{pergunta}
"""

        resposta = client.responses.create(

            model="gpt-5",

            instructions=instrucoes,

            input=prompt

        )

        return resposta.output_text

    except Exception as e:

        return (
            "❌ Erro ao consultar a IA: "
            f"{e}"
        )


# ==========================================================
# CABEÇALHO
# ==========================================================

st.markdown(
    "# 🗺️ Mapa Cultural"
)

st.markdown(
    "Explore **comércio, gastronomia, cultura e turismo** da região."
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

st.sidebar.info(
    "📍 Os pontos comerciais são carregados "
    "do OpenStreetMap."
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

with st.form(
    "pesquisa_form"
):

    pesquisa = st.text_input(

        "Pesquisar",

        placeholder=(
            "Ex: restaurante, loja, "
            "hotel, cultura..."
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

    texto = " ".join([

        local["nome"],

        local["categoria"],

        local["descricao"],

        local["endereco"]

    ]).lower()

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
            datetime.now().isoformat()
        )
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
        "🏷️ Categorias",
        len(
            set(
                x["categoria"]
                for x in resultados
            )
        )
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
    "📍 Mapa de pontos comerciais"
)

if resultados:

    centro_lat = resultados[0]["latitude"]

    centro_lon = resultados[0]["longitude"]

else:

    centro_lat = DEFAULT_LAT

    centro_lon = DEFAULT_LON


mapa = folium.Map(

    location=[
        centro_lat,
        centro_lon
    ],

    zoom_start=14,

    control_scale=True,

    tiles="OpenStreetMap"

)

# ==========================================================
# CORES
# ==========================================================

cores = {

    "Cultura": "purple",

    "Restaurante": "red",

    "Loja": "blue",

    "Mercado": "green",

    "Hotel": "orange",

    "Turismo": "cadetblue",

    "Serviço": "darkblue",

    "Comércio": "gray"

}

# ==========================================================
# MARCADORES
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

    popup = f"""

    <div style="
        width:280px;
        font-family:Arial;
    ">

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
            📍 {endereco or "Endereço não informado"}
        </p>

        <p>
            🕐 {horario or "Horário não informado"}
        </p>

        <p>
            📞 {telefone or "Telefone não informado"}
        </p>

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

            icon="shopping-cart"

        )

    ).add_to(mapa)


st_folium(

    mapa,

    width=None,

    height=600,

    returned_objects=[]

)

# ==========================================================
# IA GERAL
# ==========================================================

st.markdown("---")

st.subheader(
    "🤖 Assistente Cultural"
)

st.write(
    "Pergunte sobre um estabelecimento ou "
    "local encontrado no mapa."
)

local_nomes = [
    local["nome"]
    for local in resultados
]

if local_nomes:

    local_escolhido = st.selectbox(

        "Escolha um local",

        local_nomes

    )

    local_ia = next(

        local for local in resultados

        if local["nome"]
        == local_escolhido

    )

    pergunta = st.text_area(

        "O que você quer saber?",

        placeholder=(
            "Ex: Qual é a história deste local? "
            "Qual a importância cultural dele? "
            "O que esse estabelecimento oferece?"
        )

    )

    if st.button(
        "🤖 Perguntar à IA",
        type="primary"
    ):

        if not pergunta.strip():

            st.warning(
                "Digite uma pergunta."
            )

        else:

            with st.spinner(
                "🤖 A IA está pesquisando..."
            ):

                resposta = perguntar_ia(
                    local_ia,
                    pergunta
                )

            st.markdown(
                f"""
                <div class="ai-box">

                <h3>🤖 Resposta da IA</h3>

                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown(
                resposta
            )

else:

    st.info(
        "Nenhum local encontrado para consultar."
    )

# ==========================================================
# RESULTADOS
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
                    {html.escape(local["nome"])}
                </h2>

                <span class="badge">
                    {local["categoria"]}
                </span>

                <p>
                    {html.escape(local["descricao"])}
                </p>

                <p>
                    📍 {
                        html.escape(
                            local["endereco"]
                            or "Endereço não informado"
                        )
                    }
                </p>

                <p>
                    🕐 {
                        html.escape(
                            local["horario"]
                            or "Horário não informado"
                        )
                    }
                </p>

                <p>
                    📞 {
                        html.escape(
                            local["telefone"]
                            or "Telefone não informado"
                        )
                    }
                </p>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "🤖 Conhecer este local com IA",
                key=f"ia_{indice}"
            ):

                with st.spinner(
                    "🤖 Preparando informações..."
                ):

                    resposta = perguntar_ia(

                        local,

                        (
                            "Conte a história deste local "
                            "e explique sua importância "
                            "cultural, comercial ou turística. "
                            "Não invente informações."
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
        "Nenhum ponto encontrado."
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
        ) + 1
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
                        "",
                        latitude,
                        longitude,
                        avaliacao,
                        datetime.now().isoformat()
                    )
                )

                conn.commit()

                conn.close()

                st.success(
                    "✅ Local cadastrado!"
                )

                st.rerun()

# ==========================================================
# RODAPÉ
# ==========================================================

st.markdown("---")

st.caption(
    "🗺️ Mapa Cultural • "
    "Python + Streamlit + OpenStreetMap + OpenAI"
)
