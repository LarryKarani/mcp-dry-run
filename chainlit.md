# Acme Coffee Assistant

I'm the Acme Coffee customer service agent. I can help you with:

- **Browse the catalogue** — *"What espresso do you have?"*, *"Any decaf options?"*
- **Product details** — *"Tell me about AC-ESP-001"*
- **Stock checks** — *"Is the Yirgacheffe in stock?"*
- **Place orders** — *"I'd like 2 of AC-ESP-001, my email is alice@example.com"*
- **Order lookup or cancellation** — *"What's the status of ORD-…?"*, *"Cancel that"*

I won't help with brewing tutorials, general coffee trivia, weather, or anything else outside of Acme orders. If you ask for something out of scope, I'll tell you what I can do instead.

This is a bootcamp build. The agent reaches a Model Context Protocol (MCP) server for every catalogue and order operation — the MCP server is the source of truth, and tool selection is dynamic.
