import streamlit as st
from supabase import create_client
import pandas as pd
import math
import os
import time
from urllib.parse import urlparse
import requests
from io import StringIO
import unicodedata

# ========== CONFIG ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AUTO_REFRESH_MS = 120000  # 120s ou 2 minutos
PAGE_TITLE = "📊 Painel Supervisório — Operações PBX & Vivo"

# ✅ Planilha pública com limites (dinâmicos)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1MrG40xIke5idxF-lIu-koeyL2oNyjTXMEtcqK3E2qps/edit?usp=sharing"

# ✅ IMPORTANTE: se você editar outra aba, troque o gid abaixo
# (gid=0 é a primeira aba)
GOOGLE_SHEET_GID = os.getenv("GOOGLE_SHEET_GID", "0")

# ========== CONEXÃO ==========
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Variáveis de ambiente SUPABASE_URL e/ou SUPABASE_KEY não definidas.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.markdown(f"### {PAGE_TITLE}")

# ===== CSS GLOBAL =====
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.6rem;
        padding-bottom: 0.6rem;
    }

    .op-card {
        border-radius: 16px;
        padding: 12px 14px;
        box-shadow: 0 6px 16px rgba(15, 23, 42, 0.04);
        border: 1px solid rgba(148, 163, 184, 0.2);
        margin-bottom: 12px;
    }

    .op-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 2px;
    }

    .op-title-total {
        font-size: 24px;
        font-weight: 800;
        margin-bottom: 2px;
    }

    .pbx-total-metric [data-testid="stMetricValue"] {
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        line-height: 1.05 !important;
    }

    .op-subtitle {
        font-size: 11px;
        color: #6b7280;
        margin-bottom: 6px;
    }
    .op-updated {
        font-size: 11px;
        color: #4b5563;
        text-align: right;
    }
    .op-updated span {
        font-weight: 600;
    }

    .quad {
        border-radius: 18px;
        padding: 14px 14px 2px 14px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: rgba(255,255,255,0.55);
    }
    .quad-title {
        font-size: 14px;
        font-weight: 800;
        color: rgba(15, 23, 42, 0.75);
        margin-bottom: 10px;
    }

    /* ✅ Caixas customizadas com tamanho visual próximo ao st.metric */
    .kv-box {
        border-radius: 10px;
        padding: 8px 10px;
        border: 1px solid rgba(148,163,184,0.4);
        background-color: rgba(255,255,255,0.75);
        min-height: 72px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kv-box.warn {
        background-color: #fef08a !important; /* amarelo */
        border: 1px solid #f59e0b !important;
    }
    .kv-label {
        font-size: 0.80rem;
        color: #6b7280;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    .kv-value {
        font-size: 1.45rem;       /* ✅ maior */
        font-weight: 700;
        line-height: 1.05;
        word-break: break-word;
        color: rgb(49, 51, 63);
    }
    .kv-value-big {
        font-size: 1.45rem;       /* ✅ igual ao kv-value para ficar padrão */
        font-weight: 700;
        line-height: 1.05;
        word-break: break-word;
        color: rgb(49, 51, 63);
    }

    /* data/hora longa não precisa ficar gigante */
    .kv-box.datetime .kv-value,
    .kv-box.datetime .kv-value-big {
        font-size: 0.95rem;
        font-weight: 600;
        line-height: 1.1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Auto-refresh silencioso
st.components.v1.html(
    f"""<script>
        setTimeout(function() {{ window.parent.location.reload(); }}, {AUTO_REFRESH_MS});
    </script>""",
    height=0,
)

# ========== FUNÇÕES GERAIS ==========
def fmt_int(x):
    try:
        return f"{int(x):,}".replace(",", ".")
    except Exception:
        return "-"

def fmt_float(x, casas=2):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "-"
        return (
            f"{float(x):,.{casas}f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except Exception:
        return "-"

def fmt_moeda_brl(x):
    v = fmt_float(x, 2)
    return f"R$ {v}" if v != "-" else "-"

def fmt_datetime_br(dt_str):
    if dt_str is None or dt_str == "":
        return "-"
    try:
        ts = pd.to_datetime(dt_str, errors="coerce")
        if pd.isna(ts):
            return "-"
        if ts.tzinfo is None:
            ts = ts.tz_localize("America/Sao_Paulo")
        else:
            ts = ts.tz_convert("America/Sao_Paulo")
        return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(dt_str)

def to_float_safe(v):
    try:
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip().replace("R$", "").replace(" ", "")
            if vv == "":
                return None
            # 1.234,56 -> 1234.56
            if "," in vv and "." in vv:
                vv = vv.replace(".", "").replace(",", ".")
            elif "," in vv:
                vv = vv.replace(",", ".")
            return float(vv)
        return float(v)
    except Exception:
        return None

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    s = " ".join(s.split())
    return s

def css_class_alert(is_alert: bool, extra_class: str = "") -> str:
    base = "kv-box warn" if is_alert else "kv-box"
    return f"{base} {extra_class}".strip()

def render_kv_box(label: str, value_text: str, alert: bool = False, big: bool = False, is_datetime: bool = False):
    extra = "datetime" if is_datetime else ""
    cls = css_class_alert(alert, extra_class=extra)
    value_cls = "kv-value-big" if big else "kv-value"
    st.markdown(
        f"""
        <div class="{cls}">
            <div class="kv-label">{label}</div>
            <div class="{value_cls}">{value_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ========== LIMITES (GOOGLE SHEETS) ==========
def extrair_sheet_id(url: str) -> str | None:
    try:
        parts = urlparse(url).path.split("/")
        if "d" in parts:
            idx = parts.index("d")
            return parts[idx + 1]
        return None
    except Exception:
        return None

def build_gsheet_csv_url(sheet_url: str, gid: str = "0", force_ts: bool = True) -> str | None:
    sheet_id = extrair_sheet_id(sheet_url)
    if not sheet_id:
        return None
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    if force_ts:
        url += f"&_ts={int(time.time())}"
    return url

def carregar_csv_google_sem_cache(csv_url: str) -> pd.DataFrame:
    """
    Faz download explícito com headers anti-cache (mais confiável que pd.read_csv direto na URL).
    """
    headers = {
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "User-Agent": "Mozilla/5.0"
    }
    resp = requests.get(csv_url, headers=headers, timeout=15)
    resp.raise_for_status()
    text = resp.text

    # Remove BOM se vier
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")

    return pd.read_csv(StringIO(text))

def carregar_limites_google(sheet_url: str, gid: str) -> dict:
    """
    SEM CACHE (proposital): sempre busca os limites atuais da planilha.
    """
    csv_url = build_gsheet_csv_url(sheet_url, gid=gid, force_ts=True)
    if not csv_url:
        return {}

    try:
        df = carregar_csv_google_sem_cache(csv_url)
    except Exception:
        try:
            # fallback simples
            df = pd.read_csv(csv_url)
        except Exception:
            return {}

    if df.empty:
        return {}

    # normaliza colunas
    df.columns = [normalize_text(c) for c in df.columns]

    col_servidor = None
    col_valor = None
    col_ticket = None

    for c in df.columns:
        if col_servidor is None and "servidor" in c:
            col_servidor = c
        if col_valor is None and "valor" in c and "consum" in c:
            col_valor = c
        if col_ticket is None and "ticket" in c:
            col_ticket = c

    if not col_servidor:
        return {}

    limites = {}
    for _, row in df.iterrows():
        nome_original = row.get(col_servidor, "")
        nome = str(nome_original).strip()
        if not nome or nome.lower() == "nan":
            continue

        lim_valor = to_float_safe(row.get(col_valor)) if col_valor else None
        lim_ticket = to_float_safe(row.get(col_ticket)) if col_ticket else None

        limites[nome] = {
            "valor_consumido": lim_valor,
            "ticket": lim_ticket
        }

    return limites

def get_limites_operacao(limites_dict: dict, titulo_operacao: str) -> dict:
    """
    Busca limites com match exato e fallback normalizado.
    """
    if titulo_operacao in limites_dict:
        return limites_dict[titulo_operacao]

    alvo = normalize_text(titulo_operacao)
    for k, v in limites_dict.items():
        if normalize_text(k) == alvo:
            return v

    # fallback flexível: aceita "PBX1" na planilha para "Operação PBX1"
    for k, v in limites_dict.items():
        nk = normalize_text(k)
        if nk and (nk in alvo or alvo in nk):
            return v

    return {}

# ✅ sem cache: sempre lê na execução atual
LIMITES = carregar_limites_google(GOOGLE_SHEET_URL, GOOGLE_SHEET_GID)

# ========== DADOS SUPABASE ==========
@st.cache_data(ttl=30)
def carregar_ultima_linha(tabela: str):
    try:
        resp = (
            supabase
            .table(tabela)
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        dados = resp.data or []
        return dados[0] if len(dados) else None
    except Exception:
        try:
            resp = (
                supabase
                .table(tabela)
                .select("*")
                .order("creta_at", desc=True)
                .limit(1)
                .execute()
            )
            dados = resp.data or []
            return dados[0] if len(dados) else None
        except Exception:
            return None

def get_metrics_pbx(tabela: str, sufixo: str):
    row = carregar_ultima_linha(tabela)
    if not row:
        return None

    def _to_float(v):
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def _to_int(v):
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0

    status_campanhas = row.get(f"st_campanhas_{sufixo}")
    qtde_mailing = _to_int(row.get(f"qtde_mailing_{sufixo}"))
    ticket_medio = row.get(f"ticket_medio_{sufixo}")
    ticket_medio_f = _to_float(ticket_medio) if ticket_medio is not None else None

    qtde_leads_raw = row.get(f"qtde_lead_{sufixo}")
    if qtde_leads_raw is None:
        qtde_leads_raw = row.get(f"qtde_leads_{sufixo}")
    qtde_leads = _to_int(qtde_leads_raw)

    qtde_chamadas = _to_int(row.get(f"qtde_chamadas_{sufixo}"))
    ultimo_lead = row.get(f"ultimo_lead_{sufixo}")
    valor_consumido = _to_float(row.get(f"valor_consumido_{sufixo}"))
    created_at = row.get("created_at") or row.get("creta_at")

    return {
        "status": status_campanhas,
        "qtde_mailing": qtde_mailing,
        "ticket_medio": ticket_medio_f,
        "qtde_leads": qtde_leads,
        "qtde_chamadas": qtde_chamadas,
        "ultimo_lead": ultimo_lead,
        "valor_consumido": valor_consumido,
        "created_at": created_at,
    }

# ========== RENDER ==========
def render_secao(
    titulo: str,
    subtitulo: str,
    tabela: str,
    sufixo: str,
    bg_color: str,
    limites_dict: dict,
):
    m = get_metrics_pbx(tabela, sufixo)
    if not m:
        st.info(f"Nenhum dado encontrado na tabela **{tabela}**.")
        return

    limites = get_limites_operacao(limites_dict, titulo)
    limite_valor = to_float_safe(limites.get("valor_consumido"))
    limite_ticket = to_float_safe(limites.get("ticket"))

    valor_atual_num = to_float_safe(m["valor_consumido"])
    ticket_atual_num = to_float_safe(m["ticket_medio"])

    alerta_valor = (limite_valor is not None and valor_atual_num is not None and valor_atual_num > limite_valor)
    alerta_ticket = (limite_ticket is not None and ticket_atual_num is not None and ticket_atual_num > limite_ticket)

    m_status  = m["status"] if m["status"] else "-"
    m_mailing = fmt_int(m["qtde_mailing"])
    m_ticket  = fmt_moeda_brl(m["ticket_medio"])
    m_leads   = fmt_int(m["qtde_leads"])
    m_calls   = fmt_int(m["qtde_chamadas"])
    m_valor   = fmt_moeda_brl(m["valor_consumido"])
    m_ult     = fmt_datetime_br(m["ultimo_lead"])
    updated   = fmt_datetime_br(m["created_at"])

    st.markdown(f'<div class="op-card" style="background-color:{bg_color};">', unsafe_allow_html=True)

    col_top1, col_top2 = st.columns([2, 1])
    with col_top1:
        st.markdown(f'<div class="op-title">{titulo}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="op-subtitle">{subtitulo}</div>', unsafe_allow_html=True)
    with col_top2:
        st.markdown(f'<div class="op-updated">Atualizado em<br><span>{updated}</span></div>', unsafe_allow_html=True)

    st.markdown("")

    linha1 = st.columns(3)
    with linha1[0]:
        st.metric("Status Campanhas", m_status)
    with linha1[1]:
        st.metric("Mailing (Qtde)", m_mailing)
    with linha1[2]:
        render_kv_box(label="Ticket Médio", value_text=m_ticket, alert=alerta_ticket)

    linha2 = st.columns(3)
    with linha2[0]:
        st.metric("Leads (Qtde)", m_leads)
    with linha2[1]:
        st.metric("Chamadas (Qtde)", m_calls)
    with linha2[2]:
        render_kv_box(label="Valor Consumido", value_text=m_valor, alert=alerta_valor)

    linha3 = st.columns(3)
    with linha3[0]:
        render_kv_box(label="Último Lead (hora)", value_text=m_ult, alert=False, is_datetime=True)

    st.markdown("</div>", unsafe_allow_html=True)

def render_secao_total(
    titulo: str,
    subtitulo: str,
    metrics_list: list,
    bg_color: str,
    limites_dict: dict,
    title_class: str = "op-title",
    metric_wrapper_class: str | None = None,
):
    valid = [m for m in metrics_list if m is not None]
    if not valid:
        st.info(f"Nenhum dado encontrado para compor **{titulo}**.")
        return

    total_mailing   = sum(m["qtde_mailing"] for m in valid)
    total_leads     = sum(m["qtde_leads"] for m in valid)
    total_chamadas  = sum(m["qtde_chamadas"] for m in valid)
    total_valor     = sum(m["valor_consumido"] for m in valid)

    tickets = [m["ticket_medio"] for m in valid if m["ticket_medio"] is not None and m["ticket_medio"] != 0]
    ticket_medio_med = sum(tickets) / len(tickets) if tickets else None

    ultimos_validos = [m["ultimo_lead"] for m in valid if m["ultimo_lead"]]
    if ultimos_validos:
        ult_series = pd.to_datetime(ultimos_validos, errors="coerce").dropna()
        ultimo_global_str = fmt_datetime_br(ult_series.max()) if len(ult_series) > 0 else "-"
    else:
        ultimo_global_str = "-"

    created_validos = [m["created_at"] for m in valid if m["created_at"]]
    if created_validos:
        created_series = pd.to_datetime(created_validos, errors="coerce").dropna()
        updated_str = fmt_datetime_br(created_series.max()) if len(created_series) > 0 else "-"
    else:
        updated_str = "-"

    limites = get_limites_operacao(limites_dict, titulo)
    limite_valor = to_float_safe(limites.get("valor_consumido"))
    limite_ticket = to_float_safe(limites.get("ticket"))

    alerta_valor = (limite_valor is not None and total_valor is not None and total_valor > limite_valor)
    alerta_ticket = (limite_ticket is not None and ticket_medio_med is not None and ticket_medio_med > limite_ticket)

    m_mailing = fmt_int(total_mailing)
    m_ticket  = fmt_moeda_brl(ticket_medio_med)
    m_leads   = fmt_int(total_leads)
    m_calls   = fmt_int(total_chamadas)
    m_valor   = fmt_moeda_brl(total_valor)

    if metric_wrapper_class:
        st.markdown(f'<div class="{metric_wrapper_class}">', unsafe_allow_html=True)

    st.markdown(f'<div class="op-card" style="background-color:{bg_color};">', unsafe_allow_html=True)

    col_top1, col_top2 = st.columns([2, 1])
    with col_top1:
        st.markdown(f'<div class="{title_class}">{titulo}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="op-subtitle">{subtitulo}</div>', unsafe_allow_html=True)
    with col_top2:
        st.markdown(f'<div class="op-updated">Atualizado em<br><span>{updated_str}</span></div>', unsafe_allow_html=True)

    st.markdown("")

    linha1 = st.columns(3)
    with linha1[0]:
        st.metric("Mailing Total", m_mailing)
    with linha1[1]:
        render_kv_box(label="Ticket Médio (média)", value_text=m_ticket, alert=alerta_ticket, big=True)
    with linha1[2]:
        st.metric("Leads Totais", m_leads)

    linha2 = st.columns(3)
    with linha2[0]:
        st.metric("Chamadas Totais", m_calls)
    with linha2[1]:
        render_kv_box(label="Valor Consumido Total", value_text=m_valor, alert=alerta_valor, big=True)
    with linha2[2]:
        render_kv_box(label="Último Lead (mais recente)", value_text=ultimo_global_str, alert=False, is_datetime=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if metric_wrapper_class:
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================
# COLETA DAS MÉTRICAS PBX (PBX1..PBX5)
# ==========================
metrics_pbx1 = get_metrics_pbx("operacao_pbx1", "pbx1")
metrics_pbx2 = get_metrics_pbx("operacao_pbx2", "pbx2")
metrics_pbx3 = get_metrics_pbx("operacao_pbx3", "pbx3")
metrics_pbx4 = get_metrics_pbx("operacao_pbx4", "pbx4")
metrics_pbx5 = get_metrics_pbx("operacao_pbx5", "pbx5")  # fora do total

# ==========================
# COLETA DAS MÉTRICAS VIVO
# ==========================
metrics_soc = get_metrics_pbx("operacao_soc", "soc")
metrics_rpo = get_metrics_pbx("operacao_rpo", "rpo")
metrics_fmg = get_metrics_pbx("operacao_fmg", "fmg")
metrics_rpa = get_metrics_pbx("operacao_rpa", "rpa")

# ==========================
# LAYOUT EM 2 QUADRANTES
# ==========================
quad_esq, quad_dir = st.columns(2)

with quad_esq:
    st.markdown('<div class="quad">', unsafe_allow_html=True)
    st.markdown('<div class="quad-title">QUADRANTE PBX</div>', unsafe_allow_html=True)

    # PBX Total SOMENTE PBX1..PBX4
    render_secao_total(
        titulo="Operação PBX Total",
        subtitulo="Resumo consolidado das operações PBX1 a PBX4.",
        metrics_list=[metrics_pbx1, metrics_pbx2, metrics_pbx3, metrics_pbx4],
        bg_color="#fed7aa",
        limites_dict=LIMITES,
        title_class="op-title-total",
        metric_wrapper_class="pbx-total-metric",
    )

    render_secao("Operação PBX1", "Monitoramento em tempo quase real — PBX1.", "operacao_pbx1", "pbx1", "#ffe0b8", LIMITES)
    render_secao("Operação PBX2", "Indicadores dedicados à operação PBX2.", "operacao_pbx2", "pbx2", "#ffe9c7", LIMITES)
    render_secao("Operação PBX3", "Visão consolidada da operação PBX3.", "operacao_pbx3", "pbx3", "#fff1d7", LIMITES)
    render_secao("Operação PBX4", "Indicadores dedicados à operação PBX4.", "operacao_pbx4", "pbx4", "#fff7e6", LIMITES)

    # PBX5 individual (fora do total)
    render_secao("Operação PBX5", "Indicadores dedicados à operação PBX5.", "operacao_pbx5", "pbx5", "#fffaf0", LIMITES)

    st.markdown("</div>", unsafe_allow_html=True)

with quad_dir:
    st.markdown('<div class="quad">', unsafe_allow_html=True)
    st.markdown('<div class="quad-title">QUADRANTE VIVO</div>', unsafe_allow_html=True)

    render_secao_total(
        titulo="Operação Vivo Total",
        subtitulo="Resumo consolidado das operações SOC, RPO e FMG.",
        metrics_list=[metrics_soc, metrics_rpo, metrics_fmg],
        bg_color="#ddd6fe",
        limites_dict=LIMITES,
        title_class="op-title-total",
        metric_wrapper_class=None,
    )

    render_secao("Operação SOC (Vivo)", "Indicadores da operação Vivo — SOC.", "operacao_soc", "soc", "#e0d4ff", LIMITES)
    render_secao("Operação RPO (Vivo)", "Indicadores da operação Vivo — RPO.", "operacao_rpo", "rpo", "#e9ddff", LIMITES)
    render_secao("Operação FMG (Vivo)", "Indicadores da operação Vivo — FMG.", "operacao_fmg", "fmg", "#f3eaff", LIMITES)
    render_secao("Operação RPA (Vivo)", "Indicadores da operação Vivo — RPA.", "operacao_rpa", "rpa", "#f3eaff", LIMITES)

    st.markdown("</div>", unsafe_allow_html=True)

# ✅ Debug rápido (pode deixar temporariamente para validar atualização)
with st.expander("Debug limites (Google Sheets)"):
    st.write("GID usado:", GOOGLE_SHEET_GID)
    st.write("Limites carregados agora:", LIMITES)

st.caption("Atualização automática a cada 120 segundos (2 minutos).")