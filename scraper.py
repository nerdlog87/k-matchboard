#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""경기 일정 수집기.

대회 하나씩 어댑터를 돌리고, 하나가 실패해도 나머지는 그대로 저장한다.
어떤 대회가 몇 경기 들어왔는지 / 실패했는지를 결과 파일에 같이 남겨서
화면에서 "이 대회는 지금 비어 있습니다" 라고 말할 수 있게 한다.

대회별 상태
  ok         정상 수집
  empty      수집했지만 0경기 (대진 미발표 등, 정상)
  offseason  비시즌이라 건너뜀 — 있던 데이터는 그대로 유지
  stale      수집 실패했지만 직전 데이터가 있어 그걸 유지
  failed     수집 실패 + 대체할 데이터도 없음
  missing    0경기인데 그러면 안 되는 대회

  python scraper.py                      # 전체
  python scraper.py k3 k4                # 특정 대회만 (slug)
  python scraper.py --prev <URL 또는 경로>  # 실패 시 되돌아갈 직전 데이터
                                         # (환경변수 PREV_DATA 로도 지정 가능)
"""

import json
import os
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import adapters
from adapters import kleague
from adapters.common import http

SEASON = 2026
KST = ZoneInfo("Asia/Seoul")
HERE = Path(__file__).resolve().parent
OUT = HERE / "matches.json"


def load_prev(src):
    """직전 결과. CI 는 매번 빈 작업공간에서 시작하므로 배포된 URL 을 그대로 쓴다."""
    if not src:
        src = OUT if OUT.exists() else None
    if not src:
        return {}
    try:
        if str(src).startswith("http"):
            data = http(str(src)).json()
        else:
            data = json.loads(Path(src).read_text(encoding="utf-8"))
        print(f"  직전 데이터 불러옴: {src} ({len(data.get('matches', []))}경기)", file=sys.stderr)
        return data
    except Exception as e:
        print(f"  직전 데이터를 못 읽었습니다({src}): {e}", file=sys.stderr)
        return {}


def collect(season, only=None, prev=None):
    prev = prev or {}
    prev_matches, prev_reg = prev.get("matches") or [], prev.get("leagues") or []
    prev_by_league = {}
    for m in prev_matches:
        prev_by_league.setdefault(m["league"], []).append(m)
    prev_status = {l["name"]: l for l in prev_reg}

    today = date.today()
    matches, registry = [], []

    for comp in adapters.COMPETITIONS:
        if only and comp.slug not in only:
            continue

        kept = prev_by_league.get(comp.name, [])
        status, error, got = "ok", "", []

        if not comp.in_season(today):
            # 비시즌 — 요청 자체를 보내지 않는다. 있던 데이터는 그대로 둔다.
            got, status = kept, "offseason"
        else:
            try:
                got = comp.fetch(season, comp)
                if not got:
                    status = "empty" if comp.optional else "missing"
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
                traceback.print_exc(file=sys.stderr)
                if kept:
                    got, status = kept, "stale"      # 어제 것으로 버틴다
                else:
                    got, status = [], "failed"

        # 수집은 됐는데 직전보다 확 줄었다면 원본 쪽 사고일 수 있다. 되돌린다.
        if status == "ok" and kept and len(got) < len(kept) * 0.5:
            print(f"  ! {comp.name}: {len(kept)} -> {len(got)}경기로 급감, 직전 데이터 유지",
                  file=sys.stderr)
            got, status, error = kept, "stale", f"경기 수 급감({len(kept)}→{len(got)})"

        matches += got
        mark = {"ok": "✓", "empty": "·", "offseason": "❄", "stale": "~",
                "missing": "!", "failed": "✗"}[status]
        print(f"  {mark} {comp.name:<10} {len(got):>4}경기  {status}", file=sys.stderr)

        registry.append({
            "name": comp.name, "sport": comp.sport, "slug": comp.slug,
            "group": comp.group, "note": comp.note,
            "badge": comp.badge or comp.slug.upper(),
            "color": {"light": comp.color[0], "dark": comp.color[1]},
            "soft": {"light": comp.soft[0], "dark": comp.soft[1]},
            "count": len(got), "status": status, "error": error,
            # 마지막으로 실제 수집에 성공한 시각. 화면에서 "언제 것인지" 밝히는 데 쓴다.
            "fetchedAt": datetime.now(KST).isoformat(timespec="seconds")
            if status in ("ok", "empty")
            else (prev_status.get(comp.name, {}) or {}).get("fetchedAt", ""),
        })

    # 특정 대회만 돌린 경우, 건드리지 않은 대회는 직전 것을 그대로 살린다.
    if only:
        done = {r["name"] for r in registry}
        for l in prev_reg:
            if l["name"] not in done:
                registry.append(l)
                matches += prev_by_league.get(l["name"], [])
        order = [c.name for c in adapters.COMPETITIONS]
        registry.sort(key=lambda r: order.index(r["name"]) if r["name"] in order else 99)

    seen, deduped = set(), []
    for m in matches:
        k = (m["league"], m["date"], m["time"], m["home"], m["away"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(m)
    deduped.sort(key=lambda m: (m["date"], m["time"], m["league"]))
    return deduped, registry


def main():
    args = sys.argv[1:]
    prev_src = os.environ.get("PREV_DATA") or ""
    if "--prev" in args:
        i = args.index("--prev")
        prev_src = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]

    prev = load_prev(prev_src)
    matches, registry = collect(SEASON, set(args) or None, prev)

    payload = {
        "season": SEASON,
        "generatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "sports": list(dict.fromkeys(c["sport"] for c in registry)),
        "leagues": registry,
        "homepages": kleague.homepages() or prev.get("homepages") or {},
        "matches": matches,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장 완료: {OUT}  (총 {len(matches)}경기)", file=sys.stderr)


if __name__ == "__main__":
    main()
