from env.environment import ASCDCEnvironment


def test_env_runs():
    env = ASCDCEnvironment(seed=42)
    obs = env.reset()

    for _ in range(10):
        obs, reward, done, info = env.step({"type": "noop"})

    assert True


def test_inference_runs():
    import subprocess
    result = subprocess.run(["python", "inference.py"])
    assert result.returncode == 0
