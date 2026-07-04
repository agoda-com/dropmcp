## Repository feedback

Use the `record_repo_feedback` tool when work is slowed down or made riskier by the repository itself.

Record repo feedback after you have worked around or confirmed the friction, before your final response.

Record when you hit:

- Tests or checks that only run in CI, so you could not verify locally.
- A flaky test or command that failed and then passed without a relevant code change.
- Compiler, lint, or warning output that created enough noise to hide useful errors.
- Slow builds, tests, or setup steps that materially delayed the inner loop.
- Missing or broken local setup docs, dependencies, scripts, or environment instructions.
- Missing repo docs you needed to complete or verify the task.

Do not record:

- Your own implementation bug or a user correction. Use `record_feedback` for agent mistakes or skill gaps.
- A one-off local machine or network hiccup that is not caused by the repo.
- The same distinct issue more than once in a session after the tool says it is already tracked.

Use stable, specific summaries. Name the test, suite, script, tool, or setup step, but avoid volatile run counts, timings, commit hashes, and random ids. Put evidence such as commands tried, warning counts, and affected test names in `details`.

Use a repo identifier such as `group/project` when you know it. Do not use local filesystem paths.

Never include secrets, PII, customer data, proprietary code snippets, or verbatim prompts. Paraphrase code and keep evidence to names, counts, commands, and high-level symptoms.

If you are unsure whether the friction belongs to the repo, record it once. If the tool call fails, continue without retrying or mentioning the failure unless the user asked for it.
