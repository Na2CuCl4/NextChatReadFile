import os
import time

import aiohttp
from fastapi import FastAPI, Request, File, UploadFile
from markitdown import MarkItDown

from log import log
from model import BaseResponse, FilePayload

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

app = FastAPI()  # FastAPI 实例
md = MarkItDown()  # MarkItDown 转换器


@app.post("/read_file")
async def read_file(request: Request, file: UploadFile = File(...)):
    # 生成文件名（使用时间戳）
    timestamp = str(time.time())
    file_path = os.path.join(TEMP_DIR, f"{timestamp}")

    # 保存上传的文件到临时目录
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 转换文件为 Markdown
    try:
        # 使用 MarkItDown 转换文件
        result = md.convert(file_path)
        text_content = result.text_content
    except Exception as e:
        # 删除临时文件
        os.remove(file_path)
        log(500, f"File conversion failed: {e}", request.client.host)
        return BaseResponse(code=-4, msg="File conversion failed.", status_code=500)

    # 删除临时文件
    os.remove(file_path)

    # 返回结果
    log(200, "File converted successfully", request.client.host)
    return BaseResponse(msg="File converted successfully", data=text_content)


@app.post("/read_url")
async def read_url(request: Request, payload: FilePayload):
    # 检查 url 是否存在
    if not payload.url:
        log(400, "url is not provided", request.client.host)
        return BaseResponse(code=-1, msg="url is not provided.", status_code=400)
    url = payload.url

    # 生成文件名（使用时间戳）
    timestamp = str(time.time())
    file_path = os.path.join(TEMP_DIR, f"{timestamp}")

    # 下载文件
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    log(404, f"File download from {url} failed with status {response.status}", request.client.host)
                    return BaseResponse(code=1, msg="File download failed.", status_code=404)
                with open(file_path, "wb") as f:
                    f.write(await response.read())
    except Exception as e:
        log(404, f"File downloaded from {url} failed: {e}", request.client.host)
        return BaseResponse(code=1, msg="File download failed.", status_code=404)

    # 转换文件为 Markdown
    try:
        # 使用 MarkItDown 转换文件
        result = md.convert(file_path)
        text_content = result.text_content
    except Exception as e:
        # 删除临时文件
        os.remove(file_path)
        log(500, f"File converted from {url} failed: {e}", request.client.host)
        return BaseResponse(code=-4, msg="File conversion failed.", status_code=500)

    # 删除临时文件
    os.remove(file_path)

    # 返回结果
    log(200, f"File converted from {url} successfully", request.client.host)
    return BaseResponse(msg="File converted successfully", data=text_content)
