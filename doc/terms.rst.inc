Terms
=====

.. glossary::

   run of dlb
      The execution of a part of a :term:`script` inside the same :term:`root context`.

   tool
      Describes the abstract behaviour and the way a tool is run by a sub class of :class:`dlb.ex.Tool`.

      It is concretized by instantiation.

   tool instance
      A (concrete) instance of an (abstract) :term:`tool` with concrete dependencies.

      Can be run in an active context with ``r = t.run()`` (once or multiple times), which happens sequentially in the
      following stages:

      #. start of execution: call of :meth:`t.run() <dlb.ex.Tool.run()>`.
      #. dynamic helper resolution:
         if this is the first instance of the tool being run in the :term:`active context`:
         find the absolute path of every :term:`dynamic helper` (e.g. executable) that might be needed during a
         redo of any instance of this tool and memorize it.
      #. redo check:
         decide whether a registered dependency required a redo by inspecting its state and memorize it if it does.
      #. if redo necessary:

         #. redo: generate all output dependencies.
         #. dependency finalization: update registered dependencies and their state ("memo") in the
            :term:`run-database`.

      #. end of execution:

         a) successful after awaiting on *r* has been completed or
         b) unsuccessful after exception has been risen.

      Between start and end of execution the tool instance is said to be *running*.

   dynamic helper
      An external filesystem object in the :term:`managed tree` or outside the :term:`working tree` with a path
      to be determined at run-time.

      A dynamic helper is identified by a relative path (non-directory or directory).

      Typical example: globally installed executable (e.g. compiler) with an absolute path determined by a search for
      the first match in the environment variable :envvar:`PATH`.

   redo
      The phase of the execution of a :term:`tool instance` *t* that generates all its output dependencies.

      A redo is considered necessary if at least one of the following statements is true:

      a) Any of the output dependencies of *t* does not exist in the expected form.
      b) Any of the input dependencies of *t* has changed its existence in the expected form since the start of
         the last known successful execution of *t*.
      c) Any of the input dependencies of *t* has changed a depended-upon property (e.g. filesystem attribute, value of
         environment variable) since the start of the last known successful execution of *t*.
      d) Any of the execution parameters *t* has changed since the start of the last known successful execution of *t*.

   redo miss
      A redo miss of a :term:`tool instance` is an undesirable situation that occurs when the :term:`redo` check
      considers a redo not necessary while it actually is.

      It is caused by bugs of dlb or external helpers and violations of assumptions (e.g. on the behaviour of the
      filesystem).

   context
      An (execution) context describes how running :term:`tool instances <tool instance>` shall interact with the
      execution environment outside the :term:`working tree` and with each other.

      It is represented as an instance of :class:`dlb.ex.Context` used as a context manager.

   active context
      The innermost :term:`context`, if any.

   root context
      The outermost :term:`context`, if any.

   script
      A Python program that potentially creates an :term:`active context` at least once.

   working tree
      The filesystem tree rooted at a directory (directly) containing a directory :file:`.dlbroot/`
      (a symbolic link to directory is not considered a directory here).

   management tree
      The filesystem tree rooted at :file:`.dlbroot/` in the root of the working tree.

      Do not modify its content manually unless you are told so by dlb.

   managed tree
      The filesystem tree rooted at at the root of the working tree without the management tree.
      Contains the files involved in the build that are to be managed by dlb.

      May and (typically will) be manually modified while there is no active context (e.g. by editing source files).

   mtime
      The time of last data modification of a filesystem object in the
      `sense of ISO 1003.1-2008 <https://pubs.opengroup.org/onlinepubs/009695399/functions/stat.html>`_.

   working tree time
      The time according to the :term:`mtime` of an imaginary filesystem object created at a certain instant
      (assuming a single filesystem).

   mtime update
      Setting the :term:`mtime` of a filesystem object to the current :term:`working tree time`.

   working tree's system time
      The system time used a source for every :term:`mtime update` of every filesystem object in the working tree
      (assuming there is one).

   effective mtime resolution
      The effective :term:`mtime` resolution for a filesystem object *p* is defined by the following
      thought experiment:

      - *p* is modified at :term:`ideal time` *t*, resulting in a :term:`mtime` *m* of *p*.
      - *p* is modified at :term:`ideal time` *t* + *dt*, resulting in a
        :term:`mtime` *m*  + *dm* of *p*.
      - The effective mtime resolution for *p* is the minimum *dm* > 0 for any pair of *t* and *dt* > 0.

      Resolution of timestamps for some filesystems: XFS: 1 ns, NTFS: 100 ns, ext2: 1 s, FAT32: 2 s.
      The effective mtime resolution depends also on the filesystem driver and the operating system, but it
      cannot be finer that the timestamp resolution of the filesystem.

   ideal time
      The (strictly increasing) physical time at the place the dlb process is running.

   non-upwards path
      A relative path that has no prefix denoting its parent directory.

      Examples: :file:`a/../b` is an non-upwards path, :file:`a/../../a/b` is not.

   collapsable path
      A path *p* of an existing filesystem object with the following property:
      No prefix path of *p'* that ends with a component other than :file:`..` is the path of a symbolic link,
      where *p'* is *p* with all :file:`.` components removed.

      Example: :file:`a/b/../c/..` is collapsable if and only if neither :file:`a/b/` nor :file:`a/b/../c` is a
      symbolic link.

   canonical-case path
      A path whose components are all exactly as listed in their parent directory.

      On a case-insensitive filesystem or directory, multiple paths that differ in case or character encoding can point
      to the same filesystem object. Only one of them is a canonical-case path.

   normal path
      A path without :file:`..` components.

   working tree path
      The :term:`normal path` of an existing filesystem object relative to the :term:`working tree`'s root.

   managed tree path
      A working tree path of file system object in the :term:`managed tree`.

   run-database
      The database in the :term:`management tree` that stores information on the current and past
      :term:`runs of dlb <run of dlb>`, primarily related to dependencies.

      Its removal (permitted when :term:`dlb is not running <run of dlb>`) typically leads to unnecessary
      :term:`redos <redo>` in the following two runs.

   true input dependency
      A true input dependency of a :term:`tool instance` *t* is an input of *t* that is not known to have been generated
      by a previous running :term:`tool instance` (in the current or a previous :term:`run of dlb`).

   redo-safe
      An action (e.g. a modification of the :term:`managed tree`) is said to be redo-safe if it cannot not lead to a
      :term:`redo miss` for any :term:`tool instance` in the current run or any future :term:`run of dlb`.

   benign managed tree modification
      A modification of the :term:`managed tree` is benign, if it consist only of an arbitrary number of the
      following actions in any order:

      - Remove or create a filesystem object
        (this includes symbolic links and hard links)
      - Write to a regular file

      Examples of modifications of the managed tree that are no benign managed tree modifications:

      - Replace a regular file by any other one with :command:`mv`
        (does not :term:`update mtime <mtime update>` of the target)
      - Swap two directories
      - Set the :term:`mtime` of a filesystem object to something different from the current working tree time