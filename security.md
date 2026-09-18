# 프로젝트 보안 및 AI 코딩 어시스턴트 협업 가이드 (security.md)

이 문서는 사용자와 AI 코딩 어시스턴트가 프로젝트를 함께 개발하는 과정에서 발생할 수 있는 보안 취약점, 의도치 않은 시스템 변경 등을 예방하기 위한 핵심 원칙입니다. **OWASP GenAI LLM Top 10 (2026), OWASP Agentic Applications (ASI01~ASI10, 2026)** 및 **Git/VCS 시크릿 보호 수칙**을 반영하여 정기적으로 업데이트됩니다.

---

## 1. 🤖 최신 AI 및 Agentic 애플리케이션 보안 원칙 (OWASP 2026)

### A. OWASP GenAI LLM Top 10 (2026 핵심 및 8월 공식 릴리즈 반영)
1. **프롬프트 인젝션 방지 (Prompt Injection - #1)**: 텍스트뿐만 아니라 오디오/이미지 등 교차 모달(Cross-modal) 공격을 포함하여, 외부에서 유입되는 신뢰할 수 없는 데이터가 프롬프트를 변조하지 못하도록 합니다. 프롬프트 인젝션은 완벽한 필터링이 어려우므로 LLM을 **Zero-Trust 컴포넌트**로 취급하고 시스템 수준의 격리 방어를 적용합니다.
2. **민감 정보 노출 방지 (Sensitive Information Disclosure - #2)**: 주민등록번호, 연락처, 기부 내역 및 내부 API Key가 모델의 응답이나 공개 로그, 브라우저 화면에 불필요하게 노출되지 않도록 마스킹 처리합니다.
3. **과도한 권한 제어 (Excessive Agency / Least-Agency - #3)**: 자율 에이전트의 도구 접근 권한 오용이 주요 위협이므로 최소 권한 원칙을 적용하며, 파괴적인 작업(DB/파일 변경 등)은 반드시 **Human-in-the-Loop(사용자 명시적 승인)**을 거칩니다.
4. **숨겨진 컨텍스트 보호 (Hidden Context Exposure - #8)**: 내부 프롬프트 지침이나 백엔드 환경 설정 정보가 외부 뷰어/사용자 인터페이스로 유출되지 않도록 제어합니다.

### B. OWASP Agentic Applications 10대 보안 위험 (ASI01 ~ ASI10)
- **ASI01: Agent Goal Hijack**: 비정상적 입력으로 인해 에이전트의 원래 작업 목표가 왜곡되거나 탈취되는 현상 방어.
- **ASI02: Tool Misuse & Exploitation**: 파일 읽기/쓰기, 터미널 실행 등 정상 도구가 비인가 조작에 악용되지 않도록 인자 검증.
- **ASI03: Agent Identity & Privilege Abuse**: 에이전트의 권한이 과도하게 부여되어 발생하는 자격 증명 오용 차단.
- **ASI04: Agentic Supply Chain Compromise**: 외부 라이브러리 및 서드파티 플러그인 의존성의 악성 코드 검증.
- **ASI05: Unexpected Code Execution**: 신뢰할 수 없는 동적 코드 실행(eval, 비인가 스크립트) 원천 금지.
- **ASI06: Memory & Context Poisoning**: 지속적 대화 및 장기 메모리(`module.md`, `shared_state.json`)의 악의적 변조 방어.
- **ASI07: Insecure Inter-Agent Communication**: 에이전트 및 서브프로세스 간 데이터 교환 시 무결성 검증.
- **ASI08: Cascading Failures**: 단일 컴포넌트 오류가 전체 ERP 시스템 마비로 번지지 않도록 `try-except` 폴백 격리.
- **ASI09: Human-Agent Trust Exploitation**: AI의 조언을 맹신하여 발생할 수 있는 보안 결함을 방어적 코드 리뷰로 상쇄.
- **ASI10: Rogue Agents**: 에이전트가 예기치 않은 비정상 상태로 동작하지 않도록 명확한 중단 조건 및 감시 유지.

---

## 2. 🚨 Git 버전 관리 및 시크릿/개인정보(PII) 누출 방지 (VCS Security)

1. **인증 파일 및 시크릿의 Git 추적 원천 배제**:
   - `.streamlit/secrets.toml`은 Firebase 비공개 키, DB 인증 토큰 등이 보관되는 핵심 파일입니다.
   - **반드시 `.gitignore`에 등록**되어야 하며, 실수로 커밋되더라도 GitHub 등 원격 저장소에 Push되기 전에 반드시 인덱스 캐시를 제거(`git rm --cached .streamlit/secrets.toml`)해야 합니다.
2. **이용자 개인정보 파일(PII) 격리**:
   - 현장에서 업로드되는 이용자 명단, 바코드 리스트 등 실제 엑셀 파일(`*.xlsx`, `*.xls`)과 로컬 회원/실사 DB(`shared_state.json`)는 절대로 원격 저장소로 커밋/푸시되지 않도록 격리합니다.
3. **필수 `.gitignore` 기준 수립**:
   ```gitignore
   # Streamlit secrets & configs
   .streamlit/secrets.toml

   # Local database & state
   shared_state.json

   # Personal data & Excel files
   *.xlsx
   *.xls
   *.csv

   # Python & Environments
   .venv/
   venv/
   __pycache__/
   *.pyc

   # Logs & Temp
   *.log
   temp/
   ```

---

## 3. 🛡️ 의도치 않은 시스템 변경 및 파일 손상 방지
- **명령어 검증 및 승인**: 터미널이나 쉘에서 파일을 대량 삭제, 이동, 권한을 변경하는 파괴적인 명령어 실행 전 사용자에게 명시적인 승인을 받습니다.
- **가상환경(venv) 및 샌드박싱 격리**: 파이썬 패키지 설치는 반드시 프로젝트 내부의 격리된 가상환경(`.venv`) 내에서만 수행합니다.

---

## 4. 🔒 Streamlit 및 Firebase 특화 보안 모범 사례
- **접근 제어 및 권한 검증 강화**: `취약한 접근 제어(Broken Access Control)` 방지를 위해, CRUD 함수 호출 시 반드시 `st.session_state` 기반 권한(Role)을 재검증합니다.
- **민감 정보(Secrets) 절대 보호**: Firebase API 키 등 민감 정보는 절대 하드코딩하거나 터미널에 출력하지 않으며, 오직 `st.secrets` (`.streamlit/secrets.toml`)를 통해서만 참조합니다.
- **상태 데이터 직렬화(Serialization) 주의**: `st.cache_data`와 `st.session_state`는 내부적으로 `pickle`을 사용하므로, 외부에서 직접 주입된 신뢰할 수 없는 바이트 스트림을 역직렬화하지 않도록 통제합니다.
- **Streamlit 최신 취약점 방어 (2026 업데이트)**:
  - **위젯 상태 페이로드 제한**: 클라이언트가 제공하는 쿼리 문자열과 위젯 상태 페이로드 크기를 제한하여 무제한 리소스 할당을 방지합니다 (예: `server.maxWidgetStateSize` 25MB 이하 제한 권장).
  - **SSRF 및 약한 해시 알고리즘 방어**: 최신 버전(1.59.0 이상)으로 유지하여 CVE-2026-10804(약한 해시), CVE-2026-33682(Windows SSRF) 등의 취약점을 방어하고, child iframes나 주입된 스크립트로부터의 메시지를 차단하는 origin spoofing 방어 설정을 유지합니다.

---

## 5. ⏱️ 무한 루프 및 백그라운드 리소스 제어
- **타임아웃(Timeout) 및 백그라운드 프로세스 격리**: 무한 루프 가능성이 있는 스크립트는 `Timeout`을 명시합니다. 로컬 웹 서버(포트 8501, 8000)는 백그라운드 태스크로 전환하되 Streamlit은 반드시 `headless` 모드(`--server.headless true --browser.gatherUsageStats false`)로 실행하여 프롬프트 대기 행(Hang)을 방지합니다.

---

## 6. 👁️ AI 코딩 가시성 및 통제권 확보 (Observability & Audit)
- **AI 생성 코드 방어적 리뷰**: 아키텍처나 인증 등 핵심 보안 로직 수정 시, AI는 임의 결정하지 않고 `Implementation Plan`을 사용자에게 제시하고 승인(HITL)을 받은 후 구현합니다.
- **지속적 기록(Audit Trail)**: 매일 진행된 대화와 에이전트 도구 사용 패턴은 `260910.md` 등 일일 로그 파일과 `module.md`에 투명하게 기록하여 프로젝트 유지보수성과 보안 모니터링을 극대화합니다.
