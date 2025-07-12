import os
import json
import re
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import asyncpg
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Database config loaded from db_config.json
DB_CONFIG_FILE = "db_config.json"
db_configs: list[dict[str, str]] = []
db_pools: dict[str, asyncpg.Pool] = {}

app = FastAPI(
    title="Minimal GitHub Proxy API",
    version="1.1.0",
    openapi_url="/openapi.json",
    docs_url=None,
    redoc_url=None,
    servers=[
        {
            "url": "https://github-proxy-ycu5.onrender.com",
            "description": "Render deployment"
        }
    ],
)

security = HTTPBearer()

@app.on_event("startup")
async def startup() -> None:
    """Initialize database connection pools from configuration."""
    global db_configs, db_pools
    if not os.path.exists(DB_CONFIG_FILE):
        return
    with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
        configs = json.load(f)
    for entry in configs:
        alias = entry.get("alias")
        env_name = entry.get("dsn_env")
        description = entry.get("description", "")
        if not alias or not env_name:
            continue
        dsn = os.getenv(env_name)
        if not dsn:
            continue
        pool = await asyncpg.create_pool(dsn=dsn)
        db_pools[alias] = pool
        db_configs.append({"alias": alias, "description": description})

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

class FileInfo(BaseModel):
    name: str
    path: str
    type: str

class FileList(BaseModel):
    files: list[FileInfo]


class DatabaseInfo(BaseModel):
    alias: str
    description: str


class DatabaseList(BaseModel):
    databases: list[DatabaseInfo]


class TableList(BaseModel):
    tables: list[str]


class LogList(BaseModel):
    logs: list[dict[str, Any]]

@app.get("/list_files", response_model=FileList, dependencies=[Depends(verify_token)])
async def list_files(repo: str, path: str = ".", branch: str = "main"):
    """Recursively list files and directories in a GitHub repository."""
    if GITHUB_TOKEN is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GitHub token not configured")
    if "/" not in repo:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid repo format. Use owner/repo")

    norm_path = path.strip("/")
    if norm_path == "" or norm_path == ".":
        norm_path = "."

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "github-proxy",
    }
    commit_url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    async with httpx.AsyncClient() as client:
        commit_resp = await client.get(commit_url, headers=headers)
    if commit_resp.status_code != 200:
        if commit_resp.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        raise HTTPException(status_code=commit_resp.status_code, detail=commit_resp.text)

    tree_sha = commit_resp.json()["commit"]["tree"]["sha"]

    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{tree_sha}?recursive=1"
    async with httpx.AsyncClient() as client:
        tree_resp = await client.get(tree_url, headers=headers)
    if tree_resp.status_code != 200:
        raise HTTPException(status_code=tree_resp.status_code, detail=tree_resp.text)

    tree_entries = tree_resp.json().get("tree", [])

    if norm_path != "." and not any(e["path"] == norm_path for e in tree_entries):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path not found")

    result = []
    for entry in tree_entries:
        epath = entry["path"]
        if norm_path != ".":
            if not epath.startswith(norm_path + "/") and epath != norm_path:
                continue
            if epath == norm_path and entry["type"] == "tree":
                continue
        result.append(FileInfo(name=epath.split("/")[-1], path=epath, type="dir" if entry["type"] == "tree" else "file"))

    return FileList(files=result)


@app.get("/databases", response_model=DatabaseList, dependencies=[Depends(verify_token)])
async def list_databases() -> DatabaseList:
    """Return available databases with their aliases and descriptions."""
    return DatabaseList(databases=[DatabaseInfo(**cfg) for cfg in db_configs])


@app.get("/tables", response_model=TableList, dependencies=[Depends(verify_token)])
async def list_tables(db: str) -> TableList:
    """List tables in a selected database."""
    pool = db_pools.get(db)
    if not pool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    rows = await pool.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"
    )
    return TableList(tables=[r["table_name"] for r in rows])


_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


@app.get("/logs", response_model=LogList, dependencies=[Depends(verify_token)])
async def read_logs(db: str, table: str, limit: int = 20) -> LogList:
    """Return last N rows from any table of a configured database."""
    pool = db_pools.get(db)
    if not pool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    if not _NAME_RE.fullmatch(table):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    limit = max(1, min(limit, 500))
    exists = await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=$1)",
        table,
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    cols = await pool.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=$1",
        table,
    )
    col_names = [c["column_name"] for c in cols]
    order_col = None
    for candidate in ("created_at", "timestamp", "ts", "id"):
        if candidate in col_names:
            order_col = candidate
            break
    if order_col:
        query = f'SELECT * FROM "{table}" ORDER BY "{order_col}" DESC LIMIT $1'
        rows = await pool.fetch(query, limit)
    else:
        query = f'SELECT * FROM "{table}" LIMIT $1'
        rows = await pool.fetch(query, limit)
    return LogList(logs=[dict(r) for r in rows])
