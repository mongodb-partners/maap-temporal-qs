import asyncio
import logging
import logging.handlers
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import config
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorClient
from models.pydantic_models import LogRequest, LogResponse

# Configure logging
log_file_path = f"{config.LOG_DIR}/BufferedLogging.log"
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# Set up rotating file handler
file_handler = logging.handlers.TimedRotatingFileHandler(
    log_file_path, when="midnight", backupCount=10
)
file_handler.suffix = "%Y-%m-%d.log"
file_handler.setFormatter(formatter)

# Set up console handler for important logs
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Configure logger
logger = logging.getLogger("event-logger")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)




class LogBufferManager:
    def __init__(self):
        self.buffer: List[Dict[str, Any]] = []
        self.last_flush_time = time.time()
        self._lock = asyncio.Lock()

    async def add(self, log_document: Dict[str, Any]) -> bool:
        """Add a log to the buffer and return True if buffer size threshold reached"""
        async with self._lock:
            self.buffer.append(log_document)
            return len(self.buffer) >= config.LOG_BUFFER_SIZE

    async def get_and_clear(self) -> List[Dict[str, Any]]:
        """Get all logs from buffer and clear it"""
        async with self._lock:
            buffer_copy = self.buffer.copy()
            self.buffer.clear()
            self.last_flush_time = time.time()
            return buffer_copy

    def should_flush(self) -> bool:
        """Check if enough time has passed to flush logs"""
        return time.time() - self.last_flush_time >= config.FLUSH_INTERVAL

    def buffer_size(self) -> int:
        """Get current buffer size"""
        return len(self.buffer)


# Initialize MongoDB client and buffer manager
mongo_client = None
db = None
collection = None
log_buffer = LogBufferManager()


@asynccontextmanager
async def lifespan_context(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global mongo_client, db, collection

    # Initialize MongoDB connection
    try:
        mongo_client = AsyncIOMotorClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
        await mongo_client.admin.command("ping")  # Verify connection
        db = mongo_client[config.MONGODB_DB_NAME]
        collection = db[config.MONGODB_COLLECTION]

        # Ensure the collection exists with proper settings
        collection_list = await db.list_collection_names()
        if config.MONGODB_COLLECTION not in collection_list:
            try:
                await db.create_collection(
                    config.MONGODB_COLLECTION,
                    capped=True,
                    size=config.MAX_COLLECTION_SIZE,
                    max=config.MAX_DOCUMENTS,
                )
                logger.info(f"Capped collection '{config.MONGODB_COLLECTION}' created")

                # Create TTL index for document expiration
                await collection.create_index(
                    [("timestamp", 1)],
                    expireAfterSeconds=config.LOG_RETENTION_DAYS * 86400,
                    name="timestamp_ttl_idx",
                )
                logger.info(
                    f"TTL index created with {config.LOG_RETENTION_DAYS} days retention"
                )
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB collection: {e}")
        else:
            logger.info(f"Using existing collection '{config.MONGODB_COLLECTION}'")
    except Exception as e:
        logger.critical(f"Failed to connect to MongoDB: {e}")
        # Continue with degraded service - logs will still be written to files

    # Start background tasks
    flush_task = asyncio.create_task(periodic_flush_logs())
    cleanup_task = asyncio.create_task(periodic_cleanup())

    try:
        yield  # Yield control back to FastAPI
    finally:
        # Cleanup on shutdown
        flush_task.cancel()
        cleanup_task.cancel()

        try:
            # Final flush of any remaining logs
            buffer_content = await log_buffer.get_and_clear()
            if buffer_content and collection is not None:
                try:
                    await collection.insert_many(buffer_content)
                    logger.info(
                        f"Final flush: Saved {len(buffer_content)} logs to MongoDB"
                    )
                except Exception as e:
                    logger.error(f"Final flush failed: {e}")

            # Wait for tasks to be cancelled
            await asyncio.gather(flush_task, cleanup_task, return_exceptions=True)
        except Exception:
            pass

        # Close MongoDB connection
        if mongo_client:
            mongo_client.close()
            logger.info("MongoDB connection closed")


async def periodic_flush_logs():
    """Periodically flush logs from buffer to MongoDB"""
    while True:
        try:
            if log_buffer.should_flush() and log_buffer.buffer_size() > 0:
                buffer_content = await log_buffer.get_and_clear()
                if buffer_content and collection is not None:
                    try:
                        await collection.insert_many(buffer_content)
                        logger.info(
                            f"Periodic flush: Saved {len(buffer_content)} logs to MongoDB"
                        )
                    except Exception as e:
                        logger.error(f"Failed to flush logs to MongoDB: {e}")
        except Exception as e:
            logger.error(f"Error in periodic flush: {e}")
        finally:
            await asyncio.sleep(
                min(10, config.FLUSH_INTERVAL / 6)
            )  # Check more frequently than flush interval


async def periodic_cleanup():
    """Periodically cleanup old log files"""
    while True:
        try:
            logger.info("Starting log file cleanup check")
            cutoff_date = datetime.now() - timedelta(days=config.DELETE_LOGS_OLDER_THAN)
            cleanup_count = 0

            for file_name in os.listdir(config.LOG_DIR):
                file_path = os.path.join(config.LOG_DIR, file_name)
                if os.path.isfile(file_path):
                    file_modified_time = datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    )
                    if file_modified_time < cutoff_date:
                        try:
                            os.remove(file_path)
                            cleanup_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete log file {file_name}: {e}")

            if cleanup_count > 0:
                logger.info(f"Cleanup complete: Deleted {cleanup_count} old log files")
        except Exception as e:
            logger.error(f"Error during log file cleanup: {e}")

        # Run once per day
        await asyncio.sleep(86400)


# Initialize FastAPI app
app = FastAPI(
    title="MAAP Buffered Async Logging Service",
    version="1.1",
    description="High-performance async logging service with MongoDB persistence",
    lifespan=lifespan_context,
)


@app.post("/log", response_model=LogResponse, status_code=201)
async def log_message(
    request: LogRequest, background_tasks: BackgroundTasks, response: Response
):
    """Log a message to file and buffer it for MongoDB"""
    try:
        # Normalize log level
        log_level = request.level.upper()
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise HTTPException(
                status_code=400, detail=f"Invalid log level: {request.level}"
            )

        # Convert Pydantic model to dict
        request_dict = request.model_dump()  # Updated for Pydantic v2 compatibility

        # Create log document with all fields from the request
        log_document = {}

        # Generate timestamp
        timestamp = datetime.now(timezone.utc)
        log_document["timestamp"] = timestamp

        # Add all fields from the request
        for key, value in request_dict.items():
            if value is not None:  # Only include non-None values
                log_document[key] = value

        # Ensure level is uppercase
        log_document["level"] = log_level

        if "timestamp" in request_dict and request_dict["timestamp"]:
            log_document["timestamp"] = datetime.fromisoformat(
                request_dict["timestamp"].replace("Z", "+00:00")
            )

        # Log to file with app name prefixed
        log_function = getattr(logger, log_level.lower())

        # Create file log message with additional context if available
        log_parts = [f"[{request.app_name}]"]

        # Add optional context fields if available
        context_fields = [
            "workflow_id",
            "activity_id",
            "user_id",
            "conversation_id",
            "ctx",
        ]
        for field in context_fields:
            if field in request_dict and request_dict[field] is not None:
                log_parts.append(f"{field}={request_dict[field]}")

        # Add the main message
        log_parts.append(request.message)

        # Join all parts with spaces
        file_log_message = " ".join(log_parts)
        log_function(file_log_message)

        # Add to buffer
        should_flush = await log_buffer.add(log_document)

        # If buffer threshold is reached, schedule flush in background
        if should_flush:
            background_tasks.add_task(flush_buffer_now)

        return LogResponse(
            status="success", message="Log recorded", timestamp=timestamp
        )
    except Exception as e:
        logger.error(f"Error processing log request: {e}")
        response.status_code = 500
        return LogResponse(
            status="error",
            message=f"Failed to process log: {str(e)}",
            timestamp=datetime.now(timezone.utc),
        )


async def flush_buffer_now():
    """Force an immediate buffer flush"""
    try:
        buffer_content = await log_buffer.get_and_clear()
        if buffer_content and collection is not None:
            await collection.insert_many(buffer_content)
            logger.info(f"Manual flush: Saved {len(buffer_content)} logs to MongoDB")
    except Exception as e:
        logger.error(f"Manual buffer flush failed: {e}")


@app.get("/status")
async def status():
    """Health check endpoint with additional service status"""
    mongo_status = "connected"

    # Test MongoDB connection
    if mongo_client:
        try:
            await asyncio.wait_for(mongo_client.admin.command("ping"), timeout=2.0)
        except Exception:
            mongo_status = "disconnected"
    else:
        mongo_status = "not_configured"

    return {
        "status": "operational",
        "mongodb_status": mongo_status,
        "buffer_size": log_buffer.buffer_size(),
        "time_since_last_flush": round(time.time() - log_buffer.last_flush_time),
        "version": "1.1",
        "timestamp": datetime.now(timezone.utc),
    }


@app.post("/force-flush", status_code=200)
async def force_flush():
    """Manually trigger a buffer flush"""
    try:
        buffer_content = await log_buffer.get_and_clear()
        if not buffer_content:
            return {
                "status": "success",
                "message": "Buffer was empty, nothing to flush",
            }

        if collection is not None:
            await collection.insert_many(buffer_content)
            return {
                "status": "success",
                "message": f"Flushed {len(buffer_content)} logs to MongoDB",
            }
        else:
            return {
                "status": "partial_success",
                "message": "Logs cleared from buffer but MongoDB is not available",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to flush logs: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        workers=config.WORKER_COUNT if config.WORKER_COUNT > 0 else None,
    )
