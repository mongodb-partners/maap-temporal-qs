FROM python:3.10-slim

COPY ./requirements.txt /code/requirements.txt
COPY ./main.py /code/main.py
COPY ./models/ /code/models/
COPY ./config.py /code/

# Set up working directory
WORKDIR /code

RUN pip install -r requirements.txt

EXPOSE 8181
ENTRYPOINT [ "python3", "main.py" ]