# -*- coding: utf-8 -*-
"""KBO 리그 (koreabaseball.com) 어댑터.

  POST https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList
  form: leId=1&srIdList=0,9,6&seasonId=2026&gameMonth=08&teamId=
        ^ teamId 는 빈 값이라도 반드시 보내야 한다. 없으면 500 "매개 변수가 없습니다".

응답은 표를 그대로 옮긴 JSON 이라 칸이 HTML 조각이다.
함정 두 개:
  1) 날짜는 그 날 첫 경기 줄에만 붙는다(rowspan). 나머지 줄은 앞 날짜를 이어받는다.
     그래서 날짜 칸이 있는 줄은 9칸, 없는 줄은 8칸이 된다.
     칸 위치를 앞에서 세면 어긋나므로, 앞은 class(day/time/play)로, 뒤는 끝에서 센다.
  2) 취소된 경기는 점수가 없고 마지막 칸에 '우천취소' 같은 사유가 들어온다.
  3) 경기 칸의 구조가 함정이다. 팀 이름과 점수가 **둘 다 span** 이고, 점수 쪽은
     <em> 안에 한 겹 더 들어가 있다.
       <span>원정</span><em><span>4</span><span>vs</span><span>7</span></em><span>홈</span>
     그래서 span 을 통째로 훑으면 점수와 'vs' 까지 팀 이름으로 딸려온다.
     팀은 **바깥쪽(직계) span** 만, 점수는 <em> 안쪽에서 숫자만 꺼내야 한다.
"""

import time

from bs4 import BeautifulSoup

from .common import Competition, http, match

URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.koreabaseball.com/Schedule/Schedule.aspx",
    "X-Requested-With": "XMLHttpRequest",
}

# 응답의 구장 이름은 '잠실', '문학' 처럼 줄임말이라 지도 검색이 어긋난다.
VENUES = {
    "잠실": "잠실야구장", "고척": "고척스카이돔", "문학": "인천SSG랜더스필드",
    "수원": "수원KT위즈파크", "대전": "대전한화생명볼파크", "대구": "대구삼성라이온즈파크",
    "광주": "광주기아챔피언스필드", "사직": "사직야구장", "창원": "창원NC파크",
    "울산": "울산문수야구장", "포항": "포항야구장", "청주": "청주야구장",
    "군산": "군산월명야구장", "마산": "창원마산야구장",
}

# 중계사는 코드로 오고, 두 곳 이상이면 구분자 없이 그냥 붙어서 온다.
# 예) 'SPO-2TSPO-T' = SPO-2T + SPO-T. 그래서 긴 것부터 잘라낸다.
RELAY = {
    "SPO-2T": "SPOTV2", "SPO-T": "SPOTV",
    "MS-T": "MBC SPORTS+", "KN-T": "KBS N SPORTS", "SS-T": "SBS Sports",
    "KBS LIFE": "KBS LIFE", "TVING": "TVING",
    # 큰 경기는 지상파에도 걸린다. KN/MS/SS 와 같은 규칙으로 읽었다.
    "K-2T": "KBS2", "S-T": "SBS", "M-T": "MBC",
}
# 공백을 지운 코드끼리 맞춰야 하므로 열쇠도 공백을 지워 둔다 ('KBS LIFE' -> 'KBSLIFE').
_RELAY = {"".join(k.split()): v for k, v in RELAY.items()}
_RELAY_KEYS = sorted(_RELAY, key=len, reverse=True)


# KBO 응답에는 예매 칸이 아예 없다(빈 칸은 구분용). 그래서 구단 공식 홈페이지로 보낸다.
# 10개 구단 전부 2026-08-23 에 실제로 열어보고 확인했다.
CLUB_SITE = {
    "LG": "https://www.lgtwins.com",
    "두산": "https://www.doosanbears.com",
    "KT": "https://www.ktwiz.co.kr",
    "SSG": "https://www.ssglanders.com",
    "NC": "https://www.ncdinos.com",
    "삼성": "https://www.samsunglions.com",
    "롯데": "https://www.giantsclub.com",
    "KIA": "https://tigers.co.kr",
    "한화": "https://www.hanwhaeagles.co.kr",
    "키움": "https://www.heroesbaseball.co.kr",
}


def _text(html):
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def _cell(c):
    """칸 하나에서 글자만 뽑는다. 칸은 {"Text": "<b>18:00</b>", "Class": "time"} 모양이다."""
    return _text((c or {}).get("Text"))


def _relays(code):
    # 칸 안에서 중계사가 태그로 나뉘어 있어 글자를 뽑으면 사이에 공백이 낀다.
    # 붙어 오든 띄어 오든 같게 다루려고 공백을 전부 지우고 자른다.
    code, out = "".join((code or "").split()), []
    while code:
        for k in _RELAY_KEYS:
            if code.startswith(k):
                out.append(_RELAY[k])
                code = code[len(k):]
                break
        else:                       # 모르는 코드는 억지로 해석하지 말고 그대로 남긴다
            out.append(code)
            break
    return " · ".join(dict.fromkeys(out))


def _month(season, month):
    r = http(URL, method="POST", headers=HEADERS,
             data={"leId": "1", "srIdList": "0,9,6",
                   "seasonId": str(season), "gameMonth": f"{month:02d}",
                   "teamId": ""})
    try:
        return r.json().get("rows") or []
    except ValueError:              # 간헐적으로 HTML 오류 문서가 돌아온다
        return []


def _fetch(season, comp):
    out, cur_date = [], None
    for month in range(1, 13):
        for r in _month(season, month):
            cells = r.get("row") or []
            if len(cells) < 5:
                continue
            by = {c.get("Class"): c.get("Text") for c in cells if c.get("Class")}

            # 날짜 칸은 그 날 첫 줄에만 있다. 없으면 앞 날짜를 이어받는다.
            day = _text(by.get("day"))          # "08.01(토)"
            if day:
                cur_date = f"{season}-{day[:2]}-{day[3:5]}"
            if not cur_date:
                continue

            play = BeautifulSoup(by.get("play") or "", "html.parser")
            teams = [t.get_text(strip=True) for t in play.find_all("span", recursive=False)]
            em = play.find("em")
            goals = [x.get_text(strip=True) for x in em.find_all("span")] if em else []
            goals = [g for g in goals if g.isdigit()]
            if len(teams) < 2:
                continue
            away, home = teams[0], teams[1]     # 표기는 '원정 vs 홈' 순서다

            note = _cell(cells[-1]).strip()
            if note == "-":
                note = ""
            venue = _cell(cells[-2]).strip()
            done = len(goals) >= 2

            out.append(match(
                competition=comp,
                date=cur_date,
                time_=_text(by.get("time"))[:5],
                home=home,
                away=away,
                venue=VENUES.get(venue, venue),
                # 취소된 경기도 '그날 결과가 정해진' 경기로 본다. 점수 대신 사유를 남긴다.
                finished=done or bool(note),
                home_goal=int(goals[1]) if done else None,
                away_goal=int(goals[0]) if done else None,
                broadcast=_relays(_cell(cells[-4])),
                note=note,
                ticket_url=CLUB_SITE.get(home, ""),
                ticket_kind="club" if home in CLUB_SITE else "",
            ))
        time.sleep(0.3)
    return out


COMPETITIONS = [
    Competition(name="KBO 리그", sport="야구", slug="kbo",
                color=("#3F6B2E", "#96CC72"), soft=("#E7F0E0", "#1B2617"),
                fetch=_fetch, season=("03-01", "11-30")),
]
