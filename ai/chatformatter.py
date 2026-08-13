def lfm2_5(prompt:str):
    prompt = prompt.replace(
        "{{[SYSTEM]}}", "<|startoftext|><|im_start|>system\n"
    )  # <-- This assumes the system prompt is *always* first
    prompt = prompt.replace("{{[INPUT]}}", "<|im_end|>\n<|im_start|>user\n")
    prompt = prompt.replace("{{[OUTPUT]}}", "<|im_end|>\n<|im_start|>assistant\n")
    return prompt

def gemini(prompt:str):
    prompt = prompt.replace(
        "{{[SYSTEM]}}", "<|turn>system\n"
    )  # <-- This assumes the system prompt is *always* first
    prompt = prompt.replace("{{[INPUT]}}", "<turn|>\n<|turn>user\n")
    prompt = prompt.replace("{{[OUTPUT]}}", "<|turn>model\n<|channel>thought\n *")
    return prompt
