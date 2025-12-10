# reporting/__init__.py
from .html_generator import generate_html_report, render_html_content
from .formatters import (
    format_title_for_platform,
    render_feishu_content,
    render_dingtalk_content,
)
from .data_preparer import prepare_report_data 
from .batch_utils import split_content_into_batches, add_batch_headers, get_max_batch_header_size