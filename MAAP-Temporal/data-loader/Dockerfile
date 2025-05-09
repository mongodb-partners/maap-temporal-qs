FROM downloads.unstructured.io/unstructured-io/unstructured:latest

# Copy all application code
COPY ./main.py /code/
COPY ./config.py /code/
COPY ./database/ /code/database/
COPY ./models/ /code/models/
COPY ./services/ /code/services/
COPY ./utils/ /code/utils/
COPY ./requirements.txt /code/requirements.txt

USER root
# Set up working directory
WORKDIR /code

# Make sure directory permissions are correct
RUN chmod -R 755 /code

# Create directories with correct permissions
RUN mkdir -p uploaded_files && \
    chown -R notebook-user:notebook-user uploaded_files && \
    chmod 755 uploaded_files
USER notebook-user

RUN pip install --no-cache-dir -r requirements.txt

# Expose the API port
EXPOSE 8184

# Run the FastAPI application
ENTRYPOINT ["python3", "main.py"]