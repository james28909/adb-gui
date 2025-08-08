# AI Instructions for ADB GUI Project

Make sure to write any commands or any syntax at all that is compatible with the users shell. if "Users shell is: " doesnt have a shell, then use the terminal to figure out which shell, then add that to "Users shell is: "
Users shell is: ZSH (oh-my-zsh)

## Primary Rule
**DO NOT EDIT ANY FILES WITHOUT EXPLICIT PERMISSION FROM THE USER**

## Required Behavior
- **READ THIS FILE AFTER EVERY PROMPT** - Always check for updated instructions
- **UPDATE THIS FILE ONLY WHEN EXPLICITLY TOLD TO** - Don't modify unless instructed
- **ALWAYS write the patch file to the cwd with the name "current.patch". once verified that its written to the cwd, apply the patch in the current terminal.**
- Wait for explicit instruction before modifying gui.py or any other files
- **USE DIFF FORMAT FOR ALL CODE CHANGES** - Show changes in unified diff format, not full code blocks
- **PATCH FILE WORKFLOW** - Create patch file, show user the diff, then apply the patch automatically
- Only suggest code changes when specifically asked
- Focus on answering questions and providing information
- If asked to modify files, confirm permission first

## Project Context
- Working on ADB Partition Dumper GUI application
- Device: Galaxy S5 (serial: 644bcdd5)
- Current focus: Device identification and folder naming
- GUI uses PyQt5 and ADB commands

## Notes
- User wants to concatenate device name + serial for default folder names
- Galaxy S5 model name may not be in standard ro.product.model property
- Need to check multiple properties for device identification
- ADB shell is already root - no need for su -c or sudo

## Git/Patch Rules
- Leave patch files untracked (do not git add them)
- Do not commit patch files to repository
- Patch files are temporary working files only
- **ONLY TRACK THESE FILES**: gui.py, README.md, requirements.txt, ai_instructions.md

Remember: ASK BEFORE EDITING!
