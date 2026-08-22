import streamlit as st
import folium
from streamlit_folium import st_folium

import sqlite3
import pandas as pd
import plotly.express as px

from rapidfuzz import fuzz

from datetime import datetime
import re
import os


# =====================================
# CONFIGURAÇÃO STREAMLIT
# =====================================

st.set_page_config(
    page_title="Mapa Cultural Socorro",
    page_icon="🗺️",
    layout="wide"
)


# =====================================
# BANCO DE DADOS
# =====================================

DB_NAME = "mapa_cultural.db"


def conectar():
    return sqlite3.connect(DB_NAME)


def criar_banco():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locais (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nome TEXT,
        categoria TEXT,
        descricao TEXT,
        historia TEXT,

        endereco TEXT,
        telefone TEXT,
        whatsapp TEXT,

        dias_funcionamento TEXT,
        horario TEXT,

        latitude REAL,
        longitude REAL,

        verificado TEXT,
        data_cadastro TEXT

    )
    """)

    conn.commit()
    conn.close()


criar_banco()


# =====================================
# INSERIR LOCAL
# =====================================

def inserir_local(
        nome,
        categoria,
        descricao,
        historia,
        endereco,
        telefone,
        whatsapp,
        dias_funcionamento,
        horario,
        latitude,
        longitude,
        verificado
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""

    INSERT INTO locais (

        nome,
        categoria,
        descricao,
        historia,

        endereco,
        telefone,
        whatsapp,

        dias_funcionamento,
        horario,

        latitude,
        longitude,

        verificado,
        data_cadastro

    )

    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        nome,
        categoria,
        descricao,
        historia,

        endereco,
        telefone,
        whatsapp,

        dias_funcionamento,
        horario,

        latitude,
        longitude,

        verificado,
        datetime.now().strftime("%d/%m/%Y %H:%M")

    ))

    conn.commit()
    conn.close()


# =====================================
# CARREGAR DADOS
# =====================================

def carregar_locais():

    conn = conectar()

    df = pd.read_sql(
        "SELECT * FROM locais",
        conn
    )

    conn.close()

    return df


# =====================================
# BUSCA INTELIGENTE
# =====================================

def buscar_local(termo, df):

    resultados = []

    termo = termo.lower()

    for _, row in df.iterrows():

        nome = str(row["nome"]).lower()

        score = fuzz.ratio(
            termo,
            nome
        )

        if score >= 60:
            resultados.append(row)

    if len(resultados) == 0:
        return pd.DataFrame()

    return pd.DataFrame(resultados)


# =====================================
# GERAR KML
# =====================================

def gerar_kml(df):

    kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
"""

    for _, row in df.iterrows():

        kml += f"""
<Placemark>
    <name>{row['nome']}</name>

    <description>
        {row['descricao']}
    </description>

    <Point>
        <coordinates>
            {row['longitude']},{row['latitude']},0
        </coordinates>
    </Point>

</Placemark>
"""

    kml += """
</Document>
</kml>
"""

    return kml


# =====================================
# STATUS ABERTO AGORA
# =====================================

def verificar_status(horario):

    try:

        numeros = re.findall(
            r"(\d{1,2}):(\d{2})",
            horario
        )

        if len(numeros) < 2:
            return "⚪ Não informado"

        abertura = datetime.strptime(
            f"{numeros[0][0]}:{numeros[0][1]}",
            "%H:%M"
        ).time()

        fechamento = datetime.strptime(
            f"{numeros[1][0]}:{numeros[1][1]}",
            "%H:%M"
        ).time()

        agora = datetime.now().time()

        if abertura <= agora <= fechamento:
            return "🟢 Aberto"

        return "🔴 Fechado"

    except:
        return "⚪ Não informado"


# =====================================
# MENU LATERAL
# =====================================

st.sidebar.title("🗺️ Mapa Cultural")

menu = st.sidebar.radio(

    "Navegação",

    [
        "Mapa",
        "Cadastrar Local",
        "Dashboard",
        "Exportar"
    ]
)
# =====================================
# TELA MAPA
# =====================================

if menu == "Mapa":

    st.title("🗺️ Mapa Cultural Socorro")

    df = carregar_locais()

    busca = st.text_input(
        "🔍 Buscar local"
    )

    if busca:

        resultado = buscar_local(
            busca,
            df
        )

        if len(resultado) > 0:

            st.success(
                f"{len(resultado)} resultado(s) encontrado(s)"
            )

            df = resultado

        else:

            st.warning(
                "Nenhum local encontrado."
            )

    if len(df) == 0:

        st.info(
            "Nenhum local cadastrado."
        )

    else:

        media_lat = df["latitude"].mean()
        media_lon = df["longitude"].mean()

        mapa = folium.Map(
            location=[media_lat, media_lon],
            zoom_start=13
        )

        for _, row in df.iterrows():

            status = verificar_status(
                str(row["horario"])
            )

            popup = f"""
            <b>{row['nome']}</b><br>

            Categoria: {row['categoria']}<br>

            {row['descricao']}<br><br>

            📍 {row['endereco']}<br>

            📞 {row['telefone']}<br>

            📱 {row['whatsapp']}<br>

            🕒 {row['horario']}<br>

            {status}
            """

            folium.Marker(

                [
                    row["latitude"],
                    row["longitude"]
                ],

                popup=folium.Popup(
                    popup,
                    max_width=350
                ),

                tooltip=row["nome"]

            ).add_to(mapa)

        st_folium(
            mapa,
            width=1200,
            height=600
        )

        st.subheader(
            "📋 Locais cadastrados"
        )

        exibir = df.copy()

        colunas = [

            "nome",
            "categoria",
            "endereco",
            "horario",
            "verificado"

        ]

        st.dataframe(
            exibir[colunas],
            use_container_width=True
        )


# =====================================
# CADASTRAR LOCAL
# =====================================

elif menu == "Cadastrar Local":

    st.title("➕ Cadastrar Local")

    with st.form("cadastro_local"):

        nome = st.text_input(
            "Nome do Local"
        )

        categoria = st.selectbox(

            "Categoria",

            [

                "Museu",
                "Teatro",
                "Biblioteca",
                "Praça",
                "Igreja",
                "Patrimônio Histórico",
                "Centro Cultural",
                "Turismo",
                "Outro"

            ]

        )

        descricao = st.text_area(
            "Descrição"
        )

        historia = st.text_area(
            "História Cultural"
        )

        endereco = st.text_input(
            "Endereço"
        )

        telefone = st.text_input(
            "Telefone"
        )

        whatsapp = st.text_input(
            "WhatsApp"
        )

        dias_funcionamento = st.text_input(
            "Dias de funcionamento"
        )

        horario = st.text_input(
            "Horário (Ex: 08:00 às 18:00)"
        )

        col1, col2 = st.columns(2)

        with col1:

            latitude = st.number_input(
                "Latitude",
                format="%.6f"
            )

        with col2:

            longitude = st.number_input(
                "Longitude",
                format="%.6f"
            )

        verificado = st.selectbox(

            "Verificado",

            [
                "Sim",
                "Não"
            ]

        )

        salvar = st.form_submit_button(
            "💾 Salvar Local"
        )

    if salvar:

        if nome == "":

            st.error(
                "Informe o nome do local."
            )

        else:

            inserir_local(

                nome,
                categoria,
                descricao,
                historia,

                endereco,
                telefone,
                whatsapp,

                dias_funcionamento,
                horario,

                latitude,
                longitude,

                verificado

            )

            st.success(
                "Local cadastrado com sucesso."
            )

            st.rerun()
            # =====================================
# DASHBOARD
# =====================================

elif menu == "Dashboard":

    st.title("📊 Dashboard Cultural")

    df = carregar_locais()

    if len(df) == 0:

        st.warning(
            "Nenhum local cadastrado."
        )

    else:

        total_locais = len(df)

        total_verificados = len(
            df[df["verificado"] == "Sim"]
        )

        total_categorias = (
            df["categoria"]
            .nunique()
        )

        total_historias = len(
            df[
                df["historia"]
                .fillna("")
                .str.strip() != ""
            ]
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "📍 Locais",
                total_locais
            )

        with col2:
            st.metric(
                "✅ Verificados",
                total_verificados
            )

        with col3:
            st.metric(
                "🏷️ Categorias",
                total_categorias
            )

        with col4:
            st.metric(
                "📚 Histórias",
                total_historias
            )

        st.divider()

        categoria_df = (
            df["categoria"]
            .value_counts()
            .reset_index()
        )

        categoria_df.columns = [
            "Categoria",
            "Quantidade"
        ]

        fig_bar = px.bar(
            categoria_df,
            x="Categoria",
            y="Quantidade",
            title="Locais por Categoria"
        )

        st.plotly_chart(
            fig_bar,
            use_container_width=True
        )

        fig_pizza = px.pie(
            categoria_df,
            names="Categoria",
            values="Quantidade",
            title="Distribuição das Categorias"
        )

        st.plotly_chart(
            fig_pizza,
            use_container_width=True
        )

        st.subheader(
            "🏆 Ranking de Categorias"
        )

        st.dataframe(
            categoria_df,
            use_container_width=True
        )

        st.subheader(
            "📋 Base Completa"
        )

        st.dataframe(
            df,
            use_container_width=True
        )


# =====================================
# EXPORTAR
# =====================================

elif menu == "Exportar":

    st.title("📤 Exportação")

    df = carregar_locais()

    if len(df) == 0:

        st.warning(
            "Nenhum local cadastrado."
        )

    else:

        st.subheader(
            "📋 Prévia dos Dados"
        )

        st.dataframe(
            df,
            use_container_width=True
        )

        st.divider()

        categorias = sorted(
            df["categoria"]
            .dropna()
            .unique()
            .tolist()
        )

        filtro = st.selectbox(
            "Filtrar Categoria",
            ["Todas"] + categorias
        )

        if filtro == "Todas":

            df_export = df

        else:

            df_export = df[
                df["categoria"] == filtro
            ]

        st.info(
            f"{len(df_export)} registro(s) selecionado(s)."
        )

        st.divider()

        # ==========================
        # CSV
        # ==========================

        csv = df_export.to_csv(
            index=False,
            encoding="utf-8-sig"
        )

        st.download_button(

            label="⬇️ Baixar CSV",

            data=csv,

            file_name="mapa_cultural.csv",

            mime="text/csv"

        )

        # ==========================
        # KML
        # ==========================

        kml = gerar_kml(
            df_export
        )

        st.download_button(

            label="🌍 Baixar KML",

            data=kml,

            file_name="mapa_cultural.kml",

            mime="application/vnd.google-earth.kml+xml"

        )

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "📍 Registros",
                len(df_export)
            )

        with col2:

            st.metric(
                "🏷️ Categorias",
                df_export["categoria"].nunique()
            )

        with col3:

            st.metric(
                "✅ Verificados",
                len(
                    df_export[
                        df_export["verificado"] == "Sim"
                    ]
                )
            )

        st.success(
            "Exportação pronta para Excel, Google Sheets, Google Earth e My Maps."
        )
