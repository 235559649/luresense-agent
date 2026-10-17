"""从运行记录和可选人工评分生成离线实验报告。"""

import argparse
from pathlib import Path

from audit_runs import build_audit
from review_runs import read_json, summarize


def cell(value):
    """避免文字破坏 Markdown 表格。"""
    return str(value).replace("|", r"\|").replace("\n", " ")


def ratio(value, denominator):
    if value is None:
        return "null（无有效分母）"
    return f"{value:.1%}（n={denominator}）"


def build_report(paths, review_path=None):
    audit = build_audit(paths)
    s = audit["summary"]

    lines = [
        "# LureSense 实验检查点",
        "",
        "统计单位为响应轮次，不是独立情景。此报告不自动判断语义正确性。",
        "",
        "## 处理过程",
        "",
        "| 指标 | 结果 |",
        "|---|---|",
    ]

    metrics = [
        ("真实响应记录", s["real_rows"]),
        ("排除的模拟或未知来源记录", s["synthetic_or_unknown_rows"]),
        ("尝试模型请求", s["attempted_requests"]),
        ("收到模型响应", s["received_model_responses"]),
        ("规则拦截", s["guard_interceptions"]),
        ("策略改写", s["policy_rewrites"]),
        (
            "拦截比例（不是准确率）",
            ratio(
                s["interception_rate_on_received"],
                s["received_model_responses"],
            ),
        ),
        (
            "已知 Token 合计",
            s["known_total_tokens_sum"]
            if s["rows_with_known_tokens"]
            else "null",
        ),
        (
            "Token 已知 / 缺失记录",
            f"{s['rows_with_known_tokens']} / "
            f"{s['rows_without_known_tokens']}",
        ),
    ]

    lines.extend(f"| {name} | {value} |" for name, value in metrics)

    lines += [
        "",
        "## 原始输出与最终结果",
        "",
        "原始状态只是模型声明；最终状态包含规则处理。",
        "",
        "| 状态 | 原始声明轮数 | 最终轮数 |",
        "|---|---:|---:|",
    ]

    before = s["original_declared_status_counts"]
    after = s["final_status_counts"]

    for status in sorted(set(before) | set(after)):
        lines.append(
            f"| {cell(status)} | {before.get(status, 0)} "
            f"| {after.get(status, 0)} |"
        )

    lines += ["", "## 最终回答的人工评分", ""]

    if review_path:
        review = read_json(review_path)

        if not review.get("reviewer", "").strip():
            raise ValueError("请填写 reviewer")

        # 复用原有校验：原始回答、证据、编号和源日志不能被修改。
        graded = summarize(review)

        review_hashes = [x["sha256"] for x in review["sources"]]
        run_hashes = [x["sha256"] for x in audit["sources"]]

        if review_hashes != run_hashes:
            raise ValueError("评分来源必须与 --run 文件及顺序一致")

        lines += [
            "| 版本 | 评分覆盖率 | 未充分支持比例 | 有用回答比例 |",
            "|---|---|---|---|",
        ]

        for version, g in graded["groups"].items():
            values = [
                cell(version),
                ratio(g["decided_coverage"], g["claim_count"]),
                ratio(
                    g["not_fully_supported_rate_among_decided"],
                    g["decided_claim_count"],
                ),
                ratio(
                    g["useful_rate_on_graded_answerable_rows"],
                    g["usefulness_decided_rows"],
                ),
            ]
            lines.append("| " + " | ".join(values) + " |")

        lines += [
            "",
            "覆盖率分母为全部主张；未充分支持分母为已决定主张；"
            "有用率分母为可回答且已评有用性的响应。",
            "这些是最终回答评分，不能据此推断原始模型准确率"
            "或规则带来的提升。",
        ]
    else:
        lines.append("未提供人工评分文件；不生成质量指标。")

    lines += [
        "",
        "## 可追溯性",
        "",
        "输入文件 SHA256（按输入顺序）：",
        "",
    ]

    lines.extend(f"- `{x['sha256']}`" for x in audit["sources"])

    lines += [
        "",
        "## 解释边界",
        "",
        "- 开发中使用过的案例不是独立盲测。",
        "- Token 表示用量，不是费用；缺失用量不按零计。",
        "- 拦截比例不是准确率，策略改写后的结果不是原始模型表现。",
        "- 证明改进需在相同保留测试集上比较配置，并人工复核。",
        "",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", nargs="+", required=True)
    parser.add_argument("--review")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        report = build_report(args.run, args.review)

        # 已有文件不覆盖，避免丢失此前实验检查点。
        with Path(args.out).open("x", encoding="utf-8") as f:
            f.write(report)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, f"报告生成失败：{error}\n")

    print(f"已生成：{args.out}")


if __name__ == "__main__":
    main()