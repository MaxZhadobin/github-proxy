# GitHub Proxy

This repository contains a minimal FastAPI server that proxies requests to GitHub for reading files. It is intended for usage with GPTs Actions and requires a bearer token for authorization.

## Features

- `GET /read_file` – read a file from a GitHub repository via the GitHub API.
- `GET /list_files` – recursively list files in a repository, returning separate `files` and `dirs` arrays.
- `GET /list_dirs` – recursively list directories in a repository.
- `GET /databases` – list configured databases.
- `GET /tables` – list tables in a database.
- `GET /logs` – read recent rows from any table.
- `GET /schema` – get column schema of a table.
- `POST /shell` – execute whitelisted shell commands for diagnostics.
- Bearer token authentication.
- Minimal OpenAPI schema available at `/openapi.json`.

## Usage

1. Create a `.env` file based on `.env.example` and provide values for `API_BEARER_TOKEN`, `GITHUB_TOKEN` and database DSNs.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
Databases are discovered from environment variables named `DB_<ALIAS>_URL`.
For example `DB_CORE_URL` will register a database with alias `core`.
See the documentation in the OpenAPI schema for request details.

### Example

Listing the contents of a directory:

```bash
curl -H "Authorization: Bearer <TOKEN>" "https://github-proxy-ycu5.onrender.com/list_files?repo=user/project&path=src"
```

Example response:

```json
{
  "files": [
    {"name": "main.py", "path": "src/main.py", "type": "file"}
  ],
  "dirs": [
    {"name": "utils", "path": "src/utils", "type": "dir"}
  ]
}
```

### List only directories

Parameters:

- `repo` – repository in `owner/name` format.
- `path` – starting path inside the repository (default `.`).
- `branch` – branch name to inspect (default `main`).

Example request:

```bash
curl -H "Authorization: Bearer <TOKEN>" "https://github-proxy-ycu5.onrender.com/list_dirs?repo=user/project&path=src"
```

Example response:

```json
{
  "dirs": [
    {"name": "utils", "path": "src/utils", "type": "dir"}
  ]
}
```
