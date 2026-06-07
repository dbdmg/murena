from openai import OpenAI
import os

client = OpenAI(
    base_url=os.getenv("OPENAI_TEST_BASE_URL", "http://localhost:8081/v1"),
    api_key=os.getenv("OPENAI_TEST_API_KEY", "EMPTY"),
)

models = client.models.list()
model = models.data[0].id

print("Model:", model)

resp = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "Rispondi in modo molto breve."},
        {"role": "user", "content": "Scrivi 'ok' e una micro-spiegazione di 5 parole."}
    ],
    temperature=0.0,
    max_tokens=64,
    # Only include non-standard `chat_template_kwargs` when explicitly allowed
    # (e.g. when testing against a local server). Set env var
    # `ALLOW_CHAT_TEMPLATE_KWARGS=1` to enable.
    **({"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}} if (
        os.getenv("ALLOW_CHAT_TEMPLATE_KWARGS") == "1" or "localhost" in client.base_url
    ) else {}),
)

print("Output:")
print(resp.choices[0].message.content)