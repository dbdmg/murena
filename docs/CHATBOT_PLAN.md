# Map Assistant Chatbot - Implementation Plan

## Overview
Conversational AI assistant integrated with the map interface that can answer questions, apply filters, and help users explore properties.

---

## Phase 1: Core Chat Infrastructure

### Backend

#### [NEW] `backend/app/services/llm/agents/chat_agent.py`
```python
class MapChatAgent(BaseAgent):
    """Conversational agent with tool-calling capabilities."""
    
    def __init__(self, tools: List[BaseTool]):
        self.tools = tools
        self.memory = ConversationBufferMemory()
    
    async def stream_response(self, message: str, context: ChatContext):
        """Stream response with potential tool calls."""
```

#### [NEW] `backend/app/api/v1/endpoints/chat.py`
- `POST /api/v1/chat/message` - Send message, get response
- `WebSocket /api/v1/chat/ws` - Real-time streaming

#### [NEW] `backend/app/models/chat.py`
```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    
class ChatContext(BaseModel):
    run_id: str
    current_filters: Dict[str, Any]
    visible_building_ids: List[str]
    selected_building_id: Optional[str]
```

#### [MODIFY] `backend/app/core/config.py`
```python
# Chat Agent Configuration
CHAT_MODEL_FAST: str = "gpt-4o-mini"  # For quick responses
CHAT_MODEL_SMART: str = "gpt-4o"      # For complex reasoning
CHAT_MAX_TOKENS: int = 1024
CHAT_TEMPERATURE: float = 0.7
CHAT_CONTEXT_WINDOW: int = 10         # Messages to keep in context
```

### Frontend

#### [NEW] `frontend/src/contexts/ChatContext.tsx`
- `messages: ChatMessage[]`
- `isStreaming: boolean`
- `sendMessage(text: string)`
- `executeToolAction(action: ToolAction)`

#### [NEW] `frontend/src/components/chat/ChatWidget.tsx`
- Floating/docked chat panel
- Message list with streaming support
- Input with send button

---

## Phase 2: Tool Calling (Actions)

### Backend Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `filter_surface` | Filter by surface area | `min_m2`, `max_m2` |
| `filter_energy_class` | Filter by energy class | `classes: string[]` |
| `filter_zone` | Filter by OMI zone | `zone_name` |
| `select_building` | Highlight a building | `building_id` |
| `zoom_to_building` | Pan & zoom map | `building_id` |
| `compare_buildings` | Compare properties | `building_ids: string[]` |
| `get_building_info` | Get detailed info | `building_id` |
| `clear_filters` | Reset all filters | - |

### Tool Response Format
```json
{
  "action": "filter_surface",
  "params": {"min_m2": 100, "max_m2": 300},
  "result": {
    "matched_count": 15,
    "message": "Filtrati 15 immobili tra 100-300 m²"
  }
}
```

### Frontend Action Handler
```typescript
// ChatContext handles tool actions
const handleToolAction = (action: ToolAction) => {
  switch (action.type) {
    case 'filter_surface':
      mapContext.setFilters({ surface: action.params });
      break;
    case 'select_building':
      mapContext.selectBuilding(action.params.id);
      break;
    // ...
  }
};
```

---

## Phase 3: Context & Intelligence

### Context Injection
```python
system_prompt = f"""
Sei un assistente immobiliare esperto.

CONTESTO ATTUALE:
- Query originale: "{context.original_query}"
- Immobili visibili: {len(context.visible_ids)} risultati
- Filtri attivi: {context.active_filters}
- Immobile selezionato: {context.selected_building or "Nessuno"}

DATI IMMOBILI TOP 10:
{format_buildings_table(context.top_buildings)}
"""
```

### Conversation Memory
- Store last N messages in session (configurable via `CHAT_CONTEXT_WINDOW`)
- Summarize older messages for context window

---

## Phase 4: UI/UX (Layout TBD)

### Option A: Floating Widget
- Bottom-right corner button
- Expands to chat panel
- Stays above map

### Option B: Side Panel
- Replaces/accompanies sidebar
- Full-height chat
- Split view possible

### Option C: Bottom Drawer
- Slides up from bottom
- Partial or full screen
- Mobile-friendly

---

## Configuration (config.py)

```python
# ==========================================================================
# Chat Agent Configuration
# ==========================================================================
CHAT_MODEL_FAST: str = "gpt-4o-mini"      # Quick responses
CHAT_MODEL_SMART: str = "gpt-4o"          # Complex reasoning
CHAT_MAX_TOKENS: int = 1024               # Max response tokens
CHAT_TEMPERATURE: float = 0.7             # Creativity level
CHAT_CONTEXT_WINDOW: int = 10             # Messages in context
CHAT_ENABLE_STREAMING: bool = True        # WebSocket streaming
```

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| LLM | OpenAI (configurable via settings) |
| Streaming | WebSocket + SSE fallback |
| State | React Context or Zustand |
| Tool calling | LangChain tools / OpenAI functions |

---

## Estimated Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| Phase 1: Infrastructure | 2-3 days | High |
| Phase 2: Tool Calling | 2-3 days | High |
| Phase 3: Context | 1-2 days | Medium |
| Phase 4: UI/UX | 1-2 days | Low |

**Total: ~7-10 days**

---

## Open Questions
1. Layout preference (widget, panel, drawer)?
2. Should chat persist across page navigation?
3. Should chat history be saved per user in database?
