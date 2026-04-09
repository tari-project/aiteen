# Replace Aiteen with a Robust i18n Pipeline
> Last updated: 2026-04-09
## Overview
This feature introduces a new i18n management solution to replace the custom Aiteen pipeline, which was limited by hardcoded paths and a manual workflow. The new solution integrates with CI, supports all Tari projects, and enhances the translation process with AI capabilities.
## How It Works
The new pipeline is designed to automatically detect missing translations by comparing locale files against the English source. It utilizes AI for context-aware translations and includes a review step before merging translations. Key components include `i18n_checker.py`, which now handles dynamic translation functions, and CI integration through `run_pipeline_if_pr()` and `check_pr_and_run_pipeline()`.
## Configuration
No configuration required.
## Usage
To use the new pipeline, modify English locale files and create a pull request. The pipeline will automatically trigger and process the translations.
## References
- Closes issue #1