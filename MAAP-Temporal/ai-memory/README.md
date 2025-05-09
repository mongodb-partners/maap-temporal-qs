# AI-Memory-Service

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

### 1. Overview

AI-Memory-Service is an advanced AI-powered memory management system designed to store, retrieve, and analyze conversation histories and user memories. It leverages MongoDB Atlas for data storage, AWS Bedrock for AI capabilities, and FastAPI for API endpoints. The service provides functionalities for adding conversation messages, searching memories, generating conversation summaries, and managing a hierarchical memory structure.

Key features include:
- Conversation history storage and retrieval
- Semantic search using vector embeddings
- Dynamic memory importance scoring and pruning
- AI-powered conversation summarization
- Hybrid search combining full-text and semantic search

### 2. System Architecture

```mermaid
graph TD
    A[Client] --> B[FastAPI Server]
    B --> C[MongoDB Atlas]
    B --> D[AWS Bedrock]
    C --> E[Conversations Collection]
    C --> F[Memory Nodes Collection]
    D --> G[Embedding Model]
    D --> H[LLM Model]
```

The system consists of a FastAPI server that interacts with MongoDB Atlas for data storage and AWS Bedrock for AI operations. The MongoDB database contains two main collections: Conversations and Memory Nodes. AWS Bedrock provides embedding generation and language model capabilities.

### 3. Components

1. **FastAPI Server**
   - Purpose: Handles HTTP requests and serves as the main entry point for the application
   - Technologies: Python, FastAPI
   - Interactions: Communicates with MongoDB and AWS Bedrock

2. **MongoDB Database**
   - Purpose: Stores conversation histories and memory nodes
   - Technologies: MongoDB
   - Collections:
     - Conversations: Stores individual messages
     - Memory Nodes: Stores hierarchical memory structure

3. **AWS Bedrock Integration**
   - Purpose: Provides AI capabilities for embedding generation and language tasks
   - Technologies: AWS Bedrock API
   - Models:
     - Embedding Model: Generates vector representations of text
     - Language Model: Performs summarization and other NLP tasks

4. **Memory Management System**
   - Purpose: Manages the creation, updating, and pruning of memory nodes
   - Key Features:
     - Importance scoring
     - Memory reinforcement and decay
     - Automatic pruning of less important memories

5. **Search System**
   - Purpose: Enables efficient retrieval of relevant information
   - Features:
     - Hybrid search combining full-text and vector search
     - Semantic similarity matching

### 4. Installation & Deployment

1. Clone the repository:
   ```
   git clone https://github.com/mohammaddaoudfarooqi/AI-Memory-Service.git
   cd AI-Memory-Service
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables (see Configuration section)

4. Deploy using Docker:
   ```
   docker build -t ai-memory-service .
   docker run -p 8182:8182 ai-memory-service
   ```

### 5. Configuration

Configure the application using environment variables or a `.env` file:

```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
SUMMARY_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v1
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8182
DEBUG=False
```

### 6. Usage

1. Start the server:
   ```
   python main.py
   ```

2. Access the API at `http://localhost:8182`

3. Use the provided endpoints to add messages, search memories, and retrieve conversation summaries

### 7. API Reference

- `POST /conversation/`: Add a message to the conversation history
- `GET /retrieve_memory/`: Retrieve memory items, context, and similar memory nodes
- `GET /health`: Health check endpoint

For detailed request/response formats, refer to the Pydantic models in `models/pydantic_models.py`.

### 8. Security Considerations

- Ensure proper authentication and authorization for API access
- Use HTTPS for all communications
- Regularly rotate AWS and MongoDB credentials
- Implement rate limiting to prevent abuse

### 9. Monitoring & Logging

- The application uses a custom `MaapLogger` for logging
- Logs are stored both locally and sent to a remote logging service
- Monitor AWS Bedrock usage and costs
- Set up alerts for high memory usage or API errors

### 10. Troubleshooting

- Check MongoDB connection if database operations fail
- Verify AWS credentials if Bedrock API calls fail
- Review logs for detailed error messages and stack traces

### 11. Development Guide

- Follow PEP 8 style guide for Python code
- Use type hints and docstrings for better code readability
- Run tests before submitting pull requests
- Use the `@logger.log_function` decorator for automatic function logging

### 12. Maintenance & Operations

- Regularly update dependencies
- Monitor and optimize MongoDB indexes
- Review and adjust memory pruning settings as needed
- Backup the MongoDB database regularly

This documentation provides a comprehensive overview of the AI-Memory-Service. For further details on specific components or functionalities, refer to the inline comments and docstrings within the codebase.