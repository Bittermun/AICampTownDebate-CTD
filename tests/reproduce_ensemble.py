
from src.models import JudgeFactory
import asyncio

def test():
    # Create ensemble
    judge = JudgeFactory.create_ensemble(["ollama:qwen2.5:1.5b", "ollama:qwen2.5:1.5b"], name="TestCouncil")
    judge.load_model()
    
    topic = "Test Topic"
    arg_a = "Renewables are good."
    arg_b = "Nuclear is good."
    
    try:
        res = judge.evaluate(topic, arg_a, arg_b, 1)
        print(f"Success! Confidences: {res.confidence_a}/{res.confidence_b}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test()
