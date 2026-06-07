import os
import threading
import time

import aiohttp
from azure.core.credentials import AzureKeyCredential
from fastapi import FastAPI, Request, File, Form, UploadFile
from markitdown import MarkItDown
from openai import OpenAI

from log import log
from model import BaseResponse, FilePayload

VERSION = "1.2.0"
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

app = FastAPI()  # FastAPI 实例
md = MarkItDown()  # MarkItDown 转换器

# 任务计数器及线程锁
_counters_lock = threading.Lock()
_counters = {
    "processing_tasks": 0,
    "completed_tasks": 0,
    "failed_tasks": 0,
}


def _increment_processing():
    with _counters_lock:
        _counters["processing_tasks"] += 1


def _mark_completed():
    with _counters_lock:
        _counters["processing_tasks"] -= 1
        _counters["completed_tasks"] += 1


def _mark_failed():
    with _counters_lock:
        _counters["processing_tasks"] -= 1
        _counters["failed_tasks"] += 1


def _get_counters_snapshot():
    with _counters_lock:
        return dict(_counters)


# 支持 Document Intelligence 的 MarkItDown 实例
client = OpenAI(
    api_key=os.getenv("BASE_URL"),
    base_url=os.getenv("OPENAI_API_KEY")
)
md_docintel = MarkItDown(
    docintel_endpoint=os.getenv("DOCINTEL_ENDPOINT"),
    docintel_credential=AzureKeyCredential(os.getenv("DOCINTEL_API_KEY")),
    llm_client=client,
    llm_model=os.getenv("DOCINTEL_MODEL")
)


@app.get("/")
async def health():
    counters = _get_counters_snapshot()
    return BaseResponse(
        msg="healthy",
        data={
            "version": VERSION,
            "processing_tasks": counters["processing_tasks"],
            "completed_tasks": counters["completed_tasks"],
            "failed_tasks": counters["failed_tasks"],
        }
    )


@app.post("/read_file")
async def read_file(request: Request, file: UploadFile = File(...), docintel: bool = Form(False)):
    _increment_processing()
    try:
        # 生成文件名（使用时间戳）
        timestamp = str(time.time())
        file_path = os.path.join(TEMP_DIR, f"{timestamp}")

        # 保存上传的文件到临时目录
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 使用 MarkItDown 转换文件
        if docintel:
            result = md_docintel.convert(file_path)
        else:
            result = md.convert(file_path)
        text_content = result.text_content

        # 删除临时文件
        os.remove(file_path)

        # 返回结果
        log(200, "File converted successfully", request.client.host)
        _mark_completed()
        return BaseResponse(msg="File converted successfully", data=text_content)

    except Exception as e:
        # 删除临时文件
        if os.path.exists(file_path):
            os.remove(file_path)

        log(500, f"File conversion failed: {e}", request.client.host)
        _mark_failed()
        return BaseResponse(code=-4, msg=f"File conversion failed: {e}", status_code=500)


@app.post("/read_url")
async def read_url(request: Request, payload: FilePayload):
    _increment_processing()
    try:
        # 检查 url 是否存在
        if not payload.url:
            log(400, "url is not provided", request.client.host)
            _mark_failed()
            return BaseResponse(code=-1, msg="url is not provided.", status_code=400)
        url = payload.url

        # 生成文件名（使用时间戳）
        timestamp = str(time.time())
        file_path = os.path.join(TEMP_DIR, f"{timestamp}")

        # 下载文件
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    log(404,
                        f"File download from {url} failed with status {response.status}", request.client.host)
                    _mark_failed()
                    return BaseResponse(code=1, msg=f"File download from {url} failed with status {response.status}", status_code=404)
                with open(file_path, "wb") as f:
                    f.write(await response.read())

        # 使用 MarkItDown 转换文件
        if payload.docintel:
            result = md_docintel.convert(file_path)
        else:
            result = md.convert(file_path)
        text_content = result.text_content

        # 删除临时文件
        os.remove(file_path)

        # 返回结果
        log(200,
            f"File converted from {url} successfully", request.client.host)
        _mark_completed()
        return BaseResponse(msg="File converted successfully", data=text_content)

    except Exception as e:
        # 删除临时文件
        if os.path.exists(file_path):
            os.remove(file_path)

        log(500, f"File conversion failed: {e}", request.client.host)
        _mark_failed()
        return BaseResponse(code=-4, msg=f"File conversion failed: {e}", status_code=500)
