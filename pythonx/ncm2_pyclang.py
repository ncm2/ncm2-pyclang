from ncm2 import getLogger
from os.path import dirname, join, isfile, normpath, expanduser, expandvars, basename, splitext
from pathlib import Path
import shlex
import json

logger = getLogger(__name__)


def _extract_args_from_cmake(filepath, cmd):
    args = None
    if 'command' in cmd:
        return pick_useful_args_from_cmd(filepath, cmd['command'])
    elif 'arguments' in cmd:
        return pick_useful_args_from_cmd(filepath, cmd['arguments'])
    else:
        return None

def args_from_cmake(filepath, cwd, database_paths):
    filedir = dirname(filepath)

    cfg_path, _ = find_config([filedir, cwd], database_paths)

    if not cfg_path:
        return None, None

    filepath = normpath(filepath)

    try:
        with open(cfg_path, "r") as f:
            commands = json.load(f)

            for cmd in commands:
                try:
                    cmd_for = join(cmd['directory'], cmd['file'])
                    if normpath(cmd_for) == filepath:
                        logger.info("compile_commands: %s", cmd)
                        args = _extract_args_from_cmake(filepath, cmd)
                        return args, cmd['directory']
                except Exception as ex:
                    logger.exception("Exception processing %s", cmd)

            logger.error("Failed finding args from %s for %s", cfg_path, filepath)

            # Merge all include dirs and the flags of the last item as a
            # fallback. This is useful for editting header file.
            all_dirs = {}
            for cmd in commands:
                args = _extract_args_from_cmake(filepath, cmd)
                add_next = False
                for arg in args:
                    if add_next:
                        add_next = False
                        all_dirs['-I' + arg] = True
                    if arg == "-I":
                        add_next = True
                        continue
                    if arg.startswith("-I"):
                        all_dirs['-I' + arg[2:]] = True

            return list(all_dirs.keys()) + args, filedir

    except Exception as ex:
        logger.exception("read compile_commands.json [%s] failed.", cfg_path)

    return None, None


def args_from_clang_complete(filepath, cwd, args_file_path):
    filedir = dirname(filepath)

    clang_complete, directory = find_config([filedir, cwd], args_file_path)

    if not clang_complete:
        return None, None

    try:
        with open(clang_complete, "r") as f:
            cmd = shlex.split(" ".join(f.readlines()))

            cmd = [expanduser(expandvars(p)) for p in cmd]

            args = pick_useful_args_from_cmd(filepath, cmd)

            logger.info('.clang_complete args: [%s] cmd[%s]', args, cmd)
            return args, directory
    except Exception as ex:
        logger.exception('read config file %s failed.', clang_complete)

    return None, None

# linux kernel build init/main.o -> init/.main.o.cmd:
#
#   cmd_init/main.o := /usr/bin/ccache aarch64-linux-gnu-gcc -Wp,-MD,init/.main.o.d  -nostdinc -isystem /usr/lib/gcc-cross/aarch64-linux-gnu/7/include -I./arch/arm64/include -I./arch/arm64/include/generated  -I./include -I./arch/arm64/include/uapi -I./arch/arm64/include/generated/uapi -I./include/uapi -I./include/generated/uapi -include ./include/linux/kconfig.h -include ./include/linux/compiler_types.h -D__KERNEL__ -mlittle-endian -DKASAN_SHADOW_SCALE_SHIFT=3 -Wall -Wundef -Werror=strict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar -fno-PIE -Werror=implicit-function-declaration -Werror=implicit-int -Wno-format-security -std=gnu89 -mgeneral-regs-only -DCONFIG_AS_LSE=1 -fno-asynchronous-unwind-tables -mabi=lp64 -DKASAN_SHADOW_SCALE_SHIFT=3 -fno-delete-null-pointer-checks -Wno-frame-address -Wno-format-truncation -Wno-format-overflow -Wno-int-in-bool-context -Os -Wno-maybe-uninitialized --param=allow-store-data-races=0 -Wframe-larger-than=2048 -fstack-protector-strong -Wno-unused-but-set-variable -Wno-unused-const-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -fno-var-tracking-assignments -g -pg -Wdeclaration-after-statement -Wvla -Wno-pointer-sign -fno-strict-overflow -fno-merge-all-constants -fmerge-constants -fno-stack-check -fconserve-stack -Werror=date-time -Werror=incompatible-pointer-types -Werror=designated-init -fno-function-sections -fno-data-sections    -DKBUILD_BASENAME='"main"' -DKBUILD_MODNAME='"main"' -c -o init/main.o init/main.c
def args_from_kbuild(filepath, cwd):
    filedir = dirname(filepath)
    filename = basename(filepath)
    nameroot, ext = splitext(filename)

    dot_cmd = join(filedir, '.' + nameroot + '.o.cmd')

    if not isfile(dot_cmd):
        logger.debug('args_from_kbuild dot_cmd not found: %s', dot_cmd)
        return None, None

    with open(dot_cmd) as dot_f:
        while True:
            line = dot_f.readline()
            if line is None:
                break

            if not line.startswith('cmd_'):
                continue

            idx = line.find(':=')
            if idx == -1:
                continue

            args = pick_useful_args_from_cmd(filepath, line[idx + 2:])

            # cmd_init/main.o
            obj = line[len('cmd_') : idx].strip()
            objdir = dirname(obj)
            if filedir.endswith(objdir):
                directory = filedir[0: len(filedir) - len(objdir)]
                logger.debug('args_from_kbuild [%s] found, args: %s, dir: %s', dot_cmd, args, directory)
            else:
                directory = cwd
                logger.debug('args_from_kbuild [%s] found, args: %s, cwd dir: %s, objdir: %s', dot_cmd, args, directory, objdir)
            
            return args, directory

    logger.debug('args_from_kbuild dot_cmd found, but no result: %s', dot_cmd)

    return None, None

# FIXME this is not an exact argument parsing implementation, but it is the
# easiest implementation for now
def pick_useful_args_from_cmd(filepath, cmd):

    if type(cmd) is str:
        cmd = shlex.split(cmd)

    if cmd and cmd[0][:1] != '-':
        args = cmd[1:]
    else:
        args = cmd

    # filter for ccache
    while args and not args[0].startswith("-"):
        args = args[1:]

    # filter-out un recognized options

    # filename = basename(filepath)
    # args = list(filter(lambda e: basename(e) != filename, args))

    tmp = args
    args = []
    next_ok = False
    inc_opts = ['-I', '-isystem', '-internal-isystem', '-internal-externc-isystem']
    def_opts = ['-D']
    extra_opts_with_arg = ['-std', '-include']
    opts_with_arg = inc_opts + def_opts + extra_opts_with_arg
    opts_without_arg = ['-nostdinc']
    for arg in tmp:
        if not next_ok:

            if arg in opts_without_arg:
                args.append(arg)
                continue

            if arg in opts_with_arg:
                next_ok = True
                args.append(arg)
                continue

            for opt in opts_with_arg:
                if arg.startswith(opt):
                    args.append(arg)
                    break

            continue
        args.append(arg)
        next_ok = False

    # We don't need completion / goto to crash for any errors
    args += ['-ferror-limit=99999999']

    logger.debug('args: %s <= cmd: %s', args, cmd)
    return args


def find_config(bases, names):
    if isinstance(names, str):
        names = [names]

    if isinstance(bases, str):
        bases = [bases]

    for base in bases:
        r = Path(base).resolve()
        dirs = [r] + list(r.parents)
        for d in dirs:
            d = str(d)
            for name in names:
                p = join(d, name)
                if isfile(p):
                    return p, d

    return None, None
