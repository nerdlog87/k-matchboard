# -*- coding: utf-8 -*-
"""한국프로축구연맹 (kleague.com) 어댑터.

K리그1 · K리그2 · 코리아컵 · AFC 챔피언스리그 엘리트를 모두 같은 엔드포인트에서 가져온다.

  POST https://www.kleague.com/getScheduleList.do
  Content-Type: application/json      <- form 으로 보내면 415 를 뱉는다

리그:   {"leagueId":"1","year":"2026","month":"08"}
컵대회: {"leagueId":"<meetSeq>","meetType":"<n>","etcYn":"Y","year":..,"month":..}
"""

import time

from .common import Competition, http, match

URL = "https://www.kleague.com/getScheduleList.do"
HEADERS = {"Referer": "https://www.kleague.com/schedule.do"}

_clubs = {}          # 팀명 -> 구단 홈페이지. 수집 도중 덤으로 모인다.
_etc_cache = {}      # (시즌, 월) -> 그 달에 열리는 컵대회 목록


def _post(body):
    r = http(URL, method="POST", json=body, headers=HEADERS)
    data = (r.json() or {}).get("data") or {}
    for c in data.get("clubList") or []:
        if c.get("homepage"):
            _clubs[c["teamName"]] = c["homepage"]
    return data


def _etc_list(season, month):
    """그 달에 열리는 컵대회 목록.

    함정: meetSeq 는 고정 ID 가 아니라 '그 달 목록에서의 순번'이라
    2월의 seq 2 와 8월의 seq 2 가 서로 다른 대회다.
    그래서 매달 목록을 먼저 읽고 meetType 으로 대회를 식별해야 한다.
    """
    key = (season, month)
    if key not in _etc_cache:
        data = _post({"leagueId": "1", "year": str(season), "month": f"{month:02d}"})
        _etc_cache[key] = data.get("etcLeagueList") or []
    return _etc_cache[key]


def _rows(comp, games, meet_filter=None):
    out = []
    for g in games:
        # 같은 응답에 다른 대회(슈퍼컵 등)가 섞여 들어온다.
        meet = (g.get("meetName") or "").replace(" ", "")
        if meet_filter and meet_filter not in meet:
            continue
        finished = g.get("endYn") == "Y"
        out.append(match(
            competition=comp,
            date=g["gameDate"].replace(".", "-"),
            time_=(g.get("gameTime") or "")[:5],
            round_=g.get("roundId"),
            home=g.get("homeTeamName") or "",
            away=g.get("awayTeamName") or "",
            venue=g.get("fieldNameFull") or g.get("fieldName") or "",
            finished=finished,
            home_goal=g.get("homeGoal") if finished else None,
            away_goal=g.get("awayGoal") if finished else None,
            broadcast=g.get("matchBCList") or "",
            attendance=g.get("audienceQty"),
        ))
    return out


def _league(league_id, meet_filter):
    def fetch(season, comp):
        out = []
        for month in range(1, 13):
            data = _post({"leagueId": str(league_id),
                          "year": str(season),
                          "month": f"{month:02d}"})
            out += _rows(comp, data.get("scheduleList") or [], meet_filter)
            time.sleep(0.25)
        return out
    return fetch


def _cup(meet_type):
    """meetType 으로 대회를 고른다. 3=구 ACL, 4=코리아컵, 7=ACL 엘리트, 8=ACL 2"""
    def fetch(season, comp):
        out = []
        for month in range(1, 13):
            for e in _etc_list(season, month):
                if e.get("meetType") != meet_type:
                    continue
                data = _post({"leagueId": str(e["meetSeq"]),
                              "meetType": str(meet_type),
                              "etcYn": "Y",
                              "year": str(season),
                              "month": f"{month:02d}"})
                out += _rows(comp, data.get("scheduleList") or [])
                time.sleep(0.25)
        return out
    return fetch


COMPETITIONS = [
    Competition(name="K리그1", sport="축구", slug="k1",
                color=("#26346F", "#8B9CE8"), soft=("#E6E9F4", "#1D2440"),
                fetch=_league(1, "K리그1"), season=("02-01", "12-15")),
    Competition(name="K리그2", sport="축구", slug="k2",
                color=("#0F6F5F", "#43C4A9"), soft=("#E0F0EC", "#12302B"),
                fetch=_league(2, "K리그2"), season=("02-01", "12-15")),
    Competition(name="코리아컵", sport="축구", slug="kcup", group="컵대회",
                color=("#71409B", "#B79BDC"), soft=("#EFE7F6", "#281E36"),
                fetch=_cup(4), optional=True,
                note="코리아컵은 라운드별 대진이 확정된 뒤에 채워집니다."),
    Competition(name="ACL 엘리트", sport="축구", slug="acl", group="컵대회",
                color=("#0E7490", "#4FC0DE"), soft=("#DEEFF5", "#112C36"),
                fetch=_cup(7), optional=True,
                note="AFC 챔피언스리그 엘리트. 해외 원정 경기도 포함합니다."),
    Competition(name="ACL 2", sport="축구", slug="acl2", group="컵대회",
                color=("#4A6072", "#9DB3C4"), soft=("#E8EDF1", "#1E2933"),
                fetch=_cup(8), optional=True,
                note="AFC 챔피언스리그 2. 해외 원정 경기도 포함합니다."),
]


def homepages():
    return dict(_clubs)
