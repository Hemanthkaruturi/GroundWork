---
id: {{id}}
title: {{title}}
status: {{status}}
origin: {{origin}}
rfc: {{rfc}}
decided_at: {{decided_at}}
rationale_source: {{rationale_source}}
source: {{source}}
recorded_by: {{author}}
created: {{date}}
supersedes: []
related: []
---

# {{id}} — {{title}}

<!-- An ADR keeps the outcome of a decision. Two kinds:
- after an approved RFC was built (`rfc:` set, status proposed → accepted): written only when the outcome departed from
  the RFC's proposal, or a decision was taken during the build that the RFC does not record — and it records only that.
  The RFC holds the need, the interview and the alternatives; an RFC built as proposed needs no ADR (its row in
  DECISIONS/README.md is the record);
- RETROSPECTIVE (`origin: baseline`, status recorded): a choice found in an existing codebase. Say where the reason
  comes from, and nothing more than that: a commit subject or a folder name proves a topic, never the reason, who
  approved it, or when. `**Source:**` in §3 must be one of: documented in <path or commit> · retrospective explanation
  by <person>, <date> · historical rationale unknown. -->

## 1. Context
[TODO: the situation that forced a choice, as evidenced]

## 2. Decision
[TODO: what was chosen, in one or two sentences]

## 3. Rationale
**Source:** [TODO: documented in <path> | retrospective explanation by <person>, <date> | historical rationale unknown]
[TODO: the reasons, only as far as the source supports them]

## 4. Consequences
[TODO: what this makes easy, hard, or forbidden; what it rules out]

## 5. Evidence
[TODO: files, commits, docs or measurements that show the decision is in effect]

## Changes
_None yet._
