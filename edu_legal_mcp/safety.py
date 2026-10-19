"""안전장치: 프로젝트 폴더 밖으로 쓰지 않기, 파일 이름 정리, 백업, 입력값 정리."""
from __future__ import annotations
import re, shutil
from datetime import datetime
from pathlib import Path

BOOL_KEYS = {"ai_sends_name", "api_key_in_server"}
_BAD_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]+')
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")


class UnsafePath(ValueError):
    pass


def project_root(project_path: str) -> Path:
    """프로젝트 폴더를 절대 경로로 확정합니다. 드라이브 최상위·홈 폴더 자체는 거부합니다."""
    if not project_path or not str(project_path).strip():
        raise UnsafePath("project_path가 비어 있습니다.")
    root = Path(project_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"프로젝트 폴더가 없습니다: {root}")
    if root.parent == root or root == Path.home().resolve():
        raise UnsafePath(f"드라이브 최상위나 홈 폴더 전체는 분석·수정하지 않습니다. 웹앱 프로젝트 폴더를 지정해 주세요: {root}")
    return root


def inside(root: Path, p: Path) -> Path:
    """p가 (심볼릭 링크를 따라가도) root 안에 있는지 확인하고 실제 경로를 돌려줍니다."""
    rp = Path(p).resolve()
    if rp != root and not rp.is_relative_to(root):
        raise UnsafePath(f"프로젝트 폴더 밖의 경로에는 쓰지 않습니다: {p}")
    return rp


def safe_dir(root: Path, *parts: str) -> Path:
    d = root.joinpath(*parts)
    inside(root, d)
    d.mkdir(parents=True, exist_ok=True)
    return inside(root, d)


def safe_filename(s, fallback: str = "app", limit: int = 60) -> str:
    """사용자 정보(앱 이름·성명)로 파일 이름을 만들 때 경로 구분자·특수문자를 없앱니다."""
    t = _BAD_NAME.sub("_", str(s or "")).strip(" .")
    t = re.sub(r"\.{2,}", "_", t)[:limit].strip(" .")
    return t or fallback


def backup(root: Path, target: Path, keep: int = 5) -> Path:
    """수정 전 파일을 legal-docs/backup/에 시간 붙여 복사합니다(최근 keep개 유지)."""
    bdir = safe_dir(root, "legal-docs", "backup")
    dst = bdir / f"{target.name}.{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.bak"
    shutil.copy2(target, dst)
    olds = sorted(bdir.glob(f"{target.name}.*.bak"))
    for o in olds[:-keep]:
        o.unlink()
    return dst


def xml_text(s) -> str:
    """XML 1.0에 넣을 수 없는 제어문자를 지웁니다(특수문자 이스케이프는 lxml이 처리)."""
    return _CTRL.sub("", str(s if s is not None else ""))


def _bool(v):
    if isinstance(v, bool) or v is None:
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y", "예", "네", "o"):
        return True
    if s in ("false", "0", "no", "n", "아니오", "아니요", "x", ""):
        return False
    return None


def clean_info(info) -> dict:
    """info 값을 문자열(또는 지정 키는 True/False)로 정리합니다."""
    if not info:
        return {}
    if not isinstance(info, dict):
        raise ValueError("info는 키-값 객체여야 합니다.")
    out = {}
    for k, v in info.items():
        k = str(k)
        if k in BOOL_KEYS:
            out[k] = _bool(v)
        elif v is None:
            continue
        else:
            out[k] = xml_text(v if isinstance(v, str) else (", ".join(map(str, v)) if isinstance(v, (list, tuple)) else v)).strip()[:2000]
    return out


# ---- 팝업 CSS에 들어가는 스타일 값 검사(앱 CSS에서 읽은 값이 CSS를 깨뜨리지 않도록) ----
_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla)\([0-9.,%\s/+-]+\)|[a-zA-Z]{3,20}")
_LEN = re.compile(r"(\d+(\.\d+)?(px|rem|em|%)?\s*){1,4}")
_FONT = re.compile(r"[\w\s,'\"\-가-힣]{1,200}")


def css_value(v, kind: str, default: str) -> str:
    v = (v or "").strip()
    rx = {"color": _COLOR, "len": _LEN, "font": _FONT}[kind]
    return v if v and rx.fullmatch(v) else default
