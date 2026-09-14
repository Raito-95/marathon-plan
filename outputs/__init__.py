"""輸出層：課表產生與呈現方式分開，加新格式只要在 FORMATS 註冊。"""

from . import intervals, json_out, markdown, text

FORMATS = {
    "text": text.render,            # 單週，給 LINE 或終端機
    "markdown": markdown.render,    # 整份課表
    "json": json_out.render,        # 整份課表
    "intervals": intervals.render,  # 本週與下週，預覽 --sync 會上傳的課
}

__all__ = ["FORMATS", "intervals", "json_out", "markdown", "text"]
