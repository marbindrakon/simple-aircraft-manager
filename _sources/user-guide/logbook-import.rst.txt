Logbook Import
==============

The Logbook Import feature uses AI to transcribe scanned aircraft logbook pages
into structured digital entries. It can process images of handwritten or typed
maintenance logbook pages and extract individual entries with dates, descriptions,
hours, and signoff information.

.. TODO: Screenshot of the Logbook Import page showing the form layout

Accessing the Import Page
-------------------------

Click **Import Logbooks** in the navigation bar to access this page. This
feature is available to aircraft owners.

.. note::

   The import feature requires at least one AI provider to be configured by the
   system administrator (Anthropic API key for Claude, or an Ollama instance
   URL for self-hosted models). If no provider is configured, the import page
   will not be available.

Uploading Source Files
----------------------

You can provide logbook pages in two ways:

**Multiple image files**
   Select individual image files (JPEG, PNG, TIFF, WebP, BMP, or GIF). Files
   are processed in alphabetical order by filename, so name them so that
   alphabetical order matches page order (e.g., ``page-001.jpg``,
   ``page-002.jpg``).

**Archive file**
   Upload a single zip, tar, tar.gz, tar.bz2, or tar.xz archive containing
   image files. Images inside are also sorted alphabetically by filename.

.. TODO: Screenshot of the file upload section showing the image/archive toggle

Setting the Destination
-----------------------

- **Aircraft** -- Select which aircraft this logbook belongs to.
- **Collection name** -- Groups the uploaded images into a document collection
  (e.g., "Airframe Log #4"). This is auto-filled from the filename but can be
  edited.
- **Document name** -- The name for the document record. Defaults to the
  collection name.

Import Options
--------------

**Upload only (no transcription)**
   Check this to save the images as documents without running AI transcription.
   Useful if you just want to archive scanned pages without extracting entries.

**Document type**
   Categorize the uploaded document: Log, Alteration, Report, Invoice, Aircraft
   Record, or Other.

When transcription is enabled, additional options appear:

**AI model**
   Select which AI model to use for transcription. Available models depend on
   what providers your administrator has configured. Options may include Claude
   (cloud) or locally-hosted models via Ollama.

**Log type override**
   By default, the AI auto-detects the log type (Airframe, Engine, Propeller,
   or Other) for each entry. Use this to force all entries to a specific type.

**Batch size**
   The number of images sent per API call (1--20). Larger batches provide more
   context for the AI but use more tokens. The default is usually appropriate.

.. TODO: Screenshot of the options panel showing AI model selection and batch size

Running the Import
------------------

1. Select your files and configure the destination and options.
2. Click **Import & transcribe** (or **Upload images** if upload-only mode is
   selected).

The import runs in real time with a progress display:

- A **progress bar** showing overall completion percentage.
- A **progress log** showing detailed events as they happen:

  - Image upload confirmations (green).
  - Extracted entries (blue).
  - Warnings (yellow) -- e.g., truncated output from the AI.
  - Errors (red) -- e.g., failed API calls.

.. TODO: Screenshot of the import progress view showing the progress bar and event log

When the import completes, a summary shows:

- **Entries created** -- The number of logbook entries extracted and saved.
- **Images uploaded** -- The number of images saved as documents.
- **Warnings** and **errors** counts, if any.

Click **New import** to start another import.

Tips for Best Results
---------------------

- **Image quality matters.** Clear, high-resolution scans produce better
  results. Avoid blurry or low-contrast images.
- **Name files in order.** The AI processes pages in batches, with overlap
  between batches for context. Correct page ordering ensures entries that span
  pages are handled properly.
- **Review imported entries.** AI transcription is not perfect, especially with
  handwritten text. Check the imported entries in the :doc:`logbook` tab and
  correct any errors.
- **Use log type override** when the entire logbook is one type (e.g., an
  engine logbook). This improves accuracy by removing ambiguity.
