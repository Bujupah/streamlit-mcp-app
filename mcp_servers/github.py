import contextlib
import os
from typing import Any, Dict, Literal, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

GITHUB_API_BASE = os.environ.get("GITHUB_API_BASE", "https://api.github.com")
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=30.0, write=30.0)

app = FastAPI()


def _build_url(path: str) -> str:
    base = GITHUB_API_BASE.rstrip("/")
    return f"{base}{path if path.startswith('/') else '/' + path}"


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if value and scheme.lower() == "bearer":
        return value.strip()
    return authorization.strip()


def require_token(authorization: Optional[str] = Header(default=None)) -> str:
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="GitHub token required. Provide a Bearer token in the Authorization header.",
        )
    return token


async def github_request(
    method: str,
    path: str,
    *,
    token: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.request(
                method,
                _build_url(path),
                headers=headers,
                params=params,
                json=json_body,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail: Any = exc.response.text
            with contextlib.suppress(Exception):
                detail = exc.response.json()
            raise HTTPException(status_code=exc.response.status_code, detail=detail)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    with contextlib.suppress(ValueError):
        return response.json()
    return response.text


class GetAllPullRequestsArguments(BaseModel):
    owner: str
    repo: str
    state: Literal["open", "closed", "all"] = "open"
    per_page: int = Field(default=30, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class GetPullRequestArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int


class ListPullRequestFilesArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int


class ListPullRequestReviewsArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int
    per_page: int = Field(default=30, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class ListPullRequestCommentsArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int
    per_page: int = Field(default=30, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class ListPullRequestCommitsArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int
    per_page: int = Field(default=30, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class Comment(BaseModel):
    body: str
    path: str
    position: int = None
    line: int = None
    side: str = None
    start_line: int = None
    start_side: str = None


class CreatePullRequestReviewArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int
    body: str
    event: Literal["REQUEST_CHANGES", "APPROVE", "COMMENT"]
    comments: list[Comment] = Field(default_factory=list)


@app.get("/tools")
async def get_tools():
    return [
        {
            "name": "get_all_pull_requests",
            "description": "Gets all pull requests for a repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner."},
                    "repo": {"type": "string", "description": "Repository name."},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter pulls by state.",
                    },
                    "per_page": {
                        "type": "number",
                        "description": "Items per page (max 100).",
                    },
                    "page": {
                        "type": "number",
                        "description": "Page of results to fetch.",
                    },
                },
                "required": ["owner", "repo"],
            },
        },
        {
            "name": "get_pull_request",
            "description": "Gets a pull request for a repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pull_number": {"type": "number"},
                },
                "required": ["owner", "repo", "pull_number"],
            },
        },
        {
            "name": "list_pull_request_files",
            "description": "Lists all files for a pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pull_number": {"type": "number"},
                },
                "required": ["owner", "repo", "pull_number"],
            },
        },
        {
            "name": "list_pull_request_reviews",
            "description": "Lists all reviews on a pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pull_number": {"type": "number"},
                    "per_page": {"type": "number"},
                    "page": {"type": "number"},
                },
                "required": ["owner", "repo", "pull_number"],
            },
        },
        {
            "name": "list_pull_request_comments",
            "description": "Lists all review comments on a pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pull_number": {"type": "number"},
                    "per_page": {"type": "number"},
                    "page": {"type": "number"},
                },
                "required": ["owner", "repo", "pull_number"],
            },
        },
        {
            "name": "list_pull_request_commits",
            "description": "Lists commits that are part of a pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pull_number": {"type": "number"},
                    "per_page": {"type": "number"},
                    "page": {"type": "number"},
                },
                "required": ["owner", "repo", "pull_number"],
            },
        },
        {
            "name": "create_pull_request_review",
            "description": "Creates a review for a pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "The owner of the repository",
                    },
                    "repo": {
                        "type": "string",
                        "description": "The name of the repository",
                    },
                    "pull_number": {
                        "type": "number",
                        "description": "The number of the pull request",
                    },
                    "body": {
                        "type": "string",
                        "description": "The body of the review",
                    },
                    "event": {
                        "type": "string",
                        "description": "The review action you want to perform. The review actions include: APPROVE, REQUEST_CHANGES, or COMMENT. By leaving this blank, you set the review action state to PENDING, which means you will need to submit the pull request review when you are ready.",
                        "enum": ["REQUEST_CHANGES", "COMMENT", "APPROVE"],
                    },
                    "comments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "body": {
                                    "type": "string",
                                },
                                "path": {
                                    "type": "string",
                                },
                                "position": {
                                    "type": "number",
                                },
                                "line": {
                                    "type": "number",
                                },
                                "side": {
                                    "type": "string",
                                },
                                "start_line": {
                                    "type": "number",
                                },
                                "start_side": {
                                    "type": "string",
                                },
                            },
                            "required": ["body", "path"],
                        },
                    },
                },
                "required": ["owner", "repo", "pull_number"],
            },
        },
    ]


@app.post("/tools/get_all_pull_requests")
async def get_all_pull_requests(
    args: GetAllPullRequestsArguments, token: str = Depends(require_token)
):
    params = {"state": args.state, "per_page": args.per_page, "page": args.page}
    path = f"/repos/{args.owner}/{args.repo}/pulls"
    result = await github_request("GET", path, token=token, params=params)
    return {
        "result": result,
        "message": "Pull requests fetched successfully",
        "meta": {"endpoint": _build_url(path), "params": params},
    }


@app.post("/tools/get_pull_request")
async def get_pull_request(
    args: GetPullRequestArguments, token: str = Depends(require_token)
):
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}"
    result = await github_request("GET", path, token=token)
    return {
        "result": result,
        "message": "Pull request fetched successfully",
        "meta": {"endpoint": _build_url(path)},
    }


@app.post("/tools/list_pull_request_files")
async def list_pull_request_files(
    args: ListPullRequestFilesArguments, token: str = Depends(require_token)
):
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/files"
    result = await github_request("GET", path, token=token)
    return {
        "result": result,
        "message": "Pull request files fetched successfully",
        "meta": {"endpoint": _build_url(path)},
    }


@app.post("/tools/list_pull_request_reviews")
async def list_pull_request_reviews(
    args: ListPullRequestReviewsArguments, token: str = Depends(require_token)
):
    params = {"per_page": args.per_page, "page": args.page}
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/reviews"
    result = await github_request("GET", path, token=token, params=params)
    return {
        "result": result,
        "message": "Pull request reviews fetched successfully",
        "meta": {"endpoint": _build_url(path), "params": params},
    }


@app.post("/tools/list_pull_request_comments")
async def list_pull_request_comments(
    args: ListPullRequestCommentsArguments, token: str = Depends(require_token)
):
    params = {"per_page": args.per_page, "page": args.page}
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/comments"
    result = await github_request("GET", path, token=token, params=params)
    return {
        "result": result,
        "message": "Pull request comments fetched successfully",
        "meta": {"endpoint": _build_url(path), "params": params},
    }


@app.post("/tools/list_pull_request_commits")
async def list_pull_request_commits(
    args: ListPullRequestCommitsArguments, token: str = Depends(require_token)
):
    params = {"per_page": args.per_page, "page": args.page}
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/commits"
    result = await github_request("GET", path, token=token, params=params)
    return {
        "result": result,
        "message": "Pull request commits fetched successfully",
        "meta": {"endpoint": _build_url(path), "params": params},
    }


@app.post("/tools/create_pull_request_review")
async def create_pull_request_review(
    args: CreatePullRequestReviewArguments, token: str = Depends(require_token)
):
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/reviews"
    payload = {
        "event": args.event,
        "body": args.body,
    }
    comments = [
        comment.model_dump(exclude_none=True) for comment in args.comments or []
    ]
    if comments:
        payload["comments"] = comments
    result = await github_request("POST", path, token=token, json_body=payload)
    return {
        "result": result,
        "message": "Pull request review created successfully",
        "meta": {"endpoint": _build_url(path)},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
