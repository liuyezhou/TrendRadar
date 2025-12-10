# utils/time.py
import pytz
from datetime import datetime
from pathlib import Path

def get_beijing_time():
    """获取北京时间"""
    return datetime.now(pytz.timezone("Asia/Shanghai"))

def format_date_folder():
    """格式化日期文件夹"""
    return get_beijing_time().strftime("%Y年%m月%d日")

def format_time_filename():
    """格式化时间文件名"""
    return get_beijing_time().strftime("%H时%M分")

def is_first_crawl_today() -> bool:
    """检测是否是当天第一次爬取"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"
    if not txt_dir.exists():
        return True
    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1