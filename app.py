import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime

st.set_page_config(page_title="Inteligência de Mercado", page_icon="📊", layout="wide")

# --- FUNÇÕES DE FORMATAÇÃO PT-BR ---
def formatar_br(valor, moeda=False):
    if pd.isna(valor) or valor == '' or str(valor).lower() == 'nan': return ""
    try:
        texto = f"{float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {texto}" if moeda else texto
    except:
        return str(valor)

def formatar_data(val):
    if pd.isna(val) or str(val).strip() in ['', 'NaT', 'None', 'nan', 'NaTType']: return ""
    val_str = str(val).strip()
    if ' ' in val_str: val_str = val_str.split(' ')[0]
    if '-' in val_str:
        try:
            partes = val_str.split('-')
            if len(partes[0]) == 4: return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except: pass
    return val_str

def formatar_moeda_generica(val):
    if pd.isna(val) or val == '': return ""
    val_str = str(val).replace('R$', '').replace(' ', '').strip()
    try:
        if ',' in val_str and '.' in val_str: val_float = float(val_str.replace('.', '').replace(',', '.'))
        elif ',' in val_str: val_float = float(val_str.replace(',', '.'))
        else: val_float = float(val_str)
        return formatar_br(val_float, True)
    except:
        return str(val)

def formatar_percentual(val):
    if pd.isna(val) or val == '' or str(val).lower() in ['nan', 'none']: return ""
    val_str = str(val).strip()
    if '%' in val_str: 
        return val_str.replace('.', ',')
    try:
        return f"{float(val_str) * 100:.2f}%".replace('.', ',')
    except:
        return val_str

def formatar_peso(val):
    if pd.isna(val) or val == '' or str(val).lower() in ['nan', 'none']: return ""
    try:
        return f"{float(val):.3f}".replace('.', ',')
    except:
        return str(val).replace('.', ',')

def preparar_df_visual(df):
    df_vis = df.copy()
    cols_moeda = [c for c in df_vis.columns if any(x in c.lower() for x in ['compra', 'limite', 'capital', 'potencial'])]
    for col in cols_moeda:
        if col in df_vis.columns:
            df_vis[col] = df_vis[col].apply(lambda x: formatar_br(x, True))
            
    cols_data = [c for c in df_vis.columns if any(x in c.lower() for x in ['data', 'abertura', 'últ. compra', 'atualização', 'atualizacao'])]
    cols_data = [c for c in cols_data if 'média' not in c.lower() and 'media' not in c.lower()]
    for col in cols_data:
        if col in df_vis.columns:
            df_vis[col] = df_vis[col].apply(formatar_data)
            
    return df_vis

def obter_opcoes_unicas(df, coluna):
    if coluna not in df.columns: return []
    valores = [str(v).strip() for v in df[coluna].dropna().unique()]
    return sorted(list(set([v for v in valores if v and v.lower() != 'nan'])))

def unificar_endereco_receita(row):
    def limpa_texto(val):
        if pd.isna(val) or str(val).lower().strip() == 'nan': return ''
        return str(val).strip()

    partes = [
        f"{limpa_texto(row.get('logradouro'))} {limpa_texto(row.get('numero'))}".strip(),
        limpa_texto(row.get('complemento')),
        limpa_texto(row.get('bairro')),
        f"{limpa_texto(row.get('municipio'))}-{limpa_texto(row.get('uf'))}".strip('- '),
        f"CEP: {limpa_texto(row.get('cep'))}" if limpa_texto(row.get('cep')) else ""
    ]
    return " | ".join([p for p in partes if p and p != '-'])

# --- FUNÇÃO AUXILIAR PARA PARSER NUMÉRICO SEGURO NOS FILTROS ---
def limpar_numeric_safely(val):
    if pd.isna(val): return 0.0
    val_str = str(val).replace('R$', '').replace('%', '').replace(' ', '').strip().lower()
    if 'sem recomendação' in val_str or val_str == '': return 0.0
    try:
        if ',' in val_str and '.' in val_str:
            v = float(val_str.replace('.', '').replace(',', '.'))
        elif ',' in val_str:
            v = float(val_str.replace(',', '.'))
        else:
            v = float(val_str)
        return v
    except: return 0.0

@st.cache_data
def carregar_dados():
    df_c = pd.read_parquet('clientes_mestre.parquet')
    df_p = pd.read_parquet('produtos_mestre.parquet')
    
    df_c['Compra_Media_Num'] = pd.to_numeric(df_c['Compra Média Mensal 2026'], errors='coerce').fillna(0)
    if 'capital_social' in df_c.columns:
        df_c['Capital_Social_Num'] = pd.to_numeric(df_c['capital_social'], errors='coerce').fillna(0)
    
    df_c['Limite_Credito_Num'] = pd.to_numeric(df_c['Limite Crédito'], errors='coerce').fillna(0)
    
    for col_dt in ['Data Cadastro', 'Data Últ. Compra', 'Data Bloq.', 'data_conclusao', 'abertura', 'ultima_atualizacao']:
        if col_dt in df_c.columns:
            df_c[f'{col_dt}_dt'] = pd.to_datetime(df_c[col_dt], errors='coerce', dayfirst=True)
            
    df_c['Endereço Completo (Receita)'] = df_c.apply(unificar_endereco_receita, axis=1)
    
    def agrupar_localizacao_uni(row):
        cid = str(row.get('Cidade', '')).strip()
        bai = str(row.get('Bairro', '')).strip()
        if cid.lower() == 'nan': cid = ''
        if bai.lower() == 'nan': bai = ''
        res = f"{cid} - {bai}".strip(' -')
        return res if res else ''
        
    df_c['Localização (Unilever)'] = df_c.apply(agrupar_localizacao_uni, axis=1)
    
    # Formatação Refinada dos Produtos para Exibição Original
    for col in df_p.columns:
        cl = col.lower()
        if any(x in cl for x in ['preço', 'niv', 'valor', 'perna', 'pis/cofins total', 'venda média estado']):
            df_p[col] = df_p[col].apply(formatar_moeda_generica)
        elif any(x in cl for x in ['%', 'icms', 'margem', 'markup']):
            df_p[col] = df_p[col].apply(formatar_percentual)
        elif 'peso' in cl:
            df_p[col] = df_p[col].apply(formatar_peso)
            
    return df_c, df_p

df_clientes_raw, df_produtos_raw = carregar_dados()

# --- PREPARAÇÃO DE COLUNAS DE SUPORTE (FILTROS NUMÉRICOS) ---
df_produtos_proc = df_produtos_raw.copy()
num_cols_prod = [
    'Preço Unitário c/ ST', 'NIV por EAN', '4) Preço Caixa S/ST', '5) Preço Caixa C/ST',
    'Caixas por Pallet', 'Caixas por Camada', '1ª Perna do AT', 'Preço Máximo - Ponta',
    'Preço Médio - Ponta', 'Preço Promo - Ponta', 'Venda Média Estado RJ 2026 - Valor',
    'Venda Média RJ 2026 - Unidade', 'Venda Média RJ 2026 - Cxs', 'MARGEM   Pós Revisão'
]
for nc in num_cols_prod:
    if nc in df_produtos_proc.columns:
        df_produtos_proc[f'{nc}_Num_Filtro'] = df_produtos_proc[nc].apply(limpar_numeric_safely)

# Variável de Peso Bruto para Cálculos Logísticos
if 'Peso Bruto' in df_produtos_proc.columns:
    df_produtos_proc['Peso_Bruto_Num_Filtro'] = pd.to_numeric(df_produtos_proc['Peso Bruto'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

df_clientes_proc = df_clientes_raw.copy()

st.title("📊 Painel de Inteligência Comercial - Piloto Unilever")
st.subheader("Distribuidora Recreio Rio - Visão Integrada")
st.markdown("---")

# ==========================================
# BARRA LATERAL (FILTROS GLOBAIS)
# ==========================================
st.sidebar.header("🎯 Central de Filtros")
st.sidebar.caption("Campos em branco trazem todos os registros.")

df_f = df_clientes_proc.copy()
df_pf = df_produtos_proc.copy()

lista_cnpj_input = st.sidebar.text_area("Busca Global (Lista de CNPJs):", height=60)
if lista_cnpj_input:
    cnpjs_f = [''.join(filter(str.isdigit, l)).zfill(14) for l in lista_cnpj_input.replace(',', '\n').split('\n') if l.strip()]
    df_f = df_f[df_f['CNPJ_Limpo'].isin(cnpjs_f)]

with st.sidebar.expander("📦 Filtros Base Unilever", expanded=False):
    sel_razao_uni = st.multiselect("Razão Social (Unilever):", options=obter_opcoes_unicas(df_f, 'Razao'))
    if sel_razao_uni: df_f = df_f[df_f['Razao'].isin(sel_razao_uni)]
    
    input_cnpj_rede = st.text_input("CNPJ Rede (Lista separada por vírgula):")
    if input_cnpj_rede:
        redes_f = [x.strip() for x in input_cnpj_rede.split(',') if x.strip()]
        df_f = df_f[df_f['CNPJ_Rede'].astype(str).isin(redes_f)]
        
    sel_pdv_rede = st.multiselect("PDVS Rede:", options=obter_opcoes_unicas(df_f, 'PDVS_Rede'))
    if sel_pdv_rede: df_f = df_f[df_f['PDVS_Rede'].astype(str).isin(sel_pdv_rede)]
    
    sel_pdv_cav = st.multiselect("PDVS Cavalo:", options=obter_opcoes_unicas(df_f, 'PDVS_cavalo'))
    if sel_pdv_cav: df_f = df_f[df_f['PDVS_cavalo'].astype(str).isin(sel_pdv_cav)]
    
    sel_grupo_uni = st.multiselect("Grupo (Unilever):", options=obter_opcoes_unicas(df_f, 'Grupo'))
    if sel_grupo_uni: df_f = df_f[df_f['Grupo'].isin(sel_grupo_uni)]
    
    sel_cid_uni = st.multiselect("Cidade (Unilever):", options=obter_opcoes_unicas(df_f, 'Cidade'))
    if sel_cid_uni: df_f = df_f[df_f['Cidade'].isin(sel_cid_uni)]
    
    sel_bai_uni = st.multiselect("Bairro (Unilever):", options=obter_opcoes_unicas(df_f, 'Bairro'))
    if sel_bai_uni: df_f = df_f[df_f['Bairro'].isin(sel_bai_uni)]
    
    st.caption("Compra Média Mensal (R$)")
    cm_min, cm_max = st.columns(2)
    val_cm_min = cm_min.number_input("Min (R$)", value=0.0, step=500.0)
    val_cm_max = cm_max.number_input("Máx (R$)", value=float(df_clientes_raw['Compra_Media_Num'].max()), step=500.0)
    if val_cm_min > 0 or val_cm_max < float(df_clientes_raw['Compra_Media_Num'].max()):
        df_f = df_f[(df_f['Compra_Media_Num'] >= val_cm_min) & (df_f['Compra_Media_Num'] <= val_cm_max)]

with st.sidebar.expander("🏢 Filtros ERP (Recreio)", expanded=False):
    col_rz_rec = 'Razão Social/Nome' if 'Razão Social/Nome' in df_f.columns else 'Razao'
    sel_rz_rec = st.multiselect("Razão Social (Recreio):", options=obter_opcoes_unicas(df_f, col_rz_rec))
    if sel_rz_rec: df_f = df_f[df_f[col_rz_rec].isin(sel_rz_rec)]
    
    tp_pes = st.multiselect("Tipo Pessoa:", options=obter_opcoes_unicas(df_f, 'Tipo Pessoa'))
    if tp_pes: df_f = df_f[df_f['Tipo Pessoa'].isin(tp_pes)]
    
    ie_isento = st.radio("Inscrição Estadual:", ["Todos", "Isento", "Contribuinte"], horizontal=True)
    if ie_isento == "Isento": df_f = df_f[df_f['Insc. Est.'].astype(str).str.upper().str.strip() == 'ISENTO']
    elif ie_isento == "Contribuinte": df_f = df_f[(df_f['Insc. Est.'].astype(str).str.upper().str.strip() != 'ISENTO') & (df_f['Insc. Est.'].fillna('') != '')]
    
    in_ie = st.text_area("Lista de IEs:")
    if in_ie: df_f = df_f[df_f['Insc. Est.'].astype(str).isin([x.strip() for x in in_ie.split(',') if x.strip()])]
    
    def aplicar_filtro_dt(df, col, label, ch):
        if f'{col}_dt' in df.columns:
            st.caption(label)
            d1, d2 = st.columns(2)
            d_ini = d1.date_input("De", value=None, key=f"i_{ch}")
            d_fim = d2.date_input("Até", value=None, key=f"f_{ch}")
            if d_ini and d_fim:
                df = df[(df[f'{col}_dt'].dt.date >= d_ini) & (df[f'{col}_dt'].dt.date <= d_fim)]
        return df

    df_f = aplicar_filtro_dt(df_f, 'Data Cadastro', "Data Cadastro", "cad")
    df_f = aplicar_filtro_dt(df_f, 'Data Últ. Compra', "Data Últ. Compra", "ult")
    df_f = aplicar_filtro_dt(df_f, 'Data Bloq.', "Data Bloqueio", "blq")

    stat_sel = st.multiselect("Status no ERP:", options=obter_opcoes_unicas(df_f, 'Status_Recreio'))
    if stat_sel: df_f = df_f[df_f['Status_Recreio'].isin(stat_sel)]
    
    bloq_sel = st.multiselect("Bloqueado (S/N):", options=obter_opcoes_unicas(df_f, 'Bloq.'))
    if bloq_sel: df_f = df_f[df_f['Bloq.'].isin(bloq_sel)]
    
    col_cid_rec = 'Cidade_Recreio' if 'Cidade_Recreio' in df_f.columns else 'Cidade'
    cid_rec_sel = st.multiselect("Cidade (Recreio):", options=obter_opcoes_unicas(df_f, col_cid_rec))
    if cid_rec_sel: df_f = df_f[df_f[col_cid_rec].isin(cid_rec_sel)]
    
    st.caption("Limite Crédito (R$)")
    l_min, l_max = st.columns(2)
    val_l_min = l_min.number_input("Min Limite", value=0.0, step=500.0)
    val_l_max = l_max.number_input("Máx Limite", value=float(df_clientes_raw['Limite_Credito_Num'].max()), step=500.0)
    if val_l_min > 0 or val_l_max < float(df_clientes_raw['Limite_Credito_Num'].max()):
        df_f = df_f[(df_f['Limite_Credito_Num'] >= val_l_min) & (df_f['Limite_Credito_Num'] <= val_l_max)]

with st.sidebar.expander("🏛️ Filtros Receita Federal", expanded=False):
    df_f = aplicar_filtro_dt(df_f, 'data_conclusao', "Data Conclusão", "concl")
    df_f = aplicar_filtro_dt(df_f, 'abertura', "Data Abertura", "ab")
    df_f = aplicar_filtro_dt(df_f, 'ultima_atualizacao', "Últ. Atualização", "upd")
    
    nm = st.multiselect("Nome Empresarial:", options=obter_opcoes_unicas(df_f, 'nome'))
    if nm: df_f = df_f[df_f['nome'].isin(nm)]
    
    fan = st.multiselect("Nome Fantasia:", options=obter_opcoes_unicas(df_f, 'fantasia'))
    if fan: df_f = df_f[df_f['fantasia'].isin(fan)]
    
    sit_sel = st.multiselect("Situação Cadastral:", options=obter_opcoes_unicas(df_f, 'situacao'))
    if sit_sel: df_f = df_f[df_f['situacao'].isin(sit_sel)]
    
    for t_col in ['motivo_situacao', 'atividade_principal', 'atividade_secundaria', 'quadro_societario', 'logradouro', 'natureza_juridica']:
        if t_col in df_f.columns:
            txt = st.text_input(f"{t_col.replace('_',' ').capitalize()} (Contém):")
            if txt: df_f = df_f[df_f[t_col].astype(str).str.contains(txt, case=False, na=False)]
            
    cep = st.text_area("CEPs (Lista):")
    if cep: df_f = df_f[df_f['cep'].str.replace('-','').str.strip().isin([''.join(filter(str.isdigit, x)) for x in cep.split('\n') if x.strip()])]
    
    for s_col in ['tipo', 'porte', 'simples.optante', 'simei.optante']:
        if s_col in df_f.columns:
            sel = st.multiselect(f"{s_col.replace('.',' ').upper()}:", options=obter_opcoes_unicas(df_f, s_col))
            if sel: df_f = df_f[df_f[s_col].isin(sel)]
            
    st.caption("Capital Social (R$)")
    cs_min, cs_max = st.columns(2)
    val_cs_min = cs_min.number_input("Min Cap.", value=0.0, step=1000.0)
    val_cs_max = cs_max.number_input("Máx Cap.", value=float(df_clientes_raw['Capital_Social_Num'].max()), step=1000.0)
    if val_cs_min > 0 or val_cs_max < float(df_clientes_raw['Capital_Social_Num'].max()):
        df_f = df_f[(df_f['Capital_Social_Num'] >= val_cs_min) & (df_f['Capital_Social_Num'] <= val_cs_max)]

with st.sidebar.expander("📦 Filtros Portfólio de Produtos (Aba 5)", expanded=False):
    sel_desc = st.multiselect("Descrição do Produto:", options=obter_opcoes_unicas(df_pf, 'Descrição do Produto'))
    if sel_desc: df_pf = df_pf[df_pf['Descrição do Produto'].isin(sel_desc)]
    
    for code_col in ['Código DUN14', 'Código EAN', 'Código SKU']:
        if code_col in df_pf.columns:
            cd = st.text_area(f"{code_col} (Lista):", height=60)
            if cd: df_pf = df_pf[df_pf[code_col].astype(str).isin([x.strip() for x in cd.replace(',', '\n').split('\n') if x.strip()])]
    
    for m_col in ['Itens Por Caixas', 'Família', 'Categoria', 'Descrição PPA', 'MARGEM   Pós Revisão', 'MARKUP Pós Revisão', 'Eans Num C - Sugeridas']:
        if m_col in df_pf.columns:
            sel = st.multiselect(f"{m_col}:", options=obter_opcoes_unicas(df_pf, m_col))
            if sel: df_pf = df_pf[df_pf[m_col].astype(str).isin(sel)]
            
    for nc in num_cols_prod:
        if f'{nc}_Num_Filtro' in df_pf.columns:
            max_val = float(df_produtos_proc[f'{nc}_Num_Filtro'].max())
            if pd.isna(max_val) or max_val <= 0: max_val = 1000.0
            st.caption(f"{nc}")
            pn1, pn2 = st.columns(2)
            vmin = pn1.number_input("Mín", value=0.0, step=1.0, key=f"min_{nc}")
            vmax = pn2.number_input("Máx", value=max_val, step=1.0, key=f"max_{nc}")
            if vmin > 0 or vmax < max_val:
                df_pf = df_pf[(df_pf[f'{nc}_Num_Filtro'] >= vmin) & (df_pf[f'{nc}_Num_Filtro'] <= vmax)]

# ==========================================
# CÁLCULOS DE AGING E TEMPO DE MERCADO
# ==========================================
if 'Data Últ. Compra_dt' in df_f.columns:
    agora = pd.to_datetime('today')
    df_f['Dias_Ult_Compra'] = (agora - df_f['Data Últ. Compra_dt']).dt.days
    def classificar_aging(dias):
        if pd.isna(dias) or dias < 0: return 'Sem histórico de compra'
        if dias <= 30: return 'Até 30 dias'
        if dias <= 90: return '31 a 90 dias'
        if dias <= 180: return '91 a 180 dias'
        return 'Mais de 180 dias'
    df_f['Aging Vendas'] = df_f['Dias_Ult_Compra'].apply(classificar_aging)

if 'abertura_dt' in df_f.columns:
    df_f['Idade_Anos'] = (pd.to_datetime('today') - df_f['abertura_dt']).dt.days / 365.25
    def classificar_idade(anos):
        if pd.isna(anos) or anos < 0: return 'Não Informada'
        if anos < 1: return 'Menos de 1 ano'
        if anos <= 3: return '1 a 3 anos'
        if anos <= 5: return '4 a 5 anos'
        if anos <= 10: return '6 a 10 anos'
        return 'Mais de 10 anos'
    df_f['Tempo de Mercado'] = df_f['Idade_Anos'].apply(classificar_idade)

# ==========================================
# ABAS DO PAINEL
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Resumo Executivo (Tudo)", 
    "🎯 Análise da Base Alvo (Consolidada)", 
    "🏢 Dados ERP (Recreio)", 
    "🏛️ Dados Cadastrais (Receita)",
    "📦 Portfólio e Produtos"
])

def gerar_excel(df, nome_planilha):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=nome_planilha)
    return output.getvalue()

# ------------------------------------------
# 📈 ABA 1: RESUMO EXECUTIVO (INTELIGÊNCIA)
# ------------------------------------------
with tab1:
    st.header("Inteligência de Mercado e Resumos Consolidados")
    
    total_lojas = len(df_f)
    potencial_total = df_f['Compra_Media_Num'].sum()
    qtd_ativos = len(df_f[df_f['Status_Recreio'] == 'Ativo na Recreio']) if 'Status_Recreio' in df_f.columns else 0
    pct_cobertura = (qtd_ativos / total_lojas * 100) if total_lojas > 0 else 0
    potencial_prospects = df_f[df_f['Status_Recreio'] == 'Prospect (Sem Cadastro)']['Compra_Media_Num'].sum() if 'Status_Recreio' in df_f.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lojas no Alvo", formatar_br(total_lojas).replace(',00', ''))
    col2.metric("Potencial Mensal (Unilever)", formatar_br(potencial_total, True))
    col3.metric("Cobertura da Base (%)", f"{formatar_br(pct_cobertura).replace(',00', '').replace('.', ',')}%")
    col4.metric("Oportunidade (Prospects)", formatar_br(potencial_prospects, True))

    st.markdown("---")
    
    # 1. TABELAS DE STATUS E SITUAÇÃO
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("🏢 Status de Cadastro (Recreio)")
        if total_lojas > 0 and 'Status_Recreio' in df_f.columns:
            df_status = df_f.groupby('Status_Recreio').agg(Lojas=('CNPJ_Limpo', 'count'), Potencial=('Compra_Media_Num', 'sum')).reset_index()
            df_status = df_status.sort_values(by='Potencial', ascending=False)
            df_status['Potencial'] = df_status['Potencial'].apply(lambda x: formatar_br(x, True))
            df_status.rename(columns={'Status_Recreio': 'Status no ERP'}, inplace=True)
            st.dataframe(df_status, use_container_width=True, hide_index=True)
            
    with col_t2:
        st.subheader("🏛️ Situação Cadastral (Receita)")
        if total_lojas > 0 and 'situacao' in df_f.columns:
            df_sit = df_f.groupby('situacao').agg(Lojas=('CNPJ_Limpo', 'count'), Potencial=('Compra_Media_Num', 'sum')).reset_index()
            df_sit = df_sit.sort_values(by='Potencial', ascending=False)
            df_sit['Potencial'] = df_sit['Potencial'].apply(lambda x: formatar_br(x, True))
            df_sit.rename(columns={'situacao': 'Situação'}, inplace=True)
            st.dataframe(df_sit, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 2. LOCALIDADE: TABELA CIDADES E GRÁFICO BAIRROS
    col_loc1, col_loc2 = st.columns([1, 1.2])
    with col_loc1:
        st.subheader("📌 Resumo por Município")
        if total_lojas > 0 and 'municipio' in df_f.columns:
            df_cid = df_f.groupby('municipio').agg(Lojas=('CNPJ_Limpo', 'count'), Potencial=('Compra_Media_Num', 'sum')).reset_index()
            df_cid = df_cid.sort_values(by='Potencial', ascending=False)
            df_cid['Potencial'] = df_cid['Potencial'].apply(lambda x: formatar_br(x, True))
            df_cid.rename(columns={'municipio': 'Município'}, inplace=True)
            st.dataframe(df_cid, use_container_width=True, hide_index=True, height=400)
            
    with col_loc2:
        st.subheader("🗺️ Top 15 Bairros por Potencial")
        if total_lojas > 0 and 'bairro' in df_f.columns:
            top_bairros = df_f.groupby('bairro', as_index=False)['Compra_Media_Num'].sum().sort_values(by='Compra_Media_Num', ascending=True).tail(15)
            top_bairros['txt_br'] = top_bairros['Compra_Media_Num'].apply(lambda x: formatar_br(x, True))
            fig2 = px.bar(top_bairros, x='Compra_Media_Num', y='bairro', text='txt_br', orientation='h')
            fig2.update_traces(textposition='outside', marker_color='#2c3e50', cliponaxis=False, hovertemplate="<b>%{y}</b><br>Potencial: %{text}<extra></extra>")
            fig2.update_layout(separators=",.", xaxis=dict(showticklabels=False, title=''), yaxis=dict(title=''), margin=dict(r=120, t=10, b=10), height=400)
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    
    # 3. HEATMAP DE CANAIS X BAIRRO (INVERTIDO)
    st.subheader("📊 Concentração: Canais x Bairros")
    if total_lojas > 0 and 'Grupo' in df_f.columns and 'bairro' in df_f.columns:
        vis_hm = st.radio("Visualizar por:", ["Quantidade de Lojas", "Potencial de Compra (R$)"], horizontal=True)
        
        if vis_hm == "Quantidade de Lojas":
            # INVERSÃO: index=Grupo (Y), columns=bairro (X)
            df_heat = pd.crosstab(index=df_f['Grupo'], columns=df_f['bairro']).fillna(0)
            text_mat = df_heat.map(lambda x: f"{int(x)}" if x > 0 else "")
            hover_tpl = "<b>Canal:</b> %{y}<br><b>Bairro:</b> %{x}<br><b>Lojas:</b> %{customdata}<extra></extra>"
        else:
            # INVERSÃO: index=Grupo (Y), columns=bairro (X)
            df_heat = pd.crosstab(index=df_f['Grupo'], columns=df_f['bairro'], values=df_f['Compra_Media_Num'], aggfunc='sum').fillna(0)
            def fmt_k(val):
                if val == 0: return ""
                if val >= 1000000: return f"{val/1000000:.1f}M".replace('.', ',')
                if val >= 1000: return f"{val/1000:.1f}k".replace('.', ',')
                return formatar_br(val, False)
            text_mat = df_heat.map(fmt_k)
            hover_tpl = "<b>Canal:</b> %{y}<br><b>Bairro:</b> %{x}<br><b>Potencial:</b> %{customdata}<extra></extra>"

        if not df_heat.empty:
            # Cria hover com formatação BR exata
            hover_mat = df_heat.map(lambda x: formatar_br(x, True) if vis_hm != "Quantidade de Lojas" else str(int(x)))

            # Pega o Top 15 Bairros (COLUNAS)
            top_bairros_cols = df_heat.sum(axis=0).sort_values(ascending=False).head(15).index
            df_heat = df_heat[top_bairros_cols]
            text_mat = text_mat[top_bairros_cols]
            hover_mat = hover_mat[top_bairros_cols]
            
            # Ordena os Grupos (LINHAS) do maior pro menor
            df_heat = df_heat.loc[df_heat.sum(axis=1).sort_values(ascending=False).index]
            text_mat = text_mat.loc[df_heat.index]
            hover_mat = hover_mat.loc[df_heat.index]
            
            fig_h = px.imshow(
                df_heat, 
                text_auto=False, 
                aspect="auto", 
                color_continuous_scale="Teal",
                labels=dict(x="Bairro", y="Canal (Grupo)", color="Valor")
            )
            fig_h.update_traces(text=text_mat, customdata=hover_mat, texttemplate="%{text}", hovertemplate=hover_tpl)
            fig_h.update_layout(separators=",.", xaxis_tickangle=-45, xaxis_title="", yaxis_title="", margin=dict(t=10, b=10))
            st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("---")
    
    # 4. AGING E TEMPO DE MERCADO
    col_ag1, col_ag2 = st.columns(2)
    with col_ag1:
        st.subheader("⏳ Aging de Vendas (Última Compra)")
        if total_lojas > 0 and 'Aging Vendas' in df_f.columns:
            df_ag = df_f.groupby('Aging Vendas').agg(Lojas=('CNPJ_Limpo', 'count'), Potencial=('Compra_Media_Num', 'sum')).reset_index()
            ordem_aging = ['Até 30 dias', '31 a 90 dias', '91 a 180 dias', 'Mais de 180 dias', 'Sem histórico de compra']
            df_ag['Aging Vendas'] = pd.Categorical(df_ag['Aging Vendas'], categories=ordem_aging, ordered=True)
            df_ag = df_ag.sort_values(by='Aging Vendas')
            df_ag['Potencial'] = df_ag['Potencial'].apply(lambda x: formatar_br(x, True))
            st.dataframe(df_ag, use_container_width=True, hide_index=True)
            
    with col_ag2:
        st.subheader("🏢 Tempo de Mercado (Abertura)")
        if total_lojas > 0 and 'Tempo de Mercado' in df_f.columns:
            df_tm = df_f.groupby('Tempo de Mercado').agg(Lojas=('CNPJ_Limpo', 'count'), Potencial=('Compra_Media_Num', 'sum')).reset_index()
            ordem_idade = ['Menos de 1 ano', '1 a 3 anos', '4 a 5 anos', '6 a 10 anos', 'Mais de 10 anos', 'Não Informada']
            df_tm['Tempo de Mercado'] = pd.Categorical(df_tm['Tempo de Mercado'], categories=ordem_idade, ordered=True)
            df_tm = df_tm.sort_values(by='Tempo de Mercado')
            df_tm['Potencial'] = df_tm['Potencial'].apply(lambda x: formatar_br(x, True))
            st.dataframe(df_tm, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 5. GAP CRÉDITO E OPTANTES
    col_gc1, col_gc2, col_gc3 = st.columns([2, 1, 1])
    with col_gc1:
        st.subheader("⚠️ Gap de Crédito (Top 10 Ativos)")
        if 'Limite_Credito_Num' in df_f.columns and 'Status_Recreio' in df_f.columns:
            df_ativos = df_f[df_f['Status_Recreio'] == 'Ativo na Recreio'].copy()
            if len(df_ativos) > 0:
                df_ativos['Gap'] = df_ativos['Compra_Media_Num'] - df_ativos['Limite_Credito_Num']
                df_gap = df_ativos[df_ativos['Gap'] > 0][['Razao', 'Limite_Credito_Num', 'Compra_Media_Num']].copy()
                if len(df_gap) > 0:
                    df_gap = df_gap.sort_values(by='Compra_Media_Num', ascending=False).head(10)
                    df_gap['Limite_Credito_Num'] = df_gap['Limite_Credito_Num'].apply(lambda x: formatar_br(x, True))
                    df_gap['Compra_Media_Num'] = df_gap['Compra_Media_Num'].apply(lambda x: formatar_br(x, True))
                    df_gap.rename(columns={'Razao':'Lojista', 'Limite_Credito_Num':'Limite Atual', 'Compra_Media_Num':'Sugerido (Unilever)'}, inplace=True)
                    st.dataframe(df_gap, use_container_width=True, hide_index=True)
                else:
                    st.success("Sem Gaps de Crédito nesta seleção!")

    with col_gc2:
        st.subheader("Optante Simples")
        if total_lojas > 0 and 'simples.optante' in df_f.columns:
            df_simples = df_f['simples.optante'].replace('', 'NÃO INFORMADO').value_counts().reset_index()
            fig_s = px.pie(df_simples, values='count', names='simples.optante', hole=0.5, color_discrete_sequence=px.colors.qualitative.Set2)
            fig_s.update_traces(textinfo='label+percent', textposition='inside', hovertemplate="<b>%{label}</b><br>Lojas: %{value}<extra></extra>")
            fig_s.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig_s, use_container_width=True)

    with col_gc3:
        st.subheader("Optante Simei")
        if total_lojas > 0 and 'simei.optante' in df_f.columns:
            df_mei = df_f['simei.optante'].replace('', 'NÃO INFORMADO').value_counts().reset_index()
            fig_m = px.pie(df_mei, values='count', names='simei.optante', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_m.update_traces(textinfo='label+percent', textposition='inside', hovertemplate="<b>%{label}</b><br>Lojas: %{value}<extra></extra>")
            fig_m.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig_m, use_container_width=True)

    st.markdown("---")
    
    # 6. RAIO-X FISCAL
    st.subheader("🔍 Raio-X Fiscal (Perfil Categórico)")
    col_rx1, col_rx2, col_rx3, col_rx4 = st.columns(4)
    with col_rx1:
        if 'atividade_principal' in df_f.columns and total_lojas > 0:
            df_atv = df_f.groupby('atividade_principal').agg(Lojas=('CNPJ_Limpo', 'count')).reset_index().sort_values(by='Lojas', ascending=False).head(10)
            df_atv.rename(columns={'atividade_principal': 'Atividade Principal'}, inplace=True)
            st.dataframe(df_atv, use_container_width=True, hide_index=True)
    with col_rx2:
        if 'tipo' in df_f.columns and total_lojas > 0:
            df_tipo = df_f.groupby('tipo').agg(Lojas=('CNPJ_Limpo', 'count')).reset_index().sort_values(by='Lojas', ascending=False)
            df_tipo.rename(columns={'tipo': 'Matriz/Filial'}, inplace=True)
            st.dataframe(df_tipo, use_container_width=True, hide_index=True)
    with col_rx3:
        if 'porte' in df_f.columns and total_lojas > 0:
            df_pt = df_f.groupby('porte').agg(Lojas=('CNPJ_Limpo', 'count')).reset_index().sort_values(by='Lojas', ascending=False)
            df_pt.rename(columns={'porte': 'Porte'}, inplace=True)
            st.dataframe(df_pt, use_container_width=True, hide_index=True)
    with col_rx4:
        if 'natureza_juridica' in df_f.columns and total_lojas > 0:
            df_nat = df_f.groupby('natureza_juridica').agg(Lojas=('CNPJ_Limpo', 'count')).reset_index().sort_values(by='Lojas', ascending=False).head(10)
            df_nat.rename(columns={'natureza_juridica': 'Natureza Jurídica'}, inplace=True)
            st.dataframe(df_nat, use_container_width=True, hide_index=True)

# ------------------------------------------
# 🎯 ABA 2, 3 E 4 (Tabelas Base)
# ------------------------------------------
def gerar_df_visual_basico(df):
    d = df.copy()
    c_moeda = [c for c in d.columns if any(x in c.lower() for x in ['compra', 'limite', 'capital', 'potencial'])]
    for c in c_moeda:
        if c in d.columns: d[c] = d[c].apply(lambda x: formatar_br(x, True))
    c_data = [c for c in d.columns if any(x in c.lower() for x in ['data', 'abertura', 'compra', 'atualizacao', 'atualização', 'conclusao'])]
    c_data = [c for c in c_data if 'média' not in c.lower() and 'media' not in c.lower()]
    for c in c_data:
        if c in d.columns: d[c] = d[c].apply(formatar_data)
    return d

with tab2:
    st.header("Análise da Base Alvo (Consolidada)")
    colunas_mestre = [
        'CNPJ_Limpo', 'Razao', 'fantasia', 'situacao', 'Status_Recreio', 'Grupo', 'PDVS_Rede', 'PDVS_cavalo',
        'Compra Média Mensal 2026', 'Compra_Media_Num', 'Limite Crédito',
        'Localização (Unilever)', 'Endereço Completo (Receita)', 'telefone', 'email', 'Telefone_Recreio',
        'Data Cadastro', 'Cód.', 'Insc. Est.', 'Data Últ. Compra', 'Bloq.', 'Data Bloq.',
        'abertura', 'ultima_atualizacao', 'atividade_principal', 'tipo', 'porte', 'capital_social', 
        'simples.optante', 'simei.optante', 'natureza_juridica', 'quadro_societario'
    ]
    nomes_amigaveis = {
        'Razao': 'Razão Social', 'fantasia': 'Nome Fantasia', 'situacao': 'Situação',
        'Status_Recreio': 'Status', 'Compra Média Mensal 2026': 'Potencial Sugerido',
        'Localização (Unilever)': 'Localização', 'telefone': 'Telefone (Receita)', 'email': 'E-mail (Receita)',
        'Telefone_Recreio': 'Telefone (ERP)', 'Data Cadastro': 'Data Cadastro', 'Cód.': 'Cód ERP',
        'Insc. Est.': 'IE', 'Data Últ. Compra': 'Últ. Compra', 'Bloq.': 'Bloqueado', 'Data Bloq.': 'Data Bloqueio',
        'abertura': 'Data Abertura', 'ultima_atualizacao': 'Últ. Atualização', 'atividade_principal': 'CNAE',
        'tipo': 'Matriz/Filial', 'porte': 'Porte', 'capital_social': 'Capital Social',
        'simples.optante': 'Simples', 'simei.optante': 'Simei', 'natureza_juridica': 'Nat. Jurídica', 'quadro_societario': 'Sócios'
    }
    cols_disp = [c for c in colunas_mestre if c in df_f.columns]
    df_exibir_mestre = df_f[cols_disp].sort_values(by='Compra_Media_Num', ascending=False).drop(columns=['Compra_Media_Num'], errors='ignore')
    df_exibir_mestre = df_exibir_mestre.rename(columns=nomes_amigaveis)
    df_visual = gerar_df_visual_basico(df_exibir_mestre)
    st.dataframe(df_visual, use_container_width=True)
    st.download_button("📥 Baixar Base Consolidada", data=gerar_excel(df_visual, 'Alvo_Consolidado'), file_name='alvo_consolidado.xlsx')

with tab3:
    st.header("Dados Exclusivos do ERP (Recreio)")
    col_recreio = ['CNPJ_Limpo', 'Cód.', 'Razao_Recreio', 'Insc. Est.', 'Tipo Pessoa', 'Data Cadastro', 'Data Últ. Compra', 'Limite Crédito', 'Bloq.', 'Data Bloq.', 'Telefone_Recreio', 'Cidade_Recreio']
    df_r = df_f[df_f['Status_Recreio'] != 'Prospect (Sem Cadastro)'] if 'Status_Recreio' in df_f.columns else df_f
    df_vis_r = gerar_df_visual_basico(df_r[[c for c in col_recreio if c in df_r.columns]])
    st.dataframe(df_vis_r, use_container_width=True)
    st.download_button("📥 Baixar Dados ERP", data=gerar_excel(df_vis_r, 'ERP'), file_name='erp_recreio.xlsx')

with tab4:
    st.header("Dados Cadastrais (Receita Federal)")
    col_receita = [
        'CNPJ_Limpo', 'nome', 'fantasia', 'situacao', 'motivo_situacao', 'data_conclusao', 'abertura', 'ultima_atualizacao', 'tipo', 
        'porte', 'capital_social', 'simples.optante', 'simei.optante', 'natureza_juridica',
        'atividade_principal', 'atividade_secundaria', 'quadro_societario', 
        'logradouro', 'numero', 'complemento', 'bairro', 'municipio', 'uf', 'cep', 'telefone', 'email'
    ]
    df_vis_rec = gerar_df_visual_basico(df_f[[c for c in col_receita if c in df_f.columns]])
    st.dataframe(df_vis_rec, use_container_width=True)
    st.download_button("📥 Baixar Dados Receita", data=gerar_excel(df_vis_rec, 'Receita'), file_name='receita_federal.xlsx')

# ------------------------------------------
# 📦 ABA 5: MÁQUINA DE LUCRO E PRODUTOS
# ------------------------------------------
with tab5:
    st.header("Inteligência de Portfólio e Produtos")
    st.markdown("Visão executiva de rentabilidade, peso logístico e curva ABC do portfólio.")
    
    if len(df_pf) > 0:
        def criar_resumo_produto(df, agrupador):
            if 'Venda Média Estado RJ 2026 - Valor_Num_Filtro' not in df.columns or 'MARGEM   Pós Revisão_Num_Filtro' not in df.columns:
                return pd.DataFrame()
            
            d = df.copy()
            # Lucro Bruto Projetado
            d['Lucro_Bruto'] = d['Venda Média Estado RJ 2026 - Valor_Num_Filtro'] * (d['MARGEM   Pós Revisão_Num_Filtro'] / 100)
            
            # Peso Total Projetado em Toneladas
            if 'Venda Média RJ 2026 - Unidade_Num_Filtro' in d.columns and 'Peso_Bruto_Num_Filtro' in d.columns:
                d['Toneladas'] = (d['Venda Média RJ 2026 - Unidade_Num_Filtro'] * d['Peso_Bruto_Num_Filtro']) / 1000
            else:
                d['Toneladas'] = 0.0
            
            grp = d.groupby(agrupador).agg(
                SKUs=('Descrição do Produto', 'count'),
                Volume_Cxs=('Venda Média RJ 2026 - Unidade_Num_Filtro', 'sum'),
                Toneladas=('Toneladas', 'sum'),
                Venda_Mensal=('Venda Média Estado RJ 2026 - Valor_Num_Filtro', 'sum'),
                Lucro_Bruto=('Lucro_Bruto', 'sum')
            ).reset_index()
            
            grp['Margem Média'] = (grp['Lucro_Bruto'] / grp['Venda_Mensal'].replace(0, 1) * 100)
            grp = grp.sort_values(by='Lucro_Bruto', ascending=False)
            
            grp['Volume_Cxs'] = grp['Volume_Cxs'].apply(lambda x: f"{x:,.0f}".replace(',','.'))
            grp['Toneladas'] = grp['Toneladas'].apply(lambda x: f"{x:,.2f}".replace('.',','))
            grp['Venda_Mensal'] = grp['Venda_Mensal'].apply(lambda x: formatar_br(x, True))
            grp['Lucro_Bruto'] = grp['Lucro_Bruto'].apply(lambda x: formatar_br(x, True))
            grp['Margem Média'] = grp['Margem Média'].apply(lambda x: f"{x:.2f}%".replace('.',','))
            return grp

        # 1. Tabelas de Lucro
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.subheader("💡 Lucro Projetado por Família")
            if 'Família' in df_pf.columns:
                df_fam = criar_resumo_produto(df_pf, 'Família')
                st.dataframe(df_fam, use_container_width=True, hide_index=True)
                
        with col_p2:
            st.subheader("💡 Lucro Projetado por Categoria")
            if 'Categoria' in df_pf.columns:
                df_cat = criar_resumo_produto(df_pf, 'Categoria')
                st.dataframe(df_cat, use_container_width=True, hide_index=True)

        st.markdown("---")
        
        # 2. Curva ABC
        st.subheader("🏆 Curva ABC de Produtos (Por Venda Média)")
        if 'Venda Média Estado RJ 2026 - Valor_Num_Filtro' in df_pf.columns:
            df_abc = df_pf.sort_values(by='Venda Média Estado RJ 2026 - Valor_Num_Filtro', ascending=False).copy()
            df_abc['% Acumulado'] = df_abc['Venda Média Estado RJ 2026 - Valor_Num_Filtro'].cumsum() / df_abc['Venda Média Estado RJ 2026 - Valor_Num_Filtro'].sum()
            def classificar_abc(pct):
                if pct <= 0.7: return 'A (70%)'
                if pct <= 0.9: return 'B (20%)'
                return 'C (10%)'
            df_abc['Curva ABC'] = df_abc['% Acumulado'].apply(classificar_abc)
            
            cols_mostrar_abc = ['Curva ABC', 'Descrição do Produto', 'Venda Média Estado RJ 2026 - Valor', 'Venda Média RJ 2026 - Unidade', 'Preço Unitário c/ ST', 'Preço Médio - Ponta', 'Preço Máximo - Ponta', 'Preço Promo - Ponta', 'MARGEM   Pós Revisão', 'Itens Por Caixas']
            df_abc_vis = df_abc[[c for c in cols_mostrar_abc if c in df_abc.columns]].rename(columns={'Venda Média RJ 2026 - Unidade': 'Venda Média RJ 2026 - Cxs'})
            
            for c in df_abc_vis.columns:
                if any(x in c.lower() for x in ['%', 'icms', 'margem', 'markup']) and 'num' not in c.lower():
                    df_abc_vis[c] = df_abc_vis[c].apply(lambda x: f"{float(str(x).replace(',','.'))*100:.2f}%".replace('.',',') if str(x).replace('.','').replace(',','').isdigit() else str(x))
                elif any(x in c.lower() for x in ['preço', 'niv', 'valor', 'perna', 'pis/cofins', 'icms total', 'estado']) and 'num' not in c.lower():
                    df_abc_vis[c] = df_abc_vis[c].apply(formatar_moeda_generica)
                    
            st.dataframe(df_abc_vis, use_container_width=True, hide_index=True)

        # 3. Alerta de Preço Sem Recomendação
        if 'Preço Promo - Ponta' in df_pf.columns:
            df_sem_rec = df_pf[df_pf['Preço Promo - Ponta'].astype(str).str.contains('sem recomendação', case=False, na=False)].copy()
            if len(df_sem_rec) > 0:
                st.subheader(f"⚠️ Alerta: {len(df_sem_rec)} Produtos de Alto Volume Sem Preço na Ponta")
                cols_sr = ['Descrição do Produto', 'Venda Média RJ 2026 - Unidade', 'Venda Média Estado RJ 2026 - Valor', '5) Preço Caixa C/ST', 'MARGEM   Pós Revisão']
                
                col_sort_sr = 'Venda Média RJ 2026 - Unidade_Num_Filtro' if 'Venda Média RJ 2026 - Unidade_Num_Filtro' in df_sem_rec.columns else 'Descrição do Produto'
                df_sr_vis = df_sem_rec.sort_values(by=col_sort_sr, ascending=False)
                df_sr_vis = df_sr_vis[[c for c in cols_sr if c in df_sr_vis.columns]].rename(columns={'Venda Média RJ 2026 - Unidade': 'Venda Média RJ 2026 - Cxs'})
                
                for c in df_sr_vis.columns:
                    if 'valor' in c.lower() or 'preço' in c.lower() or 'caixa c' in c.lower():
                        df_sr_vis[c] = df_sr_vis[c].apply(formatar_moeda_generica)
                    elif 'margem' in c.lower() or '%' in c.lower():
                        df_sr_vis[c] = df_sr_vis[c].apply(formatar_percentual)
                st.dataframe(df_sr_vis, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Base de Produtos Completa (Refinada)")
    df_pf_vis = df_pf.drop(columns=[c for c in df_pf.columns if '_Num' in c], errors='ignore')
    for c in df_pf_vis.columns:
        if any(x in c.lower() for x in ['%', 'icms', 'margem', 'markup']):
            df_pf_vis[c] = df_pf_vis[c].apply(lambda x: f"{float(str(x).replace(',','.'))*100:.2f}%".replace('.',',') if str(x).replace('.','').replace(',','').isdigit() else str(x))
        elif 'peso' in c.lower():
            df_pf_vis[c] = df_pf_vis[c].apply(lambda x: f"{float(str(x).replace(',','.')):.3f}".replace('.',',') if str(x).replace('.','').replace(',','').isdigit() else str(x))
        elif any(x in c.lower() for x in ['preço', 'niv', 'valor', 'perna', 'pis/cofins', 'icms total', 'estado']):
            df_pf_vis[c] = df_pf_vis[c].apply(formatar_moeda_generica)
            
    st.dataframe(df_pf_vis, use_container_width=True)
    st.download_button("📥 Baixar Tabela Completa de Produtos", data=gerar_excel(df_pf_vis, 'Produtos'), file_name='produtos_unilever.xlsx')
