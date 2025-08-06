import streamlit as st
import pandas as pd
import os
from zipfile import ZipFile
import io  # Necessário para ler arquivos de dentro do ZIP

# --- Configuração da Página ---
st.set_page_config(page_title="Editor de Planilhas Pro", page_icon="📋", layout="wide")

# --- Funções Auxiliares ---
@st.cache_data
def converter_df_para_csv(df):
    """Converte um DataFrame para uma string CSV em memória."""
    return df.to_csv(index=False).encode('utf-8')

def carregar_arquivo(arquivo_carregado, nome_original=None):
    """Lê um arquivo CSV ou Excel e o retorna como um DataFrame pandas."""
    nome_do_arquivo = nome_original if nome_original else arquivo_carregado.name
    try:
        extensao = os.path.splitext(nome_do_arquivo)[1].lower()
        if extensao == '.csv':
            try:
                # Tenta ler com UTF-8, o padrão mais comum
                df = pd.read_csv(arquivo_carregado, encoding='utf-8')
            except UnicodeDecodeError:
                # Se falhar, tenta com latin1, comum em sistemas mais antigos
                df = pd.read_csv(arquivo_carregado, encoding='latin1')
        elif extensao in ['.xlsx', '.xls']:
            df = pd.read_excel(arquivo_carregado)
        else:
            st.warning(f"Formato de arquivo não suportado: {nome_do_arquivo}")
            return None
        
        # Remove linhas que são completamente vazias
        df.dropna(how='all', inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo '{nome_do_arquivo}': {e}")
        return None

# --- Inicialização do Session State ---
# Garante que as chaves existem na sessão para evitar erros
for key in ['dados_originais', 'dados_modificados', 'busca_resultados', 'selecao_atual']:
    if key not in st.session_state:
        st.session_state[key] = {} if key != 'busca_resultados' else []

# --- Barra Lateral (Sidebar) para Upload ---
with st.sidebar:
    st.title("🗂️ Editor de Planilhas")
    st.markdown("---")
    arquivos_carregados = st.file_uploader(
        "Selecione arquivos CSV/XLSX ou um ZIP:",
        type=['csv', 'xlsx', 'xls', 'zip'],
        accept_multiple_files=True
    )

    if arquivos_carregados:
        # Limpa os dados antigos sempre que novos arquivos são carregados
        st.session_state['dados_originais'].clear()
        st.session_state['dados_modificados'].clear()
        st.session_state['busca_resultados'] = []

        for arquivo in arquivos_carregados:
            if arquivo.name.lower().endswith('.zip'):
                with ZipFile(arquivo) as zip_ref:
                    for nome_arquivo_no_zip in zip_ref.namelist():
                        # Processa apenas arquivos de planilha dentro do ZIP
                        if nome_arquivo_no_zip.lower().endswith(('.csv', '.xlsx', '.xls')):
                            with zip_ref.open(nome_arquivo_no_zip) as arquivo_zipado:
                                # A leitura de arquivos em memória requer um wrapper
                                df = carregar_arquivo(io.BytesIO(arquivo_zipado.read()), nome_original=nome_arquivo_no_zip)
                                if df is not None:
                                    st.session_state['dados_originais'][nome_arquivo_no_zip] = df
            else:
                df = carregar_arquivo(arquivo)
                if df is not None:
                    st.session_state['dados_originais'][arquivo.name] = df
        
        # Copia os dados originais para a área de modificação
        for nome, df_original in st.session_state['dados_originais'].items():
            st.session_state['dados_modificados'][nome] = df_original.copy()
        
        # Força o recarregamento para atualizar a interface com os novos arquivos
        st.rerun()


# --- Interface Principal ---
st.title("📈 Editor e Localizador de Dados")

if not st.session_state.get('dados_modificados'):
    st.info("👋 Por favor, selecione um ou mais arquivos na barra lateral para começar.")
    st.stop()

# --- Abas para Visualização das Planilhas ---
nomes_arquivos = list(st.session_state['dados_modificados'].keys())
abas = st.tabs([f"📄 {nome}" for nome in nomes_arquivos])
for i, aba in enumerate(abas):
    with aba:
        nome_arquivo = nomes_arquivos[i]
        st.dataframe(st.session_state['dados_modificados'][nome_arquivo], use_container_width=True)

# --- Seção de Busca ---
st.header("🔎 Buscar Registros")
termo_busca = st.text_input("Digite um termo para buscar em todas as planilhas. Deixe vazio para encontrar linhas totalmente em branco.")

if st.button("🔍 Buscar"):
    st.session_state['busca_resultados'] = []
    for nome_arquivo, df in st.session_state['dados_modificados'].items():
        if termo_busca:
            # Converte todo o DataFrame para string para uma busca case-insensitive
            condicao = df.apply(lambda col: col.astype(str).str.contains(termo_busca, case=False, na=False))
            encontrados = df[condicao.any(axis=1)]
        else:
            # Busca por linhas onde todas as colunas são nulas/vazias
            encontrados = df[df.isnull().all(axis=1)]

        for idx, row in encontrados.iterrows():
            st.session_state['busca_resultados'].append({
                'nome_arquivo': nome_arquivo,
                'index': idx,
                'registro': row
            })

# --- Seção de Resultados da Busca e Ações ---
if st.session_state['busca_resultados']:
    st.markdown("---")
    st.header("🌟 Resultados da Busca")
    st.info(f"✨ {len(st.session_state['busca_resultados'])} registro(s) encontrado(s).")

    # Gera as opções para o widget de seleção
    opcoes_radio = []
    for i, res in enumerate(st.session_state['busca_resultados']):
        # Limita o tamanho da string do registro para não poluir a interface
        registro_str = ', '.join([f"{k}: {str(v)[:20]}" for k, v in res['registro'].items()])
        opcoes_radio.append(f"{i+1}. [Índice: {res['index']}] em '{res['nome_arquivo']}' -> {registro_str}...")

    # Usando selectbox que é melhor para listas longas
    selecao_usuario = st.selectbox("🔎 Selecione o registro para tomar uma ação:", options=opcoes_radio, index=0)
    
    # Extrai o índice da seleção do usuário
    indice_selecionado = opcoes_radio.index(selecao_usuario)
    resultado_escolhido = st.session_state['busca_resultados'][indice_selecionado]

    nome_arquivo_encontrado = resultado_escolhido["nome_arquivo"]
    index_registro = resultado_escolhido["index"]
    df_modificado = st.session_state['dados_modificados'][nome_arquivo_encontrado]

    st.subheader("✏️ Ação sobre o Registro Selecionado")
    acao = st.radio("O que deseja fazer?", ("Nenhuma", "Excluir o registro", "Editar o registro"), horizontal=True, key=f"acao_{index_registro}")

    if acao == "Excluir o registro":
        st.warning(f"⚠️ Esta ação removerá permanentemente a linha de índice `{index_registro}` da planilha `{nome_arquivo_encontrado}`.")
        if st.button("🗑️ Confirmar Exclusão"):
            df_modificado.drop(index_registro, inplace=True)
            st.session_state['dados_modificados'][nome_arquivo_encontrado] = df_modificado
            
            # **CORREÇÃO CRÍTICA**: Limpa os resultados da busca para evitar erros
            st.session_state['busca_resultados'] = []
            
            st.success("✅ Registro excluído com sucesso!")
            st.rerun()

    elif acao == "Editar o registro":
        st.subheader(f"📝 Editando linha de índice `{index_registro}` em `{nome_arquivo_encontrado}`")
        linha_original = df_modificado.loc[index_registro]
        
        novos_valores = {}
        # Gera um campo de input para cada coluna da linha dinamicamente
        for coluna, valor_atual in linha_original.items():
            novos_valores[coluna] = st.text_input(
                f"Novo valor para '{coluna}':",
                value=str(valor_atual),
                key=f"edit_{nome_arquivo_encontrado}_{index_registro}_{coluna}" # Chave única
            )

        if st.button("💾 Salvar Alterações"):
            for coluna, novo_valor_str in novos_valores.items():
                try:
                    # Tenta converter o valor de volta ao tipo original da coluna
                    tipo_original = df_modificado[coluna].dtype
                    valor_convertido = pd.Series([novo_valor_str]).astype(tipo_original).iloc[0]
                    df_modificado.at[index_registro, coluna] = valor_convertido
                except (ValueError, TypeError):
                    # Se a conversão falhar, salva como texto (o input do usuário)
                    df_modificado.at[index_registro, coluna] = novo_valor_str
            
            st.session_state['dados_modificados'][nome_arquivo_encontrado] = df_modificado
            
            # **CORREÇÃO CRÍTICA**: Limpa os resultados da busca para evitar erros
            st.session_state['busca_resultados'] = []
            
            st.success("✅ Registro atualizado com sucesso!")
            st.rerun()


# --- Seção de Download das Planilhas Modificadas ---
if st.session_state['dados_modificados']:
    st.markdown("---")
    st.header("📥 Baixar Planilhas Modificadas")
    st.markdown("As planilhas modificadas serão salvas no formato CSV.")
    
    for nome_arquivo, df in st.session_state['dados_modificados'].items():
        nome_base = os.path.splitext(nome_arquivo)[0]
        nome_final = f"{nome_base}_modificado.csv"
        
        st.download_button(
            label=f"⬇️ Baixar {nome_final}",
            data=converter_df_para_csv(df),
            file_name=nome_final,
            mime="text/csv"
        )
