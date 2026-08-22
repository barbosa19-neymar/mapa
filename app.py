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
# ==========================================
# CONFIGURAÇÃO
# ==========================================

st.set_page_config(
    page_title="Mapa Cultural Socorro",
    page_icon="🗺️",
    layout="wide"
)

DB_PATH = "database/mapa_socorro.db"

# ==========================================
# BANCO DE DADOS
# ==========================================

def conectar_db():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def criar_tabela():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        categoria TEXT,
        descricao TEXT,
        endereco TEXT,
        telefone TEXT,
        whatsapp TEXT,
        horario TEXT,
        dias_funcionamento TEXT,
        historia_cultural TEXT,
        latitude REAL,
        longitude REAL,
        status_verificado INTEGER DEFAULT 0,
        data_cadastro TEXT
    )
    """)

    conn.commit()
    conn.close()

criar_tabela()

# ==========================================
# FUNÇÕES BANCO
# ==========================================

def adicionar_local(
    nome,
    categoria,
    descricao,
    endereco,
    telefone,
    whatsapp,
    horario,
    dias,
    historia,
    latitude,
    longitude
):

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO locais (
        nome,
        categoria,
        descricao,
        endereco,
        telefone,
        whatsapp,
        horario,
        dias_funcionamento,
        historia_cultural,
        latitude,
        longitude,
        data_cadastro
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nome,
        categoria,
        descricao,
        endereco,
        telefone,
        whatsapp,
        horario,
        dias,
        historia,
        latitude,
        longitude,
        datetime.now().strftime("%d/%m/%Y %H:%M")
    ))

    conn.commit()
    conn.close()

def carregar_locais():
    conn = conectar_db()

    df = pd.read_sql_query(
        "SELECT * FROM locais",
        conn
    )

    conn.close()

    return df

# ==========================================
# BUSCA INTELIGENTE
# ==========================================

def buscar_locais(df, termo):

    if not termo:
        return df

    resultados = []

    termo = termo.lower()

    for _, row in df.iterrows():

        texto = f"""
        {row['nome']}
        {row['categoria']}
        {row['descricao']}
        {row['endereco']}
        """

        score = fuzz.partial_ratio(
            termo,
            texto.lower()
        )

        if score >= 60:
            resultados.append(row)

    return pd.DataFrame(resultados)

# ==========================================
# MENU
# ==========================================

st.sidebar.title("🗺️ Mapa Cultural Socorro")

menu = st.sidebar.radio(
    "Menu",
    [
        "Mapa",
        "Cadastrar Local",
        "Dashboard",
        "Exportar"
    ]
)

# ==========================================
# MAPA
# ==========================================

if menu == "Mapa":

    st.title("🗺️ Mapa Cultural de Nossa Senhora do Socorro")

    pesquisa = st.text_input(
        "Pesquisar local"
    )

    df = carregar_locais()

    if pesquisa:
        df = buscar_locais(df, pesquisa)

    mapa = folium.Map(
        location=[-10.855, -37.126],
        zoom_start=12
    )

    for _, local in df.iterrows():

        popup = f"""
        <b>{local['nome']}</b><br>
        Categoria: {local['categoria']}<br>
        Horário: {local['horario']}<br>
        {local['descricao']}
        """

        folium.Marker(
            [local['latitude'], local['longitude']],
            popup=popup
        ).add_to(mapa)

    st_folium(
        mapa,
        width=None,
        height=700
    )
    # ==========================================
# CADASTRAR LOCAL
# ==========================================

elif menu == "Cadastrar Local":

    st.title("➕ Cadastrar Novo Local")

    with st.form("form_cadastro"):

        nome = st.text_input(
            "Nome do Local *"
        )

        categoria = st.selectbox(
            "Categoria *",
            [
                "Praça",
                "Igreja",
                "Escola",
                "Hospital",
                "UBS",
                "Farmácia",
                "Comércio",
                "Restaurante",
                "Turismo",
                "Cultura",
                "Transporte",
                "Outro"
            ]
        )

        descricao = st.text_area(
            "Descrição"
        )

        historia_cultural = st.text_area(
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
            "Dias de Funcionamento",
            placeholder="Ex: Segunda a Sexta"
        )

        horario = st.text_input(
            "Horário",
            placeholder="Ex: 08:00 às 18:00"
        )

        col1, col2 = st.columns(2)

        with col1:
            latitude = st.number_input(
                "Latitude",
                value=-10.8550,
                format="%.6f"
            )

        with col2:
            longitude = st.number_input(
                "Longitude",
                value=-37.1260,
                format="%.6f"
            )

        verificar = st.checkbox(
            "Local verificado"
        )

        enviar = st.form_submit_button(
            "💾 Salvar Local"
        )

    if enviar:

        if not nome:

            st.error(
                "Informe o nome do local."
            )

        else:

            conn = conectar_db()
            cursor = conn.cursor()

            cursor.execute("""
            INSERT INTO locais (
                nome,
                categoria,
                descricao,
                endereco,
                telefone,
                whatsapp,
                horario,
                dias_funcionamento,
                historia_cultural,
                latitude,
                longitude,
                status_verificado,
                data_cadastro
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nome,
                categoria,
                descricao,
                endereco,
                telefone,
                whatsapp,
                horario,
                dias_funcionamento,
                historia_cultural,
                latitude,
                longitude,
                1 if verificar else 0,
                datetime.now().strftime(
                    "%d/%m/%Y %H:%M"
                )
            ))

            conn.commit()
            conn.close()

            st.success(
                "✅ Local cadastrado com sucesso!"
            )

            st.balloons()

    st.divider()

    st.subheader("📋 Locais Cadastrados")

    df = carregar_locais()

    if not df.empty:

        st.dataframe(
            df,
            use_container_width=True
        )

    else:

        st.info(
            "Nenhum local cadastrado."
        )
        # ==========================================
        # DASHBOARD
        # ==========================================

        elif menu == "Dashboard":

        st.title("📊 Dashboard Cultural")

        df = carregar_locais()

        if df.empty:

            st.warning(
                "Nenhum local cadastrado."
            )

        else:

            total_locais = len(df)

            total_verificados = len(
                df[df["status_verificado"] == 1]
            )

            total_categorias = (
                df["categoria"]
                .nunique()
            )

            total_com_historia = len(
                df[
                    df["historia_cultural"]
                    .fillna("")
                    .str.strip() != ""
                    ]
            )

            # ==========================
            # KPIs
            # ==========================

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
                    total_com_historia
                )

            st.divider()

            # ==========================
            # GRÁFICO CATEGORIAS
            # ==========================

            categoria_df = (
                df["categoria"]
                .value_counts()
                .reset_index()
            )

            categoria_df.columns = [
                "Categoria",
                "Quantidade"
            ]

            fig_categoria = px.bar(
                categoria_df,
                x="Categoria",
                y="Quantidade",
                title="Locais por Categoria"
            )

            st.plotly_chart(
                fig_categoria,
                use_container_width=True
            )

            # ==========================
            # GRÁFICO PIZZA
            # ==========================

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

            # ==========================
            # VERIFICADOS
            # ==========================

            verificados_df = pd.DataFrame(
                {
                    "Status": [
                        "Verificados",
                        "Não Verificados"
                    ],
                    "Quantidade": [
                        total_verificados,
                        total_locais - total_verificados
                    ]
                }
            )

            fig_verificados = px.pie(
                verificados_df,
                names="Status",
                values="Quantidade",
                title="Status dos Locais"
            )

            st.plotly_chart(
                fig_verificados,
                use_container_width=True
            )

            st.divider()

            # ==========================
            # TOP CATEGORIAS
            # ==========================

            st.subheader(
                "🏆 Ranking de Categorias"
            )

            ranking = (
                df["categoria"]
                .value_counts()
                .reset_index()
            )

            ranking.columns = [
                "Categoria",
                "Quantidade"
            ]

            st.dataframe(
                ranking,
                use_container_width=True
            )

            st.divider()

            # ==========================
            # ÚLTIMOS CADASTROS
            # ==========================

            st.subheader(
                "🕒 Últimos Locais Cadastrados"
            )

            try:

                ultimos = (
                    df.sort_values(
                        by="id",
                        ascending=False
                    )
                    .head(10)
                )

                st.dataframe(
                    ultimos[
                        [
                            "nome",
                            "categoria",
                            "data_cadastro"
                        ]
                    ],
                    use_container_width=True
                )

            except:

                st.dataframe(
                    df.head(10),
                    use_container_width=True
                )

            st.divider()

            # ==========================
            # TABELA COMPLETA
            # ==========================

            st.subheader(
                "📋 Base Completa"
            )

            st.dataframe(
                df,
                use_container_width=True
            )
            # ==========================================
            # EXPORTAR
            # ==========================================

            elif menu == "Exportar":

            st.title("📤 Exportação de Dados")

            df = carregar_locais()

            if df.empty:

                st.warning(
                    "Nenhum local cadastrado para exportar."
                )

            else:

                st.subheader("📋 Prévia dos Dados")

                st.dataframe(
                    df,
                    use_container_width=True
                )

                st.divider()

                # ==========================
                # FILTRO POR CATEGORIA
                # ==========================

                categorias = sorted(
                    df["categoria"]
                    .dropna()
                    .unique()
                    .tolist()
                )

                categoria_escolhida = st.selectbox(
                    "Filtrar Categoria",
                    ["Todas"] + categorias
                )

                if categoria_escolhida != "Todas":

                    df_export = df[
                        df["categoria"]
                        == categoria_escolhida
                        ]

                else:

                    df_export = df

                st.info(
                    f"{len(df_export)} registros selecionados."
                )

                st.divider()

                # ==========================
                # EXPORTAÇÃO CSV
                # ==========================

                csv = df_export.to_csv(
                    index=False,
                    encoding="utf-8-sig"
                )

                st.download_button(
                    label="⬇️ Baixar CSV",
                    data=csv,
                    file_name="mapa_cultural_socorro.csv",
                    mime="text/csv"
                )

                st.success(
                    "CSV pronto para importar no Excel, LibreOffice e Google Sheets."
                )

                st.divider()

                # ==========================
                # ESTATÍSTICAS EXPORTAÇÃO
                # ==========================

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
                                df_export["status_verificado"] == 1
                                ]
                        )
                    )

                st.divider()

                st.subheader(
                    "📄 Campos Exportados"
                )

                st.write(
                    list(df_export.columns)
                )


                # ==========================================
                # EXPORTAÇÃO KML
                # ==========================================

                def gerar_kml(df):

                    kml = """<?xml version="1.0" encoding="UTF-8"?>
                <kml xmlns="http://www.opengis.net/kml/2.2">
                <Document>

                <name>Mapa Cultural Socorro</name>

                """

                    for _, local in df.iterrows():

                        nome = str(local.get("nome", "Sem Nome"))
                        categoria = str(local.get("categoria", "Outro"))
                        descricao = str(local.get("descricao", ""))
                        historia = str(local.get("historia_cultural", ""))
                        endereco = str(local.get("endereco", ""))
                        telefone = str(local.get("telefone", ""))
                        horario = str(local.get("horario", ""))
                        latitude = local.get("latitude")
                        longitude = local.get("longitude")

                        if pd.isna(latitude) or pd.isna(longitude):
                            continue

                        popup_html = f"""
                        <![CDATA[
                        <h2>{nome}</h2>

                        <b>Categoria:</b> {categoria}<br>

                        <b>Endereço:</b> {endereco}<br>

                        <b>Telefone:</b> {telefone}<br>

                        <b>Horário:</b> {horario}<br><br>

                        <b>Descrição:</b><br>
                        {descricao}<br><br>

                        <b>História Cultural:</b><br>
                        {historia}
                        ]]>
                        """

                        placemark = f"""
                        <Placemark>

                            <name>{nome}</name>

                            <description>
                                {popup_html}
                            </description>

                            <Point>
                                <coordinates>
                                    {longitude},{latitude},0
                                </coordinates>
                            </Point>

                        </Placemark>
                        """

                        kml += placemark

                    kml += """
                </Document>
                </kml>
                """

                    return kml


                # ==========================================
                # STATUS ABERTO AGORA
                # ==========================================

                def verificar_status(horario):

                    if not horario:
                        return "⚪ Horário não informado"

                    try:

                        horario = horario.strip()

                        padrao = r"(\d{2}:\d{2})\s*(?:às|-)\s*(\d{2}:\d{2})"

                        resultado = re.search(
                            padrao,
                            horario
                        )

                        if not resultado:
                            return "⚪ Horário inválido"

                        abertura = resultado.group(1)
                        fechamento = resultado.group(2)

                        agora = datetime.now().time()

                        hora_abertura = datetime.strptime(
                            abertura,
                            "%H:%M"
                        ).time()

                        hora_fechamento = datetime.strptime(
                            fechamento,
                            "%H:%M"
                        ).time()

                        if hora_abertura <= agora <= hora_fechamento:

                            minutos_restantes = (
                                                        datetime.combine(
                                                            datetime.today(),
                                                            hora_fechamento
                                                        )
                                                        -
                                                        datetime.combine(
                                                            datetime.today(),
                                                            agora
                                                        )
                                                ).seconds // 60

                            if minutos_restantes <= 60:
                                return (
                                    f"🟡 Fecha em "
                                    f"{minutos_restantes} min"
                                )

                            return (
                                f"🟢 Aberto até "
                                f"{fechamento}"
                            )

                        return "🔴 Fechado"

                    except Exception:

                        return "⚪ Horário inválido"
# ==========================================
# HISTÓRIA CULTURAL AUTOMÁTICA
# ==========================================

def gerar_historia_cultural(nome, categoria):

    historias = {

        "Praça": f"""
        {nome} é um espaço público de convivência social,
        utilizado pela população para lazer, encontros,
        eventos comunitários e atividades culturais.
        As praças desempenham papel importante na
        identidade urbana e na memória coletiva.
        """,

        "Igreja": f"""
        {nome} representa um importante ponto de fé,
        tradição religiosa e encontro da comunidade.
        Igrejas costumam preservar elementos históricos,
        culturais e arquitetônicos relevantes para a cidade.
        """,

        "Escola": f"""
        {nome} contribui para o desenvolvimento educacional
        da população, formando cidadãos e promovendo
        conhecimento para as futuras gerações.
        """,

        "Hospital": f"""
        {nome} possui importância social por oferecer
        atendimento à saúde da população e contribuir
        para o bem-estar da comunidade local.
        """,

        "UBS": f"""
        {nome} atua na atenção básica à saúde,
        sendo fundamental para prevenção de doenças,
        vacinação e acompanhamento da população.
        """,

        "Farmácia": f"""
        {nome} presta serviços essenciais relacionados
        à saúde, fornecendo medicamentos e orientações
        para a população.
        """,

        "Comércio": f"""
        {nome} participa da economia local,
        gerando empregos, renda e movimentando
        as atividades comerciais da região.
        """,

        "Turismo": f"""
        {nome} apresenta potencial turístico e cultural,
        podendo atrair visitantes interessados na história,
        cultura e características locais.
        """,

        "Cultura": f"""
        {nome} contribui para a preservação e valorização
        das manifestações culturais da comunidade.
        """,

        "Transporte": f"""
        {nome} desempenha papel importante na mobilidade
        urbana e na integração entre diferentes regiões.
        """
    }

    return historias.get(
        categoria,
        f"""
        {nome} é um local de interesse para a comunidade,
        contribuindo para o desenvolvimento social,
        econômico ou cultural da região.
        """
    )
