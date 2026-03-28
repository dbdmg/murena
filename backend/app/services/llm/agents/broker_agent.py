from typing import Any, Optional
import json

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings, AGENT_MODELS
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import AgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage


class BrokerAgent(BaseAgent):
    """
    Agent responsible for comparative synthesis and qualitative reranking.
    Acts as a strategic consultant (broker) to provide initial insights on results.
    """
    name = "broker-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name 
            or AGENT_MODELS.get("broker_agent") 
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("broker_agent")
        self.user_template = get_user_template("broker_agent")

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", self.user_template),
            ]
        )
        self.chain = self.prompt_template | self.llm

    @log_llm_usage
    @handle_agent_error(fallback_value="Currently unable to generate synthesis.")
    def run(self, *, query: str, candidates_data: str) -> str:
        """
        Performs comparative synthesis of the candidates.
        """
        user_text = self.render_template(
            self.user_template,
            query=query,
            candidates_data=candidates_data
        ).strip()
        
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        response = invoke_with_langfuse(
            self.chain,
            {
                "system_content": self.system_prompt,
                "query": query,
                "candidates_data": candidates_data
            }
        )
        
        raw_text = getattr(response, "content", str(response))
        return raw_text
