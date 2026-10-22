#!/usr/bin/env python3
"""Randomized Block Curation replication runner.

Arms (same model + harness, same eval tasks):
  A  no playbook (floor)
  B  whole playbook (all 12 lessons)
  C  agent-judged curation: the model tags each lesson
     helpful/harmful/neutral in 3 passes (majority tag kept);
     lessons tagged helpful are served. Tagging tokens count
     in arm C's cost.
  D  Randomized Block Curation (treatment): on the 12 practice
     tasks, 8 randomized block assignments (96 runs); each block
     included/excluded independently at random (fixed design seed,
     same matrix every phase; the model pairing changes). A block
     is kept iff its measured practice success effect (success
     with the block - success without it) is > 0. Practice tokens
     count in arm D's cost.

Phases:
  validity     references re-verified 30/30 (abort before any model
               call on failure) + arms A and B smoke on the eval
               set, 1 rep per task. The frozen validity gate is
               computed on the main phase's arm-B runs.
  main         curation (C tags, D practice) + all four arms,
               3 reps per eval cell (216 eval runs + 96 practice)
  replication  curation re-run from scratch on the second pairing
               + all four arms, 1 rep per eval cell

Scoring is by check.py only. Runs are resumable: cells already in
runs.jsonl for the same phase+model with non-null success are
skipped; curation artifacts are cached per phase+model in
curation-<phase>-<model>.json.
"""
import concurrent.futures
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check  # noqa: E402
import model_client  # noqa: E402  (public-API shim; see model_client.py)


def append_jsonl(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def set_stage(here, stage, detail=""):
    with open(os.path.join(here, "stage.json"), "w") as f:
        json.dump({"stage": stage, "detail": detail}, f, indent=2)
    print(f"[stage] {stage}: {detail}", flush=True)

RUNS = os.path.join(HERE, "runs.jsonl")
ARMS = ("A", "B", "C", "D")
DESIGN_SEED = 20261021
N_ASSIGN = 8
AGENT_SYSTEM = ("You are completing a delivery task. Produce ONLY the "
                "deliverable record: exactly one KEY=value line per key, in "
                "the order listed, no explanation. Follow the playbook "
                "lessons where they apply.")
TAG_SYSTEM = ("You judge playbook lessons for a delivery-record system. "
              "Tag each lesson as helpful, harmful, or neutral for the "
              "quality of delivery records. Reply with ONLY a JSON object "
              "mapping lesson number to tag, e.g. {\"1\": \"helpful\"}.")

DATA = json.load(open(os.path.join(HERE, "tasks.json")))
LESSONS = DATA["lessons"]
BLOCK_IDS = [b["block"] for b in DATA["blocks"]]
LESSON_BLOCK = {l["n"]: l["block"] for l in LESSONS}


def call_model(backend, model, system, user, max_tokens=1200):
    if backend == "gemini":
        text, _thought, total = model_client.gemini_generate(
            model, system, user, max_tokens=max_tokens)
        return text, int(total or 0)
    msg, usage = model_client.openrouter_chat(
        model, [{"role": "system", "content": system},
                {"role": "user", "content": user}],
        temperature=0.0, max_tokens=max_tokens)
    text = (msg.get("content") or "") + "\n" + (msg.get("reasoning") or "")
    return text, model_client.openrouter_total_tokens(usage)


def assignments():
    """96 practice assignments: 12 tasks x 8, each block in/out at random."""
    rng = random.Random(DESIGN_SEED)
    out = []
    for task in DATA["practice_tasks"]:
        for a in range(N_ASSIGN):
            blocks = [b for b in BLOCK_IDS if rng.random() < 0.5]
            out.append((task, a, blocks))
    return out


def playbook_text(block_ids):
    sel = [l for l in LESSONS if l["block"] in block_ids]
    if not sel:
        return ""
    return "PLAYBOOK (lessons from prior work):\n" + "\n".join(
        f"- {l['text']}" for l in sel) + "\n\n"


def packet(task, block_ids):
    keys = ", ".join(task["keys"])
    return (f"{playbook_text(block_ids)}"
            f"SOURCE RECORD:\ncontact name: {task['given']} {task['family']}\n"
            f"code: {task['code']}\ndate: {task['date_words']}\n"
            f"total: {task['total']}\n\n"
            f"TASK: {task['title']}. Output exactly these keys, one per line, "
            f"in this order: {keys}.")


def curation_path(phase, model):
    safe = model.replace("/", "_")
    return os.path.join(HERE, f"curation-{phase}-{safe}.json")


def load_curation(phase, model):
    p = curation_path(phase, model)
    if os.path.exists(p):
        return json.load(open(p))
    return {}


def save_curation(phase, model, cur):
    with open(curation_path(phase, model), "w") as f:
        json.dump(cur, f, indent=2)


def recorded(phase, model):
    """(done eval/practice keys, practice recs, curation-token recs)."""
    done, practice, curtoks = set(), [], []
    if os.path.exists(RUNS):
        for line in open(RUNS):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("phase") == phase and r.get("model") == model and r.get("success") is not None:
                done.add((r["item"], r["arm"], r["rep"], tuple(r.get("blocks", []))))
                if r["arm"] == "practice":
                    practice.append(r)
            if r.get("phase") == f"{phase}_curation" and r.get("model") == model:
                curtoks.append(r)
    return done, practice, curtoks


def one_run(args):
    task, arm, rep, phase, backend, model, blocks = args
    t0 = time.time()
    rec = {"exp": "rbc-replication", "phase": phase, "item": task["id"],
           "category": task["category"], "arm": arm, "rep": rep,
           "model": model, "blocks": list(blocks)}
    try:
        raw, tokens = call_model(backend, model, AGENT_SYSTEM, packet(task, blocks))
        r = check.score(task, raw)
        rec.update(r)
        rec.update({"tokens": int(tokens), "wall_s": round(time.time() - t0, 2),
                    "raw": raw[:500]})
        print(f"{task['id']} {arm} rep{rep} blocks={','.join(blocks) or '-'} "
              f"-> success={r['success']} tok={tokens}", flush=True)
    except Exception as e:  # noqa: BLE001
        rec.update({"success": None, "error": str(e)[:200],
                    "wall_s": round(time.time() - t0, 2)})
        print(f"{task['id']} {arm} rep{rep} -> ERROR {str(e)[:120]}", flush=True)
    append_jsonl(RUNS, rec)
    return rec


def run_jobs(jobs, workers):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one_run, jobs))


def tag_lessons(backend, model):
    listing = "\n".join(f"{l['n']}. {l['text']}" for l in LESSONS)
    raw, tokens = call_model(backend, model, TAG_SYSTEM,
                             f"LESSONS:\n{listing}\n\nTag every lesson.", max_tokens=600)
    m = re.search(r"\{.*\}", raw, re.S)
    tags = {}
    if m:
        try:
            d = json.loads(m.group(0))
            tags = {int(k): str(v).lower() for k, v in d.items()}
        except Exception:  # noqa: BLE001
            tags = {}
    return tags, tokens, raw[:200]


def ensure_curation(phase, backend, model, arms, workers):
    """Compute arm C tags and arm D block effects for this phase+model."""
    cur = load_curation(phase, model)
    changed = False
    if "C" in arms and "C" not in cur:
        passes, total_toks = [], 0
        for _ in range(3):
            tags, toks, _raw = tag_lessons(backend, model)
            passes.append(tags)
            total_toks += toks
        majority = {}
        for l in LESSONS:
            votes = [p.get(l["n"], "neutral") for p in passes]
            majority[l["n"]] = max(("helpful", "harmful", "neutral"),
                                   key=lambda t: (votes.count(t), t == "helpful"))
        kept_lessons = [n for n, t in majority.items() if t == "helpful"]
        kept_blocks = sorted({LESSON_BLOCK[n] for n in kept_lessons})
        # arm C serves tagged-helpful LESSONS; a block is served only in
        # full here because lessons are served as a lesson list — record
        # the lesson set, and serve exactly those lessons via block filter
        # plus lesson filter in packet_for_arm.
        cur["C"] = {"tags_passes": passes, "majority": {str(k): v for k, v in majority.items()},
                    "kept_lessons": kept_lessons, "kept_blocks": kept_blocks,
                    "tokens": total_toks}
        append_jsonl(RUNS, {"exp": "rbc-replication", "phase": f"{phase}_curation",
                                   "item": "tags", "arm": "C", "rep": 0, "model": model,
                                   "success": None, "tokens": total_toks,
                                   "kept_lessons": kept_lessons})
        changed = True
        print(f"arm C tags done: kept lessons {kept_lessons} ({total_toks} tok)", flush=True)
    if "D" in arms and "D" not in cur:
        # practice records live under phase f"{phase}_practice"
        pdone, precs = set(), []
        if os.path.exists(RUNS):
            for line in open(RUNS):
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if (r.get("phase") == f"{phase}_practice" and r.get("model") == model
                        and r.get("success") is not None):
                    pdone.add((r["item"], r["rep"]))
                    precs.append(r)
        jobs = [(t, "practice", a, f"{phase}_practice", backend, model, blocks)
                for (t, a, blocks) in assignments()
                if (t["id"], a) not in pdone]
        print(f"arm D practice: {len(jobs)} runs queued, {len(precs)} recorded", flush=True)
        if jobs:
            precs = precs + run_jobs(jobs, workers)
        effects = {}
        for b in BLOCK_IDS:
            with_b = [r for r in precs if b in r.get("blocks", [])]
            without = [r for r in precs if b not in r.get("blocks", [])]
            sw = sum(r["success"] for r in with_b) / len(with_b) if with_b else 0.0
            so = sum(r["success"] for r in without) / len(without) if without else 0.0
            effects[b] = {"n_with": len(with_b), "n_without": len(without),
                          "success_with": round(sw, 3), "success_without": round(so, 3),
                          "effect": round(sw - so, 3)}
        kept = [b for b in BLOCK_IDS if effects[b]["effect"] > 0]
        cur["D"] = {"block_effects": effects, "kept_blocks": kept,
                    "practice_tokens": sum(r.get("tokens", 0) for r in precs),
                    "practice_n": len(precs)}
        changed = True
        print(f"arm D curation done: effects={ {b: effects[b]['effect'] for b in BLOCK_IDS} } "
              f"kept={kept}", flush=True)
    if changed:
        save_curation(phase, model, cur)
    return cur


def lesson_packet(task, lesson_numbers):
    sel = [l for l in LESSONS if l["n"] in lesson_numbers]
    if not sel:
        return packet(task, [])
    keys = ", ".join(task["keys"])
    pb = "PLAYBOOK (lessons from prior work):\n" + "\n".join(
        f"- {l['text']}" for l in sel) + "\n\n"
    return (f"{pb}SOURCE RECORD:\ncontact name: {task['given']} {task['family']}\n"
            f"code: {task['code']}\ndate: {task['date_words']}\n"
            f"total: {task['total']}\n\n"
            f"TASK: {task['title']}. Output exactly these keys, one per line, "
            f"in this order: {keys}.")


def one_eval(args):
    task, arm, rep, phase, backend, model, cur = args
    t0 = time.time()
    blocks = {"A": [], "B": BLOCK_IDS}.get(arm)
    rec = {"exp": "rbc-replication", "phase": phase, "item": task["id"],
           "category": task["category"], "arm": arm, "rep": rep, "model": model}
    try:
        if arm == "C":
            kept = cur.get("C", {}).get("kept_lessons", [])
            rec["blocks"] = sorted({LESSON_BLOCK[n] for n in kept})
            raw, tokens = call_model(backend, model, AGENT_SYSTEM,
                                     lesson_packet(task, kept))
        else:
            if arm == "D":
                blocks = cur.get("D", {}).get("kept_blocks", [])
            rec["blocks"] = list(blocks)
            raw, tokens = call_model(backend, model, AGENT_SYSTEM, packet(task, blocks))
        r = check.score(task, raw)
        rec.update(r)
        rec.update({"tokens": int(tokens), "wall_s": round(time.time() - t0, 2),
                    "raw": raw[:500]})
        print(f"{task['id']} {arm} rep{rep} -> success={r['success']} tok={tokens}", flush=True)
    except Exception as e:  # noqa: BLE001
        rec.update({"success": None, "error": str(e)[:200],
                    "wall_s": round(time.time() - t0, 2)})
        print(f"{task['id']} {arm} rep{rep} -> ERROR {str(e)[:120]}", flush=True)
    append_jsonl(RUNS, rec)
    return rec


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    ap.add_argument("--backend", default="gemini")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()

    tasks = DATA["tasks"]
    if a.phase == "validity":
        allt = tasks + DATA["practice_tasks"]
        bad = [t["id"] for t in allt
               if not (lambda r: r["completion"] and r["compliance"])(
                   check.score(t, t["reference"]))]
        print(f"reference verification: {len(allt) - len(bad)}/{len(allt)} pass")
        if bad:
            print("ABORT: reference failures:", bad)
            set_stage(HERE, "validity-failed", detail=f"reference failures: {bad}")
            return 1
        set_stage(HERE, "validity-running",
                         detail="references 30/30; arms A/B smoke running")

    arms = ["A", "B"] if a.phase == "validity" else a.arms.split(",")
    cur = {}
    if a.phase != "validity":
        set_stage(HERE, f"{a.phase}-curation",
                         detail=f"curation for arms {arms}, model={a.model}")
        cur = ensure_curation(a.phase, a.backend, a.model, arms, a.workers)

    done, _p, _c = recorded(a.phase, a.model)
    done_eval = {(d[0], d[1], d[2]) for d in done}
    jobs = [(t, arm, rep, a.phase, a.backend, a.model, cur)
            for t in tasks for arm in arms for rep in range(a.reps)
            if (t["id"], arm, rep) not in done_eval]
    print(f"{len(jobs)} eval runs queued (phase={a.phase} model={a.model} "
          f"backend={a.backend})", flush=True)
    set_stage(HERE, f"{a.phase}-running",
                     detail=f"{len(jobs)} eval runs queued, model={a.model}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(one_eval, jobs))
    ok = sum(1 for r in results if r.get("success") is not None)
    errs = sum(1 for r in results if r.get("error"))
    print(f"done: {ok} scored, {errs} errors")
    set_stage(HERE, f"{a.phase}-complete",
                     detail=f"{ok} scored, {errs} errors this invocation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
