# NextChatReadFile

中文 · [English](README_en.md)

## 简介

### 实现思路

我们希望搭建一个类似 ChatGPT 的 AI 对话平台。在 GitHub 上搜索开源项目后，我找到了一个名为 [NextChat](https://github.com/ChatGPTNextWeb/NextChat) 的项目。该项目提供了一个完整的前端和后端解决方案，支持多种部署方式。

NextChat 是支持插件的，详情可参考 [NextChat-Awesome-Plugins](https://github.com/ChatGPTNextWeb/NextChat-Awesome-Plugins) 仓库。简而言之，插件本质上是个 OpenAPI 请求模板。当你启用插件并指定 LLM 去实现某个特殊任务时，LLM 会调用合适的插件并将请求转发给它，然后将响应加入到 LLM 的上下文中，从而实现更复杂的功能。

不幸的是，NextChat 原本用于读取 PDF 的 [ChatPDF](https://github.com/ChatGPTNextWeb/NextChat-Awesome-Plugins/tree/main/plugins/chatpdf) 插件失效了，似乎是插件提供商 [AI Document Maker](https://gpt.chatpdf.aidocmaker.com/) 停止了支持。然而，这个插件却又十分常用且实用，所以我自己动手实现了一个，于是有了本项目。

本插件支持读取链接中的 DOCX、PPTX、XLS、XLSX、PDF 等格式的文件，`readfile.json` 就是本插件的 OpenAPI 模板。你可以将其粘贴至 [Swagger Editor](https://editor.swagger.io/) 中了解其详细含义。当 LLM 检测到请求中包含读取文件的任务和文件 URL 链接时，其会向 `http://nextchat-readfile:8000/read_file` 发送 POST 请求，并将文件 URL 作为请求体中 `http_url` 的值。待服务器返回文件内容时，LLM 会将其纳入上下文中，从而实现对文件内容的访问和处理。

这里的请求地址是一个 Docker 容器名称，相当于内网地址，我们后面会详细介绍。

### 前期配置

你需要有一台预装了 Ubuntu（建议 22.04 及以上版本）的服务器，服务器上需要安装 Docker 和 Docker Compose。我在服务器上使用 Docker Compose 部署所有服务，其优点是可以方便地管理多个服务，并且能够轻松地进行扩展和维护。写好配置文件后，你只需要运行以下命令即可（重新）启动所有服务：

```bash
sudo docker compose up -d
```

我不建议你使用 `apt` 的 `docker.io` 和 `docker-compose`，而参考 Docker 官方的安装说明（以 [Ubuntu](https://docs.docker.com/engine/install/ubuntu/) 为例）。

在国内环境使用 Docker 时，你可能需要配置国内镜像加速器，以提高下载速度。可以参考阿里云的 [Docker 镜像加速器](https://help.aliyun.com/zh/acr/user-guide/accelerate-the-pulls-of-docker-official-images) 进行配置。

## 搭建自己的插件服务器

### 实现基本功能

由于 NextChat 插件本质上是向插件服务商发送 OpenAPI 模板定义的请求，所以我们只需要在自己的服务器上实现一个的接口即可。这里我选择 Python + FastAPI 来实现这个插件服务器。

实现思路非常简单。对于收到的 `http_url`，我们需要用 `aiohttp` 下载文件内容，并将其暂时存在 `temp` 文件夹中。然后，我们需要解析此文件的内容，并尝试将其转换为文字，这里我们使用微软公司开发的 [MarkItDown](https://github.com/microsoft/markitdown) 库来实现，它支持将应用中常见的 DOCX、PPTX、XLS、XLSX、PDF 等格式转换为 Markdown 格式的文本。最后，我们将转换后的文本作为响应返回给 LLM。

以下是对各个文件和关键代码的说明：

- `log.py`：日志记录模块，负责记录插件服务器的运行日志。
- `model.py`：定义数据模型和请求/响应格式。
- `main.py`：FastAPI 应用程序的入口点，定义了主要的 API 路由和逻辑。

建议使用 3.10 及以上版本的 Python（例如我的服务器是 3.10.12），使用 `pip` 安装必要的依赖：

```bash
pip install -r requirements.txt
```

在本地调试时，使用 `uvicorn` 启动 FastAPI 应用，并将其运行在 8000 端口上：

```bash
uvicorn main:app --reload --port 8000
```

这样你就能在 `http://localhost:8000` 访问你的插件服务器了。向 `http://localhost:8000/read_file` 发送请求，即可实现文件读取功能。

如果你需要向外界提供服务，你需要将 `uvicorn` 的 `host` 参数设置为 `0.0.0.0`，使其可以监听所有 IP 地址：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

我将这个项目打包为 Docker 镜像，并上传到了 [Docker Hub](https://hub.docker.com/repository/docker/na2cucl4/nextchat-readfile/general) 上，镜像地址为 `na2cucl4/nextchat-readfile:latest`。如果你要使用这个镜像，可以参考下面的 Docker Compose 配置文件：

```yaml
services:
  nextchat-readfile:
    image: na2cucl4/nextchat-readfile:latest
    container_name: nextchat-readfile
    expose:
      - 8000
    restart: always
```

### 实现插件通信

NextChat 的 Docker Compose 配置文件的内容如下：

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

我们将 `127.0.0.1:3001` 的请求转发到容器内部 3000 端口运行的 NextChat 服务，随后在服务器上配置了 Apache 反向代理，将 `https://chat.mydomain.com` 的请求转发到 `http://localhost:3001`。这样，外界就可以通过域名访问 NextChat 服务。

如前文所述，NextChat 的插件通过 HTTP 请求与插件服务器进行通信，具体操作是：将 `https://chat.mydomain.com/api/proxy/<path>` 的请求转发到 `<base>/<path>` 处，其中 `<base>` 由请求头的 `X-Base-URL` 指定。例如以下两个请求在功能上是等价的：

```bash
# 在外界电脑上
curl -X POST https://chat.mydomain.com/api/proxy/read_file -H 'Content-Type: application/json' -H 'X-Base-URL: http://base.url' -d '{"data":"..."}'

# 在部署了 NextChat 的服务器上
curl -X POST http://base.url/read_file -H 'Content-Type: application/json' -d '{"data":"..."}'
```

为了让 NextChat 能够访问我们刚才搭建的插件服务器，我们需要让它们处于同一个 Docker 网络中。为此，我们可以在 Docker Compose 文件中定义一个自定义网络，例如 `nextchat-network`，并将两个服务都连接到这个网络上。最终的 Docker Compose 文件参见目录中的 `docker-compose.yml`。

最后，我们前面提到 `readfile.json` 中的 `url` 字段就是 `http://nextchat-readfile:8000`，这正是我们在 Docker Compose 中为插件服务器指定的服务名称和端口。

### 附录：使用文档智能提升转换准确度

使用微软 Azure 上的文档智能（Document Intelligence）可以提升文件转换的准确度，但转换速度会显著下降（约为原来的 1/4)。经过实际检验，提升的准确度远不足以弥补性能损失，故在此仅提供实现参考。

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
