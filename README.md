# edu-legal-mcp

교사 개발자가 만든 웹앱을 분석해서 다음 세 가지를 만들어 주는 MCP 서버입니다.

1. 앱에 맞춘 **이용약관·개인정보처리방침 초안** (마크다운 + 한글 HWPX)
2. 앱 **하단 링크와 팝업**. 팝업은 앱의 글꼴·색·모서리 스타일에 맞춰지고, 휴대전화에서도 쓸 수 있습니다.
3. **에듀집 필수기준 체크리스트**와 **학교용 필수기준 체크리스트(검토 초안)**. 원본 양식의 표를 그대로 살린 HWPX로 만듭니다.

wowideas 작업장 「개인정보처리방침/이용약관예시」에 있는 3단계 프롬프트를 그대로 따릅니다.
- 1단계: 실제 앱을 확인해 약관과 처리방침을 작성합니다.
- 2단계: 확인한 문서를 하단에 연결합니다.
- 3단계: 근거를 확인해 체크리스트를 작성합니다.

> 이 서버는 **배포·게시·제출을 하지 않습니다.** 모든 결과는 `<내 앱>/legal-docs/`에 초안으로만 저장됩니다.

## 도구

| 도구 | 하는 일 |
|---|---|
| `analyze_app(project_path)` | 코드를 분석해 다음을 찾고, 근거(파일:줄)와 함께 돌려줍니다.<br>• 입력 항목(이름·학년 등)<br>• 브라우저 저장(localStorage)<br>• 외부 AI(OpenAI·Gemini·Claude 등)<br>• Firebase·Supabase<br>• 로그인 기능<br>• 프레임워크(정적 HTML·React·Vue·Tailwind)<br>• 스타일(글꼴·색·모서리) |
| `draft_legal_docs(project_path, info)` | `terms.md`, `privacy.md`, `questions.md`와 `이용약관(초안).hwpx`, `개인정보처리방침(초안).hwpx`를 만듭니다. 모르는 내용은 `[확인 필요]`로 표시하고 질문 목록에 넣습니다. |
| `install_footer_popup(project_path, include_checklist)` | `index.html`에 스크립트 2개를 연결하고 하단 링크를 추가합니다. 팝업 동작은 아래와 같습니다.<br>• 끝까지 스크롤해야 '확인했어요' 버튼이 켜집니다.<br>• ×, Esc, 바깥 클릭으로 닫을 수 있습니다.<br>• 휴대전화에서는 아래에서 올라오는 시트로 열립니다. |
| `generate_checklists(project_path, info)` | 개인정보 있음/없음 양식을 자동으로 골라 에듀집 체크리스트를 HWPX로 만들고, 학교용 HWPX(검토 초안)도 만듭니다. `checklist.json`과 요약도 함께 저장합니다. |
| `run_all(project_path, info)` | 위 도구를 한 번에 실행합니다. |

`info`에 넣는 값은 모두 선택 사항입니다.
- `app_name`: 앱 이름
- `operator_name`: 개발 교사 성명
- `school`: 학교
- `contact_phone`: 교무실 등 공용 번호
- `contact_email`: 이메일
- `effective_date`: 시행일
- `purpose`: 용도
- `retention`: 보유 기간
- `access_url`: 접속 주소
- `summary`: 앱 소개

## 설치

```bash
git clone <이 저장소> edu-legal-mcp && cd edu-legal-mcp
pip install -e .        # Python 3.10+, mcp, lxml 설치
```

### Claude Desktop
`claude_desktop_config.json` 파일에 아래 내용을 넣습니다.
```json
{ "mcpServers": { "edu-legal": { "command": "python", "args": ["-m", "edu_legal_mcp.server"], "cwd": "/경로/edu-legal-mcp" } } }
```
### Cursor
`.cursor/mcp.json` 파일에 아래 내용을 넣습니다.
```json
{ "mcpServers": { "edu-legal": { "command": "python", "args": ["-m", "edu_legal_mcp.server"], "cwd": "/경로/edu-legal-mcp" } } }
```
### Claude Code
```bash
claude mcp add edu-legal -- python -m edu_legal_mcp.server
```
`pip install -e .`로 설치했다면 `command`에 `edu-legal-mcp` 실행 파일을 바로 써도 됩니다.

## 사용 예
> "내 앱 `C:\projects\my-app`을 analyze_app으로 분석하고, 약관·처리방침 초안을 만들어 줘. 성명 홍길동, ○○초등학교, 문의 02-000-0000."

1. AI가 `questions.md`의 질문을 보여 줍니다. 답을 `info`에 넣고 `draft_legal_docs`를 다시 실행하면 `[확인 필요]`가 줄어듭니다.
2. `install_footer_popup`을 실행한 뒤 PC와 휴대전화에서 직접 확인합니다.
3. `generate_checklists`를 실행하면 HWPX가 나옵니다. 한글에서 열어 검토하세요.

## 체크리스트 양식 충실도
- **학교용**: 원본 `필수기준체크리스트(학교용).hwpx`를 템플릿으로 그대로 씁니다(`edu_legal_mcp/templates/`). 셀 텍스트만 바꾸기 때문에 표 구조, 병합, 스타일, 용지 설정이 원본과 같습니다. 제목 뒤에는 `[검토 초안]`이 붙습니다.
  - 필수기준: 충족·미충족·해당없음 중 하나에 ■를 표시하고, 증빙자료 칸에 근거를 적습니다.
  - 선택기준: 학교가 판단할 영역이라 체크하지 않습니다. 대신 "교사 답변 / 학교 확인"을 나눠서 적습니다.
- **에듀집용**: 원본이 `.hwp` 파일이라, 같은 행·열·병합과 같은 문구로 HWPX 표를 다시 만듭니다. 스타일은 학교용 양식의 글꼴과 테두리를 씁니다.
  - 표 3개를 만듭니다: 「□ 제품/서비스 개요」, 「□ 개인정보보호 기준 충족여부」, 「□ 작성일 및 문의처」.
  - 「□ 개인정보보호 기준 충족여부」 표의 열은 `선정기준 | 세부 내용 | 확인(충족/미충족/해당 없음) | 증빙(예시)`입니다.
- 작성 규칙
  - 확인하지 못한 항목은 모두 □로 두고 `[확인 필요]`와 질문을 적습니다.
  - 기능이 실제로 없을 때만 `[해당 없음]`을 씁니다.
  - 예시 앱의 답변은 복사하지 않습니다.

## 테스트
```bash
python scripts/e2e_client.py ./sample-app   # MCP stdio 클라이언트로 4개 도구 호출
python -m http.server 8765 -d ./sample-app & python scripts/shots.py http://localhost:8765/ ./shots   # 팝업 캡처 + 모바일 열기/스크롤/닫기 검사
```

## 양식 출처
`edu_legal_mcp/templates/school_checklist.hwpx`(필수기준 체크리스트, 학교용)와 에듀집 체크리스트 표 구조·문구, 3단계 프롬프트는 **교사개발자 해커톤** 자료(wowideas 작업장 「개인정보처리방침/이용약관예시」)에 공개된 교육용 양식을 바탕으로 했습니다. 양식의 권리는 원 작성 기관에 있습니다. 다른 교사의 예시 앱 작성 사례(PDF)는 이 저장소에 포함하지 않았습니다.

## 주의
이 도구가 만드는 문서는 법률 자문이 아닙니다. 학교와 교육청의 안내, 학교운영위원회 심의 절차를 따르세요.
