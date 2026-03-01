Flight Log
==========

The **Flights** tab (visible only to authenticated users — not on share links) lets you log
individual flights and automatically maintain aircraft hour totals.

Accessing the Flight Log
------------------------

Open an aircraft's detail page and click the **Flights** tab in the navigation bar.

Logging a Flight
----------------

Click **Log a Flight** to open the flight log form.

Tach Time Fields
~~~~~~~~~~~~~~~~

* **Tach Out / Tach In** — Optional meter readings at departure and arrival. When both
  are filled in, the **Tach Time** field is auto-populated with the difference.
* **Tach Time** (required) — Duration of the flight in tach hours. You can enter this
  directly or let it be computed from Tach Out / Tach In.

After the flight is saved, the aircraft's cumulative tach time is increased by the
logged tach time, and all IN-USE components have their ``hours_in_service`` and
``hours_since_overhaul`` incremented accordingly.

Hobbs Time Fields
~~~~~~~~~~~~~~~~~

Hobbs tracking is optional. If your aircraft has a Hobbs meter:

* **Hobbs Out / Hobbs In** — Block-time meter readings. Auto-populate Hobbs Time when
  both are filled.
* **Hobbs Time** — Duration in Hobbs hours.

Tach vs Hobbs
~~~~~~~~~~~~~

* **Tach time** is the primary hours counter and drives component hour tracking and
  airworthiness calculations.
* **Hobbs time** is tracked separately (cumulative total visible in the overview) but
  does not affect component hours or airworthiness status.

Tach Reading vs Cumulative Total
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a tachometer has ever been replaced, the offset fields (``Tach Time Offset`` /
``Hobbs Time Offset``) record the accumulated hours before the new meter was installed.
The **Update Hours** modal and the Tach Out field both work in *meter reading* units
— the app converts to the underlying cumulative total automatically.

Offsets can only be set via the Django admin panel in the current version.

Route Fields
~~~~~~~~~~~~

* **Departure / Destination** — Up to 10 characters each (e.g. ICAO/FAA identifiers).
* **Route** — Free-text route description.

Consumables Added
~~~~~~~~~~~~~~~~~

If oil or fuel was added during or after the flight:

* Enter the quantity and optionally the type.
* On save, the app automatically creates corresponding **Oil** or **Fuel** records
  (visible on the Consumables tab) dated to the flight date.

.. note::
   If a flight log is later deleted, the auto-created oil/fuel records are **not**
   automatically removed. Delete them manually from the Consumables tab if needed.

Track Log
~~~~~~~~~

A KML track file can optionally be attached on creation. The file is stored securely
but is not rendered in-app in the current version.

Editing a Flight Log
--------------------

Owners can click the edit icon on any row. Editing adjusts the aircraft's tach/hobbs
cumulative total by the difference between the old and new values.

.. note::
   Component hour history is **not** retroactively adjusted when a flight log is edited.
   Use the **Update Hours** modal for corrections if needed.

Deleting a Flight Log
---------------------

Owners can click the trash icon and confirm deletion. The aircraft's tach/hobbs totals
are decremented by the deleted flight's values. Auto-created consumable records are not
removed automatically.

Pilot Access
------------

Pilots can log flights but cannot edit or delete existing flight logs — those actions
are restricted to owners and admins.

The Flights tab is never shown on public share links regardless of privilege level.
