# Offline Learning Contract

## Purpose

This document defines the minimum safe shape of the offline-learning pipeline for the MVP.

## Rules

- Do not update planner or ranking behavior online after each campaign.
- Extract datasets from stored artifacts and traces.
- Keep observational analytics separate from policy changes.
- Require benchmark checks before adopting any new learned policy.

## Current bootstrap implementation

The MVP exports a simple dataset from stored campaign artifacts with:

- campaign ID
- execution mode
- target identifier
- candidate ID
- final rank
- final score
- parent hypothesis
- mock-generation flag

This is not a production learning pipeline. It is the minimum structure required to keep future learning work grounded in stored artifacts rather than chat logs.
