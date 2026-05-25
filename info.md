# APC UPS NMC

Local-first Home Assistant integration for APC by Schneider Electric UPS units
with Network Management Cards.

The integration uses SNMP polling as the source of truth for UPS telemetry and
can optionally listen for local syslog events from one or more NMC cards. Current
support is developed and tested against NMC3 hardware while the project leaves
room for additional Schneider Electric/APC Network Management Card generations.

## Highlights

- SNMPv2c and SNMPv3 setup through the Home Assistant UI.
- UPS identity, battery, input, output, load, self-test, alarm, replacement, and
  energy telemetry.
- Home Assistant Energy dashboard-friendly output energy and power metadata.
- Optional shared UDP syslog listener for local push events.
- Multiple UPS/NMC cards as distinct Home Assistant devices.
- Reconfigure flow for host, port, SNMP version, and credentials.
- Device registry metadata, including serial, firmware, web configuration URL,
  and NMC MAC address when exposed.
- Redacted diagnostics and Repair issues for syslog listener problems.

See the [project README](https://github.com/nugget/schneider-ups-nmc#readme) for
installation, configuration, and operating notes.
