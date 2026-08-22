# K1–K4 매치보드

한국에서 볼 수 있는 경기 일정과 경기장을 날짜별로 한 화면에서 보기 위한 도구입니다.
지금은 축구(K리그1·2, K3·K4, 코리아컵, ACL 엘리트·ACL 2)를 담고 있고,
**다른 종목을 붙일 수 있는 구조**로 되어 있습니다.

## 구성

```
kfixtures/
├── .github/workflows/
│   └── update.yml      하루 2번 자동 갱신 + GitHub Pages 배포
├── adapters/           ← 리그 하나 = 어댑터 하나
│   ├── common.py         공용 HTTP·재시도, Competition/match 스키마, 시즌 창
│   ├── kleague.py        K리그1·2, 코리아컵, ACL 엘리트·ACL 2
│   └── kfa.py            K3리그, K4리그
├── scraper.py          어댑터를 하나씩 돌려 matches.json 생성
├── check.py            수집 결과 무결성 점검
├── template.html       뷰어 원본 (데이터 자리는 /*__MATCHES__*/)
├── build.py            템플릿 + 데이터 → dist/
├── matches.json        수집 결과 (= 다음 실행의 '직전 상태')
├── requirements.txt
├── SETUP.md            GitHub 자동 갱신 붙이는 법
└── dist/               ← 생성물. 커밋하지 않는다
    ├── index.html        단독 실행본 (더블클릭하면 열림 / Pages 루트)
    ├── artifact.html     Artifact 배포용 조각
    └── matches.json      공개 데이터 엔드포인트
```

## 자동 갱신

GitHub Actions 가 **한국시간 매일 06:00 · 23:30** 에 수집 → 점검 → 빌드 → Pages 배포까지 합니다.
붙이는 방법은 [SETUP.md](SETUP.md) 에 클릭 순서까지 적어뒀습니다.

갱신은 **종목별로 나누지 않습니다.** 워크플로 하나가 어댑터를 전부 돌립니다.
비시즌 대회는 `Competition(season=("10-01","04-30"))` 처럼 적힌 활동 기간을 보고
**요청조차 보내지 않고** 기존 일정을 그대로 둡니다. 해를 넘기는 겨울 종목도 그대로 씁니다.

대회별로 상태를 기록해서 화면 아래에 그대로 보여줍니다.

| 상태 | 뜻 |
|---|---|
| `ok` | 정상 수집 |
| `empty` | 수집했지만 0경기 (대진 미발표 등, 정상) |
| `offseason` | 비시즌이라 건너뜀 — 있던 데이터 유지 |
| `stale` | 수집 실패 or 경기 수 급감 → **직전 데이터 유지** |
| `failed` | 수집 실패 + 대체할 데이터도 없음 |
| `missing` | 0경기인데 그러면 안 되는 대회 |

한 대회가 죽어도 나머지는 정상 갱신되고, `check.py` 가 걸리면 배포를 멈춰
이미 올라가 있던 페이지가 유지됩니다.

## 사용법

```bash
pip install requests beautifulsoup4
python scraper.py               # 전체 수집 (약 2~3분)
python scraper.py k3 k4         # 특정 대회만 — 나머지는 직전 데이터 유지
python scraper.py --prev URL    # 직전 상태를 다른 데서 가져오기
python check.py                 # 무결성 점검
python build.py                 # dist/ 생성
```

`dist/index.html` 한 파일에 데이터까지 들어 있어 서버 없이 그냥 열려요.

## 새 리그·새 종목 추가하는 법

`scraper.py` 는 손대지 않습니다. 어댑터만 추가하면 됩니다.

1. `adapters/` 에 모듈을 하나 만들고
2. `Competition(...)` 을 담은 `COMPETITIONS` 리스트를 노출하고
3. `adapters/__init__.py` 의 `MODULES` 에 추가

```python
Competition(
    name="KBO 리그", sport="야구", slug="kbo",
    color=("#1F5C3A", "#5BC98E"),      # (라이트, 다크)
    soft=("#E2F0E8", "#14291E"),
    fetch=my_fetch,                     # (season, comp) -> [match(...), ...]
    season=("03-20", "11-10"),          # 활동 기간. 비시즌엔 건너뛴다. 생략하면 연중.
)
```

색은 데이터에 실려 화면에서 CSS 변수로 주입되므로 **스타일시트를 고칠 필요가 없습니다.**
종목이 둘 이상이 되면 상단에 종목 선택 줄(`전체 / 축구 / 야구 …`)이 자동으로 나타나고,
리그 칩은 고른 종목의 것만 보입니다.

`fetch` 는 어떤 예외를 던져도 됩니다. 직전 데이터가 있으면 그걸 유지한 채 `stale` 로,
없으면 `failed` 로 기록되고 나머지 대회는 그대로 저장됩니다.
추가한 뒤에는 **반드시 `python check.py`** 를 돌려보세요.

## 데이터 출처

**한국프로축구연맹** — `POST https://www.kleague.com/getScheduleList.do`

- 본문은 **반드시 JSON**. form-urlencoded 로 보내면 415.
- 리그: `{"leagueId":"1","year":"2026","month":"08"}`
- 컵대회: `{"leagueId":"<meetSeq>","meetType":"<n>","etcYn":"Y", ...}`
  meetType — `3` 구 ACL, `4` 코리아컵, `7` ACL 엘리트, `8` ACL 2
- 경기장·중계사·관중수·심판까지 들어 있는 넉넉한 응답입니다.

**대한축구협회** — `GET https://www.kfa.or.kr/competition/k3_2026.php?act=k3_round&chk_round=now&act_sub=k3&round=1`

- 라운드별 HTML 조각을 돌려주므로 파싱해서 씁니다.
- `joinkfa.com` 은 Nexacro(SSV) 기반이라 사실상 접근이 막혀 있어 kfa.or.kr 을 씁니다.

## 수집하면서 걸렸던 것들

- **kleague API 가 415 를 뱉음** — form 으로 보내서 그랬습니다. JSON 본문이어야 합니다.
- **슈퍼컵이 리그 일정에 섞여 들어옴** — 1라운드가 6경기가 아니라 7경기로 잡혀서 발견했습니다.
  `meetName` 으로 걸러냅니다.
- **컵대회 `meetSeq` 가 고정 ID 가 아님** — 그 달 목록에서의 *순번*입니다.
  2월의 `seq=2` 와 8월의 `seq=2` 가 서로 다른 대회라서, 처음엔 ACL 2 경기가 코리아컵으로 들어왔습니다.
  매달 `etcLeagueList` 를 먼저 읽고 **`meetType` 으로 대회를 식별**해야 합니다.
- **몰수패 경기** — K4리그 6월 20일 거제 vs 세종SA 는 점수 칸에 숫자 대신 `원정팀몰수패` 가 들어옵니다.
  숫자만 파싱하면 "아직 안 한 경기"로 잘못 잡힙니다. `note` 필드로 따로 담습니다.
- **원본 데이터 오류** — K4리그 25라운드 10월 31일 경기는 홈·원정이 둘 다 평창유나이티드입니다.
  KFA 쪽 표기 오류라 고치지 않고 그대로 두되 화면에 표시합니다.
- **K리그1 스플릿 라운드(34~38) 미편성** — 그래서 33라운드까지만 나옵니다.
- **6월에 K리그1 경기가 없음** — 2026 월드컵 휴식기입니다. 버그가 아닙니다.
- **코리아컵 0경기** — 대진이 아직 안 나왔습니다. 숨기지 않고 화면 하단에 이유를 밝힙니다.

## 아직 못 한 것

- **예매 링크** — 경기별 예매 URL은 발매 전에는 없고 구단마다 예매처가 제각각입니다.
  다만 kleague 쪽에 `getInterparkGoods.do` 라는 엔드포인트가 있어 다음 버전에서 파볼 만합니다.
- **다른 종목** — 구조는 준비됐습니다. 조사해 본 결과:
  - **KBO** — 공식 API 사용 가능. 한 달 130경기에 구장·스코어·중계사·`폭염취소` 상태까지 나옵니다.
    함정은 날짜가 그룹 첫 줄에만 붙는 rowspan 구조.
  - **KBL(농구) · KOVO(배구)** — 봇 차단으로 HTML 껍데기만 옵니다. 헤드리스 브라우저가 필요해 보입니다.
    비시즌(10월 개막)이라 검증도 아직 못 했습니다.
- **이름** — 종목이 늘어나면 "K1–K4 매치보드" 라는 이름은 더 이상 맞지 않습니다.
