import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

app = FastAPI(
    title="Minimal GitHub Proxy API",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url=None,
    redoc_url=None,
)

security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if API_BEARER_TOKEN is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server token not configured")
    if credentials.credentials != API_BEARER_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


class FileContent(BaseModel):
    content: str


@app.get("/read_file", response_model=FileContent, dependencies=[Depends(verify_token)])
async def read_file(repo: str, path: str, branch: str = "main"):
    if GITHUB_TOKEN is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GitHub token not configured")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw",
        "User-Agent": "github-proxy",
    }
    params = {"ref": branch}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return FileContent(content=resp.text)
    elif resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    else:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
