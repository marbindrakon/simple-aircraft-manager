Sharing & Access
================

The Sharing & Access tab (visible only to aircraft owners) lets you manage who
can access the aircraft and create public share links for read-only viewing.

.. TODO: Screenshot of the Sharing & Access tab showing share links and user roles sections

Share Links
-----------

Share links allow anyone with the URL to view aircraft data without logging in.
This is useful for sharing status with mechanics, insurance companies, or
prospective buyers.

Creating a Share Link
^^^^^^^^^^^^^^^^^^^^^

1. Click **Create Link**.
2. Configure the link:

   - **Label** (optional) -- A name to help you remember what this link is for
     (e.g., "Annual inspection viewer" or "Insurance company").
   - **Access Level** -- Choose the level of detail visible through this link:

     - **Current Status** -- Overview, airworthiness status, active squawks,
       public notes, current AD/inspection status, oil/fuel data, and public
       documents. Does not include maintenance history.
     - **Maintenance Detail** -- Everything in Current Status plus full
       maintenance history: logbook entries, AD/inspection compliance history,
       resolved squawks, and major repairs/alterations.

   - **Expires after** (optional) -- Number of days until the link
     automatically expires. Leave blank for no expiration.

3. Click **Create Link**.

.. TODO: Screenshot of the Create Share Link modal showing access level options

Managing Share Links
^^^^^^^^^^^^^^^^^^^^

The share links table shows all active links with:

- **Label** -- The link name, or a dash if unlabeled.
- **Access Level** -- "Current Status" (green) or "Maintenance Detail" (blue).
- **Expires** -- The expiration date, or "Never".
- **URL** -- The share link URL (truncated).
- **Copy** button -- Copies the full URL to your clipboard.
- **Revoke** button (X icon) -- Permanently disables this link. Anyone using it
  will no longer have access.

You can create up to **10 share links** per aircraft. Revoking a link does not
affect other links.

What Viewers See
^^^^^^^^^^^^^^^^

People who open a share link see a read-only version of the aircraft detail
page. A blue banner at the top indicates that they are viewing a shared view.
No account is required.

The data visible depends on the access level:

.. list-table::
   :header-rows: 1
   :widths: 50 25 25

   * - Data
     - Current Status
     - Maintenance Detail
   * - Aircraft overview and airworthiness status
     - Yes
     - Yes
   * - Components and component status
     - Yes
     - Yes
   * - Active squawks
     - Yes
     - Yes
   * - Current AD/inspection status (latest record only)
     - Yes
     - Yes
   * - Oil and fuel records
     - Yes
     - Yes
   * - Public notes and public documents
     - Yes
     - Yes
   * - Full AD/inspection compliance history
     - No
     - Yes
   * - Resolved squawks
     - No
     - Yes
   * - Logbook entries
     - No
     - Yes
   * - Major repairs and alterations
     - No
     - Yes

User Roles
----------

The User Roles section lets you grant other registered users access to your
aircraft.

Adding a User
^^^^^^^^^^^^^

1. Click **Add User**.
2. In the modal, type at least 2 characters to **search** for a user by
   username or name.
3. Select the user from the dropdown results.
4. Choose a **role**:

   - **Pilot** -- Can view all data, update hours, and create squawks, notes,
     oil records, and fuel records. Cannot edit or delete other users' entries,
     manage components, logbook, ADs, inspections, or documents.
   - **Owner** -- Full access to all aircraft data and settings, including
     managing roles and sharing.

5. Click **Add Role**.

.. TODO: Screenshot of the Add User Role modal with search results

Changing a Role
^^^^^^^^^^^^^^^

Use the **role dropdown** in the table to change a user's role between Owner
and Pilot. Changes take effect immediately.

Removing a User
^^^^^^^^^^^^^^^

Click the **X** button next to a user to remove their access. The system
prevents you from:

- Removing the last owner of an aircraft (there must always be at least one
  owner).
- Removing yourself (to prevent accidental lockout).
