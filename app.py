import os
import sys
from argparse import ArgumentParser
from flask import (Flask, render_template, request, abort)
from linebot.v3 import (
    WebhookParser,
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage
)

from crawl import product_crawl
from reply import reply_message
from upload import upload_image
from image import analyze

# Cloudinary API
import cloudinary
import cloudinary.uploader
          
cloudinary.config( 
  cloud_name = os.getenv('CLOUDINARY_NAME'), 
  api_key = os.getenv('CLOUDINARY_API_KEY'), 
  api_secret = os.getenv('CLOUDINARY_API_SECRET') 
)

app = Flask(__name__)

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

parser = WebhookParser(channel_secret)
handler = WebhookHandler(channel_secret)

configuration = Configuration(
    access_token=channel_access_token
)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        result = analyze(url)
        serial_number = ""
        for line in result.read.blocks[0].lines:
            if len(line.text) == 10:
                if line.text[-6:].isnumeric():
                    serial_number = line.text[-6:]
                    print(serial_number)
        context = {
            'caption': result.caption,
            'read': result.read,
            'serial': serial_number,
            'url': url,
        }
        return render_template('index.html', context=context)
    else:
        return render_template('index.html')


@app.route("/find_product", methods=['POST'])
def find_product():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def message_text(event):
    message_input = event.message.text
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if message_input == "1":
            img_url = "https://i.imgur.com/HLw9BhO.jpg"
            reply = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                replyToken=event.reply_token,
                messages=[reply]))
        else:
            result = product_crawl(message_input)
            reply_message(result, event, line_bot_api)
                    
    return 'OK'

@handler.add(MessageEvent, message=ImageMessageContent)
def message_image(event):
    with ApiClient(configuration) as api_client:
        print("User sent a image!")
        line_bot_api = MessagingApi(api_client)
        messageId = event.message.id
        image_url = upload_image(channel_access_token, messageId)

        result = analyze(image_url)

        serial_number = ""
        for line in result.read.blocks[0].lines:
            if len(line.text) == 10:
                if line.text[-6:].isnumeric():
                    serial_number = line.text[-6:]
                    print("serial number : " + serial_number)

        crawlResult = product_crawl(serial_number)
        
        reply_message(crawlResult, event, line_bot_api)

    return "OK"

if __name__ == '__main__':
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, port=options.port)
