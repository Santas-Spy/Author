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

def muse(prompt:str):
    raise NotImplementedError("Muse adapter not yet created")

def seperateThinking(text, thinking_start = "<think>", thinking_end = "</think>"):
	# Search the text to ensure there is only one instance of <think> and </think>, otherwise things might get messy
	split_text = {"thinking": "", "response": text}
	if text.count(thinking_start) == 1 and text.count(thinking_end) == 1:
		split = text.split(thinking_start)[1].split(thinking_end)
		split_text["thinking"] = split[0]
		split_text["response"] = split[1]
		print("Split success")
	else:
		print("WARNING: TEXT HAS INCORRECT NUMBER OF THINKING TAGS")

	return split_text
