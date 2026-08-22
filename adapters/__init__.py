# -*- coding: utf-8 -*-
"""수집 어댑터 모음.

새 리그·새 종목을 붙이려면 이 폴더에 모듈 하나를 더 만들고
COMPETITIONS 리스트를 노출한 뒤, 아래 MODULES 에 추가하면 된다.
수집기 본체(scraper.py)는 손댈 필요가 없다.
"""

from . import kfa, kleague

MODULES = [kleague, kfa]

COMPETITIONS = [c for m in MODULES for c in m.COMPETITIONS]
