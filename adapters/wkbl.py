# -*- coding: utf-8 -*-
"""WKBL 여자 프로농구 (wkbl.or.kr) 어댑터.

옛날식 ASP 페이지라 API 가 없고 HTML 표를 읽는다. 함정이 하나 있었다:
겉 페이지(scheduleb1.asp)에 보이는 표는 **박신자컵만** 담고 있다.
정규리그는 페이지 안의 axios 호출이 따로 불러온다 (개발자도구로 찾음):

  GET /game/sch/inc_list_1_new.asp?season_gu=047&ym=202611&viewType=&gun=1

ym(연월)별로 끊어 오므로 시즌 범위(8월~다음해 4월)를 월 단위로 돈다.
시즌 코드는 schedule1.asp 의 시즌 셀렉트에서 "2026-2027" 라벨로 찾는다.

행 구조 (박신자컵/정규 공통):
  <td>10/3(토)</td>                              ← 연도가 없다. 월>=7 → 시즌 첫해.
  <td><div class="team_versus">
    <div class="info_team away">…<em class="txt_score">52</em></div>  ← 원정 먼저
    <div class="info_team home">…</div></td>                          ← 홈이 뒤
  <td data-kr="청주체육관">…</td> <td>14:00</td>
  <td>…</td>   ← 끝난 경기는 기록(Data Lab) 링크, 아니면 중계 버튼 — 채널명이 아니라 버린다
점수(txt_score)는 끝난 경기에만 붙는다.
"""

from bs4 import BeautifulSoup

from .common import Competition, http, match

BASE = "https://www.wkbl.or.kr"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0",
      "Referer": "https://www.wkbl.or.kr/game/sch/schedule1.asp"}
MONTHS = (8, 9, 10, 11, 12, 1, 2, 3, 4)      # 시즌이 걸치는 달

# 구단 홈페이지 (wkbl.or.kr 티켓 안내 페이지에서 수집).
# 하나은행은 자체 홈페이지가 없어서 링크를 달지 않는다.
CLUB = {
    "삼성생명": "http://www.samsungblueminx.com/",
    "신한은행": "http://www.sbirds.com/",
    "우리은행": "https://wooriwon.wooribank.com/basketball/main/bridge.php",
    "BNK 썸": "http://bnksumbasket.com",
    "KB스타즈": "http://www.kbstars.co.kr",
}


def _season_gu(season):
    r = http(f"{BASE}/game/sch/schedule1.asp", headers=UA)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for opt in soup.select("#season_gu option") or soup.find_all("option"):
        if opt.get_text(strip=True).startswith(str(season)) and opt.get("value", "").isdigit():
            return opt["value"]
    raise ValueError(f"{season} 시즌을 시즌 목록에서 찾지 못했다")


def _rows(html, season, comp, note=""):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.find_all("tr"):
        vs = tr.find("div", class_="team_versus")
        if not vs:
            continue
        tds = tr.find_all("td")

        md = tds[0].get_text(" ", strip=True).split("(")[0].strip()
        mon, day = (int(x) for x in md.split("/"))
        year = season if mon >= 7 else season + 1

        def team(cls):
            box = vs.find("div", class_=cls)
            name = box.find(class_="team_name") if box else None
            score = box.find(class_="txt_score") if box else None
            n = (name.get("data-kr") or name.get_text(strip=True)).strip() if name else ""
            s = score.get_text(strip=True) if score else ""
            return n, (int(s) if s.isdigit() else None)

        away, a_goal = team("away")      # 원정이 먼저 온다
        home, h_goal = team("home")
        finished = h_goal is not None and a_goal is not None
        venue = (tds[2].get("data-kr") or tds[2].get_text(" ", strip=True)).strip() if len(tds) > 2 else ""
        time_ = tds[3].get_text(strip=True)[:5] if len(tds) > 3 else ""

        out.append(match(
            competition=comp,
            date=f"{year}-{mon:02d}-{day:02d}",
            time_=time_, home=home, away=away, venue=venue,
            finished=finished, home_goal=h_goal, away_goal=a_goal,
            note=note,
            ticket_url=CLUB.get(home, ""),
            ticket_kind="club" if home in CLUB else "",
        ))
    return out


def _fetch(season, comp):
    gu = _season_gu(season)
    out = []

    # 1) 박신자컵 — 겉 페이지의 표가 이것이다
    r = http(f"{BASE}/game/sch/scheduleb1.asp", headers=UA, params={"season_gu": gu})
    r.raise_for_status()
    out += _rows(r.text, season, comp, note="박신자컵")

    # 2) 정규리그 — 월별 조각을 돈다 (일정 미발표 달은 그냥 빈 응답이다)
    for mon in MONTHS:
        year = season if mon >= 7 else season + 1
        r = http(f"{BASE}/game/sch/inc_list_1_new.asp", headers=UA,
                 params={"season_gu": gu, "ym": f"{year}{mon:02d}",
                         "viewType": "", "gun": "1"})
        r.raise_for_status()
        out += _rows(r.text, season, comp)

    # 같은 경기가 두 군데서 오면 하나만 남긴다 (컵 표기가 있는 쪽 우선)
    seen, dedup = {}, []
    for m in out:
        k = (m["date"], m["home"], m["away"])
        if k in seen:
            continue
        seen[k] = True
        dedup.append(m)
    return dedup


COMPETITIONS = [
    Competition(name="WKBL", sport="농구", slug="wkbl",
                color=("#C63884", "#DE5CA8"), soft=("#F9EAF2", "#382030"), badge="WK",
                fetch=_fetch, season=("08-20", "04-30"),
                note="WKBL 여자 프로농구. 박신자컵 경기는 따로 표시합니다."),
]
