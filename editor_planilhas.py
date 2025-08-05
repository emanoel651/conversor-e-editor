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

# --- Ações ---
if st.session_state.busca_resultados:
    st.markdown("---")
    st.header("🌟 2. Resultados da Busca")
    st.info(f"✨ Foram encontrados {len(st.session_state.busca_resultados)} registros. Selecione um para editar ou excluir.")

    opcoes_radio = [f"{i+1}. {a['registro'].to_dict()} (Planilha: {a['nome_arquivo']})" for i, a in enumerate(st.session_state.busca_resultados)]
    selecao_usuario = st.radio("🔎 Selecione o registro que deseja manipular:", options=opcoes_radio, key="selecao_de_registro")

    indice_selecionado = opcoes_radio.index(selecao_usuario)
    resultado_escolhido = st.session_state.busca_resultados[indice_selecionado]

    registro_encontrado = resultado_escolhido["registro"]
    nome_arquivo_encontrado = resultado_escolhido["nome_arquivo"]
    df_para_modificar = st.session_state.dados_modificados.get(nome_arquivo_encontrado, st.session_state.dados_originais[nome_arquivo_encontrado])
    index_registro = registro_encontrado.name

    st.subheader("✏️ 3. Ação sobre o Registro Selecionado")
    acao = st.radio("O que você deseja fazer?", ("Nenhuma", "Excluir o registro", "Editar o registro"), horizontal=True)

    if acao == "Excluir o registro":
        st.warning("Atenção! Esta ação removerá a linha inteira.")
        if st.button("🗑️ Confirmar Exclusão", key="confirmar_exclusao"):
            df_modificado = df_para_modificar.drop(index_registro).reset_index(drop=True)
            st.session_state.dados_modificados[nome_arquivo_encontrado] = df_modificado
            st.success(f"✅ Registro excluído de '{nome_arquivo_encontrado}'!")
            st.rerun()

    elif acao == "Editar o registro":
        colunas_disponiveis = df_para_modificar.columns.tolist()
        coluna_para_editar = st.selectbox("Escolha a coluna para editar:", options=colunas_disponiveis)
        valor_atual = registro_encontrado[coluna_para_editar]
        novo_valor = st.text_input(f"Digite o novo valor para '{coluna_para_editar}':", value=str(valor_atual))

        if st.button("📏 Salvar Alteração", key="salvar_edicao"):
            df_modificado = df_para_modificar.copy()
            try:
                tipo_original = df_modificado[coluna_para_editar].dtype
                novo_valor_convertido = pd.Series([novo_valor]).astype(tipo_original).iloc[0]
                df_modificado.at[index_registro, coluna_para_editar] = novo_valor_convertido
            except Exception:
                df_modificado.at[index_registro, coluna_para_editar] = novo_valor

            st.session_state.dados_modificados[nome_arquivo_encontrado] = df_modificado
            st.success(f"✅ Registro editado em '{nome_arquivo_encontrado}'!")
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

