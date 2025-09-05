import os
import json
import logging
import pg8000

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler that updates an existing customer's profile.
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
        
        # Check if at least one field is provided for update (removed customer_email since it doesn't exist)
        updateable_fields = ['customer_name', 'customer_phone_number', 'customer_address']
        provided_fields = [field for field in updateable_fields if field in request_body]
        
        if not provided_fields:
            logger.error("At least one field must be provided for update")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "error": "Bad Request",
                    "message": "At least one field must be provided for update"
                })
            }
        
        # First check if customer exists
        logger.info(f"Checking if customer with ID {customer_id} exists")
        cursor.execute('SELECT customer_id FROM "Customer" WHERE customer_id = %s', [customer_id])
        
        if not cursor.fetchone():
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
        
        # Build dynamic update query
        update_fields = []
        update_values = []
        
        for field in provided_fields:
            update_fields.append(f"{field} = %s")
            update_values.append(request_body[field])
        
        # Add customer_id as the last parameter
        update_values.append(customer_id)
        
        update_query = f"""
            UPDATE "Customer" 
            SET {', '.join(update_fields)} 
            WHERE customer_id = %s
            RETURNING customer_id, customer_name, customer_phone_number, customer_address
        """
        
        logger.info(f"Updating customer {customer_id} with fields: {provided_fields}")
        cursor.execute(update_query, update_values)
        
        # Fetch the updated record
        record = cursor.fetchone()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        # Convert record to dictionary
        updated_customer = dict(zip(column_names, record))
        
        # Commit the transaction
        connection.commit()
        
        logger.info(f"Successfully updated customer with ID: {updated_customer['customer_id']}")
        
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
                "customer_id": updated_customer['customer_id'],
                "customer_name": updated_customer['customer_name'],
                "customer_phone_number": updated_customer['customer_phone_number'],
                "customer_address": updated_customer['customer_address']
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
