import json
import humanize
from typing import List
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, status
from typing_extensions import Annotated
import uvicorn
from pydantic import ValidationError

# Import from local modules
import config
from utils.logger import logger
from utils import error_utils, file_utils
from models.pydantic_models import UploadRequest, UploadResponse, ErrorResponse
from services.embedding_service import EmbeddingService

# Initialize FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description=config.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Dependencies
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post(
    "/upload",
    response_model=UploadResponse,
    responses={
        200: {"model": UploadResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def upload(
    files: Annotated[List[UploadFile], File(description="Multiple files to upload")] = [],
    json_input_params: str = Form(description="Input parameters as a JSON string"),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Upload files and web URLs to be processed and stored in the vector database.
    
    Parameters:
    - **files**: One or more files to upload and process
    - **json_input_params**: JSON string containing:
      - user_id: ID of the user
      - mongodb_config: MongoDB connection configuration
      - web_pages: List of web URLs to process (optional)
    
    Returns:
    - Upload status and details
    """
    try:
        # Parse JSON input
        try:
            upload_data = json.loads(json_input_params)
            request = UploadRequest(**upload_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON input"
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid input parameters: {str(e)}"
            )
        
        # Convert MongoDB config to dictionary for service
        mongodb_config = {
            "uri": request.mongodb_config.uri,
            "database": request.mongodb_config.database,
            "collection": request.mongodb_config.collection,
            "index_name": request.mongodb_config.index_name,
            "text_field": request.mongodb_config.text_field,
            "embedding_field": request.mongodb_config.embedding_field
        }
        
        # Process files if any
        file_docs_count = 0
        if files:
            logger.info(f"Processing {len(files)} uploaded files")
            saved_files = file_utils.save_uploaded_files(files)
            file_docs_count = await embedding_service.process_and_store_files(
                saved_files, 
                request.user_id, 
                mongodb_config
            )
        
        # Process web URLs if any
        web_docs_count = 0
        if request.web_pages:
            web_urls = [str(url) for url in request.web_pages]
            logger.info(f"Processing {len(web_urls)} web URLs")
            web_docs_count = await embedding_service.process_and_store_urls(
                web_urls, 
                request.user_id, 
                mongodb_config
            )
        
        # Build response
        file_details = [
            f"{file.filename} ({humanize.naturalsize(file.size)})" 
            for file in files
        ]
        
        web_details = [str(url) for url in request.web_pages]
        
        response = UploadResponse(
            success=True,
            message="Upload processed successfully",
            details={
                "files_processed": len(files),
                "urls_processed": len(request.web_pages),
                "documents_stored": file_docs_count + web_docs_count,
                "file_list": file_details,
                "url_list": web_details
            }
        )
        
        return response
        
    except HTTPException:
        # Pass through HTTP exceptions
        raise
    except Exception as e:
        error_response = error_utils.handle_exception(e)
        return ErrorResponse(**error_response)

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=config.SERVICE_HOST, 
        port=config.SERVICE_PORT,
        reload=config.DEBUG
    )