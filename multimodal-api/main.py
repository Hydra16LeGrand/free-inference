import os
import base64
import io
import asyncio
from typing import TypedDict, Optional, List, Any, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image
import httpx
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from langgraph.graph import StateGraph, END
from prometheus_fastapi_instrumentator import Instrumentator

# --- Config ---
VLLM_URL = os.environ.get("VLLM_URL", "http://vllm:8000/v1/chat/completions")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "sk-vllm-local-secret")
TARGET_MODEL = os.environ.get("TARGET_MODEL", "solidrust/Mistral-7B-Instruct-v0.3-AWQ")
VISION_MODEL = os.environ.get("VISION_MODEL", "Qwen/Qwen2-VL-2B-Instruct")
MAX_VISION_TOKENS = 256

# Globals set in lifespan
model = None
processor = None
preprocess_graph = None
full_graph = None


# --- LangGraph State ---
class State(TypedDict):
    messages: List[dict]
    input_type: str
    vision_result: Optional[str]
    stt_result: Optional[str]
    final_prompt: Optional[str]
    llm_response: Optional[dict]


# --- Vision Helpers ---
def _extract_text_and_images(messages: List[dict]):
    """Parse OpenAI-format messages; returns (user_text, list[PIL.Image])."""
    user_text = ""
    images = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    ptype = part.get("type", "")
                    if ptype == "text":
                        user_text = part.get("text", "")
                    elif ptype == "image_url":
                        url = part["image_url"].get("url", "")
                        if url.startswith("data:image"):
                            try:
                                header, b64 = url.split(",", 1)
                                img_bytes = base64.b64decode(b64)
                                images.append(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
                            except Exception:
                                pass
            elif isinstance(content, str):
                user_text = content
    return user_text, images


async def _run_vision_generate(images: List[Image.Image], prompt: str) -> str:
    """Blocking Qwen2-VL call wrapped in thread pool."""
    def _generate():
        qwen_messages = [
            {
                "role": "user",
                "content": [{"type": "image", "image": img} for img in images] + [{"type": "text", "text": prompt}],
            }
        ]
        text = processor.apply_chat_template(qwen_messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(qwen_messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
        inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=MAX_VISION_TOKENS)

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
        ]
        response = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        return response[0] if response else ""

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate)


# --- LangGraph Nodes ---
def classify_node(state: State) -> State:
    _, images = _extract_text_and_images(state["messages"])
    if images:
        return {"input_type": "vision"}
    return {"input_type": "text"}


async def process_vision_node(state: State) -> State:
    _, images = _extract_text_and_images(state["messages"])
    if not images:
        return {"vision_result": None}
    vision_prompt = "Describe the image in detail and transcribe any visible text."
    result = await _run_vision_generate(images, vision_prompt)
    return {"vision_result": result}


def build_prompt_node(state: State) -> State:
    messages = list(state["messages"])
    vision_result = state.get("vision_result")

    # Enrich only the last user message; keep conversation history intact
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            content = messages[i].get("content", "")
            user_text = ""
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        user_text = part.get("text", "")
            elif isinstance(content, str):
                user_text = content

            final_text = user_text
            if vision_result:
                final_text = (
                    f"[Vision Analysis]\n{vision_result}\n\n"
                    f"[User Question]\n{user_text}"
                )
            messages[i] = {"role": "user", "content": final_text}
            break

    # Inject system prompt if missing
    if not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {
            "role": "system",
            "content": (
                "You are a helpful multilingual assistant. "
                "Use the provided vision analysis to answer accurately."
            ),
        })

    return {"final_prompt": messages[-1].get("content") if messages else None, "messages": messages}


async def call_llm_node(state: State) -> State:
    payload = {
        "model": TARGET_MODEL,
        "messages": state["messages"],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {VLLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(VLLM_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return {"llm_response": data}


# --- Graph Builders ---
def _build_preprocess_graph():
    builder = StateGraph(State)
    builder.add_node("classify", classify_node)
    builder.add_node("process_vision", process_vision_node)
    builder.add_node("build_prompt", build_prompt_node)

    builder.set_entry_point("classify")
    builder.add_conditional_edges(
        "classify",
        lambda s: s["input_type"],
        {"vision": "process_vision", "text": "build_prompt"},
    )
    builder.add_edge("process_vision", "build_prompt")
    builder.add_edge("build_prompt", END)
    return builder.compile()


def _build_full_graph():
    builder = StateGraph(State)
    builder.add_node("classify", classify_node)
    builder.add_node("process_vision", process_vision_node)
    builder.add_node("build_prompt", build_prompt_node)
    builder.add_node("call_llm", call_llm_node)

    builder.set_entry_point("classify")
    builder.add_conditional_edges(
        "classify",
        lambda s: s["input_type"],
        {"vision": "process_vision", "text": "build_prompt"},
    )
    builder.add_edge("process_vision", "build_prompt")
    builder.add_edge("build_prompt", "call_llm")
    builder.add_edge("call_llm", END)
    return builder.compile()


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, processor, preprocess_graph, full_graph
    print("Loading vision model (CPU)...")
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        VISION_MODEL,
        torch_dtype="auto",
        device_map="cpu",
    )
    processor = AutoProcessor.from_pretrained(VISION_MODEL)
    preprocess_graph = _build_preprocess_graph()
    full_graph = _build_full_graph()
    print("Vision model loaded and graphs compiled.")
    yield
    print("Shutting down multimodal-api.")


app = FastAPI(title="Multimodal API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vision_loaded": model is not None,
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    stream = body.get("stream", False)
    messages = body.get("messages", [])

    initial_state: State = {
        "messages": messages,
        "input_type": "unknown",
        "vision_result": None,
        "stt_result": None,
        "final_prompt": None,
        "llm_response": None,
    }

    # Pre-process (classify + optional vision + build prompt)
    state = await preprocess_graph.ainvoke(initial_state)

    llm_payload = {
        "model": TARGET_MODEL,
        "messages": state["messages"],
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {VLLM_API_KEY}",
        "Content-Type": "application/json",
    }

    if not stream:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(VLLM_URL, json=llm_payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    # Streaming: pipe vLLM SSE directly back to client
    async def event_stream():
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", VLLM_URL, json=llm_payload, headers=headers) as response:
                async for chunk in response.aiter_text():
                    yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")
