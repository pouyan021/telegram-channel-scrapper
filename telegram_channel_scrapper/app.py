import logging
import os
import re
import sys
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
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

translate = boto3.client('translate')
sns = boto3.client('sns')
table_name = 'message_ids'
dynamo_db = boto3.client('dynamodb')

existing_tables = dynamo_db.list_tables()['TableNames']
if table_name in existing_tables:
    logger.info('Table has already been created')
else:
    try:
        dynamo_db.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'message_id', 'KeyType': 'HASH'},
                {'AttributeName': 'id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'message_id', 'AttributeType': 'S'},
                {'AttributeName': 'id', 'AttributeType': 'N'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
        )
        dynamo_db.wait_until_exists()
    except ClientError as err:
        logger.error(
            "Couldn't create table %s. Here's why: %s: %s", table_name,
            err.response['Error']['Code'], err.response['Error']['Message'])
        raise
    logger.info("Table message_ids has been successfully created for the first time")

subscriptions = sns.list_subscriptions_by_topic(TopicArn=topic_arn)['Subscriptions']
for subscription in subscriptions:
    if subscription['Endpoint'] == email:
        logger.info('Subscription already confirmed')
        break
    else:
        sns.subscribe(
            Protocol='email',
            TopicArn=topic_arn,
            Endpoint=email,
        )

session = os.environ.get('SESSION')
client = TelegramClient(StringSession(session), api_id, api_hash)
client.start()

posting_date = datetime.today() - timedelta(days=1)


def lambda_handler(event, context):
    global translated_message
    max_id = find_max_id()

    handle_messages(max_id)
    return {
        'statusCode': 200,
        'result': 'Success'
    }


def handle_messages(max_id):
    global translated_message
    for update in client.iter_messages(channel_id, reverse=True, offset_date=posting_date, min_id=max_id):
        # Translate the message to your desired language
        message_id, response = check_db(update)

        if response['Items']:
            logger.info("The item %d has been already translated", message_id)
        else:
            try:
                dynamo_db.put_item(
                    TableName=table_name,
                    Item={
                        'message_id': {
                            "S": str(message_id)
                        },
                        'id': {
                            "N": str(message_id)
                        }
                    }
                )
                logger.info("The item %d put into db", message_id)
            except ClientError as error:
                logger.error("couldn't get the query. Here's why: %s: %s",
                             error.response['Error']['Code'],
                             error.response['Error']['Message'])
                raise
            translated_message = translate_text(text=update.text)
            logger.info("the message is %s", translated_message)

            if re.search(pattern, translated_message, flags=re.IGNORECASE):
                if re.findall(sub_pattern, translated_message, flags=re.IGNORECASE):
                    # Send a push notification to yourself
                    send_notification(notification_subject, translated_message)


def check_db(update):
    message_id = update.id
    try:
        response = dynamo_db.query(
            TableName=table_name,
            KeyConditionExpression='message_id = :message_id',
            ExpressionAttributeValues={':message_id': {
                "S": str(message_id)
            }
            }
        )
    except ClientError as error:
        logger.error("couldn't get the query. Here's why: %s: %s",
                     error.response['Error']['Code'],
                     error.response['Error']['Message'])
        raise
    return message_id, response


def find_max_id():
    records = dynamo_db.scan(
        TableName=table_name
    )
    if records is not None:
        max_id_dict = max(records["Items"], key=lambda x: int(x['id']['N']))
        max_id = int(max_id_dict['id']['N'])
        logger.info("The last id processed is: %s", max_id)
    else:
        max_id = 0
    return max_id


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
