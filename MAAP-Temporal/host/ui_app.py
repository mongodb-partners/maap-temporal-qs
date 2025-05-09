import asyncio
import json
import os
import re
import time
import traceback
import uuid

import gradio as gr
import uvicorn
from fastapi import FastAPI
from gradio import Markdown as m
from maap_mcp.logger import logger
from maap_mcp.mcp_config import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    COLLECTION_NAME,
    DB_NAME,
    DEBUG,
    FULLTEXT_SEARCH_FIELD,
    MONGODB_URI,
    PLUS_IMAGE,
    VECTOR_SEARCH_FIELD,
    VECTOR_SEARCH_INDEX_NAME,
)
from models import (
    AIGenerationParams,
    CacheStorageParams,
    DataIngestionParams,
    ImageProcessingParams,
    MemoryRetrievalParams,
    MemoryStorageParams,
    PromptRetrievalParams,
    SemanticCacheParams,
)
from temporal_client import TemporalClientManager

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)


def generate_unique_conversation_id(prefix: str = "conversation_") -> str:
    """
    Generates a unique conversation ID using a UUID without dashes and a timestamp.
    :param prefix: (str) Optional prefix for the conversation ID.
    :return: (str) A unique conversation ID.
    """
    unique_id = uuid.uuid4().hex  # Generate UUID and remove dashes
    timestamp = int(time.time())  # Get current timestamp
    conversation_id = f"{prefix}{unique_id}_{timestamp}"
    return conversation_id


async def process_query_with_granular_workflows(
    user_id: str,
    query: str,
    conversation_id: str,
    previous_messages: list,
    image_path: str = None,
    current_progress_callback=None,
    tools: list = None,
) -> dict:
    """
    Process a user query using the granular workflows via Temporal.
    """
    try:
        # Get the Temporal client instance
        temporal_client = await TemporalClientManager.get_instance()

        # Create a workflow ID prefix for this conversation
        workflow_id_prefix = f"maap-{conversation_id}-{uuid.uuid4().hex}"
        task_queue = "maap-task-queue"
        query = f"Using hybrid_search to find relevant context, answer my query:{query}"

        # Prepare messages to build up during processing
        messages = previous_messages.copy() if previous_messages else []

        # Define a simple function to show progress if callback is provided
        def update_progress(message):
            if current_progress_callback:
                current_progress_callback(message)

        # Step 1: Process image if provided
        image_result = None
        if image_path:
            update_progress("Processing image...")

            image_params = ImageProcessingParams(image_path=image_path)
            image_result = await temporal_client.execute_workflow(
                "ImageProcessingWorkflow",
                image_params,
                id=f"{workflow_id_prefix}-image",
                task_queue=task_queue,
            )

            # Add user message with image
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"text": query},
                        {
                            "image": {
                                "format": image_result.image_format,
                                "source": {
                                    "bytes": (
                                        bytes(image_result.image_bytes)
                                        if isinstance(image_result.image_bytes, list)
                                        else image_result.image_bytes
                                    )
                                },
                            }
                        },
                    ],
                }
            )
        else:
            # Add user message without image
            messages.append(
                {
                    "role": "user",
                    "content": [{"text": query}],
                }
            )
        if "Use Semantic Cache" in tools:
            # Step 2: Check semantic cache
            update_progress("Checking previous similar queries...")

            cache_params = SemanticCacheParams(user_id=user_id, query=query)
            cache_result = await temporal_client.execute_workflow(
                "SemanticCacheCheckWorkflow",
                cache_params,
                id=f"{workflow_id_prefix}-cache",
                task_queue=task_queue,
            )

            # If cache hit, return immediately
            if cache_result.get("cache_hit", False):
                cached_response = cache_result["response"]
                messages.append(
                    {
                        "role": "assistant",
                        "content": [{"text": cached_response}],
                    }
                )

                return {
                    "response": cached_response,
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "source": "cache",
                }

        if "Use AI Augmented Memory" in tools:
            # Step 3: Retrieve relevant memories
            update_progress("Retrieving relevant context...")

            memory_params = MemoryRetrievalParams(user_id=user_id, query=query)
            memories = await temporal_client.execute_workflow(
                "MemoryRetrievalWorkflow",
                memory_params,
                id=f"{workflow_id_prefix}-memory",
                task_queue=task_queue,
            )
            print(f"Retrieved memories: {memories}")

            # Step 4: Get AI Prompt
            update_progress("Preparing conversation context...")

            prompt_params = PromptRetrievalParams(
                user_id=user_id,
                conversation_summary=str(memories.get("conversation_summary", "")),
                similar_memories=str(memories.get("similar_memories", "")),
            )
            prompt = await temporal_client.execute_workflow(
                "PromptRetrievalWorkflow",
                prompt_params,
                id=f"{workflow_id_prefix}-prompt",
                task_queue=task_queue,
            )
            # Add memory context to messages
            messages.append(prompt)
        else:
            # Step 4: Get AI Prompt
            update_progress("Preparing conversation context...")

            prompt_params = PromptRetrievalParams(
                user_id=user_id,
                conversation_summary="",
                similar_memories="",
            )
            prompt = await temporal_client.execute_workflow(
                "PromptRetrievalWorkflow",
                prompt_params,
                id=f"{workflow_id_prefix}-prompt",
                task_queue=task_queue,
            )
            # Add memory context to messages
            messages.append(prompt)

        # Step 5: Generate AI response
        update_progress("Generating response...")

        ai_params = AIGenerationParams(messages=messages)
        response_text = await temporal_client.execute_workflow(
            "AIGenerationWorkflow",
            ai_params,
            id=f"{workflow_id_prefix}-ai",
            task_queue=task_queue,
        )
        print(f"AI response: {response_text}")

        # Only store if we have a valid response
        if (
            response_text
            and response_text.get("result")
            and str(response_text.get("result")).strip() != ""
        ):
            update_progress(response_text.get("result"))
            if "Use AI Augmented Memory" in tools:
                # Step 6: Store conversation in memory
                update_progress("Saving conversation...")

                memory_storage_params = MemoryStorageParams(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_query=query,
                    ai_response=response_text.get("result"),
                )
                await temporal_client.execute_workflow(
                    "MemoryStorageWorkflow",
                    memory_storage_params,
                    id=f"{workflow_id_prefix}-storage",
                    task_queue=task_queue,
                )
            if "Use Semantic Cache" in tools:
                # Step 7: Cache the response
                cache_storage_params = CacheStorageParams(
                    user_id=user_id, query=query, response=response_text.get("result")
                )
                await temporal_client.execute_workflow(
                    "CacheStorageWorkflow",
                    cache_storage_params,
                    id=f"{workflow_id_prefix}-cache-storage",
                    task_queue=task_queue,
                )

        # Add assistant response to messages
        messages.append(
            {
                "role": "assistant",
                "content": [{"text": response_text.get("result", "")}],
            }
        )

        return {
            "response": response_text.get("result", ""),
            "conversation_id": conversation_id,
            "messages": messages,
            "source": "llm",
        }
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error processing query: {str(e)}\n{error_details}")
        raise


async def process_request(message, history, user_id, conversation_id, tools):
    try:
        await logger.aprint(
            f"User details - user_id: {user_id}, conversation_id: {conversation_id}, selected tools: {tools}"
        )
        await logger.aprint(f"Message content: {message}, History: {history}")

        if message and len(message) > 0:
            query = message["text"].strip()
            urls = extract_urls(query)
            await logger.aprint(urls)
            num_files = len(message["files"])
            strTempResponse = ""

            # Handle file uploads and URL ingestion
            if num_files > 0 or len(urls) > 0:
                image_path = None
                for file in message["files"]:
                    file_name, file_ext = os.path.splitext(file)
                    image_file_types = [".jpg", ".jpeg", ".png"]
                    if file_ext in image_file_types:
                        # Save the first image path for the temporal workflow
                        if not image_path:
                            image_path = file

                strTempResponse = ""
                for i in re.split(
                    r"(\s)",
                    "Initiating upload and content vectorization. \nPlease wait....",
                ):
                    strTempResponse += i
                    await asyncio.sleep(0.025)
                    yield strTempResponse

                try:
                    files = message["files"]

                    # Create workflow ID
                    workflow_id = f"maap-{conversation_id}-{uuid.uuid4().hex}-ingest"

                    # Prepare the workflow parameters
                    params = DataIngestionParams(
                        user_id=user_id,
                        mongodb_uri=MONGODB_URI,
                        urls=urls if urls else None,
                        files=files if files else None,
                        mongodb_database=DB_NAME,
                        mongodb_collection=COLLECTION_NAME,
                        mongodb_index_name=VECTOR_SEARCH_INDEX_NAME,
                        mongodb_text_field=FULLTEXT_SEARCH_FIELD,
                        mongodb_embedding_field=VECTOR_SEARCH_FIELD,
                    )
                    # Get the Temporal client instance
                    temporal_client = await TemporalClientManager.get_instance()
                    # Execute the data ingestion workflow
                    result = await temporal_client.execute_workflow(
                        "DataIngestionWorkflow",
                        params,
                        id=workflow_id,
                        task_queue="maap-task-queue",
                    )
                    logger.print(f"Data ingestion result: {result}")
                    uploadResultDetails = result.get("details")
                    uploadResult = json.loads(uploadResultDetails)["success"]
                except Exception as e:
                    logger.error(f"Error in data ingestion: {str(e)}")
                    uploadResult = False
                if uploadResult:
                    for i in re.split(
                        r"(\s)",
                        "\nFile(s)/URL(s) uploaded and ingested successfully. \nGiving time for Indexes to Update....",
                    ):
                        strTempResponse += i
                        await asyncio.sleep(0.025)
                        yield strTempResponse
                    await asyncio.sleep(5)
                else:
                    for i in re.split(
                        r"(\s)", "\nFile(s)/URL(s) upload exited with error...."
                    ):
                        strTempResponse += i
                        await asyncio.sleep(0.025)
                        yield strTempResponse
            else:
                image_path = None

            # Process the query using Temporal
            if len(query) > 0:
                # Format previous messages for Temporal workflow
                previous_messages = []
                # print(history)
                for message in history:
                    if (
                        message["role"] == "user"
                        and len(str(message["content"]).strip()) == 0
                    ):
                        formatted_message = {
                            "role": message["role"],
                            "content": [{"text": "Hi"}],
                        }
                    formatted_message = {
                        "role": message["role"],
                        "content": [{"text": str(message["content"])}],
                    }

                    previous_messages.append(formatted_message)

                # Start with any partial response from file uploads
                response_text = strTempResponse if strTempResponse else ""

                # Stream partial results
                async def stream_progress():
                    nonlocal response_text
                    yield response_text

                # Create a simple queue for progress updates
                progress_queue = asyncio.Queue()

                # Define a progress callback that adds to the queue
                def progress_callback(message):
                    progress_queue.put_nowait(message)

                # Start the workflow processing in a background task
                process_task = asyncio.create_task(
                    process_query_with_granular_workflows(
                        user_id=user_id,
                        query=query,
                        conversation_id=conversation_id,
                        previous_messages=previous_messages,
                        image_path=image_path,
                        current_progress_callback=progress_callback,
                        tools=tools,
                    )
                )

                # Stream progress updates to the user while waiting for the result
                try:
                    # Stream initial response
                    yield response_text

                    # Keep checking for new progress updates until workflow completes
                    while not process_task.done():
                        try:
                            # Wait for a progress update with timeout
                            progress_msg = await asyncio.wait_for(
                                progress_queue.get(), 0.5
                            )
                            response_text += f"\n{progress_msg}"
                            yield response_text
                        except asyncio.TimeoutError:
                            # No update yet, keep waiting
                            await asyncio.sleep(0.1)

                    # Get the final result
                    result = await process_task

                    # Return just the final LLM response
                    yield result["response"]

                except Exception as e:
                    error_details = traceback.format_exc()
                    error_msg = f"Error processing query: {str(e)}\n{error_details}"
                    await logger.aerror(error_msg)
                    yield response_text + f"\n\nError: {error_msg}"
            else:
                yield "Hi, how may I help you?"
        else:
            yield "Hi, how may I help you?"
    except Exception as error:
        exc = traceback.TracebackException.from_exception(error)
        emsg = "".join(exc.format())  # Includes stack + error message
        await logger.aerror(emsg)
        yield "There was an error.\n" + emsg


def extract_urls(string):
    regex = (
        r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»"
        "'']))"
    )
    url = re.findall(regex, string)
    return [x[0] for x in url]


def print_like_dislike(x: gr.LikeData):
    logger.print(x.index, x.value, x.liked)
    return


head = """
<link rel="shortcut icon" href="https://ok5static.oktacdn.com/bc/image/fileStoreRecord?id=fs0jq9i9e0E4EFpjn297" type="image/x-icon">
"""
mdblogo_svg = "https://ok5static.oktacdn.com/fs/bco/1/fs0jq9i9coLeryBSy297"
temporallogo_svg = "https://docs.temporal.io/img/assets/temporal-logo-dark.svg"
custom_css = """
           
            .message-row img {
                margin: 0px !important;
            }

            .avatar-container img {
            padding: 0px !important;
            }

            footer {visibility: hidden}; 
        """

with gr.Blocks(
    head=head,
    fill_height=True,
    fill_width=True,
    css=custom_css,
    title="MongoDB AI Applications Program (MAAP)",
    theme=gr.themes.Soft(primary_hue=gr.themes.colors.green),
) as demo:
    with gr.Row():
        m(
            f"""
<center>
    <div style="display: flex; justify-content: center; align-items: center;">
        <a href="https://www.mongodb.com/">
            <img src="{mdblogo_svg}" width="250px" style="margin-right: 20px"/>
        </a>
    <img src="{PLUS_IMAGE}" width="30px" style="margin-right: 20px;margin-left: 5px;margin-top: 10px;"/>
        <a href="https://temporal.io/">
            <img src="{temporallogo_svg}" width="250px"/>
        </a>
    </div>
    <h1>MongoDB AI Applications Program (<a href="https://www.mongodb.com/services/consulting/ai-applications-program">MAAP</a>)</h1>
    <h3>An integrated end-to-end technology stack in the form of MAAP Framework.</h3>
</center>
"""
        )
    with gr.Accordion(
        label="--- Inputs ---", open=True, render=True
    ) as AdditionalInputs:
        m(
            """<p>
    Enter a User ID to store and retrieve user-specific file data from MongoDB. 
    Upload files via the Attach (clip) button or submit URLs to extract and store information in the MongoDB Atlas Vector Database, enabling contextually relevant searches.
    Receive precise query responses from the AI Agent System, powered by Anthropic's Claude Sonnet 3.7 LLM, leveraging data retrieved from MongoDB.
        </p>
        """
        )

        txtuser_id = gr.Textbox(
            value="your.email@yourdomain.com", label="User Id", key="user_id"
        )

        txtConversationId = gr.Textbox(
            value="",
            label="Conversation Id (read-only)",
            key="ConversationId",
            info="Unique conversation ID for the current session. Changes on page refresh.",
            interactive=False,
        )
        demo.load(
            generate_unique_conversation_id, inputs=[], outputs=[txtConversationId]
        )

        chbkgTools = gr.CheckboxGroup(
            choices=["Use Semantic Cache", "Use AI Augmented Memory"],
            value=["Use Semantic Cache", "Use AI Augmented Memory"],
            label="Preprocessing Workflows",
            info="Which tools should the app use to extract relevant information to support the query?",
            key="tools",
        )
    txtChatInput = gr.MultimodalTextbox(
        interactive=True,
        file_count="multiple",
        placeholder="Type your query and/or upload file(s) and interact with it...",
        label="User Query",
        show_label=True,
        render=False,
    )

    examples = [
        [
            "Recommend places to visit in India.",
            "your.email@yourdomain.com",
            ["Use Semantic Cache"],
        ],
        [
            "Explain https://www.mongodb.com/services/consulting/ai-applications-program",
            "your.email@yourdomain.com",
            ["Use Semantic Cache"],
        ],
        [
            "How can I improve my leadership skills?",
            "your.email@yourdomain.com",
            ["Use Semantic Cache"],
        ],
        [
            "What are the best practices for creating a scalable AI architecture?",
            "your.email@yourdomain.com",
            ["Use Semantic Cache"],
        ],
        [
            "Explain how I can manage my team better while solving technical challenges.",
            "your.email@yourdomain.com",
            ["Use Semantic Cache"],
        ],
    ]
    bot = gr.Chatbot(
        elem_id="chatbot",
        type="messages",
        autoscroll=True,
        avatar_images=[
            "https://ca.slack-edge.com/E01C4Q4H3CL-U04D0GXU2B1-g1a101208f57-192",
            "https://avatars.slack-edge.com/2021-11-01/2659084361479_b7c132367d18b6b7ffa0_512.png",
        ],
        show_copy_button=True,
        render=False,
        min_height="550px",
        label="Type your query and/or upload file(s) and interact with it...",
    )
    bot.like(print_like_dislike, None, None, like_user_message=False)

    CI = gr.ChatInterface(
        fn=process_request,
        chatbot=bot,
        type="messages",
        title="",
        description="Interact with a AI agent system to get responses tailored to your query.",
        multimodal=True,
        additional_inputs=[txtuser_id, txtConversationId, chbkgTools],
        additional_inputs_accordion=AdditionalInputs,
        textbox=txtChatInput,
        fill_height=True,
        show_progress=False,
        concurrency_limit=None,
    )

    gr.Examples(
        examples,
        inputs=[txtChatInput, txtuser_id, chbkgTools],
        examples_per_page=3,
    )

    with gr.Row():
        m(
            """
            <center><a href="https://www.mongodb.com/">MongoDB</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            <a href="https://temporal.io/">Temporal</a>
            </center>
       """
        )


if __name__ == "__main__":
    app = gr.mount_gradio_app(
        app, demo, path="", server_name="0.0.0.0", server_port=7860
    )
    uvicorn.run(app, host="0.0.0.0", port=7860, reload=DEBUG)
