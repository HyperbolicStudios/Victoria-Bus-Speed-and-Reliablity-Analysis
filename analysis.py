import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from create_shapes import generate_lines

def retrieve_timeline():
    timeline = pd.read_csv("timeline.csv")

    #turn into geopandas dataframe based on x and y
    timeline = gpd.GeoDataFrame(timeline, geometry=gpd.points_from_xy(timeline.x, timeline.y))
    timeline = timeline.set_crs("EPSG:4326").to_crs("EPSG:26910")

    timeline = timeline[['Time', 'Speed', 'geometry']]

    return(timeline)

def aggregate_data():
    route_segments = generate_lines()
    print(len(route_segments))
    timeline = retrieve_timeline()
 
    #create a buffer around each line in lines, and create a new geodataframe with the buffers
    buffers = gpd.GeoDataFrame(geometry=route_segments.buffer(20, cap_style=2), crs="EPSG:26910")

    #convert timestamp to datetime
    timeline["Time"] = pd.to_datetime(timeline["Time"], utc=True, unit='s')
    #convert to PST
    timeline["Time"] = timeline["Time"].dt.tz_convert('America/Los_Angeles')

    timeline['Hour'] = timeline.Time.dt.hour
    
    buffers = buffers.reset_index()
    buffers['buffer_id'] = buffers.index

    #spatial merge. Find all the points that are within buffers, and retain buffer geometry.
    timeline = gpd.sjoin(buffers, timeline, how="left", predicate="intersects")
  
    print(len(timeline.buffer_id.unique()))
    timeline = timeline[["Hour", "Speed", "buffer_id", "geometry"]]

    #aggregate by Hour and buffer_id. Aggregate Speed to average and geometry to first
    timeline = timeline.groupby(["Hour", "buffer_id"]).agg({"Speed": "mean", "geometry": "first"}).reset_index()

    timeline = gpd.GeoDataFrame(timeline, geometry="geometry", crs="EPSG:26910")

    timeline = timeline.to_crs("WGS-84")
    print(len(timeline))

    timeline.Hour = timeline.Hour.round(0)
    timeline.Speed = timeline.Speed.round(0)

    timeline.to_file("analysis.geojson", driver="GeoJSON")

    return

aggregate_data()

