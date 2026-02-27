"""
pages/market_competition.py

🏴‍☠️ 2026 이더리움 파이 강탈자 (Ethereum Pie Raiders)
L1 시장 점유율 경쟁 분석 대시보드

지표 3종:
  1. TVL 유입 가속도 (Momentum Index) — 자금이 어디로 빠르게 쏠리는지
  2. 사용자당 자본 효율성 (Capital Efficiency per DAU) — 고래가 선호하는 체인
  3. 파이 침식 차트 (Market Share Erosion) — 12개월 누적 영역 차트

데이터 소스:
  - DefiLlama API (무료): TVL / 일별 히스토리
  - DAU: Token Terminal / DappRadar / 온체인 분석 기반 추정 (반정적)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta

# ── 테마 (ethereum_dashboard.py 동일 팔레트) ─────────────────────────
THEME = {
    "bg":      "#0d1117",
    "paper":   "#161b27",
    "card":    "#1e2538",
    "grid":    "#2a3045",
    "text":    "#e6edf3",
    "subtext": "#8b949e",
    "teal":    "#00d4aa",
    "gold":    "#f0c040",
    "red":     "#f85149",
    "green":   "#3fb950",
    "blue":    "#58a6ff",
    "orange":  "#f0883e",
}

# ── 체인 메타데이터 ────────────────────────────────────────────────────
CHAINS: dict = {
    "Ethereum": {
        "icon":       "Ξ",
        "color":      "#627eea",
        "fill":       "rgba(98,126,234,0.18)",
        "llama_name": "Ethereum",
        "threat":     "기준 체인",
        "threat_color": THEME["blue"] if False else "#627eea",  # 인라인 불가 — 아래 선언
        "pie_target": "기관 자금 + 스테이블코인 정착지",
        "tech":       "EVM (PoS)",
    },
    "Solana": {
        "icon":       "◎",
        "color":      "#9945ff",
        "fill":       "rgba(153,69,255,0.18)",
        "llama_name": "Solana",
        "threat":     "중기 위협 — 성능 격차",
        "threat_color": "#f0883e",
        "pie_target": "개인 거래·NFT·밈코인 (Retail)",
        "tech":       "PoH + Tower BFT",
    },
    "Aptos": {
        "icon":       "▲",
        "color":      "#00d9a3",
        "fill":       "rgba(0,217,163,0.18)",
        "llama_name": "Aptos",
        "threat":     "장기 위협 — Move 언어",
        "threat_color": "#f0c040",
        "pie_target": "개인 투자자 (Retail) — 저수수료",
        "tech":       "Move VM (BFT)",
    },
    "Berachain": {
        "icon":       "🐻",
        "color":      "#f0883e",
        "fill":       "rgba(240,136,62,0.18)",
        "llama_name": "Berachain",
        "threat":     "단기 위협 — 유동성 증명",
        "threat_color": "#f85149",
        "pie_target": "Yield Farmer (이자 농사꾼) — 유동성",
        "tech":       "Proof of Liquidity",
    },
    "Monad": {
        "icon":       "⬡",
        "color":      "#f0c040",
        "fill":       "rgba(240,192,64,0.18)",
        "llama_name": "Monad",
        "threat":     "중기 위협 — EVM 호환 고성능",
        "threat_color": "#f0883e",
        "pie_target": "EVM 개발자·DApp 마이그레이션",
        "tech":       "EVM 호환 (MonadBFT)",
    },
}

CHAIN_ORDER = ["Ethereum", "Solana", "Aptos", "Berachain", "Monad"]

# ── DAU 추정 데이터 ────────────────────────────────────────────────────
# 출처: Token Terminal / DappRadar / 온체인 고유 활성 주소 분석 2026 Q1 추정
# 반정적 데이터 — 월 1회 수동 업데이트 필요
DAU_ESTIMATES: dict[str, int] = {
    "Ethereum":  560_000,    # Etherscan 일별 고유 활성 주소 평균
    "Solana":  1_550_000,    # Solscan 일별 활성 계정
    "Aptos":     320_000,    # Aptos Explorer DAU
    "Berachain": 210_000,    # Berachain Explorer (2025년 2월 런칭 이후 성장)
    "Monad":     150_000,    # 메인넷 초기 추정 (2025년 말 런칭)
}

# ── 페이지 설정 ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="파이 강탈자 분석",
    page_icon="🏴‍☠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
  html, body, [data-testid="stAppViewContainer"] {{
      background-color: {THEME['bg']}; color: {THEME['text']};
  }}
  [data-testid="stHeader"] {{
      background-color: {THEME['bg']} !important;
      border-bottom: 1px solid {THEME['grid']};
  }}
  [data-testid="stDecoration"] {{ display: none !important; }}
  .stApp > header + div {{ padding-top: 0 !important; }}
  [data-testid="stSidebar"] {{
      background-color: #161a25; color: #e0e0e0;
  }}
  [data-testid="stSidebar"] label {{ color: #e0e0e0 !important; }}
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span {{ color: #c8ced5 !important; }}
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 {{ color: #fafafa !important; }}
  div[data-testid="stMetric"] {{
      background: {THEME['card']}; border-radius: 8px; padding: 0.7rem 1rem;
  }}
  div[data-testid="stMetric"] label {{ color: {THEME['subtext']} !important; }}
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
      color: {THEME['text']} !important;
  }}
  .stDataFrame {{ background: {THEME['card']}; }}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  데이터 수집 레이어 (DefiLlama)
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_all_chains_tvl() -> dict:
    """
    DefiLlama GET /v2/chains
    전체 체인 현재 TVL 딕셔너리 반환: {"Ethereum": float, ...}
    """
    try:
        resp = requests.get("https://api.llama.fi/v2/chains", timeout=15)
        resp.raise_for_status()
        return {d["name"]: float(d.get("tvl", 0)) for d in resp.json()}
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def fetch_historical_chain_tvl(llama_chain: str, days: int = 365) -> pd.Series:
    """
    DefiLlama GET /v2/historicalChainTvl/{chain}
    일별 TVL 시계열 반환 (DatetimeIndex, 단위: USD)
    데이터 없으면 empty Series 반환
    """
    try:
        url = f"https://api.llama.fi/v2/historicalChainTvl/{llama_chain}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        if not raw:
            return pd.Series(dtype=float)
        cutoff = datetime.utcnow() - timedelta(days=days)
        records = [
            (datetime.utcfromtimestamp(r["date"]), float(r["tvl"]))
            for r in raw
            if datetime.utcfromtimestamp(r["date"]) >= cutoff
        ]
        if not records:
            return pd.Series(dtype=float)
        dates, vals = zip(*records)
        s = pd.Series(list(vals), index=pd.DatetimeIndex(list(dates)), name=llama_chain)
        return s.sort_index().resample("D").last().ffill()
    except Exception:
        return pd.Series(dtype=float)


def _momentum_pct(series: pd.Series, window: int = 30) -> float | None:
    """
    TVL 유입 가속도 = (현재 TVL − n일전 TVL) / n일전 TVL × 100
    데이터가 window보다 짧으면 가용한 전체 기간으로 계산
    """
    if len(series) < 2:
        return None
    now_val = float(series.iloc[-1])
    idx     = max(0, len(series) - window - 1) if len(series) < window else len(series) - window - 1
    prev_val = float(series.iloc[idx])
    return (now_val - prev_val) / prev_val * 100 if prev_val else None


def _data_window_label(series: pd.Series, window: int) -> str:
    """차트 보조 텍스트용 — 실제 사용된 기간 표시"""
    avail = len(series)
    if avail == 0:
        return "데이터 없음"
    used = min(avail, window)
    if avail < window:
        return f"{used}일 (전체 이력)"
    return f"{window}일"


# ═══════════════════════════════════════════════════════════════════════
#  차트 함수
# ═══════════════════════════════════════════════════════════════════════

def _dark(fig: go.Figure, height: int = 420) -> go.Figure:
    """공통 다크 테마 적용"""
    fig.update_layout(
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font = dict(
            color=THEME["text"],
            family="Inter, -apple-system, sans-serif",
            size=12,
        ),
        xaxis  = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"], zeroline=False),
        yaxis  = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"], zeroline=False),
        legend = dict(
            bgcolor=THEME["paper"], bordercolor=THEME["grid"], borderwidth=1,
            font=dict(color=THEME["text"], size=11),
        ),
        margin    = dict(t=75, b=40, l=60, r=30),
        height    = height,
        hovermode = "x unified",
    )
    return fig


def chart_tvl_momentum(
    tvl_hist: dict[str, pd.Series],
    show_chains: list[str],
    window: int = 30,
) -> go.Figure:
    """
    TVL 유입 가속도 (Momentum Index) — 수평 막대 차트
    - 양수(초록): TVL 유입 가속 — 자금이 빠르게 쏠리는 중
    - 음수(빨강): TVL 유출 — 자금이 빠져나가는 중
    """
    names, momentums, colors, spans = [], [], [], []

    for chain in show_chains:
        s = tvl_hist.get(chain, pd.Series(dtype=float))
        m = _momentum_pct(s, window)
        if m is None:
            continue
        names.append(f"{CHAINS[chain]['icon']} {chain}")
        momentums.append(round(m, 2))
        colors.append(THEME["green"] if m >= 0 else THEME["red"])
        spans.append(_data_window_label(s, window))

    if not names:
        return go.Figure()

    # 오름차순 정렬 (좌→우 = 작→큰)
    order      = sorted(range(len(momentums)), key=lambda i: momentums[i])
    names      = [names[i]      for i in order]
    momentums  = [momentums[i]  for i in order]
    colors     = [colors[i]     for i in order]
    spans      = [spans[i]      for i in order]

    fig = go.Figure(go.Bar(
        y            = names,
        x            = momentums,
        orientation  = "h",
        marker_color = colors,
        marker_line  = dict(color="rgba(0,0,0,0)", width=0),
        text         = [f"+{m:.1f}%" if m >= 0 else f"{m:.1f}%" for m in momentums],
        textposition = "outside",
        textfont     = dict(color=THEME["text"], size=11),
        customdata   = spans,
        hovertemplate = "<b>%{y}</b><br>모멘텀: %{x:.2f}%<br>(%{customdata} 기준)<extra></extra>",
    ))

    fig.add_vline(
        x=0,
        line_color=THEME["gold"],
        line_width=1.5,
        line_dash="dot",
    )
    fig.update_layout(
        title = dict(
            text=f"📈 TVL 유입 가속도 — {window}일 모멘텀 지수",
            font=dict(color=THEME["text"], size=14),
        ),
        xaxis = dict(
            title="TVL 변화율 (%)",
            gridcolor=THEME["grid"],
            zeroline=True, zerolinecolor=THEME["grid"], zerolinewidth=1,
        ),
        yaxis      = dict(gridcolor=THEME["grid"]),
        showlegend = False,
    )
    return _dark(fig, height=370)


def chart_capital_efficiency(
    tvl_now: dict[str, float],
    show_chains: list[str],
) -> go.Figure:
    """
    사용자당 자본 효율성 = TVL ÷ DAU ($K per user)
    - 높을수록: '고래'·기관 자금 선호 체인
    - 낮을수록: 개인 투자자(Retail) 위주 체인
    """
    names, efficiency, colors = [], [], []

    for chain in show_chains:
        tvl = tvl_now.get(chain, 0)
        dau = DAU_ESTIMATES.get(chain, 1)
        if tvl > 0:
            eff = tvl / dau / 1_000   # → $K per user
            names.append(chain)
            efficiency.append(round(eff, 1))
            colors.append(CHAINS[chain]["color"])

    if not names:
        return go.Figure()

    # 내림차순 정렬
    order      = sorted(range(len(efficiency)), key=lambda i: efficiency[i], reverse=True)
    names      = [names[i]      for i in order]
    efficiency = [efficiency[i] for i in order]
    colors     = [colors[i]     for i in order]

    # DAU 정보 추가
    dau_labels = [f"DAU {DAU_ESTIMATES.get(n, 0):,}" for n in names]

    fig = go.Figure(go.Bar(
        x            = names,
        y            = efficiency,
        marker_color = colors,
        marker_line  = dict(color="rgba(0,0,0,0)", width=0),
        text         = [f"${e:,.0f}K" for e in efficiency],
        textposition = "outside",
        textfont     = dict(color=THEME["text"], size=11),
        customdata   = dau_labels,
        hovertemplate = (
            "<b>%{x}</b><br>"
            "사용자당 TVL: $%{y:,.0f}K<br>"
            "%{customdata}<extra></extra>"
        ),
    ))

    # ETH 기준선
    eth_eff = next((efficiency[i] for i, n in enumerate(names) if n == "Ethereum"), None)
    if eth_eff:
        fig.add_hline(
            y=eth_eff,
            line_dash="dot",
            line_color=CHAINS["Ethereum"]["color"],
            annotation_text="  ETH 기준",
            annotation_font_color=CHAINS["Ethereum"]["color"],
            annotation_font_size=10,
            annotation_position="bottom right",
        )

    fig.update_layout(
        title = dict(
            text="💎 사용자당 자본 효율성 (TVL ÷ DAU)",
            font=dict(color=THEME["text"], size=14),
        ),
        xaxis      = dict(gridcolor=THEME["grid"]),
        yaxis      = dict(title="TVL per DAU ($K)", gridcolor=THEME["grid"]),
        showlegend = False,
    )
    return _dark(fig, height=370)


def chart_market_share_erosion(
    tvl_hist: dict[str, pd.Series],
    show_chains: list[str],
    forecast_days: int = 60,
) -> go.Figure:
    """
    파이 침식 차트 (Stacked Area Chart)
    - 각 체인의 L1 TVL 점유율 추이
    - 데이터가 짧은 신흥 체인은 점선 트렌드 예측 추가
    """
    # 유효한 히스토리만 수집
    valid: dict[str, pd.Series] = {}
    for chain in show_chains:
        s = tvl_hist.get(chain, pd.Series(dtype=float))
        if not s.empty:
            valid[chain] = s

    if len(valid) < 2:
        return go.Figure()

    # 공통 날짜 인덱스: 가장 긴 체인 기준, 없는 날짜는 0으로 처리
    all_dates = sorted(set().union(*[set(s.index) for s in valid.values()]))
    common_idx = pd.DatetimeIndex(all_dates)
    df = pd.DataFrame(index=common_idx)
    for chain, s in valid.items():
        df[chain] = s.reindex(common_idx).ffill()   # 시작 이전은 NaN 유지

    df = df.fillna(0)
    total = df.sum(axis=1).replace(0, float("nan"))
    shares = (df.divide(total, axis=0) * 100).fillna(0)

    fig = go.Figure()

    # Stacked area — 역순으로 쌓아서 ETH가 맨 위(시각적으로 명확)
    for chain in reversed(show_chains):
        if chain not in shares.columns:
            continue
        fig.add_trace(go.Scatter(
            x           = shares.index,
            y           = shares[chain].round(2),
            name        = f"{CHAINS[chain]['icon']} {chain}",
            stackgroup  = "one",
            fillcolor   = CHAINS[chain]["fill"],
            line        = dict(color=CHAINS[chain]["color"], width=1.5),
            hovertemplate = f"<b>{CHAINS[chain]['icon']} {chain}</b>: %{{y:.1f}}%<extra></extra>",
        ))

    # 신흥 체인 트렌드 예측 (데이터 < 180일인 체인)
    for chain in show_chains:
        s = valid.get(chain)
        if s is None or len(s) >= 180 or chain == "Ethereum":
            continue
        # 최근 30일 또는 전체 기간 선형 회귀
        recent_days = min(30, len(s))
        recent = s.iloc[-recent_days:]
        x_num  = np.arange(len(recent), dtype=float)
        coeffs = np.polyfit(x_num, recent.values, 1)
        slope, intercept = coeffs

        fut_dates = [recent.index[-1] + timedelta(days=i + 1) for i in range(forecast_days)]
        fut_tvl   = [max(0.0, slope * (len(x_num) + i) + intercept) for i in range(forecast_days)]

        # Convert projected TVL to approximate share (rough estimate)
        last_total = float(df.sum(axis=1).iloc[-1]) or 1.0
        fut_shares = [v / last_total * 100 for v in fut_tvl]

        fig.add_trace(go.Scatter(
            x         = fut_dates,
            y         = [round(v, 2) for v in fut_shares],
            name      = f"{chain} (예측 추세)",
            mode      = "lines",
            line      = dict(color=CHAINS[chain]["color"], width=1.5, dash="dot"),
            showlegend= True,
            hovertemplate = f"<b>{chain} 예측</b>: %{{y:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        title = dict(
            text="🥧 파이 침식 차트 — L1 TVL 점유율 추이",
            font=dict(color=THEME["text"], size=14),
        ),
        yaxis = dict(
            title="TVL 점유율 (%)",
            range=[0, 100],
            gridcolor=THEME["grid"],
            linecolor=THEME["grid"],
        ),
        xaxis = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"]),
        legend = dict(
            bgcolor=THEME["paper"], bordercolor=THEME["grid"], borderwidth=1,
            font=dict(color=THEME["text"], size=11),
            orientation="h", y=-0.15, xanchor="center", x=0.5,
        ),
        hovermode = "x unified",
        margin    = dict(t=75, b=100, l=60, r=30),
        height    = 500,
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font = dict(color=THEME["text"], family="Inter, -apple-system, sans-serif", size=12),
    )
    return fig


def chart_tvl_abs_trends(
    tvl_hist: dict[str, pd.Series],
    show_chains: list[str],
) -> go.Figure:
    """
    절대 TVL 추이 선 차트 (참고용)
    """
    fig = go.Figure()
    for chain in show_chains:
        s = tvl_hist.get(chain, pd.Series(dtype=float))
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x    = s.index,
            y    = (s / 1e9).round(3),
            name = f"{CHAINS[chain]['icon']} {chain}",
            line = dict(color=CHAINS[chain]["color"], width=2),
            hovertemplate = f"<b>{chain}</b>: $%{{y:.2f}}B<extra></extra>",
        ))
    fig.update_layout(
        title      = dict(text="TVL 절대값 추이 ($B)", font=dict(color=THEME["text"], size=13)),
        yaxis      = dict(title="TVL ($B)"),
        hovermode  = "x unified",
    )
    return _dark(fig, height=360)


def chart_whale_index_trend(
    tvl_hist: dict[str, pd.Series],
    show_chains: list[str],
) -> go.Figure:
    """
    고래화 지수 추이 (Whale-ification Trend)
    = TVL(t) ÷ DAU_추정 — $K per user 시계열

    DAU는 반정적 추정치이므로 이 차트의 움직임은
    TVL 성장 속도 ÷ 사용자 기반의 상대적 자본화 속도를 반영.
    어떤 체인의 선이 ETH 기준선을 향해 빠르게 오른다면
    → 기관·고래 자금이 그 체인으로 이동 중이라는 신호.
    """
    fig = go.Figure()
    eth_series_vals = None   # ETH 기준선용

    for chain in show_chains:
        s   = tvl_hist.get(chain, pd.Series(dtype=float))
        dau = DAU_ESTIMATES.get(chain, 1)
        if s.empty:
            continue

        eff = (s / dau / 1_000).round(3)   # $K per user

        if chain == "Ethereum":
            eth_series_vals = eff

        # 30일 이동 평균으로 노이즈 제거
        eff_smooth = eff.rolling(7, min_periods=1).mean().round(3)

        fig.add_trace(go.Scatter(
            x    = eff_smooth.index,
            y    = eff_smooth.values,
            name = f"{CHAINS[chain]['icon']} {chain}",
            mode = "lines",
            line = dict(color=CHAINS[chain]["color"], width=2.2),
            hovertemplate = (
                f"<b>{CHAINS[chain]['icon']} {chain}</b><br>"
                "날짜: %{x|%Y-%m-%d}<br>"
                "사용자당 TVL: $%{y:,.1f}K<extra></extra>"
            ),
        ))

        # 신흥 체인 (< 180일 데이터): 점선 미래 추세 추가
        if len(s) < 180 and chain != "Ethereum":
            recent_n = min(30, len(eff_smooth))
            recent   = eff_smooth.iloc[-recent_n:]
            x_num    = np.arange(len(recent), dtype=float)
            slope, intercept = np.polyfit(x_num, recent.values, 1)
            fut_dates = [recent.index[-1] + timedelta(days=i + 1) for i in range(90)]
            fut_vals  = [max(0.0, slope * (len(x_num) + i) + intercept) for i in range(90)]

            fig.add_trace(go.Scatter(
                x         = fut_dates,
                y         = [round(v, 3) for v in fut_vals],
                name      = f"{chain} (90일 예측)",
                mode      = "lines",
                line      = dict(color=CHAINS[chain]["color"], width=1.5, dash="dot"),
                showlegend= True,
                hovertemplate = f"<b>{chain} 예측</b>: $%{{y:,.1f}}K<extra></extra>",
            ))

    # ETH 현재값 기준선
    if eth_series_vals is not None and not eth_series_vals.empty:
        eth_latest = float(eth_series_vals.rolling(7, min_periods=1).mean().iloc[-1])
        fig.add_hline(
            y=eth_latest,
            line_dash="dot",
            line_color=CHAINS["Ethereum"]["color"],
            opacity=0.5,
            annotation_text=f"  ETH 현재 기준 ${eth_latest:,.0f}K",
            annotation_font_color=CHAINS["Ethereum"]["color"],
            annotation_font_size=10,
            annotation_position="bottom right",
        )

    fig.update_layout(
        title = dict(
            text="🐳 고래화 지수 추이 — 사용자당 TVL ($K/DAU) 시계열",
            font=dict(color=THEME["text"], size=14),
        ),
        xaxis = dict(
            title="날짜",
            gridcolor=THEME["grid"], linecolor=THEME["grid"],
        ),
        yaxis = dict(
            title="TVL per DAU ($K)",
            gridcolor=THEME["grid"], linecolor=THEME["grid"],
        ),
        legend = dict(
            bgcolor=THEME["paper"], bordercolor=THEME["grid"], borderwidth=1,
            font=dict(color=THEME["text"], size=11),
            orientation="h", y=-0.18, xanchor="center", x=0.5,
        ),
        hovermode = "x unified",
        margin    = dict(t=75, b=110, l=65, r=30),
        height    = 480,
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font = dict(color=THEME["text"], family="Inter, -apple-system, sans-serif", size=12),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════
#  메인
# ═══════════════════════════════════════════════════════════════════════

def main():
    st.title("🏴‍☠️ 이더리움 파이 강탈자 (Pie Raiders)")
    st.caption(
        "2026 L1 시장 점유율 경쟁 분석 — "
        "TVL 유입 가속도 · 사용자당 자본 효율성 · 파이 침식 차트"
    )
    st.info(
        "📡 **TVL 데이터**: DefiLlama API 실시간. "
        "**DAU**: Token Terminal / DappRadar 기반 2026 Q1 추정치(반정적). "
        "Monad·Berachain은 신규 체인이므로 이력 데이터가 짧을 수 있습니다. "
        "점선 = 선형 추세 예측.",
        icon="ℹ️",
    )

    # ── 사이드바 ────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ 분석 설정")

        st.subheader("📅 모멘텀 기간")
        momentum_window = st.selectbox(
            "TVL 변화율 계산 기간",
            [7, 14, 30, 60, 90],
            index=2,
            help="선택한 기간 동안의 TVL 변화율(%)을 모멘텀 지수로 사용",
        )

        st.subheader("🔗 분석 대상 체인")
        show_chains = st.multiselect(
            "체인 선택",
            options=CHAIN_ORDER,
            default=CHAIN_ORDER,
        )
        if not show_chains:
            show_chains = CHAIN_ORDER

        st.subheader("📈 예측 설정")
        forecast_days = st.slider(
            "트렌드 예측 기간 (신흥 체인)",
            min_value=30, max_value=180, value=60, step=15,
            help="데이터가 짧은 신흥 체인의 선형 예측 기간 (일)",
        )

        st.markdown("---")
        st.markdown("""
**위협 등급 안내**
- 🔴 **단기 위협**: 베라체인 — 유동성 직접 유혹
- 🟠 **중기 위협**: 솔라나·모나드 — 성능 격차
- 🟡 **장기 위협**: 앱토스·수이 — 기술 표준 대체
""")

    # ── 데이터 로드 ─────────────────────────────────────────────────
    with st.spinner("DefiLlama TVL 데이터 로드 중..."):
        all_tvl_map = fetch_all_chains_tvl()

        tvl_hist: dict[str, pd.Series] = {}
        for chain in show_chains:
            llama = CHAINS[chain]["llama_name"]
            tvl_hist[chain] = fetch_historical_chain_tvl(llama, days=365)

        tvl_now: dict[str, float] = {}
        for chain in show_chains:
            llama = CHAINS[chain]["llama_name"]
            val = all_tvl_map.get(llama, 0.0)
            if val == 0.0 and not tvl_hist[chain].empty:
                val = float(tvl_hist[chain].iloc[-1])
            tvl_now[chain] = val

    # ── 섹션 1: TVL 현황 카드 ────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 현재 TVL 현황")

    sorted_chains = sorted(show_chains, key=lambda c: tvl_now.get(c, 0), reverse=True)
    cols = st.columns(len(sorted_chains))

    for i, chain in enumerate(sorted_chains):
        tvl  = tvl_now.get(chain, 0)
        c    = CHAINS[chain]
        hist = tvl_hist.get(chain, pd.Series(dtype=float))
        mom  = _momentum_pct(hist, momentum_window)
        mom_str = (
            f"+{mom:.1f}%" if mom and mom >= 0
            else f"{mom:.1f}%" if mom is not None
            else "—"
        )
        mom_color = THEME["green"] if (mom and mom >= 0) else THEME["red"]

        with cols[i]:
            st.markdown(f"""
<div style="background:{THEME['card']};border-left:4px solid {c['color']};
            padding:1rem 1.1rem;border-radius:8px;text-align:center;">
  <div style="color:{THEME['subtext']};font-size:0.75rem;margin-bottom:2px;">
    {c['icon']} {chain}
  </div>
  <div style="color:{c['color']};font-size:1.6rem;font-weight:700;line-height:1.2;">
    ${tvl/1e9:.1f}B
  </div>
  <div style="color:{mom_color};font-size:0.82rem;margin:3px 0;">
    {mom_str} ({momentum_window}d)
  </div>
  <div style="color:{THEME['subtext']};font-size:0.68rem;line-height:1.4;">
    {c['threat']}
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 섹션 2: 모멘텀 & 자본 효율성 ────────────────────────────────
    st.markdown("---")
    st.markdown("### 🚀 TVL 유입 속도 & 자본 효율성")

    col_m, col_e = st.columns(2)

    with col_m:
        fig_mom = chart_tvl_momentum(tvl_hist, show_chains, window=momentum_window)
        st.plotly_chart(fig_mom, use_container_width=True)
        st.markdown(f"""
<div style="background:{THEME['card']};border-left:3px solid {THEME['teal']};
            padding:0.7rem 1rem;border-radius:6px;font-size:0.8rem;
            color:{THEME['text']};line-height:1.6;">
  <b>해석</b>: 양수 = 자금 유입 가속 중 / 음수 = 유출.<br>
  ETH 대비 신흥 체인의 모멘텀이 <b>3배 이상</b>이라면 개발자·자금 이탈 신호.
  Monad의 EVM 호환성은 <b>개발자 이탈</b>의 가장 쉬운 통로.
</div>""", unsafe_allow_html=True)

    with col_e:
        fig_eff = chart_capital_efficiency(tvl_now, show_chains)
        st.plotly_chart(fig_eff, use_container_width=True)
        st.markdown(f"""
<div style="background:{THEME['card']};border-left:3px solid {THEME['gold']};
            padding:0.7rem 1rem;border-radius:6px;font-size:0.8rem;
            color:{THEME['text']};line-height:1.6;">
  <b>해석</b>: ETH 기준선 <b>위</b> = 고래·기관 자금 선호 체인.<br>
  Berachain이 높으면 → 이더리움의 <b>Yield Farmer</b>들이 대거 이동한 증거.<br>
  Solana가 낮으면 → <b>개인 투자자(Retail)</b> 위주 체인임을 의미.
</div>""", unsafe_allow_html=True)

    # ── 섹션 2-B: 고래화 지수 추이 ──────────────────────────────────
    st.markdown("---")
    st.markdown("### 🐳 고래화 지수 추이 — 어떤 체인이 가장 빠르게 '기관화'되는가?")
    st.caption(
        "공식: **TVL(t) ÷ DAU 추정 = 사용자 1인당 예탁 자본 ($K)**  |  "
        "DAU는 반정적 추정치이므로 실질적으로는 TVL 성장 가속도를 반영.  "
        "ETH 기준선(점선)을 향해 급등하는 체인 = 기관·고래 자금 유입 신호."
    )

    fig_whale = chart_whale_index_trend(tvl_hist, show_chains)
    st.plotly_chart(fig_whale, use_container_width=True)

    # 가장 빠르게 고래화되는 체인 자동 탐지
    _growth_rates = {}
    for chain in show_chains:
        s   = tvl_hist.get(chain, pd.Series(dtype=float))
        dau = DAU_ESTIMATES.get(chain, 1)
        if len(s) < 14:
            continue
        eff = s / dau / 1_000
        recent_30 = eff.iloc[-min(30, len(eff)):]
        if len(recent_30) >= 7:
            x_n = np.arange(len(recent_30), dtype=float)
            slope_val = np.polyfit(x_n, recent_30.values, 1)[0]
            _growth_rates[chain] = slope_val   # $K/day 증가 속도

    if _growth_rates:
        fastest = max(_growth_rates, key=lambda c: _growth_rates[c])
        slowest = min(_growth_rates, key=lambda c: _growth_rates[c])
        col_w1, col_w2, col_w3 = st.columns(3)
        col_w1.metric(
            "🚀 가장 빠른 고래화",
            fastest,
            f"+${_growth_rates[fastest]*30:,.1f}K / 30일",
            help="최근 30일간 사용자당 TVL 증가 속도",
        )
        col_w2.metric(
            "📉 가장 느린 고래화",
            slowest,
            f"${_growth_rates[slowest]*30:,.1f}K / 30일",
            delta_color="off",
        )
        eth_rate = _growth_rates.get("Ethereum", 0)
        if eth_rate != 0:
            top_ratio = _growth_rates[fastest] / eth_rate if fastest != "Ethereum" else 1.0
            col_w3.metric(
                "ETH 대비 고래화 가속도",
                f"ETH의 {top_ratio:.1f}배",
                fastest,
                delta_color="inverse" if top_ratio > 1 else "normal",
                help=f"{fastest}의 고래화 속도가 ETH보다 {top_ratio:.1f}배 빠름",
            )

    st.markdown(f"""
<div style="background:{THEME['card']};border-left:3px solid {THEME['teal']};
            padding:0.8rem 1.1rem;border-radius:6px;font-size:0.8rem;
            color:{THEME['text']};line-height:1.7;margin-top:0.5rem;">
  <b>🎯 투자 신호 해석 가이드</b><br>
  • Berachain / Monad의 선이 <b>ETH 기준선(점선)</b>을 향해 가파르게 오른다면
    → 이더리움에서 기관 자금이 해당 체인으로 이동하기 시작한 <b>강력한 매도 신호</b>.<br>
  • 신흥 체인(점선 구간)의 기울기가 가파를수록
    → <b>90일 내 ETH 기준선 도달</b> 가능성이 높아짐.<br>
  • DAU가 고정값이므로 이 지표는 실질적으로 <b>TVL 성장 가속도</b>를 나타냄.
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 섹션 3: 파이 침식 차트 ──────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🥧 파이 침식 차트 — L1 TVL 점유율 12개월 추이")
    st.caption("점선 = 데이터가 짧은 신흥 체인의 선형 추세 예측 (참고용)")

    fig_erosion = chart_market_share_erosion(tvl_hist, show_chains, forecast_days)
    st.plotly_chart(fig_erosion, use_container_width=True)

    # ETH 점유율 변화 분석
    eth_hist = tvl_hist.get("Ethereum", pd.Series(dtype=float))
    if not eth_hist.empty:
        # 모든 체인의 합 대비 ETH 비중
        combined_now  = sum(
            float(tvl_hist[c].iloc[-1]) if not tvl_hist[c].empty else 0
            for c in show_chains
        )
        combined_12m_ago = sum(
            float(tvl_hist[c].iloc[0]) if not tvl_hist[c].empty else 0
            for c in show_chains
        )
        eth_now_share  = tvl_now.get("Ethereum", 0) / combined_now * 100 if combined_now else 0
        eth_ago_tvl    = float(eth_hist.iloc[0]) if not eth_hist.empty else 0
        eth_ago_share  = eth_ago_tvl / combined_12m_ago * 100 if combined_12m_ago else 0
        eth_share_delta = eth_now_share - eth_ago_share

        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric(
            "ETH 현재 점유율 (분석 체인 기준)",
            f"{eth_now_share:.1f}%",
        )
        col_s2.metric(
            "ETH 12개월 전 점유율",
            f"{eth_ago_share:.1f}%",
            delta=f"{eth_share_delta:+.1f}%p",
            delta_color="inverse",
        )
        col_s3.metric(
            "이탈한 점유율",
            f"{max(0, -eth_share_delta):.1f}%p",
            help="ETH에서 경쟁 체인으로 이동한 추정 점유율",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 섹션 4: 절대 TVL 추이 (참고) ─────────────────────────────────
    with st.expander("📉 절대 TVL 추이 (참고용 선 차트)"):
        st.plotly_chart(
            chart_tvl_abs_trends(tvl_hist, show_chains),
            use_container_width=True,
        )
        st.caption("점유율 차트와 함께 보면 '파이가 줄어서 점유율 변동'인지 '파이 자체 성장'인지 구분 가능.")

    # ── 섹션 5: 체인별 위협 분석 카드 ───────────────────────────────
    st.markdown("---")
    st.markdown("### ⚠️ 체인별 이더리움 파이 침식 분석")

    THREAT_META = {
        "Berachain": {
            "level": "🔴 단기 위협",
            "color": THEME["red"],
            "title": "유동성 증명 (Proof of Liquidity)",
            "detail": (
                "베라체인은 검증인에게 블록 보상을 주는 대신 특정 DeFi 프로토콜에 유동성을 공급하도록 설계. "
                "적은 사용자로도 엄청난 거래량 생성 가능. "
                "**이더리움의 'Yield Farmer'들이 대거 이동했다면** 자본 효율성 지수가 ETH를 초과."
            ),
            "pie": "이자 농사꾼(Yield Farmer) 자금, 유동성 공급자",
        },
        "Solana": {
            "level": "🟠 중기 위협",
            "color": THEME["orange"],
            "title": "성능 격차로 소매 거래 장악",
            "detail": (
                "초당 수천 건 처리 + $0.001 수수료. ETH L1의 소매 거래 경험을 구식으로 만들고 있음. "
                "**TVL 모멘텀이 ETH의 3배 이상**이면 소매 투자자 이탈 가속화 신호. "
                "밈코인·NFT 생태계에서 ETH 점유율을 빠르게 잠식 중."
            ),
            "pie": "개인 투자자(Retail), 밈코인, NFT 거래",
        },
        "Monad": {
            "level": "🟠 중기 위협",
            "color": THEME["orange"],
            "title": "EVM 호환 고성능 — 마찰 없는 이탈",
            "detail": (
                "EVM 완전 호환 상태로 ETH 속도만 1만배 향상. 개발자가 **코드 수정 없이** 그대로 이전 가능. "
                "만약 모멘텀이 ETH의 3배를 넘는다면 → **개발 환경 이탈의 직접적 신호.** "
                "이더리움에서 가장 진입 장벽이 낮은 탈출 통로."
            ),
            "pie": "EVM DApp 개발자, ETH 생태계 프로토콜",
        },
        "Aptos": {
            "level": "🟡 장기 위협",
            "color": THEME["gold"],
            "title": "Move 언어 — 기술 표준 대체 시도",
            "detail": (
                "Move 언어 기반으로 ETH Solidity와 다른 보안 패러다임 제시. "
                "DAU가 급증하고 있다면 → **개인 투자자들이 저렴한 수수료를 찾아 이탈 중.** "
                "단기보다 장기적으로 이더리움 '기술 표준'을 대체할 잠재력 보유."
            ),
            "pie": "개인 투자자(Retail), 신규 DApp 개발자",
        },
    }

    for chain, meta in THREAT_META.items():
        if chain not in show_chains:
            continue
        tvl = tvl_now.get(chain, 0)
        mom = _momentum_pct(tvl_hist.get(chain, pd.Series(dtype=float)), momentum_window)
        eth_mom = _momentum_pct(tvl_hist.get("Ethereum", pd.Series(dtype=float)), momentum_window)
        ratio_str = ""
        if mom is not None and eth_mom and eth_mom != 0:
            ratio = mom / eth_mom
            ratio_str = f" (ETH 대비 **{ratio:.1f}배**)"

        st.markdown(f"""
<div style="background:{THEME['card']};border-left:5px solid {meta['color']};
            padding:1rem 1.4rem;border-radius:8px;margin-bottom:0.8rem;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
    <div style="color:{meta['color']};font-size:0.85rem;font-weight:700;">
      {meta['level']} — {chain}
    </div>
    <div style="color:{THEME['text']};font-size:0.9rem;">
      TVL: <b>${tvl/1e9:.2f}B</b>
      &nbsp;|&nbsp;{momentum_window}일 모멘텀:
      <span style="color:{'#3fb950' if mom and mom >= 0 else '#f85149'}">
        {f'+{mom:.1f}%' if mom and mom >= 0 else f'{mom:.1f}%' if mom else '—'}</span>{ratio_str}
    </div>
  </div>
  <div style="color:{THEME['subtext']};font-size:0.78rem;margin-bottom:0.3rem;">
    전략: {meta['title']}
  </div>
  <div style="color:{THEME['text']};font-size:0.8rem;line-height:1.6;">
    {meta['detail']}
  </div>
  <div style="margin-top:0.5rem;color:{THEME['subtext']};font-size:0.75rem;">
    🎯 빼앗는 파이: {meta['pie']}
  </div>
</div>""", unsafe_allow_html=True)

    # ── 섹션 6: 분석 가이드 ──────────────────────────────────────────
    st.markdown("---")
    with st.expander("📖 분석 해석 가이드 — 이더리움 위기 신호 읽는 법"):
        st.markdown(f"""
### 3가지 이더리움 위기 신호

| 신호 | 위기 지표 | 현재 상태 |
|---|---|---|
| 1️⃣ 모나드 TVL 모멘텀 ETH의 3× 이상 | 개발 환경 이탈 가속 | 사이드바에서 확인 |
| 2️⃣ 베라체인 자본 효율성 ETH 초과 | Yield Farmer 대거 이동 | 차트 기준선 참고 |
| 3️⃣ Aptos/Solana DAU 분기 연속 +20% | 소매 투자자 이탈 | 추이 모니터링 필요 |

### TVL 모멘텀 공식
```
모멘텀(%) = (TVL_현재 - TVL_{{n}}일전) / TVL_{{n}}일전 × 100
```
- 양수 = 자금 유입 가속 / 음수 = 유출
- 비교 기간은 사이드바에서 7·14·30·60·90일 중 선택

### 사용자당 자본 효율성 공식
```
Capital Efficiency per DAU = TVL($) ÷ DAU
```
- **높음** → 고래·기관 선호 (ETH, Berachain)
- **낮음** → 소매 투자자 위주 (Solana)

### 데이터 한계
- DAU는 온체인 고유 주소 기반 추정값으로 중복·봇 포함 가능
- Monad·Berachain 데이터는 메인넷 출시 이후 단기 이력만 존재
- TVL은 DefiLlama 집계 기준 (일부 브리지·네이티브 자산 제외 가능)
""")

    # ── 데이터 소스 안내 ─────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        "데이터 소스: DefiLlama API (TVL 실시간) · "
        "Token Terminal / DappRadar (DAU 추정, 2026 Q1) · "
        "모두 무료 공개 API / 연구 데이터 사용"
    )


if __name__ == "__main__":
    main()
