import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import math
import os

# ========== CONFIG ==========
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AUTO_REFRESH_MS = 120000  # 120s ou 2 minutos
PAGE_TITLE = "📊 Painel Supervisório — Operações PBX & Vivo"

# ========== CONEXÃO ==========
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
    }
    .op-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 2px;
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
    """
    Converte timestamp UTC do banco para horário de São Paulo (UTC-3)
    e formata como dd/mm/aaaa HH:MM:SS.
    """
    if not dt_str:
        return "-"
    try:
        ts = pd.to_datetime(dt_str, utc=True).tz_convert("America/Sao_Paulo")
        return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(dt_str)


@st.cache_data(ttl=50)
def carregar_ultima_linha(tabela: str):
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


def get_metrics_pbx(tabela: str, sufixo: str):
    """
    Lê a última linha da tabela e devolve um dicionário pronto para uso
    tanto nos cards individuais quanto no PBX Total.
    """
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

    status_campanhas   = row.get(f"st_campanhas_{sufixo}")
    qtde_mailing       = _to_int(row.get(f"qtde_mailing_{sufixo}"))
    ticket_medio       = row.get(f"ticket_medio_{sufixo}")
    ticket_medio_f     = _to_float(ticket_medio) if ticket_medio is not None else None
    qtde_leads         = _to_int(row.get(f"qtde_lead_{sufixo}"))
    qtde_chamadas      = _to_int(row.get(f"qtde_chamadas_{sufixo}"))
    ultimo_lead        = row.get(f"ultimo_lead_{sufixo}")
    valor_consumido    = _to_float(row.get(f"valor_consumido_{sufixo}"))
    created_at         = row.get("created_at")

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


def render_secao(
    titulo: str,
    subtitulo: str,
    tabela: str,
    sufixo: str,
    bg_color: str,
):
    """
    Renderiza uma seção individual (PBX ou Vivo).
    """
    m = get_metrics_pbx(tabela, sufixo)
    if not m:
        st.info(f"Nenhum dado encontrado na tabela **{tabela}**.")
        return

    m_status  = m["status"] if m["status"] else "-"
    m_mailing = fmt_int(m["qtde_mailing"])
    m_ticket  = fmt_moeda_brl(m["ticket_medio"])
    m_leads   = fmt_int(m["qtde_leads"])
    m_calls   = fmt_int(m["qtde_chamadas"])
    m_valor   = fmt_moeda_brl(m["valor_consumido"])
    m_ult     = fmt_datetime_br(m["ultimo_lead"])
    updated   = fmt_datetime_br(m["created_at"])

    # Card com fundo colorido
    st.markdown(
        f'<div class="op-card" style="background-color:{bg_color};">',
        unsafe_allow_html=True,
    )

    # Cabeçalho: título + atualizado
    col_top1, col_top2 = st.columns([2, 1])
    with col_top1:
        st.markdown(f'<div class="op-title">{titulo}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="op-subtitle">{subtitulo}</div>',
            unsafe_allow_html=True,
        )
    with col_top2:
        st.markdown(
            f'<div class="op-updated">Atualizado em<br><span>{updated}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")  # espaçinho

    # Linha 1
    linha1 = st.columns(3)
    with linha1[0]:
        st.metric("Status Campanhas", m_status)
    with linha1[1]:
        st.metric("Mailing (Qtde)", m_mailing)
    with linha1[2]:
        st.metric("Ticket Médio", m_ticket)

    # Linha 2
    linha2 = st.columns(3)
    with linha2[0]:
        st.metric("Leads (Qtde)", m_leads)
    with linha2[1]:
        st.metric("Chamadas (Qtde)", m_calls)
    with linha2[2]:
        # Valor Consumido customizado
        st.markdown(
            f"""
            <div style="
                border-radius:10px;
                padding:6px 8px;
                background-color:rgba(255,255,255,0.75);
                border:1px solid rgba(148,163,184,0.4);
            ">
                <div style="font-size:11px;color:#6b7280;">Valor Consumido</div>
                <div style="font-size:13px;font-weight:600;word-break:break-word;">
                    {m_valor}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Linha 3: Último Lead
    linha3 = st.columns(3)
    with linha3[0]:
        st.markdown(
            f"""
            <div style="
                border-radius:10px;
                padding:6px 8px;
                background-color:rgba(255,255,255,0.75);
                border:1px solid rgba(148,163,184,0.4);
            ">
                <div style="font-size:11px;color:#6b7280;">Último Lead (hora)</div>
                <div style="font-size:12px;font-weight:600;word-break:break-word;">
                    {m_ult}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)  # fecha card


def render_secao_total(
    titulo: str,
    subtitulo: str,
    metrics_list: list,
    bg_color: str,
):
    """
    Card de resumo PBX Total, calculando:
    - soma do mailing
    - média do ticket médio
    - soma de leads
    - soma de chamadas
    - soma valor consumido
    - último lead mais recente entre todos
    """
    valid = [m for m in metrics_list if m is not None]
    if not valid:
        st.info("Nenhum dado encontrado para compor o **PBX Total**.")
        return

    total_mailing   = sum(m["qtde_mailing"] for m in valid)
    total_leads     = sum(m["qtde_leads"] for m in valid)
    total_chamadas  = sum(m["qtde_chamadas"] for m in valid)
    total_valor     = sum(m["valor_consumido"] for m in valid)

    tickets = [m["ticket_medio"] for m in valid if m["ticket_medio"] is not None]
    ticket_medio_med = sum(tickets) / len(tickets) if tickets else None

    # Último lead mais recente (proteção de parsing)
    ultimos_validos = [m["ultimo_lead"] for m in valid if m["ultimo_lead"]]
    if ultimos_validos:
        ult_series = pd.to_datetime(ultimos_validos, errors="coerce")
        ult_series = ult_series.dropna()
        if len(ult_series) > 0:
            ultimo_global = ult_series.max()
            ultimo_global_str = ultimo_global.strftime("%d/%m/%Y %H:%M:%S")
        else:
            ultimo_global_str = "-"
    else:
        ultimo_global_str = "-"

    created_validos = [m["created_at"] for m in valid if m["created_at"]]
    if created_validos:
        created_series = pd.to_datetime(created_validos, errors="coerce")
        created_series = created_series.dropna()
        if len(created_series) > 0:
            updated_dt = created_series.max()
            updated_str = updated_dt.strftime("%d/%m/%Y %H:%M:%S")
        else:
            updated_str = "-"
    else:
        updated_str = "-"

    m_mailing = fmt_int(total_mailing)
    m_ticket  = fmt_moeda_brl(ticket_medio_med)
    m_leads   = fmt_int(total_leads)
    m_calls   = fmt_int(total_chamadas)
    m_valor   = fmt_moeda_brl(total_valor)

    # Card PBX Total (laranja mais escuro da família)
    st.markdown(
        f'<div class="op-card" style="background-color:{bg_color};">',
        unsafe_allow_html=True,
    )

    col_top1, col_top2 = st.columns([2, 1])
    with col_top1:
        st.markdown(f'<div class="op-title">{titulo}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="op-subtitle">{subtitulo}</div>',
            unsafe_allow_html=True,
        )
    with col_top2:
        st.markdown(
            f'<div class="op-updated">Atualizado em<br><span>{updated_str}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Linha 1
    linha1 = st.columns(3)
    with linha1[0]:
        st.metric("Mailing Total", m_mailing)
    with linha1[1]:
        st.metric("Ticket Médio (média)", m_ticket)
    with linha1[2]:
        st.metric("Leads Totais", m_leads)

    # Linha 2
    linha2 = st.columns(3)
    with linha2[0]:
        st.metric("Chamadas Totais", m_calls)
    with linha2[1]:
        st.markdown(
            f"""
            <div style="
                border-radius:10px;
                padding:6px 8px;
                background-color:rgba(255,255,255,0.82);
                border:1px solid rgba(148,163,184,0.5);
            ">
                <div style="font-size:11px;color:#6b7280;">Valor Consumido Total</div>
                <div style="font-size:13px;font-weight:600;word-break:break-word;">
                    {m_valor}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with linha2[2]:
        st.markdown(
            f"""
            <div style="
                border-radius:10px;
                padding:6px 8px;
                background-color:rgba(255,255,255,0.82);
                border:1px solid rgba(148,163,184,0.5);
            ">
                <div style="font-size:11px;color:#6b7280;">Último Lead (mais recente)</div>
                <div style="font-size:12px;font-weight:600;word-break:break-word;">
                    {ultimo_global_str}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ==========================
# COLETA DAS MÉTRICAS PBX1..PBX5
# ==========================
metrics_pbx1 = get_metrics_pbx("operacao_pbx1", "pbx1")
metrics_pbx2 = get_metrics_pbx("operacao_pbx2", "pbx2")
metrics_pbx3 = get_metrics_pbx("operacao_pbx3", "pbx3")
metrics_pbx4 = get_metrics_pbx("operacao_pbx4", "pbx4")
metrics_pbx5 = get_metrics_pbx("operacao_pbx5", "pbx5")

# ==========================
# LAYOUT: LINHA 1 -> PBX TOTAL, PBX1, PBX2 (laranjas)
# ==========================
col_total, col_pbx1, col_pbx2 = st.columns(3)

with col_total:
    render_secao_total(
        titulo="Operação PBX Total",
        subtitulo="Resumo consolidado das operações PBX1 a PBX5.",
        metrics_list=[metrics_pbx1, metrics_pbx2, metrics_pbx3, metrics_pbx4, metrics_pbx5],
        bg_color="#fed7aa",   # laranja mais escuro dentro do pastel
    )

with col_pbx1:
    render_secao(
        titulo="Operação PBX1",
        subtitulo="Monitoramento em tempo quase real — PBX1.",
        tabela="operacao_pbx1",
        sufixo="pbx1",
        bg_color="#ffe0b8",      # um pouco mais claro
    )

with col_pbx2:
    render_secao(
        titulo="Operação PBX2",
        subtitulo="Indicadores dedicados à operação PBX2.",
        tabela="operacao_pbx2",
        sufixo="pbx2",
        bg_color="#ffe9c7",      # mais claro ainda
    )

# ==========================
# LAYOUT: LINHA 2 -> PBX3, PBX4, PBX5 (laranjas mais claros)
# ==========================
col_pbx3, col_pbx4, col_pbx5 = st.columns(3)

with col_pbx3:
    render_secao(
        titulo="Operação PBX3",
        subtitulo="Visão consolidada da operação PBX3.",
        tabela="operacao_pbx3",
        sufixo="pbx3",
        bg_color="#fff1d7",      # laranja bem claro
    )

with col_pbx4:
    render_secao(
        titulo="Operação PBX4",
        subtitulo="Indicadores dedicados à operação PBX4.",
        tabela="operacao_pbx4",
        sufixo="pbx4",
        bg_color="#fff7e6",      # quase branco com toque laranja
    )

with col_pbx5:
    render_secao(
        titulo="Operação PBX5",
        subtitulo="Indicadores dedicados à operação PBX5.",
        tabela="operacao_pbx5",
        sufixo="pbx5",
        bg_color="#fffaf0",      # o mais clarinho
    )

# ==========================
# LAYOUT: LINHA 3 -> VIVO (SOC, RPO, FMG em roxos)
# ==========================
metrics_soc = get_metrics_pbx("operacao_soc", "soc")
metrics_rpo = get_metrics_pbx("operacao_rpo", "rpo")
metrics_fmg = get_metrics_pbx("operacao_fmg", "fmg")

col_soc, col_rpo, col_fmg = st.columns(3)

with col_soc:
    render_secao(
        titulo="Operação SOC (Vivo)",
        subtitulo="Indicadores da operação Vivo — SOC.",
        tabela="operacao_soc",
        sufixo="soc",
        bg_color="#e0d4ff",   # roxo mais escuro (pastel)
    )

with col_rpo:
    render_secao(
        titulo="Operação RPO (Vivo)",
        subtitulo="Indicadores da operação Vivo — RPO.",
        tabela="operacao_rpo",
        sufixo="rpo",
        bg_color="#e9ddff",   # roxo médio
    )

with col_fmg:
    render_secao(
        titulo="Operação FMG (Vivo)",
        subtitulo="Indicadores da operação Vivo — FMG.",
        tabela="operacao_fmg",
        sufixo="fmg",
        bg_color="#f3eaff",   # roxo mais claro
    )

st.caption("Atualização automática a cada 60 segundos.")
