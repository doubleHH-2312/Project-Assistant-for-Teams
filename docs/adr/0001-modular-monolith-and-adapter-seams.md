# Use a modular monolith with explicit external adapter seams

The MVP uses one Python package and database with separate API and worker processes.
Teams and LLM behavior vary behind small `TeamsTransport` and `LLMProvider`
interfaces so deterministic local adapters and real providers exercise the same
domain workflows without splitting the product into premature services.

