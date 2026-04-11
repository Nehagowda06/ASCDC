import requests


class ASCDCClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def reset(self):
        return requests.post(f"{self.base_url}/reset").json()

    def step(self, action):
        return requests.post(f"{self.base_url}/step", json=action).json()
