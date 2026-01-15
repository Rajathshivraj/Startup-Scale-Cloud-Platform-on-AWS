"""
============================================================================
AWS Lambda Function - Event-Driven Processing
============================================================================
Serverless function for processing DynamoDB Streams, scheduled tasks,
or API Gateway events.

USE CASES:
- DynamoDB Stream processing (real-time data transformation)
- Scheduled tasks (cleanup, aggregation, notifications)
- Async processing (email sending, image processing)
- Event-driven workflows (triggered by S3, SNS, SQS)

LAMBDA CHARACTERISTICS:
- Automatic scaling (0 to 10,000+ concurrent executions)
- Pay per invocation + execution time
- No server management
- 15-minute maximum execution time
============================================================================
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError

# ============================================================================
# Configuration from Environment Variables
# ============================================================================
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'startup-data')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# ============================================================================
# Logging Configuration
# ============================================================================
# Lambda automatically sends logs to CloudWatch Logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ============================================================================
# AWS Service Clients
# ============================================================================
# INITIALIZATION: Defined outside handler for connection reuse across invocations
# Lambda reuses execution environments (container warm-up optimization)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)
sns = boto3.client('sns', region_name=AWS_REGION)


# ============================================================================
# Lambda Handler Function (Entry Point)
# ============================================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda function handler.
    
    PARAMETERS:
        event (dict): Event data passed by trigger (format varies by source)
        context (LambdaContext): Runtime information (request ID, memory, timeout)
    
    RETURN:
        dict: Response object (format depends on trigger type)
    
    EVENT SOURCES:
        - DynamoDB Streams: Records of table changes
        - API Gateway: HTTP request data
        - S3: Object creation/deletion events
        - CloudWatch Events: Scheduled tasks (cron)
        - SNS/SQS: Message queue events
    """
    
    logger.info(f"Lambda invoked. Request ID: {context.request_id}")
    logger.info(f"Event source: {determine_event_source(event)}")
    
    try:
        # Route to appropriate handler based on event source
        event_source = determine_event_source(event)
        
        if event_source == 'dynamodb':
            return process_dynamodb_stream(event, context)
        elif event_source == 'api_gateway':
            return process_api_gateway_request(event, context)
        elif event_source == 'cloudwatch_events':
            return process_scheduled_task(event, context)
        elif event_source == 's3':
            return process_s3_event(event, context)
        else:
            logger.warning(f"Unknown event source: {event_source}")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Unknown event source'})}
    
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        # Return error response (don't raise exception to prevent Lambda retry)
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}


# ============================================================================
# Handler: DynamoDB Streams Processing
# ============================================================================
def process_dynamodb_stream(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process DynamoDB Stream records (real-time table change capture).
    
    STREAM RECORD FORMAT:
    {
        "Records": [
            {
                "eventID": "...",
                "eventName": "INSERT|MODIFY|REMOVE",
                "dynamodb": {
                    "Keys": {"id": {"S": "item123"}},
                    "NewImage": {...},
                    "OldImage": {...}
                }
            }
        ]
    }
    
    USE CASES:
        - Data replication (sync to Elasticsearch for search)
        - Audit logging (track all changes)
        - Aggregations (update counters, materialized views)
        - Notifications (send email when item created)
    """
    
    processed_count = 0
    failed_count = 0
    
    for record in event.get('Records', []):
        try:
            event_name = record['eventName']  # INSERT, MODIFY, REMOVE
            
            logger.info(f"Processing DynamoDB {event_name} event")
            
            # Extract item data
            keys = record['dynamodb'].get('Keys', {})
            new_image = record['dynamodb'].get('NewImage', {})
            old_image = record['dynamodb'].get('OldImage', {})
            
            # Example: Log all changes (audit trail)
            if event_name == 'INSERT':
                logger.info(f"New item created: {deserialize_dynamodb_item(keys)}")
            elif event_name == 'MODIFY':
                logger.info(f"Item modified: {deserialize_dynamodb_item(keys)}")
            elif event_name == 'REMOVE':
                logger.info(f"Item deleted: {deserialize_dynamodb_item(keys)}")
            
            # Example: Send notification for specific events
            if event_name == 'INSERT' and 'user_id' in new_image:
                send_notification(f"New user registered: {new_image['user_id']['S']}")
            
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Failed to process record: {str(e)}")
            failed_count += 1
            # Continue processing other records (partial failure handling)
    
    # Publish metrics to CloudWatch
    publish_metric('StreamRecordsProcessed', processed_count)
    if failed_count > 0:
        publish_metric('StreamRecordsFailed', failed_count)
    
    logger.info(f"Processed {processed_count} records, {failed_count} failures")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed_count,
            'failed': failed_count
        })
    }


# ============================================================================
# Handler: API Gateway Request
# ============================================================================
def process_api_gateway_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process HTTP request from API Gateway.
    
    REQUEST EVENT FORMAT:
    {
        "httpMethod": "GET|POST|PUT|DELETE",
        "path": "/api/items",
        "queryStringParameters": {"id": "123"},
        "body": "{...}"
    }
    
    RESPONSE FORMAT (for proxy integration):
    {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "{...}"
    }
    """
    
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    logger.info(f"API Gateway request: {method} {path}")
    
    # Example: GET /items - List items from DynamoDB
    if method == 'GET' and path == '/items':
        try:
            response = table.scan(Limit=10)
            items = response.get('Items', [])
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'items': items})
            }
        except ClientError as e:
            logger.error(f"DynamoDB error: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Database error'})
            }
    
    # Default response for unknown routes
    return {
        'statusCode': 404,
        'body': json.dumps({'error': 'Not found'})
    }


# ============================================================================
# Handler: Scheduled Task (CloudWatch Events)
# ============================================================================
def process_scheduled_task(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process scheduled task triggered by CloudWatch Events (EventBridge).
    
    SCHEDULE FORMATS:
        - rate(5 minutes) - Run every 5 minutes
        - cron(0 12 * * ? *) - Run daily at 12:00 UTC
    
    USE CASES:
        - Data cleanup (delete expired items)
        - Report generation (daily summaries)
        - Health checks (verify external APIs)
        - Cost optimization (stop dev resources after hours)
    """
    
    logger.info("Executing scheduled task")
    
    # Example: Delete expired items from DynamoDB (TTL alternative)
    try:
        current_timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        # Scan for expired items (in production, use Query with GSI on expiration_time)
        response = table.scan(
            FilterExpression='expiration_time < :now',
            ExpressionAttributeValues={':now': current_timestamp}
        )
        
        deleted_count = 0
        for item in response.get('Items', []):
            table.delete_item(Key={'id': item['id'], 'timestamp': item['timestamp']})
            deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} expired items")
        publish_metric('ExpiredItemsDeleted', deleted_count)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'deleted': deleted_count})
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


# ============================================================================
# Handler: S3 Event Processing
# ============================================================================
def process_s3_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process S3 object creation/deletion events.
    
    S3 EVENT FORMAT:
    {
        "Records": [
            {
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "my-bucket"},
                    "object": {"key": "path/to/file.jpg"}
                }
            }
        ]
    }
    
    USE CASES:
        - Image processing (resize, thumbnail generation)
        - File validation (virus scanning)
        - Data ingestion (process CSV uploads)
        - Backup automation (copy to Glacier)
    """
    
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        logger.info(f"Processing S3 object: s3://{bucket}/{key}")
        
        # Example: Store S3 file metadata in DynamoDB
        try:
            table.put_item(Item={
                'id': f"s3-{key.replace('/', '-')}",
                'timestamp': int(datetime.utcnow().timestamp() * 1000),
                'type': 'file_upload',
                'bucket': bucket,
                'key': key,
                'uploaded_at': datetime.utcnow().isoformat()
            })
        except ClientError as e:
            logger.error(f"Failed to store metadata: {str(e)}")
    
    return {'statusCode': 200, 'body': json.dumps({'processed': len(event.get('Records', []))})}


# ============================================================================
# Helper: Determine Event Source
# ============================================================================
def determine_event_source(event: Dict[str, Any]) -> str:
    """
    Identify event source from event structure.
    
    IDENTIFICATION LOGIC:
        - DynamoDB: 'Records' with 'dynamodb' key
        - API Gateway: 'httpMethod' and 'path'
        - CloudWatch Events: 'source' == 'aws.events'
        - S3: 'Records' with 's3' key
    """
    if 'Records' in event:
        if event['Records'] and 'dynamodb' in event['Records'][0]:
            return 'dynamodb'
        elif event['Records'] and 's3' in event['Records'][0]:
            return 's3'
    elif 'httpMethod' in event and 'path' in event:
        return 'api_gateway'
    elif 'source' in event and event['source'] == 'aws.events':
        return 'cloudwatch_events'
    return 'unknown'


# ============================================================================
# Helper: Deserialize DynamoDB Item
# ============================================================================
def deserialize_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DynamoDB JSON format to standard Python dict.
    
    DynamoDB FORMAT: {"id": {"S": "value"}, "count": {"N": "123"}}
    PYTHON FORMAT: {"id": "value", "count": 123}
    """
    from boto3.dynamodb.types import TypeDeserializer
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in item.items()}


# ============================================================================
# Helper: Publish CloudWatch Metric
# ============================================================================
def publish_metric(metric_name: str, value: float) -> None:
    """
    Publish custom CloudWatch metric.
    
    COST: ~$0.01 per 1000 metrics
    """
    try:
        cloudwatch.put_metric_data(
            Namespace='Lambda/Processing',
            MetricData=[{
                'MetricName': metric_name,
                'Value': value,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }]
        )
    except Exception as e:
        logger.warning(f"Failed to publish metric: {str(e)}")


# ============================================================================
# Helper: Send Notification
# ============================================================================
def send_notification(message: str) -> None:
    """
    Send notification via SNS.
    
    REQUIRES: SNS_TOPIC_ARN environment variable
    """
    topic_arn = os.getenv('SNS_TOPIC_ARN')
    if not topic_arn:
        logger.warning("SNS_TOPIC_ARN not configured, skipping notification")
        return
    
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject='Lambda Notification',
            Message=message
        )
        logger.info(f"Notification sent: {message}")
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")


# ============================================================================
# LAMBDA BEST PRACTICES (Interview Points):
# ============================================================================
# 1. COLD START OPTIMIZATION:
#    - Initialize SDK clients outside handler (reuse across invocations)
#    - Use Lambda SnapStart for Java (instant startup)
#    - Consider Provisioned Concurrency for latency-sensitive apps
#
# 2. ERROR HANDLING:
#    - Lambda retries failed executions (2 times for async, varies for sync)
#    - Use Dead Letter Queue (DLQ) to capture failed events
#    - Implement idempotency to handle duplicate invocations
#
# 3. MEMORY & TIMEOUT:
#    - Memory range: 128 MB - 10 GB (affects CPU allocation)
#    - Timeout: 1 second - 15 minutes
#    - Higher memory = faster execution but higher cost
#
# 4. COST OPTIMIZATION:
#    - Right-size memory (use Lambda Power Tuning tool)
#    - Use Lambda@Edge for edge computing
#    - Consider Step Functions for long-running workflows
#
# 5. MONITORING:
#    - CloudWatch Logs: Automatic log capture
#    - X-Ray: Distributed tracing
#    - CloudWatch Metrics: Duration, Invocations, Errors, Throttles
# ============================================================================

# ============================================================================
# PRODUCTION DEPLOYMENT (Terraform):
# ============================================================================
# resource "aws_lambda_function" "processor" {
#   filename      = "lambda.zip"
#   function_name = "${var.environment}-event-processor"
#   role          = aws_iam_role.lambda_execution_role.arn
#   handler       = "handler.lambda_handler"
#   runtime       = "python3.11"
#   timeout       = 60
#   memory_size   = 512
#
#   environment {
#     variables = {
#       DYNAMODB_TABLE = aws_dynamodb_table.main.name
#       SNS_TOPIC_ARN  = aws_sns_topic.alarms.arn
#     }
#   }
#
#   # DLQ for failed invocations
#   dead_letter_config {
#     target_arn = aws_sqs_queue.lambda_dlq.arn
#   }
# }
#
# # Trigger from DynamoDB Stream
# resource "aws_lambda_event_source_mapping" "dynamodb" {
#   event_source_arn  = aws_dynamodb_table.main.stream_arn
#   function_name     = aws_lambda_function.processor.arn
#   starting_position = "LATEST"
#   batch_size        = 100
# }
# ============================================================================