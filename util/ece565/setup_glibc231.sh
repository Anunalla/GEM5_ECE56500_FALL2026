#!/usr/bin/env bash
# ECE565: install the glibc 2.31 bundle that gem5 uses to run dynamically
# linked x86 binaries (e.g. the SPEC benchmarks) on hosts with a newer glibc,
# such as eceprog. Run once per user; safe to rerun. Not needed on qstruct.
#
# Usage: util/ece565/setup_glibc231.sh [install-dir]
#        (default install-dir: ~/.local/gem5-glibc231)
set -euo pipefail

DEST="${1:-$HOME/.local/gem5-glibc231}"
DEB=libc6_2.31-0ubuntu9_amd64.deb
SHA256=847a68e5f1ec2cd4e6fc191c5eaf0547445dd5c473c7617c068ba4441f63b292
URLS=(
  "http://archive.ubuntu.com/ubuntu/pool/main/g/glibc/$DEB"
  "https://launchpad.net/ubuntu/+archive/primary/+files/$DEB"
)

if [ -f "$DEST/lib64/ld-linux-x86-64.so.2" ] && \
   [ -f "$DEST/lib/x86_64-linux-gnu/libc.so.6" ]; then
  echo "glibc 2.31 bundle already installed in $DEST"
  exit 0
fi

# Only ever replace an empty directory or a previous (partial) bundle.
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ] && \
   [ ! -d "$DEST/lib/x86_64-linux-gnu" ]; then
  echo "ERROR: $DEST exists and is not a glibc bundle; pick another dir" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok=0
for url in "${URLS[@]}"; do
  echo "Downloading $url"
  if curl -fsSL -o "$TMP/$DEB" "$url" && \
     echo "$SHA256  $TMP/$DEB" | sha256sum -c --status; then
    ok=1; break
  fi
  echo "  download failed or checksum mismatch, trying next mirror"
done
[ "$ok" = 1 ] || { echo "ERROR: could not download $DEB" >&2; exit 1; }

mkdir -p "$TMP/root"
if command -v dpkg-deb >/dev/null 2>&1; then
  dpkg-deb -x "$TMP/$DEB" "$TMP/root"
else
  (cd "$TMP" && ar x "$DEB" && tar -xf data.tar.* -C root)
fi

# The package's loader symlink is absolute (/lib/x86_64-linux-gnu/...),
# which would point at the host's loader; make it relative to the bundle.
ln -sfn ../lib/x86_64-linux-gnu/ld-2.31.so \
  "$TMP/root/lib64/ld-linux-x86-64.so.2"

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST.tmp.$$"
mv "$TMP/root" "$DEST.tmp.$$"
chmod -R a+rX "$DEST.tmp.$$"
rm -rf "$DEST"
mv "$DEST.tmp.$$" "$DEST"
echo "Installed glibc 2.31 bundle in $DEST"
