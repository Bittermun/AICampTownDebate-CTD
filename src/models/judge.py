"""
Judge: Modular evaluation system for debate arguments.
Supports: single LLMs, ensembles, and consensus-based voting.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Protocol
import json
import re
from abc import ABC, abstractmethod
from pydantic import ValidationError
from .response_models import JudgmentResponse, MultiDimensionJudgment, AllocationJudgment
from .judge_prompts import MULTI_DIMENSION_SYSTEM, MULTI_DIMENSION_PROMPT, COMPARATIVE_CONTEXT_BLOCK


@dataclass
class Judgment:
    confidence_a: float  # 0.0 - 1.0
    confidence_b: float  # 0.0 - 1.0
    reasoning: str
    judge_id: str
    round_id: int
    sub_judgments: List["Judgment"] = field(default_factory=list)


class BaseJudge(ABC):
    """Abstract interface for all judge types."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def load_model(self):
        pass

    @abstractmethod
    def evaluate(
        self,
        topic: str,
        argument_a: str,
        argument_b: str,
        round_id: int,
    ) -> Judgment:
        pass

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def unload_model(self):
        pass


@dataclass
class JudgeConfig:
    model_path: str  # "stub", "ollama:model_name", or path to GGUF
    name: str = "Judge"
    system_prompt: Optional[str] = None
    gpu_layers: int = 15
    context_size: int = 2048
    randomize_argument_order: bool = False  # Mitigate positional bias
    ensemble_judge: bool = True  # Run two swapped evals and average (eliminates positional bias)
    strict_runtime: bool = True


class LLMJudge(BaseJudge):
    """
    Evaluates debate arguments using a single LLM.
    """
    
    def __init__(self, config: JudgeConfig):
        self.config = config
        self._name = config.name
        
        # Determine backend
        if config.model_path == "stub" or config.model_path.startswith("stub:"):
            self._backend = "stub"
        elif config.model_path.startswith("ollama:"):
            self._backend = "ollama"
            self._ollama_model = config.model_path.split(":", 1)[1]
        elif config.model_path.startswith("vllm:"):
            self._backend = "vllm"
            self._vllm_model = config.model_path.split(":", 1)[1]
        elif config.model_path.startswith("openai:"):
            self._backend = "openai_compat"
            self._openai_model = config.model_path.split(":", 1)[1]
        else:
            self._backend = "llama_cpp"
        
        self._model = None
        self._ollama = None
        self._vllm = None
        self._openai = None
    
    @property
    def name(self) -> str:
        return self._name

    def load_model(self):
        if self._backend == "stub":
            print(f"[{self.name}] Model loaded (stub)")
            return
        
        if self._backend == "ollama":
            from .ollama_backend import get_backend, OllamaConfig
            self._ollama = get_backend(OllamaConfig(model=self._ollama_model))
            if self._ollama.is_available():
                print(f"[{self.name}] Ollama connected: {self._ollama_model}")
            else:
                msg = f"[{self.name}] Ollama not available: {self._ollama_model}"
                if self.config.strict_runtime:
                    raise RuntimeError(msg)
                print(f"{msg}, falling back to stub")
                self._backend = "stub"
            return
        
        if self._backend == "vllm":
            from .vllm_backend import VLLMBackend, VLLMConfig
            self._vllm = VLLMBackend(VLLMConfig(model=self._vllm_model))
            if self._vllm.is_available():
                print(f"[{self.name}] vLLM connected: {self._vllm_model}")
            else:
                msg = f"[{self.name}] vLLM not available: {self._vllm_model}"
                if self.config.strict_runtime:
                    raise RuntimeError(msg)
                print(f"{msg}, falling back to stub")
                self._backend = "stub"
            return

        if self._backend == "openai_compat":
            from .openai_compat_backend import OpenAICompatBackend, OpenAICompatConfig
            self._openai = OpenAICompatBackend(OpenAICompatConfig(model=self._openai_model))
            if self._openai.is_available():
                print(f"[{self.name}] OpenAI-compatible endpoint connected: {self._openai_model}")
            else:
                msg = f"[{self.name}] OpenAI-compatible endpoint unavailable: {self._openai_model}"
                if self.config.strict_runtime:
                    raise RuntimeError(msg)
                print(f"{msg}, falling back to stub")
                self._backend = "stub"
            return
        
        
        try:
            from llama_cpp import Llama
            self._model = Llama(
                model_path=self.config.model_path,
                n_gpu_layers=self.config.gpu_layers,
                n_ctx=self.config.context_size,
                verbose=False,
            )
            print(f"[{self.name}] Model loaded: {self.config.model_path}")
        except ImportError:
            msg = f"[{self.name}] llama-cpp-python not installed"
            if self.config.strict_runtime:
                raise RuntimeError(msg)
            print(f"{msg}, using stub")
            self._backend = "stub"

    def _generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 512, json_mode: bool = False, temperature: float = 0.8) -> "GenerationResult":
        """Unified sync generation call."""
        if self._backend == "ollama":
            return self._ollama.generate(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "vllm":
            return self._vllm.generate(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "openai_compat":
            return self._openai.generate(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        else:
            # Fallback for stub/llama_cpp (simplified)
            from .ollama_backend import GenerationResult
            if self._backend == "stub":
                return GenerationResult(
                    text=(
                        '{"accuracy_a": 0.55, "accuracy_b": 0.45, '
                        '"responsiveness_a": 0.55, "responsiveness_b": 0.45, '
                        '"development_a": 0.55, "development_b": 0.45, '
                        '"reasoning": "Stub judgment response."}'
                    ),
                    tokens_used=0,
                )
            else:
                output = self._model(
                    f"{system}\n\n{prompt}" if system else prompt,
                    max_tokens=max_tokens,
                    stop=["</s>", "\n\n\n"],
                    echo=False,
                    temperature=temperature,
                )
                return GenerationResult(text=output["choices"][0]["text"].strip(), tokens_used=0)

    async def _generate_async(self, prompt: str, system: Optional[str] = None, max_tokens: int = 512, json_mode: bool = False, temperature: float = 0.8) -> "GenerationResult":
        """Unified async generation call."""
        if self._backend == "ollama":
            return await self._ollama.generate_async(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "vllm":
            return await self._vllm.generate_async(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "openai_compat":
            return await self._openai.generate_async(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        else:
            return self._generate(prompt, system, max_tokens, json_mode, temperature)
    
    def evaluate(
        self,
        topic: str,
        argument_a: str,
        argument_b: str,
        round_id: int,
        prior_judgment: Optional["Judgment"] = None,
    ) -> Judgment:
        """Evaluate arguments using multi-dimension scoring.
        
        Scores on 3 dimensions: accuracy, responsiveness, development.
        Falls back to single-score if multi-dim parsing fails.
        If prior_judgment is provided, injects comparative context so the judge
        can penalize stagnant arguments (Phase 3: Comparative Memory).
        """
        import random
        
        # Randomize argument order to mitigate positional bias
        swapped = False
        if self.config.randomize_argument_order:
            swapped = random.choice([True, False])
        
        if swapped:
            first_arg, second_arg = argument_b, argument_a
            first_label, second_label = "B", "A"
        else:
            first_arg, second_arg = argument_a, argument_b
            first_label, second_label = "A", "B"
        
        # Build comparative context block if prior scores exist
        if prior_judgment is not None:
            prior_conf_a = prior_judgment.confidence_a
            prior_conf_b = prior_judgment.confidence_b
            prior_gap = abs(prior_conf_a - prior_conf_b)
            prior_context = COMPARATIVE_CONTEXT_BLOCK.format(
                prior_conf_a=prior_conf_a,
                prior_conf_b=prior_conf_b,
                prior_gap=prior_gap,
            )
        else:
            prior_context = ""  # No prior scores: blank, prompt renders normally
        
        # Use multi-dimension prompt — respects custom system_prompt from JudgeConfig if set
        system = self.config.system_prompt or MULTI_DIMENSION_SYSTEM
        prompt = MULTI_DIMENSION_PROMPT.format(
            topic=topic,
            first_arg=first_arg[:1500],  # Truncate for context
            second_arg=second_arg[:1500],
            first_label=first_label,
            second_label=second_label,
            first_label_lower=first_label.lower(),
            second_label_lower=second_label.lower(),
            prior_context=prior_context,
        )
        
        # Generate based on backend
        result = self._generate(prompt, system=system, max_tokens=500, json_mode=True, temperature=0.0)
        j1 = self._validate_multidim_response(result.text, round_id, swapped=swapped)

        # Ensemble: run second evaluation with swapped order and average splits
        if self.config.ensemble_judge:
            swapped2 = not swapped
            first2, second2 = (argument_b, argument_a) if swapped2 else (argument_a, argument_b)
            label2_first, label2_second = ("B", "A") if swapped2 else ("A", "B")
            prompt2 = MULTI_DIMENSION_PROMPT.format(
                topic=topic,
                first_arg=first2[:1500],
                second_arg=second2[:1500],
                first_label=label2_first,
                second_label=label2_second,
                first_label_lower=label2_first.lower(),
                second_label_lower=label2_second.lower(),
                prior_context=prior_context,
            )
            result2 = self._generate(prompt2, system=system, max_tokens=500, json_mode=True, temperature=0.0)
            j2 = self._validate_multidim_response(result2.text, round_id, swapped=swapped2)
            # Average the confidences (already account for swap in _validate_multidim_response)
            avg_a = (j1.confidence_a + j2.confidence_a) / 2
            avg_b = 1.0 - avg_a
            return Judgment(
                confidence_a=round(avg_a, 4),
                confidence_b=round(avg_b, 4),
                reasoning=f"[ENSEMBLE] Run1: A={j1.confidence_a:.3f}/B={j1.confidence_b:.3f} Run2: A={j2.confidence_a:.3f}/B={j2.confidence_b:.3f} | {j1.reasoning[:200]}",
                judge_id=self.name,
                round_id=round_id,
            )
        return j1
    
    def _validate_multidim_response(self, text: str, round_id: int, swapped: bool = False) -> Judgment:
        """Parse multi-dimension response, fall back to single-score if needed."""
        
        # Strip <think> tags generated by reasoning models (e.g. Qwen-32B on Groq)
        text = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.DOTALL).strip()
        
        # First, try to repair truncated JSON
        repaired_text = self._repair_truncated_json(text)

        # --- Try AllocationJudgment first (zero-sum split format) ---
        try:
            alloc = AllocationJudgment.model_validate_json(repaired_text)
            conf_a, conf_b = alloc.weighted_confidence()
            if swapped:
                conf_a, conf_b = conf_b, conf_a
            reasoning = (
                f"[ALLOC] Acc: A={alloc.accuracy_split}%/B={100-alloc.accuracy_split}%, "
                f"Resp: A={alloc.responsiveness_split}%/B={100-alloc.responsiveness_split}%, "
                f"Dev: A={alloc.development_split}%/B={100-alloc.development_split}% | "
                f"{alloc.reasoning[:300]}"
            )
            return Judgment(
                confidence_a=conf_a,
                confidence_b=conf_b,
                reasoning=reasoning,
                judge_id=self.name,
                round_id=round_id,
            )
        except Exception:
            pass  # Fall through to legacy MultiDimensionJudgment path

        try:
            # Try multi-dimension parse first
            parsed = MultiDimensionJudgment.model_validate_json(repaired_text)
            
            # Calculate weighted confidence
            conf_a, conf_b = parsed.weighted_confidence()
            
            # Swap back if arguments were presented in reversed order
            if swapped:
                conf_a, conf_b = conf_b, conf_a
            
            # Build detailed reasoning
            reasoning = (
                f"[MULTI-DIM] Acc: A={parsed.accuracy_a:.0%}/B={parsed.accuracy_b:.0%}, "
                f"Resp: A={parsed.responsiveness_a:.0%}/B={parsed.responsiveness_b:.0%}, "
                f"Dev: A={parsed.development_a:.0%}/B={parsed.development_b:.0%} | "
                f"{parsed.reasoning[:200]}"
            )
            
            return Judgment(
                confidence_a=conf_a,
                confidence_b=conf_b,
                reasoning=reasoning,
                judge_id=self.name,
                round_id=round_id
            )
        except ValidationError:
            # Try regex rescue on multi-dim fields before falling back to
            # single-score format (which uses completely different keys and
            # would 0.5/0.5 flatline on every multi-dim response).
            rescued = self._rescue_multidim_regex(text, round_id, swapped=swapped)
            if rescued is not None:
                return rescued
            # Only fall back to single-score if regex rescue also fails
            return self._validate_response(text, round_id, swapped=swapped)

    

    def _rescue_multidim_regex(self, text: str, round_id: int, swapped: bool = False):
        """Regex-based rescue for malformed multi-dimension JSON.

        Tries allocation split format first (accuracy_split etc.), then falls
        back to the legacy float format (accuracy_a, accuracy_b etc.).

        When the LLM output has a minor formatting error (trailing comma,
        unclosed string) that breaks model_validate_json, this method
        extracts the 6 dimension scores and the reasoning string directly
        from the raw text and calculates weighted confidence manually.

        Returns a Judgment on success, None if rescue fails.
        """
        try:
            # Try allocation split format first
            def _extract_int(field):
                m = re.search(r'"' + re.escape(field) + r'"\s*:\s*\[?(?:"|\')?([0-9]+)', text)
                return int(m.group(1)) if m else None

            acc_split  = _extract_int("accuracy_split")
            resp_split = _extract_int("responsiveness_split")
            dev_split  = _extract_int("development_split")

            if acc_split is not None and resp_split is not None and dev_split is not None:
                # Clamp to valid range
                acc_split  = max(0, min(100, acc_split))
                resp_split = max(0, min(100, resp_split))
                dev_split  = max(0, min(100, dev_split))
                raw_a = 0.4*(acc_split/100) + 0.3*(resp_split/100) + 0.3*(dev_split/100)
                margin = 2*raw_a - 1
                conf_a = max(0.05, min(0.95, 0.5 + margin * 0.4))
                conf_b = 1.0 - conf_a
                if swapped:
                    conf_a, conf_b = conf_b, conf_a
                reasoning_match = re.search(
                    r'"reasoning"\s*:\s*"(.*?)"(?:\s*[,}]|$)', text, re.DOTALL
                )
                reasoning_text = reasoning_match.group(1) if reasoning_match else "[RESCUED/ALLOC]"
                reasoning = (
                    f"[ALLOC/RESCUED] Acc: A={acc_split}%/B={100-acc_split}%, "
                    f"Resp: A={resp_split}%/B={100-resp_split}%, "
                    f"Dev: A={dev_split}%/B={100-dev_split}% | {reasoning_text[:200]}"
                )
                return Judgment(
                    confidence_a=conf_a,
                    confidence_b=conf_b,
                    reasoning=reasoning,
                    judge_id=self.name,
                    round_id=round_id,
                )
        except Exception:
            pass

        # Fall back to legacy float format rescue
        try:
            def _extract_score(field):
                m = re.search(r'"' + re.escape(field) + r'"\s*:\s*([0-9]*\.?[0-9]+)', text)
                return float(m.group(1)) if m else None

            accuracy_a    = _extract_score("accuracy_a")
            accuracy_b    = _extract_score("accuracy_b")
            responsive_a  = _extract_score("responsiveness_a")
            responsive_b  = _extract_score("responsiveness_b")
            development_a = _extract_score("development_a")
            development_b = _extract_score("development_b")

            # Need at least accuracy scores to produce a meaningful result
            if accuracy_a is None or accuracy_b is None:
                return None

            # Fill missing dimensions with 0.5 (neutral) so partial LLM
            # responses still produce a useful signal rather than failing
            responsive_a  = responsive_a  if responsive_a  is not None else 0.5
            responsive_b  = responsive_b  if responsive_b  is not None else 0.5
            development_a = development_a if development_a is not None else 0.5
            development_b = development_b if development_b is not None else 0.5

            # Same weighted_confidence math as MultiDimensionJudgment
            raw_a = 0.4 * accuracy_a + 0.3 * responsive_a + 0.3 * development_a
            raw_b = 0.4 * accuracy_b + 0.3 * responsive_b + 0.3 * development_b
            margin = raw_a - raw_b
            conf_a = max(0.05, min(0.95, 0.5 + margin * 0.4))
            conf_b = 1.0 - conf_a

            if swapped:
                conf_a, conf_b = conf_b, conf_a

            # Extract reasoning string (non-greedy, stops at closing quote)
            reasoning_match = re.search(
                r'"reasoning"\s*:\s*"(.*?)"(?:\s*[,}]|$)', text, re.DOTALL
            )
            reasoning_text = (
                reasoning_match.group(1) if reasoning_match
                else "[RESCUED - reasoning truncated]"
            )

            reasoning = (
                f"[MULTI-DIM/RESCUED] Acc: A={accuracy_a:.0%}/B={accuracy_b:.0%}, "
                f"Resp: A={responsive_a:.0%}/B={responsive_b:.0%}, "
                f"Dev: A={development_a:.0%}/B={development_b:.0%} | "
                f"{reasoning_text[:200]}"
            )

            return Judgment(
                confidence_a=conf_a,
                confidence_b=conf_b,
                reasoning=reasoning,
                judge_id=self.name,
                round_id=round_id,
            )
        except Exception:
            return None

    def _repair_truncated_json(self, text: str) -> str:
        """Attempt to repair truncated JSON by completing missing fields and brackets.
        
        Common truncation patterns for multi-dimension judgments:
        - Cut off mid-field value: {"accuracy_a": 0.8, "accuracy_b": 0.
        - Cut off mid-field name: {"accuracy_a": 1.0, "responsiveness_a
        - Missing closing brace: {"accuracy_a": 1.0, ...}
        """
        # Find the JSON object in the text
        json_match = re.search(r'\{.*', text, re.DOTALL)
        if not json_match:
            return text
        
        json_str = json_match.group().strip()
        
        # Check if JSON is already valid
        try:
            json.loads(json_str)
            return json_str  # Already valid
        except json.JSONDecodeError:
            pass
        
        # Repair strategies:
        # 1. If ends with incomplete field name, remove it and close
        # 2. If ends with incomplete value, add default and close
        # 3. Add missing required fields with defaults
        
        # Remove trailing incomplete field (e.g., ", "responsiveness_a)
        json_str = re.sub(r',\s*"[^"]*$', '', json_str)
        
        # Remove trailing incomplete value (e.g., ": 0.)
        json_str = re.sub(r':\s*[\d.]*$', ': 0.5', json_str)
        
        # Ensure it ends with proper JSON structure
        if not json_str.endswith('}'):
            # Count open braces
            open_braces = json_str.count('{') - json_str.count('}')
            # Add missing required fields if they're not present
            required_fields = [
                ('accuracy_a', 0.5), ('accuracy_b', 0.5),
                ('responsiveness_a', 0.5), ('responsiveness_b', 0.5),
                ('development_a', 0.5), ('development_b', 0.5),
                ('reasoning', 'Partial judgment recovered')
            ]
            for field_name, default in required_fields:
                if f'"{field_name}"' not in json_str:
                    if isinstance(default, str):
                        json_str = json_str.rstrip() + f', "{field_name}": "{default}"'
                    else:
                        json_str = json_str.rstrip() + f', "{field_name}": {default}'
            
            # Close any open braces
            json_str += '}' * max(0, open_braces)
        
        # Final validation attempt
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            # If still invalid, return original
            return text
    
    def _validate_response(self, text: str, round_id: int, swapped: bool = False) -> Judgment:
        """Validate LLM response with Pydantic. Raises ValueError on failure.
        
        If swapped=True, the arguments were presented in B/A order, so we need
        to swap the confidence scores back to A/B order.
        """
        # Strip <think> tags generated by reasoning models (e.g. Qwen-32B on Groq)
        text = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.DOTALL).strip()
        
        try:
            # Try direct Pydantic parse first
            parsed = JudgmentResponse.model_validate_json(text)
            # Clamp to prevent extreme scores (10-90% range)
            conf_a = max(0.10, min(0.90, parsed.confidence_a))
            conf_b = max(0.10, min(0.90, parsed.confidence_b))
            
            # Swap scores back if arguments were presented in reversed order
            if swapped:
                conf_a, conf_b = conf_b, conf_a
            
            return Judgment(
                confidence_a=conf_a,
                confidence_b=conf_b,
                reasoning=parsed.reasoning,
                judge_id=self.name,
                round_id=round_id
            )
        except ValidationError:
            # Fallback: try to extract JSON from text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    parsed = JudgmentResponse.model_validate_json(json_match.group())
                    # Clamp to prevent extreme scores (10-90% range)
                    conf_a = max(0.10, min(0.90, parsed.confidence_a))
                    conf_b = max(0.10, min(0.90, parsed.confidence_b))
                    
                    if swapped:
                        conf_a, conf_b = conf_b, conf_a
                    
                    return Judgment(
                        confidence_a=conf_a,
                        confidence_b=conf_b,
                        reasoning=parsed.reasoning,
                        judge_id=self.name,
                        round_id=round_id
                    )
                except ValidationError:
                    pass
            
            # Final fallback: reject the round
            raise ValueError(f"[VALIDATION_FAILED] Could not parse: {text[:300]}")
    
    def _parse_response(self, text: str) -> tuple[float, float, str]:
        """Legacy parser for backwards compatibility with non-Ollama backends."""
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
                return conf_a, conf_b, data.get("reasoning", text[:500])
        except Exception:
            pass
        
        numbers = re.findall(r'\d+\.\d+|\d+', text)
        if len(numbers) >= 2:
            try:
                conf_a, conf_b = float(numbers[0]), float(numbers[1])
                total = conf_a + conf_b
                if total > 0:
                    return conf_a / total, conf_b / total, f"[REGEX_PARSE] {text[:500]}"
            except ValueError:
                pass
        
        return 0.5, 0.5, f"[PARSE_FAILED] {text[:500]}"
    
    def generate_judgment(
        self,
        prompt: str,
        system: str,
        round_id: int,
    ) -> Judgment:
        """Public method for generating judgments with custom prompts.
        
        This is the public interface for ConsensusJudge and other consumers
        that need to run custom prompts through the judge. Eliminates need
        to access private _ollama or _parse_response methods.
        """
        if self._backend == "stub":
            return Judgment(
                confidence_a=0.55,
                confidence_b=0.45,
                reasoning="[STUB] Synthesis complete.",
                judge_id=self.name,
                round_id=round_id
            )
        
        if self._backend == "ollama":
            result = self._ollama.generate(prompt, system=system, max_tokens=500, json_mode=True, temperature=0.0)
            return self._validate_response(result.text, round_id)
        
        if self._backend == "vllm":
            result = self._vllm.generate(prompt, system=system, max_tokens=500, json_mode=True, temperature=0.0)
            return self._validate_response(result.text, round_id)
        
        if self._backend == "openai_compat":
            result = self._openai.generate(prompt, system=system, max_tokens=500, json_mode=True, temperature=0.0)
            return self._validate_response(result.text, round_id)
        
        # llama_cpp fallback
        output = self._model(f"{system}\n\n{prompt}", max_tokens=200, stop=["</s>"], echo=False)
        return self._validate_response(output["choices"][0]["text"].strip(), round_id)

    def reset(self):
        pass

    def unload_model(self):
        self._model = None
        self._ollama = None
        self._vllm = None
        self._openai = None


class EnsembleJudge(BaseJudge):
    """
    Combines multiple judges and averages their results.
    """
    
    def __init__(self, judges: List[BaseJudge], name: str = "EnsembleJudge"):
        self.judges = judges
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name

    def load_model(self):
        for judge in self.judges:
            judge.load_model()

    def evaluate(
        self,
        topic: str,
        argument_a: str,
        argument_b: str,
        round_id: int,
        **kwargs
    ) -> Judgment:
        # Collect judgments, handling individual failures gracefully
        judgments = []
        failed_judges = []
        
        for j in self.judges:
            try:
                judgment = j.evaluate(topic, argument_a, argument_b, round_id, **kwargs)
                judgments.append(judgment)
            except ValueError as e:
                # Sub-judge validation failed - skip but log
                failed_judges.append(f"{j.name}: {str(e)[:100]}")
        
        # If all judges failed, raise to reject the round
        if not judgments:
            raise ValueError(f"[ENSEMBLE_FAILED] All sub-judges failed: {failed_judges}")
        
        avg_a = sum(j.confidence_a for j in judgments) / len(judgments)
        avg_b = sum(j.confidence_b for j in judgments) / len(judgments)
        
        # Build reasoning, noting any failures
        combined_reasoning = "\n".join([
            f"[{j.judge_id}]: {j.reasoning}"
            for j in judgments
        ])
        if failed_judges:
            combined_reasoning += f"\n[SKIPPED]: {len(failed_judges)} judge(s) failed validation"
        
        return Judgment(
            confidence_a=avg_a,
            confidence_b=avg_b,
            reasoning=combined_reasoning,
            judge_id=self.name,
            round_id=round_id,
            sub_judgments=judgments
        )

    def reset(self):
        for judge in self.judges:
            judge.reset()

    def unload_model(self):
        for judge in self.judges:
            judge.unload_model()


class ConsensusJudge(BaseJudge):
    """
    Uses an "Instructor" model to synthesize a final judgment from multiple judges.
    """
    
    def __init__(self, judges: List[BaseJudge], instructor: LLMJudge, name: str = "ConsensusJudge"):
        self.judges = judges
        self.instructor = instructor
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name

    def load_model(self):
        for judge in self.judges:
            judge.load_model()
        self.instructor.load_model()

    def evaluate(
        self,
        topic: str,
        argument_a: str,
        argument_b: str,
        round_id: int,
        **kwargs
    ) -> Judgment:
        # 1. Collect individual judgments, handling failures gracefully
        judgments = []
        failed_judges = []
        
        for j in self.judges:
            try:
                judgment = j.evaluate(topic, argument_a, argument_b, round_id, **kwargs)
                judgments.append(judgment)
            except ValueError as e:
                failed_judges.append(f"{j.name}: {str(e)[:100]}")
        
        # If all sub-judges failed, raise to reject the round
        if not judgments:
            raise ValueError(f"[CONSENSUS_FAILED] All sub-judges failed: {failed_judges}")
        
        # 2. Build synthesis prompt for instructor
        judgments_summary = "\n\n".join([
            f"Judge: {j.judge_id}\nScore: A={j.confidence_a:.2f}, B={j.confidence_b:.2f}\nReasoning: {j.reasoning}"
            for j in judgments
        ])
        
        if failed_judges:
            judgments_summary += f"\n\n[Note: {len(failed_judges)} judge(s) failed validation and were excluded]"
        
        system = (
            "You are a Senior Judge (Instructor). Your task is to synthesize the findings of multiple "
            "sub-judges into a single, definitive judgment. Weigh their arguments and resolve conflicts."
        )
        
        prompt = (
            f"Topic: {topic}\n\n"
            f"--- Sub-Judge Reports ---\n{judgments_summary}\n\n"
            f"Synthesize these reports. If sub-judges disagree, weigh their reasoning. "
            f"Identify which debater successfully pivoted or refuted the other based on these reports. "
            f"Respond in JSON:\n"
            f'{{"confidence_a": 0.X, "confidence_b": 0.Y, "reasoning": "synthetic explanation of the final verdict"}}'
        )
        
        # 3. Use public interface for instructor synthesis
        judgment = self.instructor.generate_judgment(prompt, system, round_id)
        
        judgment.judge_id = self.name
        judgment.sub_judgments = judgments
        return judgment

    def reset(self):
        for judge in self.judges:
            judge.reset()
        self.instructor.reset()

    def unload_model(self):
        for judge in self.judges:
            judge.unload_model()
        self.instructor.unload_model()


# Alias for backward compatibility (defaults to LLMJudge)
class Judge(LLMJudge):
    pass
