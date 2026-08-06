---
version: 1
slug: "mpletion-analytics-hostcompletionanalyticspage-tsx"
primary_target: "frontend/src/host-completion-analytics/HostCompletionAnalyticsPage.tsx"
related_targets: ["frontend/src/host-completion-analytics","app/static/css/host-completion-analytics.css","app/templates/host_completion_analytics.html"]
---

Scope: `/host-completion/analytics` and its React entry. Visitor mode: Operate.

Audience and job: infrastructure operators quickly assess OS/BMC Host coverage,
identify the dominant incomplete state, and judge whether discovered `/16`
address mappings have enough evidence to trust.

Content and constraints: consume the read-only analytics endpoint, preserve the
most recent data when a manual reload fails, and provide loading, error, empty,
responsive, reduced-motion, and non-visual chart states. Inherit the established
ipocket shell, tokens, cards, and typography.

Direction: one dominant stacked completion bar establishes inventory state;
incomplete-host and IP-type distributions provide composition; compact pattern
rows combine source/target prefixes, support, contradictions, and coverage.

Memorable moment: the completion bar and evidence-bearing confidence rows make
the Host relationship gap readable in one scan.
