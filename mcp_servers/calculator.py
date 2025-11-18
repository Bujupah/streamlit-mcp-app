from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class AddArguments(BaseModel):
    a: float
    b: float


class MultiplyArguments(BaseModel):
    a: float
    b: float


@app.get("/tools")
async def get_tools():
    return [
        {
            "name": "add",
            "description": "Adds two floats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "The first float"},
                    "b": {"type": "number", "description": "The second float"},
                },
                "required": ["a", "b"],
            },
        },
        {
            "name": "multiply",
            "description": "Multiplies two floats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "The first float"},
                    "b": {"type": "number", "description": "The second float"},
                },
                "required": ["a", "b"],
            },
        },
    ]


@app.post("/tools/add")
async def add(args: AddArguments):
    result = args.a + args.b
    return {"result": result}


@app.post("/tools/multiply")
async def multiply(args: MultiplyArguments):
    result = args.a * args.b
    return {"result": result}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
