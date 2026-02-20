Inspections
===========

The Inspections tab tracks periodic inspection requirements for the aircraft,
such as annual inspections, 100-hour inspections, and transponder checks.

The Inspections tab in the navigation shows a **badge count** when there are
overdue or upcoming inspections.

Inspection Types
----------------

Each inspection type defines a recurring requirement. The table shows:

- **Name** -- The inspection name (e.g., "Annual Inspection", "100-Hour").
- **Recurring** -- Whether the inspection recurs, and at what interval:

  - **Hours** -- e.g., every 100 hours.
  - **Months** -- e.g., every 12 months (annual).
  - **Days** -- e.g., every 730 days.

  An inspection can have both an hour-based and a calendar-based interval; the
  aircraft is due when *either* limit is reached first.

- **Status** -- Color-coded compliance status:

  - **Compliant** (green) -- The inspection is current.
  - **Due Soon** (orange) -- Coming due within 10 hours or 30 days.
  - **Overdue** (red) -- The inspection has lapsed. This grounds the aircraft.
  - **Not Inspected** -- No inspection record exists yet.

- **Last Completed** -- The date of the most recent inspection.
- **Next Due** -- When the next inspection is due (date or hours).

.. TODO: Screenshot of the Inspections table showing various inspection types with different statuses

Adding an Inspection Type
-------------------------

1. Click **Add Inspection Type** (owners only).
2. Fill in:

   - **Name** -- A descriptive name (e.g., "Annual Inspection").
   - **Recurring** -- Check this for inspections that repeat.
   - **Recurring Hours** -- The hour interval (e.g., 100).
   - **Recurring Months** -- The calendar interval in months (e.g., 12 for
     annual).
   - **Recurring Days** -- Alternatively, specify the interval in days.

3. Click **Save**.

Recording an Inspection
-----------------------

When an inspection is completed:

1. Click the **checkmark** button on the inspection row.
2. Fill in:

   - **Date** -- When the inspection was completed.
   - **Hours** -- Aircraft hours at the time of inspection.
   - **Notes** -- Details about the inspection.
   - **Logbook Entry** -- Optionally link the inspection record to a logbook
     entry (see below).

3. Click **Save**.

The system automatically calculates the next due date/hours based on the
inspection type's recurring interval.

.. TODO: Screenshot of the Record Inspection modal

Linking a Logbook Entry to an Inspection Record
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Logbook Entry** field is a search picker rather than a plain dropdown:

- **Search** -- Type a date, text snippet, or mechanic name. Results appear
  inline; click one to select it.
- **Browse** -- Click **Browse** to open a full browser with text search and
  Log Book / Entry Type filters. Click **Select** on any result.
- **Clear** -- Click **×** on the selected entry chip to remove the link.

You can also link entries from the logbook tab using the
:ref:`logbook link picker <logbook-link-picker>`.

Viewing Inspection History
--------------------------

Click the **history** icon on any inspection row to see all past inspection
records with dates, hours, and notes.

.. TODO: Screenshot of the inspection history modal

Editing and Removing Inspection Types
-------------------------------------

- Click the **pencil** icon to edit an inspection type's details.
- Click the **X** icon to remove an inspection type. This also removes its
  inspection history.
