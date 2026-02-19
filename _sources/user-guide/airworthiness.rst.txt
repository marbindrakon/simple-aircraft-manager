Airworthiness Status
====================

Simple Aircraft Manager automatically calculates an overall airworthiness
status for each aircraft based on multiple factors. This status is displayed
as a color-coded badge throughout the application.

Status Levels
-------------

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Status
     - Color
     - Meaning
   * - Airworthy
     - Green
     - All checks pass. No issues found.
   * - Caution
     - Orange
     - One or more items are approaching their limits. The aircraft can still
       fly, but attention is needed soon.
   * - Grounded
     - Red
     - One or more grounding conditions exist. The aircraft should not fly
       until the issues are resolved. The "Update Hours" button is disabled.

How Status is Calculated
------------------------

The system checks the following areas, in order. The overall status is
determined by the most severe issue found:

1. AD Compliance
^^^^^^^^^^^^^^^^

- **Red** -- Any Airworthiness Directive is overdue (past its next-due date or
  hours).
- **Orange** -- Any AD is coming due within **10 flight hours** of its
  hour-based limit.

2. Grounding Squawks
^^^^^^^^^^^^^^^^^^^^

- **Red** -- Any active squawk with priority "Ground Aircraft" (priority 0)
  exists.

3. Inspection Recurrency
^^^^^^^^^^^^^^^^^^^^^^^^

- **Red** -- Any required recurring inspection is overdue (past its next-due
  date or hours).
- **Orange** -- Any inspection is coming due within **10 flight hours** or
  **30 calendar days**.

4. Component Replacement
^^^^^^^^^^^^^^^^^^^^^^^^

- **Red** -- Any replacement-critical component has exceeded its replacement
  hours interval (hours in service >= replacement hours).
- **Orange** -- Any replacement-critical component is within **10 flight hours**
  of its replacement interval.

Understanding the Issues Card
-----------------------------

When issues exist, the Overview tab shows an Airworthiness Issues card listing
each issue with:

- **Severity** -- Red (grounding) or orange (upcoming).
- **Category** -- Which system flagged the issue (AD Compliance, Inspection,
  Component, or Squawk).
- **Title** -- The specific item (e.g., "AD 2024-01-05" or "Annual
  Inspection").
- **Description** -- Details about why it was flagged (e.g., "Overdue by 15
  hours" or "Due in 8 hours").

.. TODO: Screenshot of the Airworthiness Issues card with explanatory annotations

Dashboard Indicators
--------------------

On the :doc:`dashboard`, each aircraft card shows:

- The **airworthiness badge** with icon and text.
- **Issue counts** -- separate counts for grounding (red) and upcoming (orange)
  issues.
- A **colored border** on the card matching the worst status.

.. TODO: Screenshot of dashboard cards showing green, orange, and red airworthiness states side by side

Resolving Issues
----------------

To return an aircraft to green status, address each flagged issue:

- **Overdue AD** -- Record a compliance action on the :doc:`ads` tab.
- **Grounding squawk** -- Resolve the squawk on the :doc:`squawks` tab.
- **Overdue inspection** -- Record an inspection on the :doc:`inspections` tab.
- **Component replacement due** -- Reset the service time on the
  :doc:`components` tab, or replace/remove the component.

The airworthiness status recalculates automatically whenever you make changes.
