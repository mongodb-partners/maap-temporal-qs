FROM python:3.10-slim

COPY ./requirements.txt /code/requirements.txt
COPY ./maap_mcp/ /code/maap_mcp/
COPY ./activities.py /code/activities.py
COPY ./mcp_servers.json  /code/mcp_servers.json 
COPY ./models.py  /code/models.py 
COPY ./temporal_client.py  /code/temporal_client.py 
COPY ./temporal_worker.py  /code/temporal_worker.py 
COPY ./ui_app.py  /code/ui_app.py 
COPY ./workflows.py /code/workflows.py
COPY ./start.sh /code/start.sh

# Set up working directory
WORKDIR /code

RUN chmod +x ./start.sh

# Install dependencies as root
RUN pip install -r requirements.txt

# Expose the FastAPI default port
EXPOSE 7860
# Expose the Temporal default port
EXPOSE 7233
# Expose the Temporal Web UI port   
EXPOSE 8080

# Run the application
ENTRYPOINT ["./start.sh"]