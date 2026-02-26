"""
pages/security_analysis.py

블록체인 보안 강건성 분석 대시보드
BTC (PoW) vs ETH (PoS) vs SOL (PoS)
51% 공격 경제 비용 · 보안 강건성 지수 · 슬래싱 리스크 시뮬레이터

데이터 소스 (모두 무료 공개 API):
  - CoinGecko  : 현재 가격·시총·공급량·가격 히스토리
  - blockchain.info : BTC 네트워크 해시레이트 시계열
  - beaconcha.in    : ETH 비콘체인 총 스테이킹 잔고
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime

# ── 테마 팔레트 (ethereum_dashboard.py 와 동일) ──────────────────────────
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

BTC_C = "#f7931a"   # Bitcoin orange
ETH_C = "#627eea"   # Ethereum blue-purple
SOL_C = "#9945ff"   # Solana purple

# ── 국가별 해시레이트 데이터 ─────────────────────────────────────────────
# 출처: Cambridge Centre for Alternative Finance (CCAF) CBECI 2023년 추정치
# 실시간 API 없음 — 6개월~1년 주기로 발표되는 연구 데이터 기반
HASHRATE_GEO: list[dict] = [
    {
        "country": "미국",       "country_en": "United States", "iso3": "USA",
        "share": 37.8,
        # BMC(Bitcoin Mining Council) 2023 Q3 설문 + CCAF 지역 추정
        "energy": {"수력·재생에너지": 58, "석탄": 27, "천연가스": 12, "원자력": 3},
        "risk": "낮음",   # 지정학적 리스크 (서방 동맹, 법치 안정)
    },
    {
        "country": "중국",       "country_en": "China",         "iso3": "CHN",
        "share": 21.1,
        # 채굴 금지 이후에도 VPN·내몽골 등 지하 채굴 지속 (CCAF 2022~2023)
        "energy": {"수력·재생에너지": 23, "석탄": 70, "천연가스": 5,  "원자력": 2},
        "risk": "높음",
    },
    {
        "country": "카자흐스탄", "country_en": "Kazakhstan",    "iso3": "KAZ",
        "share": 13.2,
        # 전력망 불안정, 정부 채굴 제한 조치 이력
        "energy": {"수력·재생에너지": 8,  "석탄": 87, "천연가스": 5,  "원자력": 0},
        "risk": "높음",
    },
    {
        "country": "러시아",     "country_en": "Russia",        "iso3": "RUS",
        "share": 10.5,
        # 시베리아 수력 전기 + 천연가스. 제재 리스크 존재
        "energy": {"수력·재생에너지": 45, "석탄": 20, "천연가스": 35, "원자력": 0},
        "risk": "높음",
    },
    {
        "country": "캐나다",     "country_en": "Canada",        "iso3": "CAN",
        "share": 6.5,
        # 퀘벡·브리티시 컬럼비아 수력 발전 중심
        "energy": {"수력·재생에너지": 82, "석탄": 5,  "천연가스": 10, "원자력": 3},
        "risk": "낮음",
    },
    {
        "country": "독일",       "country_en": "Germany",       "iso3": "DEU",
        "share": 4.5,
        "energy": {"수력·재생에너지": 60, "석탄": 25, "천연가스": 10, "원자력": 5},
        "risk": "낮음",
    },
    {
        "country": "말레이시아", "country_en": "Malaysia",      "iso3": "MYS",
        "share": 3.1,
        "energy": {"수력·재생에너지": 15, "석탄": 45, "천연가스": 40, "원자력": 0},
        "risk": "중간",
    },
    {
        "country": "기타",       "country_en": "Others",        "iso3": None,
        "share": 3.3,
        "energy": None,
        "risk": "중간",
    },
]

# 지정학적 리스크 분류: 규제 리스크 높은 국가 ISO3
_HIGH_RISK_ISO = {"CHN", "RUS", "KAZ"}

# 에너지원 색상
_ENERGY_COLORS = {
    "수력·재생에너지": "#00d4aa",   # 청록 (친환경)
    "석탄":           "#8b7355",   # 갈색
    "천연가스":        "#f0883e",   # 주황
    "원자력":          "#58a6ff",   # 파랑
}

# ── ETH 스테이킹 엔티티 분포 ───────────────────────────────────────────
# 출처: rated.network / beaconcha.in / Dune Analytics 2025년 Q1 추정치
# "솔로 검증인(Solo/Unknown)"은 수천 명의 독립 개인으로, 단일 조직이 아님
ETH_STAKING_ENTITIES: list[dict] = [
    {
        "entity": "Lido",         "type": "유동성 스테이킹 프로토콜",
        "share": 28.2,            "color": "#627eea",
        "risk": "높음",           # 단일 프로토콜로 33% 임박 — 거버넌스 위험
        "note": "LDO 토큰 보유자가 거버넌스 결정 — 탈중앙화 논란",
    },
    {
        "entity": "솔로 검증인",   "type": "독립 개인 (비조직)",
        "share": 23.8,            "color": "#3fb950",
        "risk": "낮음",           # 수천 명의 독립 개인, 공모 불가
        "note": "32 ETH 직접 스테이킹한 개인들, 조정 불가",
    },
    {
        "entity": "Coinbase",     "type": "중앙화 거래소 (CEX)",
        "share": 11.4,            "color": "#0052ff",
        "risk": "높음",           # SEC 규제 대상, 자산 동결 가능
        "note": "미국 SEC 규제 대상 — 법적 압박 시 자산 동결 위험",
    },
    {
        "entity": "미분류/기타",   "type": "알 수 없는 엔티티",
        "share": 15.1,            "color": "#8b949e",
        "risk": "중간",
        "note": "비공개 운영자, 스테이킹 풀 등",
    },
    {
        "entity": "Binance",      "type": "중앙화 거래소 (CEX)",
        "share": 4.3,             "color": "#f0c040",
        "risk": "높음",
        "note": "글로벌 규제 리스크 보유",
    },
    {
        "entity": "Rocket Pool",  "type": "탈중앙 스테이킹 프로토콜",
        "share": 3.7,             "color": "#f0883e",
        "risk": "낮음",
        "note": "분산 노드 오퍼레이터 구조",
    },
    {
        "entity": "Kraken",       "type": "중앙화 거래소 (CEX)",
        "share": 3.1,             "color": "#9945ff",
        "risk": "높음",
        "note": "SEC 제재 이력 (2023)",
    },
    {
        "entity": "Figment",      "type": "기관 스테이킹",
        "share": 2.8,             "color": "#58a6ff",
        "risk": "중간",
        "note": "기관 투자자 대상 전문 노드 운영사",
    },
    {
        "entity": "기타 소규모",   "type": "소규모 풀·기관",
        "share": 7.6,             "color": "#2a3045",
        "risk": "낮음",
        "note": "다수 소규모 운영자 합산",
    },
]

# 공모 가능성 있는 "기관" 엔티티만 (솔로 검증인 / 미분류 제외)
_ETH_INSTITUTIONAL = {"Lido", "Coinbase", "Binance", "Rocket Pool", "Kraken", "Figment"}

# ── 페이지 설정 ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="블록체인 보안 분석",
    page_icon="🔐",
    layout="wide",
)

st.markdown(f"""
<style>
  html, body, [data-testid="stAppViewContainer"] {{
      background-color: {THEME['bg']};
      color: {THEME['text']};
  }}
  /* 상단 흰색 헤더 바 → 다크 처리 */
  [data-testid="stHeader"] {{
      background-color: {THEME['bg']} !important;
      border-bottom: 1px solid {THEME['grid']};
  }}
  /* 상단 장식용 오렌지/컬러 라인 제거 */
  [data-testid="stDecoration"] {{
      display: none !important;
  }}
  /* 상단 여백 제거 */
  .stApp > header + div {{
      padding-top: 0 !important;
  }}
  [data-testid="stSidebar"] {{
      background-color: #161a25;
      color: #e0e0e0;
  }}
  [data-testid="stSidebar"] label {{ color: #e0e0e0 !important; }}
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span {{ color: #c8ced5 !important; }}
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 {{ color: #fafafa !important; }}
  div[data-testid="stMetric"] {{
      background: {THEME['card']};
      border-radius: 8px;
      padding: 0.7rem 1rem;
  }}
  div[data-testid="stMetric"] label {{ color: {THEME['subtext']} !important; }}
  div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
      color: {THEME['text']} !important;
  }}
  .stDataFrame {{ background: {THEME['card']}; }}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  데이터 수집 레이어
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def fetch_coin_data() -> dict:
    """CoinGecko /coins/markets: BTC·ETH·SOL 현재 가격·시총·공급량"""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "bitcoin,ethereum,solana",
        "order": "market_cap_desc",
        "per_page": 3,
        "sparkline": False,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return {d["id"]: d for d in resp.json()}


@st.cache_data(ttl=3600)
def fetch_btc_hashrate_history(days: int = 180) -> pd.Series:
    """
    blockchain.info Charts API: BTC 네트워크 해시레이트 시계열
    단위: TH/s (테라해시/초)
    현재 네트워크 규모: ~600–900 EH/s = 600M–900M TH/s
    """
    try:
        url = (
            f"https://api.blockchain.info/charts/hash-rate"
            f"?timespan={days}days&format=json&cors=true"
        )
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        values = resp.json().get("values", [])
        if not values:
            return pd.Series(dtype=float)
        idx = pd.to_datetime(
            [datetime.utcfromtimestamp(v["x"]) for v in values]
        )
        return pd.Series(
            [float(v["y"]) for v in values],
            index=idx,
            name="hashrate_ths",
        )
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600)
def fetch_eth_staked() -> float:
    """
    beaconcha.in API: 비콘체인 총 스테이킹 잔고
    totalvalidatorbalance (gwei) → ETH 변환
    fallback: 34,000,000 ETH (2025년 기준 근사치)
    """
    try:
        resp = requests.get(
            "https://beaconcha.in/api/v1/epoch/latest",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "OK":
            total_gwei = data["data"].get("totalvalidatorbalance", 0)
            if total_gwei > 0:
                return float(total_gwei) / 1e9   # gwei → ETH
    except Exception:
        pass
    return 34_000_000.0  # 약 34M ETH 스테이킹 (2025년 근사)


@st.cache_data(ttl=3600)
def fetch_price_history(coin_id: str, days: int) -> pd.Series:
    """CoinGecko /market_chart: 코인 일별 종가 히스토리"""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        prices = resp.json().get("prices", [])
        if not prices:
            return pd.Series(dtype=float)
        idx = pd.to_datetime(
            [datetime.utcfromtimestamp(p[0] / 1000) for p in prices]
        )
        return pd.Series([p[1] for p in prices], index=idx, name=coin_id)
    except Exception:
        return pd.Series(dtype=float)


# ═══════════════════════════════════════════════════════════════════════
#  보안 지표 계산 함수
# ═══════════════════════════════════════════════════════════════════════

def calc_btc_attack_cost(
    hashrate_ths: float,   # 네트워크 총 해시레이트 (TH/s)
    asic_ths: float,       # ASIC 1대 해시레이트 (TH/s)
    asic_price: float,     # ASIC 1대 단가 ($)
    asic_power_w: float,   # ASIC 1대 소비 전력 (W)
    electricity: float,    # 전기요금 ($/kWh)
    attack_hours: float,   # 공격 지속 시간 (h)
) -> dict:
    """
    PoW 51% 공격 비용
    ─────────────────────────────────────────────────────
    총 비용 = 하드웨어(ASIC 구매) + 전기(공격 지속 동안)

    공격자는 네트워크 해시파워의 51% 이상을 확보해야 함.
    ASIC 공격 성공 후에도 하드웨어는 중고 판매 가능 → 실질 손실 < 투입 비용.
    """
    attack_ths  = hashrate_ths * 0.51               # 필요 해시레이트
    num_asics   = attack_ths / asic_ths             # 필요 ASIC 수량
    hw_cost     = num_asics * asic_price            # 하드웨어 비용 ($)
    power_kw    = num_asics * asic_power_w / 1000   # 총 소비 전력 (kW)
    el_cost     = power_kw * electricity * attack_hours  # 전기 비용 ($)
    return {
        "total":       hw_cost + el_cost,
        "hardware":    hw_cost,
        "energy":      el_cost,
        "num_asics":   int(num_asics),
        "attack_ths":  attack_ths,
        "attack_ehs":  attack_ths / 1e6,            # 표시용 (EH/s)
    }


def calc_eth_attack_cost(staked_eth: float, eth_price: float) -> dict:
    """
    PoS 51% 공격 비용 (이더리움)
    ─────────────────────────────────────────────────────
    공격자는 전체 스테이킹 ETH의 51% 이상을 보유해야 함.

    슬래싱(Correlated Slashing):
      - 공격 규모에 비례하여 스테이킹 지분을 소각.
      - 51% 공격 수준이면 관여 validator 지분 거의 전액 소각.
      - 공격 성공 여부와 무관하게 자본 손실 → 경제적으로 자살 행위.
    """
    attack_eth      = staked_eth * 0.51
    attack_cost     = attack_eth * eth_price
    slashing_value  = attack_eth * eth_price   # 보수적: 전액 소각 가정
    return {
        "total":          attack_cost,
        "attack_eth":     attack_eth,
        "slashing_value": slashing_value,
    }


def calc_sol_attack_cost(staked_sol: float, sol_price: float) -> dict:
    """
    PoS 51% 공격 비용 (솔라나)
    ─────────────────────────────────────────────────────
    Tower BFT / PoH 기반 합의.
    이중 투표(equivocation) 감지 시 validator 지분 전액 소각.
    ETH 슬래싱과 달리 커뮤니티 개입이 필요한 경우도 있음.
    """
    attack_sol      = staked_sol * 0.51
    attack_cost     = attack_sol * sol_price
    slashing_value  = attack_sol * sol_price   # 이중 서명 시 전액 소각
    return {
        "total":          attack_cost,
        "attack_sol":     attack_sol,
        "slashing_value": slashing_value,
    }


def calc_sri(attack_cost: float, market_cap: float) -> float:
    """
    보안 강건성 지수 (Security Robustness Index)
    SRI = 51% 공격 비용 / 시가총액
    높을수록 공격 대비 경제적 방어력이 강함.
    SRI ≥ 1.0 이면 공격 비용 ≥ 시총 (이론적 최강 방어).
    """
    return attack_cost / market_cap if market_cap > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════
#  차트 함수
# ═══════════════════════════════════════════════════════════════════════

def _dark(fig: go.Figure, height: int = 420) -> go.Figure:
    """공통 다크 테마 적용"""
    fig.update_layout(
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(
            color=THEME["text"],
            family="Inter, -apple-system, sans-serif",
            size=12,
        ),
        xaxis=dict(gridcolor=THEME["grid"], linecolor=THEME["grid"], zeroline=False),
        yaxis=dict(gridcolor=THEME["grid"], linecolor=THEME["grid"], zeroline=False),
        legend=dict(
            bgcolor=THEME["paper"],
            bordercolor=THEME["grid"],
            borderwidth=1,
            font=dict(color=THEME["text"], size=11),
        ),
        margin=dict(t=75, b=40, l=60, r=30),
        height=height,
        hovermode="x unified",
    )
    if fig.layout.title.text:
        fig.update_layout(title=dict(font=dict(color=THEME["text"], size=14)))
    return fig


def chart_attack_cost_bar(costs: dict, mcaps: dict) -> go.Figure:
    """51% 공격 비용 vs 시가총액 그룹 바 차트"""
    chains = ["BTC", "ETH", "SOL"]
    colors = [BTC_C, ETH_C, SOL_C]
    mc_alpha = [
        "rgba(247,147,26,0.2)",
        "rgba(98,126,234,0.2)",
        "rgba(153,69,255,0.2)",
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="51% 공격 비용",
        x=chains,
        y=[costs[c] / 1e9 for c in chains],
        marker_color=colors,
        text=[f"${costs[c]/1e9:.1f}B" for c in chains],
        textposition="outside",
        textfont=dict(color=THEME["text"]),
        hovertemplate="%{x}: $%{y:.2f}B<extra>공격 비용</extra>",
    ))
    fig.add_trace(go.Bar(
        name="시가총액",
        x=chains,
        y=[mcaps[c] / 1e9 for c in chains],
        marker_color=mc_alpha,
        marker_line_color=colors,
        marker_line_width=1.5,
        text=[f"${mcaps[c]/1e9:.0f}B" for c in chains],
        textposition="outside",
        textfont=dict(color=THEME["subtext"]),
        hovertemplate="%{x}: $%{y:.0f}B<extra>시가총액</extra>",
    ))
    fig.update_layout(
        barmode="group",
        title=dict(text="51% 공격 비용 vs 시가총액 ($B)"),
        yaxis_title="금액 ($B)",
        bargap=0.2,
        bargroupgap=0.05,
    )
    return _dark(fig, height=450)


def chart_sri_bar(sri: dict) -> go.Figure:
    """보안 강건성 지수 바 차트 (SRI = 공격 비용 / 시총 × 100)"""
    chains = list(sri.keys())
    vals   = [sri[c] * 100 for c in chains]
    colors = {"BTC": BTC_C, "ETH": ETH_C, "SOL": SOL_C}

    fig = go.Figure(go.Bar(
        x=chains,
        y=vals,
        marker_color=[colors[c] for c in chains],
        text=[f"{v:.1f}%" for v in vals],
        textposition="outside",
        textfont=dict(color=THEME["text"]),
        hovertemplate="%{x} SRI: %{y:.2f}%<extra></extra>",
    ))
    # SRI = 100% 참고선 (공격 비용 = 시총)
    fig.add_hline(
        y=100,
        line_dash="dot",
        line_color=THEME["gold"],
        annotation_text="SRI 100% 기준선",
        annotation_font_color=THEME["gold"],
        annotation_font_size=11,
        annotation_position="bottom right",
    )
    fig.update_layout(
        title=dict(text="보안 강건성 지수 — SRI (공격 비용 / 시총 × 100)"),
        yaxis_title="SRI (%)",
        showlegend=False,
    )
    return _dark(fig, height=450)


def chart_btc_attack_history(
    hashrate_hist: pd.Series,
    asic_ths: float,
    asic_price: float,
    asic_power_w: float,
    electricity: float,
    attack_hours: float,
) -> go.Figure | None:
    """
    BTC 51% 공격 비용 추이
    해시레이트 히스토리 × 사이드바 ASIC 파라미터로 계산
    """
    if hashrate_hist.empty:
        return None

    hw_list, el_list, total_list = [], [], []
    for ths in hashrate_hist.values:
        c = calc_btc_attack_cost(
            ths, asic_ths, asic_price, asic_power_w, electricity, attack_hours
        )
        hw_list.append(c["hardware"] / 1e9)
        el_list.append(c["energy"] / 1e6)
        total_list.append(c["total"] / 1e9)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hashrate_hist.index,
        y=total_list,
        name="총 공격 비용",
        line=dict(color=BTC_C, width=2.5),
        hovertemplate="%{x|%Y-%m-%d}: $%{y:.2f}B<extra>총 비용</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=hashrate_hist.index,
        y=hw_list,
        name="하드웨어 비용",
        line=dict(color=THEME["gold"], width=1.5, dash="dot"),
        hovertemplate="%{x|%Y-%m-%d}: $%{y:.2f}B<extra>하드웨어</extra>",
    ))
    fig.update_layout(
        title=dict(text="BTC 51% 공격 비용 추이"),
        yaxis_title="비용 ($B)",
        legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
    )
    return _dark(fig, height=400)


def chart_pos_attack_history(
    eth_hist: pd.Series,
    sol_hist: pd.Series,
    staked_eth: float,
    staked_sol: float,
) -> go.Figure:
    """
    ETH / SOL 51% 공격 비용 추이
    가격 히스토리 × 현재 스테이킹 수량으로 계산
    (스테이킹 수량은 최근 수개월 동안 비교적 안정적)
    """
    fig = go.Figure()

    if not eth_hist.empty:
        eth_cost = eth_hist * staked_eth * 0.51 / 1e9
        fig.add_trace(go.Scatter(
            x=eth_hist.index,
            y=eth_cost.values,
            name="ETH 공격 비용",
            line=dict(color=ETH_C, width=2),
            hovertemplate="%{x|%Y-%m-%d}: $%{y:.1f}B<extra>ETH</extra>",
        ))

    if not sol_hist.empty:
        sol_cost = sol_hist * staked_sol * 0.51 / 1e9
        fig.add_trace(go.Scatter(
            x=sol_hist.index,
            y=sol_cost.values,
            name="SOL 공격 비용",
            line=dict(color=SOL_C, width=2),
            hovertemplate="%{x|%Y-%m-%d}: $%{y:.1f}B<extra>SOL</extra>",
        ))

    fig.update_layout(
        title=dict(text="ETH / SOL 51% 공격 비용 추이"),
        yaxis_title="공격 비용 ($B)",
        legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
    )
    return _dark(fig, height=400)


# ═══════════════════════════════════════════════════════════════════════
#  지리적 분산 분석 차트
# ═══════════════════════════════════════════════════════════════════════

def chart_hashrate_choropleth() -> go.Figure:
    """
    Plotly Choropleth: 국가별 BTC 해시레이트 점유율 세계지도
    ISO-3 코드 기반, 기타(iso3=None) 제외
    """
    geo = [d for d in HASHRATE_GEO if d["iso3"] is not None]
    df  = pd.DataFrame(geo)

    fig = go.Figure(go.Choropleth(
        locations      = df["iso3"],
        z              = df["share"],
        text           = df["country"],
        customdata     = df["risk"],
        colorscale     = [
            [0.0,  "#1e2538"],   # 데이터 없는 나라와 구분되는 어두운 색
            [0.15, "#4a3015"],
            [0.4,  "#8b5a1a"],
            [0.7,  "#c4781f"],
            [1.0,  BTC_C],      # 최고 점유율: 비트코인 오렌지
        ],
        zmin=0, zmax=40,
        hovertemplate  = (
            "<b>%{text}</b><br>"
            "해시레이트 점유율: %{z:.1f}%<br>"
            "지정학적 리스크: %{customdata}"
            "<extra></extra>"
        ),
        colorbar=dict(
            title     = dict(text="점유율 (%)", font=dict(color=THEME["text"])),
            tickfont  = dict(color=THEME["text"]),
            bgcolor   = THEME["paper"],
            bordercolor = THEME["grid"],
            thickness = 14,
            len       = 0.7,
        ),
        marker=dict(
            line=dict(color=THEME["grid"], width=0.5)
        ),
    ))

    fig.update_geos(
        projection_type  = "natural earth",
        showcoastlines   = True,  coastlinecolor  = THEME["grid"],
        showland         = True,  landcolor       = "#1a2030",
        showocean        = True,  oceancolor      = THEME["bg"],
        showlakes        = True,  lakecolor       = THEME["bg"],
        showframe        = False,
        bgcolor          = THEME["bg"],
    )
    fig.update_layout(
        title      = dict(text="BTC 해시레이트 국가별 분포 (CCAF CBECI 2023)",
                          font=dict(color=THEME["text"], size=14)),
        paper_bgcolor = THEME["bg"],
        plot_bgcolor  = THEME["bg"],
        font          = dict(color=THEME["text"]),
        geo           = dict(bgcolor=THEME["bg"]),
        margin        = dict(t=60, b=10, l=0, r=0),
        height        = 440,
    )
    return fig


def chart_nakamoto_coalition() -> tuple[go.Figure, int, float, float]:
    """
    나카모토 계수 (물리적) 시각화
    - 국가별 해시레이트 내림차순 바 차트
    - 누적 점유율 선 오버레이
    - 51% 임계선 강조
    - 반환: (fig, 나카모토계수, 상위3국합계, 지정학적위험지수)
    """
    geo     = [d for d in HASHRATE_GEO if d["iso3"] is not None]
    sorted_ = sorted(geo, key=lambda d: d["share"], reverse=True)

    countries = [d["country"]  for d in sorted_]
    shares    = [d["share"]    for d in sorted_]
    risks     = [d["risk"]     for d in sorted_]
    cumul     = [sum(shares[:i+1]) for i in range(len(shares))]

    # 나카모토 계수: 누적 51%에 처음 도달하는 국가 수
    nakamoto = next((i + 1 for i, c in enumerate(cumul) if c >= 51), len(sorted_))

    top3_sum   = sum(shares[:3])
    geo_risk   = sum(d["share"] for d in sorted_ if d["iso3"] in _HIGH_RISK_ISO)

    # 바 색상: 51% 연합에 포함되는 나라는 오렌지, 나머지는 어둡게
    risk_border = {"낮음": "#3fb950", "중간": "#f0883e", "높음": "#f85149"}
    bar_colors  = [
        BTC_C if i < nakamoto else THEME["card"]
        for i in range(len(countries))
    ]
    bar_borders = [risk_border[r] for r in risks]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x            = countries,
        y            = shares,
        name         = "개별 점유율",
        marker_color = bar_colors,
        marker_line  = dict(color=bar_borders, width=2),
        text         = [f"{s:.1f}%" for s in shares],
        textposition = "outside",
        textfont     = dict(color=THEME["text"], size=11),
        hovertemplate= "%{x}: %{y:.1f}%<extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x          = countries,
        y          = cumul,
        name       = "누적 점유율",
        mode       = "lines+markers",
        line       = dict(color=THEME["teal"], width=2, dash="dot"),
        marker     = dict(size=6, color=THEME["teal"]),
        hovertemplate = "%{x} 누적: %{y:.1f}%<extra></extra>",
    ), secondary_y=True)

    # 51% 임계선
    fig.add_hline(y=51, line_dash="dash", line_color=THEME["red"],
                  secondary_y=True)
    fig.add_annotation(
        text="← 51% 공격 임계선", x=len(countries) - 0.5, xref="x",
        y=51, yref="y2",
        showarrow=False,
        font=dict(color=THEME["red"], size=11),
        xanchor="right", yanchor="bottom",
    )

    fig.update_layout(
        title=dict(
            text=f"나카모토 계수 (물리) = <b>{nakamoto}개국</b> — 최소 연합으로 51% 달성",
            font=dict(color=THEME["text"], size=13),
        ),
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font          = dict(color=THEME["text"], size=12),
        xaxis         = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"]),
        yaxis         = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"],
                             title="개별 점유율 (%)"),
        yaxis2        = dict(gridcolor="rgba(0,0,0,0)", linecolor=THEME["grid"],
                             title="누적 점유율 (%)", range=[0, 110]),
        legend        = dict(bgcolor=THEME["paper"], bordercolor=THEME["grid"],
                             borderwidth=1, font=dict(color=THEME["text"], size=11),
                             x=0.65, y=0.98),
        margin        = dict(t=75, b=40, l=55, r=55),
        height        = 430,
        bargap        = 0.3,
    )
    return fig, nakamoto, top3_sum, geo_risk


def chart_energy_sources() -> go.Figure:
    """
    국가별 채굴 에너지원 구성 — 수평 누적 바 차트
    친환경(수력·재생) 비중이 높을수록 지속가능성↑, 탄소 비용 하락
    """
    geo     = [d for d in HASHRATE_GEO if d["iso3"] is not None and d["energy"]]
    sorted_ = sorted(geo, key=lambda d: d["share"], reverse=True)
    countries = [d["country"] for d in sorted_]

    fig = go.Figure()
    for cat, color in _ENERGY_COLORS.items():
        vals = [d["energy"].get(cat, 0) for d in sorted_]
        fig.add_trace(go.Bar(
            name          = cat,
            y             = countries,
            x             = vals,
            orientation   = "h",
            marker_color  = color,
            hovertemplate = f"<b>%{{y}}</b> — {cat}: %{{x:.0f}}%<extra></extra>",
        ))

    fig.update_layout(
        barmode    = "stack",
        title      = dict(text="국가별 채굴 에너지원 구성",
                          font=dict(color=THEME["text"], size=14)),
        xaxis      = dict(title="에너지 비중 (%)", range=[0, 100],
                          gridcolor=THEME["grid"], linecolor=THEME["grid"]),
        yaxis      = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"]),
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font          = dict(color=THEME["text"], size=12),
        legend        = dict(bgcolor=THEME["paper"], bordercolor=THEME["grid"],
                             borderwidth=1, font=dict(color=THEME["text"], size=11),
                             orientation="h", y=-0.18, xanchor="center", x=0.5),
        margin        = dict(t=75, b=110, l=90, r=30),
        height        = 430,
    )
    return fig


def chart_eth_staking_entities() -> tuple[go.Figure, int, int]:
    """
    ETH 스테이킹 엔티티 집중도 도넛 차트
    - 33% 임계선: 라이브니스 공격 가능 (최종성 방해)
    - 51% 임계선: 검열 가능
    - 반환: (fig, entity_nakamoto_33, entity_nakamoto_51)
    """
    entities  = [d["entity"] for d in ETH_STAKING_ENTITIES]
    shares    = [d["share"]  for d in ETH_STAKING_ENTITIES]
    colors    = [d["color"]  for d in ETH_STAKING_ENTITIES]
    risks     = [d["risk"]   for d in ETH_STAKING_ENTITIES]
    notes     = [d["note"]   for d in ETH_STAKING_ENTITIES]
    total     = sum(shares)

    # 기관 엔티티만 정렬 (솔로·미분류 제외), 나카모토 계수 계산
    inst = sorted(
        [d for d in ETH_STAKING_ENTITIES if d["entity"] in _ETH_INSTITUTIONAL],
        key=lambda d: d["share"], reverse=True,
    )
    inst_shares = [d["share"] for d in inst]
    inst_cumul  = [sum(inst_shares[:i+1]) for i in range(len(inst))]

    nak_33 = next((i+1 for i, c in enumerate(inst_cumul) if c >= 33.4), len(inst))
    nak_51 = next((i+1 for i, c in enumerate(inst_cumul) if c >= 51.0), len(inst))

    # 슬라이스 텍스트: 5% 이상만 레이블 표시
    text_list = [
        f"{e}<br>{s:.1f}%" if s / total >= 0.05 else f"{s:.1f}%" if s / total >= 0.02 else ""
        for e, s in zip(entities, shares)
    ]

    fig = go.Figure(go.Pie(
        labels        = entities,
        values        = shares,
        hole          = 0.5,
        text          = text_list,
        textinfo      = "text",
        textfont      = dict(size=10, color=THEME["text"]),
        textposition  = "outside",
        customdata    = list(zip(risks, notes)),
        hovertemplate = (
            "<b>%{label}</b><br>"
            "점유율: %{value:.1f}%<br>"
            "리스크: %{customdata[0]}<br>"
            "%{customdata[1]}"
            "<extra></extra>"
        ),
        marker = dict(
            colors     = colors,
            line       = dict(color=THEME["bg"], width=1.5),
        ),
        sort     = False,
        rotation = 90,
    ))

    # 33% / 51% 임계선 텍스트를 도넛 중앙에 표시
    lido_share = next(d["share"] for d in ETH_STAKING_ENTITIES if d["entity"] == "Lido")

    fig.update_layout(
        title       = dict(text="ETH 스테이킹 엔티티 집중도 (2025 Q1 추정)",
                           font=dict(color=THEME["text"], size=13)),
        annotations = [dict(
            text      = f"<b>Lido</b><br>{lido_share:.0f}%",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow = False,
            font      = dict(size=14, color=ETH_C),
        )],
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font          = dict(color=THEME["text"], size=12),
        showlegend    = False,
        margin        = dict(t=75, b=80, l=80, r=80),
        height        = 460,
    )
    return fig, nak_33, nak_51


def chart_entity_nakamoto_bar() -> go.Figure:
    """
    ETH 기관 엔티티 나카모토 계수 바 차트 (솔로·미분류 제외)
    33% (라이브니스) / 51% (검열) 두 임계선 표시
    """
    inst = sorted(
        [d for d in ETH_STAKING_ENTITIES if d["entity"] in _ETH_INSTITUTIONAL],
        key=lambda d: d["share"], reverse=True,
    )
    entities  = [d["entity"] for d in inst]
    shares    = [d["share"]  for d in inst]
    cumul     = [sum(shares[:i+1]) for i in range(len(shares))]

    nak_33 = next((i+1 for i, c in enumerate(cumul) if c >= 33.4), len(inst))
    nak_51 = next((i+1 for i, c in enumerate(cumul) if c >= 51.0), len(inst))

    bar_colors = []
    for c in cumul:
        if c <= 33.4:
            bar_colors.append(ETH_C)
        elif c <= 51.0:
            bar_colors.append(THEME["orange"])
        else:
            bar_colors.append(THEME["red"])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x            = entities,
        y            = shares,
        name         = "개별 점유율",
        marker_color = bar_colors,
        marker_line  = dict(color=[d["color"] for d in inst], width=1.5),
        text         = [f"{s:.1f}%" for s in shares],
        textposition = "outside",
        textfont     = dict(color=THEME["text"], size=11),
        hovertemplate= "%{x}: %{y:.1f}%<extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x          = entities,
        y          = cumul,
        name       = "누적 점유율",
        mode       = "lines+markers",
        line       = dict(color=THEME["teal"], width=2, dash="dot"),
        marker     = dict(size=6, color=THEME["teal"]),
        hovertemplate = "%{x} 누적: %{y:.1f}%<extra></extra>",
    ), secondary_y=True)

    # 33% 라이브니스 임계선
    fig.add_hline(y=33.4, line_dash="dot", line_color=THEME["orange"], secondary_y=True)
    fig.add_annotation(
        text="33% 라이브니스 임계선", x=len(entities) - 0.5, xref="x",
        y=33.4, yref="y2", showarrow=False,
        font=dict(color=THEME["orange"], size=10),
        xanchor="right", yanchor="bottom",
    )
    # 51% 검열 임계선
    fig.add_hline(y=51.0, line_dash="dash", line_color=THEME["red"], secondary_y=True)
    fig.add_annotation(
        text="51% 검열 임계선", x=len(entities) - 0.5, xref="x",
        y=51.0, yref="y2", showarrow=False,
        font=dict(color=THEME["red"], size=10),
        xanchor="right", yanchor="bottom",
    )

    fig.update_layout(
        title = dict(
            text  = f"기관 엔티티 나카모토 계수 — 33%: {nak_33}개 · 51%: {nak_51}개",
            font  = dict(color=THEME["text"], size=13),
        ),
        paper_bgcolor = THEME["paper"],
        plot_bgcolor  = THEME["bg"],
        font          = dict(color=THEME["text"], size=12),
        xaxis         = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"]),
        yaxis         = dict(gridcolor=THEME["grid"], linecolor=THEME["grid"],
                             title="개별 점유율 (%)"),
        yaxis2        = dict(gridcolor="rgba(0,0,0,0)", linecolor=THEME["grid"],
                             title="누적 점유율 (%)", range=[0, 120]),
        legend        = dict(bgcolor=THEME["paper"], bordercolor=THEME["grid"],
                             borderwidth=1, font=dict(color=THEME["text"], size=11),
                             x=0.65, y=0.98),
        margin        = dict(t=75, b=40, l=55, r=55),
        height        = 400,
        bargap        = 0.3,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════
#  메인
# ═══════════════════════════════════════════════════════════════════════

def main():
    st.title("🔐 블록체인 보안 강건성 분석")
    st.caption(
        "BTC (PoW) vs ETH (PoS) vs SOL (PoS) — "
        "51% 공격 경제 비용 · 보안 강건성 지수 · 슬래싱 리스크 시뮬레이터"
    )
    st.info(
        "📌 **교육 목적 분석**: 공개 온체인 데이터로 산출한 이론적 경제 비용입니다. "
        "실제 공격은 시장 충격·커뮤니티 대응·법적 제재 등 추가 장벽이 존재합니다.",
        icon="ℹ️",
    )

    # ── 사이드바 파라미터 ─────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ 시뮬레이션 파라미터")

        st.subheader("₿ Bitcoin — ASIC 설정")
        asic_ths = st.slider(
            "ASIC 해시레이트 (TH/s)", 50, 500, 200, 10,
            help="Antminer S21 Pro = 234 TH/s · S21 = 200 TH/s",
        )
        asic_price = st.number_input(
            "ASIC 1대 단가 ($)", min_value=500, max_value=30_000,
            value=4_000, step=500,
            help="2025년 기준 S21 시세: $2,000–$6,000",
        )
        asic_power_w = st.slider(
            "ASIC 소비 전력 (W)", 500, 8_000, 3_500, 100,
        )
        electricity = st.slider(
            "전기요금 ($/kWh)", 0.01, 0.25, 0.07, 0.01,
            help="글로벌 채굴 평균: $0.05–$0.08/kWh",
        )
        attack_hours = st.slider(
            "공격 지속 시간 (시간)", 1, 168, 1, 1,
            help="1시간 = 6블록 (이중지불 최소 단위)",
        )

        st.subheader("◎ Solana — 스테이킹 비율")
        sol_stake_ratio = st.slider(
            "SOL 스테이킹 비율 (%)", 50, 80, 65, 1,
            help="현재 실제 스테이킹 비율: 약 65–68%",
        )

        st.subheader("📅 분석 기간")
        history_days = st.selectbox(
            "히스토리 기간", [30, 60, 90, 180, 365], index=3,
        )

    # ── 데이터 로드 ───────────────────────────────────────────────────
    with st.spinner("온체인 데이터 로드 중..."):
        try:
            coin_data = fetch_coin_data()
        except Exception:
            coin_data = {}

        staked_eth = fetch_eth_staked()

        def _g(coin_id, field, fallback):
            return (coin_data.get(coin_id) or {}).get(field, fallback)

        btc_price  = _g("bitcoin",  "current_price",        95_000)
        btc_mcap   = _g("bitcoin",  "market_cap",    1_900_000_000_000)
        eth_price  = _g("ethereum", "current_price",         3_500)
        eth_mcap   = _g("ethereum", "market_cap",      420_000_000_000)
        sol_price  = _g("solana",   "current_price",           180)
        sol_mcap   = _g("solana",   "market_cap",       85_000_000_000)
        sol_supply = _g("solana",   "circulating_supply",  465_000_000)

    staked_sol = sol_supply * (sol_stake_ratio / 100)

    # ── 해시레이트 & 공격 비용 계산 ───────────────────────────────────
    hashrate_hist = fetch_btc_hashrate_history(days=history_days)
    btc_hashrate_ths = (
        float(hashrate_hist.iloc[-1])
        if not hashrate_hist.empty
        else 800_000_000   # fallback: ~800 EH/s
    )

    btc_cost = calc_btc_attack_cost(
        btc_hashrate_ths, asic_ths, asic_price,
        asic_power_w, electricity, attack_hours,
    )
    eth_cost = calc_eth_attack_cost(staked_eth, eth_price)
    sol_cost = calc_sol_attack_cost(staked_sol, sol_price)

    btc_sri = calc_sri(btc_cost["total"], btc_mcap)
    eth_sri = calc_sri(eth_cost["total"], eth_mcap)
    sol_sri = calc_sri(sol_cost["total"], sol_mcap)

    # ── 섹션 1: 핵심 지표 카드 ────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💸 현재 51% 공격 비용")

    col1, col2, col3 = st.columns(3)

    def _card(col, symbol, name, color, cost_b, subtitle, sri,
              extra_label, extra_val, extra_color):
        with col:
            st.markdown(f"""
<div style="background:{THEME['card']};border-left:4px solid {color};
            padding:1.2rem 1.4rem;border-radius:10px;min-height:170px;">
  <div style="color:{THEME['subtext']};font-size:0.78rem;">{symbol}&nbsp;{name}</div>
  <div style="color:{color};font-size:2rem;font-weight:700;">${cost_b:.1f}B</div>
  <div style="color:{THEME['subtext']};font-size:0.74rem;margin-top:0.2rem;">{subtitle}</div>
  <hr style="border-color:{THEME['grid']};margin:0.6rem 0 0.4rem;">
  <div style="display:flex;justify-content:space-between;margin-bottom:0.2rem;">
    <span style="color:{THEME['subtext']};font-size:0.74rem;">보안 강건성 지수 (SRI)</span>
    <span style="color:{color};font-weight:600;">{sri*100:.1f}%</span>
  </div>
  <div style="display:flex;justify-content:space-between;">
    <span style="color:{THEME['subtext']};font-size:0.74rem;">{extra_label}</span>
    <span style="color:{extra_color};font-weight:600;">{extra_val}</span>
  </div>
</div>""", unsafe_allow_html=True)

    _card(
        col1, "₿", "Bitcoin (PoW)", BTC_C,
        btc_cost["total"] / 1e9,
        f"ASIC {btc_cost['num_asics']:,}대 + 전기 ${btc_cost['energy']/1e6:.0f}M/{attack_hours}h",
        btc_sri,
        "하드웨어 재사용", "가능 (중고 판매)", THEME["green"],
    )
    _card(
        col2, "Ξ", "Ethereum (PoS)", ETH_C,
        eth_cost["total"] / 1e9,
        f"스테이킹 {staked_eth/1e6:.1f}M ETH × 51% × ${eth_price:,.0f}",
        eth_sri,
        "슬래싱 확정 손실", f"${eth_cost['slashing_value']/1e9:.1f}B", THEME["red"],
    )
    _card(
        col3, "◎", "Solana (PoS)", SOL_C,
        sol_cost["total"] / 1e9,
        f"스테이킹 {staked_sol/1e6:.1f}M SOL × 51% × ${sol_price:,.0f}",
        sol_sri,
        "슬래싱 (이중서명)", f"${sol_cost['slashing_value']/1e9:.1f}B", THEME["orange"],
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 섹션 2: 비교 차트 ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 공격 비용 & 보안 강건성 지수 비교")

    c_a, c_b = st.columns(2)
    with c_a:
        st.plotly_chart(
            chart_attack_cost_bar(
                {"BTC": btc_cost["total"], "ETH": eth_cost["total"], "SOL": sol_cost["total"]},
                {"BTC": btc_mcap, "ETH": eth_mcap, "SOL": sol_mcap},
            ),
            use_container_width=True,
        )
    with c_b:
        st.plotly_chart(
            chart_sri_bar({"BTC": btc_sri, "ETH": eth_sri, "SOL": sol_sri}),
            use_container_width=True,
        )

    # ── 섹션 3: 공격 비용 추이 ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 공격 비용 추이")

    eth_hist = fetch_price_history("ethereum", history_days)
    sol_hist = fetch_price_history("solana",   history_days)

    c_c, c_d = st.columns(2)
    with c_c:
        btc_fig = chart_btc_attack_history(
            hashrate_hist, asic_ths, asic_price,
            asic_power_w, electricity, attack_hours,
        )
        if btc_fig:
            st.plotly_chart(btc_fig, use_container_width=True)
        else:
            st.info("blockchain.info 해시레이트 데이터를 불러오지 못했습니다.")
    with c_d:
        st.plotly_chart(
            chart_pos_attack_history(eth_hist, sol_hist, staked_eth, staked_sol),
            use_container_width=True,
        )

    # ── 섹션 4: BTC 세부 분석 ────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔧 BTC 공격 세부 분석")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("필요 ASIC 수량",        f"{btc_cost['num_asics']:,} 대")
    m2.metric("필요 해시파워",          f"{btc_cost['attack_ehs']:.1f} EH/s")
    m3.metric("하드웨어 비용",          f"${btc_cost['hardware']/1e9:.2f}B")
    m4.metric(f"전기 비용 ({attack_hours}h)", f"${btc_cost['energy']/1e6:.1f}M")

    with st.expander("⚡ 전기요금 시나리오별 BTC 공격 비용"):
        rows = []
        for rate in [0.02, 0.04, 0.07, 0.10, 0.15, 0.20]:
            c = calc_btc_attack_cost(
                btc_hashrate_ths, asic_ths, asic_price,
                asic_power_w, rate, attack_hours,
            )
            rows.append({
                "전기요금 ($/kWh)":  f"${rate:.2f}",
                "하드웨어 ($B)":     f"${c['hardware']/1e9:.2f}B",
                f"전기 비용 ({attack_hours}h)": f"${c['energy']/1e6:.1f}M",
                "총 공격 비용 ($B)": f"${c['total']/1e9:.2f}B",
                "SRI (시총 대비)":   f"{calc_sri(c['total'], btc_mcap)*100:.2f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("💻 ASIC 단가 시나리오별 BTC 공격 비용"):
        rows2 = []
        for price in [1_000, 2_000, 4_000, 6_000, 10_000, 15_000]:
            c = calc_btc_attack_cost(
                btc_hashrate_ths, asic_ths, price,
                asic_power_w, electricity, attack_hours,
            )
            rows2.append({
                "ASIC 단가 ($)":     f"${price:,}",
                "하드웨어 ($B)":     f"${c['hardware']/1e9:.2f}B",
                "총 공격 비용 ($B)": f"${c['total']/1e9:.2f}B",
                "SRI (시총 대비)":   f"{calc_sri(c['total'], btc_mcap)*100:.2f}%",
            })
        st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)

    # ── 섹션 5: 지리적 분산도 분석 (BTC 전용) ───────────────────────
    st.markdown("---")
    st.markdown("### 🌍 BTC 해시파워 지리적 분산도 분석")
    st.caption("데이터: CCAF CBECI 2023년 추정치 (6~12개월 주기 발표, 실시간 아님)")

    # ── 지리적 지표 계산 ──────────────────────────────────────────
    geo_valid    = [d for d in HASHRATE_GEO if d["iso3"] is not None]
    geo_sorted   = sorted(geo_valid, key=lambda d: d["share"], reverse=True)
    top3_share   = sum(d["share"] for d in geo_sorted[:3])
    geo_risk_pct = sum(d["share"] for d in geo_valid if d["iso3"] in _HIGH_RISK_ISO)

    # HHI (허핀달-허쉬만 지수): 0~1, 높을수록 집중도 높음
    all_shares = [d["share"] for d in HASHRATE_GEO]   # 기타 포함
    hhi = sum((s / 100) ** 2 for s in all_shares)

    # 친환경 채굴 비율: 해시레이트 가중 평균
    total_w   = sum(d["share"] for d in geo_valid if d["energy"])
    renew_pct = (
        sum(d["share"] * d["energy"].get("수력·재생에너지", 0) / 100
            for d in geo_valid if d["energy"])
        / total_w * 100
        if total_w > 0 else 0
    )

    # 나카모토 계수 계산 (표시용)
    cumul = 0
    nakamoto_preview = 0
    for d in geo_sorted:
        cumul += d["share"]
        nakamoto_preview += 1
        if cumul >= 51:
            break

    # ── 지표 요약 카드 ────────────────────────────────────────────
    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("나카모토 계수 (물리)", f"{nakamoto_preview} 개국",
              help="최소 몇 개국이 공모해야 51% 달성 가능한가")
    g2.metric("상위 3개국 점유율", f"{top3_share:.1f}%",
              help="미국 + 중국 + 카자흐스탄")
    g3.metric("지정학적 위험 점유율", f"{geo_risk_pct:.1f}%",
              help="중국·러시아·카자흐스탄 합산 해시레이트")
    g4.metric("친환경 채굴 비율", f"{renew_pct:.1f}%",
              help="수력·재생에너지 기반 채굴 가중 평균")
    g5.metric("집중도 지수 (HHI)", f"{hhi:.3f}",
              help="0.25 이상 = 고농도 집중 (US DOJ 기준)")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 세계지도 ────────────────────────────────────────────────
    st.plotly_chart(chart_hashrate_choropleth(), use_container_width=True)

    # ── 나카모토 계수 차트 + 에너지 구성 차트 ─────────────────────
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        geo_fig, nakamoto, _, geo_risk = chart_nakamoto_coalition()
        st.plotly_chart(geo_fig, use_container_width=True)

        # 나카모토 계수 해석 박스
        risk_color = THEME["red"] if nakamoto <= 2 else (
            THEME["orange"] if nakamoto <= 3 else THEME["green"]
        )
        risk_label = "⚠️ 매우 높음" if nakamoto <= 2 else (
            "🟡 중간" if nakamoto <= 3 else "✅ 낮음"
        )
        st.markdown(f"""
<div style="background:{THEME['card']};border-left:4px solid {risk_color};
            padding:0.9rem 1.2rem;border-radius:8px;margin-top:-8px;">
  <div style="color:{THEME['subtext']};font-size:0.76rem;">지정학적 집중 리스크</div>
  <div style="color:{risk_color};font-size:1.3rem;font-weight:700;">{risk_label}</div>
  <div style="color:{THEME['text']};font-size:0.8rem;margin-top:0.3rem;">
    오렌지 바(상위 {nakamoto}개국) 합산 ≥ 51% —
    해당 국가 정부 공모 시 이론적 통제 가능<br>
    규제 리스크 국가(중·러·카자흐) 점유율: <b>{geo_risk:.1f}%</b>
  </div>
</div>""", unsafe_allow_html=True)

    with col_g2:
        st.plotly_chart(chart_energy_sources(), use_container_width=True)

        # 에너지 해석 박스
        st.markdown(f"""
<div style="background:{THEME['card']};border-left:4px solid {THEME['teal']};
            padding:0.9rem 1.2rem;border-radius:8px;margin-top:-8px;">
  <div style="color:{THEME['subtext']};font-size:0.76rem;">네트워크 친환경 비율</div>
  <div style="color:{THEME['teal']};font-size:1.3rem;font-weight:700;">{renew_pct:.1f}% 재생에너지</div>
  <div style="color:{THEME['text']};font-size:0.8rem;margin-top:0.3rem;">
    카자흐스탄·중국의 석탄 의존도가 전체 평균을 낮춤.<br>
    캐나다(82%)·미국(58%) 등 서방권은 수력 중심으로 친환경 비율 높음.
  </div>
</div>""", unsafe_allow_html=True)

    with st.expander("📌 데이터 출처 및 방법론"):
        st.markdown("""
**해시레이트 지리적 분포 데이터**
- Cambridge Centre for Alternative Finance (CCAF) — *Cambridge Bitcoin Electricity Consumption Index (CBECI)*
- VPN 사용 등으로 실제 위치 추정에 오차 존재 (특히 중국 수치)
- 6~12개월 주기로 업데이트되는 연구 데이터

**에너지 구성 데이터**
- Bitcoin Mining Council (BMC) 2023 Q3 자발적 설문 (전체 해시레이트 약 50% 커버)
- CCAF 지역별 전력망 에너지 믹스 추정치

**나카모토 계수 (물리적)**
- 소프트웨어 분산도를 측정하는 기존 나카모토 계수와 다르게,
  여기서는 **지리적·지정학적 해시레이트 집중도**를 측정합니다.
- 낮을수록 소수 국가 정부에 의한 이론적 공격 가능성이 높아짐을 의미합니다.
""")

    # ── 섹션 6: ETH 자본적 집중도 분석 ─────────────────────────────
    st.markdown("---")
    st.markdown("### 🏛️ ETH 스테이킹 자본 집중도 분석")
    st.caption("데이터: rated.network / beaconcha.in 2025 Q1 추정치")

    # ETH 엔티티 지표 계산
    inst_data    = sorted(
        [d for d in ETH_STAKING_ENTITIES if d["entity"] in _ETH_INSTITUTIONAL],
        key=lambda d: d["share"], reverse=True,
    )
    inst_shares  = [d["share"] for d in inst_data]
    inst_cumul   = [sum(inst_shares[:i+1]) for i in range(len(inst_shares))]
    nak33_val    = next((i+1 for i, c in enumerate(inst_cumul) if c >= 33.4), len(inst_data))
    nak51_val    = next((i+1 for i, c in enumerate(inst_cumul) if c >= 51.0), len(inst_data))
    lido_share_v = next(d["share"] for d in ETH_STAKING_ENTITIES if d["entity"] == "Lido")
    top_inst_3   = sum(inst_shares[:3])

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("최대 단일 엔티티 (Lido)", f"{lido_share_v:.1f}%",
              help="33% 초과 시 라이브니스 공격 가능")
    e2.metric("엔티티 나카모토 계수 (33%)", f"{nak33_val}개",
              help="라이브니스 공격: 최소 몇 개 기관이 공모해야 하는가")
    e3.metric("엔티티 나카모토 계수 (51%)", f"{nak51_val}개",
              help="검열 공격: 최소 몇 개 기관이 공모해야 하는가")
    e4.metric("상위 3개 기관 합산", f"{top_inst_3:.1f}%",
              help="Lido + Coinbase + Binance 기준")

    st.markdown("<br>", unsafe_allow_html=True)

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        eth_ent_fig = chart_eth_staking_entities()[0]
        st.plotly_chart(eth_ent_fig, use_container_width=True)

        risk_color_eth = THEME["red"] if lido_share_v >= 30 else (
            THEME["orange"] if lido_share_v >= 25 else THEME["green"]
        )
        st.markdown(f"""
<div style="background:{THEME['card']};border-left:4px solid {risk_color_eth};
            padding:0.9rem 1.2rem;border-radius:8px;margin-top:-8px;">
  <div style="color:{THEME['subtext']};font-size:0.76rem;">자본 집중 리스크 (Lido)</div>
  <div style="color:{risk_color_eth};font-size:1.3rem;font-weight:700;">
    {"⚠️ 주의 필요" if lido_share_v >= 30 else "🟡 경계 수준" if lido_share_v >= 25 else "✅ 안전 구간"}
  </div>
  <div style="color:{THEME['text']};font-size:0.8rem;margin-top:0.3rem;">
    Lido {lido_share_v:.1f}% — 33% 임계선까지 {33.4 - lido_share_v:.1f}%p 여유<br>
    <b>공격 주체</b>: 월스트리트 기관 투자자 · 대형 거래소 CEO
  </div>
</div>""", unsafe_allow_html=True)

    with col_e2:
        st.plotly_chart(chart_entity_nakamoto_bar(), use_container_width=True)
        st.markdown(f"""
<div style="background:{THEME['card']};border-left:4px solid {ETH_C};
            padding:0.9rem 1.2rem;border-radius:8px;margin-top:-8px;">
  <div style="color:{THEME['subtext']};font-size:0.76rem;">슬래싱의 경제적 억제력</div>
  <div style="color:{ETH_C};font-size:1.3rem;font-weight:700;">공격 = 자본 자살</div>
  <div style="color:{THEME['text']};font-size:0.8rem;margin-top:0.3rem;">
    Lido가 33% 공격을 시도하면 → ETH 프로토콜이 Lido 지분 전액 소각<br>
    Lido TVL ${lido_share_v * staked_eth * eth_price / 100 / 1e9:.0f}B 증발 → LDO 토큰 가치 0에 수렴
  </div>
</div>""", unsafe_allow_html=True)

    # ── 섹션 7: 지정학적 vs 자본적 집중도 대조 비교 ────────────────
    st.markdown("---")
    st.markdown("### 🆚 집중도 대조: 지정학적(BTC) vs 자본적(ETH)")
    st.info(
        "**핵심 질문**: 나는 정치 권력의 공모를 더 두려워하는가 — "
        "아니면 거대 자본·기관의 공모를 더 두려워하는가?",
        icon="🤔",
    )

    # 종합 취약성 점수 계산
    # 공식: (1/나카모토계수 × 0.4) + (최대단일엔티티/100 × 0.4) + (지정학리스크/100 × 0.2)
    btc_nak_score   = 1 / nakamoto_preview
    btc_top_score   = geo_sorted[0]["share"] / 100
    btc_geo_score   = geo_risk_pct / 100
    btc_vuln        = (btc_nak_score * 0.4 + btc_top_score * 0.4 + btc_geo_score * 0.2) * 100

    eth_nak_score   = 1 / nak33_val
    eth_top_score   = lido_share_v / 100
    eth_geo_score   = top_inst_3 / 100
    eth_vuln        = (eth_nak_score * 0.4 + eth_top_score * 0.4 + eth_geo_score * 0.2) * 100

    # 비교 테이블
    cmp_df = pd.DataFrame({
        "비교 항목": [
            "합의 보안 모델",
            "공격 주체",
            "나카모토 계수 (33% 임계)",
            "나카모토 계수 (51% 임계)",
            "최대 단일 엔티티 점유율",
            "상위 3개 엔티티 합산",
            "공격 성공 시 손실",
            "핵심 억제 요인",
            "종합 취약성 점수 ↓낮을수록 안전",
        ],
        f"₿ Bitcoin (PoW) — 지정학적": [
            "물리적 해시파워",
            "국가 정부 (지도자·군)",
            f"{nakamoto_preview}개국",
            f"{nakamoto_preview}개국 (동일 — 해시 지배)",
            f"미국 {geo_sorted[0]['share']:.1f}%",
            f"{top3_share:.1f}% (미·중·카자흐)",
            "ASIC 중고 판매 가능 (부분 회수)",
            "지리적 분산 + 다국 동시 단속 불가",
            f"{btc_vuln:.1f}점",
        ],
        f"Ξ Ethereum (PoS) — 자본적": [
            "경제적 스테이킹",
            "기관 투자자 · 대형 거래소 CEO",
            f"{nak33_val}개 기관",
            f"{nak51_val}개 기관",
            f"Lido {lido_share_v:.1f}%",
            f"{top_inst_3:.1f}% (Lido·CB·Binance)",
            "슬래싱으로 전액 소각 (회수 불가)",
            "슬래싱 경제 억제 + DAO 거버넌스",
            f"{eth_vuln:.1f}점",
        ],
    })
    st.dataframe(cmp_df.set_index("비교 항목"), use_container_width=True, height=360)

    # 취약성 점수 게이지
    sc1, sc2, sc3 = st.columns([2, 1, 2])
    with sc1:
        fig_btc_gauge = go.Figure(go.Indicator(
            mode  = "gauge+number",
            value = btc_vuln,
            title = dict(text="BTC 종합 취약성 점수", font=dict(color=THEME["text"], size=13)),
            number= dict(suffix=" 점", font=dict(color=BTC_C, size=28)),
            gauge = dict(
                axis      = dict(range=[0, 100], tickcolor=THEME["text"],
                                 tickfont=dict(color=THEME["text"])),
                bar       = dict(color=BTC_C),
                bgcolor   = THEME["card"],
                bordercolor = THEME["grid"],
                steps     = [
                    dict(range=[0,  33], color="#1e3a1e"),
                    dict(range=[33, 66], color="#3a2e1e"),
                    dict(range=[66, 100], color="#3a1e1e"),
                ],
                threshold = dict(line=dict(color=THEME["red"], width=3), value=66),
            ),
        ))
        fig_btc_gauge.update_layout(
            paper_bgcolor=THEME["paper"], font=dict(color=THEME["text"]),
            height=240, margin=dict(t=60, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_btc_gauge, use_container_width=True)

    with sc2:
        st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:center;height:240px;">
  <div style="text-align:center;">
    <div style="color:{THEME['subtext']};font-size:0.75rem;">취약성 차이</div>
    <div style="color:{THEME['text']};font-size:1.6rem;font-weight:700;">
      {"BTC 높음" if btc_vuln > eth_vuln else "ETH 높음" if eth_vuln > btc_vuln else "동등"}
    </div>
    <div style="color:{THEME['gold']};font-size:1.1rem;">
      {abs(btc_vuln - eth_vuln):.1f}점 차
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    with sc3:
        fig_eth_gauge = go.Figure(go.Indicator(
            mode  = "gauge+number",
            value = eth_vuln,
            title = dict(text="ETH 종합 취약성 점수", font=dict(color=THEME["text"], size=13)),
            number= dict(suffix=" 점", font=dict(color=ETH_C, size=28)),
            gauge = dict(
                axis      = dict(range=[0, 100], tickcolor=THEME["text"],
                                 tickfont=dict(color=THEME["text"])),
                bar       = dict(color=ETH_C),
                bgcolor   = THEME["card"],
                bordercolor = THEME["grid"],
                steps     = [
                    dict(range=[0,  33], color="#1e3a1e"),
                    dict(range=[33, 66], color="#3a2e1e"),
                    dict(range=[66, 100], color="#3a1e1e"),
                ],
                threshold = dict(line=dict(color=THEME["red"], width=3), value=66),
            ),
        ))
        fig_eth_gauge.update_layout(
            paper_bgcolor=THEME["paper"], font=dict(color=THEME["text"]),
            height=240, margin=dict(t=60, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_eth_gauge, use_container_width=True)

    with st.expander("📐 종합 취약성 점수 산출 공식"):
        st.markdown(f"""
**공식**: `취약성 점수 = (1/나카모토계수) × 40 + 최대단일엔티티% × 0.4 + 상위3합산% × 0.2`

| 항목 | BTC | ETH |
|---|---|---|
| 나카모토 계수 항 | 1/{nakamoto_preview} × 40 = {1/nakamoto_preview*40:.1f} | 1/{nak33_val} × 40 = {1/nak33_val*40:.1f} |
| 최대 단일 엔티티 항 | {geo_sorted[0]['share']:.1f} × 0.4 = {geo_sorted[0]['share']*0.4:.1f} | {lido_share_v:.1f} × 0.4 = {lido_share_v*0.4:.1f} |
| 집합 리스크 항 | {geo_risk_pct:.1f} × 0.2 = {geo_risk_pct*0.2:.1f} | {top_inst_3:.1f} × 0.2 = {top_inst_3*0.2:.1f} |
| **합계** | **{btc_vuln:.1f}점** | **{eth_vuln:.1f}점** |

> 이 지수는 교육·참고 목적의 단순화된 모델입니다.
> 실제 보안은 법적 장벽, 경제적 억제, 기술 대응 등 다양한 요인이 복합 작용합니다.
""")

    # ── 섹션 8: 보안 모델 비교 테이블 ───────────────────────────────
    st.markdown("---")
    st.markdown("### ⚖️ 보안 모델 비교 — PoW vs PoS")

    risk_df = pd.DataFrame({
        "항목": [
            "합의 메커니즘",
            "공격에 필요한 자원",
            "비용 구성",
            "공격 후 자산 처분",
            "프로토콜 페널티",
            "에너지 의존성",
            "공격 준비 기간",
            "네트워크 대응",
            "공격 반복 가능성",
            "현재 51% 공격 비용",
        ],
        "₿ Bitcoin (PoW)": [
            "작업 증명 (Proof of Work)",
            "해시파워 (ASIC 장비 + 전기)",
            "하드웨어 구매 + 전기요금",
            "ASIC 중고 판매 가능 (부분 회수)",
            "없음 — 프로토콜 수준 페널티 없음",
            "매우 높음 (전기요금 민감)",
            "수개월 (장비 주문·배송·설치)",
            "채굴 알고리즘 하드포크",
            "가능 (하드웨어 재사용)",
            f"${btc_cost['total']/1e9:.1f}B",
        ],
        "Ξ Ethereum (PoS)": [
            "지분 증명 (Proof of Stake)",
            "ETH 스테이킹 자본",
            "ETH 시장 매수 비용",
            "불가 — 슬래싱으로 전액 소각",
            "상관 슬래싱: 공격 지분 거의 전액 소각",
            "없음",
            "즉시 (시장 매수)",
            "슬래싱 자동 실행 + 하드포크",
            "거의 불가능 (자본 완전 소멸)",
            f"${eth_cost['total']/1e9:.1f}B",
        ],
        "◎ Solana (PoS)": [
            "지분 증명 (Tower BFT / PoH)",
            "SOL 스테이킹 자본",
            "SOL 시장 매수 비용",
            "이중 서명 감지 시 전액 소각",
            "이중 투표 → 전액 슬래싱 (기타 제한적)",
            "없음",
            "즉시 (시장 매수)",
            "커뮤니티 하드포크 대응",
            "부분적 가능 (조건에 따라)",
            f"${sol_cost['total']/1e9:.1f}B",
        ],
    })
    st.dataframe(
        risk_df.set_index("항목"),
        use_container_width=True,
        height=420,
    )

    # ── 섹션 6: 분석 해석 가이드 ────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📖 분석 해석 가이드")

    with st.expander("1. 왜 ETH·SOL의 SRI가 BTC보다 높은가?"):
        st.markdown(f"""
**현재 SRI: BTC {btc_sri*100:.1f}% · ETH {eth_sri*100:.1f}% · SOL {sol_sri*100:.1f}%**

- BTC 공격 비용은 **물리적 자원(ASIC·전기)**에 의존하며 시총 대비 낮은 비율에 형성
- ETH/SOL은 **유통 자본의 상당 부분을 시장에서 직접 매수**해야 함
  - ETH의 경우 스테이킹된 ETH 51%는 전체 유통량의 약 **28–30%** 수준
  - 실제 매수 시 가격 급등(market impact)으로 계산값보다 훨씬 높은 비용 발생

> **결론**: PoS는 '경제적 공격 장벽'이 PoW보다 높은 경향이 있음.
> 단, PoW는 '지리적·물리적 탈중앙화'라는 별도의 보안 특성을 가짐.
""")

    with st.expander("2. 슬래싱(Slashing)이 ETH 보안의 핵심인 이유"):
        st.markdown(f"""
**이더리움 상관 슬래싱(Correlated Slashing) 메커니즘:**

- 동시에 위반하는 validator 수에 비례하여 소각 페널티 증가
- 51% 공격 = 다수 validator가 동시에 이중 서명 → **거의 전액 소각**
- BTC 공격자: 실패 후 ASIC 중고 판매로 자본 부분 회수 가능
- ETH 공격자: **성공 여부와 무관하게** 투입 ETH가 프로토콜에 의해 자동 소각

> 이더리움 51% 공격의 수학적 결론:
> **공격 수익 < 슬래싱 손실 → 경제적으로 자살 행위**
""")

    with st.expander("3. ASIC 가격 하락 시 BTC 보안은 약화되는가?"):
        st.markdown(f"""
- ASIC 가격이 50% 하락하면 하드웨어 공격 비용도 비례하여 감소
- 단, ASIC 가격 하락은 전 세계 채굴자의 진입 장벽도 낮춰 **해시레이트 상승 효과**
- 결과: 총 네트워크 해시레이트 증가 → 공격에 필요한 ASIC 수량도 증가

> 단기적으로는 보안 약화 가능하지만, 시장 논리에 의해 자기 보정되는 구조.
> 좌측 사이드바의 슬라이더로 직접 시뮬레이션해 보세요.
""")

    with st.expander("4. 공격 수익성 분석 — 실제로 이득이 되는가?"):
        st.markdown(f"""
**BTC 이중지불(Double Spend) 수익 분석:**
- 현재 공격 비용: **${btc_cost['total']/1e9:.1f}B** ({attack_hours}시간 기준)
- 1시간(6블록) 동안 이중지불로 회수 가능한 최대 이익?
  - 단일 거래소 최대 출금 한도: 통상 수억 달러 수준
  - 공격 비용 $10B+ 대비 수익은 훨씬 적음 → **경제적으로 비합리적**
- 공격 성공 시 BTC 가격 급락 → 공격 성공 직후 보유 BTC 가치도 폭락

**ETH 이중지불 수익 분석:**
- 슬래싱으로 **${ eth_cost['slashing_value']/1e9:.1f}B 확정 손실**
- 공격 이익 가능성: 실질적으로 **0** (손실만 확정)
""")

    # ── 데이터 소스 안내 ─────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        "데이터 소스: CoinGecko (가격·시총·공급량) · "
        "blockchain.info Charts API (BTC 해시레이트) · "
        "beaconcha.in API (ETH 스테이킹) · "
        "모두 무료 공개 API 사용"
    )


if __name__ == "__main__":
    main()
