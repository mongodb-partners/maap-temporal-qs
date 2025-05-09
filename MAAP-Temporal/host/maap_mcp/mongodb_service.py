from typing import Dict, List, Optional

import mcp_config
import pymongo
import pymongo.synchronous
from logger import logger
from pymongo.errors import ConnectionFailure, OperationFailure


class MongoDBService:
    def __init__(
        self,
        connection_string: str = mcp_config.MONGODB_URI,
        database_name: str = mcp_config.DB_NAME,
    ):
        """
        Initialize the MongoDB service.

        Args:
            connection_string: MongoDB connection string
            database_name: MongoDB database name
        """
        try:
            self.client = pymongo.MongoClient(connection_string)
            # Ping the server to verify connection
            self.client.admin.command("ping")
            self.db = self.client[database_name]
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def get_client(self) -> pymongo.MongoClient:
        """
        Get the MongoDB client.

        Returns:
            pymongo.MongoClient: MongoDB client
        """
        return self.client

    def get_database(self) -> pymongo.synchronous.database.Database:
        """
        Get the MongoDB database.

        Returns:
            pymongo.database.Database: MongoDB database
        """
        return self.db

    def get_collection(self, collection_name: str) -> pymongo.synchronous.collection.Collection:
        """
        Get a collection from the database.

        Args:
            collection_name: Name of the collection

        Returns:
            pymongo.collection.Collection: MongoDB collection
        """
        try:
            return self.db[collection_name]
        except Exception as e:
            logger.error(f"Error accessing collection {collection_name}: {str(e)}")
            raise

    def list_collections(self) -> List[str]:
        """
        List all collections in the database.

        Returns:
            List[str]: List of collection names
        """
        try:
            return self.db.list_collection_names()
        except Exception as e:
            logger.error(f"Error listing collections: {str(e)}")
            raise

    def create_collection(self, collection_name: str) -> None:
        """
        Create a new collection if it doesn't exist.

        Args:
            collection_name: Name of the collection
        """
        try:
            if collection_name not in self.db.list_collection_names():
                self.db.create_collection(collection_name)
                logger.info(f"Created collection: {collection_name}")
        except OperationFailure as e:
            logger.error(f"Failed to create collection {collection_name}: {str(e)}")
            raise

    def insert_one(self, collection_name: str, document: Dict) -> str:
        """
        Insert a single document into a collection.

        Args:
            collection_name: Name of the collection
            document: Document to be inserted

        Returns:
            str: ID of the inserted document
        """
        try:
            result = self.db[collection_name].insert_one(document)
            logger.info(f"Inserted document with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting document: {str(e)}")
            raise

    def insert_many(self, collection_name: str, documents: List[Dict]) -> List[str]:
        """
        Insert multiple documents into a collection.

        Args:
            collection_name: Name of the collection
            documents: List of documents to be inserted

        Returns:
            List[str]: IDs of the inserted documents
        """
        try:
            result = self.db[collection_name].insert_many(documents)
            inserted_ids = [str(id) for id in result.inserted_ids]
            logger.info(f"Inserted {len(inserted_ids)} documents")
            return inserted_ids
        except Exception as e:
            logger.error(f"Error inserting multiple documents: {str(e)}")
            raise

    def find_one(self, collection_name: str, query: Dict) -> Optional[Dict]:
        """
        Find a single document in a collection.

        Args:
            collection_name: Name of the collection
            query: Query to filter documents

        Returns:
            Optional[Dict]: Document if found, None otherwise
        """
        try:
            result = self.db[collection_name].find_one(query)
            return result
        except Exception as e:
            logger.error(f"Error finding document: {str(e)}")
            raise

    def find_many(
        self, collection_name: str, query: Dict, limit: int = 0
    ) -> List[Dict]:
        """
        Find multiple documents in a collection.

        Args:
            collection_name: Name of the collection
            query: Query to filter documents
            limit: Maximum number of documents to return (0 = no limit)

        Returns:
            List[Dict]: List of documents
        """
        try:
            cursor = self.db[collection_name].find(query)
            if limit > 0:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error finding documents: {str(e)}")
            raise

    def update_one(self, collection_name: str, query: Dict, update: Dict) -> int:
        """
        Update a single document in a collection.

        Args:
            collection_name: Name of the collection
            query: Query to filter document
            update: Update operations

        Returns:
            int: Number of documents modified
        """
        try:
            result = self.db[collection_name].update_one(query, update)
            logger.info(f"Modified {result.modified_count} document(s)")
            return result.modified_count
        except Exception as e:
            logger.error(f"Error updating document: {str(e)}")
            raise

    def update_many(self, collection_name: str, query: Dict, update: Dict) -> int:
        """
        Update multiple documents in a collection.

        Args:
            collection_name: Name of the collection
            query: Query to filter documents
            update: Update operations

        Returns:
            int: Number of documents modified
        """
        try:
            result = self.db[collection_name].update_many(query, update)
            logger.info(f"Modified {result.modified_count} document(s)")
            return result.modified_count
        except Exception as e:
            logger.error(f"Error updating documents: {str(e)}")
            raise

    def delete_one(self, collection_name: str, query: Dict) -> int:
        """
        Delete a single document from a collection.

        Args:
            collection_name: Name of the collection
            query: Query to filter document

        Returns:
            int: Number of documents deleted
        """
        try:
            result = self.db[collection_name].delete_one(query)
            logger.info(f"Deleted {result.deleted_count} document(s)")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise

    def delete_many(self, collection_name: str, query: Dict) -> int:
        """
        Delete multiple documents from a collection.

        Args:
            collection_name: Name of the collection
            query: Query to filter documents

        Returns:
            int: Number of documents deleted
        """
        try:
            result = self.db[collection_name].delete_many(query)
            logger.info(f"Deleted {result.deleted_count} document(s)")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            raise

    def aggregate(self, collection_name: str, pipeline: List[Dict]) -> List[Dict]:
        """
        Perform an aggregation operation on a collection.

        Args:
            collection_name: Name of the collection
            pipeline: Aggregation pipeline

        Returns:
            List[Dict]: Result of the aggregation
        """
        try:
            result = self.db[collection_name].aggregate(pipeline)
            return list(result)
        except Exception as e:
            logger.error(f"Error performing aggregation: {str(e)}")
            raise

    def create_index(self, collection_name: str, keys: Dict, **kwargs) -> str:
        """
        Create an index on a collection.

        Args:
            collection_name: Name of the collection
            keys: Keys to index
            **kwargs: Additional index options

        Returns:
            str: Name of the created index
        """
        try:
            result = self.db[collection_name].create_index(keys, **kwargs)
            logger.info(f"Created index: {result}")
            return result
        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            raise


def get_mongodb_service() -> MongoDBService:
    """
    Get a cached MongoDB service instance.

    Returns:
        MongoDBService: MongoDB service instance
    """
    return MongoDBService()
