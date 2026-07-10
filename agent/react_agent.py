from langchain.agents import create_agent
from agent.tools.middleware import log_before_model, log_after_model, monitor_tool, report_prompt_switch
from agent.tools.registry import get_enabled_tools
from model.factory import chat_model
from utils.prompts_loader import system_prompt

class ReActAgent:
    def __init__(self):
        self.agent = create_agent(
            model = chat_model,
            system_prompt = system_prompt,
            tools = get_enabled_tools(),
            middleware = [monitor_tool, log_before_model, log_after_model, report_prompt_switch]
        )

    @staticmethod
    def build_messages(query: str, history: list[dict] | None, max_history_messages: int = 12):
        messages = []

        for message in (history or [])[-max_history_messages:]:
            role = message.get("role")
            content = str(message.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": query})
        return messages
    
    def execute_stream(self, query: str, history: list[dict] | None = None, max_history_messages: int = 12):
        input_dict = {
            "messages": self.build_messages(query, history, max_history_messages),
        }

        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest_message = chunk["messages"][-1]
            if getattr(latest_message, "type", None) == "human":
                continue

            if latest_message.content:
                yield latest_message.content.strip() + "\n"
        

if __name__ == "__main__":
    agent = ReActAgent()

    for chunk in agent.execute_stream("告诉我上海的天气"):
        print(chunk, end="", flush=True)

