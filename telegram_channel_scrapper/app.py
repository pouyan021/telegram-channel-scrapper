from datetime import datetime, timedelta
import os
import re
import sys

import boto3
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession


logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
user_name = os.getenv('USER_NAME')
channel_id = os.getenv('CHANNEL_ID')
email = os.getenv('EMAIL')
pattern = os.getenv('PATTERN')
sub_pattern = os.getenv('SUB_PATTERN')
source_lang = os.getenv('SRC_LNG')
target_lang = os.getenv('TRG_LNG')
notification_subject = os.getenv('NOTIF_SUB')
topic_arn = os.getenv('TOPIC_ARN')

translate = boto3.client(service_name='translate')
sns = boto3.client('sns')

sns.subscribe(
    Protocol='email',
    TopicArn=topic_arn,
    Endpoint=email,
)

session = os.environ.get('SESSION')
client = TelegramClient(StringSession(session), api_id, api_hash)
client.start()


def lambda_handler(event, context):
    posting_date = datetime.today() - timedelta(days=1)
    for update in client.iter_messages(channel_id, reverse=True, offset_date=posting_date):
        # Translate the message to your desired language
        translated_message = translate_text(text=update.text)
        logger.info("the message is %s", translated_message)

        if re.search(pattern, translated_message, flags=re.IGNORECASE):
            if re.findall(sub_pattern, translated_message, flags=re.IGNORECASE):
                # Send a push notification to yourself
                send_notification(notification_subject, translated_message)


def translate_text(text):
    result = translate.translate_text(Text=text,
                                      SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)
    return result['TranslatedText']


def send_notification(subject, message):
    sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject=subject
    )
