Getting Started
===============

Logging In
----------

Simple Aircraft Manager supports two authentication methods:

- **Single sign-on (SSO)** via an OIDC provider such as Keycloak. If SSO is
  enabled for your instance, you will see a "Sign in with Keycloak" button on
  the login page. Click it to authenticate through your organization's identity
  provider. Your account is created automatically on first login.

- **Local accounts** with a username and password. Local accounts always work,
  even when SSO is enabled. An administrator must create your local account
  for you.

.. TODO: Screenshot of the login page showing both SSO and local login options

After logging in, you are taken to the :doc:`Aircraft Fleet page <dashboard>`.

Creating Your First Aircraft
-----------------------------

1. From the Aircraft page, click the **New Aircraft** button in the top right.
2. Fill in the required fields:

   - **Tail Number** -- The aircraft registration (e.g., N12345).
   - **Make** -- The aircraft manufacturer (e.g., Cessna).
   - **Model** -- The aircraft model (e.g., 172S).

3. Optionally upload a **photo** of the aircraft. This will be displayed on the
   aircraft card and the aircraft detail page.
4. Click **Save**.

You are automatically assigned as the **Owner** of any aircraft you create.

.. TODO: Screenshot of the new aircraft modal with fields filled in

User Roles
----------

Each aircraft has its own set of user roles. Your role determines what you can
do:

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - Action
     - Admin
     - Owner
     - Pilot
   * - View all aircraft data
     - Yes
     - Yes
     - Yes
   * - Update hours, create squawks/notes/oil/fuel records
     - Yes
     - Yes
     - Yes
   * - Edit or delete squawks and notes
     - Yes
     - Yes
     - No
   * - Manage components, logbook, ADs, inspections, documents
     - Yes
     - Yes
     - No
   * - Edit or delete the aircraft, manage roles and sharing
     - Yes
     - Yes
     - No

**Admin** users are Django staff/superuser accounts and can manage all aircraft
regardless of role assignments.

Aircraft owners can invite other users and assign them roles from the
:doc:`sharing-and-access` tab.
