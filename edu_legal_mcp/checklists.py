"""체크리스트 작성: 원본 양식 항목·번호·표 구조를 그대로 유지합니다.

- 학교용: 원본 '필수기준체크리스트(학교용).hwpx'의 셀만 바꿔 저장(양식 100% 보존)
- 에듀집용: 원본 .hwp(개인정보 있는/없는) 표 구조를 같은 행·열·병합으로 HWPX에 재구성
"""
from __future__ import annotations
import json, re
from datetime import date
from pathlib import Path
from . import hwpx
from .legal import ART, TBD, out_dir

ON, OFF = "■", "□"
NA = "[해당 없음]"

# 원본 양식의 필수기준 항목(번호·문구 그대로). 그룹: (선정기준, [(번호, 세부 내용)])
REQUIRED = [
    ("1. 최소처리 원칙 준수", [("1-1", "1-1. 개인정보가 최소한으로 수집되는가?"),
                          ("1-2", "1-2. 개인정보 수집·이용 목적이 기재되어 있는가?"),
                          ("1-3", "1-3. 개인정보 수집항목, 보유기간 등이 기재되어 있는가?")]),
    ("2. 개인정보\n안전조치 의무", [("2-1", "2-1. 개인정보 안전성 확보에 필요한 조치 사항이 기재되어 있는가?")]),
    ("3. 열람/정정/ 삭제/처리정지 절차", [("3-1", "3-1. 이용자에게 언제든지 자신의 정보를 열람·정정·삭제·처리정지를 요구할 수 있는 절차가 안내되어 있는가?")]),
    ("4. 만14세 미만 아동의\n개인정보 보호", [("4-1", "4-1. 만 14세 미만 아동의 경우 법정대리인 동의 등 아동의 개인정보 보호를 위한 절차가 마련되어 있는가?")]),
    ("5. 보호책임자/ 제3자제공/ 위탁 등", [("5-1", "5-1. 개인정보 보호책임자 관련 정보가 안내되어 있는가?"),
                                ("5-2", "5-2. 개인정보 제3자 제공에 관한 정보가 기재되어 있는가? (필요시)"),
                                ("5-3", "5-3. 개인정보 위·수탁관계에 관한 정보가 기재되어 있는가? (필요시)")]),
]
SCHOOL_OPTIONAL = [
    ("1. 교육목표 및 학생특성 적합성", "1-1. 수업 목표와 학생의 학습 수준에 적합한 내용과 기능을 제공하는가?"),
    ("2. 콘텐츠 품질 및 안전성", "2-1. 학습 콘텐츠가 정확하고 신뢰할 수 있으며, 학생 연령에 적합·안전한가?"),
    ("3. 사용 환경 적합성", "3-1. 학교의 기기·네트워크 환경에서 모든 학생이 안정적으로 사용할 수 있는가?"),
    ("4. 접근성 및 사용성", "4-1. 교사와 학생이 필요한 기능과 자료에 쉽게 접근하고 활용할 수 있는가?"),
    ("5. 서비스 운영 및 지원체계", "5-1. 이용 안내, 기술 지원, 문의 대응 등 서비스 지원 체계를 갖추고 있는가?"),
]
ITEM_ART = {"1-1": ["항목"], "1-2": ["목적"], "1-3": ["보유", "항목"], "2-1": ["안전"], "3-1": ["권리"], "4-1": ["아동"], "5-1": ["책임자"], "5-2": ["제공위탁"], "5-3": ["제공위탁"]}


def _articles(privacy_md: str) -> dict[int, str]:
    arts, cur = {}, None
    for line in privacy_md.splitlines():
        m = re.match(r"##\s*제(\d+)조", line)
        if m:
            cur = int(m.group(1)); arts[cur] = ""
        elif cur:
            arts[cur] += line + "\n"
    return arts


def answer_required(a: dict, privacy_md: str, privacy_path: str) -> dict[str, dict]:
    """각 항목: {mark: 충족|미충족|해당없음|None, evidence, question}"""
    arts = _articles(privacy_md)
    pi = a["collects_personal_info"]
    res = {}
    def cite(keys):
        return "개인정보 처리방침 " + ", ".join(f"제{ART[k]}조" for k in keys)
    for _, items in REQUIRED:
        for no, _t in items:
            keys = ITEM_ART[no]
            unsure = [k for k in keys if TBD in arts.get(ART[k], TBD)]
            code = ""
            if no in ("1-1", "1-3") and a["personal_fields"]:
                code = " / 코드: " + "; ".join(f"{k} {v[0]}" for k, v in list(a["personal_fields"].items())[:2])
            if no == "2-1" and a["external_ai"]:
                code = " / 코드: " + a["external_ai"][0]["근거"][0]
            if no == "3-1" and a["has_delete_feature"]:
                code = " / 삭제 기능: " + a["has_delete_feature"][0]
            if not pi and no != "5-1":
                res[no] = {"mark": "해당없음", "evidence": f"{NA} 회원가입·이름 입력 등 개인정보 입력 기능이 코드에 없음 (분석 근거: 입력 필드 검사 결과 없음)"}
                continue
            if no in ("5-2", "5-3"):
                if not a["external_ai"] and not a["backends"]:
                    res[no] = {"mark": "해당없음", "evidence": f"{NA} 외부로 개인정보를 보내는 코드 없음 ({cite(keys)})"}
                    continue
                kind = "제3자 제공" if no == "5-2" else "처리위탁"
                ext = ", ".join([x["provider"] for x in a["external_ai"]] + a["backends"])
                res[no] = {"mark": None, "evidence": f"{TBD} 외부 서비스({ext})로 데이터 전송이 있어 {kind} 해당 여부를 확인해야 함 ({cite(keys)}, 근거: {(a['external_ai'] or [{'근거': ['']}])[0]['근거'][0]})",
                           "question": f"{no}: {ext} 전송이 '{kind}'에 해당하는지 학교/교육청과 확인해 주세요."}
                continue
            if unsure:
                res[no] = {"mark": None, "evidence": f"{TBD} {cite(keys)}에 미확인 내용이 있음{code}", "question": f"{no}: {cite(unsure)}의 [확인 필요]를 채우면 충족으로 바꿀 수 있습니다."}
            else:
                res[no] = {"mark": "충족", "evidence": f"({cite(keys)}){code} — {privacy_path}"}
    return res


def _boxes(mark):
    return [ON if mark == m else OFF for m in ("충족", "미충족", "해당없음")]


def school_optional(a: dict, info: dict | None = None) -> list[str]:
    info = info or {}
    ai = ", ".join(x["provider"] for x in a["external_ai"])
    return [
        f"교사 답변: {a['audience_guess']} 대상 활동 {TBD}\n학교 확인: 교육과정·학년 적합성 판단",
        "교사 답변: " + (f"AI 응답({ai})은 참고용임을 이용약관에 안내, 연령 적합성 필터 {TBD}" if ai else f"콘텐츠 출처 {TBD}") + "\n학교 확인: 콘텐츠 정확성·안전성 검토",
        f"교사 답변: 설치 없는 웹앱({a['framework_style']['framework']}), 반응형 화면 {TBD}\n학교 확인: 학교 기기·네트워크에서 시험 사용",
        "교사 답변: 화면 하단 이용약관·개인정보처리방침 링크(팝업) 제공\n학교 확인: 학생·교사 사용성 확인",
        f"교사 답변: 문의 연락처 {info.get('contact_phone') or TBD}, 사용 안내 자료 {TBD}\n학교 확인: 지원 체계 적정성 판단",
    ]


def generate(project: str, a: dict, info: dict | None) -> dict:
    info = info or {}
    d = out_dir(project)
    pp = d / "privacy.md"
    if not pp.exists():
        raise FileNotFoundError("먼저 draft_legal_docs로 개인정보처리방침 초안을 만들어 주세요.")
    privacy = pp.read_text("utf-8")
    rel_pp = "legal-docs/privacy.md"
    ans = answer_required(a, privacy, rel_pp)
    variant = a["checklist_variant"]
    name = info.get("app_name") or a["app_title"]
    q = [v["question"] for v in ans.values() if v.get("question")]

    # ---- 학교용 (원본 hwpx 셀 채우기) ----
    rows = {"1-1": 3, "1-2": 4, "1-3": 5, "2-1": 6, "3-1": 7, "4-1": 8, "5-1": 9, "5-2": 10, "5-3": 11}
    vals = {(0, 0, 2): "학습지원 소프트웨어 선정기준 체크리스트(학교용) [검토 초안]"}
    for no, r in rows.items():
        b = _boxes(ans[no]["mark"])
        vals[(1, r, 4)], vals[(1, r, 5)], vals[(1, r, 8)] = b
        vals[(1, r, 12)] = ans[no]["evidence"]
    for i, txt in enumerate(school_optional(a, info)):
        r = 13 + i
        vals[(1, r, 4)], vals[(1, r, 6)], vals[(1, r, 9)] = OFF, OFF, OFF  # 선택기준: 학교 판단 영역
        vals[(1, r, 11)] = txt
    school_path = d / f"필수기준체크리스트(학교용)_{name}_검토초안.hwpx"
    hwpx.fill_cells(vals, school_path)

    # ---- 에듀집 (원본 hwp 표 구조 재구성) ----
    W = [7600, 19300, 3000, 3000, 3000, 12290]
    overview = [
        {"r": 0, "c": 0, "text": "제품/서비스명", "kind": "head"}, {"r": 0, "c": 1, "text": name},
        {"r": 0, "c": 2, "text": "공급자", "kind": "head"}, {"r": 0, "c": 3, "text": "교사"},
        {"r": 1, "c": 0, "text": "접속경로", "kind": "head"}, {"r": 1, "c": 1, "cs": 3, "text": info.get("access_url") or f"{TBD} (아직 배포 전)"},
        {"r": 2, "c": 0, "text": "주요 내용 및 기능 · 특장점", "kind": "head"},
        {"r": 2, "c": 1, "cs": 3, "text": info.get("summary") or f"{name}: {_feat(a)} {TBD}"},
    ]
    OW = [9000, 19190, 7000, 13000]
    main = [{"r": 0, "c": 0, "rs": 2, "text": "선정기준", "kind": "head"}, {"r": 0, "c": 1, "rs": 2, "text": "세부 내용", "kind": "head"},
            {"r": 0, "c": 2, "cs": 3, "text": "확인", "kind": "head"}, {"r": 0, "c": 5, "rs": 2, "text": "증빙(예시)", "kind": "head"},
            {"r": 1, "c": 2, "text": "충족", "kind": "head"}, {"r": 1, "c": 3, "text": "미충족", "kind": "head"}, {"r": 1, "c": 4, "text": "해당 없음", "kind": "head"}]
    r = 2
    for grp, items in REQUIRED:
        main.append({"r": r, "c": 0, "rs": len(items), "text": grp, "kind": "group"})
        for no, t in items:
            b = _boxes(ans[no]["mark"])
            main += [{"r": r, "c": 1, "text": t}, {"r": r, "c": 2, "text": b[0], "kind": "check"}, {"r": r, "c": 3, "text": b[1], "kind": "check"},
                     {"r": r, "c": 4, "text": b[2], "kind": "check"}, {"r": r, "c": 5, "text": ans[no]["evidence"], "kind": "evid"}]
            r += 1
    contact = " ".join(x for x in [("전화) " + info["contact_phone"]) if info.get("contact_phone") else "", ("이메일) " + info["contact_email"]) if info.get("contact_email") else ""] if x) or TBD
    tail = [{"r": 0, "c": 0, "text": "작성일", "kind": "head"}, {"r": 0, "c": 1, "text": date.today().strftime("%Y.%-m.%-d")},
            {"r": 1, "c": 0, "text": "문의처", "kind": "head"}, {"r": 1, "c": 1, "text": contact}]
    blocks = [("heading", "□ 제품/서비스 개요"), ("table", OW, overview), ("para", ""),
              ("heading", "□ 개인정보보호 기준 충족여부"), ("table", W, main), ("para", ""),
              ("heading", "□ 작성일 및 문의처"), ("table", [9000, 39190], tail)]
    edzip_path = d / f"에듀집 필수기준 체크리스트({name}_{info.get('operator_name') or '000'})_{variant}_초안.hwpx"
    hwpx.build_document(blocks, edzip_path)

    data = {"variant": variant, "app_name": name, "overview": overview, "required": [
        {"group": g, "items": [{"no": no, "text": t, "mark": ans[no]["mark"], "evidence": ans[no]["evidence"]} for no, t in items]} for g, items in REQUIRED],
        "school_optional": [{"group": g, "text": t, "answer": x} for (g, t), x in zip(SCHOOL_OPTIONAL, school_optional(a, info))],
        "date": date.today().isoformat(), "contact": contact}
    (d / "checklist.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    md = [f"# 체크리스트 작성 결과 ({variant})", "", "| 번호 | 확인 | 증빙 |", "|---|---|---|"]
    for g in data["required"]:
        for it in g["items"]:
            md.append(f"| {it['no']} | {it['mark'] or '[확인 필요]'} | {it['evidence']} |")
    md += ["", "## 추가로 확인할 내용"] + [f"- {x}" for x in q] + ["- 학교용 '선택기준'은 학교가 판단할 영역이라 체크하지 않았습니다(교사 답변/학교 확인 구분 기재).", "", "※ 아직 제출·공개하지 마세요."]
    (d / "checklist_summary.md").write_text("\n".join(md), "utf-8")
    return {"variant": variant, "files": [str(edzip_path), str(school_path), str(d / "checklist.json"), str(d / "checklist_summary.md")], "questions": q, "answers": ans}


def _feat(a):
    from .legal import _features
    return _features(a).replace(f" {TBD}", "")
