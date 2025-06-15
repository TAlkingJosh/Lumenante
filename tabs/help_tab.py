# tabs/help_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel, QTabWidget
from PyQt6.QtCore import Qt

class HelpTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def _create_help_section(self, markdown_content: str) -> QTextEdit:
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(markdown_content)
        return text_edit

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel("Help & About")
        title_label.setObjectName("HelpTitleLabel") 
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px; padding-left: 5px;") 
        main_layout.addWidget(title_label)

        self.help_tab_widget = QTabWidget()
        self.help_tab_widget.setObjectName("HelpSubTabWidget") 

        # --- General / Overview ---
        overview_text = """
## Lumenante Console - Overview

Welcome to the Lumenante Console application! This software aims to provide a conceptual emulation of certain GrandMA3 lighting console functionalities, with a focus on creating and controlling light shows for integration with ROBLOX environments.

### Core Concepts

This application is built around a workflow similar to professional lighting desks:

1.  **Define:** In the **Fixtures Tab**, you create **Fixture Profiles** which define the capabilities of your lights (e.g., a "Moving Head Spot" has pan, tilt, color, and gobos).
2.  **Patch:** Still in the **Fixtures Tab**, you "patch" instances of these profiles into your show, giving them a unique Fixture ID (FID) and position in the 3D world.
3.  **Organize:** In the **Groups Tab**, you organize your patched fixtures into logical groups (e.g., "Front Truss Wash", "Floor Spots") for fast selection.
4.  **Program:** In the **Layouts Tab**, you create a custom control surface. You can use the **Command Line** or UI controls to select fixtures/groups and change their parameters (color, position, brightness, etc.). You then store these looks into **Presets** (in the Presets Tab) or **Loop Palettes** (in the Loops Tab).
5.  **Sequence:** In the **Timeline Tab**, you build your show by creating **Cues**. Inside these cues, you place **Events** that trigger the Presets and Palettes you programmed, creating the final, automated show.
6.  **Visualize & Sync:** You can see a live representation of your work in the **Stage 3D** tab. The **Video Sync** tab helps you align your cues to a video file, and the **Roblox Integration** (in the Setup Tab) allows for live control and position import from a running game.

### Key Features

- **Fixture Profiles:** A flexible, data-driven system for defining fixture capabilities (personalities).
- **Multi-Instance Patching:** Add and configure complex fixtures with multiple controllable parts (e.g., an LED bar with 8 cells) using the `Fixture ID.Sub-Fixture Index` (e.g., `101.1`, `101.2`) system.
- **Fixture Groups:** Organize fixtures into groups for easier selection and control.
- **Presets:** Store and recall snapshots of fixture states. Presets use a "tracking" system on the timeline, meaning values persist until changed.
- **Loop Palettes:** Create dynamic, generative effects like sine waves and circles for various parameters.
- **Customizable Layouts:** Build your own control surface by arranging widgets on a grid.
- **Timeline & Cues:** A multi-track timeline for sequencing events with absolute, relative, and follow-timing.
- **Command Line Interface (CLI):** A powerful text-based interface for fast selection, attribute control, and show management (e.g., `fixture 1.1 thru 1.8 at 100`, `store preset 1.1 "My Look"`, `go cue 5`).
- **Plugin System:** Extend the application's functionality with custom-made plugins.

Navigate through the sub-tabs above for more detailed help on each section.

---
*Version: 1.0.Alpha*
        """
        self.help_tab_widget.addTab(self._create_help_section(overview_text), "Overview")

        # --- Layouts Tab Help ---
        layouts_tab_help_text = """
### Layouts Tab (Main Tab)

The Layouts tab is your primary control surface where you can build a custom user interface for your show. The entire layout is saved with your show file.

#### Layout Editing

- **Lock/Unlock:** Use the **"Lock Layout"** button in the header to toggle editing mode.
    - **Unlocked:** You can create new areas by clicking and dragging on the grid. You can also select existing areas to modify their assignment.
    - **Locked:** The layout is in "user" mode. All widgets are interactive, and you cannot create or select areas for editing.
- **Panning & Zooming:**
    - **Pan:** **Right-click and drag** on the canvas background to pan your view.
    - **Zoom:** **Ctrl + Mouse Wheel** to zoom in and out of the canvas.
- **Area Assignment:** When an area is selected (by clicking on it in unlock mode), the right-hand **Assignment Panel** becomes active. Here you can assign a function to the area and configure its options. Click **"Apply Assignment"** to save the changes to that area.
- **Context Menu:** **Right-click** on an area (in unlock mode) to quickly edit or delete it.
- **Multi-Area Selection:** Hold **Ctrl** while clicking on areas to select multiple at once. Right-clicking will then give an option to delete all selected areas.

#### Available Area Functions

- **None:** A blank, unassigned area.
- **Preset Trigger:** A button that applies a specific preset to the currently selected fixtures.
- **Executor Fader:** A vertical slider that acts as a sub-master for a specific fixture group's intensity.
- **Executor Button:** A button that triggers the main timeline's Play/Pause function.
- **Fixture/Group Selector Lists:** List widgets to select individual fixtures or entire groups, updating the global selection.
- **Group Selector:** A button that selects all fixtures within a specific group.
- **Embedded Stage View:** A mini 3D preview of your stage layout. The camera view is saved with the layout.
- **Embedded Timeline:** A compact set of timeline controls and a visual overview of the timeline.
- **Clock Display:** A digital clock. You can configure its format and font size in the assignment panel.
- **Slider Control:** A generic slider (or dual sliders) that can control parameters like Intensity, Pan, Tilt, Focus, etc., for the currently selected fixtures. These sliders will sync with the state of the selected fixture(s).
- **Color Picker:** A visual color wheel for applying color to selected fixtures. This will sync with the color of the selected fixture(s).
- **Color Palette:** A grid of buttons to store and recall specific colors. Right-click a button to store the selected fixture's color, left-click to apply it.
- **Position Palette:** A grid of buttons to store and recall position data (X/Y/Z position and rotation).
- **Loop Palette:** A grid of buttons to activate/deactivate the dynamic Loop Palettes you've created. Right-click a button to edit the associated Loop Palette.
- **Gradient Editor:** A tool to create color gradients and apply them across a selection of fixtures.
- **Fixture Control:** A dedicated mini-widget to control a single, specific fixture's intensity and color.
- **Master Intensity:** A slider that directly controls the application's main Master Fader.
- **Toggle/Flash Fixture:** Buttons for toggling power or momentarily flashing a specific fixture.
- **Plugin Widgets:** Plugins can register their own custom widgets, which will appear in the assignment list if available.
"""
        self.help_tab_widget.addTab(self._create_help_section(layouts_tab_help_text), "Layouts Tab")
        
        fixtures_tab_help_text = """
### Patch & Fixtures Tab

This tab is where you manage the lighting fixtures in your show file.

#### Core Concepts

- **Fixture ID (FID):** The main number for a fixture (e.g., the `101` in `101.1`). This is the ID used for selection in the command line.
- **Sub-Fixture Index (SFI):** The instance number of a fixture (e.g., the `1` in `101.1`). This allows a single conceptual fixture to have multiple controllable parts, like an LED bar.
- **Fixture List:** The list on the left is a tree view, grouping all sub-fixtures under their parent FID. You can select the parent to affect all instances or a child to affect a single instance.

#### Fixture Profiles

A "Profile" defines the capabilities of a fixture type. It's a template that tells the console what a light can do.

- **Manage Profiles:** Click this button to open the Profile Management dialog.
- **Add/Delete/Edit:** Here you can create new profiles (e.g., "My Custom Laser"), delete unused ones, or edit existing ones.
- **Attributes (JSON):** The core of a profile is its JSON attributes. This defines the parameters the console can control (like `brightness`, `rotation_y`, `zoom`). This flexible system allows you to define almost any kind of device.

#### Patching a Fixture (Adding to your show)

1.  Click **"Add New"**. The form on the right becomes active.
2.  Select a **Fixture Profile** from the dropdown. This is the most important step.
3.  Give the fixture a **Name** (e.g., "Front Truss Wash"). This name is shared by all instances created at once.
4.  Set the starting **FID** and **SFI**.
5.  Set the **Number of Instances** to create. For a single moving head, this is 1. For an 8-cell LED bar, this would be 8, creating fixtures `FID.SFI` through `FID.(SFI+7)`.
6.  Click **"Create New Fixture(s)"** to save. Position and other parameters can be edited after creation.

#### Editing & Deleting

- **Select an Instance:** Click a specific sub-fixture in the tree (e.g., `101.2`) to load its unique properties like 3D position, rotation, and default values. FID and SFI cannot be changed after creation.
- **Save Changes:** After editing, click **"Save Changes"**.
- **Delete Single Instance:** Select a sub-fixture and click **"Delete Selected"**.
- **Delete Entire FID:** Select the top-level parent item (e.g., `101`) in the tree and click **"Delete Selected"** to remove all of its instances.
"""
        self.help_tab_widget.addTab(self._create_help_section(fixtures_tab_help_text), "Fixtures Tab")
        
        fixture_groups_tab_help_text = """
### Groups Tab

This tab is for organizing your patched fixtures into logical groups for fast and easy selection.

#### Why Use Groups?
Instead of selecting fixtures one by one (e.g., `fixture 1 + 3 + 5...`), you can place them in a group (e.g., "Odd Front Truss") and select them all with a single action. Groups are essential for efficient programming.

#### User Interface
- **Left Panel (Fixture Groups):** This list shows all the groups you have created.
  - **Add Group:** Creates a new, empty group. You will be prompted for a unique name.
  - **Rename Group:** Renames the currently selected group.
  - **Delete Group:** Deletes the selected group. This does *not* delete the fixtures themselves, it only un-assigns them from the group.
- **Right Panel (Fixture Assignment):** This area becomes active when you select a group on the left.
  - **Fixtures in Selected Group:** Shows fixtures currently assigned to the selected group. Select one or more and click **"Remove Selected"** to un-assign them.
  - **Available Fixtures:** Shows all fixtures in your patch that are *not* currently in the selected group. Select one or more and click **"Add Selected"** to assign them to the group.

Groups can be selected via the **Quick Selector** dropdown in the header, via the **Command Line** (`group 1`), or by using a **Group Selector** widget in the Layouts tab.
"""
        self.help_tab_widget.addTab(self._create_help_section(fixture_groups_tab_help_text), "Fixture Groups Tab")

        presets_tab_help_text = """
### Presets Tab

Presets are powerful tools for storing and recalling fixture states. They are the building blocks of your show.

#### The "Tracking" Concept
This console uses a "tracking" or "latest-take-precedence" system. When a preset is applied in the timeline, its values for a fixture *persist* through all subsequent cues until a different value for that same parameter is applied. For example, if Cue 1 sets a fixture to Blue, it will remain Blue in Cues 2, 3, and 4, unless one of those cues explicitly sets it to another color.

#### Preset Types
When creating a preset, you must assign it a type. This tells the console which parameters to store.
- **All:** Stores all standard parameters (Dimmer, Color, Position, Beam, Gobo).
- **Dimmer:** Stores only the `brightness` value.
- **Color:** Stores only `red`, `green`, and `blue` values.
- **Position:** Stores `rotation_x`, `rotation_y`, `rotation_z`.
- **Beam:** Stores `zoom`, `focus`, and `shutter_strobe_rate`.
- **Gobo:** Stores the `gobo_spin` value.
This is useful for modular programming (e.g., having separate presets for colors and positions that can be combined).

#### Creating and Updating Presets
- **Create New (from Selection):**
  1. Select fixtures and set their parameters to the desired look.
  2. Click **"Create New"**. You will be prompted for a **Preset Number** (e.g., `1`, `2.5`), an optional name, and the **Preset Type**.
- **Storing to an Existing Number:** If you try to create a preset with a number that already exists, you will be prompted to **Overwrite**, **Merge** (Not Implemented), or **Cancel**.
- **Update (from Selection):** This is the primary way to modify a preset's values. Select a preset in the list, adjust the fixtures, and click this button. The preset will be overwritten with the new values, preserving its original name and type.
- **Command Line:** `store preset <number> "<name>" /type=<type>`. For example: `store preset 1.1 "Blue Fans" /type=Color`.

#### Management
- **Edit Label:** Changes only the name of a preset, not its values.
- **Apply Selected:** Applies the stored values to the currently selected fixtures, affecting their live state immediately. Double-clicking a preset also applies it.
- **View Data:** Shows the raw JSON data stored within the preset.
- **Delete Selected:** Permanently removes the preset.
"""
        self.help_tab_widget.addTab(self._create_help_section(presets_tab_help_text), "Presets Tab")
        
        loop_palettes_tab_help_text = """
### Loops Tab (Loop Palettes)

The Loops tab allows you to create dynamic, generative effects that can be applied to fixtures. These are not static values but continuous, calculated changes over time.

#### Effect Types
- **Sine Wave:** Modulates a single parameter (Dimmer, Pan, Tilt, etc.) along a sine wave.
  - *Speed:* How fast the wave oscillates (in Hz).
  - *Size:* The amplitude of the wave (how far it moves from the center). The max size for Pan/Tilt is 540 degrees.
  - *Center:* The baseline value the wave oscillates around.
  - *Phase Offset:* Shifts the starting point of the wave.
- **Circle:** Creates a circular Pan/Tilt movement.
  - *Speed:* How fast the circle is drawn (in Hz).
  - *Pan/Tilt Radius:* The size of the circle on each axis.
  - *Pan/Tilt Center:* The center point of the circle.
- **U-Shape, Figure 8, Bally, Stagger:** Other pre-defined shapes for specific movements.

#### Grouping & Wings (For Sine Wave on Multiple Fixtures)
When a sine wave loop is applied to a group of fixtures, you can control how the effect is distributed:
- **Group Mode:**
  - *All Same Phase:* All fixtures move together.
  - *Spread Phase Evenly:* Creates a "wave" or "chase" effect across the selection.
  - *Block Modes:* Groups fixtures into blocks (of 2, 3, or 4) that share the same phase, and spreads the phase across the blocks.
- **Wing Style:** Overrides Group Mode to create symmetrical patterns from the center of the selection.
  - *Symmetrical Wings:* Creates a mirrored effect (e.g., fixtures move from the center outwards).
  - *Asymmetrical Wings:* Allows you to define the "center" of the wing effect as a percentage of the selection.

#### Secondary Effects
A single Loop Palette can contain two effects. This allows you to layer movements.
- **Rules:**
  - You cannot have two Pan/Tilt *shape* effects (Circle, U-Shape, etc.) in one palette.
  - You cannot have a sine wave on Pan or Tilt if a shape effect is already active on the other axis.
  - You cannot have two sine waves targeting the exact same parameter.
- **Example:** A primary Circle effect for Pan/Tilt, with a secondary Sine Wave effect on the Dimmer parameter to make the lights fade in and out as they move.
"""
        self.help_tab_widget.addTab(self._create_help_section(loop_palettes_tab_help_text), "Loops Tab")


        # --- Timeline Tab Help ---
        timeline_tab_help_text = """
### Cues / Timeline Tab

This is where you sequence your show for automated playback.

#### UI Components
- **Multi-Track View:** The main area shows events organized into tracks for the Master, each Group, and each Fixture.
- **Ruler:** The top ruler shows time in seconds.
- **Cue Markers:** Diamond markers below the tracks represent your Cues.
- **Event List:** A list at the bottom shows all events for quick selection and overview.

#### Cues vs. Events
- **Cues:** These are the main "Go" points of your show. They are markers on the timeline with a number and an exact trigger time. Think of them as the moments an operator would press the "Go" button.
- **Events:** These are the actual actions that happen. An event might be "Apply Preset 1.1" or "Set Brightness to 50%". Events are linked to cues.

#### Event Timing Modes
This is a critical concept for sequencing. When you create or edit an event, you choose its **Trigger Type**:
1.  **Absolute Time:** The event starts at a specific, fixed time on the timeline (e.g., at `0:15.500`). It is independent of any cue.
2.  **Relative to Cue Trigger:** The event is linked to a cue. It starts a specific amount of time *after* its parent cue fires. If you drag the cue marker on the timeline, this event will move with it, maintaining its relative delay.
3.  **Follow Event in Cue:** The event is chained to another event *within the same cue*. It will start a specific amount of time *after* the previous event finishes. This is useful for creating complex sequences within a single cue press.

#### Interaction
- **Playhead:** The red vertical line shows the current time. You can click and drag it to scrub through the timeline.
- **Cues:** Drag the diamond markers left or right to change their trigger time. Right-click for an edit/delete menu.
- **Events:**
  - **Move:** Click and drag the body of an event to change its start time.
  - **Resize:** Click and drag the left or right edge of an event to change its start time or duration.
  - **Re-assign Track:** Drag an event vertically to a different track to change its target (e.g., from "Group 1" to "Group 2").
  - **Selection:** Click to select, Ctrl-click to multi-select, Right-click-drag to marquee-select.
  - **Context Menu:** Right-click a selected event for options like Edit, Delete, or Assign to Cue.

#### Recording
The **"Record"** button enables a live programming mode. While active, any manual changes you make to fixtures (e.g., via sliders, color pickers, or command line) will be automatically captured as new events on the timeline at the current playhead position.
"""
        self.help_tab_widget.addTab(self._create_help_section(timeline_tab_help_text), "Timeline Tab")
        
        video_sync_tab_help_text = """
### Video Sync Tab

This tab is a utility to help you create cues by watching a video. It is designed to simplify the process of synchronizing your light show to a pre-existing video or performance.

#### Workflow
1.  **Load Video:** Click the **"Load Video"** button and select a video file (`.mp4`, `.mov`, etc.). The video will appear in the player.
2.  **Play/Pause & Seek:** Use the playback controls to navigate the video. Find the exact moments where you want a lighting change to occur.
3.  **Mark Cue:** When the video is at the desired moment, click the **"Mark Cue Point"** button. The current timestamp will be added to the list of "Marked Cues" on the right. You can add as many cue points as you need.
4.  **Review & Remove:** The list on the right shows all your marked timestamps. If you make a mistake, you can **double-click** an item in the list to remove it.
5.  **Send to Timeline:** Once you are satisfied with your marked points, click **"Send Marked Cues to Timeline"**.
6.  **Process in Timeline Tab:** The application will then switch to the Timeline tab and open the "Add Event" dialog for the *first* cue point you marked. After you create that event, the dialog will automatically open again for the second cue point, and so on, until all marked cues have been processed. This allows you to quickly build the basic structure of your show's timing.
"""
        self.help_tab_widget.addTab(self._create_help_section(video_sync_tab_help_text), "Video Sync Tab")


        visualization_tab_help_text = """
### Stage 3D Tab

This tab provides a live 3D visualization of your patched fixtures and their current state.

#### Navigation
- **Orbit:** **Left-click and drag** to rotate the camera around the center point.
- **Pan:** **Right-click and drag** to move the camera view left, right, up, and down.
- **Zoom:** Use the **mouse wheel** to zoom in and out.

#### Display Options
- **Show Grid:** Toggles the visibility of the ground grid.
- **Show Axes:** Toggles the visibility of the world X (Red), Y (Green), and Z (Blue) axis lines at the origin.
- **Show Beams:** Toggles the visibility of all light beams. This is useful for reducing visual clutter when focusing on fixture positions.

#### Visual Feedback
- **Fixture State:** The 3D models will update in real-time to reflect changes in position, rotation, color, and brightness.
- **Selection:** Any fixtures currently selected in the application (e.g., via the Layouts or Groups tab) will be highlighted with a yellow wireframe box for easy identification.
"""
        self.help_tab_widget.addTab(self._create_help_section(visualization_tab_help_text), "3D View Tab")

        settings_tab_help_text = """
### Setup Tab (Settings)

This tab is for configuring application-wide settings and managing show data.

#### Sections
- **Appearance:**
  - **Theme:** Select a visual theme for the application. Themes can change colors, widget styles, and even the main tab bar position.
- **Application Settings:**
  - **Window Always on Top:** Forces the application window to stay on top of all other windows.
- **Gamepad Settings:**
  - **Enable Gamepad Control:** Toggles all gamepad input on or off.
  - **Control Mode:** Choose between **Single Joystick** (Right stick controls Pan/Tilt) or **Dual Joystick** (Left stick for Tilt, Right stick for Pan).
  - **Sensitivity:** Adjusts the speed of Pan/Tilt movement from the joystick.
  - **Invert Tilt:** Inverts the Y-axis for tilt control.
- **ROBLOX Integration:**
  - **Enable Live Mode:** When checked, the application's internal HTTP server is active and will send fixture updates to a listening Roblox game.
  - **Import Positions from ROBLOX:** Sends a request to the connected Roblox game, asking it to report the current 3D positions of its light models. The application will then update the patched fixture positions to match.
- **Keybinds:**
  - This table lists all available actions that can be assigned a keyboard shortcut.
  - **Change Keybind:** Select an action and click this to press the new key combination.
  - **Clear Keybind:** Removes the shortcut for the selected action.
  - **Apply & Save Keybinds:** You **must** click this button to save your keybinding changes. The new keybinds will become active immediately.
- **Data Management:**
  - **Export/Import Complete Show Data:** Saves or loads the *entire* show file (all fixtures, profiles, presets, cues, layouts, etc.) to a single `.json` file. This is for backing up or sharing your whole project.
  - **Export/Import Current Layout:** Saves or loads *only* the layout from the Main Tab. This is useful for sharing or reusing control surface layouts between different show files.
"""
        self.help_tab_widget.addTab(self._create_help_section(settings_tab_help_text), "Settings Tab")

        plugins_tab_help_text = """
### Plugins Tab

This tab allows you to manage external plugins that can extend the functionality of the application.

#### How Plugins Work
Plugins are self-contained modules that can add new features, such as new area widgets for the Layouts tab, new data export formats, or new ways to interact with external hardware.

#### Managing Plugins
- **Installation:** To install a new plugin, simply place its entire folder into the `plugins` directory located alongside the main application executable.
- **Discover New Plugins:** After adding or removing plugin folders, click this button to have the application re-scan the `plugins` directory and update the list.
- **Enable/Disable:** Use the checkbox next to each plugin to enable or disable it.
- **Details:** Selecting a plugin from the list will show its name, author, version, and a description in the panel on the right.

**IMPORTANT:** You must **restart the application** for any changes made on this tab (enabling, disabling, or discovering new plugins) to take full effect.
"""
        self.help_tab_widget.addTab(self._create_help_section(plugins_tab_help_text), "Plugins Tab")


        main_layout.addWidget(self.help_tab_widget)
        self.setLayout(main_layout)
