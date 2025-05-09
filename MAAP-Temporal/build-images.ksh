#!/bin/ksh

docker network inspect temporal-network >/dev/null 2>&1 || docker network create temporal-network

rm -rf docker-compose && git clone https://github.com/temporalio/docker-compose.git
cd  docker-compose
echo -e "    external: true" >> "docker-compose.yml"
docker-compose up -d

cd ../event-logger 
docker build  --tag 'event-logger' .

cd ../data-loader 
docker build  --tag 'data-loader' .

cd ../ai-memory 
docker build  --tag 'ai-memory' .

cd ../semantic-cache
docker build  --tag 'semantic-cache' .

cd ../host
docker build  --tag 'host' .