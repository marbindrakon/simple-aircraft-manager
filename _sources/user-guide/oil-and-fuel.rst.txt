Oil & Fuel Tracking
===================

The Oil and Fuel tabs track consumable usage over time and display trend charts
to help identify consumption patterns.

Oil Tab
-------

The Oil tab tracks oil additions and consumption.

.. TODO: Screenshot of the Oil tab showing the consumption trend chart and records table

Adding an Oil Record
^^^^^^^^^^^^^^^^^^^^

1. Click **Add Oil Record** (owners and pilots).
2. Fill in:

   - **Date** -- When the oil was added.
   - **Flight Hours** -- Aircraft hours at the time.
   - **Quantity Added** -- Amount of oil added in quarts.
   - **Level After** -- Oil level after adding (optional).
   - **Type** -- The oil brand/type used (optional).
   - **Notes** -- Any additional details (optional).

3. Click **Save**.

Oil Consumption Chart
^^^^^^^^^^^^^^^^^^^^^

When you have two or more oil records, a **trend chart** appears showing oil
consumption over time in **hours per quart**. This helps you monitor engine
health -- increasing oil consumption can indicate wear.

The chart plots each data point against flight hours so you can spot trends
over the life of the engine. The dashed line shows the **average** consumption
rate, calculated from the most recent 20 data points.

Outlier Detection
"""""""""""""""""

Events like an oil change (where a large quantity is added after only a few
hours) can skew the average. When there are five or more data points, the
chart automatically identifies statistical outliers using the
**IQR (Interquartile Range)** method: any data point that falls outside
Q1 − 1.5 × IQR or Q3 + 1.5 × IQR is considered an outlier.

- Outlier points appear as **larger orange dots** on the chart.
- The average line is recalculated **excluding those outliers**, and the legend
  notes how many were excluded (e.g., *Average (8.2, 1 outlier excluded)*).
- In the records table, outlier records are flagged with a **⚠ warning icon**
  next to the date. Hover over the icon for an explanation.

Outlier detection requires at least five inter-record intervals and does not
fire when all consumption rates are identical.

Oil Records Table
^^^^^^^^^^^^^^^^^

Below the chart, a table lists all oil records with date, hours, quantity,
level after, type, and notes. Records whose consumption rate was identified as
an outlier are marked with a **⚠ icon** next to the date. Owners can click
the **pencil** icon to edit a record.

Fuel Tab
--------

The Fuel tab works identically to the Oil tab but tracks fuel consumption.

.. TODO: Screenshot of the Fuel tab showing the burn rate chart and records table

Adding a Fuel Record
^^^^^^^^^^^^^^^^^^^^

1. Click **Add Fuel Record** (owners and pilots).
2. Fill in:

   - **Date** -- When you refueled.
   - **Flight Hours** -- Aircraft hours at the time.
   - **Quantity Added** -- Amount of fuel added in gallons.
   - **Level After** -- Fuel level after refueling (optional).
   - **Type** -- The fuel grade (e.g., 100LL) (optional).
   - **Notes** -- Any additional details (optional).

3. Click **Save**.

Fuel Consumption Chart
^^^^^^^^^^^^^^^^^^^^^^

With two or more records, a trend chart displays fuel burn rate in **gallons
per hour**. This helps verify that fuel consumption is within expected
parameters for your engine and flight profile. The dashed line shows the
**average** burn rate, calculated from the most recent 20 data points.

Outlier detection works the same way as for oil: records whose burn rate falls
outside the IQR bounds are rendered as **larger orange dots** on the chart,
excluded from the average, and flagged with a **⚠ icon** in the records table
below. Common causes include a missed refueling entry (which inflates the
hours between two records) or an unusually large top-off after a long flight.
