# 🗺️ Mapa de Nossa Senhora do Socorro

Mapa interativo de Nossa Senhora do Socorro-SE usando Python, Streamlit, Folium, OpenStreetMap e SQLite.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + Streamlit Cloud

1. Crie um repositório no GitHub.
2. Envie `app.py` e `requirements.txt`.
3. No Streamlit Community Cloud, escolha o repositório.
4. Se usar a SergIA, adicione `OPENAI_API_KEY` nos Secrets.

## Google My Maps

O aplicativo possui botões para gerar CSV e KML.

No Google My Maps:
- crie um mapa;
- adicione uma camada;
- escolha Importar;
- envie o CSV ou KML gerado pelo aplicativo.

## Observação

Os pontos do OpenStreetMap dependem do que está cadastrado no banco de dados do OpenStreetMap e podem estar incompletos ou desatualizados.
