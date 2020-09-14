# Image Manager

[![License badge](https://img.shields.io/badge/license-GPL-blue.svg)](https://opensource.org/licenses/GPL-3.0)
[![Docker badge](https://img.shields.io/docker/pulls/dojot/iotagent-json.svg)](https://hub.docker.com/r/dojot/image-manager/)

The Image Manager handles all CRUD operations related to dojot's firmware images.

# Usage

These instructions are meant for development only.
They should be run on the repository root and will execute the following:

1. Run the necessary environment (PostgreSQL and Minio) using Docker Compose
2. Build an image based on the current repository
3. Run the application inside Docker Compose network
4. Run the test application

**Obs.:** Using the option  ```-v $PWD:/usr/src/app local/imagemanager``` will link the docker image
application with the local development code; any changes in the code will update the application
immediately using Flask's hot swap mechanism.

On terminal #1:
```shell
docker-compose -f local/compose.yml -p imgm up -d
docker build -f Dockerfile -t local/imagemanager .
docker run --rm -it --network imgm_default -p 8000:5000 --network-alias image-manager -v $PWD:/usr/src/app local/imagemanager
```

On terminal #2:
```shell
cd tests/
python3 client.py
```
