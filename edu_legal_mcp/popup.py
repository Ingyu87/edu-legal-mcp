"""웹앱 하단(footer)에 이용약관·개인정보처리방침(·체크리스트) 링크와 팝업을 설치합니다.
대상 앱의 글꼴·색·모서리 둥글기를 그대로 써서 팝업을 만들며, 프레임워크와 무관하게 동작하는
의존성 없는 스크립트 1개(+내용 파일 1개)를 index.html에 연결합니다."""
from __future__ import annotations
import html, json, re
from pathlib import Path
from .legal import TBD, AI_RULE, DRAFT, out_dir, find_forbidden, read_meta
from .safety import project_root, inside, safe_dir, backup, css_value, UnsafePath

MARK = "<!-- edu-legal-mcp -->"


def md_to_html(md: str) -> str:
    out, inlist = [], False
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("- "):
            if not inlist:
                out.append("<ul>"); inlist = True
            out.append(f"<li>{_inline(s[2:])}</li>"); continue
        if inlist:
            out.append("</ul>"); inlist = False
        if not s:
            continue
        if s.startswith("> "):
            out.append(f'<p class="el-note">{_inline(s[2:])}</p>')
        elif s.startswith("# "):
            continue  # 제목은 팝업 머리글에 표시
        elif s.startswith("## "):
            out.append(f"<h3>{_inline(s[3:])}</h3>")
        elif s.startswith("|"):
            continue
        else:
            out.append(f"<p>{_inline(s)}</p>")
    if inlist:
        out.append("</ul>")
    return "\n".join(out)


def _inline(t: str) -> str:
    t = html.escape(t)
    return t.replace(html.escape(TBD), f'<mark class="el-tbd">{TBD}</mark>')


def checklist_html(data: dict) -> str:
    e = html.escape
    o = {x["text"]: x for x in data["overview"]}
    ov = data["overview"]
    h = [f'<p class="el-note">양식: 에듀집 필수기준 체크리스트 – {e(data["variant"])}</p>',
         "<h3>□ 제품/서비스 개요</h3>", '<div class="el-tw"><table class="el-t">',
         f'<tr><th>제품/서비스명</th><td>{e(ov[1]["text"])}</td><th>공급자</th><td>{e(ov[3]["text"])}</td></tr>',
         f'<tr><th>접속경로</th><td colspan="3">{_inline(ov[5]["text"])}</td></tr>',
         f'<tr><th>주요 내용 및 기능 · 특장점</th><td colspan="3">{_inline(ov[7]["text"])}</td></tr></table></div>',
         "<h3>□ 개인정보보호 기준 충족여부</h3>", '<div class="el-tw"><table class="el-t">',
         '<tr><th rowspan="2">선정기준</th><th rowspan="2">세부 내용</th><th colspan="3">확인</th><th rowspan="2">증빙(예시)</th></tr>',
         "<tr><th class=\"el-n\">충족</th><th class=\"el-n\">미충족</th><th class=\"el-n\">해당 없음</th></tr>"]
    for g in data["required"]:
        for i, it in enumerate(g["items"]):
            boxes = "".join(f'<td class="el-c">{"■" if it["mark"] == m else "□"}</td>' for m in ("충족", "미충족", "해당없음"))
            grp = f'<th rowspan="{len(g["items"])}">{e(g["group"]).replace(chr(10), "<br>")}</th>' if i == 0 else ""
            h.append(f"<tr>{grp}<td>{e(it['text'])}</td>{boxes}<td>{_inline(it['evidence'])}</td></tr>")
    h += ["</table></div>", "<h3>□ 작성일 및 문의처</h3>", '<div class="el-tw"><table class="el-t">',
          f"<tr><th>작성일</th><td>{e(data['date'])}</td></tr><tr><th>문의처</th><td>{_inline(data['contact'])}</td></tr></table></div>"]
    return "\n".join(h)


POPUP_JS = r"""/* edu-legal-mcp: 이용약관·개인정보처리방침 팝업 (자동 생성, 의존성 없음) */
(function () {
  var D = window.__EDU_LEGAL__; if (!D) return;
  var S = D.style;
  var css = "\n.el-footer{margin:32px auto 16px;padding:16px;text-align:center;font-family:" + S.font + ";font-size:13px;color:" + S.text + ";opacity:.85;line-height:1.7}" +
  ".el-footer a{color:inherit;text-decoration:underline;cursor:pointer;margin:0 6px;background:none;border:0;font:inherit;padding:0}" +
  ".el-ov{position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:2147483000;padding:16px;animation:elf .15s}" +
  "@keyframes elf{from{opacity:0}to{opacity:1}}" +
  ".el-m{background:" + S.surface + ";color:" + S.text + ";font-family:" + S.font + ";border-radius:" + S.radius + ";width:min(760px,100%);max-height:min(86vh,900px);display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.25);overflow:hidden;border-top:6px solid " + S.primary + "}" +
  ".el-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:16px 20px;border-bottom:1px solid rgba(0,0,0,.08)}" +
  ".el-h h2{margin:0;font-size:1.15rem;color:" + S.primary + "}" +
  ".el-x{border:0;background:transparent;font-size:26px;line-height:1;cursor:pointer;color:inherit;width:40px;height:40px;border-radius:" + S.radius + "}" +
  ".el-b{padding:4px 20px 16px;overflow-y:auto;-webkit-overflow-scrolling:touch;line-height:1.75;font-size:15px}" +
  ".el-b h3{font-size:1rem;margin:18px 0 6px;color:" + S.primary + "}.el-b p{margin:6px 0}.el-b ul{margin:4px 0;padding-left:20px}" +
  ".el-tbd{background:#fff3b0;color:#7a4b00;border-radius:4px;padding:0 3px}" +
  ".el-note{background:rgba(0,0,0,.04);border-left:4px solid " + S.primary + ";padding:8px 12px;border-radius:6px;font-size:13px}" +
  ".el-tw{overflow-x:auto}.el-t{border-collapse:collapse;width:100%;min-width:560px;font-size:13px}.el-t th,.el-t td{border:1px solid rgba(0,0,0,.25);padding:6px;vertical-align:middle}.el-t th{background:rgba(0,0,0,.06);font-weight:700}.el-c{text-align:center;font-size:16px}.el-n{white-space:nowrap;width:1%}" +
  ".el-f{padding:12px 20px;border-top:1px solid rgba(0,0,0,.08);display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px}" +
  ".el-ok{background:" + S.primary + ";color:" + S.onPrimary + ";border:0;border-radius:" + S.radius + ";padding:10px 22px;font:inherit;font-weight:700;cursor:pointer}" +
  ".el-ok:disabled{opacity:.45;cursor:not-allowed}" +
  "@media (max-width:600px){.el-ov{padding:0;align-items:flex-end}.el-m{max-height:92vh;border-radius:" + S.radius + " " + S.radius + " 0 0}.el-b{font-size:14px}}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  var last = null;
  function open(key) {
    var doc = D.docs[key]; if (!doc) return;
    last = document.activeElement;
    var ov = document.createElement("div"); ov.className = "el-ov";
    ov.innerHTML = '<div class="el-m" role="dialog" aria-modal="true" aria-labelledby="el-t"><div class="el-h"><h2 id="el-t"></h2><button class="el-x" aria-label="닫기">×</button></div>' +
      '<div class="el-b" tabindex="0"></div><div class="el-f"><span class="el-hint">끝까지 읽으면 확인 버튼이 켜져요</span><button class="el-ok" disabled>확인했어요</button></div></div>';
    ov.querySelector("#el-t").textContent = doc.title;
    var body = ov.querySelector(".el-b"); body.innerHTML = doc.html;
    var ok = ov.querySelector(".el-ok"), hint = ov.querySelector(".el-hint");
    function check() { if (body.scrollTop + body.clientHeight >= body.scrollHeight - 8) { ok.disabled = false; hint.textContent = "다 읽었어요 ✓"; } }
    body.addEventListener("scroll", check); setTimeout(check, 50);
    function close() { ov.remove(); document.body.style.overflow = ""; document.removeEventListener("keydown", esc); if (last) last.focus(); }
    function esc(e) { if (e.key === "Escape") close(); }
    ov.querySelector(".el-x").onclick = close; ok.onclick = close;
    ov.addEventListener("click", function (e) { if (e.target === ov) close(); });
    document.addEventListener("keydown", esc);
    document.body.appendChild(ov); document.body.style.overflow = "hidden"; ok.focus({preventScroll:true}); body.focus();
  }
  window.eduLegalOpen = open;
  if (D.noFooter) return;  /* link-only: 앱에 이미 있는 링크에서 eduLegalOpen 호출 */
  function mount() {
    var host = document.querySelector("footer") || (function () { var f = document.createElement("footer"); document.body.appendChild(f); return f; })();
    var box = document.createElement("div"); box.className = "el-footer";
    var links = Object.keys(D.docs).map(function (k) { return '<a role="button" tabindex="0" data-el="' + k + '">' + D.docs[k].label + "</a>"; }).join("|");
    box.innerHTML = "<div>" + links + "</div>" + (D.owner ? "<div>" + D.owner + "</div>" : "");
    host.appendChild(box);
    box.addEventListener("click", function (e) { var k = e.target.getAttribute("data-el"); if (k) open(k); });
    box.addEventListener("keydown", function (e) { var k = e.target.getAttribute("data-el"); if (k && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); open(k); } });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
})();
"""


def _contrast(hexcolor: str) -> str:
    m = re.fullmatch(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", (hexcolor or "").strip())
    if not m:
        return "#ffffff"
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#222222" if (0.299 * r + 0.587 * g + 0.114 * b) > 170 else "#ffffff"


def _write_standalone(root, asset_dir, docs) -> list[str]:
    """팝업 없이 주소로도 열어 볼 수 있는 문서 파일. SPA·기존 링크가 있는 앱에서 이 파일로 연결합니다."""
    made = []
    for key, fn in (("terms", "terms.html"), ("privacy", "privacy.html")):
        if key not in docs:
            continue
        p = inside(root, asset_dir / fn)
        p.write_text("<!doctype html><meta charset=\"utf-8\"><title>" + html.escape(docs[key]["title"]) +
                     "</title><article>" + docs[key]["html"] + "</article>\n", "utf-8")
        made.append(str(p))
    return made


def _snippet(prefix: str) -> str:
    return (
        f'<script src="{prefix}legal-content.js"></script>\n'
        f'<script src="{prefix}legal-popup.js" defer></script>\n'
        '<a role="button" onclick="eduLegalOpen(\'terms\')">이용약관</a>\n'
        '<a role="button" onclick="eduLegalOpen(\'privacy\')">개인정보처리방침</a>'
    )


def install(project: str, analysis: dict, include_checklist: bool = True, html_file: str | None = None) -> dict:
    root = project_root(project)
    d = out_dir(project)
    st = analysis["framework_style"]
    # 앱 CSS에서 읽은 값은 형식 검사 후 사용(이상한 값이면 기본값)
    style = {
        "font": css_value(st.get("font_family"), "font", "inherit"),
        "primary": css_value(st.get("primary"), "color", "#4f46e5"),
        "text": css_value(st.get("text"), "color", "#222222"),
        "surface": "#ffffff",
        "radius": css_value(st.get("radius"), "len", "12px"),
    }
    style["onPrimary"] = _contrast(style["primary"])
    docs, problems, skipped = {}, [], []
    for key, fn, label in [("terms", "terms.md", "이용약관"), ("privacy", "privacy.md", "개인정보처리방침")]:
        p = d / fn
        if not p.exists():
            raise FileNotFoundError("먼저 write_legal_docs를 실행해 주세요.")
        md = p.read_text("utf-8")
        title = next((l[2:] for l in md.splitlines() if l.startswith("# ")), label)
        tbd = [l.strip() for l in md.splitlines() if TBD in l]
        bad = find_forbidden(md)
        if tbd:
            problems.append({"file": str(p), "확인 필요 줄": tbd})
        if bad:
            problems.append({"file": str(p), "금지 표현": bad})
        docs[key] = {"label": label, "title": title, "html": md_to_html(md)}
    if problems:
        qf = d / "questions.md"
        return {"installed": False,
                "reason": "이용약관·개인정보처리방침에 [확인 필요] 또는 금지 표현이 남아 있어 앱에 넣지 않았습니다. 앱 파일은 바꾸지 않았습니다.",
                "problems": problems,
                "questions_for_teacher": qf.read_text("utf-8") if qf.exists() else "",
                "next": "위 질문을 교사에게 하나씩 묻고, 답을 info에 넣어 write_legal_docs를 다시 실행한 뒤 install_footer_popup을 다시 호출하세요. "
                        "[확인 필요]를 지우거나 '" + DRAFT + "' 같은 꼬리표로 대신하지 마세요.",
                "rule": AI_RULE}
    if include_checklist and (d / "checklist.json").exists():
        data = json.loads((d / "checklist.json").read_text("utf-8"))
        ch = checklist_html(data)
        if TBD in ch or find_forbidden(ch):
            skipped.append("checklist: 체크리스트에 [확인 필요]가 남아 있어 하단 링크에 넣지 않았습니다. generate_checklists를 info와 함께 다시 실행하세요.")
        else:
            docs["checklist"] = {"label": "필수기준 체크리스트", "title": f"에듀집 필수기준 체크리스트 – {data['app_name']}", "html": ch}
    meta = read_meta(project)
    owner = ""
    if meta.get("operator_name") and meta.get("school"):
        owner = f"개인정보 보호책임자: {html.escape(meta['operator_name'])} 교사 ({html.escape(meta['school'])})" + (f" | 문의: {html.escape(meta['contact_phone'])}" if meta.get("contact_phone") else "")
    # 정적 파일 위치: Vite/React 등은 public/, 정적 사이트는 루트
    pub = root / "public" if (root / "public").is_dir() or st["framework"] in ("react", "vue", "svelte", "next") else root
    link_mode = (analysis.get("legal_link_mode") or {}).get("mode", "inject")
    # html_file 을 직접 지정하면 그 파일에 연결(교사·AI가 위치를 확인한 경우)
    link_only = (link_mode == "link-only" or st["framework"] == "next") and not html_file
    asset_dir = safe_dir(root, *pub.relative_to(root).parts, "legal")
    # 기존 파일이 있으면 프로젝트 밖을 가리키는 링크가 아닌지 확인 후 덮어씀
    content_js = inside(root, asset_dir / "legal-content.js")
    popup_js = inside(root, asset_dir / "legal-popup.js")
    payload = json.dumps({"style": style, "docs": docs, "owner": owner, "noFooter": link_only}, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    content_js.write_text("window.__EDU_LEGAL__ = " + payload + ";\n", "utf-8")
    popup_js.write_text(POPUP_JS, "utf-8")
    standalone = _write_standalone(root, asset_dir, docs)
    if link_only:
        why = (analysis.get("legal_link_mode") or {}).get("reason") or "SPA 라 index.html 을 직접 고치지 않습니다."
        return {"installed": False, "mode": "link-only",
                "reason": why + " 팝업 파일은 만들었고, 앱 파일(index.html 등)은 바꾸지 않았습니다.",
                "assets": [str(content_js), str(popup_js)] + standalone,
                "existing_links": (analysis.get("legal_link_mode") or {}).get("existing_links", []),
                "snippet": _snippet("./legal/" if pub == root else "/legal/"),
                "how_to_wire": ("이미 있는 '이용약관'·'개인정보처리방침' 링크(또는 버튼)의 클릭 이벤트에서 "
                                "eduLegalOpen('terms'), eduLegalOpen('privacy')를 호출하세요. "
                                "페이지가 열릴 때 두 스크립트를 한 번만 불러오면 됩니다. 아래 snippet 을 참고하세요."),
                "style_used": style, "skipped": skipped, "rule": AI_RULE}
    # index.html 찾기(프로젝트 폴더 안의 .html 파일만 수정)
    if html_file:
        hp = Path(html_file).expanduser()
        target = inside(root, hp if hp.is_absolute() else root / hp)
        if target.suffix.lower() not in (".html", ".htm") or not target.is_file():
            raise UnsafePath(f"html_file은 프로젝트 폴더 안의 기존 .html 파일이어야 합니다: {html_file}")
    else:
        target = next((inside(root, p) for p in [root / "index.html", root / "public" / "index.html", root / "src" / "index.html"] if p.is_file()), None)
    if target is None:
        return {"installed": False, "reason": "index.html을 찾지 못했습니다. html_file 경로를 알려 주세요.", "assets": str(asset_dir)}
    src = target.read_text("utf-8")
    bak = backup(root, target)
    prefix = "./legal/" if pub == root else "/legal/"
    tag = f'{MARK}\n<script src="{prefix}legal-content.js"></script>\n<script src="{prefix}legal-popup.js" defer></script>\n'
    src = re.sub(re.escape(MARK) + r".*?legal-popup\.js[^>]*></script>\n?", "", src, flags=re.S)
    src = src.replace("</body>", tag + "</body>") if "</body>" in src else src + tag
    target.write_text(src, "utf-8")
    return {"installed": True, "mode": "inject", "html_file": str(target), "backup": str(bak), "assets": [str(asset_dir / "legal-content.js"), str(asset_dir / "legal-popup.js")], "style_used": style,
            "footer": "기존 <footer>가 있으면 그 안에, 없으면 body 끝에 링크를 추가합니다(로그인 전/후 모든 화면 공통).",
            "test": "PC·휴대전화 폭에서 열기→끝까지 스크롤→'확인했어요'/×/Esc/바깥 클릭으로 닫기를 확인하세요.",
            "skipped": skipped,
            "note": ("체크리스트 링크는 에듀집 제출용입니다. 학생·학부모가 보는 실제 앱에 필요 없으면 include_checklist=false로 다시 설치하세요. " if "checklist" in docs else "") +
                    "배포는 교사가 직접 확인한 뒤 합니다.",
            "rule": AI_RULE}
