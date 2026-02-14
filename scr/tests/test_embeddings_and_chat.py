import os
import types
import asyncio
import pytest
from fastapi.testclient import TestClient


def test_openai_embeddings_dimension(monkeypatch):
    # Use project settings to read API credentials and embedding size
    from helper.config import get_settings
    settings = get_settings()

    # Skip if OpenAI API key is not configured (no network during CI/local)
    if not settings.OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY not configured; skipping OpenAI embeddings test")

    from stores.LLM.providers.OpenAIProvider import OpenAIProvider

    provider = OpenAIProvider(
        api_key=settings.OPENAI_API_KEY,
        api_url=settings.OPENAI_API_URL or None,
        default_input_max_characters=256,
        default_out_put_max_characters=1000,
        default_generation_temperature=None,
    )
    # Expect dimensions to match configured EMBEDDING_MODEL_SIZE
    provider.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)
    vecs = provider.embed_text(["hello world", "test"], document_type="document")
    assert isinstance(vecs, list) and len(vecs) == 2
    assert all(isinstance(v, list) for v in vecs)
    assert all(len(v) == settings.EMBEDDING_MODEL_SIZE for v in vecs)


def test_chat_answer_endpoint(monkeypatch, tmp_path):
    # Prepare fake UI file
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "index.html").write_text("<html>hello ui</html>", encoding="utf-8")

    # Point app to tmp UI path by monkeypatching os.path.join in the route context
    import routes.nlp as nlp_route

    def fake_join(a, b, c):
        # redirect to tmp ui
        return str(ui_dir)

    # Fake app with test clients and methods
    class FakeVectorDB:
        async def connect(self):
            pass

        async def disconnect(self):
            pass

        def list_all_collection(self):
            return []

    class FakeEmbeddings:
        embedding_size = 1024

        def embed_text(self, texts, document_type=None):
            return [[0.0] * 1024 for _ in (texts if isinstance(texts, list) else [texts])]

    class FakeGenClient:
        def __init__(self):
            self.enums = types.SimpleNamespace(SYSTEM="SYSTEM")
            self.client = types.SimpleNamespace(
                rerank=lambda **kwargs: types.SimpleNamespace(results=[])
            )

        def set_generation_model(self, model_id: str):
            pass

        def process_text(self, t: str):
            return t

        def generate_text(self, prompt: str, max_output_tokens: int = 1000, chat_history=None, temperature: float = None):
            return "ok"

        def construct_prompt(self, prompt: str, role: str):
            return {"role": role, "content": prompt}

    # Build FastAPI app instance
    from main import app

    app.vectordb_client = FakeVectorDB()
    app.embedding_client = FakeEmbeddings()
    app.generation_client = FakeGenClient()
    app.template_parser = types.SimpleNamespace(
        get=lambda ns, key, ctx=None: ctx.get("chunk_text") if ctx else "system"
    )

    # Monkeypatch UI path resolution
    import os as _os

    def fake_isdir(p):
        return True

    def fake_listdir(p):
        return ["index.html"]

    def fake_isfile(p):
        return True

    def fake_getsize(p):
        return 10

    def fake_open(path, mode="r", encoding=None, errors=None):
        return open(ui_dir / "index.html", mode, encoding=encoding)

    monkeypatch.setattr(nlp_route.os.path, "join", lambda *args: str(ui_dir))
    monkeypatch.setattr(nlp_route.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(nlp_route.os, "listdir", lambda p: ["index.html"])
    monkeypatch.setattr(nlp_route.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(nlp_route.os.path, "getsize", lambda p: 10)

    client = TestClient(app)
    resp = client.post("/nlp/chat/answer", json={"question": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("answer")
    # Optional UI may be present
    assert "ui" in data


