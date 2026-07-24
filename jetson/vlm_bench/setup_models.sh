#!/usr/bin/env bash
#
# Make sure all benchmark models are available in Ollama.
# SmolVLM isn't in Ollama's registry, so we pull the official ggml-org GGUFs
# from HuggingFace (which include the vision projector) and alias them to
# short names. Then we self-test that each one can actually SEE an image.
#
#     bash ~/vlm_bench/setup_models.sh

set -uo pipefail
TESTIMG=/tmp/vlm_test.jpg

pull_hf () {   # $1 = hf repo:tag   $2 = short alias
    local repo="$1" alias="$2"
    echo ">> $alias  <-  hf.co/$repo"
    if ollama pull "hf.co/$repo" 2>&1 | tail -1; then
        ollama cp "hf.co/$repo" "$alias" 2>/dev/null && echo "   aliased -> $alias"
    fi
}

echo "=== registry models ==="
ollama pull moondream 2>&1 | tail -1
ollama list | grep -q "qwen2.5vl:3b" || ollama pull qwen2.5vl:3b 2>&1 | tail -1

echo; echo "=== SmolVLM variants (GGUF import) ==="
pull_hf "ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0" "smolvlm-256m"
pull_hf "ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0" "smolvlm-500m"
pull_hf "ggml-org/SmolVLM-Instruct-GGUF:Q8_0"      "smolvlm-2.2b"

echo; echo "=== VISION SELF-TEST (does each model actually see the image?) ==="
[ -f "$TESTIMG" ] || { echo "no $TESTIMG to test with — capture one first"; exit 0; }
# send the image in the request BODY via python (avoids 'argument list too long')
python3 - "$TESTIMG" <<'PY'
import base64, json, sys, urllib.request
img = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
for m in ["smolvlm-256m", "smolvlm-500m", "smolvlm-2.2b", "moondream", "qwen2.5vl:3b"]:
    payload = {"model": m, "prompt": "What is the main color in this image? One word.",
               "images": [img], "stream": False,
               "options": {"num_gpu": 99, "num_predict": 10}}
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate",
              data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=180))
        print(f"  {m:14s}: {d.get('response','').strip() or d.get('error','(empty)')}")
    except Exception as e:
        print(f"  {m:14s}: NOT INSTALLED / ERROR ({e})")
PY
echo
echo "If a SmolVLM line is empty or nonsense, Ollama didn't load its vision"
echo "projector -> we'll fall back to llama.cpp for that model."
