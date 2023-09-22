import os

from flask import Flask, request
from slack_bolt import App, BoltResponse, Say
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient

import gcloud_storage
import slack_api
from helpers import get_temp_dir
from interpreter_helper import OpenInterpreterHelper, convert_interpreter_responses_to_slack_message
from logging_conf import logger

app = Flask(__name__)
slack_app = App(token=os.environ["SLACK_BOT_TOKEN"], signing_secret=os.environ["SLACK_SIGNING_SECRET"])
handler = SlackRequestHandler(slack_app)


@app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@slack_app.middleware
def handle_retry(req, next):
    if "x-slack-retry-num" in req.headers and req.headers["x-slack-retry-reason"][0] == "http_timeout":
        return BoltResponse(status=200, body="success")

    next()


@slack_app.event("app_mention")
def mentioned(body, say: Say):
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_token)
    event = body["event"]
    thread_ts = event.get("thread_ts", None) or event["ts"]
    channel_id = event["channel"]
    parent_message_user_id = slack_api.get_thread_parent_message_user_id(client, channel_id, thread_ts)
    text = event["text"]
    message_by_user = text.replace(f"<@{slack_api.get_bot_id(client)}>", "").strip()

    temp_dir = get_temp_dir(parent_message_user_id, thread_ts)
    bucket_name = gcloud_storage.get_bucket_name(parent_message_user_id)
    os.makedirs(temp_dir, exist_ok=True)
    loaded_file_paths = gcloud_storage.download_files_from_bucket(bucket_name, temp_dir, thread_ts + "/")

    logger.info(
        {
            "message": "Bot mentioned.",
            "parent_message_user_id": parent_message_user_id,
            "thread_ts": thread_ts,
            "channel_id": channel_id,
            "message_by_user": message_by_user,
            "temp_dir": temp_dir,
            "loaded_file_paths": loaded_file_paths,
        }
    )

    if message_by_user == "ダウンロード":
        for file_path in loaded_file_paths:
            if file_path.endswith("/messages.json"):
                continue
            slack_api.upload_file_to_thread(client, channel_id, thread_ts, file_path)
        return

    files = event.get("files", [])
    file_paths = []
    for file in files:
        file_path = slack_api.load_files_uploaded_by_user(client, file["id"], temp_dir)
        file_paths.append(file_path)
        message_by_user = f"I uploaded {file['name']} to {temp_dir}\n{message_by_user}"
        logger.info({"message": "Loading file to local.", "file_path": file_path})

    if message_by_user == "":
        say(text="Enter something", thread_ts=thread_ts)
        logger.info({"message": "Empty message."})
        return

    interpreter = OpenInterpreterHelper.with_default_system_message(temp_dir)
    previous_messages_length = len(interpreter.messages)
    messages = interpreter.chat_and_save_messages_json(message_by_user)
    new_messages = messages[previous_messages_length:]
    display_message = convert_interpreter_responses_to_slack_message(new_messages)

    gcloud_storage.upload_files_to_bucket(temp_dir, bucket_name, thread_ts + "/")
    say(text=display_message, thread_ts=thread_ts)
