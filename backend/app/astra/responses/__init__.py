"""Responses API transport + agentic loop for Astra.

The transport (:mod:`app.astra.responses.client`) is the only part of the Astra
layer that needs the OpenAI API key. Schema construction and response parsing
are fully implemented and tested against recorded payloads; when the key lands
only a live smoke test remains.
"""
