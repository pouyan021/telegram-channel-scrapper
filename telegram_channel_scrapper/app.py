import os
import re
import sys
import telebot
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

bot_token = os.getenv('TELEGRAM_TOKEN')
channel_id = os.getenv('CHANNEL_ID')
email = os.getenv('EMAIL')
pattern = os.getenv('PATTERN')
sub_pattern = os.getenv('SUB_PATTERN')
source_lang = os.getenv('SRC_LNG')
target_lang = os.getenv('TRG_LNG')
notification_subject = os.getenv('NOTIF_SUB')
topic_arn = os.getenv('TOPIC_ARN')

bot = telebot.TeleBot(bot_token)
translate = boto3.client(service_name='translate')
sns = boto3.client('sns')

sns.subscribe(
    Protocol='email',
    TopicArn=topic_arn,
    Endpoint=email,
)


def lambda_handler(event, context):
    updates = bot.get_updates()
    logger.debug("There are %d new messages", len(updates))
    for update in updates:
        message = update.channel_post.text
        logger.debug("the message is %s", message)
        logger.debug("received the event %s", event)
        # Translate the message to your desired language
        translated_message = translate_text(message)

        if re.search(pattern, translated_message, flags=re.IGNORECASE):
            if re.findall(sub_pattern, translated_message, flags=re.IGNORECASE):
                # Send a push notification to yourself
                send_notification(notification_subject, translated_message)


def translate_text(text):
    result = translate.translate_text(text,
                                      SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)
    return result['TranslatedText']


def send_notification(subject, message):
    sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject=subject
    )
