"""Render recorded results; missing measurements remain explicitly unmeasured."""
import argparse
import json
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('input',type=Path)
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'docs/BENCHMARK_RESULT.md')
args=parser.parse_args()
data=json.loads(args.input.read_text())
m=data['metadata']; summary=data['summary']
quality=m.get('quality_measurement') is True and m.get('mode')=='openai'
def metric(v, percent=False):
    if v is None:return '미측정'
    return f'{v*100:.1f}%' if percent else f'{v:,.2f}'
lines=['# 개선 전후 비교 실행 결과','',f"- 실행 시각: {m['created_at']}",
       f"- 실행 모드: **{m['mode']}**",f"- 데이터: {m['case_count']}개 × {m['repeat']}회, 각 조건 동일 입력",
       f"- 임베딩: `{m['embedding_model']}`",f"- 판단 모델: `{m.get('model') or '미사용'}`",'']
if not quality:lines+=['> 데모 검색의 연결과 결과 저장을 확인한 기록입니다. 의미 검색 정확도나 실제 API 비용·속도의 개선 근거로 사용할 수 없습니다.','']
lines+=['| 측정 항목 | Before: 전체 20개 정책 | After: 검색 상위 4개 |','|---|---:|---:|']
for label,key,percent in [('시도 횟수','attempts',False),('정상 처리 횟수','successful',False),
                         ('평균 정책 문서 수','mean_context_docs',False),('평균 정책 원문 문자 수','mean_context_chars',False),
                         ('평균 정책 JSON 토큰 수 (cl100k, 과금량 아님)','mean_context_tokens_cl100k',False),
                         ('기대 정책 포함률 (Before 전체 범위 / After Recall@4)','expected_recall',True),
                         ('문맥 정밀도','context_precision',True),
                         ('정책 준수 판정 정답률 (실패 포함)','judge_accuracy_all_attempts',True),
                         ('평균 처리 시간 ms (실패 포함)','mean_elapsed_ms_all_attempts',False)]:
    lines.append('| '+label+' | '+' | '.join(metric(summary[v].get(key),percent) for v in ('before','after'))+' |')
lines+=['','## 해석과 비교 조건','',
        '- Before는 과거 앱의 실측 기록이 아니라, 같은 20개 정책을 모두 주입하는 통제 실험 기준선입니다. 과거 앱은 시나리오별 정책 3~4개를 직접 주입했습니다.',
        '- 질문·상담사 답변·판정 프롬프트·모델·문서 버전은 동일하고 문서 선택 방식만 다릅니다. 실행 순서는 교차 배치했습니다.',
        '- Before 전체 문서의 포함률은 범위 확인용입니다. 상위 4개 검색과 같은 검색 정확도 지표로 해석하면 안 됩니다.',
        '- `--judge`를 사용해야 실제 판단 결과와 LLM 사용량이 생깁니다. 미사용 시 시간은 문맥 준비/검색 시간이며 상담 평가 전체 지연이 아닙니다.',
        '- 신규 인덱스 생성 비용과 캐시 재사용은 각 행의 retrieval.index_cache_hit, index_ms, embedding_usage에서 구분합니다.',
        '- 각 모델의 실제 과금 토큰은 원본 rows[].usage에, 임베딩 토큰은 rows[].retrieval.embedding_usage에 따로 보존합니다. 문서 JSON 로컬 토큰 수와 구분합니다.',
        '- 12개 자체 작성 예제와 반복 측정으로 일반화 성능·전문가 일치도·상담 역량 향상을 입증할 수 없습니다. 반복 횟수가 늘어도 독립 사례 수는 12개입니다.',
        '- 검색 실패는 포함률·정밀도 계산에서 0점으로 반영하고 문맥 길이 평균은 생성된 문맥에서 계산합니다. 실패한 요청은 정상 처리 횟수에서 제외하고, 전체 시도 기준 정답률에는 실패로 반영합니다. 제공자 SDK는 네트워크 오류에 최대 1회 재시도합니다.',
        '',f"- 코퍼스 해시: `{m['corpus_hash']}`",f"- 데이터셋 해시: `{m['dataset_sha256']}`",'',
        '원본 JSON은 실행 시 지정한 파일에 저장됩니다. 제출 저장소에는 해당 JSON도 함께 올리세요.']
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text('\n'.join(lines)+'\n')
print(args.output)
