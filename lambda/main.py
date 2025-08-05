import os
import json
import boto3

def handler(event, context):
    path = event["rawPath"]
    if path != "/":
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "Not Found"})
        }

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ.get('TABLE_NAME'))

    response = table.get_item(Key={'id': 'visit_count'})
    
    if 'Item' in response:
        visit_count = int(response['Item']['count'])
    else:
        visit_count = 0

    new_visit_count = visit_count + 1
    table.put_item(Item={'id': 'visit_count', 'count': new_visit_count})

    response_body = {
        "message": "Hello from Lambda!",
        "visit_count": new_visit_count
    }

    return {"statusCode": 200, "body": json.dumps(response_body)}