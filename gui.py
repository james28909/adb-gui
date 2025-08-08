import os
import sys
import subprocess
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QCheckBox, 
                             QLabel, QFileDialog, QLineEdit, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QScreen

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
        
        # Output directory section
        self.setup_output_directory_section()
        
        # Partition list
        self.list_widget = QTreeWidget()
        self.list_widget.setHeaderLabels(["Partition", "Size", "Status"])
        self.list_widget.setColumnCount(3)
        
        # Dump button
        self.dump_button = QPushButton("Dump Selected Partitions")
        
        # Status label
        self.status_label = QLabel("Status: Ready")
        
        # Add widgets to layout
        self.layout.addWidget(self.output_group)
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.dump_button)
        self.layout.addWidget(self.status_label)
        
        self.setLayout(self.layout)
        self.dump_button.clicked.connect(self.dump_partitions)
        self.load_partitions()

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
        """Open a folder selection dialog and update the path field."""
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
            self.output_path_edit.setText(selected_dir)

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

    def load_partitions(self):
        """
        Loads partition information from an Android device via ADB and populates a QTreeWidget.
        This method executes a shell command on the connected Android device to retrieve partition
        information including partition names, actual names, and sizes. The command iterates through
        MMC block device partitions and extracts metadata from the kernel's sysfs interface.
        The retrieved data is parsed and each valid partition is added as a QTreeWidgetItem to the
        GUI's tree widget, displaying:
        - Partition name (from PARTNAME in uevent)
        - Size in megabytes (converted from 512-byte sectors)
        - Default status of "Pending"
        - Unchecked checkbox state
        Args:
            None
        Returns:
            None
            - Updates self.status_label.setText() if partition loading fails
            - Populates self.list_widget with QTreeWidgetItem objects for each partition
            - Each item has checkbox functionality (initially unchecked)
        Raises:
            No explicit exceptions raised, but handles:
            - subprocess failures (non-zero return code)
            - ValueError when parsing size information
        Assumptions:
            - Android device is connected and accessible via ADB
            - Device has MMC storage (/sys/block/mmcblk0/*)
            - GUI contains 'status_label' and 'list_widget' attributes
            - ADB is installed and available in system PATH
        Note:
            The method assumes MMC block device naming convention (mmcblk0p*) which is
            standard for most Android devices but may not work on all device types.
        """

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
        actual_spacing = self.layout.spacing()
        if actual_spacing == -1:  # Default spacing
            actual_spacing = 6  # Qt default
        
        layout_margins = self.layout.contentsMargins()
        margin_height = layout_margins.top() + layout_margins.bottom()
        
        # Only 2 spacing gaps between 3 widgets
        total_spacing = actual_spacing * 2
        
        # Window title bar - be more precise
        title_bar_height = 28
        
        # Calculate total height
        total_height = (tree_widget_height + button_height + status_height + 
                       total_spacing + margin_height + title_bar_height)
        
        # Debug output to see exact calculations
        print(f"Fixed resize calculation:")
        print(f"  Row count: {row_count} (was using {row_count - 1})")
        print(f"  Header height: {header_height}")
        print(f"  Row height: {row_height} x {row_count} = {rows_height}")
        print(f"  Tree frame: {tree_frame}")
        print(f"  Tree widget total: {tree_widget_height}")
        print(f"  Button: {button_height}")
        print(f"  Status: {status_height}")
        print(f"  Spacing: {total_spacing} ({actual_spacing} x 2)")
        print(f"  Layout margins: {margin_height}")
        print(f"  Title bar: {title_bar_height}")
        print(f"  Total height: {total_height}")
        print(f"  Width calculation:")
        print(f"    Columns: {total_column_width}")
        print(f"    Frame: {frame_width}")
        print(f"    Scrollbar space: {scrollbar_width}")
        print(f"    Window margins: {window_margins}")
        print(f"    Total width: {total_width}")
        
        # Don't exceed screen size
        screen = QApplication.primaryScreen().geometry()
        max_width = int(screen.width() * 0.9)
        max_height = int(screen.height() * 0.9)
        
        final_width = min(total_width, max_width)
        final_height = min(total_height, max_height)
        
        print(f"  Final size: {final_width} x {final_height}")
        
        self.resize(final_width, final_height)

    def dump_partitions(self):
        """
        Dumps selected partitions from an Android device to image files.
        
        This method iterates through all top-level items in the list widget,
        identifies which partitions are checked/selected, and creates binary
        dumps of those partitions using ADB commands.
        
        The function performs the following operations:
        1. Ensures the output directory exists or creates it
        2. Retrieves all checked partitions from the list widget
        3. Validates that at least one partition is selected
        4. For each selected partition:
           - Updates status label to show current dumping progress
           - Constructs output filename as "{partition_name}.img"
           - Executes ADB command to dump partition data using dd
           - Marks partition as "Done" in the UI
        5. Updates final status when all dumps are complete
        
        The ADB command used reads from /dev/block/by-name/{partition} with
        4096-byte blocks and redirects output to a local .img file in the
        specified output directory.
        
        Returns:
            None
            
        Side Effects:
            - Creates .img files in the specified output directory
            - Updates UI status label and list widget items
            - Processes Qt events to maintain UI responsiveness
            
        Note:
            Requires ADB connection to Android device with appropriate
            permissions to read partition block devices.
        """
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
            self.status_label.setText(f"Dumping {part}...")
            QApplication.processEvents()
            dump_file = os.path.join(output_path, f"{part}.img")
            if dump_file:
                cmd = f'adb exec-out dd if=/dev/block/by-name/{part} bs=4096 status=none > "{dump_file}"'
                subprocess.run(cmd, shell=True)
                item.setText(2, "Done")
        self.status_label.setText(f"Status: Dump completed to {output_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PartitionDumper()
    window.show()
    sys.exit(app.exec())

