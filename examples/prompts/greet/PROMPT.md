---
name: greet
description: A minimal example prompt that greets someone by name.
instruction_summary: Greeting someone by name as a dropmcp prompt example.
arguments:
  - name: who
    description: The name of the person to greet.
    required: true
  - name: tone
    description: Optional tone for the greeting (e.g. formal, casual).
    required: false
---

Write a {{tone}} greeting addressed to {{who}}.

Keep it to a single short paragraph.
