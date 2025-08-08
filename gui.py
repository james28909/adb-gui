import os
import sys
import subprocess
import shlex
import re
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QFileDialog, QLineEdit, QGroupBox, QTabWidget,
                             QTextEdit, QSplitter, QScrollArea, QListWidget, QGridLayout, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

class PartitionDumper(QWidget):
    """
    A Qt-based GUI application for dumping Android device partitions via ADB.
    This class provides a user-friendly interface for connecting to Android devices,
    listing available partitions, and creating binary dumps of selected partitions.
    The application uses ADB (Android Debug Bridge) to communicate with connected
    Android devices and extract partition data.
    Key Features:
    - Automatic discovery and listing of device partitions
    - Display of partition names and sizes in a tree widget
    - Selective dumping of partitions via checkboxes
    - Configurable output directory with path validation
    - Real-time status updates during operations
    - Output files saved as .img format in specified directory
    GUI Components:
    - QTreeWidget: Displays partitions with name, size, and status columns
    - QLineEdit: Input field for custom output directory path
    - QPushButton: Browse button for folder selection dialog
    - QPushButton: Triggers the dumping process for selected partitions
    - QLabel: Shows current operation status and progress
    Requirements:
    - ADB installed and accessible in system PATH
    - Android device connected with USB debugging enabled
    - Appropriate device permissions for partition access
    - Qt/PyQt for GUI functionality
    Usage:
    1. Connect Android device via USB with debugging enabled
    2. Launch application to automatically load partition list
    3. Specify output directory (defaults to "./dumped")
    4. Select desired partitions using checkboxes
    5. Click "Dump Selected Partitions" to begin extraction
    6. Monitor status label for progress and completion
    Output:
    - Binary partition dumps saved as {partition_name}.img files
    - Files created in specified output directory
    - Directory automatically created if it doesn't exist
    This tool is designed for MMC-based Android devices (mmcblk0 naming convention)
    and may not work with all device types or storage configurations.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADB Partition Dumper")
        self.layout = QVBoxLayout()
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Partition dumper tab
        self.partition_tab = QWidget()
        self.setup_partition_tab()
        self.tab_widget.addTab(self.partition_tab, "Partition Dumper")
        
        # Device info tab
        self.device_info_tab = QWidget()
        self.setup_device_info_tab()
        self.tab_widget.addTab(self.device_info_tab, "Device Info")
        
        self.layout.addWidget(self.tab_widget)
        self.setLayout(self.layout)
        
        self.load_partitions()
        self.load_device_info()

    def setup_partition_tab(self):
        """Setup the original partition dumper interface."""
        layout = QVBoxLayout()
        
        # Output directory section
        self.setup_output_directory_section()
        
        # Partition list
        self.list_widget = QTreeWidget()
        self.list_widget.setHeaderLabels(["Partition", "Size", "Status"])
        self.list_widget.setColumnCount(3)
        
        # Dump button
        self.dump_button = QPushButton("Dump Selected Partitions")
        self.dump_button.clicked.connect(self.dump_partitions)
        
        # Status label
        self.status_label = QLabel("Status: Ready")
        
        # Add widgets to layout
        layout.addWidget(self.output_group)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.dump_button)
        layout.addWidget(self.status_label)
        
        self.partition_tab.setLayout(layout)

    def setup_device_info_tab(self):
        """Modern device info UI: Overview + Filter + Categorized tree + Copy/Export."""
        layout = QVBoxLayout()

        # Overview group
        self.overview_group = QGroupBox("Overview")
        grid = QGridLayout()
        self.overview_fields = [
            "Model", "Manufacturer", "Android", "Security Patch",
            "Build ID", "Build Display", "Fingerprint",
            "Device", "Name", "Board",
            "Bootloader", "Baseband", "Serial",
            "LineageOS", "Treble", "ADB Root"
        ]
        self.overview_labels = {}
        for i, field in enumerate(self.overview_fields):
            grid.addWidget(QLabel(f"{field}:"), i, 0, alignment=Qt.AlignRight)
            val_lbl = QLabel("")
            val_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.overview_labels[field] = val_lbl
            grid.addWidget(val_lbl, i, 1)
        self.overview_group.setLayout(grid)
        layout.addWidget(self.overview_group)

        # Toolbar: filter + actions
        tool = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter properties (substring or regex)...")
        self.filter_edit.textChanged.connect(self.apply_property_filter)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_device_info)
        copy_overview_btn = QPushButton("Copy Overview")
        copy_overview_btn.clicked.connect(self.copy_overview)
        copy_filtered_btn = QPushButton("Copy Filtered")
        copy_filtered_btn.clicked.connect(self.copy_filtered_properties)
        copy_all_btn = QPushButton("Copy All")
        copy_all_btn.clicked.connect(self.copy_all_properties)
        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self.export_properties)

        tool.addWidget(QLabel("Filter:"))
        tool.addWidget(self.filter_edit)
        tool.addWidget(refresh_btn)
        tool.addStretch(1)
        tool.addWidget(copy_overview_btn)
        tool.addWidget(copy_filtered_btn)
        tool.addWidget(copy_all_btn)
        tool.addWidget(export_btn)
        layout.addLayout(tool)

        # Categorized properties tree
        self.props_tree = QTreeWidget()
        self.props_tree.setHeaderLabels(["Property", "Value"])
        self.props_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.props_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.props_tree.setUniformRowHeights(True)
        self.props_tree.setAlternatingRowColors(True)
        layout.addWidget(self.props_tree)

        self.device_info_tab.setLayout(layout)

    def create_property_list(self, category_name, properties):
        """Create a scrollable list widget for a property category."""
        group = QGroupBox(category_name)
        group_layout = QVBoxLayout()
        
        # List widget for properties
        list_widget = QListWidget()
        list_widget.setFont(QFont("Courier", 9))
        list_widget.setMaximumHeight(300)
        
        # Add properties to list
        for prop in properties:
            list_widget.addItem(prop)
        
        # Copy button for this category
        copy_button = QPushButton(f"Copy {category_name}")
        copy_button.clicked.connect(lambda checked, cat=category_name: self.copy_property_list(cat))
        
        group_layout.addWidget(list_widget)
        group_layout.addWidget(copy_button)
        group.setLayout(group_layout)
        
        self.property_lists[category_name] = list_widget
        return group

    def copy_property_list(self, category):
        """Copy specific property list to clipboard."""
        list_widget = self.property_lists[category]
        items = []
        for i in range(list_widget.count()):
            items.append(list_widget.item(i).text())
        content = '\n'.join(items)
        self.copy_to_clipboard(content)

    def setup_output_directory_section(self):
        """Setup the output directory selection UI components."""
        # Create group box for output directory controls
        self.output_group = QGroupBox("Output Directory")
        output_layout = QHBoxLayout()
        
        # Directory path input field
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setText("./dumped")  # Default value
        self.output_path_edit.setPlaceholderText("Enter output directory path...")
        
        # Browse button for folder selection
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_output_directory)
        
        # Add to layout
        output_layout.addWidget(QLabel("Path:"))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.browse_button)
        
        self.output_group.setLayout(output_layout)

    def browse_output_directory(self):
        """Open a folder selection dialog and update the path field with device-specific subfolder."""
        current_path = self.get_resolved_output_path()
        
        # Use current directory if the resolved path doesn't exist
        if not os.path.exists(current_path):
            current_path = os.getcwd()
            
        selected_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Directory", 
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if selected_dir:
            # Get device info and create default subfolder
            device_name, serial = self.get_device_info()
            default_folder_name = self.create_default_folder_name(device_name, serial)
            
            # Set path to include the device-specific subfolder
            device_specific_path = os.path.join(selected_dir, default_folder_name)
            self.output_path_edit.setText(device_specific_path)

    def get_resolved_output_path(self):
        """
        Resolve the output path handling various path formats.
        
        Supports:
        - Relative paths: "./here", "here"
        - Home directory shortcuts: "~/here"
        - Environment variables: "$HOME/here"
        - Absolute paths: "/home/user/here"
        
        Returns:
            str: Absolute path to the output directory
        """
        path = self.output_path_edit.text().strip()
        
        if not path:
            path = "./dumped"  # Default fallback
            
        # Expand environment variables (like $HOME)
        path = os.path.expandvars(path)
        
        # Expand user home directory (like ~)
        path = os.path.expanduser(path)
        
        # Convert to absolute path
        path = os.path.abspath(path)
        
        return path

    def ensure_output_directory(self):
        """
        Ensure the output directory exists, create it if necessary.
        
        Returns:
            bool: True if directory exists or was created successfully, False otherwise
        """
        try:
            output_path = self.get_resolved_output_path()
            
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)
                self.status_label.setText(f"Status: Created directory {output_path}")
                QApplication.processEvents()
                
            return True
            
        except Exception as e:
            self.status_label.setText(f"Status: Error creating directory - {str(e)}")
            return False

    def create_default_folder_name(self, device_name, serial):
        """Create a safe folder name from device name and serial"""
        # Remove invalid characters and replace spaces with underscores
        safe_name = "".join(c for c in device_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        safe_serial = "".join(c for c in serial if c.isalnum() or c in ('-', '_')).strip()
        
        return f"{safe_name}_{safe_serial}"

    def load_partitions(self):
        """Loads partition information from an Android device via ADB and populates a QTreeWidget."""
        # Single command that outputs: partition_name|actual_name|size_bytes
        cmd = '''for part in /sys/block/mmcblk0/mmcblk0p*; do 
            name=$(grep ^PARTNAME= "$part/uevent" 2>/dev/null | cut -d= -f2)
            size=$(cat "$part/size" 2>/dev/null)
            if [ -n "$size" ]; then
                echo "$(basename "$part")|${name:-unknown}|$size"
            fi
        done'''
        
        result = subprocess.run(['adb', 'shell', cmd], capture_output=True, text=True)
        
        if result.returncode != 0:
            self.status_label.setText("Status: Failed to load partitions")
            return
        
        # Collect all partition data first
        partition_data = []
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) == 3:
                    partition_id, part_name, size_sectors_str = parts
                    try:
                        # Convert to Python int (unlimited precision) first, then to bytes
                        size_sectors = int(size_sectors_str)
                        size_bytes = size_sectors * 512
                        
                        # Show readable format with exact bytes
                        if size_bytes >= 1024**3:  # GB
                            size_gb = round(size_bytes / (1024**3), 2)
                            size_str = f"{size_gb} GB ({size_bytes:,} bytes)"
                        elif size_bytes >= 1024**2:  # MB
                            size_mb = round(size_bytes / (1024**2), 2)
                            size_str = f"{size_mb} MB ({size_bytes:,} bytes)"
                        elif size_bytes >= 1024:  # KB
                            size_kb = round(size_bytes / 1024, 2)
                            size_str = f"{size_kb} KB ({size_bytes:,} bytes)"
                        else:  # Bytes
                            size_str = f"{size_bytes:,} bytes"
                            
                    except ValueError:
                        size_str = "Unknown"
                    
                    partition_data.append((part_name, size_str))
        
        # Sort by partition name (alphabetically)
        partition_data.sort(key=lambda x: x[0].lower())
        
        # Add sorted items to the widget
        for part_name, size_str in partition_data:
            item = QTreeWidgetItem([part_name, size_str, "Pending"])
            item.setCheckState(0, Qt.Unchecked)
            self.list_widget.addTopLevelItem(item)
        
        # Auto-resize columns to fit content with custom padding
        self.list_widget.resizeColumnToContents(0)  # Partition column
        self.list_widget.resizeColumnToContents(1)  # Size column  
        self.list_widget.resizeColumnToContents(2)  # Status column

        # Add custom padding to each column
        partition_padding = 15
        size_padding = 25      # Size column needs more space due to long text
        status_padding = 15

        self.list_widget.setColumnWidth(0, self.list_widget.columnWidth(0) + partition_padding)
        self.list_widget.setColumnWidth(1, self.list_widget.columnWidth(1) + size_padding)
        self.list_widget.setColumnWidth(2, self.list_widget.columnWidth(2) + status_padding)

        # Calculate and set window size to fit content
        self.resize_to_fit_content()

    def resize_to_fit_content(self):
        """Resize the window to fit the tree widget content without scrollbars."""
        # Force layout update first
        QApplication.processEvents()
        
        # Calculate total width needed (columns + margins)
        total_column_width = sum(self.list_widget.columnWidth(i) for i in range(3))
        
        # Account for tree widget frame, potential scrollbar space, and window margins
        frame_width = self.list_widget.frameWidth() * 2  # Left and right frame
        scrollbar_width = 20  # Reserve space for potential scrollbar even if hidden
        window_margins = 30  # Window border and layout margins
        
        total_width = total_column_width + frame_width + scrollbar_width + window_margins
        
        # Calculate height needed - use actual row count (not minus 1)
        row_count = self.list_widget.topLevelItemCount()
        
        if row_count > 0:
            # Get actual row height from first item
            first_item = self.list_widget.topLevelItem(0)
            item_rect = self.list_widget.visualItemRect(first_item)
            row_height = item_rect.height()
        else:
            row_height = 25  # Fallback
        
        # Calculate exact tree widget height needed
        header_height = self.list_widget.header().height()
        rows_height = row_count * row_height  # Use full row count
        
        # Only add the frame for the tree widget border
        tree_frame = self.list_widget.frameWidth() * 2
        tree_widget_height = header_height + rows_height + tree_frame
        
        # Get other component heights
        button_height = self.dump_button.sizeHint().height()
        status_height = self.status_label.sizeHint().height()
        
        # Get actual layout spacing and margins
        actual_spacing = self.partition_tab.layout().spacing()
        if actual_spacing == -1:  # Default spacing
            actual_spacing = 6  # Qt default
        
        layout_margins = self.partition_tab.layout().contentsMargins()
        margin_height = layout_margins.top() + layout_margins.bottom()
        
        # Only 2 spacing gaps between 3 widgets
        total_spacing = actual_spacing * 2
        
        # Window title bar - be more precise
        title_bar_height = 28
        
        # Calculate total height
        total_height = (tree_widget_height + button_height + status_height + 
                       total_spacing + margin_height + title_bar_height)
        
        # Don't exceed screen size
        try:
            screen = QApplication.primaryScreen().geometry()
            max_width = int(screen.width() * 0.9)
            max_height = int(screen.height() * 0.9)
            
            final_width = min(total_width, max_width)
            final_height = min(total_height, max_height)
            
            self.resize(final_width, final_height)
        except:
            # Fallback if screen detection fails
            self.resize(800, 600)

    def load_device_info(self):
        """Fetch, parse, summarize, categorize, and render device properties."""
        def _post_load(all_props_text):
            self.all_properties = all_props_text
            props = self.parse_getprop_output(all_props_text)
            self.populate_overview(props)
            self.populate_properties_tree(props)
            # Apply current filter (if any)
            self.apply_property_filter()

        try:
            result = subprocess.run(['adb', 'shell', 'getprop'],
                                    capture_output=True, text=True, check=True)
            _post_load(result.stdout)
        except subprocess.CalledProcessError:
            # Fallback to local sample if ADB fails
            try:
                fallback_path = os.path.join(os.path.dirname(__file__), 'adb_shell_getprop.output')
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    _post_load(f.read())
            except Exception as e:
                # Minimal error display
                self.props_tree.clear()
                root = QTreeWidgetItem(["Error", f"Failed to load properties: {str(e)}"])
                self.props_tree.addTopLevelItem(root)
                self.all_properties = "Error loading properties."

    # Helpers: parsing and categorization

    def parse_getprop_output(self, text):
        """Parse adb shell getprop output into dict."""
        props = {}
        for line in text.strip().splitlines():
            if line.startswith('[') and ']: [' in line:
                key = line.split(']: [', 1)[0][1:]
                value = line.split(']: [', 1)[1].rstrip(']')
                props[key] = value
        return props

    def get_prop(self, props, keys, default=""):
        """Return first non-empty/non-unknown value for keys."""
        for k in keys:
            v = props.get(k, "").strip()
            if v and v.lower() not in ("unknown",):
                return v
        return default

    def populate_overview(self, props):
        """Compute and fill the overview grid."""
        android = self.get_prop(props, ['ro.build.version.release'])
        sdk = self.get_prop(props, ['ro.build.version.sdk'])
        android_display = f"{android} (SDK {sdk})" if android or sdk else ""

        adb_root_raw = self.get_prop(props, ['service.adb.root', 'init.svc.adb_root'])
        adb_root = "Yes" if adb_root_raw in ("1", "running", "true", "True") else ("No" if adb_root_raw else "")

        overview = {
            "Model": self.get_prop(props, ['ro.product.model', 'ro.product.system.model', 'ro.product.vendor.model', 'ro.product.odm.model'], "Unknown"),
            "Manufacturer": self.get_prop(props, ['ro.product.manufacturer', 'ro.product.vendor.manufacturer']),
            "Android": android_display,
            "Security Patch": self.get_prop(props, ['ro.build.version.security_patch']),
            "Build ID": self.get_prop(props, ['ro.build.id']),
            "Build Display": self.get_prop(props, ['ro.build.display.id']),
            "Fingerprint": self.get_prop(props, ['ro.build.fingerprint']),
            "Device": self.get_prop(props, ['ro.product.device']),
            "Name": self.get_prop(props, ['ro.product.name']),
            "Board": self.get_prop(props, ['ro.product.board', 'ro.board.platform']),
            "Bootloader": self.get_prop(props, ['ro.bootloader', 'ro.boot.bootloader']),
            "Baseband": self.get_prop(props, ['gsm.version.baseband']),
            "Serial": self.get_prop(props, ['ro.serialno', 'ro.boot.serialno']),
            "LineageOS": self.get_prop(props, ['ro.lineage.display.version', 'ro.modversion', 'ro.lineage.version']),
            "Treble": self.get_prop(props, ['ro.treble.enabled']),
            "ADB Root": adb_root,
        }

        for field in self.overview_fields:
            val = overview.get(field, "")
            self.overview_labels[field].setText(val)

    def categorize_property(self, key):
        """Heuristic category for a given prop key."""
        # Ordered checks from most specific to general
        if key.startswith(('ro.build.', 'build.', 'ro.system.build.', 'ro.vendor.build.', 'ro.odm.build.', 'ro.product.build.')):
            return "Build"
        if key.startswith(('ro.product.',)):
            return "Product"
        if key.startswith(('ro.vendor.', 'vendor.')):
            return "Vendor"
        if key.startswith(('ro.boot', 'ro.bootloader', 'boot.', 'init.svc', 'init.svc_debug_pid', 'ro.boottime.', 'service.bootanim')):
            return "Boot"
        if key.startswith(('dalvik.', 'pm.dexopt', 'ro.zygote', 'sys.system_server', 'sys.boot', 'sys.use_memfd', 'ro.runtime.', 'tombstoned.')):
            return "Runtime/ART"
        if key.startswith(('ril.', 'gsm.', 'telephony.', 'ro.telephony.', 'keyguard.')):
            return "Radio/Telephony"
        if key.startswith(('net.', 'wifi.', 'wlan.', 'dhcp.', 'ro.wifi.', 'wificond', 'wifi.', 'netd', 'ro.opengles.')):
            return "Network/Wi‑Fi"
        if key.startswith(('usb.', 'sys.usb.', 'persist.sys.usb.', 'ro.usb.', 'vendor.usb.', 'init.svc.vendor.usb')):
            return "USB"
        if key.startswith(('bluetooth', 'bt.', 'vendor.bluetooth', 'persist.bluetooth', 'net.bt.')):
            return "Bluetooth"
        if key.startswith(('audio.', 'media.', 'vendor.audio', 'av.offload', 'qcom.audio.', 'log.tag.APM_AudioPolicyManager', 'media.recorder.')):
            return "Audio/Media"
        if key.startswith(('graphics.', 'debug.sf.', 'ro.hwui.', 'vendor.hwcomposer', 'gralloc', 'ro.sf.')):
            return "Graphics/Display"
        if key.startswith(('nfc.', 'ro.nfc.')):
            return "NFC"
        if key.startswith(('vold.', 'ro.crypto', 'ro.storage', 'selinux.restorecon_recursive')) or 'fstab' in key or key.endswith('.fsck'):
            return "Storage/FS"
        if key.startswith(('service.', 'hwservicemanager', 'servicemanager', 'vndservicemanager', 'ro.persistent_properties')):
            return "Services/Daemons"
        if key.startswith(('security.', 'selinux.', 'ro.secure', 'ro.secwvk', 'ro.control_privapp_permissions')):
            return "Security"
        if key.startswith(('persist.', 'debug.', 'log.', 'logd.', 'ro.logd.')):
            return "Debug/Logging"
        if key.startswith('ro.'):
            return "System (ro.*)"
        return "Other"

    def populate_properties_tree(self, props):
        """Fill the tree with categorized properties."""
        self.props_tree.clear()
        categories = {}
        for k, v in props.items():
            cat = self.categorize_property(k)
            categories.setdefault(cat, []).append((k, v))

        for cat in sorted(categories.keys()):
            parent = QTreeWidgetItem([cat, ""])
            parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
            self.props_tree.addTopLevelItem(parent)
            for k, v in sorted(categories[cat], key=lambda x: x[0].lower()):
                child = QTreeWidgetItem([k, v])
                parent.addChild(child)
            parent.setExpanded(True)

    def apply_property_filter(self):
        """Filter visible rows by substring or regex on key/value."""
        pattern = self.filter_edit.text().strip()
        regex = None
        if pattern:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                # Fallback to plain substring
                regex = None

        def match(text):
            if not pattern:
                return True
            if regex:
                return bool(regex.search(text))
            return pattern.lower() in text.lower()

        for i in range(self.props_tree.topLevelItemCount()):
            parent = self.props_tree.topLevelItem(i)
            visible_children = 0
            for j in range(parent.childCount()):
                child = parent.child(j)
                key = child.text(0)
                val = child.text(1)
                is_match = match(key) or match(val)
                child.setHidden(not is_match)
                if is_match:
                    visible_children += 1
            parent.setHidden(visible_children == 0)
            parent.setExpanded(visible_children > 0)

    def collect_visible_properties(self):
        """Collect currently visible key: value pairs from the tree."""
        lines = []
        for i in range(self.props_tree.topLevelItemCount()):
            parent = self.props_tree.topLevelItem(i)
            if parent.isHidden():
                continue
            for j in range(parent.childCount()):
                child = parent.child(j)
                if not child.isHidden():
                    lines.append(f"{child.text(0)}: {child.text(1)}")
        return "\n".join(lines)

    # Copy/Export actions

    def copy_overview(self):
        """Copy overview section."""
        lines = []
        for field in self.overview_fields:
            val = self.overview_labels[field].text()
            if val:
                lines.append(f"{field}: {val}")
        self.copy_to_clipboard("\n".join(lines) if lines else "No overview data.")

    def copy_filtered_properties(self):
        """Copy only currently visible (filtered) properties."""
        content = self.collect_visible_properties()
        if not content and hasattr(self, 'all_properties'):
            content = self.all_properties
        self.copy_to_clipboard(content or "No properties.")

    def copy_all_properties(self):
        """Copy all device properties to clipboard."""
        if hasattr(self, 'all_properties'):
            self.copy_to_clipboard(self.all_properties)
        else:
            self.copy_to_clipboard("Properties not loaded yet")

    def export_properties(self):
        """Export filtered (or all if no filter) to a file."""
        default_name = "device_properties.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Export Properties", default_name, "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        content = self.collect_visible_properties() or getattr(self, 'all_properties', '')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            # Optional: update status on partition tab if present
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Status: Exported properties to {path}")
        except Exception as e:
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Status: Export failed - {str(e)}")

    # ...existing code...

    def copy_to_clipboard(self, text):
        """Cross-platform clipboard copy function."""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # Update status if we're on partition tab
            if hasattr(self, 'status_label'):
                self.status_label.setText("Status: Copied to clipboard")
                
        except Exception as e:
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Status: Copy failed - {str(e)}")

    def get_device_info(self):
        """Get device name and serial for folder naming"""
        try:
            # Get device serial
            result = subprocess.run(['adb', 'get-serialno'], 
                                  capture_output=True, text=True, check=True)
            serial = result.stdout.strip()
            
            # Try to get device model from the loaded properties
            if hasattr(self, 'all_properties'):
                # Parse for ro.product.model
                for line in self.all_properties.split('\n'):
                    if 'ro.product.model' in line and ']: [' in line:
                        device_name = line.split(']: [')[1].rstrip(']')
                        if device_name and device_name != 'unknown':
                            return device_name, serial
            
            # Fallback to original method
            device_props = [
                'ro.product.model',
                'ro.product.name', 
                'ro.product.device'
            ]
            
            device_name = "Unknown"
            for prop in device_props:
                result = subprocess.run(['adb', 'shell', f'getprop {prop}'], 
                                      capture_output=True, text=True, check=True)
                value = result.stdout.strip()
                if value and value.lower() not in ['unknown', '', 'android']:
                    device_name = value
                    break
            
            return device_name, serial
        except subprocess.CalledProcessError:
            return "Unknown", "Unknown"

    def dump_partitions(self):
        """Dumps selected partitions with improved error handling."""
        # First ensure output directory exists
        if not self.ensure_output_directory():
            return
            
        count = self.list_widget.topLevelItemCount()
        selected_items = [self.list_widget.topLevelItem(i) for i in range(count)
                        if self.list_widget.topLevelItem(i).checkState(0) == Qt.Checked]
        if not selected_items:
            self.status_label.setText("Status: No partitions selected")
            return
            
        output_path = self.get_resolved_output_path()
        
        for item in selected_items:
            part = item.text(0)
            # Sanitize partition name
            safe_part = "".join(c for c in part if c.isalnum() or c in ('-', '_'))
            if safe_part != part:
                self.status_label.setText(f"Status: Invalid partition name: {part}")
                item.setText(2, "Failed")
                continue
                
            self.status_label.setText(f"Dumping {part}...")
            QApplication.processEvents()
            
            dump_file = os.path.join(output_path, f"{part}.img")
            
            try:
                # Use shlex.quote for proper escaping
                cmd = f'adb exec-out dd if=/dev/block/by-name/{safe_part} bs=4096 status=none > {shlex.quote(dump_file)}'
                result = subprocess.run(cmd, shell=True, check=True)
                
                # Verify file was created and has content
                if os.path.exists(dump_file) and os.path.getsize(dump_file) > 0:
                    item.setText(2, "Done")
                else:
                    item.setText(2, "Failed")
                    
            except subprocess.CalledProcessError as e:
                self.status_label.setText(f"Status: Error dumping {part}: {str(e)}")
                item.setText(2, "Failed")
                
        self.status_label.setText(f"Status: Dump completed to {output_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PartitionDumper()
    window.show()
    sys.exit(app.exec())

