from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class GetAllPullRequestsArguments(BaseModel):
    owner: str
    repo: str  # Changed from 'repository' to match tool definition


class GetPullRequestArguments(BaseModel):
    owner: str
    repo: str  # Changed from 'repository' to match tool definition
    pull_number: int


class ListPullRequestFilesArguments(BaseModel):
    owner: str
    repo: str  # Changed from 'repository' to match tool definition
    pull_number: int


class Comment(BaseModel):
    body: str
    path: str
    position: int = None  # Made optional with default
    line: int = None  # Made optional with default
    side: str = None  # Made optional with default
    start_line: int = None  # Made optional with default
    start_side: str = None  # Made optional with default


class CreatePullRequestReviewArguments(BaseModel):
    owner: str
    repo: str
    pull_number: int
    body: str
    event: Literal["REQUEST_CHANGES", "APPROVE", "COMMENT"]  # Added COMMENT
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
                    "owner": {
                        "type": "string",
                        "description": "The owner of the repository",
                    },
                    "repo": {
                        "type": "string",
                        "description": "The name of the repository",
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
                                    "description": "Text of the review comment.",
                                },
                                "path": {
                                    "type": "string",
                                    "description": "The relative path to the file that necessitates a review comment.",
                                },
                                "position": {
                                    "type": "number",
                                    "description": 'The position in the diff where you want to add a review comment. Note this value is not the same as the line number in the file. The position value equals the number of lines down from the first "@@" hunk header in the file you want to add a comment. The line just below the "@@" line is position 1, the next line is position 2, and so on. The position in the diff continues to increase through lines of whitespace and additional hunks until the beginning of a new file.',
                                },
                                "line": {
                                    "type": "number",
                                    "description": "The line of the comment",
                                },
                                "side": {
                                    "type": "string",
                                    "description": "The side of the comment",
                                },
                                "start_line": {
                                    "type": "number",
                                    "description": "The start line of the comment",
                                },
                                "start_side": {
                                    "type": "string",
                                    "description": "The start side of the comment",
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
async def get_all_pull_requests(args: GetAllPullRequestsArguments):
    endpoint = (
        "https://api.github.com"
        + "/repos/"
        + args.owner
        + "/"
        + args.repo  # Changed from args.repository
        + "/pulls"
    )
    return {
        "result": [],
        "message": "Pull requests fetched successfully",
        "meta": {"endpoint": endpoint, "args": args.model_dump_json()},
    }


@app.post("/tools/get_pull_request")
async def get_pull_request(args: GetPullRequestArguments):
    endpoint = (
        "https://api.github.com"
        + "/repos/"
        + args.owner
        + "/"
        + args.repo  # Changed from args.repository
        + "/pulls/"
        + str(args.pull_number)
    )
    return {
        "result": {
            "title": "Pull Request Title",
            "body": "Pull Request Body",
            "state": "OPEN",
            "created_at": "2021-01-01",
            "updated_at": "2021-01-01",
            "closed_at": "2021-01-01",
        },
        "message": "Pull request fetched successfully",
        "meta": {"endpoint": endpoint, "args": args.model_dump_json()},
    }


@app.post("/tools/list_pull_request_files")
async def list_pull_request_files(args: ListPullRequestFilesArguments):
    endpoint = (
        "https://api.github.com"
        + "/repos/"
        + args.owner
        + "/"
        + args.repo  # Changed from args.repository
        + "/pulls/"
        + str(args.pull_number)
        + "/files"
    )
    return {
        "result": [],
        "message": "Pull request files fetched successfully",
        "meta": {"endpoint": endpoint, "args": args.model_dump_json()},
    }


@app.post("/tools/create_pull_request_review")
async def create_pull_request_review(args: CreatePullRequestReviewArguments):
    endpoint = (
        "https://api.github.com"
        + "/repos/"
        + args.owner
        + "/"
        + args.repo
        + "/pulls/"
        + str(args.pull_number)
        + "/reviews"
    )
    return {
        "result": {
            "files": [
                {
                    "path": "path/to/file.txt",
                    "status": "added",
                    "changes": 10,
                    "additions": 10,
                    "deletions": 10,
                }
            ],
            "summary": {
                "total_changes": 10,
                "total_additions": 10,
                "total_deletions": 10,
            },
            "conclusion": "APPROVED",
            "review_comments": [
                {
                    "body": "Review comment body",
                    "path": "path/to/file.txt",
                    "position": 1,
                }
            ],
            "review_comments_count": 1,
            "review_comments_url": "https://api.github.com/repos/owner/repo/pulls/1/reviews/1/comments",
            "review_comments_html_url": "https://github.com/owner/repo/pull/1/reviews/1/comments",
        },
        "message": "Pull request review created successfully",
        "meta": {"endpoint": endpoint, "args": args.model_dump_json()},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
