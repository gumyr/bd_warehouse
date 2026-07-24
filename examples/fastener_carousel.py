import math
from build123d import *
from bd_warehouse.fastener import (
    Screw,
    Nut,
    DomedCapNut,
    HeatSetNut,
    HexNut,
    UnchamferedHexagonNut,
    SquareNut,
    Washer,
    ClearanceHole,
    InsertHole,
)

from ocp_vscode import show, set_defaults, Camera, show_all
from bd_materials.materials.metals import aluminum
from bd_materials.finishes import brushed, anodize

set_defaults(reset_camera=Camera.CENTER)

simple = False
metric_size = "M5-0.8"
imperial_size = "1/4-20"
screw_dict = Screw.select_by_size(metric_size)
imperial_screw_dict = Screw.select_by_size(imperial_size)
for cls, type_list in imperial_screw_dict.items():
    if cls in screw_dict.keys():
        screw_dict[cls].extend(type_list)
    else:
        screw_dict.update({cls: type_list})
nut_washer_dict = Nut.select_by_size(metric_size)
nut_washer_dict[HeatSetNut] = HeatSetNut.types()
nut_washer_dict.update(Washer.select_by_size(metric_size.split("-")[0]))
imperial_nut_washer_dict = Nut.select_by_size(imperial_size)
for cls, type_list in imperial_nut_washer_dict.items():
    if cls in nut_washer_dict.keys():
        nut_washer_dict[cls].extend(type_list)
    else:
        nut_washer_dict.update({cls: type_list})

# Create one of each type of screw and nut
screws: list[Screw] = []
for screw_class in screw_dict.keys():
    for screw_type in screw_dict[screw_class]:
        print(f"{screw_class.__name__}:{screw_type}")
        size = (
            metric_size if screw_class.sizes(screw_type)[0][0] == "M" else imperial_size
        )
        screw = screw_class(
            size=size, length=22 * MM, fastener_type=screw_type, simple=simple
        )
        screw.color = Color(0xC0C0C0)  # Silver
        screws.append(screw)

heatset_sizes = {
    "McMaster-Carr": "M5-0.8-Standard",
    "Hilitchi": "M5-0.8-10",
    "AE-SamZhihui": "M5-0.8-H6-D7",
    "ruthex": "M6-1-6.8",
    "CNCKitchen": "M5-0.8-9.5",
}
nuts_washers: list[Nut] = []
for nut_washer_class in nut_washer_dict.keys():
    for nut_washer_type in nut_washer_dict[nut_washer_class]:
        print(f"{nut_washer_class.__name__}:{nut_washer_type}")
        size_base = (
            metric_size
            if nut_washer_class.sizes(nut_washer_type)[0][0] == "M"
            else imperial_size
        )
        if nut_washer_class == HeatSetNut:
            size = heatset_sizes[nut_washer_type]
        elif issubclass(nut_washer_class, Washer):
            size = size_base.split("-")[0]
        else:
            size = size_base
        if issubclass(nut_washer_class, Washer):
            nut_washer = nut_washer_class(size=size, fastener_type=nut_washer_type)
        else:
            nut_washer = nut_washer_class(
                size=size, fastener_type=nut_washer_type, simple=simple
            )
        nut_washer.color = Color(0xC0C0C0)  # Silver
        nuts_washers.append(nut_washer)

# Calculate the size of the carousel such that there is room for all the screws in the
# perimeter with countersunk holes
screw_diameters = [screw.head_diameter for screw in screws]
total_diameters = sum(screw_diameters) + 20 * MM * len(screws)
disk_radius = total_diameters / (2 * math.pi)
disk_thickness = 20 * MM

with BuildPart() as carousel:
    Cylinder(disk_radius, disk_thickness, align=(Align.CENTER, Align.CENTER, Align.MAX))
    hole_locs = PolarLocations(disk_radius, len(screws)).locations
    for i, screw in enumerate(screws):
        with Locations(hole_locs[i]):
            ClearanceHole(screw, fit="Close", counter_sunk=True)
        screw.locate(screw.hole_locations[-1])  # Includes vertical offset

        if i < len(nuts_washers):
            nut_washer = nuts_washers[i]
            nut_location = (
                Location((0, 0, -disk_thickness), (1, 0, 0), 180) * hole_locs[i]
            )
            captive = nut_washer.__class__ in [
                DomedCapNut,
                HexNut,
                UnchamferedHexagonNut,
                SquareNut,
            ] and bool(i % 2)
            with Locations(nut_location):
                if nut_washer.__class__ == HeatSetNut:
                    InsertHole(nut_washer)
                else:
                    ClearanceHole(
                        nut_washer,
                        counter_sunk=bool(i % 2),
                        captive_nut=captive,
                    )
            nuts_washers[i].locate(nuts_washers[i].hole_locations[-1])

carousel.part.material = aluminum(finish=[brushed(), anodize("SeaGreen")])


with BuildSketch(Plane.XY.offset(0.01)) as top_labels:
    for i, screw in enumerate(screws):
        angle = i * (360 / len(screws))
        with PolarLocations(disk_radius - 15 * MM, 1, start_angle=angle + 0.5):
            Text(
                screw.__class__.__name__,
                font_size=5 * MM,
                align=(Align.MAX, Align.MIN),
            )
        with PolarLocations(disk_radius - 15 * MM, 1, start_angle=angle - 0.5):
            Text(
                screw.fastener_type,
                font_size=5 * MM,
                align=(Align.MAX, Align.MAX),
            )

with BuildSketch(-Plane.XY.offset(-disk_thickness - 0.01)) as bottom_labels:
    for i, nut_washer in enumerate(nuts_washers):
        angle = i * (360 / len(screws))
        with PolarLocations(disk_radius - 10 * MM, 1, start_angle=angle + 0.5):
            Text(
                nut_washer.__class__.__name__,
                font_size=5 * MM,
                align=(Align.MAX, Align.MIN),
            )
        with PolarLocations(disk_radius - 10 * MM, 1, start_angle=angle - 0.5):
            Text(
                nut_washer.fastener_type,
                font_size=5 * MM,
                align=(Align.MAX, Align.MAX),
            )

labels = Compound(children=top_labels.sketch.faces() + bottom_labels.sketch.faces())
labels.color = Color("White")

show(carousel.part, screws, nuts_washers, labels)
full_carousel = Compound(children=[carousel.part, labels] + screws + nuts_washers)
export_gltf(full_carousel, "carousel.glb", angular_deflection=1, binary=True)
