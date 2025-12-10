# core/history.py
from typing import Optional, List, Tuple, Dict
from ..repository.abc import NewsItemRepository

# 全局 repo 实例（由 main 注入）
_repo: Optional[NewsItemRepository] = None

def set_repository(repo: NewsItemRepository):
    global _repo
    _repo = repo

def read_all_today_titles(current_platform_ids: Optional[List[str]] = None) -> Tuple[Dict, Dict, Dict]:
    if _repo is None:
        raise RuntimeError("Repository not initialized")
    return _repo.get_all_today(current_platform_ids)

def detect_latest_new_titles(current_platform_ids: Optional[List[str]] = None) -> Dict:
    if _repo is None:
        raise RuntimeError("Repository not initialized")
    return _repo.get_latest_new_titles(current_platform_ids)