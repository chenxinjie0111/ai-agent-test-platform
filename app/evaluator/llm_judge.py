"""
LLM-as-a-Judge：用另一个 LLM 来评价 Agent 的回答

为什么需要它：
  阶段三的 Final Answer 测试只能做"关键词匹配"——工具返回 temperature=20，
  检查回答里有没有 "20"。但 LLM 可能回答"气温大约二十度"——语义正确，
  但关键词匹配会误判为失败。

  LLM-as-a-Judge 用另一个 LLM 做"语义级"判断：
    输入 → 用户问题 + 期望结果 + Agent回答 + 工具返回
    输出 → {score: 0.0-1.0, passed: true/false, reason: "..."}

注意（面试必问）：
  LLM-as-a-Judge 本身也有偏差：
    - 评测员可能打分偏高（"和稀泥"）
    - 评测员可能不稳定（同一输入打不同分）
    - 评测员可能被 Agent 回答的"自信语气"误导
  所以评测器本身也需要测试和约束：
    - 要求返回 JSON 格式（可解析）
    - 设定明确的评分标准（system prompt 约束）
    - 做容错处理（解析失败时返回 score=0）
"""

import json
import re
from dataclasses import dataclass

from app.llm.client import LLMClient


@dataclass
class JudgeResult:
    """
    LLM 评测员的判定结果。

    score: 0.0 - 1.0 之间的分数
    passed: score >= 0.8 为 True
    reason: 评测理由（评测员自己写的解释）
    raw_response: 评测员的原始返回文本（调试用）
    """
    score: float
    passed: bool
    reason: str
    raw_response: str


class LLMJudge:
    """用 LLM 做语义级评分的评测员。"""

    JUDGE_SYSTEM_PROMPT = (
        "你是一个专业的 AI 助手回答质量评测员。\n"
        "你的任务是评估 AI 助手的回答质量，并给出结构化的评分。\n\n"
        "评分标准：\n"
        "- score: 0.0 到 1.0 之间的分数\n"
        "  - 1.0: 回答完全正确，包含所有关键信息，表述清晰\n"
        "  - 0.8-0.9: 回答基本正确，包含主要信息，表述较好\n"
        "  - 0.5-0.7: 回答部分正确，缺少部分信息或表述不够清晰\n"
        "  - 0.0-0.4: 回答错误、遗漏关键信息、或包含幻觉（编造数据）\n\n"
        "- passed: score >= 0.8 为 true，否则为 false\n"
        "- reason: 简要说明评分理由（一句话）\n\n"
        "重要：你必须只返回一个 JSON 对象，不要包含任何其他内容。\n"
        '格式如下：{"score": 0.9, "passed": true, "reason": "回答包含了正确的天气和温度信息"}'
    )

    # 评测通过的分數阈值
    PASS_THRESHOLD = 0.8

    def __init__(self, llm_client=None):
        self.llm = llm_client or LLMClient()

    def judge(self, question: str, expected: str,
              answer: str, tool_result: dict) -> JudgeResult:
        """
        评估一个 Agent 回答。

        参数:
            question: 用户原始问题
            expected: 期望的回答内容描述（自然语言）
            answer: Agent 的实际回答
            tool_result: Agent 调用工具返回的数据（dict）

        返回:
            JudgeResult，包含 score/passed/reason
        """
        prompt = (
            f"请评估以下 AI 助手的回答质量：\n\n"
            f"用户问题：{question}\n"
            f"期望结果：{expected}\n"
            f"助手回答：{answer}\n"
            f"工具返回数据：{json.dumps(tool_result, ensure_ascii=False)}\n\n"
            f"请返回 JSON 格式的评估结果。"
        )

        resp = self.llm.ask(prompt, system_prompt=self.JUDGE_SYSTEM_PROMPT)

        if not resp.success:
            return JudgeResult(
                score=0.0,
                passed=False,
                reason=f"评测员调用失败: {resp.error}",
                raw_response="",
            )

        return self._parse_response(resp.answer)

    def _parse_response(self, text: str) -> JudgeResult:
        """
        从 LLM 返回文本中解析 JSON 评分结果。

        为什么需要容错（面试点）：
          LLM-as-a-Judge 虽然被要求"只返回 JSON"，但它可能：
            - 加 markdown 代码块（```json ... ```）
            - 在 JSON 前后加解释文字
            - 返回不完整的 JSON
          所以解析必须做容错：先尝试提取 JSON 片段，再 json.loads。
          解析失败时返回 score=0（宁可误判失败，也不能让程序崩溃）。
        """
        # 去掉 markdown 代码块标记
        cleaned = text.strip()
        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
        cleaned = cleaned.replace('```', '')
        cleaned = cleaned.strip()

        # 找第一个 { 和最后一个 }，提取 JSON 片段
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = cleaned[start:end + 1]
            try:
                data = json.loads(json_str)
                score = float(data.get("score", 0))
                # 限制在 0-1 范围
                score = max(0.0, min(1.0, score))
                passed = data.get("passed", score >= self.PASS_THRESHOLD)
                # 确保 passed 是 bool 类型
                if isinstance(passed, str):
                    passed = passed.lower() == "true"
                reason = data.get("reason", "")
                return JudgeResult(
                    score=score,
                    passed=bool(passed),
                    reason=reason,
                    raw_response=text,
                )
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # 解析失败：返回安全默认值
        return JudgeResult(
            score=0.0,
            passed=False,
            reason=f"评测员返回格式错误，无法解析: {text[:200]}",
            raw_response=text,
        )
