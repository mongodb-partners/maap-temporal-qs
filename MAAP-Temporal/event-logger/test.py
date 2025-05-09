# Basic initialization
from event-logger.maap_logging import MaapLogger

# Create an instance of the logger
logger = MaapLogger(service_url="http://0.0.0.0:8181", app_name="MAAP")

# Simple logging with additional fields
logger.info("User login successful", user_id="12345", conversation_id="abc123")
logger.error("Database connection failed", db_host="db.example.com", retries=3)

# Using context manager for structured logging
with logger.with_context(workflow_id="wf-123", activity_id="act-456"):
    logger.info("Started processing file")
    # ... do work ...
    logger.info("Finished processing file", records_processed=500)

# Decorator for function logging
@logger.log_function
def process_user(user_id: str, options: dict):
    # This function's entry, exit, and any exceptions will be logged
    # with parameters, return value, and execution time
    result = "mdfuser"
    return {"processed": True, "count": len(result)}

process_user(user_id="user123", options={"option1": "value1"})

# Log with custom fields
logger.info("User login successful", user_id="user123", conversation_id="sess-456", ip_address="192.168.1.1")

# Log with context
with logger.with_context(workflow_id="wf-789", activity_id="act-101112"):
    logger.warning("Resource usage high", cpu_percent=85.6, memory_mb=1024.5)