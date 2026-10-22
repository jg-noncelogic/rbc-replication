#!/usr/bin/env python3
"""Analysis for the RBC replication packet: per phase+arm success, harmful enactment, cost.

Cost rules (spec): arm D eval-phase tokens/task = eval tokens / eval
runs; arm D total cost per successful eval task includes its practice
tokens amortised over eval runs. Arm C total likewise includes its
tagging tokens.
"""
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return round(cov / (vx * vy) ** 0.5, 3) if vx and vy else None


def main():
    groups = defaultdict(list)
    practice_tokens, tag_tokens = defaultdict(int), defaultdict(int)
    for line in open(os.path.join(HERE, "runs.jsonl")):
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        ph = r.get("phase", "")
        if ph.endswith("_practice"):
            practice_tokens[ph[: -len("_practice")]] += r.get("tokens", 0)
            continue
        if ph.endswith("_curation"):
            tag_tokens[ph[: -len("_curation")]] += r.get("tokens", 0)
            continue
        if r.get("success") is None:
            continue
        groups[(ph, r["arm"])].append(r)
    out = {}
    for k in sorted(groups):
        rs = groups[k]
        phase, arm = k
        eval_toks = sum(r.get("tokens", 0) for r in rs)
        extra = 0
        if arm == "D":
            extra = practice_tokens.get(phase, 0)
        if arm == "C":
            extra = tag_tokens.get(phase, 0)
        succ = sum(r["success"] for r in rs)
        out[f"{phase}:{arm}"] = {
            "n": len(rs),
            "success_rate": round(succ / len(rs), 3),
            "harmful_enactment_rate": round(
                sum(r["harmful_enacted"] for r in rs) / len(rs), 3),
            "tokens_mean": round(eval_toks / len(rs), 1),
            "cost_per_success_total": round((eval_toks + extra) / succ, 1) if succ else None,
        }
    # tag-vs-effect correlation per phase where both curations exist
    import glob
    for p in glob.glob(os.path.join(HERE, "curation-*.json")):
        cur = json.load(open(p))
        name = os.path.basename(p)[len("curation-"):-len(".json")]
        if "C" in cur and "D" in cur:
            tag_score = {"helpful": 1, "neutral": 0, "harmful": -1}
            blocks = ["B1", "B2", "B3", "B4", "B5", "B6"]
            maj = cur["C"]["majority"]
            lessons = json.load(open(os.path.join(HERE, "tasks.json")))["lessons"]
            tag_by_block = {}
            for b in blocks:
                vals = [tag_score[maj[str(l["n"])]] for l in lessons if l["block"] == b]
                tag_by_block[b] = sum(vals) / len(vals)
            xs = [tag_by_block[b] for b in blocks]
            ys = [cur["D"]["block_effects"][b]["effect"] for b in blocks]
            out[f"curation:{name}"] = {
                "tag_by_block": tag_by_block,
                "effect_by_block": {b: cur["D"]["block_effects"][b]["effect"] for b in blocks},
                "tag_effect_spearman": spearman(xs, ys),
                "C_kept_lessons": cur["C"]["kept_lessons"],
                "D_kept_blocks": cur["D"]["kept_blocks"],
            }
    print(json.dumps(out, indent=2))
    with open(os.path.join(HERE, "analysis.json"), "w") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
