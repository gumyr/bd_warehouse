"""
Aluminum extrusions

name: aluminum_extrusions.py
by:   Alex Verschoot
date: December 27, 2025

desc:
    This python module is a CAD library of parametric aluminum extrions. 
    They are mostly based on manufacturer provided data.

"""

from build123d import Align, BasePartObject, BuildLine, BuildPart, BuildSketch, Circle, Color, DimensionLine, ExtensionLine, Face, Location, Mode, Polyline, RectangleRounded, FilletPolyline, RotationLike, ShapeList, extrude, make_face, pi, sin, sqrt, cos
from build123d import Draft
import csv
import bd_warehouse # type: ignore
import importlib.resources

from sympy import false, true


class AluminiumExtrusion(BasePartObject):
    def __init__(
        self,
        length:float,
        extrusion_type: str = "Item24 Profile 5 20x20",
        rotation: RotationLike = (0, 0, 0),
        align: tuple[Align, Align] = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
    ):
        with BuildPart() as extrusion:
            extrude(to_extrude=self.getExtrusionFace(extrusion_type), amount=length)
        super().__init__(part=extrusion.part, rotation=rotation, align=align, mode=mode) # pyright: ignore[reportArgumentType]

    @staticmethod
    def getExtrusionFace(extrusion_type: str) -> Face:  
        extrusionData = AluminiumExtrusion.getExtrusionData()
        with BuildSketch() as mainSketch:
            # Base rectangle
            RectangleRounded(
                width=float(extrusionData[extrusion_type]['width']), 
                height=float(extrusionData[extrusion_type]['height']), 
                radius=float(extrusionData[extrusion_type]['corner_radius']) 
            )
            Circle(radius=float(extrusionData[extrusion_type]['hole_dia'])/2, mode=Mode.SUBTRACT) 
            
            # Add grooves
            groove_placements: list[tuple[tuple[float, float], float]] = [ 
                ((0, -float(extrusionData[extrusion_type]['height']) / 2), 0),
                ((0,  float(extrusionData[extrusion_type]['height']) / 2), 180),
                ((-float(extrusionData[extrusion_type]['width']) / 2, 0), -90),
                (( float(extrusionData[extrusion_type]['width']) / 2, 0), 90),
            ]
            for (x, y), rot in groove_placements: 
                with BuildLine(Location((x, y, 0), angle=rot)) as grooves:
                    AluminiumExtrusion.getGrooveGeometry(extrusion_type)
                make_face(edges=grooves.edges(), mode=Mode.SUBTRACT)
        return mainSketch.face()

    @staticmethod
    def getGrooveGeometry(extrusion_type: str) -> FilletPolyline:
        extrusionData = AluminiumExtrusion.getExtrusionData()
        points: list[tuple[float, float]] = []
        radii: list[float] = []

        # Extra start in line with the profile to make easy entry fillet
        points.append((float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, -1))
        radii.append(0)
        points.append((float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, 0))
        radii.append(0)

        # The real figure starts
        points.append((float(extrusionData[extrusion_type]['flange_opening']) / 2, 0))
        radii.append(float(extrusionData[extrusion_type]['flange_neck_top_radius']))
        points.append((float(extrusionData[extrusion_type]['flange_opening']) / 2, float(extrusionData[extrusion_type]['flange_thickness'])))
        radii.append(float(extrusionData[extrusion_type]['flange_neck_bottom_radius']))
        points.append((float(extrusionData[extrusion_type]['flange_max_width']) / 2, float(extrusionData[extrusion_type]['flange_thickness'])))
        radii.append(float(extrusionData[extrusion_type]['flange_top_radius']))
        if float(extrusionData[extrusion_type]['flange_offset']) > 0:
            points.append((float(extrusionData[extrusion_type]['flange_max_width']) / 2, float(extrusionData[extrusion_type]['flange_thickness']) + float(extrusionData[extrusion_type]['flange_offset'])))
            radii.append(0)
        points.append((float(extrusionData[extrusion_type]['flange_bottom_width']) / 2, float(extrusionData[extrusion_type]['flange_depth'])))
        radii.append(float(extrusionData[extrusion_type]['flange_bottom_radius']))
        if float(extrusionData[extrusion_type]['flange_notch_width']) > 0:
            points.append((float(extrusionData[extrusion_type]['flange_notch_width']) / 2, float(extrusionData[extrusion_type]['flange_depth'])))
            radii.append(0)
            points.append((0, float(extrusionData[extrusion_type]['flange_depth']) + float(extrusionData[extrusion_type]['flange_notch_depth'])))
            radii.append(0)
            points.append((-float(extrusionData[extrusion_type]['flange_notch_width']) / 2, float(extrusionData[extrusion_type]['flange_depth'])))
            radii.append(0)
        points.append((-float(extrusionData[extrusion_type]['flange_bottom_width']) / 2, float(extrusionData[extrusion_type]['flange_depth'])))
        radii.append(float(extrusionData[extrusion_type]['flange_bottom_radius']))
        if float(extrusionData[extrusion_type]['flange_offset']) > 0:
            points.append((-float(extrusionData[extrusion_type]['flange_max_width']) / 2, float(extrusionData[extrusion_type]['flange_thickness']) + float(extrusionData[extrusion_type]['flange_offset'])))
            radii.append(0)
        points.append((-float(extrusionData[extrusion_type]['flange_max_width']) / 2, float(extrusionData[extrusion_type]['flange_thickness'])))
        radii.append(float(extrusionData[extrusion_type]['flange_top_radius']))
        points.append((-float(extrusionData[extrusion_type]['flange_opening']) / 2, float(extrusionData[extrusion_type]['flange_thickness'])))
        radii.append(float(extrusionData[extrusion_type]['flange_neck_bottom_radius']))
        points.append((-float(extrusionData[extrusion_type]['flange_opening']) / 2, 0))
        radii.append(float(extrusionData[extrusion_type]['flange_neck_top_radius']))

        # The real figure ends
        points.append((-float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, 0))
        radii.append(0)
        points.append((-float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, -1))
        radii.append(0)
        
        return FilletPolyline(points, radius=radii, close=True, mode=Mode.ADD)
    
    @staticmethod
    def getDimensionedExtrusionFace(extrusion_type:str, labels:bool)->Face|ShapeList[Face]:  
        extrusionData = AluminiumExtrusion.getExtrusionData()
        extrusion_face: Face = AluminiumExtrusion.getExtrusionFace(extrusion_type) 
        newFace = extrusion_face 
        draft = Draft(font_size=1, extension_gap=0, line_width=0.1, pad_around_text=0.5,arrow_length=1)
        width =  ExtensionLine(
                border=[
                    (-float(extrusionData[extrusion_type]['width'])/2, float(extrusionData[extrusion_type]['height'])/2, 0.1),
                    (float(extrusionData[extrusion_type]['width'])/2, float(extrusionData[extrusion_type]['height'])/2, 0.1)
                ],
                offset=-float(extrusionData[extrusion_type]['height'])*1/4, 
                draft=draft,
                label="width" if labels else None
            )
        newFace += width
        height =  ExtensionLine(
                border=[
                    (float(extrusionData[extrusion_type]['width'])/2, -float(extrusionData[extrusion_type]['height'])/2,0.1),
                    (float(extrusionData[extrusion_type]['width'])/2, float(extrusionData[extrusion_type]['height'])/2,0.1)
                ],
                offset=float(extrusionData[extrusion_type]['width'])*1/4, 
                draft=draft,
                label="height" if labels else None
            )
        newFace += height
        corner_radius =  DimensionLine(
                path=[
                    (float(extrusionData[extrusion_type]['width'])/2-float(extrusionData[extrusion_type]['corner_radius']), 
                     float(extrusionData[extrusion_type]['height'])/2-float(extrusionData[extrusion_type]['corner_radius']),
                     0.1),
                    (float(extrusionData[extrusion_type]['width'])/2-float(extrusionData[extrusion_type]['corner_radius'])+sin(pi/4)*float(extrusionData[extrusion_type]['corner_radius']), 
                     float(extrusionData[extrusion_type]['height'])/2-float(extrusionData[extrusion_type]['corner_radius'])+sin(pi/4)*float(extrusionData[extrusion_type]['corner_radius']),
                     0.1) #a little bit higher, so it would be visible over the other arrows
                ],
                draft=draft,
                arrows=(false, true),
                label="corner_radius" if labels else None
            )
       #corner_radius.color = Color(0,0,0)
        newFace += corner_radius
        hole_dia =  DimensionLine(
                path=[
                    (0.0, 
                     -float(extrusionData[extrusion_type]['hole_dia'])/2,
                     0.1),
                    (0.0, 
                     float(extrusionData[extrusion_type]['hole_dia'])/2,
                     0.1) #a little bit higher, so it would be visible over the figure
                ],
                draft=draft,
                arrows=(true, true),
                label="hole_dia" if labels else None
            )
       #corner_radius.color = Color(0,0,0)
        newFace += hole_dia
        

        return newFace 
    
    @staticmethod
    def getDimensionedGroove(extrusion_type:str, labels:bool): 
        extrusionData = AluminiumExtrusion.getExtrusionData()

        with BuildSketch() as grooves:
            with BuildLine() as groovesRaw:
                AluminiumExtrusion.getGrooveGeometry(extrusion_type)
            make_face(edges=groovesRaw.edges(), mode=Mode.ADD)
            
            with BuildLine() as groovesCorrection:
                #remove the groove helper part
                points: list[tuple[float, float]] = []
                points.append((float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, -1))
                points.append((float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, 0))
                points.append((-float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, 0))
                points.append((-float(extrusionData[extrusion_type]['flange_opening']) * 3 / 4, -1))
                Polyline(points, close=true)
            make_face(edges=groovesCorrection.edges(), mode=Mode.SUBTRACT)

        draft = Draft(font_size=0.5, extension_gap=0, line_width=0.05, pad_around_text=0.1,arrow_length=0.3)
        newFace = grooves.face() 

        flange_opening =  ExtensionLine(
                border=[
                    (-float(extrusionData[extrusion_type]['flange_opening'])/2, 0,0),
                    (float(extrusionData[extrusion_type]['flange_opening'])/2, 0,0)
                ],
                offset=float(extrusionData[extrusion_type]['flange_opening'])*1/4, 
                draft=draft,
                label="flange_opening" if labels else None
            )
        flange_opening.color=Color("black")
        newFace += flange_opening

        flange_neck_top_radius = DimensionLine(
                path=[
                    (float(extrusionData[extrusion_type]['flange_opening'])/2+float(extrusionData[extrusion_type]['flange_neck_top_radius'])+sin(5*pi/4)*float(extrusionData[extrusion_type]['flange_neck_top_radius']), 
                     float(extrusionData[extrusion_type]['flange_neck_top_radius'])+sin(5*pi/4)*float(extrusionData[extrusion_type]['flange_neck_top_radius']),
                     0.1) #a little bit higher, so it would be visible over the other arrows
                    ,(float(extrusionData[extrusion_type]['flange_opening'])/2+5,#-float(extrusionData[extrusion_type]['flange_neck_top_radius']), 
                     2, #random value to get nice looking angle on the dimension
                     0.1)
                ],
                draft=draft,
                arrows=(true, false),
                label="flange_neck_top_radius" if labels else None
            )
        newFace += flange_neck_top_radius

        return newFace

    @staticmethod
    def getExtrusionData() -> dict[str, dict[str, float | str]]: 
        extrusionData:dict[str, dict[str, float | str]] = {}
        
        with importlib.resources.files(bd_warehouse).joinpath("data/aluminum_extrusions.csv").open("r") as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)  # skip the header row
            for row in reader:
                if len(row) == 0:  # skip blank rows
                    continue
                name, width, height, corner_radius, hole_dia, flange_thickness, flange_opening, flange_bottom_width, flange_max_width, flange_offset, flange_depth, flange_bottom_radius, flange_neck_top_radius, flange_neck_bottom_radius, flange_top_radius, flange_notch_width,flange_notch_depth, source = row

                extrusionData[name] = {}
                extrusionData[name]['width'] = float(width)
                extrusionData[name]['height'] = float(height)
                extrusionData[name]['corner_radius'] = float(corner_radius)
                extrusionData[name]['hole_dia'] = float(hole_dia)
                extrusionData[name]['flange_thickness'] = float(flange_thickness)
                extrusionData[name]['flange_opening'] = float(flange_opening)
                extrusionData[name]['flange_bottom_width'] = float(flange_bottom_width)
                extrusionData[name]['flange_max_width'] = float(flange_max_width)
                extrusionData[name]['flange_offset'] = float(flange_offset)
                extrusionData[name]['flange_depth'] = float(flange_depth)
                extrusionData[name]['flange_bottom_radius'] = float(flange_bottom_radius)
                extrusionData[name]['flange_neck_top_radius'] = float(flange_neck_top_radius)
                extrusionData[name]['flange_neck_bottom_radius'] = float(flange_neck_bottom_radius)
                extrusionData[name]['flange_top_radius'] = float(flange_top_radius)
                extrusionData[name]['flange_notch_width'] = float(flange_notch_width)
                extrusionData[name]['flange_notch_depth'] = float(flange_notch_depth)
                extrusionData[name]['source'] = source
        return extrusionData




if __name__ == "__main__":
    from ocp_vscode import show_all # type: ignore

    #Misumi_HFS5_2020 = AluminiumExtrusion(extrusion_type='Misumi HFS5-2020', length=50.0)
    #Item24_Profile_5_20x20 = AluminiumExtrusion(extrusion_type='Item24 Profile 5 20x20', length=50.0).move(Location([30,0,0]))
    name ='Misumi HFS5-2020'
    #faceWithLabels = AluminiumExtrusion.getDimensionedExtrusionFace(name, labels=true) 
    #faceWithDims = AluminiumExtrusion.getDimensionedExtrusionFace(name, labels=false)
    #for face in faceWithDims:
    #    face.move(Location([30,0,0]))
    groove = AluminiumExtrusion.getDimensionedGroove(name, labels=true)



    show_all()