![build123d, a parametric part collection](docs/assets/bd_title_image.png)

# bd_warehouse

build123d, a parametric part collection

If you've ever wondered about finding a better alternative to proprietary
software for mechanical CAD, consider exploring 
[Build123d](https://build123d.readthedocs.io/en/latest/), along with related
packages like [bd_warehouse](https://github.com/gumyr/bd_warehouse) and 
[cq_gears](https://github.com/meadiode/cq_gears). Build123d enhances the widely 
used Python programming language by adding powerful capabilities that enable the
creation of various mechanical designs using the same techniques employed in today's technology.

By incorporating **bd_warehouse** into **Build123d**, you gain access to on-demand
generation of parametric parts and extensions that expand the core capabilities
of Build123d. These resulting parts can be seamlessly integrated into your
projects or saved as CAD files in formats such as STEP or STL. This allows for
compatibility with a wide range of CAD, CAM, and analytical systems.

With just a few lines of code, you can create parametric parts that are easily
reviewable and version controlled using tools like [git](https://git-scm.com/) 
and [GitHub](https://github.com/).
Documentation can be automatically generated from the source code of your
designs, similar to the documentation you're currently reading. Additionally,
comprehensive test suites can automatically validate parts, ensuring that no
flaws are introduced during their lifecycle.

The benefits of adopting a full software development pipeline are numerous and
extend beyond the scope of this text. Furthermore, all these tools are
open-source, free to use, and customizable, eliminating the need for licenses.
Empower yourself by taking control of your CAD development tools.

The documentation for **bd_warehouse** can found at [bd_warehouse](https://bd-warehouse.readthedocs.io/en/latest/index.html).

There is a [***Discord***](https://discord.com/invite/Bj9AQPsCfx) server (shared with CadQuery) where you can ask for help in the build123d channel.

To install **bd_warehouse** from github:
```
python3 -m pip install git+https://github.com/gumyr/bd_warehouse
```
Development install
```
git clone https://github.com/gumyr/bd_warehouse.git
cd bd_warehouse
python3 -m pip install -e .
```
