# gem5 on eceprog

You can now do the gem5 assignments on eceprog as well as qstruct. Follow
these steps once on eceprog. After that, every command in the assignments
works as written.

| Host | What changes |
|---|---|
| `qstruct.ecn.purdue.edu` | Nothing changes. Keep working as before. |
| `eceprog.ecn.purdue.edu` | Ubuntu 22.04. Rebuild gem5 and install one extra library bundle. |

## Setup steps

### 1. Get the eceprog update

Merge the `eceprog` branch of the course repository into your gem5
directory. Commit your own changes first.

```console
cd GEM5_ECE56500_FALL2026
git fetch origin
git merge origin/eceprog
```

### 2. Build gem5 on eceprog

A gem5 binary built on qstruct will not start on eceprog, so build it again
there.

- Use `scons`. eceprog has no `scons-3`.
- Skip the `/package/gcc/8.3.0` changes to `PATH` and `LD_LIBRARY_PATH`.
  The default compiler works.

```console
# only if you built build/ECE565-X86 on qstruct before
rm -rf build/ECE565-X86
scons USE_HDF5=0 -j 32 build/ECE565-X86/gem5.opt
# for part 3 and later
scons USE_HDF5=0 -j 32 build/ECE565-ARM/gem5.opt
```

Your home directory is shared between the two hosts. To keep a working
qstruct binary too, give the eceprog build its own name and use that path in
your commands:

```console
scons USE_HDF5=0 --default=ECE565-X86 -j 32 build/ECE565-X86-eceprog/gem5.opt
```

### 3. Install the glibc bundle

The SPEC benchmarks are dynamically linked, and eceprog's C library cannot
run them inside this gem5. This script downloads an older glibc, about 3 MB,
into `~/.local/gem5-glibc231`. gem5 uses it automatically from then on.

```console
util/ece565/setup_glibc231.sh
```

You only need to run it once. If you skip it, gem5 stops and tells you to
run it.

### 4. Run the assignments as written

Nothing else changes. For example:

```console
./build/ECE565-X86/gem5.opt configs/spec/spec_se.py -b sjeng --maxinsts=10000000
```

### 5. Compile your own programs with `-static`

When you compile an x86 program on eceprog to run in gem5, such as the
DAXPY program in part 2, link it statically.

```console
g++ -O2 -std=gnu++11 -static daxpy.cc -o daxpy
```

A dynamically linked program built on eceprog needs a newer glibc than gem5
can provide. It fails with ``version `GLIBC_2.34' not found``.

## If something fails

| Error you see | Cause | Fix |
|---|---|---|
| `libpython3.6m.so.1.0: cannot open shared object file` | The binary was built on qstruct. | Rebuild on eceprog, step 2. |
| `scons-3: command not found` | eceprog only has `scons`. | Use `scons`. |
| `fatal: This host has glibc 2.35, which cannot run dynamically linked x86 binaries` | The glibc bundle is not installed. | Run the setup script, step 3. |
| `CPU ISA level is lower than required` | Your gem5 tree does not have the eceprog update. | Merge the update, step 1. |
| `fatal: Syscall 334 out of range` | Your gem5 tree does not have the eceprog update. | Merge the update, step 1. |
| ``version `GLIBC_2.34' not found`` | Your program was linked dynamically on eceprog. | Recompile with `-static`, step 5. |
