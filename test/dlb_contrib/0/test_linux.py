# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb_contrib.linux
import sys
import os.path
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class KernelInfoTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_is_correct_for_typical(self):
        os.makedirs(os.path.join('sys', 'kernel'))
        with open(os.path.join('sys', 'kernel', 'ostype'), 'xb') as f:
            f.write(b'Linux\n')
        with open(os.path.join('sys', 'kernel', 'osrelease'), 'xb') as f:
            f.write(b'4.19.0-9-amd64\n')
        with open(os.path.join('sys', 'kernel', 'version'), 'xb') as f:
            f.write(b'#1 SMP Debian 4.19.118-2 (2020-04-29)\n')

        info = dlb_contrib.linux.get_kernel_info(proc_root_directory='.')
        self.assertEqual(('Linux', '4.19.0-9-amd64', '#1 SMP Debian 4.19.118-2 (2020-04-29)'), info)

    def test_fails_if_too_long(self):
        os.makedirs(os.path.join('sys', 'kernel'))
        with open(os.path.join('sys', 'kernel', 'ostype'), 'xb') as f:
            f.write(b'Linux\n')
        with open(os.path.join('sys', 'kernel', 'osrelease'), 'xb') as f:
            f.write(b'4.19.0-9-amd64\n')
        with open(os.path.join('sys', 'kernel', 'version'), 'xb') as f:
            version = b'#1 SMP Debian 4.19.118-2 (2020-04-29)'
            f.write(version + b'\n')

        info = dlb_contrib.linux.get_kernel_info(proc_root_directory='.', max_size=len(version))
        self.assertEqual(('Linux', '4.19.0-9-amd64', '#1 SMP Debian 4.19.118-2 (2020-04-29)'), info)

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.linux.get_kernel_info(proc_root_directory='.', max_size=len(version) - 1)
        self.assertEqual("does not end with '\\n' (too large?): 'sys/kernel/version'", str(cm.exception))

    @unittest.skipIf(sys.platform != 'linux', 'Linux only')
    def test_can_query_running_kernel(self):
        dlb_contrib.linux.get_kernel_info()


class MemoryInfoTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_is_correct_for_typical(self):
        with open('meminfo', 'xb') as f:
            f.write(
                b'MemTotal:       16303360 kB\n'
                b'MemFree:         1085972 kB\n'
                b'MemAvailable:   12711600 kB\n'
                b'Buffers:            1440 kB\n'
                b'Cached:         12167780 kB\n'
                b'SwapCached:          264 kB\n'
                b'Active:          3855816 kB\n'
            )

        info = dlb_contrib.linux.get_memory_info(proc_root_directory='.')
        self.assertEqual((16303360 * 2**10, 12711600 * 2**10), info)

    def test_fails_for_unexpected_line(self):
        with open('meminfo', 'xb') as f:
            f.write(
                b'MemTotal:       16303360 kB\n'
                b'MemFree:         1085972 kB\n'
                b'MemAvailable    12711600 kB\n'
            )

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.linux.get_memory_info(proc_root_directory='.')
        self.assertEqual("unexpected key-value line: b'MemAvailable    12711600 kB\\n'", str(cm.exception))

    def test_fails_for_unexpected_unit(self):
        with open('meminfo', 'xb') as f:
            f.write(
                b'MemTotal:       16303360 MB\n'
                b'MemFree:            1085 kB\n'
                b'MemAvailable:   12711600 kB\n'
            )

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.linux.get_memory_info(proc_root_directory='.')
        self.assertEqual("'MemTotal' in 'meminfo' has unexpected value: '16303360 MB'", str(cm.exception))

    def test_fails_for_missing_key(self):
        with open('meminfo', 'xb') as f:
            f.write(
                b'MemTotal:       16303360 kB\n'
                b'MemFree:         1085972 kB\n'
            )

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.linux.get_memory_info(proc_root_directory='.')
        self.assertEqual("missing key in 'meminfo': 'MemAvailable'", str(cm.exception))

    @unittest.skipIf(sys.platform != 'linux', 'Linux only')
    def test_can_query_running_kernel(self):
        dlb_contrib.linux.get_memory_info()


@unittest.skipIf(sys.platform != 'linux', 'Linux only')  # involves native absolute paths
class MountedFilesystemsTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_is_correct_for_typical(self):
        os.mkdir('self')
        with open(os.path.join('self', 'mounts'), 'xb') as f:
            f.write(
                b'udev /dev devtmpfs rw,nosuid,relatime,size=8127516k,nr_inodes=2031879,mode=755 0 0\n'
                b'/dev/mapper/g-root / xfs rw,relatime,attr2,inode64,noquota 0 0\n'
                b'systemd-1 /proc/sys/fs/binfmt_misc autofs rw,relatime,fd=35,pgrp=1,timeout=0,minproto=5,'
                b'maxproto=5,direct,pipe_ino=13711 0 0\n'
                
                b'/dev/nvme0n1p2 /boot/efi vfat rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,'
                b'shortname=mixed,utf8,errors=remount-ro 0 0\n'
                
                b'none /tmp/t/test\\012m\\011ou\rnt tmpfs rw,relatime 0 0\n'
                b'binfmt_misc /proc/sys/fs/binfmt_misc binfmt_misc rw,relatime 0 0\n'
            )

        vfstype_name_by_mountpoint = dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.')
        self.assertEqual({
                dlb.fs.Path('/dev/'): 'devtmpfs',
                dlb.fs.Path('/'): 'xfs',
                dlb.fs.Path('/proc/sys/fs/binfmt_misc/'): 'autofs',
                dlb.fs.Path('/boot/efi/'): 'vfat',
                dlb.fs.Path('/tmp/t/test\012m\011ou\rnt/'): 'tmpfs',
                dlb.fs.Path('/proc/sys/fs/binfmt_misc/'): 'binfmt_misc'
            },
            vfstype_name_by_mountpoint
        )

        vfstype_name_by_mountpoint = dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.', contained_paths=[])
        self.assertEqual({}, vfstype_name_by_mountpoint)

        vfstype_name_by_mountpoint = dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.', contained_paths=[
            '/tmp/t/test\012m\011ou\rnt/x/y',
            '/.//boot/efi',
            '/dev/../boot/efi/'
        ])
        self.assertEqual({
            dlb.fs.Path('/tmp/t/test\012m\011ou\rnt/'): 'tmpfs',
            dlb.fs.Path('/boot/efi/'): 'vfat',
            dlb.fs.Path('/dev/'): 'devtmpfs'
        }, vfstype_name_by_mountpoint)

    def test_is_correct_for_oci_excerpt(self):
        os.mkdir('self')
        with open(os.path.join('self', 'mounts'), 'xb') as f:
            f.write(
                b'/dev/mapper/g-home / xfs rw,nosuid,nodev,relatime,attr2,inode64,logbufs=8,logbsize=32k,noquota 0 0\n'
                b'proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0\n'
                b'tmpfs /dev tmpfs rw,nosuid,size=65536k,mode=755,uid=1000,gid=1000 0 0\n'
                b'sysfs /sys sysfs ro,nosuid,nodev,noexec,relatime 0 0\n'
                b'mqueue /dev/mqueue mqueue rw,nosuid,nodev,noexec,relatime 0 0\n'
                b'tmpfs /etc/resolv.conf tmpfs rw,nosuid,nodev,relatime,size=1626876k,nr_inodes=406719,mode=700,uid=1000,gid=1000 0 0\n'
                b'cgroup2 /sys/fs/cgroup cgroup2 ro,nosuid,nodev,noexec,relatime,nsdelegate,memory_recursiveprot 0 0\n'
                b'udev /dev/null devtmpfs rw,nosuid,relatime,size=8105068k,nr_inodes=2026267,mode=755 0 0\n'
                b'devpts /dev/console devpts rw,nosuid,noexec,relatime,gid=100004,mode=620,ptmxmode=666 0 0\n'
            )

        vfstype_name_by_mountpoint = dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.')
        self.assertEqual({
                dlb.fs.Path('/'): 'xfs',
                dlb.fs.Path('/proc/'): 'proc',
                dlb.fs.Path('/dev/'): 'tmpfs',
                dlb.fs.Path('/sys/'): 'sysfs',
                dlb.fs.Path('/dev/mqueue/'): 'mqueue',
                dlb.fs.Path('/etc/resolv.conf/'): 'tmpfs',  # note: is actually a regular file
                dlb.fs.Path('/sys/fs/cgroup/'): 'cgroup2',
                dlb.fs.Path('/dev/null/'): 'devtmpfs',
                dlb.fs.Path('/dev/console/'): 'devpts',
            },
            vfstype_name_by_mountpoint
        )

    def test_fails_for_corrupt_line(self):
        os.mkdir('self')
        with open(os.path.join('self', 'mounts'), 'xb') as f:
            f.write(
                b'mount tmpfs rw,relatime 0 0\n'
            )

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.')
        self.assertEqual("unexpected line in 'self/mounts': b'mount tmpfs rw,relatime 0 0\\n'", str(cm.exception))

    def test_succeeds_if_mountpoint_does_not_exist(self):
        self.assertFalse(os.path.exists('/tmp/this/does/not/exist'))

        os.mkdir('self')
        with open(os.path.join('self', 'mounts'), 'xb') as f:
            f.write(b'none /tmp/this/does/not/exist tmpfs rw,relatime 0 0\n')

        vfstype_name_by_mountpoint = dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.')
        self.assertEqual({dlb.fs.Path('/tmp/this/does/not/exist/'): 'tmpfs'}, vfstype_name_by_mountpoint)

    def test_fails_for_relative_contained_paths(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.linux.get_mounted_filesystems(proc_root_directory='.', contained_paths=['x/y'])
        self.assertEqual("invalid path for 'AbsolutePath': 'x/y' (must be absolute)", str(cm.exception))

    @unittest.skipIf(sys.platform != 'linux', 'Linux only')  # involves native absolute paths
    def test_can_query_running_kernel(self):
        vfstype_name_by_mountpoint = dlb_contrib.linux.get_mounted_filesystems()
        self.assertIn(dlb.fs.Path('/'), vfstype_name_by_mountpoint)
        self.assertTrue(all(p.is_absolute() for p in vfstype_name_by_mountpoint))
        self.assertTrue(all(p.is_dir() for p in vfstype_name_by_mountpoint))


class CpuInfoTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_is_correct_for_empty(self):
        os.mkdir('self')
        open('cpuinfo', 'xb').close()
        cpu_info = dlb_contrib.linux.get_cpu_info(proc_root_directory='.')
        self.assertEqual(0, cpu_info.cpu_count)

    def test_is_correct_for_typical(self):
        with open('cpuinfo', 'xb') as f:
            f.write(
                b'processor\t: 0\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3700.099\n'
                b'core id\t\t: 0\n'
                b'apicid\t\t: 0\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'

                b'processor\t: 1\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3700.003\n'
                b'core id\t\t: 1\n'
                b'apicid\t\t: 2\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
                
                b'processor\t: 2\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3700.034\n'
                b'core id\t\t: 2\n'
                b'apicid\t\t: 4\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
                
                b'processor\t: 3\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3699.999\n'
                b'core id\t\t: 3\n'
                b'apicid\t\t: 6\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
                
                b'processor\t: 4\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3700.160\n'
                b'core id\t\t: 0\n'
                b'apicid\t\t: 1\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
                
                b'processor\t: 5\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3700.058\n'
                b'core id\t\t: 1\n'
                b'apicid\t\t: 3\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
                
                b'processor\t: 6\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3700.011\n'
                b'core id\t\t: 2\n'
                b'apicid\t\t: 5\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
                
                b'processor\t: 7\n'
                b'model name\t: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n'
                b'cpu MHz\t\t: 3699.995\n'
                b'core id\t\t: 3\n'
                b'apicid\t\t: 7\n'
                b'bugs\t\t: cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit\n'
                b'power management:\n\n'
            )

        cpu_info = dlb_contrib.linux.get_cpu_info(proc_root_directory='.')

        self.assertEqual(8, cpu_info.cpu_count)

        self.assertEqual((
                (0, 1, 2, 3, 4, 5, 6, 7),
                (0, 4),
                (1, 5),
                (2, 6),
                (3, 7),
                (0,),
                (1,),
                (2,),
                (3,),
                (4,),
                (5,),
                (6,),
                (7,)
            ),
            cpu_info.maximum_cpu_index_sets
        )

        self.assertEqual({
                'processor': '6',
                'model name': 'Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz',
                'cpu MHz': '3700.011',
                'core id': '2',
                'apicid': '5',
                'bugs': 'cpu_meltdown spectre_v1 spectre_v2 spec_store_bypass l1tf mds swapgs taa itlb_multihit',
                'power management': None
            },
            cpu_info.by_cpu_index(6)
        )

        self.assertEqual({'apicid': '0', 'cpu MHz': '3700.099', 'processor': '0'},
                         cpu_info.by_maximum_cpu_index_set({0}))
        self.assertEqual({'core id': '0'}, cpu_info.by_maximum_cpu_index_set([4, 0]))
        self.assertEqual({}, cpu_info.by_maximum_cpu_index_set({1, 2, 3}))  # no exception

        self.assertEqual({'0': (0, 4), '1': (1, 5), '2': (2, 6), '3': (3, 7)}, cpu_info.by_key('core id'))

    def test_repr_is_sorted(self):
        with open('cpuinfo', 'xb') as f:
            f.write(
                b'processor\t: 0\n'
                b'cpu MHz\t\t: 3700.099\n'
                b'core id\t\t: 0\n'
                b'apicid\t\t: 0\n'
                b'power management:\n\n'
    
                b'processor\t: 1\n'
                b'cpu MHz\t\t: 3700.003\n'
                b'core id\t\t: 1\n'
                b'apicid\t\t: 2\n'
                b'power management:\n\n'
            )

        cpu_info = dlb_contrib.linux.get_cpu_info(proc_root_directory='.')
        s = (
            "CpuInfo({"
                "(0, 1): {'power management': None}, "
                "(0,): {'processor': '0', 'cpu MHz': '3700.099', 'core id': '0', 'apicid': '0'}, "
                "(1,): {'processor': '1', 'cpu MHz': '3700.003', 'core id': '1', 'apicid': '2'}"
            "})"
        )
        self.assertEqual(s, repr(cpu_info))

    def test_is_correct_for_single(self):
        with open('cpuinfo', 'xb') as f:
            f.write(
                b'processor\t: 0\n'
                b'cpu MHz\t\t: 3700.099\n'
            )

        cpu_info = dlb_contrib.linux.get_cpu_info(proc_root_directory='.')
        self.assertEqual(1, cpu_info.cpu_count)

    def test_fails_without_newline(self):
        with open('cpuinfo', 'xb') as f:
            f.write(b'processor\t: 0')

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.linux.get_cpu_info(proc_root_directory='.')
        self.assertEqual("unexpected key-value line: b'processor\\t: 0'", str(cm.exception))

    @unittest.skipIf(sys.platform != 'linux', 'Linux only')
    def test_can_query_running_kernel(self):
        cpu_info = dlb_contrib.linux.get_cpu_info()
        self.assertGreaterEqual(cpu_info.cpu_count, 1)

        value_by_key = cpu_info.by_cpu_index(cpu_info.cpu_count - 1)
        print(value_by_key)

        self.assertGreaterEqual(len(value_by_key), 1)
        key = sorted(value_by_key)[0]

        cpu_index_set_by_value = cpu_info.by_key(key)
        print(cpu_index_set_by_value)

        for maximum_cpu_index_set in cpu_info.maximum_cpu_index_sets:
            print('CPU {}:'.format(', '.join(str(i) for i in maximum_cpu_index_set)))
            value_by_key = cpu_info.by_maximum_cpu_index_set(maximum_cpu_index_set)
            for key in sorted(value_by_key):
                print(f'    {key!r}: {value_by_key[key]!r}')

        print(repr(cpu_info))
