# Ethereum Intrinsic Value Dashboard

이더리움(ETH) 적정 가치 분석 대시보드. 무료 공개 API만을 사용해 온체인 데이터·거시경제 지표·RWA 점유율을 한 화면에서 분석합니다.

---

## 주요 기능

### 1. ETH 현재가 & 핵심 지표
- 실시간 ETH 가격·시가총액·24시간/7일 등락률 (CoinGecko)
- 스테이킹 APY, 24시간 소각량, 공급량 실시간 표시

### 2. TVL 기반 ETH 적정 가치 산출
- **공식**: `적정가 = (L1 TVL + L2 TVL) × 계수 / 유통량`
- 보수적(×0.5) / 기본(×1.0) / 낙관적(×2.0) 3가지 시나리오
- 사이드바 슬라이더로 계수 실시간 조정

### 3. 시계열 상관관계 분석
- ETH 가격 vs 이더리움 L1 TVL 피어슨 상관계수(r) 시각화
- ETH 가격 vs L1/L2 TVL 누적 면적 차트 (Arbitrum·Base·OP·Polygon·Starknet)
- ETH vs Solana TVL·활성 주소·스테이블코인 비교

### 4. 활동량 분석
- ETH 총 공급량 시계열 + 순 발행량(소각 반영) 이중 차트
- 스테이블코인 유통량 (Ethereum vs Solana)
- DEX 거래량 / TVL 자본 효율성 비율 (ETH vs SOL 7일 MA)
- DeFi 프로토콜 수수료 수익 (DefiLlama 집계)

### 5. 가격 트리거 분석 (거시경제 상관관계)
- **미 국채 10년물 금리** vs ETH 가격 (급락 -5%↓ 이벤트 자동 표시)
- **DXY 달러 인덱스** vs ETH 가격
- **BTC 도미넌스 대리지표** (BTC 시가총액 비율) vs ETH 가격
- **공포·탐욕 지수** 바 차트 + 게이지 (alternative.me)
- 4개 패널 통합 차트 (공유 X축)

### 6. RWA (실물자산) 이더리움 점유율 추적
- 이더리움 L1 내 RWA 프로토콜 구성 도넛 차트 (BlackRock BUIDL·Ondo·Franklin Templeton 등)
- 골드 토큰(PAXG·XAUT) 제외 토글 — 순수 금융 RWA만 분리 분석
- RWA 프로토콜별 TVL 시계열 (적층 영역)
- 이더리움 L1 TVL 내 RWA 비중 추이
- **자금 흐름 분석**: 이더리움 L1 vs 전체 체인 비교
  - ETH TVL ↓ + 전체 TVL 유지 → L2/타 체인으로 이동
  - ETH TVL ↓ + 전체 TVL ↓ → 오프체인 상환(자금 이탈)
- **체인별 TVL 분포**: Ethereum + Arbitrum·Base·Solana·Stellar 등 적층 면적

### 7. Non-RWA DeFi 카테고리 구성 분석
- L1 TVL을 20개 카테고리로 분류 (유동성 스테이킹·대출·DEX·CDP·리스테이킹·베이시스 트레이딩 등)
- 카테고리별 상위 프로토콜 TVL 순위
- 주요 프로토콜 ETH L1 TVL 시계열 (Lido·Aave·Uniswap·MakerDAO 등)
- **"기타 DeFi" 세부 내역 익스팬더** — 분류되지 않은 프로토콜 카테고리·TVL 전체 공개

---

## 사용 데이터 소스

| API | 용도 | 비용 |
|---|---|---|
| [CoinGecko](https://www.coingecko.com/en/api) | ETH 가격·시가총액·공급량·히스토리 | 무료 |
| [DefiLlama](https://defillama.com/docs/api) | L1/L2 TVL·프로토콜·RWA·수수료 | 무료 |
| [yfinance](https://pypi.org/project/yfinance/) | 미 국채 10년물(^TNX)·DXY 달러 인덱스 | 무료 |
| [Alternative.me](https://alternative.me/crypto/fear-and-greed-index/) | 공포·탐욕 지수 (365일) | 무료 |

> 모든 데이터는 **완전 무료 공개 API**만 사용합니다. API 키 불필요.

---

## 설치 및 실행

### 요구 사항
- Python 3.10+
- Anaconda 또는 venv 환경 권장

### 설치

```bash
git clone https://github.com/woosp/cryto_analyzer.git
cd cryto_analyzer
pip install -r requirements.txt
```

### 실행

```bash
streamlit run ethereum_dashboard.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 사이드바 설정

| 설정 | 기본값 | 범위 |
|---|---|---|
| 보수적 계수 | 0.5 | 0.2 – 1.0 |
| 기본 계수 | 1.0 | 0.5 – 2.0 |
| 낙관적 계수 | 2.0 | 1.0 – 5.0 |
| 분석 기간 | 180일 | 30 / 60 / 90 / 180 / 270 / 365일 |
| 자동 새로고침 | OFF | 5분 간격 |

---

## 아키텍처

```
ethereum_dashboard.py
│
├── CSS / 다크 테마 팔레트 (THEME dict)
│
├── 데이터 수집 레이어 (@st.cache_data)
│   ├── _fetch_eth_market_chart_raw()     # CoinGecko 공유 캐시 (중복 호출 방지)
│   ├── fetch_eth_current()               # 현재가 (TTL 5분)
│   ├── fetch_eth_history()               # 가격 히스토리
│   ├── fetch_eth_supply_history()        # 공급량 히스토리
│   ├── fetch_defillama_tvl_history()     # 체인별 TVL 시계열
│   ├── fetch_defillama_protocols()       # 프로토콜 목록
│   ├── fetch_rwa_protocol_history()      # RWA 프로토콜 ETH TVL
│   ├── fetch_rwa_protocol_total_tvl()    # RWA 프로토콜 전체 체인 TVL
│   ├── fetch_rwa_protocol_chains()       # RWA 프로토콜 체인별 TVL
│   ├── fetch_macro_data()               # yfinance (^TNX, DXY)
│   ├── fetch_btc_dominance_proxy()      # BTC 도미넌스 대리지표
│   └── fetch_fear_greed()               # 공포·탐욕 지수
│
├── 차트 레이어 (Plotly)
│   ├── _apply_dark_theme()              # 공통 다크 테마 헬퍼
│   ├── chart_price_vs_tvl()
│   ├── chart_l1_l2_tvl_history()
│   ├── chart_eth_vs_solana()
│   ├── chart_eth_supply_burn()
│   ├── chart_stablecoin_history()
│   ├── chart_dex_volume_history()
│   ├── chart_dex_capital_efficiency()
│   ├── chart_rwa_pie()
│   ├── chart_rwa_composition_history()
│   ├── chart_rwa_share_trend()
│   ├── chart_rwa_chain_flow()
│   ├── chart_rwa_chains_breakdown()
│   ├── chart_l1_tvl_categories()
│   ├── chart_defi_top_protocols_history()
│   ├── chart_eth_treasury_yield()       # 트리거: ETH + 금리
│   ├── chart_dxy_vs_eth()               # 트리거: DXY
│   ├── chart_btc_dominance()            # 트리거: BTC 도미넌스
│   ├── chart_fear_greed()               # 트리거: 공포·탐욕 바차트
│   ├── chart_fear_greed_gauge()         # 트리거: 게이지
│   ├── chart_trigger_combined()         # 트리거: 4패널 통합
│   └── chart_intrinsic_value()
│
└── main()
    ├── 섹션 1: 현재가 & 핵심 지표
    ├── 섹션 2: 적정 가치 (Intrinsic Value)
    ├── 섹션 3: 상관관계 분석
    ├── 섹션 4: 활동량 분석
    ├── 섹션 5: 가격 트리거 분석
    ├── 섹션 5-RWA: 실물자산 점유율 추적
    ├── 섹션 5-DeFi: Non-RWA 카테고리 분석
    └── 섹션 6: 종합 분석 요약
```

---

## 주요 분석 해석 가이드

### TVL 기반 적정가
TVL은 이더리움 위 프로토콜들의 총 예치 자산 규모입니다. ETH가 이 생태계의 담보 자산 역할을 한다는 전제 하에, TVL이 클수록 ETH의 내재 가치가 높다고 봅니다. 계수는 "ETH 1달러가 TVL 몇 달러를 지지하는가"를 조정합니다.

### RWA 비중
BlackRock·Franklin Templeton 같은 기관이 이더리움 위에 국채·MMF를 토큰화하면 → 구조적이고 장기적인 ETH 수요가 형성됩니다. RWA 비중 상승 = 기관 채택 가속화 신호.

### 자금 흐름 해석
- **ETH L1 TVL ↓ + 전체 RWA TVL 유지** → Arbitrum·Base 등 L2로 자금 이동 (이더리움 생태계 내)
- **ETH L1 TVL ↓ + 전체 RWA TVL ↓** → 만기 상환 등 오프체인 자금 이탈

### 거시 트리거
| 신호 | 의미 |
|---|---|
| 미 국채 금리 ↑ | 기관 de-risking → ETH 매도 압력 |
| DXY ↑ | 달러 강세 → 위험자산 전반 약세 |
| BTC 도미넌스 ↑ | 알트코인에서 BTC로 로테이션 |
| 공포·탐욕 ≤ 25 | 극도 공포 → 역발상 매수 구간 |

---

## 라이선스

MIT License
