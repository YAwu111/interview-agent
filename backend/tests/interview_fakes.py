"""集成测试共用的面试编排假件：打桩 LLM/检索，不触达真实模型与 PG 检索。"""

from app.orchestration.agents.interview.deps import InterviewDeps


class FakeLLM:
    async def chat(self, messages, model, **kw):
        sys = messages[0].get("content", "") if messages else ""
        if "第一个面试问题" in sys:
            return {
                "content": "请先做 60 秒自我介绍。",
                "usage": {"total_tokens": 15},
                "latency_ms": 10,
            }
        if "语义单元" in sys:
            return {
                "content": '{"claims":[{"id":"c1","type":"tech_claim",'
                '"text":"我用 React 做了项目","has_evidence":true}]}',
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if any(
            k in sys
            for k in (
                "技术正确性",
                "逻辑严密性",
                "从深度评估",
                "从证据充分性",
                "从一致性",
                "从完整性",
            )
        ):
            return {
                "content": '{"dimension":"technical","verdict":"strong",'
                '"confidence":0.8,"evidence_refs":["c1"]}',
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "综合多位评审" in sys:
            return {
                "content": (
                    '{"abilities":[{"dimension":"technical","level":4,"confidence":0.8,'
                    '"evidence_refs":["c1"]}],"unverified":[],"needs_probe":true,'
                    '"candidates":[{"dimension":"depth","severity":2,"importance":2,'
                    '"uncertainty":3,"relevance":3,"probeability":2}]}'
                ),
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "递进式追问" in sys:
            return {
                "content": "能展开说说你的具体分工吗？",
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "结构化面试报告" in sys:
            return {
                "content": '{"overall":4,"dimensions":[],"strengths":["表达清晰"],'
                '"weaknesses":["缺少量化"],"next_steps":["补数据"],"end_reason":"user_end"}',
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        return {"content": "", "usage": {}, "latency_ms": 0}

    async def stream(self, messages, model, **kw):
        for ch in "点评：回答得不错，但缺少具体例子。":
            yield {"type": "delta", "content": ch}
        yield {"type": "usage", "usage": {"total_tokens": 1}}


class FakeRetriever:
    async def retrieve(self, query, top_k=None):
        return [
            {
                "id": "c1",
                "title": "前端面经",
                "text": "React 并发渲染通过并发特性协调优先级，区别于虚拟 DOM 的 diff 机制。",
                "snippet": "React 并发渲染通过并发特性协调优先级",
                "base_name": "面试知识库",
                "score": 0.9,
            }
        ]


def fake_deps() -> InterviewDeps:
    return InterviewDeps(
        llm=FakeLLM(), retriever=FakeRetriever(), fast_model="fast", strong_model="strong"
    )
