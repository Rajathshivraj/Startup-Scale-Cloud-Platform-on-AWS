#!/usr/bin/env python3
"""
============================================================================
Startup Platform Flask API - Microservice Application
============================================================================
Lightweight Flask API demonstrating AWS integration patterns:
- DynamoDB for NoSQL data storage
- RDS PostgreSQL for relational data
- CloudWatch Logs for observability
- IAM roles for secure AWS service access

ARCHITECTURE PATTERNS:
- RESTful API design
- Health check endpoint for load balancer
- Environment-based configuration
- Graceful shutdown handling
============================================================================
"""

import os
import sys
import signal
import logging
from datetime import datetime
from typing import Dict, Any

from flask import Flask, jsonify, request
import boto3
from botocore.exceptions import ClientError

# ============================================================================
# Configuration from Environment Variables
# ============================================================================
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'startup-data')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'startupdb')
DB_USER = os.getenv('DB_USERNAME', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'changeme')  # Use Secrets Manager in production

# ============================================================================
# Logging Configuration
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    stream=sys.stdout  # CloudWatch captures stdout/stderr
)
logger = logging.getLogger(__name__)

# ============================================================================
# Flask Application Factory
# ============================================================================
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False  # Preserve JSON key order

# ============================================================================
# AWS Service Clients (Using IAM Role Credentials)
# ============================================================================
# NO ACCESS KEYS NEEDED: ECS task role provides temporary credentials via STS
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
dynamodb_table = dynamodb.Table(DYNAMODB_TABLE)

cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)

logger.info(f"Application starting in {ENVIRONMENT} environment")
logger.info(f"DynamoDB table: {DYNAMODB_TABLE}")
logger.info(f"AWS Region: {AWS_REGION}")

# ============================================================================
# Route: Health Check (Required for ALB Target Health)
# ============================================================================
@app.route('/health', methods=['GET'])
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for AWS Application Load Balancer.
    
    ALB expects HTTP 200 response to consider target healthy.
    Returns application status and dependency health.
    
    BEST PRACTICE: Include dependency checks (database, external APIs)
    to ensure application is truly ready to serve traffic.
    """
    health_status = {
        'status': 'healthy',
        'environment': ENVIRONMENT,
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'dependencies': {
            'dynamodb': 'unknown',
            'rds': 'unknown'
        }
    }
    
    # Check DynamoDB connectivity
    try:
        dynamodb_table.table_status  # Simple check to verify table exists
        health_status['dependencies']['dynamodb'] = 'connected'
    except Exception as e:
        logger.warning(f"DynamoDB health check failed: {str(e)}")
        health_status['dependencies']['dynamodb'] = 'disconnected'
        health_status['status'] = 'degraded'  # Partial outage
    
    # PRODUCTION: Add RDS connectivity check with psycopg2
    # try:
    #     import psycopg2
    #     conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    #     conn.close()
    #     health_status['dependencies']['rds'] = 'connected'
    # except Exception as e:
    #     logger.error(f"RDS health check failed: {str(e)}")
    #     health_status['dependencies']['rds'] = 'disconnected'
    #     health_status['status'] = 'unhealthy'
    #     return jsonify(health_status), 503  # Service Unavailable
    
    return jsonify(health_status), 200


# ============================================================================
# Route: Root Endpoint (API Information)
# ============================================================================
@app.route('/', methods=['GET'])
def root() -> Dict[str, Any]:
    """
    Root endpoint providing API documentation.
    """
    return jsonify({
        'service': 'Startup Platform API',
        'version': '1.0.0',
        'environment': ENVIRONMENT,
        'endpoints': {
            'health': '/health',
            'items': '/api/items',
            'item_by_id': '/api/items/<id>',
            'metrics': '/api/metrics'
        },
        'documentation': 'https://docs.startup.com/api'
    }), 200


# ============================================================================
# Route: Create Item in DynamoDB
# ============================================================================
@app.route('/api/items', methods=['POST'])
def create_item() -> Dict[str, Any]:
    """
    Create a new item in DynamoDB table.
    
    REQUEST BODY (JSON):
    {
        "name": "Sample Item",
        "description": "Item description"
    }
    
    RESPONSE: 201 Created with item data
    """
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({'error': 'Missing required field: name'}), 400
        
        # Generate unique ID and timestamp
        item_id = f"item-{datetime.utcnow().timestamp()}"
        timestamp = int(datetime.utcnow().timestamp() * 1000)  # Milliseconds
        
        item = {
            'id': item_id,
            'timestamp': timestamp,
            'name': data['name'],
            'description': data.get('description', ''),
            'created_at': datetime.utcnow().isoformat(),
            'environment': ENVIRONMENT
        }
        
        # Write to DynamoDB
        dynamodb_table.put_item(Item=item)
        
        logger.info(f"Created item: {item_id}")
        
        # Publish custom CloudWatch metric (business KPI)
        publish_metric('ItemsCreated', 1)
        
        return jsonify({
            'message': 'Item created successfully',
            'item': item
        }), 201
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Route: Get Item from DynamoDB
# ============================================================================
@app.route('/api/items/<item_id>', methods=['GET'])
def get_item(item_id: str) -> Dict[str, Any]:
    """
    Retrieve item by ID from DynamoDB.
    
    PARAMETERS:
        item_id (str): Unique item identifier
    
    RESPONSE: 200 OK with item data, or 404 Not Found
    """
    try:
        # Query DynamoDB by partition key
        # NOTE: This is simplified - production would query with both partition and sort key
        response = dynamodb_table.get_item(Key={'id': item_id})
        
        if 'Item' not in response:
            return jsonify({'error': 'Item not found'}), 404
        
        return jsonify({'item': response['Item']}), 200
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return jsonify({'error': 'Database error'}), 500


# ============================================================================
# Route: List Items from DynamoDB (Paginated)
# ============================================================================
@app.route('/api/items', methods=['GET'])
def list_items() -> Dict[str, Any]:
    """
    List items with pagination support.
    
    QUERY PARAMETERS:
        limit (int): Number of items to return (default: 10, max: 100)
        last_key (str): Last evaluated key for pagination
    
    RESPONSE: 200 OK with items array and pagination token
    """
    try:
        limit = min(int(request.args.get('limit', 10)), 100)  # Cap at 100
        
        # Scan DynamoDB (inefficient for large tables - use Query with GSI in production)
        response = dynamodb_table.scan(Limit=limit)
        
        items = response.get('Items', [])
        
        return jsonify({
            'items': items,
            'count': len(items),
            'last_evaluated_key': response.get('LastEvaluatedKey'),  # For pagination
            'message': 'Use last_evaluated_key parameter for next page'
        }), 200
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return jsonify({'error': 'Database error'}), 500


# ============================================================================
# Route: Custom Metrics Endpoint
# ============================================================================
@app.route('/api/metrics', methods=['GET'])
def get_metrics() -> Dict[str, Any]:
    """
    Return application metrics for monitoring dashboards.
    
    PRODUCTION: Integrate with Prometheus, Datadog, or CloudWatch Embedded Metrics
    """
    # Example metrics - in production, use actual application counters
    metrics = {
        'environment': ENVIRONMENT,
        'uptime_seconds': 3600,  # Placeholder - track actual uptime
        'requests_total': 1000,  # Placeholder - use request counter
        'requests_per_second': 5.2,
        'active_connections': 10,
        'error_rate': 0.02  # 2% error rate
    }
    
    return jsonify({'metrics': metrics}), 200


# ============================================================================
# Helper: Publish Custom CloudWatch Metric
# ============================================================================
def publish_metric(metric_name: str, value: float, unit: str = 'Count') -> None:
    """
    Publish custom metric to CloudWatch for business KPI tracking.
    
    ARGS:
        metric_name (str): Name of metric (e.g., 'OrdersPlaced')
        value (float): Metric value
        unit (str): CloudWatch unit (Count, Seconds, Percent, etc.)
    
    COST: ~$0.01 per 1000 metrics
    """
    try:
        cloudwatch.put_metric_data(
            Namespace='StartupPlatform',  # Custom namespace
            MetricData=[{
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {'Name': 'Environment', 'Value': ENVIRONMENT}
                ]
            }]
        )
    except Exception as e:
        logger.warning(f"Failed to publish metric {metric_name}: {str(e)}")
        # Don't fail request if metrics publishing fails


# ============================================================================
# Signal Handlers for Graceful Shutdown
# ============================================================================
def signal_handler(signum, frame):
    """
    Handle SIGTERM signal for graceful shutdown.
    
    FLOW:
    1. ECS sends SIGTERM to container
    2. Application stops accepting new requests
    3. Finish processing in-flight requests (up to deregistration_delay)
    4. Close database connections
    5. Exit cleanly
    
    ECS waits 'deregistration_delay' (30s) before force-killing (SIGKILL)
    """
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    # PRODUCTION: Close database connections, flush logs, clean up resources
    # db_connection_pool.close_all()
    
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C for local development


# ============================================================================
# Application Entry Point
# ============================================================================
if __name__ == '__main__':
    """
    Start Flask development server.
    
    PRODUCTION: Use gunicorn instead:
        gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 60 app:app
    """
    port = int(os.getenv('PORT', 5000))
    debug = ENVIRONMENT == 'dev'  # Only enable debug mode in development
    
    logger.info(f"Starting Flask application on port {port}")
    
    # host='0.0.0.0' makes server accessible outside container
    # use_reloader=False prevents duplicate processes in Docker
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)


# ============================================================================
# PRODUCTION ENHANCEMENTS:
# ============================================================================
# 1. Database Connection Pooling:
#    - Use psycopg2.pool for PostgreSQL
#    - Reuse connections instead of creating per-request
#
# 2. Request ID Tracing:
#    - Generate unique ID per request (X-Request-ID header)
#    - Include in all logs for distributed tracing
#
# 3. Rate Limiting:
#    - Use Flask-Limiter to prevent abuse
#    - Implement per-user or per-IP rate limits
#
# 4. API Versioning:
#    - Use /v1/items, /v2/items for backward compatibility
#    - Deprecate old versions with sunset dates
#
# 5. Authentication:
#    - Implement JWT tokens or AWS Cognito
#    - Validate tokens in middleware
#
# 6. Structured Logging:
#    - Use JSON format for logs (easier parsing in CloudWatch Insights)
#    - Include trace_id, user_id, endpoint in every log
#
# 7. Caching:
#    - Add ElastiCache Redis for frequently accessed data
#    - Cache DynamoDB query results with TTL
# ============================================================================

# ============================================================================
# INTERVIEW TALKING POINTS:
# ============================================================================
# Q: How does the application get AWS credentials?
# A: ECS task role provides temporary credentials via EC2 instance metadata
#    service (IMDS). Boto3 automatically uses these credentials - no keys needed.
#
# Q: Why use health checks?
# A: ALB health checks ensure traffic only goes to healthy tasks. If health
#    check fails, ALB stops routing traffic and ECS starts replacement task.
#
# Q: How do you handle database connection failures?
# A: Implement retry logic with exponential backoff, circuit breakers to
#    prevent cascading failures, and graceful degradation (return cached data).
#
# Q: How do you ensure zero-downtime deployments?
# A: ECS rolling update: start new tasks, wait for health checks to pass,
#    drain connections from old tasks (deregistration_delay), stop old tasks.
# ============================================================================