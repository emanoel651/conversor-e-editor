# --- Requisitos ---
# Para rodar este aplicativo, você precisa ter as seguintes bibliotecas instaladas:
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
    """Converte um DataFrame para uma string CSV em memória, codificada em UTF-8."""
    return df.to_csv(index=False).encode('utf-8')

def carregar_arquivo(arquivo_carregado, nome_original=None):
    """Lê um arquivo CSV ou Excel e o retorna como um DataFrame pandas."""
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
            st.warning(f"Formato de arquivo não suportado: {nome_do_arquivo}")
            return None
        
        df.dropna(how='all', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo '{nome_do_arquivo}': {e}")
        return None

# --- Inicialização do Session State ---
# Garante que as chaves existem na sessão para evitar erros
if 'dados_modificados' not in st.session_state:
    st.session_state.dados_modificados = {}
if 'busca_resultados' not in st.session_state:
    st.session_state.busca_resultados = []


# --- Barra Lateral (Sidebar) para Upload ---
with st.sidebar:
    st.title("🗂️ Editor de Planilhas")
    st.markdown("---")
    arquivos_carregados = st.file_uploader(
        "Selecione arquivos CSV/XLSX ou um ZIP:",
        type=['csv', 'xlsx', 'xls', 'zip'],
        accept_multiple_files=True,
        key="file_uploader"
    )

    if arquivos_carregados:
        # Limpa o estado anterior para carregar os novos arquivos
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
        
        # Copia os dados originais para a área de modificação
        for nome, df_original in dados_originais.items():
            st.session_state.dados_modificados[nome] = df_original.copy()
        
        # Limpa o uploader e recarrega a página para refletir as mudanças
        st.session_state.file_uploader = []
        st.rerun()


# --- Interface Principal ---
st.title("📈 Editor e Localizador de Dados")

if not st.session_state.get('dados_modificados'):
    st.info("👋 Por favor, selecione um ou mais arquivos na barra lateral para começar.")
    st.stop()

# --- Abas para Visualização das Planilhas ---
nomes_dos_arquivos = list(st.session_state.dados_modificados.keys())
if nomes_dos_arquivos:
    abas = st.tabs([f"📄 {nome}" for nome in nomes_dos_arquivos])
    for i, aba in enumerate(abas):
        with aba:
            nome_arquivo = nomes_dos_arquivos[i]
            st.dataframe(st.session_state.dados_modificados[nome_arquivo], use_container_width=True)

# --- Seção de Busca ---
st.header("🔎 Buscar Registros")
termo_busca = st.text_input("Digite um termo para buscar. Deixe vazio para encontrar linhas totalmente em branco.")

if st.button("🔍 Buscar"):
    st.session_state.busca_resultados = []
    for nome_arquivo, df in st.session_state.dados_modificados.items():
        try:
            if termo_busca:
                condicao = df.apply(lambda col: col.astype(str).str.contains(termo_busca, case=False, na=False))
                encontrados = df[condicao.any(axis=1)]
            else:
                encontrados = df[df.isnull().all(axis=1)]

            for idx, row in encontrados.iterrows():
                st.session_state.busca_resultados.append({
                    'nome_arquivo': nome_arquivo,
                    'index': idx,
                    'registro': row
                })
        except Exception as e:
            st.error(f"Ocorreu um erro durante a busca no arquivo {nome_arquivo}: {e}")
    # Força o rerun para atualizar a seção de resultados
    st.rerun()

# --- Seção de Resultados da Busca e Ações ---
if st.session_state.get('busca_resultados'):
    st.markdown("---")
    st.header("🌟 Resultados da Busca")
    
    resultados_validos = [res for res in st.session_state.busca_resultados if res['index'] in st.session_state.dados_modificados.get(res['nome_arquivo'], pd.DataFrame()).index]

    if not resultados_validos:
        st.warning("Os resultados da busca anterior não são mais válidos. Por favor, faça a busca novamente.")
        st.session_state.busca_resultados = []
    else:
        st.info(f"✨ {len(resultados_validos)} registro(s) encontrado(s).")
        
        opcoes_selecao = []
        for i, res in enumerate(resultados_validos):
            registro_str = ', '.join([f"{k}: {str(v)[:20]}" for k, v in res['registro'].items()])
            # Chave única para cada opção
            opcoes_selecao.append(f"{i+1}. [Índice: {res['index']}] em '{res['nome_arquivo']}' -> {registro_str}...")

        selecao_usuario = st.selectbox(
            "🔎 Selecione o registro para tomar uma ação:", 
            options=opcoes_selecao, 
            index=0,
            key="selecao_registro_busca"
        )
        
        indice_selecionado_na_lista = opcoes_selecao.index(selecao_usuario)
        resultado_escolhido = resultados_validos[indice_selecionado_na_lista]

        nome_arquivo_encontrado = resultado_escolhido["nome_arquivo"]
        index_registro = resultado_escolhido["index"]
        
        # Chave única combinando nome do arquivo e índice do registro
        chave_unica_registro = f"{nome_arquivo_encontrado}_{index_registro}"

        st.subheader("✏️ Ação sobre o Registro Selecionado")
        acao = st.radio(
            "O que deseja fazer?", 
            ("Nenhuma", "Excluir o registro", "Editar o registro"), 
            horizontal=True, 
            key=f"acao_{chave_unica_registro}" # BUGFIX: Chave única
        )

        if acao == "Excluir o registro":
            st.warning(f"⚠️ Esta ação removerá permanentemente a linha de índice `{index_registro}` da planilha `{nome_arquivo_encontrado}`.")
            if st.button("🗑️ Confirmar Exclusão", key=f"excluir_{chave_unica_registro}"):
                df_modificado = st.session_state.dados_modificados[nome_arquivo_encontrado]
                df_modificado.drop(index_registro, inplace=True)
                st.session_state.busca_resultados = [] # Limpa resultados obsoletos
                st.success("✅ Registro excluído com sucesso!")
                st.rerun()

        elif acao == "Editar o registro":
            st.subheader(f"📝 Editando linha de índice `{index_registro}` em `{nome_arquivo_encontrado}`")
            with st.form(key=f"form_edit_{chave_unica_registro}"):
                df_modificado = st.session_state.dados_modificados[nome_arquivo_encontrado]
                linha_original = df_modificado.loc[index_registro]
                novos_valores = {}
                
                for coluna, valor_atual in linha_original.items():
                    novos_valores[coluna] = st.text_input(
                        f"Novo valor para '{coluna}':",
                        value=str(valor_atual),
                        key=f"edit_input_{chave_unica_registro}_{coluna}"
                    )
                
                if st.form_submit_button("💾 Salvar Alterações"):
                    for coluna, novo_valor_str in novos_valores.items():
                        try:
                            tipo_original = df_modificado[coluna].dtype
                            valor_convertido = pd.Series([novo_valor_str]).astype(tipo_original).iloc[0]
                            df_modificado.at[index_registro, coluna] = valor_convertido
                        except (ValueError, TypeError):
                            df_modificado.at[index_registro, coluna] = novo_valor_str
                    
                    st.session_state.busca_resultados = [] # Limpa resultados obsoletos
                    st.success("✅ Registro atualizado com sucesso!")
                    st.rerun()

# --- Seção de Download ---
if st.session_state.dados_modificados:
    st.markdown("---")
    st.header("📥 Baixar Planilhas Modificadas")
    st.markdown("As planilhas modificadas serão salvas no formato CSV.")
    
    for nome_arquivo, df in st.session_state.dados_modificados.items():
        nome_base = os.path.splitext(nome_arquivo)[0]
        nome_final = f"{nome_base}_modificado.csv"
        
        st.download_button(
            label=f"⬇️ Baixar {nome_final}",
            data=converter_df_para_csv(df),
            file_name=nome_final,
            mime="text/csv",
            key=f"download_{nome_arquivo}"
        )
