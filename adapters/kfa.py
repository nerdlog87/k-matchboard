# -*- coding: utf-8 -*-
"""대한축구협회 (kfa.or.kr) 어댑터 — K3리그 · K4리그.

joinkfa.com 은 Nexacro(SSV) 기반이라 사실상 접근이 막혀 있다.
대신 kfa.or.kr 이 라운드별 HTML 조각을 그대로 돌려주므로 그쪽을 파싱한다.

  GET https://www.kfa.or.kr/competition/k3_2026.php
      ?act=k3_round&chk_round=now&act_sub=k3&round=1
"""

import re
import time

from bs4 import BeautifulSoup

from .common import Competition, http, match

URL = "https://www.kfa.or.kr/competition/{key}_{season}.php"
DT_RE = re.compile(r"(\d{2})-(\d{2})\([^)]*\)\s*(\d{2}:\d{2})")   # "08-29(토요일) 16:00"


def _parse_round(html, comp, season, round_no):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for td in soup.select("div.chart_result td"):
        divs = td.find_all("div", recursive=False)
        if len(divs) < 2:
            continue
        info, result = divs[0], divs[1]

        venue_el = info.find("span")
        venue = venue_el.get_text(strip=True) if venue_el else ""

        team_els = info.find_all("h3")
        if len(team_els) < 2:
            continue
        names = [re.sub(r"\s+", " ", t.get_text(" ", strip=True)).strip() for t in team_els]

        # 홈팀은 icon_home.png 가 붙어 있다. 없으면 첫 번째를 홈으로 본다.
        home_idx = 0
        for i, t in enumerate(team_els):
            if t.find("img", src=re.compile("icon_home")):
                home_idx = i
                break
        away_idx = 1 - home_idx

        dt_el = result.find("span")
        m = DT_RE.search(dt_el.get_text(strip=True) if dt_el else "")
        if not m:
            continue
        mm, dd, hhmm = m.groups()

        scores = [s.get_text(strip=True) for s in result.find_all("h3")[:2]]
        finished = len(scores) == 2 and all(s.isdigit() for s in scores)

        # 점수 칸에 숫자 대신 '원정팀몰수패' 같은 문구가 들어오는 경기가 있다.
        note = ""
        if not finished:
            text = " ".join(t for t in scores if t).strip()
            if text:
                note, finished = text, True
        # KFA 원본에 홈·원정이 같은 팀으로 잘못 올라온 행이 실제로 존재한다.
        if names[home_idx] == names[away_idx]:
            note = (note + " / " if note else "") + "원본 표기 오류(상대팀 미확정)"

        out.append(match(
            competition=comp,
            date=f"{season}-{mm}-{dd}",
            time_=hhmm,
            round_=round_no,
            home=names[home_idx],
            away=names[away_idx],
            venue=venue,
            finished=finished,
            home_goal=int(scores[home_idx]) if finished and not note else None,
            away_goal=int(scores[away_idx]) if finished and not note else None,
            note=note,
        ))
    return out


def _rounds(key, max_round=45):
    def fetch(season, comp):
        url = URL.format(key=key, season=season)
        out, empty = [], 0
        for rnd in range(1, max_round + 1):
            r = http(url, params={"act": f"{key}_round", "chk_round": "now",
                                  "act_sub": key, "round": rnd},
                     headers={"X-Requested-With": "XMLHttpRequest", "Referer": url})
            got = _parse_round(r.text, comp, season, rnd)
            if got:
                out += got
                empty = 0
            else:
                empty += 1
                if empty >= 3:      # 시즌 마지막 라운드를 지났다고 본다
                    break
            time.sleep(0.3)
        return out
    return fetch


COMPETITIONS = [
    Competition(name="K3리그", sport="축구", slug="k3",
                color=("#7B3FBF", "#9A64E8"), soft=("#F0EAF8", "#2A243C"), badge="K3",
                fetch=_rounds("k3"), season=("02-15", "12-10")),
    Competition(name="K4리그", sport="축구", slug="k4",
                color=("#2E7D32", "#55A85C"), soft=("#E8F1E8", "#1C3220"), badge="K4",
                fetch=_rounds("k4"), season=("02-15", "12-10")),
]
