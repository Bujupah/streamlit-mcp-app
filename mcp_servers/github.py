import contextlib
import logging
import os
from typing import Any, Dict, Literal, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

GITHUB_API_BASE = os.environ.get("GITHUB_API_BASE", "https://api.github.com")
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=30.0, write=30.0)

app = FastAPI()

logger = logging.getLogger("mcp.github")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [mcp.github]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_event(message: str, **context: Any) -> None:
    if context:
        context_str = " ".join(f"{key}={value!r}" for key, value in context.items())
        logger.info("%s | %s", message, context_str)
    else:
        logger.info(message)


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
        log_event("Token missing for GitHub request")
        raise HTTPException(
            status_code=401,
            detail="GitHub token required. Provide a Bearer token in the Authorization header.",
        )
    log_event("GitHub token received", length=len(token))
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
    log_event("GitHub API call", method=method, path=path, params=params or {})
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
            log_event(
                "GitHub API returned error",
                method=method,
                path=path,
                status=exc.response.status_code,
                detail=exc.response.text,
            )
            detail: Any = exc.response.text
            with contextlib.suppress(Exception):
                detail = exc.response.json()
            raise HTTPException(status_code=exc.response.status_code, detail=detail)
        except httpx.HTTPError as exc:
            log_event(
                "GitHub API request failed", method=method, path=path, error=str(exc)
            )
            raise HTTPException(status_code=502, detail=str(exc))
    log_event(
        "GitHub API call succeeded",
        method=method,
        path=path,
        status=response.status_code,
    )
    with contextlib.suppress(ValueError):
        return response.json()
    return response.text


class GetAllPullRequestsArguments(BaseModel):
    owner: str
    repo: str
    state: Literal["open", "closed", "all"] = "open"


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


class ListPullRequestCommentsArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int


class ListPullRequestCommitsArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int


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
    params = {"state": args.state}
    path = f"/repos/{args.owner}/{args.repo}/pulls"
    log_event(
        "Fetching pull requests",
        owner=args.owner,
        repo=args.repo,
        state=args.state,
    )
    result = await github_request("GET", path, token=token, params=params)
    log_event(
        "Fetched pull requests",
        owner=args.owner,
        repo=args.repo,
        count=len(result) if isinstance(result, list) else "unknown",
    )
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
    log_event(
        "Fetching pull request",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
    )
    result = await github_request("GET", path, token=token)
    log_event(
        "Fetched pull request",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
    )
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
    log_event(
        "Listing pull request files",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
    )
    result = await github_request("GET", path, token=token)
    log_event(
        "Listed pull request files",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
        count=len(result) if isinstance(result, list) else "unknown",
    )
    return {
        "result": result,
        "message": "Pull request files fetched successfully",
        "meta": {"endpoint": _build_url(path)},
    }


@app.post("/tools/list_pull_request_reviews")
async def list_pull_request_reviews(
    args: ListPullRequestReviewsArguments, token: str = Depends(require_token)
):
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/reviews"
    log_event(
        "Listing pull request reviews",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
    )
    result = await github_request("GET", path, token=token)
    log_event(
        "Listed pull request reviews",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
        count=len(result) if isinstance(result, list) else "unknown",
    )
    return {
        "result": result,
        "message": "Pull request reviews fetched successfully",
        "meta": {"endpoint": _build_url(path)},
    }


@app.post("/tools/list_pull_request_comments")
async def list_pull_request_comments(
    args: ListPullRequestCommentsArguments, token: str = Depends(require_token)
):
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/comments"
    log_event(
        "Listing pull request comments",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
    )
    result = await github_request("GET", path, token=token)
    log_event(
        "Listed pull request comments",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
        count=len(result) if isinstance(result, list) else "unknown",
    )
    return {
        "result": result,
        "message": "Pull request comments fetched successfully",
        "meta": {"endpoint": _build_url(path)},
    }


@app.post("/tools/list_pull_request_commits")
async def list_pull_request_commits(
    args: ListPullRequestCommitsArguments, token: str = Depends(require_token)
):
    path = f"/repos/{args.owner}/{args.repo}/pulls/{args.pull_number}/commits"
    log_event(
        "Listing pull request commits",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
    )
    result = await github_request("GET", path, token=token)
    log_event(
        "Listed pull request commits",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
        count=len(result) if isinstance(result, list) else "unknown",
    )
    return {
        "result": result,
        "message": "Pull request commits fetched successfully",
        "meta": {"endpoint": _build_url(path)},
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
    log_event(
        "Creating pull request review",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
        event=args.event,
        comments=len(comments),
    )
    result = await github_request("POST", path, token=token, json_body=payload)
    log_event(
        "Pull request review created",
        owner=args.owner,
        repo=args.repo,
        pull=args.pull_number,
        event=args.event,
    )
    return {
        "result": result,
        "message": "Pull request review created successfully",
        "meta": {"endpoint": _build_url(path)},
    }

