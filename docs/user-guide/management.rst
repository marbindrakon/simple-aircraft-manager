Management Portal
=================

Staff users (accounts with the *staff* flag) have access to a **Manage** item
in the top navigation bar. The management portal provides operational workflows
for controlling who can register and what aircraft they can access.

The themed Django admin (``/admin/``) is still available to superusers for raw
data access, but the management portal covers the day-to-day workflows.

.. note::

   The Manage nav item is only visible to staff accounts. Regular owners and
   pilots do not see it.

Invitation Codes
----------------

Invitation codes are the mechanism for creating new user accounts. Each code
contains a unique registration link; anyone who opens that link can create an
account (subject to any restrictions you configure).

Navigate to **Manage → Invitation Codes** to see all codes.

The table shows:

- **Label** -- An internal name for the code (e.g., "Club XYZ - Spring 2026").
  Click the label to open the code's detail page.
- **Email** -- If set, the registration form will be pre-filled with this
  address.
- **Uses** -- How many times the code has been redeemed vs. the maximum
  (``∞`` means unlimited).
- **Expires** -- The expiration date, or "Never".
- **Status** -- Green "Active", grey "Inactive", or red "Expired/Exhausted".
- **Actions** -- Copy the registration link, toggle active/inactive, or delete.

Creating an Invitation Code
^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Click **New Invitation Code**.
2. Fill in the fields:

   - **Label** *(required)* -- A descriptive name for your own reference.
   - **Email** *(optional)* -- Pre-fills the registration form. Effectively
     makes the code single-use for one specific person.
   - **Name** *(optional)* -- Pre-fills the name field on the registration form.
   - **Max Uses** *(optional)* -- Leave blank for unlimited uses.
   - **Expires At** *(optional)* -- Leave blank for no expiration.

3. Click **Create Code**.

The new code appears in the table with an "Active" badge.

Sharing the Link
^^^^^^^^^^^^^^^^

Click the **copy icon** (clipboard) next to a code to copy its registration URL
to your clipboard. Send this URL to the person you want to invite. When they
open it, they will see a registration form and can create their account.

Toggling a Code
^^^^^^^^^^^^^^^

Click **Deactivate** to disable a code without deleting it. Deactivated codes
can be re-activated at any time by clicking **Activate**. Links to a deactivated
code will show an "invalid code" message to anyone who opens them.

Deleting a Code
^^^^^^^^^^^^^^^

Click the **trash icon** and confirm to permanently delete a code. Existing
accounts created with the code are not affected.

Invitation Code Detail
^^^^^^^^^^^^^^^^^^^^^^

Click a code's label to open its detail page. From here you can:

- **Edit** the label, email, name, max uses, expires at, and active status,
  then click **Save Changes**.
- **Copy** the full registration link.
- Manage **Initial Aircraft Roles** — roles automatically granted when someone
  redeems the code (see below).
- View **Redemptions** — a read-only table of users who have redeemed the code
  and when.

Initial Aircraft Roles
""""""""""""""""""""""

You can pre-assign aircraft roles to a code so that anyone who registers with it
is automatically granted access to specific aircraft.

To add a role:

1. On the code detail page, select an **Aircraft** from the dropdown.
2. Choose a **Role** (Pilot or Owner).
3. Click **Add**.

The role appears in the table. Click the **X** to remove it. Changes take effect
for future redemptions only; users who already redeemed the code are not affected.

Users
-----

Navigate to **Manage → Users** to see a table of all registered users.

The table shows:

- **Username**, **Name**, **Email**
- **Staff** badge (if the account has staff privileges)
- **Active** / **Inactive** badge
- **Joined** date and **Last Login** date
- **Aircraft Access** -- A summary of the aircraft roles granted to this user
  (e.g., ``N12345 (owner), N67890 (pilot)``). Shown as "—" if the user has no
  aircraft roles.

Superusers see an **Edit in Admin** link next to each user that opens the Django
admin edit page for that account.
