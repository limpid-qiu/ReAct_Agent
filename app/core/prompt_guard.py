from dataclasses import dataclass


SUSPICIOUS_PROMPT_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "forget previous instructions",
    "disregard previous instructions",
    "system prompt",
    "developer message",
    "reveal your prompt",
    "print your prompt",
    "bypass",
    "jailbreak",
    "忽略之前的指令",
    "忽略以上指令",
    "忽略所有规则",
    "忘记之前的指令",
    "显示系统提示词",
    "输出系统提示词",
    "泄露提示词",
    "绕过限制",
    "越狱",
]


@dataclass(frozen=True)
class PromptGuardResult:
    suspicious: bool
    matched_patterns: list[str]


def inspect_prompt_text(text: str | None) -> PromptGuardResult:
    if not text:
        return PromptGuardResult(
            suspicious=False,
            matched_patterns=[],
        )

    normalized = text.lower()
    matched_patterns = [
        pattern
        for pattern in SUSPICIOUS_PROMPT_PATTERNS
        if pattern.lower() in normalized
    ]

    return PromptGuardResult(
        suspicious=bool(matched_patterns),
        matched_patterns=matched_patterns,
    )