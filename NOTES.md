# Development notes

## Multiple devices

Currently the daemon opens the first device returned by `easyhid.Enumeration.find()` and ignores any others. To support two connected mice, the daemon would need to accept a specific hidraw device path as an argument (e.g. `spacenavlcdd --device /dev/hidraw0`), and the udev rule would start a separate instance per device, passing the path via `%E{DEVNAME}`.
