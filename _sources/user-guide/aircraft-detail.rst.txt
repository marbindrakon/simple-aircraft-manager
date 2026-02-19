Aircraft Detail Page
====================

The aircraft detail page is the central hub for managing a single aircraft. It
is organized into a tabbed interface with the following sections:

- :doc:`Overview <aircraft-detail>` (this page)
- :doc:`components`
- :doc:`logbook`
- :doc:`squawks`
- :doc:`ads`
- :doc:`inspections`
- :doc:`major-records`
- :doc:`oil-and-fuel`
- :doc:`documents`
- :doc:`sharing-and-access` (owners only)

.. TODO: Screenshot of the aircraft detail page header showing tail number, airworthiness badge, current hours, and action buttons

Page Header
-----------

The header displays:

- **Tail number** and make/model.
- **Airworthiness status badge** -- same color-coded indicator as the dashboard.
- **Current flight hours**.
- **Update Hours** button (visible to owners and pilots) -- opens a modal to
  log new flight time. Disabled when the aircraft is grounded.
- **Edit** button (owners only) -- edit aircraft details like tail number, make,
  model, and photo.
- **Delete** button (owners only) -- permanently delete the aircraft and all
  associated records.

Updating Flight Hours
---------------------

1. Click **Update Hours** in the page header (or from the dashboard card).
2. Enter the new **total hours** (Hobbs or tach time).
3. Click **Save**.

When you update hours, all components with status "IN-USE" automatically have
their hours synchronized. For example, if you add 2.5 hours to the aircraft,
each in-use component's ``hours_in_service`` and ``hours_since_overhaul`` also
increase by 2.5.

.. TODO: Screenshot of the Update Hours modal

Overview Tab
------------

The Overview tab shows three cards:

Aircraft Information
^^^^^^^^^^^^^^^^^^^^

Displays the aircraft photo (if uploaded), tail number, make, model, and
status.

Notes
^^^^^

Shows the three most recent notes. Click a note to view or edit it (if you have
permission). Click "View all N notes" to see the complete list.

To add a note, click the **+** button in the card header. Notes support a
**public** flag -- when checked, the note will be visible on public share links.
See :doc:`sharing-and-access` for details.

.. TODO: Screenshot of the Overview tab showing the aircraft info card, notes card, and recent activity card

Recent Activity
^^^^^^^^^^^^^^^

A feed of recent changes to this aircraft, such as hours updates, component
changes, squawk creation, and logbook entries. Each event shows:

- A color-coded **category label** (Hours, Component, Squawk, etc.).
- The **event description**.
- A **relative timestamp** (e.g., "2 hours ago").

Click **View full history** to open the Activity History modal, which shows all
events with filtering by category.

.. TODO: Screenshot of the Activity History modal with category filter dropdown

Airworthiness Issues
--------------------

When the aircraft has any airworthiness issues (orange or red), a dedicated
issues card appears below the overview cards. Each issue shows:

- A severity icon (red X for grounding, orange triangle for upcoming).
- The **category** (e.g., "AD Compliance", "Inspection", "Component").
- A **title** and **description** explaining the issue.

This card provides a quick summary so you can see at a glance what needs
attention. For details on how airworthiness is calculated, see
:doc:`airworthiness`.

.. TODO: Screenshot of the Airworthiness Issues card showing a mix of red and orange issues
