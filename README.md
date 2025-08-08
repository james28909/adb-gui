# ADB Partition Dumper GUI

A Qt-based graphical user interface for dumping Android device partitions via ADB (Android Debug Bridge). This tool provides an intuitive way to extract partition data from Android devices for backup, analysis, or forensic purposes.

## 🚀 Features

- **Automatic Partition Discovery**: Automatically detects and lists all available partitions on connected Android devices
- **Visual Partition Management**: Tree widget display showing partition names, sizes, and dump status
- **Selective Dumping**: Choose specific partitions to dump using checkboxes
- **Flexible Output Directory**: 
  - Configurable output directory with default `./dumped`
  - Support for various path formats (relative, absolute, `~`, `$HOME`)
  - GUI folder picker for easy directory selection
  - Automatic directory creation if it doesn't exist
- **Real-time Progress**: Live status updates during dumping operations
- **Size Information**: Displays partition sizes in human-readable format (GB/MB/KB) with exact byte counts
- **Safe Operation**: Creates timestamped backups and validates operations

## 📋 Requirements

### System Requirements
- **ADB (Android Debug Bridge)**: Must be installed and accessible in system PATH
- **Python 3.6+**: Required for running the application
- **PyQt5**: GUI framework dependency

### Device Requirements
- Android device with **USB Debugging enabled**
- Appropriate **device permissions** for partition access
- Device connected via USB cable

### Python Dependencies
```
PyQt5>=5.15.0
```

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/james28909/adb-gui.git
   cd adb-gui
   ```

2. **Install Python dependencies:**
   ```bash
   # (Optional) Activate your virtual environment if you are using one:
   source .venv/bin/activate
   # Replace '.venv/bin/activate' with your venv path if different
   pip install -r requirements.txt
   ```

3. **Ensure ADB is installed:**
   - **Windows**: Download from [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools)
   - **macOS**: `brew install android-platform-tools`
   - **Linux**: `sudo apt install android-tools-adb` (Ubuntu/Debian) or equivalent

4. **Verify ADB installation:**
   ```bash
   adb version
   ```

## 🚀 Usage

### Quick Start

1. **Enable USB Debugging on your Android device:**
   - Go to Settings → About Phone
   - Tap "Build Number" 7 times to enable Developer Options
   - Go to Settings → Developer Options
   - Enable "USB Debugging"

2. **Connect your device via USB**

3. **Authorize the connection** (accept the popup on your device)

4. **Run the application:**
   ```bash
   python gui.py
   ```

### Using the Interface

1. **Launch the application** - partitions will be automatically loaded
2. **Configure output directory:**
   - Use the default `./dumped` directory, or
   - Type a custom path in the input field, or
   - Click "Browse..." to select a folder
3. **Select partitions** to dump using the checkboxes
4. **Click "Dump Selected Partitions"** to begin extraction
5. **Monitor progress** in the status label

### Supported Path Formats

The output directory field supports various path formats:
- **Relative paths**: `./backups`, `data/dumps`
- **Home directory**: `~/android-backups`
- **Environment variables**: `$HOME/backups`, `${USER}/dumps`
- **Absolute paths**: `/home/user/android-dumps`

## 📁 Output

- **File format**: Binary partition dumps saved as `.img` files
- **Naming convention**: `{partition_name}.img`
- **Location**: Specified output directory (default: `./dumped`)
- **Directory creation**: Automatically creates output directory if it doesn't exist

Example output:
```
./dumped/
├── boot.img
├── system.img
├── recovery.img
└── userdata.img
```

## 🔧 Technical Details

### Device Compatibility
- **Designed for**: MMC-based Android devices (mmcblk0 naming convention)
- **Partition detection**: Uses `/sys/block/mmcblk0/` interface
- **Block device access**: Reads from `/dev/block/by-name/` paths

### Partition Information Extraction
The tool executes the following ADB shell command to gather partition data:
```bash
for part in /sys/block/mmcblk0/mmcblk0p*; do 
    name=$(grep ^PARTNAME= "$part/uevent" 2>/dev/null | cut -d= -f2)
    size=$(cat "$part/size" 2>/dev/null)
    if [ -n "$size" ]; then
        echo "$(basename "$part")|${name:-unknown}|$size"
    fi
done
```

### Dumping Process
Partitions are dumped using:
```bash
adb exec-out dd if=/dev/block/by-name/{partition} bs=4096 status=none > "{output_file}"
```

## ⚠️ Important Notes

- **Root access**: Some partitions may require root access on the device
- **Device storage**: Ensure sufficient free space for partition dumps
- **Backup safety**: Tool creates automatic backups before modifications
- **Device compatibility**: May not work with all Android device types or storage configurations
- **Data sensitivity**: Partition dumps may contain sensitive data - handle securely

## 🐛 Troubleshooting

### Common Issues

**"Failed to load partitions"**
- Ensure device is connected and ADB is working: `adb devices`
- Check USB debugging is enabled
- Try authorizing the connection again

**"No partitions selected"**
- Select at least one partition using the checkboxes before dumping

**"Error creating directory"**
- Check write permissions for the specified output path
- Ensure the parent directory exists

**Empty partition list**
- Device may not use MMC storage (mmcblk0)
- Try different ADB commands for your specific device type

### Verification Commands
```bash
# Check ADB connection
adb devices

# List device partitions manually
adb shell ls -la /dev/block/by-name/

# Check available storage
adb shell df -h
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is open source. Please use responsibly and in accordance with applicable laws and regulations.

## ⚖️ Legal Disclaimer

This tool is intended for legitimate purposes such as:
- Personal device backups
- Security research (with proper authorization)
- Educational purposes
- Forensic analysis (with appropriate legal authority)

Users are responsible for ensuring their use complies with applicable laws and regulations. The authors are not responsible for any misuse of this software.

## 🔗 Related Projects

- [Android Platform Tools](https://developer.android.com/studio/releases/platform-tools)
- [PyQt5 Documentation](https://doc.qt.io/qtforpython/)
- [ADB Documentation](https://developer.android.com/studio/command-line/adb)

---

**Made with ❤️ for the Android development and security research community**
