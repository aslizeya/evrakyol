from app.config import REPO_ROOT
from app.process_types import load_process_types


def test_mvp_contains_eight_unique_process_types() -> None:
    types = load_process_types(REPO_ROOT / "config")
    codes = [t.code for t in types]
    assert len(codes) == 8
    assert len(set(codes)) == len(codes)
    assert "miras_arac_devri" in codes
