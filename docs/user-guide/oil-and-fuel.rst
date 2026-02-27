Oil & Fuel Tracking
===================

The **Health** tab contains three sub-tabs: **Oil Usage**, **Fuel Usage**, and
**Oil Analysis**. Oil and Fuel track consumable usage over time and display
trend charts. Oil Analysis records and trends lab reports from companies
such as Blackstone Laboratories and Aviation Laboratories (AvLab).

Oil Usage Sub-Tab
-----------------

The Oil Usage sub-tab tracks oil additions and consumption.

.. TODO: Screenshot of the Oil Usage sub-tab showing the consumption trend chart and records table

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

Fuel Usage Sub-Tab
------------------

The Fuel Usage sub-tab works identically to the Oil Usage sub-tab but tracks fuel consumption.

.. TODO: Screenshot of the Fuel Usage sub-tab showing the burn rate chart and records table

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

Oil Analysis Sub-Tab
--------------------

The **Oil Analysis** sub-tab tracks oil analysis lab reports and trends
elemental wear-metal data over time. Each report stores the PPM values for
up to 20 elements (iron, copper, chromium, aluminum, lead, silicon, etc.)
and optional oil properties (flashpoint, viscosity, water content).

Reports can be added manually or imported from a PDF lab report.

Adding a Report Manually
^^^^^^^^^^^^^^^^^^^^^^^^

1. Click **Add Report** (owners only).
2. Fill in:

   - **Engine Component** -- The engine component the sample came from (optional but recommended for multi-engine aircraft).
   - **Sample Date** -- Date the oil sample was taken (required).
   - **Analysis Date** -- Date the lab performed the analysis (optional).
   - **Lab** -- Laboratory name (e.g., Blackstone Laboratories).
   - **Lab Number** -- Lab-assigned sample or report number.
   - **Engine Hours at Sample** -- Total engine hours when the sample was taken.
   - **Oil Hours at Sample** -- Hours on the current oil at time of sampling.
   - **Oil Type** -- Oil brand and grade (e.g., Phillips XC 20W/50).
   - **Oil Added (qt)** -- Makeup oil added during the sample interval.
   - **Lab Status** -- Overall assessment: Normal, Monitor, or Action Required.
   - **Elements (PPM)** -- Element concentrations in PPM. Enter the elements that appear on your report and leave the rest empty.
   - **Lab Comments** -- Verbatim lab technician comments.
   - **Notes** -- Your own notes about this sample.

3. Click **Add Report**.

Importing from a PDF
^^^^^^^^^^^^^^^^^^^^

PDF import reads lab reports and automatically populates all sample fields.
A single PDF may contain multiple samples (current plus historical); all are
extracted and presented for review.

1. Click **Import from PDF**.
2. Select the PDF file from your computer.
3. Click **Extract Data** and wait for the report to be processed.
4. Review the extracted samples. For each sample:

   - Check the checkbox to include it (all are checked by default).
   - Assign an **engine component** from the dropdown.
   - Verify element values and lab comments.

5. Click **Save Selected Samples**.

**Supported labs**: Blackstone Laboratories and Aviation Laboratories (AvLab).
PDF import requires a text-based PDF (the standard output from both labs);
scanned image PDFs are not supported.

Element Trend Chart
^^^^^^^^^^^^^^^^^^^

When two or more reports are present, a **trend chart** appears showing
selected element PPM values over time (by sample date). Each element is
plotted as a separate colored line.

**Element toggles**: Click the element chips above the chart to show or hide
individual elements. The six default elements shown are Iron, Copper,
Chromium, Aluminum, Lead, and Silicon — the most common wear indicators.
Additional elements (nickel, tin, molybdenum, etc.) can be toggled on.

**Outlier detection**: The same IQR method used for oil/fuel records is
applied per element. Outlier data points are rendered as **larger orange
triangles**. Each element's dashed average line excludes outliers.

**Multiple engines**: If the aircraft has more than one engine component, a
component filter dropdown appears so you can focus on a single engine's
history.

Status Labels
^^^^^^^^^^^^^

Each report can carry a lab-assigned status:

- **Normal** (green) — No concerns; oil analysis is within expected parameters.
- **Monitor** (orange) — One or more elements are elevated; recheck at shorter interval.
- **Action Required** (red) — Immediate attention needed; investigate before further flight.

Status labels appear in the reports table and are derived from lab comments
during PDF import or set manually.
