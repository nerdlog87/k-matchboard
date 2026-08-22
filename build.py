#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
template.html + matches.json  ->  dist/index.html (단독 실행용 / GitHub Pages)
                             ->  dist/artifact.html (Artifact 배포용 조각)
데이터를 파일 안에 그대로 박아 넣기 때문에 어디에 올려도 그냥 열린다.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
DIST.mkdir(exist_ok=True)

tpl = (HERE / "template.html").read_text(encoding="utf-8")
data = json.loads((HERE / "matches.json").read_text(encoding="utf-8"))

# 뷰어가 쓰지 않는 필드는 덜어내서 파일 크기를 줄인다.
slim = {
    "season": data["season"],
    "generatedAt": data["generatedAt"],
    "sports": data["sports"],
    "leagues": data["leagues"],
    "matches": [
        {k: m[k] for k in
         ("sport", "league", "date", "time", "round", "home", "away", "venue",
          "finished", "homeGoal", "awayGoal", "broadcast", "note")}
        for m in data["matches"]
    ],
}
payload = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))

full = re.sub(r"/\*__MATCHES__\*/.*?/\*__END__\*/", lambda _: payload, tpl, flags=re.S)
(DIST / "index.html").write_text(full, encoding="utf-8")

# Artifact 는 <head>/<body> 껍데기를 자기가 씌우므로 알맹이만 뽑는다.
head = full.split("<!--HEAD_START-->")[1].split("<!--HEAD_END-->")[0]
body = full.split("<!--BODY_START-->")[1].split("<!--BODY_END-->")[0]
(DIST / "artifact.html").write_text(head + body, encoding="utf-8")

# 데이터도 같이 배포한다. 다음 실행에서 "직전 상태"로 되돌아갈 근거가 되고,
# 덤으로 공개 JSON 엔드포인트가 된다.
(DIST / "matches.json").write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

for f in ("index.html", "artifact.html", "matches.json"):
    print(f"dist/{f}  {(DIST / f).stat().st_size / 1024:,.0f} KB")
print(f"경기 {len(slim['matches'])}건")
