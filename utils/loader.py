import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

# Global variables to hold the MongoDB client and database instances
_mongo_client = None
_mongo_db = None

def _initialize_mongo_connection():
    """
    Initializes the MongoDB client and database globally.
    This function should be called once when your bot starts up.
    """
    global _mongo_client, _mongo_db

    if _mongo_client is None:
        mongo_url = os.getenv("MONGO_URL")
        db_name = os.getenv("MONGO_DB_NAME")

        if not mongo_url or not db_name:
            raise ValueError("Missing MONGO_URL or MONGO_DB_NAME in environment. Cannot initialize MongoDB.")

        try:
            # Set a timeout for server selection to prevent indefinite blocking
            _mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
            # The ping command attempts to connect to the database
            _mongo_client.admin.command('ping')
            _mongo_db = _mongo_client[db_name]
            print("MongoDB connection initialized successfully.")
        except ConnectionFailure as e:
            print(f"MongoDB connection failed: {e}")
            _mongo_client = None  # Reset to prevent using a bad client
            _mongo_db = None
            raise  # Re-raise to indicate a critical startup failure
        except Exception as e:
            print(f"An unexpected error occurred during MongoDB initialization: {e}")
            _mongo_client = None
            _mongo_db = None
            raise  # Re-raise for unexpected errors

def _get_db():
    global _mongo_client, _mongo_db
    if _mongo_client is None or _mongo_db is None:
        _initialize_mongo_connection()
    return _mongo_db

def load_data(name: str):
    """
    Load data from a MongoDB collection by its name.
    """
    db = _get_db()
    try:
        # Exclude the default MongoDB '_id' field from results
        return list(db[name].find({}, {"_id": False}))
    except OperationFailure as e:
        print(f"MongoDB operation failed for collection '{name}' during load: {e}")
        return []  # Return empty list on failure
    except Exception as e:
        print(f"An error occurred loading data from MongoDB collection '{name}': {e}")
        return []

def save_data(name: str, data):
    """
    Save data to a MongoDB collection by its name.
    This replaces all existing documents in the collection with the new data.
    """
    db = _get_db()
    collection = db[name]
    try:
        # Clear existing data
        collection.delete_many({})
        # Insert new data
        if isinstance(data, list):
            if data:  # Only insert if the list is not empty
                collection.insert_many(data)
        else:  # For single documents
            collection.insert_one(data)
    except OperationFailure as e:
        print(f"MongoDB operation failed for collection '{name}' during save: {e}")
    except Exception as e:
        print(f"An error occurred saving data to MongoDB collection '{name}': {e}")

def close_mongo_connection():
    """
    Closes the MongoDB client connection.
    This should be called when your bot shuts down.
    """
    global _mongo_client, _mongo_db
    if _mongo_client:
        _mongo_client.close()
        print("MongoDB connection closed.")
        _mongo_client = None
        _mongo_db = None
        
