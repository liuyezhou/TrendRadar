# utils/text.py
import re

def clean_title(title: str) -> str:
    """清理标题中的特殊字符"""
    if not isinstance(title, str):
        title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    cleaned_title = cleaned_title.strip()
    return cleaned_title

def html_escape(text: str) -> str:
    """HTML转义"""
    if not isinstance(text, str):
        text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

def strip_markdown(text: str) -> str:
    """去除文本中的 markdown 语法格式，用于个人微信推送"""
    # 去除粗体 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # 去除斜体 *text* 或 _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    # 去除删除线 ~~text~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # 转换链接 [text](url) -> text url（保留 URL）
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2', text)
    # 去除图片 ![alt](url) -> alt
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)
    # 去除行内代码 `code`
    text = re.sub(r'`(.+?)`', r'\1', text)
    # 去除引用符号 >
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # 去除标题符号 # ## ### 等
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # 去除水平分割线 --- 或 ***
    text = re.sub(r'^[\-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    # 去除 HTML 标签 <font color='xxx'>text</font> -> text
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    # 清理多余的空行（保留最多两个连续空行）
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()