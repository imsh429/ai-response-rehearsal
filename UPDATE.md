# RAG·측정·보고서 업데이트 적용

이 ZIP은 변경·추가 파일만 담은 업데이트입니다. 기존 프로젝트의 폴더 구조에 덮어씁니다. `.env`, 훈련 DB, 가상환경은 포함하지 않았습니다.

## macOS / VS Code

1. 기존 서버 터미널에서 **Ctrl+C**로 서버를 종료합니다.
2. 다운로드한 파일 이름을 `response-rehearsal-rag-update.zip`으로 유지합니다.
3. VS Code에서 기존 `response-rehearsal` 폴더를 연 뒤 아래 명령을 실행합니다. 압축 파일이 Downloads에 있을 때의 명령입니다.

```bash
cd ~/workspace/response-rehearsal
source .venv/bin/activate
unzip -o ~/Downloads/response-rehearsal-rag-update.zip -d .
python -m pip install -r requirements.txt
python scripts/check_setup.py
python run.py
```

ZIP 최상위에는 `backend`, `frontend`, `scripts`, `docs` 등이 있습니다. 기존 프로젝트 안에 `response-rehearsal` 폴더를 한 번 더 만들지 마세요. 위 명령은 대응하는 소스와 화면 파일을 덮어씁니다. 별도로 직접 수정한 코드가 있으면 먼저 프로젝트 폴더를 복사해 두세요.

기존 `backend/.env`를 유지합니다. 새 키를 발급할 필요 없이 **기존 OPENAI_API_KEY**를 임베딩에도 사용합니다. `.env.example`을 기존 `.env`로 다시 복사하지 마세요. 새 임베딩 모델 설정을 생략하면 `text-embedding-3-small`이 기본입니다. 해당 임베딩 모델을 사용할 수 있는 API 권한·크레딧은 필요합니다.

브라우저에서 `http://127.0.0.1:8000`을 열고 **⌘+Shift+R**로 새로고침합니다. 기존 훈련은 보존되지만, 새 20개 정책 코퍼스는 **새로 시작한 훈련**부터 적용됩니다. 기존 세션은 자신의 정책 버전을 유지합니다. 프롬프트 버전이 바뀐 이전 세션은 직접 재도전할 수 없으므로 대시보드에서 새 훈련을 시작하세요.

## 화면에서 확인

1. 새 배송 지연 훈련을 시작합니다.
2. 회사 정책 탭 → `출고 전 취소와 배송 지연 보상` 입력 → **관련 정책 검색**.
3. OpenAI 모드라면 **의미 검색 · 4개 / 20개 정책**이 표시되는지 확인합니다.
4. 주문·이력도 조회하고 상담을 진행한 뒤 평가합니다.
5. 리포트의 **평가에 사용한 정책 검색 근거**를 펼칩니다.

최초 검색에는 문서 임베딩과 인덱스 생성이 필요합니다. 같은 문서·임베딩 모델에서는 인덱스를 재사용하고, 검색어 임베딩은 매번 호출합니다. 실제 API 비용이 발생합니다. 오류가 나면 전체 정책이나 데모로 조용히 대체하지 않고 조회·평가 오류로 표시합니다.

## 실제 API 전체 점검 (선택, 과금)

서버를 실행한 상태에서 VS Code의 별도 터미널을 열고 프로젝트 루트에서 실행합니다.

```bash
source .venv/bin/activate
python scripts/smoke_openai.py
```

실제 주문 조회 → OpenAI 임베딩 검색 → 고객 스트리밍 → 평가·코칭을 확인합니다. 실패 시 출력과 서버 상태를 확인하세요. 키를 채팅에 붙여 넣지 마세요.

## 제출용 실제 측정

프로젝트 루트의 별도 터미널에서 실행합니다. 서버 실행 여부와 무관하며 벤치마크는 별도 Chroma 경로를 사용합니다.

```bash
source .venv/bin/activate
# 먼저 검색 연결을 확인: 임베딩 API만 호출
python scripts/benchmark_rag.py --repeat 1

# 연결 성공 후 정책 판단까지 Before/After 비교: 유료 호출
python scripts/benchmark_rag.py --repeat 3 --judge
python scripts/render_benchmark_report.py docs/results/rag-benchmark.json
```

두 번째 명령은 기본 72회 판정을 실행하며, 모델의 구조화 응답 처리와 네트워크 재시도로 제공자 요청 수가 달라질 수 있습니다. 비용 추정치를 임의로 제시하지 않습니다. `--repeat 1 --judge`는 24회로 먼저 점검할 수 있습니다.

API 키 없이 기능만 점검하려면 `python scripts/benchmark_rag.py --demo --output docs/results/rag-demo-smoke.json`을 사용합니다. 이 결과는 의미 검색 품질·실제 API 비용의 증거가 아닙니다.

## 보고서와 공개 링크

- 완성된 보고서: **`PROJECT_REPORT.md`**. 필수 5개 항목, 흐름도, 기술 적용, 시연, 검증, 한계·교훈 포함.
- 실제 수치 표: **`docs/BENCHMARK_RESULT.md`**. 위 생성 명령을 실행하면 갱신됩니다.
- 원본 측정 데이터: **`docs/results/rag-benchmark.json`**. 실제 측정 전에는 없습니다.
- 발표 구성: **`docs/PRESENTATION_NOTES.md`**.

보고서 표지의 소속·반·고유번호·이름·제출일은 실제 값으로 채우세요. 문서의 공개 URL도 공개 저장소에 올린 후 입력합니다. 실제 API 측정이 끝나면 보고서 4.5절의 현재 데모 상태 설명을 실제 실행 결과에 맞게 고치고, 원본 JSON과 함께 제출하세요. 수치가 없으면 미측정 상태를 유지합니다.

과제 링크는 공개 GitHub 보고서 URL로 제출할 수 있습니다. 전체 프로젝트를 올릴 경우 루트 `.gitignore`를 유지하고 `.env`나 데이터 폴더는 올리지 마세요. 새 Chroma 파일도 `backend/data/` 아래라 Git 제외됩니다. 기존 저장소가 없다면 GitHub에서 Public 저장소를 만들고 VS Code Git으로 소스를 커밋·푸시한 뒤 `PROJECT_REPORT.md`를 여세요.

```bash
python scripts/check_public_report.py https://github.com/OWNER/REPO/blob/main/PROJECT_REPORT.md
```

위 URL은 형식 예시이므로 자신의 공개 문서 URL로 바꿉니다. 시크릿 창에서도 문서와 연결 문서가 보이는지 확인합니다. 현재 업데이트 파일에는 실제로 생성·검증한 외부 공개 링크가 없습니다.

## 설치가 실패한다면

`python --version`과 `python -m pip --version`을 확인하여 가상환경 Python을 쓰고 있는지 확인하세요. Linux/Python 3.12 환경에서 설치·검증했으며, 실제 macOS/Python 3.11 설치는 이 환경에서 수행하지 못했습니다. 설치 오류 전문을 전달하면 해당 의존성 문제만 수정할 수 있습니다. `Permission denied`가 나도록 `.py` 파일 경로 자체를 터미널에서 실행하지 말고 안내된 `python ...` 명령을 사용하세요.
