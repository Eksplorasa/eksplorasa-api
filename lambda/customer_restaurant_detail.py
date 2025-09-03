import os
import json
import logging
import pg8000

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda handler that reads a specific restaurant from the restaurants table
    using restaurant_id and branch_id parameters.
    """
    try:
        # Extract path parameters from the event
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}

        # Get restaurant_id and branch_id from path or query parameters
        restaurant_id = path_parameters.get(
            'restaurant_id') or query_parameters.get('restaurant_id')
        branch_id = path_parameters.get(
            'branch_id') or query_parameters.get('branch_id')

        logger.info(
            f"Received request for restaurant_id: {restaurant_id}, branch_id: {branch_id}")

        # Validate required parameters
        if not restaurant_id:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Bad Request",
                    "message": "restaurant_id is required"
                })
            }

        if not branch_id:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Bad Request",
                    "message": "branch_id is required"
                })
            }

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

        # Query the restaurants table for specific restaurant and branch
        logger.info(
            f"Querying restaurants table for restaurant_id: {restaurant_id}, branch_id: {branch_id}")
        cursor.execute(
            "SELECT * FROM restaurants WHERE restaurant_id = %s AND branch_id = %s",
            (restaurant_id, branch_id)
        )

        # Fetch the record
        record = cursor.fetchone()

        # Get column names
        column_names = [desc[0] for desc in cursor.description]

        # Close database connection
        cursor.close()
        connection.close()

        logger.info("Database connection closed successfully")

        # Check if restaurant was not found
        if not record:
            logger.info(
                f"Restaurant not found for restaurant_id: {restaurant_id}, branch_id: {branch_id}")
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Not Found",
                    "message": f"Restaurant with restaurant_id {restaurant_id} and branch_id {branch_id} not found"
                })
            }

        # Convert record to dictionary
        restaurant = dict(zip(column_names, record))

        logger.info(
            f"Found restaurant: {restaurant.get('restaurant_name', 'Unknown')}")

        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps(restaurant, default=str)
        }

    except pg8000.Error as db_error:
        logger.error(f"Database error: {str(db_error)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Database error occurred",
                "message": str(db_error)
            })
        }

    except ValueError as ve:
        logger.error(f"Invalid parameter value: {str(ve)}")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Bad Request",
                "message": f"Invalid parameter value: {str(ve)}"
            })
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
