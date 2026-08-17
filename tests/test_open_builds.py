"""Basic construction tests for the OpenBuilds parts and assemblies."""

import pytest
from bd_warehouse.open_builds import (
    AcmeAntiBacklashNutBlock8mm,
    AcmeAntiBacklashNutBlock8mmAssembly,
    AluminumSpacer,
    CBeamAssembly,
    CBeamCapped,
    CBeamEndAssembly,
    CBeamEndMount,
    CBeamGantryPlate,
    CBeamGantryPlateXLarge,
    CBeamLinearRail,
    CBeamLinearRailProfile,
    CBeamRiserPlate,
    EccentricSpacer,
    FlexibleCoupler,
    LBracket,
    LockCollar,
    MetricLeadScrew,
    RouterSpindleMount,
    ShimWasher,
    SpacerBlock,
    StepperMotor,
    TNut,
    VSlotLinearRail,
    VSlotLinearRailProfile,
    XLargeCBeamGantry,
    XtremeSolidVWheel,
    XtremeSolidVWheelAssembly,
    _VSlotGroove,
    _VSlotInternalCavity,
)


@pytest.mark.parametrize(
    "build_part",
    [
        AcmeAntiBacklashNutBlock8mm,
        AcmeAntiBacklashNutBlock8mmAssembly,
        lambda: AluminumSpacer("6mm"),
        lambda: CBeamAssembly(100),
        lambda: CBeamAssembly(100, end_plate=False),
        lambda: CBeamCapped(100),
        CBeamEndAssembly,
        CBeamEndMount,
        CBeamGantryPlate,
        CBeamGantryPlateXLarge,
        lambda: CBeamLinearRail(100),
        CBeamLinearRailProfile,
        CBeamRiserPlate,
        lambda: EccentricSpacer("6mm"),
        lambda: FlexibleCoupler("8mm"),
        LBracket,
        lambda: LockCollar("8mm"),
        lambda: MetricLeadScrew(100),
        RouterSpindleMount,
        lambda: ShimWasher("FlatWasher"),
        SpacerBlock,
        TNut,
        _VSlotGroove,
        _VSlotInternalCavity,
        VSlotLinearRailProfile,
        lambda: VSlotLinearRail("20x20", 100),
        XLargeCBeamGantry,
        XtremeSolidVWheel,
        lambda: XtremeSolidVWheelAssembly(False),
        lambda: StepperMotor("Nema17"),
    ],
)
def test_open_builds_classes_construct_geometry(build_part):
    """Every OpenBuilds class should construct a non-empty shape."""
    part = build_part()

    assert part.is_valid
    assert len(part.faces()) > 0
