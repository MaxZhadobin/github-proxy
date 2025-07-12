# GitHub Proxy

This repository contains a minimal FastAPI server that proxies requests to GitHub for reading files. It is intended for usage with GPTs Actions and requires a bearer token for authorization.

## Features

- `GET /read_file` – read a file from a GitHub repository via the GitHub API.
- Bearer token authentication.
- Minimal OpenAPI schema available at `/openapi.json`.

## Usage

1. Create a `.env` file based on `.env.example` and provide values for `API_BEARER_TOKEN` and `GITHUB_TOKEN`.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:

   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

See the documentation in the OpenAPI schema for request details.
