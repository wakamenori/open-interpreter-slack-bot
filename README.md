# Bot の仕様

今回作成するBotの仕様は以下のようになっています。

1. Botはメンションすることで起動し、スレッド内に出力結果を送信する
1. スレッド内でさらにメンションすることで会話を継続できる
1. スレッドごとに会話履歴とOpen interpreterの操作するファイルが分離している
    - 新規スレッドを立てればクリーンな状態から処理を開始できる
    - 複数スレッドから全く同じ名前のファイルが作成されてもバッティングしない
1. ファイルをアップロードし、それを読み込ませられる
    - アップロードしたCSVを分析させるなどが可能
1. Open interpreterの作成したファイルをダウンロードできる
    - 作成したグラフなどを、全てSlack内で閲覧できる
1. 定番のライブラリを事前にインストールしている
    - 余分なインストール時間が発生するのを防ぐ

# 工夫ポイント

## ファイルや会話履歴を保持したい

同じスレッドからは同じファイルにアクセスできるようにするため「処理の前にGCSから読みとり」「処理が終わったらGCSに保存」を行います。

少しでもわかりやすいようにGCSのバケット名を`open-interpreter-<UserId>`のようにし、スレッドごとにGCSのパス(prefix)も分けます。

```py
def get_bucket_name(user_id: str) -> str:
    return f"open-interpreter-{user_id}".lower()
```

Open interpreterの処理が始まる前にGCSからCloud Runにファイルを読み取る。

```python
def download_files_from_bucket(bucket_name: str, destination_dir_path: str, blob_prefix: str) -> List[str]:
    """
    Download files from GCS bucket to cloud run
    :param bucket_name: bucket name to download
    :param destination_dir_path: directory path to save files
    :param blob_prefix: prefix of blob to download
    """
    # Initialize the Cloud Storage client
    storage_client = storage.Client()

    if not os.path.exists(destination_dir_path):
        os.makedirs(destination_dir_path)

    # Check if the bucket exists
    if not storage_client.lookup_bucket(bucket_name):
        storage_client.create_bucket(bucket_name)
        return []

    # Get the bucket
    bucket = storage_client.get_bucket(bucket_name)

    file_paths = []

    # Loop through the blobs (files) and download them
    for blob in bucket.list_blobs(prefix=blob_prefix):
        file_name = os.path.basename(blob.name)
        destination_file_path = os.path.join(destination_dir_path, file_name)
        blob.download_to_filename(destination_file_path)
        file_paths.append(destination_file_path)
    return file_paths

```

Open interpreterの処理が終わった後にCloud RunからGCSにファイルを保存する。

```python
def upload_files_to_bucket(local_directory_path: str, bucket_name: str, blob_prefix: str):
    """
    Upload files from cloud run to GCS bucket
    :param local_directory_path: directory path to upload files in cloud run
    :param bucket_name: bucket name to upload
    :param blob_prefix: prefix of blob to upload
    """
    # Initialize the Cloud Storage client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.get_bucket(bucket_name)

    # Check if the directory exists
    if not os.path.exists(local_directory_path):
        return

    ignore_patterns = get_ignore_patterns(".gitignore")

    # Loop through each file in the temporary directory
    for root, _, files in os.walk(local_directory_path):
        for filename in files:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in ignore_patterns):
                continue

            source_file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_file_path, local_directory_path)
            blob_name = os.path.join(blob_prefix, relative_path)

            # Create a blob
            blob = bucket.blob(blob_name)

            # Upload the file
            blob.upload_from_filename(source_file_path)
```

何でもかんでも保存する必要はないので`.gitignore`に記載されているファイルはアップロードしないようにしています。
ただし、今回はCloud Run上にtmpフォルダを作って作業するのですが(後述)、tmpフォルダ内には無駄なものは作られないらしく、この処理は不要っぽいです。

```python
def get_ignore_patterns(ignore_file_path):
    if os.path.exists(ignore_file_path):
        with open(ignore_file_path, "r") as f:
            return f.read().splitlines()
    else:
        return []
```

Open interpreterではこれまでの会話履歴の取得、読み込み機能が搭載されています。
そこでこの`messages`を`messages.json`として保存し、これもGCSにアップすることで会話履歴を保存します。

```python
messages = interpreter.chat("My name is Killian.", return_messages=True)  # Save messages to 'messages'
interpreter.reset()  # Reset interpreter ("Killian" will be forgotten)

interpreter.load(messages)  # Resume chat from 'messages' ("Killian" will be remembered)
```

```python
...


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


...
```

## ユーザーからのファイルアップロードを受け付けたい

ユーザーがSlack上でファイルをアップロードすると`event["files"]`にその情報が入るので、fileのidを元にSlack APIを使ってCloud
Runにロードします。
その上で、ユーザーメッセージに「`<ファイル名>を<アップロード先のパス>にアップしました。`」と追加してOpen
interpreterに認識させてあげます。

なお、この処理もBotへのメンションをトリガーとしているためファイルをアップロードする際もメンションが必須になります。

```python
@slack_app.event("app_mention")
def mentioned(body, say: Say):
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_token)
    event = body["event"]

    ...

    files = event.get("files", [])
    file_paths = []
    for file in files:
        file_path = slack_api.load_file(client, file["id"], temp_dir)
        file_paths.append(file_path)
        message_by_user = f"I uploaded {file['name']} to {temp_dir}\n{message_by_user}"

    ...
```

```python
def load_file(client: WebClient, file_id: str, save_dir_path: str) -> str:
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
        return file_path
    except SlackApiError as e:
        raise e
```

次に、ユーザーが処理結果をダウンロードできるようにします。
できればChatGPTに上手いこと認識してほしいですが、ここではハードコーディングで対応します。
ユーザーが「`@Open Interpreter ダウンロード`」とメッセージを送信した時だけ分岐し、Cloud Run上のファイルをスレッドに送信します。
なお`message.json`は基本的に不要なので除いています。

```python
    ...
loaded_file_paths = gcloud_storage.download_files_from_bucket(parent_message_user_id, thread_ts)

if message_by_user == "ダウンロード":
    for file_path in loaded_file_paths:
        if file_path.endswith("/messages.json"):
            continue
        slack_api.upload_file_to_thread(client, channel_id, thread_ts, file_path)
    return
...
```

```python
def upload_file_to_thread(client: WebClient, channel_id: str, thread_ts: str, file_path: str):
    try:
        response = client.files_upload(channels=channel_id, thread_ts=thread_ts, file=file_path)
        assert response["file"]  # the uploaded file
    except Exception as e:
        logger.error({"message": "SlackApiError", **e.__dict__})
        raise e
```

## 同時リクエスト問題

Cloud Runでは、1コンテナが同時に捌くリクエストの数を指定することができます。
ここで1を指定すれば、おそらくこの問題は無視できますが、今回はデフォルト設定のまま、別の方法で対応します。

やるべきこと2つあります。

1. スレッドごとにCloud Run内での作業フォルダを分割する
1. Open interpreterの呼び出し方を変える

### スレッドごとにCloud Run内での作業フォルダを分割する

スレッドごとにユニークCloud Run内の作業フォルダを作成し、GCSからのダウンロード・アップロードもそのフォルダのみで行います。
`user_id`も含めてユニークにしていますが、実際は`thread_ts`のみで良いはずです。

```python
def get_temp_dir(user_id: str, thread_ts: str) -> str:
    return f"/tmp/{user_id}/{thread_ts}"
```

### Open interpreterの呼び出し方を変える

Slack bot経由でOpen interpreterに同時に複数のリクエストを送信すると、メッセージが混ざってしまうという現象が発生しました。

```text
ま1ず.、デ マーータクをダ読ウみン形込式みの、そのファ概イ要ルをを作確成します認。
する2こ.とから フ始めまァイしルにテょキうスト。をそのた書めきに込はみ以下ます。
のまスずテ、ッマプークをダウン実形行式しますの。
ファ1イ.ル pandasをラ作イ成しブラまリをしインストょールう。します（ファイ既ルに名インはスト何にしますか？ールまた、されファイてルいにる書場合きは込スキむッテプキでストきはます）。
2何.ですか？ CSVファイルを読み込みます。
```

詳細な原因や仕組みはわかっていないのですが、呼び出し方の変更によってとりあえず治ったので、そのままにしています。

pythonコード内でOpen interpreterを使う時、通常はこのようにして呼び出します。

```python
import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices")  # Executes a single command
interpreter.chat()  # Starts an interactive chat
```

この時`interpreter/__init__.py`が読み込まれるのですが、その中身はこうなっています。

```python
from .interpreter import Interpreter
import sys

# This is done so when users `import interpreter`,
# they get an instance of interpreter:

sys.modules["interpreter"] = Interpreter()

# **This is a controversial thing to do,**
# because perhaps modules ought to behave like modules.

# But I think it saves a step, removes friction, and looks good.

#     ____                      ____      __                            __
#    / __ \____  ___  ____     /  _/___  / /____  _________  ________  / /____  _____
#   / / / / __ \/ _ \/ __ \    / // __ \/ __/ _ \/ ___/ __ \/ ___/ _ \/ __/ _ \/ ___/
#  / /_/ / /_/ /  __/ / / /  _/ // / / / /_/  __/ /  / /_/ / /  /  __/ /_/  __/ /
#  \____/ .___/\___/_/ /_/  /___/_/ /_/\__/\___/_/  / .___/_/   \___/\__/\___/_/
#      /_/                                         /_/
```

`sys.modules["interpreter"] = Interpreter()`のせいで同時に生成されたmessageが混ざったのだと思われます。

そこで`Interpreter`クラスをこのように呼び出して使うことで対応します。

```python
from interpreter.interpreter import Interpreter

interpreter = Interpreter()
interpreter.chat("His name is Killian.")
```

## 使いそうなライブラリを事前にインストールしたい

コンテナ内に事前インストールし、インストール済みであることをこのようなシステムメッセージに追記します。
これによりコンテナのデプロイ時間がものすごく長くなりますが、しゃーなしとします。

```
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
```

## Slack との繋ぎこみ

FlaskとSlack Boltを使って接続します。

Slack Botは3秒以内にリクエストを返さないとリクエストのリトライが行わレてしまいます。
そこで、これを無理やり対処するためにmiddlewareを設定しています。

```python
from flask import Flask, request
from slack_bolt import App, BoltResponse, Say
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient

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
    ...

```

これに加え、コンテナのCPU常時起動設定も行う必要があります。設定方法はデプロイと合わせて説明します。

詳細はこちらの記事をご覧ください。
https://zenn.dev/bisque/articles/slack-bolt-on-google-cloud

# デプロイする

Slack Botの設定とCloud Runの設定を行き来する必要がありますが、そんなに難しくは無いです。

## Slack Botを作成する。

[こちらのページ](https://api.slack.com/apps)からアプリを作成します。

### OAuthの設定, Tokenの取得

OAuth & PermissionsページのScopesからBotに以下の権限を与えます。

- app_mentions:read
- channels:history
- chat:write
- files:read
- files:write
- groups:history
- im:history
- mpim:history

設定したら、Botをワークスペースにインストールします。
`Install to Workspace`という緑のボタンをクリックします。

その後`xoxb-`から始まる`Bot User OAuth Token`が作成されるので、これをどこかにメモしておきます。

### Secretの取得

`Basic Information`ページから`Signing Secret`を取得し、これもどこかにメモしておきます。

## コンテナをCloud Runにデプロイする

`Bot User OAuth Token`と`Signing Secret`が取得できたところで、Cloud Runのビルド、設定を行います。
環境変数はGCPのコンソールで設定するため`.env`ファイル等はありません。
`$PROJECT` `$REGION`などは適宜書き換えてください。

ライブラリをインストールしまくっているため、かなり時間がかかります。

```sh
gcloud run deploy open-interpreter-slack-bot \
  --source . \
  --region $REGION \
  --memory 2048Mi \
  --project $PROJECT \
  --allow-unauthenticated
```

デプロイが完了するとこのようにCloud Runのエンドポイントが表示されますので、コピーしておきます。

`https://open-interpreter-slack-bot-XXXXXXXXXXX.a.run.app`

### コンソール上での設定

続いてGCPコンソールでCloud Runを開き、先ほどデプロイしたサービスを開きます。
上記デプロイコマンドをそのまま使った場合`open-interpreter-slack-bot`という名前をになっているはずです。

`新しいリビジョン編集とデプロイ`を選択し、以下の環境変数を設定します。

- OPENAI_API_KEY
- SLACK_BOT_TOKEN (先ほど取得したもの)
- SLACK_SIGNING_SECRET (先ほど取得したもの)

さらに、`CPU の割り当てと料金`から`CPU を常に割り当てる`選択します。

### Event Subscriptionの設定

最後に、再びSlackの設定に戻り、SlackのEventをSubscribeします。

`Event Subscriptions`ページでEnable Eventsから先ほどCloud Runのデプロイ後に取得したURLをペーストします。
この時、URLの末尾に`/slack/events`を追加します。

するとSlackからこのエンドポイントにヘルスチェックが行われます。
これが通らない場合Cloud Runで何らかのエラーが起きています。

Subscribeするイベントには`app_mention`を選択すればOKです。

これにて作成完了です。
どこかのチャンネルにBotを招待し、メンションしてみましょう。



