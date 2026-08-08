import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px

# =========================================================
# CONFIGURAÇÃO
# =========================================================

st.set_page_config(
    page_title="Mapa Cultural",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# ESTILO
# =========================================================

st.markdown("""
<style>

.main {
    background-color: #f5f7fb;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.titulo {
    font-size: 42px;
    font-weight: 800;
    color: #173b57;
    margin-bottom: 0;
}

.subtitulo {
    color: #667085;
    font-size: 18px;
    margin-bottom: 25px;
}

.card {
    background: white;
    padding: 18px;
    border-radius: 16px;
    border: 1px solid #e8edf3;
    margin-bottom: 12px;
    box-shadow: 0px 3px 12px rgba(0,0,0,0.05);
}

.card h3 {
    margin-top: 0;
    color: #173b57;
}

.tag {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 20px;
    background: #e8f3ff;
    color: #1769aa;
    font-size: 13px;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# TÍTULO
# =========================================================

st.markdown(
    '<div class="titulo">🗺️ Mapa Cultural</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitulo">'
    'Descubra lugares, histórias e manifestações culturais de '
    'Nossa Senhora do Socorro - Sergipe.'
    '</div>',
    unsafe_allow_html=True
)

# =========================================================
# DADOS CULTURAIS
# =========================================================

locais = [
    {
        "nome": "Centro de Nossa Senhora do Socorro",
        "categoria": "História",
        "emoji": "🏛️",
        "lat": -10.855,
        "lon": -37.125,
        "descricao": "Região central do município e referência para conhecer a história local.",
        "palavras": ["história", "centro", "cidade", "socorro"]
    },
    {
        "nome": "Gastronomia Regional",
        "categoria": "Gastronomia",
        "emoji": "🍲",
        "lat": -10.850,
        "lon": -37.115,
        "descricao": "Espaço relacionado à culinária e aos sabores tradicionais da região.",
        "palavras": ["comida", "gastronomia", "comida típica", "culinária", "comer"]
    },
    {
        "nome": "Festas Tradicionais",
        "categoria": "Festas",
        "emoji": "🎭",
        "lat": -10.865,
        "lon": -37.135,
        "descricao": "Manifestações e festas tradicionais da comunidade.",
        "palavras": ["festa", "festas", "são joão", "junina", "quadrilha"]
    },
    {
        "nome": "Música e Forró",
        "categoria": "Música",
        "emoji": "🎵",
        "lat": -10.845,
        "lon": -37.130,
        "descricao": "Cultura musical regional, incluindo o forró e outras manifestações.",
        "palavras": ["música", "musica", "forró", "forro", "dança"]
    },
    {
        "nome": "Artesanato Regional",
        "categoria": "Artesanato",
        "emoji": "🧵",
        "lat": -10.860,
        "lon": -37.110,
        "descricao": "Produção artesanal e manifestações da cultura material.",
        "palavras": ["artesanato", "artesão", "artesao", "arte", "cultura"]
    }
]

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🎛️ Filtros")

categorias = sorted(
    list(set(local["categoria"] for local in locais))
)

categorias_selecionadas = st.sidebar.multiselect(
    "Categorias",
    categorias,
    default=categorias
)

st.sidebar.markdown("---")

st.sidebar.info(
    "💡 Pesquise por uma palavra como "
    "**comida**, **forró**, **festa**, "
    "**história** ou **artesanato**."
)

# =========================================================
# PESQUISA
# =========================================================

st.subheader("🔎 O que você quer descobrir?")

with st.form("form_pesquisa"):

    col1, col2 = st.columns([5, 1])

    with col1:
        pesquisa = st.text_input(
            "Pesquisa",
            placeholder="Ex: comida típica, forró, festas...",
            label_visibility="collapsed"
        )

    with col2:
        buscar = st.form_submit_button(
            "🔍 Buscar",
            use_container_width=True
        )

# =========================================================
# FILTRAR RESULTADOS
# =========================================================

if buscar:

    termo = pesquisa.lower().strip()

    if termo:

        resultados = []

        for local in locais:

            if local["categoria"] not in categorias_selecionadas:
                continue

            texto = (
                local["nome"] + " " +
                local["categoria"] + " " +
                local["descricao"] + " " +
                " ".join(local["palavras"])
            ).lower()

            if termo in texto:
                resultados.append(local)

    else:
        resultados = [
            local for local in locais
            if local["categoria"] in categorias_selecionadas
        ]

else:

    resultados = [
        local for local in locais
        if local["categoria"] in categorias_selecionadas
    ]

# =========================================================
# MÉTRICAS
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "📍 Locais encontrados",
        len(resultados)
    )

with col2:
    st.metric(
        "🏛️ Categorias",
        len(set(l["categoria"] for l in resultados))
        if resultados else 0
    )

with col3:
    st.metric(
        "🌎 Região",
        "Socorro - SE"
    )

# =========================================================
# MAPA
# =========================================================

st.subheader("📍 Explore o mapa")

if resultados:

    # Centraliza no primeiro resultado
    centro = [
        resultados[0]["lat"],
        resultados[0]["lon"]
    ]

else:

    centro = [-10.855, -37.125]

mapa = folium.Map(
    location=centro,
    zoom_start=14,
    control_scale=True,
    tiles="OpenStreetMap"
)

# Cores
cores = {
    "História": "blue",
    "Gastronomia": "green",
    "Festas": "red",
    "Música": "purple",
    "Artesanato": "orange"
}

for local in resultados:

    popup_html = f"""
    <div style="width:240px">
        <h3>{local['emoji']} {local['nome']}</h3>
        <b>{local['categoria']}</b>
        <p>{local['descricao']}</p>
    </div>
    """

    folium.Marker(
        location=[
            local["lat"],
            local["lon"]
        ],
        tooltip=local["nome"],
        popup=folium.Popup(
            popup_html,
            max_width=300
        ),
        icon=folium.Icon(
            color=cores.get(
                local["categoria"],
                "blue"
            ),
            icon="info-sign"
        )
    ).add_to(mapa)

# =========================================================
# MOSTRAR MAPA
# =========================================================

st_folium(
    mapa,
    width=None,
    height=550,
    returned_objects=[]
)

# =========================================================
# RESULTADOS
# =========================================================

st.subheader("📚 Resultados culturais")

if resultados:

    for local in resultados:

        st.markdown(
            f"""
            <div class="card">
                <h3>
                    {local['emoji']} {local['nome']}
                </h3>

                <span class="tag">
                    {local['categoria']}
                </span>

                <p>
                    {local['descricao']}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

else:

    st.warning(
        "😕 Não encontrei resultados para essa pesquisa."
    )

    st.write(
        "Experimente pesquisar: comida, forró, festa, "
        "história ou artesanato."
    )

# =========================================================
# GRÁFICO
# =========================================================

st.subheader("📊 Cultura encontrada")

if resultados:

    contagem = {}

    for local in resultados:

        categoria = local["categoria"]

        contagem[categoria] = (
            contagem.get(categoria, 0) + 1
        )

    dados_grafico = {
        "Categoria": list(contagem.keys()),
        "Locais": list(contagem.values())
    }

    grafico = px.bar(
        dados_grafico,
        x="Categoria",
        y="Locais",
        color="Categoria",
        title="Resultados por categoria"
    )

    grafico.update_layout(
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white"
    )

    st.plotly_chart(
        grafico,
        use_container_width=True
    )
