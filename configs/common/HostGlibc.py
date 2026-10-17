# ECE565 helper: per-host runtime compatibility for x86 SE-mode workloads.
#
# On qstruct (old host glibc) nothing special is needed and this module is a
# no-op. On hosts with glibc >= 2.33 (e.g. eceprog, Ubuntu 22.04 / glibc 2.35)
# dynamically linked x86 binaries cannot run under this gem5 (v22.0):
#   * the host libc.so.6 refuses to load on gem5's simulated CPU
#     ("CPU ISA level is lower than required"), and
#   * glibc >= 2.35 registers rseq (x86-64 syscall 334), which is not in
#     this gem5's syscall table ("Syscall 334 out of range").
# The fix is to run the simulated process against a bundled glibc 2.31
# (Ubuntu 20.04 libc6 package) via gem5's interpreter-directory hook plus
# LD_LIBRARY_PATH, and to disable rseq for statically linked binaries that
# were built on the new host.
#
# Install the bundled glibc once per user with:
#     util/ece565/setup_glibc231.sh
#
# Bundle search order: $GEM5_GLIBC_DIR, ~/.local/gem5-glibc231, then a shared
# course-wide copy. Explicit --interp-dir always wins. Entries from -e/--env
# are kept; the variables below are only added when the env file does not
# already set them.

import os
import struct

from m5.core import setInterpDir
from m5.defines import buildEnv
from m5.util import fatal

GLIBC_CANDIDATES = [
    os.environ.get('GEM5_GLIBC_DIR', ''),
    os.path.expanduser('~/.local/gem5-glibc231'),
    '/home/min/a/ece565/gem5-glibc231',
]
LOADER = os.path.join('lib64', 'ld-linux-x86-64.so.2')
LIBDIR = os.path.join('lib', 'x86_64-linux-gnu')

_interp_dir_set = False


def gcc_lib_dir():
    """Per-user mirror of /package/gcc/8.3.0/lib64 plus libgfortran.so.3.

    /package/gcc/8.3.0/lib64 is read-only and lacks libgfortran.so.3 (needed
    by leslie3d), so mirror it into a writable directory the loader can use.
    """
    libdir = os.path.expanduser('~/.local/gem5-libs64')
    os.makedirs(libdir, exist_ok=True)
    src_dir = '/package/gcc/8.3.0/lib64'
    if os.path.isdir(src_dir):
        for name in os.listdir(src_dir):
            link = os.path.join(libdir, name)
            if not os.path.lexists(link):
                try:
                    os.symlink(os.path.join(src_dir, name), link)
                except OSError:
                    pass
    gfortran3 = os.path.join(libdir, 'libgfortran.so.3')
    if not os.path.lexists(gfortran3):
        try:
            os.symlink('/package/gcc/4.9.4/lib64/libgfortran.so.3', gfortran3)
        except OSError:
            pass
    return libdir


def host_glibc_version():
    try:
        ver = os.confstr('CS_GNU_LIBC_VERSION').split()[1]
        return tuple(int(x) for x in ver.split('.')[:2])
    except Exception:
        return (0, 0)


def host_needs_bundle():
    return buildEnv['TARGET_ISA'] == 'x86' and host_glibc_version() >= (2, 33)


def find_bundle():
    for d in GLIBC_CANDIDATES:
        if d and os.path.isfile(os.path.join(d, LOADER)) and \
                os.path.isfile(os.path.join(d, LIBDIR, 'libc.so.6')):
            return d
    return None


def _elf_info(path):
    """Return (is_dynamic, needs_rseq_tunable) for an ELF64 executable."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError:
        return (False, False)
    if data[:4] != b'\x7fELF' or data[4] != 2:
        return (False, False)
    phoff = struct.unpack_from('<Q', data, 0x20)[0]
    phentsize, phnum = struct.unpack_from('<HH', data, 0x36)
    PT_INTERP = 3
    is_dynamic = any(
        struct.unpack_from('<I', data, phoff + i * phentsize)[0] == PT_INTERP
        for i in range(phnum))
    # A statically linked binary built against glibc >= 2.35 embeds the
    # tunable name and will issue the rseq syscall unless it is disabled.
    needs_rseq = not is_dynamic and b'glibc.pthread.rseq' in data
    return (is_dynamic, needs_rseq)


def _check_visible(path, what):
    # config_filesystem() redirects the simulated program's /tmp (and /proc,
    # /sys) to the output directory, so libraries there are invisible to it.
    real = os.path.realpath(path)
    for hidden in ('/tmp', '/proc', '/sys'):
        if real == hidden or real.startswith(hidden + '/'):
            fatal("The %s at %s is under %s, which gem5 hides from the "
                  "simulated program. Install it under your home directory "
                  "instead." % (what, path, hidden))


def _add_env(env, key, value):
    if not any(e.split('=', 1)[0] == key for e in env):
        env.append('%s=%s' % (key, value))


def apply(process, args):
    """Set interpreter dir and environment for a Process. Call once per
    process, after its executable has been set. The environment is left
    untouched unless the binary needs help, so e.g. the stock static 'hello'
    is simulated identically on every host."""
    global _interp_dir_set
    env = []
    if getattr(args, 'env', None):
        with open(args.env, 'r') as f:
            env = [line.rstrip() for line in f if line.strip()]

    is_dynamic, needs_rseq = _elf_info(process.executable)
    interp_dir = getattr(args, 'interp_dir', None)

    if is_dynamic and host_needs_bundle() and not interp_dir:
        bundle = find_bundle()
        if bundle is None:
            fatal("This host has glibc %d.%d, which cannot run dynamically "
                  "linked x86 binaries under this gem5.\n"
                  "Install the bundled glibc 2.31 once by running:\n"
                  "    util/ece565/setup_glibc231.sh\n"
                  "from your gem5 directory, then rerun this command."
                  % host_glibc_version())
        interp_dir = bundle
        gcc_dir = gcc_lib_dir()
        _check_visible(bundle, 'glibc bundle')
        _check_visible(gcc_dir, 'gcc library mirror')
        _add_env(env, 'LD_LIBRARY_PATH',
                 os.path.join(bundle, LIBDIR) + ':' + gcc_dir)
    elif needs_rseq:
        _add_env(env, 'GLIBC_TUNABLES', 'glibc.pthread.rseq=0')

    if interp_dir and not _interp_dir_set:
        setInterpDir(interp_dir)
        _interp_dir_set = True
    if env:
        process.env = env
