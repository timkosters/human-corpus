# Hugging Face Space (Docker SDK) running the public human-corpus MCP server.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app
COPY --chown=user . /app
RUN pip install --no-cache-dir ".[semantic]" "huggingface_hub>=0.24" uvicorn starlette

USER user
ENV HOME=/home/user \
    HUMANCORPUS_DB=/home/user/data/corpus.db \
    HUMANCORPUS_DATASET=timourxyz/human-corpus \
    HUMANCORPUS_PUBLIC_URL=https://timourxyz-human-corpus.hf.space/mcp
# Bake the small embedding model into the image so cold starts don't fetch it.
RUN python -c "from model2vec import StaticModel; StaticModel.from_pretrained('minishlab/potion-base-8M')"

EXPOSE 7860
CMD ["python", "-m", "humancorpus.hosted"]
