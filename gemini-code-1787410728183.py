import streamlit as st
import folium
import requests
import html
import os
import sqlite3
import pandas as pd
import json
from datetime import datetime
from streamlit_folium import st_folium
import plotly.express as px
from xml.sax.saxutils import escape as xml_escape
from rapidfuzz import fuzz, process

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
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
# ESTILOS CSS
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
    .badge-open {
        background: #2e7d32;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-closed {
        background: #c62828;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .history-box {
        background: linear-gradient(135deg, #173b57, #256d8f);
        color: white;
        padding: 20px;
        border-radius: 14px;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .source-box {
        background: #eef4f8;
        padding: 15px;
        border-radius: 12px;
        font-size: 14px;
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
            historia TEXT,
            endereco TEXT,
            telefone TEXT,
            horario TEXT,
            dias_funcionamento TEXT,
            aberto_ate TEXT,
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

    # Migrações dinâmicas para tabelas legadas
    colunas = {row[1] for row in cursor.execute("PRAGMA table_info(locais)").fetchall()}
    novas_colunas = {
        "fonte": "TEXT DEFAULT 'Cadastro manual'",
        "historia": "TEXT DEFAULT ''",
        "dias_funcionamento": "TEXT DEFAULT 'Segunda a Sábado'",
        "aberto_ate": "TEXT DEFAULT ''"
    }

    for col, col_def in novas_colunas.items():
        if col not in colunas:
            cursor.execute(f"ALTER TABLE locais ADD COLUMN {col} {col_def}")

    conn.commit()
    conn.close()

criar_banco()

# ==========================================================
# CATEGORIAS E REGRAS DA OVERPASS API
# ==========================================================

CATEGORIAS = [
    "Comércio",
    "Alimentação",
    "Mercado",
    "Saúde",
    "Educação",
    "Religião",
    "Cultura",
    "Turismo e lazer",
    "Praça",
    "Esporte",
    "Serviço",
    "Hotel",
    "Transporte",
    "Órgão público",
    "Outro",
]

def classificar_categoria(tags):
    shop = tags.get("shop", "")
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    healthcare = tags.get("healthcare", "")
    office = tags.get("office", "")
    craft = tags.get("craft", "")
    building = tags.get("building", "")

    if healthcare or amenity in {"hospital", "clinic", "doctors", "dentist", "pharmacy", "nursing_home"}:
        return "Saúde"
    if amenity in {"school", "kindergarten", "college", "university"} or tags.get("education"):
        return "Educação"
    if amenity in {"place_of_worship", "monastery"} or building in {"church", "chapel"}:
        return "Religião"
    if amenity in {"restaurant", "cafe", "fast_food", "food_court", "ice_cream"}:
        return "Alimentação"
    if shop in {"supermarket", "convenience", "greengrocer", "bakery"}:
        return "Mercado"
    if shop:
        return "Comércio"
    if tourism in {"hotel", "guest_house", "hostel", "motel"}:
        return "Hotel"
    if tourism in {"museum", "gallery", "attraction", "arts_centre"} or amenity in {"library", "theatre", "cinema"}:
        return "Cultura"
    if leisure == "park" or tags.get("place") == "square":
        return "Praça"
    if leisure in {"sports_centre", "stadium", "pitch", "playground", "fitness_centre"}:
        return "Turismo e lazer"
    if office or craft:
        return "Serviço"
    if amenity in {"townhall", "police", "fire_station", "post_office", "courthouse"}:
        return "Órgão público"
    return "Outro"

def montar_endereco(tags):
    partes = [tags.get(k) for k in ["addr:street", "addr:housenumber", "addr:suburb", "addr:city"] if tags.get(k)]
    return ", ".join(partes)

def buscar_locais_osm():
    query_area = """
    [out:json][timeout:60];
    area["name"="Nossa Senhora do Socorro"]["boundary"="administrative"]->.socorro;
    (
      nwr(area.socorro)["name"]["shop"];
      nwr(area.socorro)["name"]["amenity"];
      nwr(area.socorro)["name"]["healthcare"];
      nwr(area.socorro)["name"]["tourism"];
      nwr(area.socorro)["name"]["leisure"];
    );
    out center tags;
    """
    try:
        res = requests.post(OVERPASS_URL, data=query_area, timeout=60, headers={"User-Agent": "MapaSocorro/2.0"})
        dados = res.json()
        locais = []
        for item in dados.get("elements", []):
            tags = item.get("tags", {})
            nome = tags.get("name")
            if not nome: continue
            lat = item.get("lat") or item.get("center", {}).get("lat")
            lon = item.get("lon") or item.get("center", {}).get("lon")
            if lat is None or lon is None: continue

            categoria = classificar_categoria(tags)
            locais.append({
                "nome": nome,
                "categoria": categoria,
                "descricao": f"{nome} localizado no OpenStreetMap ({categoria}).",
                "historia": tags.get("description", "Ponto de interesse em Nossa Senhora do Socorro."),
                "endereco": montar_endereco(tags) or "Nossa Senhora do Socorro - SE",
                "telefone": tags.get("phone", "Não informado"),
                "horario": tags.get("opening_hours", "Consulte no local"),
                "dias_funcionamento": "Segunda a Sábado",
                "aberto_ate": tags.get("opening_hours", "").split("-")[-1] if "-" in tags.get("opening_hours", "") else "18:00",
                "site": tags.get("website", ""),
                "imagem": tags.get("image", ""),
                "latitude": float(lat),
                "longitude": float(lon),
                "avaliacao": 4.0,
                "fonte": "OpenStreetMap",
            })
        return locais
    except Exception:
        return []

def carregar_locais_banco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT nome, categoria, descricao, historia, endereco, telefone, horario,
               dias_funcionamento, aberto_ate, site, imagem, latitude, longitude, avaliacao, fonte
        FROM locais
        """
    )
    linhas = cursor.fetchall()
    conn.close()
    
    locais = []
    for r in linhas:
        locais.append({
            "nome": r[0], "categoria": r[1], "descricao": r[2] or "", "historia": r[3] or "",
            "endereco": r[4] or "", "telefone": r[5] or "", "horario": r[6] or "",
            "dias_funcionamento": r[7] or "Segunda a Sexta", "aberto_ate": r[8] or "",
            "site": r[9] or "", "imagem": r[10] or "", "latitude": r[11], "longitude": r[12],
            "avaliacao": r[13] or 0.0, "fonte": r[14] or "Cadastro manual"
        })
    return locais

@st.cache_data(ttl=300)
def carregar_todos_pontos():
    return carregar_locais_banco() + buscar_locais_osm()

locais = carregar_todos_pontos()

# ==========================================================
# BUSCA INTELIGENTE (TOLERANTE A ERROS & IA)
# ==========================================================

def obter_chave_openai():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.environ.get("OPENAI_API_KEY")

def buscar_tolerante(termo, lista_locais, limite_score=55):
    if not termo:
        return lista_locais
    
    termo_limpo = termo.lower().strip()
    resultados_com_score = []

    for item in lista_locais:
        texto_alvo = f"{item['nome']} {item['categoria']} {item['descricao']} {item['endereco']}".lower()
        score = fuzz.partial_ratio(termo_limpo, texto_alvo)
        
        # Bônus para nomes muito parecidos
        nome_score = fuzz.ratio(termo_limpo, item['nome'].lower())
        final_score = max(score, nome_score)

        if final_score >= limite_score:
            resultados_com_score.append((item, final_score))

    resultados_com_score.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in resultados_com_score]

def buscar_semantica_ia(termo_busca, lista_locais):
    chave = obter_chave_openai()
    if not chave or not termo_busca:
        return []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=chave)

        resumo_locais = [
            {"id": i, "nome": loc["nome"], "categoria": loc["categoria"], "descricao": loc["descricao"]}
            for i, loc in enumerate(lista_locais)
        ]

        prompt = f"""
        O usuário digitou a seguinte pesquisa: "{termo_busca}".
        Mesmo com erros ortográficos graves, gírias ou sinônimos (ex: "farrmacia" -> farmácia, "prasa" -> praça), identifique quais dos locais abaixo correspondem à intenção.
        
        Locais:
        {resumo_locais[:50]}
        
        Retorne APENAS um JSON em formato de lista com os IDs numéricos correspondentes. Exemplo: [0, 2, 5].
        """

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        ids_encontrados = json.loads(resposta.choices[0].message.content.strip())
        return [lista_locais[i] for i in ids_encontrados if i < len(lista_locais)]
    except Exception:
        return []

def perguntar_sergia(local, pergunta):
    chave = obter_chave_openai()
    if not chave:
        return "⚠️ A SergIA necessita da OPENAI_API_KEY configurada nos Secrets do Streamlit."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=chave)

        contexto = f"""
Nome: {local.get('nome')}
Categoria: {local.get('categoria')}
Descrição: {local.get('descricao')}
História Cultural: {local.get('historia')}
Endereço: {local.get('endereco')}
Horário / Dias: {local.get('dias_funcionamento')} - Aberto até: {local.get('aberto_ate')}
"""
        instrucoes = "Você é a SergIA, assistente cultural e turística de Nossa Senhora do Socorro - SE. Seja amigável, clara e valorize a história local."
        
        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": instrucoes},
                {"role": "user", "content": f"DADOS:\n{contexto}\n\nPERGUNTA DO USUÁRIO: {pergunta}"}
            ]
        )
        return resposta.choices[0].message.content
    except Exception as e:
        return f"❌ Erro ao consultar a SergIA: {e}"

def gerar_historia_ia(nome, categoria, endereco):
    chave = obter_chave_openai()
    if not chave:
        return "Localizado no município de Nossa Senhora do Socorro - SE."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=chave)
        prompt = f"Escreva um parágrafo enriquecedor e cultural de até 4 frases sobre o local '{nome}' (Categoria: {categoria}), situado em {endereco}, Nossa Senhora do Socorro - Sergipe. Destaque sua relevância para a comunidade local."
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return "Ponto cultural e comercial de relevância em Nossa Senhora do Socorro."

# ==========================================================
# EXPORTAÇÃO (GOOGLE MY MAPS & GOOGLE EARTH)
# ==========================================================

def criar_kml_avancado(pontos):
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        '<name>Mapa Cultural - Nossa Senhora do Socorro</name>',
        '<description>Locais comerciais, saúde, praças e equipamentos culturais.</description>'
    ]

    for local in pontos:
        lat = local.get("latitude")
        lon = local.get("longitude")
        if lat is None or lon is None: continue

        nome = xml_escape(str(local.get("nome", "")))
        categoria = xml_escape(str(local.get("categoria", "")))
        historia = xml_escape(str(local.get("historia", "")))
        horario = xml_escape(f"{local.get('dias_funcionamento', '')} - Aberto até {local.get('aberto_ate', '')}")
        endereco = xml_escape(str(local.get("endereco", "")))
        telefone = xml_escape(str(local.get("telefone", "")))

        html_description = f"""<![CDATA[
            <div style="font-family: Arial, sans-serif; padding: 5px;">
                <h3 style="color: #173b57; margin-bottom: 5px;">{nome}</h3>
                <p><b>Categoria:</b> {categoria}</p>
                <p><b>📍 Endereço:</b> {endereco}</p>
                <p><b>🕐 Funcionamento:</b> {horario}</p>
                <p><b>📞 Contato:</b> {telefone}</p>
                <hr>
                <p><b>🏛️ História e Cultura:</b><br>{historia}</p>
            </div>
        ]]>"""

        partes.extend([
            '<Placemark>',
            f'<name>{nome}</name>',
            f'<description>{html_description}</description>',
            f'<ExtendedData><Data name="Categoria"><value>{categoria}</value></Data></ExtendedData>',
            '<Point>',
            f'<coordinates>{lon},{lat},0</coordinates>',
            '</Point>',
            '</Placemark>'
        ])

    partes.extend(['</Document>', '</kml>'])
    return "\n".join(partes)

# ==========================================================
# CABEÇALHO & SIDEBAR
# ==========================================================

st.markdown("# 🗺️ Mapa Cultural de Nossa Senhora do Socorro")
st.markdown("Explore comércios, unidades de saúde, praças, horários de funcionamento e a história dos locais de Nossa Senhora do Socorro-SE.")

st.sidebar.title("🎛️ Filtros & Opções")
cats_disponiveis = sorted(list(set(l["categoria"] for l in locais)))
cats_selecionadas = st.sidebar.multiselect("Categorias", cats_disponiveis, default=cats_disponiveis)

mostrar_mapa = st.sidebar.checkbox("🗺️ Exibir Mapa Interativo", True)
if st.sidebar.button("🔄 Recarregar Dados"):
    carregar_todos_pontos.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 **Dica de Busca:** Você pode digitar mesmo com erros (ex: *'farrmacia'*, *'prasa'*, *'posto'*) que o sistema encontrará os locais.")

# ==========================================================
# PESQUISA
# ==========================================================

st.subheader("🔎 Pesquisa Inteligente")

with st.form("form_busca"):
    termo_input = st.text_input("O que você procura?", placeholder="Ex: farrmacia, posto de saude, praça matriz, mercado...")
    btn_buscar = st.form_submit_button("🔍 Buscar")

resultados = [l for l in locais if l["categoria"] in cats_selecionadas]

if termo_input.strip():
    # 1. Busca por aproximação (fuzz/rapidfuzz)
    resultados_fuzz = buscar_tolerante(termo_input, resultados)
    
    if resultados_fuzz:
        resultados = resultados_fuzz
    else:
        # 2. Fallback via IA Semântica se a busca direta falhar
        resultados = buscar_semantica_ia(termo_input, resultados)

# ==========================================================
# MÉTRICAS
# ==========================================================

c1, c2, c3, c4 = st.columns(4)
c1.metric("📍 Total Exibido", len(resultados))
c2.metric("🏥 Saúde", len([x for x in resultados if x["categoria"] == "Saúde"]))
c3.metric("🌳 Praças", len([x for x in resultados if x["categoria"] == "Praça"]))
c4.metric("🛍️ Comércio", len([x for x in resultados if x["categoria"] == "Comércio"]))

# ==========================================================
# MAPA
# ==========================================================

if mostrar_mapa:
    st.subheader("📍 Visualização Geográfica")

    m = folium.Map(location=[DEFAULT_LAT, DEFAULT_LON], zoom_start=13, tiles="OpenStreetMap")
    
    cores = {
        "Comércio": "blue", "Alimentação": "red", "Mercado": "green", "Saúde": "pink",
        "Educação": "darkblue", "Religião": "purple", "Cultura": "purple", "Praça": "lightgreen",
        "Turismo e lazer": "cadetblue", "Serviço": "orange", "Órgão público": "darkgreen", "Outro": "gray"
    }

    bounds = []
    for loc in resultados:
        if loc.get("latitude") is None or loc.get("longitude") is None: continue

        popup_content = f"""
        <div style="width:260px; font-family:Arial;">
            <h4 style="color:#173b57; margin-bottom:5px;">{html.escape(loc['nome'])}</h4>
            <p><b>🏷️ {html.escape(loc['categoria'])}</b></p>
            <p>📍 {html.escape(loc['endereco'])}</p>
            <p>🕐 <b>Funcionamento:</b> {html.escape(loc['dias_funcionamento'])}<br>Aberto até: <b>{html.escape(loc['aberto_ate'])}</b></p>
            <p>📞 {html.escape(loc['telefone'])}</p>
            <hr>
            <p style="font-size:12px; color:#555;">{html.escape(loc['historia'][:150])}...</p>
        </div>
        """

        folium.Marker(
            location=[loc["latitude"], loc["longitude"]],
            popup=folium.Popup(popup_content, max_width=300),
            tooltip=loc["nome"],
            icon=folium.Icon(color=cores.get(loc["categoria"], "blue"), icon="info-sign")
        ).add_to(m)

        bounds.append([loc["latitude"], loc["longitude"]])

    if bounds:
        m.fit_bounds(bounds)

    st_folium(m, width=None, height=500, returned_objects=[])

# ==========================================================
# EXPORTAÇÃO PARA GOOGLE MY MAPS E GOOGLE EARTH
# ==========================================================

st.markdown("---")
st.subheader("📥 Exportar para Google My Maps e Google Earth")
st.write("Baixe a lista de locais estruturada e importe no **Google My Maps** (para celular/web) ou no **Google Earth** (para visualizações 3D em camadas).")

col_kml, col_csv = st.columns(2)

with col_kml:
    kml_data = criar_kml_avancado(resultados)
    st.download_button(
        "🌎 Baixar KML Completo (My Maps / Earth)",
        data=kml_data.encode("utf-8"),
        file_name="mapa_cultural_socorro.kml",
        mime="application/vnd.google-earth.kml+xml",
        use_container_width=True
    )

with col_csv:
    df_exp = pd.DataFrame(resultados)
    csv_data = df_exp.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📄 Baixar Planilha CSV (My Maps)",
        data=csv_data,
        file_name="mapa_cultural_socorro.csv",
        mime="text/csv",
        use_container_width=True
    )

# ==========================================================
# LISTAGEM DOS LOCAIS E HISTÓRIA CULTURAL
# ==========================================================

st.markdown("---")
st.subheader("📚 Cartões de Locais e História Cultural")

if resultados:
    for idx, loc in enumerate(resultados):
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col_img, col_info = st.columns([1, 3])

            with col_img:
                if loc.get("imagem"):
                    st.image(loc["imagem"], use_container_width=True)
                else:
                    st.markdown(
                        """
                        <div style="height:150px; background:#eef4f8; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:40px;">
                        🏛️
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            with col_info:
                st.markdown(f"### {html.escape(loc['nome'])}")
                st.markdown(f"<span class='badge'>{html.escape(loc['categoria'])}</span>", unsafe_allow_html=True)
                st.write(f"📍 **Endereço:** {loc['endereco']}")
                st.write(f"🕐 **Funcionamento:** {loc['dias_funcionamento']} — **Aberto até:** {loc['aberto_ate']}")
                st.write(f"📞 **Telefone:** {loc['telefone']}")

                if loc.get("historia"):
                    st.markdown(f"""
                    <div class="history-box">
                        <b>📖 História & Contexto Cultural:</b><br>{html.escape(loc['historia'])}
                    </div>
                    """, unsafe_allow_html=True)

                if st.button(f"🤖 Perguntar à SergIA sobre este local", key=f"btn_ia_{idx}"):
                    with st.spinner("Consultando SergIA..."):
                        resposta = perguntar_sergia(loc, "Explique a importância histórica/cultural deste local e dicas para quem quer visitar.")
                        st.info(resposta)

            st.markdown('</div>', unsafe_allow_html=True)
else:
    st.warning("Nenhum local encontrado.")

# ==========================================================
# CADASTRO COM SUPORTE À IA
# ==========================================================

st.markdown("---")
st.subheader("➕ Cadastrar Novo Ponto Cultural / Comercial")

with st.expander("Clique para abrir o formulário de cadastro"):
    with st.form("form_novo_local"):
        nome_c = st.text_input("Nome do Local *")
        categoria_c = st.selectbox("Categoria *", CATEGORIAS)
        endereco_c = st.text_input("Endereço Completo")
        dias_c = st.text_input("Dias de Funcionamento", "Segunda a Sábado")
        aberto_ate_c = st.text_input("Aberto até", "18:00")
        telefone_c = st.text_input("Telefone")
        
        historia_c = st.text_area("História / Descrição Cultural (Deixe em branco para a IA gerar automaticamente)")
        
        c_lat, c_lon = st.columns(2)
        lat_c = c_lat.number_input("Latitude", value=DEFAULT_LAT, format="%.6f")
        lon_c = c_lon.number_input("Longitude", value=DEFAULT_LON, format="%.6f")

        btn_salvar = st.form_submit_button("💾 Cadastrar Ponto", type="primary")

        if btn_salvar:
            if not nome_c.strip():
                st.error("O campo Nome é obrigatório.")
            else:
                # Se não informou história, a IA gera automaticamente
                if not historia_c.strip():
                    historia_c = gerar_historia_ia(nome_c, categoria_c, endereco_c)

                conn = conectar()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO locais (
                        nome, categoria, descricao, historia, endereco, telefone, horario,
                        dias_funcionamento, aberto_ate, latitude, longitude, fonte, criado_em
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        nome_c.strip(), categoria_c, f"{nome_c} ({categoria_c})", historia_c,
                        endereco_c, telefone_c, f"{dias_c} até {aberto_ate_c}", dias_c, aberto_ate_c,
                        lat_c, lon_c, "Cadastro Manual", datetime.now().isoformat()
                    )
                )
                conn.commit()
                conn.close()

                carregar_todos_pontos.clear()
                st.success("✅ Ponto cadastrado com sucesso!")
                st.rerun()

st.caption("🗺️ Mapa Cultural de Nossa Senhora do Socorro - SE • Desenvolvido com Streamlit, OpenStreetMap, OpenAI e Folium")