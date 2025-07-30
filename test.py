import os

from azure.core.credentials import AzureKeyCredential
from markitdown import MarkItDown
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-01-preview"
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
