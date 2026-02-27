# 설치 메뉴얼 — Process Mining Application

**버전**: 1.0.0
**지원 OS**: macOS, Windows 10/11, Ubuntu 20.04+

---

## 사전 요구사항

| 항목 | 최소 버전 | 확인 방법 |
|------|-----------|-----------|
| Python | 3.9 이상 | `python3 --version` |
| pip | 21 이상 | `pip3 --version` |
| graphviz (시스템) | 2.50 이상 | `dot -V` |
| Git | 2.x | `git --version` |

---

## 설치 절차

### 1단계: 저장소 클론

```bash
git clone https://github.com/your-org/ProcessEng.git
cd ProcessEng
```

### 2단계: 가상 환경 생성

```bash
# .venv 가상 환경 생성
python3 -m venv .venv
```

### 3단계: 가상 환경 활성화

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (명령 프롬프트):**
```cmd
.venv\Scripts\activate.bat
```

활성화되면 터미널 프롬프트 앞에 `(.venv)` 표시가 나타납니다.

### 4단계: Python 패키지 설치

```bash
pip install -r requirements.txt
```

> 설치에는 2~5분 정도 소요될 수 있습니다 (pm4py 의존성 포함).

### 5단계: graphviz 시스템 패키지 설치

graphviz는 Python 패키지 외에 **시스템 바이너리**가 별도로 필요합니다.

**macOS (Homebrew):**
```bash
brew install graphviz
```

**Ubuntu / Debian:**
```bash
sudo apt-get install graphviz
```

**Windows:**
1. https://graphviz.org/download/ 접속
2. Windows용 설치 파일(`.exe`) 다운로드 및 실행
3. 설치 중 "Add Graphviz to PATH" 옵션 체크 (중요!)
4. 설치 완료 후 새 터미널 열기

**설치 확인:**
```bash
dot -V
# 예: dot - graphviz version 10.0.1 (...)
```

### 6단계: 샘플 데이터 생성 (선택)

내장 샘플 데이터가 이미 포함되어 있지만, 재생성이 필요한 경우:

```bash
python3 sample_data/generate_samples.py
```

### 7단계: 앱 실행

```bash
streamlit run app/main.py
```

브라우저가 자동으로 열리며 다음 주소로 접속됩니다:
```
http://localhost:8501
```

자동으로 열리지 않으면 위 주소를 브라우저에 직접 입력하세요.

---

## 가상 환경 없이 실행하는 경우

> **권장하지 않습니다.** 다른 Python 프로젝트와 패키지 충돌이 발생할 수 있습니다.

```bash
pip3 install -r requirements.txt
streamlit run app/main.py
```

---

## 종료 방법

Streamlit 서버를 종료하려면 터미널에서 `Ctrl + C`를 누릅니다.

가상 환경을 비활성화하려면:
```bash
deactivate
```

---

## 재실행 방법

다음 번 실행 시:

**macOS / Linux:**
```bash
cd ProcessEng
source .venv/bin/activate
streamlit run app/main.py
```

**Windows:**
```cmd
cd ProcessEng
.venv\Scripts\activate.bat
streamlit run app/main.py
```

---

## 문제 해결

### 문제: `ModuleNotFoundError: No module named 'pm4py'`

가상 환경이 활성화되지 않았거나 패키지가 설치되지 않았습니다.

```bash
source .venv/bin/activate   # 가상 환경 활성화
pip install -r requirements.txt  # 패키지 재설치
```

---

### 문제: `ExecutableNotFound: failed to execute PosixPath('dot')`

graphviz 시스템 패키지가 설치되지 않았습니다.

**macOS:**
```bash
brew install graphviz
```

**설치 후에도 오류가 지속되면:**
```bash
# graphviz 경로 확인
which dot
# /usr/local/bin/dot 또는 /opt/homebrew/bin/dot

# 경로가 PATH에 없는 경우 (~/.zshrc 또는 ~/.bashrc에 추가)
export PATH="/opt/homebrew/bin:$PATH"
source ~/.zshrc
```

---

### 문제: `UnicodeDecodeError` (CSV 로딩 실패)

한글 인코딩 문제입니다. 파일을 UTF-8로 재저장하세요.

**Excel에서 저장하는 방법:**
1. 파일 열기
2. 다른 이름으로 저장 → CSV UTF-8 (쉼표로 구분)
3. 저장된 파일 다시 업로드

---

### 문제: Streamlit 포트 충돌 (`Port 8501 is already in use`)

```bash
# 다른 포트로 실행
streamlit run app/main.py --server.port 8502
```

---

### 문제: Python 3.9 미만 버전 오류

```bash
# 현재 Python 버전 확인
python3 --version

# pyenv를 통해 Python 3.11 설치 (macOS)
brew install pyenv
pyenv install 3.11
pyenv local 3.11
python3 -m venv .venv
```

---

### 문제: Windows에서 graphviz PATH 미인식

1. 시작 메뉴 → "환경 변수 편집" 검색
2. 시스템 변수 → `Path` 선택 → 편집
3. `C:\Program Files\Graphviz\bin` 추가 (graphviz 설치 경로에 따라 다름)
4. 새 명령 프롬프트 열고 `dot -V` 확인

---

## 패키지 버전 정보

`requirements.txt` 기준:

```
streamlit>=1.32.0
pm4py>=2.7.0
pandas>=2.0.0
openpyxl>=3.1.0
plotly>=5.18.0
graphviz>=0.20.0
numpy>=1.24.0
networkx>=3.0
```

설치된 버전 확인:
```bash
pip list | grep -E "streamlit|pm4py|pandas|plotly|graphviz|networkx"
```

---

## 디렉토리 구조 확인

정상 설치 후 프로젝트 구조:

```
ProcessEng/
├── .venv/                    ← 가상 환경 (자동 생성)
├── app/
│   ├── main.py
│   └── core/
│       ├── __init__.py
│       ├── loader.py
│       ├── column_mapper.py
│       ├── miner.py
│       ├── stats.py
│       └── visualizer.py
├── docs/
│   ├── design_document.md
│   ├── installation_manual.md    ← 이 문서
│   ├── user_manual.md
│   ├── process_discovery_algorithms.md
│   ├── column_mapping_design.md
│   └── sample_data_guide.md
├── sample_data/
│   ├── purchase_process.csv
│   ├── purchase_process.xlsx
│   ├── running_example.csv
│   └── generate_samples.py
└── requirements.txt
```

---

## 빠른 설치 요약 (macOS)

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/ProcessEng.git && cd ProcessEng

# 2. graphviz 설치
brew install graphviz

# 3. 가상 환경 생성 및 패키지 설치
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. 앱 실행
streamlit run app/main.py
```

---

*최종 수정: 2026-02-28*
