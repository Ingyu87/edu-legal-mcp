"""이용약관·개인정보처리방침 작성 (예시 문서의 '구조'만 따르고 사실은 분석 결과/교사 확인 정보로만 채움).

생성 문서는 실제 앱에 그대로 붙는 최종본 형식입니다. 임시본 표시는 넣지 않고,
확인하지 못한 사실만 [확인 필요]로 남깁니다(이 표시가 남아 있으면 팝업 설치가 거부됩니다)."""
from __future__ import annotations
import json, re
from datetime import date
from pathlib import Path
from . import hwpx
from .safety import project_root, safe_dir, clean_info, inside

TBD = "[확인 필요]"
# 실제 앱·문서에 들어가면 안 되는 표시(최종 문서에 임시본 꼬리표 금지)
DRAFT = "\ucd08\uc548"  # 금지어 자체를 소스에 그대로 적지 않습니다
FORBIDDEN = [DRAFT, "시연용", "검토용", "확정 전", "확정된 이용약관이 아닙", "확정된 개인정보"]
AI_RULE = ("[AI 작업 규칙] ① [확인 필요] 항목은 추측하지 말고 모두 교사에게 질문해 info로 채운 뒤 다시 생성하세요. "
           "② 앱 화면·팝업 제목·하단 링크·문서 어디에도 '" + DRAFT + "', '검토 " + DRAFT + "', '시연용', '검토용', '확정 전' 같은 말이나 "
           "'확정된 약관이 아닙니다' 같은 면책 문구를 넣지 마세요. 문서는 시행일이 있는 최종본으로 게시됩니다. "
           "③ [확인 필요]가 남은 문서는 install_footer_popup이 앱에 넣지 않습니다.")
META = "meta.json"
LEGACY = [f"이용약관({DRAFT}).hwpx", f"개인정보처리방침({DRAFT}).hwpx", "draft_meta.json"]
# 개인정보처리방침 조문 번호(체크리스트 증빙에서 동일하게 사용)
ART = {"목적": 1, "보유": 2, "항목": 3, "아동": 4, "파기": 5, "안전": 6, "권리": 7, "책임자": 8, "제공위탁": 9, "변경": 10}


def out_dir(project: str) -> Path:
    root = project_root(project)
    d = safe_dir(root, "legal-docs")
    # legal-docs 안에 프로젝트 밖을 가리키는 링크 파일이 있으면 덮어쓰지 않음
    for p in list(d.iterdir()) + (list((d / "backup").iterdir()) if (d / "backup").is_dir() else []):
        if p.is_symlink():
            inside(root, p)
    return d


def find_forbidden(text: str) -> list[str]:
    return [w for w in FORBIDDEN if w in text]


def read_meta(project: str) -> dict:
    d = out_dir(project)
    for fn in (META, "draft_meta.json"):
        if (d / fn).exists():
            return clean_info(json.loads((d / fn).read_text("utf-8")).get("info", {}) or {})
    return {}


def _v(info: dict, key: str, q: list, question: str) -> str:
    val = (info or {}).get(key)
    if val:
        return str(val)
    if question not in q:
        q.append(question)
    return TBD


def build(analysis: dict, info: dict | None) -> dict:
    info = clean_info(info)
    q: list[str] = []
    ev: list[str] = []
    name = info.get("app_name") or analysis["app_title"]
    if not info.get("app_name"):
        q.append(f"서비스 이름을 '{name}'(으)로 표기해도 될까요? (index.html <title> 기준)")
    op = _v(info, "operator_name", q, "운영 주체(개발 교사) 성명은 무엇인가요?")
    school = _v(info, "school", q, "소속 학교명은 무엇인가요?")
    phone = _v(info, "contact_phone", q, "문의 연락처(학교 교무실 등 공용 번호)는 무엇인가요? 개인 휴대전화는 권장하지 않습니다.")
    email = info.get("contact_email") or TBD
    if email == TBD:
        q.append("문의 이메일(학교/교육청 계정)을 적을까요?")
    eff = _v(info, "effective_date", q, "약관·처리방침 시행일(예: 2026년 11월 1일)은 언제로 할까요?")
    feats = info.get("features") or _features(analysis)
    if TBD in feats:
        q.append(f"주요 기능을 이렇게 적어도 될까요? '{_features(analysis).replace(' ' + TBD, '')}' (맞으면 info.features에 확정 문구를 넣어 주세요)")
    use = info.get("purpose") or analysis.get("audience_guess", TBD)
    if TBD in use:
        q.append("이 앱은 학생 수업용인가요, 교사 행정업무용인가요? 이용 대상 학년은?")
    retention = info.get("retention") or TBD
    if retention == TBD and analysis["collects_personal_info"]:
        q.append("개인정보 보유 기간을 어떻게 정할까요? (예: 해당 학년도 종료 시까지, 또는 '브라우저에서 기록 지우기 전까지')")
    items = analysis["personal_items"]
    stor = analysis["storage_locations"]
    ais = analysis["external_ai"]
    for k, v in analysis["signals"].items():
        ev.append(f"- {v['설명']}: {', '.join(v['근거'][:4])}")
    for k, v in analysis["personal_fields"].items():
        ev.append(f"- 입력 항목 '{k}': {', '.join(v[:3])}")
    sends_name = info.get("ai_sends_name")  # True/False/None
    if analysis["ai_request_may_include_name"] and sends_name is None:
        q.append("외부 AI로 보내는 요청에 학생 이름이 함께 전송되나요? (코드상 가능성: " + ", ".join(analysis["ai_request_may_include_name"][:3]) + ") 전송하지 않도록 바꾸는 것을 권장합니다.")
    elif analysis["external_ai"] and not analysis["ai_request_may_include_name"] and sends_name is None:
        q.append("[확인 필요] 외부 AI 호출은 있지만, 코드에서 이름 등 개인정보가 함께 가는지는 확인하지 못했습니다. AI에 보내는 내용이 글·그림·이름 중 무엇인지 알려 주세요. (info.ai_sends_name)")
    for qq in analysis.get("questions", []):
        if qq not in q:
            q.append(qq)
    if analysis.get("retention_hints") and not info.get("retention"):
        q.append("코드에 보관 기간으로 보이는 값이 있습니다(" + ", ".join(analysis["retention_hints"][:3]) + "). 개인정보 보유 기간을 이 값으로 정할까요?")
    ai_ret = info.get("ai_retention")
    ai_type = info.get("ai_transfer_type")
    if ais and not ai_ret:
        q.append("외부 AI 서비스의 데이터 보관·학습 활용 정책(예: API 데이터 30일 보관, 학습 미사용)을 확인하셨나요? 계약/약관 기준으로 적어 주세요.")
    delm = info.get("delete_method")
    if "localStorage" in analysis["signals"] and not analysis["has_delete_feature"] and not delm:
        q.append("브라우저에 저장된 기록을 지우는 버튼이 없습니다. 삭제 방법을 무엇으로 안내할까요? (예: '기록 지우기' 버튼 추가, info.delete_method)")
    if ais and not ai_type:
        q.append("외부 AI로 보내는 것을 '처리위탁'과 '제3자 제공' 중 무엇으로 안내할까요? (학교·교육청 안내 기준, info.ai_transfer_type)")
    if ais and not info.get("api_key_in_server"):
        q.append("외부 AI 호출 키(API Key)를 서버 환경변수에만 보관하고 화면 코드에 노출하지 않나요? (맞으면 info.api_key_in_server=true)")
    if analysis["backends"] and not info.get("server_location"):
        q.append("데이터베이스 서버 위치(국가/리전)는 어디인가요? (info.server_location)")
    if analysis["collects_personal_info"] and not info.get("consent_method"):
        q.append("만 14세 미만 학생의 보호자 동의는 어떤 방식(가정통신문, 학교 일괄 동의 등)으로 받으셨나요? (info.consent_method)")
    if "auth" in analysis["signals"] and not info.get("withdrawal_method"):
        q.append("회원 탈퇴는 어떻게 하나요? (info.withdrawal_method)")
    hosting = analysis["hosting"] or [TBD]
    if not analysis["hosting"]:
        q.append("배포(호스팅) 서비스는 무엇인가요? (예: Vercel, Netlify, GitHub Pages)")
    pi = analysis["collects_personal_info"]

    # ---------- 이용약관 ----------
    T = [f"# {name} 이용약관", "", f"시행일: {eff}", "",
         f"본 이용약관(이하 '약관')은 {name}(이하 '본 서비스')이 제공하는 교육용 웹 애플리케이션의 이용에 관한 사항을 규정합니다.", "",
         "## 제1조 (목적)", f"이 약관은 {school} {op} 교사가 교육 활동을 위해 제공하는 본 서비스를 이용함에 있어 서비스 제공자와 이용자의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.", "",
         "## 제2조 (정의)", "1. '서비스'란 본 웹 애플리케이션과 그 기능을 말합니다.",
         "2. '이용자'란 본 서비스에 접속하여 이 약관에 따라 서비스를 이용하는 사람을 말합니다." + ("" if "auth" in analysis["signals"] else " 본 서비스는 회원가입 없이 이용합니다."), "",
         "## 제3조 (약관의 게시와 개정)", "① 본 서비스는 이 약관을 화면 하단 '이용약관' 링크를 통해 언제든지 확인할 수 있도록 게시합니다.",
         "② 본 서비스는 관련 법령을 위반하지 않는 범위에서 약관을 개정할 수 있으며, 개정 시 적용일자와 개정 사유를 적용일 7일 전부터 서비스 화면에 공지합니다.", "",
         "## 제4조 (서비스의 내용)", f"① 본 서비스는 {use} 목적의 무료 교육용 웹 애플리케이션입니다.",
         "② 주요 기능: " + feats, "③ 본 서비스는 상업적 목적으로 운영되지 않으며, 별도의 결제가 없습니다.", ""]
    n = 5
    if ais:
        T += [f"## 제{n}조 (인공지능 기능 이용 시 유의사항)",
              "① 본 서비스의 AI 피드백은 외부 인공지능 서비스(" + ", ".join(a['provider'] for a in ais) + ")가 생성하며, 내용이 부정확하거나 학생 연령에 맞지 않을 수 있습니다.",
              "② 이용자는 AI 응답을 참고 자료로만 활용하며, 중요한 판단은 교사의 안내를 따릅니다.",
              "③ 이용자는 AI 입력란에 주민등록번호, 주소, 전화번호 등 개인정보나 다른 사람의 정보를 입력하지 않습니다.", ""]; n += 1
    T += [f"## 제{n}조 (서비스의 중단)", "① 시스템 점검, 외부 서비스 장애, 통신 두절 등의 사유로 서비스 제공이 일시 중단될 수 있습니다.",
          "② 본 서비스는 무료 교육용 서비스이므로 중단에 따른 별도 보상은 없습니다.", ""]; n += 1
    if "auth" in analysis["signals"]:
        T += [f"## 제{n}조 (회원가입과 탈퇴)", "① 만 14세 미만 아동은 보호자(법정대리인)의 동의를 받은 후 이용할 수 있습니다.", f"② 회원 탈퇴 방법: {info.get('withdrawal_method') or TBD}", ""]; n += 1
    else:
        T += [f"## 제{n}조 (만 14세 미만 이용자)", "만 14세 미만 이용자는 교사의 지도와 학교 안내(가정통신문 등)에 따라 서비스를 이용합니다.", ""]; n += 1
    T += [f"## 제{n}조 (이용자의 의무)", "이용자는 다음 행위를 해서는 안 됩니다.", "1. 다른 사람의 이름이나 정보를 도용하는 행위", "2. 욕설, 비방 등 다른 사람에게 상처를 주는 내용을 입력하는 행위",
          "3. 서비스의 정상적인 운영을 방해하는 행위", "4. 서비스의 내용을 무단으로 변경하거나 복제·배포하는 행위", ""]; n += 1
    T += [f"## 제{n}조 (저작권)", "① 서비스 화면과 자료의 저작권은 서비스 제공자에게 있습니다.", "② 이용자가 작성한 글의 권리는 이용자에게 있습니다.", ""]; n += 1
    T += [f"## 제{n}조 (면책)", "① 본 서비스는 무료 교육용 서비스로서 기술적 오류에 대해 고의 또는 중대한 과실이 없는 한 책임을 지지 않습니다.",
          "② 외부 서비스(AI, 호스팅 등)의 장애로 인한 손해에 대해서는 해당 제공자의 정책이 적용될 수 있습니다.", ""]; n += 1
    T += [f"## 제{n}조 (문의 및 분쟁 해결)", f"서비스 관련 문의: {school} {op} 교사 / 연락처 {phone}", "본 서비스와 이용자 간 분쟁은 대한민국 법을 따릅니다.", "",
          "## 부칙", f"이 약관은 {eff}부터 시행됩니다."]

    # ---------- 개인정보처리방침 ----------
    P = [f"# {name} 개인정보 처리방침", "", f"시행일: {eff}", "",
         f"{name}(이하 '본 서비스')은(는) 「개인정보 보호법」 제30조에 따라 정보주체의 개인정보를 보호하고 관련 고충을 신속하게 처리하기 위하여 다음과 같이 개인정보 처리방침을 수립·공개합니다.", ""]
    if pi:
        purpose = ["서비스 제공: " + feats]
        if "이름(또는 닉네임)" in items:
            purpose.append("이름(또는 닉네임): 화면 표시 및 학생 본인의 활동 기록 구분")
        P += [f"## 제{ART['목적']}조 (개인정보의 처리 목적)", "본 서비스는 다음 목적을 위하여 개인정보를 처리하며, 목적이 변경되면 「개인정보 보호법」 제18조에 따라 별도 동의를 받는 등 필요한 조치를 합니다."] + [f"- {x}" for x in purpose] + [""]
        P += [f"## 제{ART['보유']}조 (개인정보의 처리 및 보유 기간)", f"- 저장 위치: {', '.join(stor) or TBD}", f"- 보유 기간: {retention}",
              "- 파기 시점: 보유 기간 종료 또는 이용자가 기록을 삭제한 즉시" + ("" if "localStorage" not in analysis["signals"] else " (브라우저 저장 정보는 개발자 서버로 전송되지 않으며 이용자 기기에만 남습니다)"), ""]
        P += [f"## 제{ART['항목']}조 (처리하는 개인정보 항목)", "본 서비스는 학습 지원에 필요한 최소한의 정보만 처리합니다.", f"- 수집 항목: {', '.join(items)}",
              "- 수집 방법: 이용자가 화면에 직접 입력", "- 수집하지 않는 항목: 주민등록번호, 주소, 전화번호 등 학습에 불필요한 정보" + (" (이용자가 AI 입력란에 직접 적지 않도록 안내합니다)" if ais else ""), ""]
        P += [f"## 제{ART['아동']}조 (만 14세 미만 아동의 개인정보 처리)", "① 만 14세 미만 아동의 개인정보는 학교 가정통신문(개인정보 수집·이용·제공 동의서) 등을 통해 법정대리인의 동의를 받은 후 처리합니다.",
              "② 법정대리인이 동의하지 않는 경우 이름 대신 별명을 사용하는 등 개인정보 없이 이용하도록 안내합니다." if "localStorage" in analysis["signals"] else "② 법정대리인이 동의하지 않는 경우 서비스 이용이 제한될 수 있습니다.", f"- 동의 절차 운영 방식: {info.get('consent_method') or TBD}", ""]
        P += [f"## 제{ART['파기']}조 (개인정보의 파기 절차 및 방법)", "① 보유 기간이 지나거나 처리 목적이 달성되면 지체 없이 파기합니다."]
        if "localStorage" in analysis["signals"]:
            P += [f"② 브라우저에 저장된 정보는 {delm}" if delm else "② 브라우저에 저장된 정보는 " + ("화면의 기록 삭제 기능 또는 " if analysis["has_delete_feature"] else "") + "브라우저의 사이트 데이터 삭제로 즉시 지울 수 있습니다."]
        if analysis["backends"]:
            P += ["③ 서버(DB)에 저장된 정보는 복구할 수 없는 방법으로 영구 삭제합니다."]
        P += [""]
        sec = ["전 구간 암호화 통신(HTTPS) 사용" + (f" (호스팅: {', '.join(hosting)})" if hosting else "")]
        if ais:
            sec.append("외부 AI 호출 키(API Key)는 서버 환경변수에 보관하고 화면 코드에 노출하지 않음" + ("" if info.get("api_key_in_server") else " " + TBD))
        for note in analysis.get("safety_notes", []):
            sec.append(note)
        if "localStorage" in analysis["signals"]:
            sec.append("입력 정보는 이용자 기기의 브라우저 저장소에만 보관(개발자 서버에 저장하지 않음)")
        sec.append("개인정보 처리 담당자를 개발 교사 1인으로 최소화")
        P += [f"## 제{ART['안전']}조 (개인정보의 안전성 확보 조치)", "본 서비스는 「개인정보 보호법」 제29조에 따라 다음 조치를 하고 있습니다."] + [f"- {s}" for s in sec] + [""]
        P += [f"## 제{ART['권리']}조 (정보주체와 법정대리인의 권리·의무 및 행사 방법)", "① 정보주체(학생)와 법정대리인은 언제든지 개인정보 열람·정정·삭제·처리정지를 요구할 수 있습니다.",
              "② " + ("화면의 기록 삭제 기능으로 즉시 삭제할 수 있으며, " if analysis["has_delete_feature"] else "") + f"담당 교사에게 구두·서면으로 요청하면 지체 없이 조치합니다. (연락처: {phone})", ""]
    else:
        P += [f"## 제{ART['목적']}조 (개인정보의 처리 목적)", "본 서비스는 회원가입·로그인이 없고 이름 등 개인을 알아볼 수 있는 정보를 입력받지 않아 개인정보를 처리하지 않습니다.", "",
              f"## 제{ART['보유']}조 (개인정보의 처리 및 보유 기간)", "처리하는 개인정보가 없으므로 해당 없음.", "",
              f"## 제{ART['항목']}조 (처리하는 개인정보 항목)", "수집 항목 없음.", "",
              f"## 제{ART['아동']}조 (만 14세 미만 아동의 개인정보 처리)", "만 14세 미만 아동의 개인정보를 수집하지 않습니다.", "",
              f"## 제{ART['파기']}조 (개인정보의 파기)", "파기할 개인정보가 없습니다.", "",
              f"## 제{ART['안전']}조 (안전성 확보 조치)", "전 구간 암호화 통신(HTTPS)을 사용합니다.", "",
              f"## 제{ART['권리']}조 (정보주체의 권리)", "수집된 정보가 없어 열람·삭제 대상이 없습니다. 문의는 아래 책임자에게 할 수 있습니다.", ""]
    P += [f"## 제{ART['책임자']}조 (개인정보 보호책임자)", "개인정보 처리에 관한 업무를 총괄하고 고충 처리를 위해 아래와 같이 보호책임자를 지정합니다.",
          f"- 성명: {op} (개발자)", f"- 소속: {school}", "- 직위: 교사", f"- 연락처: {phone} (※ 교사 개인 휴대전화는 기재하지 않습니다)", ] + ([f"- 이메일: {email}"] if email != TBD else []) + [""]
    P += [f"## 제{ART['제공위탁']}조 (개인정보의 제3자 제공·처리위탁·국외 이전)"]
    if ais:
        for a in ais:
            if analysis["ai_request_may_include_name"] and sends_name is None:
                nm = " 및 이름(전송 여부 " + TBD + ")"
            else:
                nm = " 및 이름" if sends_name else ""
            P += [f"- 외부 AI: {a['provider']} / 이전 국가: {a['country']} / 이전 항목: 학생이 입력한 글{nm}" +
                  f" / 이전 시기·방법: AI 피드백 요청 시 인터넷(HTTPS)으로 전송 / 목적: AI 피드백 생성 / 보유 기간: {ai_ret or '제공자 정책에 따름 ' + TBD}"]
        if ai_type:
            P += [f"- 위 외부 AI 전송은 개인정보 {ai_type}에 해당하며, 국외 이전 사항은 이 조항으로 알립니다." + (" 이름 등 개인을 알아볼 수 있는 정보는 보내지 않습니다." if sends_name is False else "")]
        else:
            P += [f"- 위 전송이 '제3자 제공'인지 '처리위탁'인지, 국외 이전 고지·동의 필요 여부: {TBD}"]
    if analysis["backends"]:
        P += [f"- 데이터 저장 위탁: {', '.join(analysis['backends'])} / 서버 위치: {info.get('server_location') or TBD}"]
    sig = analysis["signals"]
    if "email_send" in sig:
        P += ["- 이메일 발송 위탁: 발송 업체(코드 근거 " + ", ".join(sig["email_send"]["근거"][:2]) + ") / 위탁 항목: 수신자 이메일 주소 / 목적: 안내 메일 발송 / 보유 기간: " + TBD]
    if "storage_upload" in sig:
        P += ["- 파일 저장: 업로드한 파일(학생 산출물)을 서버 저장소에 보관 (근거 " + ", ".join(sig["storage_upload"]["근거"][:2]) + ")"]
    if not ais and not analysis["backends"] and "email_send" not in sig:
        P += ["본 서비스는 개인정보를 제3자에게 제공하거나 처리를 위탁하지 않습니다." + (f" (호스팅: {', '.join(hosting)})" if hosting else "")]
    P += ["", f"## 제{ART['변경']}조 (개인정보 처리방침의 변경)", f"이 개인정보 처리방침은 {eff}부터 적용됩니다."]

    return {"terms": "\n".join(T), "privacy": "\n".join(P), "questions": q, "evidence": ev}


def _features(a: dict) -> str:
    f = []
    if a["personal_fields"]:
        f.append("이름 등 정보 입력")
    if a["external_ai"]:
        f.append("외부 AI를 이용한 피드백 제공")
    if "localStorage" in a["signals"]:
        f.append("활동 기록을 이용자 기기에 저장")
    if a["backends"]:
        f.append("서버에 학습 기록 저장")
    return ", ".join(f) + f" {TBD}" if f else TBD


def md_to_blocks(md: str) -> list[tuple]:
    blocks = []
    for line in md.splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            blocks.append(("title", line[2:]))
        elif line.startswith("## "):
            blocks.append(("heading", line[3:]))
        elif line.startswith("- "):
            blocks.append(("para", "  · " + line[2:]))
        else:
            blocks.append(("para", line))
    return blocks


def write(project: str, analysis: dict, info: dict | None) -> dict:
    d = out_dir(project)
    info = clean_info(info)
    r = build(analysis, info)
    for fn in LEGACY:  # 예전 버전이 만든 임시본 파일 정리
        if (d / fn).exists():
            (d / fn).unlink()
    (d / "terms.md").write_text(r["terms"] + "\n", "utf-8")
    (d / "privacy.md").write_text(r["privacy"] + "\n", "utf-8")
    qtxt = "# 교사에게 확인할 질문\n\n" + ("[확인 필요] 항목은 교사에게 확인해 info로 채운 뒤 다시 생성하세요." + "\n\n" if r["questions"] else "") + "\n".join(f"{i}. {x}" for i, x in enumerate(r["questions"], 1)) + "\n\n# 코드에서 찾은 근거\n\n" + "\n".join(r["evidence"]) + "\n"
    (d / "questions.md").write_text(qtxt, "utf-8")
    hwpx.build_document(md_to_blocks(r["terms"]), d / "이용약관.hwpx")
    hwpx.build_document(md_to_blocks(r["privacy"]), d / "개인정보처리방침.hwpx")
    (d / META).write_text(json.dumps({"info": info or {}, "date": date.today().isoformat()}, ensure_ascii=False, indent=2), "utf-8")
    return {"files": [str(d / x) for x in ["terms.md", "privacy.md", "questions.md", "이용약관.hwpx", "개인정보처리방침.hwpx"]],
            "questions": r["questions"], "evidence": r["evidence"],
            "unresolved_count": (r["terms"] + r["privacy"]).count(TBD), "rule": AI_RULE}
