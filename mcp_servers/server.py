from fastapi import FastAPI
from calculator import app as calculator_app
from github import app as github_app

app = FastAPI()

app.mount("/calculator", calculator_app)
app.mount("/github", github_app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=3000, reload=True)
