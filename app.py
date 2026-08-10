import streamlit as st
import folium
import requests
import html
import os
import sqlite3
from datetime import datetime
from streamlit_folium import st_folium

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

DEFAULT_LAT = -10.855
DEFAULT_LON = -37.125

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

.history-box {
    background: #eee6f7;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 15px;
}

.memory-box {
    background: #e8f5e9;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)

# ==========================================================
# BANCO DE DADOS
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

        # ==================================================
        # REMOVER DUPLICADOS
        # ==================================================

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
            f"Não foi possível carregar os pontos: {e}"
        )

        return []


# ==========================================================
# CLASSIFICAÇÃO
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


# ==========================================================
# ENDEREÇO
# ==========================================================

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


# ==========================================================
# DESCRIÇÃO
# ==========================================================

def gerar_descricao_osm(
    nome,
    categoria,
    tags
):

    if categoria == "Restaurante":

        return (
            f"{nome} é um estabelecimento "
            "de gastronomia."
        )

    if categoria == "Loja":

        produto = tags.get("shop", "")

        if produto:

            return (
                f"{nome} é um comércio "
                f"classificado no OpenStreetMap "
                f"como {produto}."
            )

        return (
            f"{nome} é um estabelecimento comercial."
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
        "localizado na região."
    )


# ==========================================================
# CARREGAR PONTOS
# ==========================================================

@st.cache_data(ttl=600)
def carregar_pontos():

    return buscar_comercios_osm()


locais_osm = carregar_pontos()


# ==========================================================
# PONTOS HISTÓRICOS
# ==========================================================

PONTOS_HISTORICOS = [

    {
        "nome": "Centro Histórico de Nossa Senhora do Socorro",

        "categoria": "História",

        "descricao": (
            "Local ligado à formação histórica de "
            "Nossa Senhora do Socorro. A região era "
            "habitada por povos indígenas antes da "
            "colonização portuguesa. Em 25 de setembro "
            "de 1718, a localidade foi elevada à "
            "categoria de freguesia."
        ),

        "endereco": (
            "Centro, Nossa Senhora do Socorro - SE"
        ),

        "telefone": "",
        "horario": "",
        "site": "",
        "imagem": "",

        "latitude": -10.855,
        "longitude": -37.125,

        "avaliacao": 0
    },

    {
        "nome": "Piabeta",

        "categoria": "Memória Local",

        "descricao": (
            "Piabeta é um dos conjuntos habitacionais "
            "de Nossa Senhora do Socorro. A origem "
            "específica do nome Piabeta ainda não foi "
            "confirmada em fonte histórica oficial "
            "consultada."
        ),

        "endereco": (
            "Piabeta, Nossa Senhora do Socorro - SE"
        ),

        "telefone": "",
        "horario": "",
        "site": "",
        "imagem": "",

        "latitude": -10.858,
        "longitude": -37.126,

        "avaliacao": 0
    }

]


# ==========================================================
# JUNTAR LOCAIS
# ==========================================================

locais = locais_osm + PONTOS_HISTORICOS


# ==========================================================
# FIGURAS HISTÓRICAS
# ==========================================================

FIGURAS_HISTORICAS = [

    {
        "nome": "Cacique Serigy",

        "periodo": "Período anterior à colonização",

        "descricao": (
            "Cacique indígena associado ao território "
            "onde atualmente está localizado "
            "Nossa Senhora do Socorro. A história "
            "oficial do município registra que as "
            "terras eram dominadas por indígenas "
            "da tribo do cacique Serigy."
        ),

        "observacao": (
            "Figura histórica ligada ao território "
            "do município. Não há comprovação de que "
            "tenha sido morador de Piabeta."
        )
    },

    {
        "nome": "Dom Sebastião Monteiro da Vide",

        "periodo": "Século XVIII",

        "descricao": (
            "Arcebispo da Bahia que, em 25 de setembro "
            "de 1718, elevou a localidade à categoria "
            "de freguesia, sob a invocação de Nossa "
            "Senhora do Perpétuo Socorro do Tomar da "
            "Cotinguiba."
        ),

        "observacao": (
            "Figura histórica ligada à formação "
            "religiosa e administrativa de Nossa "
            "Senhora do Socorro. Não era morador "
            "de Piabeta."
        )
    }

]


# ==========================================================
# MORADORES ANTIGOS
# ==========================================================

MORADORES_ANTIGOS = [

    {
        "nome": "Morador antigo 1",

        "descricao": (
            "Espaço reservado para registrar a história "
            "de um morador antigo de Piabeta."
        ),

        "observacao": (
            "O nome deve ser preenchido após entrevista "
            "ou consulta a uma fonte local confiável."
        )
    },

    {
        "nome": "Morador antigo 2",

        "descricao": (
            "Espaço reservado para registrar a história "
            "de outro morador antigo de Piabeta."
        ),

        "observacao": (
            "O nome deve ser preenchido após entrevista "
            "ou consulta a uma fonte local confiável."
        )
    }

]


# ==========================================================
# IA
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
"""

        instrucoes = """
Você é o Assistente Cultural do projeto
Mapa Cultural.

Responda em português do Brasil.

Não invente informações históricas.

Use somente informações fornecidas
ou informações gerais que sejam seguras.

Se não houver dados suficientes,
diga claramente que não há informação
disponível.
"""

        resposta = client.responses.create(

            model="gpt-5",

            instructions=instrucoes,

            input=f"""
DADOS DO LOCAL:

{contexto}

PERGUNTA:

{pergunta}
"""
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
    "Explore **comércio, gastronomia, cultura, "
    "história e memória de Nossa Senhora do Socorro**."
)


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title(
    "🎛️ Explorar"
)


if locais:

    categorias = sorted(
        list(
            set(
                local["categoria"]
                for local in locais
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
            "Ex: restaurante, Piabeta, "
            "história, loja..."
        ),

        label_visibility="collapsed"

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
        "🏛️ História",
        len(
            [
                x for x in resultados
                if x["categoria"]
                in [
                    "História",
                    "Memória Local"
                ]
            ]
        )
    )


# ==========================================================
# MAPA
# ==========================================================

st.subheader(
    "📍 Mapa Cultural"
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

    "História": "purple",

    "Memória Local": "green",

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


    if categoria == "História":

        icone = "info-sign"

    elif categoria == "Memória Local":

        icone = "home"

    else:

        icone = "shopping-cart"


    folium.Marker(

        location=[
            local["latitude"],
            local["longitude"]
        ],

        tooltip=local["nome"],

        popup=folium.Popup(
            popup,
            max_width=350
