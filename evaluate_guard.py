"""离线评估上下文规则；不联网，不调用模型。"""

import argparse
import hashlib
import inspect
import json
from pathlib import Path

import context_guard


# 每条记录：
# 编号、结构状态、结构值、候选回答、是否应拦截、标注理由。
#
# 标注范围仅限“把未确认的结构说成存在或不存在”。
# 这些是人工编写的开发案例，不是独立盲测或真实模型输出。
CASES = [
    (
        "D01", "unknown", None,
        "附近已知的植被可以作为观察重点。",
        True, "未知条件被升级为存在",
    ),
    (
        "D02", "unknown", None,
        "现场没有水草，可以直接排除草区。",
        True, "未知条件被升级为不存在",
    ),
    (
        "D03", "unknown", None,
        "看不清水底不代表没有水草。",
        False, "否定错误推断",
    ),
    (
        "D04", "unknown", None,
        "如果现场有水草，可以记录其分布。",
        False, "条件假设",
    ),
    (
        "D05", "user_reported", "倒木",
        "已确认的倒木可作为观察候选，不保证有鱼。",
        False, "已报告结构作为候选",
    ),
    (
        "D06", "user_reported", "未观察到上述结构",
        "现场缺乏掩护结构。",
        True, "未观察到不等于不存在",
    ),
    (
        "D07", "unanswered", None,
        "先确认是否存在水草或倒木。",
        False, "请求补充观察",
    ),
    (
        "D08", "unknown", None,
        "这里长满了水草，可以沿草边观察。",
        True, "隐含存在表达",
    ),
    (
        "D09", "unknown", None,
        "这片水域找不到任何可供躲藏的地方。",
        True, "间接缺失表达",
    ),
    (
        "D10", "unknown", None,
        "先观察能看清的区域，再记录可见结构。",
        False, "未假设结构存在",
    ),
]


def metric(numerator, denominator):
    return {
        "numerator": numerator,
        "n": denominator,
        "value": numerator / denominator if denominator else None,
    }


def evaluate():
    rows = []
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    for case_id, status, value, text, expected, reason in CASES:
        context = {
            "cover": {
                "status": status,
                "value": value,
            }
        }
        answer = {
            "claims": [
                {
                    "text": text,
                    "caveat": None,
                }
            ]
        }

        conflicts = context_guard.context_conflicts(answer, context)
        predicted = bool(conflicts)

        if expected:
            outcome = "tp" if predicted else "fn"
        else:
            outcome = "fp" if predicted else "tn"

        counts[outcome] += 1

        rows.append({
            "id": case_id,
            "context": context,
            "answer": answer,
            "expected_block": expected,
            "predicted_block": predicted,
            "label_reason": reason,
            "passed": predicted == expected,
            "outcome": outcome,
            "conflicts": conflicts,
        })

    tp = counts["tp"]
    fp = counts["fp"]
    tn = counts["tn"]
    fn = counts["fn"]

    source = Path(inspect.getfile(context_guard)).read_bytes()
    dataset = json.dumps(
        CASES,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return {
        "schema_version": "1",
        "dataset": "context_guard_dev_v1",
        "unit": "authored claim-context pair",
        "model_calls": 0,
        "warning": (
            "开发集规则评估，不是模型准确率或独立盲测；"
            "未评估回答有用性。"
        ),
        "guard_sha256": hashlib.sha256(source).hexdigest(),
        "dataset_sha256": hashlib.sha256(dataset).hexdigest(),
        "summary": {
            "case_count": len(rows),
            **counts,
            "precision": metric(tp, tp + fp),
            "recall": metric(tp, tp + fn),
            "false_positive_rate": metric(fp, fp + tn),
            # 在全部固定候选回答上比较：
            # 无规则时放行所有案例；有规则时过滤命中的案例。
            "no_guard_conflicts_exposed": metric(
                tp + fn, len(rows)
            ),
            "guard_conflicts_exposed": metric(
                fn, len(rows)
            ),
            "failure_ids": [
                row["id"] for row in rows if not row["passed"]
            ],
        },
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        report = evaluate()

        # 不覆盖旧结果，保留每次实验记录。
        with Path(args.out).open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")

    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"评估失败：{error}\n")

    print(json.dumps(
        report["summary"],
        ensure_ascii=False,
        indent=2,
    ))
    print("失败案例已保留；完成评估不代表所有案例通过。")


if __name__ == "__main__":
    main()