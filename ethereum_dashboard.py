"""
이더리움 내재 가치 분석 대시보드 (Ethereum Intrinsic Value Dashboard)
=========================================================================
분석 철학:
    이더리움의 가치는 단순 시장 가격이 아니라 세 가지 핵심 축의 유기적 결합으로 결정된다:
      1. 공급(소각)    : EIP-1559 이후 소각되는 ETH → 디플레이션 압력
      2. 확장성(L2)    : L2 TVL 합계 → 이더리움 보안에 의존하는 생태계 규모
      3. 수익률(스테이킹): 스테이킹 APY → 장기 보유 인센티브

데이터 출처:
    - CoinGecko API  : ETH 가격, 시가총액, 유통량, 히스토리 (무료 티어)
    - DefiLlama API  : 체인별 TVL, 프로토콜 TVL, RWA 분류 (무료)
    - DefiLlama Yields: 스테이킹 APY (무료)

실행 방법:
    pip install streamlit pandas plotly requests numpy
    streamlit run ethereum_dashboard.py
"""

import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

# ============================================================
# 1. 페이지 기본 설정 (반드시 최초 st 호출이어야 함)
# ============================================================
st.set_page_config(
    page_title="⟠ ETH 내재 가치 대시보드",
    page_icon="⟠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 다크모드 최적화 CSS ───────────────────────────────────
# Streamlit의 기본 테마 위에 커스텀 CSS를 덧입혀
# 맥북 다크모드 환경에서 눈의 피로를 줄이고 가독성을 높인다.
st.markdown(
    """
<style>
    /* Streamlit 기본 헤더/툴바 숨김 → 상단 흰 여백 제거 */
    [data-testid="stHeader"]  { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    #MainMenu                 { visibility: hidden !important; }
    .stDeployButton           { display: none !important; }

    /* 상단 패딩 최소화 */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
    }

    /* 전체 배경 */
    .stApp { background-color: #0e1117; color: #fafafa; }

    /* 메트릭 카드 */
    [data-testid="stMetric"] {
        background-color: #1e2130;
        border: 1px solid #2d3250;
        border-radius: 10px;
        padding: 15px 18px;
    }
    [data-testid="stMetricValue"] { font-size: 1.7rem; color: #00d4aa; }

    /* 상단 흰색 헤더 바 → 다크 처리 */
    [data-testid="stHeader"] { background-color: #0d1117 !important; border-bottom: 1px solid #2a3045; }
    [data-testid="stDecoration"] { display: none !important; }

    /* 사이드바 */
    [data-testid="stSidebar"] { background-color: #161a25; color: #e0e0e0; }
    [data-testid="stSidebar"] label { color: #e0e0e0 !important; }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span { color: #c8ced5 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #fafafa !important; }

    /* 섹션 헤더 (좌측 액센트 라인) */
    .section-header {
        background: linear-gradient(90deg, #00d4aa22, transparent);
        padding: 8px 16px;
        border-left: 3px solid #00d4aa;
        border-radius: 4px;
        margin: 24px 0 8px 0;
    }
    .section-header h3 { margin: 0; color: #fafafa; }

    /* 정보/분석의도 박스 */
    .info-box {
        background-color: #1e2130;
        border: 1px solid #2d3250;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 6px 0 12px 0;
        font-size: 0.84rem;
        color: #a0aab4;
        line-height: 1.55;
    }

    /* 요약 리스트 */
    .summary-item {
        display: flex;
        justify-content: space-between;
        padding: 5px 0;
        border-bottom: 1px solid #2d3250;
        font-size: 0.9rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# 2. 공통 다크 테마 팔레트 (Plotly 차트 전체에 적용)
# ============================================================
THEME = {
    "bg": "#0e1117",
    "paper": "#1e2130",
    "grid": "#2d3250",
    "text": "#fafafa",
    "subtext": "#a0aab4",
    "accent_teal": "#00d4aa",   # 긍정 / 주요 지표
    "accent_blue": "#7289da",   # 보조 지표
    "accent_gold": "#f0a500",   # 현재 가격 / 중립
    "accent_red": "#ff4b4b",    # 부정 / 고평가
}


def _apply_dark_theme(fig: go.Figure, height: int = 420) -> go.Figure:
    """모든 Plotly 차트에 일관된 다크 테마를 적용하는 헬퍼 함수."""
    fig.update_layout(
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(color=THEME["text"], family="Inter, -apple-system, sans-serif", size=12),
        xaxis=dict(gridcolor=THEME["grid"], linecolor=THEME["grid"], zeroline=False),
        yaxis=dict(gridcolor=THEME["grid"], linecolor=THEME["grid"], zeroline=False),
        legend=dict(
            bgcolor=THEME["paper"],
            bordercolor=THEME["grid"],
            borderwidth=1,
            font=dict(color=THEME["text"], size=11),
        ),
        margin=dict(t=75, b=40, l=50, r=30),
        height=height,
        hovermode="x unified",
    )
    # 타이틀이 실제로 존재할 때만 폰트를 지정한다.
    # 타이틀 텍스트 없이 font 만 설정하면 브라우저가 "undefined" 를 렌더링함.
    if fig.layout.title.text:
        fig.update_layout(title=dict(font=dict(color=THEME["text"], size=14)))
    return fig


# ============================================================
# 3. 데이터 수집 함수 (API 호출 + 캐싱)
#    @st.cache_data(ttl=N): N초 동안 동일 파라미터 결과를 메모리에 캐싱.
#    CoinGecko 무료 티어는 분당 ~10-30 req 제한이 있으므로 캐싱이 필수.
# ============================================================

@st.cache_data(ttl=300)  # 5분 캐시 — 현재가는 비교적 자주 갱신
def fetch_eth_current() -> dict | None:
    """
    CoinGecko: ETH 현재 가격·시가총액·유통량·등락률 수집.
    유통량(circulating_supply)은 적정 가치 공식의 분모로 사용된다.
    """
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/coins/ethereum",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
            },
            timeout=12,
        )
        resp.raise_for_status()
        md = resp.json()["market_data"]
        return {
            "price":              md["current_price"]["usd"],
            "market_cap":         md["market_cap"]["usd"],
            "circulating_supply": md["circulating_supply"],
            "total_supply":       md.get("total_supply"),
            "change_24h":         md["price_change_percentage_24h"] or 0.0,
            "change_7d":          md["price_change_percentage_7d"] or 0.0,
            "ath":                md["ath"]["usd"],
            "volume_24h":         md["total_volume"]["usd"],
        }
    except Exception as exc:
        st.warning(f"CoinGecko 현재가 API 오류: {exc}")
        return None


@st.cache_data(ttl=3600)  # 1시간 캐시 — ETH market_chart 단일 공유 캐시
def _fetch_eth_market_chart_raw(days: int) -> dict | None:
    """
    CoinGecko /coins/ethereum/market_chart 단일 HTTP 호출 캐시.

    fetch_eth_history / fetch_eth_supply_history / fetch_btc_dominance_proxy
    세 함수가 같은 days 인수로 이 함수를 호출하면 HTTP 요청은 1회만 발생하고
    나머지는 캐시 히트로 처리된다. 429 Rate Limit 방지가 목적.
    """
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/coins/ethereum/market_chart",
            params={"vs_currency": "usd", "days": min(days, 365), "interval": "daily"},
            timeout=20,
        )
        resp.raise_for_status()
        track("CoinGecko", n=1)
        return resp.json()
    except Exception as exc:
        st.warning(f"CoinGecko 히스토리 API 오류: {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_eth_history(days: int = 90) -> pd.DataFrame | None:
    """ETH 일별 가격 시계열. _fetch_eth_market_chart_raw 캐시를 공유한다."""
    data = _fetch_eth_market_chart_raw(days)
    if not data:
        return None
    df = pd.DataFrame(data["prices"], columns=["ts", "price"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
    return df.drop_duplicates("date").set_index("date")[["price"]]


@st.cache_data(ttl=3600)
def fetch_eth_supply_history(days: int = 365) -> pd.DataFrame | None:
    """
    ETH 유통 공급량 + 일일 순발행량 시계열.
    공급량(ETH) = 시가총액(USD) ÷ 가격(USD/ETH)
    _fetch_eth_market_chart_raw 캐시를 공유하여 중복 HTTP 요청을 방지한다.

    순발행량 > 0 : 스테이킹 보상 > EIP-1559 소각 → 인플레이션
    순발행량 < 0 : EIP-1559 소각 > 스테이킹 보상 → 디플레이션 ("ultrasound money")
    """
    data = _fetch_eth_market_chart_raw(min(days, 365))
    if not data:
        return None
    prices = pd.DataFrame(data["prices"],      columns=["ts", "price"])
    mcaps  = pd.DataFrame(data["market_caps"], columns=["ts", "market_cap"])
    df = prices.merge(mcaps, on="ts")
    df["date"]         = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
    df["supply"]       = df["market_cap"] / df["price"]
    df = df.drop_duplicates("date").sort_values("date")
    df["net_issuance"] = df["supply"].diff().clip(-15_000, 15_000)
    return df.set_index("date")[["supply", "net_issuance"]]


@st.cache_data(ttl=600)  # 10분 캐시 — TVL은 비교적 실시간 반영
def fetch_defillama_chains() -> list | None:
    """
    DefiLlama: 모든 체인의 현재 TVL 스냅샷.
    이더리움 L1 TVL 및 각 L2 TVL 추출에 사용.
    """
    try:
        resp = requests.get("https://api.llama.fi/v2/chains", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.warning(f"DefiLlama Chains API 오류: {exc}")
        return None


@st.cache_data(ttl=3600)  # 1시간 캐시
def fetch_defillama_tvl_history(chain: str = "Ethereum") -> pd.DataFrame | None:
    """
    DefiLlama: 특정 체인의 TVL 일별 시계열.
    ETH 가격과의 시계열 상관관계 분석에 활용한다.
    TVL은 해당 체인 DeFi 프로토콜에 예치된 달러 가치의 합계.
    """
    try:
        resp = requests.get(
            f"https://api.llama.fi/v2/historicalChainTvl/{chain}", timeout=15
        )
        resp.raise_for_status()
        df = pd.DataFrame(resp.json())  # [{date: unix, tvl: float}, ...]
        df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
        return df.drop_duplicates("date").set_index("date")[["tvl"]]
    except Exception as exc:
        st.warning(f"DefiLlama TVL 히스토리 API 오류 ({chain}): {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_l2_tvl_histories(l2_names: list[str], days: int = 90) -> dict[str, pd.DataFrame]:
    """
    DefiLlama: 여러 L2 체인의 TVL 시계열을 일괄 수집.
    API 호출 수를 최소화하기 위해 상위 L2만 요청한다.
    반환값은 {표시명: DataFrame(index=date, columns=[tvl])} 딕셔너리.
    """
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
    results: dict[str, pd.DataFrame] = {}
    for name in l2_names:
        try:
            resp = requests.get(
                f"https://api.llama.fi/v2/historicalChainTvl/{name}", timeout=15
            )
            if resp.status_code != 200:
                continue
            raw = resp.json()
            if not raw:
                continue
            df = pd.DataFrame(raw)
            df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
            df = df.drop_duplicates("date").set_index("date")[["tvl"]]
            df = df[df.index >= cutoff]
            if not df.empty:
                results[name] = df
        except Exception:
            continue
    return results


@st.cache_data(ttl=600)
def fetch_defillama_protocols() -> list | None:
    """
    DefiLlama: 전체 프로토콜 목록 (카테고리·체인·TVL 포함).
    RWA(실물자산) 카테고리 프로토콜 필터링에 사용.
    """
    try:
        resp = requests.get("https://api.llama.fi/protocols", timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.warning(f"DefiLlama Protocols API 오류: {exc}")
        return None


@st.cache_data(ttl=1800)  # 30분 캐시
def fetch_staking_apy() -> list:
    """
    DefiLlama Yields: 이더리움 스테이킹 APY 수집.
    ETH 스테이킹 수익률은 PoS 네트워크 참여율과 수수료 수입을 반영하며,
    '채권 수익률'에 해당하는 ETH 내재 수익률 지표다.
    """
    try:
        resp = requests.get("https://yields.llama.fi/pools", timeout=15)
        resp.raise_for_status()
        pools = resp.json().get("data", [])
        # 이더리움 체인의 주요 유동 스테이킹 프로토콜만 필터링
        target_projects = {"lido", "rocket-pool", "frax-ether", "coinbase-wrapped-staked-eth"}
        return [
            p for p in pools
            if p.get("chain") == "Ethereum"
            and p.get("project") in target_projects
            and p.get("apy") is not None
            and "ETH" in (p.get("symbol") or "")
        ]
    except Exception as exc:
        st.warning(f"DefiLlama Yields API 오류: {exc}")
        return []


@st.cache_data(ttl=300)
def fetch_burn_estimate() -> dict:
    """
    ETH 소각량 추정 (EIP-1559, 2021.08 이후 적용).

    EIP-1559는 기본 수수료(base fee) 전량을 소각하여 ETH를 디플레이션 자산으로 전환했다.
    소각량이 신규 발행량을 초과하면 ETH 유통량이 순감소하므로 장기 가격 상승 압력이 된다.

    참고: 정확한 소각 데이터는 Etherscan API 키(무료 등록)가 필요하다.
    API 키 없이는 추정치를 사용한다.
    """
    # ── Etherscan API (API 키 없는 공개 엔드포인트, 제한적) ──
    try:
        resp = requests.get(
            "https://api.etherscan.io/api",
            params={"module": "stats", "action": "ethsupply2"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "1":
                result = data.get("result", {})
                # ETHBurnt 필드: 누적 소각량 (wei 단위)
                burnt_wei = int(result.get("ETHBurnt", 0))
                if burnt_wei > 0:
                    # 일평균 소각량: 런치(2021-08-05) 이후 일수로 나눔
                    days_since_eip1559 = (datetime.now() - datetime(2021, 8, 5)).days
                    avg_daily_burn = (burnt_wei / 1e18) / max(days_since_eip1559, 1)
                    return {"burn_24h_eth": avg_daily_burn, "source": "etherscan_avg", "is_estimated": True}
    except Exception:
        pass

    # ── 폴백: 네트워크 활동 기반 보수적 추정 ──
    # 이더리움 네트워크가 정상 운영될 때 약 1,500~3,000 ETH/day 소각.
    # 가스비가 높을수록 소각량도 증가한다.
    return {"burn_24h_eth": 1_800.0, "source": "conservative_estimate", "is_estimated": True}


@st.cache_data(ttl=3600)
def _fetch_coinmetrics_activity(asset: str, days: int) -> pd.DataFrame | None:
    """
    CoinMetrics Community API: 활성 주소 수 + 트랜잭션 수.
    커뮤니티 티어는 ETH(eth)는 지원하나 SOL(sol)은 유료 플랜 전용.
    403 응답 시 None을 반환하고 상위 함수에서 폴백을 시도한다.
    """
    start_time = (datetime.now() - timedelta(days=days + 2)).strftime("%Y-%m-%d")
    resp = requests.get(
        "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
        params={
            "assets":     asset,
            "metrics":    "AdrActCnt,TxCnt",
            "frequency":  "1d",
            "start_time": start_time,
            "page_size":  10000,
        },
        timeout=20,
    )
    if resp.status_code == 403:
        return None          # 유료 플랜 전용 → 조용히 None 반환
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return None
    df = pd.DataFrame(data)
    df["date"]      = pd.to_datetime(df["time"]).dt.normalize()
    df["AdrActCnt"] = pd.to_numeric(df.get("AdrActCnt"), errors="coerce")
    df["TxCnt"]     = pd.to_numeric(df.get("TxCnt"),     errors="coerce")
    return df.drop_duplicates("date").set_index("date")[["AdrActCnt", "TxCnt"]]


@st.cache_data(ttl=3600)
def fetch_onchain_activity(asset: str, days: int = 90) -> pd.DataFrame | None:
    """
    CoinMetrics Community API: 활성 주소 수 + 트랜잭션 수.
    ETH('eth')는 커뮤니티 티어에서 지원.
    SOL('sol')은 커뮤니티 티어 미지원(403) → None 반환.
    Solana 활동 비교는 fetch_fees_history로 별도 처리.
    """
    try:
        return _fetch_coinmetrics_activity(asset, days)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_fees_history(chain: str, days: int = 90) -> pd.DataFrame | None:
    """
    DefiLlama Fees API: 체인별 일일 네트워크 수수료 시계열.

    네트워크 수수료 = 사용자들이 하루 동안 지불한 총 가스비(USD).
    활성 주소 수가 없는 Solana 활동 비교의 대안 지표로 사용.

    수수료가 높다 = 트랜잭션이 많다 = 네트워크가 활발히 사용됨.
    ETH는 건당 수수료가 높고(고가치 거래), SOL은 건수가 많고 건당 수수료가 낮음.
    → 총 수수료 비교는 두 체인의 '경제 활동 총량'을 나타냄.
    """
    try:
        resp = requests.get(
            f"https://api.llama.fi/overview/fees/{chain}",
            params={
                "excludeTotalDataChart":          "false",
                "excludeTotalDataChartBreakdown": "true",
                "dataType":                       "dailyFees",
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json().get("totalDataChart", [])
        if not raw:
            return None
        df = pd.DataFrame(raw, columns=["ts", "fees_usd"])
        df["date"] = pd.to_datetime(df["ts"], unit="s").dt.normalize()
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        return df[df["date"] >= cutoff].drop_duplicates("date").set_index("date")[["fees_usd"]]
    except Exception as exc:
        st.warning(f"DefiLlama Fees API 오류 ({chain}): {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_dex_volume_history(chain: str, days: int = 90) -> pd.DataFrame | None:
    """
    DefiLlama DEX API: 체인별 일일 DEX 거래량 시계열.

    DEX 거래량 / TVL = 자본 효율성 (Capital Efficiency) 지표.
    이 비율이 높을수록 예치된 자본이 적극적으로 거래에 활용된다는 의미.
    솔라나는 초저수수료 + 고속 처리 특성으로 일반적으로 이더리움보다 이 비율이 높아
    '저장(Storage)' 보다 '거래(Trading)' 특화 체인임을 수치로 나타낸다.
    """
    try:
        resp = requests.get(
            f"https://api.llama.fi/overview/dexs/{chain}",
            params={
                "excludeTotalDataChart":          "false",
                "excludeTotalDataChartBreakdown": "true",
                "dataType":                       "dailyVolume",
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json().get("totalDataChart", [])
        if not raw:
            return None
        df = pd.DataFrame(raw, columns=["ts", "volume"])
        df["date"] = pd.to_datetime(df["ts"], unit="s").dt.normalize()
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        return df[df["date"] >= cutoff].drop_duplicates("date").set_index("date")[["volume"]]
    except Exception as exc:
        st.warning(f"DefiLlama DEX Volume API 오류 ({chain}): {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_stablecoin_history(chain: str, days: int = 90) -> pd.DataFrame | None:
    """
    DefiLlama Stablecoins API: 체인별 스테이블코인 시가총액 시계열.

    스테이블코인 잔액 해석:
      - 잔액 증가 → 자본이 체인을 '이탈'하지 않고 변동성 회피를 위해 안정 자산으로 전환.
        즉 자금 유출이 아닌 '관망 대기' 상태. 재진입 가능성이 높음.
      - 잔액 유지 + TVL 하락 → ETH/SOL 가격 하락으로 인한 평가 절하가 주요 원인.
    이 지표는 실제 스테이블코인 전송량이 아닌 온체인 잔액(시가총액)이지만,
    무료 API 중 가장 신뢰할 수 있는 대리 지표다.
    """
    try:
        resp = requests.get(
            f"https://stablecoins.llama.fi/stablecoincharts/{chain}", timeout=20
        )
        resp.raise_for_status()
        raw = resp.json()
        if not raw:
            return None
        records = []
        for entry in raw:
            total_usd = entry.get("totalCirculatingUSD") or {}
            usd_val = sum(v for v in total_usd.values() if isinstance(v, (int, float)))
            records.append({"date": entry.get("date", 0), "stablecoin_mcap": usd_val})
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        return df[df["date"] >= cutoff].drop_duplicates("date").set_index("date")[["stablecoin_mcap"]]
    except Exception as exc:
        st.warning(f"DefiLlama Stablecoins API 오류 ({chain}): {exc}")
        return None


# ============================================================
# 4. 데이터 가공 / 분석 함수
# ============================================================

# 주요 이더리움 L2 목록 (이름: DefiLlama 체인 이름 매핑)
L2_TARGETS = {
    "Arbitrum":       "arbitrum",
    "Optimism":       "optimism",
    "Base":           "base",
    "zkSync Era":     "zksync era",
    "Polygon zkEVM":  "polygon zkevm",
    "Linea":          "linea",
    "Starknet":       "starknet",
    "Scroll":         "scroll",
    "Mantle":         "mantle",
    "Blast":          "blast",
}


def extract_l2_tvl(chains_data: list) -> dict[str, float]:
    """
    전체 체인 데이터에서 주요 L2의 TVL(USD)을 추출.
    L2 TVL 합계는 '이더리움 보안에 의존하는 확장 생태계'의 총 가치를 나타낸다.
    """
    result: dict[str, float] = {}
    if not chains_data:
        return result
    for chain in chains_data:
        name_lower = (chain.get("name") or "").lower()
        for display, key in L2_TARGETS.items():
            if key == name_lower:
                result[display] = float(chain.get("tvl") or 0)
                break
    return result


def extract_l1_tvl(chains_data: list) -> float:
    """DefiLlama 체인 목록에서 이더리움 L1 TVL 추출."""
    if not chains_data:
        return 0.0
    for chain in chains_data:
        if (chain.get("name") or "").lower() == "ethereum":
            return float(chain.get("tvl") or 0)
    return 0.0


def calc_intrinsic_value(
    l1_tvl: float,
    l2_tvl_total: float,
    circulating_supply: float,
    factor: float = 1.0,
) -> float:
    """
    TVL 기반 ETH 적정 가치 지수 계산.

    공식:  (L1 TVL + L2 TVL 합계) / ETH 유통량 × 조정 계수

    이론적 근거:
        - ETH는 이더리움 네트워크의 '기본 담보 자산' 역할을 한다.
        - DeFi 프로토콜에 예치된 TVL은 ETH 네트워크가 보증하는 경제적 가치.
        - 주식의 P/B(주가순자산비율) 역산 개념: 담보 가치 ÷ 유통량 = 단위당 장부 가치.
        - 조정 계수: 성장 프리미엄, 규제 리스크, 기술 위험 등 주관적 요소를 반영.
    """
    if circulating_supply and circulating_supply > 0:
        return (l1_tvl + l2_tvl_total) / circulating_supply * factor
    return 0.0


def extract_rwa_protocols_full(
    protocols_data: list | None, min_tvl: float = 1e6
) -> list[dict]:
    """
    RWA 프로토콜 전체 정보 추출. 히스토리 fetch에 필요한 slug 포함.
    반환값: [{"name": str, "slug": str, "tvl": float}, ...] TVL 내림차순 상위 10개.
    """
    if not protocols_data:
        return []
    rwa = []
    for p in protocols_data:
        cat = (p.get("category") or "").lower()
        if "rwa" not in cat and "real world" not in cat:
            continue
        if "Ethereum" not in (p.get("chains") or []):
            continue
        tvl = float(p.get("tvl") or 0)
        if tvl >= min_tvl:
            rwa.append({
                "name": p.get("name", "Unknown"),
                "slug": p.get("slug", ""),
                "tvl":  tvl,
            })
    return sorted(rwa, key=lambda x: x["tvl"], reverse=True)[:10]


def extract_rwa_protocols(protocols_data: list | None, min_tvl: float = 1e6) -> dict[str, float]:
    """
    기존 파이 차트용 {name: tvl} 딕셔너리 반환. extract_rwa_protocols_full 래퍼.
    """
    return {p["name"]: p["tvl"] for p in extract_rwa_protocols_full(protocols_data, min_tvl)}


@st.cache_data(ttl=3600)
def fetch_rwa_protocol_history(slug: str, days: int = 365) -> pd.Series | None:
    """
    DefiLlama /protocol/{slug}: 이더리움 RWA 프로토콜 TVL 시계열.

    chainTvls.Ethereum.tvl → [{date: unix_ts, totalLiquidityUSD: float}] 배열.
    Ethereum 체인 데이터가 없으면 전체 tvl 배열로 폴백.
    DefiLlama 무료 API 무제한 — 프로토콜별로 1회씩 호출.
    """
    if not slug:
        return None
    try:
        resp = requests.get(f"https://api.llama.fi/protocol/{slug}", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        eth_arr = (
            data.get("chainTvls", {}).get("Ethereum", {}).get("tvl", [])
            or data.get("tvl", [])
        )
        if not eth_arr:
            return None
        df = pd.DataFrame(eth_arr)
        df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff].drop_duplicates("date").set_index("date")
        return df["totalLiquidityUSD"]
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_rwa_protocol_total_tvl(slug: str, days: int = 365) -> pd.Series | None:
    """
    DefiLlama /protocol/{slug}: 전체 체인 합산 TVL 시계열.

    data["tvl"] → 모든 체인 합산 [{date: unix_ts, totalLiquidityUSD: float}]
    이더리움 L1 TVL(fetch_rwa_protocol_history)과 비교해
    "이더리움 비중 %" 및 타 체인 유출 여부를 파악한다.

    ETH TVL 감소 + 전체 TVL 유지  → L2 / 타 체인 이동
    ETH TVL 감소 + 전체 TVL 감소  → 오프체인 상환 (자금 이탈)
    """
    if not slug:
        return None
    try:
        resp = requests.get(f"https://api.llama.fi/protocol/{slug}", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        tvl_arr = data.get("tvl", [])
        if not tvl_arr:
            return None
        df = pd.DataFrame(tvl_arr)
        df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff].drop_duplicates("date").set_index("date")
        return df["totalLiquidityUSD"]
    except Exception:
        return None


# 주요 체인 표시 순서 및 색상 (이더리움 제외한 타 체인)
_CHAIN_PALETTE: dict[str, str] = {
    "Arbitrum":  "#2d9cdb",
    "Base":      "#0052ff",
    "Optimism":  "#ff0420",
    "Polygon":   "#8247e5",
    "Solana":    "#9945ff",
    "Stellar":   "#7ec8e3",
    "Avalanche": "#e84142",
    "BSC":       "#f3ba2f",
}


@st.cache_data(ttl=3600)
def fetch_rwa_protocol_chains(slug: str, days: int = 365) -> dict[str, pd.Series]:
    """
    DefiLlama /protocol/{slug}: 이더리움 제외 체인별 TVL 시계열.

    반환값: {chain_name: pd.Series(index=date, values=tvl_usd)}
    이더리움은 포함하지 않음 (fetch_rwa_protocol_history 로 별도 수집).
    소규모 체인은 "기타" 로 합산.
    """
    if not slug:
        return {}
    try:
        resp = requests.get(f"https://api.llama.fi/protocol/{slug}", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        chain_tvls = data.get("chainTvls", {})
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        result: dict[str, pd.Series] = {}
        for chain, chain_data in chain_tvls.items():
            if chain.lower() in ("ethereum", "ethereum-staking", "ethereum-pool2"):
                continue
            arr = chain_data.get("tvl", [])
            if not arr:
                continue
            df = pd.DataFrame(arr)
            df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
            df = df[df["date"] >= cutoff].drop_duplicates("date").set_index("date")
            s = df["totalLiquidityUSD"].rename(chain)
            if s.max() > 1e5:  # 10만 달러 미만 체인 제외
                result[chain] = s
        return result
    except Exception:
        return {}


def pearson_corr(s1: pd.Series, s2: pd.Series) -> float | None:
    """
    두 시계열의 피어슨 상관계수 계산.

    r 해석:
        ±1.0  완벽한 선형 상관  |  0.0  무상관
        |r| ≥ 0.7  강한 상관    |  0.4 ≤ |r| < 0.7  중간 상관
    """
    try:
        return float(s1.corr(s2))
    except Exception:
        return None


# ============================================================
# 5. Plotly 차트 생성 함수
# ============================================================

def chart_price_vs_tvl(
    price_df: pd.DataFrame,
    tvl_df: pd.DataFrame,
) -> tuple[go.Figure, float | None]:
    """
    ETH 가격 vs 이더리움 L1 TVL 이중 Y축 차트 + 피어슨 상관계수 표시.

    이중 Y축:
        - 좌축: ETH 가격 (USD)
        - 우축: L1 TVL (십억 달러)
    두 지표의 동조화 여부를 시각적으로 확인한다.
    상관계수가 높을수록 TVL이 가격의 신뢰 가능한 선행 지표임을 시사.
    """
    # 날짜 기준 내부 조인 — 데이터가 없는 구간 제거
    merged = (
        price_df.reset_index()
        .merge(tvl_df.reset_index(), on="date", how="inner")
    )
    if merged.empty:
        return go.Figure(), None

    corr = pearson_corr(merged["price"], merged["tvl"])

    fig = make_subplots(
        specs=[[{"secondary_y": True}]],
        subplot_titles=[f"ETH 가격 vs 이더리움 L1 TVL ({len(merged)}일 데이터)"],
    )

    # ── 좌축: ETH 가격 ──────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["price"],
            name="ETH 가격 (USD)",
            line=dict(color=THEME["accent_teal"], width=2),
            hovertemplate="<b>ETH</b>: $%{y:,.0f}<br>%{x|%Y-%m-%d}<extra></extra>",
        ),
        secondary_y=False,
    )

    # ── 우축: L1 TVL ────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["tvl"] / 1e9,
            name="ETH L1 TVL ($B)",
            line=dict(color=THEME["accent_blue"], width=2, dash="dot"),
            hovertemplate="<b>TVL</b>: $%{y:.2f}B<br>%{x|%Y-%m-%d}<extra></extra>",
        ),
        secondary_y=True,
    )

    # 상관계수 어노테이션
    if corr is not None:
        fig.add_annotation(
            text=f"피어슨 r = {corr:.4f}",
            xref="paper", yref="paper",
            x=0.02, y=0.97,
            showarrow=False,
            bgcolor=THEME["paper"],
            bordercolor=THEME["accent_teal"],
            borderwidth=1,
            borderpad=6,
            font=dict(color=THEME["accent_teal"], size=13, family="monospace"),
        )

    fig.update_yaxes(title_text="ETH 가격 (USD)", secondary_y=False, tickprefix="$")
    fig.update_yaxes(title_text="TVL (십억 달러)", secondary_y=True, tickprefix="$", ticksuffix="B")

    _apply_dark_theme(fig, height=460)
    return fig, corr


def chart_l2_tvl_bar(l2_tvl: dict[str, float]) -> go.Figure:
    """
    이더리움 L2 생태계 TVL 수평 막대 차트.

    L2 프로토콜들은 이더리움 L1의 보안(Security) 을 임대하는 구조.
    따라서 L2 TVL 합계는 이더리움이 간접적으로 담보하는 경제적 가치의 확장을 의미.
    """
    if not l2_tvl:
        return go.Figure()

    sorted_data = sorted(l2_tvl.items(), key=lambda x: x[1])
    names  = [d[0] for d in sorted_data]
    values = [d[1] / 1e9 for d in sorted_data]  # 십억 달러 단위

    # 값에 비례하는 색상 그라디언트 (teal 계열)
    n = len(names)
    colors = [f"rgba(0,{int(180 + 74 * i / max(n-1,1))},{int(120 + 50 * i / max(n-1,1))},0.85)" for i in range(n)]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"${v:.2f}B" for v in values],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>TVL: $%{x:.2f}B<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="이더리움 L2 생태계 TVL 분포", x=0.02),
        xaxis_title="TVL (십억 달러)",
        showlegend=False,
    )
    _apply_dark_theme(fig, height=400)
    return fig


def chart_l1_l2_tvl_history(
    l1_df: pd.DataFrame,
    l2_dfs: dict[str, pd.DataFrame],
) -> go.Figure:
    """
    L1 + 주요 L2 TVL 시계열 누적 면적(Stacked Area) 차트.

    누적 면적 차트로 표현하는 이유:
        - 각 L2의 개별 기여도와 전체 합계를 동시에 직관적으로 파악 가능.
        - L2 생태계의 성장 속도와 L1 대비 비중 변화를 한눈에 볼 수 있다.
        - 이더리움이 담보하는 총 경제 가치(L1+L2)의 추세를 확인한다.
    """
    def _hex_rgba(hex_color: str, alpha: float = 0.45) -> str:
        """hex 색상 문자열 (#RRGGBB) 을 rgba(R,G,B,A) 형식으로 변환."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    fig = go.Figure()

    # 색상 팔레트: L1은 teal, L2는 다채로운 계열
    l2_colors = [
        "#7289da", "#9b59b6", "#e67e22", "#e74c3c",
        "#1abc9c", "#f39c12", "#2ecc71", "#3498db",
        "#e91e63", "#ff5722",
    ]

    # ── L2 면적 (아래부터 쌓아 올림) ──────────────────────
    for i, (name, df) in enumerate(l2_dfs.items()):
        color = l2_colors[i % len(l2_colors)]
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["tvl"] / 1e9,
                name=name,
                mode="lines",
                line=dict(width=0.5, color=color),
                fill="tonexty" if i > 0 else "tozeroy",
                fillcolor=_hex_rgba(color),
                stackgroup="tvl",  # Plotly 내장 스태킹
                hovertemplate=f"<b>{name}</b>: $%{{y:.2f}}B<br>%{{x|%Y-%m-%d}}<extra></extra>",
            )
        )

    # ── L1 면적 (최상단에 별도 표시) ──────────────────────
    if l1_df is not None and not l1_df.empty:
        fig.add_trace(
            go.Scatter(
                x=l1_df.index,
                y=l1_df["tvl"] / 1e9,
                name="Ethereum L1",
                mode="lines",
                line=dict(width=0.5, color=THEME["accent_teal"]),
                fill="tonexty",
                fillcolor="rgba(0,212,170,0.50)",
                stackgroup="tvl",
                hovertemplate="<b>ETH L1</b>: $%{y:.2f}B<br>%{x|%Y-%m-%d}<extra></extra>",
            )
        )

    fig.update_layout(
        title=dict(text="이더리움 L1 + L2 TVL 시계열 (누적)", x=0.02),
        yaxis_title="TVL (십억 달러)",
        yaxis_tickprefix="$",
        yaxis_ticksuffix="B",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
        ),
    )
    _apply_dark_theme(fig, height=460)
    return fig


def chart_eth_vs_solana(
    l1_df: pd.DataFrame | None,
    l2_dfs: dict[str, pd.DataFrame],
    solana_df: pd.DataFrame | None,
) -> go.Figure:
    """
    이더리움 Total TVL(L1+L2 합산) vs 솔라나 TVL 직접 비교 라인 차트.

    비교 분석 목적:
        - ETH Total TVL이 하락할 때 SOL TVL이 상승하면 → 생태계 자금 이동 신호.
        - 두 체인이 동반 하락하면 → 가격 하락에 의한 달러 환산 효과 (실질 이탈 아님).
        - 두 체인이 동반 상승하면 → 전체 크립토 시장으로의 자금 유입.
    Gemini 분석 맥락:
        TVL은 '예치 코인 수' 가 아닌 '달러 환산 가치'이므로
        자산 가격 하락 시 TVL도 자동 하락 (자금 이탈과 구별 필요).
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # ── ETH L1 TVL 계산 ────────────────────────────────────
    if l1_df is not None and not l1_df.empty:
        eth_total = l1_df[["tvl"]].copy().rename(columns={"tvl": "eth"})

        # L2 TVL 합산: 날짜 기준으로 모두 합산
        for df in l2_dfs.values():
            aligned = df[["tvl"]].reindex(eth_total.index, method="ffill")
            eth_total["eth"] = eth_total["eth"] + aligned["tvl"].fillna(0)

        fig.add_trace(
            go.Scatter(
                x=eth_total.index,
                y=eth_total["eth"] / 1e9,
                name="ETH Total TVL (L1+L2)",
                line=dict(color=THEME["accent_teal"], width=2.5),
                hovertemplate="<b>ETH Total</b>: $%{y:.2f}B<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

        # ETH L1만 별도 표시 (참조선)
        fig.add_trace(
            go.Scatter(
                x=l1_df.index,
                y=l1_df["tvl"] / 1e9,
                name="ETH L1 TVL",
                line=dict(color=THEME["accent_teal"], width=1.2, dash="dot"),
                opacity=0.55,
                hovertemplate="<b>ETH L1</b>: $%{y:.2f}B<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

    # ── 솔라나 TVL (우측 Y축) ──────────────────────────────
    if solana_df is not None and not solana_df.empty:
        fig.add_trace(
            go.Scatter(
                x=solana_df.index,
                y=solana_df["tvl"] / 1e9,
                name="Solana TVL",
                line=dict(color="#9945FF", width=2.5),  # 솔라나 브랜드 퍼플
                hovertemplate="<b>Solana</b>: $%{y:.2f}B<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(
        title_text="ETH TVL (십억 달러)",
        secondary_y=False,
        tickprefix="$", ticksuffix="B",
    )
    fig.update_yaxes(
        title_text="SOL TVL (십억 달러)",
        secondary_y=True,
        tickprefix="$", ticksuffix="B",
        showgrid=False,
    )
    fig.update_layout(
        title=dict(text="이더리움 Total TVL vs 솔라나 TVL 비교", x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    _apply_dark_theme(fig, height=440)
    return fig


def chart_intrinsic_value(
    current_price: float,
    l1_tvl: float,
    l2_tvl_total: float,
    circulating_supply: float,
    factors: dict[str, float],
) -> go.Figure:
    """
    TVL 기반 적정 가치 지수 vs 현재 ETH 가격 막대 차트.

    색상 코드:
        초록(teal)  : 적정가 > 현재가 → 저평가 신호
        빨강(red)   : 적정가 < 현재가 → 고평가 신호
        금색(gold)  : 현재 ETH 가격 기준선
    """
    labels, values, colors = [], [], []

    for label, factor in factors.items():
        iv = calc_intrinsic_value(l1_tvl, l2_tvl_total, circulating_supply, factor)
        labels.append(label)
        values.append(iv)
        colors.append(THEME["accent_teal"] if iv >= current_price else THEME["accent_red"])

    labels.append("현재 ETH 가격")
    values.append(current_price)
    colors.append(THEME["accent_gold"])

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"${v:,.0f}" for v in values],
            textposition="outside",
            textfont=dict(size=12),
            hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
        )
    )

    # 현재가 기준 수평선
    fig.add_hline(
        y=current_price,
        line_dash="dash",
        line_color=THEME["accent_gold"],
        annotation_text=f"현재가 ${current_price:,.0f}",
        annotation_position="top right",
        annotation_font=dict(color=THEME["accent_gold"], size=11),
    )

    fig.update_layout(
        title=dict(text="이더리움 적정 가치 지수 vs 현재 가격", x=0.02),
        yaxis_title="가격 (USD)",
        yaxis_tickprefix="$",
        showlegend=False,
    )
    _apply_dark_theme(fig, height=420)
    return fig


def chart_rwa_pie(
    rwa_data: dict[str, float],
    l1_tvl: float,
    data_date: str | None = None,
) -> tuple[go.Figure, float, float, bool]:
    """
    이더리움 RWA 점유율 이중 파이 차트.

    좌측: RWA 프로토콜 내부 구성 (도넛 차트)
    우측: 이더리움 L1 TVL 대비 RWA 비중

    RWA TVL이 증가한다는 것은 기관 자본이 이더리움 위에서 전통 금융 상품을
    토큰화하고 있음을 의미 → 구조적이고 장기적인 ETH 수요 기반 형성.
    """
    is_estimated = False
    if not rwa_data:
        # API 데이터 없을 때 공개 데이터 기반 추정치 사용 (2025년 기준)
        rwa_data = {
            "BlackRock BUIDL":            520_000_000,
            "Ondo Finance":               800_000_000,
            "Franklin Templeton BENJI":   650_000_000,
            "Maple Finance":              200_000_000,
            "Centrifuge":                 150_000_000,
            "기타 RWA":                   300_000_000,
        }
        is_estimated = True

    total_rwa   = sum(rwa_data.values())
    rwa_pct     = (total_rwa / l1_tvl * 100) if l1_tvl > 0 else 0.0
    non_rwa_tvl = max(0.0, l1_tvl - total_rwa)

    teal_palette = px.colors.sequential.Teal_r[: len(rwa_data)]

    date_label = f" — {data_date}" if data_date else ""
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "pie"}]],
        subplot_titles=[
            f"RWA 프로토콜 구성 (이더리움){date_label}",
            f"이더리움 L1 TVL 내 RWA 비중 ({rwa_pct:.1f}%){date_label}",
        ],
    )

    # 좌: RWA 내부 구성
    fig.add_trace(
        go.Pie(
            labels=list(rwa_data.keys()),
            values=list(rwa_data.values()),
            hole=0.42,
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>TVL: $%{value:,.0f}<br>%{percent}<extra></extra>",
            marker=dict(colors=teal_palette),
        ),
        row=1, col=1,
    )

    # 우: L1 TVL 대비 RWA 비중
    fig.add_trace(
        go.Pie(
            labels=["RWA 자산", "기타 DeFi"],
            values=[total_rwa, non_rwa_tvl],
            hole=0.42,
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            marker=dict(colors=[THEME["accent_teal"], THEME["grid"]]),
        ),
        row=1, col=2,
    )

    _apply_dark_theme(fig, height=420)
    return fig, total_rwa, rwa_pct, is_estimated


def chart_rwa_composition_history(hist_df: pd.DataFrame) -> go.Figure:
    """
    RWA 프로토콜별 이더리움 TVL 시계열 적층 영역 차트.

    각 프로토콜의 TVL이 시간이 지남에 따라 어떻게 변했는지,
    그리고 전체 RWA TVL의 성장 추이를 한눈에 파악할 수 있다.

    해석 가이드:
      - 특정 프로토콜이 빠르게 영역을 넓히면 기관 자금 유입의 선두 주자.
      - 전체 높이가 꾸준히 증가하면 RWA 섹터 자체의 구조적 성장.
      - 급격한 감소가 있다면 특정 프로토콜의 상환·해지 이벤트.
    """
    fig = go.Figure()

    # 색상 팔레트 (최대 10개 프로토콜)
    palette = [
        THEME["accent_teal"],
        THEME["accent_blue"],
        THEME["accent_gold"],
        "#a78bfa",  # violet
        "#f472b6",  # pink
        "#34d399",  # emerald
        "#fb923c",  # orange
        "#60a5fa",  # sky blue
        "#e879f9",  # fuchsia
        "#a3e635",  # lime
    ]

    cols = list(hist_df.columns)
    for i, col in enumerate(cols):
        color = palette[i % len(palette)]
        fig.add_trace(
            go.Scatter(
                x=hist_df.index,
                y=hist_df[col] / 1e9,
                name=col,
                mode="lines",
                stackgroup="rwa",
                line=dict(width=0.5, color=color),
                fillcolor=color.replace(")", ", 0.7)").replace("rgb(", "rgba(")
                    if color.startswith("rgb") else color,
                hovertemplate=f"<b>{col}</b><br>%{{x|%Y-%m-%d}}<br>$%{{y:.3f}}B<extra></extra>",
            )
        )

    # 전체 합계 선
    total = hist_df.sum(axis=1) / 1e9
    fig.add_trace(
        go.Scatter(
            x=total.index,
            y=total,
            name="합계",
            mode="lines",
            line=dict(color="white", width=1.5, dash="dot"),
            hovertemplate="<b>RWA 합계</b><br>%{x|%Y-%m-%d}<br>$%{y:.3f}B<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(
            text="RWA 프로토콜 구성 추이 (이더리움 TVL)",
            font=dict(size=14, color=THEME["text"]),
        ),
        xaxis=dict(title="날짜", gridcolor=THEME["grid"], color=THEME["text"]),
        yaxis=dict(title="TVL (십억 달러)", gridcolor=THEME["grid"], color=THEME["text"]),
        legend=dict(
            orientation="h",
            yanchor="top",  y=-0.18,
            xanchor="left", x=0,
        ),
        hovermode="x unified",
    )
    _apply_dark_theme(fig, height=460)
    fig.update_layout(margin=dict(b=110))  # extra room for legend below
    return fig


def chart_rwa_share_trend(
    hist_df: pd.DataFrame,
    l1_hist: pd.DataFrame | None,
) -> go.Figure:
    """
    이더리움 L1 TVL 내 RWA 비중(%) 시계열 라인 차트.

    비중 = (RWA 합계 TVL) / (이더리움 L1 총 TVL) × 100

    해석 가이드:
      - 우상향 추세 → 기관 채택이 DeFi 성장보다 빠름.
      - 횡보/하락 → DeFi 전반의 성장이 RWA 증가를 희석.
      - L1 TVL 데이터 없으면 RWA 절대 규모만 표시.
    """
    rwa_total = hist_df.sum(axis=1)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if l1_hist is not None and not l1_hist.empty:
        # L1 TVL 히스토리와 날짜 정렬 후 비중 계산
        combined = rwa_total.to_frame("rwa").join(
            l1_hist["tvl"].rename("l1"), how="inner"
        )
        combined["share"] = combined["rwa"] / combined["l1"] * 100

        # 비중 % (좌축, 채워진 선)
        fig.add_trace(
            go.Scatter(
                x=combined.index,
                y=combined["share"],
                name="RWA 비중 (%)",
                mode="lines",
                line=dict(color=THEME["accent_teal"], width=2),
                fill="tozeroy",
                fillcolor="rgba(0,212,170,0.15)",
                hovertemplate="<b>RWA 비중</b><br>%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>",
            ),
            secondary_y=False,
        )

        # L1 TVL (우축, 점선)
        fig.add_trace(
            go.Scatter(
                x=l1_hist.index,
                y=l1_hist["tvl"] / 1e9,
                name="L1 TVL (십억 달러)",
                mode="lines",
                line=dict(color=THEME["accent_gold"], width=1.2, dash="dot"),
                hovertemplate="<b>L1 TVL</b><br>%{x|%Y-%m-%d}<br>$%{y:.1f}B<extra></extra>",
            ),
            secondary_y=True,
        )

        fig.update_yaxes(
            title_text="RWA 비중 (%)",
            gridcolor=THEME["grid"], color=THEME["subtext"],
            secondary_y=False,
        )
        fig.update_yaxes(
            title_text="L1 TVL (십억 달러)",
            gridcolor=THEME["grid"], color=THEME["subtext"],
            secondary_y=True,
        )
    else:
        # L1 데이터 없으면 RWA 절대 TVL만 표시
        fig.add_trace(
            go.Scatter(
                x=rwa_total.index,
                y=rwa_total / 1e9,
                name="RWA 합계 TVL",
                mode="lines",
                line=dict(color=THEME["accent_teal"], width=2),
                fill="tozeroy",
                hovertemplate="<b>RWA TVL</b><br>%{x|%Y-%m-%d}<br>$%{y:.3f}B<extra></extra>",
            ),
            secondary_y=False,
        )
        fig.update_yaxes(
            title_text="RWA TVL (십억 달러)",
            gridcolor=THEME["grid"], color=THEME["subtext"],
            secondary_y=False,
        )

    fig.update_layout(
        title=dict(
            text="이더리움 L1 내 RWA 비중 추이",
            font=dict(size=14, color=THEME["text"]),
        ),
        xaxis=dict(title="날짜", gridcolor=THEME["grid"], color=THEME["text"]),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
        ),
        hovermode="x unified",
    )
    _apply_dark_theme(fig, height=380)
    return fig


def chart_rwa_chain_flow(
    eth_hist_df: pd.DataFrame,
    total_hist_df: pd.DataFrame,
) -> go.Figure:
    """
    RWA 자금 흐름: 이더리움 L1 vs 전체 체인 비교.

    Row 1 — 적층 영역
      · 이더리움 L1 RWA TVL (청록 채움)
      · 기타 체인(L2 + 타 체인) TVL (주황 채움) = 전체 - ETH
      → 주황 영역이 커질수록 ETH L1에서 타 체인으로 자금 이동 중

    Row 2 — ETH 비중 % 선
      · ETH TVL / 전체 TVL × 100
      → 하락 추세 = 기관이 이더리움 외 체인으로 다변화 중

    해석 가이드:
      ETH TVL ↓ + 전체 TVL 유지  →  L2/타 체인으로 이동 (생태계 내)
      ETH TVL ↓ + 전체 TVL ↓     →  오프체인 상환 (자금 완전 이탈)
    """
    # 날짜 정렬 및 공통 인덱스 확보
    eth_total   = eth_hist_df.reindex(eth_hist_df.index.union(total_hist_df.index)).fillna(0).sum(axis=1)
    all_total   = total_hist_df.reindex(eth_total.index).fillna(0).sum(axis=1)
    other_total = (all_total - eth_total).clip(lower=0)
    eth_share   = eth_total / all_total.replace(0, float("nan")) * 100

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.62, 0.38],
        vertical_spacing=0.06,
        subplot_titles=["이더리움 L1 vs 타 체인 RWA TVL", "이더리움 L1 비중 (%)"],
    )

    # Row 1: 적층 영역 (ETH + 기타)
    fig.add_trace(
        go.Scatter(
            x=eth_total.index, y=eth_total / 1e9,
            name="이더리움 L1",
            mode="lines", stackgroup="chains",
            line=dict(width=0.5, color=THEME["accent_teal"]),
            fillcolor="rgba(0,212,170,0.55)",
            hovertemplate="<b>이더리움 L1</b><br>%{x|%Y-%m-%d}<br>$%{y:.3f}B<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=other_total.index, y=other_total / 1e9,
            name="기타 체인 (L2 · 타 체인)",
            mode="lines", stackgroup="chains",
            line=dict(width=0.5, color=THEME["accent_gold"]),
            fillcolor="rgba(240,165,0,0.45)",
            hovertemplate="<b>기타 체인</b><br>%{x|%Y-%m-%d}<br>$%{y:.3f}B<extra></extra>",
        ),
        row=1, col=1,
    )

    # Row 2: ETH 비중 %
    fig.add_trace(
        go.Scatter(
            x=eth_share.index, y=eth_share,
            name="ETH L1 비중 (%)",
            mode="lines",
            line=dict(color=THEME["accent_teal"], width=2),
            fill="tozeroy",
            fillcolor="rgba(0,212,170,0.15)",
            hovertemplate="<b>ETH L1 비중</b><br>%{x|%Y-%m-%d}<br>%{y:.1f}%<extra></extra>",
        ),
        row=2, col=1,
    )
    # 50% 기준선
    fig.add_hline(
        y=50, row=2, col=1,
        line=dict(color=THEME["grid"], width=1, dash="dot"),
    )

    # 현재 비중 주석
    last_share = eth_share.dropna().iloc[-1] if not eth_share.dropna().empty else None
    if last_share is not None:
        fig.add_annotation(
            xref="paper", yref="y2",
            x=0.98, y=last_share,
            text=f"현재 {last_share:.1f}%",
            showarrow=False,
            font=dict(color=THEME["accent_teal"], size=11),
            xanchor="right",
        )

    fig.update_yaxes(title_text="TVL (십억 달러)", gridcolor=THEME["grid"], row=1, col=1)
    fig.update_yaxes(title_text="ETH 비중 (%)",    gridcolor=THEME["grid"], range=[0, 105], row=2, col=1)
    fig.update_xaxes(gridcolor=THEME["grid"], row=2, col=1)

    fig.update_layout(
        title=dict(
            text="RWA 자금 흐름: 이더리움 L1 vs 타 체인",
            font=dict(color=THEME["text"], size=14),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor=THEME["paper"], bordercolor=THEME["grid"], borderwidth=1,
            font=dict(color=THEME["text"], size=11),
        ),
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(color=THEME["text"], family="Inter, -apple-system, sans-serif", size=11),
        margin=dict(t=95, b=40, l=60, r=30),
        height=500,
        hovermode="x unified",
    )
    for ann in fig.layout.annotations:
        if getattr(ann, "yref", None) == "paper":
            ann.font.color = THEME["text"]
            ann.font.size  = 10
    return fig


def chart_rwa_chains_breakdown(
    eth_hist_df: pd.DataFrame,
    chains_agg: dict[str, pd.Series],
) -> go.Figure:
    """
    RWA 체인별 TVL 분포 적층 영역 차트.

    이더리움 L1 + 각 L2 / 타 체인 TVL을 모두 쌓아 올려
    "RWA 자금이 어느 체인에 얼마나 있는가"를 한눈에 파악한다.

    해석 가이드:
      · 이더리움(청록) 영역이 줄고 Arbitrum·Base(파랑) 영역이 늘면
        기관이 ETH 보안성은 유지하되 L2 저비용 환경을 선호하는 신호.
      · Solana·Stellar(보라/하늘) 영역이 커지면 이더리움 외 생태계로 다변화 중.
      · 특정 체인 영역이 갑자기 사라지면 해당 프로토콜의 만기 상환 이벤트.
    """
    fig = go.Figure()

    # 이더리움 L1 (항상 맨 아래 첫 번째 레이어)
    eth_total = eth_hist_df.sum(axis=1)
    fig.add_trace(go.Scatter(
        x=eth_total.index, y=eth_total / 1e9,
        name="Ethereum",
        mode="lines", stackgroup="chains",
        line=dict(width=0.5, color=THEME["accent_teal"]),
        fillcolor="rgba(0,212,170,0.65)",
        hovertemplate="<b>Ethereum</b><br>%{x|%Y-%m-%d}<br>$%{y:.3f}B<extra></extra>",
    ))

    # 알려진 체인은 팔레트 색상, 나머지는 "기타" 로 합산
    known_order = list(_CHAIN_PALETTE.keys())
    other_series: list[pd.Series] = []

    for chain in known_order:
        if chain not in chains_agg:
            continue
        s = chains_agg[chain]
        color = _CHAIN_PALETTE[chain]
        # hex → rgba 변환 (투명도 0.65)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        fig.add_trace(go.Scatter(
            x=s.index, y=s / 1e9,
            name=chain,
            mode="lines", stackgroup="chains",
            line=dict(width=0.5, color=color),
            fillcolor=f"rgba({r},{g},{b},0.65)",
            hovertemplate=f"<b>{chain}</b><br>%{{x|%Y-%m-%d}}<br>$%{{y:.3f}}B<extra></extra>",
        ))

    # 팔레트에 없는 체인 → "기타" 합산
    for chain, s in chains_agg.items():
        if chain not in known_order:
            other_series.append(s)
    if other_series:
        other = pd.concat(other_series, axis=1).sum(axis=1)
        fig.add_trace(go.Scatter(
            x=other.index, y=other / 1e9,
            name="기타 체인",
            mode="lines", stackgroup="chains",
            line=dict(width=0.5, color=THEME["subtext"]),
            fillcolor="rgba(160,170,180,0.45)",
            hovertemplate="<b>기타 체인</b><br>%{x|%Y-%m-%d}<br>$%{y:.3f}B<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text="RWA 체인별 TVL 분포 (이더리움 + L2 + 타 체인)",
            font=dict(color=THEME["text"], size=14),
        ),
        xaxis=dict(title="날짜", gridcolor=THEME["grid"], color=THEME["text"]),
        yaxis=dict(title="TVL (십억 달러)", gridcolor=THEME["grid"], color=THEME["text"]),
        legend=dict(
            orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0,
            bgcolor=THEME["paper"], bordercolor=THEME["grid"], borderwidth=1,
            font=dict(color=THEME["text"], size=10),
        ),
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(color=THEME["text"], family="Inter, -apple-system, sans-serif", size=11),
        margin=dict(t=55, b=120, l=60, r=30),
        height=460,
        hovermode="x unified",
    )
    return fig


# ── DeFi 카테고리 메타데이터 ──────────────────────────────────
_DEFI_CAT_KO: dict[str, str] = {
    "Liquid Staking":           "유동성 스테이킹",
    "Lending":                  "대출/차입",
    "Dexs":                     "DEX 유동성",          # ← DefiLlama 현행 카테고리명
    "CDP":                      "CDP 스테이블",
    "RWA":                      "RWA 실물자산",
    "RWA Lending":              "RWA 대출",
    "Staking":                  "스테이킹",
    "Staking Pool":             "스테이킹 풀",
    "Restaking":                "리스테이킹",
    "Liquid Restaking":         "유동성 리스테이킹",
    "Bridge":                   "브리지",
    "Canonical Bridge":         "공식 브리지",
    "Basis Trading":            "베이시스 트레이딩",
    "Onchain Capital Allocator":"온체인 자본 배분",
    "Risk Curators":            "리스크 큐레이터",
    "Derivatives":              "파생상품",
    "Yield":                    "수익 최적화",
    "Yield Aggregator":         "수익 어그리게이터",
    "Stablecoin Issuer":        "스테이블코인 발행",
    "CEX":                      "CEX 보관 자산",       # 거래소 지갑 잔액
}
_DEFI_CAT_COLOR: dict[str, str] = {
    "Liquid Staking":           "#7289da",
    "Lending":                  "#00d4aa",
    "Dexs":                     "#f0a500",
    "CDP":                      "#e879f9",
    "RWA":                      "#34d399",
    "RWA Lending":              "#2ecc71",
    "Staking":                  "#5b8dee",
    "Staking Pool":             "#4a78d4",
    "Restaking":                "#a78bfa",
    "Liquid Restaking":         "#c084fc",
    "Bridge":                   "#fb923c",
    "Canonical Bridge":         "#f97316",
    "Basis Trading":            "#f59e0b",
    "Onchain Capital Allocator":"#10b981",
    "Risk Curators":            "#06b6d4",
    "Derivatives":              "#f87171",
    "Yield":                    "#60a5fa",
    "Yield Aggregator":         "#38bdf8",
    "Stablecoin Issuer":        "#94a3b8",
    "CEX":                      "#64748b",
}
_DEFI_KEEP_CATS = set(_DEFI_CAT_KO.keys())


def extract_defi_categories_tvl(protocols_data: list | None) -> dict[str, dict]:
    """
    이더리움 L1 DeFi 카테고리별 TVL 집계.

    핵심: p["chainTvls"]["Ethereum"] 사용 — p["tvl"] 은 모든 체인 합산이라
    멀티체인 프로토콜의 TVL 이 이더리움 버킷을 비정상적으로 부풀린다.

    반환: {category_en: {tvl, ko, color, protocols: [{name, slug, tvl}]}}
    """
    if not protocols_data:
        return {}
    cat_data: dict[str, dict] = {}
    other_tvl = 0.0
    other_protocols: list[dict] = []
    for p in protocols_data:
        # 이더리움 전용 TVL 사용 (멀티체인 오염 방지)
        chain_tvls = p.get("chainTvls") or {}
        eth_raw = chain_tvls.get("Ethereum", 0)
        tvl = float(eth_raw) if isinstance(eth_raw, (int, float)) else 0.0
        if tvl < 1e5:          # 10만 달러 미만 제외
            continue
        cat = p.get("category") or "Unknown"
        slug = p.get("slug", "")
        if cat in _DEFI_KEEP_CATS:
            if cat not in cat_data:
                cat_data[cat] = {
                    "tvl": 0.0,
                    "ko": _DEFI_CAT_KO[cat],
                    "color": _DEFI_CAT_COLOR[cat],
                    "protocols": [],
                }
            cat_data[cat]["tvl"] += tvl
            cat_data[cat]["protocols"].append({"name": p.get("name", ""), "slug": slug, "tvl": tvl})
        else:
            other_tvl += tvl
            other_protocols.append({
                "name": p.get("name", ""),
                "slug": slug,
                "tvl": tvl,
                "category": cat,
            })
    if other_tvl > 1e6:
        cat_data["기타 DeFi"] = {
            "tvl": other_tvl,
            "ko": "기타 DeFi",
            "color": THEME["subtext"],
            "protocols": sorted(other_protocols, key=lambda x: x["tvl"], reverse=True)[:30],
        }
    for v in cat_data.values():
        v["protocols"].sort(key=lambda x: x["tvl"], reverse=True)
    return dict(sorted(cat_data.items(), key=lambda x: x[1]["tvl"], reverse=True))


def chart_l1_tvl_categories(cat_data: dict) -> go.Figure:
    """
    이더리움 L1 TVL DeFi 카테고리 구성 도넛 차트.

    유동성 스테이킹 > 대출 > DEX > CDP > RWA > 기타 순으로
    '79.7% Non-RWA'의 실제 구성 요소를 보여준다.

    해석 가이드:
      · 유동성 스테이킹(Lido 등)이 가장 크면 ETH 가 '기초 담보 자산'으로 사용 중.
      · 대출(Aave 등)이 클수록 레버리지·이자 수익 DeFi 활동이 활발.
      · RWA 비중이 서서히 커지면 기관 채택 추세 확인.
    """
    labels = [v["ko"] for v in cat_data.values()]
    values = [v["tvl"] for v in cat_data.values()]
    colors = [v["color"] for v in cat_data.values()]

    total = sum(values) or 1
    # 5% 이상 슬라이스만 레이블 표시, 작은 슬라이스는 퍼센트만
    text_list = [
        f"{l}<br>{v/total*100:.1f}%" if v / total >= 0.05
        else f"{v/total*100:.1f}%" if v / total >= 0.025
        else ""
        for l, v in zip(labels, values)
    ]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        text=text_list,
        textinfo="text",
        textfont=dict(size=10, color=THEME["text"]),
        textposition="outside",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
        marker=dict(colors=colors, line=dict(color=THEME["bg"], width=1)),
        sort=False,
        rotation=30,
    ))
    fig.update_layout(
        title=dict(
            text="이더리움 L1 TVL: DeFi 카테고리 구성",
            font=dict(color=THEME["text"], size=14),
        ),
        showlegend=False,
        margin=dict(t=80, b=80, l=80, r=80),
    )
    _apply_dark_theme(fig, height=480)
    return fig


def chart_defi_top_protocols_history(histories: dict[str, dict]) -> go.Figure:
    """
    주요 DeFi 프로토콜 ETH L1 TVL 시계열 (카테고리별 색상).

    histories: {
        protocol_name: {
            "series":      pd.Series,
            "color":       str,
            "category_ko": str,
        }
    }

    해석 가이드:
      · Lido(스테이킹) 선이 압도적으로 높으면 이더리움의 핵심 역할이 '보안 자산'.
      · Aave 대출 TVL 이 상승하면 레버리지 수요가 살아있는 시장.
      · Uniswap/Curve 유동성이 커지면 DEX 거래량 증가 선행 신호.
      · MakerDAO CDP TVL 은 순수 ETH 담보 수요의 온도계.
    """
    fig = go.Figure()
    for name, meta in histories.items():
        s = meta["series"]
        color = meta["color"]
        cat_ko = meta["category_ko"]
        fig.add_trace(go.Scatter(
            x=s.index, y=s / 1e9,
            name=f"{name} ({cat_ko})",
            mode="lines",
            line=dict(width=1.8, color=color),
            hovertemplate=f"<b>{name}</b><br>%{{x|%Y-%m-%d}}<br>$%{{y:.3f}}B<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text="주요 DeFi 프로토콜 ETH L1 TVL 추이",
            font=dict(color=THEME["text"], size=14),
        ),
        xaxis=dict(title="날짜", gridcolor=THEME["grid"], color=THEME["text"]),
        yaxis=dict(title="TVL (십억 달러)", gridcolor=THEME["grid"], color=THEME["text"]),
        legend=dict(
            orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0,
            bgcolor=THEME["paper"], bordercolor=THEME["grid"], borderwidth=1,
            font=dict(color=THEME["text"], size=10),
        ),
        hovermode="x unified",
    )
    _apply_dark_theme(fig, height=420)
    fig.update_layout(margin=dict(b=110))
    return fig


# ============================================================
# 5-b. 활동량 분석 차트 함수
# ============================================================

def chart_active_addresses(
    eth_df: pd.DataFrame | None,
    sol_df: pd.DataFrame | None,
) -> go.Figure:
    """
    ETH L1 vs Solana 일일 활성 주소 수(DAA) 비교 이중 Y축 차트.

    해석 가이드:
      - TVL 하락 구간에서 DAA가 유지/상승 → 가격 하락 탓이지 사용자 이탈이 아님.
      - SOL의 DAA가 ETH를 크게 상회 → 솔라나의 소비자(Retail) 사용자 기반이 더 넓음.
      - 단, ETH L1 DAA는 고가스비로 인해 실제 ETH 생태계 총 사용자보다 낮게 집계됨.
        (대부분 L2로 이동했기 때문)
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if eth_df is not None and "AdrActCnt" in eth_df.columns:
        fig.add_trace(
            go.Scatter(
                x=eth_df.index,
                y=eth_df["AdrActCnt"] / 1e6,
                name="ETH L1 활성 주소 (백만)",
                line=dict(color=THEME["accent_teal"], width=2),
                hovertemplate="<b>ETH L1 DAA</b>: %{y:.3f}M<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

    if sol_df is not None and "AdrActCnt" in sol_df.columns:
        fig.add_trace(
            go.Scatter(
                x=sol_df.index,
                y=sol_df["AdrActCnt"] / 1e6,
                name="Solana 활성 주소 (백만)",
                line=dict(color="#9945FF", width=2),
                hovertemplate="<b>SOL DAA</b>: %{y:.3f}M<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="ETH L1 (백만 주소)", secondary_y=False, ticksuffix="M")
    fig.update_yaxes(title_text="Solana (백만 주소)", secondary_y=True, ticksuffix="M", showgrid=False)
    fig.update_layout(
        title=dict(text="일일 활성 주소 수 (ETH L1 vs Solana)", x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=380)
    return fig


def chart_network_fees(
    eth_fees_df: pd.DataFrame | None,
    sol_fees_df: pd.DataFrame | None,
) -> go.Figure:
    """
    ETH vs Solana 일일 네트워크 수수료 비교 (이중 Y축).

    Solana 트랜잭션 수/활성주소는 무료 API 미지원 → 네트워크 수수료로 대체.
    수수료 총액 = 사용자 수 × 건당 수수료. 두 체인의 경제 활동 총량을 비교하는 지표.

    해석:
      ETH: 건당 수수료 높음 (고가치 DeFi·RWA 거래 중심)
      SOL: 건당 수수료 극히 낮지만 건수 압도적 → 총 수수료로 비교 가능
    이중 Y축으로 절대 규모 차이를 조정하여 추세 비교에 집중.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if eth_fees_df is not None and not eth_fees_df.empty:
        # 7일 이동평균으로 일별 노이즈 제거
        smoothed = eth_fees_df["fees_usd"].rolling(7, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=eth_fees_df.index,
                y=smoothed / 1e6,
                name="ETH DeFi 프로토콜 수수료 (7일 MA, $M)",
                line=dict(color=THEME["accent_teal"], width=2.5),
                hovertemplate="<b>ETH DeFi 수수료</b>: $%{y:.1f}M<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

    if sol_fees_df is not None and not sol_fees_df.empty:
        smoothed_sol = sol_fees_df["fees_usd"].rolling(7, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=sol_fees_df.index,
                y=smoothed_sol / 1e6,
                name="SOL DeFi 프로토콜 수수료 (7일 MA, $M)",
                line=dict(color="#9945FF", width=2.5),
                hovertemplate="<b>SOL DeFi 수수료</b>: $%{y:.3f}M<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="ETH DeFi 수수료 ($M, 7일 MA)", secondary_y=False,
                     tickprefix="$", ticksuffix="M")
    fig.update_yaxes(title_text="SOL DeFi 수수료 ($M, 7일 MA)", secondary_y=True,
                     tickprefix="$", ticksuffix="M", showgrid=False)
    fig.update_layout(
        title=dict(text="DeFi 프로토콜 수수료: ETH vs Solana (7일 MA, 이중 Y축)", x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=380)
    return fig


def chart_eth_supply_burn(df: pd.DataFrame | None) -> go.Figure:
    """
    ETH 총 공급량 + 일일 순발행량(= 스테이킹 보상 − EIP-1559 소각) 2-패널 차트.

    상단: ETH 유통 공급량 (M ETH) — 면적 차트
    하단: 일일 순발행량 (ETH) — 양수=인플레이션(청록), 음수=디플레이션(빨강)

    핵심 내러티브:
      - 머지(2022-09-15) 이전: 채굴 보상으로 일 ~13,000 ETH 발행
      - 머지 이후: 스테이킹 보상 ~1,700 ETH/일로 급감
      - 네트워크 혼잡 시(EIP-1559 소각 > 스테이킹 보상): 공급 감소 = "ultrasound money"
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.58, 0.42],
        subplot_titles=[
            "ETH 유통 공급량 (M ETH)",
            "일일 순발행량 (ETH) = 스테이킹 보상 − EIP-1559 소각",
        ],
        vertical_spacing=0.10,
    )

    if df is not None and not df.empty:
        supply_m = df["supply"] / 1e6
        net      = df["net_issuance"].dropna()

        # ── 상단: 유통 공급량 면적 차트 ─────────────────────
        fig.add_trace(
            go.Scatter(
                x=supply_m.index,
                y=supply_m,
                name="유통 공급량",
                fill="tozeroy",
                fillcolor="rgba(0,212,170,0.15)",
                line=dict(color=THEME["accent_teal"], width=2),
                hovertemplate="<b>공급량</b>: %{y:.3f}M ETH<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            row=1, col=1,
        )

        # 현재 공급량 주석
        last_supply = supply_m.iloc[-1]
        fig.add_annotation(
            x=supply_m.index[-1], y=last_supply,
            text=f"현재 {last_supply:.3f}M ETH",
            showarrow=True, arrowhead=2, arrowcolor=THEME["accent_teal"],
            font=dict(color=THEME["accent_teal"], size=11),
            bgcolor=THEME["paper"], bordercolor=THEME["accent_teal"],
            borderwidth=1, xanchor="right", yanchor="bottom",
            row=1, col=1,
        )

        # ── 하단: 순발행량 막대 차트 (인플레=청록, 디플레=빨강) ─
        bar_colors = [
            THEME["accent_teal"] if v >= 0 else THEME["accent_red"]
            for v in net
        ]
        fig.add_trace(
            go.Bar(
                x=net.index,
                y=net,
                name="순발행량",
                marker_color=bar_colors,
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d}</b><br>"
                    "순발행량: %{y:+,.0f} ETH<br>"
                    "<i>양수=인플레이션, 음수=디플레이션</i><extra></extra>"
                ),
            ),
            row=2, col=1,
        )

        # 기준선 0 강조
        fig.add_hline(
            y=0, line=dict(color=THEME["subtext"], width=1, dash="dot"),
            row=2, col=1,
        )

        # 통계 주석 (하단 패널)
        total_days = len(net)
        deflationary = int((net < 0).sum())
        avg_net = net.mean()
        fig.add_annotation(
            x=0.01, y=0.12, xref="paper", yref="paper",
            text=(
                f"평균 순발행: {avg_net:+,.0f} ETH/일 &nbsp;|&nbsp; "
                f"디플레이션 일수: {deflationary}/{total_days}일 "
                f"({deflationary/total_days*100:.0f}%)"
            ),
            showarrow=False,
            font=dict(color=THEME["subtext"], size=10),
            bgcolor=THEME["paper"], bordercolor=THEME["grid"],
            borderwidth=1, align="left",
        )

    else:
        fig.add_annotation(
            x=0.5, y=0.5, xref="paper", yref="paper",
            text="데이터를 불러오는 중 오류가 발생했습니다.",
            showarrow=False, font=dict(color=THEME["subtext"], size=13),
        )

    fig.update_yaxes(title_text="공급량 (M ETH)", row=1, col=1, ticksuffix="M")
    fig.update_yaxes(title_text="순발행량 (ETH/일)", row=2, col=1)
    fig.update_layout(
        title=dict(
            text="ETH 총 공급량 & 순발행량 (스테이킹 보상 − EIP-1559 소각)",
            x=0.02,
        ),
        showlegend=False,
    )
    _apply_dark_theme(fig, height=480)
    return fig


def chart_stablecoin_activity(
    eth_stbl: pd.DataFrame | None,
    sol_stbl: pd.DataFrame | None,
) -> go.Figure:
    """
    ETH vs Solana 스테이블코인 온체인 잔액 비교 (이중 Y축).

    스테이블코인 잔액 증가의 의미:
      (A) 가격 하락 시 잔액 유지 → 자본이 체인 밖으로 떠나지 않고 USDC/USDT로 대기 중.
          '이탈'이 아닌 '관망'. 시장 반전 시 즉각 재진입 가능.
      (B) TVL 하락 + 스테이블코인 잔액 증가 → 리스크 자산(ETH) 청산 후 스테이블로 보유.
          이 경우 체인의 경제 활동은 유지된 채 자산 구성만 바뀐 것.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if eth_stbl is not None and not eth_stbl.empty:
        fig.add_trace(
            go.Scatter(
                x=eth_stbl.index,
                y=eth_stbl["stablecoin_mcap"] / 1e9,
                name="ETH 스테이블코인 ($B)",
                line=dict(color=THEME["accent_teal"], width=2),
                fill="tozeroy",
                fillcolor="rgba(0,212,170,0.12)",
                hovertemplate="<b>ETH Stable</b>: $%{y:.1f}B<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

    if sol_stbl is not None and not sol_stbl.empty:
        fig.add_trace(
            go.Scatter(
                x=sol_stbl.index,
                y=sol_stbl["stablecoin_mcap"] / 1e9,
                name="Solana 스테이블코인 ($B)",
                line=dict(color="#9945FF", width=2),
                fill="tozeroy",
                fillcolor="rgba(153,69,255,0.12)",
                hovertemplate="<b>SOL Stable</b>: $%{y:.1f}B<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="ETH 스테이블코인 ($B)", secondary_y=False, tickprefix="$", ticksuffix="B")
    fig.update_yaxes(title_text="SOL 스테이블코인 ($B)", secondary_y=True, tickprefix="$", ticksuffix="B", showgrid=False)
    fig.update_layout(
        title=dict(text="스테이블코인 온체인 잔액 (ETH vs Solana)", x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=380)
    return fig


def chart_price_activity_decoupling(
    price_df: pd.DataFrame | None,
    eth_act_df: pd.DataFrame | None,
    sol_act_df: pd.DataFrame | None,
) -> go.Figure:
    """
    ETH 가격 변화율 vs 활성 주소 수 변화율 디커플링 분석.

    기준점(=100)으로 정규화하여 세 지표를 같은 축에 표시.
    → 가격이 하락해도 활성 주소가 100을 유지하거나 상승하면,
      '가격 하락 = 사용자 이탈'이라는 오해를 수치로 반박할 수 있다.
    이것이 Gemini가 언급한 '활동량-가격 디커플링(Decoupling)' 현상.
    """
    fig = go.Figure()

    def _normalize(series: pd.Series) -> pd.Series:
        """첫 유효 값을 100으로 설정하여 변화율(%) 비교."""
        s = series.dropna()
        if s.empty or s.iloc[0] == 0:
            return s
        return s / s.iloc[0] * 100

    if price_df is not None and not price_df.empty:
        norm_price = _normalize(price_df["price"])
        fig.add_trace(go.Scatter(
            x=norm_price.index,
            y=norm_price,
            name="ETH 가격 (정규화)",
            line=dict(color=THEME["accent_gold"], width=2.5),
            hovertemplate="<b>ETH 가격</b>: %{y:.1f} (기준 100)<br>%{x|%Y-%m-%d}<extra></extra>",
        ))

    if eth_act_df is not None and "AdrActCnt" in eth_act_df.columns:
        norm_eth_adr = _normalize(eth_act_df["AdrActCnt"])
        fig.add_trace(go.Scatter(
            x=norm_eth_adr.index,
            y=norm_eth_adr,
            name="ETH L1 활성 주소 (정규화)",
            line=dict(color=THEME["accent_teal"], width=2, dash="dash"),
            hovertemplate="<b>ETH DAA</b>: %{y:.1f} (기준 100)<br>%{x|%Y-%m-%d}<extra></extra>",
        ))

    if sol_act_df is not None and "AdrActCnt" in sol_act_df.columns:
        norm_sol_adr = _normalize(sol_act_df["AdrActCnt"])
        fig.add_trace(go.Scatter(
            x=norm_sol_adr.index,
            y=norm_sol_adr,
            name="Solana 활성 주소 (정규화)",
            line=dict(color="#9945FF", width=2, dash="dash"),
            hovertemplate="<b>SOL DAA</b>: %{y:.1f} (기준 100)<br>%{x|%Y-%m-%d}<extra></extra>",
        ))

    # 기준선 100
    fig.add_hline(y=100, line_dash="dot", line_color=THEME["grid"],
                  annotation_text="기준점(100)", annotation_font_color=THEME["subtext"])

    fig.update_layout(
        title=dict(text="가격 vs 활성 주소 수 디커플링 분석 (기준점=100)", x=0.02),
        yaxis_title="정규화 지수 (시작점=100)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=400)
    return fig


def chart_dex_capital_efficiency(
    eth_vol_df: pd.DataFrame | None,
    eth_tvl_df: pd.DataFrame | None,
    sol_vol_df: pd.DataFrame | None,
    sol_tvl_df: pd.DataFrame | None,
) -> go.Figure:
    """
    DEX 거래량 / TVL 자본 효율성 비율 비교 (ETH vs SOL).

    자본 효율성 = 일일 DEX 거래량 / TVL
    해석:
      - 비율 높음 → 예치된 자본이 하루에 몇 번씩 거래에 활용됨 (자본 회전율 높음).
      - 솔라나: 초저수수료로 빈번한 소액 거래 → 비율 높음 (거래 특화).
      - 이더리움: 고가치 자산이 장기 예치 → 비율 낮지만 건당 경제 가치는 큼 (저장 특화).
    이 차트는 두 체인이 '경쟁'이 아닌 '다른 시장'을 공략함을 보여준다.
    """
    fig = go.Figure()

    def _compute_ratio(vol_df, tvl_df, label, color):
        if vol_df is None or tvl_df is None:
            return
        merged = vol_df.join(tvl_df, how="inner")
        if merged.empty or merged["tvl"].eq(0).all():
            return
        merged["ratio"] = merged["volume"] / merged["tvl"] * 100  # 퍼센트
        merged = merged.dropna(subset=["ratio"])
        # 7일 이동평균으로 노이즈 제거
        merged["ratio_ma7"] = merged["ratio"].rolling(7, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=merged.index,
            y=merged["ratio_ma7"],
            name=f"{label} (7일 MA)",
            line=dict(color=color, width=2.5),
            hovertemplate=f"<b>{label}</b>: %{{y:.2f}}%<br>%{{x|%Y-%m-%d}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=merged.index,
            y=merged["ratio"],
            name=f"{label} (일별)",
            line=dict(color=color, width=0.8),
            opacity=0.35,
            showlegend=False,
            hovertemplate=f"<b>{label} 일별</b>: %{{y:.2f}}%<br>%{{x|%Y-%m-%d}}<extra></extra>",
        ))

    _compute_ratio(eth_vol_df, eth_tvl_df, "ETH DEX Vol/TVL", THEME["accent_teal"])
    _compute_ratio(sol_vol_df, sol_tvl_df, "SOL DEX Vol/TVL", "#9945FF")

    fig.update_layout(
        title=dict(text="DEX 거래량 / TVL 자본 효율성 비교 (ETH vs Solana, 7일 MA)", x=0.02),
        yaxis_title="DEX Volume / TVL (%)",
        yaxis_ticksuffix="%",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=400)
    return fig


# ============================================================
# 5-B. 트리거 분석 차트 함수
# ============================================================

def chart_eth_treasury_yield(
    eth_df: pd.DataFrame | None,
    macro_df: pd.DataFrame | None,
) -> go.Figure:
    """
    ETH 가격 + 미 국채 10년물 금리 + 급락(-5%+) 이벤트 마커.

    금리 급등과 ETH 가격 하락이 겹치면 기관의 de-risking에 의한 하락.
    빨간 삼각형 마커: 당일 ETH 가격이 전일 대비 5% 이상 하락한 날.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if eth_df is not None and not eth_df.empty:
        fig.add_trace(
            go.Scatter(
                x=eth_df.index,
                y=eth_df["price"],
                name="ETH 가격 ($)",
                line=dict(color=THEME["accent_teal"], width=2),
                hovertemplate="<b>ETH</b>: $%{y:,.0f}<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

        # 급락 이벤트: 붉은 세로선 + 삼각형 마커 (-5% 이상 하락)
        pct_chg = eth_df["price"].pct_change()
        drops   = eth_df[pct_chg <= -0.05]
        if not drops.empty:
            # 붉은 점선 세로선
            # add_vline의 annotation은 날짜 문자열 평균 계산 오류를 일으킴
            # → add_shape(선) + add_annotation(레이블) 분리 방식으로 대체
            for drop_date, _ in drops.iterrows():
                chg  = pct_chg[drop_date] * 100
                x_str = str(drop_date.date())
                fig.add_shape(
                    type="line",
                    x0=x_str, x1=x_str,
                    y0=0, y1=1, yref="paper",
                    line=dict(color=THEME["accent_red"], width=1.2, dash="dash"),
                )
                fig.add_annotation(
                    x=x_str,
                    y=eth_df.loc[drop_date, "price"],
                    text=f"{chg:.1f}%",
                    showarrow=False,
                    font=dict(color=THEME["accent_red"], size=9),
                    xanchor="center", yanchor="bottom",
                )
            # 삼각형 마커 — 호버 시 정확한 가격/변동률 확인
            fig.add_trace(
                go.Scatter(
                    x=drops.index,
                    y=drops["price"],
                    mode="markers",
                    name="급락 ≥-5%",
                    marker=dict(
                        symbol="triangle-down",
                        color=THEME["accent_red"],
                        size=11,
                        line=dict(color="#fff", width=1),
                    ),
                    hovertemplate=(
                        "<b>급락</b>: $%{y:,.0f}<br>"
                        "변동: %{customdata:.1f}%<br>"
                        "%{x|%Y-%m-%d}<extra></extra>"
                    ),
                    customdata=pct_chg[pct_chg <= -0.05] * 100,
                ),
                secondary_y=False,
            )
            fig.add_annotation(
                x=0.01, y=0.97, xref="paper", yref="paper",
                text=f"기간 내 급락(-5%↓) 발생: {len(drops)}회",
                showarrow=False,
                font=dict(color=THEME["accent_red"], size=11),
                bgcolor=THEME["paper"], bordercolor=THEME["accent_red"],
                borderwidth=1, align="left",
            )

    if macro_df is not None and "tnx" in macro_df.columns:
        fig.add_trace(
            go.Scatter(
                x=macro_df.index,
                y=macro_df["tnx"],
                name="미 국채 10년물 금리 (%)",
                line=dict(color=THEME["accent_gold"], width=2, dash="dot"),
                hovertemplate="<b>10년물</b>: %{y:.2f}%<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="ETH 가격 ($)", secondary_y=False, tickprefix="$")
    fig.update_yaxes(
        title_text="10년물 금리 (%)", secondary_y=True,
        ticksuffix="%", showgrid=False,
    )
    fig.update_layout(
        title=dict(text="ETH 가격 vs 미 국채 10년물 금리 + 급락 이벤트 마커", x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=400)
    return fig


def chart_dxy_vs_eth(
    eth_df: pd.DataFrame | None,
    macro_df: pd.DataFrame | None,
) -> go.Figure:
    """
    달러 인덱스(DXY) vs ETH 가격 (이중 Y축).

    달러 강세(DXY ↑) → 위험자산 약세(ETH ↓): 역상관 관계.
    두 선이 반대 방향으로 움직이는 구간 = 달러 강세가 하락 트리거인 시기.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if eth_df is not None and not eth_df.empty:
        fig.add_trace(
            go.Scatter(
                x=eth_df.index,
                y=eth_df["price"],
                name="ETH 가격 ($)",
                line=dict(color=THEME["accent_teal"], width=2),
                hovertemplate="<b>ETH</b>: $%{y:,.0f}<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

    if macro_df is not None and "dxy" in macro_df.columns:
        fig.add_trace(
            go.Scatter(
                x=macro_df.index,
                y=macro_df["dxy"],
                name="DXY 달러 인덱스",
                line=dict(color=THEME["accent_gold"], width=2, dash="dot"),
                hovertemplate="<b>DXY</b>: %{y:.2f}<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="ETH 가격 ($)", secondary_y=False, tickprefix="$")
    fig.update_yaxes(
        title_text="DXY 달러 인덱스", secondary_y=True,
        showgrid=False,
    )
    fig.update_layout(
        title=dict(text="달러 인덱스(DXY) vs ETH 가격 — 달러 강세 = ETH 약세?", x=0.02),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=400)
    return fig


def chart_btc_dominance(
    dom_df: pd.DataFrame | None,
    eth_df: pd.DataFrame | None,
) -> go.Figure:
    """
    BTC 도미넌스 대리 지표 vs ETH 가격 (이중 Y축).

    BTC/(BTC+ETH) 시가총액 비율이 오를 때 ETH가 하락하면
    → 시장 자금이 알트코인에서 안전자산(BTC)으로 피신하는 중.
    이 경우 하락 원인은 외부 충격이 아닌 내부 로테이션.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if eth_df is not None and not eth_df.empty:
        fig.add_trace(
            go.Scatter(
                x=eth_df.index,
                y=eth_df["price"],
                name="ETH 가격 ($)",
                line=dict(color=THEME["accent_teal"], width=2),
                hovertemplate="<b>ETH</b>: $%{y:,.0f}<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=False,
        )

    if dom_df is not None and not dom_df.empty:
        fig.add_trace(
            go.Scatter(
                x=dom_df.index,
                y=dom_df["dom_proxy"],
                name="BTC 도미넌스 대리 (%)",
                line=dict(color=THEME["accent_blue"], width=2, dash="dot"),
                fill="tozeroy",
                fillcolor="rgba(114,137,218,0.08)",
                hovertemplate="<b>BTC 도미넌스</b>: %{y:.1f}%<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="ETH 가격 ($)", secondary_y=False, tickprefix="$")
    fig.update_yaxes(
        title_text="BTC 도미넌스 대리 (%)", secondary_y=True,
        ticksuffix="%", showgrid=False,
    )
    fig.update_layout(
        title=dict(
            text="BTC 도미넌스 대리 지표 vs ETH — BTC↑ = 알트코인 로테이션?",
            x=0.02,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    _apply_dark_theme(fig, height=400)
    return fig


def chart_fear_greed(fg_df: pd.DataFrame | None) -> go.Figure:
    """
    암호화폐 공포-탐욕 지수 (Fear & Greed Index) 막대 차트.

    색상 의미:
      0–25  빨강  Extreme Fear  — 시장 패닉
      26–45 주황  Fear          — 비관
      46–55 노랑  Neutral       — 중립
      56–75 연두  Greed         — 낙관
      76–100청록  Extreme Greed — 과열 경고

    Trigger 해석:
      지수 평온 + 가격 급락 → 고래 차익실현(내부 요인).
      지수 + 가격 동시 급락 → 외부 악재(규제/거시) 트리거.
    """
    fig = go.Figure()

    if fg_df is not None and not fg_df.empty:
        def _fg_color(v: float) -> str:
            if v <= 25:  return THEME["accent_red"]
            if v <= 45:  return "#f0a500"
            if v <= 55:  return "#f5c518"
            if v <= 75:  return "#7dbb00"
            return THEME["accent_teal"]

        bar_colors = [_fg_color(v) for v in fg_df["value"]]
        fig.add_trace(
            go.Bar(
                x=fg_df.index,
                y=fg_df["value"],
                marker_color=bar_colors,
                name="공포-탐욕 지수",
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d}</b><br>"
                    "지수: %{y}<br>"
                    "%{customdata}<extra></extra>"
                ),
                customdata=fg_df["classification"],
            )
        )

        # 구간 구분선
        for level, label in [(25, "극도 공포"), (45, "공포"), (55, "탐욕"), (75, "극도 탐욕")]:
            fig.add_hline(
                y=level,
                line=dict(color=THEME["grid"], width=1, dash="dot"),
                annotation_text=label,
                annotation_position="right",
                annotation_font_color=THEME["subtext"],
                annotation_font_size=10,
            )

        # 현재값 주석
        cur_val   = int(fg_df["value"].iloc[-1])
        cur_class = fg_df["classification"].iloc[-1]
        cur_color = _fg_color(cur_val)
        fig.add_annotation(
            x=0.99, y=0.95, xref="paper", yref="paper",
            text=f"현재: <b>{cur_val}</b> ({cur_class})",
            showarrow=False,
            font=dict(color=cur_color, size=13),
            bgcolor=THEME["paper"], bordercolor=cur_color,
            borderwidth=1, align="right",
        )

    fig.update_yaxes(range=[0, 100], title_text="지수 (0=극도공포, 100=극도탐욕)")
    fig.update_layout(
        title=dict(text="암호화폐 공포-탐욕 지수 (Fear & Greed Index)", x=0.02),
        showlegend=False,
    )
    _apply_dark_theme(fig, height=400)
    return fig


def chart_fear_greed_gauge(fg_df: pd.DataFrame | None) -> go.Figure:
    """
    공포-탐욕 지수 현재값을 반원 게이지(go.Indicator)로 표시.
    bar chart와 함께 사이드바/좁은 컬럼에 배치하여 현재 상태를 직관적으로 전달.
    """
    fig = go.Figure()

    if fg_df is not None and not fg_df.empty:
        cur_val   = int(fg_df["value"].iloc[-1])
        cur_class = fg_df["classification"].iloc[-1]

        def _fg_color(v: float) -> str:
            if v <= 25:  return THEME["accent_red"]
            if v <= 45:  return "#f0a500"
            if v <= 55:  return "#f5c518"
            if v <= 75:  return "#7dbb00"
            return THEME["accent_teal"]

        cur_color = _fg_color(cur_val)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=cur_val,
            title={"text": f"<b>{cur_class}</b>", "font": {"color": cur_color, "size": 14}},
            number={"font": {"color": cur_color, "size": 36}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickvals": [0, 25, 45, 55, 75, 100],
                    "ticktext": ["0", "25", "45", "55", "75", "100"],
                    "tickfont": {"color": THEME["subtext"], "size": 9},
                },
                "bar": {"color": cur_color, "thickness": 0.25},
                "bgcolor": THEME["bg"],
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  25],  "color": "rgba(255,75,75,0.25)"},
                    {"range": [25, 45],  "color": "rgba(240,165,0,0.25)"},
                    {"range": [45, 55],  "color": "rgba(245,197,24,0.25)"},
                    {"range": [55, 75],  "color": "rgba(125,187,0,0.25)"},
                    {"range": [75, 100], "color": "rgba(0,212,170,0.25)"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 3},
                    "thickness": 0.75,
                    "value": cur_val,
                },
            },
        ))
    else:
        fig.add_annotation(
            x=0.5, y=0.5, xref="paper", yref="paper",
            text="데이터 없음", showarrow=False,
            font=dict(color=THEME["subtext"]),
        )

    fig.update_layout(
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(color=THEME["text"], family="Inter, -apple-system, sans-serif"),
        margin=dict(t=30, b=10, l=20, r=20),
        height=260,
    )
    return fig


def chart_trigger_combined(
    eth_df:   pd.DataFrame | None,
    macro_df: pd.DataFrame | None,
    dom_df:   pd.DataFrame | None,
    fg_df:    pd.DataFrame | None,
) -> go.Figure:
    """
    트리거 분석 통합 4-패널 스택 차트 (make_subplots, 공유 X축).

    Row 1 (38%): ETH 가격 + 급락 이벤트 붉은 세로선 + 변동률 주석
    Row 2 (21%): 미 국채 10년물 금리(%) — 금리 급등 = 기관 de-risking
    Row 3 (21%): BTC 도미넌스 대리 지표(%) — 도미넌스 상승 = 알트 약세
    Row 4 (20%): 공포-탐욕 지수 — 색상 막대

    모든 패널이 같은 X축(날짜)을 공유하여 시점별 인과관계를 한눈에 파악.
    """
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.38, 0.21, 0.21, 0.20],
        subplot_titles=[
            "ETH 가격 ($) — 급락(-5%↓) 붉은 세로선",
            "미 국채 10년물 금리 (%) — 금리↑ = 기관 de-risking",
            "BTC 도미넌스 대리 (%) — BTC↑ = 알트코인 로테이션",
            "공포-탐욕 지수 — 극도공포(빨강) ~ 극도탐욕(청록)",
        ],
        vertical_spacing=0.04,
    )

    # ── Row 1: ETH 가격 + 급락 세로선 ──────────────────────
    if eth_df is not None and not eth_df.empty:
        fig.add_trace(
            go.Scatter(
                x=eth_df.index, y=eth_df["price"],
                name="ETH 가격",
                line=dict(color=THEME["accent_teal"], width=2),
                hovertemplate="<b>ETH</b>: $%{y:,.0f}<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            row=1, col=1,
        )
        pct_chg = eth_df["price"].pct_change()
        drops   = eth_df[pct_chg <= -0.05]
        for drop_date, _ in drops.iterrows():
            chg   = pct_chg[drop_date] * 100
            x_str = str(drop_date.date())
            fig.add_shape(
                type="line",
                x0=x_str, x1=x_str,
                y0=0, y1=1, yref="paper",
                line=dict(color=THEME["accent_red"], width=1.2, dash="dash"),
                row=1, col=1,
            )
            fig.add_annotation(
                x=x_str,
                y=eth_df.loc[drop_date, "price"],
                text=f"{chg:.1f}%",
                showarrow=False,
                font=dict(color=THEME["accent_red"], size=8),
                xanchor="center", yanchor="bottom",
                row=1, col=1,
            )

    # ── Row 2: 10년물 금리 ─────────────────────────────────
    if macro_df is not None and "tnx" in macro_df.columns:
        fig.add_trace(
            go.Scatter(
                x=macro_df.index, y=macro_df["tnx"],
                name="10년물 금리",
                line=dict(color=THEME["accent_gold"], width=1.8),
                hovertemplate="<b>TNX</b>: %{y:.2f}%<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            row=2, col=1,
        )

    # ── Row 3: BTC 도미넌스 대리 ──────────────────────────
    if dom_df is not None and not dom_df.empty:
        fig.add_trace(
            go.Scatter(
                x=dom_df.index, y=dom_df["dom_proxy"],
                name="BTC 도미넌스",
                line=dict(color=THEME["accent_blue"], width=1.8),
                fill="tozeroy",
                fillcolor="rgba(114,137,218,0.10)",
                hovertemplate="<b>BTC 도미넌스</b>: %{y:.1f}%<br>%{x|%Y-%m-%d}<extra></extra>",
            ),
            row=3, col=1,
        )

    # ── Row 4: 공포-탐욕 막대 ─────────────────────────────
    if fg_df is not None and not fg_df.empty:
        def _fg_color(v: float) -> str:
            if v <= 25:  return THEME["accent_red"]
            if v <= 45:  return "#f0a500"
            if v <= 55:  return "#f5c518"
            if v <= 75:  return "#7dbb00"
            return THEME["accent_teal"]

        fig.add_trace(
            go.Bar(
                x=fg_df.index,
                y=fg_df["value"],
                marker_color=[_fg_color(v) for v in fg_df["value"]],
                name="공포-탐욕",
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d}</b><br>"
                    "지수: %{y} (%{customdata})<extra></extra>"
                ),
                customdata=fg_df["classification"],
            ),
            row=4, col=1,
        )
        # 중립선(50) 표시
        fig.add_hline(
            y=50, row=4, col=1,
            line=dict(color=THEME["subtext"], width=1, dash="dot"),
        )

    # Y축 레이블
    fig.update_yaxes(title_text="ETH ($)",  tickprefix="$", row=1, col=1)
    fig.update_yaxes(title_text="금리 (%)", ticksuffix="%", row=2, col=1, gridcolor=THEME["grid"])
    fig.update_yaxes(title_text="BTC 도미 (%)", ticksuffix="%", row=3, col=1, gridcolor=THEME["grid"])
    fig.update_yaxes(title_text="F&G",  range=[0, 100], row=4, col=1, gridcolor=THEME["grid"])

    fig.update_layout(
        title=dict(
            text="트리거 통합 분석: ETH 가격 / 금리 / BTC 도미넌스 / 공포-탐욕 (공유 X축)",
            x=0.02,
            font=dict(color=THEME["text"], size=14),
        ),
        showlegend=False,
        paper_bgcolor=THEME["paper"],
        plot_bgcolor=THEME["bg"],
        font=dict(color=THEME["text"], family="Inter, -apple-system, sans-serif", size=11),
        margin=dict(t=75, b=40, l=60, r=30),
        height=720,
        hovermode="x unified",
    )
    # 서브플롯 row 타이틀만 흰색으로 표시
    # (yref='paper' → make_subplots 생성 annotation, 나머지는 사용자 정의 annotation)
    for ann in fig.layout.annotations:
        if getattr(ann, "yref", None) == "paper":
            ann.font.color = THEME["text"]
            ann.font.size  = 10
    return fig


# ============================================================
# 5-C. 트리거 분석용 데이터 Fetch 함수
# ============================================================

@st.cache_data(ttl=3600)
def fetch_macro_data(days: int = 90) -> pd.DataFrame | None:
    """
    yfinance: 미 국채 10년물 금리(^TNX) + 달러 인덱스(DX-Y.NYB) 일봉.

    ^TNX  : 미 국채 10년물 수익률 (%). 금리 급등 → 기관 de-risking → ETH 하락.
    DX-Y.NYB: 달러 인덱스. 달러 강세 ↑ → 위험자산 약세 ↓ (역상관).

    yfinance는 과거 최대 252 영업일(약 1년) 데이터를 제공.
    """
    try:
        period = f"{min(days, 365)}d"
        raw = yf.download(
            ["^TNX", "DX-Y.NYB"],
            period=period,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if raw.empty:
            return None
        # yfinance MultiIndex 컬럼 처리: ('Close', '^TNX') 형태
        close = raw["Close"] if "Close" in raw.columns else raw
        tnx = close["^TNX"].rename("tnx").dropna()
        dxy = close["DX-Y.NYB"].rename("dxy").dropna()
        df = pd.DataFrame({"tnx": tnx, "dxy": dxy})
        df.index = pd.to_datetime(df.index).normalize()
        track("yfinance", n=1)
        return df.dropna(how="all")
    except Exception as exc:
        st.warning(f"yfinance 매크로 데이터 오류: {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_btc_dominance_proxy(days: int = 90) -> pd.DataFrame | None:
    """
    CoinGecko: BTC + ETH 시가총액으로 BTC 도미넌스 대리 지표 계산.

    BTC 도미넌스(대리) = BTC 시가총액 / (BTC + ETH 시가총액) × 100

    실제 BTC 도미넌스는 전체 암호화폐 시가총액 대비 BTC 비중이지만,
    CoinGecko 무료 API는 전체 시가총액 시계열을 제공하지 않음.
    BTC/(BTC+ETH) 비율은 "BTC vs 대표 알트코인" 자금 흐름을 나타내는 유효한 대리 지표.

    도미넌스 상승 → 알트코인에서 BTC로 자금 이동 → ETH 약세 시그널.
    """
    days = min(days, 365)
    try:
        # BTC 시가총액: 별도 HTTP 요청 (1회)
        btc_resp = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=20,
        )
        btc_resp.raise_for_status()
        track("CoinGecko", n=1)

        # ETH 시가총액: _fetch_eth_market_chart_raw 공유 캐시 재사용 (HTTP 요청 없음)
        eth_data = _fetch_eth_market_chart_raw(days)
        if not eth_data:
            return None

        btc_mc = pd.DataFrame(btc_resp.json()["market_caps"], columns=["ts", "btc_mc"])
        eth_mc = pd.DataFrame(eth_data["market_caps"],        columns=["ts", "eth_mc"])
        btc_mc["date"] = pd.to_datetime(btc_mc["ts"], unit="ms").dt.normalize()
        eth_mc["date"] = pd.to_datetime(eth_mc["ts"], unit="ms").dt.normalize()

        df = btc_mc[["date", "btc_mc"]].merge(eth_mc[["date", "eth_mc"]], on="date")
        df["dom_proxy"] = df["btc_mc"] / (df["btc_mc"] + df["eth_mc"]) * 100
        return df.drop_duplicates("date").set_index("date")[["dom_proxy"]]
    except Exception as exc:
        st.warning(f"BTC 도미넌스 데이터 오류: {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_fear_greed(days: int = 90) -> pd.DataFrame | None:
    """
    Alternative.me: 암호화폐 공포-탐욕 지수 (Fear & Greed Index).

    0–25  : Extreme Fear  (극도 공포) → 시장 패닉, 과매도 가능성
    26–45 : Fear          (공포)
    46–55 : Neutral       (중립)
    56–75 : Greed         (탐욕)
    76–100: Extreme Greed (극도 탐욕) → 과열, 고점 경고

    Trigger 해석:
      지표가 평온(중립)한데 가격만 급락 → 고래 차익실현 가능성.
      지표와 가격이 동시에 극도 공포로 → 외부 악재(규제/해킹) 트리거.
    무료 API, 하루 1회 업데이트.
    """
    try:
        resp = requests.get(
            f"https://api.alternative.me/fng/?limit={min(days, 365)}",
            timeout=15,
        )
        resp.raise_for_status()
        entries = resp.json().get("data", [])
        if not entries:
            return None
        df = pd.DataFrame(entries)
        df["date"]  = pd.to_datetime(df["timestamp"].astype(int), unit="s").dt.normalize()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["classification"] = df["value_classification"]
        track("AlternativeMe", n=1)
        return (
            df[["date", "value", "classification"]]
            .drop_duplicates("date")
            .sort_values("date")
            .set_index("date")
        )
    except Exception as exc:
        st.warning(f"공포-탐욕 지수 오류: {exc}")
        return None


# ============================================================
# 6. API 사용량 추적 + 사이드바 렌더링
# ============================================================

# ── API별 공식 한도 정보 ──────────────────────────────────
# 출처: 각 API 공식 문서 (2025년 기준)
API_LIMITS: dict[str, dict] = {
    "CoinGecko": {
        "label":       "CoinGecko",
        "day_limit":   None,       # 월 정액제, 일 한도 없음
        "min_limit":   30,         # 분당 ~30회 (무료 데모 키 없이)
        "session_warn": 20,        # 세션 내 이 횟수 초과 시 경고
        "color":       "#f0a500",
        "note":        "분당 ~30회 제한. 빠른 새로고침 자제 권장.",
        "paid_url":    "https://www.coingecko.com/en/api/pricing",
    },
    "DefiLlama": {
        "label":       "DefiLlama",
        "day_limit":   None,       # 공식 무제한 (공정 사용 정책)
        "min_limit":   None,
        "session_warn": 200,       # 과도한 사용 감지용
        "color":       "#00d4aa",
        "note":        "공식 무제한 (공정 사용 정책). 실질 제한 없음.",
        "paid_url":    None,
    },
    "CoinMetrics": {
        "label":       "CoinMetrics Community",
        "day_limit":   1_000,      # 일 1,000회 하드 리밋 (공식 문서)
        "min_limit":   10,         # 초당 10회
        "session_warn": 50,        # 세션 내 이 횟수 초과 시 경고
        "color":       "#e74c3c",
        "note":        "⚠️ 일 1,000회 하드 한도. 초과 시 429 에러 발생.",
        "paid_url":    "https://coinmetrics.io/api/",
    },
    "Etherscan": {
        "label":       "Etherscan (키 없음)",
        "day_limit":   None,
        "min_limit":   2,          # API 키 없이 분당 ~1-2회 실질 제한
        "session_warn": 5,
        "color":       "#7289da",
        "note":        "API 키 없이 분당 ~1-2회. 소각 데이터 추정치로 대체됨.",
        "paid_url":    "https://etherscan.io/apis",
    },
    # Messari API는 2024년에 완전히 종료됨 → 제거
    "yfinance": {
        "label":       "yfinance (Yahoo Finance)",
        "day_limit":   None,       # 공식 무제한 (공정 사용 정책)
        "min_limit":   None,
        "session_warn": 100,
        "color":       "#6c3483",
        "note":        "주가/금리/DXY 일봉. 과도한 연속 호출 자제 권장.",
        "paid_url":    None,
    },
    "AlternativeMe": {
        "label":       "Alternative.me (Fear & Greed)",
        "day_limit":   None,       # 무제한
        "min_limit":   None,
        "session_warn": 5,         # 하루 1회 업데이트이므로 5회면 충분
        "color":       "#e67e22",
        "note":        "공포-탐욕 지수. 하루 1회 업데이트, 365일 무료 제공.",
        "paid_url":    None,
    },
}


def _init_api_counters() -> None:
    """세션 시작 시 API 호출 카운터를 초기화."""
    if "api_counters" not in st.session_state:
        st.session_state.api_counters = {k: 0 for k in API_LIMITS}
    if "api_session_start" not in st.session_state:
        st.session_state.api_session_start = datetime.now()


def track(api_name: str, n: int = 1) -> None:
    """
    API 호출 카운터 증가.
    @st.cache_data 캐시가 살아있으면 실제 HTTP 요청은 발생하지 않지만,
    함수 호출 자체는 항상 발생하므로 세션 내 최대 호출 횟수의 상한으로 활용.
    """
    if "api_counters" not in st.session_state:
        _init_api_counters()
    st.session_state.api_counters[api_name] = (
        st.session_state.api_counters.get(api_name, 0) + n
    )


def api_warning_banner(api_name: str) -> None:
    """
    API 한도에 근접했을 때 인라인 경고 배너를 표시.
    캐시가 유효하면 실제 API 호출이 없으므로 경고는 보수적 상한 기준.
    """
    info  = API_LIMITS.get(api_name, {})
    count = st.session_state.get("api_counters", {}).get(api_name, 0)
    warn  = info.get("session_warn", 9999)
    dlim  = info.get("day_limit")

    if dlim and count >= int(dlim * 0.85):
        pct = count / dlim * 100
        st.error(
            f"🚨 **{info['label']} 일 한도 위험** — "
            f"세션 호출 {count}회 / 일 한도 {dlim}회 ({pct:.0f}%). "
            f"캐시 만료 전 새로고침을 자제하세요. "
            + (f"[유료 플랜]({info['paid_url']})" if info.get("paid_url") else "")
        )
    elif dlim and count >= int(dlim * 0.5):
        pct = count / dlim * 100
        st.warning(
            f"⚠️ **{info['label']} 주의** — "
            f"세션 호출 {count}회 / 일 한도 {dlim}회 ({pct:.0f}%). "
            f"한도 초과 시 데이터 로딩이 실패합니다."
        )
    elif count >= warn:
        st.info(
            f"ℹ️ **{info['label']}** — "
            f"이번 세션에서 {count}회 호출했습니다. {info.get('note', '')}"
        )


def render_sidebar() -> dict:
    """
    사이드바에 분석 파라미터 설정 UI를 렌더링하고 설정값 딕셔너리를 반환.
    사용자가 조정 계수를 실시간으로 변경하면 적정 가치 차트가 즉시 업데이트된다.
    """
    st.sidebar.title("⚙️ 분석 설정")
    st.sidebar.markdown("---")

    st.sidebar.subheader("📐 적정 가치 조정 계수")
    st.sidebar.markdown(
        "<div class='info-box'>"
        "조정 계수는 순수 TVL 모델에 시장 프리미엄/할인을 적용합니다.<br>"
        "1.0 = 순수 TVL 대비 가치, 2.0 = 성장성 프리미엄 50% 반영"
        "</div>",
        unsafe_allow_html=True,
    )
    conservative = st.sidebar.slider("보수적 계수", 0.2, 1.0, 0.5, 0.05)
    base_case    = st.sidebar.slider("기본 계수",   0.5, 2.0, 1.0, 0.05)
    optimistic   = st.sidebar.slider("낙관적 계수", 1.0, 5.0, 2.0, 0.25)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 데이터 설정")
    history_days = st.sidebar.selectbox(
        "분석 기간 (일)",
        [30, 60, 90, 180, 270, 365],
        index=3,
        help="최대 365일 — CoinGecko 무료 티어 한도. DefiLlama/yfinance는 365일 이상 지원하나 CoinGecko가 병목.",
    )
    auto_refresh = st.sidebar.checkbox("자동 새로고침 (5분)", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
**데이터 출처**
- [CoinGecko API](https://www.coingecko.com/api/documentation)
- [DefiLlama API](https://defillama.com/docs/api)
- [DefiLlama Yields](https://yields.llama.fi)
- [CoinMetrics Community](https://coinmetrics.io/api/)

**분석 방법론**
- 피어슨 상관계수 (가격-TVL 선형 관계)
- TVL 기반 적정 가치 모델 (P/B 응용)
- EIP-1559 소각 디플레이션 추적
- RWA 기관 채택 모니터링

---
> ⚠️ 본 대시보드는 **교육·연구 목적** 전용입니다.
> 투자 조언이 아닙니다.
        """
    )

    # ── API 사용량 모니터 ─────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("📡 API 사용량 모니터")
    st.sidebar.caption(
        "캐시가 유효하면 실제 HTTP 요청은 발생하지 않습니다.\n"
        "표시 수치는 세션 내 함수 호출 횟수(상한)입니다."
    )

    counters = st.session_state.get("api_counters", {})
    session_start = st.session_state.get("api_session_start", datetime.now())
    elapsed_min = max(1, int((datetime.now() - session_start).total_seconds() / 60))

    for api_key, info in API_LIMITS.items():
        count    = counters.get(api_key, 0)
        day_lim  = info["day_limit"]
        min_lim  = info["min_limit"]

        # 진행 바 색상 결정
        if day_lim:
            pct = count / day_lim
            if   pct >= 0.85: bar_color = "🔴"
            elif pct >= 0.50: bar_color = "🟡"
            else:             bar_color = "🟢"
            limit_str = f"{count} / {day_lim:,}회 (일 한도)"
            remain    = max(0, day_lim - count)
            remain_str = f"잔여 약 **{remain:,}회**"
        else:
            bar_color  = "🟢"
            limit_str  = f"{count}회 (세션)"
            remain_str = "한도 없음"

        rate_str = f"분당 최대 {min_lim}회" if min_lim else "속도 제한 없음"

        st.sidebar.markdown(
            f"**{bar_color} {info['label']}**  \n"
            f"호출: {limit_str}  \n"
            f"{remain_str} &nbsp;|&nbsp; {rate_str}",
        )
        if day_lim and count > 0:
            # 심플 프로그레스 바 (0~1 범위)
            st.sidebar.progress(min(1.0, count / day_lim))

    st.sidebar.caption(f"세션 시작: {session_start.strftime('%H:%M:%S')} ({elapsed_min}분 경과)")

    return {
        "conservative": conservative,
        "base_case":    base_case,
        "optimistic":   optimistic,
        "history_days": history_days,
        "auto_refresh": auto_refresh,
    }


# ============================================================
# 7. 메인 대시보드 진입점
# ============================================================

def main() -> None:
    # ── 세션 초기화 ───────────────────────────────────────
    _init_api_counters()

    # ── 페이지 헤더 ───────────────────────────────────────
    st.markdown(
        """
<div style='text-align:center; padding: 20px 0 10px 0;'>
    <h1 style='color:#00d4aa; font-size:2.1rem; margin:0; letter-spacing:-0.5px;'>
        ⟠ 이더리움 내재 가치 분석 대시보드
    </h1>
    <p style='color:#a0aab4; font-size:0.95rem; margin:8px 0 0 0;'>
        공급(소각) · 확장성(L2) · 수익률(스테이킹)의 유기적 결합으로 ETH 가치를 다각 평가
    </p>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── 사이드바 설정 로드 ────────────────────────────────
    settings = render_sidebar()

    # ── 업데이트 시각 + 새로고침 버튼 ───────────────────
    col_t, col_r = st.columns([5, 1])
    with col_t:
        st.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col_r:
        if st.button("🔄 새로고침"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ── 데이터 수집 (병렬적으로 모두 요청) ───────────────
    track("CoinGecko",  n=1)   # fetch_eth_current
    track("DefiLlama",  n=3)   # chains + staking(yields) + protocols
    track("Etherscan",  n=1)   # burn estimate
    with st.spinner("실시간 데이터 수집 중 ..."):
        eth        = fetch_eth_current()
        chains     = fetch_defillama_chains()
        staking    = fetch_staking_apy()
        burn       = fetch_burn_estimate()
        protocols  = fetch_defillama_protocols()
    api_warning_banner("CoinGecko")
    api_warning_banner("Etherscan")

    # ── 파생 지표 계산 ────────────────────────────────────
    l1_tvl      = extract_l1_tvl(chains)
    l2_tvl      = extract_l2_tvl(chains)
    l2_tvl_total = sum(l2_tvl.values())

    # 스테이킹 APY: Lido 우선, 없으면 첫 번째 항목
    staking_apy = 0.0
    if staking:
        lido = [p for p in staking if p.get("project") == "lido"]
        staking_apy = (lido or staking)[0].get("apy", 0.0)

    burn_24h     = burn.get("burn_24h_eth", 0.0)
    burn_source  = burn.get("source", "estimate")

    # ──────────────────────────────────────────────────────
    # 섹션 1: 실시간 핵심 메트릭 카드
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>📊 실시간 핵심 메트릭</h3></div>",
        unsafe_allow_html=True,
    )

    if eth:
        price              = eth["price"]
        market_cap         = eth["market_cap"]
        circulating_supply = eth["circulating_supply"]
        change_24h         = eth["change_24h"]
        change_7d          = eth["change_7d"]
        volume_24h         = eth["volume_24h"]
    else:
        st.error("ETH 가격 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        price              = 0.0
        market_cap         = 0.0
        circulating_supply = 120_000_000.0
        change_24h         = change_7d = volume_24h = 0.0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("ETH 가격",     f"${price:,.2f}",         f"{change_24h:+.2f}% 24h")
    with c2:
        st.metric("시가총액",     f"${market_cap/1e9:.1f}B", f"{change_7d:+.2f}% 7d")
    with c3:
        st.metric("24h 거래량",   f"${volume_24h/1e9:.2f}B")
    with c4:
        burn_label = "24h 소각량 (추정)" if "estimate" in burn_source else "24h 소각량"
        st.metric(burn_label,     f"{burn_24h:,.0f} ETH",   f"≈ ${burn_24h * price:,.0f}")
    with c5:
        st.metric("스테이킹 APY", f"{staking_apy:.2f}%",    "Lido 기준 연 수익률")
    with c6:
        st.metric("L2 TVL 합계",  f"${l2_tvl_total/1e9:.2f}B", f"{len(l2_tvl)}개 L2")

    # ──────────────────────────────────────────────────────
    # 섹션 2: 상관관계 분석 (ETH 가격 vs L1 TVL)
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>📈 상관관계 분석: ETH 가격 vs 이더리움 L1 TVL</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: 피어슨 상관계수(r)로 ETH 가격과 L1 TVL 사이의 선형 관계 강도를 정량화합니다. "
        "높은 양의 r(> 0.7)은 TVL이 ETH 가격의 신뢰할 수 있는 선행 지표임을 시사합니다. "
        "두 변수의 동조화는 '이더리움 = 담보 자산' 가설을 지지합니다."
        "</div>",
        unsafe_allow_html=True,
    )

    track("CoinGecko", n=1)   # fetch_eth_history
    track("DefiLlama", n=1)   # fetch_defillama_tvl_history
    with st.spinner("시계열 데이터 로딩 중 ..."):
        price_hist = fetch_eth_history(settings["history_days"])
        tvl_hist   = fetch_defillama_tvl_history("Ethereum")

    if price_hist is not None and tvl_hist is not None:
        corr_fig, corr_val = chart_price_vs_tvl(price_hist, tvl_hist)
        st.plotly_chart(corr_fig, use_container_width=True)

        if corr_val is not None:
            abs_r = abs(corr_val)
            if   abs_r >= 0.8: strength, color = "매우 강한",  THEME["accent_teal"]
            elif abs_r >= 0.6: strength, color = "강한",        THEME["accent_blue"]
            elif abs_r >= 0.4: strength, color = "중간",        THEME["accent_gold"]
            else:              strength, color = "약한",         THEME["accent_red"]
            direction = "양의" if corr_val > 0 else "음의"
            st.markdown(
                f"<div class='info-box'>"
                f"📊 r = <span style='color:{color}; font-weight:bold'>{corr_val:.4f}</span> "
                f"— ETH 가격과 L1 TVL 간 <b>{direction} {strength} 상관관계</b>. "
                f"두 지표는 공통 분산의 <b>{abs_r**2*100:.1f}%</b>를 공유합니다 (결정계수 R²)."
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.warning("시계열 데이터를 불러올 수 없습니다.")

    # ──────────────────────────────────────────────────────
    # 섹션 3: L2 생태계 TVL 분포
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>🔗 이더리움 L2 생태계 TVL</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: L2는 이더리움 L1의 보안을 임대하여 확장성을 제공합니다. "
        "L2 TVL 합계는 이더리움이 간접적으로 담보하는 가치이므로, "
        "적정 가치 공식의 분자에 포함됩니다. L2 생태계의 성장은 ETH 수요 증가를 유도합니다."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── L1 + L2 TVL 시계열 차트 ─────────────────────────────
    # 현재 TVL 기준 상위 5개 L2만 시계열 조회 (API 호출 최소화)
    top_l2_names = [
        name for name, _ in sorted(l2_tvl.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    # L2_TARGETS의 display명 → DefiLlama URL에 쓰는 체인명 역매핑
    l2_api_name_map = {v.title(): k for k, v in L2_TARGETS.items()}
    # DefiLlama API는 체인명을 Title Case로 받음 (예: "Arbitrum", "Optimism")
    top_l2_api = []
    for display in top_l2_names:
        for key, search in L2_TARGETS.items():
            if key == display:
                # DefiLlama 체인 이름은 Title Case 사용
                top_l2_api.append((display, search.title()))
                break

    # L2 체인 수만큼 + L1 + Solana 카운트
    track("DefiLlama", n=len(top_l2_api) + 2)
    with st.spinner("L1 · L2 · Solana 시계열 데이터 로딩 중 ..."):
        l2_histories_raw = fetch_l2_tvl_histories(
            [api_name for _, api_name in top_l2_api],
            days=settings["history_days"],
        )
        l1_hist_for_stack = fetch_defillama_tvl_history("Ethereum")
        solana_hist       = fetch_defillama_tvl_history("Solana")

    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=settings["history_days"])

    # API 이름 → 표시 이름으로 재매핑
    api_to_display = {api: disp for disp, api in top_l2_api}
    l2_histories = {
        api_to_display.get(api_name, api_name): df
        for api_name, df in l2_histories_raw.items()
    }

    if l2_histories or l1_hist_for_stack is not None:
        # 분석 기간으로 L1 데이터 자르기
        l1_sliced = l1_hist_for_stack[l1_hist_for_stack.index >= cutoff] if l1_hist_for_stack is not None else None
        st.plotly_chart(
            chart_l1_l2_tvl_history(l1_sliced, l2_histories),
            use_container_width=True,
        )
    else:
        st.warning("TVL 시계열 데이터를 불러올 수 없습니다.")

    # ── ETH vs Solana 비교 차트 ──────────────────────────
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>ETH vs Solana TVL 비교 분석</b>: "
        "TVL은 '예치 코인 수'가 아닌 <b>달러 환산 가치</b>이므로, 가격 하락만으로도 TVL이 감소합니다. "
        "ETH와 SOL이 동반 하락 → 가격 효과(자금 이탈 아님). "
        "SOL만 상승 → 이더리움에서 솔라나로의 자금 이동 신호. "
        "이중 Y축: 좌=ETH(L1+L2), 우=SOL (절대 규모 차이를 조정)"
        "</div>",
        unsafe_allow_html=True,
    )
    l1_sliced_sol = l1_hist_for_stack[l1_hist_for_stack.index >= cutoff] if l1_hist_for_stack is not None else None
    sol_sliced    = solana_hist[solana_hist.index >= cutoff] if solana_hist is not None else None
    st.plotly_chart(
        chart_eth_vs_solana(l1_sliced_sol, l2_histories, sol_sliced),
        use_container_width=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 현재 스냅샷 막대 차트 + 상세 테이블 ─────────────
    col_chart, col_stats = st.columns([3, 1])
    with col_chart:
        if l2_tvl:
            st.plotly_chart(chart_l2_tvl_bar(l2_tvl), use_container_width=True)
        else:
            st.warning("L2 TVL 데이터를 불러올 수 없습니다.")

    with col_stats:
        st.markdown("**L2 TVL 상세**")
        c_grid = THEME["grid"]
        c_sub  = THEME["subtext"]
        c_teal = THEME["accent_teal"]
        c_blue = THEME["accent_blue"]
        for name, tvl in sorted(l2_tvl.items(), key=lambda x: x[1], reverse=True):
            pct = tvl / l2_tvl_total * 100 if l2_tvl_total > 0 else 0
            st.markdown(
                f"<div style='margin:5px 0; font-size:0.84rem; border-bottom:1px solid {c_grid}; padding-bottom:4px;'>"
                f"<span style='color:{c_sub}'>{name}</span><br>"
                f"<span style='color:{c_teal}'>${tvl/1e9:.2f}B</span> "
                f"<span style='color:{c_blue}'>({pct:.1f}%)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("---")
        st.markdown(
            f"<div style='font-size:0.88rem; color:{THEME['text']};'>"
            f"L1 TVL: <b>${l1_tvl/1e9:.2f}B</b><br>"
            f"L2 합계: <b>${l2_tvl_total/1e9:.2f}B</b><br>"
            f"L1+L2 합계: <b>${(l1_tvl+l2_tvl_total)/1e9:.2f}B</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ──────────────────────────────────────────────────────
    # 섹션 4: 활동량 분석 — 가격 효과를 제거한 실제 네트워크 사용 지표
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>⚡ 활동량 분석: 가격 효과를 제거한 실제 네트워크 사용 지표</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: TVL은 '달러 환산 가치'이므로 ETH/SOL 가격 하락만으로도 수치가 감소합니다. "
        "아래 지표들은 <b>자산 가격에 비의존적인 순수 사용자 행동</b>을 측정합니다. "
        "TVL이 하락해도 이 지표들이 유지·상승하면 → 네트워크 이탈이 아닌 <b>가격 하락에 의한 평가 절하</b>임을 증명합니다. "
        "데이터 출처: ETH 활성주소 → CoinMetrics Community, "
        "SOL 비교 → DefiLlama 네트워크 수수료 (Solana 활성주소는 무료 API 미지원)"
        "</div>",
        unsafe_allow_html=True,
    )

    track("CoinMetrics", n=1)    # eth only (sol은 403이므로 카운트 감소)
    track("DefiLlama",   n=2)    # eth fees + sol fees
    api_warning_banner("CoinMetrics")
    with st.spinner("온체인 활동 데이터 로딩 중 ..."):
        eth_activity  = fetch_onchain_activity("eth", days=settings["history_days"])
        eth_fees      = fetch_fees_history("Ethereum", days=settings["history_days"])
        sol_fees      = fetch_fees_history("Solana",   days=settings["history_days"])

    # ── 4-A: ETH 활성 주소 (좌) + ETH vs SOL 네트워크 수수료 (우) ─
    act_col1, act_col2 = st.columns(2)
    with act_col1:
        st.plotly_chart(chart_active_addresses(eth_activity, None), use_container_width=True)
        st.caption("ℹ️ Solana 활성 주소: CoinMetrics 유료 전용. 오른쪽 수수료 차트로 대체 비교.")
    with act_col2:
        st.plotly_chart(chart_network_fees(eth_fees, sol_fees), use_container_width=True)

    # ── 4-B: ETH 총 공급량 & 순발행량 (좌) + 스테이블코인 온체인 잔액 (우) ─
    supply_col, stbl_col = st.columns(2)

    with supply_col:
        st.markdown(
            "<div class='info-box'>"
            "💡 <b>ETH 공급량 해석</b>: "
            "<b>총 공급량 = 스테이킹 보상(발행) − EIP-1559 소각</b>. "
            "머지(2022.09) 이후 일일 발행량이 ~13,000→~1,700 ETH로 급감. "
            "네트워크 혼잡일에는 소각이 발행을 초과해 <b>디플레이션</b>이 발생합니다."
            "</div>",
            unsafe_allow_html=True,
        )
        with st.spinner("ETH 공급량 데이터 로딩 중 ..."):
            eth_supply_df = fetch_eth_supply_history(days=min(settings["history_days"], 365))
        st.plotly_chart(chart_eth_supply_burn(eth_supply_df), use_container_width=True)

    with stbl_col:
        st.markdown(
            "<div class='info-box'>"
            "💡 <b>스테이블코인 잔액 해석</b>: "
            "가격 하락 시 잔액이 유지·증가 → ETH/SOL을 USDC/USDT로 전환한 '관망 자본'이 체인 안에 머무는 중. "
            "= 자금 이탈이 아닌 <b>리스크 회피 포지션</b>. 시장 반전 시 즉각 재진입 가능."
            "</div>",
            unsafe_allow_html=True,
        )
        track("DefiLlama", n=2)   # eth + sol stablecoins
        with st.spinner("스테이블코인 데이터 로딩 중 ..."):
            eth_stbl = fetch_stablecoin_history("Ethereum", days=settings["history_days"])
            sol_stbl = fetch_stablecoin_history("Solana",   days=settings["history_days"])
        st.plotly_chart(chart_stablecoin_activity(eth_stbl, sol_stbl), use_container_width=True)

    # ── 4-C: 가격 vs 활성 주소 디커플링 ─────────────────
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>디커플링 분석</b>: 세 지표를 동일 기준점(=100)으로 정규화. "
        "가격선이 하락해도 활성 주소선이 100 근처를 유지하면 → "
        "<b>'가격 하락 = 사용자 이탈'이라는 오해를 수치로 반박</b>하는 강력한 증거."
        "</div>",
        unsafe_allow_html=True,
    )
    # 캐시 TTL 내라면 실제 API 호출 없음 (counter는 상한값)
    track("CoinGecko", n=1)
    price_hist_for_decoupling = fetch_eth_history(settings["history_days"])
    st.plotly_chart(
        chart_price_activity_decoupling(price_hist_for_decoupling, eth_activity, None),
        use_container_width=True,
    )

    # ── 4-D: DEX 자본 효율성 비율 ────────────────────────
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>자본 효율성 = DEX 거래량 / TVL</b>: "
        "같은 TVL 대비 하루 거래량이 많을수록 자본이 활발히 순환하는 체인. "
        "솔라나(거래 특화): 높은 비율 | 이더리움(저장 특화): 낮은 비율. "
        "→ 두 체인은 경쟁 관계가 아니라 <b>서로 다른 시장을 공략</b>하고 있음."
        "</div>",
        unsafe_allow_html=True,
    )
    track("DefiLlama", n=4)   # eth_vol + sol_vol + eth_tvl + sol_tvl
    with st.spinner("DEX 거래량 데이터 로딩 중 ..."):
        eth_vol = fetch_dex_volume_history("Ethereum", days=settings["history_days"])
        sol_vol = fetch_dex_volume_history("Solana",   days=settings["history_days"])
        eth_tvl_for_ratio = fetch_defillama_tvl_history("Ethereum")
        sol_tvl_for_ratio = fetch_defillama_tvl_history("Solana")

    if eth_tvl_for_ratio is not None:
        cutoff_r = pd.Timestamp.now().normalize() - pd.Timedelta(days=settings["history_days"])
        eth_tvl_for_ratio = eth_tvl_for_ratio[eth_tvl_for_ratio.index >= cutoff_r]
    if sol_tvl_for_ratio is not None:
        cutoff_r = pd.Timestamp.now().normalize() - pd.Timedelta(days=settings["history_days"])
        sol_tvl_for_ratio = sol_tvl_for_ratio[sol_tvl_for_ratio.index >= cutoff_r]

    st.plotly_chart(
        chart_dex_capital_efficiency(eth_vol, eth_tvl_for_ratio, sol_vol, sol_tvl_for_ratio),
        use_container_width=True,
    )

    # ──────────────────────────────────────────────────────
    # 섹션 5: 가격 트리거 분석 (거시 경제 & 시장 심리)
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>📡 가격 트리거 분석: 거시 경제 & 시장 심리</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: 가격 변동이 <b>어디서 시작됐는지</b>를 데이터로 추적합니다. "
        "금리 급등·달러 강세(외부 충격) vs BTC 도미넌스 상승(내부 로테이션) vs "
        "공포-탐욕 패닉(심리 트리거)을 구분하면 하락의 성격을 판단할 수 있습니다.<br>"
        "⚠️ <b>청산 데이터</b>(연쇄 청산 맵)와 <b>거래소 입출금</b>(고래 추적)은 "
        "Coinglass · CryptoQuant · Glassnode 등 <b>유료 API 전용</b> 기능입니다."
        "</div>",
        unsafe_allow_html=True,
    )

    track("yfinance",     n=1)
    track("CoinGecko",    n=2)
    track("AlternativeMe", n=1)
    with st.spinner("거시 경제 & 시장 심리 데이터 로딩 중 ..."):
        macro_df  = fetch_macro_data(days=settings["history_days"])
        dom_df    = fetch_btc_dominance_proxy(days=settings["history_days"])
        fg_df     = fetch_fear_greed(days=settings["history_days"])
        # ETH 가격은 이미 fetch_eth_history로 캐시됨 (캐시 히트)
        eth_price_df = fetch_eth_history(settings["history_days"])

    # ── 5-A: 통합 4-패널 스택 차트 (전체 폭) ─────────────
    st.plotly_chart(
        chart_trigger_combined(eth_price_df, macro_df, dom_df, fg_df),
        use_container_width=True,
    )

    # ── 5-B: 공포-탐욕 게이지 (좌) + 사용법 안내 (우) ────
    gauge_col, guide_col = st.columns([1, 2])
    with gauge_col:
        st.plotly_chart(
            chart_fear_greed_gauge(fg_df),
            use_container_width=True,
        )
    with guide_col:
        st.markdown(
            "<div class='info-box' style='margin-top:8px'>"
            "<b>통합 차트 읽는 법</b><br>"
            "① 붉은 세로선 위치에서 <b>2번째 패널(금리)</b>이 동시에 튀었다면 "
            "→ <b>기관 de-risking</b>이 트리거.<br>"
            "② 붉은 세로선 위치에서 <b>3번째 패널(BTC 도미넌스)</b>가 상승했다면 "
            "→ 알트코인→BTC <b>자금 로테이션</b>이 트리거.<br>"
            "③ 붉은 세로선 위치에서 <b>4번째 패널(공포-탐욕)</b>이 먼저 꺾였다면 "
            "→ <b>시장 심리 패닉</b>이 트리거.<br>"
            "④ 세 패널 모두 평온한데 가격만 하락 → "
            "<b>고래 차익실현</b>(내부 요인) 가능성."
            "</div>",
            unsafe_allow_html=True,
        )

    # ── 5-C: 개별 상세 차트 (expander) ────────────────────
    with st.expander("개별 지표 상세 차트 보기", expanded=False):
        det_col1, det_col2 = st.columns(2)
        with det_col1:
            st.plotly_chart(
                chart_eth_treasury_yield(eth_price_df, macro_df),
                use_container_width=True,
            )
            st.plotly_chart(
                chart_btc_dominance(dom_df, eth_price_df),
                use_container_width=True,
            )
        with det_col2:
            st.plotly_chart(
                chart_dxy_vs_eth(eth_price_df, macro_df),
                use_container_width=True,
            )
            st.plotly_chart(
                chart_fear_greed(fg_df),
                use_container_width=True,
            )

    # ──────────────────────────────────────────────────────
    # 섹션 6: 적정 가치 계산기 (구 섹션 5)
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>💎 이더리움 적정 가치 계산기</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: 주식의 P/B(주가순자산비율)에서 착안한 TVL 기반 적정가치 모델. "
        "<b>공식: (L1 TVL + L2 TVL 합계) ÷ ETH 유통량 × 조정 계수</b><br>"
        "🟢 초록색 막대 = 적정가 > 현재가 (저평가 신호) &nbsp;|&nbsp; "
        "🔴 빨간색 막대 = 적정가 < 현재가 (고평가 신호). 조정 계수는 사이드바에서 변경 가능."
        "</div>",
        unsafe_allow_html=True,
    )

    if price > 0 and circulating_supply > 0:
        factors = {
            f"보수적 (×{settings['conservative']:.2f})": settings["conservative"],
            f"기본 (×{settings['base_case']:.2f})":      settings["base_case"],
            f"낙관적 (×{settings['optimistic']:.2f})":   settings["optimistic"],
        }
        st.plotly_chart(
            chart_intrinsic_value(price, l1_tvl, l2_tvl_total, circulating_supply, factors),
            use_container_width=True,
        )

        iv_cols = st.columns(len(factors))
        for col, (label, factor) in zip(iv_cols, factors.items()):
            iv    = calc_intrinsic_value(l1_tvl, l2_tvl_total, circulating_supply, factor)
            delta = iv - price
            col.metric(label, f"${iv:,.0f}", f"{delta:+,.0f} vs 현재가")

    # ──────────────────────────────────────────────────────
    # 섹션 5: RWA 점유율 추적
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>🏦 RWA (실물자산) 이더리움 점유율 추적</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: RWA는 국채·부동산·사모신용 등 전통 금융 자산의 온체인 토큰화. "
        "BlackRock·Franklin Templeton 등 기관의 이더리움 RWA 토큰 발행은 "
        "구조적이고 지속적인 ETH 수요 기반을 형성하는 장기 가치 드라이버입니다. "
        "RWA TVL 점유율 상승 추세가 지속될 경우, ETH 기관 채택이 가속화되고 있다는 신호."
        "</div>",
        unsafe_allow_html=True,
    )

    # 골드 제외 토글
    GOLD_KEYWORDS = {"gold", "paxg", "xaut"}
    exclude_gold = st.checkbox(
        "🥇 토큰화 골드 제외 (Paxos Gold · Tether Gold)",
        value=False,
        help="PAXG·XAUT 같은 금 담보 토큰은 금 시세에 연동돼 기관 채택 지표로는 부적합합니다. "
             "체크하면 금융 RWA(국채·MMF·사모신용)만 표시합니다.",
    )

    def _is_gold(name: str) -> bool:
        n = name.lower()
        return any(kw in n for kw in GOLD_KEYWORDS)

    rwa_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    rwa_full_all = extract_rwa_protocols_full(protocols)
    rwa_full     = [p for p in rwa_full_all if not (exclude_gold and _is_gold(p["name"]))]
    rwa_raw      = {p["name"]: p["tvl"] for p in rwa_full}

    rwa_fig, total_rwa, rwa_pct, rwa_estimated = chart_rwa_pie(
        rwa_raw, l1_tvl, data_date=rwa_fetch_time
    )
    if rwa_estimated:
        st.warning("⚠️ RWA 데이터를 API에서 수신하지 못했습니다. 2025년 공개 데이터 기반 추정치를 표시합니다.")
    st.caption(f"데이터 기준: {rwa_fetch_time} (DefiLlama 실시간 스냅샷)")
    st.plotly_chart(rwa_fig, use_container_width=True)

    rwa_c1, rwa_c2, rwa_c3 = st.columns(3)
    rwa_c1.metric("이더리움 RWA 총 TVL",  f"${total_rwa/1e9:.2f}B")
    rwa_c2.metric("L1 TVL 대비 RWA 비중", f"{rwa_pct:.2f}%")
    rwa_c3.metric("추적 RWA 프로토콜 수", f"{len(rwa_raw) or 6}개")

    # RWA 시계열 차트 (프로토콜별 히스토리 수집)
    if rwa_full:
        with st.spinner("RWA 프로토콜 히스토리 로딩 중 ..."):
            rwa_series:       dict[str, pd.Series] = {}
            rwa_series_total: dict[str, pd.Series] = {}
            # 체인별 TVL 집계: {chain_name: [pd.Series, ...]}
            chains_raw: dict[str, list[pd.Series]] = {}
            for p in rwa_full:
                s_eth    = fetch_rwa_protocol_history(p["slug"],   days=settings["history_days"])
                s_total  = fetch_rwa_protocol_total_tvl(p["slug"], days=settings["history_days"])
                s_chains = fetch_rwa_protocol_chains(p["slug"],    days=settings["history_days"])
                if s_eth is not None and not s_eth.empty:
                    rwa_series[p["name"]] = s_eth
                if s_total is not None and not s_total.empty:
                    rwa_series_total[p["name"]] = s_total
                for chain, s in s_chains.items():
                    chains_raw.setdefault(chain, []).append(s)

        if rwa_series:
            rwa_hist_df = pd.concat(rwa_series, axis=1).sort_index()
            rwa_hist_df.columns = list(rwa_series.keys())
            rwa_hist_df = rwa_hist_df.fillna(0)

            rwa_total_df = pd.DataFrame()
            if rwa_series_total:
                rwa_total_df = pd.concat(rwa_series_total, axis=1).sort_index()
                rwa_total_df.columns = list(rwa_series_total.keys())
                rwa_total_df = rwa_total_df.fillna(0)

            # 체인별 합산 시리즈 빌드
            chains_agg: dict[str, pd.Series] = {
                chain: pd.concat(series_list, axis=1).sum(axis=1)
                for chain, series_list in chains_raw.items()
            }

            # L1 TVL 히스토리 (캐시돼 있으면 추가 HTTP 없음)
            l1_tvl_hist = fetch_defillama_tvl_history("Ethereum")
            if l1_tvl_hist is not None:
                cutoff_rwa = pd.Timestamp.now().normalize() - pd.Timedelta(days=settings["history_days"])
                l1_tvl_hist = l1_tvl_hist[l1_tvl_hist.index >= cutoff_rwa]

            rwa_ts_c1, rwa_ts_c2 = st.columns(2)
            with rwa_ts_c1:
                st.plotly_chart(
                    chart_rwa_composition_history(rwa_hist_df),
                    use_container_width=True,
                )
            with rwa_ts_c2:
                st.plotly_chart(
                    chart_rwa_share_trend(rwa_hist_df, l1_tvl_hist),
                    use_container_width=True,
                )

            # 자금 흐름 (ETH vs 전체) + 체인별 분포 — 2열
            if not rwa_total_df.empty:
                flow_c1, flow_c2 = st.columns(2)
                with flow_c1:
                    st.plotly_chart(
                        chart_rwa_chain_flow(rwa_hist_df, rwa_total_df),
                        use_container_width=True,
                    )
                with flow_c2:
                    if chains_agg:
                        st.plotly_chart(
                            chart_rwa_chains_breakdown(rwa_hist_df, chains_agg),
                            use_container_width=True,
                        )
                    else:
                        st.info("타 체인 분포 데이터 없음 — 모든 RWA가 이더리움 L1에 집중되어 있습니다.")

                st.markdown(
                    "<div class='info-box'>"
                    "📌 <b>해석 방법</b> — "
                    "<b>좌측</b>: 주황 영역이 커질수록 RWA 자금이 L2·타 체인으로 분산 중. "
                    "ETH TVL ↓ + 전체 TVL 유지 → Arbitrum·Base·Solana 등으로 이동. "
                    "ETH TVL ↓ + 전체 TVL ↓ → 만기 상환(오프체인 자금 이탈). "
                    "<b>우측</b>: 체인별 TVL 누적 면적으로 구체적인 목적지 확인. "
                    "청산·고래 수준의 실시간 추적은 유료 API(Nansen·Glassnode) 필요."
                    "</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("RWA 프로토콜 히스토리 데이터를 불러오지 못했습니다.")

    # ── DeFi 카테고리 분석 서브섹션 ──────────────────────────
    st.markdown(
        "<div class='section-header'><h3>🔍 Non-RWA DeFi 카테고리 구성 분석</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>"
        "💡 <b>분석 의도</b>: '기타 DeFi(Non-RWA)'는 단순한 잔여분이 아니라 이더리움 경제를 지탱하는 "
        "4개 핵심 엔진입니다. "
        "① <b>유동성 스테이킹</b>(Lido·Rocket Pool): 네트워크 보안 + stETH 담보 순환. "
        "② <b>대출/차입</b>(Aave·Compound): 레버리지·이자 수익 수요. "
        "③ <b>DEX 유동성</b>(Uniswap·Curve): 거래량 생성 엔진. "
        "④ <b>CDP</b>(MakerDAO·Sky): ETH 담보 탈중앙 스테이블코인 발행."
        "</div>",
        unsafe_allow_html=True,
    )

    cat_data = extract_defi_categories_tvl(protocols)

    if cat_data:
        defi_c1, defi_c2 = st.columns(2)
        with defi_c1:
            st.plotly_chart(chart_l1_tvl_categories(cat_data), use_container_width=True)

        # 카테고리별 상위 프로토콜 TVL 순위 표
        with defi_c2:
            for cat_en, meta in list(cat_data.items())[:5]:
                if cat_en == "기타 DeFi" or not meta["protocols"]:
                    continue
                top = meta["protocols"][:3]
                rows_html = "".join(
                    f"<div class='summary-item'>"
                    f"<span style='color:{THEME['subtext']}'>{p['name']}</span>"
                    f"<span style='color:{meta['color']};font-weight:bold'>${p['tvl']/1e9:.2f}B</span>"
                    f"</div>"
                    for p in top
                )
                st.markdown(
                    f"<div style='margin-bottom:10px;'>"
                    f"<b style='color:{meta['color']}'>{meta['ko']}</b>"
                    f"{rows_html}</div>",
                    unsafe_allow_html=True,
                )

        # 주요 프로토콜 ETH TVL 시계열
        TOP_N_PER_CAT = 2
        KEY_CATS = ["Liquid Staking", "Lending", "Dexes", "CDP"]
        top_protocols: list[dict] = []
        for cat_en in KEY_CATS:
            if cat_en not in cat_data:
                continue
            for p in cat_data[cat_en]["protocols"][:TOP_N_PER_CAT]:
                if p["slug"]:
                    top_protocols.append({
                        "name":        p["name"],
                        "slug":        p["slug"],
                        "color":       cat_data[cat_en]["color"],
                        "category_ko": cat_data[cat_en]["ko"],
                    })

        if top_protocols:
            with st.spinner("주요 DeFi 프로토콜 히스토리 로딩 중 ..."):
                defi_histories: dict[str, dict] = {}
                for p in top_protocols:
                    s = fetch_rwa_protocol_history(p["slug"], days=settings["history_days"])
                    if s is not None and not s.empty:
                        defi_histories[p["name"]] = {
                            "series":      s,
                            "color":       p["color"],
                            "category_ko": p["category_ko"],
                        }
            if defi_histories:
                st.plotly_chart(
                    chart_defi_top_protocols_history(defi_histories),
                    use_container_width=True,
                )

    # 기타 DeFi 세부 내역 익스팬더
    if cat_data and "기타 DeFi" in cat_data:
        other_protos = cat_data["기타 DeFi"]["protocols"]
        other_tvl_total = cat_data["기타 DeFi"]["tvl"]
        with st.expander(
            f"🔎 '기타 DeFi' 세부 내역 — 총 ${other_tvl_total/1e9:.1f}B  "
            f"({len(other_protos)}개 주요 프로토콜 표시)",
            expanded=False,
        ):
            st.markdown(
                "<div class='info-box'>"
                "📌 아래는 파이 차트에서 <b>'기타 DeFi'</b>로 분류된 프로토콜의 실제 목록입니다. "
                "카테고리명이 지속적으로 세분화되는 DefiLlama 분류 체계상, "
                "아직 주요 8개 카테고리에 포함되지 않은 새 카테고리가 이 버킷에 쌓입니다. "
                "<b>CEX 보관 자산</b>은 거래소 지갑 ETH로, 실제 DeFi 활동이 아닌 점 참고."
                "</div>",
                unsafe_allow_html=True,
            )
            # 카테고리별 소계
            from collections import defaultdict as _dd
            cat_subtotals: dict[str, float] = _dd(float)
            for op in other_protos:
                cat_subtotals[op["category"]] += op["tvl"]
            sub_rows = sorted(cat_subtotals.items(), key=lambda x: -x[1])
            cols_sub = st.columns(3)
            for i, (cat_en, sub_tvl) in enumerate(sub_rows):
                cols_sub[i % 3].metric(cat_en, f"${sub_tvl/1e9:.2f}B")

            st.markdown("---")
            # 프로토콜 리스트
            rows_per_col = max(1, (len(other_protos) + 2) // 3)
            col_a, col_b, col_c = st.columns(3)
            for chunk, col in zip(
                [other_protos[:rows_per_col],
                 other_protos[rows_per_col:rows_per_col*2],
                 other_protos[rows_per_col*2:]],
                [col_a, col_b, col_c],
            ):
                for op in chunk:
                    col.markdown(
                        f"<div class='summary-item'>"
                        f"<span style='color:{THEME['subtext']};font-size:0.82rem'>"
                        f"{op['name']} <i>({op['category']})</i></span>"
                        f"<span style='color:{THEME['text']};font-weight:bold'>"
                        f"${op['tvl']/1e9:.2f}B</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    # ──────────────────────────────────────────────────────
    # 섹션 6: 종합 분석 요약
    # ──────────────────────────────────────────────────────
    st.markdown(
        "<div class='section-header'><h3>📋 종합 분석 요약</h3></div>",
        unsafe_allow_html=True,
    )

    if price > 0:
        base_iv = calc_intrinsic_value(l1_tvl, l2_tvl_total, circulating_supply, settings["base_case"])
        ratio   = price / base_iv if base_iv > 0 else 0

        if   ratio < 0.85:  signal, sig_color = "🟢 저평가 (기본 모델 기준)",      THEME["accent_teal"]
        elif ratio < 1.15:  signal, sig_color = "🟡 적정 가격 근접",                THEME["accent_gold"]
        else:               signal, sig_color = "🔴 고평가 (기본 모델 기준)",       THEME["accent_red"]

        sum_col1, sum_col2 = st.columns(2)
        with sum_col1:
            st.markdown(
                f"<h4 style='color:{sig_color};'>{signal}</h4>",
                unsafe_allow_html=True,
            )
            rows = [
                ("ETH 현재가",             f"${price:,.2f}"),
                ("TVL 기반 적정가 (기본)", f"${base_iv:,.0f}"),
                ("현재가/적정가 비율",     f"{ratio:.2f}x"),
                ("L1 + L2 TVL 합계",       f"${(l1_tvl+l2_tvl_total)/1e9:.1f}B"),
                ("ETH 유통량",             f"{circulating_supply/1e6:.2f}M ETH"),
                ("스테이킹 APY",           f"{staking_apy:.2f}%"),
                ("24h 소각량 (추정)",      f"≈{burn_24h:,.0f} ETH"),
                ("RWA TVL",                f"${total_rwa/1e9:.2f}B"),
            ]
            c_sub  = THEME["subtext"]
            c_text = THEME["text"]
            for k, v in rows:
                st.markdown(
                    f"<div class='summary-item'>"
                    f"<span style='color:{c_sub}'>{k}</span>"
                    f"<span style='color:{c_text}; font-weight:bold;'>{v}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with sum_col2:
            st.markdown(
                """
#### 모델 한계 및 주의사항
- **단순성**: 본 모델은 TVL 단일 변수 기반이며, 실제 시장은
  통화정책·심리·규제·기술 위험 등 복합 변수에 의해 결정됩니다.
- **조정 계수 주관성**: 적정 계수 범위에 대한 학술적 합의가 없습니다.
- **상관관계 ≠ 인과관계**: TVL-가격 상관계수가 높아도 인과 방향이
  확정되지 않습니다 (역인과 가능성 존재).
- **데이터 지연**: API 캐싱으로 인해 수 분의 데이터 지연이 발생합니다.

> **이 대시보드는 교육·연구 목적 전용입니다. 투자 조언이 아닙니다.**
                """
            )

    # ── 자동 새로고침 ─────────────────────────────────────
    if settings["auto_refresh"]:
        time.sleep(300)
        st.rerun()

    # ── 푸터 ──────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:center; color:{THEME['subtext']}; font-size:0.78rem; margin-top:40px; padding-top:16px; border-top:1px solid {THEME['grid']};'>"
        f"데이터 출처: CoinGecko API · DefiLlama API · DefiLlama Yields &nbsp;|&nbsp; "
        f"갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; "
        f"© 이더리움 내재 가치 분석 대시보드"
        f"</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
