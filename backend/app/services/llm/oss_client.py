"""
OSS Client - Support for local Hugging Face models.
Provides a LangChain-compatible interface for direct inference without an external server.
"""
import torch
import os
from app.core.config import settings
from typing import Any, List, Optional, Type, Union, Literal, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.messages import (
    AIMessage, 
    BaseMessage, 
    HumanMessage, 
    SystemMessage
)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr, BaseModel

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, GenerationConfig
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
        
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, 
            trust_remote_code=True,
            token=settings.HF_TOKEN if settings.HF_TOKEN else None
        )
        
        # Determine optimal dtype for the device
        # Use bfloat16 for Ampere GPUs (like RTX A6000) for better stability and speed
        if device == "cuda" and torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] >= 8:
            dtype = torch.bfloat16
        elif device != "cpu":
            dtype = torch.float16
        else:
            dtype = torch.float32
        
        model_kwargs = {
            "trust_remote_code": True,
            "token": settings.HF_TOKEN if settings.HF_TOKEN else None
        }
        
        # device_map="auto" is recommended for multi-GPU or large models (requires accelerate)
        if device == "cuda":
            # Detect ALL available GPUs and set memory limits with buffer
            num_gpus = torch.cuda.device_count()
            max_memory = {}
            for i in range(num_gpus):
                free_mem_bytes, _ = torch.cuda.mem_get_info(i)
                # Reserve 4 GB buffer per GPU for activations, KV cache, etc.
                reserve_buffer = 4 * 1024**3 
                available_gb = max((free_mem_bytes - reserve_buffer) // (1024**3), 2)
                max_memory[i] = f"{available_gb}GiB"
            
            print(f"[OSS] Configurazione multi-GPU: {max_memory}")

            # Create offload folder if it doesn't exist
            offload_folder = os.path.join(settings.CACHE_DIR, "offload")
            os.makedirs(offload_folder, exist_ok=True)

            model_kwargs.update({
                "device_map": "auto",
                "max_memory": max_memory,
                "torch_dtype": dtype,
                "offload_folder": offload_folder,
            })

            # Apply quantization if enabled in settings
            if settings.OSS_LOAD_IN_4BIT and "gpt-oss" not in self.model_id.lower():
                from transformers import BitsAndBytesConfig
                # Use bfloat16 as compute dtype for 4-bit quantization on Ampere+ GPUs
                compute_dtype = torch.bfloat16 if torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
                
                print(f"[OSS] Applicazione quantizzazione 4-bit (NF4) con compute_dtype={compute_dtype}")
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=compute_dtype,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                model_kwargs["quantization_config"] = quantization_config
            elif not settings.OSS_LOAD_IN_4BIT and "gpt-oss" not in self.model_id.lower():
                # Optional: could add 8-bit support here if needed
                # For now, if 4-bit is off, we load in full precision (or half depending on dtype)
                pass
        elif device == "mps":
             # MPS doesn't support 8-bit yet
             model_kwargs["torch_dtype"] = torch.float16
        else:
             model_kwargs["torch_dtype"] = torch.float32
        
        model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)
        
        # If model was loaded with accelerate (device_map), we MUST NOT manually move it
        # or pass device to the pipeline.
        pipe_kwargs = {
            "task": "text-generation",
            "model": model,
            "tokenizer": tokenizer,
        }
        
        if "device_map" not in model_kwargs:
            if device == "mps":
                model = model.to("mps")
            
            # Direct device assignment for standard loading
            pipe_kwargs["device"] = 0 if device == "cuda" else (-1 if device == "cpu" else device)
            
        self._pipeline = pipeline(**pipe_kwargs)

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
        do_sample = self.temperature > 0
        
        # Generation-related parameters
        gen_params = {
            "max_new_tokens": self.max_tokens,
            "do_sample": do_sample,
            "pad_token_id": self._pipeline.tokenizer.eos_token_id
        }
        if do_sample:
            gen_params["temperature"] = max(self.temperature, 0.01)

        # Pipeline-specific parameters (not generation config)
        pipeline_params = {
            "return_full_text": False
        }

        # Handling to avoid deprecation warning: either pass a config object OR individual parameters
        if "generation_config" in kwargs:
            gen_config_obj = kwargs.pop("generation_config")
            if isinstance(gen_config_obj, dict):
                gen_config_obj = GenerationConfig.from_dict(gen_config_obj)
            
            # Update existing config with our defaults
            for k, v in gen_params.items():
                setattr(gen_config_obj, k, v)
            
            pipeline_params["generation_config"] = gen_config_obj
        else:
            # Pass individual parameters if no config object is provided
            pipeline_params.update(gen_params)

        # Update with remaining kwargs
        pipeline_params.update(kwargs)

        outputs = self._pipeline(prompt, **pipeline_params)
        content = outputs[0]["generated_text"]
        
        generation = ChatGeneration(message=AIMessage(content=content.strip()))
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        """Identifier for LangChain."""
        return "huggingface_oss_local"

    def with_structured_output(
        self,
        schema: Union[Dict, Type[BaseModel]],
        *,
        method: Optional[Literal["function_calling", "json_mode"]] = None,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable:
        """
        Implementazione di with_structured_output per modelli locali.
        Ignora il metodo 'function_calling' e forza il parsing JSON dell'output testuale.
        """
        from langchain_core.runnables import RunnableLambda
        from app.utils.json_parser import safe_extract_json
        from pydantic import BaseModel
        
        def parse_output(generation: ChatResult) -> Any:
            # LangChain passa ChatResult a questo punto se concatenato a un LLM
            # o BaseMessage se concatenato a un ChatModel
            if hasattr(generation, "generations"):
                text = generation.generations[0].message.content
            else:
                # Se riceve direttamente il messaggio (e.g. AIMessage)
                text = generation.content
                
            pydantic_schema = schema if isinstance(schema, type) and issubclass(schema, BaseModel) else None
            return safe_extract_json(text, schema=pydantic_schema)

        return self | RunnableLambda(parse_output)
