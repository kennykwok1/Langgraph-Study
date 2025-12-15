from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Union, Annotated, Sequence
from PIL import Image as PILImage
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
import io

load_dotenv()

class AngentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

model = ChatOpenAI(model="gpt-4o")

@tool
def add(a: int, b: int) -> int:
    """这是一个加法的函数，将两个数字相加并返回结果。"""
    return a + b


tools = [add]

def model_call_node(state: AngentState) -> AngentState:
    print("Model Call Node executed")
    system_prompt = SystemMessage(content="你是一个 AI 助手。你的任务是根据用户的输入和可用的工具来生成适当的响应。")
    response = model.bind_tools(tools=tools).invoke([system_prompt] + list(state["messages"]))

    return {"messages": [response]}

def should_use_tool(state: AngentState) -> AngentState:
    print("Should Use Tool Node executed")
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"
    

graph = StateGraph(AngentState)
tool_node = ToolNode(tools=tools)



graph.add_node("ModelCall", model_call_node)
graph.set_entry_point("ModelCall")

graph.add_node("tools", tool_node)

graph.add_conditional_edges("ModelCall", should_use_tool, {
    "end": END,
    "continue": "tools"
})


graph.add_edge("tools", "ModelCall")

app = graph.compile()

# Display the graph
# img_bytes = app.get_graph().draw_mermaid_png()
# PILImage.open(io.BytesIO(img_bytes)).show()


def print_stream(stream):
    """打印流式输出的辅助函数"""
    for chunk in stream:
        if "messages" in chunk:
            for message in chunk["messages"]:
                print(f"[{message.__class__.__name__}]: {message.content}")


input_state = {"messages": [HumanMessage(content="请计算 5 加 3 的结果")]}
print_stream(app.stream(input_state, stream_mode="values"))