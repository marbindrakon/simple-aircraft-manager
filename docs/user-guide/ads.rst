ADs / Bulletins
===============

The **ADs / Bulletins** tab tracks Airworthiness Directives and other maintenance
bulletins that apply to your aircraft. Mandatory bulletins (such as FAA ADs) affect
airworthiness status; optional/advisory bulletins are tracked for completeness but
do not affect the airworthiness badge.

The tab in the navigation shows a **badge count** when mandatory bulletins have
overdue or missing compliance records.

Bulletin Types
--------------

Each bulletin has a **type** that describes its origin and authority:

- **AD** -- FAA Airworthiness Directive. Mandatory federal regulation.
- **SAIB** -- Special Airworthiness Information Bulletin. FAA advisory;
  non-mandatory.
- **SB** -- Manufacturer Service Bulletin. May be mandatory or optional
  depending on context.
- **Airworthiness Alert** -- FAA advisory notice; non-mandatory.
- **Other** -- Any other bulletin or notice you want to track.

The type is shown as a badge on each row: red for ADs, blue for all others.

Mandatory vs Optional / Advisory
---------------------------------

The **Mandatory** checkbox controls whether a bulletin affects airworthiness
status:

- **Mandatory** -- Overdue or missing compliance turns the airworthiness badge
  red. These appear in the **Mandatory** section of the tab.
- **Not mandatory** -- Tracked for reference but does not affect airworthiness.
  These appear in the **Optional / Advisory** section.

When you add a new AD, the Mandatory checkbox is automatically set to checked.
For SAIBs, SBs, and other advisory types, it is automatically unchecked. You
can override this manually before saving.

Bulletin List
-------------

The tab is split into two sections: **Mandatory** (top) and **Optional /
Advisory** (bottom). Each section shows a table with the following columns:

- **Type** -- Bulletin type badge (AD, SAIB, SB, etc.).
- **Name** -- The bulletin number or identifier (e.g., "2024-01-05",
  "SB-300-27-01").
- **Description** -- A short summary of what the bulletin covers.
- **Recurring** -- Whether repeated compliance is required, and at what
  interval (hours or months).
- **Status** -- Color-coded compliance status:

  - **Compliant** (green) -- Currently in compliance.
  - **Due Soon** (orange) -- Compliance coming due within 10 hours or 30 days.
  - **Overdue** (red) -- Compliance has lapsed. For mandatory bulletins, this
    grounds the aircraft.
  - **Not Complied** -- No compliance record exists yet.
  - **Conditional** -- Only applies when a trigger condition is met.

- **Last Complied** -- Date of the most recent compliance action.
- **Next Due** -- When the next compliance action is due (date or hours).

.. TODO: Screenshot of the ADs / Bulletins tab showing both sections

Adding a Bulletin
-----------------

1. Click **Add Bulletin** on the ADs / Bulletins tab (owners only).
2. Fill in:

   - **Bulletin Type** -- Select the type (AD, SAIB, SB, etc.). Choosing a
     type automatically sets the Mandatory checkbox for you; override as needed.
   - **Mandatory** -- Check to include this bulletin in airworthiness status
     calculations. Uncheck for advisory/optional tracking only.
   - **Name / Number** -- The official bulletin number or identifier.
   - **Short Description** -- A brief summary.
   - **Compliance Type** -- Select the compliance model:

     - **Standard** -- A normal recurring or one-time bulletin.
     - **Conditional** -- Only applies when a trigger condition is met. Enter
       the trigger condition in the field that appears.

   - **Recurring** -- Check if the bulletin requires repeated compliance.
   - **Recurring Hours** -- For hour-based recurrence (e.g., every 100 hours).
   - **Recurring Months** -- For calendar-based recurrence (e.g., every 12
     months).

3. Click **Create and Add to Aircraft**.

You can also add a bulletin that already exists in the system by selecting it
from the **Add Existing Bulletin** dropdown at the top of the modal.

.. TODO: Screenshot of the Add Bulletin modal

Recording Compliance
--------------------

When you comply with a bulletin:

1. Click the **checkmark** button on the bulletin row.
2. Fill in the compliance record:

   - **Date Complied** -- The date the compliance action was performed.
   - **Hours at Compliance** -- Aircraft hours at the time.
   - **Notes** -- Details about what was done.
   - **Permanent** -- Check this if the compliance action permanently resolves
     the bulletin (e.g., replacing the affected part with a non-affected part).
   - **Logbook Entry** -- Optionally link the compliance record to a logbook
     entry (see below).

3. Click **Save**.

For recurring bulletins, the system automatically calculates the **next due**
date or hours based on the recurrence interval and the last compliance record.
Monthly and annual recurrence uses end-of-month calculation -- if a bulletin is
due every 12 months from a compliance date of January 15, the next due date is
the end of January the following year.

.. TODO: Screenshot of the Record Compliance modal

Linking a Logbook Entry to a Compliance Record
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Logbook Entry** field in the compliance modal is a search picker rather
than a plain dropdown. To associate a logbook entry:

- **Search** -- Type a date, text snippet, or mechanic name into the search
  field. Results appear below as you type; click one to select it.
- **Browse** -- Click **Browse** to open a full browser with text search and
  Log Book / Entry Type filters. Click **Select** on any result.
- **Clear** -- Click **×** on the selected entry chip to remove the link.

You can also link entries from the logbook tab using the
:ref:`logbook link picker <logbook-link-picker>`.

Viewing Compliance History
--------------------------

Click the **history** icon on any bulletin row to view the full compliance
history, showing all past compliance records with dates, hours, and notes.

.. TODO: Screenshot of the compliance history modal

Editing and Removing Bulletins
-------------------------------

- Click the **pencil** icon to edit a bulletin's details (type, mandatory flag,
  name, description, recurrence, etc.).
- Click the **X** icon to remove a bulletin from tracking. This does not delete
  the compliance history.
