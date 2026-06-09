# Installation Reference

## Codex / ChatGPT Skill Folder

This skill is stored as:

`F:\001COnsultora politica\diagonales-intelligence\.codex\skills\diagonales-intelligence`

To install into local Codex/ChatGPT-compatible skills:

```powershell
.\scripts\install-local.ps1
```

The script copies this folder to:

`C:\Users\FAMILIA\.codex\skills\diagonales-intelligence`

Restart the app after copying so the skill list refreshes.

## Claude

Claude skills generally use a folder containing `SKILL.md` and optional resources. Export the folder as a ZIP:

```powershell
.\scripts\export-skill.ps1
```

Upload or import the generated ZIP wherever Claude's skill/project tooling expects custom skills.

## Portable ZIP

The export script writes:

`dist\diagonales-intelligence-skill.zip`

This ZIP contains only the skill folder, not repo secrets or databases.
