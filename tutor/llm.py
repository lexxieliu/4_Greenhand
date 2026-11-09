"""Local Hugging Face model for the tutor (ported from the A6 tutor, commit ab9d2b5).

* The model (settings.LOCAL_MODEL_ID, default Qwen/Qwen2.5-3B-Instruct) is loaded ONCE, on the first
  request, then reused. torch/transformers are imported lazily, so Django start-up, migrations and
  tests stay fast and never need the weights.
* transformers downloads the weights (~6 GB) into the Hugging Face cache (~/.cache/huggingface, outside
  the repo) the first time. To do that ahead of time run:  python manage.py warmup_model
* Greedy decoding (same as the A6/A7 benchmarks). Generation stops after MAX_NEW_TOKENS tokens or
  settings.TUTOR_TIMEOUT_SECONDS seconds, whichever comes first.
* Prefix caching (recommended in the A7 system design): every prompt starts with the same system prompt
  and worked examples (~60% of its tokens). Their key/value cache is computed once and copied into each
  request, so only the question-specific part is processed. Output is unchanged (greedy decoding).

Public API:
    generate(messages) -> str     raw model text; raises LLMUnavailable if the model cannot load or run
"""
import copy
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

MAX_NEW_TOKENS = 220

_load_lock = threading.Lock()
_generate_lock = threading.Lock()     # one generation at a time: the model is not thread-safe
_state = {}                           # filled by get_model(): tokenizer, model, device
_prefix = {}                          # text -> (token ids, key/value cache) of the fixed prompt prefix


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
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype)
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


def _prefix_cache(tokenizer, model, device, messages):
    """Key/value cache for every message except the last one (the fixed system prompt + examples)."""
    import torch
    from transformers import DynamicCache

    text = tokenizer.apply_chat_template(messages[:-1], tokenize=False)
    if text not in _prefix:
        ids = tokenizer(text, return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)
        cache = DynamicCache()
        with torch.inference_mode():
            model(ids, past_key_values=cache, use_cache=True)
        _prefix.clear()                            # keep only the current prompt version
        _prefix[text] = (ids, cache)
    return _prefix[text]


def _run(tokenizer, model, device, messages):
    import torch

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    options = dict(max_new_tokens=MAX_NEW_TOKENS, do_sample=False, pad_token_id=pad_id,
                   max_time=settings.TUTOR_TIMEOUT_SECONDS)
    with _generate_lock, torch.inference_mode():
        prefix_ids, prefix_cache = _prefix_cache(tokenizer, model, device, messages)
        n = prefix_ids.shape[1]
        if input_ids.shape[1] > n and torch.equal(input_ids[0, :n], prefix_ids[0]):
            options["past_key_values"] = copy.deepcopy(prefix_cache)
        output = model.generate(input_ids, **options)
    new_tokens = output[0, input_ids.shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def usage(messages, output):
    """(prompt_tokens, completion_tokens) for a finished call, or (None, None) if the model is not loaded."""
    if not _state:
        return None, None
    tokenizer = _state["tokenizer"]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return len(tokenizer(prompt, add_special_tokens=False)["input_ids"]), len(tokenizer(output, add_special_tokens=False)["input_ids"])


def generate(messages):
    """Run the local model on chat messages and return its raw text."""
    try:
        tokenizer, model, device = get_model()
        return _run(tokenizer, model, device, messages)
    except Exception as exc:                       # download/offline/out-of-memory/etc.
        logger.exception("Local model failed")
        raise LLMUnavailable(str(exc)) from exc
