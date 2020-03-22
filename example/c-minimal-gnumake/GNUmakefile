# Restrictions:
#
#   - Must only be interpreted by GNU make without the options -e, -k or -s
#   - The directory src/ must not contain regular files with names that end in '.c' and
#     contain white-space characters or ':' or ';'
#   - /bin/sh must be a POSIX compliant shell
#   - The GNU utilities 'find', 'mkdir', 'mv', 'rm' must be in found in search path
#   - The system time must be monotonic during execution of GNU make
#   - The mtime of all target or source files must be in the past

# https://pubs.opengroup.org/onlinepubs/009695399/utilities/make.html
#
#   Applications shall select target names from the set of characters consisting solely of periods,
#   underscores, digits, and alphabetics from the portable character set [...].
#   Implementations may allow other characters in target names as extensions.
#   The interpretation of targets containing the characters '%' and '"' is implementation-defined.

.SUFFIXES:

SHELL=/bin/sh
GCC=gcc
FIND=find
MKDIR=mkdir
MV=mv
RM=rm

# functions are GNU Make specific: sort, shell, patsubst
source_files := $(sort $(shell $(FIND) -P src -name '*.c' -type f))
object_files := $(patsubst src/%.c,build/out/src/%.c.o,$(source_files))
dependency_files := $(patsubst src/%.c,build/out/src/%.c.o.d,$(source_files))

# $(MAKEFILE_LIST), $(@D) are GNU Make specific
build/out/application: $(object_files) $(MAKEFILE_LIST)
	unset -v LANG LC_CTYPE LC_MESSAGES LC_ALL TMPDIR GCC_COMPARE_DEBUG GCC_EXEC_PREFIX
	unset -v COMPILER_PATH LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH
	unset -v DEPENDENCIES_OUTPUT SUNPRO_DEPENDENCIES SOURCE_DATE_EPOCH
	$(MKDIR) -p -- $(@D)
	$(RM) -f -- $@
	$(GCC) -o $@.t $(object_files)
	$(MV) -- $@.t $@

# static pattern rules are GNU Make specific
# $(MAKEFILE_LIST), $(@D) are GNU Make specific
$(object_files): build/out/src/%.c.o: src/%.c $(MAKEFILE_LIST)
	unset -v LANG LC_CTYPE LC_MESSAGES LC_ALL TMPDIR GCC_COMPARE_DEBUG GCC_EXEC_PREFIX
	unset -v COMPILER_PATH LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH
	unset -v DEPENDENCIES_OUTPUT SUNPRO_DEPENDENCIES SOURCE_DATE_EPOCH
	$(MKDIR) -p -- $(@D)
	$(RM) -f -- $@
	$(GCC) -x c -std=c99 -MMD -MT $@ -MF $@.d.t -o $@.t -c $<	
	$(MV) -- $@.d.t $@.d
	$(MV) -- $@.t $@

# static pattern rules are GNU Make specific
$(dependency_files): build/out/src/%.c.o.d: build/out/src/%.c.o

include $(dependency_files)
