# GitHub 자동 갱신 붙이기

git 명령을 몰라도 **웹 브라우저만으로** 끝납니다. 10분쯤 걸립니다.

---

## 1. 저장소 만들기

1. <https://github.com> 로그인 (계정이 없으면 가입)
2. 오른쪽 위 **＋ → New repository**
3. 이렇게 채웁니다
   - **Repository name** — `k-matchboard` (원하는 이름으로 바꾸셔도 됩니다)
   - **Public** 선택 ← **중요**. Private 은 GitHub Pages 가 유료 플랜에서만 됩니다.
   - "Add a README file" 은 **체크하지 않기**
4. **Create repository**

## 2. 파일 올리기

만들어진 저장소 화면에서 **uploading an existing file** 링크를 누릅니다.

`k1-k4-매치보드` 폴더 안의 아래 항목을 창에 끌어다 놓습니다.

```
adapters/          ← 폴더째로
scraper.py
check.py
build.py
template.html
matches.json
requirements.txt
.gitignore
README.md
SETUP.md
```

> `dist/` 폴더는 **올리지 마세요.** 실행할 때마다 자동으로 만들어집니다.

아래 **Commit changes** 를 누릅니다.

## 3. 워크플로 파일 올리기 (따로 해야 합니다)

`.github` 처럼 점으로 시작하는 폴더는 윈도우 탐색기에서 숨겨져 있어
끌어다 놓기가 잘 안 됩니다. 웹에서 직접 만드는 게 확실합니다.

1. 저장소 첫 화면에서 **Add file → Create new file**
2. 파일 이름 칸에 아래를 **그대로** 입력합니다. `/` 를 칠 때마다 폴더가 자동으로 생깁니다.
   ```
   .github/workflows/update.yml
   ```
3. 내려받으신 `update.yml` 파일을 메모장으로 열어 **전체 복사 → 붙여넣기**
4. **Commit changes**

## 4. Pages 켜기

1. 저장소 상단 **Settings** → 왼쪽 메뉴 **Pages**
2. **Source** 를 `Deploy from a branch` 가 아니라 **`GitHub Actions`** 로 바꿉니다

## 5. 첫 실행

1. 상단 **Actions** 탭 → 왼쪽에서 **경기 일정 갱신** 선택
2. 오른쪽 **Run workflow** → 초록 **Run workflow** 버튼
3. 3~4분 기다립니다. 초록 체크가 뜨면 성공입니다.
4. **Settings → Pages** 로 돌아가면 맨 위에 주소가 나옵니다

   ```
   https://<깃허브아이디>.github.io/k-matchboard/
   ```

이 주소를 블로그 글에 넣으시면 됩니다. 데이터도 함께 열려 있습니다.

```
https://<깃허브아이디>.github.io/k-matchboard/matches.json
```

---

## 이제 알아서 굴러갑니다

| 시각(한국) | 하는 일 |
|---|---|
| 매일 **06:00** | 일정 변경 반영 + `matches.json` 커밋 |
| 매일 **23:30** | 밤경기 결과 반영 |

급하게 지금 갱신하고 싶으면 언제든 **Actions → 경기 일정 갱신 → Run workflow**.

## 알아두실 점

- **예약 시간은 몇 분에서 몇십 분 늦을 수 있습니다.** GitHub 무료 플랜의 예약 실행은
  "정확히 그 시각"이 아니라 "그 즈음"입니다. 일정 보는 용도라 문제되진 않습니다.
- **60일 규칙** — GitHub 은 저장소에 아무 활동이 없으면 예약 워크플로를 자동으로 끕니다.
  그래서 06:00 실행이 하루 한 번 `matches.json` 을 커밋하도록 해뒀습니다. 이게 활동으로 잡혀서
  계속 살아 있습니다. 그래도 중지 안내 메일이 오면 Actions 탭에서 **Enable workflow** 를 누르면 됩니다.
- **원본이 죽어도 화면이 비지 않습니다.** 어떤 대회 수집이 실패하면 그 대회만 직전 데이터를
  그대로 쓰고, 화면 아래에 `⚠ K3리그 — 원본에서 못 받아와 8월 20일 자료를 보여주고 있습니다`
  처럼 표시합니다. 나머지 대회는 정상 갱신됩니다.
- **이상한 데이터는 배포되지 않습니다.** `check.py` 가 걸리면 워크플로가 거기서 멈추고,
  이미 올라가 있던 페이지가 그대로 유지됩니다.
- **비시즌 대회는 건너뜁니다.** 어댑터에 활동 기간이 적혀 있어서, 시즌이 아닌 대회는
  요청조차 보내지 않고 기존 일정을 그대로 둡니다. 개막일이 되면 알아서 다시 들어옵니다.
- **사용량** — 한 번에 3~4분, 하루 2번이면 월 200분 남짓입니다.
  Public 저장소는 Actions 가 무제한 무료라 요금 걱정은 없습니다.
