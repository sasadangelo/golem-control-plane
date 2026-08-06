from agent import agent_executor
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

app = FastAPI(title="Golem Agent Runner", version="0.1.0")


class ChatPayload(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatPayload):
    try:
        inputs = {"messages": [HumanMessage(content=payload.message)]}
        result = agent_executor.invoke(inputs)
        last_message = result["messages"][-1]
        return ChatResponse(reply=str(last_message.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
async def health():
    return {"status": "ok"}
