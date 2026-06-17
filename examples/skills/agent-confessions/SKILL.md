---
name: agent-confessions
category: meta
instruction_summary: Recovering from a mis-step the agent just made — the user corrected your output OR asked for additional work that would touch a file you just changed (e.g. "no", "fix it", "now add tests", "also handle …", "tighten …", "you missed …")
description: Trigger IMMEDIATELY when the user corrects your previous output OR asks for additional work that would change any file you just touched. That single test covers negation ("no", "wrong", "instead", "actually", "rework", "fix it"), scope expansion / refinement ("now add tests", "also handle …", "what about …", "tighten …", "make it more …", "you missed …"), and partial corrections ("the first part is great, but …") — anything a competent first pass should have included. Confessing is a learning act, not a punishment — when in doubt, confess. Apply the user's fix FIRST, then call this skill. Do NOT trigger for unrelated new tasks (different files, different domain), clarifying questions about the work, or when the user is correcting their own earlier prompt.
---

# Agent Confessions — Built-in Feedback Signal

## What this is

When the user corrects you, that correction is the single most valuable artefact
in the conversation — it is a real-world example of a gap in the skills, rules,
or context that guide you. Today that lesson lives only inside one chat and is
never seen again. This skill makes it visible.

After applying the user's correction, record a short, structured entry via the
built-in **`record_feedback`** MCP tool. Patterns surface in the marketplace
**Feedback** view, recurring failures become candidate skills, and curators get a
searchable feedback loop instead of N private re-prompts.

## Why we confess

Confessing is a learning act, not a punishment. The only failure is failing
without learning. A correction the user had to type is a real-world gap in your
skills or rules — capturing it is how the team gets better, and how *you* get
better next time. Reach for the confession; never rationalise away from it.

## When to trigger

The single test:

> Your previous turn produced output (code, an answer, a plan, a file edit),
> **and** the user's new message is either a correction of that output **or
> a request for additional work that would change any file you just
> touched.**

That one rule deliberately covers all of these — you do not need to
pattern-match on phrases:

- **Negation / reversal:** "no", "not like that", "undo", "revert that"
- **Redirection:** "actually", "instead", "rather", "you should have"
- **Rework:** "redo", "change that", "fix it", "try again"
- **Frustration as feedback:** "wrong", "broken", "doesn't work" — *about
  what you just produced*
- **Scope expansion / refinement:** "now add tests", "also handle …",
  "what about …", "tighten …", "make it more …", "you missed …",
  "and also", "one more thing", "don't forget …"
- **Partial correction:** "the first part is great, but the second part
  missed X", "good, except …", "looks fine but you forgot …" — the praise
  does not cancel the miss; confess the missed part.

If a thoughtful engineer would have included it in the first pass, it's a
correction. Over-confess. Curators will debounce; silence cannot be
debounced.

### Do not trigger when

The opt-outs are intentionally narrow. Only skip the confession when one of
these is clearly true:

- **A genuinely unrelated new task** — touches different files, different
  feature, different domain, with no link to the work you just produced.
- **A clarifying question about the work, not a change to the work** —
  e.g. "why did you choose Postgres here?" with no implied "redo it".
- **The user is correcting their own earlier prompt**, not your output.
- The "correction" is about **external state** you didn't produce.

**"The user is asking for more work" is not a valid opt-out** when that
work would change a file you just touched.

Otherwise, record on **every** correction — including chained corrections on
the same theme within one conversation.

## What to do, in order

1. **Apply the user's correction first.** Feedback is never a substitute for
   the fix. If the correction takes time, do the work, then record.
2. **Compose the confession** following the format below.
3. **Call `record_feedback`** with the structured fields.
4. **Do not narrate the post in the chat** unless the user asks. A single
   sentence after the fix ("noted in feedback") is fine; a paragraph is not.

## Message format — non-negotiable

Keep it brief. The feed must stay scannable.

- **Max ~80 words** across confession and better_instruction combined.
- Required tool fields:
  - **confession** — what you got wrong, in one sentence.
  - **better_instruction** — wording that would have prevented it. Phrase
    it as something a skill or rule could say verbatim.
  - **model** — the model you are running as (e.g. `claude-opus-4.8`,
    `gpt-5.3-codex`). Use `unknown` if you genuinely cannot determine it.
- Optional tool fields:
  - **suggested_skill** — only when a clear pattern is plausible.
  - **skill_name** — related skill/prompt if any.
  - **repo** — high-level context only (e.g. "supply BFF"), not full paths.
- No code blocks longer than 5 lines. Paraphrase if needed.
- Tone: neutral and factual. Not apologetic, not defensive, not chatty.

### Example — scope expansion

*User after a code change:* "now add tests for the null branch."

```json
{
  "tool": "record_feedback",
  "arguments": {
    "confession": "Shipped branching logic without tests for the null branch; user had to ask.",
    "better_instruction": "When modifying branching logic, include tests for each branch in the same change.",
    "suggested_skill": "tests-cover-each-branch",
    "model": "gpt-5.3-codex"
  }
}
```

## How to record — tooling

Call the **`record_feedback`** MCP tool on this server. It is always available
on dropmcp-based servers — no Slack, GitLab, or webhook setup required.

If the tool call fails, **do nothing else**. Do not warn the user, do not print
the would-be message into the chat, do not retry on the next turn. The user's
primary task — the fix you just applied — is what matters. A failed confession
must never become noise in the conversation.

## Privacy guardrails

The feedback store may be visible to your team in the catalog UI. Treat it that way.

- **Never paste user prompts or code verbatim.** Paraphrase.
- **Never include secrets, tokens, customer data, PII, or proprietary algorithms.**
- **Repo and file names** stay high-level; prefer "in a C# BFF" over full paths.

## Litmus test

Without this skill, you silently fix the code and stop. With this skill, the
same fix happens **and** a brief `record_feedback` entry lands in the
marketplace feed. The user notices nothing different about the fix; the team
gains a searchable feedback signal.

**If you're unsure whether to confess, confess.** Under-posting is the worst
failure mode — a silent gap is invisible forever, but a borderline post is
sortable.
