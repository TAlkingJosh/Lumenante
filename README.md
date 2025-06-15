# Lumenante by SpectraForge

*Discord Server for help, models, and more:* https://discord.gg/cvcPm6gnth

**Lumenante** is a powerful lighting control application designed to emulate the workflow of professional lighting consoles. It provides a comprehensive toolset for designing, programming, and operating light shows, with a primary focus on live integration with the **Roblox** platform.

Created by **Talking_Josh** under the **SpectraForge** brand.

---

## Features

-   **Customizable Layouts:** Build your own personalized control surface using a drag-and-drop grid system. Add sliders, buttons, color pickers, 3D views, and more.
-   **Fixture Patch & Profiles:** Define the "personality" of any light with a flexible JSON-based profile system. Patch multi-instance fixtures (e.g., LED bars) with unique Fixture IDs (FID) and Sub-Fixture Indexes (SFI).
-   **Groups, Presets & Loop Palettes:**
    -   Organize fixtures into logical groups for quick selection.
    -   Store snapshots of fixture parameters (color, position, etc.) into versatile presets.
    -   Create dynamic, generative effects like sine waves and circles with Loop Palettes.
-   **Command Line Interface (CLI):** A powerful, industry-standard text interface for fast programming and show management (e.g., `fixture 1 thru 8 at 100`, `store preset 1.1 "My Look"`).
-   **Multi-Track Timeline:** A visual, multi-track timeline for sequencing cues and events with absolute, relative, and follow-timing.
-   **Live 3D Visualization:** See a live, real-time 3D preview of your stage, fixtures, and their output.
-   **Real-time Roblox Integration:** A built-in local HTTP server sends fixture data directly to a running Roblox game for live control. You can also import fixture positions from Roblox back into the console.
-   **Gamepad Support:** Control fixture parameters like Pan, Tilt, and Intensity using a connected USB gamepad for a tactile programming experience.
-   **Plugin System:** Extend the application's core functionality by creating or installing custom plugins.

---

## Setup Guide

Follow these steps to get Lumenante and your Roblox game connected.

### 1. Application Setup

1.  Download the latest release. You will have a folder named `lumenante`.
2.  Inside this folder is the main application, `lumenante.exe`.
3.  **Important:** The `lumenante.exe` file must remain in the same folder as the `_internal` directory for it to function correctly. Do not move the `.exe` file by itself.
4.  To add custom themes or plugins, you will place them inside the respective folders within the `_internal` directory.

The final structure should look like this:
```
lumenante/
├── lumenante.exe
└── _internal/
    ├── plugins/
    ├── themes/
    └── (and other files)
```

### 2. Roblox Setup

1.  Open your place in **Roblox Studio**.
2.  Drag and drop the `Lumenante.rbxm` file directly into the main 3D viewport of Roblox Studio.
3.  In the **Explorer** window, you will see a folder titled `Lumenant`, take the two models named `Ungroup in Workspace` & `Ungroup in ServerScriptService`
4.  Take the files and place them in their respective places.
5.  Enable HTTP Requests for your game:
    -   Go to **Home -> Game Settings -> Security**.
    -   Turn on the **"Allow HTTP Requests"** toggle.
    -   Click **Save**.

### 3. Running the System

1.  **You must start the app first** run `lumenante.exe`
2.  **Start you roblox studio instance** you can either `Run` or `Test` in the top left, I use `Test` for easier use.
3.  In the Lumenante application, look at the status bar at the bottom. It should change from "ROBLOX: Disconnected" to "ROBLOX: Listening on...".

You are now connected! Any changes you make to fixtures in Lumenante will be sent to the Roblox game in real-time.

***This app only works in studio for now***, until I buy/own a server, roblox won't be able to connect to the app.

---

## Basic Workflow Walkthrough

Here’s a quick guide to creating a simple look.

1.  **Patch a Fixture:**
    -   Go to the **"Patch & Fixtures"** tab.
    -   Click **"Add New"**. The form on the right will activate.
    -   Give it a **Name** (e.g., "Front Spot"), a **FID** (e.g., 1), and click **"Create New Fixture(s)"**.

2.  **Control the Fixture:**
    -   Go to the **"Layouts"** tab.
    -   In the header's command line, type `fixture 1 at 100` and press **Enter**. This selects fixture 1 and sets its brightness to 100%.
    -   You should see the fixture light up in the **"Stage 3D"** tab and in your Roblox game.

3.  **Store a Preset:**
    -   With the fixture still selected and at 100%, type `store preset 1 "Full On"` in the command line and press **Enter**.
    -   Go to the **"Presets"** tab to see your newly created preset.

4.  **Create a Cue:**
    -   Go to the **"Cues / Timeline"** tab.
    -   Click **"Add Cue (at Playhead)"**. Enter `1` for the cue number and click OK.
    -   Right-click on the timeline near the start and select "Add New Event...".
    -   In the dialog:
        -   Set **Event Type** to "preset".
        -   In the **Preset** dropdown, select your "P 1: Full On" preset.
        -   Click OK.
    -   You have now programmed Cue 1 to fire your preset! Use the playback controls to test it.

---

## Command Line Basics

The command line is the fastest way to program. Here are some essential commands:

| Command                               | Description                                     |
| ------------------------------------- | ----------------------------------------------- |
| `fixture 1` or `f 1`                  | Selects fixture with FID 1.                     |
| `f 1 thru 8`                          | Selects fixtures 1 through 8.                   |
| `f 1 + 3`                             | Selects fixtures 1 and 3.                       |
| `group 1` or `g 1`                    | Selects all fixtures in group 1.                |
| `f 1 at 50`                           | Sets selected fixture's brightness to 50%.      |
| `f 1 at color red`                    | Sets selected fixture's color to red.           |
| `clearselection` or `cs`              | Clears the current fixture selection.           |
| `store preset 1.1 "My Blue Look"`     | Stores the current selection into preset 1.1.   |
| `go cue 5`                            | Jumps the timeline playhead to cue 5.           |
| `label preset 1.1 "New Name"`         | Renames preset 1.1.                             |

---

## Development

To run this project from source, you will need Python 3.10+ and the libraries listed in `requirements.txt`.

```bash
# Clone the repository
git clone https://github.com/TAlkingJosh/lumenante.git
cd lumenante

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python lumenante_main.py
```

---

## License

This project is licensed under the MIT License - see the LICENSE.md file for details.

## Credits

**Lumenante** is developed by **Talking_Josh** of **SpectraForge**.
