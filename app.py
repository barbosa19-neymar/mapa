import streamlit as st
import folium
from streamlit_folium import st_folium

st.title("🗺️ Mapa Cultural")

st.write("Nossa Senhora do Socorro - Sergipe")

mapa = folium.Map(
    location=[-10.855, -37.125],
    zoom_start=13
)

folium.Marker(
    [-10.855, -37.125],
    popup="Nossa Senhora do Socorro",
    tooltip="Clique aqui"
).add_to(mapa)

st_folium(mapa, width=1000, height=600)
