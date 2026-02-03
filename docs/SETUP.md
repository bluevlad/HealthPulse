# 개발환경 설정 가이드

## 1. Windows 터미널 환경 설정

### 1.1 터미널 비교

| 항목 | CMD | PowerShell | Windows Terminal |
|------|:---:|:---:|:---:|
| 유니코드/한글 지원 | △ | ○ | ◎ |
| 복사/붙여넣기 | △ | ○ | ◎ |
| 탭 기능 | ✗ | ✗ | ◎ |
| 스크롤 버퍼 | 제한적 | 보통 | 우수 |
| 색상/테마 | 제한적 | 보통 | 우수 |

### 1.2 권장: Windows Terminal + PowerShell

```powershell
# Windows Terminal 설치
winget install Microsoft.WindowsTerminal
```

### 1.3 PowerShell 인코딩 설정 (한글 깨짐 방지)

PowerShell 프로필 파일 편집:
```powershell
# 프로필 경로 확인
echo $PROFILE

# 프로필 편집 (없으면 생성)
notepad $PROFILE
```

프로필에 추가할 내용:
```powershell
# UTF-8 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# 프로젝트 폴더 별칭 (선택사항)
function hp { Set-Location C:\GIT\HealthPaulse }
```

### 1.4 Windows Terminal 권장 설정

설정 파일 위치: `%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`

```json
{
    "profiles": {
        "defaults": {
            "font": {
                "face": "Cascadia Code",
                "size": 11
            },
            "scrollbarState": "visible",
            "padding": "8"
        }
    },
    "theme": "dark"
}
```

---

## 2. Python 환경 설정

### 2.1 Python 설치

```powershell
# Python 3.10+ 설치 (winget 사용)
winget install Python.Python.3.11

# 설치 확인
python --version
pip --version
```

### 2.2 가상환경 생성

```powershell
# 프로젝트 폴더로 이동
cd C:\GIT\HealthPaulse

# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (PowerShell)
.\venv\Scripts\Activate.ps1

# 가상환경 활성화 (CMD)
.\venv\Scripts\activate.bat
```

### 2.3 PowerShell 실행 정책 (필요시)

```powershell
# 스크립트 실행 허용 (관리자 권한 필요)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 3. 필수 패키지 설치

### 3.1 requirements.txt

```text
# 웹 프레임워크
fastapi==0.109.0
uvicorn==0.27.0

# HTTP 클라이언트
requests==2.31.0
httpx==0.26.0

# 웹 크롤링
beautifulsoup4==4.12.3
lxml==5.1.0

# 데이터베이스
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
redis==5.0.1

# AI/ML
openai==1.10.0
anthropic==0.18.0
sentence-transformers==2.3.1

# 스케줄러
apscheduler==3.10.4

# 이메일
emails==0.6

# 유틸리티
python-dotenv==1.0.0
pydantic==2.5.3
jinja2==3.1.3

# 개발/테스트
pytest==7.4.4
black==24.1.1
flake8==7.0.0
```

### 3.2 패키지 설치

```powershell
# 가상환경 활성화 확인
# (venv) 표시가 있어야 함

# 패키지 설치
pip install -r requirements.txt
```

---

## 4. 네이버 API 설정

### 4.1 API 키 발급

1. [네이버 개발자 센터](https://developers.naver.com) 접속
2. 애플리케이션 등록
3. 검색 API 사용 신청
4. Client ID / Client Secret 발급

### 4.2 환경변수 설정

`.env` 파일 생성:
```env
# 네이버 API
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret

# AI API (택일)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# 데이터베이스
DATABASE_URL=postgresql://user:password@localhost:5432/healthpulse

# 이메일 (AWS SES)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=ap-northeast-2
SENDER_EMAIL=noreply@yourdomain.com
```

**주의**: `.env` 파일은 절대 Git에 커밋하지 마세요!

### 4.3 .gitignore 설정

```gitignore
# 환경변수
.env
.env.local
.env.*.local

# 가상환경
venv/
.venv/

# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp

# 로그
*.log
logs/

# 테스트
.pytest_cache/
.coverage
htmlcov/
```

---

## 5. 데이터베이스 설정

### 5.1 PostgreSQL 설치 (로컬 개발용)

```powershell
# Docker 사용 (권장)
docker run --name healthpulse-db \
  -e POSTGRES_USER=healthpulse \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=healthpulse \
  -p 5432:5432 \
  -d postgres:15
```

### 5.2 Redis 설치 (선택사항)

```powershell
# Docker 사용
docker run --name healthpulse-redis \
  -p 6379:6379 \
  -d redis:7
```

---

## 6. IDE 설정

### 6.1 VS Code 권장 확장

```json
// .vscode/extensions.json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.black-formatter",
        "charliermarsh.ruff",
        "mtxr.sqltools"
    ]
}
```

### 6.2 VS Code 설정

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true
}
```

---

## 7. 프로젝트 구조 생성

```powershell
# 프로젝트 폴더 구조 생성
cd C:\GIT\HealthPaulse

# 폴더 생성
mkdir src\crawler
mkdir src\processor
mkdir src\reporter
mkdir src\mailer
mkdir templates
mkdir config
mkdir tests
mkdir logs

# __init__.py 생성
New-Item -ItemType File -Path src\__init__.py
New-Item -ItemType File -Path src\crawler\__init__.py
New-Item -ItemType File -Path src\processor\__init__.py
New-Item -ItemType File -Path src\reporter\__init__.py
New-Item -ItemType File -Path src\mailer\__init__.py
New-Item -ItemType File -Path tests\__init__.py
```

---

## 8. 실행 확인

### 8.1 환경 테스트

```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# Python 확인
python -c "import sys; print(f'Python {sys.version}')"

# 패키지 확인
pip list

# 환경변수 로드 테스트
python -c "from dotenv import load_dotenv; load_dotenv(); print('OK')"
```

### 8.2 네이버 API 테스트

```python
# test_naver_api.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = "https://openapi.naver.com/v1/search/news.json"
headers = {
    "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
    "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET")
}
params = {"query": "디지털헬스케어", "display": 5}

response = requests.get(url, headers=headers, params=params)
print(f"Status: {response.status_code}")
print(f"Results: {len(response.json().get('items', []))}")
```

```powershell
python test_naver_api.py
```

---

## 9. 문제 해결

### 9.1 한글 깨짐
```powershell
# PowerShell에서 UTF-8 강제 설정
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### 9.2 가상환경 활성화 오류
```powershell
# 실행 정책 변경
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 9.3 pip 설치 오류
```powershell
# pip 업그레이드
python -m pip install --upgrade pip

# 특정 패키지 설치 실패 시
pip install --no-cache-dir package_name
```
