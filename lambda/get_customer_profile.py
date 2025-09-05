import os
import json
import logging
import pg8000

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler that retrieves a single customer's profile by customer_id.
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
        
        # Get customer_id from path parameters
        customer_id = event.get('pathParameters', {}).get('customer_id')
        
        if not customer_id:
            logger.error("Customer ID is required")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "Bad Request",
                    "message": "Customer ID is required"
                })
            }
        
        # Query the customer by ID
        logger.info(f"Querying customer with ID: {customer_id}")
        cursor.execute(
            'SELECT customer_id, customer_name, customer_phone_number, customer_address FROM "Customer" WHERE customer_id = %s',
            [customer_id]
        )
        
        # Fetch the record
        record = cursor.fetchone()
        
        if not record:
            logger.info(f"Customer with ID {customer_id} not found")
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "Not Found",
                    "message": "Customer not found"
                })
            }
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        # Convert record to dictionary
        customer = dict(zip(column_names, record))
        
        logger.info(f"Found customer: {customer['customer_name']}")
        
        # Close database connection
        cursor.close()
        connection.close()
        
        logger.info("Database connection closed successfully")
        
        # Return success response
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "customer_id": customer['customer_id'],
                "customer_name": customer['customer_name'],
                "customer_phone_number": customer['customer_phone_number'],
                "customer_address": customer['customer_address']
            })
        }
        
    except pg8000.Error as db_error:
        logger.error(f"Database error: {str(db_error)}")
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
