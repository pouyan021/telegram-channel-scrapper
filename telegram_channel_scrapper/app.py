import os
import re
import telebot
import boto3
import logging


logger = logging.getLogger()

bot_token = os.getenv('TELEGRAM_TOKEN')
channel_id = os.getenv('CHANNEL_ID')

bot = telebot.TeleBot(bot_token)
translate = boto3.client(service_name='translate')
sns = boto3.client('sns')


def lambda_handler(event, context):
    for update in bot.get_updates():
        message = update.channel_post.text
        logger.info("received the event %s", event)
        # Translate the message to your desired language
        translated_message = translate_text(message)

        pattern = os.getenv('NEIGHBOURHOOD')
        address = os.getenv('ADDRESS')
        if re.search(pattern, translated_message, flags=re.IGNORECASE):
            if re.findall(address, translated_message, flags=re.IGNORECASE):
                # Send a push notification to yourself
                send_notification('Water Interruption Alert', translated_message)


def translate_text(text):
    result = translate.translate_text(text,
                                      SourceLanguageCode="hy", TargetLanguageCode="en")
    return result['TranslatedText']


def send_notification(subject, message):
    sns.publish(
        TopicArn=os.getenv('TOPIC_ARN'),
        Message=message,
        Subject=subject
    )
