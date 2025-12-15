# LangGraph + DeepSeek + FAISS RAG 应用
import os
import pandas as pd
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage

load_dotenv()

# 1. 读取Excel并构建Document列表
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Ballista_仕様書リスト.xlsx")
INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index")
os.makedirs(INDEX_DIR, exist_ok=True)
INDEX_FAISS = os.path.join(INDEX_DIR, "index.faiss")
INDEX_PKL = os.path.join(INDEX_DIR, "index.pkl")

def load_excel_to_documents(excel_path):
	df = pd.read_excel(excel_path, engine="openpyxl")
	docs = []
	for _, row in df.iterrows():
		# 合并主要字段为文本内容
		content = f"項目: {row.get('項目', '')}\nカテゴリ: {row.get('カテゴリ', '')}\nステータス: {row.get('ステータス', '')}\n備考: {row.get('備考', '')}\nメモ: {row.get('メモ', '')}"
		# metadata 包含所有链接和结构化信息
		metadata = {
			"仕様書リンク": row.get("仕様書リンク", ""),
			"UI仕様リンク": row.get("UI仕様リンク", ""),
			"企画担当": row.get("企画担当", ""),
			"制作担当": row.get("制作担当", ""),
			"開発担当": row.get("開発担当", ""),
			"完成予定日": str(row.get("完成予定日", "")),
			"更新日": str(row.get("更新日", "")),
			"対応フェーズ": row.get("対応フェーズ", ""),
			"CBTの状態": row.get("CBTの状態", ""),
		}
		docs.append(Document(page_content=content, metadata=metadata))
	return docs

# 2. 初始化Embedding模型
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")

# 3. 构建或加载FAISS向量库
def get_vectorstore():
	if os.path.exists(INDEX_FAISS) and os.path.exists(INDEX_PKL):
		return FAISS.load_local(INDEX_DIR, embedding_model, allow_dangerous_deserialization=True)
	else:
		docs = load_excel_to_documents(EXCEL_PATH)
		vectorstore = FAISS.from_documents(docs, embedding_model)
		vectorstore.save_local(INDEX_DIR)
		return vectorstore

vectorstore = get_vectorstore()
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# 4. DeepSeek LLM配置
llm = ChatOpenAI(
	model="deepseek-chat",
	base_url="https://api.deepseek.com",
	api_key=os.getenv("DEEPSEEK_API_KEY")
)

# 5. 定义RAG状态
class RAGState(TypedDict):
	question: str
	context: str
	answer: str

# 6. LangGraph节点定义
def retrieve_node(state: RAGState) -> RAGState:
	"""检索相关文档，拼接上下文"""
	docs = retriever.invoke(state["question"])
	context = "\n\n".join([
		f"{doc.page_content}\n仕様書リンク: {doc.metadata.get('仕様書リンク', '')}\nUI仕様リンク: {doc.metadata.get('UI仕様リンク', '')}"
		for doc in docs
	])
	return {"question": state["question"], "context": context, "answer": ""}

def generate_node(state: RAGState) -> RAGState:
	"""用DeepSeek生成答案"""
	system_prompt = SystemMessage(content="你是一个仕様書检索AI助手。请根据提供的知识内容（包含仕様書链接和UI仕様链接），用日文或中文简明回答用户问题，并在答案末尾附上相关链接。若无相关内容请如实说明。")
	user_prompt = HumanMessage(content=f"用户问题: {state['question']}\n\n知识内容:\n{state['context']}")
	response = llm.invoke([system_prompt, user_prompt])
	answer = response.content if hasattr(response, 'content') else str(response)
	return {"question": state["question"], "context": state["context"], "answer": answer}

# 7. 构建LangGraph
graph = StateGraph(RAGState)
graph.add_node("retrieve", retrieve_node)
graph.add_node("generate", generate_node)
graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", END)
app = graph.compile()

# 8. 交互主流程
def main():
	print("\n=== 仕様書RAG QA (DeepSeek + FAISS) ===\n")
	while True:
		question = input("请输入您的问题（日文/中文，输入exit退出）：\n> ").strip()
		if question.lower() in {"exit", "quit", "q"}:
			break
		state = {"question": question, "context": "", "answer": ""}
		for step in app.stream(state, stream_mode="values"):
			if step.get("answer"):
				print("\n【回答】\n" + step["answer"] + "\n")

if __name__ == "__main__":
	main()
