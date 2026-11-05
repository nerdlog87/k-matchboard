# -*- coding: utf-8 -*-
"""직관 알리미 — 조건에 맞는 경기를 텔레그램으로 알려준다.

  python notify.py            # 실제 발송 (환경변수 필요)
  python notify.py --dry      # 보낼 내용만 출력, 발송·저장 안 함

필요한 환경변수 (GitHub Secrets 로 주입된다)
  TELEGRAM_BOT_TOKEN   BotFather 가 준 토큰
  TELEGRAM_CHAT_ID     알림 받을 채팅 ID (이 ID 가 보낸 명령만 믿는다)

하는 일 (매 실행마다)
  1) 봇이 받은 메시지를 읽어 구독 명령을 처리한다
       /구독 종목=야구 팀=롯데 지역=수도권 요일=토,일   ← 사이트 알림 탭이 만들어 준다
       /목록   /해지 3   /start
  2) matches.json 의 경기를 구독 조건과 대조해 알림을 보낸다
       [D-14]   경기 14일 전 사전 알림 (전 종목)
       [오픈 임박] 예매 오픈 시각이 24시간 안 (V리그=API 정각 / KBO=구단 관행 추정)
       [예매 중]  예매가 실제로 열림 (K리그=예매 링크 등장 / V리그=오픈 시각 경과)
       KBL·WKBL 은 오픈 시각을 공개하지 않아 D-14 알림만 간다.
  3) 보낸 알림은 alert_state.json 에 적어 같은 알림을 두 번 보내지 않는다.

상태 파일(alert_state.json)은 구독 목록과 발송 기록을 담고, 워크플로가 커밋한다.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
HERE = Path(__file__).resolve().parent
MATCHES = HERE / "matches.json"
STATE = HERE / "alert_state.json"
SITE = "https://nerdlog87.github.io/k-matchboard/"

# ── 수도권 판별 ───────────────────────────────────────────────────────
# 1차: 현재 데이터의 경기장 전수조사로 만든 명시 목록 (2026-11 기준 135곳 검토)
CAPITAL_VENUES = {
    "고양소노아레나", "고척스카이돔", "김포솔터축구장", "남양주체육문화센터 축구장",
    "목동 종합 운동장", "물맑은양평종합운동장", "부천 종합 운동장", "부천체육관",
    "서울 월드컵", "서울 월드컵 경기장", "서울장충체육관", "수원 KT 소닉붐 아레나",
    "수원 월드컵 경기장", "수원 종합 운동장", "수원KT위즈파크", "수원체육관",
    "안산 와~스타디움", "안양 정관장 아레나", "안양 종합 운동장", "여주종합운동장",
    "용인 미르스타디움", "용인실내체육관", "인천 축구 전용경기장", "인천SSG랜더스필드",
    "인천계양체육관", "인천도원체육관", "인천삼산월드체육관", "잠실야구장",
    "잠실학생체육관", "탄천 종합 운동장", "파주 스타디움", "평택이충문화체육관",
    "포천종합운동장", "화성종합경기타운", "화성종합실내체육관",
    "경희대 선승관",        # 서울캠퍼스 체육관
    "중랑구립운동장",        # 서울 중랑구
    "정왕스타디움",          # 시흥
    "소사벌레포츠타운",       # 평택
}
# 2차: 목록에 없는 새 경기장은 지명 키워드로 추정한다
CAPITAL_KEYWORDS = (
    "서울", "인천", "잠실", "고척", "목동", "상암", "장충",
    "수원", "고양", "성남", "부천", "안양", "안산", "용인", "김포", "의정부",
    "파주", "화성", "평택", "광명", "시흥", "하남", "이천", "여주", "양평",
    "구리", "남양주", "포천", "동두천", "가평", "과천", "군포", "의왕",
    "오산", "안성", "탄천", "계양", "청라", "송도", "미추홀", "일산", "위례",
)


def is_capital(venue):
    v = (venue or "").strip()
    return v in CAPITAL_VENUES or any(k in v for k in CAPITAL_KEYWORDS)


# ── KBO 구단별 예매 오픈 관행 (일반예매 기준, 홈팀이 결정한다) ─────────
# 제3자 정리 기준의 '추정'이다. 메시지에도 (추정) 을 붙인다.
KBO_OPEN = {  # 홈팀: (경기 며칠 전, "HH:MM")
    "롯데": (14, "14:00"), "LG": (7, "11:00"), "한화": (7, "11:00"),
    "SSG": (5, "11:00"), "삼성": (7, "11:00"), "NC": (7, "11:00"),
    "KT": (7, "16:00"), "KIA": (7, "11:00"), "두산": (7, "11:00"),
    "키움": (7, "14:00"),
}

WD = ["월", "화", "수", "목", "금", "토", "일"]


# ── 텔레그램 ─────────────────────────────────────────────────────────
class TG:
    def __init__(self, token, chat_id, dry):
        self.base = f"https://api.telegram.org/bot{token}" if token else None
        self.chat = str(chat_id or "")
        self.dry = dry or not token

    def updates(self, offset):
        if not self.base:
            return []
        r = requests.get(f"{self.base}/getUpdates",
                         params={"offset": offset, "timeout": 0}, timeout=30)
        r.raise_for_status()
        return r.json().get("result") or []

    def send(self, text):
        if self.dry:
            print("─" * 46)
            print(text)
            return True
        r = requests.post(f"{self.base}/sendMessage", timeout=30, json={
            "chat_id": self.chat, "text": text,
            "disable_web_page_preview": True,
        })
        if not r.ok:
            print(f"  ! 발송 실패 {r.status_code}: {r.text[:120]}", file=sys.stderr)
        return r.ok


# ── 구독 명령 ─────────────────────────────────────────────────────────
FIELDS = {"종목": "sport", "리그": "league", "팀": "teams",
          "지역": "region", "요일": "days"}


def parse_rule(text):
    """'/구독 종목=야구 팀=롯데 지역=수도권 요일=토,일 홈만' → 조건 dict"""
    rule = {}
    for tok in text.split()[1:]:
        if tok == "홈만":
            rule["home_only"] = True
            continue
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if k not in FIELDS or not v:
            continue
        key = FIELDS[k]
        rule[key] = [x.strip() for x in v.split(",") if x.strip()] \
            if key in ("teams", "days") else v.strip()
    return rule or None


def rule_label(rule):
    out = []
    if rule.get("sport"):
        out.append(rule["sport"])
    if rule.get("league"):
        out.append(rule["league"])
    if rule.get("teams"):
        out.append("팀 " + "·".join(rule["teams"]))
    if rule.get("home_only"):
        out.append("홈만")
    if rule.get("region"):
        out.append(rule["region"])
    if rule.get("days"):
        out.append("/".join(rule["days"]))
    return " · ".join(out) or "(조건 없음)"


def norm(s):
    return re.sub(r"\s+", "", s or "").casefold()


def team_hit(t, side):
    """팀 이름 매칭. 띄어쓰기를 무시한 **양방향** 포함 매칭이되, 함정 하나를 막는다:
    '수원'이 '수원FC'를, '서울'이 '서울E'를 무는 것. 포함된 자리의 바로
    옆 글자가 영문·숫자면 다른 팀(라틴 접미사 구단)으로 보고 거른다.
    양방향인 이유: 같은 팀이 '부산 KCC'/'KCC' 처럼 길고 짧게 섞여 오기 때문.
    """
    t, side = norm(t), norm(side)
    if t == side:
        return True

    def contains(big, small):
        i = big.find(small)
        if i < 0:
            return False
        before = big[i - 1] if i > 0 else ""
        after = big[i + len(small)] if i + len(small) < len(big) else ""
        latin = re.compile(r"[a-z0-9]")
        return not (latin.match(after) or latin.match(before))

    return contains(side, t) or contains(t, side)


def rule_matches(rule, m):
    if rule.get("sport") and m["sport"] != rule["sport"]:
        return False
    if rule.get("league") and m["league"] != rule["league"]:
        return False
    if rule.get("region") == "수도권" and not is_capital(m["venue"]):
        return False
    if rule.get("days"):
        wd = WD[datetime.strptime(m["date"], "%Y-%m-%d").weekday()]
        if wd not in rule["days"]:
            return False
    if rule.get("teams"):
        pool = [m["home"]] if rule.get("home_only") else [m["home"], m["away"]]
        if not any(team_hit(t, side) for t in rule["teams"] for side in pool):
            return False
    return True


def handle_commands(tg, state):
    """봇이 받은 메시지를 읽어 구독을 갱신한다. 주인의 chat_id 만 믿는다."""
    changed = False
    for u in tg.updates(state.get("offset", 0) + 1):
        state["offset"] = max(state.get("offset", 0), u["update_id"])
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        sender = str((msg.get("chat") or {}).get("id") or "")
        if not text:
            continue
        if sender != tg.chat:        # 모르는 사람 명령은 무시한다
            continue

        if text.startswith("/구독"):
            rule = parse_rule(text)
            if rule:
                state.setdefault("subs", []).append(rule)
                changed = True
                tg.send(f"✅ 구독 등록 {len(state['subs'])}번\n{rule_label(rule)}")
            else:
                tg.send("조건을 읽지 못했습니다. 사이트의 알림 탭에서 만든 명령을 그대로 보내주세요.")
        elif text.startswith("/목록"):
            subs = state.get("subs", [])
            body = "\n".join(f"{i+1}. {rule_label(r)}" for i, r in enumerate(subs)) \
                or "등록된 구독이 없습니다."
            tg.send(f"📋 구독 목록\n{body}\n\n해지: /해지 번호")
        elif text.startswith("/해지"):
            mnum = re.search(r"\d+", text)
            subs = state.get("subs", [])
            if mnum and 1 <= int(mnum.group()) <= len(subs):
                gone = subs.pop(int(mnum.group()) - 1)
                changed = True
                tg.send(f"🗑 해지했습니다: {rule_label(gone)}")
            else:
                tg.send("해지할 번호를 못 찾았습니다. /목록 으로 번호를 확인해주세요.")
        elif text.startswith("/start"):
            tg.send("안녕하세요, 경기 있는 날 알리미입니다!\n"
                    f"구독 조건은 사이트의 알림 탭에서 만들 수 있습니다.\n{SITE}#alert\n"
                    "명령: /목록 · /해지 번호")
    return changed


# ── V리그 예매 오픈 시각 (공개 API) ───────────────────────────────────
def kovo_open_times():
    """(날짜, 정규화된 팀이름들) → 오픈 시각 매핑을 만든다."""
    try:
        r = requests.get("https://user-api.kovo.co.kr/ticket/game-schedules/ticket-buy",
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://kovo.co.kr/",
                                  "Origin": "https://kovo.co.kr", "Accept-Language": "ko"},
                         params={"size": 500, "page": 0, "sort": "playDate,ASC"}, timeout=30)
        r.raise_for_status()
        rows = (r.json().get("payload") or {}).get("content") or []
    except Exception as e:
        print(f"  ! KOVO 예매 정보 조회 실패(이번 회차는 건너뜀): {e}", file=sys.stderr)
        return []
    out = []
    for x in rows:
        d = x.get("playDate") or ""
        opening = x.get("openingTime") or ""
        if len(d) == 8 and opening:
            out.append({
                "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                "title": norm(x.get("subTitle") or x.get("scheduleName") or ""),
                "open": opening,            # "2026-10-31T11:00"
            })
    return out


def find_open_time(m, kovo_rows):
    """경기 하나의 예매 오픈 시각(KST datetime)과 출처를 찾는다."""
    if m["sport"] == "배구":
        d = m["date"]
        for row in kovo_rows:
            if row["date"] == d and norm(m["home"]) in row["title"] and norm(m["away"]) in row["title"]:
                try:
                    return datetime.fromisoformat(row["open"]).replace(tzinfo=KST), "정확"
                except ValueError:
                    pass
        return None, None
    if m["league"] == "KBO 리그":
        for club, (days, hm) in KBO_OPEN.items():
            if norm(club) in norm(m["home"]):
                gd = datetime.strptime(m["date"], "%Y-%m-%d")
                h, mi = hm.split(":")
                return (gd - timedelta(days=days)).replace(
                    hour=int(h), minute=int(mi), tzinfo=KST), "추정"
    return None, None


# ── 알림 만들기 ───────────────────────────────────────────────────────
def fmt_match(m):
    dt = datetime.strptime(m["date"], "%Y-%m-%d")
    note = f"\n{m['note']}" if m.get("note") else ""
    return (f"{m['home']} vs {m['away']}\n"
            f"{m['date'][5:].replace('-', '/')}({WD[dt.weekday()]}) {m['time'] or '시간 미정'}"
            f" · {m['venue'] or '장소 미정'} · {m['league']}{note}")


def build_alerts(state, data, now):
    sent = state.setdefault("sent", {})
    subs = state.get("subs", [])
    if not subs:
        return []
    kovo_rows = kovo_open_times()
    today = now.date()
    alerts = []

    for m in data["matches"]:
        if m.get("finished"):
            continue
        try:
            gdate = datetime.strptime(m["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        left = (gdate - today).days
        if left < 0 or left > 15:
            continue

        hit = [r for r in subs if rule_matches(r, m)]
        if not hit:
            continue
        why = " / ".join(dict.fromkeys(rule_label(r) for r in hit))
        key = f"{m['date']}|{m['league']}|{norm(m['home'])}|{norm(m['away'])}"
        tkt = f"\n🔗 {m['ticketUrl']}" if m.get("ticketUrl") else ""

        # ① D-14 사전 알림 — 전 종목
        if left <= 14 and f"pre|{key}" not in sent:
            sent[f"pre|{key}"] = now.isoformat(timespec="seconds")
            extra = ""
            if m["league"] in ("KBL", "WKBL"):
                extra = "\n(이 리그는 예매 오픈 시각을 공개하지 않아요. 구단 공지를 확인해두세요.)"
            alerts.append(f"📅 D-{left} 사전 알림\n{fmt_match(m)}{tkt}{extra}\n조건: {why}")

        open_at, kind = find_open_time(m, kovo_rows)

        # ② 오픈 임박 — 오픈까지 24시간 이내
        if open_at and f"soon|{key}" not in sent and timedelta(0) <= (open_at - now) <= timedelta(hours=24):
            sent[f"soon|{key}"] = now.isoformat(timespec="seconds")
            tag = "" if kind == "정확" else " (구단 관행 기준 추정)"
            when = "오늘" if open_at.date() == today else "내일"
            alerts.append(f"⏰ 예매 오픈 임박 — {when} {open_at.strftime('%H:%M')}{tag}\n"
                          f"{fmt_match(m)}{tkt}\n조건: {why}")

        # ③ 예매 열림 — V리그는 오픈 시각 경과, K리그는 예매 링크 등장
        opened = (open_at and now >= open_at and kind == "정확") or \
                 (m.get("ticketKind") == "shop" and m["sport"] == "축구")
        if opened and f"open|{key}" not in sent:
            sent[f"open|{key}"] = now.isoformat(timespec="seconds")
            alerts.append(f"🎫 예매가 열렸습니다!\n{fmt_match(m)}{tkt}\n조건: {why}")

    return alerts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="발송·저장 없이 출력만")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not args.dry and (not token or not chat):
        sys.exit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없습니다. --dry 로 시험하세요.")

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() \
        else {"offset": 0, "subs": [], "sent": {}}
    data = json.loads(MATCHES.read_text(encoding="utf-8"))
    now = datetime.now(KST)
    tg = TG(token, chat, args.dry)

    sub_changed = handle_commands(tg, state) if not args.dry else False

    alerts = build_alerts(state, data, now)
    ok = 0
    for a in alerts:            # 헷갈리지 않게 경기·종류별로 따로 보낸다
        ok += 1 if tg.send(a) else 0

    # 6개월 지난 발송 기록은 청소한다
    cutoff = (now - timedelta(days=180)).isoformat()
    state["sent"] = {k: v for k, v in state["sent"].items() if v >= cutoff}

    if not args.dry:
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"구독 {len(state.get('subs', []))}건 · 알림 {len(alerts)}건 (발송 {ok})"
          + (" · 구독 변경됨" if sub_changed else ""))


if __name__ == "__main__":
    main()
