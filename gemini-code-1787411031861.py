import streamlit as st
import folium
import requests
import html
import os
import sqlite3
import json
import pandas as pd
from datetime import datetime
from streamlit_folium import st_folium
import plotly.express as px
from xml.sax.saxutils import escape as xml_escape
from rapidfuzz import fuzz

# ==========================================================
# CONFIGURAÇÃO
# ==========================================================

st.set_page_config(
    page_title="Mapa Cultural de Nossa Senhora do Socorro",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_LAT = -10.855
DEFAULT_LON = -37.125
RAIO_METROS = 12000
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DB = "mapa_socorro.db"

# ==========================================================
# ESTILO CSS
# ==========================================================

st.markdown(
    """
    <style>
    .main { background-color: #f5f7fa; }
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
    .badge-open { background: #2e7d32; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
    .badge-closed { background: #c62828; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
    .history-box {
        background: linear-gradient(135deg, #173b57, #256d8f);
        color: white;
        padding: 20px;
        border-radius: 16px;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
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
            dias_funcionamento TEXT,
            aberto_ate TEXT,
            historia_cultural TEXT,
            site TEXT,
            imagem TEXT,
            latitude REAL,
            longitude REAL,
            avaliacao REAL DEFAULT 0,
            fonte TEXT DEFAULT 'Cadastro manual',
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

    # Migração dinâmica
    cursor.execute("PRAGMA table_info(locais)")
    colunas = {row[1] for row in cursor.fetchall()}
    
    novas_colunas = {
        "dias_funcionamento": "TEXT",
        "aberto_ate": "TEXT",
        "historia_cultural": "TEXT",
        "fonte": "TEXT DEFAULT 'Cadastro manual'"
    }
    
    for col, tipo in novas_colunas.items():
        if col not in colunas:
            cursor.execute(f"ALTER TABLE locais ADD COLUMN {col} {tipo}")

    conn.commit()
    conn.close()

criar_banco()

# ==========================================================
# REGRAS E CATEGORIAS
# ==========================================================

CATEGORIAS = [
    "Comércio", "Alimentação", "Mercado", "Saúde", "Educação",
    "Religião", "Cultura", "Turismo e lazer", "Esporte",
    "Serviço", "Hotel", "Transporte", "Órgão público", "Outro"
]

def classificar_categoria(tags):
    shop = tags.get("shop", "")
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    healthcare = tags.get("healthcare", "")
    
    if healthcare or amenity in {"hospital", "clinic", "doctors", "dentist", "pharmacy"}:
        return "Saúde"
    if amenity in {"school", "kindergarten", "college", "university"}:
        return "Educação"
    if amenity in {"place_of_worship"} or tags.get("building") in {"church", "chapel"}:
        return "Religião"
    if amenity in {"restaurant", "cafe", "fast_food"}:
        return "Alimentação"
    if shop in {"supermarket", "convenience", "bakery"}:
        return "Mercado"
    if shop:
        return "Comércio"
    if tourism in {"museum", "gallery", "attraction"} or amenity in {"theatre", "cinema"}:
        return "Cultura"
    if leisure in {"park", "sports_centre", "stadium", "pitch", "playground"}:
        return "Turismo e lazer"
    return "Outro"

def calcular_status_aberto(horario_str, aberto_ate):
    agora = datetime.now()
    hora_atual = agora.time()
    
    if aberto_ate:
        try:
            hora_fechamento = datetime.strptime(aberto_ate.strip(), "%H:%M").time()
            if hora_atual <= hora_fechamento:
                return f"🟢 Aberto até às {aberto_ate}", "badge-open"
            else:
                return "🔴 Fechado agora", "badge-closed"
        except ValueError:
            pass

    if horario_str and "24/7" in horario_str:
        return "🟢 Aberto 24h", "badge-open"
        
    return "ℹ️ Horário não confirmado", "badge"

# ==========================================================
# CONSULTA OVERPASS / BANCO
# ==========================================================

def carregar_locais_banco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT nome, categoria, descricao, endereco, telefone, horario,
               dias_funcionamento, aberto_ate, historia_cultural, site,
               imagem, latitude, longitude, avaliacao, fonte
        FROM locais
        """
    )
    linhas = cursor.fetchall()
    conn.close()

    locais = []
    for l in linhas:
        locais.append({
            "nome": l[0], "categoria": l[1], "descricao": l[2] or "",
            "endereco": l[3] or "", "telefone": l[4] or "", "horario": l[5] or "",
            "dias_funcionamento": l[6] or "", "aberto_ate": l[7] or "",
            "historia_cultural": l[8] or "", "site": l[9] or "",
            "imagem": l[10] or "", "latitude": l[11], "longitude": l[12],
            "avaliacao": l[13] or 0, "fonte": l[14] or "Cadastro manual"
        })
    return locais

def buscar_locais_osm():
    query_area = f"""
    [out:json][timeout:120];
    (
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["shop"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["amenity"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["healthcare"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["tourism"];
      nwr(around:{RAIO_METROS},{DEFAULT_LAT},{DEFAULT_LON})["name"]["leisure"];
    );
    out center tags;
    """
    try:
        res = requests.post(OVERPASS_URL, data=query_area, timeout=120, headers={"User-Agent": "MapaSocorro/2.0"})
        dados = res.json()
        locais = []
        for item in dados.get("elements", []):
            tags = item.get("tags", {})
            nome = tags.get("name")
            if not nome: continue
            
            lat = item.get("lat") or item.get("center", {}).get("lat")
            lon = item.get("lon") or item.get("center", {}).get("lon")
            if not lat or not lon: continue

            cat = classificar_categoria(tags)
            locais.append({
                "nome": nome, "categoria": cat,
                "descricao": f"Ponto identificado via OpenStreetMap ({cat}).",
                "endereco": tags.get("addr:street", "Nossa Senhora do Socorro"),
                "telefone": tags.get("phone", ""), "horario": tags.get("opening_hours", ""),
                "dias_funcionamento": "Não especificado", "aberto_ate": "",
                "historia_cultural": "", "site": tags.get("website", ""),
                "imagem": "", "latitude": float(lat), "longitude": float(lon),
                "avaliacao": 0, "fonte": "OpenStreetMap"
            })
        return locais
    except Exception:
        return []

@st.cache_data(ttl=600)
def carregar_pontos():
    return buscar_locais_osm() + carregar_locais_banco()

locais = carregar_pontos()

# ==========================================================
# ALGORITMO DE BUSCA INTELIGENTE (TOLERANTE A ERROS)
# ==========================================================

def buscar_com_ia(termo_busca, lista_locais):
    chave = obter_chave_openai()
    if not chave or not termo_busca: return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=chave)
        resumo = [{"id": i, "nome": l["nome"], "categoria": l["categoria"], "desc": l["descricao"]} for i, l in enumerate(lista_locais)]
        
        prompt = f"""
        O usuário digitou: "{termo_busca}" (pode haver erros fonéticos ou de digitação).
        Identifique quais itens correspondem à intenção de busca.
        Lista: {json.dumps(resumo, ensure_ascii=False)}
        Responda APENAS com um array JSON com os IDs. Exemplo: [0, 2]
        """
        
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        ids = json.loads(resp.choices[0].message.content.strip())
        return [lista_locais[i] for i in ids if i < len(lista_locais)]
    except Exception:
        return []

def buscar_inteligente(termo, lista_locais, limite_score=55):
    if not termo: return lista_locais
    termo_clean = termo.lower().strip()
    resultados = []

    for item in lista_locais:
        texto = f"{item['nome']} {item['categoria']} {item['descricao']} {item['endereco']} {item['historia_cultural']}".lower()
        score = fuzz.partial_ratio(termo_clean, texto)
        if score >= limite_score:
            resultados.append((item, score))
            
    resultados.sort(key=lambda x: x[1], reverse=True)
    filtrados = [r[0] for r in resultados]

    if not filtrados:
        filtrados = buscar_com_ia(termo, lista_locais)
        
    return filtrados

# ==========================================================
# INTEGRACAO IA (OPENAI)
# ==========================================================

def obter_chave_openai():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.environ.get("OPENAI_API_KEY")

def gerar_historia_ia(nome_local, categoria):
    chave = obter_chave_openai()
    if not chave:
        return "Configure a OPENAI_API_KEY nos Secrets para usar a IA."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=chave)
        prompt = f"Escreva um pequeno resumo histórico e cultural (máximo 100 palavras) sobre o local '{nome_local}' (Categoria: {categoria}), localizado no município de Nossa Senhora do Socorro, Sergipe."
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Erro ao gerar com IA: {e}"

# ==========================================================
# EXPORTAÇÃO KML / MY MAPS / EARTH ENRIQUECIDO
# ==========================================================

def criar_kml_avancado(pontos):
    kml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        '<name>Mapa Cultural - Nossa Senhora do Socorro</name>'
    ]
    for p in pontos:
        lat, lon = p.get("latitude"), p.get("longitude")
        if not lat or not lon: continue

        nome = xml_escape(str(p.get("nome", "")))
        cat = xml_escape(str(p.get("categoria", "")))
        historia = xml_escape(str(p.get("historia_cultural", "")))
        
        cdata_desc = f"<![CDATA[" \
                     f"<h3>{nome}</h3>" \
                     f"<p><b>Categoria:</b> {cat}</p>" \
                     f"<p><b>Dias:</b> {p.get('dias_funcionamento','')}</p>" \
                     f"<p><b>Aberto até:</b> {p.get('aberto_ate','')}</p>" \
                     f"<p><b>História & Cultura:</b> {historia}</p>" \
                     f"]]>"

        kml.append(f"""
        <Placemark>
            <name>{nome}</name>
            <description>{cdata_desc}</description>
            <LookAt>
                <longitude>{lon}</longitude>
                <latitude>{lat}</latitude>
                <altitude>0</altitude>
                <range>500</range>
                <tilt>45</tilt>
                <heading>0</heading>
            </LookAt>
            <Point>
                <coordinates>{lon},{lat},0</coordinates>
            </Point>
        </Placemark>
        """)
    kml.append('</Document></kml>')
    return "".join(kml)

# ==========================================================
# INTERFACE PRINCIPAL STREAMLIT
# ==========================================================

st.markdown("# 🗺️ Mapa Cultural & Comercial de Socorro")
st.info("📍 Nossa Senhora do Socorro — Sergipe")

# SIDEBAR
st.sidebar.title("🎛️ Filtros & Opções")
categorias_disponiveis = sorted(list(set(l["categoria"] for l in locais)))
categorias_sel = st.sidebar.multiselect("Categorias", categorias_disponiveis, default=categorias_disponiveis)
mostrar_mapa = st.sidebar.checkbox("🗺️ Exibir Mapa Interativo", True)

if st.sidebar.button("🔄 Recarregar Dados"):
    carregar_pontos.clear()
    st.rerun()

# PESQUISA TOLERANTE A ERROS
st.subheader("🔎 Pesquisa Inteligente")
pesquisa = st.text_input("Busque por praças, postos de saúde, comércios...", placeholder="Pode digitar com erros: 'farrmacia', 'prasa', 'posto'...")

locais_filtrados = [l for l in locais if l["categoria"] in categorias_sel]
resultados = buscar_inteligente(pesquisa, locais_filtrados)

# MÉTRICAS
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Encontrado", len(resultados))
col2.metric("🏥 Saúde", len([x for x in resultados if x["categoria"] == "Saúde"]))
col3.metric("🛍️ Comércio", len([x for x in resultados if x["categoria"] == "Comércio"]))
col4.metric("🎭 Cultura & Praças", len([x for x in resultados if x["categoria"] in ["Cultura", "Turismo e lazer"]]))

# MAPA FOLIUM
if mostrar_mapa:
    st.subheader("📍 Visualização Geográfica")
    mapa = folium.Map(location=[DEFAULT_LAT, DEFAULT_LON], zoom_start=13)
    pontos_bounds = []

    for loc in resultados:
        if loc.get("latitude") and loc.get("longitude"):
            status_txt, class_css = calcular_status_aberto(loc.get("horario"), loc.get("aberto_ate"))
            popup_html = f"""
            <div style="width:240px;">
                <h4>{html.escape(loc['nome'])}</h4>
                <p><b>Categoria:</b> {loc['categoria']}</p>
                <p><b>Status:</b> {status_txt}</p>
                <p><b>Endereço:</b> {loc.get('endereco','')}</p>
            </div>
            """
            folium.Marker(
                location=[loc["latitude"], loc["longitude"]],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=loc["nome"]
            ).add_to(mapa)
            pontos_bounds.append([loc["latitude"], loc["longitude"]])

    if pontos_bounds:
        mapa.fit_bounds(pontos_bounds)
    st_folium(mapa, width=None, height=500, returned_objects=[])

# EXPORTAÇÃO MY MAPS / EARTH
st.markdown("---")
st.subheader("📥 Exportação Avançada (Google My Maps & Earth 3D)")
col_kml, col_csv = st.columns(2)

with col_kml:
    kml_data = criar_kml_avancado(resultados)
    st.download_button("🌍 Baixar KML Completo (My Maps/Earth)", data=kml_data.encode("utf-8"), file_name="mapa_socorro_completo.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)

with col_csv:
    df_exp = pd.DataFrame(resultados)
    st.download_button("📄 Baixar CSV para My Maps", data=df_exp.to_csv(index=False).encode("utf-8-sig"), file_name="mapa_socorro.csv", mime="text/csv", use_container_width=True)

# CARDS DOS LOCAIS
st.markdown("---")
st.subheader("📚 Locais Encontrados")

for idx, loc in enumerate(resultados):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        c1, c2 = st.columns([1, 3])
        
        status_txt, status_class = calcular_status_aberto(loc.get("horario"), loc.get("aberto_ate"))

        with c1:
            st.markdown(f"### 📍 {loc['nome']}")
            st.markdown(f"<span class='{status_class}'>{status_txt}</span>", unsafe_allow_html=True)

        with c2:
            st.markdown(f"**Categoria:** {loc['categoria']} | **Dias:** {loc.get('dias_funcionamento', 'Não informado')}")
            st.markdown(f"**Endereço:** {loc.get('endereco', 'Não informado')}")
            
            if loc.get("historia_cultural"):
                st.markdown(f"<div class='history-box'>📜 <b>História & Cultura:</b><br>{loc['historia_cultural']}</div>", unsafe_allow_html=True)

            if st.button(f"✨ Gerar Contexto Histórico com IA", key=f"hist_{idx}"):
                with st.spinner("Pesquisando história do local..."):
                    historia = gerar_historia_ia(loc['nome'], loc['categoria'])
                    st.success(historia)

        st.markdown("</div>", unsafe_allow_html=True)

# CADASTRO DE NOVO LOCAL
st.markdown("---")
st.subheader("➕ Cadastrar Novo Ponto Cultural ou Comercial")

with st.form("cad_form"):
    c_nome = st.text_input("Nome do Local")
    c_cat = st.selectbox("Categoria", CATEGORIAS)
    c_dias = st.text_input("Dias de Funcionamento", placeholder="Ex: Segunda a Sexta")
    c_ate = st.text_input("Aberto até (HH:MM)", placeholder="Ex: 18:00")
    c_hist = st.text_area("História / Descrição Cultural")
    c_end = st.text_input("Endereço Completo")
    c_lat = st.number_input("Latitude", value=DEFAULT_LAT, format="%.6f")
    c_lon = st.number_input("Longitude", value=DEFAULT_LON, format="%.6f")
    
    if st.form_submit_button("💾 Salvar no Banco"):
        if c_nome:
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO locais (nome, categoria, dias_funcionamento, aberto_ate, historia_cultural, endereco, latitude, longitude, fonte, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (c_nome, c_cat, c_dias, c_ate, c_hist, c_end, c_lat, c_lon, "Cadastro manual", datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            carregar_pontos.clear()
            st.success("Cadastrado com sucesso!")
            st.rerun()