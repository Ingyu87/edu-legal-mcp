"""웹앱 코드베이스 분석: 실제로 수집·저장·외부 전송하는 정보와 화면 스타일을 찾습니다."""
from __future__ import annotations
import json, re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".vercel", "legal-docs", "legal", ".cache", "coverage", "out"}
CODE_EXT = {".html", ".htm", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".css", ".scss", ".json", ".py", ".gs"}

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
    ("auth", "로그인/회원 기능", r"signInWith|signUp|createUserWithEmailAndPassword|auth\.signIn|type=['\"]password['\"]"),
    ("google_login", "구글 로그인", r"GoogleAuthProvider|signInWithOAuth\(\s*\{\s*provider:\s*['\"]google"),
    ("upload", "파일·사진 업로드", r"type=['\"]file['\"]"),
    ("camera_mic", "카메라·마이크 사용", r"getUserMedia"),
    ("analytics", "방문 통계/분석 도구", r"googletagmanager|gtag\(|google-analytics|clarity\.ms"),
    ("google_sheets", "구글 시트/Apps Script로 전송", r"script\.google\.com/macros|sheets\.googleapis"),
]
AI_KEYS = {"openai": ("OpenAI, L.L.C.", "미국"), "anthropic": ("Anthropic, PBC", "미국"),
           "gemini": ("Google LLC (Gemini API)", "미국"), "xai": ("X.AI LLC", "미국")}
PI_FIELDS = [  # (정규식, 항목명)
    (r"이름|성명|name|nickname|닉네임", "이름(또는 닉네임)"),
    (r"학년|grade", "학년"), (r"반\b|class(?!Name)", "반"), (r"번호|학번|student.?(no|num|id)", "번호"),
    (r"e-?mail|이메일", "이메일"), (r"전화|phone|tel\b", "전화번호"), (r"생년|birth", "생년월일"),
    (r"아이디|user.?id|username", "아이디"), (r"password|비밀번호", "비밀번호"), (r"학교|school", "학교명"),
]
INPUT_RE = re.compile(r"<(input|textarea|select)\b[^>]*>", re.I | re.S)


def _files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS) and p.suffix.lower() in CODE_EXT:
            if p.name in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml") or p.stat().st_size > 800_000:
                continue
            yield p


def _line(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


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
    for v in variables.values():
        pass
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
    # 버튼 배경색
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
    tw = {}
    if tailwind:
        tw = {"font": "inherit", "radius": "1rem", "primary": primary or "#4f46e5"}
    return {
        "framework": framework, "tailwind": tailwind,
        "font_family": font or ("inherit" if tailwind else None),
        "google_fonts": sorted(set(gfonts)),
        "primary": resolve(primary) if primary else None, "background": resolve(bg) if bg else None,
        "text": resolve(text) if text else None, "radius": resolve(radius) if radius else None,
        "css_variables": dict(list(variables.items())[:30]), "tailwind_tokens": tw,
    }


def analyze(project_path: str) -> dict:
    root = Path(project_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"프로젝트 폴더가 없습니다: {root}")
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
    title = None
    for f in files:
        rel = str(f.relative_to(root))
        t = f.read_text("utf-8", "ignore")
        if f.suffix in (".html", ".htm") and not title:
            m = re.search(r"<title>(.*?)</title>", t, re.S)
            if m: title = m.group(1).strip()
        for key, _, rx in SIGNALS:
            for m in re.finditer(rx, t):
                findings.setdefault(key, [])
                ev = f"{rel}:{_line(t, m.start())}"
                if ev not in findings[key] and len(findings[key]) < 8:
                    findings[key].append(ev)
        for m in re.finditer(r"https?://[\w.-]+(?:/[^\s'\"`)<>]*)?", t):
            host = urlparse(m.group(0)).hostname or ""
            if host and not re.search(r"(w3\.org|schema|fonts\.(googleapis|gstatic)|localhost|example\.|127\.0\.0\.1|github\.com|cdn\.|unpkg|jsdelivr)", host):
                urls.setdefault(host, f"{rel}:{_line(t, m.start())}")
        if f.suffix in (".html", ".htm", ".vue", ".jsx", ".tsx", ".svelte"):
            for m in INPUT_RE.finditer(t):
                tag = m.group(0)
                if re.search(r"type=['\"](button|submit|checkbox|radio|hidden|range|color)['\"]", tag):
                    continue
                attrs = " ".join(re.findall(r"(?:name|id|placeholder|aria-label|v-model)=['\"{]([^'\"}]*)", tag))
                # 바로 앞 label 텍스트
                lab = re.findall(r"<label[^>]*>([^<]{1,40})", t[max(0, m.start() - 300):m.start()])
                hay = attrs + " " + (lab[-1] if lab else "")
                for rx, label in PI_FIELDS:
                    if re.search(rx, hay, re.I):
                        fields.setdefault(label, [])
                        ev = f"{rel}:{_line(t, m.start())} ({(lab[-1].strip() if lab else attrs.split()[0] if attrs.split() else label)[:30]})"
                        if ev not in fields[label]:
                            fields[label].append(ev)
                        break
    # AI 요청에 이름이 함께 실리는지 추정
    name_in_ai = []
    for f in files:
        t = f.read_text("utf-8", "ignore")
        for m in re.finditer(r"fetch\(|axios\.|\.chat\.completions|generateContent|messages\.create", t):
            win = t[m.start():m.start() + 900]
            if re.search(r"\b(name|studentName|userName|이름)\b", win):
                name_in_ai.append(f"{f.relative_to(root)}:{_line(t, m.start())}")
    ai = [k for k in AI_KEYS if k in findings]
    if any(re.search(r"openai|anthropic|generativelanguage|x\.ai", h) for h in urls):
        pass
    backends = [k for k in ("firebase", "supabase", "google_sheets") if k in findings]
    hosting = [n for n, f in [("Vercel", "vercel.json"), ("Netlify", "netlify.toml"), ("Firebase Hosting", "firebase.json")] if (root / f).exists()]
    if (root / "api").is_dir() and not hosting:
        hosting.append("Vercel(서버리스 api/ 폴더 감지, [확인 필요])")
    collects_pi = bool(fields) or "auth" in findings
    personal_items = sorted(fields)
    if "auth" in findings and "비밀번호" not in personal_items:
        personal_items.append("로그인 정보([확인 필요])")
    storage = []
    if "localStorage" in findings or "sessionStorage" in findings or "indexedDB" in findings:
        storage.append("이용자 기기(브라우저 저장소)")
    if "firestore" in findings or "firebase" in findings:
        storage.append("Google Firebase(서버)")
    if "supabase" in findings:
        storage.append("Supabase(서버)")
    if "google_sheets" in findings:
        storage.append("Google 스프레드시트")
    audience = "학생 수업용([확인 필요])" if re.search(r"학생|어린이|초등|친구|student", " ".join(f.read_text('utf-8','ignore')[:4000] for f in files if f.suffix in ('.html', '.vue', '.jsx', '.tsx'))) else "[확인 필요]"
    result = {
        "project_path": str(root), "app_title": title or pkg.get("name") or root.name,
        "framework_style": _style(root, files, deps), "file_count": len(files),
        "audience_guess": audience,
        "signals": {k: {"설명": d, "근거": findings[k]} for k, d, _ in SIGNALS if k in findings},
        "personal_fields": fields, "personal_items": personal_items,
        "collects_personal_info": collects_pi,
        "checklist_variant": "개인정보 있는 웹앱" if collects_pi else "개인정보 없는 일반앱",
        "storage_locations": storage,
        "external_ai": [{"key": k, "provider": AI_KEYS[k][0], "country": AI_KEYS[k][1], "근거": findings[k]} for k in ai],
        "ai_request_may_include_name": name_in_ai,
        "backends": backends, "hosting": hosting,
        "external_hosts": urls,
        "has_delete_feature": _has_delete(files),
    }
    return result


def _has_delete(files) -> list[str]:
    out = []
    for f in files:
        t = f.read_text("utf-8", "ignore")
        for m in re.finditer(r"localStorage\.(removeItem|clear)|deleteDoc|\.delete\(\)|탈퇴|기록 지우기|삭제", t):
            out.append(f"{f.name}:{_line(t, m.start())}")
            break
    return out
