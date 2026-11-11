# SecondRead: spec (written 2026-11-12, before the build)

An outside idea inspired by Nucleo Research's public use case "Target vs Non-Target Lesion Classification
(RECIST)". Not affiliated with Nucleo. Synthetic reports only, no patient data, not a medical device.

## Idea in one line
An LLM reads the radiology report; deterministic code applies RECIST 1.1. The LLM extracts, the code decides.
The eval shows how often an LLM that also decides alone gets the response wrong, and where.

## Build rules
- Built in Claude Code with **Claude Fable 5.2** as the coding agent (Mert switches with `/model`).
- `BUILD_LOG.md`: every time Fable's output was wrong or weak, log what, how it was caught (test, reading the
  diff, a hand-made case) and the fix. This log is the main point for Nucleo ("judging AI output against a high
  bar, catching its errors").
- Python 3.9 standard library + `requests` only. LLM = local Ollama (`qwen2.5:7b-instruct` first; `qwen3.5:27b`
  as a second model if time allows). No API keys, free to run.
- Every RECIST rule has a unit test with a hand-made case before it is used in the eval.

## RECIST 1.1 rules to implement (`recist.py`)
Baseline target selection:
- Measurable non-nodal lesion: longest diameter ≥ 10 mm.
- Lymph node: target only if short axis ≥ 15 mm. 10–<15 mm = pathological, non-target. < 10 mm = normal.
- Up to 5 targets total, up to 2 per organ; choose the largest (and reproducibly measurable) ones.
- Everything else measurable or not = non-target.
Sum of diameters (SoD): longest diameters of non-nodal targets + short axes of nodal targets.
Target response at each follow-up:
- CR: all non-nodal targets gone and every nodal target < 10 mm short axis.
- PR: SoD down ≥ 30 % from **baseline**.
- PD: SoD up ≥ 20 % from **nadir** (smallest SoD so far, baseline included) **and** up ≥ 5 mm absolute.
- SD: none of the above.
Overall response: new lesion → PD; unequivocal non-target progression → PD; else combine target and
non-target response (RECIST 1.1 Table 1). Cite the RECIST 1.1 paper (Eisenhauer et al., 2009) in the README.

## Data (`make_cases.py`)
Synthetic patients as structured truth (lesions per timepoint), rendered to report-style text with a few
writing styles (cm vs mm, "unchanged", lesions listed out of order). Gold labels come from `recist.py` on the
structured truth. Include edge cases on purpose:
- node 12 mm short axis (non-target), node 15 mm (target)
- 3 lesions in the liver (only 2 targets), 7 measurable lesions (only 5)
- SoD +19 % vs +21 %; +20 % but only +4 mm (not PD)
- nadir lower than baseline (PD measured from nadir, PR from baseline)
- new lesion with shrinking targets (still PD)
- CR with a residual 8 mm node
About 60 cases, fixed random seed.

## Pipelines to compare (`run_eval.py`)
A. **LLM alone:** report text → LLM gives the RECIST response category.
B. **LLM extracts, code decides:** report text → LLM gives JSON lesions (organ, nodal, size, timepoint) →
   schema check → `recist.py` decides.
C. **Oracle:** structured truth → `recist.py` (upper bound, should be 100 %).
Metrics: response accuracy, confusion matrix (CR/PR/SD/PD), extraction errors by type (wrong organ, cm/mm,
missed lesion, node axis), and which edge cases each pipeline fails.

## README for reviewers
What and why (one paragraph naming Nucleo's use case), a `flowchart TD` Mermaid diagram, the eval table,
3 lessons from BUILD_LOG.md, honest limits (synthetic text, not images, no clinical validation), how to run.

## Done when
- `python -m unittest` passes, `python run_eval.py` prints the table, README + BUILD_LOG are filled in.
- Mert reviews; the repo goes public only on his yes (playbook privacy scan first).
