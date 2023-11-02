from typing import List

from interpreter.core.core import Interpreter
from custom_interpreter.utils import (
    generate_system_message,
    load_messages_json,
    save_messages_json,
)

from logging_conf import logger
from custom_interpreter.respond_hepler import respond


class OpenInterpreterHelper(Interpreter):
    temp_dir_path: str

    def __init__(self, temp_dir_path: str):
        super().__init__()
        self.temp_dir_path = temp_dir_path
        self.auto_run = True
        self.messages = load_messages_json(temp_dir_path)
        self.system_message += generate_system_message(temp_dir_path)

    def _respond(self):
        yield from respond(self)

    def chat_and_save_messages_json(self, message: str) -> List[dict]:
        """
        Chat with interpreter
        :param message: message to interpreter
        :return: list of response messages from interpreter
        """
        messages = self.chat(message, stream=False)
        messages = [message for message in messages]  # TODO: fix this
        save_messages_json(self.temp_dir_path, messages)
        logger.info({"message": "Chat with interpreter.", "messages": messages})
        return messages


def convert_interpreter_responses_to_slack_message(messages: list) -> str:
    logger.info(
        {
            "message": "Convert interpreter responses to slack message.",
            "messages": messages,
        }
    )
    output_text = ""

    for message in messages:
        role = message["role"]
        if role == "user":
            continue

        elif role == "assistant":
            content = message.get("message")
            language = message.get("language")  # いらないかも
            code = message.get("code")

            if code is not None and language is not None:
                output_text += f"\n```\n{code}\n```\n"
            if content is not None:
                output_text += f"\n{content}\n"

    logger.info(
        {
            "message": "Generate response to user.",
            "output_text": output_text,
            "messages": messages,
        }
    )
    return output_text
