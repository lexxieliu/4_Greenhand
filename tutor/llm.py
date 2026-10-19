"""Local Hugging Face model for the tutor (and any other feature that wants the local model).

* The model (settings.LOCAL_MODEL_ID, default Qwen/Qwen2.5-3B-Instruct) is loaded ONCE, on the first
  request, then reused. torch/transformers are imported lazily, so Django start-up, migrations and
  tests stay fast and never need the weights.
* transformers downloads the weights (~6 GB) automatically the first time. To do that ahead of time
  run:  python manage.py warmup_model
* Generation settings match the Part 1 benchmark: greedy decoding, 160 new tokens.

Public API:
    generate_json(task, text) -> dict     task is "care" or "summary"; never raises for bad model output
    generate(task, text)      -> (dict, raw_text)
Both raise LLMUnavailable if the model cannot be loaded or run.
"""
import logging
import threading

from django.conf import settings

from . import prompts
from .guardrails import parse_and_validate

logger = logging.getLogger(__name__)

MAX_NEW_TOKENS = 160

_load_lock = threading.Lock()
_generate_lock = threading.Lock()     # one generation at a time: the model is not thread-safe
_state = {}                           # filled by get_model(): tokenizer, model, device


class LLMUnavailable(Exception):
    """The local model could not be loaded or could not produce an answer."""


def _load():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_id = settings.LOCAL_MODEL_ID
    if torch.cuda.is_available():
        device = "cuda"
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    elif torch.backends.mps.is_available():
        device, dtype = "mps", torch.float16
    else:
        device, dtype = "cpu", torch.bfloat16     # half the RAM of float32 (3B model: ~6 GB instead of ~12 GB)

    logger.info("Loading %s on %s (first use downloads the weights)...", model_id, device)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype)
    except TypeError:                              # older transformers call it torch_dtype
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype)
    model.to(device).eval()
    logger.info("Model ready.")
    return {"tokenizer": tokenizer, "model": model, "device": device}


def get_model():
    """Return the loaded model, loading it on first call (safe to call from many threads)."""
    if not _state:
        with _load_lock:
            if not _state:
                _state.update(_load())
    return _state["tokenizer"], _state["model"], _state["device"]


def _run(tokenizer, model, device, messages):
    import torch

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(device)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    with _generate_lock, torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False, pad_token_id=pad_id)
    new_tokens = output[0, inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def generate(task, text):
    """Run the local model. Returns (validated_result_dict, raw_model_text)."""
    try:
        tokenizer, model, device = get_model()
        raw = _run(tokenizer, model, device, prompts.build_messages(task, text))
    except Exception as exc:                       # download/offline/out-of-memory/etc.
        logger.exception("Local model failed")
        raise LLMUnavailable(str(exc)) from exc
    return parse_and_validate(raw, task), raw


def generate_json(task, text):
    """Like generate() but returns only the validated dict:
    the model's JSON, a {"refused": True, "reason": ...} dict, or {"error": True, "message": ...}."""
    return generate(task, text)[0]
