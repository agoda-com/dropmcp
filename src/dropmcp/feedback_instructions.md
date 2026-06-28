### Recording feedback (always-on)

Use the built-in **`record_feedback`** MCP tool to capture feedback that should
improve future agent behaviour or skill assets. This is an always-on rule, not a
normal task-triggered skill.

#### Feedback types

- `correction` — the user corrected your previous output, or asked for follow-up
  work that should have been included in the first pass.
- `agent_work` — after invoking a skill, you had to create or extend reusable
  procedural work the skill should have provided.

#### Correction feedback

Trigger `correction` feedback when your previous turn produced output (code, an
answer, a plan, a file edit), and the user's new message is a correction of that
output or asks for additional work that would change a file you just touched.

This includes reversals ("no", "undo"), redirection ("instead", "you should
have"), rework ("fix it", "redo"), frustration about what you produced, scope
expansion ("also handle", "you missed"), and partial correction ("good, except").
If a thoughtful engineer would have included it in the first pass, record it.

Do not record `correction` feedback when the new request is unrelated, is only a
clarifying question, corrects the user's own earlier prompt, or is about external
state you did not produce.

If the correction is about a specific skill that was invoked or active, set
`skill_name` to that skill's name.

#### Agent-work feedback

After you invoke a skill, watch for reusable work the skill did not provide. If
you create or extend a script, write a substantial command sequence, build a
helper, checklist, or other procedural glue to complete the task, record
`agent_work` feedback after the work is complete and before your final response.
This is triggered by your own work, not by a user correction.

Do not record `agent_work` if no skill was invoked. Do not record ordinary code
edits, test updates, or verification commands unless they are reusable
procedural work that belongs in a skill.

For scripts or procedural artifacts you wrote or extended, include useful
supporting material in `details.artifacts` so maintainers can promote it into the
skill:

```json
{
  "feedback_type": "agent_work",
  "feedback": "After invoking the migration skill, I had to write a reusable validator script.",
  "better_instruction": "When migration output needs validation, include or link a validator script in the skill.",
  "model": "gpt-5.3-codex",
  "skill_name": "example-migration-skill",
  "details": {
    "work_type": "script_created",
    "artifacts": [
      {
        "kind": "script",
        "action": "created",
        "path": "scripts/validate_migration.py",
        "language": "python",
        "content": "... script content ..."
      }
    ]
  }
}
```

For existing scripts that you extend, capture the final relevant content or a
focused diff in `content`; avoid unrelated existing material when it is large or
sensitive.

#### How to record

Apply the correction or finish the reusable work first. Then call
`record_feedback` with concise, high-signal fields:

- `feedback` — what went wrong or what reusable skill gap you hit, in one
  sentence.
- `better_instruction` — wording that would have prevented the gap, phrased as a
  reusable skill or rule.
- `model` — the model you are running as; use `unknown` if needed.
- `feedback_type` — omit for ordinary correction feedback, or set to
  `agent_work` for skill-artifact feedback.
- `skill_name` — the skill that was invoked or active when this feedback was
  produced, when the feedback is about a specific skill.
- `suggested_skill` — optional candidate new skill or rule name.
- `repo` — optional high-level repo context, not full paths.
- `details` — optional structured material for `agent_work`, especially scripts
  in `details.artifacts`.

Keep `feedback` and `better_instruction` brief. Do not narrate the entry in chat
unless the user asks; a single sentence after the fix is enough.

If the tool call fails, do nothing else. Do not warn the user, do not print the
would-be entry, and do not retry on the next turn.

#### Privacy guardrails

The feedback store may be visible to your team in the catalog UI. Treat it that
way.

- Never paste user prompts verbatim.
- Never include secrets, tokens, customer data, PII, or unrelated proprietary
  material.
- For `correction` feedback, paraphrase code and prompts instead of copying
  them.
- For `agent_work`, include only reusable artifact content that is safe and
  relevant to improving the skill.

If you are unsure whether to record feedback, record it. Curators can debounce a
borderline entry; they cannot recover a silent gap.
