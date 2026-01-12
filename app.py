Você colou no `app.py` com as crases do Markdown (`python). No arquivo **tem que ficar só o código**, sem `.

Abaixo está o **código inteiro limpo** (pode copiar e colar direto no `app.py`):

```python
import streamlit as st
from supabase import create_client
import pandas as pd
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
        margin-bottom: 12px;
    }

    .op-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 2px;
    }

    /* ✅ Apenas para PBX Total (título maior) */
    .op-title-total {
        font-size: 24px;
        font-weight: 800;
        margin-bottom: 2px;
    }

    /* ✅ Apenas para PBX Total (números maiores) */
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

    /* “Quadrantes” (caixas grandes) */
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
    Converte para horário de São Paulo (UTC-3) e formata como dd/mm/aaaa HH:MM:SS.
    - Se vier com timezone, converte para America/Sao_Paulo.
    - Se vier sem timezone, assume que já está em America/Sao_Paulo.
    """
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
    tanto nos cards individuais quanto nos consolidados.
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

    st.markdown(
        f'<div class="op-card" style="background-color:{bg_color};">',
        unsafe_allow_html=True,
    )

    col_top1, col_top2 = st.columns([2, 1])
    with col_top1:
        st.markdown(f'<div class="op-title">{titulo}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="op-subtitle">{subtitulo}</div>', unsafe_allow_html=True)
    with col_top2:
        st.markdown(
            f'<div class="op-updated">Atualizado em<br><span>{updated}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    linha1 = st.columns(3)
    with linha1[0]:
        st.metric("Status Campanhas", m_status)
    with linha1[1]:
        st.metric("Mailing (Qtde)", m_mailing)
    with linha1[2]:
        st.metric("Ticket Médio", m_ticket)

    linha2 = st.columns(3)
    with linha2[0]:
        st.metric("Leads (Qtde)", m_leads)
    with linha2[1]:
        st.metric("Chamadas (Qtde)", m_calls)
    with linha2[2]:
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

    st.markdown("</div>", unsafe_allow_html=True)

def render_secao_total(
    titulo: str,
    subtitulo: str,
    metrics_list: list,
    bg_color: str,
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

    tickets = [
        m["ticket_medio"]
        for m in valid
        if m["ticket_medio"] is not None and m["ticket_medio"] != 0
    ]
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

    m_mailing = fmt_int(total_mailing)
    m_ticket  = fmt_moeda_brl(ticket_medio_med)
    m_leads   = fmt_int(total_leads)
    m_calls   = fmt_int(total_chamadas)
    m_valor   = fmt_moeda_brl(total_valor)

    if metric_wrapper_class:
        st.markdown(f'<div class="{metric_wrapper_class}">', unsafe_allow_html=True)

    st.markdown(
        f'<div class="op-card" style="background-color:{bg_color};">',
        unsafe_allow_html=True,
    )

    col_top1, col_top2 = st.columns([2, 1])
    with col_top1:
        st.markdown(f'<div class="{title_class}">{titulo}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="op-subtitle">{subtitulo}</div>', unsafe_allow_html=True)
    with col_top2:
        st.markdown(
            f'<div class="op-updated">Atualizado em<br><span>{updated_str}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    linha1 = st.columns(3)
    with linha1[0]:
        st.metric("Mailing Total", m_mailing)
    with linha1[1]:
        st.metric("Ticket Médio (média)", m_ticket)
    with linha1[2]:
        st.metric("Leads Totais", m_leads)

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

    if metric_wrapper_class:
        st.markdown("</div>", unsafe_allow_html=True)


# ==========================
# COLETA DAS MÉTRICAS PBX (PBX1..PBX4)
# ==========================
metrics_pbx1 = get_metrics_pbx("operacao_pbx1", "pbx1")
metrics_pbx2 = get_metrics_pbx("operacao_pbx2", "pbx2")
metrics_pbx3 = get_metrics_pbx("operacao_pbx3", "pbx3")
metrics_pbx4 = get_metrics_pbx("operacao_pbx4", "pbx4")

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

# ===== QUADRANTE ESQUERDO (PBX) =====
with quad_esq:
    st.markdown('<div class="quad">', unsafe_allow_html=True)
    st.markdown('<div class="quad-title">QUADRANTE PBX</div>', unsafe_allow_html=True)

    render_secao_total(
        titulo="Operação PBX Total",
        subtitulo="Resumo consolidado das operações PBX1 a PBX4.",
        metrics_list=[metrics_pbx1, metrics_pbx2, metrics_pbx3, metrics_pbx4],
        bg_color="#fed7aa",
        title_class="op-title-total",
        metric_wrapper_class="pbx-total-metric",
    )

    render_secao(
        titulo="Operação PBX1",
        subtitulo="Monitoramento em tempo quase real — PBX1.",
        tabela="operacao_pbx1",
        sufixo="pbx1",
        bg_color="#ffe0b8",
    )

    render_secao(
        titulo="Operação PBX2",
        subtitulo="Indicadores dedicados à operação PBX2.",
        tabela="operacao_pbx2",
        sufixo="pbx2",
        bg_color="#ffe9c7",
    )

    render_secao(
        titulo="Operação PBX3",
        subtitulo="Visão consolidada da operação PBX3.",
        tabela="operacao_pbx3",
        sufixo="pbx3",
        bg_color="#fff1d7",
    )

    render_secao(
        titulo="Operação PBX4",
        subtitulo="Indicadores dedicados à operação PBX4.",
        tabela="operacao_pbx4",
        sufixo="pbx4",
        bg_color="#fff7e6",
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ===== QUADRANTE DIREITO (VIVO) =====
with quad_dir:
    st.markdown('<div class="quad">', unsafe_allow_html=True)
    st.markdown('<div class="quad-title">QUADRANTE VIVO</div>', unsafe_allow_html=True)

    render_secao_total(
        titulo="Operação Vivo Total",
        subtitulo="Resumo consolidado das operações SOC, RPO e FMG.",
        metrics_list=[metrics_soc, metrics_rpo, metrics_fmg],
        bg_color="#ddd6fe",
        title_class="op-title-total",
        metric_wrapper_class=None,
    )

    render_secao(
        titulo="Operação SOC (Vivo)",
        subtitulo="Indicadores da operação Vivo — SOC.",
        tabela="operacao_soc",
        sufixo="soc",
        bg_color="#e0d4ff",
    )

    render_secao(
        titulo="Operação RPO (Vivo)",
        subtitulo="Indicadores da operação Vivo — RPO.",
        tabela="operacao_rpo",
        sufixo="rpo",
        bg_color="#e9ddff",
    )

    render_secao(
        titulo="Operação FMG (Vivo)",
        subtitulo="Indicadores da operação Vivo — FMG.",
        tabela="operacao_fmg",
        sufixo="fmg",
        bg_color="#f3eaff",
    )

    # RPA no final
    render_secao(
        titulo="Operação RPA (Vivo)",
        subtitulo="Indicadores da operação Vivo — RPA.",
        tabela="operacao_rpa",
        sufixo="rpa",
        bg_color="#f3eaff",
    )

    st.markdown("</div>", unsafe_allow_html=True)

st.caption("Atualização automática a cada 120 segundos (2 minutos).")
```

Se ainda der erro, me mande o **nome exato da tabela** e 1 exemplo de **coluna real** do RPA no Supabase (só o nome da coluna, sem dados), pra eu garantir que o sufixo `rpa` bate 100% com o schema.
