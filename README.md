# Weapons Classification Assistant

An interactive tool for classifying small arms based on the **ARES Arms & Munitions Classification System (ARCS)** and the **SAS Weapons Identification Guide**.

Select observable physical characteristics of a weapon (how it's held, bore type, loading mechanism, action) and matching weapon classifications are filtered in real time.

**Live site**: https://paigemoody.github.io/weapons_classification_resources.github.io/

---

## Prerequisites

- Node.js v24+

---

## Local setup

```bash
npm install
npm run dev
```

Then open `http://localhost:5173`.

---

## Editing content

All data lives in `src/imports/` as CSV files. These can be edited in Excel, Google Sheets, or any spreadsheet tool.

| File | Purpose |
|---|---|
| `Weapons_Classifications__Small_Arms_-_classifications.csv` | Weapon classification records (ARCS taxonomy levels, characteristics, descriptions, ARES page refs) |
| `Weapons_Classifications__Small_Arms_-_characteristic_options.csv` | Available options for each characteristic |
| `Weapons_Classifications__Small_Arms_-_characteristic_values.csv` | Guidance text for identifying each characteristic visually |
| `Weapons_Classifications__Small_Arms_-_classification_level_definitions.csv` | ARCS taxonomy level definitions (Class → Group → Type → Sub-type) |

---

## Deployment

GitHub Pages is configured to use **GitHub Actions** as its source (repo Settings → Pages). The workflow builds the app and deploys it — files are never served directly from the branch.

### Production (`gh-pages` branch)
Pushing to `gh-pages` triggers a build and deploys to the live site.

### Branch previews (any other branch)
Pushing to a feature branch builds the app and publishes it to a subfolder on the `gh-pages` branch:

```
https://paigemoody.github.io/weapons_classification_resources.github.io/branch-preview/<branch-name>/
```

When a PR is closed or a branch is deleted, the preview folder is automatically removed via a cleanup workflow.

### The `gh-pages` branch
`gh-pages` serves two roles: it holds the React source code (your main branch) and also stores the `branch-preview/` subfolders for feature branch previews.

---

## File reference

| File/Directory | Purpose |
|---|---|
| `src/app/App.tsx` | Main app component and filtering logic |
| `src/app/data/weaponData.ts` | CSV parsing (PapaParse) and typed data layer |
| `src/app/components/` | UI components (CharacteristicCard, OptionPanel, ResultsPanel, etc.) |
| `src/imports/` | Source data (CSV files) |
| `src/styles/` | Tailwind / theme styles |
| `CLAUDE.md` | Claude Code guidelines |


### Attributions

Includes components from [shadcn/ui](https://ui.shadcn.com/) used under [MIT license](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md).

Includes photos from [Unsplash](https://unsplash.com) used under [license](https://unsplash.com/license).
