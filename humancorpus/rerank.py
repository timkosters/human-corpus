"""Optional second-stage reranker: a small transformer (all-MiniLM-L6-v2, int8 ONNX, 23 MB) that reads
word order, so "love is patient" stops matching hospital patients. Runs on the top candidates only.

Enabled when onnxruntime and tokenizers are installed (pip install -e ".[rerank]"); disable with
HUMANCORPUS_RERANK=0. The model is fetched from the Hugging Face Hub once and cached.
"""
from __future__ import annotations

import os
import threading

import numpy as np

REPO = os.environ.get("HUMANCORPUS_RERANK_MODEL", "Xenova/all-MiniLM-L6-v2")
TOP = int(os.environ.get("HUMANCORPUS_RERANK_TOP", 40))

_model = None
_lock = threading.Lock()


class _MiniLM:
    def __init__(self):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(hf_hub_download(REPO, "tokenizer.json"))
        tok.enable_truncation(64)
        tok.enable_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("HUMANCORPUS_THREADS", os.cpu_count() or 2))
        self.tok = tok
        self.sess = ort.InferenceSession(hf_hub_download(REPO, "onnx/model_quantized.onnx"), so,
                                         providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def embed(self, texts: list[str]) -> np.ndarray:
        enc = self.tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        h = self.sess.run(None, feed)[0]
        v = (h * mask[..., None]).sum(1) / mask.sum(1, keepdims=True)
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


def model():
    """The reranker, or None when disabled or unavailable."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                if os.environ.get("HUMANCORPUS_RERANK", "1") == "0":
                    _model = False
                else:
                    try:
                        _model = _MiniLM()
                    except Exception:  # missing extras or offline: keep the first-stage ranking
                        _model = False
    return _model or None


def rerank(query: str, texts: list[str], score: np.ndarray) -> np.ndarray:
    """Blend the first-stage score with MiniLM similarity for the top candidates; others sink below them."""
    m = model()
    if m is None or len(texts) < 2:
        return score
    top = np.argsort(-score)[:TOP]
    v = m.embed([query] + [texts[i] for i in top])
    sim = v[1:] @ v[0]
    out = score - 1.0
    out[top] = 0.5 * score[top] + 0.5 * sim
    return out
