# Beyond90 AI — Project Brief

## Hackathon

Microsoft Inside the Game: Developer Hackathon 2026.

**Deadline:** October 27, 2026, 11:59 PM Pacific.

**Goal:** Build an original, functioning, Azure-integrated AI football intelligence platform that uses synthetic match events.

## Project Vision

**Beyond90 AI — Football intelligence that proves its insights.**

Beyond90 analyzes simulated football matches, identifies meaningful patterns, explains tactical developments using verifiable evidence, and delivers personalized insights to fans, analysts, and broadcasters.

## Required Pipeline

1. **Ingest:** Receive synthetic football events in chronological order.
2. **Interpret:** Calculate accurate match statistics and detect meaningful changes.
3. **Explain:** Investigate important moments using AI and supporting evidence.
4. **Render:** Generate synchronized, broadcast-ready insights.
5. **Personalize:** Offer casual, analyst, and player-focused experiences.

Include automated match recaps and multilingual storytelling.

## Main Differentiator

The simulator introduces hidden tactical interventions, such as a change in pressing strategy.

The analytics engine and AI agents must infer these changes from observable match events without accessing the hidden instructions.

We will measure detection accuracy, false alarms, detection delay, and explanation reliability.

The system must distinguish supported insights from uncertain or unsupported claims.

## Fundamental Engineering Rules

- Use fictional teams, players, and synthetic data.
- Never expose hidden tactical intervention metadata to the live analysis system.
- Never allow live analysis to access future match events.
- Calculate deterministic statistics in code, not with LLMs.
- Ground AI-generated explanations in event IDs and verified statistics.
- Allow the system to decline unsupported tactical claims.
- Use reproducible simulation seeds and automated tests.
- Never fabricate evaluation results.
- Keep development realistic for the hackathon deadline.

## Initial Technology Direction

- Python for simulation and analytics.
- React and TypeScript for the frontend.
- Microsoft Agent Framework for AI orchestration, subject to compatibility testing.
- Microsoft Foundry for hosted AI models where available.
- Azure for deployment.

Specific deployment services and model choices remain unconfirmed.

## Priorities

1. Correct synthetic football simulation.
2. Real-time match intelligence.
3. Evidence-backed AI explanations.
4. Working broadcast and personalized experiences.
5. Measured reliability and a compelling demonstration.

Do not prioritize unnecessary complexity over a functioning submission.