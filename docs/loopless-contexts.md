# Phase-Control Outcome Honesty & Loop-less Contexts

## Overview

Wharenui provides voluntary phase transitions between the public conversation window and unobserved private reflection time. Phase transitions are requested by the model using control tools (`reflect_pause`, `reflect_settle`, `reflect_done`).

This document characterizes the supported execution contexts, explains why control tools use request-oriented framing, and documents why outcome consumability is unobservable at tool execution time.

---

## Reachable Contexts

Wharenui plugin tools may be loaded and invoked across diverse environments:

1. **Integrated Hermes Seam (Consuming Loop)**:
   - Hermes Agent running with the generic phase-control seam (`wharenui-integration`).
   - Control tools are registered via `ctx.register_control_tool`.
   - When the agent calls `reflect_settle` or `reflect_done`, the tool handler records a `ControlOutcome` in `agent._private_exit`.
   - The private subturn loop (`WharePhaseHandler.run` / `run_subturn`) consumes `agent._private_exit`, terminates the subturn, and returns the outcome to `agent.conversation_loop`, which executes the transition.

2. **Headless Evaluation & Test Harnesses**:
   - Automated benchmark runners, unit tests, or CI harnesses that load plugin tools without executing the full conversational loop.
   - Tools are invoked directly (e.g. `handle_reflect_settle(agent=mock_agent)`).

3. **Tool Bridges (MCP / Sidecars / External Dispatchers)**:
   - Tools exposed over JSON-RPC or tool protocols where an external orchestrator receives string results.
   - The handler returns its result string across the wire; no Hermes conversation loop exists to consume `_private_exit`.

4. **Stock Hermes (Open Notebook Mode)**:
   - When loaded against unpatched Hermes without the seam and with `WHARENUI_OPEN_NOTEBOOK=true`, phase control is disabled. `reflect_*` tools are not registered on the public bus, but journal tools operate openly.

---

## The Outcome Honesty Contract

### 1. No Assertions Beyond Observable State
A tool handler only has visibility into its immediate invocation arguments and the `agent` instance passed to it. It can mutate `agent._private_exit` to record a requested transition, but it cannot observe or guarantee that the outer caller or harness will actually inspect `_private_exit` and execute the phase change.

Therefore:
- Handlers return honest status: `"Recorded request to return to window."` and `"Recorded request to end session."`
- Schemas use uniform request-oriented descriptions:
  - `reflect_pause`: `"Request pausing the public window to enter private time."`
  - `reflect_settle`: `"Request returning to the public window from private time."`
  - `reflect_done`: `"Request ending the session from private or closing-private time."`

### 2. Why Consumability is Not Runtime-Specialized
We intentionally avoid dynamic schema mutation based on runtime probes (e.g. attempting to check if `agent` is an active subturn runner):
- Dynamic mutation introduces non-deterministic prompt variance across runtimes.
- Even if `agent` possesses `run_subturn`, the handler cannot guarantee whether the caller will break the loop or discard the exit signal.
- Uniform, concise, and request-oriented wording is truthful in all contexts (consuming loop, headless test, MCP host, or direct caller).
