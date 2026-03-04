# How to Edit the Weapons Classification Taxonomy

Based on **ARES** and **SAS** reference materials.

## Overview

The taxonomy is now stored as **structured JSON** (`taxonomy.json`) instead of Mermaid syntax. This makes it much easier to:

- Add and edit classifications without worrying about diagram syntax
- Include images and attributes for each classification
- Have the Mermaid flowchart auto-generated for you
- Validate your changes automatically

## File Organization

All images must be PNG and organized by source:

```
sources/
├── source_name/
│   └── visuals/
│       ├── example.png
│       ├── example2.png
│       └── example3.png
└── other_source_name/
    └── visuals/
        └── other_image.png
```

## Step 1: Prepare Your Images

Before editing the taxonomy, add all images in the correct source folder:

```
sources/<source_name>/visuals/<your_image>.png
```

Where `<source_name>` is either:
- `small_arms_survey` (SAS Weapons Identification Guide)
- `ARES_arms_munitions_classification_system` (ARES database)

**Example:**

```
sources/sas_guide/visuals/example_name.png
```

## Step 2: Gather Classification Information

Before editing `taxonomy.json`, prepare all the information for your classification:

### Identifiers

- **Classification ID** (lowercase, underscores, unique):  
  Example: `handgun_semi_automatic_pistol`
- **Display Name**:  
  Example: "Semi-Automatic Pistol"

### ARES/SAS Hierarchy (Levels 1–4)

All classifications must fit into this four-level hierarchy:

- **Level 1**: Category (e.g., "Firearms")
- **Level 2**: Type (e.g., "Handguns")
- **Level 3**: Subtype (e.g., "Pistols")
- **Level 4**: Variant (e.g., "Semi-Automatic")

**Example:**

```
Level 1: Firearms
Level 2: Handguns
Level 3: Pistols
Level 4: Semi-Automatic
```

### Attributes

Key-value pairs describing the weapon. Use full terms (not abbreviations):

```json
{
  "action_type": "Semi-Automatic",
  "firing_mechanism": "Recoil-Operated",
  "magazine_fed": true,
  "barrel_type": "Rifled",
  "intended_use": "Self-Defense"
}
```

Common attributes:

- `action_type`: "Semi-Automatic", "Bolt-Action", "Pump-Action", etc.
- `firing_mechanism`: "Recoil-Operated", "Manual Bolt Cycling", etc.
- `magazine_fed`: `true` or `false`
- `barrel_type`: "Rifled" or "Smooth"
- `intended_use`: "Self-Defense", "Hunting", "Military", etc.

### Description

A concise 1–2 sentence explanation:

Example: "A semi-automatic pistol fires one round per trigger pull and automatically cycles the action."

### Images

For each PNG image, provide:

- **source_name**: "sas_guide" or "ares_database"
- **filename**: "m1911.png" (must match the file in `sources/<source>/visuals/`)
- **caption**: "M1911 Semi-Automatic Pistol Example"
- **alt_text**: "Side view of M1911 pistol" (for accessibility)

## Step 3: Edit `taxonomy.json` on GitHub

### Option A: Direct GitHub Editing

1. Open `taxonomy.json` in GitHub
2. Click the **pencil icon** to edit
3. Find the `"classifications"` array
4. Add your new classification object (copy the template below)
5. Fill in all required fields
6. **Commit changes** to your branch

### Option B: Local Editing (Faster)

1. Clone the repo locally
2. Edit `taxonomy.json` in your editor
3. Run validation: `python3 src/taxonomy_validator.py validate taxonomy.json`
4. Push to your branch on GitHub

## Template

Copy this template and fill in your values:

```json
{
  "id": "shotgun_pump_action",
  "name": "Pump-Action Shotgun",
  "arcs_levels": {
    "level_1": "Firearms",
    "level_2": "Long Arms",
    "level_3": "Shotguns",
    "level_4": "Pump-Action"
  },
  "attributes": {
    "action_type": "Pump-Action",
    "firing_mechanism": "Manual Pump Cycling",
    "magazine_fed": true,
    "barrel_type": "Smooth",
    "intended_use": "Hunting"
  },
  "description": "A pump-action shotgun requires manual operation of the pump to chamber and eject rounds.",
  "images": [
    {
      "source_name": "sas_guide",
      "filename": "remington_870.png",
      "caption": "Remington 870 Pump-Action Shotgun",
      "alt_text": "Side view of Remington 870 shotgun"
    }
  ]
}
```

## Step 4: Validation & Auto-Generation

After you commit:

1. **GitHub Actions automatically validates** your `taxonomy.json`
   - Checks for duplicate IDs
   - Verifies all image files exist
   - Ensures required fields are present

2. **If validation passes:**
   - Mermaid flowchart is auto-generated from your JSON
   - HTML guides are regenerated from the Mermaid
   - All files are committed back to your branch

3. **If validation fails:**
   - Check the **Actions** tab on GitHub for error messages
   - Fix the issues and push again

## Step 5: Preview Your Changes

Once GitHub Actions finishes, preview your branch:

- **Click-through guide:**  
  `https://paigemoody.github.io/weapons_classification_resources.github.io/branch-preview/<your-branch-name>/classification-guide.html`

- **Hypothesis-filtering guide:**  
  `https://paigemoody.github.io/weapons_classification_resources.github.io/branch-preview/<your-branch-name>/classification-guide-hypothesis-filtering.html`

## Step 6: Create a Pull Request & Merge

When everything looks good:

1. Create a **Pull Request** (PR) on GitHub
2. Add a description of your changes
3. **Merge** to `gh-pages` to publish to the main site

## Tips & Best Practices

### Naming Conventions

- **Classification IDs:** lowercase, underscores  
  ✅ `handgun_semi_automatic_pistol`  
  ❌ `HandgunSemiAutomaticPistol` or `handgun-semi-auto`

- **Image filenames:** descriptive, no spaces  
  ✅ `remington_870.png`  
  ❌ `image1.png` or `Remington 870.png`

- **All terminology:** full terms, no abbreviations  
  ✅ "Semi-Automatic"  
  ❌ "Semi-Auto"

### Image Guidelines

- **Format:** PNG only
- **Location:** `sources/<source_name>/visuals/<filename>.png`
- **Captions:** Describe what the image shows (helps users understand the example)
- **Alt text:** Screen-reader friendly description

### Attributes

- Use **standardized terminology** from ARES/SAS
- Keep attribute names consistent across classifications
- Use booleans (`true`/`false`) for yes/no questions
- Use strings for descriptive fields

### Hierarchy

- Choose appropriate ARES/SAS levels for your classification
- Level 4 is usually the most specific (variant/sub-type)
- Don't skip levels in the hierarchy

## Troubleshooting

### "Image not found" error

Check:
- Image is in the correct folder: `sources/<source_name>/visuals/`
- Filename matches exactly (case-sensitive on Linux)
- File extension is `.png`
- You've uploaded the image to GitHub

### Duplicate ID error

- IDs must be unique
- Use a more specific name: `handgun_semi_automatic_pistol_compact` instead of `handgun_semi_automatic_pistol`

### GitHub Actions workflow failed

1. Go to the **Actions** tab on GitHub
2. Click the failed workflow
3. Read the error message
4. Make corrections and push again

### Local validation script fails

Run this to see detailed errors:

```bash
python3 src/taxonomy_validator.py validate taxonomy.json
```

## Questions?

Refer to the **main README** for:
- GitHub branch workflow
- Preview URLs
- Pull request process