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
