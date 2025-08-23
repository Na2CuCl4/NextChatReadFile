# NextChatReadFile

## 简介

### 实现思路

我们希望搭建一个类似 ChatGPT 的 AI 对话平台。在 GitHub 上搜索开源项目后，我找到了一个名为 [NextChat](https://github.com/ChatGPTNextWeb/NextChat) 的项目。该项目提供了一个完整的前端和后端解决方案，支持多种部署方式。

NextChat 是支持插件的，详情可参考 [NextChat-Awesome-Plugins](https://github.com/ChatGPTNextWeb/NextChat-Awesome-Plugins) 仓库。简而言之，插件本质上是个 OpenAPI 请求模板。当你启用插件并指定 LLM 去实现某个特殊任务时，LLM 会判断是否存在对应的插件，如果存在，则会调用该插件并将请求转发给它，然后将响应加入到 LLM 的上下文中，从而实现更复杂的功能。

`readfile.json` 就是本插件的 OpenAPI 模板。你可以将其粘贴至 [Swagger Editor](https://editor.swagger.io/) 中了解其详细含义。简而言之，当 LLM 检测到请求中包含读取文件的任务和文件 URL 连接时，其会向 `https://your-domain.com/api/proxy/read_file` 发送 POST 请求，并将文件 URL 作为请求体 `http_url` 的值。待服务器返回文件内容时，LLM 会将其纳入上下文中，从而实现对文件内容的访问和处理。

你可能发现了请求地址正是你的域名，没错！我们后面会介绍如何制作你自己的插件服务器。因为 NextChat 原有的 ChatPDF 插件失效了，似乎插件提供商 [AI Document Maker](https://gpt.chatpdf.aidocmaker.com/) 停止了支持，这倒逼我自己动手实现一个。

当然，不要忘记将 `readfile.json` 中的 `url` 替换为你自己的域名。

### 前期配置

你需要有一台能连接公网、**有公网 IP**、预装了 Ubuntu（22.04 及以上版本）的服务器。如果你没有公网 IP（常见于家庭网络场景），你可以采用内网穿透，或者使用云服务器（如腾讯云等）。

同时，你需要有一个域名（记为 `your-domain.com`），并将其解析到你的服务器 IP 上。你可以使用 [Cloudflare](https://www.cloudflare.com/) 或 [腾讯云](https://cloud.tencent.com/) 等服务商来购买和管理域名。

## 搭建自己的插件服务器

### 实现基本功能

由于 NextChat 插件本质上是向插件服务商发送 OpenAPI 模板定义的请求，所以我们只需要在自己的服务器上实现一个的接口即可。这里我选择 Python + FastAPI 来实现这个插件服务器，亦即项目 [NextChatReadFile](https://github.com/Na2CuCl4/NextChatReadFile)。

实现思路非常简单。对于收到的 `http_url`，我们需要用 `aiohttp` 下载文件内容，并将其暂时存在 `temp` 文件夹中。然后，我们需要解析此文件的内容，并尝试将其转换为文字，这里我们使用微软公司开发的 [MarkItDown](https://github.com/microsoft/markitdown) 库来实现，它支持将应用中常见的 DOCX、PPTX、XLS、XLSX、PDF 等格式转换为 Markdown 格式的文本。最后，我们将转换后的文本作为响应返回给 LLM。

以下是对各个文件和关键代码的说明：

- `config_template.json`：插件服务器的运行配置的模板文件。使用时请将其复制为 `config.json` 并根据需要进行修改。注意，将本地配置储存在本地而不同步到 Git 是一个好习惯，你可能发现了 `.gitignore` 文件中已经包含了 `config.json`。
  - `origins`：允许的跨域请求来源，通常包括你的前端应用的地址。
  - `max_requests`：限制每秒的最大请求数。
  - `temp_dir`：临时文件存储目录。
- `config.py`：加载运行配置文件 `config.json`。
- `log.py`：日志记录模块，负责记录插件服务器的运行日志。
- `model.py`：定义数据模型和请求/响应格式。
- `main.py`：FastAPI 应用程序的入口点，定义了主要的 API 路由和逻辑。

使用时建议使用 3.10 及以上版本的 Python（例如我的服务器是 3.10.12），使用 `pip install -r requirements.txt` 安装依赖，使用 `uvicorn` 启动 FastAPI 应用：

```bash
uvicorn main:app --reload --port 8000
```

这样你就能在 `http://localhost:8000` 访问你的插件服务器了。向 `http://localhost:8000/read_file` 发送请求，即可实现文件读取功能。

### 创建后台或守护进程

如果你直接在命令行中使用 `uvicorn` 启动，应用将在前台运行，命令行退出进程即结束。要将其作为后台进程运行，可以使用 `nohup` 命令：

```bash
nohup uvicorn main:app --port 8000 --reload &
```

这将在后台启动应用，并将输出重定向到 `nohup.out` 文件中。

另一种方法是创建守护进程，使用 `systemd` 来管理你的 FastAPI 应用。首先，创建一个 `service` 文件，例如 `/etc/systemd/system/fastapi.service`：

```ini
[Unit]
Description=FastAPI Application
After=network.target

[Service]
User=your-user
Group=your-group
WorkingDirectory=/path/to/your/app
ExecStart=/usr/local/bin/uvicorn main:app --port 8000 --reload
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

其中 `your-user` 和 `your-group` 是运行 FastAPI 应用的用户和用户组，`/path/to/your/app` 是你的 FastAPI 应用的工作目录，`/usr/local/bin/uvicorn` 是 `uvicorn` 的安装路径（可能因系统而异），需要根据实际情况进行调整。

然后，重新加载 `systemd`，并启动你的服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start fastapi
sudo systemctl enable fastapi
```

这样，你就可以将 FastAPI 应用作为守护进程运行，并在系统启动时自动启动。

### 使用反向代理

完成以上操作后，你的 FastAPI 应用并不能被外界访问。一种方法是在运行 `uvicorn` 时，指定参数 `--host 0.0.0.0` 使其可以监听所有 IP 地址。但是经过实际操作发现，NextChat 会将 `/api/proxy` 下的请求转发到请求头中定义的 `X-Base-URL`，而且这一操作不支持带 IP 地址和端口号的请求。为此，我们需要使用域名来访问应用，并通过反向代理将请求转发到 `http://localhost:8000/`。

我们可以使用 Apache2 作为反向代理，以下是一个简单的配置示例（支持 SSL）`readfile.conf`：

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    Redirect permanent / https://your-domain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName your-domain.com

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/your-cert.crt
    SSLCertificateKeyFile /etc/ssl/private/your-key.key

    RewriteEngine On
    RewriteCond %{REQUEST_URI} ^/api/proxy/(.*)$
    RewriteRule ^/api/proxy/(.*)$ http://localhost:8000/$1 [P,L]
    ProxyPassReverse / http://localhost:8000/

    ErrorLog ${APACHE_LOG_DIR}/your-domain-error.log
    CustomLog ${APACHE_LOG_DIR}/your-domain-access.log combined
</VirtualHost>
```

别忘了对你的域名、SSL 证书路径和其他相关配置进行相应的修改。完成后，重启 Apache2 服务以应用更改：

```bash
sudo a2ensite readfile
sudo systemctl restart apache2
```

这样，你就可以通过 `http://your-domain.com/api/proxy/` 访问你的 FastAPI 应用了。

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
