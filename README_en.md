# NextChatReadFile

[中文](README.md) · English

## Introduction

### Implementation approach

We aim to build an AI chat platform similar to ChatGPT. After searching open-source projects on GitHub, I found a project called [NextChat](https://github.com/ChatGPTNextWeb/NextChat). It provides a complete front-end and back-end solution and supports multiple deployment methods.

NextChat supports plugins; see the [NextChat-Awesome-Plugins](https://github.com/ChatGPTNextWeb/NextChat-Awesome-Plugins) repository for details. In short, a plugin is essentially an OpenAPI request template. When you enable a plugin and instruct the LLM to perform a specific task, the LLM calls the appropriate plugin and forwards the request to it, then incorporates the response into the LLM’s context to achieve more complex functionality.

Unfortunately, the [ChatPDF](https://github.com/ChatGPTNextWeb/NextChat-Awesome-Plugins/tree/main/plugins/chatpdf) plugin that NextChat originally used for reading PDFs has stopped working—apparently the provider, [AI Document Maker](https://gpt.chatpdf.aidocmaker.com/), ended support. However, this plugin is popular and useful, so I implemented a replacement myself, which led to this project.

This plugin supports reading files in DOCX, PPTX, XLS, XLSX, and PDF formats from links. The `readfile.json` file is the plugin’s OpenAPI template. You can paste it into the [Swagger Editor](https://editor.swagger.io/) to understand its details. When the LLM detects that a request involves reading a file and contains a file URL, it sends a POST request to `http://nextchat-readfile:8000/read_file`, with the file URL set as the value of `http_url` in the request body. Once the server returns the file contents, the LLM includes them in its context, enabling access to and processing of the file content.

The request address here is a Docker container name, which is equivalent to an internal network address; we’ll explain this in detail later.

### Prerequisites

You need a server with Ubuntu preinstalled (22.04 or above is recommended), with Docker and Docker Compose installed. I use Docker Compose on the server to deploy all services, which makes it easy to manage multiple services and to scale and maintain them. After writing the configuration file, you only need to run the following command to (re)start all services:

```bash
sudo docker compose up -d
```

I don’t recommend using `apt`’s `docker.io` and `docker-compose`; instead, follow Docker’s official installation guide (using [Ubuntu](https://docs.docker.com/engine/install/ubuntu/) as an example).

When using Docker in mainland China, you may need to configure a domestic mirror accelerator to improve download speeds. You can refer to Alibaba Cloud’s [Docker image accelerator](https://help.aliyun.com/zh/acr/user-guide/accelerate-the-pulls-of-docker-official-images) for configuration.

## Build your own plugin server

### Implement the basic functionality

Since a NextChat plugin essentially sends requests defined by an OpenAPI template to a plugin service, all we need is to implement such an endpoint on our own server. I chose Python + FastAPI to build this plugin server.

The approach is straightforward. For each `http_url` received, we use `aiohttp` to download the file and temporarily store it in a `temp` folder. Then we parse the file’s contents and try to convert them to text using Microsoft’s [MarkItDown](https://github.com/microsoft/markitdown) library, which supports converting common formats such as DOCX, PPTX, XLS, XLSX, and PDF into Markdown text. Finally, we return the converted text to the LLM as the response.

Below are explanations for each file and key parts of the code:

- `log.py`: Logging module, responsible for recording the plugin server’s runtime logs.
- `model.py`: Defines data models and request/response formats.
- `main.py`: Entry point of the FastAPI application, defining the main API routes and logic.

Python 3.10 or above is recommended (for example, my server runs 3.10.12). Use `pip` to install the required dependencies:

```bash
pip install -r requirements.txt
```

For local debugging, use `uvicorn` to start the FastAPI app and run it on port 8000:

```bash
uvicorn main:app --reload --port 8000
```

You can then access your plugin server at `http://localhost:8000`. Send a request to `http://localhost:8000/read_file` to use the file-reading feature.

If you need to provide the service externally, set `uvicorn`’s `host` parameter to `0.0.0.0` so it listens on all IP addresses:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

I packaged this project as a Docker image and uploaded it to [Docker Hub](https://hub.docker.com/repository/docker/na2cucl4/nextchat-readfile/general); the image is `na2cucl4/nextchat-readfile:latest`. If you want to use this image, you can refer to the following Docker Compose configuration:

```yaml
services:
  nextchat-readfile:
    image: na2cucl4/nextchat-readfile:latest
    container_name: nextchat-readfile
    expose:
      - 8000
    restart: always
```

### Implement plugin communication

The Docker Compose configuration for NextChat is as follows:

```yaml
services:
  nextchat:
    image: yidadaa/chatgpt-next-web:latest
    container_name: nextchat
    ports:
      - 127.0.0.1:3001:3000
    environment:
      AZURE_API_KEY: <azure-api-key>
      AZURE_URL: <azure-endpoint>
      AZURE_API_VERSION: 2024-12-01-preview
      CODE: <code>
      CUSTOM_MODELS: -all,+gpt-5@Azure,+gpt-5-mini@Azure,+gpt-5-nano@Azure,+gpt-5-chat@Azure,+gpt-4.1@Azure,+gpt-4.1-mini@Azure,+gpt-4.1-nano@Azure,+gpt-4o@Azure,+gpt-4o-mini@Azure,+o4-mini@Azure,+o3@Azure,+o3-mini@Azure,+o1@Azure,+o1-mini@Azure
      DEFAULT_MODEL: gpt-5-mini@Azure
      HIDE_USER_API_KEY: 1
      HIDE_BALANCE_QUERY: 1
    restart: always
```

We forward requests from `127.0.0.1:3001` to the NextChat service running on port 3000 inside the container, and then configure an Apache reverse proxy on the server to forward requests from `https://chat.mydomain.com` to `http://localhost:3001`. This allows external access to the NextChat service via a domain name.

As mentioned earlier, NextChat plugins communicate with the plugin server via HTTP. Specifically, requests to `https://chat.mydomain.com/api/proxy/<path>` are forwarded to `<base>/<path>`, where `<base>` is specified by the `X-Base-URL` request header. For example, the following two requests are functionally equivalent:

```bash
# On an external machine
curl -X POST https://chat.mydomain.com/api/proxy/read_file -H 'Content-Type: application/json' -H 'X-Base-URL: http://base.url' -d '{"data":"..."}'

# On the server where NextChat is deployed
curl -X POST http://base.url/read_file -H 'Content-Type: application/json' -d '{"data":"..."}'
```

To allow NextChat to access the plugin server we just set up, we need to place them on the same Docker network. To do this, define a custom network in the Docker Compose file (for example, `nextchat-network`) and connect both services to this network. See the `docker-compose.yml` in this directory for the final configuration.

Lastly, the `url` field in `readfile.json` is `http://nextchat-readfile:8000`, which is exactly the service name and port we assigned to the plugin server in Docker Compose.

### Appendix: Use Document Intelligence to improve conversion accuracy

Using Microsoft Azure Document Intelligence can improve conversion accuracy, but conversion speed decreases significantly (to about one quarter of the original). In practice, the accuracy gains are far from enough to offset the performance loss, so the following is provided for reference only.

```py
import os

from azure.core.credentials import AzureKeyCredential
from markitdown import MarkItDown
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview"
)
md = MarkItDown(
    docintel_endpoint=os.getenv("AZURE_DOCINTEL_ENDPOINT"),
    docintel_credential=AzureKeyCredential(os.getenv("AZURE_DOCINTEL_API_KEY")),
    llm_client=client,
    llm_model="gpt-4o"
)
result = md.convert("example.docx")
with open("example.md", "w") as f:
    f.write(result.text_content)
```
