
import re
import json

def parse_response(text: str) -> tuple[float, float, str]:
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            conf_a = float(data.get("confidence_a", 0.5))
            conf_b = float(data.get("confidence_b", 0.5))
            total = conf_a + conf_b
            if total > 0:
                conf_a /= total
                conf_b /= total
            return conf_a, conf_b, data.get("reasoning", text[:200])
    except Exception as e:
        print(f"JSON Parse failed: {e}")
    
    numbers = re.findall(r'0\.\d+', text)
    if len(numbers) >= 2:
        conf_a, conf_b = float(numbers[0]), float(numbers[1])
        total = conf_a + conf_b
        if total > 0:
            return conf_a / total, conf_b / total, text[:200]
    
    return 0.5, 0.5, f"[PARSE_FAILED] {text[:200]}"

# Test cases from logs
test1 = """
{
  "confidence_a": 0.4,
  "confidence_b": 0.6,
  "reasoning": "Argument A focuses on renewables..."
}
"""

test2 = """
Judgment:
Confidence A: 0.3
Confidence B: 0.7
Reasoning: ...
"""

test3 = """
{
  "confidence_a": 0.3,
  "confidence_b": 0.7,
  "reasoning": "Consistent with research..."
}
"""

print(f"Test 1: {parse_response(test1)}")
print(f"Test 2: {parse_response(test2)}")
print(f"Test 3: {parse_response(test3)}")
