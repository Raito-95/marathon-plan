"""輸出層：課表產生與呈現方式分開，加新格式只要在 FORMATS 註冊。"""

from . import json_out, markdown, text

FORMATS = {
    "text": text.render,          # 單週，給 LINE 或終端機
    "markdown": markdown.render,  # 整份課表
    "json": json_out.render,      # 整份課表
}

__all__ = ["FORMATS", "json_out", "markdown", "text"]
