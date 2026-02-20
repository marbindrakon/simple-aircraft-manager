Repairs & Alterations
=====================

The Repairs & Alterations tab tracks major repairs and major alterations
performed on the aircraft, corresponding to Form 337 or equivalent records.

Filtering
---------

Use the toggle buttons at the top to filter between:

- **All** -- Show both repairs and alterations.
- **Repairs** -- Show only major repairs.
- **Alterations** -- Show only major alterations.

.. TODO: Screenshot of the Repairs & Alterations tab showing both sections with the filter toggle

Major Repairs
-------------

The repairs table shows:

- **Title** -- A description of the repair, with a truncated preview of the
  full description.
- **Date** -- When the repair was performed.
- **Component** -- The affected component, if linked.
- **Performed By** -- The person or shop that performed the repair.
- **Related** -- Links to associated records:

  - **Logbook** -- Click to view the related logbook entry.
  - **Form 337** -- Click to view the attached Form 337 document.

Major Alterations
-----------------

The alterations table includes the same fields as repairs, plus:

- **STC #** -- The Supplemental Type Certificate number, if applicable.
- **STC Holder** -- The STC holder's name.
- **Related** -- May also include a link to the STC document.

Adding a Record
---------------

1. Click **Add Repair** or **Add Alteration** (owners only).
2. Fill in:

   - **Record Type** -- Repair or Alteration.
   - **Title** -- A brief title.
   - **Description** -- Detailed description of the work.
   - **Date Performed** -- When the work was done.
   - **Component** -- Optionally link to a specific component.
   - **Performed By** -- The person or shop.
   - **Logbook Entry** -- Optionally link to a logbook entry (see below).
   - **Form 337 Document** -- Optionally link to a Form 337 document.

   For alterations, additional fields are available:

   - **STC Number** -- The STC number.
   - **STC Holder** -- The STC holder.
   - **STC Document** -- Optionally link to the STC document.

3. Click **Save**.

Linking a Logbook Entry
~~~~~~~~~~~~~~~~~~~~~~~~

The **Logbook Entry** field is a search picker rather than a plain dropdown,
making it practical even when the aircraft has hundreds of logbook entries:

- **Search** -- Type a date, text snippet, or mechanic name. Results appear
  inline; click one to select it.
- **Browse** -- Click **Browse** to open a full browser with text search and
  Log Book / Entry Type filters. Click **Select** on any result.
- **Clear** -- Click **×** on the selected entry chip to remove the link.

You can also link entries from the logbook tab using the
:ref:`logbook link picker <logbook-link-picker>`.

.. TODO: Screenshot of the Add Repair modal with fields filled in

Editing and Deleting
--------------------

- Click the **pencil** icon to edit a record.
- Click the **trash** icon to delete a record. This cannot be undone.
