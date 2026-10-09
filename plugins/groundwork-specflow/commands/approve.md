---
description: Approve one or more RFCs or specs (human sign-off, recorded against each document's content). Usage - /groundwork-specflow:approve <path | RFC-0001> [more paths]
argument-hint: <document path | RFC-NNNN> [more paths …]
disable-model-invocation: true
---
The groundwork UserPromptSubmit hook has already executed this approval for the user; its result is in your context under "[groundwork approve]". Report that result in one or two lines. If it says REFUSED, explain why and what must change first. Do not run anything yourself and do not edit documents to work around a refusal.
