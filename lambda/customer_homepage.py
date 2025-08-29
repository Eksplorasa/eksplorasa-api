import os
import json
import logging
import pg8000

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler that reads from the restaurants table in the eksplorsadatabase
    and logs the records it reads.
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
        
        
        # Query the restaurants table
        logger.info("Querying restaurants table...")
        cursor.execute("SELECT * FROM restaurants ORDER BY restaurant_id DESC")
        
        # Fetch all records
        records = cursor.fetchall()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        logger.info(f"Found {len(records)} records in restaurants table")
        
        # Convert records to list of dictionaries
        restaurants = [dict(zip(column_names, record)) for record in records]
        
        # Close database connection
        cursor.close()
        connection.close()
        
        logger.info("Database connection closed successfully")
        
        # Prepare the response body
        response_body = {
            "Penawaran Terkini untuk Anda": restaurants[0:5],
            "Amankan Sebelum Terlambat": restaurants[5:10],
            "Kesukaan Anda": restaurants[10:15]
        }
        
        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps(response_body, default=str)
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
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
