from .client import api_key, complete_text, get_client


def generate_visual_prompt(memory_text, style):
    clean_text = " ".join(memory_text.split())
    if not api_key():
        return (
            f"A {style.lower()} personal memory illustration inspired only by: {clean_text}. "
            "No invented people, locations, or events; natural lighting and authentic details."
        ), "demo"
    prompt = complete_text(
        "Write one concise image-generation prompt for a personal memory. "
        "Use only the supplied facts and do not infer identity, emotion, or location. "
        f"Visual style: {style}. Memory: {clean_text}",
        temperature=0.4,
    )
    return prompt, "ai"


def generate_visual_image(prompt):
    """Optional image generation. Requires an API key and a vision/image-capable model setup."""
    client = get_client()
    if client is None:
        raise RuntimeError("Add OPENAI_API_KEY to generate an image.")
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as error:
        raise RuntimeError(f"Image generation is unavailable: {error}") from error
