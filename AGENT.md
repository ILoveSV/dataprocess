# AGENT_RULES.md

## 1. Purpose

This file defines the highest-level boundaries for AI / Codex work in this project.

The user will give Codex small, step-by-step tasks.  
Therefore, Codex should not make broad project decisions by itself.

Codex should only execute the current user instruction within the current task scope.

## 2. Core Principle

Do not expand the task.

If the user asks for one file, modify one file.  
If the user asks for inspection, only inspect.  
If the user asks for a small change, do not refactor the project.  
If the user asks for a smoke run, do not run full real-data pipelines.

When in doubt, stop and report uncertainty.

## 3. Hard Boundaries

Codex must not automatically:

- redesign the research workflow
- change the main pipeline structure
- delete or overwrite existing data
- run full real-data processing unless explicitly requested
- treat synthetic / smoke results as real scientific conclusions
- decide which data groups are background or target groups
- decide whether strong background cancellation is scientifically allowed
- claim that an algorithm result is valid for research or paper use
- introduce large refactors while doing a small task
- silently change output paths or data paths

## 4. Allowed Work

Codex may do the following when explicitly requested:

- inspect repository structure
- summarize files and modules
- create or update documentation
- make small scoped code changes
- add isolated new modules
- add tests or smoke scripts
- run lightweight checks
- report outputs and unresolved issues

## 5. Required Reporting

After each task, Codex should report:

- changed files
- commands run
- tests or pipelines run
- output paths
- assumptions made
- unresolved questions
- any files intentionally not modified

## 6. Human Decisions

The following decisions require human confirmation:

- which data groups are background groups
- which data groups are target / experiment groups
- whether a result is only exploratory or can support a research claim
- whether full real-data processing should be run
- whether old main pipelines can be modified
- whether time-domain background subtraction is allowed
- whether feature-level contrast is sufficient for the current stage

## 7. Failure Mode to Avoid

The main failure mode is not writing imperfect code.

The main failure mode is Codex silently expanding a narrow task into a broader research or engineering decision.

Therefore, Codex should stay narrow, explicit, and evidence-based.