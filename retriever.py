"""LureSense 第一阶段：纯本地检索，无模型调用、无网络请求。"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# 一个概念的不同叫法。可根据开发集中的真实漏检继续扩充。
CONCEPTS = {
    "vegetation": ("水草", "植被", "草区", "草边", "草丛"),
    "cover": ("障碍物", "掩护", "结构", "倒木", "树根", "岩石"),
    "diet": ("吃什么", "吃啥", "食物", "食性", "捕食", "饵鱼", "螯虾"),
    "habitat": ("水库", "湖泊", "池塘", "回湾", "栖息"),
    "flow": ("水流", "缓流", "静水", "强流"),
    "timing": ("清晨", "早晨", "早上", "黎明", "黄昏", "傍晚", "早晚"),
    "spawning": ("繁殖", "产卵", "繁殖期"),
    "taxonomy": ("学名", "分类", "nigricans", "salmoides", "florida bass"),
    "softworm": ("软虫", "软饵", "德州", "卡罗莱纳", "texas rig"),
    "crankbait": ("摇滚饵", "摇摆饵", "crankbait", "导水舌", "潜深"),
    "topwater": ("水面饵", "topwater"),
    "color": ("颜色", "饵色", "光照"),
    "clarity": ("浑水", "水浑", "水色", "浑浊"),
    "oxygen": ("溶氧", "溶解氧", "缺氧", "氧气"),
    "stratification": ("深水", "深层", "表层", "分层", "最深"),
    "water_temperature": ("水温",),
    "air_temperature": ("气温",),
    "weather": ("天气", "预报", "降水", "风速"),
    "sensory": ("侧线", "振动", "感知"),
}

OUT_OF_SCOPE = ("海鲈", "花鲈", "尖吻鲈", "小口黑鲈", "孔雀鲈", "海水", "海边")


def normalize(text: str) -> str:
    """统一全角字符与英文大小写，保留中文。"""
    return unicodedata.normalize("NFKC", text).casefold().strip()


class KnowledgeBase:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.cards = json.loads((data_dir / "knowledge_cards.json").read_text(encoding="utf-8"))
        source_rows = json.loads((data_dir / "sources.json").read_text(encoding="utf-8"))
        self.sources = {s["id"]: s for s in source_rows}
        if len(self.sources) != len(source_rows):
            raise ValueError("来源 ID 重复")
        card_ids = set()
        for card in self.cards:
            if card["id"] in card_ids:
                raise ValueError("卡片 ID 重复")
            card_ids.add(card["id"])
            for field in ("claim", "applicability", "application_note", "tags", "source_ids"):
                if not card.get(field):
                    raise ValueError(f"{card['id']} 缺少字段 {field}")
            for source_id in card["source_ids"]:
                if source_id not in self.sources:
                    raise ValueError(f"{card['id']} 引用了不存在的来源 {source_id}")
                if not self.sources[source_id]["url"].startswith("https://"):
                    raise ValueError("来源必须有 HTTPS 链接")

    def search(self, query: str, limit: int = 4) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("请输入非空问题")
        if len(query) > 2000:
            raise ValueError("问题请控制在 2000 字符以内")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 4:
            raise ValueError("返回条数必须为 1～4")
        q = normalize(query)
        base = {"query": query, "mode": "local_keyword_retrieval", "results": [],
                "notice": "本工具只检索资料，不判断现场是否有鱼，不生成中鱼概率。"}
        # 保守的范围检查：比较性问题也可能触发，属于本版本已知限制。
        if any(word in q for word in OUT_OF_SCOPE):
            return {**base, "status": "out_of_scope", "message": "当前仅支持大口黑鲈淡水资料；问题包含其他鱼种或水域，请明确范围。"}

        concepts = [terms for terms in CONCEPTS.values() if any(t in q for t in terms)]
        # 泛称不是检索意图；避免每个含“鲈鱼”的问题都命中分类卡片。
        generic = {"大口黑鲈", "鲈鱼", "bass", "largemouth bass"}
        explicit_tags = {normalize(t) for c in self.cards for t in c["tags"]
                         if normalize(t) not in generic and normalize(t) in q}
        # 支持精确查询 K003，且不把 K0030 错当成 K003。
        requested_ids = set(re.findall(r"\bk\d{3}\b", q))
        ranked = []
        for card in self.cards:
            tags = {normalize(t) for t in card["tags"]}
            title = normalize(card["title"])
            claim = normalize(card["claim"])
            score, reasons = 0, set()
            if normalize(card["id"]) in requested_ids:
                score += 100
                reasons.add(card["id"])
            for term in explicit_tags:
                if term in tags:
                    score += 4
                    reasons.add(term)
            # 同一概念最多加一次，避免重复词堆砌分数。
            for terms in concepts:
                hits = {t for t in terms if t in tags or t in title or t in claim}
                if hits:
                    score += 3 if any(t in tags for t in hits) else 1
                    reasons.update(hits)
            if score:
                ranked.append((score, card, sorted(reasons)))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        results = [{"card": card, "matched_terms": reasons,
                    "sources": [self.sources[s] for s in card["source_ids"]]}
                   for _, card, reasons in ranked[:limit]]
        return {**base, "status": "ok" if results else "empty", "results": results,
                "message": "找到相关资料；请核对适用条件。" if results else "当前知识库没有匹配资料，请换用具体主题；不会补造答案。"}


def format_result(result: dict) -> str:
    lines = [result["notice"], result["message"]]
    for item in result["results"]:
        card = item["card"]
        lines.extend(["", f"[{card['id']}] {card['title']}",
                      f"资料主张：{card['claim']}",
                      f"适用条件：{card['applicability']}",
                      f"项目推断：{card['application_note']}",
                      "匹配词：" + "、".join(item["matched_terms"])])
        for source in item["sources"]:
            lines.extend([f"来源：{source['publisher']} · {source['title']}",
                          source["url"], f"原文位置：{card['locator']}",
                          f"来源限制：{source['limitations']}"])
    return "\n".join(lines)
