############
Installation
############
Install bd_warehouse from github:
----------------------------------------------

The recommended method for most users is to install bd_warehouse with one of the following two commands.

In Linux/MacOS, use the following command:

.. doctest::

	>>> python3 -m pip install git+https://github.com/gumyr/bd_warehouse

In Windows, use the following command:

.. doctest::

	>>> python -m pip install git+https://github.com/gumyr/bd_warehouse

If you receive errors about conflicting dependencies, you can retry the installation after having
upgraded pip to the latest version with the following command:

.. doctest::

	>>> python3 -m pip install --upgrade pip

If you use `poetry <https://python-poetry.org/>`_ to install bd_warehouse, you might need to specify
the branch that is used for git-based installs ; until quite recently, poetry used to checkout the
`master` branch when none was specified, and this fails on bd_warehouse that uses a `dev` branch.

Pip does not suffer from this issue because it correctly fetches the repository default branch.

If you are a poetry user, you can work around this issue by installing bd_warehouse in the following
way:

.. doctest::

	>>> poetry add git+https://github.com/gumyr/bd_warehouse.git@dev

Please note that always suffixing the URL with ``@dev`` is safe and will work with both older and
recent versions of poetry.

Development install of bd_warehouse:
----------------------------------------------
**Warning**: it is highly recommended to upgrade pip to the latest version before installing
bd_warehouse, especially in development mode. This can be done with the following command:

.. doctest::

	>>> python3 -m pip install --upgrade pip

Once pip is up-to-date, you can install bd_warehouse
`in development mode <https://setuptools.pypa.io/en/latest/userguide/development_mode.html>`_
with the following commands:

.. doctest::

	>>> git clone https://github.com/gumyr/bd_warehouse.git
	>>> cd bd_warehouse
	>>> python3 -m pip install -e .

Please substitute ``python3`` with ``python`` in the lines above if you are using Windows.

Test your bd_warehouse installation:
----------------------------------------------
If all has gone well, you can open a command line/prompt, and type:

.. doctest::

	>>> python
	>>> from bd_warehouse import *
	>>> print(Solid.make_box(1,2,3).show_topology(limit_class="Face"))

Which should return something similar to:

.. code::

		Solid        at 0x165e75379f0, Center(0.5, 1.0, 1.5)
		└── Shell    at 0x165eab056f0, Center(0.5, 1.0, 1.5)
			├── Face at 0x165b35a3570, Center(0.0, 1.0, 1.5)
			├── Face at 0x165e77957f0, Center(1.0, 1.0, 1.5)
			├── Face at 0x165b3e730f0, Center(0.5, 0.0, 1.5)
			├── Face at 0x165e8821570, Center(0.5, 2.0, 1.5)
			├── Face at 0x165e88218f0, Center(0.5, 1.0, 0.0)
			└── Face at 0x165eb21ee70, Center(0.5, 1.0, 3.0)
