from typing import List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings

AGENT_MODELS = settings.agent_models
from app.services.llm.agents.base import BaseAgent
from app.services.llm.agents.schema import ConsistencyAgentResult, PromptRecord
from app.services.llm.langchain_client import get_llm, invoke_with_langfuse
from app.services.llm.prompt_loader import get_system_prompt, get_user_template
from app.utils.decorators import handle_agent_error, log_llm_usage
from app.utils.json_parser import safe_extract_json


# Modello per la risposta strutturata
class ConsistencyResponse(BaseModel):
    requirements: List[str] = Field(
        default_factory=list, description="Lista dei requisiti consolidati"
    )


class ConsistencyAgent(BaseAgent):
    name = "consistency-agent"

    def __init__(self, model_name: str = None):
        resolved_model = (
            model_name
            or AGENT_MODELS.get("consistency_agent")
            or AGENT_MODELS.get("default")
        )
        self.llm = get_llm(model_name=resolved_model)

        self.system_prompt = get_system_prompt("consistency_agent")
        self.user_template = get_user_template("consistency_agent")

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_content}"),
                ("user", "{user_content}"),
            ]
        )
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser

    @log_llm_usage
    @handle_agent_error(
        fallback_value=ConsistencyAgentResult(
            raw_text="{}", prompt=None
        )
    )
    def run(
        self,
        query: str,
        typologies: List[str],
        locations: List[str],
        normative_info: str,
        ape_info: str,
    ) -> ConsistencyAgentResult:
        prompt_inputs = {
            "query": query,
            "typologies": ", ".join(typologies) if typologies else "Nessuna specifica",
            "locations": ", ".join(locations) if locations else "Nessuna specifica",
            "normative_info": normative_info or "Nessuna specifica",
            "ape_info": ape_info or "Nessuna specifica",
        }

        user_text = self.render_template(self.user_template, **prompt_inputs).strip()
        full_text = f"[SYSTEM]\n{self.system_prompt}\n\n[USER]\n{user_text}"

        response_text = invoke_with_langfuse(
            self.chain,
            {
                "system_content": self.system_prompt,
                "user_content": user_text,
            },
        )

        return ConsistencyAgentResult(
            raw_text=response_text,
            prompt=PromptRecord(
                system=self.system_prompt.strip(),
                user=user_text,
                full_text=full_text,
            ),
        )
