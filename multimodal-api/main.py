import os
import re
import base64
import io
import asyncio
import tempfile
from typing import TypedDict, Optional, List
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image
import httpx
from langgraph.graph import StateGraph, END
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multimodal-api")

# --- Config ---
VLLM_URL = os.environ["VLLM_URL"]
VLLM_API_KEY = os.environ["VLLM_API_KEY"]
TARGET_MODEL = os.environ.get("TARGET_MODEL", "solidrust/Mistral-7B-Instruct-v0.3-AWQ")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
EMBED_MODEL_NAME = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")
VLLM_HEALTH_URL = os.environ.get("VLLM_HEALTH_URL", "http://vllm:8000/health")
MAX_BODY_SIZE_MB = int(os.environ.get("MAX_BODY_SIZE_MB", "10"))

# Globals set in lifespan
ocr_predictor = None
whisper_model = None
embed_model = None
preprocess_graph = None
http_client: Optional[httpx.AsyncClient] = None


# --- Pydantic Request Models ---
class TextPart(BaseModel):
    type: str = "text"
    text: str

class ImageUrlPart(BaseModel):
    type: str = "image_url"
    image_url: dict

class AudioUrlPart(BaseModel):
    type: str = "audio_url"
    audio_url: dict

class ChatMessage(BaseModel):
    role: str
    content: str | list[dict]

class ChatCompletionRequest(BaseModel):
    model: str = "base-mind"
    messages: list[ChatMessage]
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[str | list[str]] = None
    seed: Optional[int] = None

class EmbeddingsRequest(BaseModel):
    input: str | list[str]
    model: str = "bge-m3"


# --- LangGraph State ---
class State(TypedDict):
    messages: List[dict]
    input_type: str
    ocr_result: Optional[str]
    stt_result: Optional[str]
    final_prompt: Optional[str]
    llm_response: Optional[dict]


# --- Response Post-Processor ---
# Mistral-7B-Instruct-v0.3 is notoriously "chatty". This filter strips
# self-introductions and English drift to guarantee a consistent dev experience.
_SELF_INTRO_PATTERNS = [
    # Match anywhere in the text (not just start) to catch mid-sentence intros
    r"(?i)je\s+suis\s+(un\s+|une\s+|l['\"']|le\s+|la\s+)?(assistant|modèle|outil|ia|intelligence|robot|agent|programme|logiciel)(\s+[^.!?]*|[.!?])",
    r"(?i)je\s+m'appelle\s+[^.!?]*[.!?]",
    r"(?i)je\s+suis\s+(là\s+pour|ravi|heureux|heureuse|content|disponible|prêt)\s+(de\s+|à\s+)?(vous\s+|te\s+)?(aider|rencontrer|servir|répondre|assister)(\s+[^.!?]*|[.!?])",
    r"(?i)comment\s+(puis-je|peux-je|puis\s+je|peux\s+je)\s+(vous\s+|te\s+)?(aider|servir|renseigner|assister)(\s+[^.!?]*|[.!?])",
    r"(?i)en\s+quoi\s+puis-je\s+(vous\s+|te\s+)?aider[.!?]",
    r"(?i)à\s+votre\s+service[.!?]",
    r"(?i)je\s+suis\s+(conçu|programmé|entraîné|optimisé|développé)\s+pour\s+[^.!?]*[.!?]",
    r"(?i)bien\s+sûr,?\s+je\s+suis\s+[^.!?]*[.!?]",
    r"(?i)oui,?\s+je\s+suis\s+[^.!?]*[.!?]",
    r"(?i)je\s+suis\s+base-mind[.!?]?",
    r"(?i)je\s+suis\s+ivoire-mind[.!?]?",
]

_ENGLISH_DRIFT_PATTERNS = [
    r"(?i)\b(hello|hi|hey)\b",
    r"(?i)\bphotosynthesis\b",
    r"(?i)\bartificial\s+intelligence\b",
    # Avoid matching "L'IA" in French — require space/punctuation around "AI"
    r"(?i)(^|\s)AI(\s|$|[.,;:!?])",
    r"(?i)\bmachine\s+learning\b",
]

_SALUTATION_RE = re.compile(r"(?i)\b(salut|bonjour|coucou|hey|hello|hi)\b")


def _post_process_response(data: dict, last_user_text: str) -> dict:
    if not data or "choices" not in data or not data["choices"]:
        return data
    msg = data["choices"][0].get("message", {})
    original = msg.get("content", "")
    cleaned = original

    # 1. Strip self-introductions sentence by sentence
    for pat in _SELF_INTRO_PATTERNS:
        cleaned = re.sub(pat, "", cleaned)

    # 2. Strip any remaining English self-intro drift mid-response
    # (e.g. "I am happy to help you" mixed into French)
    cleaned = re.sub(r"(?i)I\s+am\s+[^.!?]*[.!?]", "", cleaned)
    cleaned = re.sub(r"(?i)I\s+can\s+help\s+[^.!?]*[.!?]", "", cleaned)

    # 3. If salutation prompt and response is still too chatty, force short
    is_salutation = bool(_SALUTATION_RE.search(last_user_text))
    if is_salutation and len(cleaned.split()) > 12:
        cleaned = "Salut."

    # 4. Clean up leftover whitespace
    cleaned = cleaned.strip()
    if not cleaned:
        if is_salutation:
            cleaned = "Salut."
        else:
            cleaned = "Je n'ai pas compris."

    # Only mutate if we actually changed something
    if cleaned != original:
        logger.info(f"Post-processed response: '{original[:60]}...' -> '{cleaned[:60]}...'")
        data["choices"][0]["message"]["content"] = cleaned
    return data


# --- Content Extraction ---
def _extract_content(messages: List[dict]):
    user_texts = []
    images = []
    audios = []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    ptype = part.get("type", "")
                    if ptype == "text":
                        t = part.get("text", "")
                        if t:
                            user_texts.append(t)
                    elif ptype == "image_url":
                        url = part["image_url"].get("url", "")
                        if url.startswith("data:image"):
                            try:
                                images.append(url.split(",", 1)[1])
                            except Exception as e:
                                logger.warning(f"Failed to parse image_url: {e}")
                    elif ptype == "audio_url":
                        url = part["audio_url"].get("url", "")
                        if url.startswith("data:audio"):
                            try:
                                audios.append(url.split(",", 1)[1])
                            except Exception as e:
                                logger.warning(f"Failed to parse audio_url: {e}")
            elif isinstance(content, str):
                user_texts.append(content)
            break
    return "\n".join(user_texts), images, audios


# --- LangGraph Nodes ---
def classify_node(state: State) -> State:
    _, images, audios = _extract_content(state["messages"])
    if images and audios:
        return {"input_type": "mixed"}
    elif images:
        return {"input_type": "image"}
    elif audios:
        return {"input_type": "audio"}
    return {"input_type": "text"}


async def process_ocr_node(state: State) -> State:
    _, images, _ = _extract_content(state["messages"])
    if not images or ocr_predictor is None:
        return {"ocr_result": None}

    def _run_ocr():
        from doctr.io import DocumentFile
        results = []
        for b64 in images:
            img_bytes = base64.b64decode(b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                img.save(f, format="PNG")
                tmp_path = f.name
            try:
                doc = DocumentFile.from_images([tmp_path])
                result = ocr_predictor(doc)
                export = result.export()
                lines = []
                for page in export.get("pages", []):
                    for block in page.get("blocks", []):
                        for line in block.get("lines", []):
                            words = [w["value"] for w in line.get("words", [])]
                            if words:
                                lines.append(" ".join(words))
                results.append("\n".join(lines))
            finally:
                os.remove(tmp_path)
        return "\n\n".join(results) if results else None

    loop = asyncio.get_event_loop()
    ocr_text = await loop.run_in_executor(None, _run_ocr)
    return {"ocr_result": ocr_text}


async def process_stt_node(state: State) -> State:
    _, _, audios = _extract_content(state["messages"])
    if not audios or whisper_model is None:
        return {"stt_result": None}

    def _run_stt():
        results = []
        for b64 in audios:
            audio_bytes = base64.b64decode(b64)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                path = f.name
            try:
                segments, _ = whisper_model.transcribe(path, language="fr", beam_size=5)
                text = " ".join([seg.text for seg in segments])
            finally:
                os.remove(path)
            results.append(text)
        return "\n\n".join(results) if results else None

    loop = asyncio.get_event_loop()
    stt_text = await loop.run_in_executor(None, _run_stt)
    return {"stt_result": stt_text}


def after_ocr(state: State) -> str:
    _, _, audios = _extract_content(state["messages"])
    if audios:
        return "process_stt"
    return "build_prompt"


def build_prompt_node(state: State) -> State:
    messages = list(state["messages"])
    ocr_result = state.get("ocr_result")
    stt_result = state.get("stt_result")

    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            content = messages[i].get("content", "")
            user_texts = []
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        t = part.get("text", "")
                        if t:
                            user_texts.append(t)
            elif isinstance(content, str):
                user_texts.append(content)

            user_text = "\n".join(user_texts)

            parts = []
            if ocr_result:
                parts.append(f"[Texte extrait de l'image]\n{ocr_result}")
            if stt_result:
                parts.append(f"[Transcription audio]\n{stt_result}")
            if parts:
                parts.append(f"[Question]\n{user_text}")
                final_text = "\n\n".join(parts)
            else:
                final_text = user_text

            messages[i] = {"role": "user", "content": final_text}
            break

    return {"final_prompt": messages[-1].get("content") if messages else None, "messages": messages}


# --- Graph Builder ---
def _build_preprocess_graph():
    builder = StateGraph(State)
    builder.add_node("classify", classify_node)
    builder.add_node("process_ocr", process_ocr_node)
    builder.add_node("process_stt", process_stt_node)
    builder.add_node("build_prompt", build_prompt_node)

    builder.set_entry_point("classify")
    builder.add_conditional_edges(
        "classify",
        lambda s: s["input_type"],
        {"image": "process_ocr", "audio": "process_stt", "mixed": "process_ocr", "text": "build_prompt"},
    )
    builder.add_conditional_edges("process_ocr", after_ocr, {"process_stt": "process_stt", "build_prompt": "build_prompt"})
    builder.add_edge("process_stt", "build_prompt")
    builder.add_edge("build_prompt", END)
    return builder.compile()


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ocr_predictor, whisper_model, embed_model, preprocess_graph, http_client
    logger.info("Loading CPU models (DocTR, faster-whisper, bge-m3)...")

    from doctr.models import ocr_predictor as doctr_ocr_predictor
    ocr_predictor = doctr_ocr_predictor(pretrained=True)
    logger.info("DocTR loaded.")

    from faster_whisper import WhisperModel
    whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    logger.info(f"faster-whisper ({WHISPER_MODEL_SIZE}) loaded.")

    from sentence_transformers import SentenceTransformer
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    logger.info("bge-m3 loaded.")

    http_client = httpx.AsyncClient(timeout=120.0)
    logger.info("HTTP client initialized.")

    preprocess_graph = _build_preprocess_graph()
    logger.info("Graph compiled.")
    yield

    logger.info("Shutting down multimodal-api.")
    if http_client:
        await http_client.aclose()


app = FastAPI(title="Multimodal API (OCR+STT+Embed)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health():
    vllm_ok = False
    if http_client:
        try:
            r = await http_client.get(VLLM_HEALTH_URL, timeout=5.0)
            vllm_ok = r.status_code == 200
        except Exception:
            pass
    return {
        "status": "ok",
        "doctr_loaded": ocr_predictor is not None,
        "whisper_loaded": whisper_model is not None,
        "embed_loaded": embed_model is not None,
        "vllm_reachable": vllm_ok,
    }


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Payload exceeds {MAX_BODY_SIZE_MB}MB limit")

    messages = [m.model_dump() for m in body.messages]
    initial_state: State = {
        "messages": messages,
        "input_type": "unknown",
        "ocr_result": None,
        "stt_result": None,
        "final_prompt": None,
        "llm_response": None,
    }

    state = await preprocess_graph.ainvoke(initial_state)

    messages = list(state["messages"])

    # Extract last real user text BEFORE any injection for post-processing context
    last_user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                last_user_text = content.strip().lower()
            break

    llm_payload = {
        "model": TARGET_MODEL,
        "messages": messages,
        "stream": body.stream,
        "temperature": 0.2,
        "max_tokens": 256,
    }
    for key in ("max_tokens", "temperature", "top_p", "frequency_penalty", "presence_penalty", "stop", "seed"):
        val = getattr(body, key)
        if val is not None:
            llm_payload[key] = val
    headers = {
        "Authorization": f"Bearer {VLLM_API_KEY}",
        "Content-Type": "application/json",
    }

    if not body.stream:
        resp = await http_client.post(VLLM_URL, json=llm_payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # Post-process: strip self-introductions and English drift
        data = _post_process_response(data, last_user_text)
        return data

    async def event_stream():
        async with http_client.stream("POST", VLLM_URL, json=llm_payload, headers=headers) as response:
            async for chunk in response.aiter_text():
                yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/v1/embeddings")
async def embeddings(body: EmbeddingsRequest):
    texts = body.input if isinstance(body.input, list) else [body.input]
    if not texts or embed_model is None:
        return {"object": "list", "data": [], "model": EMBED_MODEL_NAME}

    def _encode():
        vecs = embed_model.encode(texts, normalize_embeddings=True)
        return vecs.tolist()

    loop = asyncio.get_event_loop()
    vectors = await loop.run_in_executor(None, _encode)

    data = [
        {"object": "embedding", "index": i, "embedding": vec}
        for i, vec in enumerate(vectors)
    ]
    return {"object": "list", "data": data, "model": EMBED_MODEL_NAME}
