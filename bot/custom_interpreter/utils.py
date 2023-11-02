import json
import os
from typing import List

from logging_conf import logger


def generate_system_message(temp_dir_path: str) -> str:
    return f"""
You are running in a remote sandbox environment, so any files you generate will be private.
You must respect the following rules:
1. Current directory is read-only. Use {temp_dir_path} as your working directory and generate all files there.
2. Use PYTHON to run any code you need.
3. If you need to use a third-party library, install it immediately.
4. Answer in Japanese.
5. Save all data and files to `{temp_dir_path}`.
6. Please reinitialize variables and files each time, as each request comes from a new session.

You can use the following libraries without installing:
- pandas
- numpy
- matplotlib
- seaborn
- scikit-learn
- pandas-datareader
- mplfinance
- yfinance
- requests
- scrapy
- beautifulsoup4
- opencv-python
- ffmpeg-python
- PyMuPDF
- pytube
- pyocr
- easyocr
- pydub
- pdfkit
- weasyprint
"""


def load_messages_json(temp_dir_path: str) -> List[dict]:
    """
    Read messages history from temp directory
    :return: list of messages
    """
    messages_file_path = os.path.join(temp_dir_path, "messages.json")
    if os.path.exists(messages_file_path):
        with open(messages_file_path, "r") as f:
            messages = json.load(f)
    else:
        messages = []
    logger.info({"message": "Read messages json.", "messages": messages})
    return messages


def save_messages_json(temp_dir_path: str, messages: List[dict]):
    """
    Save messages history to temp directory
    :param temp_dir_path: path to temp directory
    :param messages: list of messages
    """
    messages_json = json.dumps(messages, indent=4, ensure_ascii=False)
    with open(os.path.join(temp_dir_path, "messages.json"), "w", encoding="utf-8") as f:
        f.write(messages_json)
    logger.info({"message": "Save messages json.", "messages": messages})
