# Randomized Block Curation — an independent replication datapoint

A replication, on a different and much smaller substrate, of:

> Hoang Pham, Cong-Duy Nguyen, Dong Le, Ponhvoan Srey, Anh Tuan Luu.
> *Reliable Memory from Unstable Growth: Curating Self-Written Agent
> Playbooks with Randomized Experiments.* arXiv:2610.18427.
> https://arxiv.org/abs/2610.18427

Run 2026-10-21 / 2026-10-22 by an independent agent-systems lab, as part
of an ongoing programme that evaluates published agent-memory methods on
our own task shapes before adopting any of them into a production
multi-agent software-delivery pipeline. The experiment's pass bar was
written down and frozen before any run. **Headline verdict: the bar was
missed (partial).** We are not affiliated with the paper's authors; this
packet is a datapoint offered back to them and to anyone else working on
playbook curation, with the full run data so the numbers can be checked.

## The paper's claim

- Persistent textual memory (a *playbook* of lessons an agent writes
  after each task and rereads in its prompt, as in ACE and Dynamic
  Cheatsheet) is unstable: the same growth procedure can produce a
  playbook that helps, or one that falls **up to 69.6 points below no
  playbook at all**.
- Leaving keep/drop decisions to the agent is the weak link: the agent's
  own helpful-versus-harmful tags correlate only **0.21** with measured
  effect.
- **Randomized Block Curation (RBC)** values lessons by experiment:
  lessons are grouped into blocks, each block is included or excluded at
  random on practice tasks, and the success gap estimates the block's
  causal effect. Helpful blocks are kept.
- Reported effect (two memory systems, three models, three benchmarks —
  AppWorld, WebShop, ALFWorld — 19 settings): **RBC 66.9** average
  success, against **55.5** whole playbook, **54.1** no playbook, and
  **53.8** agent-judged curation.

## What we ran

A deliberately small, fully deterministic analogue of the paper's
scenario, in the shape of our own work (delivery records):

- **Substrate.** Synthetic delivery-record tasks. Each packet gives the
  facts of one record (a person's name as "Given Family", a code, a date
  in word form, an exact total) and the required key order, and asks for
  a `KEY=value` deliverable. The packet deliberately omits two delivery
  conventions (ISO dates; "Family, Given" name order) that only the
  playbook supplies.
- **Playbook.** 12 lessons in 6 blocks of 2, with ground truth planted
  by construction: 2 helpful blocks (the two omitted conventions),
  2 harmful blocks (plausible but wrong conventions: round totals to
  the nearest ten; add an `ARC-` prefix to codes), 2 neutral blocks
  (true, irrelevant facts). Lessons carry no marker of their class.
- **Tasks.** 12 practice tasks and 18 fresh eval tasks (code /
  data-config / document shapes), disjoint sets, each with a verified
  reference completion. All 30 references pass the checker with no
  playbook at all, verified before any model call.
- **Scoring.** A deterministic checker only — completion (all required
  lines present) and compliance (no trap lines present). No model judge
  of outcomes. Per-block enactment is read from planted signature lines.
- **Arms** (same model and harness across arms):
  - **A** — no playbook (floor).
  - **B** — whole playbook (all 12 lessons).
  - **C** — agent-judged curation: the model tags each lesson
    helpful/harmful/neutral in 3 passes; majority tags decide; helpful
    lessons are served.
  - **D** — RBC: on the practice set, 12 tasks × 8 randomized block
    assignments = 96 runs; a block is kept iff its measured practice
    success effect (with − without) is > 0.
- **Main run.** Gemini 3.8 Flash, temperature 0: 216 eval runs
  (18 tasks × 4 arms × 3 repetitions), plus arm D's 96 practice runs and
  arm C's tagging passes, all costs counted to their arm.
- **Replication.** DeepSeek v4.1 Flash (via OpenRouter), 72 eval runs
  (18 × 4 × 1 repetition), with both curations re-run from scratch on
  that pairing.
- **Frozen bar** (adopt RBC only if all four hold on the main run):
  (1) D success ≥ B success + 10 points; (2) D success ≥ A success;
  (3) D success ≥ C success + 5 points; (4) D eval-phase tokens/task
  ≤ B's, and D's total cost per successful eval task (practice runs
  amortised) ≤ 1.5 × B's. Validity gate: B must fall ≥10 points below
  A, or harmful blocks must be enacted in ≥33% of B's runs.

## What we found

**Bar missed (partial): conditions 1 and 2 met, condition 3 missed,
condition 4 only partly evaluable.**

Main run (216 eval runs):

| Arm | Success | Harmful enactment | Tokens/task | Total cost per success |
|---|---|---|---|---|
| A — no playbook | 0% | 0% | 205.0 | — (no successes) |
| B — whole playbook | 0% | 100% | 502.3 | — (no successes) |
| C — agent-judged | 100% | 0% | 271.1 | 304.2 |
| D — RBC | 100% | 0% | 376.9 | 999.6 |

- The validity gate **passed** via the harmful-enactment clause: arm B
  enacted a harmful block in 100% of its runs. The unstable-growth
  phenomenon reproduces in this substrate — an unfiltered playbook was
  actively harmful, not merely useless.
- Condition 3 missed because **arm C matched arm D**: the agent's tags
  were near-perfect here. Tag-vs-effect Spearman correlation was
  **0.956**, against the paper's reported **0.21**. Arm C tagging
  (3 passes, 1,785 tokens) kept exactly the two helpful blocks.
- Condition 4b was not computable — arm B had zero successful tasks, so
  its cost per success is undefined; under the frozen rules that counts
  as not met, not as passed.

Measured block effects (arm D practice phase, success with − without):

| Block | Class (planted) | Measured effect | Kept by D |
|---|---|---|---|
| B1 | helpful | +0.102 | yes |
| B2 | helpful | +0.093 | yes |
| B3 | harmful | −0.098 | no |
| B4 | harmful | −0.116 | no |
| B5 | neutral | +0.021 | yes |
| B6 | neutral | +0.060 | yes |

Replication (72 eval runs, second model): A 0%, B 0% (harmful enactment
100%), **C 0%**, **D 100%**. Directions for conditions 1–3 all hold —
but with a caveat that changes what the replication shows:

- Arm C **degenerated**: all three DeepSeek tagging passes returned no
  parseable tags, the majority defaulted to neutral for every lesson,
  arm C kept 0 lessons and silently served an empty playbook. Its
  failure was an output-format failure, not a judgment failure.
- Arm D's re-run curation produced block effects **identical** to the
  main run (same values to three decimals) and kept the same blocks.
  In this substrate the practice-phase success pattern is close to a
  deterministic function of block inclusion, across both models.

## The 0.956 vs 0.21 discrepancy — our reading

We read this as a **boundary datapoint, not a refutation**. The most
plausible explanation is fixture cleanliness:

- Our planted lessons are separable *by reading them*. Each lesson
  states one convention; the helpful and harmful ones differ in content
  in a way a strong model can assess directly from the text. A real,
  accumulated playbook — the paper's setting — contains lessons whose
  value depends on interactions, staleness, and task distribution,
  which is exactly what makes self-tagging unreliable there.
- Both helpful conventions are jointly necessary for checker success in
  our tasks, so the no-playbook floor sits at 0% (the paper's floors
  are ≈54%). The curation question here is closer to "find the two
  necessary conventions" than to the paper's graded trade-offs.
- Our tasks are one-shot packet → deliverable calls with deterministic
  checkers — no tool loop, no multi-step state, none of AppWorld /
  WebShop / ALFWorld's ambiguity.

A follow-up that changes exactly one variable — a messier, real-shaped
playbook whose lessons are not cleanly separable by reading — would
test whether the headline gap appears. We have not run it.

## The robustness observation

The result we did not expect, and the one we would most like the
paper's authors' reaction to: **measured curation never collapsed.**
Across two models, RBC's curation reproduced identically and its arm
succeeded in both phases. Agent-judged curation matched it when its
tagging worked (at roughly a third of the total cost per success:
304.2 vs 999.6 tokens in the main run) and collapsed to zero when its
tagging output failed to parse. That is an argument for measured
curation as a fallback or check on judgment curation — not, in this
substrate, evidence for the paper's headline gap.

## Where our substrate differs from the paper's

- Synthetic single-step record tasks vs multi-step tool-use benchmarks
  (AppWorld, WebShop, ALFWorld).
- A planted playbook with known ground truth vs playbooks grown by real
  memory systems (ACE, Dynamic Cheatsheet) over real task histories.
- 18 eval tasks: one task is ≈5.6 points of success rate. All rates
  here should be read with that granularity.
- One fixed randomized-assignment design (same matrix in both phases),
  so the replication tests model robustness more than independent
  curation noise.
- Different models from the paper's three; model strings in the data
  are as recorded at run time.

## Limits

- The 0.956 tag correlation must not be read as evidence that agent
  judgment is reliable on real playbooks; the fixture's lessons are
  cleanly separable by construction (see above).
- Condition 2 of our bar is weak in this substrate because the floor
  is 0% by construction.
- Practice-phase effects repeated exactly across models, so the
  replication is a weaker independence test than it appears.
- Nothing here measures RBC on grown playbooks, multi-step tasks, or
  at the paper's scale; claims beyond this substrate are not supported
  by this data.

## Repository layout

- `data/runs.jsonl` — every recorded run (518 lines: validity, main,
  replication, practice, and curation records), with per-run success,
  enactment, tokens, wall time, and the model output (truncated to 500
  characters, as recorded).
- `data/analysis.json` — the aggregate analysis; `code/analyze.py`
  reproduces it exactly from `data/runs.jsonl` and the curation files.
- `data/curation-*.json` — the two curation records (arm C tag passes
  and majority; arm D block effects and kept blocks), one per phase.
- `data/tasks.json` — the fixture set; `code/gen_fixtures.py`
  regenerates it exactly.
- `code/check.py` — the deterministic checker; run it to verify all 30
  reference completions pass.
- `code/run_experiment.py` — the runner (arms, packets, curation,
  phases). `code/model_client.py` is a public-API shim for model
  access (the original runs used the lab's internal harness for this);
  experiment logic is unchanged.

To re-run: copy `data/tasks.json` next to the code, set
`GEMINI_API_KEY` and/or `OPENROUTER_API_KEY`, then e.g.
`python3 run_experiment.py --phase main --backend gemini` or
`--phase replication --backend openrouter --model deepseek/deepseek-v4.1-flash --reps 1`.

Data note: the only transformation applied to the published dataset is
normalization of an internal run label (the `exp` field) and the
docstring/plumbing adaptations in the runner noted above. All numbers,
outputs, and timestamps are as recorded.

## Licence

MIT (see `LICENSE`). The paper itself is © its authors; this packet
contains no text from the paper beyond short attributed figures quoted
for comparison.

*Contact: we welcome corrections — especially anywhere our substrate
misrepresents the paper's method. See the repository issues.*
