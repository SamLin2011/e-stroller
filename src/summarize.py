from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from openai import OpenAI


REPORT_SECTIONS = [
    "今日摘要",
    "今日新增信息",
    "上市产品动态",
    "最新研发方向",
    "专利 / 论文 / 展会线索",
    "产品功能趋势表",
    "对中国市场的启示",
    "明日继续跟踪清单",
    "来源链接",
]


def generate_chinese_report(
    items: list[dict[str, Any]],
    errors: list[str],
    report_date: date,
    allow_fallback: bool = False,
) -> str:
    try:
        return _generate_with_openai(items, errors, report_date)
    except Exception:
        if not allow_fallback:
            raise
        return build_fallback_report(items, errors, report_date)


def _generate_with_openai(items: list[dict[str, Any]], errors: list[str], report_date: date) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    payload = {
        "report_date": report_date.isoformat(),
        "items": items,
        "collection_errors": errors,
        "required_sections": REPORT_SECTIONS,
    }

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是婴童出行、智能硬件和机器人产品方向的中文行业情报分析师。"
                    "请只基于用户提供的来源材料生成日报；不确定的信息要标注为“未披露”或“线索待核验”。"
                    "输出 Markdown，语言精炼、可执行，避免夸大。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请根据以下采集结果生成中文日报。重点提取产品名称、品牌、上市地区、价格、"
                    "电助力、下坡制动、自动驻车、自动摇晃、App 控制、电池续航、传感器、AI/机器人功能、"
                    "安全功能、来源链接、发布时间或页面更新时间。\n\n"
                    f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty report")
    return content.strip() + "\n"


def build_fallback_report(items: list[dict[str, Any]], errors: list[str], report_date: date) -> str:
    lines: list[str] = [
        f"# 婴童电助力推车 / 智能婴儿车日报 - {report_date.isoformat()}",
        "",
        "## 今日摘要",
    ]
    if items:
        lines.append(f"今日发现 {len(items)} 条未报告过的信息线索，需进一步核验产品参数、上市地区和价格。")
    else:
        lines.append("今日未发现新的未报告链接。建议继续跟踪重点品牌官网、新闻、专利、论文和电商页面。")

    lines.extend(["", "## 今日新增信息"])
    if not items:
        lines.append("- 无新增。")
    for item in items:
        lines.append(
            "- "
            f"{item.get('title') or '未命名线索'} | "
            f"品牌：{item.get('brand') or '未披露'} | "
            f"产品：{item.get('product_name') or '未披露'} | "
            f"来源：{item.get('source_category') or 'unknown'} | "
            f"[链接]({item.get('url')})"
        )

    lines.extend(
        [
            "",
            "## 上市产品动态",
            _bullet_by_category(items, ["brand_official", "ecommerce"]),
            "",
            "## 最新研发方向",
            _bullet_by_feature(items),
            "",
            "## 专利 / 论文 / 展会线索",
            _bullet_by_category(items, ["patent", "paper", "exhibition"]),
            "",
            "## 产品功能趋势表",
            "| 产品/线索 | 电助力 | 下坡制动 | 自动驻车 | 自动摇晃 | App 控制 | 电池续航 | 传感器 | AI/机器人 | 安全功能 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in items[:20]:
        lines.append(
            "| "
            f"{_table_cell(item.get('product_name') or item.get('title'))} | "
            f"{_table_cell(item.get('electric_assist'))} | "
            f"{_table_cell(item.get('downhill_brake'))} | "
            f"{_table_cell(item.get('auto_parking'))} | "
            f"{_table_cell(item.get('auto_rocking'))} | "
            f"{_table_cell(item.get('app_control'))} | "
            f"{_table_cell(item.get('battery_life'))} | "
            f"{_table_cell(item.get('sensors'))} | "
            f"{_table_cell(item.get('ai_robotics'))} | "
            f"{_table_cell(item.get('safety_features'))} |"
        )

    lines.extend(
        [
            "",
            "## 对中国市场的启示",
            "- 重点关注电助力、下坡制动、自动驻车、避障感知和 App 互联是否成为高端婴儿车差异化卖点。",
            "- 对海外上市产品的价格、认证、安全表述和渠道反馈进行持续对标。",
            "- 对 AI/机器人功能保持谨慎判断，优先核验真实量产状态和安全冗余设计。",
            "",
            "## 明日继续跟踪清单",
            "- CYBEX e-Priam / e-Gazelle S 官方页面与零售渠道变化。",
            "- Glüxkind Rosa / Ella 的量产、价格、地区和媒体评测。",
            "- Bosch eStroller 相关技术授权、供应链和专利动态。",
            "- 关键词：electric stroller、AI stroller、robotic stroller、powered stroller、smart stroller。",
            "",
            "## 来源链接",
        ]
    )
    if not items:
        lines.append("- 无新增来源链接。")
    for item in items:
        lines.append(f"- [{item.get('title') or item.get('url')}]({item.get('url')})")

    if errors:
        lines.extend(["", "## 抓取异常"])
        lines.extend(f"- {error}" for error in errors)

    return "\n".join(lines).strip() + "\n"


def _bullet_by_category(items: list[dict[str, Any]], categories: list[str]) -> str:
    selected = [item for item in items if item.get("source_category") in categories]
    if not selected:
        return "- 暂无新增。"
    return "\n".join(
        f"- {item.get('title') or '未命名线索'}：{item.get('snippet') or '摘要待补充'}"
        for item in selected[:8]
    )


def _bullet_by_feature(items: list[dict[str, Any]]) -> str:
    selected = [
        item
        for item in items
        if item.get("ai_robotics") or item.get("sensors") or item.get("electric_assist")
    ]
    if not selected:
        return "- 暂无新增。"
    return "\n".join(
        f"- {item.get('title') or '未命名线索'}：关注 "
        f"{', '.join(_feature_names(item)) or '功能细节待核验'}。"
        for item in selected[:8]
    )


def _feature_names(item: dict[str, Any]) -> list[str]:
    labels = {
        "electric_assist": "电助力",
        "downhill_brake": "下坡制动",
        "auto_parking": "自动驻车",
        "auto_rocking": "自动摇晃",
        "app_control": "App 控制",
        "battery_life": "电池续航",
        "sensors": "传感器",
        "ai_robotics": "AI/机器人",
        "safety_features": "安全功能",
    }
    return [label for key, label in labels.items() if item.get(key)]


def _table_cell(value: Any) -> str:
    if not value:
        return "未披露"
    return str(value).replace("|", "/").replace("\n", " ")[:80]
