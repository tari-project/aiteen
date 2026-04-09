# Internationalization (i18n) Management with Tolgee

This repository previously contained a custom i18n pipeline (`aiteen`), which has been deprecated and replaced by **Tolgee**, an established open-source i18n management platform. Tolgee provides a robust solution for managing translations across Tari projects (Universe, WXTM Bridge, and future applications) with integrated AI translation, a review workflow, and full CI/CD support.

## Solution Rationale: Why Tolgee?

Tolgee was selected as the replacement solution due to its comprehensive features that directly address the pain points of the previous custom pipeline:

1.  **Robust Platform:** Tolgee offers a dedicated web interface for translation management, making it easy for non-developers to contribute, review, and approve translations.
2.  **Seamless AI Integration:** It has built-in support for AI translation services (like OpenAI), allowing for automated, context-aware translation of missing keys directly within the platform.
3.  **Review Workflow:** Tolgee provides clear states for translations (untranslated, translated, reviewed), enabling a structured review and approval process before translations are finalized. Permissions can be set to control who can perform reviews.
4.  **CI/CD Integration:** With its powerful CLI tool and API, Tolgee integrates natively into GitHub Actions, automating the detection of new English strings and the synchronization of translated content.
5.  **Multi-Project Support:** Tolgee handles multiple projects (e.g., Tari Universe, WXTM Bridge) within a single instance, allowing for shared languages and streamlined management across the ecosystem.
6.  **Flexible Locale Structure:** It supports various file formats, including JSON, and can be configured to work with existing project structures (`public/locales/{lang}/`).

## New i18n Workflow with Tolgee

The new workflow focuses on automating translation management via Tolgee and GitHub Actions.

### 1. Add New English Keys

Developers add new strings directly into their English locale JSON files (e.g., `public/locales/en/common.json`). When these changes are pushed to a `main` branch (or merged via PR), a GitHub Action automatically pushes these new keys to Tolgee.

### 2. Automatic AI Translation & Review

Once new keys are pushed to Tolgee:
*   Tolgee automatically detects missing translations for other configured languages.
*   Configured AI translation (e.g., OpenAI) generates initial translations.
*   Translators or project managers log into the Tolgee UI to review, refine, and approve these AI-generated translations. The review process ensures high-quality output before deployment.

### 3. Pulling Translations into Projects

Periodically (e.g., daily schedule) or manually, a GitHub Action runs to pull all approved translations from Tolgee back into the respective project repositories. This action updates the locale JSON files for all languages.

### 4. Integration with CI (GitHub Actions)

Two primary GitHub Actions workflows are now in place:

*   **`push-english-keys.yml`**: Watches for changes in English locale files in `tari-project/universe` and `tari/wxtm-bridge` and automatically pushes new/updated keys to Tolgee.
*   **`pull-translations.yml`**: Periodically (or on demand) pulls all reviewed translations from Tolgee, updates the locale files in both `tari-project/universe` and `tari/wxtm-bridge`, and commits the changes.

## Deprecation of Legacy Scripts

The custom Python scripts (`i18n_checker.py`, `i18n_translator.py`, `i18n_patch_locales.py`, `i18n_qa.py`) previously used for Aiteen are now deprecated. All functionality related to auditing, translating, patching, and QA is now handled by the Tolgee platform and its integrated CI workflows.

## Requirements for Tolgee Integration

*   **Tolgee Instance:** A running Tolgee instance (cloud or self-hosted).
*   **Tolgee API Key:** An API key with appropriate permissions (read/write keys, languages, translations) to be set as a GitHub Secret (`TOLGEE_API_KEY`).
*   **Tolgee Project ID:** The Project ID(s) for your Tolgee project(s), to be set as GitHub Secrets (`TOLGEE_UNIVERSE_PROJECT_ID`, `TOLGEE_WXTM_BRIDGE_PROJECT_ID`).

Refer to the GitHub Actions workflows in `.github/workflows/` for detailed implementation.