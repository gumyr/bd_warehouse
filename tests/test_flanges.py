import random
from typing import Literal, get_args
from itertools import product
import inspect
import pytest
from bd_warehouse.flange import (
    Flange,
    LappedFlangeStub,
    WeldNeckFlange,
    Nps,
    FaceType,
    FlangeClass,
)
from build123d import *

valid_flanges = []
for flange_type, flange_size, face_type, flange_cls in product(
    Flange.__subclasses__(), get_args(Nps), get_args(FaceType), get_args(FlangeClass)
):
    if not isinstance(flange_type, LappedFlangeStub):
        try:
            flange_type.get_face_section_data(flange_size, flange_cls, face_type)
            valid_flanges.append((flange_type, flange_size, flange_cls, face_type))
        except:
            pass

print(len(valid_flanges))
print(valid_flanges[0])


@pytest.mark.parametrize(
    "flange_type, flange_size, flange_class, face_type",
    random.sample(valid_flanges, 20),
)
def test_flanges(
    flange_type: Flange,
    flange_size: Nps,
    flange_class: FlangeClass,
    face_type: FaceType,
):
    print(flange_type)
    print(f"{type(flange_size)=}, {flange_size}")
    print(f"{type(flange_class)=}, {flange_class}")
    print(f"{type(face_type)=}, {face_type}")
    if "face_type" in inspect.signature(flange_type.__init__).parameters:
        flange: Flange = flange_type(
            nps=flange_size,
            flange_class=flange_class,
            face_type=face_type,
        )
    else:
        flange: Flange = flange_type(nps=flange_size, flange_class=flange_class)

    # Check that flange properties are created


if __name__ == "__main__":
    test_flanges(WeldNeckFlange, "12", 300, "Ring")
