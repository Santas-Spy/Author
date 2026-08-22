def lfm2_5(prompt: str):
    prompt = prompt.replace(
        "{{[SYSTEM]}}", "<|startoftext|><|im_start|>system\n"
    )  # <-- This assumes the system prompt is *always* first
    prompt = prompt.replace("{{[INPUT]}}", "<|im_end|>\n<|im_start|>user\n")
    prompt = prompt.replace("{{[OUTPUT]}}", "<|im_end|>\n<|im_start|>assistant\n")
    return prompt


def gemini(prompt: str):
    prompt = prompt.replace(
        "{{[SYSTEM]}}", "<|turn>system\n"
    )  # <-- This assumes the system prompt is *always* first
    prompt = prompt.replace("{{[INPUT]}}", "<turn|>\n<|turn>user\n")
    prompt = prompt.replace("{{[OUTPUT]}}", "<|turn>model\n<|channel>thought\n *")
    return prompt


def muse(prompt: str):
    raise NotImplementedError("Muse adapter not yet created")


def seperateThinking(text, thinking_start="<think>", thinking_end="</think>"):
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


def replacePlaceholders(prompt: str, model: str) -> str:
    markers = {
        "{{[SYSTEM]}}": "system",
        "{{[INPUT]}}": "user",
        "{{[OUTPUT]}}": "assistant",
    }
    positions = []

    for marker, role in markers.items():
        start = 0

        # Iterate over the string, finding every marker and it's index
        while True:
            pos = prompt.find(marker, start)

            if pos == -1:
                break

            positions.append((pos, marker, role))
            start = pos + len(marker)

    if not positions:
        return prompt  # Return the raw prompt if no markers were used

    # Sort the list by the order the markers came in
    positions.sort(key=lambda x: x[0])

    # Split the text into messages
    messages = []
    for i, (_, marker, role) in enumerate(positions):
        start = positions[i][0] + len(marker)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(prompt)

        content = prompt[start:end].strip()

        if content:
            messages.append((role, content))

    # ChatML/Qwen expects system before the conversation. This is recommended but we will skip.
    # messages.sort(key=lambda message: 0 if message[0] == "system" else 1)

    # Rejoin all messages together into one big formatted string
    text = "".join(f"<|im_start|>{role}\n{content}<|im_end|>\n" for role, content in messages)

    # Strip the last imend so that text can be continued
    text = text[: -len("<|im_end|>\n")]
    return text


def cleanPlaceholders(text: str) -> str:
    """
    Replaces all conversation tags with invalid ones. This allows a model to read the conversation history as an input rather than multiple messages
    """
    text = text.replace("{{[SYSTEM]}}", "{[SYSTEM]}")
    text = text.replace("{{[INPUT]}}", "{[INPUT]}")
    text = text.replace("{{[OUTPUT]}}", "{[OUTPUT]}")
    return text
