# -*- coding: utf-8 -*-
"""V-리그 남·여 프로배구 (kovo.co.kr) 어댑터.

  GET https://user-api.kovo.co.kr/stat/game-schedule
      ?gcode=001&seasonCodes=NNN&leagueCodes=201&gender=1|2&page=0&size=300

주의: www.kovo.co.kr 은 봇을 연결 단계에서 끊어버리지만(RST),
API 서버(user-api.kovo.co.kr)는 열려 있다. SPA 번들에서 찾아낸 경로다.
파라미터 이름이 함정: 프론트 화면 주소는 season/league 단수인데
실제 API 는 **seasonCodes/leagueCodes 복수형**이다. 단수로 보내면 500.

시즌 코드는 /stat/season-list?gcode=001 에서 ryear(시즌 첫해)로 찾는다.
leagueCode 201 = 정규리그.
컵대회(여수·NH농협컵)는 gcode=002 가 따로 있고, 단계가 리그 코드로 쪼개져 있다:
  212=조별리그, 213=준결승, 214=결승전 (200=대회통산 기록용 — 일정은 0건)
leagueCodes 에 "212,213,214" 처럼 콤마로 이어 보내면 한 번에 온다.

응답 필드 메모
  gdate "2026-10-31" · gstime "14:00" · getime "" (끝난 경기만 채워짐)
  hsname/asname "대한항공" (짧은 이름. hname 이 풀네임)
  hspoint/aspoint  세트 스코어 (배구는 세트로 이긴다)
  place "인천계양체육관"
"""

from .common import Competition, http, match

API = "https://user-api.kovo.co.kr"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0",
      "Referer": "https://kovo.co.kr/", "Origin": "https://kovo.co.kr",
      "Accept-Language": "ko"}

_season_cache = {}


def _season_code(season, gcode="001"):
    """시즌 목록에서 ryear 가 시즌 첫해로 시작하는 seasonCode 를 찾는다.

    정규리그(001)는 ryear "2026-2027", 컵대회(002)는 ryear "2026" 꼴이다.
    """
    key = (gcode, season)
    if key in _season_cache:
        return _season_cache[key]
    r = http(f"{API}/stat/season-list", headers=UA, params={"gcode": gcode})
    r.raise_for_status()
    for s in r.json().get("payload") or []:
        if str(s.get("ryear") or "").startswith(str(season)):
            _season_cache[key] = s["seasonCode"]
            return s["seasonCode"]
    raise ValueError(f"{season} 시즌 코드를 찾지 못했다 (gcode={gcode})")


def _league(gender):
    def fetch(season, comp):
        r = http(f"{API}/stat/game-schedule", headers=UA, params={
            "gcode": "001", "seasonCodes": _season_code(season),
            "leagueCodes": "201", "gender": gender, "page": 0, "size": 500,
        })
        r.raise_for_status()
        body = r.json()
        payload = body.get("payload") or {}
        rows = payload.get("content") if isinstance(payload, dict) else payload
        if rows is None:
            raise ValueError(f"응답 형태가 다르다: {str(body)[:80]}")

        out = []
        for g in rows:
            finished = bool((g.get("getime") or "").strip())
            out.append(match(
                competition=comp,
                date=g.get("gdate") or "",
                time_=(g.get("gstime") or "")[:5],
                home=g.get("hsname") or g.get("hname") or "",
                away=g.get("asname") or g.get("aname") or "",
                venue=g.get("place") or "",
                round_=str(g["round"]) if g.get("round") else None,
                finished=finished,
                home_goal=g.get("hspoint") if finished else None,
                away_goal=g.get("aspoint") if finished else None,
                # 연맹 통합 예매의 홈팀 필터 페이지. 경기별 딥링크는 판매 시작
                # 전이라 검증할 수 없어서, 검증된 팀 단위 주소를 쓴다.
                ticket_url=f"https://kovo.co.kr/tickets/single?tcode={g['hcode']}" if g.get("hcode") else "",
                ticket_kind="shop" if g.get("hcode") else "",
            ))
        return out
    return fetch


def _cup(season, comp):
    """여수·NH농협컵. 남·여 대회가 같은 시즌코드 아래 gender 로 갈린다."""
    code = _season_code(season, gcode="002")
    out = []
    for gender, label in (("1", "남자부"), ("2", "여자부")):
        r = http(f"{API}/stat/game-schedule", headers=UA, params={
            "gcode": "002", "seasonCodes": code,
            "leagueCodes": "212,213,214",      # 조별리그·준결승·결승전
            "gender": gender, "page": 0, "size": 200,
        })
        r.raise_for_status()
        rows = (r.json().get("payload") or {}).get("content") or []
        for g in rows:
            finished = bool((g.get("getime") or "").strip())
            stage = (g.get("leagueName") or "").strip()      # "조별리그" 등
            out.append(match(
                competition=comp,
                date=g.get("gdate") or "",
                time_=(g.get("gstime") or "")[:5],
                home=g.get("hsname") or g.get("hname") or "",
                away=g.get("asname") or g.get("aname") or "",
                venue=g.get("place") or "",
                finished=finished,
                home_goal=g.get("hspoint") if finished else None,
                away_goal=g.get("aspoint") if finished else None,
                note=f"{stage} · {label}" if stage else label,
                ticket_url="https://kovo.co.kr/tickets/cup",
                ticket_kind="shop",
            ))
    return out


COMPETITIONS = [
    Competition(name="V리그 남자부", sport="배구", slug="vm",
                color=("#0154C5", "#4A8EE8"), soft=("#E4EDF9", "#1D2C41"), badge="V남",
                fetch=_league("1"), season=("09-01", "05-15"),
                note="V-리그 남자부 정규리그. 점수는 세트 스코어입니다."),
    Competition(name="V리그 여자부", sport="배구", slug="vw",
                color=("#00909A", "#0FAA87"), soft=("#E2F2F3", "#122F2C"), badge="V여",
                fetch=_league("2"), season=("09-01", "05-15"),
                note="V-리그 여자부 정규리그. 점수는 세트 스코어입니다."),
    Competition(name="KOVO컵", sport="배구", slug="vcup", group="컵대회",
                color=("#6A3FD8", "#9D7BF0"), soft=("#EFEAFB", "#2B293E"), badge="V컵",
                fetch=_cup, optional=True, season=("09-01", "11-15"),
                note="여수·NH농협컵. 남자부·여자부 경기가 함께 나옵니다. 점수는 세트 스코어입니다."),
]
