# -*- coding: utf-8 -*-
"""KBL 남자 프로농구 (kbl.or.kr) 어댑터.

  GET https://api.kbl.or.kr/match/list
      ?fromDate=YYYYMMDD&toDate=YYYYMMDD&tcodeList=all

SPA 가 쓰는 내부 API 다. 그냥 부르면 400 "필수 헤더 정보가 누락" 이 온다.
번들(assets/index-*.js)의 axios 인터셉터를 읽어보면 웹 채널일 때
Channel/TeamCode/lang 헤더를 채워 보낸다. 그대로 흉내내면 열린다.

응답 필드 메모
  gameDate "20261024" · gameStart "1400" · isEnded 0/1
  tnameH/tnameA  "서울 SK" (짧은 표기. tnameFH 가 풀네임)
  scoreH/scoreA  숫자. 시작 전엔 0:0 이므로 isEnded 로만 종료를 판단한다.
                 (진행 중 경기도 isEnded=0 에 점수가 실려온다 — 점수는
                  isEnded=1 일 때만 믿는다)
  stadiumnameF   "안양 정관장 아레나" (풀 경기장명)
  tv             "tvN SPORTS" 또는 None
  seasonCategory "R"=정규시즌, "OM"=오픈 매치 등. 정규가 아니면 note 로 밝힌다.
"""

from .common import Competition, http, match

API = "https://api.kbl.or.kr/match/list"
HEADERS = {
    "Channel": "WEB",
    "TeamCode": "XX",
    "lang": "ko",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.kbl.or.kr/",
}


# 구단 홈페이지 (kbl.or.kr SPA 번들의 팀 서브도메인 목록에서 추출).
# 각 구단 사이트에 티켓 메뉴가 있다. 해체 구단(오리온·캐롯)은 뺐다.
CLUB = {
    "원주 DB":       "https://promy.kbl.or.kr/",
    "서울 삼성":      "https://thunders.kbl.or.kr/",
    "서울 SK":       "https://knights.kbl.or.kr/",
    "창원 LG":       "https://sakers.kbl.or.kr/",
    "고양 소노":      "https://skygunners.kbl.or.kr/",
    "대구 한국가스공사": "https://pegasus.kbl.or.kr/",
    "부산 KCC":      "https://egis.kbl.or.kr/",
    "안양 정관장":     "https://kgc.kbl.or.kr/",
    "수원 KT":       "https://sonicboom.kbl.or.kr/",
    "울산 현대모비스":   "https://phoebus.kbl.or.kr/",
}


def _fetch(season, comp):
    # 시즌은 해를 넘긴다: 2026-27 시즌이면 2026-09 ~ 2027-05.
    r = http(API, headers=HEADERS, params={
        "fromDate": f"{season}0901",
        "toDate": f"{season + 1}0531",
        "tcodeList": "all",
    })
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise ValueError(f"응답이 목록이 아니다: {str(rows)[:80]}")

    out = []
    for g in rows:
        d = g.get("gameDate") or ""
        t = g.get("gameStart") or ""
        ended = bool(g.get("isEnded"))
        cat = g.get("seasonCategory")
        home = g.get("tnameH") or ""
        club = CLUB.get(home, "")
        out.append(match(
            competition=comp,
            date=f"{d[:4]}-{d[4:6]}-{d[6:8]}",
            time_=f"{t[:2]}:{t[2:4]}" if len(t) >= 4 else "",
            home=home,
            away=g.get("tnameA") or "",
            venue=g.get("stadiumnameF") or g.get("stadiumname") or "",
            round_=None,
            finished=ended,
            home_goal=g.get("scoreH") if ended else None,
            away_goal=g.get("scoreA") if ended else None,
            broadcast=g.get("tv") or "",
            note="" if cat == "R" else (g.get("seasonCategoryName") or ""),
            ticket_url=club, ticket_kind="club" if club else "",
        ))
    return out


COMPETITIONS = [
    Competition(name="KBL", sport="농구", slug="kbl",
                color=("#D45500", "#DE7010"), soft=("#FAEDE2", "#3A2814"), badge="KBL",
                fetch=_fetch, season=("09-01", "05-31"),
                note="KBL 프로농구. 오픈 매치·컵대회 경기는 따로 표시합니다."),
]
