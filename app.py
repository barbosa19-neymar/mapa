import streamlit as st
import folium
import sqlite3
import os
import re

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
# CORES E ESTILO
# ==========================================================

st.markdown("""
<style>

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

.stApp {
    background: #f5f7fb;
}

.block-container {
    padding-top: 1.5rem;
    max-width: 1500px;
}

.titulo {
    font-size: 42px;
    font-weight: 800;
    color: #173b57;
}

.subtitulo {
    color: #667085;
    font-size: 17px;
    margin-bottom: 25px;
}

.card {
    background: white;
    border-radius: 18px;
    padding: 20px;
    margin-bottom: 15px;
    border: 1px solid #e7ebf0;
    box-shadow: 0 4px 15px rgba(0,0,0,.05);
}

.card:hover {
    box-shadow: 0 7px 25px rgba(0,0,0,.09);
}

.badge {
    display: inline-block;
    background: #e9f4ff;
    color: #1769aa;
    padding: 5px 11px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
}

.info {
    color: #667085;
    font-size: 14px;
}

.metric-card {
    background: white;
    border-radius: 15px;
    padding: 15px;
    border: 1px solid #e7ebf0;
}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# BANCO DE DADOS
# ==========================================================

DB = "mapa_cultural.db"


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
# DADOS INICIAIS
# ==========================================================

def inserir_exemplos():

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM locais"
    )

    quantidade = cursor.fetchone()[0]

    if quantidade == 0:

        exemplos = [

            (
                "Centro Histórico",
                "Cultura",
                "Área de interesse histórico e cultural.",
                "Nossa Senhora do Socorro - SE",
                "",
                "",
                "",
                "",
                -10.855,
                -37.125,
                4.5
            ),

            (
                "Restaurante Regional",
                "Restaurante",
                "Exemplo de estabelecimento de gastronomia regional.",
                "Nossa Senhora do Socorro - SE",
                "",
                "11:00 - 22:00",
                "",
                "",
                -10.850,
                -37.115,
                4.3
            ),

            (
                "Comércio Local",
                "Loja",
                "Exemplo de comércio local.",
                "Nossa Senhora do Socorro - SE",
                "",
                "08:00 - 18:00",
                "",
                "",
                -10.860,
                -37.130,
                4.2
            ),

            (
                "Espaço Cultural",
                "Cultura",
                "Local para manifestações culturais.",
                "Nossa Senhora do Socorro - SE",
                "",
                "",
                "",
                "",
                -10.865,
                -37.135,
                4.7
            )

        ]

        for item in exemplos:

            cursor.execute("""
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
            """, (

                item[0],
                item[1],
                item[2],
                item[3],
                item[4],
                item[5],
                item[6],
                item[7],
                item[8],
                item[9],
                item[10],
                datetime.now().isoformat()

            ))

    conn.commit()

    conn.close()


inserir_exemplos()


# ==========================================================
# CONSULTAR LOCAIS
# ==========================================================

def buscar_locais():

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute("""
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
            avaliacao

        FROM locais

        ORDER BY nome
    """)

    dados = cursor.fetchall()

    conn.close()

    return dados


locais = buscar_locais()


# ==========================================================
# CABEÇALHO
# ==========================================================

st.markdown(
    '<div class="titulo">🗺️ Mapa Cultural</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitulo">'
    'Explore lugares, comércio, gastronomia e cultura da sua região.'
    '</div>',
    unsafe_allow_html=True
)


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title("🎛️ Explorar")

categorias = sorted(
    list(set(local[2] for local in locais))
)

categorias_selecionadas = st.sidebar.multiselect(
    "Categorias",
    categorias,
    default=categorias
)

st.sidebar.markdown("---")

st.sidebar.markdown("### 📍 Categorias")

st.sidebar.write("🏛️ Cultura")
st.sidebar.write("🍴 Restaurante")
st.sidebar.write("🛍️ Loja")
st.sidebar.write("🛒 Mercado")
st.sidebar.write("🏨 Hotel")
st.sidebar.write("🎭 Eventos")
st.sidebar.write("📸 Turismo")


# ==========================================================
# PESQUISA
# ==========================================================

st.subheader("🔎 Pesquisar")

with st.form("pesquisa_form"):

    col1, col2 = st.columns([6, 1])

    with col1:

        pesquisa = st.text_input(
            "Pesquisa",
            placeholder="Ex: restaurante, loja, cultura...",
            label_visibility="collapsed"
        )

    with col2:

        pesquisar = st.form_submit_button(
            "🔍 Buscar",
            use_container_width=True
        )


# ==========================================================
# FILTRO
# ==========================================================

resultados = []

termo = pesquisa.lower().strip()

for local in locais:

    categoria = local[2]

    if categoria not in categorias_selecionadas:
        continue

    texto = " ".join([
        str(local[1]),
        str(local[2]),
        str(local[3]),
        str(local[4])
    ]).lower()

    if termo == "" or termo in texto:

        resultados.append(local)


# ==========================================================
# REGISTRAR PESQUISA
# ==========================================================

if pesquisar and termo:

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pesquisas
        (termo, data)

        VALUES (?, ?)
    """, (
        termo,
        datetime.now().isoformat()
    ))

    conn.commit()

    conn.close()


# ==========================================================
# MÉTRICAS
# ==========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "📍 Locais",
        len(resultados)
    )

with col2:

    st.metric(
        "🏷️ Categorias",
        len(set(x[2] for x in resultados))
    )

with col3:

    st.metric(
        "⭐ Média",
        round(
            sum(x[10] for x in resultados) /
            len(resultados),
            1
        ) if resultados else 0
    )

with col4:

    st.metric(
        "🔎 Resultado",
        "Encontrado" if resultados else "Nenhum"
    )


# ==========================================================
# MAPA
# ==========================================================

st.subheader("📍 Mapa")

if resultados:

    centro_lat = resultados[0][9]
    centro_lon = resultados[0][10]

else:

    centro_lat = -10.855
    centro_lon = -37.125


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

    "Eventos": "pink",

    "Turismo": "cadetblue"

}


# ==========================================================
# MARCADORES
# ==========================================================

for local in resultados:

    id_local = local[0]

    nome = local[1]

    categoria = local[2]

    descricao = local[3]

    endereco = local[4]

    telefone = local[5]

    horario = local[6]

    site = local[7]

    imagem = local[8]

    latitude = local[9]

    longitude = local[10]

    avaliacao = local[11]


    popup = f"""

    <div style="
        width:280px;
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
            ⭐ <b>{avaliacao}</b>
        </p>

        <p>
            📍 {endereco}
        </p>

        <p>
            🕐 {horario}
        </p>

    </div>

    """


    folium.Marker(

        location=[
            latitude,
            longitude
        ],

        tooltip=nome,

        popup=folium.Popup(
            popup,
            max_width=350
        ),

        icon=folium.Icon(

            color=cores.get(
                categoria,
                "blue"
            ),

            icon="info-sign"

        )

    ).add_to(mapa)


st_folium(
    mapa,
    width=None,
    height=600,
    returned_objects=[]
)


# ==========================================================
# RESULTADOS
# ==========================================================

st.subheader("📚 Locais encontrados")


if resultados:

    for local in resultados:

        id_local = local[0]

        nome = local[1]

        categoria = local[2]

        descricao = local[3]

        endereco = local[4]

        telefone = local[5]

        horario = local[6]

        site = local[7]

        imagem = local[8]

        avaliacao = local[11]


        col1, col2 = st.columns(
            [1, 3]
        )


        with col1:

            if imagem and os.path.exists(imagem):

                st.image(
                    imagem,
                    use_container_width=True
                )

            else:

                st.markdown(
                    """
                    <div style="
                        height:160px;
                        background:#eaf0f6;
                        border-radius:15px;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        font-size:50px;
                    ">
                    📍
                    </div>
                    """,
                    unsafe_allow_html=True
                )


        with col2:

            st.markdown(
                f"""
                <div class="card">

                    <h2>
                        {nome}
                    </h2>

                    <span class="badge">
                        {categoria}
                    </span>

                    <p>
                        {descricao}
                    </p>

                    <p class="info">
                        📍 {endereco}
                    </p>

                    <p class="info">
                        ⭐ {avaliacao}
                    </p>

                    <p class="info">
                        🕐 {horario}
                    </p>

                    <p class="info">
                        📞 {telefone}
                    </p>

                </div>
                """,
                unsafe_allow_html=True
            )


# ==========================================================
# GRÁFICOS
# ==========================================================

st.markdown("---")

st.subheader("📊 Dados do mapa")


contagem = {}

for local in resultados:

    categoria = local[2]

    contagem[categoria] = (
        contagem.get(categoria, 0) + 1
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
# CADASTRAR LOCAL
# ==========================================================

st.markdown("---")

st.subheader("➕ Adicionar local")


with st.expander(
    "Cadastrar um novo local"
):

    with st.form("novo_local"):

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
                "Turismo"
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
            "Caminho da imagem"
        )

        col1, col2 = st.columns(2)

        with col1:

            latitude = st.number_input(
                "Latitude",
                value=-10.855,
                format="%.6f"
            )

        with col2:

            longitude = st.number_input(
                "Longitude",
                value=-37.125,
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

                cursor.execute("""

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

                """, (

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

                ))

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
    "🗺️ Mapa Cultural • Projeto desenvolvido em Python + Streamlit"
)
