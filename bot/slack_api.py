import os
import urllib.request

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from logging_conf import logger


def get_thread_parent_message_user_id(client: WebClient, channel_id: str, thread_ts: str) -> str:
    """
    Get id of user who sent the parent message of thread.
    :param client: slack web client
    :param channel_id: channel id
    :param thread_ts: thread ts
    :return: thread parent message user id
    """
    try:
        response = client.conversations_replies(channel=channel_id, ts=thread_ts)
        messages = response["messages"]
        original_thread_ts = messages[0]["user"]
        logger.info(
            {
                "message": "Get thread parent message user id.",
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "original_thread_ts": original_thread_ts,
            }
        )
        return original_thread_ts
    except SlackApiError as e:
        print(f"SlackApiError: {e.response['error']}")
        logger.error({"message": "SlackApiError", **e.__dict__})
        raise e


def get_bot_id(client: WebClient) -> str:
    """
    Get slack bot id.
    :param client: slack web client
    :return: bot id
    """
    try:
        response = client.auth_test()
        logger.info({"message": "Get bot id.", "bot_id": response["user_id"]})
        return response["user_id"]
    except SlackApiError as e:
        logger.error({"message": "SlackApiError", **e.__dict__})
        raise e


def load_files_uploaded_by_user(client: WebClient, file_id: str, save_dir_path: str) -> str:
    """
    Load files uploaded by user to cloud run.
    :param client: slack web client
    :param file_id: file id
    :param save_dir_path: directory path to save file
    :return: path of saved file
    """
    try:
        # Call the files.info method using the WebClient
        result = client.files_info(file=file_id)

        file_info = result["file"]

        file_url = file_info["url_private"]
        file_name = file_info["name"]

        # Download the file
        opener = urllib.request.build_opener()
        opener.addheaders = [("Authorization", "Bearer " + os.environ.get("SLACK_BOT_TOKEN", ""))]
        urllib.request.install_opener(opener)
        if not os.path.exists(save_dir_path):
            os.makedirs(save_dir_path)
        file_path = os.path.join(save_dir_path, file_name)
        urllib.request.urlretrieve(file_url, file_path)
        logger.info({"message": "Download file to cloud run.", "file_path": file_path})
        return file_path
    except SlackApiError as e:
        logger.error({"message": "SlackApiError", **e.__dict__})
        raise e


def upload_file_to_thread(client: WebClient, channel_id: str, thread_ts: str, file_path: str):
    try:
        response = client.files_upload(channels=channel_id, thread_ts=thread_ts, file=file_path)
        logger.info(
            {
                "message": "Upload file to thread.",
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "file_path": file_path,
            }
        )
        assert response["file"]  # the uploaded file
    except Exception as e:
        logger.error({"message": "SlackApiError", **e.__dict__})
        raise e
