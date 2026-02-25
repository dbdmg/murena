"""
OSS Client - Support for local Hugging Face models.
Provides a LangChain-compatible interface for direct inference without an external server.
"""
from typing import Any, List, Optional
import torch
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage, 
    BaseMessage, 
    HumanMessage, 
    SystemMessage
)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr

# Lazy import to avoid crashing if dependencies are missing during initial app loading
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

class ChatOSS(BaseChatModel):
    """
    Local instantiation of a Hugging Face model using Transformers.
    Implements LangChain BaseChatModel to be used by agents.
    """
    
    model_id: str = Field(..., description="Hugging Face model ID or path.")
    temperature: float = Field(0.0, description="Sampling temperature.")
    max_tokens: int = Field(1024, description="Maximum number of tokens to generate.")
    device: str = Field("auto", description="Device to use for inference (cpu, mps, cuda).")
    
    _pipeline: Any = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not HAS_TRANSFORMERS:
            raise ImportError(
                "Mancano i pacchetti 'transformers' e 'torch'. "
                "Per favore installali con: pip install transformers torch accelerate"
            )
        self._init_backend()

    def _init_backend(self):
        """Initializes the Hugging Face pipeline."""
        if self.device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        else:
            device = self.device

        print(f"[OSS] Caricamento modello {self.model_id} su {device}...")
        
        tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        
        # Determine optimal dtype for the device
        dtype = torch.float16 if device != "cpu" else torch.float32
        
        model_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": dtype
        }
        
        # device_map="auto" is recommended for multi-GPU or large models (requires accelerate)
        if device != "mps" and device != "cpu":
            model_kwargs["device_map"] = "auto"
        
        model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)
        
        if device == "mps":
            model = model.to("mps")
            
        self._pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device=0 if device == "cuda" else (-1 if device == "cpu" else device)
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Core execution logic for LangChain integration."""
        
        # Use tokenizer's chat template if available
        if hasattr(self._pipeline.tokenizer, "apply_chat_template"):
            hf_messages = []
            for m in messages:
                role = "system" if isinstance(m, SystemMessage) else \
                       "user" if isinstance(m, HumanMessage) else "assistant"
                hf_messages.append({"role": role, "content": m.content})
            
            prompt = self._pipeline.tokenizer.apply_chat_template(
                hf_messages, tokenize=False, add_generation_prompt=True
            )
        else:
            # Traditional fallback
            prompt = ""
            for m in messages:
                role = "User" if isinstance(m, HumanMessage) else \
                       "Assistant" if isinstance(m, AIMessage) else "System"
                prompt += f"{role}: {m.content}\n"
            prompt += "Assistant: "

        # Generation configuration
        gen_config = {
            "max_new_tokens": self.max_tokens,
            "temperature": max(self.temperature, 0.01) if self.temperature > 0 else 0,
            "do_sample": self.temperature > 0,
            "return_full_text": False,
            "pad_token_id": self._pipeline.tokenizer.eos_token_id
        }
        gen_config.update(kwargs)

        outputs = self._pipeline(prompt, **gen_config)
        content = outputs[0]["generated_text"]
        
        generation = ChatGeneration(message=AIMessage(content=content.strip()))
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        """Identifier for LangChain."""
        return "huggingface_oss_local"
