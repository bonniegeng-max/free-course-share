---
name: free-course-share
version: 1.1.9
description: Verify whether a course is truly free, screen or compare free courses, build a shortlist, or draft accurate share copy. Use when the user requests any one of these free-course tasks; combine them only when requested.
allowed-tools: WebSearch, WebFetch
---

# Free Course Verifier & Share Kit

## What It Does

Verify whether a course is genuinely free, compare free-course options, build an evidence-based shortlist, or turn verified course facts into reviewable sharing copy.

The user may request any one mode or combine several modes:

- **Verify** one course or certificate offer.
- **Find** suitable free courses for a stated goal.
- **Compare** two or more course options.
- **Shortlist** the strongest verified choices.
- **Draft** accurate sharing copy from verified or user-provided facts.

Do not require course curation and share-copy creation to appear together.

## When to Use

Invoke when the request explicitly concerns a free course, free learning resource, free certificate, audit track, scholarship-funded course, or a course offer whose free scope needs checking.

Examples:

- “这门课现在真的免费吗？证书也免费吗？”
- “推荐几门免费的数据分析入门课。”
- “比较这三门公开课，帮我选一门。”
- “筛选 5 门适合零基础的免费 Python 课。”
- “把这些已经核实的课程信息写成一段分享文案。”
- “Find free cybersecurity courses with a verifiable certificate.”

Do not invoke for:

- a general learning plan with no request to find or verify courses;
- paid-course shopping when free access is irrelevant;
- unrelated promotional copy;
- automatic enrollment, purchasing, posting, or account actions.

## Operating Boundary

- Work only with user-provided facts and publicly accessible course pages.
- Use `WebSearch` and `WebFetch` only when current public facts require verification.
- Keep all activity read-only.
- Do not enroll, purchase, sign in, submit forms, publish content, or modify external data.
- Return reviewable results in the current conversation unless the user explicitly requests a file.

## Decide the Requested Mode

Infer the smallest mode that satisfies the request:

| Request | Mode | Default output |
|---|---|---|
| Check one offer | Verify | Verification result and restrictions |
| Discover options | Find | Candidate list with evidence status |
| Choose among options | Compare | Comparable table and recommendation |
| Reduce a long list | Shortlist | Ranked shortlist and exclusions |
| Prepare public wording | Draft | Reviewable copy with caveats |
| End-to-end request | Combined | Verification, selection, then draft |

Ask one concise question only when a missing constraint would materially change eligibility or ranking. Do not ask for details that can be safely left open.

## Fact Verification

For each relevant course, verify:

- course title and provider;
- whether access is free and exactly what “free” includes;
- whether a certificate, badge, assessment, or graded work costs extra;
- enrollment status, deadline, or expiration when time-sensitive;
- format, level, duration, prerequisites, language, and region restrictions;
- subscription, trial, audit-track, financial-aid, or account requirements;
- direct official URL when available.

Use this evidence policy:

1. Prefer the official course or provider page.
2. Cross-check material claims when sources conflict or “free” is ambiguous.
3. Label evidence as `Verified`, `User-provided`, `Unverified`, `Conflicting`, or `Outdated`.
4. Record the verification date for time-sensitive claims.
5. Distinguish free course access from a free certificate.
6. Preserve uncertainty; never invent deadlines, eligibility, certificate value, or availability.

If reliable verification is unavailable, label the gap. Exclude the item only when the user requires verified choices.

## Selection Method

1. Extract the audience, topic, level, goal, time budget, language, region, preferred format, and definition of “free.”
2. Normalize duplicate entries without merging conflicting facts.
3. Check eligibility and access restrictions before ranking.
4. Rank by the user's criteria. When none are supplied, use relevance, access clarity, provider credibility, practical fit, and time cost.
5. Explain each inclusion or exclusion with concise evidence.

## Output Contracts

### Verify

- Course and provider
- Verdict: Fully free / Free to audit / Trial only / Financial aid / Paid / Unclear
- What is free
- What may cost money
- Certificate or badge status
- Important restrictions or dates
- Evidence status and official URL
- Verification date

### Find or Shortlist

- Search criteria and material unknowns
- Candidate courses
- Free-access scope
- Level, format, duration, and prerequisites
- Evidence status
- Include / Exclude / Needs confirmation
- Reason and official URL

### Compare

Use the same fields and definitions for every course. End with a recommendation tied to the user's stated goal, not a generic winner.

### Draft

Create one ready-to-review draft that:

- uses only verified or visibly labeled user-provided facts;
- states restrictions near the relevant claim;
- includes direct course URLs when available;
- avoids false urgency, guaranteed outcomes, and inflated certificate claims;
- notes that availability and terms may change when time-sensitive;
- remains a draft and is not posted automatically.

## Completion Standard

- The requested mode is completed without forcing unrelated outputs.
- Every material claim is supported or visibly labeled.
- “Free” is defined precisely.
- Course access and certificate cost are not conflated.
- Time-sensitive facts include a verification date.
- The work remains read-only and has no external side effects.

## 相关 skill / Related skills

- 推荐文案定稿前跑 `xiaohongshu-prohibited-words`，避免「免费」「最」这类词触发限流。
