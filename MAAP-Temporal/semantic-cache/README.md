# Semantic-Cache Documentation

## Table of Contents
1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Components](#3-components)
4. [Installation & Deployment](#4-installation--deployment)
5. [Configuration](#5-configuration)
6. [Usage](#6-usage)
7. [API Reference](#7-api-reference)
8. [Security Considerations](#8-security-considerations)
9. [Monitoring & Logging](#9-monitoring--logging)
10. [Troubleshooting](#10-troubleshooting)
11. [Development Guide](#11-development-guide)
12. [Maintenance & Operations](#12-maintenance--operations)

## 1. Overview

Semantic-Cache is a service designed to store and retrieve query responses based on semantic similarity. It provides a caching mechanism that allows for efficient retrieval of previously computed responses to semantically similar queries, potentially reducing computational load and response times for repeated or similar requests.

Key features:
- Semantic similarity-based caching
- Integration with AWS Bedrock for embedding generation
- MongoDB-based storage with vector search capabilities
- FastAPI-powered RESTful API
- Configurable similarity thresholds and cache TTL

## 2. System Architecture

```mermaid
graph TD
    A[Client] --> B[FastAPI Service]
    B --> C[Cache Service]
    C --> D[MongoDB]
    C --> E[Bedrock Service]
    E --> F[AWS Bedrock]
    B --> G[Logger Service]
```

The system consists of several interconnected components:
1. FastAPI Service: Handles incoming HTTP requests
2. Cache Service: Manages cache operations
3. MongoDB: Stores cache entries and performs vector searches
4. Bedrock Service: Generates embeddings using AWS Bedrock
5. Logger Service: Provides logging capabilities

## 3. Components

### FastAPI Service
- Purpose: Handles HTTP requests and routes them to appropriate handlers
- Technologies: FastAPI, Uvicorn
- Interactions: Communicates with Cache Service

### Cache Service
- Purpose: Manages cache operations, including saving and retrieving entries
- Technologies: Python
- Interactions: Communicates with MongoDB and Bedrock Service

### MongoDB Manager
- Purpose: Handles database operations and vector searches
- Technologies: PyMongo, MongoDB Atlas
- Interactions: Stores and retrieves cache entries

### Bedrock Service
- Purpose: Generates embeddings for queries
- Technologies: Boto3, AWS Bedrock
- Interactions: Communicates with AWS Bedrock API

### Logger
- Purpose: Provides logging capabilities for the entire application
- Technologies: Python's logging module, custom async logging
- Interactions: Used by all components for logging

## 4. Installation & Deployment

1. Clone the repository:
   ```
   git clone https://github.com/mohammaddaoudfarooqi/semantic-cache.git
   cd semantic-cache
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables (see [Configuration](#5-configuration) section).

4. Run the application:
   ```
   python main.py
   ```

For Docker deployment:
1. Build the Docker image:
   ```
   docker build -t semantic-cache .
   ```

2. Run the container:
   ```
   docker run -p 8183:8183 --env-file .env semantic-cache
   ```

## 5. Configuration

Configuration is managed through environment variables. Create a `.env` file with the following variables:

```
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v1
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8183
LOGGER_SERVICE_URL=http://event-logger:8181
DEBUG=False
CACHE_TTL_SECONDS=3600
SIMILARITY_THRESHOLD=0.95
```

Adjust these values according to your specific setup and requirements.

## 6. Usage

The Semantic-Cache service provides two main endpoints:

1. Save to cache:
   ```
   POST /save_to_cache
   ```
   Saves a query-response pair to the cache.

2. Read from cache:
   ```
   POST /read_cache
   ```
   Retrieves a cached response for a semantically similar query.

Example usage with curl:

```bash
# Save to cache
curl -X POST http://localhost:8183/save_to_cache \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123", "query": "What is the capital of France?", "response": "The capital of France is Paris."}'

# Read from cache
curl -X POST http://localhost:8183/read_cache \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123", "query": "What's the capital city of France?"}'
```

## 7. API Reference

### POST /save_to_cache

Saves a query-response pair to the cache.

Request body:
```json
{
  "user_id": "string",
  "query": "string",
  "response": "string"
}
```

Response:
```json
{
  "message": "string",
  "error": "string (optional)"
}
```

### POST /read_cache

Retrieves a cached response for a semantically similar query.

Request body:
```json
{
  "user_id": "string",
  "query": "string"
}
```

Response:
```json
{
  "response": "string",
  "error": "string (optional)"
}
```

## 8. Security Considerations

- Ensure proper authentication and authorization for API access.
- Use HTTPS for all communications.
- Regularly update dependencies and apply security patches.
- Implement rate limiting to prevent abuse.
- Use secure configurations for MongoDB and AWS services.

## 9. Monitoring & Logging

The application uses a custom logger that supports both local and remote logging. Key metrics to monitor include:

- Cache hit/miss rates
- Response times for cache operations
- Error rates and types
- MongoDB query performance
- AWS Bedrock API usage and latency

Use the provided logging functionality to track application behavior and performance.

## 10. Troubleshooting

Common issues and solutions:

1. MongoDB connection errors:
   - Check MongoDB URI and credentials
   - Ensure network connectivity to MongoDB Atlas

2. AWS Bedrock API errors:
   - Verify AWS credentials and permissions
   - Check AWS region configuration

3. Embedding generation failures:
   - Review AWS Bedrock service status
   - Check input query format and length

4. Cache misses:
   - Adjust similarity threshold in configuration
   - Verify vector search index setup in MongoDB

## 11. Development Guide

1. Code Structure:
   - `main.py`: FastAPI application entry point
   - `config.py`: Configuration management
   - `database/`: MongoDB-related code
   - `models/`: Pydantic models
   - `services/`: Business logic services
   - `utils/`: Utility functions and logger

2. Adding new features:
   - Implement new services in the `services/` directory
   - Add new API endpoints in `main.py`
   - Update models in `models/pydantic_models.py` as needed

3. Testing:
   - Write unit tests for new services and API endpoints
   - Use pytest for running tests

4. Debugging:
   - Set `DEBUG=True` in the configuration for verbose logging
   - Use the custom logger for adding debug statements

## 12. Maintenance & Operations

1. Regular tasks:
   - Monitor cache hit rates and adjust similarity threshold if needed
   - Review and optimize MongoDB indexes
   - Update dependencies regularly

2. Scaling considerations:
   - Implement horizontal scaling for the FastAPI service
   - Consider sharding for MongoDB as data grows
   - Monitor AWS Bedrock usage and adjust limits if necessary

3. Backup and recovery:
   - Set up regular backups for MongoDB data
   - Implement a disaster recovery plan

4. Performance optimization:
   - Profile API endpoints and optimize slow operations
   - Consider caching embeddings to reduce AWS Bedrock API calls
   - Optimize MongoDB queries and index usage

By following this documentation, you should be able to effectively deploy, use, and maintain the Semantic-Cache service.