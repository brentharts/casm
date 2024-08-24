#!/usr/bin/env python3
import os, sys, subprocess

if not os.path.isdir('holypycparser'):
	cmd = 'git clone --depth 1 https://github.com/brentharts/holypycparser.git'
	print(cmd)
	subprocess.check_call(cmd.split())


sys.path.append('./holypycparser')
import holyguacamole as guaca
print(guaca)

def mklinux():
	## https://risc-v-getting-started-guide.readthedocs.io/en/latest/linux-qemu.html
	if not os.path.isfile('/usr/bin/riscv64-linux-gnu-gcc'):
		os.system('sudo apt-get install gcc-riscv64-linux-gnu')

	if not os.path.isdir('linux'):
		cmd = 'git clone --depth 1 https://github.com/torvalds/linux.git'.split()
		print(cmd)
		subprocess.check_call(cmd)
	cmd = 'make V=1 ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- defconfig'.split()
	print(cmd)
	subprocess.check_call(cmd, cwd='./linux')
	cmd = 'make V=1 ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu-'.split()
	print(cmd)
	subprocess.check_call(cmd, cwd='./linux')


if __name__ == '__main__':
	out = None
	c = None
	includes = []
	defines  = []
	if '-o' in sys.argv:
		out = sys.argv[sys.argv.index('-o')+1]
	for arg in sys.argv:
		if arg.startswith('-I~/'): includes.append(os.path.expanduser(arg[2:]))
		elif arg.startswith('-I'): includes.append(arg)
		elif arg.startswith('-D'): defines.append(arg)

	for arg in sys.argv:
		if arg.endswith('.c'):
			c = arg
			if out: assert os.path.abspath(c) != os.path.abspath(out)
			s = guaca.c2asm( open(c).read(), {}, [], includes=includes, defines=defines )
			if out:
				print('saving:', out)
				open(out,'w').write(s)

	if '--linux' in sys.argv:
		mklinux()
	elif not c:
		print('no .c input files')