"""edu-legal-mcp 분석기 회귀 테스트 (표준 unittest, 실행: python -m unittest discover tests)."""
import shutil, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edu_legal_mcp import analyzer, legal, popup  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures"
FULL_INFO = {
    "app_name": "테스트 앱", "operator_name": "홍길동", "school": "○○초등학교", "contact_phone": "02-000-0000",
    "contact_email": "teacher@example.sen.go.kr", "effective_date": "2026년 11월 1일", "purpose": "학생 수업용",
    "retention": "해당 학년도 종료 시까지", "features": "글쓰기", "consent_method": "가정통신문",
    "ai_sends_name": False, "ai_retention": "30일", "ai_transfer_type": "처리위탁", "api_key_in_server": True,
    "server_location": "서울", "withdrawal_method": "교사에게 요청", "delete_method": "기록 지우기 버튼",
}


def copy(name):
    d = Path(tempfile.mkdtemp()) / name
    shutil.copytree(FX / name, d)
    return d


def evidence_files(a):
    out = []
    for v in a["signals"].values():
        out += v["근거"]
    for v in list(a["personal_fields"].values()) + list(a["personal_fields_low_confidence"].values()):
        out += v
    return out


class PasswordForm(unittest.TestCase):
    def test_password_is_own_item_not_number(self):
        a = analyzer.analyze(str(copy("password_form")))
        f = a["personal_fields"]
        self.assertIn("비밀번호", f)
        self.assertIn("전화번호", f)
        self.assertIn("아이디", f)
        # 출석번호만 '번호'로 잡혀야 함 (비밀번호·전화번호 칸이 '번호'로 섞이면 안 됨)
        self.assertEqual(len(f.get("번호", [])), 1, f)
        self.assertIn("출석번호", f["번호"][0])
        self.assertNotIn("이름(또는 닉네임)", f)


class StaticHtml(unittest.TestCase):
    def setUp(self):
        self.p = copy("static_html")
        self.a = analyzer.analyze(str(self.p))

    def test_name_high_confidence_activity_and_search_excluded(self):
        f = self.a["personal_fields"]
        self.assertIn("이름(또는 닉네임)", f)
        self.assertEqual(len(f["이름(또는 닉네임)"]), 1)
        joined = " ".join(evidence_files(self.a))
        self.assertNotIn("activityName", joined)
        self.assertNotIn("활동 이름", joined)

    def test_ai_without_personal_payload_is_question(self):
        self.assertTrue(self.a["external_ai"])
        self.assertEqual(self.a["ai_request_may_include_name"], [])
        self.assertTrue(any("AI에 보내는 내용" in q for q in self.a["questions"]))

    def test_inject_mode_and_install(self):
        self.assertEqual(self.a["legal_link_mode"]["mode"], "inject")
        legal.write(str(self.p), self.a, FULL_INFO)
        r = popup.install(str(self.p), self.a, include_checklist=False)
        self.assertTrue(r["installed"], r)
        self.assertIn("legal-popup.js", (self.p / "index.html").read_text("utf-8"))

    def test_guard_blocks_unresolved(self):
        legal.write(str(self.p), self.a, {})
        r = popup.install(str(self.p), self.a)
        self.assertFalse(r["installed"])
        self.assertNotIn("legal-popup.js", (self.p / "index.html").read_text("utf-8"))

    def test_guard_blocks_banned_word(self):
        legal.write(str(self.p), self.a, FULL_INFO)
        pm = self.p / "legal-docs/privacy.md"
        pm.write_text(pm.read_text("utf-8") + "\n" + legal.DRAFT + "\n", "utf-8")
        r = popup.install(str(self.p), self.a)
        self.assertFalse(r["installed"])


class FirebaseSpa(unittest.TestCase):
    def setUp(self):
        self.p = copy("firebase_spa")
        self.a = analyzer.analyze(str(self.p))

    def test_build_and_reference_dirs_excluded(self):
        ev = " ".join(evidence_files(self.a))
        self.assertNotIn("functions/lib", ev)
        self.assertNotIn("참고자료", ev)
        self.assertEqual(self.a["ai_request_may_include_name"], [])

    def test_admin_labels_not_asserted(self):
        f = self.a["personal_fields"]
        self.assertNotIn("학년", f)
        self.assertNotIn("이름(또는 닉네임)", f)

    def test_missed_signals_found(self):
        s = self.a["signals"]
        for k in ("email_send", "secret_manager", "anonymous_auth", "chat_store", "ip_log",
                  "storage_upload", "usage_log", "teacher_profile"):
            self.assertIn(k, s, k)
        items = self.a["personal_items"]
        for it in ("익명 계정 식별자(uid)", "이메일(발송 수신자)", "대화 내용", "업로드 파일(학생 산출물)",
                   "이용 기록", "접속 IP 주소", "교사 계정 정보(이메일·이름)"):
            self.assertIn(it, items)
        self.assertTrue(self.a["collects_personal_info"])
        self.assertTrue(any(h.startswith("90일") for h in self.a["retention_hints"]), self.a["retention_hints"])
        self.assertTrue(any("Secret Manager" in n for n in self.a["safety_notes"]))
        self.assertTrue(any("IP" in q for q in self.a["questions"]))

    def test_privacy_doc_uses_signals(self):
        r = legal.build(self.a, FULL_INFO)
        self.assertIn("이메일 발송 위탁", r["privacy"])
        self.assertIn("Secret Manager", r["privacy"])
        self.assertIn("대화 내용", r["privacy"])

    def test_link_only_mode_does_not_touch_index(self):
        lm = self.a["legal_link_mode"]
        self.assertEqual(lm["mode"], "link-only")
        self.assertTrue(any("App.tsx" in e for e in lm["existing_links"]))
        before = (self.p / "public/index.html").read_text("utf-8")
        legal.write(str(self.p), self.a, FULL_INFO)
        r = legal.build(self.a, FULL_INFO)
        # 교사 질문이 남아 있으면 설치 거부(가드 유지)
        res = popup.install(str(self.p), self.a)
        if "[확인 필요]" in r["privacy"] + r["terms"]:
            self.assertFalse(res["installed"])
        else:
            self.assertEqual(res["mode"], "link-only")
            self.assertTrue((self.p / "public/legal/terms.html").exists())
            self.assertIn("eduLegalOpen", res["snippet"])
        self.assertEqual(before, (self.p / "public/index.html").read_text("utf-8"))

    def test_link_only_writes_standalone_when_resolved(self):
        legal.write(str(self.p), self.a, FULL_INFO)
        d = self.p / "legal-docs"
        for fn in ("terms.md", "privacy.md"):  # 질문 반영이 끝난 상태를 흉내
            (d / fn).write_text((d / fn).read_text("utf-8").replace("[확인 필요]", "교사 확인 완료"), "utf-8")
        res = popup.install(str(self.p), self.a)
        self.assertEqual(res["mode"], "link-only", res)
        self.assertFalse(res["installed"])
        self.assertTrue((self.p / "public/legal/privacy.html").exists())
        self.assertIn('"noFooter": true', (self.p / "public/legal/legal-content.js").read_text("utf-8"))
        self.assertNotIn("legal", (self.p / "public/index.html").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
