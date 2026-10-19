"""HWPX(한글) 읽기/쓰기 도우미.

- 원본 학교용 체크리스트 .hwpx 패키지를 템플릿으로 사용합니다(header.xml 스타일 그대로).
- fill_cells(): 원본 표의 셀 텍스트만 바꿔 양식을 100% 보존합니다.
- build_document(): 같은 스타일로 새 표/문단을 만들어 HWPX로 저장합니다(에듀집 양식 재구성, 약관 문서).
"""
from __future__ import annotations
import copy, secrets, zipfile, io, struct, zlib
from pathlib import Path
from lxml import etree
from .safety import xml_text

# 외부 엔티티·네트워크 접근을 끈 파서(XXE 방지)
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)


def _parse(b: bytes):
    return etree.fromstring(b, PARSER)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS = {"hp": HP}
TEMPLATE = Path(__file__).parent / "templates" / "school_checklist.hwpx"
TEXT_WIDTH = 48190  # A4, 좌우 여백 제외(HWPUNIT)


def q(tag: str) -> str:
    return "{%s}%s" % (HP, tag)


def _load(path: Path = TEMPLATE) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def _blank_png(w=200, h=283) -> bytes:
    raw = b"".join(b"\x00" + b"\xff" * (w * 3) for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _save(files: dict[str, bytes], out: Path, preview_text: str) -> Path:
    files = dict(files)
    files["Preview/PrvText.txt"] = xml_text(preview_text)[:1000].encode("utf-8")
    files["Preview/PrvImage.png"] = _blank_png()
    out.parent.mkdir(parents=True, exist_ok=True)
    order = ["mimetype"] + [n for n in files if n != "mimetype"]
    with zipfile.ZipFile(out, "w") as z:
        for n in order:
            ct = zipfile.ZIP_STORED if n in ("mimetype", "version.xml", "Preview/PrvImage.png") else zipfile.ZIP_DEFLATED
            z.writestr(zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0)), files[n], compress_type=ct)
    validate(out)
    return out


def validate(path: Path) -> list[str]:
    """패키지 구조와 XML 형식을 검사합니다. 문제가 있으면 예외."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        def need(ok, msg):
            if not ok:
                raise ValueError(f"HWPX 검사 실패: {msg}")
        need(names and names[0] == "mimetype", "mimetype이 첫 항목이 아님")
        need(z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED, "mimetype 압축됨")
        need(z.read("mimetype") == b"application/hwp+zip", "mimetype 값 이상")
        for req in ["version.xml", "Contents/header.xml", "Contents/section0.xml", "Contents/content.hpf", "META-INF/container.xml"]:
            need(req in names, f"{req} 누락")
        for n in names:
            if n.endswith((".xml", ".hpf", ".rdf")):
                _parse(z.read(n))
    return names


def _cell_map(root) -> dict[tuple[int, int, int], etree._Element]:
    out = {}
    for ti, tbl in enumerate(root.iter(q("tbl"))):
        for tc in tbl.iter(q("tc")):
            a = tc.find("hp:cellAddr", NS)
            out[(ti, int(a.get("rowAddr")), int(a.get("colAddr")))] = tc
    return out


def _set_tc_text(tc, text: str):
    sub = tc.find("hp:subList", NS)
    ps = sub.findall("hp:p", NS)
    proto = ps[0]
    for p in ps:
        sub.remove(p)
    for line in (text.split("\n") if text else [""]):
        sub.append(_para_like(proto, line))


def _para_like(proto, text: str):
    p = copy.deepcopy(proto)
    for ls in p.findall("hp:linesegarray", NS):
        p.remove(ls)
    runs = p.findall("hp:run", NS)
    for r in runs[1:]:
        p.remove(r)
    if not runs:
        r = etree.SubElement(p, q("run"), charPrIDRef="0")
    else:
        r = runs[0]
    for c in list(r):
        r.remove(c)
    t = etree.SubElement(r, q("t"))
    t.text = xml_text(text)
    return p


def fill_cells(values: dict[tuple[int, int, int], str], out: Path, template: Path = TEMPLATE) -> Path:
    """(표 번호, 행, 열) -> 텍스트. 원본 표 구조/스타일은 그대로 둡니다."""
    files = _load(template)
    root = _parse(files["Contents/section0.xml"])
    cells = _cell_map(root)
    for key, text in values.items():
        if key not in cells:
            raise KeyError(f"셀 {key} 이(가) 원본 양식에 없습니다")
        _set_tc_text(cells[key], text)
    files["Contents/section0.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    prev = "\n".join(" | ".join(t for t in [values[k]]) for k in sorted(values))
    return _save(files, out, prev)


# ---------------- 새 문서 만들기 (원본 스타일 재사용) ----------------
class _Protos:
    def __init__(self, root):
        cells = _cell_map(root)
        big = list(root.iter(q("tbl")))[1]
        self.tbl = big
        self.head = cells[(1, 0, 3)]      # 회색 머리글 셀
        self.body = cells[(1, 3, 1)]      # 본문 셀(왼쪽 정렬)
        self.group = cells[(1, 3, 0)]     # 선정기준 셀
        self.check = cells[(1, 3, 4)]     # 가운데 체크 셀
        self.evid = cells[(1, 3, 12)]     # 증빙 셀
        self.title = cells[(0, 0, 2)]     # 제목 셀
        first_p = root.find("hp:p", NS)
        self.plain_p = first_p
        self.head_p = self.head.find("hp:subList/hp:p", NS)
        self.title_p = self.title.find("hp:subList/hp:p", NS)


def _set(el, **kw):
    for k, v in kw.items():
        el.set(k, str(v))


def _make_tc(proto, r, c, rs, cs, w, h, text):
    tc = copy.deepcopy(proto)
    _set(tc.find("hp:cellAddr", NS), rowAddr=r, colAddr=c)
    _set(tc.find("hp:cellSpan", NS), rowSpan=rs, colSpan=cs)
    _set(tc.find("hp:cellSz", NS), width=w, height=h)
    _set_tc_text(tc, text)
    return tc


def _make_table(P: _Protos, widths: list[int], cells: list[dict], row_h=1665):
    """cells: {r,c,rs,cs,text,kind(head|body|group|check|evid)}"""
    nrows = max(x["r"] + x.get("rs", 1) for x in cells)
    tbl = copy.deepcopy(P.tbl)
    for tr in tbl.findall("hp:tr", NS):
        tbl.remove(tr)
    tbl.set("id", str(10**9 + secrets.randbelow(10**9)))
    tbl.set("rowCnt", str(nrows)); tbl.set("colCnt", str(len(widths)))
    _set(tbl.find("hp:sz", NS), width=sum(widths), height=nrows * row_h)
    for r in range(nrows):
        tr = etree.SubElement(tbl, q("tr"))
        for x in sorted([x for x in cells if x["r"] == r], key=lambda x: x["c"]):
            cs, rs = x.get("cs", 1), x.get("rs", 1)
            w = sum(widths[x["c"]:x["c"] + cs])
            proto = getattr(P, x.get("kind", "body"))
            tr.append(_make_tc(proto, r, x["c"], rs, cs, w, row_h * rs, x.get("text", "")))
    return tbl


def build_document(blocks: list[tuple], out: Path) -> Path:
    """blocks: ("title", text) | ("heading", text) | ("para", text) | ("table", widths, cells)"""
    files = _load()
    root = _parse(files["Contents/section0.xml"])
    P = _Protos(root)
    first = P.plain_p
    # 첫 문단: secPr(용지 설정)만 남김
    for run in first.findall("hp:run", NS):
        for ch in list(run):
            if ch.tag not in (q("secPr"), q("ctrl")):
                run.remove(ch)
    for ls in first.findall("hp:linesegarray", NS):
        first.remove(ls)
    for p in root.findall("hp:p", NS)[1:]:
        root.remove(p)
    preview = []
    for b in blocks:
        kind = b[0]
        if kind == "table":
            p = _para_like(first, "")
            p.attrib.pop("id", None); p.set("id", "2147483648")
            for r in p.findall("hp:run", NS):
                for ch in list(r):
                    r.remove(ch)
                r.append(_make_table(P, b[1], b[2]))
                etree.SubElement(r, q("t"))
            root.append(p)
            preview.append(" | ".join(c.get("text", "") for c in b[2]))
        else:
            proto = {"title": P.title_p, "heading": P.head_p}.get(kind, first)
            p = _para_like(proto, b[1])
            for r in p.findall("hp:run", NS):
                for ch in list(r):
                    if ch.tag in (q("secPr"), q("ctrl")):
                        r.remove(ch)
            p.set("id", "2147483648")
            root.append(p)
            preview.append(b[1])
    files["Contents/section0.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return _save(files, out, "\n".join(preview))


def dump_tables(path: Path) -> list[list[list[str]]]:
    """검증용: HWPX의 표를 (표 → 행 → 셀 텍스트)로 읽습니다."""
    with zipfile.ZipFile(path) as z:
        root = _parse(z.read("Contents/section0.xml"))
    res = []
    for tbl in root.iter(q("tbl")):
        rows = []
        for tr in tbl.findall("hp:tr", NS):
            rows.append(["/".join("".join(p.itertext()) for p in tc.find("hp:subList", NS).findall("hp:p", NS)) for tc in tr.findall("hp:tc", NS)])
        res.append(rows)
    return res
