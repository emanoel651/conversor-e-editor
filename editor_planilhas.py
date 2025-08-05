import streamlit as st
import pandas as pd
import os
from zipfile import ZipFile

# --- Configuração da Página ---
st.set_page_config(
    page_title="Editor de Planilhas Pro",
    page_icon="📋",
    layout="wide"
)

# --- Funções Auxiliares ---
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

# --- Inicialização do Session State ---
for key in ['dados_originais', 'dados_modificados', 'busca_resultados']:
    if key not in st.session_state:
        st.session_state[key] = {}

# --- Barra Lateral ---
with st.sidebar:
    st.title("🗂️ Editor de Planilhas")
    st.markdown("---")

    arquivos_carregados = st.file_uploader(
        "Selecione arquivos CSV/XLSX ou um ZIP contendo planilhas:",
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

# --- Conteúdo Principal ---
st.title("📈 Editor e Localizador de Dados")

if not st.session_state['dados_originais']:
    st.info("👋 Por favor, selecione arquivos para continuar.")
    st.stop()

nomes_arquivos = list(st.session_state['dados_originais'].keys())
st.session_state['dados_modificados'] = st.session_state['dados_modificados'] or {
    nome: df.copy() for nome, df in st.session_state['dados_originais'].items()
}

abas = st.tabs([f"📄 {nome}" for nome in nomes_arquivos])
for i, aba in enumerate(abas):
    with aba:
        nome_arquivo = nomes_arquivos[i]
        df_exibir = st.session_state['dados_modificados'][nome_arquivo]
        st.dataframe(df_exibir, use_container_width=True)

# --- Busca ---
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

if st.session_state['busca_resultados']:
    st.markdown("---")
    st.subheader("🌟 Resultados Encontrados")
    opcoes = [
        f"{i+1}. {r['registro'].to_dict()} (Arquivo: {r['nome_arquivo']})"
        for i, r in enumerate(st.session_state['busca_resultados'])
    ]
    selecao = st.radio("Selecione um registro:", opcoes)
    selecionado = st.session_state['busca_resultados'][opcoes.index(selecao)]

    nome_arquivo = selecionado['nome_arquivo']
    idx = selecionado['index']
    df_mod = st.session_state['dados_modificados'][nome_arquivo]

    acao = st.radio("Ação:", ["Nenhuma", "Editar", "Excluir"], horizontal=True)

    if acao == "Excluir":
        if st.button("🗑️ Confirmar Exclusão"):
            df_mod = df_mod.drop(idx).reset_index(drop=True)
            st.session_state['dados_modificados'][nome_arquivo] = df_mod
            st.success("Registro excluído com sucesso!")
            st.rerun()

    elif acao == "Editar":
        colunas = df_mod.columns.tolist()
        coluna = st.selectbox("Coluna para editar:", colunas)
        valor_atual = df_mod.loc[idx, coluna]
        novo_valor = st.text_input("Novo valor:", str(valor_atual))
        if st.button("📏 Salvar Edição"):
            try:
                tipo = df_mod[coluna].dtype
                valor_convertido = pd.Series([novo_valor]).astype(tipo).iloc[0]
            except:
                valor_convertido = novo_valor
            df_mod.at[idx, coluna] = valor_convertido
            st.session_state['dados_modificados'][nome_arquivo] = df_mod
            st.success("Registro editado com sucesso!")
            st.rerun()

# --- Download ---
if st.session_state['dados_modificados']:
    st.markdown("---")
    st.header("📥 Baixar Planilhas Modificadas")
    for nome_arquivo, df in st.session_state['dados_modificados'].items():
        csv = obter_csv_binario_para_download(df)
        nome_final = f"{os.path.splitext(nome_arquivo)[0]}_modificado.csv"
        st.download_button(
            f"⬇️ Baixar {nome_final}",
            data=csv,
            file_name=nome_final,
            mime="text/csv"
        )
