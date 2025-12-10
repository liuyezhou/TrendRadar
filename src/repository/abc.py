# repository/abc.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

class NewsItemRepository(ABC):
    @abstractmethod
    def save_batch(self, news_items: List[Dict]) -> None:
        """保存一批新闻条目"""
        pass

    @abstractmethod
    def get_all_today(self, platform_ids: Optional[List[str]] = None) -> Tuple[Dict, Dict, Dict]:
        """获取当天所有新闻（all_results, id_to_name, title_info）"""
        pass

    @abstractmethod
    def get_latest_new_titles(self, platform_ids: Optional[List[str]] = None) -> Dict:
        """检测最新批次中的新增标题"""
        pass