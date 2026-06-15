"""多轮对话记忆模块"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ConversationMessage:
    """对话消息"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    sources: Optional[list[dict]] = None


@dataclass
class ConversationSession:
    """对话会话"""
    session_id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Optional[dict] = None

    def add_message(
        self,
        role: str,
        content: str,
        sources: Optional[list[dict]] = None,
    ):
        """添加消息"""
        self.messages.append(ConversationMessage(
            role=role,
            content=content,
            sources=sources,
        ))

    def get_history(self, max_messages: int = 10) -> list[dict]:
        """获取历史消息"""
        messages = self.messages[-max_messages:]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    def get_context_window(self, max_tokens: int = 2000) -> str:
        """获取上下文窗口（截断到指定 token 数）"""
        context_parts = []
        total_chars = 0

        for msg in reversed(self.messages):
            if total_chars + len(msg.content) > max_tokens * 4:  # 粗略估计 1 token ≈ 4 chars
                break
            context_parts.append(f"{msg.role}: {msg.content}")
            total_chars += len(msg.content)

        return "\n".join(reversed(context_parts))


class ConversationMemory:
    """对话记忆管理器

    支持会话数量限制和自动清理，防止内存无限增长。
    """

    MAX_SESSIONS = 1000  # 最大会话数量

    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self.sessions: dict[str, ConversationSession] = {}
        self.max_sessions = max_sessions

    def _cleanup_old_sessions(self):
        """清理最旧的会话，保持会话数量在限制内"""
        while len(self.sessions) >= self.max_sessions:
            # 删除最旧的会话
            oldest_id = next(iter(self.sessions))
            del self.sessions[oldest_id]

    def create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """创建新会话"""
        import uuid
        if session_id is None:
            # 使用更长的UUID，降低碰撞概率
            session_id = uuid.uuid4().hex[:12]

        # 清理旧会话
        self._cleanup_old_sessions()

        session = ConversationSession(session_id=session_id)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """列出所有会话"""
        return list(self.sessions.keys())


def multi_turn_rag(
    query: str,
    session: ConversationSession,
    settings,
    vector_store,
    embedder,
    llm,
    top_k: int = 5,
) -> dict:
    """
    多轮 RAG 问答

    Args:
        query: 用户问题
        session: 对话会话
        settings: 配置
        vector_store: 向量存储
        embedder: 嵌入管理器
        llm: LLM 实例
        top_k: 检索文档数量

    Returns:
        RAG 结果
    """
    from .search import semantic_search

    # 1. 检索相关文档
    results = semantic_search(query, vector_store, embedder, top_k=top_k)

    # 2. 构建上下文
    context_parts = []
    sources = []
    for i, r in enumerate(results, 1):
        context_parts.append(f"[来源{i}] {r.title}\n{r.text}")
        sources.append({
            "index": i,
            "title": r.title,
            "source": r.source,
            "doc_type": r.doc_type,
            "score": r.score,
        })

    context = "\n\n---\n\n".join(context_parts)

    # 3. 获取历史对话
    history = session.get_history(max_messages=5)
    history_text = "\n".join([
        f"{'用户' if msg['role'] == 'user' else '助手'}: {msg['content']}"
        for msg in history
    ])

    # 4. 构建系统提示
    system_prompt = """你是一个基于用户知识库的问答助手。根据提供的参考资料和对话历史回答用户问题。

规则：
- 只基于提供的参考资料回答，不要编造信息
- 如果参考资料不足以回答问题，明确说明
- 在回答中标注信息来源（使用 [来源N] 格式）
- 使用中文回答
- 回答要准确、简洁、有条理
- 考虑对话历史，保持连贯性"""

    # 5. 构建用户提示（包含历史）
    user_prompt = f"""对话历史：
{history_text}

参考资料：
{context}

当前问题：{query}

请基于参考资料和对话历史回答问题。"""

    # 6. 生成回答
    answer = llm.chat(system_prompt, user_prompt)

    # 7. 保存到会话历史
    session.add_message("user", query)
    session.add_message("assistant", answer, sources=sources)

    return {
        "answer": answer,
        "sources": sources,
        "session_id": session.session_id,
        "message_count": len(session.messages),
    }
