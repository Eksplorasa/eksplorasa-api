import os
import json
import logging
import pg8000
import math
from typing import Dict, List, Any, Optional

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler for the Browse API that queries restaurants with filtering capabilities.
    Supports filtering by cuisine, price, bag type, time, distance, and sorting.
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
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        filters = parse_query_parameters(query_params)
        
        logger.info(f"Applied filters: {filters}")
        
        # Build and execute the main query
        query, params = build_restaurant_query(filters)
        logger.info(f"Executing query: {query}")
        logger.info(f"Query parameters: {params}")
        
        cursor.execute(query, params)
        records = cursor.fetchall()

        column_names = [desc[0] for desc in cursor.description]
        
        logger.info(f"Found {len(records)} restaurants from database")
        
        # Convert records to list of dictionaries
        restaurants = [dict(zip(column_names, record)) for record in records]
        
        # Apply distance filtering
        restaurants = apply_distance_filter(restaurants, filters)
        logger.info(f"{len(restaurants)} restaurants after distance filtering")
        
        # Transform the response to match the expected API format
        transformed_restaurants = []
        for restaurant in restaurants:
            transformed_restaurant = {
                "id": restaurant['restaurant_id'],
                "branchId": restaurant['branch_id'],
                "name": restaurant['name'],
                "cuisine": restaurant['cuisinetype'],
                "rating": float(restaurant['rating']) if restaurant['rating'] else 0.0,
                "mainImageUrl": restaurant['mainimageurl'],
                "logoUrl": restaurant['logourl'],
                "coordinates": {
                    "latitude": float(restaurant['latitude']) if restaurant['latitude'] else 0.0,
                    "longitude": float(restaurant['longitude']) if restaurant['longitude'] else 0.0
                },
                "description": restaurant['what_you_could_get'],
                "isLive": restaurant['liveflag'],
                "priceRange": {
                    "min": float(restaurant['min_price']) if restaurant['min_price'] else 0.0,
                    "max": float(restaurant['max_price']) if restaurant['max_price'] else 0.0
                },
                "availableBagTypes": restaurant['available_bag_types'] or []
            }
            transformed_restaurants.append(transformed_restaurant)
        
        # Close database connection
        cursor.close()
        connection.close()
        
        logger.info("Database connection closed successfully")
        
        # Prepare response
        response_body = {
            "restaurants": transformed_restaurants,
            "totalCount": len(transformed_restaurants),
            "appliedFilters": filters
        }
        
        # Return success response with CORS headers
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,OPTIONS"
            },
            "body": json.dumps(response_body, default=str)
        }
        
    except pg8000.Error as db_error:
        logger.error(f"Database error: {str(db_error)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
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
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }

def parse_query_parameters(query_params: Dict[str, str]) -> Dict[str, Any]:
    """Parse query parameters from the API Gateway event."""
    filters = {}
    
    if query_params.get('sort'):
        filters['sort'] = query_params['sort']
    
    if query_params.get('timeStart'):
        filters['timeStart'] = query_params['timeStart']
    
    if query_params.get('timeEnd'):
        filters['timeEnd'] = query_params['timeEnd']
    
    if query_params.get('minPrice'):
        try:
            filters['minPrice'] = float(query_params['minPrice'])
        except ValueError:
            pass
    
    if query_params.get('maxPrice'):
        try:
            filters['maxPrice'] = float(query_params['maxPrice'])
        except ValueError:
            pass
    
    # Validate price range - if min > max, swap them
    if filters.get('minPrice') is not None and filters.get('maxPrice') is not None:
        if filters['minPrice'] > filters['maxPrice']:
            logger.warning(f"minPrice ({filters['minPrice']}) > maxPrice ({filters['maxPrice']}), swapping values")
            filters['minPrice'], filters['maxPrice'] = filters['maxPrice'], filters['minPrice']
    
    # Handle cuisines - support both [item1,item2] and item1,item2 formats
    if query_params.get('cuisines'):
        cuisines_str = query_params['cuisines']
        # Remove brackets if present
        if cuisines_str.startswith('[') and cuisines_str.endswith(']'):
            cuisines_str = cuisines_str[1:-1]
        filters['cuisines'] = [c.strip() for c in cuisines_str.split(',')]
    
    # Handle bagTypes - support both [item1,item2] and item1,item2 formats
    if query_params.get('bagTypes'):
        bag_types_str = query_params['bagTypes']
        # Remove brackets if present
        if bag_types_str.startswith('[') and bag_types_str.endswith(']'):
            bag_types_str = bag_types_str[1:-1]
        filters['bagTypes'] = [b.strip() for b in bag_types_str.split(',')]
    
    if query_params.get('maxDistance'):
        try:
            filters['maxDistance'] = float(query_params['maxDistance'])
        except ValueError:
            pass
    
    if query_params.get('latitude'):
        try:
            filters['latitude'] = float(query_params['latitude'])
        except ValueError:
            pass
    
    if query_params.get('longitude'):
        try:
            filters['longitude'] = float(query_params['longitude'])
        except ValueError:
            pass
    
    return filters

def build_restaurant_query(filters: Dict[str, Any]) -> tuple[str, List[Any]]:
    """Build the main SQL query with filters and sorting."""
    conditions = ["r.liveflag = true"]  # Only show live restaurants by default
    params = []
    param_index = 1
    
    # Cuisine filtering
    if filters.get('cuisines'):
        placeholders = ', '.join([f'${i}' for i in range(param_index, param_index + len(filters['cuisines']))])
        conditions.append(f"r.cuisinetype IN ({placeholders})")
        params.extend(filters['cuisines'])
        param_index += len(filters['cuisines'])
    
    # Price filtering
    if filters.get('minPrice') is not None:
        conditions.append(f"i.sale_price >= ${param_index}")
        params.append(filters['minPrice'])
        param_index += 1
    
    if filters.get('maxPrice') is not None:
        conditions.append(f"i.sale_price <= ${param_index}")
        params.append(filters['maxPrice'])
        param_index += 1
    
    # Bag type filtering
    if filters.get('bagTypes'):
        placeholders = ', '.join([f'${i}' for i in range(param_index, param_index + len(filters['bagTypes']))])
        conditions.append(f"i.bag_type IN ({placeholders})")
        params.extend(filters['bagTypes'])
        param_index += len(filters['bagTypes'])
    
    # Time filtering
    if filters.get('timeStart') and filters.get('timeEnd'):
        conditions.append(f"${param_index}::time BETWEEN i.order_start_time::time AND i.order_end_time::time")
        params.append(filters['timeStart'])
        param_index += 1
        conditions.append(f"${param_index}::time BETWEEN i.order_start_time::time AND i.order_end_time::time")
        params.append(filters['timeEnd'])
        param_index += 1
    
    # order by
    order_by = build_order_by_clause(filters.get('sort'))
    
    # main query
    query = f"""
        SELECT DISTINCT 
            r.restaurant_id,
            r.branch_id,
            r.name,
            r.cuisinetype,
            r.rating,
            r.mainimageurl,
            r.logourl,
            r.longitude,
            r.latitude,
            r.what_you_could_get,
            r.liveflag,
            MIN(i.sale_price) as min_price,
            MAX(i.sale_price) as max_price,
            ARRAY_AGG(DISTINCT i.bag_type) as available_bag_types
        FROM "Restaurant" r
        LEFT JOIN "Inventory" i ON r.restaurant_id = i.restaurant_id AND r.branch_id = i.branch_id
    """
    
    if conditions:
        query += f" WHERE {' AND '.join(conditions)}"
    
    query += f"""
        GROUP BY r.restaurant_id, r.branch_id, r.name, r.cuisinetype, r.rating, 
                 r.mainimageurl, r.logourl, r.longitude, r.latitude, 
                 r.what_you_could_get, r.liveflag
        {order_by}
    """
    
    return query, params

def build_order_by_clause(sort_type: Optional[str]) -> str:
    """Build ORDER BY clause based on sort type."""
    if not sort_type:
        return "ORDER BY r.rating DESC" # sort descending
    
    sort_mapping = {
        'priceLowToHigh': 'ORDER BY MIN(i.sale_price) ASC',
        'priceHighToLow': 'ORDER BY MIN(i.sale_price) DESC',
        'ratingHighToLow': 'ORDER BY r.rating DESC',
        'ratingLowToHigh': 'ORDER BY r.rating ASC',
        'nameAZ': 'ORDER BY r.name ASC',
        'nameZA': 'ORDER BY r.name DESC'
    }
    
    return sort_mapping.get(sort_type, 'ORDER BY r.rating DESC')

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates using Haversine formula."""
    R = 6371
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2) * math.sin(dlon/2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def apply_distance_filter(restaurants: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply distance filtering to restaurants."""
    if not filters.get('maxDistance') or not filters.get('latitude') or not filters.get('longitude'):
        return restaurants
    
    filtered_restaurants = []
    for restaurant in restaurants:
        distance = calculate_distance(
            filters['latitude'],
            filters['longitude'],
            float(restaurant['latitude']) if restaurant['latitude'] else 0.0,
            float(restaurant['longitude']) if restaurant['longitude'] else 0.0
        )
        if distance <= filters['maxDistance']:
            filtered_restaurants.append(restaurant)
    
    return filtered_restaurants
