import streamlit as st
import pandas as pd
import os

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

def carregar_arquivo(arquivo_carregado):
    try:
        _, extensao = os.path.splitext(arquivo_carregado.name)
        if extensao == '.csv':
            df = pd.read_csv(arquivo_carregado)
        elif extensao in ['.xlsx', '.xls']:
            df = pd.read_excel(arquivo_carregado)
        else:
            return None

        # Remove linhas completamente vazias
        df.dropna(how='all', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {arquivo_carregado.name}: {e}")
        return None

# --- Inicialização do Session State ---
if 'dados_originais' not in st.session_state:
    st.session_state.dados_originais = {}
if 'dados_modificados' not in st.session_state:
    st.session_state.dados_modificados = {}
if 'busca_resultados' not in st.session_state:
    st.session_state.busca_resultados = []

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.title("🗂️ Editor de Planilhas")
    st.markdown("---")

    arquivos_carregados = st.file_uploader(
        "📂 1. Carregue suas planilhas",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True
    )

    if arquivos_carregados:
        novos_nomes = [f.name for f in arquivos_carregados]
        if set(novos_nomes) != set(st.session_state.dados_originais.keys()):
            st.session_state.dados_originais = {}
            st.session_state.dados_modificados = {}
            st.session_state.busca_resultados = []
            for arquivo in arquivos_carregados:
                st.session_state.dados_originais[arquivo.name] = carregar_arquivo(arquivo)

        arquivos_xlsx = [f for f in st.session_state.dados_originais.keys() if f.endswith(('.xlsx', '.xls'))]
        if arquivos_xlsx:
            st.header("⚙️ Conversor XLSX → CSV")
            xlsx_para_converter = st.selectbox("Selecione um arquivo XLSX para converter:", options=arquivos_xlsx)

            if xlsx_para_converter:
                df_para_converter = st.session_state.dados_originais.get(xlsx_para_converter)

                if df_para_converter is not None and isinstance(df_para_converter, pd.DataFrame):
                    csv_convertido = obter_csv_binario_para_download(df_para_converter)
                    st.download_button(
                        label="⬇️ Baixar CSV Convertido",
                        data=csv_convertido,
                        file_name=f"{os.path.splitext(xlsx_para_converter)[0]}.csv",
                        mime="text/csv"
                    )
                else:
                    st.error(f"❌ O arquivo '{xlsx_para_converter}' não pôde ser carregado corretamente como DataFrame.")

            st.markdown("---")

# --- Conteúdo Principal ---
st.title("📈 Editor e Localizador de Dados")

if not st.session_state.dados_originais:
    st.info("👋 Bem-vindo! Por favor, carregue uma ou mais planilhas na barra lateral para começar.")
    st.stop()

# Exibe todas as planilhas carregadas em abas
nomes_arquivos = list(st.session_state.dados_originais.keys())
abas = st.tabs([f"📄 {nome}" for nome in nomes_arquivos])
for i, aba in enumerate(abas):
    with aba:
        nome_arquivo_atual = nomes_arquivos[i]
        df_para_exibir = st.session_state.dados_modificados.get(nome_arquivo_atual, st.session_state.dados_originais.get(nome_arquivo_atual))
        if df_para_exibir is not None:
            st.dataframe(df_para_exibir, use_container_width=True)

# --- Seção de Pesquisa ---
st.header("🔎 1. Encontrar Registros ou Linhas Vazias")
termo_busca = st.text_input("Digite o termo que deseja encontrar:")

if st.button("Procurar em Todas as Planilhas"):
    st.session_state.busca_resultados = []
    lista_de_achados = []

    for nome_arquivo, df_original in st.session_state.dados_originais.items():
        df_busca = st.session_state.dados_modificados.get(nome_arquivo, df_original)

        if termo_busca:
            condicoes = df_busca.astype(str).apply(lambda col: col.str.contains(termo_busca, case=False, na=False))
            resultados_no_arquivo = df_busca[condicoes.any(axis=1)]
        else:
            resultados_no_arquivo = df_busca[df_busca.isnull().all(axis=1)]  # apenas linhas completamente vazias

        for index, row in resultados_no_arquivo.iterrows():
            lista_de_achados.append({"registro": row, "nome_arquivo": nome_arquivo})

    if lista_de_achados:
        st.session_state.busca_resultados = lista_de_achados
    else:
        st.warning("Nenhum registro correspondente ou linha vazia encontrada.")

# --- Seção de Ações ---
if st.session_state.busca_resultados:
    st.markdown("---")
    st.header("🌟 2. Resultados da Busca")
    st.info(f"✨ Foram encontrados {len(st.session_state.busca_resultados)} registros. Selecione um para editar ou excluir.")

    opcoes_radio = [f"{a['registro'].to_dict()} (Planilha: {a['nome_arquivo']})" for a in st.session_state.busca_resultados]
    selecao_usuario = st.radio("🔎 Selecione o registro que deseja manipular:", options=opcoes_radio, key="selecao_de_registro")

    indice_selecionado = opcoes_radio.index(selecao_usuario)
    resultado_escolhido = st.session_state.busca_resultados[indice_selecionado]

    registro_encontrado = resultado_escolhido["registro"]
    nome_arquivo_encontrado = resultado_escolhido["nome_arquivo"]
    index_registro = registro_encontrado.name

    st.subheader("✏️ 3. Ação sobre o Registro Selecionado")

    df_para_modificar = st.session_state.dados_modificados.get(nome_arquivo_encontrado, st.session_state.dados_originais[nome_arquivo_encontrado])

    acao = st.radio("O que você deseja fazer?", ("Nenhuma", "Excluir o registro", "Editar o registro"), horizontal=True, key="acao_radio")

    if acao == "Excluir o registro":
        st.warning("Atenção! Esta ação removerá a linha inteira.")
        if st.button("🗑️ Confirmar Exclusão", type="primary"):
            df_modificado = df_para_modificar.drop(index_registro)
            st.session_state.dados_modificados[nome_arquivo_encontrado] = df_modificado
            st.session_state.busca_resultados = []
            st.success(f"✅ Registro excluído de '{nome_arquivo_encontrado}'! A visualização foi atualizada.")
            st.rerun()

    elif acao == "Editar o registro":
        colunas_disponiveis = df_para_modificar.columns.tolist()
        coluna_para_editar = st.selectbox("Escolha a coluna para editar:", options=colunas_disponiveis)
        valor_atual = registro_encontrado[coluna_para_editar]
        novo_valor = st.text_input(f"Digite o novo valor para '{coluna_para_editar}':", value=str(valor_atual), key=f"edit_{indice_selecionado}")

        if st.button("📏 Salvar Alteração"):
            df_modificado = df_para_modificar.copy()
            try:
                tipo_original = df_modificado[coluna_para_editar].dtype
                novo_valor_convertido = pd.Series([novo_valor]).astype(tipo_original).iloc[0]
                df_modificado.loc[index_registro, coluna_para_editar] = novo_valor_convertido
            except (ValueError, TypeError):
                df_modificado.loc[index_registro, coluna_para_editar] = novo_valor

            st.session_state.dados_modificados[nome_arquivo_encontrado] = df_modificado
            st.session_state.busca_resultados = []
            st.success(f"✅ Registro editado em '{nome_arquivo_encontrado}'! A visualização foi atualizada.")
            st.rerun()

# --- Seção de Download ---
if st.session_state.dados_modificados:
    st.markdown("---")
    st.header("📏 Baixar Planilhas Modificadas")
    for nome_arquivo, df_final in st.session_state.dados_modificados.items():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"Planilha modificada: `{nome_arquivo}`")
        with col2:
            csv_final = obter_csv_binario_para_download(df_final)
            nome_original, _ = os.path.splitext(nome_arquivo)
            nome_arquivo_final = f"{nome_original}_modificado.csv"
            st.download_button(
                label=f"⬇️ Baixar CSV",
                data=csv_final,
                file_name=nome_arquivo_final,
                mime="text/csv",
                key=f"download_{nome_arquivo}"
            )
