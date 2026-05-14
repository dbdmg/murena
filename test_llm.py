from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8081/v1",
    api_key="EMPTY",
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
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)

print("Output:")
print(resp.choices[0].message.content)