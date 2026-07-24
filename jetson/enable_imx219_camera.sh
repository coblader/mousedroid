#!/usr/bin/env bash
#
# Enable the Arducam IMX219 CSI camera on the Jetson Orin Nano Dev Kit
# by adding the required FDT (base DTB) line to extlinux.conf so the
# bootloader actually applies the camera device-tree overlay.
#
# Safe / idempotent: backs up extlinux.conf, only adds lines if missing.
# Does NOT reboot automatically — it prints the result for you to review.

set -euo pipefail

EXTLINUX=/boot/extlinux/extlinux.conf
FDT_DTB=/boot/tegra234-p3768-0000+p3767-0005-nv.dtb
OVERLAY=/boot/tegra234-p3767-camera-p3768-imx219-dual.dtbo

if [[ $EUID -ne 0 ]]; then
    echo ">> Re-running with sudo (enter your password if prompted)..."
    exec sudo bash "$0" "$@"
fi

echo ">> Sanity checks..."
[[ -f "$FDT_DTB" ]] || { echo "ERROR: base DTB not found: $FDT_DTB"; exit 1; }
[[ -f "$OVERLAY" ]] || { echo "ERROR: overlay not found: $OVERLAY"; exit 1; }

# Back up once (don't clobber an existing backup)
if [[ ! -f "${EXTLINUX}.bak" ]]; then
    cp "$EXTLINUX" "${EXTLINUX}.bak"
    echo ">> Backed up $EXTLINUX -> ${EXTLINUX}.bak"
else
    echo ">> Backup already exists at ${EXTLINUX}.bak (leaving it)"
fi

# Add the OVERLAYS line if it is somehow missing
if ! grep -qE "^[[:space:]]*OVERLAYS .*imx219-dual" "$EXTLINUX"; then
    sed -i "/^[[:space:]]*APPEND /a\\      OVERLAYS $OVERLAY" "$EXTLINUX"
    echo ">> Added OVERLAYS line."
else
    echo ">> OVERLAYS line already present."
fi

# Add the FDT line if missing (this is the piece that was missing before)
if ! grep -qE "^[[:space:]]*FDT " "$EXTLINUX"; then
    sed -i "/^[[:space:]]*INITRD \/boot\/initrd/a\\      FDT $FDT_DTB" "$EXTLINUX"
    echo ">> Added FDT line."
else
    echo ">> FDT line already present."
fi

echo
echo ">> Resulting 'primary' boot entry:"
echo "------------------------------------------------------------"
sed -n '/^LABEL primary/,/^[[:space:]]*$/p' "$EXTLINUX"
echo "------------------------------------------------------------"
echo
echo ">> If the block above shows LINUX / FDT / INITRD / APPEND / OVERLAYS,"
echo ">> reboot to load the camera:   sudo reboot"
echo ">> To undo:  sudo cp ${EXTLINUX}.bak $EXTLINUX"
