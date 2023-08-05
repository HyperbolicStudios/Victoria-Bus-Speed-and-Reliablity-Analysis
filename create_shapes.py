import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
import time
from inspect import getsourcefile
from os.path import abspath

from shapely.geometry import LineString, Point, MultiPoint

from shapely.ops import split

import plotly.graph_objs as go


def generate_lines():
    
    all_lines = pd.DataFrame()

    routes = {26:60,
              95:0,
              15:0,
              4:0,
              70:0,
              2:300,
              27:100,
              11:100,
              14:100,
              7:100,
              21:100,
              6:100

    }

    routes_static = pd.read_csv("static/routes.csv")
    trips_static = pd.read_csv("static/trips.csv")
    shapes_static = pd.read_csv("static/shapes.csv")

    for route in routes.keys():
        #looking in routes_static what the route_id is for the route
        trip_num = routes[route]
        route_id = routes_static[routes_static["route_short_name"] == route].iloc[0]["route_id"]
        
        #looking in trips_static what the shape_id is for the route
        shape_id = trips_static[trips_static["route_id"] == route_id].iloc[trip_num]["shape_id"]
        
        shape = shapes_static[shapes_static["shape_id"] == shape_id]

        #turn into geopandas dataframe using shape_pt_lat and shape_pt_lon and set geographical CRS
        shape = gpd.GeoDataFrame(shape, geometry=gpd.points_from_xy(shape.shape_pt_lon, shape.shape_pt_lat))
        shape = shape.set_crs("EPSG:4326").to_crs("EPSG:26910")
        
        #shapes is a series of points, ordered by shape_pt_sequence. turn it into a line
        shape = shape.sort_values(by="shape_pt_sequence")
        line = LineString(shape["geometry"])
        
        length = line.length
        
        n = int(length/200)

        points = ([line.interpolate((i/n), normalized=True) for i in range(1, n)])

        #create lines from points
        line = []
        for i in range(0, len(points)-1):
            line.append(LineString([points[i], points[i+1]]))
        
        line = pd.DataFrame(line, columns=["geometry"])
        
        all_lines = gpd.GeoDataFrame(pd.concat([all_lines,line]), geometry="geometry")

    all_lines['buffer'] = all_lines.buffer(10,cap_style=2)
    all_lines['delete'] = False

    for i in range(1, len(all_lines)):
        #check if the ith line is COMPLETELY within the buffer of the i-1th line
        if all_lines.iloc[i].geometry.within(all_lines.iloc[i-1].buffer):
            #modify all_lines.delete to True for the ith line
            all_lines.at[i, 'delete'] = True

    all_lines = all_lines[all_lines['delete'] == False]
    all_lines = all_lines.drop(columns=['buffer', 'delete'])
    #turn to gdf
    all_lines = gpd.GeoDataFrame(all_lines, geometry="geometry")
    all_lines = all_lines.set_crs("EPSG:26910")

    return(all_lines)

def test():
    all_lines = generate_lines()
    #plot each line segment in a different color
    all_lines['colour'] = np.random.choice(range(0, 20), all_lines.shape[0])

    #plot by colour
    fig, ax = plt.subplots(figsize=(10,10))
    all_lines.plot(ax=ax, column='colour', cmap='tab20')
    plt.show()
    return

test()