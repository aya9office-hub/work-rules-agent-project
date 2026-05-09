from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, asdict
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


@dataclass
class Finding:
    category: str
    title: str
    severity: str
    location: str
    issue: str
    recommendation: str


def heuristic_checks(docs: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    combined = "\n".join(docs.values())

    # 規程名参照の簡易検出
    referenced_rules = set(re.findall(r"([一-龥ぁ-んァ-ヶA-Za-z0-9]+規程)", combined))
    provided_rules = set()
    for name in docs:
        stem = re.sub(r"\.(docx|pdf|txt|md)$", "", name, flags=re.I)
        if "規程" in stem or "規則" in stem:
            provided_rules.add(stem)

    for rule in sorted(referenced_rules):
        if "旅費" in rule:
            continue
        if not any(rule in p for p in provided_rules):
            findings.append(Finding(
                category="参照先確認",
                title=f"参照されている附属規程が提出資料に見当たりません: {rule}",
                severity="中",
                location="全規程横断",
                issue=f"本文中に『{rule}』への参照がありますが、同名または近似名の提出ファイルを確認できませんでした。",
                recommendation="参照先規程が存在するか、規程名が現在の名称と一致しているか確認してください。"
            ))

    # 用語ゆれ
    term_pairs = [("従業員", "社員"), ("職員", "社員"), ("会社", "法人")]
    for a, b in term_pairs:
        if a in combined and b in combined:
            findings.append(Finding(
                category="用語統一",
                title=f"用語の混在: 『{a}』と『{b}』",
                severity="中",
                location="全規程横断",
                issue=f"『{a}』と『{b}』が混在しています。定義上の使い分けがない場合、適用対象の解釈に揺れが出ます。",
                recommendation="定義条項で使い分けを明示するか、主要用語を統一してください。"
            ))

    # 章立て・条番号の簡易チェック
    for filename, text in docs.items():
        nums = [int(n) for n in re.findall(r"第\s*(\d+)\s*条", text)]
        if nums:
            missing = [n for n in range(min(nums), max(nums) + 1) if n not in nums]
            if missing[:5]:
                findings.append(Finding(
                    category="条番号",
                    title="条番号に欠番または抽出不能箇所があります",
                    severity="低",
                    location=filename,
                    issue=f"第{missing[:5]}条付近に欠番がある可能性があります。",
                    recommendation="意図的な欠番か、条番号の修正漏れか確認してください。"
                ))

    if "懲戒" in combined and "服務" not in combined:
        findings.append(Finding(
            category="懲戒・服務",
            title="懲戒規定と服務規律の接続が弱い可能性があります",
            severity="中",
            location="就業規則または附属規程",
            issue="懲戒に関する記載はありますが、服務規律との明確な接続を十分に確認できませんでした。",
            recommendation="懲戒事由が服務規律・禁止事項と対応しているか確認してください。"
        ))

    return findings


def ai_checks(docs: dict[str, str], rules: dict[str, Any]) -> list[Finding]:
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        return heuristic_checks(docs)

    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    payload = {
        "rules": rules,
        "documents": {k: v[:50000] for k, v in docs.items()}
    }
    prompt = """
あなたは社会保険労務士のための就業規則構造チェック支援AIです。
目的は法違反の断定ではなく、就業規則と附属規程を横断し、構造上・運用上の不整合を抽出することです。
旅費規程は通常対象外です。違法・適法の断定は避け、確認推奨・整合確認という表現にしてください。
出力はJSON配列のみ。各要素は category,title,severity,location,issue,recommendation を持つこと。
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    items = data.get("findings", data if isinstance(data, list) else [])
    return [Finding(**item) for item in items]


def analyze(docs: dict[str, str], rules: dict[str, Any]) -> list[dict[str, Any]]:
    findings = ai_checks(docs, rules)
    return [asdict(f) for f in findings]
