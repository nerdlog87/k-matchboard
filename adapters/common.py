# -*- coding: utf-8 -*-
"""어댑터 공용 도구.

리그(대회) 하나 = Competition 하나 = fetch() 하나.
수집기는 Competition 을 하나씩 돌리고, 하나가 죽어도 나머지는 그대로 간다.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})


def http(url, method="GET", tries=4, **kw):
    """네트워크가 간헐적으로 끊겨서 재시도 래퍼를 둔다."""
    last = None
    for attempt in range(tries):
        try:
            return session.request(method, url, timeout=30, **kw)
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


@dataclass
class Competition:
    """화면에 칩 하나로 나타나는 단위."""
    name: str                       # 화면 표기 ("K리그1")
    sport: str                      # 종목 ("축구")
    slug: str                       # CSS 변수 키 ("k1")
    color: Tuple[str, str]          # (light, dark) 강조색
    soft: Tuple[str, str]           # (light, dark) 배경색
    fetch: Callable[[int], List[dict]] = None
    group: str = "리그"             # "리그" | "컵대회"
    optional: bool = False          # 대진 미발표 등으로 0경기여도 정상인 대회
    note: str = ""                  # 화면 하단에 덧붙일 설명
    season: Tuple[str, str] = None  # 활동 기간 ("02-15","12-10"). None 이면 연중.

    def in_season(self, today):
        """비시즌이면 갱신할 때 통째로 건너뛴다.

        겨울 종목처럼 해를 넘기는 기간("10-01" ~ "04-30")도 그대로 쓴다.
        """
        if not self.season:
            return True
        start, end, now = self.season[0], self.season[1], today.strftime("%m-%d")
        return start <= now <= end if start <= end else (now >= start or now <= end)


def match(*, competition: Competition, date, time_, home, away, venue,
          round_=None, finished=False, home_goal=None, away_goal=None,
          broadcast="", attendance=None, note=""):
    """모든 어댑터가 이 모양으로만 돌려준다. 종목이 뭐든 동일하다."""
    return {
        "sport": competition.sport,
        "league": competition.name,
        "date": date,            # YYYY-MM-DD
        "time": time_,           # HH:MM
        "round": round_,
        "home": home,
        "away": away,
        "venue": venue,
        "finished": finished,
        "homeGoal": home_goal,
        "awayGoal": away_goal,
        "broadcast": broadcast,
        "attendance": attendance,
        "note": note,            # "원정팀몰수패", "폭염취소" 처럼 점수로 표현 못 하는 결과
    }
