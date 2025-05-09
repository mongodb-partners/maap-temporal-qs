from datetime import datetime
from pydantic import BaseModel, Field

# Pydantic models
class LogRequest(BaseModel):
    level: str = Field(
        ..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    message: str = Field(..., description="Log message content")
    app_name: str = Field(..., description="Source application name")

    # Dynamic fields support - allow any additional fields
    class Config:
        extra = "allow"

        # Updated schema extra field for Pydantic v2 compatibility
        json_schema_extra = {
            "example": {
                "level": "INFO",
                "message": "User login successful",
                "app_name": "auth-service",
                "workflow_id": "wf-123456",
                "activity_id": "act-78910",
                "user_id": "user@example.com",
                "conversation_id": "sess-abcdef",
                "ctx": "login-flow",
                "custom_field": "custom value",
            }
        }


class LogResponse(BaseModel):
    status: str
    message: str
    timestamp: datetime
