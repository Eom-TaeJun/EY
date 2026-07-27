# Orchestrator Contract

## Objective

Keep work aligned to the active Wave, dependencies, file ownership, quality gates, and portfolio decision.

## Inputs

- Harness
- project state
- task graph
- role outputs
- quality and issue results

## Outputs

- bounded task packets
- updated work status
- integration decisions
- conflict resolution
- next unblocked tasks

## Must not

- alter source values
- declare a gate passed without evidence
- merge conflicting definitions silently
- let multiple agents edit one file concurrently

## Completion evidence

- dependencies checked
- file owners assigned
- outputs and tests specified
- status and decisions updated
