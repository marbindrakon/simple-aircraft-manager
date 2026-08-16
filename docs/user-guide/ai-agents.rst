AI Agents (MCP)
===============

Simple Aircraft Manager can act as a Model Context Protocol (MCP) server so AI
assistants — Claude (claude.ai custom connectors), Claude Code, and any other
MCP-capable client — can look up your aircraft's status and record routine data
on your behalf.

The MCP server is disabled by default. Your administrator enables it with the
``MCP_ENABLED`` environment variable (see the Configuration reference).

What agents can do
------------------

Agents authenticate as **you** and see exactly the aircraft your account can
see, with the same role rules as the web interface.

**Read (any role):**

- List your aircraft with hours and an airworthiness rollup
- Refer to an aircraft by tail number or UUID in any tool
- Get a full aircraft summary (components, recent logbook entries, active
  squawks, notes, feature flags)
- Check airworthiness and AD/inspection compliance status
- List squawks and flight logs, search the maintenance logbook
- Review the activity log
- Get oil/fuel consumption statistics

**Write (pilot role or above):**

- Update aircraft hours
- Log flights (with automatic hour cascade and oil/fuel records)
- Report squawks, and resolve them (resolving requires the owner role)
- Add notes
- Record oil/fuel top-offs

Agents cannot perform maintenance-tier changes: no logbook entries, AD
compliance records, inspections, component changes, document management, role
management, or sharing changes. Those remain owner actions in the web
interface. Airworthiness enforcement also applies to agents: a grounded
aircraft rejects hour updates and flight logs.

Connecting from claude.ai
-------------------------

By default, an administrator first registers the connector as an OAuth client
(this instance does not allow anonymous client registration). In the Django
admin, under **Applications → Add**, create a *confidential* application with
the *authorization-code* grant and redirect URI
``https://claude.ai/api/mcp/auth_callback``, and note the generated client ID
and secret.

Then in claude.ai:

1. Go to **Settings → Connectors → Add custom connector**.
2. Enter your instance's MCP URL: ``https://your-instance.example.com/mcp``.
3. Under **Advanced settings**, enter the client ID and secret from the step
   above.
4. Claude opens your instance's login page. Sign in (your normal account,
   including single sign-on if your instance uses it) and approve the requested
   access.

(If your administrator has enabled ``MCP_DCR_ENABLED``, claude.ai registers
itself automatically and the client ID/secret step is skipped.)

Tokens expire and refresh automatically. To revoke an agent's access, an
administrator can delete its application/tokens in the Django admin.

Connecting from Claude Code
---------------------------

.. code-block:: bash

   claude mcp add --transport http sam https://your-instance.example.com/mcp

Claude Code will walk through the same browser login and consent flow.

Scopes
------

Access tokens carry OAuth scopes:

- ``read`` — read-only tools
- ``write`` — the recording tools listed above

A token with only the ``read`` scope cannot call write tools (they are not
even advertised to it).
