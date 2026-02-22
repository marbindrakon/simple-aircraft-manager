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

ICA Indicator
-------------

Records that include **Instructions for Continued Airworthiness (ICAs)** are
flagged with a gold **ICA** badge next to the title in both the repairs and
alterations tables. This makes it easy for a mechanic to quickly identify
which repairs or alterations have associated ICA requirements.

Major Repairs
-------------

The repairs table shows:

- **Title** -- A brief title. A gold **ICA** badge appears here if the record
  includes ICAs.
- **Date** -- When the repair was performed.
- **Component** -- The affected component, if linked.
- **Actions** -- Edit and delete buttons (owners only), plus a **paperclip
  icon** that appears when the record has linked files. Click the paperclip to
  open a popup with links to the associated logbook entry and/or Form 337
  document. Click the icon again (or anywhere outside the popup) to dismiss it.

Click the **chevron** (▸) at the left of any row to expand it and reveal
additional detail:

- **Performed By** -- The mechanic, shop, or IA who performed the work.
- **Aircraft Hours** -- The aircraft's total time at the time of the repair.
- **ICAs / ICA Notes** -- Whether the record includes Instructions for
  Continued Airworthiness, and any notes about where they can be found.
- **Description** -- The full work description.
- **Notes** -- Any additional notes.

Major Alterations
-----------------

The alterations table includes the same columns as repairs, plus:

- **STC #** -- The Supplemental Type Certificate number, if applicable.
- **STC Holder** -- The STC holder's name.

Expanding an alteration row reveals the same detail fields as repairs.
The paperclip popup for alterations may also include a link to the STC
document when one is attached.

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

   To flag ICAs:

   - **Instructions for Continued Airworthiness (ICAs)** -- Check this box if
     the repair or alteration includes ICAs. The record will display a gold
     **ICA** badge in the table.
   - **ICA Notes** -- (Appears when the ICA checkbox is checked.) Describe
     where the ICAs are located and what they cover, e.g. the document they
     appear in or the maintenance tasks they define.

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
