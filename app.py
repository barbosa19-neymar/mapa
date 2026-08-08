import streamlit as st
import folium

from streamlit_folium import st_folium
from folium.plugins import Fullscreen, Geocoder

st.set_page_config(
    page_title="Mapa Cultural",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Mapa Cultural")
st.write("Explore os pontos culturais de Nossa Senhora do Socorro - Sergipe")

# -----------------------------
# DADOS DOS LOCAIS
# -----------------------------

locais = [
    {
        "nome": "Centro de Nossa Senhora do Socorro",
        "lat": -10.855,
        "lon": -37.125,
        "categoria": "História",
        "descricao": "Centro do município."
    },
    {
        "nome": "Ponto Cultural 1",
        "lat": -10.850,
        "lon": -37.115,
        "categoria": "Gastronomia",
        "descricao": "Local relacionado à gastronomia regional."
    },
    {
        "nome": "Ponto Cultural 2",
        "lat": -10.865,
        "lon": -37.135,
        "categoria": "Festas",
        "descricao": "Local relacionado às festas tradicionais."
    }
]

# -----------------------------
# FILTROS
# -----------------------------

st.sidebar.header("🎛️ Filtros")

mostrar_historia = st.sidebar.checkbox(
    "🏛️ História",
    value=True
)

mostrar_gastronomia = st.sidebar.checkbox(
    "🍲 Gastronomia",
    value=True
)

mostrar_festas = st.sidebar.checkbox(
    "🎭 Festas",
    value=True
)

# -----------------------------
# MAPA
# -----------------------------

mapa = folium.Map(
    location=[-10.855, -37.125],
    zoom_start=13,
    control_scale=True
)

# Tela cheia
Fullscreen().add_to(mapa)

# Pesquisa de lugares
Geocoder().add_to(mapa)

# Grupos de categorias
grupo_historia = folium.FeatureGroup(
    name="🏛️ História"
)

grupo_gastronomia = folium.FeatureGroup(
    name="🍲 Gastronomia"
)

grupo_festas = folium.FeatureGroup(
    name="🎭 Festas"
)

# -----------------------------
# MARCADORES
# -----------------------------

for local in locais:

    popup = f"""
    <b>{local['nome']}</b><br>
    Categoria: {local['categoria']}<br>
    <br>
    {local['descricao']}
    """

    marcador = folium.Marker(
        location=[
            local["lat"],
            local["lon"]
        ],
        popup=folium.Popup(
            popup,
            max_width=300
        ),
        tooltip=local["nome"]
    )

    if local["categoria"] == "História":
        if mostrar_historia:
            marcador.add_to(grupo_historia)

    elif local["categoria"] == "Gastronomia":
        if mostrar_gastronomia:
            marcador.add_to(grupo_gastronomia)

    elif local["categoria"] == "Festas":
        if mostrar_festas:
            marcador.add_to(grupo_festas)

# Adiciona os grupos
grupo_historia.add_to(mapa)
grupo_gastronomia.add_to(mapa)
grupo_festas.add_to(mapa)

# Controle de camadas
folium.LayerControl().add_to(mapa)

# -----------------------------
# MOSTRAR MAPA
# -----------------------------

resultado = st_folium(
    mapa,
    width=None,
    height=600,
    returned_objects=[
        "last_clicked"
    ]
)

# -----------------------------
# CLIQUE NO MAPA
# -----------------------------

if resultado["last_clicked"]:

    latitude = resultado["last_clicked"]["lat"]
    longitude = resultado["last_clicked"]["lng"]

    st.subheader("📍 Local selecionado")

    st.write(
        f"Latitude: `{latitude:.6f}`"
    )

    st.write(
        f"Longitude: `{longitude:.6f}`"
    )
