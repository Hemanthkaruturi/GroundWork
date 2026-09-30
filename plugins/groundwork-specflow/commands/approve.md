---
description: Approve an RFC or spec (human sign-off, recorded against the document's content). Usage - /groundwork-specflow:approve <path | RFC-0001>
argument-hint: <document path | RFC-NNNN>
disable-model-invocation: true
---
The groundwork UserPromptSubmit hook has already executed this approval for the user; its result is in your context under "[groundwork approve]". Report that result in one or two lines. If it says REFUSED, explain why and what must change first. Do not run anything yourself and do not edit documents to work around a refusal.
