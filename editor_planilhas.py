# --- Requisitos ---
# pip install streamlit pandas openpyxl

import streamlit as st
import pandas as pd
import os
from zipfile import ZipFile
import io

# --- Configuração da Página ---
st.set_page_config(page_title="Editor de Planilhas Pro", page_icon="📋", layout="wide")

# --- Funções Auxiliares ---
def converter_df_para_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def carregar_arquivo(arquivo_carregado, nome_original=None):
    nome_do_arquivo = nome_original if nome_original else arquivo_carregado.name
    try:
        extensao = os.path.splitext(nome_do_arquivo)[1].lower()
        if extensao == '.csv':
            try:
                df = pd.read_csv(arquivo_carregado, encoding='utf-8', sep=None, engine='python')
            except (UnicodeDecodeError, pd.errors.ParserError):
                df = pd.read_csv(arquivo_carregado, encoding='latin1', sep=None, engine='python')
        elif extensao in ['.xlsx', '.xls']:
            df = pd.read_excel(arquivo_carregado)
        else:
            st.warning(f"Formato não suportado: {nome_do_arquivo}")
            return None
        df.dropna(how='all', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao ler '{nome_do_arquivo}': {e}")
        return None

# --- Inicialização ---
if 'dados_modificados' not in st.session_state:
    st.session_state.dados_modificados = {}
if 'busca_resultados' not in st.session_state:
    st.session_state.busca_resultados = []
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = []
if 'select_all' not in st.session_state:
    st.session_state.select_all = False

# --- Sidebar ---
with st.sidebar:
    st.title("🗂️ Editor de Planilhas")
    arquivos_carregados = st.file_uploader(
        "Selecione arquivos CSV/XLSX ou um ZIP:",
        type=['csv', 'xlsx', 'xls', 'zip'],
        accept_multiple_files=True,
        key="file_uploader"
    )

    current_file_names = [f.name for f in arquivos_carregados] if arquivos_carregados else []

    if arquivos_carregados and set(current_file_names) != set(st.session_state.processed_files):
        dados_originais = {}
        st.session_state.dados_modificados = {}
        st.session_state.busca_resultados = []

        for arquivo in arquivos_carregados:
            if arquivo.name.lower().endswith('.zip'):
                with ZipFile(arquivo) as zip_ref:
                    for nome_arquivo_no_zip in zip_ref.namelist():
                        if nome_arquivo_no_zip.lower().endswith(('.csv', '.xlsx', '.xls')):
                            with zip_ref.open(nome_arquivo_no_zip) as arquivo_zipado:
                                df = carregar_arquivo(io.BytesIO(arquivo_zipado.read()), nome_original=nome_arquivo_no_zip)
                                if df is not None:
                                    dados_originais[nome_arquivo_no_zip] = df
            else:
                df = carregar_arquivo(arquivo)
                if df is not None:
                    dados_originais[arquivo.name] = df
        
        for nome, df_original in dados_originais.items():
            st.session_state.dados_modificados[nome] = df_original.copy()
        
        st.session_state.processed_files = current_file_names
        st.rerun()

# --- Interface Principal ---
st.title("📈 Editor e Localizador de Dados")

if not st.session_state.get('dados_modificados'):
    st.info("👋 Por favor, selecione um ou mais arquivos na barra lateral para começar.")
    st.stop()

# --- Abas de Visualização ---
nomes_dos_arquivos = list(st.session_state.dados_modificados.keys())
if nomes_dos_arquivos:
    abas = st.tabs([f"📄 {nome}" for nome in nomes_dos_arquivos])
    for i, aba in enumerate(abas):
        with aba:
            st.dataframe(st.session_state.dados_modificados[nomes_dos_arquivos[i]], use_container_width=True)

# --- Busca Múltipla ---
st.header("🔎 Buscar Registros")
entrada_busca = st.text_area("Cole aqui um ou mais números/termos (vírgula, espaço ou quebra de linha):")

if st.button("🔍 Buscar"):
    termos_busca = [t.strip() for t in entrada_busca.replace(",", "\n").split("\n") if t.strip()]
    st.session_state.busca_resultados = []
    st.session_state.select_all = False

    for nome_arquivo, df in st.session_state.dados_modificados.items():
        try:
            if termos_busca:
                condicao_total = pd.Series([False] * len(df))
                for termo in termos_busca:
                    condicao = df.apply(lambda col: col.astype(str).str.contains(termo, case=False, na=False))
                    condicao_total = condicao_total | condicao.any(axis=1)
                encontrados = df[condicao_total]
            else:
                encontrados = df[df.isnull().all(axis=1)]

            for idx, row in encontrados.iterrows():
                st.session_state.busca_resultados.append({
                    'nome_arquivo': nome_arquivo,
                    'index': idx,
                    'registro': row
                })
        except Exception as e:
            st.error(f"Erro na busca em {nome_arquivo}: {e}")
    st.rerun()

# --- Resultados ---
if st.session_state.get('busca_resultados'):
    st.markdown("---")
    st.header("🌟 Resultados da Busca")
    resultados_validos = [res for res in st.session_state.busca_resultados if res['index'] in st.session_state.dados_modificados.get(res['nome_arquivo'], pd.DataFrame()).index]

    if not resultados_validos:
        st.warning("Resultados inválidos. Busque novamente.")
        st.session_state.busca_resultados = []
    else:
        st.info(f"✨ {len(resultados_validos)} registro(s) encontrado(s).")
        st.checkbox("Selecionar/Deselecionar Todos", key="select_all")

        selecionados = []
        for res in resultados_validos:
            chave_unica = f"{res['nome_arquivo']}_{res['index']}"
            registro_str = ', '.join([f"{k}: {str(v)[:30]}" for k, v in res['registro'].items()])
            if st.checkbox(f"[{res['index']}] '{res['nome_arquivo']}' -> `{registro_str}`", value=st.session_state.select_all, key=f"cb_{chave_unica}"):
                selecionados.append(res)

        if selecionados:
            acao = st.radio("O que deseja fazer?", ("Nenhuma", "Excluir todos", "Editar todos"), horizontal=True)

            # Exclusão (já estava funcionando)
            if acao == "Excluir todos":
                if st.button("🗑️ Confirmar Exclusão"):
                    para_excluir_por_arquivo = {}
                    for item in selecionados:
                        para_excluir_por_arquivo.setdefault(item['nome_arquivo'], []).append(item['index'])
                    for nome_arquivo, indices in para_excluir_por_arquivo.items():
                        df_modificado = st.session_state.dados_modificados[nome_arquivo]
                        df_modificado.drop(indices, inplace=True)
                        st.session_state.dados_modificados[nome_arquivo] = df_modificado.reset_index(drop=True)
                    st.session_state.busca_resultados = []
                    st.success(f"{len(selecionados)} registro(s) excluído(s).")
                    st.rerun()

            # Edição em Lote
            elif acao == "Editar todos":
                with st.form("form_edit_lote"):
                    colunas_unicas = set()
                    for item in selecionados:
                        colunas_unicas.update(st.session_state.dados_modificados[item['nome_arquivo']].columns)

                    novos_valores = {}
                    for coluna in sorted(colunas_unicas):
                        novos_valores[coluna] = st.text_input(f"Novo valor para '{coluna}' (em branco = não alterar):")

                    if st.form_submit_button("💾 Salvar Alterações"):
                        for item in selecionados:
                            df_modificado = st.session_state.dados_modificados[item['nome_arquivo']]
                            for coluna, novo_valor in novos_valores.items():
                                if novo_valor != "" and coluna in df_modificado.columns:
                                    try:
                                        tipo_original = df_modificado[coluna].dtype
                                        valor_convertido = pd.Series([novo_valor]).astype(tipo_original).iloc[0]
                                        df_modificado.at[item['index'], coluna] = valor_convertido
                                    except (ValueError, TypeError):
                                        df_modificado.at[item['index'], coluna] = novo_valor
                        st.success(f"{len(selecionados)} registros atualizados com sucesso!")
                        st.session_state.busca_resultados = []
                        st.rerun()

# --- Download ---
if st.session_state.dados_modificados:
    st.markdown("---")
    st.header("📥 Baixar Planilhas Modificadas")
    for nome_arquivo, df in st.session_state.dados_modificados.items():
        st.download_button(
            label=f"⬇️ Baixar {os.path.splitext(nome_arquivo)[0]}_modificado.csv",
            data=converter_df_para_csv(df),
            file_name=f"{os.path.splitext(nome_arquivo)[0]}_modificado.csv",
            mime="text/csv"
        )
