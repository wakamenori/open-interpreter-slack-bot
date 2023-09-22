import json
import os
from typing import List

from interpreter.interpreter import Interpreter

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


class OpenInterpreterHelper(Interpreter):
    @classmethod
    def with_default_system_message(cls, temp_dir_path: str):
        instance = cls()
        instance.temp_dir_path = temp_dir_path
        instance.load(instance.read_messages_json())
        instance.auto_run = True
        instance.system_message += generate_system_message(temp_dir_path)
        logger.info({"message": "Open interpreter with default system message.", "temp_dir_path": temp_dir_path})

        return instance

    def read_messages_json(self) -> list:
        """
        Read messages history from temp directory
        :return: list of messages
        """
        messages_file_path = os.path.join(self.temp_dir_path, "messages.json")
        if os.path.exists(messages_file_path):
            with open(messages_file_path, "r") as f:
                messages = json.load(f)
        else:
            messages = []
        logger.info({"message": "Read messages json.", "messages": messages})
        return messages

    def save_messages_json(self, messages: List[dict]):
        """
        Save messages history to temp directory
        :param messages: list of messages
        """
        messages_json = json.dumps(messages, indent=4, ensure_ascii=False)
        with open(os.path.join(self.temp_dir_path, "messages.json"), "w", encoding="utf-8") as f:
            f.write(messages_json)
        logger.info({"message": "Save messages json.", "messages": messages})

    def chat_and_save_messages_json(self, message: str) -> List[dict]:
        """
        Chat with interpreter
        :param message: message to interpreter
        :return: list of response messages from interpreter
        """
        messages = self.chat(message, return_messages=True)
        self.save_messages_json(messages)
        logger.info({"message": "Chat with interpreter.", "messages": messages})
        return messages


def convert_interpreter_responses_to_slack_message(messages: list) -> str:
    output_text = ""

    for message in messages:
        role = message["role"]
        if role == "user":
            continue

        elif role == "assistant":
            content = message["content"]
            output_text += f"\n{content}"
            function_call = message.get("function_call")
            if function_call:
                function_name = function_call["name"]
                if function_name == "run_code":
                    arguments = function_call["parsed_arguments"]
                    code = arguments["code"]
                    language = arguments["language"]
                    output_text += f"\n```{language}\n{code}\n```\n"

        elif role == "function" and message["content"] != "No output":
            output_text += f"\n```{message['content']}```\n"
    logger.info({"message": "Generate response to user.", "output_text": output_text, "messages": messages})
    return output_text
