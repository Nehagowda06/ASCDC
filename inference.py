import os
from openai import OpenAI

# --- ENV VARS ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
)

def run():
    print("START")

    for step in range(10):
        prompt = "Decide next action based on system state"

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a system control agent."},
                {"role": "user", "content": prompt}
            ],
        )

        action = response.choices[0].message.content
        reward = 0  # replace later with real env

        print(f"STEP {step} | action={action} | reward={reward}")

    print("END")


if __name__ == "__main__":
    run()
