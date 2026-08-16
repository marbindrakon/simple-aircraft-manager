Logbook Import
==============

The Logbook Import feature uploads scanned aircraft logbook pages as documents
and, when an AI provider is configured, can also transcribe them into structured
digital entries with dates, descriptions, hours, and signoff information.

.. TODO: Screenshot of the Logbook Import page showing the form layout

Accessing the Import Page
-------------------------

Click **Import Logbooks** in the navigation bar to access this page. This
feature is available to aircraft owners.

.. note::

   AI transcription requires at least one AI provider to be configured by the
   system administrator (Anthropic API key for Claude, or an Ollama instance
   URL for self-hosted models). If no provider is configured, the page operates
   in upload-only mode: images are saved as documents but no logbook entries are
   extracted.

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
   If no AI provider is configured, this mode is used automatically and the
   option is not shown.

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

.. _local-ai-desktop:

Local & Custom AI Providers (Desktop App)
-----------------------------------------

The desktop build can run logbook transcription against a **local Ollama
model** or **any OpenAI-compatible endpoint** (vLLM, LiteLLM proxy,
OpenRouter, etc.) in addition to or instead of the Anthropic API. You can
configure any combination of the three; if more than one is configured,
you pick which becomes the default in the import-page model selector.

On Apple Silicon Macs, Ollama uses the GPU via Metal -- but the same setup
works on Windows and Linux desktop builds (Ollama uses CUDA or ROCm where
available, otherwise CPU).

This is a power-user feature: you choose and size models yourself, and
quality varies between providers and models.

Local Ollama
~~~~~~~~~~~~

1. Install Ollama from https://ollama.com (or ``brew install ollama`` on
   macOS) and start it -- the menu-bar app, or ``ollama serve`` in a
   terminal.

2. Pull a **vision-capable** model. Text-only models will not work here:

   .. code-block:: console

      $ ollama pull llama3.2-vision
      # or, for a smaller / faster option:
      $ ollama pull qwen2.5vl:7b

3. **First-run setup screen** (when you launch the desktop app for the
   first time): in the *AI features* section, fill in **Ollama model**
   with the tag you pulled (e.g. ``llama3.2-vision``). Leave the
   **Ollama base URL** on its default unless you run Ollama on a
   non-default port. The Anthropic API key field can be blank if you
   only want local AI.

4. Restart the app. The Ollama model will appear in the **AI model**
   dropdown on the import page.

**Choosing a model**

- ``llama3.2-vision`` (11B parameters) is a reasonable starting point on
  Apple Silicon Macs or recent NVIDIA GPUs with 16 GB+ of system or VRAM.
- ``qwen2.5vl:7b`` is faster and uses less memory but with somewhat
  lower extraction quality on dense logbook pages.
- A 7B-class model needs roughly 6 GB of free RAM; 11B-class models want
  12 GB+.

OpenAI-compatible endpoint (vLLM, OpenRouter, LiteLLM)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For routing through a hosted aggregator (OpenRouter), a self-hosted
inference server (vLLM, LiteLLM proxy), or any other server that speaks
the OpenAI Chat Completions API, fill in the **OpenAI-compatible
endpoint** subsection of the setup form:

- **Model ID** -- whatever string the endpoint expects, e.g.
  ``gpt-4o-mini``, ``anthropic/claude-sonnet-4-6`` (OpenRouter-style),
  or your vLLM-served model name.
- **Endpoint base URL** -- the OpenAI-compatible base, e.g.
  ``https://openrouter.ai/api/v1``, ``http://localhost:8000/v1`` (vLLM),
  or your LiteLLM proxy URL.
- **API key** -- stored in your OS credential store (Keychain on macOS,
  Credential Manager on Windows, Secret Service on Linux). Leave blank
  for endpoints with no authentication, such as a local vLLM server on
  your own machine.

The model needs to be vision-capable for logbook transcription to work.
Text-only models will fail at the first batch.

Choosing a default
~~~~~~~~~~~~~~~~~~

When more than one provider is configured, the **Default model** radio
group at the bottom of the AI section decides which provider's model is
preselected on the logbook import page. You can still pick any of the
configured models per import; the radio just sets the initial value.

To flip the default later, edit the desktop config file (path varies by
OS, see below) and change the ``default_provider`` line in the ``[ai]``
section to one of ``anthropic``, ``ollama``, or ``litellm``. Then restart
the app.

Editing config.ini after first-run setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Already past first-run setup? You can edit the desktop config file
directly. Its location depends on your OS:

- **macOS**: ``~/Library/Application Support/SimpleAircraftManager/config.ini``
- **Windows**: ``%LOCALAPPDATA%\SimpleAircraftManager\config.ini``
- **Linux**: ``~/.local/share/SimpleAircraftManager/config.ini``

Add an ``[ai]`` section like this:

.. code-block:: ini

   [ai]
   default_provider = ollama
   ollama_model = llama3.2-vision
   ollama_base_url = http://localhost:11434
   litellm_model = gpt-4o-mini
   litellm_base_url = https://openrouter.ai/api/v1

API keys are *not* stored in this file -- they live in the OS credential
store. To set or change them outside the first-run flow, use the Keychain
Access app (macOS), Credential Manager (Windows), or ``secret-tool``
(Linux), under service ``SimpleAircraftManager`` with usernames
``anthropic_api_key`` or ``litellm_api_key``.

Restart the app for changes to ``config.ini`` to take effect.

Tradeoffs
~~~~~~~~~

- Local models are slower per page than the Anthropic API on most
  hardware, and JSON-schema compliance is weaker -- expect occasional
  truncation or malformed entries that you have to clean up by hand.
- OpenAI-compatible endpoints vary widely. Hosted aggregators
  (OpenRouter, etc.) typically work well. Self-hosted vLLM with a
  capable vision model is fast but requires GPU resources.
- Image quality matters even more than with the Anthropic API. Crisp
  scans make a noticeable difference.
- With Ollama or a self-hosted endpoint, all processing stays on your
  machine; nothing leaves it.
