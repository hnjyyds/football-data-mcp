from __future__ import annotations

from typing import Any


def _summary_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def build_validation_verdict(summary: dict[str, Any]) -> dict[str, Any]:
    """Turn validation metrics into an operator-facing decision.

    负 log-loss 差表示模型优于市场基线；正 ROI 只在样本足够时才有产品意义。
    这个结论不会开放真实交易，只给 dashboard 一个清晰的下一步动作。
    """
    evaluated = int(summary.get("evaluated_count") or 0)
    bet_count = int(summary.get("bet_count") or 0)
    failed_leagues = int(summary.get("failed_leagues") or 0)
    log_loss_diff = _summary_number(summary.get("log_loss_diff"))
    brier_diff = _summary_number(summary.get("brier_diff"))
    roi = _summary_number(summary.get("roi"))
    evidence = {
        "evaluated_count": evaluated,
        "bet_count": bet_count,
        "failed_leagues": failed_leagues,
        "log_loss_diff": log_loss_diff,
        "brier_diff": brier_diff,
        "roi": roi,
    }

    if failed_leagues > 0:
        return {
            "status": "league_validation_failed",
            "tone": "bad",
            "title": "部分联赛验证失败",
            "detail": f"{failed_leagues} 个联赛没有完成验证，当前结果不能作为生产判断。",
            "next_action": "先重试失败联赛；若仍失败，检查对应联赛的数据源、赔率字段和历史样本覆盖。",
            "blockers": ["failed_league_results"],
            "evidence": evidence,
        }
    if evaluated <= 0 or bet_count <= 0:
        return {
            "status": "no_validation_samples",
            "tone": "caution",
            "title": "没有可评估样本",
            "detail": "Holdout 已执行，但没有形成可比较的验证样本或下注样本。",
            "next_action": "扩大验证赛季或降低临时样本门槛，并检查数据源是否缺少赔率、赛果或盘口字段。",
            "blockers": ["validation_samples_missing"],
            "evidence": evidence,
        }
    if evaluated < 100 or bet_count < 50:
        return {
            "status": "insufficient_sample",
            "tone": "caution",
            "title": "验证样本不足",
            "detail": f"当前仅 {evaluated} 场可评估、{bet_count} 条下注样本，结论容易被偶然结果带偏。",
            "next_action": "继续积累样本或扩大 holdout 范围；暂时只用于诊断，不开放推荐发布。",
            "blockers": ["validation_sample_below_gate"],
            "evidence": evidence,
        }
    if log_loss_diff is None:
        return {
            "status": "market_baseline_missing",
            "tone": "caution",
            "title": "缺少市场基线",
            "detail": "没有可比较的市场 log-loss，无法判断模型概率是否真的优于赔率隐含概率。",
            "next_action": "优先补齐市场隐含概率和赔率快照，再重跑 holdout validation。",
            "blockers": ["market_baseline_missing"],
            "evidence": evidence,
        }
    if log_loss_diff >= 0:
        return {
            "status": "model_underperforms_market" if roi is None or roi <= 0 else "roi_positive_but_market_worse",
            "tone": "bad" if roi is None or roi <= 0 else "caution",
            "title": "模型跑输市场基线" if roi is None or roi <= 0 else "收益为正但概率未跑赢市场",
            "detail": (
                f"模型 log-loss 比市场高 {log_loss_diff:.4f}"
                + (f"，ROI {roi:+.1%}" if roi is not None else "")
                + "；这说明当前概率质量不足以支撑生产发布。"
            ),
            "next_action": "暂停推荐发布，优先检查赔率快照、特征工程和模型校准；修复后再重跑 holdout validation。",
            "blockers": ["model_not_beating_market"],
            "evidence": evidence,
        }
    if roi is None or roi <= 0:
        roi_text = f"{roi:+.1%}" if roi is not None else "不可计算"
        return {
            "status": "probability_improved_but_unprofitable",
            "tone": "caution",
            "title": "概率优于市场但收益未转正",
            "detail": f"模型 log-loss 已优于市场 {abs(log_loss_diff):.4f}，但 ROI 仍为 {roi_text}。",
            "next_action": "继续纸面验证，重点调优候选过滤、赔率区间和盘口选择，暂不开放正式推荐。",
            "blockers": ["roi_not_positive"],
            "evidence": evidence,
        }
    return {
        "status": "watchlist_candidate",
        "tone": "good",
        "title": "验证通过观察候选",
        "detail": f"模型 log-loss 优于市场 {abs(log_loss_diff):.4f}，ROI {roi:+.1%}，可进入受控观察。",
        "next_action": "进入观察候选，继续监控 CLV、分联赛稳定性和新增样本；达到更高门槛后再评估生产发布。",
        "blockers": [],
        "evidence": evidence,
    }
