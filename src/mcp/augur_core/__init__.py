"""augur-core: registry/discovery MCP server.

Hosts 29 tools that span all bundles' metadata: skill listings,
hub indexes, ADR/agent/script/test enumerations, scheduled execution
details, capability advertisements.

Per Track 3a design, this server multiplexes registry tools across
all project- and vault-tier bundles via dynamic skill discovery.
"""
