"""Unauthenticated content check for a GitHub Markdown report URL.
python scripts/check_public_report.py https://github.com/OWNER/REPO/blob/main/PROJECT_REPORT.md
Also open the same URL in a signed-out/incognito browser before submission.
"""
import argparse
from urllib.parse import urlparse
import httpx
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('url')
args=parser.parse_args()
u=urlparse(args.url)
parts=u.path.strip('/').split('/')
if u.scheme!='https' or u.netloc!='github.com' or len(parts)<5 or parts[2]!='blob':
    parser.error('Use a GitHub report file URL: https://github.com/OWNER/REPO/blob/main/PROJECT_REPORT.md')
owner,repo,_,ref,*path=parts
with httpx.Client(timeout=30,follow_redirects=True,trust_env=False) as client:
    meta=client.get(f'https://api.github.com/repos/{owner}/{repo}')
    if meta.status_code!=200 or meta.json().get('private',True):
        raise SystemExit('공개 저장소로 확인되지 않았습니다. 저장소 공개 설정과 URL을 확인하세요.')
    report=client.get('https://raw.githubusercontent.com/'+owner+'/'+repo+'/'+ref+'/'+'/'.join(path))
    if report.status_code!=200 or '# 응대 리허설' not in report.text or '교훈' not in report.text:
        raise SystemExit('인증 없는 요청으로 보고서 원문을 확인하지 못했습니다.')
    print('인증 없는 HTTP 요청으로 공개 저장소와 보고서 본문 접근을 확인했습니다.')
    print('제출 전 동일 URL을 시크릿 브라우저에서도 열어 표·흐름도·첨부 링크를 확인하세요.')
