:mod:`dlb.di` --- Line-oriented hierarchical diagnostic messages
================================================================

.. module:: dlb.di
   :synopsis: Line-oriented hierarchical diagnostic messages

Output formatted indented printable ASCII lines to represent hierarchic diagnostic information.
It uses the level mechanism of the 'logging' module.
The filtering and destination is determined by the active context.

Example::

   import dlb.di
   ...

   with dlb.di.Cluster(f"analyze memory usage\n    note: see {logfile.as_string()!r} for details", is_progress=True):
      ram, rom, emmc = ...

      dlb.di.inform(
          f"""
          in use:
              RAM:\t {ram}\b kB
              ROM (NOR flash):\t {rom}\b kB
              eMMC:\t {emmc}\b kB
          """)

      if rom > 0.8 * rom_max:
          dlb.di.inform("more than 80 % of ROM used", logging.WARNING)

This will generated the following output:

.. code-block:: text

   I analyze memory usage...
     | note: see 'out/linker.log' for details
     I in use:
       | RAM:              12 kB
       | ROM (NOR flash): 108 kB
       | eMMC:            512 kB
     W more than 80 % of ROM used
     I done.
