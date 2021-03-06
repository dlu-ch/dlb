# Restrictions:
#
#   - Must only be interpreted by GNU make without the options -e, -k or -s
#   - /bin/sh must be a POSIX compliant shell
#   - The GNU utilities 'find', 'xargs', 'mkdir', 'mv', 'rm' must be in found in search path
#   - The system time must be monotonic during execution of GNU make
#   - The mtime of all target or source files must be in the past
#   - After a source dependency in a .c.o.d file is removed, the .c.o and .c.o.d files must be removed manually

.SUFFIXES:

SHELL=/bin/sh
GCC=gcc
FIND=find
MKDIR=mkdir
CP=cp
MV=mv
RM=rm

# functions are GNU Make specific: shell, sort, patsubst, subst, file
# ':=' is GNU Make specific
# variable value cannot hold NUL - use LF
source_files := $(shell $(FIND) -P src -name '*.c' -type f -exec build/print-makefile-safe-filename {} \;)
ifneq ($(.SHELLSTATUS), 0)
    $(error failed while looking for source files)
endif
source_files := $(sort $(source_files))
$(shell $(MKDIR) -p build/out/)
$(file >build/out/source_files.makevar.t,$(source_files))
$(shell build/replace-if-different build/out/source_files.makevar.t build/out/source_files.makevar)

object_files := $(patsubst src/%.c,build/out/src/%.c.o,$(source_files))
dependency_files := $(patsubst src/%.c,build/out/src/%.c.o.d,$(source_files))

# $(MAKEFILE_LIST), $(@D) are GNU Make specific
build/out/application: $(object_files) $(MAKEFILE_LIST) build/out/source_files.makevar
	unset -v LANG LC_CTYPE LC_MESSAGES LC_ALL TMPDIR GCC_COMPARE_DEBUG GCC_EXEC_PREFIX
	unset -v COMPILER_PATH LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH
	unset -v DEPENDENCIES_OUTPUT SUNPRO_DEPENDENCIES SOURCE_DATE_EPOCH
	$(MKDIR) -p -- $(@D)
	$(RM) -f -- $@
	echo > $@.ts
	$(GCC) -o $@.t $(object_files)
	$(CP) --attributes-only --preserve=timestamps -- $@.ts $@.t
	$(MV) -- $@.t $@

# static pattern rules are GNU Make specific
# $(MAKEFILE_LIST), $(@D) are GNU Make specific
$(object_files): build/out/src/%.c.o: src/%.c $(MAKEFILE_LIST)
	unset -v LANG LC_CTYPE LC_MESSAGES LC_ALL TMPDIR GCC_COMPARE_DEBUG GCC_EXEC_PREFIX
	unset -v COMPILER_PATH LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH
	unset -v DEPENDENCIES_OUTPUT SUNPRO_DEPENDENCIES SOURCE_DATE_EPOCH
	$(MKDIR) -p -- $(@D)
	$(RM) -f -- $@
	echo > $@.ts
	$(GCC) -x c -std=c99 -MMD -MT $@ -MF $@.d.t -o $@.t -c $<
	$(CP) --attributes-only --preserve=timestamps -- $@.ts $@.d.t
	$(CP) --attributes-only --preserve=timestamps -- $@.ts $@.t
	$(MV) -- $@.d.t $@.d
	$(MV) -- $@.t $@

# static pattern rules are GNU Make specific
$(dependency_files): build/out/src/%.c.o.d: build/out/src/%.c.o

include $(dependency_files)
