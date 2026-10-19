"""웹앱 코드베이스 분석: 실제로 수집·저장·외부 전송하는 정보와 화면 스타일을 찾습니다.

정규식 기반이라 확정 사실이 아닙니다. 신호(파일:줄)만 찾고, 낮은 확신의 항목은
questions([확인 필요])로 돌려 줍니다. AI가 코드를 다시 읽고 교사에게 확인해야 합니다."""
from __future__ import annotations
import json, os, re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from .safety import project_root

# 생성물·의존성·참고 문서 폴더는 수집 근거로 쓰지 않습니다.
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", "out",
    ".vercel", ".firebase", "coverage", "vendor", "legal-docs", "legal", ".cache",
    "참고자료", "reference", "references", "docs",
}
# functions/lib 처럼 컴파일 결과로 보이는 lib 만 건너뜁니다(src 가 있을 때).
COMPILED_DIRS = {"lib"}
CODE_EXT = {".html", ".htm", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".css", ".scss", ".json", ".py", ".gs"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "package.json"}

# (key, 한글 설명, 정규식)
SIGNALS = [
    ("localStorage", "브라우저 localStorage에 저장", r"localStorage\s*\.\s*(setItem|getItem)|localStorage\["),
    ("sessionStorage", "브라우저 sessionStorage에 저장", r"sessionStorage\s*\."),
    ("indexedDB", "브라우저 IndexedDB 사용", r"\bindexedDB\b"),
    ("cookie", "쿠키 사용", r"document\.cookie"),
    ("openai", "OpenAI API(미국) 호출", r"api\.openai\.com|from ['\"]openai['\"]|require\(['\"]openai['\"]\)"),
    ("anthropic", "Anthropic Claude API(미국) 호출", r"api\.anthropic\.com|@anthropic-ai"),
    ("gemini", "Google Gemini API(미국) 호출", r"generativelanguage\.googleapis\.com|@google/generative-ai|@google/genai"),
    ("xai", "xAI API(미국) 호출", r"api\.x\.ai"),
    ("firebase", "Google Firebase 사용", r"firebase/|firebaseConfig|initializeApp\("),
    ("firestore", "Firestore DB 저장", r"getFirestore|firestore\(\)|collection\(\s*db"),
    ("supabase", "Supabase 사용", r"@supabase/|createClient\([^)]*supabase|supabase\.co"),
    ("auth", "로그인/회원 기능", r"signInWith(?!Anonymously)|signUp|createUserWithEmailAndPassword|auth\.signIn|type=['\"]password['\"]"),
    ("anonymous_auth", "익명 로그인(익명 계정 식별자 uid)", r"signInAnonymously"),
    ("google_login", "구글 로그인", r"GoogleAuthProvider|signInWithOAuth\(\s*\{\s*provider:\s*['\"]google"),
    ("upload", "파일·사진 업로드", r"type=['\"]file['\"]"),
    ("storage_upload", "서버 저장소에 파일 업로드(학생 산출물)",
     r"uploadBytes|uploadString|putString\s*\(|storage\(\)\.ref|getStorage\(|storage\.from\([^)]*\)\.upload|\.upload\(\s*['\"][^'\"]+['\"]|putObject\("),
    ("camera_mic", "카메라·마이크 사용", r"getUserMedia"),
    ("analytics", "방문 통계/분석 도구", r"googletagmanager|gtag\(|google-analytics|clarity\.ms"),
    ("google_sheets", "구글 시트/Apps Script로 전송", r"script\.google\.com/macros|sheets\.googleapis"),
    ("email_send", "이메일 발송(수신자 이메일 주소 처리, 발송 업체 위탁)",
     r"nodemailer|createTransport\s*\(|smtp\.gmail\.com|sendgrid|@sendgrid|resend\.com|resend\.emails|mailgun|trigger-email|firebase-functions.*mail|sendMail\s*\("),
    ("secret_manager", "비밀값 보관(Secret Manager 등, 교사 API 키 암호화 보관)",
     r"SecretManagerServiceClient|@google-cloud/secret-manager|defineSecret\s*\(|functions\.config\s*\(|defineString\s*\("),
    ("ip_log", "접속 IP 주소 수집(요청 제한·기록)",
     r"req\.ip\b|request\.ip\b|x-forwarded-for|remoteAddress|express-rate-limit|rateLimit\s*\(|rate-limiter"),
    ("chat_store", "대화·채팅 내용을 서버에 저장",
     r"\b(collection|from|doc)\(\s*(?:\w+\s*,\s*)?['\"][^'\"]*(messages|chats|conversations|대화)[^'\"]*['\"]"),
    ("usage_log", "이용 기록(로그·이벤트) 저장",
     r"\b(collection|from|doc)\(\s*(?:\w+\s*,\s*)?['\"][^'\"]*(logs|events|analytics|activity)[^'\"]*['\"]"),
    ("teacher_profile", "교사 계정 정보(이메일·이름) 저장",
     r"\b(collection|from|doc)\(\s*(?:\w+\s*,\s*)?['\"][^'\"]*(teachers|users|profiles)[^'\"]*['\"]"),
    ("error_report", "오류 기록 전송", r"\bSentry\b|@sentry/|captureException|captureMessage|/error['\"]"),
]
AI_KEYS = {"openai": ("OpenAI, L.L.C.", "미국"), "anthropic": ("Anthropic, PBC", "미국"),
           "gemini": ("Google LLC (Gemini API)", "미국"), "xai": ("X.AI LLC", "미국")}

# 긴 표현을 먼저 맞춰 '비밀번호'가 '번호'로 잡히지 않게 합니다.
PI_FIELDS = [  # (정규식, 항목명)
    (r"password|비밀번호|passwd", "비밀번호"),
    (r"전화\s*번호|휴대폰|휴대전화|phone|tel\b|mobile", "전화번호"),
    (r"학번|출석\s*번호|student[._-]?(no|num|id|number)", "번호"),
    (r"e-?mail|이메일", "이메일"),
    (r"생년|birth", "생년월일"),
    (r"아이디|username|login.?id|(?<![.\w])user.?id(?![.\w])", "아이디"),
    (r"닉네임|nickname|nick\b", "이름(또는 닉네임)"),
    (r"성명|(학생|아이|어린이|회원|사용자|이용자)\s*이름|student.?name|display.?name|real.?name|(?<![가-힣a-z])이름(?![가-힣])|(?<![.\w])name(?![.\w])", "이름(또는 닉네임)"),
    (r"학년|grade", "학년"),
    (r"(?<![가-힣])반(?![가-힣])|(?<![.\w])class(?!Name)(?![.\w])", "반"),
    (r"학교|school", "학교명"),
]
# '활동 이름', '파일명'처럼 사람이 아닌 대상의 이름·번호는 수집 항목이 아닙니다.
NOT_PERSON = re.compile(
    r"(활동|파일|폴더|문서|게시물|게시글|과제|수업|단원|프로젝트|앱|서비스|작품|그림|사진|이미지|상품|메뉴|버튼|학급|학원)\s*(이름|명)|"
    r"(file|folder|activity|project|app|document|image|photo|item|menu|button)[._-]?name|filename|fileName", re.I)
SEARCH_INPUT = re.compile(r"type=['\"]search['\"]|role=['\"]search['\"]|\bsearch\b|검색", re.I)
SKIP_INPUT_TYPE = re.compile(r"type=['\"](button|submit|checkbox|radio|hidden|range|color|reset|image)['\"]", re.I)
INPUT_RE = re.compile(r"<(input|textarea|select)\b[^>]*>", re.I | re.S)
AI_CALL_RE = re.compile(r"fetch\(|axios\.|\.chat\.completions|generateContent|messages\.create|responses\.create")
AI_NAME_RE = re.compile(r"\b(studentName|userName|displayName|realName|nickName|nickname|student_name|user_name)\b|(?<![.\w가-힣])(name|이름)(?![.\w가-힣])")
AI_OTHER_PI_RE = re.compile(r"이메일|email|전화|phone|학년|grade|학번|학교|school|비밀번호|password", re.I)
TTL_RE = re.compile(r"(ttl|expireAt|expiresAt|expires_at|TTL)\b[^;\n]{0,80}?(\d+)\s*(일|day|d\b|시간|hour|h\b)?", re.I)
HASH_RE = re.compile(r"(sha256|createHash|hashUid|uid\s*를?\s*해시|해시)", re.I)


def _skip_dir(name: str, parent: Path) -> bool:
    if name in SKIP_DIRS or name.startswith("."):
        return True
    if name in COMPILED_DIRS and ((parent / "src").is_dir() or (parent / "tsconfig.json").is_file()):
        return True
    return False


def _files(root: Path):
    # 심볼릭 링크 폴더는 따라가지 않고, 프로젝트 밖을 가리키는 링크 파일은 읽지 않습니다.
    for dp, dns, fns in os.walk(root, followlinks=False):
        dns[:] = sorted(d for d in dns if not _skip_dir(d, Path(dp)))
        for fn in sorted(fns):
            p = Path(dp) / fn
            low = fn.lower()
            if p.suffix.lower() not in CODE_EXT or fn in SKIP_FILES or low.endswith(".min.js") or low.endswith(".map"):
                continue
            try:
                rp = p.resolve()
                if not rp.is_relative_to(root) or not rp.is_file() or rp.stat().st_size > 800_000:
                    continue
            except OSError:
                continue
            yield p


def _line(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _ev(rel: str, text: str, idx: int, note: str = "") -> str:
    s = f"{rel}:{_line(text, idx)}"
    return f"{s} ({note})" if note else s


def _add(bucket: dict, key: str, ev: str, limit: int = 8):
    bucket.setdefault(key, [])
    if ev not in bucket[key] and len(bucket[key]) < limit:
        bucket[key].append(ev)


def _style(root: Path, files: list[Path], deps: set[str]) -> dict:
    css_text, html_text = "", ""
    for f in files:
        t = f.read_text("utf-8", "ignore")
        if f.suffix in (".css", ".scss"):
            css_text += t + "\n"
        elif f.suffix in (".html", ".vue", ".svelte", ".jsx", ".tsx"):
            html_text += t + "\n"
            css_text += "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", t, re.S)) + "\n"
    framework = "static-html"
    for k, v in [("next", "next"), ("react", "react"), ("vue", "vue"), ("svelte", "svelte")]:
        if k in deps:
            framework = v; break
    tailwind = "tailwindcss" in deps or "cdn.tailwindcss.com" in html_text or bool(list(root.glob("tailwind.config.*")))
    variables = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;}{]+)(?=[;}])", css_text))
    fonts = Counter(m.strip().strip(";") for m in re.findall(r"font-family\s*:\s*([^;}{]+)", css_text))
    radii = Counter(m.strip() for m in re.findall(r"border-radius\s*:\s*([^;}{]+)", css_text) if "var(" not in m and "50%" not in m and "999" not in m)
    colors = Counter(c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", css_text))

    def var(*names):
        for n in names:
            for k, v in variables.items():
                if re.search(n, k, re.I):
                    return v.strip()

    def resolve(v):
        m = re.match(r"var\((--[\w-]+)", v or "")
        return variables.get(m.group(1), v).strip() if m else v

    font = resolve(fonts.most_common(1)[0][0]) if fonts else None
    primary = var(r"primary", r"accent", r"brand", r"main", r"point")
    btn = re.search(r"(button|\.btn[\w-]*)[^{]*\{[^}]*background(?:-color)?\s*:\s*([^;]+);", css_text)
    if not primary and btn:
        primary = resolve(btn.group(2).strip())
    if not primary:
        sat = [c for c, _ in colors.most_common() if c not in ("#fff", "#ffffff", "#000", "#000000", "#333", "#333333")]
        primary = sat[0] if sat else None
    bg = var(r"^--(bg|background)$", r"bg", r"background")
    body = re.search(r"body\s*\{[^}]*background(?:-color)?\s*:\s*([^;]+);", css_text)
    if body:
        bg = resolve(body.group(1).strip()) if not bg else bg
    text = var(r"^--(text|fg|ink)", r"text-color", r"foreground")
    radius = var(r"radius") or (radii.most_common(1)[0][0] if radii else None)
    gfonts = re.findall(r"https://fonts\.googleapis\.com/css2?\?[^\"' )]+", html_text + css_text)
    tw = {"font": "inherit", "radius": "1rem", "primary": primary or "#4f46e5"} if tailwind else {}
    return {
        "framework": framework, "tailwind": tailwind,
        "font_family": font or ("inherit" if tailwind else None),
        "google_fonts": sorted(set(gfonts)),
        "primary": resolve(primary) if primary else None, "background": resolve(bg) if bg else None,
        "text": resolve(text) if text else None, "radius": resolve(radius) if radius else None,
        "css_variables": dict(list(variables.items())[:30]), "tailwind_tokens": tw,
    }


def _classify_input(tag: str, label: str) -> tuple[str, str] | None:
    """(항목명, 확신 'high'|'low') 또는 None. 검색창·화면 라벨·대상이 아닌 이름은 제외합니다."""
    if SKIP_INPUT_TYPE.search(tag) or SEARCH_INPUT.search(tag):
        return None
    attrs = " ".join(re.findall(r"(?:name|id|placeholder|aria-label|v-model)=['\"{]([^'\"}]*)", tag))
    if SEARCH_INPUT.search(attrs) or SEARCH_INPUT.search(label):
        return None
    hay = (attrs + " " + label).strip()
    if not hay or NOT_PERSON.search(hay):
        return None
    for rx, item in PI_FIELDS:
        m = re.search(rx, hay, re.I)
        if not m:
            continue
        # 화면 글자(라벨)만 맞고 입력칸 이름·자리표시에는 없는 경우: 단정하지 않고 질문으로 남깁니다.
        in_attrs = bool(re.search(rx, attrs, re.I))
        return item, ("high" if in_attrs else "low")
    return None


def _ai_payload(files, root) -> dict:
    """AI 호출 근처 코드에 개인정보로 보이는 변수가 있는지. 호출만으로는 단정하지 않습니다."""
    name_hits, other_hits = [], []
    for f in files:
        t = f.read_text("utf-8", "ignore")
        rel = str(f.relative_to(root))
        for m in AI_CALL_RE.finditer(t):
            win = t[m.start():m.start() + 700]  # 호출 뒤(요청 본문)만 봅니다
            if AI_NAME_RE.search(win):
                _add({"_": name_hits}, "_", _ev(rel, t, m.start()), 6)
            elif AI_OTHER_PI_RE.search(win):
                _add({"_": other_hits}, "_", _ev(rel, t, m.start()), 6)
    return {"name": name_hits, "other": other_hits}


def _retention_hints(files, root) -> list[str]:
    out = []
    for f in files:
        t = f.read_text("utf-8", "ignore")
        rel = str(f.relative_to(root))
        for m in TTL_RE.finditer(t):
            n, unit = m.group(2), (m.group(3) or "").lower()
            if unit.startswith("h") or unit.startswith("시간"):
                label = f"{n}시간"
            elif unit.startswith("d") or unit.startswith("일") or not unit:
                label = f"{n}일" if unit or int(n) <= 3650 else ""
            else:
                label = ""
            if label:
                _add({"_": out}, "_", f"{label} ({_ev(rel, t, m.start())})", 6)
    return out


def analyze(project_path: str) -> dict:
    root = project_root(project_path)
    files = list(_files(root))
    pkg = {}
    if (root / "package.json").exists():
        try:
            pkg = json.loads((root / "package.json").read_text("utf-8"))
        except Exception:
            pkg = {}
    deps = set((pkg.get("dependencies") or {}) | (pkg.get("devDependencies") or {}))
    findings: dict[str, list[str]] = {}
    urls: dict[str, str] = {}
    fields: dict[str, list[str]] = {}
    low_fields: dict[str, list[str]] = {}
    title = None
    hashed = []
    for f in files:
        rel = str(f.relative_to(root))
        t = f.read_text("utf-8", "ignore")
        if f.suffix in (".html", ".htm") and not title:
            m = re.search(r"<title>(.*?)</title>", t, re.S)
            if m:
                title = m.group(1).strip()
        for key, _, rx in SIGNALS:
            for m in re.finditer(rx, t):
                _add(findings, key, _ev(rel, t, m.start()))
        if HASH_RE.search(t) and re.search(r"\buid\b", t):
            mm = HASH_RE.search(t)
            _add({"_": hashed}, "_", _ev(rel, t, mm.start()))
        for m in re.finditer(r"https?://[\w.-]+(?:/[^\s'\"`)<>]*)?", t):
            host = urlparse(m.group(0)).hostname or ""
            if host and not re.search(r"(w3\.org|schema|fonts\.(googleapis|gstatic)|localhost|example\.|127\.0\.0\.1|github\.com|cdn\.|unpkg|jsdelivr)", host):
                urls.setdefault(host, _ev(rel, t, m.start()))
        if f.suffix in (".html", ".htm", ".vue", ".jsx", ".tsx", ".svelte"):
            for m in INPUT_RE.finditer(t):
                prev = t[max(0, m.start() - 300):m.start()]
                labs = re.findall(r"<label[^>]*>([^<]{1,40})", prev)
                label = labs[-1].strip() if labs else ""
                got = _classify_input(m.group(0), label)
                if not got:
                    continue
                item, conf = got
                shown = (label or " ".join(re.findall(r"(?:name|placeholder)=['\"]([^'\"]*)", m.group(0)))[:1] or [item])[:30]
                _add(fields if conf == "high" else low_fields, item, _ev(rel, t, m.start(), shown))

    ai_payload = _ai_payload(files, root)
    retention_hints = _retention_hints(files, root)
    ai = [k for k in AI_KEYS if k in findings]
    backends = [k for k in ("firebase", "supabase", "google_sheets") if k in findings]
    hosting = [n for n, f in [("Vercel", "vercel.json"), ("Netlify", "netlify.toml"), ("Firebase Hosting", "firebase.json")] if (root / f).exists()]
    if (root / "api").is_dir() and not hosting:
        hosting.append("Vercel(서버리스 api/ 폴더 감지, [확인 필요])")

    questions: list[str] = []
    personal_items = sorted(fields)
    if "auth" in findings and "비밀번호" not in personal_items and "비밀번호" not in low_fields:
        personal_items.append("로그인 정보")
    if "anonymous_auth" in findings:
        personal_items.append("익명 계정 식별자(uid)")
    if "email_send" in findings and "이메일" not in personal_items:
        personal_items.append("이메일(발송 수신자)")
    if "chat_store" in findings:
        personal_items.append("대화 내용")
    if "storage_upload" in findings:
        personal_items.append("업로드 파일(학생 산출물)")
    if "usage_log" in findings:
        personal_items.append("이용 기록")
    if "ip_log" in findings:
        personal_items.append("접속 IP 주소")
    if "teacher_profile" in findings:
        personal_items.append("교사 계정 정보(이메일·이름)")
    if "error_report" in findings:
        personal_items.append("오류 기록")

    for item, evs in low_fields.items():
        questions.append(f"[확인 필요] '{item}'(으)로 보이는 입력칸이 있습니다({', '.join(evs[:2])}). 학생 등 사람의 정보를 받는 칸인가요, 화면 안내용 글자인가요?")
    if ai and not ai_payload["name"] and not ai_payload["other"]:
        questions.append("[확인 필요] 외부 AI를 호출하는 코드가 있습니다. 호출만으로는 무엇을 보내는지 알 수 없습니다. AI에 보내는 내용이 글·그림·이름 중 무엇인지 코드에서 확인해 주세요. (" + ", ".join(findings[ai[0]][:2]) + ")")
    elif ai_payload["other"] and not ai_payload["name"]:
        questions.append("[확인 필요] 외부 AI 호출 근처에 개인정보로 보이는 값이 있습니다(" + ", ".join(ai_payload["other"][:2]) + "). 실제로 무엇을 보내는지 확인해 주세요.")
    if "ip_log" in findings:
        questions.append("[확인 필요] 접속 IP를 다루거나 요청 횟수를 제한하는 코드가 있습니다(" + ", ".join(findings["ip_log"][:2]) + "). IP를 저장하나요? 저장한다면 보관 기간은 얼마인가요?")
    if "usage_log" in findings and not retention_hints:
        questions.append("[확인 필요] 이용 기록(로그)을 저장하는 코드가 있습니다(" + ", ".join(findings["usage_log"][:2]) + "). 보관 기간은 얼마인가요?")
    if "email_send" in findings:
        questions.append("[확인 필요] 이메일을 보내는 코드가 있습니다(" + ", ".join(findings["email_send"][:2]) + "). 수신자 이메일을 어디에 보관하고, 발송을 어느 업체에 맡기나요?")
    if "chat_store" in findings:
        questions.append("[확인 필요] 대화 내용을 서버에 저장하는 코드가 있습니다(" + ", ".join(findings["chat_store"][:2]) + "). 보관 기간과 누가 볼 수 있는지를 확인해 주세요.")
    if "teacher_profile" in findings:
        questions.append("[확인 필요] 교사(회원) 계정 정보를 저장하는 코드가 있습니다(" + ", ".join(findings["teacher_profile"][:2]) + "). 저장하는 항목(이메일·이름 등)을 확인해 주세요.")
    if hashed:
        questions.append("[확인 필요] 식별자(uid)를 해시하는 코드가 있습니다(" + ", ".join(hashed[:2]) + "). 원본 식별자를 따로 보관하는지 확인해 주세요.")

    storage = []
    if "localStorage" in findings or "sessionStorage" in findings or "indexedDB" in findings:
        storage.append("이용자 기기(브라우저 저장소)")
    if "firestore" in findings or "firebase" in findings:
        storage.append("Google Firebase(서버)")
    if "supabase" in findings:
        storage.append("Supabase(서버)")
    if "google_sheets" in findings:
        storage.append("Google 스프레드시트")
    if "storage_upload" in findings and "Google Firebase(서버)" not in storage and "Supabase(서버)" not in storage:
        storage.append("파일 저장소(서버)")
    audience = "학생 수업용([확인 필요])" if re.search(r"학생|어린이|초등|친구|student", " ".join(f.read_text('utf-8', 'ignore')[:4000] for f in files if f.suffix in ('.html', '.vue', '.jsx', '.tsx'))) else "[확인 필요]"

    safety_notes = []
    if "secret_manager" in findings:
        safety_notes.append("비밀값(API 키 등)을 Secret Manager 등 별도 비밀 저장소에 보관하는 코드: " + ", ".join(findings["secret_manager"][:3]))
    if hashed:
        safety_notes.append("식별자 해시 처리: " + ", ".join(hashed[:3]))
    if retention_hints:
        safety_notes.append("코드에 적힌 보관 기간(TTL): " + ", ".join(retention_hints[:3]))

    collects_pi = bool(personal_items)
    return {
        "project_path": str(root), "app_title": title or pkg.get("name") or root.name,
        "framework_style": _style(root, files, deps), "file_count": len(files),
        "audience_guess": audience,
        "signals": {k: {"설명": d, "근거": findings[k]} for k, d, _ in SIGNALS if k in findings},
        "personal_fields": fields, "personal_fields_low_confidence": low_fields,
        "personal_items": personal_items,
        "collects_personal_info": collects_pi,
        "checklist_variant": "개인정보 있는 웹앱" if collects_pi else "개인정보 없는 일반앱",
        "storage_locations": storage,
        "external_ai": [{"key": k, "provider": AI_KEYS[k][0], "country": AI_KEYS[k][1], "근거": findings[k]} for k in ai],
        "ai_request_may_include_name": ai_payload["name"],
        "ai_request_nearby_fields": ai_payload["other"],
        "retention_hints": retention_hints,
        "safety_notes": safety_notes,
        "questions": questions,
        "backends": backends, "hosting": hosting,
        "external_hosts": urls,
        "has_delete_feature": _has_delete(files, root),
        "legal_link_mode": _legal_links(files, root, deps),
    }


def _has_delete(files, root) -> list[str]:
    out = []
    for f in files:
        t = f.read_text("utf-8", "ignore")
        for m in re.finditer(r"localStorage\.(removeItem|clear)|deleteDoc|\.delete\(\)|탈퇴|기록 지우기|삭제", t):
            out.append(_ev(str(f.relative_to(root)), t, m.start()))
            break
    return out


LEGAL_LINK_RE = re.compile(r"이용\s*약관|개인\s*정보\s*처리\s*방침|privacy\s*policy|terms\s*of\s*service", re.I)
UI_EXT = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}


def _legal_links(files, root, deps) -> dict:
    """이미 약관·처리방침 링크가 있거나 번들러 SPA 이면 index.html 에 주입하지 않습니다."""
    hits = []
    for f in files:
        if f.suffix.lower() not in UI_EXT:
            continue
        t = f.read_text("utf-8", "ignore")
        m = LEGAL_LINK_RE.search(t)
        if m:
            hits.append(_ev(str(f.relative_to(root)), t, m.start()))
    spa = bool(deps & {"react", "vue", "svelte", "next", "@angular/core", "vite"}) or any((root / n).exists() for n in ("vite.config.js", "vite.config.ts", "vite.config.mjs"))
    if hits or spa:
        return {"mode": "link-only", "existing_links": hits,
                "reason": "이미 이용약관·개인정보처리방침 링크가 있거나, 번들러로 빌드하는 SPA 입니다. index.html 에 링크를 넣지 않고 파일만 만듭니다."}
    return {"mode": "inject", "existing_links": [], "reason": "정적 HTML 이라 하단 링크를 index.html 에 연결합니다."}
