#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""matches.json 무결성 점검.

수집기가 조용히 이상한 값을 넣고 지나가는 걸 막는다.
새 리그·새 종목을 붙인 다음에는 반드시 이걸 돌려볼 것.

  python check.py
"""

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

DATA = json.loads((Path(__file__).resolve().parent / "matches.json").read_text(encoding="utf-8"))
MS = DATA["matches"]
REG = DATA["leagues"]

problems, warnings = [], []


def check(cond, msg, hard=True):
    if not cond:
        (problems if hard else warnings).append(msg)


# 1. 필수 필드
for m in MS:
    tag = f"{m['date']} {m['league']} {m['home']}-{m['away']}"
    check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", m["date"]), f"날짜 형식 이상: {tag}")
    check(re.fullmatch(r"\d{2}:\d{2}", m["time"] or ""), f"시간 형식 이상: {tag}", hard=False)
    check(bool(m["home"] and m["away"]), f"팀명 비어 있음: {tag}")
    check(bool(m["venue"]), f"경기장 비어 있음: {tag}", hard=False)
    check(m["league"] in {l["name"] for l in REG}, f"등록되지 않은 리그: {m['league']}")

# 2. 점수와 종료 상태가 어긋나지 않는지
for m in MS:
    tag = f"{m['date']} {m['league']} {m['home']}-{m['away']}"
    if m["finished"] and m["homeGoal"] is None:
        check(bool(m["note"]), f"종료인데 점수도 설명도 없음: {tag}")
    if not m["finished"]:
        check(m["homeGoal"] is None, f"미종료인데 점수가 있음: {tag}")
    if m["date"] > date.today().isoformat():
        check(not m["finished"], f"미래 경기인데 종료 표시: {tag}")

# 3. 같은 팀끼리 붙는 경기 (원본 오류) 는 설명이 달려 있어야 한다
for m in MS:
    if m["home"] == m["away"]:
        check(bool(m["note"]), f"홈·원정이 같은데 설명 없음: {m['date']} {m['league']} {m['home']}")

# 4. 중복
dup = [k for k, n in Counter((m["league"], m["date"], m["time"], m["home"], m["away"])
                             for m in MS).items() if n > 1]
check(not dup, f"중복 경기 {len(dup)}건: {dup[:3]}")

# 5. 리그별 라운드당 경기 수가 고르게 나오는지 (편성 누락 감지)
for l in REG:
    ms = [m for m in MS if m["league"] == l["name"] and m["round"]]
    if len(ms) < 20 or l["group"] == "컵대회":
        continue
    per = Counter(m["round"] for m in ms)
    common = Counter(per.values()).most_common(1)[0][0]
    odd = {r: n for r, n in per.items() if n != common}
    check(not odd, f"{l['name']} 라운드별 경기 수 불균일 (기준 {common}): {odd}", hard=False)

# 6. 대회별 수집 상태
for l in REG:
    check(l["status"] != "failed", f"{l['name']} 수집 실패 + 대체 데이터 없음: {l['error']}")
    check(l["status"] != "missing", f"{l['name']} 경기 0건 (예상 밖)")
    # stale/offseason 은 의도된 상태다. 실패가 아니라 알림으로 남긴다.
    check(l["status"] != "stale",
          f"{l['name']} 수집 실패 — 직전 데이터 유지 중 ({l['error']})", hard=False)
    check(l["status"] != "offseason",
          f"{l['name']} 비시즌이라 건너뜀 (기존 {l['count']}경기 유지)", hard=False)

# ── 결과 ──
print(f"경기 {len(MS)}건 / 대회 {len(REG)}개 / 기준 {DATA['generatedAt']}")
for l in REG:
    print(f"  {l['status']:<8} {l['name']:<12} {l['count']:>4}경기")

for w in warnings:
    print(f"  ! {w}")
for p in problems:
    print(f"  ✗ {p}")

print("\n통과" if not problems else f"\n실패 — 문제 {len(problems)}건")
sys.exit(1 if problems else 0)
