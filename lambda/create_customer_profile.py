import os
import json
import logging
import pg8000

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler that creates a new customer profile.
    """
    try:
        # Get database connection parameters from environment variables
        db_endpoint = os.environ.get('DB_ENDPOINT')
        db_port = int(os.environ.get('DB_PORT', '5432'))
        db_name = os.environ.get('DB_NAME')
        db_username = os.environ.get('DB_USERNAME')
        db_password = os.environ.get('DB_PASSWORD')
        
        logger.info("Connecting to database...")
        
        # Connect to PostgreSQL database using pg8000
        connection = pg8000.connect(
            host=db_endpoint,
            port=db_port,
            database=db_name,
            user=db_username,
            password=db_password,
            ssl_context=True
        )
        
        cursor = connection.cursor()
        
        # Parse request body
        if not event.get('body'):
            logger.error("Request body is required")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "Bad Request",
                    "message": "Request body is required"
                })
            }
        
        request_body = json.loads(event['body'])
        
        # Validate required fields
        required_fields = ['customer_name', 'customer_phone_number', 'customer_address']
        missing_fields = [field for field in required_fields if not request_body.get(field)]
        
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "Bad Request",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                })
            }
        
        # Insert new customer (without customer_email since it doesn't exist in the table)
        logger.info(f"Creating customer: {request_body['customer_name']}")
        cursor.execute(
            'INSERT INTO "Customer" (customer_name, customer_phone_number, customer_address) VALUES (%s, %s, %s) RETURNING customer_id, customer_name, customer_phone_number, customer_address',
            [
                request_body['customer_name'],
                request_body['customer_phone_number'],
                request_body['customer_address']
            ]
        )
        
        # Fetch the created record
        record = cursor.fetchone()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        # Convert record to dictionary
        new_customer = dict(zip(column_names, record))
        
        # Commit the transaction
        connection.commit()
        
        logger.info(f"Successfully created customer with ID: {new_customer['customer_id']}")
        
        # Close database connection
        cursor.close()
        connection.close()
        
        logger.info("Database connection closed successfully")
        
        # Return success response
        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "customer_id": new_customer['customer_id'],
                "customer_name": new_customer['customer_name'],
                "customer_phone_number": new_customer['customer_phone_number'],
                "customer_address": new_customer['customer_address']
            })
        }
        
    except pg8000.Error as db_error:
        logger.error(f"Database error: {str(db_error)}")
        
        # Check if it's a unique constraint violation
        if "duplicate key" in str(db_error).lower():
            return {
                "statusCode": 409,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "Conflict",
                    "message": "Customer with this information already exists"
                })
            }
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "error": "Database error occurred",
                "message": str(db_error)
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
