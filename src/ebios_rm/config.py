"""Environment-driven settings and the single model factory.

OpenRouter is the sole model provider in every environment; only MODEL_ID
changes between test and production. No agent or workshop may reference a
provider or model name directly (conception CONCEPTION.md §3.2, §13.1).
"""
