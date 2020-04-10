# Plot data collected by build-with-dlb-and-scons-and-make.bash.
# Run in the directory of the script.
#
# Input: build/result.txt
# Output: build/*.svg

import re
import os.path
import matplotlib.pyplot as plt
import matplotlib.pylab

build_dir_path = 'build/'
result_file_path = os.path.join(build_dir_path, 'result.txt')


matplotlib.pylab.rcParams.update({
    'figure.titlesize': 'medium',
    'axes.titlesize': 'medium'
})


def safe_fig(fig, name):
    fig.set_size_inches(*[m / 24.3e-3 for m in [200e-3, 150e-3]])
    fig.savefig(os.path.join(build_dir_path, f'benchmark-{name}.svg'), format='svg', transparent=True)


description_by_tool = {}
durations_by_configuration = {}
with open(result_file_path, 'r') as result_file:
    for line in result_file:
        line = line.strip()
        if line[:1] == '#':
            m = re.fullmatch(r'# dlb version: ([0-9a-z.+]+)\.', line)
            if m:
                description_by_tool['dlb'] = f'dlb {m.group(1)}'
                continue
            m = re.fullmatch(r'# GNU Make ([0-9a-z.]+).*', line)
            if m:
                description_by_tool['make'] = f'GNU Make {m.group(1)}'
                continue
            m = re.fullmatch(r'# SCons .* v([0-9][0-9a-z.]+).*', line)
            if m:
                v = m.group(1)
                if len(v) > 10:
                    v = f'{v[:15]}...'
                description_by_tool['scons'] = f'SCons {v}'
                continue
            raise ValueError(f'unexpected comment line: {line!r}')

        fields = line.split(' ')
        tool_name, number_of_libraries, number_of_classes_per_library = fields[:3]
        configuration = tool_name, int(number_of_libraries), int(number_of_classes_per_library)
        if len(fields) > 3:
            t0, t1, t2, tpartial = [float(f) for f in fields[3:]]
            durations_by_configuration[configuration] = t0, t1, t2, tpartial
        else:
            durations_by_configuration[configuration] = None  # failed

description_by_tool['make2'] = '{}\n(complete)'.format(description_by_tool['make'])
description_by_tool['make'] = '{}\n+ makedepend (simplistic)'.format(description_by_tool['make'])
description_by_tool['dlb2'] = '{}\n(5 source files\nper tool instance)'.format(description_by_tool['dlb'])

tools = ['make', 'make2', 'dlb2', 'dlb', 'scons']  # as used in file *result_file_path*
colormap = plt.get_cmap("tab10")
style_by_tool = {
    'make': (colormap(2), '-', 'x', 'none'),
    'make2': (colormap(2), '-', 'v', 'full'),
    'dlb': (colormap(0), '-', 'o', 'full'),
    'dlb2': (colormap(0), '-', 'o', 'none'),
    'scons': (colormap(1), '-', 's', 'full')
}


# vary number_of_classes_per_library

fig, axs = plt.subplots(2, 2, gridspec_kw={'hspace': 0})
number_of_libraries = 3
ncls = set(ncls for (t, nlib, ncls), v in durations_by_configuration.items())
fig.suptitle(f'{number_of_libraries} static libraries with {min(ncls)} to {max(ncls)} C++ source files each')

for tool in tools:
    line_color, line_style, marker, marker_fillstyle = style_by_tool[tool]
    
    # full build (maximum of first two runs)
    x, y = zip(*[
        (ncls, max(v[0], v[1]))
        for (t, nlib, ncls), v in durations_by_configuration.items()
        if v and nlib == number_of_libraries and t == tool
    ])
    axs[0][0].plot(x, y, label=tool, color=line_color, linestyle=line_style,
                   marker=marker, fillstyle=marker_fillstyle)
    axs[0][0].grid()
    axs[0][0].set_xticklabels([])
    axs[1][0].semilogy(x, y, label=tool, color=line_color, linestyle=line_style,
                       marker=marker, fillstyle=marker_fillstyle)
    axs[1][0].grid(which='both')
    axs[0][0].set_title('full build\n(each source file compiled, linked)')
    axs[1][0].set_xlabel('number of source files per library')
    axs[1][0].set_ylabel('duration (s)')

    # partial build, vary number_of_classes_per_library
    x, y = zip(*[
        (ncls, v[3])
        for (t, nlib, ncls), v in durations_by_configuration.items()
        if v and nlib == 3 and t == tool
    ])
    axs[0][1].plot(x, y, label=tool, color=line_color, linestyle=line_style,
                   marker=marker, fillstyle=marker_fillstyle)
    axs[0][1].grid()
    axs[0][1].set_xticklabels([])
    axs[0][1].yaxis.tick_right()
    axs[1][1].semilogy(x, y, label=tool, color=line_color, linestyle=line_style,
                       marker=marker, fillstyle=marker_fillstyle)
    axs[1][1].grid(which='both')
    axs[0][1].set_title(f'partial build\n(after one source file has been changed)')
    axs[1][1].set_xlabel('number of source files per library')
    axs[1][1].set_ylabel('duration (s)')
    axs[1][1].yaxis.tick_right()
    axs[1][1].yaxis.set_label_position("right")

axs[0][1].legend([description_by_tool[t] for t in tools], fancybox=True, framealpha=0.5)

safe_fig(fig, '1')


# vary number_of_libraries

fig, axs = plt.subplots(2, 2, gridspec_kw={'hspace': 0})
number_of_classes_per_library = 100
nlib = set(nlib for (t, nlib, ncls), v in durations_by_configuration.items())
fig.suptitle(f'{min(nlib)} to {max(nlib)} static libraries with {number_of_classes_per_library} C++ source files each')

for tool in style_by_tool:
    line_color, line_style, marker, marker_fillstyle = style_by_tool[tool]

    # full build (first run)
    x, y = zip(*[
        (nlib, v[0])
        for (t, nlib, ncls), v in durations_by_configuration.items()
        if v and ncls == number_of_classes_per_library and t == tool
    ])
    axs[0][0].plot(x, y, label=tool, color=line_color, linestyle=line_style,
                   marker=marker, fillstyle=marker_fillstyle)
    axs[0][0].grid()
    axs[0][0].set_xticklabels([])
    axs[1][0].semilogy(x, y, label=tool, color=line_color, linestyle=line_style,
                       marker=marker, fillstyle=marker_fillstyle)
    axs[1][0].grid(which='both')
    axs[0][0].set_title('full build\n(each source file compiled, linked)')
    axs[1][0].set_xlabel('number of libraries')
    axs[1][0].set_ylabel('duration (s)')

    # partial build, vary number_of_classes_per_library
    x, y = zip(*[
        (nlib, v[3])
        for (t, nlib, ncls), v in durations_by_configuration.items()
        if v and ncls == number_of_classes_per_library and t == tool
    ])
    axs[0][1].plot(x, y, label=tool, color=line_color, linestyle=line_style,
                   marker=marker, fillstyle=marker_fillstyle)
    axs[0][1].grid()
    axs[0][1].set_xticklabels([])
    axs[0][1].yaxis.tick_right()
    axs[1][1].semilogy(x, y, label=tool, color=line_color, linestyle=line_style,
                       marker=marker, fillstyle=marker_fillstyle)
    axs[1][1].grid(which='both')
    axs[0][1].set_title('partial build\n(after one source file has been changed)')
    axs[1][1].set_xlabel('number of libraries')
    axs[1][1].set_ylabel('duration (s)')
    axs[1][1].yaxis.tick_right()
    axs[1][1].yaxis.set_label_position("right")

axs[0][1].legend([description_by_tool[t] for t in tools], fancybox=True, framealpha=0.5)

safe_fig(fig, '2')
