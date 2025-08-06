import streamlit as st
import pandas as pd
import os
from zipfile import ZipFile

st.set_page_config(page_title="Editor de Planilhas Pro", page_icon="📋", layout="wide")

# Funções
@st.cache_data
def converter_df_para_csv(df):
    return df.to_csv(index=False)

def obter_csv_binario_para_download(df):
    csv_texto = converter_df_para_csv(df)
    return csv_texto.encode('utf-8')

def carregar_arquivo(arquivo_carregado, nome=None):
    try:
        extensao = os.path.splitext(arquivo_carregado.name if not nome else nome)[1].lower()
        if extensao == '.csv':
            try:
                df = pd.read_csv(arquivo_carregado, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(arquivo_carregado, encoding='latin1')
        elif extensao in ['.xlsx', '.xls']:
            df = pd.read_excel(arquivo_carregado)
        else:
            return None
        df.dropna(how='all', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {nome or arquivo_carregado.name}: {e}")
        return None

# Session State
for key in ['dados_originais', 'dados_modificados', 'busca_resultados']:
    if key not in st.session_state:
        st.session_state[key] = {}

# Sidebar
with st.sidebar:
    st.title("🗂️ Editor de Planilhas")
    st.markdown("---")
    arquivos_carregados = st.file_uploader(
        "Selecione arquivos CSV/XLSX ou ZIP:",
        type=['csv', 'xlsx', 'xls', 'zip'],
        accept_multiple_files=True
    )

    if arquivos_carregados:
        st.session_state['dados_originais'].clear()
        st.session_state['dados_modificados'].clear()
        st.session_state['busca_resultados'].clear()

        for arquivo in arquivos_carregados:
            if arquivo.name.endswith('.zip'):
                with ZipFile(arquivo) as zip_ref:
                    for nome_arquivo in zip_ref.namelist():
                        if nome_arquivo.endswith(('.csv', '.xlsx', '.xls')):
                            with zip_ref.open(nome_arquivo) as arquivo_zipado:
                                df = carregar_arquivo(arquivo_zipado, nome=nome_arquivo)
                                if df is not None:
                                    st.session_state['dados_originais'][nome_arquivo] = df
            else:
                df = carregar_arquivo(arquivo)
                if df is not None:
                    st.session_state['dados_originais'][arquivo.name] = df

# Interface Principal
st.title("📈 Editor e Localizador de Dados")

if not st.session_state['dados_originais']:
    st.info("👋 Por favor, selecione arquivos para continuar.")
    st.stop()

# Inicializa dados modificados
if not st.session_state['dados_modificados']:
    for nome, df in st.session_state['dados_originais'].items():
        st.session_state['dados_modificados'][nome] = df.copy()

# Abas com planilhas
abas = st.tabs([f"📄 {nome}" for nome in st.session_state['dados_modificados']])
for i, aba in enumerate(abas):
    with aba:
        nome_arquivo = list(st.session_state['dados_modificados'].keys())[i]
        st.dataframe(st.session_state['dados_modificados'][nome_arquivo], use_container_width=True)

# Busca
st.header("🔎 Buscar Registros ou Linhas Vazias")
termo_busca = st.text_input("Digite o termo ou deixe vazio para buscar linhas vazias:")

if st.button("🔍 Buscar"):
    st.session_state['busca_resultados'] = []
    for nome_arquivo, df in st.session_state['dados_modificados'].items():
        if termo_busca:
            condicoes = df.apply(lambda col: col.astype(str).str.contains(termo_busca, case=False, na=False))
            encontrados = df[condicoes.any(axis=1)]
        else:
            encontrados = df[df.isnull().all(axis=1)]

        for idx, row in encontrados.iterrows():
            st.session_state['busca_resultados'].append({
                'nome_arquivo': nome_arquivo,
                'index': idx,
                'registro': row
            })

# Resultados da busca
if st.session_state['busca_resultados']:
    st.markdown("---")
    st.header("🌟 Resultados da Busca")
    st.info(f"✨ {len(st.session_state.busca_resultados)} registros encontrados.")

    opcoes_radio = [
        f"{i+1}. {a['registro'].to_dict()} (Planilha: {a['nome_arquivo']})"
        for i, a in enumerate(st.session_state['busca_resultados'])
    ]
    selecao_usuario = st.radio("🔎 Selecione o registro:", options=opcoes_radio)

    indice_selecionado = opcoes_radio.index(selecao_usuario)
    resultado_escolhido = st.session_state['busca_resultados'][indice_selecionado]

    nome_arquivo_encontrado = resultado_escolhido["nome_arquivo"]
    index_registro = resultado_escolhido["index"]
    df_modificado = st.session_state['dados_modificados'][nome_arquivo_encontrado]

     st.subheader("✏️ Ação sobre o Registro")
    acao = st.radio("O que deseja fazer?", ("Nenhuma", "Excluir o registro", "Editar o registro"), horizontal=True)

    if acao == "Excluir o registro":
        st.warning("⚠️ Esta ação removerá a linha inteira.")
        if st.button("🗑️ Confirmar Exclusão"):
            df_modificado = df_modificado.drop(index_registro)
            st.session_state['dados_modificados'][nome_arquivo_encontrado] = df_modificado
            st.success("✅ Registro excluído!")
            st.rerun()

    elif acao == "Editar o registro":
        colunas = df_modificado.columns.tolist()
        nome_editavel = 'Nome' in colunas
        numero_editavel = 'Número' in colunas

        if nome_editavel:
            valor_nome = df_modificado.at[index_registro, 'Nome']
            novo_nome = st.text_input("✏️ Novo valor para 'Nome':", value=str(valor_nome))
        else:
            novo_nome = None
            st.warning("⚠️ A coluna 'Nome' não foi encontrada.")

        if numero_editavel:
            valor_numero = df_modificado.at[index_registro, 'Número']
            novo_numero = st.text_input("🔢 Novo valor para 'Número':", value=str(valor_numero))
        else:
            novo_numero = None
            st.warning("⚠️ A coluna 'Número' não foi encontrada.")

        if st.button("📏 Salvar Alterações"):
            if nome_editavel:
                try:
                    tipo_nome = df_modificado['Nome'].dtype
                    df_modificado.at[index_registro, 'Nome'] = pd.Series([novo_nome]).astype(tipo_nome).iloc[0]
                except Exception:
                    df_modificado.at[index_registro, 'Nome'] = novo_nome

            if numero_editavel:
                try:
                    tipo_numero = df_modificado['Número'].dtype
                    df_modificado.at[index_registro, 'Número'] = pd.Series([novo_numero]).astype(tipo_numero).iloc[0]
                except Exception:
                    df_modificado.at[index_registro, 'Número'] = novo_numero

            st.session_state['dados_modificados'][nome_arquivo_encontrado] = df_modificado
            st.success("✅ Registro atualizado com sucesso!")
            st.rerun()
# Download
if st.session_state['dados_modificados']:
    st.markdown("---")
    st.header("📥 Baixar Planilhas Modificadas")
    for nome_arquivo, df in st.session_state['dados_modificados'].items():
        csv = obter_csv_binario_para_download(df)
        nome_final = f"{os.path.splitext(nome_arquivo)[0]}_modificado.csv"
        st.download_button(
            label=f"⬇️ Baixar {nome_final}",
            data=csv,
            file_name=nome_final,
            mime="text/csv"
        )

