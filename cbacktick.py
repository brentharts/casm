#!/usr/bin/env python3
import os, sys, subprocess

if not os.path.isdir('holypycparser'):
	cmd = 'git clone --depth 1 https://github.com/brentharts/holypycparser.git'
	print(cmd)
	subprocess.check_call(cmd.split())


sys.path.append('./holypycparser')
import holyguacamole as guaca
print(guaca)

def decomp(o):
	objdump_output = subprocess.check_output(["riscv64-linux-gnu-objdump", "-d", o]).decode("utf-8")
	asm = []
	sects = {}
	info = {'sections':sects, 'asm':asm}
	sect  = None
	current_section = None
	for ln in objdump_output.splitlines():
		if '--verbose' in sys.argv: print(ln)
		if ln.startswith("Disassembly of section"):
			current_section = ln.split()[-1]
			sect = {}
			sects[current_section]=sect
			continue

		elif ln.strip().endswith(':'):  ## label
			asm.append(ln[ln.index(' '):])
			print(asm[-1])
		elif ':' in ln:
			if ln.startswith('./') and 'file format' in ln: continue
			if '--verbose' in sys.argv: asm.append('#'+ln)
			a = ln[ ln.index(':')+1 : ].strip().split()[1:]
			print(a)
			a = ' '.join(a)
			asm.append(a)

		if current_section:
			if ln.startswith('  ') and ':' in ln:
				ops = None
				if '<' in ln:
					ln, comment = ln.split('<')
				if '#' in ln:
					ln, comment2 = ln.split('#')

				if ln.count(':')==1:
					mem, ln = ln.split(':')

				a = ln.split()
				if len(a)==3:
					mem2, inst, ops = a
				elif len(a)==2: ## some inst have no ops, like ret,mret,nop..
					mem2, inst = a
				else:
					raise RuntimeError(len(a))
				#print(a)
				if ops:
					for b in ops.split(','):
						if b in guaca.REGS:
							if b not in sect: sect[b] = {'count':0,'asm':[]}
							sect[b]['count'] += 1
							sect[b]['asm'].append(ln)
						## only checking the first operand
						break

	return info


def print_regs(register_usage):
	for section, registers in register_usage.items():
		print(section)
		for reg in registers:
			if reg in guaca.reg_colors:
				print('\033[%sm' % guaca.reg_colors[reg], end='')
			elif reg.startswith('a'):
				if reg in guaca.A_COLORS:
					clr = '48;5;%s' % guaca.A_COLORS[reg]
				else:
					clr = '30;44'
				print('\033[%sm' % clr, end='')
			elif reg.startswith('s'):
				if reg in guaca.S_COLORS:
					clr = '48;5;%s' % guaca.S_COLORS[reg]
				else:
					clr = '30;43'
				print('\033[%sm' % clr, end='')
			print('	%s : %s' %(reg, registers[reg]['count']), end='')
			print('\033[0m')
			if registers[reg]['count'] <= 10:
				for asm in registers[reg]['asm']:
					print('		: %s' %(asm))

def asm2json(asm):
	bareasm = None
	out = {'labels':{}, 'data':[]}
	lab = None
	for idx, ln in enumerate(asm):
		a = guaca.parse_asm(ln, term_colors=False)
		if 'label' in a:
			lab = a['label']
			out['labels'][lab] = []
		elif 'data' in a:
			out['data'].append(a)
		else:
			if lab:
				out['labels'][lab].append(a)
			else:
				if bareasm is None:
					bareasm = lab = '__bareasm__'
					out['labels'][lab] = []
				out['labels'][lab].append(a)
	return out

## https://packages.fedoraproject.org/pkgs/cross-gcc/gcc-riscv64-linux-gnu/
#Only building kernels is currently supported.  Support for cross-building
#user space programs is not currently provided as that would massively multiply
#the number of packages.
TEST_C_FAILS = '''
#include <stdio.h>
int main(int argc, char **argv) {
	printf("hello kernel!\\n");
	return 0;
}
'''

TEST_C = '''
const char *ptr = "hello world!\\n";
void _start(int argc, char **argv) {
	__asm__(
		"addi  a0, x0, 1   # 1 = StdOut"
		"la    a1, ptr     # load address of helloworld"
		"addi  a2, x0, 13   # length of our string"
		"addi  a7, x0, 64   # linux write system call"
		"ecall              # Call linux to output the string"
	);
}
'''

def parse_linux_config(cfg):
	p = {}
	for ln in cfg.splitlines():
		if ln.startswith('#') or not ln.strip(): continue
		assert '=' in ln
		key   = ln[ : ln.index('=') ]
		value = ln[ ln.index('=')+1 : ]
		p[key] = value
	return p

def parse_linux_not_config(cfg):
	p = {}
	for ln in cfg.splitlines():
		if '--verbose' in sys.argv: print(ln)
		if not ln.startswith('#'): continue
		if not ln.endswith('is not set'): continue
		key = ln[1:].strip().split()[0]
		p[key] = False
	return p

def mklinux():
	## https://risc-v-getting-started-guide.readthedocs.io/en/latest/linux-qemu.html
	## https://github.com/riscv-collab/riscv-gnu-toolchain/issues/825
	## https://github.com/ayushbansal323/riscv64-sample
	if not os.path.isfile('/usr/bin/riscv64-linux-gnu-gcc'):
		if 'fedora' in os.uname().nodename:
			os.system('sudo dnf install gcc-riscv64-linux-gnu')
		else:
			os.system('sudo apt-get install gcc-riscv64-linux-gnu')
	if not os.path.isfile('/usr/bin/qemu-system-riscv64'):
		if 'fedora' in os.uname().nodename:
			os.system('sudo dnf install qemu-system-riscv-core')

	if not os.path.isdir('linux'):
		cmd = 'git clone --depth 1 https://github.com/torvalds/linux.git'.split()
		print(cmd)
		subprocess.check_call(cmd)

		if 'fedora' in os.uname().nodename:
			cmd = 'sudo dnf install gcc flex make bison openssl-devel elfutils-libelf-devel'
			print(cmd)
			subprocess.check_call(cmd.split())

	vmlinux = './linux/vmlinux'
	if not os.path.isfile(vmlinux) or '--rebuild' in sys.argv:
		cmd = 'make V=1 ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu- defconfig'.split()
		print(cmd)
		subprocess.check_call(cmd, cwd='./linux')
		cmd = 'make V=1 ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu-'.split()
		print(cmd)
		subprocess.check_call(cmd, cwd='./linux')

	subprocess.check_call(['ls', '-lh', './linux/vmlinux'])

	info = decomp( './linux/virt/kvm/kvm_main.o' )
	print_regs(info['sections'])
	guaca.print_asm( '\n'.join(info['asm']) )
	d = asm2json(info['asm'])

	kernel = './linux/arch/riscv/boot/Image'
	assert os.path.isfile(kernel)
	subprocess.check_call(['ls', '-lh', kernel])

	if not os.path.isdir('/tmp/root'):
		os.mkdir('/tmp/root')

	open('/tmp/init.c', 'w').write(TEST_C)
	cmd = [
		'riscv64-linux-gnu-gcc', 
		'/tmp/init.c', '-o', '/tmp/root/init', 
		'--static', '-ffreestanding', '-nostdlib',
	]
	print(cmd)
	subprocess.check_call(cmd)

	os.system('ldd /tmp/root/init')
	os.system('riscv64-linux-gnu-readelf -S /tmp/root/init')
	cmd = 'cd /tmp/root/ && find . | cpio --create --format=newc | gzip > /tmp/root.cpio.gz'
	print(cmd)
	os.system(cmd)

	cmd = [
		'qemu-system-riscv64',
		'-M', 'virt',
		'-m', 'size=1G',
		'-serial', 'stdio',
		'-device', 'VGA',
		'--no-reboot',
		'-kernel', kernel,
		'-initrd', '/tmp/root.cpio.gz',
		#'-append', 'panic=1 console=ttyS0',
	]
	print(cmd)
	try:
		subprocess.check_call(cmd)
	except:
		pass

	print('-'*80)
	cfg = parse_linux_config(open('./linux/.config').read())
	trace = {'VGA':[], 'RISCV':[], 'VIRT':[]}
	for n in cfg:
		print(n, '=', cfg[n])
		for k in trace:
			if k in n:
				trace[k].append('%s=%s' % (n,cfg[n]))
	for k in trace:
		print(k)
		for a in trace[k]:
			print('\t', a)

	print('-'*80)
	cfg = parse_linux_not_config(open('./linux/.config').read())
	trace = {'VGA':[], 'RISCV':[], 'VIRT':[], 'FB_SIMPLE':[]}
	for n in cfg:
		for k in trace:
			if k in n:
				trace[k].append('%s=%s' % (n,cfg[n]))
	for k in trace:
		print(k)
		for a in trace[k]:
			print('\t#', a)

def mkbsd():
	if not os.path.isdir('ghostbsd-src'):
		cmd = 'git clone --depth 1 https://github.com/ghostbsd/ghostbsd-src.git'.split()
		print(cmd)
		subprocess.check_call(cmd)

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

	if not c:
		print('no .c input files')
		if '--bsd' in sys.argv:
			mkbsd()
		else:
			mklinux()
