Airworthiness Directives (ADs)
==============================

The ADs tab tracks FAA Airworthiness Directives that apply to your aircraft.
ADs are mandatory safety requirements that must be complied with to maintain
airworthiness.

The ADs tab in the navigation shows a **badge count** when there are overdue or
upcoming AD compliance issues.

AD List
-------

ADs are displayed in a table with the following columns:

- **AD Name** -- The AD number or identifier (e.g., "2024-01-05").
- **Description** -- A short summary of what the AD requires.
- **Recurring** -- Whether the AD requires repeated compliance, and at what
  interval (hours or months).
- **Status** -- Color-coded compliance status:

  - **Compliant** (green) -- The AD is currently in compliance.
  - **Due Soon** (orange) -- Compliance is coming due within 10 hours or
    30 days.
  - **Overdue** (red) -- Compliance has lapsed. This grounds the aircraft.
  - **Not Complied** -- No compliance record exists yet.

- **Last Complied** -- The date of the most recent compliance action.
- **Next Due** -- When the next compliance action is due (date or hours).

.. TODO: Screenshot of the ADs table showing a mix of compliant, due soon, and overdue ADs

Adding an AD
------------

1. Click **Add AD** on the ADs tab (owners only).
2. Fill in:

   - **AD Name** -- The official AD number.
   - **Short Description** -- A brief summary.
   - **Compliance Type** -- Select the type:

     - **Standard** -- A normal recurring or one-time AD.
     - **Conditional** -- An AD that only applies when a trigger condition is
       met. Enter the trigger condition in the field that appears.

   - **Recurring** -- Check this if the AD requires repeated compliance.
   - **Recurring Hours** -- For hour-based recurrence (e.g., every 100 hours).
   - **Recurring Months** -- For calendar-based recurrence (e.g., every 12
     months).

3. Click **Save**.

.. TODO: Screenshot of the Add AD modal

Recording Compliance
--------------------

When you comply with an AD:

1. Click the **checkmark** button on the AD row.
2. Fill in the compliance record:

   - **Date Complied** -- The date the compliance action was performed.
   - **Hours at Compliance** -- Aircraft hours at the time.
   - **Notes** -- Details about what was done.
   - **Permanent** -- Check this if the compliance action permanently resolves
     the AD (e.g., replacing the affected part with a non-affected part).

3. Click **Save**.

For recurring ADs, the system automatically calculates the **next due** date
or hours based on the recurrence interval and the last compliance record.
Monthly and annual recurrence uses end-of-month calculation -- if an AD is due
every 12 months from a compliance date of January 15, the next due date is the
end of January the following year.

.. TODO: Screenshot of the Record Compliance modal

Viewing Compliance History
--------------------------

Click the **history** icon on any AD row to view the full compliance history,
showing all past compliance records with dates, hours, and notes.

.. TODO: Screenshot of the AD compliance history modal

Editing and Removing ADs
------------------------

- Click the **pencil** icon to edit an AD's details.
- Click the **X** icon to remove an AD from tracking. This does not delete the
  AD's compliance history.
