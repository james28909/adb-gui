import os
import sys
import subprocess
import shlex
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QFileDialog, QLineEdit, QGroupBox, QTabWidget,
                             QTextEdit, QSplitter, QScrollArea)
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
        """Setup device information display with organized categories."""
        layout = QVBoxLayout()
        
        # Top button for copying all getprop output
        copy_all_button = QPushButton("Copy All Device Properties to Clipboard")
        copy_all_button.clicked.connect(self.copy_all_properties)
        layout.addWidget(copy_all_button)
        
        # Create splitter for organized property categories
        splitter = QSplitter(Qt.Horizontal)
        
        # Property categories
        self.property_categories = {
            "Device Identity": [
                "ro.product.model", "ro.product.manufacturer", "ro.product.brand",
                "ro.product.device", "ro.serialno", "ro.product.board"
            ],
            "System Version": [
                "ro.build.version.release", "ro.build.version.sdk", "ro.build.id",
                "ro.build.type", "ro.build.fingerprint", "ro.build.date"
            ],
            "Custom ROM": [
                "ro.lineage.version", "ro.lineage.device", "ro.lineage.releasetype",
                "ro.lineage.build.vendor_security_patch"
            ],
            "Security & Debug": [
                "ro.debuggable", "ro.secure", "ro.crypto.state", "ro.build.tags"
            ],
            "Hardware & Features": [
                "ro.product.cpu.abi", "ro.treble.enabled", "ro.vndk.lite",
                "ro.fastbootd.available"
            ],
            "Connectivity": [
                "sys.usb.config", "sys.usb.state", "persist.sys.usb.config"
            ]
        }
        
        # Create text widgets for each category
        self.category_widgets = {}
        for category, props in self.property_categories.items():
            group = QGroupBox(category)
            group_layout = QVBoxLayout()
            
            # Text area for this category
            text_widget = QTextEdit()
            text_widget.setFont(QFont("Courier", 9))
            text_widget.setMaximumHeight(200)
            
            # Copy button for this category
            copy_button = QPushButton(f"Copy {category}")
            copy_button.clicked.connect(lambda checked, cat=category: self.copy_category(cat))
            
            group_layout.addWidget(text_widget)
            group_layout.addWidget(copy_button)
            group.setLayout(group_layout)
            
            self.category_widgets[category] = text_widget
            splitter.addWidget(group)
        
        layout.addWidget(splitter)
        self.device_info_tab.setLayout(layout)

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
        """Load device properties and populate category widgets."""
        try:
            # Get all properties
            result = subprocess.run(['adb', 'shell', 'getprop'], 
                                  capture_output=True, text=True, check=True)
            all_props = result.stdout
            
            # Parse properties into dictionary
            props_dict = {}
            for line in all_props.strip().split('\n'):
                if line.startswith('[') and ']: [' in line:
                    key = line.split(']: [')[0][1:]
                    value = line.split(']: [')[1].rstrip(']')
                    props_dict[key] = value
            
            # Populate each category
            for category, prop_keys in self.property_categories.items():
                text_widget = self.category_widgets[category]
                content = []
                
                for prop_key in prop_keys:
                    if prop_key in props_dict:
                        content.append(f"{prop_key}: {props_dict[prop_key]}")
                    else:
                        content.append(f"{prop_key}: <not found>")
                
                text_widget.setPlainText('\n'.join(content))
            
            # Store all properties for full copy function
            self.all_properties = all_props
            
        except subprocess.CalledProcessError as e:
            for widget in self.category_widgets.values():
                widget.setPlainText(f"Error loading properties: {str(e)}")

    def copy_category(self, category):
        """Copy specific category properties to clipboard."""
        text_widget = self.category_widgets[category]
        content = text_widget.toPlainText()
        self.copy_to_clipboard(content)

    def copy_all_properties(self):
        """Copy all device properties to clipboard."""
        if hasattr(self, 'all_properties'):
            self.copy_to_clipboard(self.all_properties)
        else:
            self.copy_to_clipboard("Properties not loaded yet")

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

