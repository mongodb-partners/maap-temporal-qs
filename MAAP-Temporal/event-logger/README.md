# Event-Logger Documentation

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

The Event-Logger is a high-performance, asynchronous logging service designed to capture and store event logs for MAAP (Multi-Mission Algorithm and Analysis Platform) applications. It provides a robust solution for centralized logging with features such as buffered writes, MongoDB persistence, and local file backups.

Key features include:
- Asynchronous log processing
- Buffered writes to reduce database load
- MongoDB persistence for long-term storage
- Local file logging for backup and quick access
- Customizable log retention policies
- RESTful API for log submission and management
- Support for structured logging with dynamic fields
- Automatic log file cleanup

This service is ideal for distributed systems that require a centralized, scalable logging solution with high throughput and reliability.

## 2. System Architecture

```mermaid
graph TD
    A[Client Applications] -->|HTTP POST| B[FastAPI Server]
    B --> C[Log Buffer Manager]
    C --> D[Local File Logger]
    C --> E[MongoDB]
    B --> F[Background Tasks]
    F -->|Periodic Flush| C
    F -->|Periodic Cleanup| D
    B --> G[Status Endpoint]
    B --> H[Force Flush Endpoint]
```

The Event-Logger consists of the following main components:
1. FastAPI Server: Handles incoming log requests and manages the overall flow.
2. Log Buffer Manager: Temporarily stores logs in memory before persisting.
3. Local File Logger: Writes logs to local files for backup and quick access.
4. MongoDB Connection: Persists logs for long-term storage and querying.
5. Background Tasks: Manages periodic operations like flushing logs and cleanup.
6. API Endpoints: Provides interfaces for log submission, status checks, and manual operations.

## 3. Components

### FastAPI Server
- Purpose: Serves as the main entry point for the logging service.
- Core Functionality: Handles HTTP requests, manages the lifecycle of the application, and coordinates between different components.
- Technologies: FastAPI, Uvicorn

### Log Buffer Manager
- Purpose: Temporarily stores logs in memory to reduce database write operations.
- Core Functionality: Buffers incoming logs, manages buffer size, and triggers flushes when necessary.
- Technologies: Python asyncio

### Local File Logger
- Purpose: Provides a backup logging mechanism and quick access to recent logs.
- Core Functionality: Writes logs to rotating files on the local filesystem.
- Technologies: Python's built-in logging module

### MongoDB Connection
- Purpose: Offers persistent storage for logs with advanced querying capabilities.
- Core Functionality: Inserts buffered logs into MongoDB, manages collection size and document expiration.
- Technologies: Motor (asynchronous MongoDB driver)

### Background Tasks
- Purpose: Executes periodic maintenance operations.
- Core Functionality: Flushes log buffer to MongoDB, cleans up old log files.
- Technologies: Python asyncio

## 4. Installation & Deployment

### Prerequisites
- Python 3.10 or higher
- Docker (optional, for containerized deployment)
- MongoDB instance (can be local or cloud-hosted)

### Setup Steps
1. Clone the repository:
   ```
   git clone https://github.com/mohammaddaoudfarooqi/event-logger.git
   cd event-logger
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables (see Configuration section for details).

5. Run the application:
   ```
   python main.py
   ```

### Docker Deployment
1. Build the Docker image:
   ```
   docker build -t maap-event-logger .
   ```

2. Run the container:
   ```
   docker run -p 8181:8181 --env-file .env maap-event-logger
   ```

## 5. Configuration

The application uses environment variables for configuration. Create a `.env` file in the project root with the following variables:

```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DB_NAME=event_logs
MONGODB_COLLECTION=logs
LOG_DIR=logs
FLUSH_INTERVAL=10
DELETE_LOGS_OLDER_THAN=30
LOG_RETENTION_DAYS=60
LOG_BUFFER_SIZE=1000
MAX_COLLECTION_SIZE=1073741824
MAX_DOCUMENTS=100000
HOST=0.0.0.0
PORT=8181
WORKER_COUNT=0
```

Adjust these values according to your requirements. For production deployments, ensure secure handling of sensitive information like database credentials.

## 6. Usage

To log an event, send a POST request to the `/log` endpoint with a JSON payload:

```python
import requests

log_data = {
    "level": "INFO",
    "message": "User login successful",
    "app_name": "auth-service",
    "workflow_id": "wf-123456",
    "user_id": "user@example.com"
}

response = requests.post("http://localhost:8181/log", json=log_data)
print(response.json())
```

The service supports dynamic fields, allowing you to include any additional context in your log entries.

## 7. API Reference

### POST /log
Submit a log entry.

Request body:
```json
{
  "level": "INFO",
  "message": "Log message content",
  "app_name": "application-name",
  "additional_field": "custom value"
}
```

Response:
```json
{
  "status": "success",
  "message": "Log recorded",
  "timestamp": "2023-04-01T12:00:00Z"
}
```

### GET /status
Check the service status.

Response:
```json
{
  "status": "operational",
  "mongodb_status": "connected",
  "buffer_size": 50,
  "time_since_last_flush": 5,
  "version": "1.1",
  "timestamp": "2023-04-01T12:00:00Z"
}
```

### POST /force-flush
Manually trigger a buffer flush.

Response:
```json
{
  "status": "success",
  "message": "Flushed 100 logs to MongoDB"
}
```

## 8. Security Considerations

- Use HTTPS in production to encrypt log data in transit.
- Implement authentication for the logging API in production environments.
- Regularly update dependencies to patch security vulnerabilities.
- Use strong, unique passwords for the MongoDB connection.
- Implement network security measures to restrict access to the logging service and database.

## 9. Monitoring & Logging

- The service provides a `/status` endpoint for health checks and monitoring.
- Use the local log files (`logs/BufferedLogging.log`) for debugging and monitoring the logger itself.
- Set up alerts for MongoDB disconnections or large buffer sizes.
- Monitor disk usage for local log files.

## 10. Troubleshooting

Common issues and solutions:
- If logs are not appearing in MongoDB, check the MongoDB connection status and the local log files for errors.
- For performance issues, adjust the `FLUSH_INTERVAL` and `LOG_BUFFER_SIZE` settings.
- If the service is not starting, ensure all environment variables are correctly set.

## 11. Development Guide

To contribute to the project:
1. Fork the repository and create a new branch for your feature or bug fix.
2. Ensure all tests pass before submitting a pull request.
3. Follow PEP 8 style guidelines for Python code.
4. Update documentation for any new features or changes.

## 12. Maintenance & Operations

- Regularly monitor disk usage and clean up old log files if necessary.
- Schedule periodic backups of the MongoDB database.
- Review and adjust log retention policies based on storage capacity and compliance requirements.
- Perform regular security audits and update dependencies.

This documentation provides a comprehensive overview of the Event-Logger. For further assistance or to report issues, please contact the project maintainers.